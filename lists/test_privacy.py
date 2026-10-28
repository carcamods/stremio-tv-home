"""Core invariant (ADR 0004): the published lists contain catalog data only.

Runs the whole builder (collect + write_addon) against a fake Trakt account whose answers carry a planted
private value in every field that isn't catalog data, and fails if any of them reaches the output, if a
list left out by lists.json shows up, or if a title, row or manifest carries a field beyond the allowed
ones. Then runs the job as the builder workflow does (build.py twice over one state folder, the second time
keeping a failed list's last titles) and checks every file cloudflare.py would upload. Never weaken this
test. When the builder learns a new list kind or field, add what Trakt returns for it below with private
values; LeaksAreCaught proves the checks still fire.
"""

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import build
import cloudflare

WORKFLOW = Path(__file__).with_name("builder") / "publish-lists.yml"

SECRETS = [
    "SECRET-ACCESS-TOKEN",
    "SECRET-REFRESH-TOKEN",
    "SECRET-CLIENT-ID",
    "PRIVATE-USERNAME",
    "PRIVATE-REAL-NAME",
    "PRIVATE-NOTE",
    "PRIVATE-AVATAR",
    "PRIVATE-LOCATION",
    "PRIVATE-ABOUT",
    "PRIVATE-LIST-DESCRIPTION",
    "PRIVATE-SMART-FILTER",
    "PRIVATE-SHARE-LINK",
    # Lists that lists.json leaves out must not appear at all.
    "EXCLUDED-OWN-LIST",
    "EXCLUDED-LIKED-LIST",
]
ALLOWED_META = {"id", "type", "name", "poster", "releaseInfo", "genres", "description"}
ALLOWED_MANIFEST = {
    "id",
    "version",
    "name",
    "description",
    "resources",
    "types",
    "idPrefixes",
    "catalogs",
    "behaviorHints",
}
ALLOWED_CATALOG = {"type", "id", "name", "extra"}
ME = {
    "username": "PRIVATE-USERNAME",
    "name": "PRIVATE-REAL-NAME",
    "private": True,
    "vip": False,
    "ids": {"slug": "PRIVATE-USERNAME", "uuid": "PRIVATE-USERNAME"},
    "images": {"avatar": {"full": "PRIVATE-AVATAR"}},
    "location": "PRIVATE-LOCATION",
    "about": "PRIVATE-ABOUT",
}


def movie(n):
    return {
        "title": f"Movie {n}",
        "year": 2020,
        "released": "2020-01-01",
        "genres": ["drama"],
        "overview": "A film.",
        "ids": {"trakt": 100 + n, "slug": f"movie-{n}", "imdb": f"tt10000{n:02d}", "tmdb": 500 + n},
    }


def show(n):
    return {
        "title": f"Show {n}",
        "year": 2021,
        "first_aired": "2021-01-01T00:00:00.000Z",
        "aired_episodes": 8,
        "ids": {"trakt": 200 + n, "slug": f"show-{n}", "imdb": f"tt20000{n:02d}", "tvdb": 700 + n},
    }


def item(kind, entry):
    # What list endpoints return around each title: who added it, notes, when.
    return {
        "rank": 1,
        "id": 9,
        "listed_at": "2026-01-01T00:00:00.000Z",
        "notes": "PRIVATE-NOTE",
        "type": kind,
        kind: entry,
        "user": ME,
    }


def a_list(name, slug, trakt_id, privacy, user=ME):
    # What Trakt returns for a list: its owner, description, privacy, share link.
    return {
        "name": name,
        "description": "PRIVATE-LIST-DESCRIPTION",
        "privacy": privacy,
        "share_link": "https://trakt.tv/lists/PRIVATE-SHARE-LINK",
        "display_numbers": False,
        "sort_by": "rank",
        "sort_how": "asc",
        "user": user,
        "ids": {"slug": slug, "trakt": trakt_id},
    }


