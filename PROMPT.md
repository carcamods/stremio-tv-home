# The prompt

Paste the text between the lines into Claude Code, or another coding agent that can run commands on
your computer. It sets up [your Trakt lists in Stremio](lists/README.md): it does the GitHub part itself
and tells you exactly what to do on trakt.tv and Cloudflare. About 25 minutes; you need a Trakt account, a
GitHub account and a Cloudflare account, all free.

---

I want my Trakt lists in Stremio, using https://github.com/carcamods/stremio-tv-home. Follow the setup in
its `lists/README.md` at the release it names (read it first:
https://raw.githubusercontent.com/carcamods/stremio-tv-home/v1.0.0/lists/README.md). Run the commands
yourself, except `connect.py`, and whenever a step needs me in a browser, on trakt.tv or on Cloudflare,
tell me exactly what to click. Work step by step and check each step worked before the next.

Before anything else:
- Check that `git`, Python 3.9 or newer and the GitHub CLI are installed and that `gh auth status` shows
  me signed in. If not, help me install them; for the sign-in, ask me to run `gh auth login` myself.
  On Windows, use Git Bash for your commands.
- Ask me, in one go: the name Stremio should show for my addon; my country (for "where to watch" in
  Trakt Smart lists); which lists I want (my watchlist, Trakt's recommendations for me, my Smart lists,
  my own lists, lists I liked, any public Trakt list I give you a link to); and the name of my private
  builder repo (default `tv-lists-builder`).
- Tell me plainly how private it is: my lists are served at a private link, and anyone who has the link
  can see every list in the addon, including lists I made private or friends-only on Trakt, lists I liked
  that their owners keep private or friends-only (with those owners' Trakt user names), and Trakt's
  recommendations for me, which reflect what I watch. Offer to leave lists out.
- If I want rows per streaming service, explain Trakt Smart lists (free accounts can have only a few) and
  walk me through creating them on trakt.tv, with both movies and shows, before the first run.

Rules:
- Keys never pass through you. Never ask me to paste a Client ID, token, key or my private link into this
  chat, and never run `connect.py` yourself: I run it in my own terminal, where it asks for my keys without
  showing them and stores them as secrets of my builder repo. If I paste one anyway, don't repeat or use
  it; tell me to replace it (a new Cloudflare token, or `connect.py --new-link` for the link).
- Create the builder repo only after I confirm its name, in my home folder or another folder that isn't
  inside a git repo (never inside a clone of stremio-tv-home). Download its files from the release as the
  guide's step 3 does, even if you have a clone, and pin the release's commit in the workflow as that step
  shows. Add files to git by name, never with `git add -A` or `git add .`. The builder repo stays private:
  never make it public.
- For the Trakt API app, read https://developer.trakt.tv/docs/create-an-app for what Trakt currently asks,
  then guide me through creating my own (Redirect URI `http://localhost`, no permissions). Never use
  anyone else's app or Client ID.
- For Cloudflare, guide me through the free plan, choosing a `workers.dev` subdomain if it asks, and a
  custom API token with the single permission Account · Workers Scripts · Edit.
- Then give me the two commands that download and run `connect.py` for my system, with my repo filled
  in, and wait until I say it's done. Check with `gh secret list` and `gh variable list` on my builder
  repo: the secrets `TRAKT_CLIENT_ID`, `TRAKT_TOKEN_JSON`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`
  and `ADDON_KEY`, and the variable `ADDON_URL`. If some are missing, give me the `connect.py` command for
  that part (the guide's "If something goes wrong").
- Use `--repo <user>/<builder>` with my builder repo in every `gh` command below. Switch the job on with
  `gh variable set LISTS_ENABLED --body true`; until then every run skips its only job. Start the first
  run with `gh workflow run publish-lists.yml -f force_refresh=true`, so the Trakt sign-in renewal is
  tested while I'm here. Find it with `gh run list --workflow publish-lists.yml --event workflow_dispatch
  --limit 1`; it must have started less than a minute ago (if not, wait a few seconds and list again).
  Follow it with `gh run watch <id> --exit-status`. If it fails, read `gh run view <id> --log-failed` and
  fix it with me.
- When it passes, tell me to open the private link `connect.py` showed me and press Install in Stremio.

When it works, give me a short summary: my builder repo, which must stay private; where to change my
lists (`lists.json` in the builder repo, or on trakt.tv); what to do if the Trakt sign-in stops working or
the link leaks (`connect.py --trakt` or `--new-link`); and how to update (the guide's "Updating").

---

Expect to answer a few questions, to spend a few minutes on trakt.tv and Cloudflare, and to run one command
yourself. Nothing is installed on your TV for this part; the lists show up in Stremio on every device
signed in to your Stremio account.
