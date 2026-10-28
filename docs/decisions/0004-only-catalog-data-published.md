# 0004: Core invariant: only catalog data is published, guarded by a test

**Status:** Accepted, 2026-10-27

## Context

Anyone who has a person's private link can read their lists (ADR 0002). Trakt's answers carry much more than titles: the user's name and
profile, private list descriptions, notes on list items, internal ids. The builder holds the Trakt access
and refresh tokens and the app's Client ID in memory while it writes files that are served to anyone with
the link. If any of
that reached the published files, the project would expose exactly what people trust it to keep private.

## Decision

- The published files contain catalog data only: per title `id` (IMDb), `type`, `name`, `poster`,
  `releaseInfo`, `genres`, `description`; per catalog its id and name; the manifest and an install page.
- `to_meta` builds each title from an explicit list of fields; no Trakt object is passed through.
- `lists/test_privacy.py` runs the whole builder against a fake Trakt account full of planted private values
  and fails if any of them, or any field outside the list above, reaches the output. It is never weakened or
  skipped. When the builder learns a new list kind or field, the fake account gets the private values that
  come with it, and the test is shown to catch a leak injected on purpose.

## Consequences

- Adding a published field means changing this ADR's list, the test and `to_meta` together.
- The test was proven on 2026-10-27 to catch an extra field and private text inside an allowed field.
- Catalog ids of liked lists contain the list owner's Trakt user name, which is public on Trakt; the
  person's own user name never appears.
