#!/usr/bin/env python3
"""
AI Analyst Redesign Verification Script.
Tests data layer, extraction, and reporting APIs.
Usage: python scripts/test_analyst.py [base_url]
"""
import sys, requests, json

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8766"

# Get auth token (admin/admin123)
def get_token():
    try:
        r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=5)
        if r.ok:
            return r.json().get('token', '')
    except Exception:
        pass
    return ""

HEADERS = {"Authorization": f"Bearer {get_token()}"} if get_token() else {}

passed = 0
failed = 0

def check(desc, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  ✅ {desc}")
        passed += 1
    else:
        print(f"  ❌ {desc} — {detail}")
        failed += 1

# ── 1. Data Layer ──────────────────────────────────────────
print("\n=== 数据层 ===")

r = requests.get(f"{BASE}/api/extract/rules", headers=HEADERS, timeout=5)
if r.status_code == 200:
    rules = r.json()
    check("提取规则 API 可用", True)
    check(f"内置规则 ≥2 (实际 {len(rules)})", len(rules) >= 2, f"got {len(rules)}")
else:
    check("提取规则 API 可用", False, f"status={r.status_code}")
    rules = []

r = requests.get(f"{BASE}/api/reports/templates", headers=HEADERS, timeout=5)
if r.status_code == 200:
    templates = r.json()
    check("报告模板 API 可用", True)
    check(f"内置模板 ≥4 (实际 {len(templates)})", len(templates) >= 4, f"got {len(templates)}")
else:
    check("报告模板 API 可用", False, f"status={r.status_code}")
    templates = []

r = requests.get(f"{BASE}/api/reports/scheduler", headers=HEADERS, timeout=5)
if r.status_code == 200:
    sched = r.json()
    check("调度器状态 API 可用", True)
    check("调度器已启用", sched.get("scheduler_enabled") == 1, f"got {sched.get('scheduler_enabled')}")
else:
    check("调度器状态 API 可用", False, f"status={r.status_code}")
    sched = {}

# ── 2. Extraction Functions ────────────────────────────────
print("\n=== 抽取功能 ===")

r = requests.get(f"{BASE}/api/extract/stats", headers=HEADERS, timeout=5)
if r.status_code == 200:
    stats = r.json()
    check("抽取统计 API 可用", True)
    check(f"总情报数 > 0", stats.get("total_intelligence", 0) > 0, f"got {stats.get('total_intelligence')}")
    check(f"已抽取 ≥ 0", stats.get("extracted", 0) >= 0, f"got {stats.get('extracted')}")
else:
    check("抽取统计 API 可用", False, f"status={r.status_code}")
    stats = {}

# ── 3. Reporting Functions ─────────────────────────────────
print("\n=== 报告功能 ===")

r = requests.get(f"{BASE}/api/reports/overview", headers=HEADERS, timeout=5)
if r.status_code == 200:
    overview = r.json()
    check("报告概览 API 可用", True)
    check(f"有 {len(overview)} 个报告模板", len(overview) > 0, f"got {len(overview)}")
else:
    check("报告概览 API 可用", False, f"status={r.status_code}")
    overview = []

r = requests.get(f"{BASE}/api/extract/facts?limit=10", headers=HEADERS, timeout=5)
if r.status_code == 200:
    facts = r.json()
    check("事实查询 API 可用", True)
    check(f"有 {facts.get('total', 0)} 条结构化事实", facts.get("total", 0) >= 0)
else:
    check("事实查询 API 可用", False, f"status={r.status_code}")

# ── 4. CRUD Smoke Tests ────────────────────────────────────
print("\n=== CRUD 功能 ===")

# Create a temp rule
r = requests.post(f"{BASE}/api/extract/rules", headers={**HEADERS, "Content-Type": "application/json"},
    json={"name": "测试规则", "domain": "research", "description": "验证用规则", "scope": "full", "max_fields": 5, "enabled": True, "fields": [
        {"field_key": "test_name", "field_label": "测试名称", "field_type": "text", "is_required": 1, "sort_order": 1}
    ]}, timeout=5)
if r.status_code == 201:
    check("新建规则成功", True)
    new_rule_id = r.json().get("id")
    
    # Get it
    r2 = requests.get(f"{BASE}/api/extract/rules/{new_rule_id}", headers=HEADERS, timeout=5)
    check("获取规则详情", r2.status_code == 200, f"got {r2.status_code}")
    if r2.status_code == 200:
        check("含字段列表", "fields" in r2.json(), f"keys: {list(r2.json().keys())}")
    
    # Update it
    r3 = requests.put(f"{BASE}/api/extract/rules/{new_rule_id}", headers={**HEADERS, "Content-Type": "application/json"},
        json={"name": "测试规则（已更新）", "enabled": False, "fields": []}, timeout=5)
    check("更新规则", r3.status_code == 200, f"got {r3.status_code}")
    
    # Delete it
    r4 = requests.delete(f"{BASE}/api/extract/rules/{new_rule_id}", headers=HEADERS, timeout=5)
    check("删除规则", r4.status_code == 200, f"got {r4.status_code}")
else:
    check("新建规则成功", False, f"got {r.status_code}")
    print(f"    Response: {r.text[:200]}")

# Try to delete built-in rule (should fail with 403)
if rules:
    built_in = [r for r in rules if r.get("built_in") == 1]
    if built_in:
        r = requests.delete(f"{BASE}/api/extract/rules/{built_in[0]['id']}", headers=HEADERS, timeout=5)
        check("内置规则不可删除 (403)", r.status_code == 403, f"got {r.status_code}")

# ── Summary ────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"汇总: {passed} 通过, {failed} 失败, 总计 {passed + failed}")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
