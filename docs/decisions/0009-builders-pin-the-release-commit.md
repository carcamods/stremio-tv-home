# 0009: Builders pin the release's commit, not only its tag

**Status:** Accepted, 2026-10-28

## Context

Every builder checks out this repo by name at the tag in its workflow and runs that code with the person's
Trakt sign-in and Cloudflare token (ADR 0003). The tag ruleset and immutable releases (ADR 0008) stop a tag
from being moved, but not every way the code behind a name can change: someone who takes over the owner's
account can delete the repo and create a new one with the same name and tag, and a deleted repo or a
renamed account frees the name for someone else. Each builder's next scheduled run would then run their
code. A commit id can't be reused: a checkout by commit gets that code or fails. A release's workflow can't
name its own commit, because a commit can't contain its own id.

## Decision

- The workflow has `STREMIO_TV_HOME_COMMIT` next to `STREMIO_TV_HOME_VERSION`, and checks out the builder
  code at that commit. In this repo the line stays a placeholder.
- Setup step 3 looks up the commit the release tag points to (`gh api .../commits/<tag>`) and writes it
  into the person's workflow with `sed -i.bak`, which works with GNU sed (Linux, Git Bash) and BSD sed
  (macOS).
- The workflow refuses to run unless `STREMIO_TV_HOME_COMMIT` is a 40-character commit id.
- Updating downloads the new release's workflow and pins its commit the same way. Release notes name the
  tag's commit.
- `lists/test_release.py` checks that the workflow checks out the commit, keeps the placeholder, and that the
  guide's setup and update steps both pin it.

## Consequences

- What a builder runs can't change after setup, even if the tag, the repo or the account changes hands. If
  the repo were deleted, runs fail instead of running other code.
- One more command at setup and on each update, and updating also takes the new release's workflow, so
  changes to the workflow itself reach people.
- The release steps live in `docs/standards.md`. ADR 0003's mention of a `RAW` line in `lists/README.md` is
  out of date: the guide's links are checked by `lists/test_release.py` instead.
