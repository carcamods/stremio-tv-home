# Standards

How this repo is built and changed. Ask the owner before changing anything here.

## Code

- **Lists builder:** Python 3.9 or newer, standard library only (the Action installs nothing). ruff for
  lint and format (`pyproject.toml`). Explicit field mapping for anything published (ADR 0004).
- **TV Home (stage 2):** Kotlin, Compose for TV, release builds only on TVs (debug builds are too slow).
  Personal values come from a git-ignored properties file, never from code.
- No network in tests, no real keys anywhere; fakes use obviously fake values (`SECRET-…`, `PRIVATE-…`).

## Quality gates

| Gate | Where |
|---|---|
| Tests (`python -m unittest discover -s lists`) | CI, and before every commit |
| The core invariant test | CI; never weakened or skipped |
| ruff, YAML/JSON checks, private keys | pre-commit and CI |
| Files under 1 MB; pictures and demos under 8 MB (`--enforce-all`, so every file, not only new ones) | pre-commit and CI |
| gitleaks with `.gitleaks.toml` (adds private links and Trakt Client IDs) | pre-commit on staged changes at commit time, and over the full history in CI |
| Release links, the commit pin and pinned actions match the release (`lists/test_release.py`) | CI, with the tests |

Hooks are pinned to commits (`# frozen:` tags), and CI runs a fixed pre-commit version.

## Releases

- Tags are `vMAJOR.MINOR.PATCH`. Builders run the commit their release tag had when they set up or
  updated (ADRs 0003, 0009), so a change reaches people only through a release.
- Each release: update `STREMIO_TV_HOME_VERSION` in `lists/builder/publish-lists.yml` and every
  `carcamods/stremio-tv-home/vX.Y.Z` link or mention in `lists/README.md`, `PROMPT.md` and that workflow
  (the tests fail until they match), a `CHANGELOG.md` entry, and release notes that name the tag's commit
  and say what people must change, if anything. `STREMIO_TV_HOME_COMMIT` stays a placeholder here: each
  builder fills it in. A breaking change to `lists.json` needs a new major version.
- Release tags are never moved or deleted: a tag ruleset and immutable releases enforce it (ADR 0008).

## Git and PRs

- Short-lived `type/short-description` branches, Conventional Commits (`feat(lists): …`, `docs: …`),
  squash merge. Only the owner merges, tags and publishes.
- A PR is done when CI is green, `CHANGELOG.md` has an entry, `README.md` and the guides match the new
  behaviour, decisions have an ADR, and the touched `AGENTS.md` files and "Active work" are current.
- Commits use the owner's GitHub private email in this repo. No AI attribution anywhere.

## Working with AI agents

- Layered repo memory (ADR 0006): the root `AGENTS.md` is a short map read every session; each folder's
  `AGENTS.md` is read before changing that folder; decisions are ADRs; `/checkpoint` ends a session and
  `/adr` records a decision when it's made.
- `PROMPT.md` is self-contained, because the agents of people setting up their lists often don't clone the
  repo. Setup rules that matter go there as well as in the guides.

## Docs

Plain English, short sentences, written for outside readers. Neutral about streams (Trakt's terms). No
personal data.

Pictures and demos for the README live in `docs/media/`, the only place files over 1 MB are allowed: under
8 MB each, captured from a real device. Before one goes in: account photos and names blurred, no city,
Wi-Fi name or other personal detail on screen, and lists shown under neutral names rather than streaming
services' (a demo build with other tab labels is fine).
