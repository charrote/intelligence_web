"""Jinja2 template renderer for extraction and report prompts."""
from jinja2 import Environment, StrictUndefined, BaseLoader

# Global Jinja2 environment (strict mode)
_env = Environment(undefined=StrictUndefined)


def render(template_str: str, variables: dict) -> str:
    """Render Jinja2 template string with variables."""
    tmpl = _env.from_string(template_str)
    return tmpl.render(**variables)


def render_extraction_prompt(rule_name: str, fields: list,
                              intel_title: str, intel_content: str) -> tuple:
    """
    Render extraction prompt.

    Args:
        rule_name: extraction rule name
        fields: list of dicts with {field_key, field_label, field_type, is_required}
        intel_title: intelligence title
        intel_content: intelligence content

    Returns:
        tuple of (system_prompt, user_prompt)
    """
    system_prompt = """你是一个专业的情报数据提取员。你的任务是从文本中提取指定字段的数据。

重要规则：
1. 只提取文本中明确提到的信息，不要推断或虚构
2. 找不到的字段填 null
3. 严格按 JSON 格式返回，不要包含任何其他内容
4. 数值字段请提取为数字（不是字符串）
5. 如果文本中提到多个实体（如多家公司），只提取第一个出现的完整记录"""

    fields_list = ""
    for f in fields:
        req = "，必填" if f.get("is_required") else ""
        fields_list += f'- {f["field_key"]}（{f["field_label"]}）：类型为 {f["field_type"]}{req}\n'

    json_fields = ",\n  ".join(f'"{f["field_key"]}": null' for f in fields)

    user_prompt = f"""请从以下情报文本中提取以下字段的数据：

【抽取规则】{rule_name}

【字段定义】
{fields_list}【情报标题】{intel_title}

【情报内容】
{intel_content}

请严格按以下 JSON 格式返回（字段顺序与定义一致）：
{{
  {json_fields}
}}"""

    return system_prompt, user_prompt


def render_report_prompt(report_name: str, start_date: str, end_date: str,
                          fact_count: int, aggregated_data: str,
                          chart_data: str, prompt_template: str) -> tuple:
    """
    Render report analysis prompt.

    Args:
        report_name: report name
        start_date / end_date: date range
        fact_count: number of facts
        aggregated_data: JSON aggregated data
        chart_data: JSON chart data
        prompt_template: custom prompt template (Jinja2 format)

    Returns:
        (system_prompt, user_prompt) tuple
    """
    system_prompt = """你是专业情报分析师。请基于已聚合的数据，撰写市场分析报告。

重要规则：
1. 只描述已有数据，不要推断或虚构任何信息
2. 所有数据来自 JSON 格式提供的聚合结果
3. 报告应有逻辑结构，先总后分
4. 语言简洁专业
5. 严格 JSON 格式返回"""

    variables = {
        "report_name": report_name,
        "start_date": start_date,
        "end_date": end_date,
        "fact_count": fact_count,
        "aggregated_data": aggregated_data,
        "chart_data": chart_data,
    }

    try:
        user_prompt = render(prompt_template, variables)
    except Exception:
        # Use default template on render failure
        user_prompt = f"""【报告名称】{report_name}
【分析范围】{start_date} 至 {end_date}
【参与分析的数据】{fact_count} 条结构化事实

=== 数据聚合结果 ===
{aggregated_data}

=== 图表数据 ===
{chart_data}

请基于以上数据撰写分析报告，按 JSON 格式返回：
{{
  "analysis": "文字分析内容...",
  "summary": "一段话总结..."
}}"""

    return system_prompt, user_prompt
