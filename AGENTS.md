# stremio-tv-home

Stremio TV Home, in two parts: (1) a list-only Stremio addon that a GitHub Actions job builds from a
person's own Trakt account, in their private builder repo, and serves from their own Cloudflare account at
a private link; (2, next) TV Home,
an Android TV / Google TV launcher built around it. The builder is standard-library Python; the launcher
will be Kotlin with Compose for TV. Public repo; the owner reviews and merges every PR.

This file is a map, read at the start of every session by Claude Code, Codex and other agents that use
`AGENTS.md`. Each folder has its own `AGENTS.md`: read it before changing anything there. Read what the
task needs, not the whole repo.

## Which job are you doing?

| You were asked to | Do this |
|---|---|
| Set up someone's Trakt lists in Stremio | Follow [PROMPT.md](PROMPT.md) and [lists/README.md](lists/README.md) on their computer. Create their private builder repo outside this clone; you write its `lists.json` and download the workflow from the release tag as the guide does, never from this clone's files, which can be ahead of the release. They run `connect.py` themselves: never handle their keys or their private link. Don't change this repo or open issues or PRs unless they ask. |
| Set up TV Home on someone's TV | Not published yet (stage 2). Say so; don't improvise it from this repo. |
| Change this repo | Read on. |

## Active work (updated 2026-10-28)

- **Done:** stage 1 built and reviewed before publication: lists served at a private link from the
  person's Cloudflare account (ADR 0002), keys typed by the person into `connect.py` (ADR 0007),
  `released_only` (ADR 0005). Since 2026-10-28 the owner's lists run on it from `tv-lists-builder` (a test
  build of the unreleased code), installed in Stremio and TV Home. A second review's fixes are in: builders
  pin the release's commit (ADR 0009), `connect.py --cloudflare` makes a missing link, kept rows are cut
  to catalog fields, gitleaks rules for private links and Client IDs, size checks that work in CI.
- **Next (owner):** recreate the repo once more from one clean commit (the first history still had
  personal details), then make it public, protect release tags and turn on immutable releases (ADR 0008),
  the ruleset on `main`, release `v1.0.0` with its commit in the notes; then switch `tv-lists-builder` to
  the release workflow (`docs/checklist.md`).
- **Later:** stage 2 (TV Home) and stage 3 (Clean Your TV showcase). See `docs/requirements.md#roadmap`.

## Where things live (read on demand)

| Need | Read |
|---|---|
| Goal, audiences, requirements, roadmap | `docs/requirements.md` |
| Tasks per stage and who does them | `docs/checklist.md` |
| Why something is the way it is | `docs/decisions/README.md` (index), then only the relevant ADR |
| What changed recently | the top ~40 lines of `CHANGELOG.md` |
| Tools, CI, releases, before structural changes | `docs/standards.md` |
| The lists builder: files, rules, tests | `lists/AGENTS.md` |
| Writing docs | `docs/AGENTS.md` |

## Commands

```bash
python -m unittest discover -s lists -v      # tests: offline, no keys, under a second
uvx pre-commit run --all-files               # ruff, file checks (gitleaks: staged changes only)
uvx pre-commit install                       # once per clone
```

## Rules that always apply

- **Only catalog data is published.** List names, titles, IMDb ids, years, genres, descriptions and poster
  links, nothing else from the account. `lists/test_privacy.py` enforces it and must never be weakened
  (ADR 0004).
- **Secrets.** The Trakt sign-in, Cloudflare tokens, addon keys and private links, and any real app's
  Client ID never reach git, logs, output, issues or chat; people type them into `connect.py` themselves
  (ADR 0007). Tests use obviously fake values.
- **Releases are the contract.** Builders run the tag named in their workflow, so nothing reaches people
  without a new tag and release notes; keep `lists.json` backward compatible (ADR 0003).
- **Trakt's terms.** Documented API methods only, few calls, neutral wording: this project lists titles and
  posters. Never mention, recommend or link addons or sites that provide streams.
- **No personal data** in commits, examples or screenshots: no real user names, IPs, MACs, emails, cities
  or Wi-Fi names. Use `<you>`, `YOUR-GITHUB-USER`, `192.168.1.50`.
- **Scope.** Do the task asked; flag unrelated issues at the end. Ask before changing the structure, the
  setup flow or `docs/standards.md`.
- **Git.** A `type/short-description` branch and a PR; never push to `main`, merge, tag or publish.
  Conventional Commits. No AI attribution anywhere.
- **Context files are `AGENTS.md`.** Never add a `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md`:
  any of them makes Claude Code stop reading every `AGENTS.md` (ADR 0006).

## Ending a session

Run `/checkpoint`: it logs decisions, updates the changelog, refreshes "Active work" and the touched
folders' `AGENTS.md`, runs the checks and commits on the branch. Use `/adr` to record a decision as soon as
it's made.
