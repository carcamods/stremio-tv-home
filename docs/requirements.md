# Requirements

## Goal

Let anyone make Stremio the center of their TV without running a server or paying for anything: their own
Trakt lists inside Stremio on every device, and an Android TV / Google TV home screen built around them.
Each person's own coding agent should be able to set it up from this repo, safely and step by step, and
someone without one should be able to follow the guides by hand.

## Audiences

1. **Stremio users with a Trakt account** (phone, computer or TV): they want their watchlist,
   recommendations and "what's on my services" lists as rows in Stremio. Stage 1.
2. **Android TV / Google TV owners who mostly watch through Stremio:** they want a home screen without
   Google's suggestions, with their lists, Continue watching and their apps. Stage 2.
3. **Coding agents** working for either of them, and the owner's agent maintaining the repo.

## Requirements

- **R1** A person's lists are built from their own Trakt account with their own Trakt API app, never a
  shared one.
- **R2** No server to run: the lists are rebuilt by GitHub Actions and served as static files from the
  person's own Cloudflare account; TV Home calls public APIs straight from the TV.
- **R3** Free: free Trakt, free GitHub (private repo Actions minutes stay well under the free 2,000 a
  month), Cloudflare's free plan, no paid launcher or service.
- **R4** Only catalog data is published, at a private link only the person has; they are told plainly
  that anyone with the link sees every list in the addon, private Trakt lists included (ADRs 0004, 0002).
- **R5** By default lists show only released titles: released movies, shows with an aired episode
  (ADR 0005).
- **R6** Setup works with a coding agent (`PROMPT.md`) and by hand (`lists/README.md`), and never shows or
  stores a secret where it could leak: people type their keys into `connect.py` themselves (ADR 0007).
- **R7** Updates reach people only through releases they choose to take, at the commit they pinned
  (ADRs 0003, 0009).
- **R8** On a TV (stage 2): nothing is uninstalled or rooted; every change is reversible and checked; the
  remote's buttons, Cast and play/pause keep working.

## Out of scope

- Streams, or any addon or site that provides them. This project lists titles and posters only.
- TVs that aren't Android TV / Google TV (Samsung Tizen, LG webOS, Roku, Fire TV for the launcher part).
- Paid Trakt features (VIP) and paid services.
- Hosting anything for other people: each person runs their own copy.

## Roadmap

| Stage | What | Status |
|---|---|---|
| 1 | **Lists:** builder, setup guide, `PROMPT.md`, release `v1.0.0`; the owner's builder runs the public code | released, `v1.0.0` on 2026-10-28; the owner's lists run from it |
| 2 | **TV Home:** move the launcher in with every personal value in config (lists URL, tabs, weather, Twitch app ID, package id), a TV setup prompt with the safety rules (snapshot first, one change at a time, verify with screenshots), docs per tested TV; tested as a new user's install on a second device | not started |
| 3 | **Outreach:** a row in Clean Your TV's `SHOWCASE.md`, and a small PR there with what we learned on Google TV (its home re-launching itself, the gear's quick settings, the Bluetooth pairing permission, a note for one TV model) | not started |

## Milestones

- **M1** Stage 1 public: repo published, release tags protected, `v1.0.0` released, ruleset on `main`,
  the owner's lists built from the release. The owner publishes. Done 2026-10-28.
- **M2** First outside user sets up their lists from `PROMPT.md` without help.
- **M3** Stage 2 released.
