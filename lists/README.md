# Your Trakt lists in Stremio

A small, list-only Stremio addon built from **your own Trakt account**: your watchlist, Trakt's
recommendations for you, your Smart lists (for example "everything on Netflix in my country"), your own
lists, the lists you liked, and any public list you pick. It shows up in Stremio on every device signed in
to your Stremio account: phone, computer and TV.

There is no server to run. A GitHub Actions job in **your private builder repo** reads Trakt every 3 hours
and uploads plain JSON files to **your own Cloudflare account**, which serves them at **your private
link**: an address with a long random key in it. Stremio, and the TV Home launcher in this project, just
download those files.

| What | Where | Who can see it |
|---|---|---|
| The lists (list names, titles, IMDb ids, years, genres, descriptions, poster links) | your Cloudflare account, at your private link | anyone who has the link |
| Your Trakt sign-in, your Cloudflare token, your `lists.json` | secrets, cache and files of your private builder repo | you |
| The code | this repo, at a fixed release the builder names | everyone |

**The link is the lock.** Anyone who has it can see every list in your addon, including lists you made
private or friends-only on Trakt, lists you liked that their owners keep private or friends-only (with
those owners' Trakt user names), and Trakt's recommendations for you, which reflect what you watch.
Nothing links to it and search engines are asked not to index it; Stremio keeps it in your Stremio
account. Don't post it, and leave out of the addon any list you wouldn't want someone with the link to
see. If it leaks, make a new one ([below](#if-something-goes-wrong)).

**Keep the builder repo private.** Its Actions cache holds your newest Trakt sign-in and its run logs name
your lists. The job stops in a public repo or a fork, but that doesn't hide what's already there, so never
make it public ([if it happened](#if-something-goes-wrong)).

Everything here is free: a free Trakt account, a free GitHub account (about 240-480 of the 2,000 free
Actions minutes a month that private repos get), and Cloudflare's free plan.

## Set it up

With Claude Code (or another coding agent with a terminal), paste [`PROMPT.md`](../PROMPT.md): it does the
GitHub part itself and tells you what to do on Trakt and Cloudflare. By hand, about 25 minutes.

**You need:** a [Trakt](https://trakt.tv) account; a GitHub account, which Trakt asks you to connect
(verified) before it lets you create an API app; a [Cloudflare](https://dash.cloudflare.com/sign-up)
account; and on your computer `git`, Python 3.9 or newer, and the [GitHub CLI](https://cli.github.com)
signed in (`gh auth login`). The commands use `python3`; on Windows it's `py`, and the other commands run in
Git Bash.

In the commands, `<you>` is your GitHub user name and `<builder>` the name of your private builder repo
(e.g. `tv-lists-builder`).

1. **Create a Trakt API app.** On Trakt, connect your GitHub account under the developer section, then
   create an app ([Trakt's guide](https://developer.trakt.tv/docs/create-an-app)). Any name; Redirect URI
   `http://localhost`; no permissions needed. Keep its **Client ID** at hand for step 4; you don't need the
   Client Secret. Create one app and use it only for yourself: Trakt asks people not to create extra apps
   to get around its rate limits.
2. **Get a Cloudflare API token.** Sign up for Cloudflare's free plan, open **Workers & Pages** once, and if
   it asks you to choose a `workers.dev` subdomain, pick one (it becomes part of your link; it doesn't need
   to be your name). Then open **My Profile → API Tokens → Create Token → Create Custom Token**, give it one
   permission, **Account · Workers Scripts · Edit**, limited to your account, and create it. Keep the token
   at hand for step 4: Cloudflare shows it only once.
3. **Create your private builder repo** with the workflow and an example `lists.json`. Do it in your home
   folder or another folder that isn't inside a git repo:
   ```bash
   gh repo create <builder> --private --clone
   cd <builder>
   mkdir -p .github/workflows
   curl -fsSL https://raw.githubusercontent.com/carcamods/stremio-tv-home/v1.0.0/lists/builder/publish-lists.yml -o .github/workflows/publish-lists.yml
   curl -fsSL https://raw.githubusercontent.com/carcamods/stremio-tv-home/v1.0.0/lists/lists.example.json -o lists.json
   commit=$(gh api repos/carcamods/stremio-tv-home/commits/v1.0.0 --jq .sha)
   sed -i.bak "s/STREMIO_TV_HOME_COMMIT: .*/STREMIO_TV_HOME_COMMIT: $commit/" .github/workflows/publish-lists.yml
   rm .github/workflows/publish-lists.yml.bak
   ```
   The last three commands pin the workflow to the commit `v1.0.0` points to today, so your builder keeps
   running exactly that code even if the tag or this repo were ever changed:
   `grep COMMIT .github/workflows/publish-lists.yml` shows a 40-character commit id.

   Choose your lists in `lists.json` ([reference](#listsjson) below): replace `YOUR-GITHUB-USER`, pick your
   country and your rows. Then commit and push both files:
   ```bash
   git add lists.json .github/workflows/publish-lists.yml
   git commit -m "My lists"
   git push
   ```
4. **Connect Trakt and Cloudflare.** Open a terminal window of your own (on Windows, PowerShell) in your
   home folder, and run:
   ```bash
   curl -fsSLO https://raw.githubusercontent.com/carcamods/stremio-tv-home/v1.0.0/lists/connect.py
   python3 connect.py --repo <you>/<builder>
   ```
   In PowerShell, write `curl.exe` and `py`. It asks for the Client ID and the API token without showing
   them, shows a code to enter at trakt.tv/activate, and stores everything as secrets of your builder repo.
   Nothing is saved on your computer. At the end it shows **your private link**: keep it for step 6 (it
   works after the first run). Then you can delete `connect.py`. If it stops at the Cloudflare part, fix what
   it says and run it again with `--cloudflare`: it makes your link then.
5. **Switch it on** and run it once. The first run also renews the Trakt sign-in, which tests the renewal
   the job does by itself every few days:
   ```bash
   gh variable set LISTS_ENABLED --repo <you>/<builder> --body true
   gh workflow run publish-lists.yml --repo <you>/<builder> -f force_refresh=true
   gh run list --repo <you>/<builder> --workflow publish-lists.yml --event workflow_dispatch --limit 1
   gh run watch <run id from the line above> --repo <you>/<builder> --exit-status
   ```
   It takes a minute or two. The run to watch is the one that started less than a minute ago: if the list
   is empty or shows an older run, wait a few seconds and list again.
6. **Add it to Stremio:** open your private link on your phone or computer and press **Install in
   Stremio**, or paste the link with `manifest.json` added at the end into Stremio's addon search. Your lists
   appear as rows on Stremio's board and under Discover.

## lists.json

| Field | What |
|---|---|
| `addon_id` | Unique id of your addon, e.g. `io.github.<you>.tvlists` |
| `name`, `description` | What Stremio shows for the addon |
| `country` | Two-letter country for Smart lists' "where to watch" (e.g. `us`, `ca`, `gb`) |
| `max_items` | Most titles per list (Stremio pages them 100 at a time) |
| `catalogs` | The rows, in this order (below) |

| `kind` | What it adds |
|---|---|
| `watchlist` | Your Trakt watchlist, movies and shows |
| `recommendations` | Trakt's recommendations for you; `media` is `movies` or `shows`, and a `name`, one row each |
| `smart_lists` | Every Smart list on your account, in the order you created them |
| `personal_lists` | Every list you made, private ones included, each in its own Trakt sort |
| `liked_lists` | Every list you liked on Trakt |
| `list` | One public list: `user` (its owner), `list` (its id or slug) and a `name` |

Optional on any entry: `sort` as `<field>,<asc|desc>` (`rank`, `added`, `title`, `released`, ...;
recommendations always come in Trakt's order) and `released_only` (below). On `personal_lists` and
`liked_lists`, `exclude` lists names or slugs to leave out; a liked list can also be named `user/slug`.
Most changes happen on Trakt itself: create a Smart list, like a list, and it shows up after the next run.
New or removed rows change the addon's manifest; Stremio may need the addon reinstalled to show new rows.
Each run checks `lists.json` first and stops with what to fix.

**Smart lists** are Trakt lists that fill themselves from filters, such as "all titles available on
Netflix in my country". Free Trakt accounts can have only a few. When you create one, check its type
includes both movies and shows if you want both.

## Only released titles

By default every list leaves out titles that aren't out yet: movies whose release date (on Trakt) hasn't
come, and shows without an aired episode in Cinemeta, the catalog Stremio's episode lists come from. Smart
lists sorted newest first otherwise start with titles a service has announced but not released. The job's
log says how many each list left out. To keep everything in a list, give its entry
`"released_only": false` (the example does it for the watchlist, so upcoming titles you added yourself
stay).

## If something goes wrong

Stremio keeps showing the last published lists meanwhile, and GitHub emails you when a run fails.

- **A list can't be read** (its owner deleted it or made it private, or Trakt was briefly down): its row
  keeps its last titles and the job's log marks it with `!`. If no list at all can be read, the run fails.
- **The Trakt sign-in stops working** (the run fails and says so; for example after a week without runs,
  when GitHub drops the cache that holds the newest sign-in): sign in again with
  `python3 connect.py --repo <you>/<builder> --trakt`. The next run picks up the new sign-in by itself.
- **Your Cloudflare token expired or was revoked:** create a new one (step 2), then `--cloudflare`.
- **Your link leaked or got lost:** `--new-link` makes a new one; the old one stops working after the next
  run. Install the addon again from the new link.
- **Your builder repo was public, even briefly:** make it private again
  (`gh repo edit <you>/<builder> --visibility private --accept-visibility-change-consequences`), delete its
  caches (`gh cache delete --all --repo <you>/<builder>`) and its old runs (Actions tab, or
  `gh run delete <id> --repo <you>/<builder>`), remove your Trakt app's access in your Trakt settings
  (connected apps), and sign in again with `--trakt`.

To test the renewal any time, run the workflow with **Renew the Trakt sign-in now** checked (Actions →
Publish lists → Run workflow).

## Running the setup again

Nothing needs undoing: the builder repo, its secrets and the Cloudflare Worker stay. Run only the part you
need (above). To remove everything, delete the builder repo (`gh auth refresh -s delete_repo` once, then
`gh repo delete <you>/<builder>`), the Worker (`tv-lists`, unless you gave `connect.py` another `--worker`;
Cloudflare dashboard, Workers & Pages) and the API token, and the addon in Stremio.

## Updating

Your builder runs this repo's code at the release named in its workflow (`STREMIO_TV_HOME_VERSION`), at
the commit that release had when you set it up (`STREMIO_TV_HOME_COMMIT`), so nothing changes behind your
back. To update, read the notes of a newer [release](https://github.com/carcamods/stremio-tv-home/releases)
(they name its commit), then, in your builder repo's folder, with that release in `version`:
```bash
version=vX.Y.Z
curl -fsSL "https://raw.githubusercontent.com/carcamods/stremio-tv-home/$version/lists/builder/publish-lists.yml" -o .github/workflows/publish-lists.yml
commit=$(gh api "repos/carcamods/stremio-tv-home/commits/$version" --jq .sha)
sed -i.bak "s/STREMIO_TV_HOME_COMMIT: .*/STREMIO_TV_HOME_COMMIT: $commit/" .github/workflows/publish-lists.yml
rm .github/workflows/publish-lists.yml.bak
git add .github/workflows/publish-lists.yml
git commit -m "Update to $version"
git push
```
This takes the new release's workflow too. If you changed anything else in it, make that change again.
