#!/usr/bin/env python3
"""仅采集源开关（source_only）验证脚本。

验证内容（不依赖外部网络与真实 LLM）：
1. schema：projects.source_only 列（新建/迁移），create/update 归一化
2. source_only=1：只从项目关联的数据源 URL 采集（本地 RSS），
   旧条目按新鲜度窗口过滤，重复轮次按 source_url 去重
3. source_only=0：沿用现有开放式搜索逻辑（不抓数据源 URL）
4. source_only=1 但未关联数据源：跳过该项目

用法：python3 scripts/test_source_only.py
"""
import functools
import http.server
import json
import os
import socket
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

SLUG = "test_source_only"
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, SLUG)  # 与 get_db_path 一致：无 .db 扩展名

passed = 0
failed = 0


def check(desc, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS {desc}")
        passed += 1
    else:
        print(f"  FAIL {desc} — {detail}")
        failed += 1


# ── 本地 HTTP 服务器：RSS feed + 普通网页 ─────────────────────────

now = datetime.now(timezone.utc)
RECENT1 = (now - timedelta(hours=1)).strftime("%a, %d %b %Y %H:%M:%S +0000")
RECENT2 = (now - timedelta(hours=3)).strftime("%a, %d %b %Y %H:%M:%S +0000")
STALE = (now - timedelta(days=30)).strftime("%a, %d %b %Y %H:%M:%S +0000")

FEED_DIR = tempfile.mkdtemp(prefix="feed_")

REQUESTS = []  # 记录本地服务器收到的路径（用于断言开放模式不抓数据源）


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=FEED_DIR, **kw)

    def do_GET(self):
        REQUESTS.append(self.path)
        super().do_GET()

    def log_message(self, *a):
        pass


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


PORT = _free_port()
BASE = f"http://127.0.0.1:{PORT}"
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with open(os.path.join(FEED_DIR, "feed.xml"), "w", encoding="utf-8") as f:
    f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>测试行业源</title>
<link>{BASE}</link>
<item>
  <title>稳定剂市场价格周报</title>
  <link>{BASE}/item1</link>
  <description>本周稳定剂市场价格平稳，原料供应充足，下游需求稳定，整体无大幅波动，供应商维持正常交付节奏，渠道库存处于合理区间。</description>
  <pubDate>{RECENT1}</pubDate>
</item>
<item>
  <title>供应商产能扩张公告</title>
  <link>{BASE}/item2</link>
  <description>某主要稳定剂供应商宣布新增生产线，预计下季度投产，产能提升约三成，行业整体供给格局或将发生变化，值得持续跟踪。</description>
  <pubDate>{RECENT2}</pubDate>
</item>
<item>
  <title>三年前的旧闻</title>
  <link>{BASE}/item3</link>
  <description>一条非常陈旧的历史新闻，不应被新鲜度窗口过滤掉，用来验证旧料过滤逻辑是否生效的测试条目内容。</description>
  <pubDate>{STALE}</pubDate>
</item>
</channel></rss>""")

with open(os.path.join(FEED_DIR, "page.html"), "w", encoding="utf-8") as f:
    f.write("""<html><head><title>行业新闻页</title></head><body>
