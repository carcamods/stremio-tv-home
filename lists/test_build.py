"""Offline tests for build.py (no Trakt, no network): python -m unittest discover -s lists"""

import http.client
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build

EXAMPLE = Path(__file__).with_name("lists.example.json")


def movie(n):
    return {"title": f"Movie {n}", "year": 2020, "released": "2020-01-01", "ids": {"imdb": f"tt90000{n:02d}"}}


class FakeTrakt:
    """A Trakt account with two own lists, three liked lists and three Smart lists. Paths containing any of
    `fail` answer with an error."""

    def __init__(self, fail=()):
        self.fail = fail

    def get(self, path, auth=True, **query):
        if any(f in path for f in self.fail):
            raise RuntimeError(f"GET {path} -> HTTP 404: fake")
        if path == "/users/me/lists":
            return [
                {"name": "Own A", "ids": {"slug": "own-a", "trakt": 1}},
                {"name": "Own B", "ids": {"slug": "own-b", "trakt": 2}},
            ]
        if path == "/users/me/likes/lists":
            return [
                {"list": {"name": f"Liked {c}", "ids": {"slug": f"{c}-list", "trakt": n}, "user": {"ids": {"slug": c}}}}
                for n, c in ((11, "a"), (12, "b"), (13, "c"))
            ]
        if path == "/users/me/smart-lists":
            return [
                {"name": f"Smart {n}", "created_at": f"2026-0{n}", "ids": {"slug": f"s{n}", "trakt": n}}
                for n in (1, 2, 3)
            ]
        return [{"type": "movie", "movie": movie(1)}]


CONFIG = {
    "addon_id": "io.github.test.tvlists",
    "name": "Test Lists",
    "description": "d",
    "country": "us",
    "max_items": 50,
    "catalogs": [{"kind": "watchlist"}, {"kind": "smart_lists"}, {"kind": "personal_lists"}, {"kind": "liked_lists"}],
}


def names(catalogs):
    return [name for _, name, _ in catalogs]


class ToMeta(unittest.TestCase):
    def test_show_becomes_series_with_imdb_id(self):
        meta = build.to_meta(
            {
                "title": "Show",
                "year": 2024,
                "ids": {"imdb": "tt1234567"},
                "genres": ["science-fiction", "drama"],
                "overview": "x" * 600,
            },
            "show",
        )
        self.assertEqual(meta["type"], "series")
        self.assertEqual(meta["id"], "tt1234567")
        self.assertEqual(meta["releaseInfo"], "2024")
        self.assertEqual(meta["genres"], ["Science Fiction", "Drama"])
        self.assertEqual(len(meta["description"]), 500)
        self.assertIn("tt1234567", meta["poster"])

    def test_without_imdb_id_is_skipped(self):
        self.assertIsNone(build.to_meta({"title": "No id", "ids": {}}, "movie"))

    def test_unwrap_list_item(self):
        self.assertEqual(build.unwrap({"type": "movie", "movie": {"title": "M"}}), ("movie", {"title": "M"}))
        self.assertEqual(build.unwrap({"title": "S"}, "show"), ("show", {"title": "S"}))


class Released(unittest.TestCase):
    def setUp(self):
        self.r = build.Released()
        self.r.today = "2026-06-15"
        self.r.year = 2026

    def test_movies_by_release_date(self):
        self.assertTrue(self.r.ok("movie", {"released": "2026-06-15"}, "tt1"))
        self.assertFalse(self.r.ok("movie", {"released": "2026-06-16"}, "tt1"))
        self.assertTrue(self.r.ok("movie", {"year": 2019}, "tt1"))
        self.assertFalse(self.r.ok("movie", {"year": 2026}, "tt1"))

    def test_shows_by_cinemeta_then_trakt(self):
        self.r.series = {"tt1": True, "tt2": False, "tt3": None}
        self.assertTrue(self.r.ok("show", {}, "tt1"))
        self.assertFalse(self.r.ok("show", {"aired_episodes": 10}, "tt2"))
        # Cinemeta couldn't be asked: Trakt's own count decides.
        self.assertTrue(self.r.ok("show", {"aired_episodes": 3}, "tt3"))
        self.assertFalse(self.r.ok("show", {"aired_episodes": 0}, "tt3"))

    def test_shows_known_to_have_aired_are_not_asked_again(self):
        r = build.Released(["tt1"])
        with mock.patch.object(build.Released, "_aired_in_cinemeta", side_effect=AssertionError("asked")):
            r.prefetch([("show", {"ids": {"imdb": "tt1"}})])
        self.assertEqual(r.aired(), ["tt1"])

    def test_a_dropped_connection_to_cinemeta_is_not_fatal(self):
        for error in (
            http.client.RemoteDisconnected("closed"),
            ConnectionResetError(),
            http.client.IncompleteRead(b""),
            OSError("timed out"),
        ):
            with mock.patch("urllib.request.urlopen", side_effect=error):
                self.assertIsNone(self.r._aired_in_cinemeta("tt1"), repr(error))


