"""End-to-end RBAC API test against the live research container (8766).
Logs in as admin, then exercises the new role/permission/user-role endpoints.
Run AFTER `docker compose build research && up -d research`.
"""
import json, urllib.request, urllib.error, time

BASE = "http://localhost:8766"
RUN = str(int(time.time()))

def req(method, path, body=None, token=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, (json.loads(raw) if raw else {"raw": raw})
        except Exception:
            return e.code, {"raw": raw}

results = []
def check(name, cond, detail=""):
    results.append((name, cond, detail))
    print(("PASS" if cond else "FAIL"), name, ("| " + str(detail) if detail and not cond else ""))

# 1. Login as admin
st, data = req("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
check("login admin", st == 200 and "token" in data, f"st={st} data={data}")
tok = data.get("token", "")
check("admin role in login", data.get("user", {}).get("role") == "admin")

# 2. GET /api/roles
st, roles = req("GET", "/api/roles", token=tok)
check("GET roles 200", st == 200, f"st={st} data={roles}")
check("roles is list", isinstance(roles, list))
names = {r["name"] for r in roles} if isinstance(roles, list) else set()
check("4 built-in roles present", {"admin","power_user","user","agent"} <= names, names)
if isinstance(roles, list) and roles:
    check("role has permissions field", "permissions" in roles[0], roles[0])

# 3. GET /api/permissions
st, perms = req("GET", "/api/permissions", token=tok)
check("GET permissions 200", st == 200, f"st={st}")
check("11 permission codes", isinstance(perms, list) and len(perms) == 11, f"len={len(perms) if isinstance(perms,list) else perms}")

# 4. POST /api/roles — create
new_role_name = "api_test_role_x_" + RUN
st, created = req("POST", "/api/roles", {"name": new_role_name, "label": "测试角色", "description": "api test", "permissions": ["intel.view","intel.import"]}, token=tok)
check("POST create role 201", st == 201, f"st={st} data={created}")
check("created role has id", isinstance(created, dict) and created.get("id"), created)
rid = created.get("id") if isinstance(created, dict) else None
check("created role perms applied", isinstance(created, dict) and set(created.get("permissions",[]))=={"intel.view","intel.import"}, created.get("permissions") if isinstance(created,dict) else None)

# duplicate should 409
st, d = req("POST", "/api/roles", {"name": new_role_name}, token=tok)
check("duplicate role 409", st == 409, f"st={st}")

# 5. PUT /api/roles/<id> — update permissions
st, upd = req("PUT", f"/api/roles/{rid}", {"label": "改名", "permissions": ["intel.view","intel.import","audit.view"]}, token=tok)
check("PUT role 200", st == 200, f"st={st} data={upd}")
check("updated perms count 3", isinstance(upd, dict) and len(upd.get("permissions",[]))==3, upd.get("permissions") if isinstance(upd,dict) else None)

# 6. GET /api/me/permissions for admin
st, me = req("GET", "/api/me/permissions", token=tok)
check("me/permissions 200", st == 200, f"st={st}")
check("admin has all 11", isinstance(me, dict) and len(me.get("permissions",[]))==11, f"n={len(me.get('permissions',[])) if isinstance(me,dict) else me}")

# 7. User role assignment: create a user, assign roles
st, u = req("POST", "/api/users", {"username": "api_test_user_" + RUN, "display_name": "测试用户", "password": "pass123", "role_ids": [1, rid], "domains": []}, token=tok)
check("create user 201", st == 201, f"st={st} data={u}")
uid = u.get("id") if isinstance(u, dict) else None
check("user has role_ids", isinstance(u, dict) and isinstance(u.get("role_ids"), list) and len(u.get("role_ids"))==2, u.get("role_ids") if isinstance(u,dict) else None)
check("user role_names", isinstance(u, dict) and "admin" in u.get("role_names",[]) and new_role_name in u.get("role_names",[]), u.get("role_names") if isinstance(u,dict) else None)

# 8. GET user roles
st, ur = req("GET", f"/api/users/{uid}/roles", token=tok)
check("GET user roles 200", st == 200, f"st={st} data={ur}")
check("user roles match", isinstance(ur, dict) and set(ur.get("role_ids",[]))=={1, rid}, ur)

# 9. PUT user roles — change
st, ur2 = req("PUT", f"/api/users/{uid}/roles", {"role_ids": [rid]}, token=tok)
check("PUT user roles 200", st == 200, f"st={st} data={ur2}")
check("user now 1 role", isinstance(ur2, dict) and ur2.get("role_ids")==[rid], ur2)

# 10. me/permissions for the test user (re-login)
st, d2 = req("POST", "/api/auth/login", {"username": "api_test_user_" + RUN, "password": "pass123"})
check("login test user", st == 200, f"st={st}")
tok2 = d2.get("token","")
st, me2 = req("GET", "/api/me/permissions", token=tok2)
check("test user me/permissions 200", st == 200, f"st={st}")
# test user now only has editor role -> intel.view, intel.import, audit.view
check("test user perms = editor set", isinstance(me2, dict) and set(me2.get("permissions",[]))=={"intel.view","intel.import","audit.view"}, me2.get("permissions") if isinstance(me2,dict) else me2)

# 11. Authorization: test user (non-admin, editor-only) should NOT be able to manage roles
st, d3 = req("GET", "/api/roles", token=tok2)
check("non-admin GET roles 403", st == 403, f"st={st} data={d3}")

# 11b. New permission gates: projects / datasources / target_types write ops
#     test user (editor only) lacks these -> 403
st, d = req("POST", "/api/projects", {"name":"x","target_type":"company"}, token=tok2)
check("non-admin POST projects 403", st == 403, f"st={st}")
st, d = req("POST", "/api/datasources", {"name":"x","url":"http://x"}, token=tok2)
check("non-admin POST datasources 403", st == 403, f"st={st}")
st, d = req("POST", "/api/target_types", {"slug":"x","label":"x"}, token=tok2)
check("non-admin POST target_types 403", st == 403, f"st={st}")
# but READ (list) of these should still be allowed (login only) for intel viewers
st, d = req("GET", "/api/projects", token=tok2)
check("non-admin GET projects 200 (read ok)", st == 200, f"st={st}")
st, d = req("GET", "/api/datasources", token=tok2)
check("non-admin GET datasources 200 (read ok)", st == 200, f"st={st}")
st, d = req("GET", "/api/target_types", token=tok2)
check("non-admin GET target_types 200 (read ok)", st == 200, f"st={st}")

# 11c. admin CAN write projects (has projects.manage)
st, d = req("POST", "/api/projects", {"name":"rbac_probe_"+RUN, "target_type":"company"}, token=tok)
check("admin POST projects 201", st == 201, f"st={st} data={d}")
probe_pid = d.get('id') if isinstance(d, dict) else None
if probe_pid:
    st, d = req("DELETE", f"/api/projects/{probe_pid}", token=tok)
    check("admin DELETE probe project 200", st == 200, f"st={st}")

# 12. Cleanup: delete test role + disable test user
if rid:
    st, d = req("DELETE", f"/api/roles/{rid}", token=tok)
    check("cleanup delete role", st == 200, f"st={st}")
if uid:
    st, d = req("DELETE", f"/api/users/{uid}", token=tok)
    check("cleanup disable user", st == 200, f"st={st}")

# Summary
passed = sum(1 for _,c,_ in results if c)
print(f"\n==== {passed}/{len(results)} PASSED ====")
if passed < len(results):
    print("FAILURES:")
    for n,c,d in results:
        if not c:
            print(" -", n, "|", d)
