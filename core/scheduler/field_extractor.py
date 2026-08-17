"""Regex fast path: extract structured fields without LLM.

Handles numeric-ish field types (number / pct / currency / currency_code /
date / year) deterministically. Entity and free-text fields (company /
location / text) always go to the LLM.

Windowing: fields are expected to appear in document order matching the
field definition order. Each field's search window is
[own_label_pos, next_field_label_pos) — the value typically follows its
label ("…营收为120亿元，同比增长15%"), and the window keeps a numeric field
from grabbing a value that belongs to its neighbour. Date/year fields get a
small lookback prefix because time adverbials often precede the label
("2024年第三季度营收…").
"""
import re
from typing import Dict, List, Tuple

# Field types handled by regex. Everything else → LLM.
REGEX_TYPES = {"number", "pct", "currency", "currency_code", "date", "year"}

# ── Patterns ──────────────────────────────────────────────────────────

# 年份: 4 digits 1900-2099, not part of a longer digit run
RE_YEAR = re.compile(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)')
# 百分比: 12.3% / 12.3％ / 12.5个百分点
RE_PCT = re.compile(
    r'(?<!\d)(\d{1,5}(?:[.,]\d{1,4})?)\s*[%％]'
    r'|(?<!\d)(\d{1,4}(?:[.,]\d{1,4})?)\s*个百分点'
)
# 日期: 完整日期 / 年月 / 月份 / 年份+季度 / 纯季度（兼容中文数字 一二三四、财年）
RE_DATE = re.compile(
    r'\d{4}\s*[年/\-]\s*\d{1,2}\s*[月/\-]\s*\d{1,2}\s*日?'
    r'|\d{4}\s*[年/\-]\s*\d{1,2}\s*月'
    r'|\d{1,2}\s*月\s*\d{1,2}\s*日'
    r'|(?:20\d{2}|19\d{2})\s*(?:财)?年?\s*(?:第\s*[一二三四1-4]\s*季度|Q[1-4])'
    r'|(?:20\d{2}|19\d{2})\s*Q[1-4]'
    r'|Q[1-4]\s*(?:20\d{2}|19\d{2})'
    r'|(?:20\d{2}|19\d{2})\s*(?:财)?年'
    r'|第\s*[一二三四1-4]\s*季度'
    r'|[一二三四1-4]\s*季度'
)
# 货币代码
RE_CURRENCY_CODE = re.compile(
    r'\b(USD|CNY|EUR|GBP|JPY|HKD|SGD|TWD|KRW|AUD|CAD|CHF|INR|IDR|THB|VND)\b'
    r'|人民币|美元|欧元|英镑|日元|港币'
)
# 纯数值：整数（任意位数）或带千分位/小数（千分位必须 3 位一组，避免 1,234.56 被截断）
RE_NUMBER = re.compile(
    r'(?<![\d.])(?:\d{1,3}(?:,\d{3})+(?:\.\d{1,4})?|\d+(?:\.\d{1,4})?)(?![\d,])'
)

_CN_UNIT = {"万亿": 1e12, "亿": 1e8, "万": 1e4, "千": 1e3}


def _format_num(v: float) -> str:
    """26000000000.0 → '26000000000'; 12.5 → '12.5'"""
    if v == int(v) and abs(v) < 1e18:
        return str(int(v))
    return f"{v:g}"


def _normalize_num(raw: str) -> float:
    try:
        return float(raw.replace(",", "").replace("，", "").replace(" ", ""))
    except (ValueError, TypeError):
        return 0.0


def _extract_number(text: str) -> float:
    """First plausible number; bare 4-digit years are skipped."""
    for m in RE_NUMBER.finditer(text):
        s = m.group(0)
        if re.fullmatch(r'(19\d{2}|20\d{2})', s):
            continue  # 疑似年份
        v = _normalize_num(s)
        if v != 0:
            return v
    return 0.0


def _extract_pct(text: str) -> float:
    for m in RE_PCT.finditer(text):
        raw = m.group(1) if m.group(1) is not None else m.group(2)
        v = _normalize_num(raw)
        if 0 < v <= 99999:
            return v
    return 0.0


def _extract_currency(text: str) -> float:
    """First currency amount: 符号前缀 / 中文单位 / 币种代码 三种形态。"""
    # 1) 货币符号前缀: $260亿 / ¥3.5万 / €12,345
    m = re.search(r'[$€£¥]\s*(\d{1,3}(?:,\d{3})+(?:\.\d{1,4})?|\d{1,15}(?:\.\d{1,4})?)', text)
    if m:
        return _normalize_num(m.group(1))
    # 2) 数字 + 中文单位（亿/万/万亿）
    m = re.search(r'(\d{1,3}(?:,\d{3})+(?:\.\d{1,4})?|\d{1,15}(?:\.\d{1,4})?)\s*(万亿|亿|万|千)\s*(?:美元|欧元|英镑|人民币|日元|元)?', text)
    if m:
        return _normalize_num(m.group(1)) * _CN_UNIT[m.group(2)]
    # 3) 数字 + 币种代码
    m = re.search(r'(\d{1,3}(?:,\d{3})+(?:\.\d{1,4})?|\d{1,15}(?:\.\d{1,4})?)\s*(?:USD|CNY|EUR|GBP|JPY|HKD|SGD|TWD|KRW|AUD|CAD|CHF|INR|IDR|THB|VND)\b', text, re.IGNORECASE)
    if m:
        return _normalize_num(m.group(1))
    return 0.0


