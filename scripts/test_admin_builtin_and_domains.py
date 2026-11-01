#!/usr/bin/env python3
"""UA100 冒烟：内置 admin 不可删除 + admin 必定可访问所有域（含私有域）。

隔离临时库 + app.test_client()，不碰线上数据。私有域判定读真实
config/domains.json（intelligence_sales = private），本测试只读不写该文件。
Run: python scripts/test_admin_builtin_and_domains.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CREDENTIALS_ENCRYPT_KEY"] = "api-smoke-credential-key"
os.environ.setdefault("JWT_SECRET", "ua100-smoke-secret")

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


def build(tmp, slug, port, db_filename, domain_key):
    from core.domain import build_spec
    from core.app import create_app
    spec = build_spec(slug=slug, port=port, title_prefix=slug,
                      scout_label=slug, agent_names=[slug], theme_color="#722ed1",
                      inbox_rel="../inbox/", db_filename=db_filename,
                      domain_key=domain_key)
    return create_app(tmp, spec)


def login(client, username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["token"]


def main():
    tmp = tempfile.mkdtemp(prefix="ua100_admin_")
    DB = tmp + "/data/test_admin_dom"
    research = build(tmp, "intelligence_web", 8766, "test_admin_dom", "research")
    sales = build(tmp, "intelligence_sales", 8767, "test_admin_dom_sales", "sales")
    rc, sc = research.test_client(), sales.test_client()

    from core.db import (create_user, set_user_roles, list_roles, update_user)

    admin = login(rc, "admin", "admin123")
    ah = {"Authorization": "Bearer " + admin}

    # ---- 1. 内置 admin 不可删除 -------------------------------------------
    r = rc.delete("/api/users/1", headers=ah)
    check("admin 删除自己 → 403", r.status_code == 403, r.get_json())
    check("403 提示内置管理员", "内置管理员" in (r.get_json() or {}).get("error", ""), r.get_json())
    r = rc.get("/api/users/1", headers=ah)
    check("admin 账号仍在", r.status_code == 200 and r.get_json().get("username") == "admin")

    # 用户名为 'admin' 的账号（非 id=1）同样受保护——验证
    # _is_builtin_admin_id 的 username 分支：先把内置 admin 改名，再建一个
    # id!=1 但用户名仍为 admin 的账号。
    update_user(DB, 1, {"username": "root_backup"})
    other_admin = create_user(DB, "admin", "x", "pass1234", role="user")
    r = rc.delete(f"/api/users/{other_admin}", headers=ah)
    check("用户名为 admin 的账号同样不可删除", r.status_code == 403, r.get_json())
    update_user(DB, 1, {"username": "admin"})

    # 普通用户仍可正常删除（保护不是「谁都删不掉」）
    plain = create_user(DB, "plainuser", "普通人", "pass1234", role="user")
    r = rc.delete(f"/api/users/{plain}", headers=ah)
    check("普通用户可删除 → 200", r.status_code == 200, r.get_json())

    # 非管理员不能删管理员
    pw = create_user(DB, "mgr", "管理员B", "pass1234", role="user")
    set_user_roles(tmp + "/data/test_admin_dom", pw,
                   [r_["id"] for r_ in list_roles(tmp + "/data/test_admin_dom") if r_["name"] == "power_user"])
    mgr = login(rc, "mgr", "pass1234")
    r = rc.delete("/api/users/1", headers={"Authorization": "Bearer " + mgr})
    check("非管理员删内置 admin → 403", r.status_code == 403, r.get_json())

    # ---- 2. admin 必定能访问所有域（含私有域） -----------------------------
    r = rc.get("/api/system/domains", headers=ah)
    slugs = {d["slug"] for d in r.get_json().get("domains", [])}
    check("admin 域切换器含私有域 intelligence_sales", "intelligence_sales" in slugs, slugs)
    r = sc.get("/api/intelligence?limit=1", headers=ah)
    check("admin 可访问私有域接口", r.status_code == 200, r.get_json())

    # 普通用户：看不到也进不了私有域
    u = create_user(DB, "viewer1", "读者", "pass1234", role="user")
    tok = login(rc, "viewer1", "pass1234")
    vh = {"Authorization": "Bearer " + tok}
    r = rc.get("/api/system/domains", headers=vh)
    slugs = {d["slug"] for d in r.get_json().get("domains", [])}
    check("普通用户看不到私有域", "intelligence_sales" not in slugs, slugs)
    r = sc.get("/api/intelligence?limit=1", headers=vh)
    check("普通用户进私有域 → 403", r.status_code == 403, r.get_json())

    # 授权后可进
    update_user(tmp + "/data/test_admin_dom", u, {"domains": "intelligence_sales"})
    tok = login(rc, "viewer1", "pass1234")
    r = sc.get("/api/intelligence?limit=1",
               headers={"Authorization": "Bearer " + tok})
    check("授权后普通用户可进私有域", r.status_code == 200, r.get_json())

    # ---- 3. 仅靠多角色关联持有 admin 的账号也不被域门禁误挡 -----------------
    # 用真实登录令牌（权限集与线上一致），只把 role 字段改回 'user'，
    # 模拟「role 字段非 admin、但 role_ids 持有 admin」的账号。
    import jwt as pyjwt
    multi = create_user(DB, "multiadmin", "多角色", "pass1234", role="user")
    admin_role_id = next(r_["id"] for r_ in list_roles(DB) if r_["name"] == "admin")
    set_user_roles(DB, multi, [admin_role_id])
    real = login(rc, "multiadmin", "pass1234")
    claims = pyjwt.decode(real, os.environ["JWT_SECRET"], algorithms=["HS256"])
    assert claims["role"] == "admin" and admin_role_id in claims["role_ids"], claims
    claims["role"] = "user"
    claims["domains"] = []
    tok = pyjwt.encode(claims, os.environ["JWT_SECRET"], algorithm="HS256")
    r = sc.get("/api/intelligence?limit=1", headers={"Authorization": "Bearer " + tok})
    check("多角色 admin 也可访问私有域", r.status_code == 200, r.get_json())
    r = rc.get("/api/system/domains", headers={"Authorization": "Bearer " + tok})
    slugs = {d["slug"] for d in (r.get_json() or {}).get("domains", [])}
    check("多角色 admin 域切换器含私有域", r.status_code == 200 and "intelligence_sales" in slugs, slugs)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
