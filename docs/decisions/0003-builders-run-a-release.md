# 0003: Builders run a release tag of this repo, not a copy of the code

**Status:** Accepted, 2026-10-27

## Context

The first design had people create their builder repo from this repo as a GitHub template. A template copy
starts its own history, so taking later fixes with `git pull` fails ("unrelated histories") or conflicts on
every file. The builder code also runs with the person's Trakt sign-in, so what it runs should not change
without them choosing it.

## Decision

- A builder repo holds two files: the person's `lists.json` and `.github/workflows/publish-lists.yml`
  (copied from `lists/builder/`).
- The workflow checks out this repo at the tag in `STREMIO_TV_HOME_VERSION` and runs
  `upstream/lists/build.py` with the person's `lists.json`.
- Updating means changing that one line after reading the release notes. `lists.json` stays backward
  compatible within a major version.
- The owner's own builder works the same way.

## Consequences

- Fixes reach people when they choose, and a compromised `main` can't reach a builder that pins a tag.
  (Tags can be moved, so they are never moved once published.)
- Every release must update the tag in `lists/builder/publish-lists.yml` and the `RAW` line in
  `lists/README.md` (`docs/standards.md`).
- People who never update keep working on their old release as long as Trakt's API stays compatible.
