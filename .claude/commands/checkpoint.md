---
description: End-of-session review - record decisions, update changelog and context files, run checks, commit
---
We are wrapping up this working session. Do the following, in order, and report each step.

1. **Decisions.** Review the whole session for durable decisions (approach, setup flow, published data,
   releases, tooling, conventions) that have no ADR yet. Record each one as described in `/adr`. If there
   are none, say so.
2. **Changelog.** Add or extend today's entry at the top of `CHANGELOG.md`: a dated heading and
   Added / Changed / Fixed / Removed bullets that say what changed and why.
3. **Context files.** Update whatever this session made stale:
   - the "Active work" section of the root `AGENTS.md` (what's done, what's waiting, next step);
   - the `AGENTS.md` of every folder whose files changed (status, files, rules, tests);
   - stage statuses in the roadmap in `docs/requirements.md`, and finished tasks in `docs/checklist.md`;
   - `README.md`, `PROMPT.md` and the guides, if setup steps or behaviour changed (`PROMPT.md` and
     `lists/README.md` must say the same thing).
   Keep each `AGENTS.md` short; link to ADRs and docs instead of copying them.
4. **Checks.** Run `uvx pre-commit run --all-files` and `python -m unittest discover -s lists -v`. If any
   fail, stop and report instead of committing.
5. **Git.** Show `git status`. Commit on the current feature branch (never `main`) with a Conventional
   Commit message, push, and open or update the PR. Remind the owner to merge it.