def _extract_date(text: str) -> str:
    m = RE_DATE.search(text)
    return m.group(0).strip() if m else ""


def _extract_year(text: str) -> str:
    m = RE_YEAR.search(text)
    return m.group(1) if m else ""


def _extract_currency_code(text: str) -> str:
    m = RE_CURRENCY_CODE.search(text)
    return (m.group(1) or m.group(0)) if m else ""


# ── Windowing ─────────────────────────────────────────────────────────

# 日期/年份常出现在字段标签之前（"2024年第三季度营收…"），向前回看若干字符
LOOKBECK_CHARS = 30


def _compute_windows(fields: List[dict], full_text: str) -> Tuple[List[Tuple[int, int]], List[bool]]:
    """Per-field search window (start, end) over full_text.

    Field values typically follow their label ("…收入为120亿元，同比增长15%"),
    and fields appear in document order matching the definition order.
    Window for field i = [own_label_pos, next_field_label_pos), which keeps
    each numeric field from grabbing a value belonging to its neighbour.
    Fields whose label is absent inherit the previous field's end as start.

    Returns (windows, label_found) — label_found[i] is True when the field's
    own label was located in the text (used to enable the lookback prefix
    for date/year fields).
    """
    labels = []
    for f in fields:
        labels.append(f.get("field_label") or f.get("field_key") or "")
    label_pos = [full_text.find(l) if l else -1 for l in labels]

    n = len(fields)
    windows = []
    label_found = []
    for i in range(n):
        own = label_pos[i]
        if own != -1:
            start = own
            label_found.append(True)
        else:
            start = windows[i - 1][1] if i > 0 else 0
            label_found.append(False)
        end = len(full_text)
        for j in range(i + 1, n):
            if label_pos[j] != -1:
                end = label_pos[j]
                break
        if end < start:
            start, end = 0, len(full_text)
        windows.append((start, end))
    return windows, label_found


# ── Public API ────────────────────────────────────────────────────────

# 标签未找到时可安全做全文回退的类型（词汇有界、无跨字段歧义）。
# 其余类型（year/number/pct/currency）标签缺失时交给 LLM 语义判断。
FULLTEXT_FALLBACK_TYPES = {"currency_code", "date"}


def extract_fields_regex(fields: List[dict], intel_title: str,
                         intel_content: str) -> Tuple[Dict[str, str], List[dict]]:
    """Run regex extraction over regex-eligible fields.

    Returns:
        values: {field_key: raw_string} — fields where regex found a value
        remaining_fields: fields still to be handled by the LLM
            (non-regex types, or regex types where nothing was found)
    """
    full_text = (intel_title or "") + "\n" + (intel_content or "")
    windows, label_found = _compute_windows(fields, full_text)
    values: Dict[str, str] = {}
    remaining: List[dict] = []

    for i, f in enumerate(fields):
        fk = f.get("field_key", "")
        ftype = f.get("field_type", "")
        if ftype not in REGEX_TYPES:
            remaining.append(f)
            continue

        # 标签未出现在文本中：
        #   低风险类型（currency_code/date）→ 全文回退（词汇有界，不会串值）
        #   其余类型（year/number/pct/currency）→ 交给 LLM（语义判断更可靠）
        if not label_found[i]:
            if ftype in FULLTEXT_FALLBACK_TYPES:
                s, e = 0, len(full_text)
            else:
                remaining.append(f)
                continue
        else:
            s, e = windows[i]

        # 日期/年份：向前回看（时间状语常在标签前："2024年第三季度营收…"）
        if ftype in ("date", "year"):
            s = max(0, s - LOOKBECK_CHARS)
        window = full_text[s:e]

        try:
            if ftype == "pct":
                v = _extract_pct(window)
                raw = _format_num(v) if v else ""
            elif ftype == "currency":
                v = _extract_currency(window)
                raw = _format_num(v) if v else ""
            elif ftype == "number":
                v = _extract_number(window)
                raw = _format_num(v) if v else ""
            elif ftype == "year":
                raw = _extract_year(window)
            elif ftype == "date":
                raw = _extract_date(window)
            elif ftype == "currency_code":
                raw = _extract_currency_code(window)
            else:
                raw = ""
        except Exception:
            raw = ""

        if raw not in ("", "0", "0.0"):
            values[fk] = raw
        else:
            remaining.append(f)

    return values, remaining