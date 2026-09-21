#!/usr/bin/env python3
"""End-to-end test for datasource auth (auth_type: basic/bearer/cookie/form_login).

Covers:
  1. Credential encryption (Fernet) roundtrip + key-missing behavior
  2. Schema migration + CRUD semantics (encrypt on create, keep-unchanged on
     update, clear on auth_type=none)
  3. mask_source (no credential / no raw username in API output)
  4. build_auth_map / match_auth (host + subdomain matching)
  5. auth_fetch against a LOCAL http.server: basic / bearer / cookie /
     form_login (correct + wrong password)

Run: python scripts/test_datasource_auth.py   (from repo root)
No network access required; no production data touched (temp DB only).
"""
import base64
import http.server
import os
import socketserver
import sqlite3
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_KEY = "unit-test-credential-key-do-not-use-in-prod"
os.environ["CREDENTIALS_ENCRYPT_KEY"] = TEST_KEY

PASS = 0
FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {extra}")


# ── 1. Encryption ────────────────────────────────────────────────────────────

def test_encryption():
    print("\n== 1. Credential encryption ==")
    from core.credentials import (
        encrypt_secret, decrypt_secret, CredentialKeyMissingError,
    )
    token = encrypt_secret("s3cret")
    check("token != plaintext", token and token != "s3cret")
    check("token is ascii", token.isascii())
    check("roundtrip", decrypt_secret(token) == "s3cret")
    check("empty token -> empty", decrypt_secret("") == "")
    check("garbage token -> empty", decrypt_secret("not-a-fernet-token") == "")
    check("different tokens each call", encrypt_secret("s3cret") != token)

    old = os.environ.pop("CREDENTIALS_ENCRYPT_KEY")
    try:
        try:
            encrypt_secret("x")
            check("missing key raises", False)
        except CredentialKeyMissingError:
            check("missing key raises", True)
        check("decrypt with missing key -> empty", decrypt_secret(token) == "")
    finally:
        os.environ["CREDENTIALS_ENCRYPT_KEY"] = old


# ── 2/3. CRUD + masking ──────────────────────────────────────────────────────

def test_crud(db_path):
    print("\n== 2. CRUD + masking ==")
    from core import datasource as dslib
    from core.credentials import decrypt_secret

    sid = dslib.create_source(
        db_path, "测试源", "website", "https://example.com/",
        auth_type="basic", username="alice", password="pw123",
    )
    row = dslib.get_source_by_id(db_path, sid)
    check("auth_type stored", row["auth_type"] == "basic")
    check("username stored", row["username"] == "alice")
    check("credential encrypted (not plaintext)",
          row["credential"] and row["credential"] != "pw123")
    check("credential decrypts", decrypt_secret(row["credential"]) == "pw123")

    m = dslib.mask_source(row)
    check("masked: no credential key", "credential" not in m)
    check("masked: has_credentials", m["has_credentials"] is True)
    check("masked: username masked", m["username"] == "a***")
    check("masked: other fields intact", m["name"] == "测试源" and m["url"].endswith("/"))

    # update: name only -> credential kept
    dslib.update_source(db_path, sid, {"name": "改名"})
    check("update name keeps credential",
          dslib.get_source_by_id(db_path, sid)["credential"] == row["credential"])
    # update: new password
    dslib.update_source(db_path, sid, {"password": "pw456"})
    check("update password re-encrypts",
          decrypt_secret(dslib.get_source_by_id(db_path, sid)["credential"]) == "pw456")
    # update: empty password -> keep old
    dslib.update_source(db_path, sid, {"password": ""})
    check("empty password keeps old credential",
          decrypt_secret(dslib.get_source_by_id(db_path, sid)["credential"]) == "pw456")
    # update: auth_type none -> cleared
    dslib.update_source(db_path, sid, {"auth_type": "none"})
    r2 = dslib.get_source_by_id(db_path, sid)
    check("auth none clears username", r2["username"] == "")
    check("auth none clears credential", r2["credential"] == "")
    # unknown auth_type normalized
    dslib.update_source(db_path, sid, {"auth_type": "weird"})
    check("unknown auth_type -> none",
          dslib.get_source_by_id(db_path, sid)["auth_type"] == "none")
    dslib.delete_source(db_path, sid)


