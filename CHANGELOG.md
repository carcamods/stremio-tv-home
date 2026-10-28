# Changelog

Newest first. Each entry says what changed and why.

## [2026-10-28] Stage 1: Trakt lists as a private Stremio addon

### Added

- `lists/build.py`: generic version of the builder the owner runs for their own lists. Reads a person's Trakt
  watchlist, recommendations, Smart lists (with a country for "where to watch"), own, liked and public lists
  and writes a static, list-only Stremio addon. A list Trakt can't return keeps its last titles; `lists.json`
  is checked before Trakt is read; network errors are retried.
- `lists/cloudflare.py`: serves the addon from the person's own Cloudflare account at a private link, with
  Cloudflare's direct upload API and the standard library only, so nothing about anyone's lists lands in a
  public repo or its history (ADR 0002).
- `lists/connect.py`: people type their Trakt Client ID and Cloudflare token into it, in their own terminal;
  it stores them as secrets of their builder repo through `gh`, never in a file, a command line or an
  agent's chat (ADR 0007).
- "Only released titles" (`released_only`): movies must be released and shows must have an aired episode
  in Cinemeta, because new titles on service lists opened empty pages in Stremio (ADR 0005).
- `lists/builder/publish-lists.yml`: the workflow for each person's private builder repo. It runs a release
  tag of this repo with its actions pinned to commits, and only in a private repo on its default branch
  (ADRs 0002, 0003).
- Setup by hand (`lists/README.md`) and with a coding agent (`PROMPT.md`), both saying plainly what the
  private link shows.
- Tests, offline and keyless: the core invariant `lists/test_privacy.py` (ADR 0004), shown to catch
  injected leaks; the builder; the upload against a fake Cloudflare API; `connect.py`'s handling of keys; the
  guides' release links.
- Layered repo memory: `AGENTS.md` map and folder notes, `docs/` (requirements, checklist, standards,
  ADRs 0001-0009), `/checkpoint` and `/adr` (ADR 0006).
- CI: tests on Python 3.9 and 3.13, pre-commit (ruff, file checks, picture sizes), and gitleaks over the full
  history with a pinned checksum.
- README: a before/after picture (Google TV's home, then TV Home) and a short demo of TV Home, captured on
  Google TV with neutral tab names, the account photo and the status row blurred (`docs/media/`).

### Changed (second pre-publication review)

- Builders pin the commit their release tag points to at setup, and the workflow checks out that commit, so
  a tag moved later, or a repo replaced under the same name, can't change the code that runs with people's
  keys (ADR 0009). Updating takes the new release's workflow too.
- `connect.py --cloudflare` makes the private link when there's none yet: its own error messages sent a
  first run that stopped at Cloudflare there, and the builder was left without a link. A token Cloudflare
  rejects now stops before any question; a missing certificate on macOS is named.
- Rows kept from the last run, when Trakt can't return a list, are cut to the catalog fields and leave out
  lists `exclude` now names. `test_privacy.py` also runs the whole job as the workflow does and checks every
  file that would be uploaded, so the Trakt sign-in next to the site can't slip in.
- `lists.json` checks catch the `YOUR-GITHUB-USER` placeholder, a malformed `sort`, `exclude` given as text,
  `released_only` in quotes and a `list` with a `/` in it, which used to run and quietly do something else.
- `PROMPT.md` matches the guide: it switches the job on (`LISTS_ENABLED`), uses `--repo`, watches the run it
  started (`--event workflow_dispatch`), and keeps the builder repo private. The guides say what to do if
  that repo was ever public, and that private lists you liked are visible at the link too.
- `.gitleaks.toml` adds rules for private links and Trakt Client IDs, which the default rules missed. The
  file-size hooks use `--enforce-all`: before, they checked only files being added, so in CI they checked
  nothing. Hooks are pinned to commits, and CI runs a fixed pre-commit version.