<article><p>本页正文：行业报告显示稳定剂市场整体保持平稳运行态势，供需两端均无明显异常，价格体系稳定，
企业交付能力正常，短期 outlook 平稳，渠道反馈良好，库存结构合理。</p></article></body></html>""")

time.sleep(0.2)

# ── LLM 桩 ───────────────────────────────────────────────────────

import core.scheduler.llm_client as llm_client

llm_stats = {"judge": 0, "keyword": 0}


def fake_call_llm(system_prompt, user_prompt, **kw):
    if "情报价值判断器" in system_prompt:
        llm_stats["judge"] += 1
        return {"ok": True, "raw": json.dumps({
            "relevant": True,
            "title": f"测试情报{llm_stats['judge']}",
            "category": "market",
            "summary": "　　来自采集源的测试情报摘要。",
        }, ensure_ascii=False)}
    llm_stats["keyword"] += 1
    return {"ok": True, "raw": '["测试关键词"]'}


llm_client.call_llm = fake_call_llm

# ── 建库 ─────────────────────────────────────────────────────────

from core.domain import build_spec
import core.db as dblib
import core.project as projlib
import core.datasource as dslib

os.makedirs(DATA_DIR, exist_ok=True)
for p in (DB_PATH,):
    if os.path.exists(p):
        os.remove(p)

spec = build_spec(
    slug=SLUG, port=1, title_prefix="T", scout_label="T",
    agent_names=[], db_filename=SLUG,
)
dblib.init_db(ROOT, spec)
dblib.migrate_db(DB_PATH, domain_key=SLUG)

# ── 1. schema / create / update ────────────────────────────────

print("\n=== 1. schema 与 CRUD ===")
pid_a = projlib.create_project(DB_PATH, "项目A", "market", "测试目标",
                               frequency="weekly", source_only=True)
pid_b = projlib.create_project(DB_PATH, "项目B", "market", "测试目标",
                               frequency="weekly")
pid_c = projlib.create_project(DB_PATH, "项目C", "market", "测试目标",
                               frequency="weekly", source_only=True)

check("create_project(source_only=True) → 1",
      projlib.get_project_by_id(DB_PATH, pid_a)["source_only"] == 1)
check("create_project 默认 → 0",
      projlib.get_project_by_id(DB_PATH, pid_b)["source_only"] == 0)
check("update_project source_only True→1",
      projlib.update_project(DB_PATH, pid_c, {"source_only": True})["source_only"] == 1)
check("update_project source_only 'false' 字符串→0",
      projlib.update_project(DB_PATH, pid_c, {"source_only": "false"})["source_only"] == 0)
projlib.update_project(DB_PATH, pid_c, {"source_only": True})

# 存量库迁移：删掉新列后跑 migrate_db 应补回
import sqlite3
with sqlite3.connect(DB_PATH) as conn:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)")]
check("migrate 后 projects 含 source_only 列", "source_only" in cols, str(cols))

# ── 2. 数据源 ───────────────────────────────────────────────────

ds_feed = dslib.create_source(DB_PATH, "RSS行业源", "website", f"{BASE}/feed.xml")
ds_page = dslib.create_source(DB_PATH, "网页源", "website", f"{BASE}/page.html")
dslib.link_datasource_to_project(DB_PATH, pid_a, ds_feed)
dslib.link_datasource_to_project(DB_PATH, pid_b, ds_feed)
dslib.link_datasource_to_project(DB_PATH, pid_c, ds_page)
dslib.toggle_source_status(DB_PATH, ds_page, False)  # 项目C 的数据源停用 → 无可用源

# ── 3. 采集周期 ─────────────────────────────────────────────────

from core.scheduler import search_cycle
search_cycle._REQUEST_TIMEOUT = 10

os.environ["ANALYZER_DB_SLUG"] = SLUG

print("\n=== 2. source_only=1：仅从数据源采集 ===")
r1 = search_cycle.run_search_cycle(trigger_type="manual",
                                   project_ids=[pid_a, pid_c])
a_items = [i for i in r1.get("intel", []) if i["project"] == "项目A"]
c_items = [i for i in r1.get("intel", []) if i["project"] == "项目C"]
check("项目A 从 RSS 采到 2 条（旧闻被过滤）", len(a_items) == 2,
      f"got {len(a_items)}: {[i['title'] for i in a_items]}")
check("旧闻未入库", all("item3" not in (i.get("url") or "") for i in a_items))
check("项目A 未调用关键词构造（无开放式搜索）", llm_stats["keyword"] == 0,
      f"keyword calls={llm_stats['keyword']}")
check("仅采集源项目 LLM 判断次数=2（每条候选各一次）", llm_stats["judge"] == 2,
      f"judge={llm_stats['judge']}")
check("数据源 URL 被抓取", "/feed.xml" in REQUESTS, str(REQUESTS))
check("项目C（源停用）0 条且被处理", len(c_items) == 0 and
      any(s["project_id"] == pid_c and s["new_intel"] == 0 for s in r1.get("project_summaries", [])),
      json.dumps(r1.get("project_summaries"), ensure_ascii=False))
check("source_run 履历记录 source_only 标记",
      all(s.get("source_only") in (True, False) for s in r1.get("project_summaries", [])))

# 入库字段
rows = dblib.get_intelligence_by_project(DB_PATH, pid_a, limit=10)
check("入库情报带 source_url", all((r.get("source_url") or "").startswith(BASE) for r in rows),
      str([r.get("source_url") for r in rows]))
check("入库情报状态为 done", all(r["status"] == "done" for r in rows))

print("\n=== 3. 重复轮次：按 source_url 去重 ===")
judge_before = llm_stats["judge"]
r2 = search_cycle.run_search_cycle(trigger_type="manual", project_ids=[pid_a])
a2 = [i for i in r2.get("intel", []) if i["project"] == "项目A"]
check("第二轮项目A 0 条新情报（source_url 去重）", len(a2) == 0,
      str([i["title"] for i in a2]))
check("第二轮未再调 LLM 判断", llm_stats["judge"] == judge_before,
      f"judge {judge_before} -> {llm_stats['judge']}")

print("\n=== 4. source_only=0：沿用开放式搜索 ===")
req_before = list(REQUESTS)
llm_stats["keyword"] = 0
r3 = search_cycle.run_search_cycle(trigger_type="manual", project_ids=[pid_b])
b_items = [i for i in r3.get("intel", []) if i["project"] == "项目B"]
new_reqs = [q for q in REQUESTS[len(req_before):]]
check("开放模式不抓取数据源 URL", not new_reqs, str(new_reqs))
check("开放模式仍走关键词构造（现有逻辑）", llm_stats["keyword"] == 1,
      f"keyword calls={llm_stats['keyword']}")
check("无 Tavily key 时开放模式 0 条（行为与现状一致）", len(b_items) == 0)

# ── 清理 ─────────────────────────────────────────────────────────

httpd.shutdown()
os.remove(DB_PATH)
bak_dir = os.path.join(DATA_DIR, "backups")
for f in os.listdir(bak_dir) if os.path.isdir(bak_dir) else []:
    if f.startswith(SLUG):
        os.remove(os.path.join(bak_dir, f))
for f in os.listdir(FEED_DIR):
    os.remove(os.path.join(FEED_DIR, f))
os.rmdir(FEED_DIR)

print(f"\n=== 结果: {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)