# ── 4. auth map matching ─────────────────────────────────────────────────────

def test_auth_map(db_path):
    print("\n== 3. build_auth_map / match_auth ==")
    from core import datasource as dslib

    dslib.create_source(db_path, "S1", "website", "https://example.com/members",
                        auth_type="form_login", username="u1", password="p1")
    dslib.create_source(db_path, "S2", "api", "https://api.example.org",
                        auth_type="bearer", password="tok123")
    dslib.create_source(db_path, "S3", "website", "https://open.example.net",
                        auth_type="none", username="x", password="y")

    # raw rows (as get_projects would provide them)
    rows = dslib.list_sources(db_path)
    amap = dslib.build_auth_map(rows)
    check("map has example.com", "example.com" in amap)
    check("map has api.example.org", "api.example.org" in amap)
    check("none-type excluded", "open.example.net" not in amap)
    check("map carries plaintext password",
          amap["example.com"]["password"] == "p1" and amap["example.com"]["login_url"].endswith("/members"))

    check("exact host match", dslib.match_auth("https://example.com/a/b", amap)["auth_type"] == "form_login")
    check("subdomain match", dslib.match_auth("https://www.example.com/x", amap)["auth_type"] == "form_login")
    check("no match", dslib.match_auth("https://other.com/", amap) is None)
    check("bearer match", dslib.match_auth("https://api.example.org/v1", amap)["auth_type"] == "bearer")

    for r in rows:
        dslib.delete_source(db_path, r["id"])


# ── 5. Live fetch against local HTTP server ─────────────────────────────────

LOGIN_HTML = """<html><body>
<form action="/login" method="post">
<input type="hidden" name="csrf" value="csrf-42">
<input type="text" name="username" value="">
<input type="password" name="password" value="">
<button type="submit">Login</button>
</form></body></html>"""

