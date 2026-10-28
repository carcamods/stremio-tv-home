# 0005: Lists leave out titles that aren't released yet (`released_only`)

**Status:** Accepted, 2026-10-28

## Context

Smart lists sorted newest first start with titles a service has announced but not released. On
2026-10-27 the newest titles of three service lists were checked against Cinemeta, the catalog Stremio's
episode lists come from: one show had no episodes at all in Cinemeta, so Stremio showed an empty page; one
had three episodes, none of them aired; and several new movies had a release date on Trakt but none in
Cinemeta. The option is named and described by release dates only: Trakt's terms and this project keep any
mention of streams out.

## Decision

- By default a list keeps movies whose Trakt `released` date is today or earlier (with no date, a year
  before the current one) and shows with at least one episode in Cinemeta whose `released` is in the past.
  If Cinemeta can't be reached, Trakt's `aired_episodes` decides.
- `"released_only": false` on a `lists.json` entry turns it off for that list; the example does this for
  the watchlist, where people add upcoming titles on purpose.
- Shows are checked 8 at a time. Shows found to have aired are kept in the state folder between runs, and
  Cinemeta is asked only about the others. A failed Cinemeta call (dropped connection, timeout) counts as
  "couldn't ask", never as a failed run.

## Consequences

- After the first run, Cinemeta sees a handful of requests per run instead of hundreds.
- The job's log says how many titles each list left out.
