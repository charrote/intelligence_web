"""短信验证码服务（阿里云短信服务 SendSms / 兼容旧 PNVS）。

注册手机号核验用。三种模式（由 config/sms.json 决定）：
  - aliyun_sms（默认，标准「短信服务」）：本服务本地生成 6 位验证码，内存保管
    （5 分钟有效、错 5 次作废、重发覆盖），调用 dysmsapi SendSms 发送，
    注册时本地校验。需要 sign_name + template_code。
  - aliyun_pnvs（旧「号码认证服务」）：验证码由阿里云生成并保管，本服务
    只发、只校验（SendSmsVerifyCode / CheckSmsVerifyCode）。
  - test_mode：未配置 key（或显式 test_mode=true）时，不真发短信，
    任意 4-8 位数字直接通过（打印到日志），用于本地/生产打通注册链路。

设计原则（与 Tavily 一致）：key 单一来源 config/sms.json，不设 env 兜底。
"""

import hmac
import hashlib
import base64
import json
import secrets
import threading
import time
import urllib.parse
import uuid
import requests

from config import get_sms_config

# 阿里云开放平台签名参数（RPC 风格，HMAC-SHA1）
_ALIYUN_FORMAT = "JSON"
_ALIYUN_SIGN_METHOD = "HMAC-SHA1"
_ALIYUN_VERSION_PNVS = "2017-05-25"
_ALIYUN_VERSION_SMS = "2017-05-25"

# 本地验证码存储（仅 aliyun_sms 模式使用）
# f"{scene}|{phone}" -> {"code", "expires_at", "attempts"}
# UA107: 按 scene（register/login/reset）分仓——注册用的码不能拿来登录，
# 找回密码的码不能拿来登录，用途之间不可复用；重发作废仅限同 scene。
_CODE_STORE = {}
_CODE_LOCK = threading.Lock()
_CODE_TTL_SEC = 300       # 验证码有效期 5 分钟
_MAX_ATTEMPTS = 5         # 错 5 次作废，需重新发送


class AliyunApiError(Exception):
    """阿里云接口返回错误（网关 4xx/5xx 或业务错误码），携带真实 Code/Message。

    与网络层异常（requests.RequestException）区分开：网络异常是"暂时不可用、
    重试可能恢复"；而 AliyunApiError 是阿里云明确拒绝（如 AccessKey 被网络
    访问策略拒绝、签名非法、模板/签名非法等），属持续性配置问题，重试无用，
    必须把真实原因透传给运维去修。
    """

    def __init__(self, code, message, request_id="", http_status=0):
        self.code = code
        self.message = message
        self.request_id = request_id
        self.http_status = http_status
        super().__init__(
            f"[{code}] {message}" + (f" (RequestId={request_id})" if request_id else "")
        )


def _is_test_mode():
    """test_mode 判定：显式配置 test_mode=true，或缺少 AccessKey。"""
    cfg = get_sms_config()
    if cfg.get("test_mode"):
        return True
    return not (cfg.get("access_key_id") and cfg.get("access_key_secret"))


def _provider(cfg):
    """通道判定：显式 provider 优先；endpoint 是标准短信服务域名也视为 aliyun_sms。"""
    provider = (cfg.get("provider") or "").strip()
    if provider == "aliyun_pnvs":
        return "aliyun_pnvs"
    if provider == "aliyun_sms":
        return "aliyun_sms"
    if cfg.get("endpoint", "") == "dysmsapi.aliyuncs.com":
        return "aliyun_sms"
    return "aliyun_pnvs"


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


