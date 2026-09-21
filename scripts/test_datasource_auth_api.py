#!/usr/bin/env python3
"""Flask API smoke test for datasource auth endpoints (temp DB, no network).

Run: python scripts/test_datasource_auth_api.py   (from repo root)
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_KEY = "api-smoke-credential-key"
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


def main():
    tmp = tempfile.mkdtemp(prefix="ds_auth_api_")
    from core.domain import build_spec
    from core.app import create_app

    spec = build_spec(
        slug="intelligence_web", port=8766, title_prefix="测试",
        scout_label="测试采集", agent_names=["测试"], theme_color="#722ed1",
        inbox_rel="../inbox/", db_filename="test_api", domain_key="research",
    )
    app = create_app(tmp, spec)
    client = app.test_client()

    print("== API smoke: datasource auth ==")
    # unauthenticated GET -> 401 (new require_auth)
    r = client.get("/api/datasources")
    check("GET list unauth -> 401", r.status_code == 401, f"got {r.status_code}")

    # login as built-in admin
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    check("admin login", r.status_code == 200, r.get_data(as_text=True)[:200])
    token = r.get_json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    # create with basic auth
    r = client.post("/api/datasources", headers=h, json={
        "name": "测试源", "url": "https://example.com/",
        "auth_type": "basic", "username": "alice", "password": "pw123",
    })
    check("POST create 201", r.status_code == 201, r.get_data(as_text=True)[:200])
    body = r.get_json()
    sid = body["id"]
    check("POST response masked (no credential)", "credential" not in body, str(body))
    check("POST response has_credentials", body.get("has_credentials") is True)
    check("POST response username masked", body.get("username") == "a***")
    check("POST response auth_type", body.get("auth_type") == "basic")

    # list + detail masked
    r = client.get("/api/datasources", headers=h)
    items = r.get_json()
    me = [i for i in items if i["id"] == sid][0]
    check("GET list masked", "credential" not in me and me["has_credentials"] is True)
    r = client.get(f"/api/datasources/{sid}", headers=h)
    check("GET detail masked", "credential" not in r.get_json())

    # plaintext never appears in any response
    raw = client.get("/api/datasources", headers=h).get_data(as_text=True)
    check("no plaintext in list response", "pw123" not in raw)

    # PUT name only -> credential kept (verify via decrypt on stored row)
    r = client.put(f"/api/datasources/{sid}", headers=h, json={"name": "改名"})
    check("PUT name 200", r.status_code == 200)
    from core.db import get_db
    from core.credentials import decrypt_secret
    db_path = os.path.join(tmp, "data", "test_api")
    with get_db(db_path) as conn:
        row = conn.execute("SELECT credential, username FROM datasources WHERE id=?", (sid,)).fetchone()
    check("PUT name kept credential", decrypt_secret(row["credential"]) == "pw123")
    check("PUT name kept username", row["username"] == "alice")

    # PUT new password
    r = client.put(f"/api/datasources/{sid}", headers=h, json={"password": "pw456"})
    with get_db(db_path) as conn:
        row = conn.execute("SELECT credential FROM datasources WHERE id=?", (sid,)).fetchone()
    check("PUT password re-encrypts", decrypt_secret(row["credential"]) == "pw456")

    # PUT empty password -> keep old
    client.put(f"/api/datasources/{sid}", headers=h, json={"password": ""})
    with get_db(db_path) as conn:
        row = conn.execute("SELECT credential FROM datasources WHERE id=?", (sid,)).fetchone()
    check("PUT empty password keeps old", decrypt_secret(row["credential"]) == "pw456")

    # PUT auth_type none -> cleared
    r = client.put(f"/api/datasources/{sid}", headers=h, json={"auth_type": "none"})
    body = r.get_json()
    check("PUT none 200", r.status_code == 200)
    with get_db(db_path) as conn:
        row = conn.execute("SELECT credential, username FROM datasources WHERE id=?", (sid,)).fetchone()
    check("PUT none clears credential", row["credential"] == "")
    check("PUT none clears username", row["username"] == "")
    check("PUT none has_credentials false", body["has_credentials"] is False)

    # unknown auth_type normalized
    r = client.put(f"/api/datasources/{sid}", headers=h, json={"auth_type": "weird"})
    check("PUT unknown auth_type -> none", r.get_json()["auth_type"] == "none")

    # project endpoints must not expose credential (re-arm creds first)
    client.put(f"/api/datasources/{sid}", headers=h,
               json={"auth_type": "basic", "username": "alice", "password": "pw123"})
    r = client.post("/api/projects", headers=h,
                    json={"name": "P1", "target_type": "company",
                          "target_name": "T", "datasource_ids": [sid]})
    check("create project 201", r.status_code == 201, r.get_data(as_text=True)[:200])
    pid = r.get_json()["id"]
    raw = client.get("/api/projects", headers=h).get_data(as_text=True)
    check("GET /api/projects no credential token",
          '"credential"' not in raw and "gAAAAA" not in raw)
    raw = client.get(f"/api/projects/{pid}", headers=h).get_data(as_text=True)
    check("GET project detail no credential", '"credential"' not in raw)
    ds_in = client.get(f"/api/projects/{pid}/datasources", headers=h).get_json()["datasources"]
    check("project datasources masked",
          ds_in and "credential" not in ds_in[0] and ds_in[0]["has_credentials"] is True)

    # missing env key -> 400 (create with password)
    os.environ.pop("CREDENTIALS_ENCRYPT_KEY")
    r = client.post("/api/datasources", headers=h, json={
        "name": "密钥缺失", "url": "https://x.com/",
        "auth_type": "basic", "username": "u", "password": "p",
    })
    check("missing key -> 400", r.status_code == 400, f"got {r.status_code}: {r.get_data(as_text=True)[:150]}")
    os.environ["CREDENTIALS_ENCRYPT_KEY"] = TEST_KEY

    # non-admin (role=user) cannot create
    # 注：种子 'user' 账号有既有 bug（_hash_password 被调两次、盐不一致，永远无法登录），
    # 这里直接用 create_user 造一个非管理员账号
    from core.db import create_user
    create_user(db_path, "tester", "测试用户", "test1234", role="user")
    r = client.post("/api/auth/login", json={"username": "tester", "password": "test1234"})
    check("user login", r.status_code == 200, r.get_data(as_text=True)[:200])
    uh = {"Authorization": f"Bearer {r.get_json()['token']}"}
    r = client.post("/api/datasources", headers=uh, json={"name": "x", "url": "https://x.com/"})
    check("non-admin create -> 403", r.status_code == 403, f"got {r.status_code}")
    r = client.get("/api/datasources", headers=uh)
    check("non-admin list (masked) ok", r.status_code == 200)

    print(f"\n{'=' * 40}\nRESULT: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
