# 0006: Layered repo memory with `AGENTS.md` files

**Status:** Accepted, 2026-10-27

## Context

Two kinds of agents read this repo: the owner's agent maintaining it across many sessions, and other
people's agents setting up their own lists or TV. The first needs the project's state and the reasons
behind it without re-reading everything; the second needs to reach the right instructions quickly and load
nothing else. The owner uses this approach in other projects.

## Decision

- The repo is the agents' memory: anything a future session needs is a committed file.
- The root `AGENTS.md` is a short map read every session. It opens with a "which job are you doing?" table
  that sends setup agents to `PROMPT.md` and the guides, then Active work, where things live, commands and
  the rules that always apply.
- Each folder has its own `AGENTS.md` (`lists/`, `docs/`; the launcher folders in stage 2), read before
  changing that folder.
- Decisions are ADRs with an index; `CHANGELOG.md` is newest first; `/checkpoint` ends a session and `/adr`
  records a decision (`.claude/commands/`).
- The files are named `AGENTS.md`, never `CLAUDE.md`: Claude Code reads `AGENTS.md` only when no
  `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` exists, and other agents read `AGENTS.md` too.
- `PROMPT.md` stays self-contained, because setup agents often run without a clone of the repo.

## Consequences

- Context files must be kept current in the same PR as the change they describe; `/checkpoint` checks it.
- Claude Code reads a folder's `AGENTS.md` only when it opens a file there with its Read tool, so the root
  map tells agents to read it explicitly.
- Setup rules that matter appear twice (`PROMPT.md` and the guides) and must be changed together.
