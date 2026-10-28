# Docs

The repo is public, so everything here is written for outside readers: plain English, short sentences, no
secrets, no real personal identifiers, and neutral about streams (Trakt's terms).

## What lives where

| File | Owns | Update when |
|---|---|---|
| `requirements.md` | goal, audiences, requirements, roadmap with stage status, milestones | a stage starts or ends, a requirement changes |
| `checklist.md` | tasks per stage, owner tasks marked *owner* | a task is done (tick it in the PR that finishes it) |
| `standards.md` | code, gates, releases, git, working with agents | a convention changes (ask the owner first) |
| `decisions/` | ADRs, one decision per file, plus `README.md` (index and template) | a decision is made (`/adr`) |

`CHANGELOG.md` (repo root) is newest first: a dated `## [YYYY-MM-DD] title` heading with Added / Changed /
Fixed / Removed bullets that say what changed and why. Existing entries are never rewritten.

The guides people follow live next to what they set up (`lists/README.md`), and `PROMPT.md` at the root.
README pictures and demos live in `docs/media/` (rules in `standards.md#docs`).

## ADRs

- Numbered `NNNN-kebab-title.md`, next number = highest + 1. Never renumber or delete one; if a decision is
  reversed, write a new ADR and mark the old one "Superseded by NNNN".
- Sections: Status, Context, Decision, Consequences (template in `decisions/README.md`).
- Every new ADR gets a one-line row in the index in `decisions/README.md`.
