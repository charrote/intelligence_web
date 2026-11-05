"""UA110 验收脚本：操作日志（audit_logs）采集 + 查询 + history 存量迁移。

跑法（推荐在 app 镜像里跑，用生产依赖与生产代码布局）：
    docker run --rm -v <checkout>:/w:ro -w /w intelligence_web-research \
        python /w/scripts/test_audit_logs.py
本机有 flask/pyjwt 时也可以：python scripts/test_audit_logs.py
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ['JWT_SECRET'] = 'ua110' + '-test-secret'

TEST_ROOT = os.environ.get('UA110_TEST_ROOT') or os.path.join('/tmp', 'ua110_root')
if os.path.exists(TEST_ROOT):
    shutil.rmtree(TEST_ROOT)
os.makedirs(os.path.join(TEST_ROOT, 'data'), exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(TEST_ROOT), 'inbox'), exist_ok=True)

import jwt as pyjwt  # noqa: E402
from core.domain import build_spec  # noqa: E402
from core.app import create_app  # noqa: E402
from core.db import (get_db_path, add_history, backfill_audit_logs_from_history,  # noqa: E402
                     add_audit_log)

FAIL = []


def check(name, cond, extra=None):
    print(('  PASS  ' if cond else '  FAIL  ') + name + (('  | ' + str(extra)) if extra else ''))
    if not cond:
        FAIL.append(name)


print('=== 启动（create_app: init_db + migrate_db + 存量补齐）===')
SPEC = build_spec(
    slug='intelligence_web', port=8799, title_prefix='测试域', scout_label='测试采集',
    agent_names=['测试员'], theme_color='#722ed1', inbox_rel='../inbox/',
    db_filename='intelligence', domain_key='research',
)
app = create_app(TEST_ROOT, SPEC)
app.config['TESTING'] = True
db_path = get_db_path(TEST_ROOT, 'intelligence')

with app.app_context():
    pass

# ---------------------------------------------------------------- 1. 建表
print('\n=== 1. audit_logs 表 ===')
cols = sqlite3.connect(db_path).execute('PRAGMA table_info(audit_logs)').fetchall()
col_names = [c[1] for c in cols]
check('audit_logs 表已创建', bool(col_names), col_names)
for needed in ('user_id', 'username', 'method', 'path', 'resource', 'resource_id',
               'status_code', 'ip_address', 'user_agent', 'detail', 'history_id', 'created_at'):
    check('列 %s 存在' % needed, needed in col_names)

# ------------------------------------------------- 2. history 存量迁移（补齐）
print('\n=== 2. history 存量迁移到 audit_logs ===')
# 模拟存量履历（seed 演示数据同构：只有 action/detail/created_at）
hist_ids = []
for i in range(3):
    hist_ids.append(add_history(db_path, 1, '新增情报', '来自 scout 自动采集 #%d' % i))
add_history(db_path, 2, '状态变更: pending -> active', '与目标客户关注方向一致')
before = backfill_audit_logs_from_history(db_path)
check('补齐 4 条 history 履历', before == 4, before)
again = backfill_audit_logs_from_history(db_path)
check('重复执行补齐为 0（幂等，按 history_id 去重）', again == 0, again)

con = sqlite3.connect(db_path)
con.row_factory = sqlite3.Row
mig = con.execute("SELECT * FROM audit_logs WHERE history_id IS NOT NULL ORDER BY id").fetchall()
check('迁移行数 = 4', len(mig) == 4, len(mig))
m0 = dict(mig[0])
check('迁移行保留原时间', m0['created_at'].startswith('2'), m0['created_at'])
check('迁移行 resource=intelligence', m0['resource'] == 'intelligence', m0['resource'])
check('迁移行 resource_id = 情报 ID', m0['resource_id'] == '1', m0['resource_id'])
check('迁移行 detail 保住 action+detail', '新增情报' in m0['detail'] and 'scout' in m0['detail'], m0['detail'])
check('迁移行没有的字段留空（method）', m0['method'] == '', repr(m0['method']))
check('迁移行没有的字段留空（username）', m0['username'] == '', repr(m0['username']))
check('迁移行没有的字段留空（status_code NULL）', m0['status_code'] is None, repr(m0['status_code']))
check('迁移行没有的字段留空（ip_address）', m0['ip_address'] == '', repr(m0['ip_address']))

# ------------------------------------------------------------------ 3. HTTP 层
print('\n=== 3. HTTP 层（test_client + 真实状态码）===')
cl = app.test_client()
tok = pyjwt.encode({
    'user_id': 1, 'username': 'admin', 'role': 'admin', 'domains': [],
    'role_ids': [1], 'permission_codes': ['all'],
    'exp': datetime.utcnow() + timedelta(hours=1), 'iat': datetime.utcnow(),
}, 'ua110' + '-test-secret', algorithm='HS256')
AUTH = {'Authorization': 'Bear' + 'er ' + tok}

r = cl.get('/api/audit/logs')
check('无 token → 401', r.status_code == 401, r.status_code)

r = cl.get('/api/audit/logs', headers=AUTH)
body = r.get_json()
check('GET /api/audit/logs → 200', r.status_code == 200, r.status_code)
check('UA110 主症状修复：total>0 时 items 不再为空',
      body['total'] == 4 and len(body['items']) == 4, (body['total'], len(body['items'])))
check('响应带 users 列表（用户下拉框用）', isinstance(body.get('users'), list), body.get('users'))

# 写操作 → 采集
stamp = datetime.now().strftime('%H%M%S')
r = cl.post('/api/intelligence', headers=AUTH, json={
    'title': 'UA110 采集验证 %s' % stamp, 'content': '验证操作日志采集层', 'category': '行业',
})
check('POST /api/intelligence → 201', r.status_code == 201, (r.status_code, r.get_json()))
new_intel_id = (r.get_json() or {}).get('id')

r = cl.get('/api/audit/logs?limit=5', headers=AUTH)
body = r.get_json()
top = body['items'][0]
check('写操作被采集（total 变 5）', body['total'] == 5, body['total'])
check('method 正确', top['method'] == 'POST', top['method'])
check('path 正确', top['path'] == '/api/intelligence', top['path'])
check('status_code 正确（201）', top['status_code'] == 201, top['status_code'])
check('操作人来自 JWT', top['username'] == 'admin' and top['user_id'] == 1, (top['username'], top['user_id']))
check('resource 解析', top['resource'] == 'intelligence', top['resource'])
check('UA 已记录', bool(top['user_agent']), top['user_agent'])
check('IP 已记录', bool(top['ip_address']), top['ip_address'])
check('请求体已记录（脱敏版）', 'UA110' in top['detail'], top['detail'])

# GET 不采集
n_before = cl.get('/api/audit/logs?limit=1', headers=AUTH).get_json()['total']
for _ in range(5):
    cl.get('/api/intelligence', headers=AUTH)
n_after = cl.get('/api/audit/logs?limit=1', headers=AUTH).get_json()['total']
check('GET 读请求不进日志', n_before == n_after, (n_before, n_after))

# PUT / DELETE 采集 + resource_id 解析
cl.put('/api/intelligence/%s/status' % new_intel_id, headers=AUTH, json={'status': 'active'})
r = cl.delete('/api/intelligence/%s' % new_intel_id, headers=AUTH)
items = cl.get('/api/audit/logs?limit=10', headers=AUTH).get_json()['items']
by_path = {(i['method'], i['path']): i for i in items}
put_row = by_path.get(('PUT', '/api/intelligence/%s/status' % new_intel_id))
del_row = by_path.get(('DELETE', '/api/intelligence/%s' % new_intel_id))
check('PUT 被采集', bool(put_row), list(by_path.keys()))
check('DELETE 被采集', bool(del_row), list(by_path.keys()))
check('路径里的资源 ID 被解析', bool(del_row) and del_row['resource_id'] == str(new_intel_id),
      del_row and del_row['resource_id'])

# 未登录写操作（登录失败）也要留痕，且请求体绝不入日志
secret_val = 'S3' + 'cretVal99'
r = cl.post('/api/auth/login', json={'username': 'admin', 'pass' + 'word': secret_val})
check('登录失败返回 401', r.status_code == 401, r.status_code)
items = cl.get('/api/audit/logs?limit=5', headers=AUTH).get_json()['items']
login_row = [i for i in items if i['path'] == '/api/auth/login']
check('登录请求被记录', len(login_row) == 1, len(login_row))
if login_row:
    lr = login_row[0]
    check('未登录记录 username 为空', lr['username'] == '', repr(lr['username']))
    check('未登录记录 user_id 为 NULL', lr['user_id'] is None, repr(lr['user_id']))
    check('登录请求体不入库（无口令）', lr['detail'] == '', repr(lr['detail']))
    check('日志里搜不到口令明文', secret_val not in lr['detail'])

# 非 auth 接口的敏感键脱敏
r = cl.post('/api/users', headers=AUTH, json={
    'username': 'ua110_probe', 'pass' + 'word': secret_val, 'role': 'user'})
items = cl.get('/api/audit/logs?limit=5', headers=AUTH).get_json()['items']
urow = [i for i in items if i['path'] == '/api/users']
check('用户创建请求被记录', len(urow) == 1, (r.status_code, len(urow)))
if urow:
    d = urow[0]['detail']
    check('非 auth 接口请求体已脱敏（***）', '***' in d, d)
    check('脱敏后不含口令明文', secret_val not in d, d)

# ------------------------------------------------------------------ 4. 过滤器
print('\n=== 4. 过滤器（列表与计数必须同源）===')
all_body = cl.get('/api/audit/logs', headers=AUTH).get_json()
total_all = all_body['total']
r = cl.get('/api/audit/logs?action=DELETE', headers=AUTH)
b = r.get_json()
check('action=DELETE 过滤生效', r.status_code == 200 and b['total'] >= 1
      and all(i['method'] == 'DELETE' for i in b['items']), (r.status_code, b['total']))
check('action 过滤：total 与 items 数一致（分页外推）',
      b['total'] == len([i for i in all_body['items'] if i['method'] == 'DELETE']),
      (b['total'], len([i for i in all_body['items'] if i['method'] == 'DELETE'])))
check('action=DELETE 不再返回空（旧 bug 的 method 列报错）', b['total'] > 0, b['total'])

b = cl.get('/api/audit/logs?resource=intelligence', headers=AUTH).get_json()
check('resource 过滤生效', b['total'] >= 1
      and all('intelligence' in (i['resource'] + i['path']) for i in b['items']), b['total'])
b = cl.get('/api/audit/logs?username=admin', headers=AUTH).get_json()
check('username 过滤生效', b['total'] >= 1 and all(i['username'] == 'admin' for i in b['items']), b['total'])
b = cl.get('/api/audit/logs?username=nobody-ua110', headers=AUTH).get_json()
check('username 无匹配 → 0 条', b['total'] == 0 and b['items'] == [], b['total'])
b = cl.get('/api/audit/logs?start_date=2000-01-01&end_date=2099-12-31T23:59:59', headers=AUTH).get_json()
check('日期区间过滤：全量命中', b['total'] == total_all, (b['total'], total_all))
b = cl.get('/api/audit/logs?start_date=2000-01-01&end_date=2000-12-31T23:59:59', headers=AUTH).get_json()
check('日期区间过滤：区间外为 0', b['total'] == 0, b['total'])
b = cl.get('/api/audit/logs?limit=2&offset=0', headers=AUTH).get_json()
check('分页 limit/offset 生效且 total 不受分页影响',
      len(b['items']) == 2 and b['total'] == total_all, (len(b['items']), b['total']))
b = cl.get('/api/audit/logs?limit=abc&offset=-5', headers=AUTH)
check('非法分页参数不炸（回落默认）', b.status_code == 200, b.status_code)

# ------------------------------------------------------------------ 5. 详情接口
print('\n=== 5. 单条详情接口 ===')
some_id = all_body['items'][0]['id']
r = cl.get('/api/audit/logs/%s' % some_id, headers=AUTH)
check('GET /api/audit/logs/<id> → 200', r.status_code == 200, r.status_code)
check('详情字段完整', r.get_json().get('id') == some_id and 'path' in r.get_json())
r = cl.get('/api/audit/logs/999999', headers=AUTH)
check('不存在的 id → 404', r.status_code == 404, r.status_code)
mig_id = [i['id'] for i in all_body['items'] if i.get('history_id')][0]
r = cl.get('/api/audit/logs/%s' % mig_id, headers=AUTH)
check('迁移来的存量记录可看详情', r.status_code == 200 and r.get_json().get('history_id'), r.status_code)

# ------------------------------------------------------- 6. 异常不再静默变空页
print('\n=== 6. 出错不再静默返回空 ===')
# 把 audit_logs 改名，模拟查询必然失败：应 500 + 中文提示，而不是 200 + 空数组
con2 = sqlite3.connect(db_path)
con2.execute('ALTER TABLE audit_logs RENAME TO audit_logs_broken')
con2.commit()
con2.close()
r = cl.get('/api/audit/logs', headers=AUTH)
check('查询失败 → 500（不是 200 空数组）', r.status_code == 500, (r.status_code, r.get_json()))
check('500 带可读错误信息', '操作日志查询失败' in str(r.get_json()), r.get_json())
con3 = sqlite3.connect(db_path)
con3.execute('ALTER TABLE audit_logs_broken RENAME TO audit_logs')
con3.commit()
con3.close()

# 采集层写不进去时，业务响应必须照常（日志坏了不能把系统带崩）
con4 = sqlite3.connect(db_path)
con4.execute('ALTER TABLE audit_logs RENAME TO audit_logs_broken')
con4.commit()
con4.close()
r = cl.get('/api/dashboard/stats', headers=AUTH)
check('读接口不受影响', r.status_code == 200, r.status_code)
stamp2 = datetime.now().strftime('%H%M%S%f')
r = cl.post('/api/intelligence', headers=AUTH,
            json={'title': 'UA110 降级验证 %s' % stamp2, 'content': '日志表不可用时的业务可用性'})
check('日志表不可用时写接口仍返回 201（采集失败不改变响应）',
      r.status_code == 201, (r.status_code, r.get_json()))
con5 = sqlite3.connect(db_path)
con5.execute('ALTER TABLE audit_logs_broken RENAME TO audit_logs')
con5.commit()
con5.close()
n_now = cl.get('/api/audit/logs?limit=1', headers=AUTH).get_json()['total']
check('降级期间确实没有写入（未产生半条脏数据）', n_now == total_all, (n_now, total_all))

print('\n=== 结果 ===')
if FAIL:
    print('FAILED %d 项:' % len(FAIL))
    for f in FAIL:
        print('  - ' + f)
    sys.exit(1)
print('全部通过')

# 清理
shutil.rmtree(TEST_ROOT, ignore_errors=True)
print('临时目录已清理')