class TraktRequests(unittest.TestCase):
    def test_network_errors_are_retried_then_reported_as_list_errors(self):
        trakt = build.Trakt("FAKE-CLIENT-ID", {"access_token": "FAKE"}, None)
        with mock.patch("urllib.request.urlopen", side_effect=http.client.RemoteDisconnected("closed")) as urlopen:
            with mock.patch("time.sleep"), self.assertRaises(RuntimeError):
                trakt.get("/sync/watchlist")
        self.assertEqual(urlopen.call_count, 6)


class NewestToken(unittest.TestCase):
    def token(self, created_at):
        return {"access_token": "A", "refresh_token": "R", "created_at": created_at, "expires_in": 604800}

    def test_the_newer_sign_in_wins_and_is_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "trakt-token.json"
            # First run: only the secret.
            self.assertEqual(build.newest_token(path, json.dumps(self.token(100)))["created_at"], 100)
            self.assertEqual(json.loads(path.read_text())["created_at"], 100)
            # The job's own copy was renewed since: it is newer than the secret.
            path.write_text(json.dumps(self.token(200)))
            self.assertEqual(build.newest_token(path, json.dumps(self.token(100)))["created_at"], 200)
            # A new sign-in with connect.py: the secret is newer.
            self.assertEqual(build.newest_token(path, json.dumps(self.token(300)))["created_at"], 300)
            self.assertEqual(json.loads(path.read_text())["created_at"], 300)

    def test_a_broken_secret_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trakt-token.json"
            path.write_text(json.dumps(self.token(200)))
            self.assertEqual(build.newest_token(path, "")["created_at"], 200)
            self.assertEqual(build.newest_token(path, "not json")["created_at"], 200)
            path.unlink()
            with self.assertRaises(SystemExit):
                build.newest_token(path, '{"access_token": "only"}')


class CheckConfig(unittest.TestCase):
    def test_the_example_is_valid_once_its_placeholder_is_replaced(self):
        example = json.loads(EXAMPLE.read_text())
        self.assertEqual(
            build.check_config(example), ['"addon_id": replace YOUR-GITHUB-USER with your GitHub user name']
        )
        example["addon_id"] = example["addon_id"].replace("YOUR-GITHUB-USER", "someone")
        self.assertEqual(build.check_config(example), [])

    def test_mistakes_are_found_before_trakt_is_read(self):
        self.assertIn('"catalogs" is missing', build.check_config({k: v for k, v in CONFIG.items() if k != "catalogs"}))
        bad = dict(
            CONFIG,
            country="usa",
            catalogs=[{"kind": "list", "user": "x", "list": "y"}, {"kind": "recommendations"}, {"kind": "nope"}],
        )
        problems = build.check_config(bad)
        self.assertEqual(len(problems), 4, problems)

    def test_options_are_checked_too(self):
        # Each of these used to run and quietly do something else.
        bad = dict(
            CONFIG,
            max_items=True,
            catalogs=[
                {"kind": "watchlist", "sort": "added desc"},
                {"kind": "personal_lists", "exclude": "Old list"},
                {"kind": "liked_lists", "released_only": "false"},
                {"kind": "list", "user": "someone", "list": "lists/42", "name": "X"},
            ],
        )
        problems = build.check_config(bad)
        self.assertEqual(len(problems), 5, problems)


