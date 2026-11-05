"""UA110 迁移演练：拿生产库的一致性副本跑一遍启动路径，确认 28 条 history 能迁进 audit_logs。

只读生产库：宿主机先把库文件 cp 到快照目录并只读挂进容器，本脚本再在容器内
用 sqlite backup API 取一致快照，所有写操作都发生在 /tmp 的副本上。

跑法：
    SCRATCH=~/.hermes/cache/scratch/ua110-prod-snap && rm -rf $SCRATCH && mkdir -p $SCRATCH
    cp <prod>/intelligence_web/data/intelligence $SCRATCH/
    docker run --rm -v <checkout>:/w:ro -v $SCRATCH:/hostprod:ro -w /w \
        intelligence_web-research python /w/scripts/test_audit_logs_migration.py
"""
import os
import shutil
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

PROD_DB = '/hostprod/intelligence'          # 生产库（只读挂载）
WORK = '/tmp/ua110_prod_drill'
ROOT = os.path.join(WORK, 'root')

if os.path.exists(WORK):
    shutil.rmtree(WORK)
os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
os.makedirs('/tmp/inbox', exist_ok=True)

# 1) 一致性快照（WAL 安全）
#    生产库先被 cp 成一份普通文件（无 -wal，说明已 checkpoint），再在容器内
#    以可写方式打开并用 sqlite backup API 取一致快照 + 做一次完整性检查。
tmp_copy = '/tmp/ua110_prod_copy.db'
shutil.copyfile(PROD_DB, tmp_copy)
chk = sqlite3.connect(tmp_copy)
print('副本完整性检查:', chk.execute('PRAGMA integrity_check').fetchone()[0])
print('副本 journal_mode:', chk.execute('PRAGMA journal_mode').fetchone()[0])
dst = os.path.join(ROOT, 'data', 'intelligence')
out = sqlite3.connect(dst)
chk.backup(out)
chk.close()
out.close()


def counts(path):
    con = sqlite3.connect(path)   # 一次性副本，直接可写打开（WAL 只读打开需要 -shm）
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    c = {t: con.execute('SELECT COUNT(*) FROM [%s]' % t).fetchone()[0] for t in tables}
    con.close()
    return c


before = counts(dst)
print('副本迁移前：intelligence=%s history=%s audit_logs=%s'
      % (before.get('intelligence'), before.get('history'), before.get('audit_logs')))
assert 'audit_logs' not in before, '副本不该已有 audit_logs（生产尚未上线本功能）'

# 2) 走真实启动路径：init_db + migrate_db + 存量补齐
from core.domain import build_spec  # noqa: E402
from core.db import init_db, migrate_db, backfill_audit_logs_from_history  # noqa: E402

SPEC = build_spec(slug='intelligence_web', port=8799, title_prefix='演练', scout_label='演练',
                  agent_names=['演练'], theme_color='#000', inbox_rel='../inbox/',
                  db_filename='intelligence', domain_key='research')
init_db(ROOT, SPEC)
migrate_db(dst, domain_key='research')
n = backfill_audit_logs_from_history(dst)
print('补齐行数:', n)

con = sqlite3.connect(dst)
con.row_factory = sqlite3.Row
rows = con.execute('SELECT * FROM audit_logs ORDER BY created_at').fetchall()
print('audit_logs 行数:', len(rows))
print('样例:')
for r in rows[:3]:
    d = dict(r)
    print('  ', {k: d[k] for k in ('id', 'username', 'method', 'path', 'resource',
                                   'resource_id', 'status_code', 'detail', 'history_id', 'created_at')})
again = backfill_audit_logs_from_history(dst)
print('再跑一次补齐（应为 0）:', again)

after = counts(dst)
lost = {t: before[t] - after.get(t, 0) for t in before if before[t] - after.get(t, 0) > 0}
print('数据丢失检查:', lost or 'NONE')

ok = (n == before['history'] == len(rows) and again == 0 and not lost
      and all(r['history_id'] for r in rows)
      and all(r['created_at'].startswith('2026-07-23') for r in rows))
print('\n演练结论:', 'PASS' if ok else 'FAIL')
shutil.rmtree(WORK, ignore_errors=True)
sys.exit(0 if ok else 1)
