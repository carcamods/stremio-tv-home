#!/usr/bin/env python3
"""Builds a static, list-only Stremio addon from a Trakt account.

Reads the Trakt account (watchlist, recommendations, Smart lists, personal and liked lists) plus the
public lists in lists.json, and writes manifest.json, one JSON file per catalog page and an install page
into <state>/site, which cloudflare.py then serves at the person's private link. Stremio and TV Home only
download these files, so nothing has to keep running.

The state folder is kept between runs (the Actions cache): the Trakt sign-in, the lists published last
time (a list Trakt can't return keeps its last titles) and the shows known to have aired.

Standard library only, so the GitHub Action needs no installs.

    TRAKT_CLIENT_ID=<id> python lists/build.py --config lists/lists.json --state .state
"""

import argparse
import concurrent.futures
import html
import http.client
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.trakt.tv"
# Must equal a redirect URI of the Trakt app (the setup guide says http://localhost); the token refresh
# call requires it even though the device sign-in itself never redirects.
REDIRECT_URI = "http://localhost"
CINEMETA_SERIES = "https://v3-cinemeta.strem.io/meta/series/{}.json"
USER_AGENT = "stremio-tv-home-lists/1.0"
POSTER = "https://api.ratingposterdb.com/t0-free-rpdb/imdb/poster-default/{}.jpg?fallback=true"
CATALOG_TYPE = "trakt"  # mixed movies + shows, like the Trakt Tv addon
PAGE_SIZE = 100
REFRESH_MARGIN_S = 2 * 24 * 3600  # refresh the 7-day access token when less than 2 days are left
TOKEN_KEYS = ("access_token", "refresh_token", "created_at", "expires_in")
KINDS = ("watchlist", "recommendations", "smart_lists", "personal_lists", "liked_lists", "list")
# The fields a published title may have (ADR 0004). to_meta builds them one by one; rows kept from the last run
# are cut down to them, whatever an older release left in the files.
META_FIELDS = ("id", "type", "name", "poster", "releaseInfo", "genres", "description")
SORT = re.compile(r"[a-z_]+(,(asc|desc))?")
SLUG = re.compile(r"[^/\s?#]+")  # a Trakt user or list, as one piece of a URL path


class Trakt:
    def __init__(self, client_id, token, token_path):
        self.client_id = client_id
        self.token = token
        self.token_path = token_path

    def request(self, method, path, body=None, auth=True, query=None):
        """JSON answer of a Trakt call. Retries rate limits, server and network errors; anything else, or
        still failing after the retries, raises RuntimeError."""
        url = API + path + ("?" + urllib.parse.urlencode(query) if query else "")
        headers = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": self.client_id,
            "User-Agent": USER_AGENT,
        }
        if auth:
            headers["Authorization"] = "Bearer " + self.token["access_token"]
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(6):
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    raw = resp.read()
                return json.loads(raw) if raw else None
            except urllib.error.HTTPError as e:
                if e.code == 429 or e.code >= 500:
                    wait = int(e.headers.get("Retry-After") or 2**attempt)
                    time.sleep(min(max(wait, 1), 60))
                    continue
                detail = e.read()[:300].decode(errors="replace")
                raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from None
            except (OSError, http.client.HTTPException, ValueError) as e:
                # Timeouts, dropped connections, a cut-off answer.
                if attempt == 5:
                    raise RuntimeError(f"{method} {path}: {e!r}") from None
                time.sleep(2**attempt)
        raise RuntimeError(f"{method} {path}: still failing after retries")

    def get(self, path, auth=True, **query):
        return self.request("GET", path, auth=auth, query={k: v for k, v in query.items() if v is not None} or None)

    def ensure_fresh_token(self, force=False):
        expires_at = self.token["created_at"] + self.token["expires_in"]
        if not force and time.time() < expires_at - REFRESH_MARGIN_S:
            return
        body = {
            "refresh_token": self.token["refresh_token"],
            "client_id": self.client_id,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "refresh_token",
        }
        new_token = self.request("POST", "/oauth/token", body=body, auth=False)
        # Refresh tokens are single-use: save the new pair before anything else can fail.
        self.token_path.write_text(json.dumps(new_token))
        self.token = new_token
        print("Trakt sign-in renewed")


def parse_token(text):
    """A Trakt sign-in from JSON text, or None if the text isn't one."""
    try:
        token = json.loads(text)
    except ValueError:
        return None
    return token if isinstance(token, dict) and all(k in token for k in TOKEN_KEYS) else None


