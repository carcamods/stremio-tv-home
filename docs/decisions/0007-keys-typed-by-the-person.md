# 0007: People type their keys into `connect.py` themselves; keys never pass through the agent

**Status:** Accepted, 2026-10-28

## Context

A first draft of the setup asked people to paste their Trakt Client ID and Client Secret into the agent's chat.
The guide put them on command lines (`--client-id`, `gh secret set --body`), where shell history keeps
them, and wrote the Trakt sign-in and a deploy key as files inside the builder repo's folder, where a failed
step followed by `git add -A` would commit them. An agent couldn't even show the Trakt activation code:
Python holds back output that goes to a pipe, so the code appeared only when the script ended. Trakt now
marks the Client Secret as deprecated and optional for the device sign-in and the token refresh.

## Decision

- `lists/connect.py` is run by the person, in a terminal window of their own. It refuses to run without a
  terminal, so an agent can't run it and keys can't be typed into an agent's chat.
- It asks for the Trakt Client ID and the Cloudflare API token without echoing them, signs in to Trakt
  (printing the code at once), checks the token can publish a Worker, makes the key of the private link, and
  hands each value to `gh secret set` on standard input. Nothing goes to a file, a command line or a chat.
  It shows the private link once, in that terminal.
- Each part can run again alone: `--trakt`, `--cloudflare`, `--new-link`.
- No Client Secret anywhere.
- The job uses whichever Trakt sign-in is newer, the secret or its own cached copy, so a new sign-in
  needs no cache cleanup.
- The agent checks the result with `gh secret list` and `gh variable list` (names only); it never sees a
  key or the link.

## Consequences

- One step of the setup is done by the person in a separate terminal; on Windows in PowerShell, because
  Git Bash's terminal isn't a console Python can read hidden input from (`winpty` works around it).
- `test_connect.py` checks that secrets reach `gh` on standard input only, and the terminal check.
- `trakt_login.py` is gone; `connect.py --trakt` replaces it.