class Collect(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(build.Released, "_aired_in_cinemeta", lambda self, imdb: True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_one_failing_list_does_not_stop_the_others(self):
        catalogs, fresh = build.collect(FakeTrakt(fail=["/users/a/", "/smart-lists/1/", "/users/me/lists/1/"]), CONFIG)
        self.assertEqual(names(catalogs), ["Watchlist", "Smart 2", "Smart 3", "Own B", "Liked b", "Liked c"])
        self.assertEqual(fresh, 6)

    def test_a_failing_list_keeps_its_last_titles(self):
        previous = {"list-a-11": ("Liked a", [{"id": "tt1"}]), "mine-own-a": ("Own A", [{"id": "tt2"}])}
        catalogs, _ = build.collect(FakeTrakt(fail=["/users/a/", "/users/me/lists/1/"]), CONFIG, previous)
        self.assertEqual(
            names(catalogs),
            ["Watchlist", "Smart 1", "Smart 2", "Smart 3", "Own A", "Own B", "Liked a", "Liked b", "Liked c"],
        )
        self.assertIn(("list-a-11", "Liked a", [{"id": "tt1"}]), catalogs)

    def test_a_failing_kind_keeps_its_last_rows_in_place(self):
        previous = {"smart-s1": ("Smart 1", []), "smart-s9": ("Smart 9", []), "watchlist": ("Watchlist", [])}
        catalogs, _ = build.collect(FakeTrakt(fail=["/users/me/smart-lists"]), CONFIG, previous)
        self.assertEqual(names(catalogs)[:3], ["Watchlist", "Smart 1", "Smart 9"])

    def test_a_row_left_out_stays_out_when_its_kind_fails(self):
        # The person excludes a list, and that run can't read their lists: the excluded row isn't kept.
        previous = {"mine-own-a": ("Own A", []), "mine-own-b": ("Own B", []), "list-c-13": ("Liked c", [])}
        config = dict(
            CONFIG,
            catalogs=[
                {"kind": "personal_lists", "exclude": ["own-a"]},
                {"kind": "liked_lists", "exclude": ["Liked c"]},
            ],
        )
        catalogs, _ = build.collect(FakeTrakt(fail=["/users/me/"]), config, previous)
        self.assertEqual(names(catalogs), ["Own B"])

    def test_nothing_read_is_reported(self):
        _, fresh = build.collect(FakeTrakt(fail=["/"]), CONFIG, {"watchlist": ("Watchlist", [])})
        self.assertEqual(fresh, 0)

    def test_exclude_takes_names_slugs_and_user_slug(self):
        config = dict(
            CONFIG,
            catalogs=[
                {"kind": "personal_lists", "exclude": ["own-a"]},
                {"kind": "liked_lists", "exclude": ["a-list", "Liked b", "c/c-list"]},
            ],
        )
        self.assertEqual(names(build.collect(FakeTrakt(), config)[0]), ["Own B"])


class WriteAddon(unittest.TestCase):
    CONFIG = {"addon_id": "io.github.test.tvlists", "name": "Test <Lists>", "description": "d"}

    def test_pages_manifest_and_install_page(self):
        metas = [{"id": f"tt{i:07d}", "type": "movie", "name": str(i)} for i in range(250)]
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            build.write_addon(site, self.CONFIG, [("watchlist", "Watchlist", metas)])
            base = site / "catalog" / build.CATALOG_TYPE
            self.assertEqual(len(json.loads((base / "watchlist.json").read_text())["metas"]), 100)
            self.assertEqual(len(json.loads((base / "watchlist" / "skip=200.json").read_text())["metas"]), 50)
            self.assertEqual(json.loads((site / "manifest.json").read_text())["catalogs"][0]["id"], "watchlist")
            page = (site / "index.html").read_text()
            self.assertIn("Test &lt;Lists&gt;", page)
            self.assertNotIn("https://", page)  # the link comes from the address the page is opened at
            self.assertEqual(build.load_previous(site), {"watchlist": ("Watchlist", metas)})
            self.assertFalse(site.with_name("site.new").exists())

    def test_version_changes_only_with_the_rows_and_keeps_growing(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"

            def version():
                return json.loads((site / "manifest.json").read_text())["version"]

            def parts(v):
                return tuple(int(x) for x in v.split("."))

            build.write_addon(site, self.CONFIG, [("watchlist", "Watchlist", [])])
            first = version()
            self.assertGreater(parts(first), (1, 0, 99))  # above the old 1.0.N versions
            build.write_addon(site, self.CONFIG, [("watchlist", "Watchlist", [{"id": "tt1"}])])
            self.assertEqual(version(), first)  # same rows: Stremio sees no update
            build.write_addon(site, self.CONFIG, [("watchlist", "Watchlist", []), ("x", "X", [])])
            self.assertGreater(parts(version()), parts(first))  # a new row: a newer version, even within a second
        self.assertEqual(build.next_version({"version": "9999.1.1"}, []), "9999.1.2")

    def test_split_sort(self):
        self.assertEqual(build.split_sort(None, "rank,asc"), ("rank", "asc"))
        self.assertEqual(build.split_sort("released,desc", "rank,asc"), ("released", "desc"))
        self.assertEqual(build.split_sort("title", "rank,asc"), ("title", "asc"))


if __name__ == "__main__":
    unittest.main()