def _aliyun_call(action, biz_params, cfg, version=None):
    """调用阿里云 RPC 接口（dypnsapi / dysmsapi），返回解析后的 dict。

    网络层异常（连不上/超时）→ 原样抛 requests.RequestException（调用方按
    "暂时不可用"处理）。阿里云明确返回错误（HTTP>=400 且带业务 Code）→ 抛
    AliyunApiError，携带真实 Code/Message/RequestId，供调用方透传给运维。
    """
    common = {
        "Format": _ALIYUN_FORMAT,
        "Version": version or _ALIYUN_VERSION_PNVS,
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
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    code = str(body.get("Code", ""))
    # 阿里云对网关级错误（鉴权/访问策略/签名）返回 4xx + Code：抛出，让调用方
    # 拿到真实原因，而不是被笼统的"暂时不可用"掩盖。
    if resp.status_code >= 400 and code:
        raise AliyunApiError(
            code,
            body.get("Message", "") or resp.text[:200],
            request_id=body.get("RequestId", ""),
            http_status=resp.status_code,
        )
    if resp.status_code >= 400 and not code:
        # 4xx/5xx 但没解析出业务 Code（如 HTML 错误页）：也视为接口错误
        raise AliyunApiError(
            f"HTTP_{resp.status_code}",
            resp.text[:200],
            request_id="",
            http_status=resp.status_code,
        )
    return body


# 已知阿里云短信/鉴权错误码 → 面向运维的可操作提示。
# 命中这些"配置类"错误时，重试无用，直接告诉管理员该做什么。
_KNOWN_ALIYUN_ERRORS = {
    "InvalidAccessKeyId.AccessPolicyDenied":
        "阿里云 AccessKey 被「网络访问控制」策略拒绝：服务器出口 IP 不在该 "
        "AccessKey 的 IP 白名单内。请让管理员到 阿里云 RAM 控制台 → 该用户/角色 "
        "→ 网络访问策略，把本服务器出口 IP 加入允许网段，或换一个不受该策略限制的 "
        "AccessKey。此为持续性问题，重试不会恢复。",
    "AccessPolicyDenied":
        "阿里云 AccessKey 被「网络访问控制」策略拒绝（出口 IP 不在白名单）。"
        "请到 RAM 控制台调整该 AccessKey 的 IP 白名单，或更换 AccessKey。",
    "InvalidAccessKeyId.NotFound":
        "阿里云 AccessKey 不存在（可能已被删除）。请核对 config/sms.json 里的 "
        "access_key_id / access_key_secret。",
    "InvalidAccessKeyId.Inactive":
        "阿里云 AccessKey 已禁用。请到 RAM 控制台启用该 AccessKey 或更换。",
    "InvalidSignature.SignatureDoesNotMatch":
        "阿里云签名校验失败：access_key_secret 可能填错。请核对 config/sms.json。",
    "isv.SMS_SIGNATURE_ILLEGAL":
        "短信签名非法：sign_name 未通过审核或与签名管理里的名称不一致。请到 "
        "阿里云短信服务「签名管理」核对签名名称。",
    "isv.SMS_TEMPLATE_ILLEGAL":
        "短信模板非法：template_code 无效或已变更。请核对「模板管理」里的模板 CODE。",
    "isv.BUSINESS_LIMIT_CONTROL":
        "触发阿里云流控限制（单位时间发送超限）。请稍后再试。",
    "isv.DAY_LIMIT": "该手机号当日发送已达上限。",
    "isv.MOBILE_NUMBER_ILLEGAL":
        "手机号非法：请确认发送的手机号格式正确（11 位大陆手机号）。",
    "isv.MOBILE_NUMBER_SIGNS_NOT_MATCH":
        "运营商侧手机号与签名不匹配，短信被拦截。请核对签名归属。",
}


def _friendly_sms_error(err):
    """把 AliyunApiError 翻译成面向用户/运维的可读提示（未命中则透传原文）。"""
    if isinstance(err, AliyunApiError):
        return _KNOWN_ALIYUN_ERRORS.get(
            err.code,
            f"短信发送失败：{err.message}（Code={err.code}）",
        )
    return "短信发送失败，请稍后重试"


# ── 本地验证码存储（aliyun_sms 模式） ──────────────────────────────────────

def _store_key(phone, scene):
    """scene 分仓键。register 为默认用途，兼容旧调用方不传 scene。"""
    return f"{scene or 'register'}|{phone}"


def _store_code(phone, code, scene="register"):
    with _CODE_LOCK:
        _purge_expired()
        _CODE_STORE[_store_key(phone, scene)] = {
            "code": code,
            "expires_at": time.time() + _CODE_TTL_SEC,
            "attempts": 0,
        }


def _purge_expired(now=None):
    """清掉过期码。调用方需持有 _CODE_LOCK。"""
    now = now if now is not None else time.time()
    for p in [p for p, r in _CODE_STORE.items() if r["expires_at"] < now]:
        _CODE_STORE.pop(p, None)


def _check_local_code(phone, code, scene="register"):
    """本地校验：存在、未过期、未超尝试次数、码匹配。返回 (ok, message)。

    UA107: 校验与 scene 绑定——登录/重置/注册的码各查各仓，不可跨用途复用。
    """
    now = time.time()
    key = _store_key(phone, scene)
    with _CODE_LOCK:
        _purge_expired(now)
        rec = _CODE_STORE.get(key)
        if rec is None:
            return False, "请先获取短信验证码"
        if rec["attempts"] >= _MAX_ATTEMPTS:
            _CODE_STORE.pop(key, None)
            return False, "验证码已失效，请重新获取"
        if rec["code"] != code:
            rec["attempts"] += 1
            left = _MAX_ATTEMPTS - rec["attempts"]
            if left <= 0:
                _CODE_STORE.pop(key, None)
                return False, "验证码错误次数过多，已作废，请重新获取"
            return False, f"验证码错误，还可尝试 {left} 次"
        # 校验通过：一次性使用，立即作废
        _CODE_STORE.pop(key, None)
        return True, "验证码正确"


# ── 对外接口 ───────────────────────────────────────────────────────────────

def send_verify_code(phone, scene="register"):
    """发送短信验证码。

    scene（UA107）：register=注册 / login=验证码登录 / reset=找回密码。
    aliyun_sms 模式下按 scene 分仓存储，码不可跨用途复用；PNVS 模式由
    阿里云保管验证码，不区分 scene（旧链路，保留兼容）。

    返回 (ok, message)。ok=False 时 message 为人类可读错误。
    test_mode 下不真发，直接 ok=True（验证码走 verify_code 时直接通过）。
    """
    cfg = get_sms_config()
    if _is_test_mode():
        print(f"[SMS][TEST_MODE] 验证码已'发送'到 {phone}（scene={scene}），测试模式任意 6 位码均可通过")
        return True, "（测试模式）验证码已生成，可直接输入任意 6 位数字"
    if _provider(cfg) == "aliyun_sms":
        return _send_sms_standard(phone, cfg, scene=scene)
    return _send_pnvs(phone, cfg)


def verify_code(phone, code, scene="register"):
    """校验用户输入的短信验证码。

    返回 (ok, message)。
    test_mode 下：只要 code 是 4-8 位数字即通过（方便本地跑通）。
    aliyun_sms：本地存储校验（scene 分仓，UA107）；
    aliyun_pnvs：调用 CheckSmsVerifyCode 由阿里云校验（不区分 scene）。
    """
    cfg = get_sms_config()
    if _is_test_mode():
        ok = bool(code) and code.isdigit() and 4 <= len(code) <= 8
        if ok:
            print(f"[SMS][TEST_MODE] 验证码通过: {phone} -> {code}")
            return True, "验证码正确"
        return False, "验证码格式不正确（测试模式需 4-8 位数字）"
    if _provider(cfg) == "aliyun_sms":
        return _check_local_code(phone, code, scene=scene)
    return _verify_pnvs(phone, code, cfg)


# ── 标准短信服务（dysmsapi SendSms） ───────────────────────────────────────

def _send_sms_standard(phone, cfg, scene="register"):
    """标准短信服务发码：本地生成 6 位码 → SendSms → 发送成功才入库（按 scene 分仓）。"""
    missing = [k for k in ("sign_name", "template_code") if not cfg.get(k)]
    if missing:
        print(f"[SMS] 配置缺少必填项: {missing}")
        return False, "短信服务未配置完整，请联系管理员"
    code = f"{secrets.randbelow(1000000):06d}"
    template_param = json.dumps(
        {cfg.get("code_param") or "code": code}, ensure_ascii=False)
    try:
        result = _aliyun_call("SendSms", {
            "PhoneNumbers": phone,
            "SignName": cfg["sign_name"],
            "TemplateCode": cfg["template_code"],
            "TemplateParam": template_param,
        }, cfg, version=_ALIYUN_VERSION_SMS)
        if str(result.get("Code", "")) == "OK":
            _store_code(phone, code, scene=scene)
            print(f"[SMS] SendSms 成功 phone={phone} bizId={result.get('BizId', '')}")
            return True, "验证码已发送，5 分钟内有效，请查收短信"
        err_code = str(result.get("Code", ""))
        err_msg = result.get("Message", "")
        print(f"[SMS] SendSms 失败 phone={phone} Code={err_code} Message={err_msg}")
        # 200 + 业务 Code（签名/模板/手机号/流控等）：透传真实原因
        return False, _KNOWN_ALIYUN_ERRORS.get(
            err_code, f"短信发送失败：{err_msg}（Code={err_code}）")
    except AliyunApiError as e:
        print(f"[SMS] 阿里云接口错误: {e}")
        return False, _friendly_sms_error(e)
    except requests.RequestException as e:
        print(f"[SMS] 发送异常: {e}")
        return False, "短信服务暂时不可用，请稍后重试"
    except Exception as e:
        print(f"[SMS] 发送未知错误: {e}")
        return False, "发送验证码失败，请稍后重试"


# ── 旧号码认证服务（dypnsapi PNVS，保留兼容） ──────────────────────────────

def _send_pnvs(phone, cfg):
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
    except AliyunApiError as e:
        print(f"[SMS] 阿里云接口错误: {e}")
        return False, _friendly_sms_error(e)
    except requests.RequestException as e:
        print(f"[SMS] 发送异常: {e}")
        return False, "短信服务暂时不可用，请稍后重试"
    except Exception as e:
        print(f"[SMS] 发送未知错误: {e}")
        return False, f"发送验证码失败：{e}"


def _verify_pnvs(phone, code, cfg):
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
    except AliyunApiError as e:
        print(f"[SMS] 阿里云接口错误: {e}")
        return False, _friendly_sms_error(e)
    except requests.RequestException as e:
        print(f"[SMS] 校验异常: {e}")
        return False, "验证码校验服务暂时不可用，请稍后重试"
    except Exception as e:
        print(f"[SMS] 校验未知错误: {e}")
        return False, f"验证码校验失败：{e}"
