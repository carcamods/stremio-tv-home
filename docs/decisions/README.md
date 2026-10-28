# Decisions

Architecture decision records: one decision per file, never rewritten. A reversed decision gets a new ADR,
and the old one is marked superseded. Read the index, then only the ADR you need.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-fresh-public-repo.md) | A fresh public repo, separate from the owner's private TV project | Accepted |
| [0002](0002-private-link-on-cloudflare.md) | Lists are built in a private repo and served from the person's own Cloudflare account, at a private link | Accepted |
| [0003](0003-builders-run-a-release.md) | Builders run a release tag of this repo, not a copy of the code | Accepted |
| [0004](0004-only-catalog-data-published.md) | Core invariant: only catalog data is published, guarded by a test | Accepted |
| [0005](0005-only-released-titles.md) | Lists leave out titles that aren't released yet (`released_only`) | Accepted |
| [0006](0006-layered-repo-memory.md) | Layered repo memory with `AGENTS.md` files | Accepted |
| [0007](0007-keys-typed-by-the-person.md) | People type their keys into `connect.py` themselves; keys never pass through the agent | Accepted |
| [0008](0008-protected-release-tags.md) | Release tags are protected before the first release | Accepted |
| [0009](0009-builders-pin-the-release-commit.md) | Builders pin the release's commit, not only its tag | Accepted |

## Template

```markdown
# NNNN: Title

**Status:** Accepted, YYYY-MM-DD

## Context

What prompted the decision, with the facts that matter.

## Decision

What we chose, specific enough to check against the code.

## Consequences

What follows from it, including costs and what it rules out.
```