class FakeTrakt:
    client_id = "SECRET-CLIENT-ID"
    token = {"access_token": "SECRET-ACCESS-TOKEN", "refresh_token": "SECRET-REFRESH-TOKEN"}

    def get(self, path, auth=True, **query):
        if path.startswith("/sync/watchlist"):
            return [item("movie", movie(1)), item("show", show(1))]
        if path.startswith("/recommendations/movies"):
            return [dict(movie(2), user=ME, favorited_by=[ME])]
        if path.startswith("/recommendations/shows"):
            return [dict(show(2), user=ME, favorited_by=[ME])]
        if path == "/users/me/smart-lists":
            smart = a_list("Netflix", "netflix", 1, "private")
            smart["filters"] = {"query": "PRIVATE-SMART-FILTER"}
            return [dict(smart, created_at="2026-01-01")]
        if path.startswith("/smart-lists/"):
            return [item("movie", movie(3)), item("show", show(3))]
        if path == "/users/me/lists":
            return [
                a_list("Mine", "mine", 2, "private"),
                a_list("EXCLUDED-OWN-LIST", "excluded-own", 4, "private"),
            ]
        if path == "/users/me/likes/lists":
            owner = {"username": "listowner", "ids": {"slug": "listowner"}, "location": "PRIVATE-LOCATION"}
            return [
                {"liked_at": "2026-01-01", "list": a_list("Liked", "liked", 3, "friends", owner)},
                {"liked_at": "2026-01-01", "list": a_list("EXCLUDED-LIKED-LIST", "excluded-liked", 5, "public", owner)},
            ]
        if path.startswith("/users/"):
            return [item("movie", movie(4)), item("show", show(4))]
        raise AssertionError(f"unexpected Trakt call {path}")


CONFIG = {
    "addon_id": "io.github.test.tvlists",
    "name": "Test Lists",
    "description": "d",
    "country": "us",
    "max_items": 50,
    "catalogs": [
        {"kind": "watchlist", "name": "Watchlist", "released_only": False},
        {"kind": "recommendations", "media": "movies", "name": "Recommended Movies"},
        {"kind": "recommendations", "media": "shows", "name": "Recommended Series"},
        {"kind": "smart_lists"},
        {"kind": "personal_lists", "exclude": ["excluded-own"]},
        {"kind": "liked_lists", "exclude": ["listowner/excluded-liked"]},
        {"kind": "list", "user": "someone", "list": "42", "name": "Public list"},
    ],
}


def leaks(site):
    """Everything in the published files that isn't catalog data."""
    found = []
    files = [p for p in site.rglob("*") if p.is_file()]
    for path in files:
        text = path.read_text(encoding="utf-8")
        found += [f"{secret} in {path.relative_to(site)}" for secret in SECRETS if secret in text]
    manifest = json.loads((site / "manifest.json").read_text(encoding="utf-8"))
    found += [f"manifest field {k}" for k in set(manifest) - ALLOWED_MANIFEST]
    for cat in manifest["catalogs"]:
        found += [f"catalog field {k}" for k in set(cat) - ALLOWED_CATALOG]
    for path in (site / "catalog").rglob("*.json"):
        for meta in json.loads(path.read_text(encoding="utf-8"))["metas"]:
            found += [f"title field {k} in {path.relative_to(site)}" for k in set(meta) - ALLOWED_META]
    return found


def build_site(tmp):
    catalogs, _ = build.collect(FakeTrakt(), CONFIG)
    site = Path(tmp) / "site"
    build.write_addon(site, CONFIG, catalogs)
    return site, catalogs