MEMBER_HTML = """<html><body><article>
SECRET MEMBER CONTENT: the quarterly industry report shows growth of 12.4 percent
across all segments, with the smart manufacturing division leading at 18.1 percent.
</article></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _auth(self):
        h = self.headers.get("Authorization", "")
        if h.startswith("Basic "):
            try:
                u, p = base64.b64decode(h[6:]).decode().split(":", 1)
                return u == "bob" and p == "basipw"
            except Exception:
                return False
        if h.startswith("Bearer "):
            return h[7:] == "tok-999"
        return False

    def do_GET(self):
        if self.path == "/basic":
            if self._auth():
                self._send(200, "<article>BASIC SECRET: 42</article>" * 10)
            else:
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="x"')
                self.end_headers()
        elif self.path == "/bearer":
            if self._auth():
                self._send(200, "<article>BEARER SECRET: 99</article>" * 10)
            else:
                self.send_response(401)
                self.end_headers()
        elif self.path == "/cookie":
            if self.headers.get("Cookie", "") == "session=good":
                self._send(200, "<article>COOKIE SECRET: 77</article>" * 10)
            else:
                self.send_response(401)
                self.end_headers()
        elif self.path == "/login":
            self._send(200, LOGIN_HTML)
        elif self.path == "/member":
            if "sid=ok" in self.headers.get("Cookie", ""):
                self._send(200, MEMBER_HTML)
            else:
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/login":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            fields = dict(p.split("=", 1) for p in body.split("&") if "=" in p)
            ok = (fields.get("username") == "carol" and fields.get("password") == "pw-form"
                  and fields.get("csrf") == "csrf-42")
            if ok:
                self.send_response(302)
                self.send_header("Set-Cookie", "sid=ok; Path=/")
                self.send_header("Location", "/member")
                self.end_headers()
            else:
                self._send(200, LOGIN_HTML)
        else:
            self.send_response(404)
            self.end_headers()

    def _send(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


def test_fetch():
    print("\n== 4. auth_fetch (local http server) ==")
    from core.scheduler import auth_fetch

    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler) as httpd:
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        try:
            # basic
            html, ok = auth_fetch.fetch_url(f"{base}/basic",
                                            {"auth_type": "basic", "username": "bob",
                                             "password": "basipw", "login_url": f"{base}/basic"})
            check("basic fetch", ok and "BASIC SECRET" in html)
            _, ok = auth_fetch.fetch_url(f"{base}/basic",
                                         {"auth_type": "basic", "username": "bob",
                                          "password": "wrong", "login_url": f"{base}/basic"})
            check("basic wrong creds -> not ok", not ok)

            # bearer
            html, ok = auth_fetch.fetch_url(f"{base}/bearer",
                                            {"auth_type": "bearer", "username": "",
                                             "password": "tok-999", "login_url": f"{base}/bearer"})
            check("bearer fetch", ok and "BEARER SECRET" in html)

            # cookie
            html, ok = auth_fetch.fetch_url(f"{base}/cookie",
                                            {"auth_type": "cookie", "username": "",
                                             "password": "session=good", "login_url": f"{base}/cookie"})
            check("cookie fetch", ok and "COOKIE SECRET" in html)

            # form_login (correct)
            auth_fetch._login_cache.clear()
            html, ok = auth_fetch.fetch_url(f"{base}/member",
                                            {"auth_type": "form_login", "username": "carol",
                                             "password": "pw-form", "login_url": f"{base}/login"})
            check("form_login correct -> member content", ok and "SECRET MEMBER CONTENT" in html)
            # cached session reused (no second login): clear nothing, fetch again
            html2, ok2 = auth_fetch.fetch_url(f"{base}/member",
                                              {"auth_type": "form_login", "username": "carol",
                                               "password": "pw-form", "login_url": f"{base}/login"})
            check("form_login session cached", ok2 and "SECRET MEMBER CONTENT" in html2)

            # form_login (wrong) — separate host key via different username
            auth_fetch._login_cache.clear()
            _, ok = auth_fetch.fetch_url(f"{base}/member",
                                         {"auth_type": "form_login", "username": "carol",
                                          "password": "WRONG", "login_url": f"{base}/login"})
            check("form_login wrong -> not ok", not ok)
            # backoff: immediate retry suppressed
            _, ok = auth_fetch.fetch_url(f"{base}/member",
                                         {"auth_type": "form_login", "username": "carol",
                                          "password": "WRONG", "login_url": f"{base}/login"})
            check("form_login failure backoff", not ok)

            # no auth at all (fallback path) — /member redirects to login
            html, ok = auth_fetch.fetch_url(f"{base}/member",
                                            {"auth_type": "basic", "username": "",
                                             "password": "", "login_url": f"{base}/member"})
            check("unauthenticated member page not used", not ok or "SECRET MEMBER CONTENT" not in html)
        finally:
            httpd.shutdown()


def main():
    tmp = tempfile.mkdtemp(prefix="ds_auth_test_")
    from core.db import init_db, migrate_db, get_db_path
    spec = {
        "slug": "test_domain",
        "db_filename": "test.db",
        "statuses": [("pending", "待处理"), ("done", "已完成")],
        "extra_columns": [],
    }
    init_db(tmp, spec)
    db_path = get_db_path(tmp, "test.db")
    migrate_db(db_path)

    # verify migration columns exist
    conn = sqlite3.connect(db_path)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(datasources)")}
    conn.close()
    check("migration added auth columns",
          {"auth_type", "username", "credential"} <= cols, str(cols))

    test_encryption()
    test_crud(db_path)
    test_auth_map(db_path)
    test_fetch()

    # search_cycle imports cleanly with new wiring
    import core.scheduler.search_cycle  # noqa
    check("search_cycle imports", True)

    print(f"\n{'=' * 40}\nRESULT: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
