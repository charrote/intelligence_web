"""LLM API client for extraction and report generation tasks."""
import json
import requests


def get_llm_config():
    """Read LLM config from settings table."""
    from core.db import get_setting
    return {
        "provider": get_setting("model.provider", "openai"),
        "api_base_url": get_setting("model.api_base_url", "https://api.openai.com"),
        "api_key": get_setting("model.api_key", ""),
        "model_name": get_setting("model.name", "gpt-4"),
    }


def call_openai_compatible(system_prompt: str, user_prompt: str,
                           temperature: float = 0.1, max_tokens: int = 500,
                           timeout: int = 60) -> dict:
    """Call OpenAI-compatible API."""
    config = get_llm_config()
    response = requests.post(
        url=f"{config['api_base_url'].rstrip('/')}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json"
        },
        json={
            "model": config["model_name"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=timeout
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return {"raw": content, "ok": True}


def call_anthropic(system_prompt: str, user_prompt: str,
                   temperature: float = 0.1, max_tokens: int = 500,
                   timeout: int = 60) -> dict:
    """Call Anthropic Messages API."""
    config = get_llm_config()
    response = requests.post(
        url=f"{config['api_base_url'].rstrip('/')}/v1/messages",
        headers={
            "x-api-key": config["api_key"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        },
        json={
            "model": config["model_name"],
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=timeout
    )
    response.raise_for_status()
    data = response.json()
    content = data["content"][0]["text"]
    return {"raw": content, "ok": True}


def call_llm(system_prompt: str, user_prompt: str,
             temperature: float = 0.1, max_tokens: int = 500,
             timeout: int = 60) -> dict:
    """
    Unified LLM call entry point. Auto-selects API provider based on config.

    Returns:
        {"raw": str, "ok": True}   on success
        {"error": str, "ok": False} on failure
    """
    try:
        config = get_llm_config()
        if config["provider"] == "anthropic":
            return call_anthropic(system_prompt, user_prompt,
                                  temperature, max_tokens, timeout)
        else:
            return call_openai_compatible(system_prompt, user_prompt,
                                          temperature, max_tokens, timeout)
    except requests.exceptions.Timeout:
        return {"error": f"LLM API timeout ({timeout}s)", "ok": False}
    except requests.exceptions.ConnectionError:
        return {"error": f"LLM API connection failed: {config.get('api_base_url', '')}", "ok": False}
    except requests.exceptions.HTTPError as e:
        return {"error": f"LLM API HTTP error: {e.response.status_code} {e.response.text[:200]}", "ok": False}
    except Exception as e:
        return {"error": f"LLM call error: {str(e)[:200]}", "ok": False}


def parse_json_from_response(raw: str) -> tuple:
    """
    Extract JSON object from LLM raw response.

    Supports:
    - Plain JSON
    - ```json ... ``` wrapped
    - Other ```...``` wrapped
    - JSON with surrounding text

    Returns:
        (parsed_dict, True)   on success
        (None, False)         on failure
    """
    raw = raw.strip()

    try:
        return json.loads(raw), True
    except json.JSONDecodeError:
        pass

    import re
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1)), True
        except json.JSONDecodeError:
            pass

    match = re.search(r'\{(.*)\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads("{" + match.group(1) + "}"), True
        except json.JSONDecodeError:
            pass

    return None, False
