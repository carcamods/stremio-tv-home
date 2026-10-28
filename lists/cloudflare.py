#!/usr/bin/env python3
"""Publishes the built lists to the person's own Cloudflare account, at their private link.

Uploads the files of the site folder as the static assets of a Worker (no Worker code runs), inside a
folder named by the ADDON_KEY secret: the addon is served at <ADDON_URL>/<ADDON_KEY>/manifest.json and
nowhere else. Cloudflare keeps files it already has, so only changed files are uploaded. Uses Cloudflare's
direct upload API for Workers static assets.

Standard library only, so the GitHub Action needs no installs.

    CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=... ADDON_KEY=... \\
    ADDON_URL=https://tv-lists.<subdomain>.workers.dev python lists/cloudflare.py --site .state/site
"""

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.cloudflare.com/client/v4"
USER_AGENT = "stremio-tv-home-lists/1.0"
# Every response: readable by Stremio Web (CORS), kept out of search engines, and the private link isn't
# sent on to other sites as a referrer.
HEADERS = """/*
  Access-Control-Allow-Origin: *
  X-Robots-Tag: noindex, nofollow
  Referrer-Policy: no-referrer
"""
CONTENT_TYPES = {".json": "application/json", ".html": "text/html; charset=utf-8"}
COMPATIBILITY_DATE = "2025-09-01"
KEY = re.compile(r"[A-Za-z0-9_-]{32,}")
WORKER = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?")


class Cloudflare:
    def __init__(self, token, account_id, api=API):
        self.token = token
        self.base = f"{api}/accounts/{account_id}"

    def call(self, method, path, body=None, content_type="application/json", bearer=None, headers=None):
        """The result of a Cloudflare API call. Retries rate limits and server errors; anything else raises
        RuntimeError with Cloudflare's messages (which never contain the token)."""
        if body is not None and not isinstance(body, bytes):
            body = json.dumps(body).encode()
        all_headers = {
            "Authorization": f"Bearer {bearer or self.token}",
            "Content-Type": content_type,
            "User-Agent": USER_AGENT,
            **(headers or {}),
        }
        for attempt in range(5):
            req = urllib.request.Request(self.base + path, data=body, method=method, headers=all_headers)
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    return (json.loads(resp.read() or b"{}") or {}).get("result")
            except urllib.error.HTTPError as e:
                if (e.code == 429 or e.code >= 500) and attempt < 4:
                    time.sleep(min(int(e.headers.get("Retry-After") or 2**attempt), 60))
                    continue
                raise RuntimeError(f"{method} {path.split('?')[0]} -> HTTP {e.code}: {errors(e)}") from None
            except OSError as e:
                if attempt == 4:
                    raise RuntimeError(f"{method} {path.split('?')[0]}: {e!r}") from None
                time.sleep(2**attempt)
        raise RuntimeError(f"{method} {path}: still failing after retries")


def errors(http_error):
    try:
        body = json.loads(http_error.read() or b"{}")
        return "; ".join(f"{e.get('code')} {e.get('message')}" for e in body.get("errors") or []) or "no details"
    except (OSError, ValueError, AttributeError):
        return "no details"


def multipart(parts):
    """(body, content type) of a multipart/form-data request from (name, file name or None, type, bytes)."""
    boundary = "stremio-tv-home-" + secrets.token_hex(16)
    body = bytearray()
    for name, filename, ctype, data in parts:
        disposition = f'form-data; name="{name}"' + (f'; filename="{filename}"' if filename else "")
        body += f"--{boundary}\r\nContent-Disposition: {disposition}\r\nContent-Type: {ctype}\r\n\r\n".encode()
        body += data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def content_type(path):
    return CONTENT_TYPES.get(path.suffix, "application/octet-stream")


