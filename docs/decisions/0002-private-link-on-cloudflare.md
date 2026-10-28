# 0002: Lists are built in a private repo and served from the person's own Cloudflare account, at a private link

**Status:** Accepted, 2026-10-28

## Context

Stremio needs the addon at an HTTPS address, and it can't send a password or a header with its requests,
so an addon can only be kept private through its address. The builder needs the person's Trakt sign-in,
and Trakt's refresh tokens work only once, so each run must keep the newest token where the next run can
read it: the Actions cache. In a public repo, workflows from pull requests can read that cache.

The first design served the lists from a public GitHub Pages repo (Pages is free only for public repos).
A review before publication found that it published every personal list whatever its Trakt privacy, so
lists made private or friends-only on Trakt became public, along with Trakt's recommendations, which
reflect what the person watches, and that every version stayed in the public repo's git history.

Cloudflare's free plan serves a Worker's static files ("static assets") without running any code, for free
and without a request limit, and Cloudflare's API accepts them directly (the same calls its own CLI makes),
which the standard library can do. The owner's lists are served this way since 2026-10-28.

## Decision

- Each person has a **private builder repo**: their `lists.json`, the workflow, their secrets, and in the
  Actions cache the Trakt sign-in and the lists published last (`.state`). The workflow first checks that it
  runs in a private repo, not a fork, on its default branch, and stops otherwise.
- The builder uploads the files to a Worker in the person's **own free Cloudflare account**, inside a folder
  named by a random key (`ADDON_KEY`, 32 characters from `secrets.token_urlsafe(24)`).
- The addon is served only at `https://<worker>.<subdomain>.workers.dev/<key>/manifest.json`. Every other
  path is a 404, nothing lists the files, and every response carries `X-Robots-Tag: noindex` and
  `Referrer-Policy: no-referrer`, plus `Access-Control-Allow-Origin: *` for Stremio Web.
- The link is the lock. The guides and `PROMPT.md` say plainly that anyone with it sees every list in the
  addon, including private and friends-only Trakt lists and the recommendations, and how to make a new one.

## Consequences

- No server and no cost: private repos get 2,000 free Actions minutes a month and a run every 3 hours uses
  about 240-480; Cloudflare's free plan covers the rest.
- Setup needs a Cloudflare account and an API token with only Account · Workers Scripts · Edit; the token,
  the account id and the key are secrets of the builder repo.
- Nothing about a person's lists is in any git history. A leaked link is replaced with
  `connect.py --new-link`; the old one stops working at the next run.
- The install page builds its links from the address it is opened at, so `lists.json` needs no URL.
- GitHub drops a cache unused for 7 days; then the person signs in again and the next run rebuilds every
  list. The manifest version is a date and time, so it keeps growing anyway.
- Private, not secret: Stremio keeps the link in the person's Stremio account, and Cloudflare serves it.
- Cloudflare is a dependency of serving; TV Home (stage 2) reads the same link.
