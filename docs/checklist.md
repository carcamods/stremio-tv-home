# Checklist

Tasks per stage. *owner* marks the owner's tasks: publishing, accounts, keys, merging.

## Stage 1: lists

- [x] Builder, publishing and sign-in scripts and the workflow made generic (no personal values)
- [x] Builder workflow runs a release tag of this repo (ADR 0003)
- [x] Setup guide (`lists/README.md`) and `PROMPT.md`
- [x] Offline tests, including the core invariant (`lists/test_privacy.py`), proven to catch leaks
- [x] Layered repo memory: `AGENTS.md` map and folder notes, ADRs, changelog, `/checkpoint`, `/adr`
- [x] CI: tests on Python 3.9 and 3.13, pre-commit (ruff, file checks), gitleaks over the full history
- [x] Review the repo locally — *owner*
- [x] Pre-publication review and its fixes: private link on Cloudflare (ADR 0002), keys typed into
  `connect.py` (ADR 0007), `released_only` (ADR 0005), protected release tags planned (ADR 0008)
- [x] First real run on Cloudflare (2026-10-28): the owner's `tv-lists-builder`, a test build of the
  unreleased code; `connect.py`, the Trakt renewal, the addon installed from the private link, paging past
  100 titles
- [x] Old setup retired: the owner's public GitHub Pages lists repo and old builder deleted, TV Home
  pointed at the private link — *owner*
- [x] Recreate `carcamods/stremio-tv-home` (private) with a fresh history, issues on
- [x] Second pre-publication review and its fixes: builders pin the release's commit (ADR 0009),
  `connect.py --cloudflare` makes a missing link, kept rows cut to catalog fields, gitleaks rules for
  private links and Client IDs, size checks that work in CI, `PROMPT.md` matching the guide
- [x] Recreate the repo again from one clean commit, because the first history still had personal
  details — *owner*
- [x] Make it public; tag ruleset on `refs/tags/v*` blocking updates and deletions; immutable releases on
  (ADR 0008) — *owner*
- [x] Ruleset on `main`: PR required (squash only), the three CI checks required — *owner*
- [x] Release `v1.0.0` (2026-10-28) with notes that name its commit, `dc0b61b` — *owner*
- [x] Switch `tv-lists-builder` to the `v1.0.0` workflow with its commit pinned (setup guide, step 3),
  delete its copy of the code, check a run
- [x] Walk through `PROMPT.md` as a new user would and fix what's unclear (2026-10-28, without real
  accounts: commands, messages and current Trakt and Cloudflare docs; fixes in `v1.0.1`)
- [ ] Release `v1.0.1` with notes that name its commit — *owner*
- [ ] M2: a first outside user sets up their lists from `PROMPT.md`, with real accounts, without help

## Stage 2: TV Home

- [ ] Requirements for the TV part agreed (config, tabs, which TVs) — *owner*
- [ ] Launcher moved in, every personal value in config; the owner's build keeps its own package id
- [ ] TV setup prompt with the safety rules; docs per tested TV
- [ ] New-user install test on a second device
- [ ] Release

## Stage 3: outreach

- [ ] Row in Clean Your TV's `SHOWCASE.md`
- [ ] PR there with what we learned on Google TV
