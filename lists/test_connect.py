"""Offline tests for connect.py: no Trakt, no Cloudflare, no GitHub (the gh CLI is faked)."""

import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

import connect

REPO = "someone/tv-lists-builder"
CLIENT_ID = "FAKE-TRAKT-CLIENT-ID"
CF_TOKEN = "FAKE-CLOUDFLARE-TOKEN"
TRAKT_TOKEN = {"access_token": "FAKE-ACCESS", "refresh_token": "FAKE-REFRESH", "created_at": 1, "expires_in": 2}


class FakeGh:
    """Records the gh commands run, with what went in on standard input. The builder repo is private and
    already has the secrets named in `existing`, and `addon_url` as its ADDON_URL variable."""

    def __init__(self, existing=(), addon_url=""):
        self.runs = []
        self.existing = list(existing)
        self.addon_url = addon_url

    def __call__(self, args, input=None, **kwargs):
        self.runs.append((args, input))
        stdout = ""
        if args[1:3] == ["repo", "view"]:
            stdout = json.dumps({"isPrivate": True, "isFork": False, "nameWithOwner": REPO})
        elif args[1:3] == ["secret", "list"]:
            stdout = "\n".join(self.existing + list(self.stored()))
        elif args[1:3] == ["variable", "list"]:
            stdout = self.addon_url + "\n"
        elif args[1:4] == ["variable", "set", "ADDON_URL"]:
            self.addon_url = args[args.index("--body") + 1]
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    def stored(self):
        return {args[3]: value for args, value in self.runs if args[1:3] == ["secret", "set"]}

    def command_lines(self):
        return " ".join(" ".join(args) for args, _ in self.runs)


def trakt(responses):
    answers = iter(responses)

    def post(path, body):
        assert body["client_id"] == CLIENT_ID
        return next(answers)

    return post


CODES = (
    200,
    {
        "device_code": "D",
        "user_code": "FAKE-CODE",
        "verification_url": "https://trakt.tv/activate",
        "expires_in": 600,
        "interval": 1,
    },
)


def cloudflare_api(method, path, token):
    """An account with a workers.dev subdomain and no Worker yet, that accepts CF_TOKEN only."""
    if token != CF_TOKEN:
        return 400, {"errors": [{"code": 6003, "message": "Invalid request headers"}]}
    return {
        "/accounts": (200, {"result": [{"id": "fakeaccount"}]}),
        "/accounts/fakeaccount/workers/subdomain": (200, {"result": {"subdomain": "someone"}}),
    }.get(path, (404, {"errors": [{"code": 10007}]}))