def job_paths():
    """(lists.json, state folder, uploaded folder) as the builder workflow passes them."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    config, state = re.search(r"build\.py --config (\S+) --state (\S+)", workflow).groups()
    return config, state, re.search(r"cloudflare\.py --site (\S+)", workflow)[1]


def run_job(tmp, upload=None):
    """Runs build.py's main() twice in the folder tmp, as the workflow does, and returns what the files
    cloudflare.py would upload leak. The Trakt sign-in has expired, so the job renews it into the state
    folder. Before the second run an older release left a private field in the watchlist's file, and the
    watchlist then fails, so its last titles are kept. upload: the folder handed to cloudflare.py, if not
    the workflow's."""
    config, state, site = job_paths()
    job = Path(tmp)
    (job / config).write_text(json.dumps(CONFIG), encoding="utf-8")
    sign_in = {"access_token": "SECRET-ACCESS-TOKEN", "refresh_token": "SECRET-REFRESH-TOKEN", "expires_in": 604800}
    failing = []

    def request(self, method, path, body=None, auth=True, query=None):
        if path == "/oauth/token":
            return dict(sign_in, created_at=int(time.time()))
        if any(path.startswith(f) for f in failing):
            raise RuntimeError(f"{method} {path} -> HTTP 502: fake")
        return FakeTrakt().get(path, auth, **(query or {}))

    env = {"TRAKT_CLIENT_ID": "SECRET-CLIENT-ID", "TRAKT_TOKEN_JSON": json.dumps(dict(sign_in, created_at=1))}
    argv = ["build.py", "--config", str(job / config), "--state", str(job / state)]
    with (
        mock.patch.object(build.Trakt, "request", request),
        mock.patch.dict(os.environ, env),
        mock.patch.object(sys, "argv", argv),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        build.main()
        watchlist = job / site / "catalog" / build.CATALOG_TYPE / "watchlist.json"
        page = json.loads(watchlist.read_text(encoding="utf-8"))
        page["metas"][0]["notes"] = "PRIVATE-NOTE"
        watchlist.write_text(json.dumps(page), encoding="utf-8")
        failing.append("/sync/watchlist")
        build.main()
    _, uploaded = cloudflare.asset_manifest(job / (upload or site), "K" * 32)
    found = []
    for path in uploaded.values():
        text = path.read_text(encoding="utf-8")
        found += [f"{secret} in uploaded {path.name}" for secret in SECRETS if secret in text]
    return found + leaks(job / site)


class PublishedListsContainCatalogDataOnly(unittest.TestCase):
    def setUp(self):
        # No network: every show counts as aired in Cinemeta.
        patcher = mock.patch.object(build.Released, "_aired_in_cinemeta", lambda self, imdb: True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_nothing_private_in_the_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            site, catalogs = build_site(tmp)
            self.assertEqual(len(catalogs), 7)
            self.assertEqual(leaks(site), [])


class TheJobUploadsCatalogDataOnly(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(build.Released, "_aired_in_cinemeta", lambda self, imdb: True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_nothing_private_is_uploaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run_job(tmp), [])
            # The renewed sign-in really was written next to the uploaded folder.
            token = Path(tmp) / job_paths()[1] / "trakt-token.json"
            self.assertIn("SECRET-REFRESH-TOKEN", token.read_text(encoding="utf-8"))


class LeaksAreCaught(unittest.TestCase):
    """The checks above fire when the builder leaks (ADR 0004): each case injects one leak on purpose."""

    def setUp(self):
        patcher = mock.patch.object(build.Released, "_aired_in_cinemeta", lambda self, imdb: True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def assertLeaks(self):
        with tempfile.TemporaryDirectory() as tmp:
            site, _ = build_site(tmp)
            self.assertNotEqual(leaks(site), [])

    def test_an_extra_title_field(self):
        to_meta = build.to_meta

        def leaky(entry, kind):
            meta = to_meta(entry, kind)
            return meta and dict(meta, slug=entry["ids"]["slug"])

        with mock.patch.object(build, "to_meta", leaky):
            self.assertLeaks()

    def test_private_text_in_a_row_name(self):
        real_get = FakeTrakt.get

        def leaky(self, path, auth=True, **query):
            answer = real_get(self, path, auth, **query)
            if path == "/users/me/likes/lists":
                for like in answer:
                    like["list"]["name"] += " " + like["list"]["description"]
            return answer

        with mock.patch.object(FakeTrakt, "get", leaky):
            self.assertLeaks()

    def test_an_excluded_list(self):
        catalogs = [e for e in CONFIG["catalogs"] if e["kind"] != "personal_lists"] + [{"kind": "personal_lists"}]
        with mock.patch.dict(CONFIG, catalogs=catalogs):
            self.assertLeaks()

    def test_an_extra_manifest_field(self):
        write_json = build.write_json

        def leaky(path, data):
            if path.name == "manifest.json":
                data = dict(data, contactEmail="x")
            write_json(path, data)

        with mock.patch.object(build, "write_json", leaky):
            self.assertLeaks()

    def test_the_state_folder_uploaded(self):
        # As if the workflow handed cloudflare.py the state folder, which holds the Trakt sign-in.
        with tempfile.TemporaryDirectory() as tmp:
            self.assertNotEqual(run_job(tmp, upload=job_paths()[1]), [])

    def test_a_private_field_kept_from_the_last_run(self):
        with mock.patch.object(build, "META_FIELDS", (*build.META_FIELDS, "notes")):
            with tempfile.TemporaryDirectory() as tmp:
                self.assertNotEqual(run_job(tmp), [])


if __name__ == "__main__":
    unittest.main()