def asset_manifest(site, key):
    """({"/<key>/<path>": {"hash", "size"}} for every file of the site, {hash: file})."""
    manifest, files = {}, {}
    for path in sorted(p for p in site.rglob("*") if p.is_file()):
        data = path.read_bytes()
        # As in Cloudflare's direct upload example: 32 hex characters of a hash of the base64 contents plus
        # the extension (the extension too, because it sets the type the file is served with).
        digest = hashlib.sha256((base64.b64encode(data).decode() + path.suffix[1:]).encode()).hexdigest()[:32]
        manifest[f"/{key}/{path.relative_to(site).as_posix()}"] = {"hash": digest, "size": len(data)}
        files[digest] = path
    return manifest, files


def jwt_claims(jwt):
    try:
        payload = jwt.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError):
        return {}


def publish(cf, site, key, worker):
    """Uploads the site as the Worker's assets under /<key>/, deploys it and serves it on workers.dev."""
    manifest, files = asset_manifest(site, key)
    session = cf.call("POST", f"/workers/scripts/{worker}/assets-upload-session", {"manifest": manifest})
    upload_jwt, buckets = session["jwt"], session.get("buckets") or []
    # With nothing new to upload, the session's token already completes the upload.
    completion = None if buckets else upload_jwt
    one_by_one = jwt_claims(upload_jwt).get("wrangler_single_asset_uploads") is True
    for bucket in buckets:
        if one_by_one:
            for digest in bucket:
                path = files[digest]
                result = cf.call(
                    "POST", f"/workers/assets/upload/{digest}", path.read_bytes(), content_type(path), upload_jwt
                )
                completion = (result or {}).get("jwt") or completion
        else:
            body, ctype = multipart(
                [(d, d, content_type(files[d]), base64.b64encode(files[d].read_bytes())) for d in bucket]
            )
            result = cf.call("POST", "/workers/assets/upload?base64=true", body, ctype, upload_jwt)
            completion = (result or {}).get("jwt") or completion
    if not completion:
        raise RuntimeError("Cloudflare didn't confirm the upload; the next run tries again")

    metadata = {
        "assets": {
            "jwt": completion,
            "config": {"_headers": HEADERS, "html_handling": "auto-trailing-slash", "not_found_handling": "none"},
        },
        "compatibility_date": COMPATIBILITY_DATE,
    }
    body, ctype = multipart([("metadata", None, "application/json", json.dumps(metadata).encode())])
    cf.call("PUT", f"/workers/scripts/{worker}", body, ctype)
    cf.call(
        "POST",
        f"/workers/scripts/{worker}/subdomain",
        {"enabled": True, "previews_enabled": False},
        headers={"Cloudflare-Workers-Script-Api-Date": "2025-08-01"},
    )
    changed = sum(len(bucket) for bucket in buckets)
    print(f"Published {len(manifest)} files ({changed} changed) to your private link")


def worker_name(addon_url):
    """The Worker's name, from ADDON_URL (https://<worker>.<subdomain>.workers.dev)."""
    host = urllib.parse.urlsplit(addon_url).hostname or ""
    name = host.split(".")[0]
    return name if host.endswith(".workers.dev") and WORKER.fullmatch(name) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--site", type=Path, required=True)
    args = parser.parse_args()

    names = ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "ADDON_KEY", "ADDON_URL")
    env = {name: os.environ.get(name, "").strip() for name in names}
    missing = [name for name in names if not env[name]]
    if missing:
        sys.exit(f"Not set: {', '.join(missing)}. Run connect.py (see lists/README.md).")
    if not KEY.fullmatch(env["ADDON_KEY"]):
        sys.exit("ADDON_KEY isn't a key made by connect.py. Make a new one: run connect.py with --new-link.")
    worker = worker_name(env["ADDON_URL"])
    if not worker:
        sys.exit("ADDON_URL isn't https://<worker>.<subdomain>.workers.dev. Run connect.py with --cloudflare.")
    if not (args.site / "manifest.json").is_file():
        sys.exit(f"Nothing to publish: {args.site} has no manifest.json.")
    try:
        publish(
            Cloudflare(env["CLOUDFLARE_API_TOKEN"], env["CLOUDFLARE_ACCOUNT_ID"]), args.site, env["ADDON_KEY"], worker
        )
    except RuntimeError as e:
        sys.exit(f"Cloudflare: {e}")


if __name__ == "__main__":
    main()