class Secrets(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGh()
        for patcher in (mock.patch("subprocess.run", self.gh), mock.patch("time.sleep")):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.out = io.StringIO()
        redirect = contextlib.redirect_stdout(self.out)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def test_trakt_sign_in_shows_the_code_and_stores_the_sign_in(self):
        connect.connect_trakt(REPO, ask=lambda prompt: CLIENT_ID, post=trakt([CODES, (400, None), (200, TRAKT_TOKEN)]))
        self.assertIn("FAKE-CODE", self.out.getvalue())
        self.assertEqual(self.gh.stored(), {"TRAKT_CLIENT_ID": CLIENT_ID, "TRAKT_TOKEN_JSON": json.dumps(TRAKT_TOKEN)})

    def test_cloudflare_is_checked_then_stored(self):
        url = connect.connect_cloudflare(REPO, "tv-lists", ask=lambda prompt: CF_TOKEN, api=cloudflare_api)
        self.assertEqual(url, "https://tv-lists.someone.workers.dev")
        self.assertEqual(self.gh.stored(), {"CLOUDFLARE_API_TOKEN": CF_TOKEN, "CLOUDFLARE_ACCOUNT_ID": "fakeaccount"})
        self.assertIn(
            ["gh", "variable", "set", "ADDON_URL", "--repo", REPO, "--body", url], [a for a, _ in self.gh.runs]
        )

    def test_an_account_without_a_workers_dev_subdomain_is_explained(self):
        def api(method, path, token):
            if path == "/accounts":
                return 200, {"result": [{"id": "fakeaccount"}]}
            return 404, {"errors": [{"code": 10007, "message": "not found"}]}

        with self.assertRaises(SystemExit) as stop:
            connect.connect_cloudflare(REPO, "tv-lists", ask=lambda prompt: CF_TOKEN, api=api)
        self.assertIn("workers.dev subdomain", str(stop.exception))
        self.assertEqual(self.gh.stored(), {})

    def test_the_new_link_is_shown_once_and_stored(self):
        link = connect.new_link(REPO, "https://tv-lists.someone.workers.dev")
        key = self.gh.stored()["ADDON_KEY"]
        self.assertEqual(link, f"https://tv-lists.someone.workers.dev/{key}/")
        self.assertGreaterEqual(len(key), 32)

    def test_no_key_ever_goes_on_a_command_line(self):
        connect.connect_trakt(REPO, ask=lambda prompt: CLIENT_ID, post=trakt([CODES, (200, TRAKT_TOKEN)]))
        connect.new_link(REPO, "https://tv-lists.someone.workers.dev")
        for value in self.gh.stored().values():
            self.assertNotIn(value, self.gh.command_lines())


class Terminal(unittest.TestCase):
    """connect.py runs only in a terminal window of the person's own, never in an agent's shell."""

    def assertRefuses(self, stdin, stdout):
        with (
            mock.patch.object(sys, "argv", ["connect.py", "--repo", REPO]),
            mock.patch.object(sys, "stdin", stdin),
            mock.patch.object(sys, "stdout", stdout),
            mock.patch("subprocess.run", side_effect=AssertionError("ran gh")),
        ):
            with self.assertRaises(SystemExit) as stop:
                connect.main()
        self.assertIn("not through a coding agent", str(stop.exception))

    def test_refuses_without_a_terminal_to_read_keys_from(self):
        # A pipe, as in most agents' shells.
        self.assertRefuses(io.StringIO(), mock.Mock(isatty=lambda: True))

    def test_refuses_when_an_agent_reads_the_output(self):
        # Input that passes for a terminal, as an agent's empty input does on Windows, but the output captured:
        # the private link would land in the agent's chat.
        self.assertRefuses(mock.Mock(isatty=lambda: True), io.StringIO())

    def test_refuses_on_the_null_device(self):
        # What an agent's PowerShell gives a command on Windows: isatty() is true there, but it isn't a console.
        with open(os.devnull) as null_in, open(os.devnull, "w") as null_out:
            self.assertRefuses(null_in, null_out)


class RunningItAgain(unittest.TestCase):
    """connect.py as the person runs it a second time, after a first run that stopped part way."""

    def run_connect(self, gh, *flags, token=CF_TOKEN):
        connect_cloudflare = connect.connect_cloudflare
        out = io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["connect.py", "--repo", REPO, *flags]),
            mock.patch.object(connect, "own_terminal", return_value=True),
            mock.patch("shutil.which", return_value="gh"),
            mock.patch("subprocess.run", gh),
            mock.patch("builtins.input", side_effect=AssertionError("asked a question")),
            mock.patch.object(
                connect,
                "connect_cloudflare",
                lambda repo, worker: connect_cloudflare(repo, worker, ask=lambda prompt: token, api=cloudflare_api),
            ),
            contextlib.redirect_stdout(out),
        ):
            connect.main()
        return out.getvalue()

    def test_cloudflare_again_makes_the_link_when_there_is_none(self):
        # The first run stored the Trakt sign-in, then stopped at Cloudflare; its message says --cloudflare.
        gh = FakeGh(existing=["TRAKT_CLIENT_ID", "TRAKT_TOKEN_JSON"])
        out = self.run_connect(gh, "--cloudflare")
        key = gh.stored()["ADDON_KEY"]
        self.assertIn(f"https://tv-lists.someone.workers.dev/{key}/", out)

    def test_cloudflare_again_keeps_the_link(self):
        gh = FakeGh(
            existing=["TRAKT_CLIENT_ID", "TRAKT_TOKEN_JSON", "ADDON_KEY"],
            addon_url="https://tv-lists.someone.workers.dev",
        )
        out = self.run_connect(gh, "--cloudflare")
        self.assertNotIn("ADDON_KEY", gh.stored())
        self.assertIn("Your private link stays the same", out)

    def test_cloudflare_again_makes_a_new_link_when_its_address_changed(self):
        # The person renamed their workers.dev subdomain: the old link stops working at the next run.
        gh = FakeGh(
            existing=["TRAKT_CLIENT_ID", "TRAKT_TOKEN_JSON", "ADDON_KEY"],
            addon_url="https://tv-lists.oldname.workers.dev",
        )
        out = self.run_connect(gh, "--cloudflare")
        key = gh.stored()["ADDON_KEY"]
        self.assertIn("address changed", out)
        self.assertIn(f"https://tv-lists.someone.workers.dev/{key}/", out)

    def test_a_rejected_token_stops_before_any_question(self):
        gh = FakeGh(existing=["TRAKT_CLIENT_ID", "TRAKT_TOKEN_JSON"])
        with self.assertRaises(SystemExit) as stop:
            self.run_connect(gh, "--cloudflare", token="FAKE-WRONG-TOKEN")
        self.assertIn("didn't accept this token", str(stop.exception))
        self.assertEqual(gh.stored(), {})


if __name__ == "__main__":
    unittest.main()
