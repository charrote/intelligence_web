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

    target_types=[
        "product",
        "technology",
        "company",
        "market",
        "policy",
        "standard",
    ],

    statuses=[
        ("pending", "待处理"),
        ("active", "处理中"),
        ("done", "已完成"),
    ],

    intelligence_ttl_days={
        "default": 90,
    },

    target_type_initial_data=[
        {"slug": "product", "label": "产品", "description": "制造产品、设备、零部件等", "color": "#3b4f8c", "sort_order": 1},
        {"slug": "technology", "label": "技术", "description": "制造工艺、技术趋势、研发动态", "color": "#2a7d4f", "sort_order": 2},
        {"slug": "company", "label": "公司", "description": "竞争对手、合作伙伴、潜在客户", "color": "#b8862d", "sort_order": 3},
        {"slug": "market", "label": "市场", "description": "市场规模、增长趋势、区域分布", "color": "#b33a3a", "sort_order": 4},
        {"slug": "policy", "label": "政策", "description": "行业标准、政策法规、监管要求", "color": "#3b6ea5", "sort_order": 5},
        {"slug": "standard", "label": "标准", "description": "国际标准、国家标准、行业标准", "color": "#722ed1", "sort_order": 6},
    ],
)
