# `lists/`: the Trakt lists builder

Turns a person's Trakt account into a static, list-only Stremio addon: `build.py` reads Trakt and writes
`manifest.json` plus one JSON file per catalog page, and `cloudflare.py` uploads them to the person's own
Cloudflare account, which serves them at their private link (ADR 0002). It runs in each person's private
builder repo (`builder/publish-lists.yml`) from a release tag of this repo. It knows nothing about TV Home,
which only downloads the published files.

**Status:** stage 1, `v1.0.0` not tagged yet. Serves the owner's lists from Cloudflare every 3 hours since
2026-10-28 (`tv-lists-builder`, a test build of this code); the Trakt renewal, the cache between runs and
paging past 100 titles in Stremio are checked in real runs.

## Files

- `build.py`: `Trakt` (requests, retries, single-use refresh token saved first), `newest_token` (the secret
  or the job's own copy, whichever is newer), `check_config`, `collect` (one catalog per `lists.json` entry;
  a list that fails keeps its last titles, cut to `META_FIELDS` and minus rows `exclude` now names), `Released` (the "only released titles" filter, ADR 0005),
  `to_meta` (Trakt title to Stremio meta), `write_addon` (pages of 100, manifest, install page) into
  `<state>/site`.
- `cloudflare.py`: uploads `<state>/site` as a Worker's static assets under `/<ADDON_KEY>/`, with Cloudflare's
  direct upload API (no Worker code).
- `connect.py`: run by the person in their own terminal: Trakt device sign-in, Cloudflare token check,
  the private link's key; stores them as builder repo secrets through `gh`, on standard input (ADR 0007).
  Each part runs again alone; `--cloudflare` also makes the link when there's none yet.
- `builder/publish-lists.yml`: the workflow people copy into their builder repo. Its
  `STREMIO_TV_HOME_VERSION` names the release; it checks out `STREMIO_TV_HOME_COMMIT`, the commit the
  setup guide's `sed` writes in, and refuses to run without one (ADR 0009). Here that line stays a
  placeholder. Its actions are pinned to commits.
- `lists.example.json`: starting point for a person's `lists.json`. `README.md`: the setup guide.

## Rules that must not break

- **Only catalog data in the output.** `to_meta` copies an explicit set of fields, and rows kept from the last
  run are cut to `META_FIELDS`; never pass a Trakt object through. Only `<state>/site` is uploaded: the
  sign-in and `aired.json` live beside it. `test_privacy.py` guards all of it (ADR 0004).
- **Keys never pass through an agent, a file or a command line:** `connect.py` reads them hidden and hands
  them to `gh` on standard input, and refuses to run without a terminal (ADR 0007).
- **Standard library only:** the Action installs nothing, and people can run it anywhere.
- **The refresh token is saved before anything else can fail:** Trakt's refresh tokens work once, and losing
  the new one means a new sign-in by hand.
- **`lists.json` stays backward compatible** between releases; a new option needs a default that keeps
  today's behaviour (ADR 0003).
- **Few calls:** one Trakt request per list per run, `limit` instead of paging through everything; Cinemeta
  is asked only about shows not yet known to have aired.

## Adding a list kind

1. Add the branch in `collect` (through `add_list`, with `released_only=only`), and the kind to `KINDS` and
   `check_config`.
2. Document it in the `kind` table in `README.md`.
3. Add its endpoint to `FakeTrakt` in `test_privacy.py` with the private fields Trakt returns around it,
   and check `LeaksAreCaught` still passes.

## Facts worth knowing

- Smart lists: `GET /users/me/smart-lists`, then `/smart-lists/{id}/items/all/{sort}/{how}` with
  `watchnow_country`. The type (movies, shows) is a setting of the Smart list on Trakt.
- Trakt's Client Secret is deprecated and optional for the device sign-in and the token refresh; the builder
  doesn't use one. Access tokens last 7 days; refresh tokens work once.
- Cinemeta (`v3-cinemeta.strem.io/meta/series/<imdb>.json`) is what Stremio's episode lists come from; its
  `released` dates are ISO strings, compared as text.
- Development Trakt apps only accept `http://localhost` as redirect URI, and the refresh call needs it.
- `/users/me/likes/lists` returns the most recently liked first. A liked list and a `list` entry that uses
  the list's number share the row id `list-<user>-<number>`, so a list in both shows once, where the `list`
  entry is.
- Cloudflare's asset upload: a session with the manifest (32-hex hash of base64 contents + extension), then
  the missing files in the buckets it returns (or one by one when its upload token says so), then a Worker
  upload whose metadata has only `assets` (`jwt`, `config` with `_headers`). `workers.dev` is turned on per
  Worker. Error 10007 on `/workers/subdomain` means the account has no `workers.dev` subdomain yet.

## Tests

`python -m unittest discover -s lists -v`: `test_build.py` (meta mapping, the release rules, failures,
config checks, sign-in choice, pages and versions), `test_privacy.py` (the core invariant, the whole job
as the workflow runs it and what it would upload, and proof it catches leaks), `test_cloudflare.py` (the
upload against a fake Cloudflare API), `test_connect.py` (secrets only on standard input, the terminal
check, running parts again), `test_release.py` (links, the commit pin and action pins match the release).
Offline and keyless. The real Trakt and Cloudflare calls are checked by the first run of a builder.
