"""Standalone unit tests for field_extractor (no project deps needed)."""
import sys
sys.path.insert(0, ".")
from core.scheduler.field_extractor import extract_fields_regex, REGEX_TYPES

FIELDS = [
    {"field_key": "company",     "field_label": "公司名称",   "field_type": "company"},
    {"field_key": "revenue",     "field_label": "营收",       "field_type": "currency"},
    {"field_key": "growth",      "field_label": "同比增长",   "field_type": "pct"},
    {"field_key": "quarter",     "field_label": "季度",       "field_type": "date"},
    {"field_key": "founded",     "field_label": "成立年份",   "field_type": "year"},
    {"field_key": "summary",     "field_label": "摘要",       "field_type": "text"},
]

T1 = "英伟达 2024财年第一季度营收为260亿美元，同比增长204%。"
T2 = "华为2024年第三季度营收2000亿元，同比增长9%。"
T3 = "某公司2024年Q4营收1,234.56亿元，同比增长12.5%。"

passed = failed = 0

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")

print("── Case 1: 美元符号 + 百分比 ──")
v, rest = extract_fields_regex(FIELDS, "财报", T1)
check("revenue=26000000000", v.get("revenue") == "26000000000", f"got {v.get('revenue')}")
check("growth=204", v.get("growth") == "204", f"got {v.get('growth')}")
check("company → LLM", any(f["field_key"] == "company" for f in rest))
check("summary → LLM", any(f["field_key"] == "summary" for f in rest))
check("quarter=2024财年第一季度 (含回看)", v.get("quarter") == "2024财年第一季度", f"got {v.get('quarter')}")
check("year label absent → LLM fallback", any(f["field_key"] == "founded" for f in rest))

print("── Case 2: 中文单位 + 年份 ──")
v, rest = extract_fields_regex(FIELDS, "财报", T2)
check("revenue=200000000000", v.get("revenue") == "200000000000", f"got {v.get('revenue')}")
check("growth=9", v.get("growth") == "9", f"got {v.get('growth')}")
# 2024年 appears; quarter label 季度 appears at "第三季度"
check("date=2024年", v.get("quarter", "").startswith("2024年"), f"got {v.get('quarter')}")
check("year label absent → LLM (year 不做全文回退)", any(f["field_key"] == "founded" for f in rest))

print("── Case 3: 千分位 + 全角百分比 ──")
v, rest = extract_fields_regex(FIELDS, "财报", T3)
check("revenue=123456000000 (1234.56亿)", v.get("revenue") == "123456000000", f"got {v.get('revenue')}")
check("growth=12.5", v.get("growth") == "12.5", f"got {v.get('growth')}")

print("── Case 4: 窗口隔离（相邻字段不串值）──")
FIELDS4 = [
    {"field_key": "rev", "field_label": "营收", "field_type": "number"},
    {"field_key": "profit", "field_label": "净利润", "field_type": "number"},
]
T4 = "2024年营收5000亿，净利润120亿。"
v, rest = extract_fields_regex(FIELDS4, "", T4)
check("rev=5000 (not 120)", v.get("rev") == "5000", f"got {v.get('rev')}")
check("profit=120", v.get("profit") == "120", f"got {v.get('profit')}")

print("── Case 5: 空文本 ──")
v, rest = extract_fields_regex(FIELDS, "", "")
check("no values", v == {}, f"got {v}")
check("all 6 fields → LLM", len(rest) == 6, f"got {len(rest)}")

print("── Case 6: 货币代码（标签缺失 → 全文回退）──")
F6 = [{"field_key": "ccy", "field_label": "币种", "field_type": "currency_code"}]
v, rest = extract_fields_regex(F6, "", "以人民币计价，收入约10亿元")
check("ccy=人民币", v.get("ccy") == "人民币", f"got {v.get('ccy')}")

print("── Case 7: 金额标签缺失 → 交给 LLM（防误抓）──")
F7 = [{"field_key": "amt", "field_label": "金额", "field_type": "currency"}]
v, rest = extract_fields_regex(F7, "", "投资总额3000亿美元，相当于2100亿人民币。")
check("currency label absent → LLM fallback", any(f["field_key"] == "amt" for f in rest), f"values={v}")

print("── Case 8: 金额标签在文本中 → 正则直抽 ──")
F8 = [{"field_key": "amt", "field_label": "投资总额", "field_type": "currency"}]
v, rest = extract_fields_regex(F8, "", "投资总额3000亿美元，相当于2100亿人民币。")
check("amt=300000000000", v.get("amt") == "300000000000", f"got {v.get('amt')}")

print(f"\n=== {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)