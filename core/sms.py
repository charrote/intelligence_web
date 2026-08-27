"""短信验证码服务（阿里云号码认证服务 PNVS）。

注册手机号核验用。两种模式：
  - 真实模式：配置了 config/sms.json 的 access_key_id / secret 时，调用
    阿里云 dypnsapi 的 SendSmsVerifyCode / CheckSmsVerifyCode。验证码由
    阿里云生成并保管，本服务不存码、不管有效期——只发、只校验。
  - test_mode：未配置 key（或显式 test_mode=true）时，不真发短信，
    验证码直接通过（打印到日志）。用于本地/生产打通整条注册链路，
    待阿里云 AccessKey 就绪后填入 config/sms.json 即切换真实短信，零代码改动。

设计原则（与 Tavily 一致）：key 单一来源 config/sms.json，不设 env 兜底。
"""

import hmac
import hashlib
import base64
import json
import time
import urllib.parse
import uuid
import requests

from config import get_sms_config

# 阿里云开放平台签名参数（RPC 风格，HMAC-SHA1）
_ALIYUN_VERSION = "2017-05-25"
_ALIYUN_FORMAT = "JSON"
_ALIYUN_SIGN_METHOD = "HMAC-SHA1"


def _is_test_mode():
    """test_mode 判定：显式配置 test_mode=true，或缺少 AccessKey。"""
    cfg = get_sms_config()
    if cfg.get("test_mode"):
        return True
    return not (cfg.get("access_key_id") and cfg.get("access_key_secret"))


def _aliyun_sign(params, access_key_secret):
    """计算阿里云 RPC 风格 API 的 Signature（HMAC-SHA1 + Base64）。

    params: 不含 Signature 的字典（含公共参数）。
    返回签名值（str）。
    """
    # 1) 按参数名 ASCII 排序
    sorted_params = sorted(params.items(), key=lambda kv: kv[0])
    # 2) 构造规范化查询字符串（RFC3986 编码）
    canonicalized = "&".join(
        _pct_encode(k) + "=" + _pct_encode(v) for k, v in sorted_params
    )
    # 3) 构造待签字符串
    string_to_sign = "GET&" + _pct_encode("/") + "&" + _pct_encode(canonicalized)
    # 4) HMAC-SHA1，key = access_key_secret + "&"
    key = (access_key_secret + "&").encode("utf-8")
    digest = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


def _pct_encode(s):
    """RFC3986 百分号编码（阿里云签名要求）。"""
    return urllib.parse.quote(str(s), safe="").replace("+", "%20").replace("*", "%2A").replace("%7E", "~")


def _aliyun_call(action, biz_params, cfg):
    """调用阿里云 dypnsapi 的一个 RPC 接口，返回解析后的 dict。"""
    common = {
        "Format": _ALIYUN_FORMAT,
        "Version": _ALIYUN_VERSION,
        "AccessKeyId": cfg["access_key_id"],
        "SignatureMethod": _ALIYUN_SIGN_METHOD,
        "SignatureVersion": "1.0",
        "SignatureNonce": uuid.uuid4().hex,
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "Action": action,
    }
    params = {**common, **biz_params}
    params["Signature"] = _aliyun_sign(params, cfg["access_key_secret"])
    url = "https://{}?{}".format(cfg.get("endpoint", "dypnsapi.aliyuncs.com"),
                                 urllib.parse.urlencode(params))
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def send_verify_code(phone, scene="register"):
    """发送短信验证码。

    返回 (ok, message)。ok=False 时 message 为人类可读错误。
    test_mode 下不真发，直接 ok=True（验证码走 verify_code 时直接通过）。
    """
    cfg = get_sms_config()
    if _is_test_mode():
        print(f"[SMS][TEST_MODE] 验证码已'发送'到 {phone}（scene={scene}），测试模式任意 6 位码均可通过")
        return True, "（测试模式）验证码已生成，可直接输入任意 6 位数字"
    try:
        result = _aliyun_call("SendSmsVerifyCode", {
            "Phone": phone,
            "TemplateCode": cfg.get("template_code", ""),  # PNVS 内置模板，通常无需
        }, cfg)
        # 阿里云成功响应通常无 Code=OK / 无错误码
        code = str(result.get("Code", "OK"))
        if code == "OK" or "Code" not in result:
            return True, "验证码已发送，请查收短信"
        return False, result.get("Message", f"发送失败（Code={code}）")
    except requests.RequestException as e:
        print(f"[SMS] 发送异常: {e}")
        return False, "短信服务暂时不可用，请稍后重试"
    except Exception as e:
        print(f"[SMS] 发送未知错误: {e}")
        return False, f"发送验证码失败：{e}"


def verify_code(phone, code):
    """校验用户输入的短信验证码。

    返回 (ok, message)。
    test_mode 下：只要 code 是 4-8 位数字即通过（方便本地跑通）。
    真实模式：调用 CheckSmsVerifyCode 由阿里云校验。
    """
    cfg = get_sms_config()
    if _is_test_mode():
        ok = bool(code) and code.isdigit() and 4 <= len(code) <= 8
        if ok:
            print(f"[SMS][TEST_MODE] 验证码通过: {phone} -> {code}")
            return True, "验证码正确"
        return False, "验证码格式不正确（测试模式需 4-8 位数字）"
    try:
        result = _aliyun_call("CheckSmsVerifyCode", {
            "Phone": phone,
            "Code": code,
        }, cfg)
        code_val = str(result.get("Code", "OK"))
        if code_val == "OK" or code_val == "200" or "Code" not in result:
            # 部分响应用 VerifyCode 字段标识是否通过
            if result.get("VerifyCode") in ("true", True, "YES"):
                return True, "验证码正确"
            # 无 VerifyCode 字段时，以无错误码视为通过
            return True, "验证码正确"
        return False, result.get("Message", "验证码错误")
    except requests.RequestException as e:
        print(f"[SMS] 校验异常: {e}")
        return False, "验证码校验服务暂时不可用，请稍后重试"
    except Exception as e:
        print(f"[SMS] 校验未知错误: {e}")
        return False, f"验证码校验失败：{e}"
