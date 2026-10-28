"""Offline tests for cloudflare.py, against a fake Cloudflare API on localhost that follows the direct upload
protocol for Workers static assets (as Cloudflare's own CLI, wrangler, uses it)."""

import base64
import contextlib
import email.parser
import email.policy
import io
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import build
import cloudflare

TOKEN = "FAKE-CLOUDFLARE-TOKEN"
ACCOUNT = "fakeaccount"
KEY = "FAKE-ADDON-KEY-0123456789abcdefghij"


def fake_jwt(claims):
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"e30.{payload}.sig"


class FakeCloudflare(BaseHTTPRequestHandler):
    """Records every call in server.calls; answers like the real API."""

    def log_message(self, *args):
        pass

    def answer(self, result, status=200):
        body = json.dumps({"success": True, "errors": [], "result": result}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def parts(self, body):
        message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
            f"Content-Type: {self.headers['Content-Type']}\r\n\r\n".encode() + body
        )
        return {p.get_param("name", header="content-disposition"): p for p in message.iter_parts()}

    def handle_any(self):
        server = self.server
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        path = self.path.replace(f"/client/v4/accounts/{ACCOUNT}", "")
        call = {"method": self.command, "path": path, "auth": self.headers["Authorization"], "body": body}
        server.calls.append(call)
        if path == "/workers/scripts/tv-lists/assets-upload-session":
            manifest = json.loads(body)["manifest"]
            server.manifest = manifest
            new = sorted({e["hash"] for e in manifest.values()} - server.stored)
            return self.answer(
                {"jwt": server.upload_jwt if new else "COMPLETED-NOTHING-NEW", "buckets": [new] if new else []}
            )
        if path == "/workers/assets/upload?base64=true":
            assert call["auth"] == f"Bearer {server.upload_jwt}"
            for digest, part in self.parts(body).items():
                server.stored.add(digest)
                server.files[digest] = (base64.b64decode(part.get_content()), part.get_content_type())
            return self.answer({"jwt": "COMPLETED"}, 201)
        if path.startswith("/workers/assets/upload/"):
            assert call["auth"] == f"Bearer {server.upload_jwt}"
            digest = path.rsplit("/", 1)[1]
            server.stored.add(digest)
            server.files[digest] = (body, self.headers.get_content_type())
            return self.answer({"jwt": "COMPLETED"} if server.stored >= set(server.hashes()) else {}, 201)
        if path == "/workers/scripts/tv-lists":
            server.metadata = json.loads(self.parts(body)["metadata"].get_content())
            return self.answer({"id": "tv-lists"})
        if path == "/workers/scripts/tv-lists/subdomain":
            server.subdomain = json.loads(body)
            return self.answer(server.subdomain)
        self.send_error(404)

    do_GET = do_POST = do_PUT = handle_any


class Server(ThreadingHTTPServer):
    def __init__(self, single_uploads=False):
        super().__init__(("127.0.0.1", 0), FakeCloudflare)
        self.calls, self.stored, self.files, self.manifest = [], set(), {}, {}
        self.upload_jwt = fake_jwt({"wrangler_single_asset_uploads": single_uploads})

    def hashes(self):
        return [e["hash"] for e in self.manifest.values()]


class Publish(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.site = Path(tmp.name) / "site"
        metas = [{"id": f"tt{i:07d}", "type": "movie", "name": str(i)} for i in range(150)]
        build.write_addon(self.site, {"addon_id": "x", "name": "Lists", "description": "d"}, [("w", "W", metas)])

    def serve(self, server):
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def publish(self, server):
        cf = cloudflare.Cloudflare(TOKEN, ACCOUNT, api=f"http://127.0.0.1:{server.server_port}/client/v4")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cloudflare.publish(cf, self.site, KEY, "tv-lists")
        return out.getvalue()

    def check_served(self, server):
        # Every file sits under the private key, and Cloudflare got exactly its bytes and type.
        self.assertEqual(
            sorted(server.manifest),
            [
                f"/{KEY}/catalog/trakt/w.json",
                f"/{KEY}/catalog/trakt/w/skip=100.json",
                f"/{KEY}/index.html",
                f"/{KEY}/manifest.json",
            ],
        )
        for path, entry in server.manifest.items():
            data, ctype = server.files[entry["hash"]]
            self.assertEqual(data, (self.site / path.split("/", 2)[2]).read_bytes())
            self.assertEqual(ctype, "text/html" if path.endswith(".html") else "application/json")
        config = server.metadata["assets"]["config"]
        self.assertIn("Access-Control-Allow-Origin: *", config["_headers"])
        self.assertIn("X-Robots-Tag: noindex", config["_headers"])
        self.assertEqual(config["not_found_handling"], "none")
        self.assertEqual(server.subdomain, {"enabled": True, "previews_enabled": False})

    def test_upload_in_buckets_then_deploy(self):
        server = self.serve(Server())
        out = self.publish(server)
        self.check_served(server)
        self.assertEqual(server.metadata["assets"]["jwt"], "COMPLETED")
        self.assertNotIn("main_module", server.metadata)  # static files only, no Worker code
        api_calls = [c for c in server.calls if "/assets/upload" not in c["path"]]
        self.assertTrue(all(c["auth"] == f"Bearer {TOKEN}" for c in api_calls))
        self.assertIn("Published 4 files (4 changed)", out)
        for secret in (TOKEN, KEY, ACCOUNT):
            self.assertNotIn(secret, out)

    def test_one_file_per_request_when_cloudflare_asks_for_it(self):
        server = self.serve(Server(single_uploads=True))
        self.publish(server)
        self.check_served(server)
        self.assertEqual(len([c for c in server.calls if c["path"].startswith("/workers/assets/upload/")]), 4)

    def test_nothing_new_uploads_nothing(self):
        server = self.serve(Server())
        self.publish(server)
        server.calls.clear()
        out = self.publish(server)
        self.assertEqual([c["path"] for c in server.calls if "/workers/assets/upload" in c["path"]], [])
        self.assertEqual(server.metadata["assets"]["jwt"], "COMPLETED-NOTHING-NEW")
        self.assertIn("(0 changed)", out)


class Settings(unittest.TestCase):
    def test_worker_name_from_the_addon_url(self):
        self.assertEqual(cloudflare.worker_name("https://tv-lists.someone.workers.dev"), "tv-lists")
        self.assertIsNone(cloudflare.worker_name("https://tv-lists.example.com"))
        self.assertIsNone(cloudflare.worker_name("tv-lists.someone.workers.dev"))

    def test_keys_made_by_connect_are_accepted(self):
        import secrets

        self.assertTrue(cloudflare.KEY.fullmatch(secrets.token_urlsafe(24)))
        self.assertFalse(cloudflare.KEY.fullmatch("short"))
        self.assertFalse(cloudflare.KEY.fullmatch("a/b" * 20))


if __name__ == "__main__":
    unittest.main()
