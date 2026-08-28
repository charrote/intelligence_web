"""
端口配置文件加载器

从 config/ports.json 读取所有服务的端口配置
"""

import os
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent / 'config' / 'ports.json'
_LLM_CONFIG_PATH = Path(__file__).parent.parent / 'config' / 'llm.json'
_TAVILY_CONFIG_PATH = Path(__file__).parent.parent / 'config' / 'tavily.json'

def load_ports_config():
    """加载端口配置文件"""
    try:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Warning] 无法加载端口配置文件 {_CONFIG_PATH}: {e}")
        return _get_default_config()

def _get_default_config():
    """默认配置（用于配置文件不存在时）"""
    return {
        "services": {
            "gateway": {"port": 8765},
            "research": {"port": 8766},
            "sales": {"port": 8767},
            "mcp_server": {"port": 8768},
            "meilisearch": {"port": 7700},
        },
        "mcp": {
            "path": "",
            "transport": "http",
        }
    }

def get_service_port(service_name):
    """获取指定服务的端口"""
    config = load_ports_config()
    service = config.get('services', {}).get(service_name, {})
    return service.get('port', 0)

def get_mcp_config():
    """获取 MCP 服务器配置"""
    config = load_ports_config()
    mcp_section = config.get('mcp', {})
    path = mcp_section.get('path') or '/mcp'  # 空字符串时 fallback 到 /mcp
    # 本地默认 localhost，生产环境通过环境变量覆盖为域名（如 nat.ywapi.com）
    host = os.environ.get('MCP_HOST', 'localhost')
    port = get_service_port('mcp_server')
    return {
        'url': f"http://{host}:{port}{path}",
        'port': port,
        'path': path,
        'transport': mcp_section.get('transport', 'http'),
        'enable_auth': mcp_section.get('enable_auth', True),
    }

def get_all_service_ports():
    """获取所有服务端口"""
    config = load_ports_config()
    ports = {}
    for name, info in config.get('services', {}).items():
        ports[name] = info.get('port', 0)
    return ports


# ── 平台级 LLM 配置（所有域共享，单一来源） ─────────────
_DEFAULT_LLM = {
    "provider": "openai",
    "api_base_url": "https://api.openai.com/v1",
    "model_name": "gpt-4",
    "api_key": "",
    "temperature": 0.7,
    "max_tokens": 4096,
}


def get_llm_config():
    """读取平台级 LLM 配置（config/llm.json）。

    平台级配置，与具体域无关——一个模型服务对应所有域。
    返回 dict，缺失项用默认值兜底。
    """
    cfg = dict(_DEFAULT_LLM)
    try:
        with open(_LLM_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for k in _DEFAULT_LLM:
            if data.get(k) not in (None, ""):
                cfg[k] = data[k]
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[Warning] 无法加载 LLM 配置文件 {_LLM_CONFIG_PATH}: {e}")
    return cfg


def save_llm_config(cfg: dict):
    """保存平台级 LLM 配置到 config/llm.json。"""
    data = dict(_DEFAULT_LLM)
    for k in _DEFAULT_LLM:
        if cfg.get(k) not in (None, ""):
            data[k] = cfg[k]
    _LLM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LLM_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


# ── Tavily 搜索 API 配置（微信公众号情报「搜」用） ─────────────
_DEFAULT_TAVILY = {
    "api_key": "",
    "base_url": "https://api.tavily.com",
}


def get_tavily_config():
    """读取 Tavily 搜索配置（config/tavily.json）。缺失项用默认值兜底。

    key 唯一来源 = 系统设置（config/tavily.json）。未配置时 api_key 为空，
    调用方据此明确报错（不设 key 就不能搜索，不做环境变量兜底）。
    """
    cfg = dict(_DEFAULT_TAVILY)
    try:
        with open(_TAVILY_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for k in _DEFAULT_TAVILY:
            if data.get(k) not in (None, ""):
                cfg[k] = data[k]
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[Warning] 无法加载 Tavily 配置文件 {_TAVILY_CONFIG_PATH}: {e}")
    return cfg


def save_tavily_config(cfg: dict):
    """保存 Tavily 搜索配置到 config/tavily.json。"""
    data = dict(_DEFAULT_TAVILY)
    for k in _DEFAULT_TAVILY:
        if cfg.get(k) not in (None, ""):
            data[k] = cfg[k]
    _TAVILY_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_TAVILY_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


# ── 搜刮调度配置（系统自驱 search_cycle） ─────────────────────
_SEARCH_CONFIG_PATH = Path(__file__).parent.parent / 'config' / 'search.json'
_DEFAULT_SEARCH = {
    "enabled": True,
    "max_per_domain": 20,    # 每域每轮最多采集条数
    "max_keywords_per_project": 5,  # 每项目最多关键词数
    "max_llm_calls_per_cycle": 50,  # 每轮 LLM 调用安全上限
    "results_per_keyword": 5,       # 每关键词搜索结果数
    "content_max_chars": 400,       # 摘要最大字数
}


def get_search_config():
    """读取搜刮调度配置（config/search.json）。缺失项用默认值。"""
    cfg = dict(_DEFAULT_SEARCH)
    try:
        with open(_SEARCH_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for k in _DEFAULT_SEARCH:
            if data.get(k) is not None:
                cfg[k] = data[k]
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[Warning] 无法加载搜刮配置 {_SEARCH_CONFIG_PATH}: {e}")
    return cfg


def save_search_config(cfg: dict):
    """保存搜刮调度配置到 config/search.json。"""
    data = dict(_DEFAULT_SEARCH)
    for k in _DEFAULT_SEARCH:
        if cfg.get(k) is not None:
            data[k] = cfg[k]
    _SEARCH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SEARCH_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


# ── 短信验证码配置（阿里云号码认证服务 PNVS，注册手机号核验用） ─────────────
# key 唯一来源 = config/sms.json（gitignore）。未配置 access_key_id/secret 时
# 进入 test_mode：验证码不真发、直接通过，用于本地打通整条注册链路。
_SMS_CONFIG_PATH = Path(__file__).parent.parent / 'config' / 'sms.json'
_DEFAULT_SMS = {
    "provider": "aliyun_pnvs",   # 预留：未来可切换其他通道
    "access_key_id": "",
    "access_key_secret": "",
    "endpoint": "dypnsapi.aliyuncs.com",
    "test_mode": False,          # True 时不真发短信，验证码直接通过
}


def get_sms_config():
    """读取短信验证码配置（config/sms.json）。缺失项用默认值兜底。

    access_key_id/secret 唯一来源 = config/sms.json（gitignore）。
    未配置时 test_mode 由调用方根据是否缺 key 推断（见 core/sms.py）。
    """
    cfg = dict(_DEFAULT_SMS)
    try:
        with open(_SMS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for k in _DEFAULT_SMS:
            if data.get(k) is not None:
                cfg[k] = data[k]
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[Warning] 无法加载短信配置 {_SMS_CONFIG_PATH}: {e}")
    return cfg


def save_sms_config(cfg: dict):
    """保存短信验证码配置到 config/sms.json。"""
    data = dict(_DEFAULT_SMS)
    for k in _DEFAULT_SMS:
        if cfg.get(k) is not None:
            data[k] = cfg[k]
    _SMS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SMS_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


if __name__ == '__main__':
    print("当前端口配置:")
    for name, port in get_all_service_ports().items():
        print(f"  {name}: {port}")

    print(f"\nMCP 服务器 URL: {get_mcp_config()['url']}")
    _llm = get_llm_config()
    print(f"\nLLM 配置: provider={_llm['provider']}, model={_llm['model_name']}, base={_llm['api_base_url']}")
