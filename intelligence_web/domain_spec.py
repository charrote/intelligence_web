"""Research domain configuration."""

from core.domain import build_spec

SPEC = build_spec(
    slug="intelligence_web",
    port=8766,
    title_prefix="情报管理系统",
    scout_label="制造情报采集",
    agent_names=["贾维斯", "美雪", "南希", "马格南"],
    theme_color="#722ed1",
    inbox_rel="../inbox/",
    db_filename="intelligence",

    search={"engine": "meilisearch", "url": "http://meilisearch:7700", "api_key": "intel-search-key"},

    default_entities=[
        {"name": "MES 系统", "type": "product", "description": "制造执行系统"},
        {"name": "边缘计算", "type": "technology", "description": "工业边缘计算平台"},
        {"name": "网络安全", "type": "category", "description": "工业网络安全"},
        {"name": "AI 质检", "type": "product", "description": "AI 驱动的质量检测"},
    ],
)
