#!/usr/bin/env python3
"""Connects your Trakt and Cloudflare accounts to your private builder repo. Run it yourself.

Asks for your Trakt Client ID and your Cloudflare API token without showing them, signs you in to Trakt
(a code to enter at trakt.tv/activate), and stores everything as secrets of your builder repo through the
GitHub CLI: no key is written to a file, a command line or a chat. It ends with your addon's private link.

    python3 connect.py --repo <you>/<builder>               # the first time: all of it
    python3 connect.py --repo <you>/<builder> --trakt       # sign in to Trakt again
    python3 connect.py --repo <you>/<builder> --cloudflare  # a new Cloudflare API token (and the link, if none yet)
    python3 connect.py --repo <you>/<builder> --new-link    # a new private link; the old one stops working

It needs a terminal window of your own (on Windows, PowerShell) and the GitHub CLI, signed in. Standard
library only.
"""

import argparse
import getpass
import http.client
import json
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TRAKT = "https://api.trakt.tv"
CLOUDFLARE = "https://api.cloudflare.com/client/v4"
USER_AGENT = "stremio-tv-home-lists/1.0"
WORKER = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?")


def say(text=""):
    # Flushed at once: the Trakt code must show while the script waits for it to be approved.
    print(text, flush=True)


def call(url, method="GET", body=None, token=None):
    """(HTTP status, JSON answer or None)."""
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except (OSError, ValueError):
            return e.code, None
    except (OSError, http.client.HTTPException, ValueError) as e:
        hint = ""
        if "CERTIFICATE_VERIFY_FAILED" in repr(e):
            hint = (
                " On a Mac with Python from python.org, run Install Certificates.command (Applications, Python) first."
            )
        sys.exit(f"Couldn't reach {urllib.parse.urlsplit(url).hostname} ({e!r}). Check the connection and retry.{hint}")


def trakt_post(path, body):
    return call(TRAKT + path, "POST", body)


def cloudflare(method, path, token):
    return call(CLOUDFLARE + path, method, token=token)


def gh(*args, secret=None):
    """Runs the GitHub CLI and returns what it prints. A secret goes in on standard input, never on the
    command line, where other programs and the shell history could see it."""
    result = subprocess.run(["gh", *args], input=secret or "", capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"gh {' '.join(args[:2])} failed: {result.stderr.strip() or 'no details'}")
    return result.stdout


def set_secret(repo, name, value):
    gh("secret", "set", name, "--repo", repo, secret=value)
    say(f"   Stored the {name} secret.")


def ask_hidden(prompt):
    while True:
        value = getpass.getpass(prompt).strip()
        if value:
            return value


def confirm(prompt):
    return input(prompt).strip().lower() in ("y", "yes")


def trakt_sign_in(client_id, post=trakt_post):
    """Device code sign-in: shows a code to enter at trakt.tv/activate and returns the Trakt sign-in."""
    status, codes = post("/oauth/device/code", {"client_id": client_id})
    if status != 200 or not codes:
        sys.exit(f"Trakt didn't start the sign-in (HTTP {status}). Check the Client ID, then run this again.")
    say(f"\n   On any device, open {codes['verification_url']} and enter the code:  {codes['user_code']}\n")
    say("   Waiting for you to approve it on trakt.tv ...")
    body = {"code": codes["device_code"], "client_id": client_id}
    deadline = time.time() + codes["expires_in"]
    interval = codes["interval"]
    while time.time() < deadline:
        time.sleep(interval)
        status, token = post("/oauth/device/token", body)
        if status == 200:
            return token
        if status == 400:  # still waiting for the person
            continue
        if status == 429:  # polling too fast
            interval += 1
            continue
        reason = {404: "Invalid code", 409: "Code already used", 410: "Code expired", 418: "Access was denied"}
        sys.exit(f"{reason.get(status, f'Trakt answered HTTP {status}')}. Run this again.")
    sys.exit("The code expired before it was approved. Run this again.")


def connect_trakt(repo, ask=ask_hidden, post=trakt_post):
    say("\nTrakt")
    client_id = ask("   Client ID of your Trakt app (it won't show as you paste it): ")
    token = trakt_sign_in(client_id, post)
    set_secret(repo, "TRAKT_CLIENT_ID", client_id)
    set_secret(repo, "TRAKT_TOKEN_JSON", json.dumps(token))
    say("   Trakt is connected.")


