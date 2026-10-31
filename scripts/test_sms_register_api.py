#!/usr/bin/env python3
"""Flask API smoke test: /api/auth/sms/send + /api/auth/register on aliyun_sms mode.

Mocked SendSms (no network), temp DB. Run: python scripts/test_sms_register_api.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CREDENTIALS_ENCRYPT_KEY"] = "api-smoke-credential-key"

PASS = 0
FAIL = 0

def check(name, cond, extra=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  [PASS] {name}")
    else: FAIL += 1; print(f"  [FAIL] {name} {extra}")


class FakeResp:
    def raise_for_status(self): pass
    def json(self): return {"Code": "OK", "BizId": "biz-smoke", "Message": "OK"}


def main():
    tmp = tempfile.mkdtemp(prefix="sms_reg_api_")
    from core.domain import build_spec
    from core.app import create_app
    import core.sms as sms
    import requests

    # mock SendSms network call
    requests.get = lambda url, timeout=None: FakeResp()

    spec = build_spec(
        slug="intelligence_web", port=8766, title_prefix="测试",
        scout_label="测试采集", agent_names=["测试"], theme_color="#722ed1",
        inbox_rel="../inbox/", db_filename="test_sms", domain_key="research",
    )
    app = create_app(tmp, spec)
    client = app.test_client()

    # force aliyun_sms mode config (signed-in-memory, no real keys needed)
    CFG = {"provider": "aliyun_sms", "access_key_id": "testak",
           "access_key_secret": "testsk", "sign_name": "测试签名",
           "template_code": "SMS_123456", "code_param": "code",
           "endpoint": "dysmsapi.aliyuncs.com", "test_mode": False}
    import config as config_pkg
    config_pkg.get_sms_config = lambda: dict(CFG)
    sms.get_sms_config = config_pkg.get_sms_config

    # enable self-registration
    from core.db import set_setting
    db_path = os.path.join(tmp, "data", "test_sms")
    set_setting(db_path, "register_enabled", "1")

    # 1) send code
    r = client.post("/api/auth/sms/send", json={"phone": "13800001111"})
    check("sms/send 200", r.status_code == 200, r.get_json())
    check("send ok=True", r.get_json().get("ok") is True, r.get_json())
    check("真实模式提示(非测试模式)", "测试模式" not in r.get_json().get("message", ""), r.get_json())
    check("码已入内存存储", "13800001111" in sms._CODE_STORE)
    code = sms._CODE_STORE["13800001111"]["code"]

    # 2) cooldown
    r = client.post("/api/auth/sms/send", json={"phone": "13800001111"})
    check("60s 冷却 429", r.status_code == 429, r.get_json())

    # 3) register with wrong code -> 400
    wrong = "000000" if code != "000000" else "111111"
    r = client.post("/api/auth/register", json={
        "username": "smokeuser", "phone": "13800001111", "code": wrong, "password": "pass1234"})
    check("错误码注册 400", r.status_code == 400, r.get_json())

    # 4) register with right code -> 200 + JWT
    # wrong attempt incremented attempts but code still valid
    r = client.post("/api/auth/register", json={
        "username": "smokeuser", "phone": "13800001111", "code": code, "password": "pass1234"})
    body = r.get_json() or {}
    check("正确码注册 200", r.status_code == 200, body)
    check("注册即登录(有 token)", bool(body.get("token")))
    check("注册后码作废", "13800001111" not in sms._CODE_STORE)

    # 5) register disabled -> 403
    set_setting(db_path, "register_enabled", "0")
    r = client.post("/api/auth/register", json={
        "username": "smokeuser2", "phone": "13800002222", "code": "123456", "password": "pass1234"})
    check("关闭注册后 403", r.status_code == 403, r.get_json())

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
