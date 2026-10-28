# 0001: A fresh public repo, separate from the owner's private TV project

**Status:** Accepted, 2026-10-27

## Context

Everything here was first built in the owner's private repo for the owner's own two Google TV devices.
That repo's history and files hold what must never be public: device IP and MAC addresses, the owner's
city, package snapshots of the owner's TVs, the Trakt list owners they follow and a change log of their home
network. The setup turned out useful to others, and the owner wants other people's coding agents to be able
to replicate it, as Clean Your TV (Gathin23/cleanyourtv) does for debloating TVs.

## Decision

- A new public repo, `carcamods/stremio-tv-home`, starts from a fresh history. Code is copied in with every
  personal value replaced by configuration or placeholders; nothing is pushed from the private repo.
- This repo becomes the source of the code. The private repo keeps only the owner's device logs, snapshots
  and personal configuration, and runs the public code (the owner's lists builder runs a release of this repo; the
  owner's TV Home build keeps its package id through a local setting, so their TVs need no reinstall).
- Commits here use the owner's GitHub private email, not a personal address.
- Issues are open and answered on a best-effort basis.
- Published in stages: lists first, TV Home second (`requirements.md#roadmap`).

## Consequences

- One codebase: a fix made for the owner reaches everyone through a release, and the reverse.
- Before anything is copied from the private repo it is scanned for personal values; gitleaks runs over the
  full history in CI.
- Issues bring support work; the README says help is best effort.