def connect_cloudflare(repo, worker, ask=ask_hidden, api=cloudflare):
    """Checks the token can publish a Worker, stores it and returns the Worker's address (ADDON_URL)."""
    say("\nCloudflare")
    token = ask("   Your Cloudflare API token (it won't show as you paste it): ")
    status, body = api("GET", "/accounts", token)
    if status in (400, 401):
        sys.exit(
            f"Cloudflare didn't accept this token (HTTP {status}). Create a new one (step 2 of lists/README.md), "
            "then run this again with --cloudflare."
        )
    accounts = (body or {}).get("result") or [] if status == 200 else []
    if len(accounts) == 1:
        account = accounts[0]["id"]
    else:
        account = input("   Your Cloudflare Account ID (dashboard, Workers & Pages, right column): ").strip()
    status, body = api("GET", f"/accounts/{account}/workers/subdomain", token)
    codes = {e.get("code") for e in (body or {}).get("errors") or []}
    subdomain = ((body or {}).get("result") or {}).get("subdomain") if status == 200 else None
    if not subdomain:
        if 10007 in codes:
            sys.exit(
                "Your Cloudflare account has no workers.dev subdomain yet. On dash.cloudflare.com, open "
                "Workers & Pages and choose one, then run this again with --cloudflare."
            )
        sys.exit(
            f"Cloudflare didn't accept the token for this account (HTTP {status}). It needs the permission "
            "Account, Workers Scripts, Edit. Check it, then run this again with --cloudflare."
        )
    status, _ = api("GET", f"/accounts/{account}/workers/scripts/{worker}/settings", token)
    if status == 200 and not confirm(
        f"   Your Cloudflare account already has a Worker named {worker}. Reuse it only if this builder repo "
        "published it before. If it serves anything else, another person's lists included, answer n and run "
        "this again with --worker <another name>. Reuse it? [y/N] "
    ):
        sys.exit("Nothing changed on Cloudflare.")
    url = f"https://{worker}.{subdomain}.workers.dev"
    set_secret(repo, "CLOUDFLARE_API_TOKEN", token)
    set_secret(repo, "CLOUDFLARE_ACCOUNT_ID", account)
    gh("variable", "set", "ADDON_URL", "--repo", repo, "--body", url)
    say("   Stored the ADDON_URL variable.\n   Cloudflare is connected.")
    return url


def new_link(repo, url):
    """Makes a new random key for the private link, stores it and returns the link."""
    key = secrets.token_urlsafe(24)
    set_secret(repo, "ADDON_KEY", key)
    return f"{url}/{key}/"


def main():
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", required=True, help="your private builder repo, <you>/<builder>")
    only = parser.add_mutually_exclusive_group()
    only.add_argument("--trakt", action="store_true", help="only sign in to Trakt again")
    only.add_argument(
        "--cloudflare", action="store_true", help="only store a new Cloudflare API token (and the link, if none yet)"
    )
    only.add_argument("--new-link", action="store_true", help="only make a new private link")
    parser.add_argument("--worker", default="tv-lists", help="name of the Cloudflare Worker (default tv-lists)")
    args = parser.parse_args()

    if not sys.stdin.isatty():
        sys.exit(
            "Run this yourself, in a terminal window of your own, not through a coding agent: it asks for your "
            "keys without showing them. On Windows use PowerShell (py connect.py ...), or in Git Bash "
            "winpty py connect.py ..."
        )
    if not WORKER.fullmatch(args.worker):
        sys.exit("--worker takes lowercase letters, digits and hyphens.")
    if not shutil.which("gh"):
        sys.exit("The GitHub CLI (gh) isn't installed: https://cli.github.com")
    repo = json.loads(gh("repo", "view", args.repo, "--json", "isPrivate,isFork,nameWithOwner"))
    if not repo["isPrivate"] or repo["isFork"]:
        sys.exit(f"{repo['nameWithOwner']} must be a private repo of your own, not public and not a fork.")
    name = repo["nameWithOwner"]
    everything = not (args.trakt or args.cloudflare or args.new_link)

    if everything or args.trakt:
        connect_trakt(name)
    url = None
    if everything or args.cloudflare:
        url = connect_cloudflare(name, args.worker)
    if everything or args.cloudflare or args.new_link:
        # --cloudflare makes the link too when there's none yet: after a first run that stopped at Cloudflare.
        stored = "" if args.new_link else gh("secret", "list", "--repo", name, "--json", "name", "--jq", ".[].name")
        if "ADDON_KEY" in stored.split():
            if args.cloudflare or not confirm(
                "\n   You already have a private link. Make a new one? The old one stops working after the next run. "
                "[y/N] "
            ):
                say("\nDone. Your private link stays the same.")
                return
        jq = '.[] | select(.name == "ADDON_URL") | .value'
        url = url or gh("variable", "list", "--repo", name, "--json", "name,value", "--jq", jq).strip()
        if not url:
            sys.exit("Connect Cloudflare first: run this again with --cloudflare.")
        link = new_link(name, url)
        say(
            "\nDone. Your addon's private link (it works after the next run of the builder):\n\n"
            f"   {link}\n\n"
            "Open it on your phone or computer and press Install in Stremio. Keep it to yourself: anyone with\n"
            "the link can see your lists. If it ever leaks, run this again with --new-link."
        )
        return
    say("\nDone.")


if __name__ == "__main__":
    main()