def newest_token(path, secret):
    """The newest Trakt sign-in: the job's own copy in the state folder, or the TRAKT_TOKEN_JSON secret when
    that is newer (the first run, or a new sign-in with connect.py). Saved to the state folder."""
    saved = parse_token(path.read_text()) if path.exists() else None
    given = parse_token(secret) if secret else None
    if secret and given is None:
        print("! The TRAKT_TOKEN_JSON secret isn't a Trakt sign-in; ignoring it")
    candidates = [t for t in (saved, given) if t]
    if not candidates:
        sys.exit("No Trakt sign-in. Run connect.py with --trakt (see lists/README.md).")
    token = max(candidates, key=lambda t: t["created_at"])
    if token is not saved:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(token))
    return token


class Released:
    """Keeps only released titles: movies whose release date has passed, and shows with at least one aired
    episode in Cinemeta, the episode list Stremio shows. Smart lists sorted newest first start with titles
    a service has announced but not released yet, and with new shows Cinemeta doesn't list yet."""

    def __init__(self, known_aired=()):
        now = time.gmtime()
        self.today = time.strftime("%Y-%m-%d", now)
        self.now_iso = time.strftime("%Y-%m-%dT%H:%M:%S", now)
        self.year = now.tm_year
        # imdb id -> True / False, or None when Cinemeta couldn't be asked. Shows that have aired stay aired,
        # so the ones known from earlier runs aren't asked again.
        self.series = dict.fromkeys(known_aired, True)

    def aired(self):
        return sorted(imdb for imdb, ok in self.series.items() if ok)

    def _aired_in_cinemeta(self, imdb):
        req = urllib.request.Request(CINEMETA_SERIES.format(imdb), headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                videos = (json.loads(resp.read()).get("meta") or {}).get("videos") or []
        except urllib.error.HTTPError as e:
            return False if e.code == 404 else None
        except (OSError, http.client.HTTPException, ValueError, AttributeError):
            return None
        return any((v.get("released") or "9") < self.now_iso for v in videos)

    def prefetch(self, pairs):
        todo = {(entry.get("ids") or {}).get("imdb") for kind, entry in pairs if kind == "show"}
        todo = [imdb for imdb in todo if imdb and imdb not in self.series]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for imdb, ok in zip(todo, pool.map(self._aired_in_cinemeta, todo)):
                self.series[imdb] = ok

    def ok(self, kind, entry, imdb):
        if kind == "movie":
            released = entry.get("released")
            return released <= self.today if released else bool(entry.get("year")) and entry["year"] < self.year
        aired = self.series.get(imdb)
        return aired if aired is not None else (entry.get("aired_episodes") or 0) > 0


def split_sort(sort, default):
    by, _, how = (sort or default).partition(",")
    return by, how or "asc"


def unwrap(item, kind=None):
    """(kind, movie or show) from a Trakt list item, or from a bare movie/show when kind is given."""
    if kind is not None:
        return kind, item
    kind = item.get("type")
    return kind, item.get(kind) or {}


def to_meta(entry, kind):
    """Trakt movie or show -> Stremio meta preview. Items without an IMDb id can't open in Stremio: skipped."""
    imdb = (entry.get("ids") or {}).get("imdb")
    if kind not in ("movie", "show") or not imdb:
        return None
    meta = {
        "id": imdb,
        "type": "series" if kind == "show" else "movie",
        "name": entry.get("title") or imdb,
        "poster": POSTER.format(imdb),
    }
    if entry.get("year"):
        meta["releaseInfo"] = str(entry["year"])
    genres = [g.replace("-", " ").title() for g in entry.get("genres") or []][:3]
    if genres:
        meta["genres"] = genres
    if entry.get("overview"):
        meta["description"] = entry["overview"][:500]
    return meta


def check_config(config):
    """What's wrong in lists.json, found before Trakt is read (an empty list when nothing is)."""
    if not isinstance(config, dict):
        return ["it must be a JSON object"]
    problems = [
        f'"{key}" is missing'
        for key in ("addon_id", "name", "description", "country", "max_items", "catalogs")
        if key not in config
    ]
    if problems:
        return problems
    country = config["country"]
    if not (isinstance(country, str) and len(country) == 2 and country.isalpha()):
        problems.append('"country" must be a two-letter code, such as "us"')
    if "YOUR-GITHUB-USER" in str(config["addon_id"]):
        problems.append('"addon_id": replace YOUR-GITHUB-USER with your GitHub user name')
    max_items = config["max_items"]
    if isinstance(max_items, bool) or not isinstance(max_items, int) or max_items < 1:
        problems.append('"max_items" must be a whole number above 0')
    if not isinstance(config["catalogs"], list) or not config["catalogs"]:
        return [*problems, '"catalogs" must be a list of rows']
    for n, entry in enumerate(config["catalogs"], start=1):
        kind = entry.get("kind") if isinstance(entry, dict) else None
        where = f"catalogs entry {n}"
        if kind not in KINDS:
            problems.append(f'{where}: "kind" must be one of {", ".join(KINDS)}')
        elif kind == "recommendations" and (entry.get("media") not in ("movies", "shows") or not entry.get("name")):
            problems.append(f'{where} (recommendations): needs "media" ("movies" or "shows") and a "name"')
        elif kind == "list" and not all(entry.get(k) for k in ("user", "list", "name")):
            problems.append(f'{where} (list): needs "user", "list" and "name"')
        elif kind == "list" and not all(SLUG.fullmatch(str(entry[k])) for k in ("user", "list")):
            problems.append(f'{where} (list): "user" and "list" are parts of the list address, without "/"')
        if not isinstance(entry, dict):
            continue
        sort = entry.get("sort")
        if sort is not None and not (isinstance(sort, str) and SORT.fullmatch(sort)):
            problems.append(f'{where}: "sort" must be a field, a comma and asc or desc, such as "added,desc"')
        if not isinstance(entry.get("released_only", True), bool):
            problems.append(f'{where}: "released_only" must be true or false, without quotes')
        exclude = entry.get("exclude", [])
        if not (isinstance(exclude, list) and all(isinstance(x, str) for x in exclude)):
            problems.append(f'{where}: "exclude" must be a list of names, such as ["Old list"]')
    return problems


def collect(trakt, config, previous=None, released=None):
    """Returns ([(catalog id, name, [metas])] in the order of lists.json, number of lists read from Trakt).

    A list Trakt can't return this time keeps its last published titles, taken from previous
    ({catalog id: (name, [metas])}), so a passing error doesn't remove a row from Stremio."""
    previous = previous or {}
    released = released or Released()
    limit = config["max_items"]
    country = config["country"]
    explicit = {f"list-{e['user']}-{e['list']}" for e in config["catalogs"] if e["kind"] == "list"}
    catalogs = []
    seen = set()
    fresh = 0

    def add(cid, name, items, kind=None, released_only=True):
        nonlocal fresh
        seen.add(cid)
        fresh += 1
        pairs = [unwrap(item, kind) for item in items or []]
        if released_only:
            released.prefetch(pairs)
        metas, ids, dropped = [], set(), 0
        for item_kind, entry in pairs:
            meta = to_meta(entry, item_kind)
            if not meta or meta["id"] in ids:
                continue
            if released_only and not released.ok(item_kind, entry, meta["id"]):
                dropped += 1
                continue
            ids.add(meta["id"])
            metas.append(meta)
        metas = metas[:limit]
        catalogs.append((cid, name, metas))
        print(f"  {name}: {len(metas)} titles" + (f" ({dropped} not out yet, left out)" if dropped else ""))

    def failed(label, error, match):
        """Logs a list Trakt couldn't return and republishes the last titles of the rows that match, with the
        catalog fields only."""
        kept = [cid for cid in previous if cid not in seen and match(cid)]
        for cid in kept:
            seen.add(cid)
            name, metas = previous[cid]
            metas = [{k: m[k] for k in META_FIELDS if k in m} for m in metas if isinstance(m, dict)]
            catalogs.append((cid, name, metas))
        print(f"  ! {label}: {error}" + (" (kept its last titles)" if kept else ""))

    def add_list(cid, name, path, kind=None, released_only=True, **query):
        if cid in seen:
            return
        query.setdefault("limit", limit)
        try:
            items = trakt.get(path, extended="full", **query)
        except RuntimeError as e:
            failed(name, e, lambda c: c == cid)
            return
        add(cid, name, items, kind, released_only)

    def items_path(user, list_id, sort):
        by, how = split_sort(sort, "rank,asc")
        return f"/users/{user}/lists/{list_id}/items/movie,show/{by}/{how}"

    for entry in config["catalogs"]:
        kind = entry["kind"]
        only = entry.get("released_only", True)
        sort = entry.get("sort")
        if kind == "watchlist":
            by, how = split_sort(sort, "added,desc")
            add_list("watchlist", entry.get("name", "Watchlist"), f"/sync/watchlist/movie,show/{by}/{how}", None, only)
        elif kind == "recommendations":
            media = entry["media"]  # movies | shows
            add_list(
                f"recommended-{media}",
                entry["name"],
                f"/recommendations/{media}",
                "movie" if media == "movies" else "show",
                only,
                limit=min(limit, 100),
            )
        elif kind == "smart_lists":
            by, how = split_sort(sort, "released,desc")
            try:
                smart_lists = trakt.get("/users/me/smart-lists") or []
            except RuntimeError as e:
                failed("Smart lists", e, lambda c: c.startswith("smart-"))
                continue
            # Oldest first: the order they were created in (Netflix, Prime Video, ...).
            for smart in sorted(smart_lists, key=lambda sl: sl.get("created_at") or ""):
                add_list(
                    f"smart-{smart['ids']['slug']}",
                    smart["name"],
                    f"/smart-lists/{smart['ids']['trakt']}/items/all/{by}/{how}",
                    None,
                    only,
                    watchnow_country=country,
                )
        elif kind == "personal_lists":
            skip = set(entry.get("exclude") or [])
            try:
                own_lists = trakt.get("/users/me/lists") or []
            except RuntimeError as e:
                # A row lists.json now leaves out stays out, even when its list can't be checked this time.
                failed(
                    "Your lists", e, lambda c, skip=skip: c.startswith("mine-") and not {c[5:], previous[c][0]} & skip
                )
                continue
            for own in own_lists:
                if own["ids"]["slug"] in skip or own["name"] in skip:
                    continue
                own_sort = sort or f"{own.get('sort_by') or 'rank'},{own.get('sort_how') or 'asc'}"
                add_list(
                    f"mine-{own['ids']['slug']}",
                    own["name"],
                    items_path("me", own["ids"]["trakt"], own_sort),
                    None,
                    only,
                )
        elif kind == "liked_lists":
            skip = set(entry.get("exclude") or [])
            try:
                likes = trakt.get("/users/me/likes/lists", limit=100) or []
            except RuntimeError as e:
                # Only the name is known for a kept liked row: one left out by slug or user/slug can come back
                # for this run.
                failed(
                    "Liked lists",
                    e,
                    lambda c, skip=skip: c.startswith("list-") and c not in explicit and previous[c][0] not in skip,
                )
                continue
            for like in likes:
                lst = like.get("list") or {}
                ids = lst.get("ids") or {}
                user = ((lst.get("user") or {}).get("ids") or {}).get("slug")
                if not user or not ids.get("trakt"):
                    continue
                if {lst.get("name"), ids.get("slug"), f"{user}/{ids.get('slug')}"} & skip:
                    continue
                add_list(
                    f"list-{user}-{ids['trakt']}",
                    lst.get("name") or ids.get("slug"),
                    items_path(user, ids["trakt"], sort),
                    None,
                    only,
                )
        elif kind == "list":
            add_list(
                f"list-{entry['user']}-{entry['list']}",
                entry["name"],
                items_path(entry["user"], entry["list"], sort),
                None,
                only,
            )
    return catalogs, fresh


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def load_previous(site):
    """{catalog id: (name, [metas])} of the lists published last time, from the site folder."""
    previous = {}
    base = site / "catalog" / CATALOG_TYPE
    for cat in (read_json(site / "manifest.json") or {}).get("catalogs") or []:
        cid = cat.get("id")
        first = read_json(base / f"{cid}.json")
        if not cid or not isinstance(first, dict):
            continue
        metas = list(first.get("metas") or [])
        for page in sorted((base / cid).glob("skip=*.json"), key=lambda p: int(p.stem.split("=")[1])):
            metas += (read_json(page) or {}).get("metas") or []
        previous[cid] = (cat.get("name") or cid, metas)
    return previous


def next_version(old, entries):
    """The manifest version changes only when the set of rows does (Stremio re-reads the manifest then).
    A new version is the UTC date and time, YYYY.MMDD.HHMMSS, so it keeps growing even after the job lost
    its last files."""
    if old and old.get("catalogs") == entries and old.get("version"):
        return old["version"]
    t = time.gmtime()
    new = (t.tm_year, t.tm_mon * 100 + t.tm_mday, t.tm_hour * 10000 + t.tm_min * 100 + t.tm_sec)
    try:
        last = tuple(int(x) for x in old["version"].split("."))
    except (TypeError, KeyError, ValueError, AttributeError):
        last = ()
    if new <= last:
        new = (*last[:2], last[2] + 1)
    return ".".join(str(x) for x in new)


INSTALL_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer"><meta name="robots" content="noindex">
<title>{name}</title>
<style>body{{font-family:system-ui,sans-serif;background:#0b0c0f;color:#f2f4f7;
max-width:640px;margin:40px auto;padding:0 16px}}
a.button{{display:inline-block;background:#f2f4f7;color:#0b0c0f;padding:10px 18px;
border-radius:10px;text-decoration:none;font-weight:600}}
code{{background:#1c1f24;padding:2px 6px;border-radius:6px;overflow-wrap:anywhere}}</style></head>
<body><h1>{name}</h1>
<p><a class="button" id="install" href="manifest.json">Install in Stremio</a></p>
<p>Or paste this link into Stremio's addon search: <code id="manifest">manifest.json</code></p>
<p>This page's address is private: anyone who has it can see these lists.</p>
<h2>Lists</h2><ul>
{rows}
</ul>
<script>
// The addon lives next to this page, at whatever private address it was opened from.
const base = location.origin + location.pathname.replace(/[^/]*$/, "");
document.getElementById("install").href = base.replace(/^https?:/, "stremio:") + "manifest.json";
document.getElementById("manifest").textContent = base + "manifest.json";
</script></body></html>
"""


def write_addon(site, config, catalogs):
    """Writes the addon into the site folder, replacing what was there only once all of it is written."""
    entries = [
        {"type": CATALOG_TYPE, "id": cid, "name": name, "extra": [{"name": "skip"}]} for cid, name, _ in catalogs
    ]
    version = next_version(read_json(site / "manifest.json"), entries)
    new = site.with_name(site.name + ".new")
    shutil.rmtree(new, ignore_errors=True)
    for cid, _, metas in catalogs:
        pages = [metas[i : i + PAGE_SIZE] for i in range(0, len(metas), PAGE_SIZE)] or [[]]
        base = new / "catalog" / CATALOG_TYPE
        write_json(base / f"{cid}.json", {"metas": pages[0]})
        for n, page in enumerate(pages[1:], start=1):
            write_json(base / cid / f"skip={n * PAGE_SIZE}.json", {"metas": page})
    write_json(
        new / "manifest.json",
        {
            "id": config["addon_id"],
            "version": version,
            "name": config["name"],
            "description": config["description"],
            "resources": ["catalog"],
            "types": ["movie", "series", CATALOG_TYPE],
            "idPrefixes": ["tt"],
            "catalogs": entries,
            "behaviorHints": {"configurable": False},
        },
    )
    rows = "\n".join(f"<li>{html.escape(name)} ({len(metas)})</li>" for _, name, metas in catalogs)
    (new / "index.html").write_text(INSTALL_PAGE.format(name=html.escape(config["name"]), rows=rows), encoding="utf-8")
    shutil.rmtree(site, ignore_errors=True)
    new.rename(site)
    print(f"Wrote {len(catalogs)} catalogs, manifest version {version}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True, help="folder kept between runs")
    parser.add_argument("--force-refresh", action="store_true", help="renew the Trakt sign-in now (to test it)")
    args = parser.parse_args()

    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
    except ValueError as e:
        sys.exit(f"{args.config} isn't valid JSON: {e}")
    problems = check_config(config)
    if problems:
        sys.exit(f"Fix {args.config}:\n- " + "\n- ".join(problems))
    client_id = os.environ.get("TRAKT_CLIENT_ID") or sys.exit(
        "TRAKT_CLIENT_ID is not set. Run connect.py (see lists/README.md)."
    )
    token_path = args.state / "trakt-token.json"
    trakt = Trakt(client_id, newest_token(token_path, os.environ.get("TRAKT_TOKEN_JSON")), token_path)
    try:
        trakt.ensure_fresh_token(force=args.force_refresh)
    except RuntimeError as e:
        sys.exit(
            f"Trakt didn't renew the sign-in ({e}). Check that your Trakt app's Redirect URI is {REDIRECT_URI}, "
            "then sign in again: run connect.py with --trakt."
        )

    site = args.state / "site"
    aired_path = args.state / "aired.json"
    aired = read_json(aired_path, [])
    released = Released(aired if isinstance(aired, list) else [])
    catalogs, fresh = collect(trakt, config, load_previous(site), released)
    aired_path.write_text(json.dumps(released.aired()))
    if not fresh:
        sys.exit("Trakt returned none of the lists in lists.json; the published lists stay as they are.")
    write_addon(site, config, catalogs)


if __name__ == "__main__":
    main()
