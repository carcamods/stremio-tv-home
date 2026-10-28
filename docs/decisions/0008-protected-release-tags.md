# 0008: Release tags are protected before the first release

**Status:** Accepted, 2026-10-28

## Context

Every builder runs whatever its workflow's tag points to, with the person's Trakt sign-in and Cloudflare
token (ADR 0003). A git tag can be moved or deleted by anyone with write access to this repo, or by a stolen
token, and every builder's next scheduled run would then run the new code. ADR 0003 relied on a promise not
to move tags. GitHub can enforce it: a tag ruleset can block updates and deletions, and immutable releases
lock a published release's tag and files. Rulesets on a free plan need a public repo, so they can only be
turned on after publication.

## Decision

In this order, before anyone is pointed at a release:

1. The repo is made public.
2. A tag ruleset on `refs/tags/v*` blocks updates and deletions, so tags can only be created.
3. Immutable releases are turned on.
4. `v1.0.0` is published as a GitHub release, with notes.

Every later version is a new tag and release; none is ever changed.

## Consequences

- A broken release can't be fixed in place: it gets a new version, and people update when they choose.
- The steps are owner tasks in `docs/checklist.md`.
- The builder workflow pins the actions it runs to commits, so a moved action tag can't reach people's keys
  either (`lists/test_release.py`).
