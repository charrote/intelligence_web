"""Sales domain configuration."""

from core.domain import build_spec

SPEC = build_spec(
    slug="intelligence_sales",
    port=8767,
    title_prefix="销售情报",
    scout_label="销售情报采集",
    agent_names=["贾维斯", "南希"],
    theme_color="#1890ff",
    inbox_rel="../sales_inbox/",
    db_filename="intelligence_sales",

    statuses=[
        ("pending", "待核实"),
        ("qualified", "合格商机"),
        ("proposal", "方案报价"),
        ("negotiation", "商务谈判"),
        ("won", "成交"),
        ("lost", "丢标"),
    ],

    extra_columns=[
        ("company", "TEXT DEFAULT ''"),
        ("contact_name", "TEXT DEFAULT ''"),
        ("deal_value", "REAL DEFAULT 0"),
        ("industry", "TEXT DEFAULT ''"),
    ],

    list_columns=["id", "title", "company", "deal_value", "status", "date"],

    search={"engine": "meilisearch", "url": "http://meilisearch:7700", "api_key": "intel-search-key"},

    intelligence_ttl_days={
        "default": 180,
        "展会信息": 7,
        "市场价格": 30,
        "商机线索": 90,
        "竞品动态": 180,
        "公司概况": 365,
    },

    default_entities=[
        {"name": "丹尼斯克", "type": "competitor", "aliases": ["Danisco", "杜邦"],
         "description": "全球领先的食品配料供应商，关注冰淇淋稳定剂等产品",
         "metadata": {"location": [10.5, 56], "location_name": "丹麦", "capacity": 18.5, "unit": "万吨/年"}},
        {"name": "凯瑞集团", "type": "competitor", "aliases": ["Kerry", "Kerry Group"],
         "description": "爱尔兰食品配料巨头，近期在菲律宾有收购动作",
         "metadata": {"location": [-8, 53], "location_name": "爱尔兰", "capacity": 12.3, "unit": "万吨/年"}},
        {"name": "帕斯嘉", "type": "competitor", "aliases": ["Palsgaard"],
         "description": "丹麦食品配料公司，专注乳化剂和稳定剂",
         "metadata": {"location": [12.5, 42], "location_name": "意大利", "capacity": 9.8, "unit": "万吨/年"}},
        {"name": "李岩", "type": "competitor", "aliases": ["Li Yan", "李岩集团"],
         "description": "日本食品配料企业，在泰国新建工厂",
         "metadata": {"location": [138, 36], "location_name": "日本", "capacity": 5.6, "unit": "万吨/年"}},
        {"name": "和路雪", "type": "customer", "aliases": ["Wall's", "联合利华"],
         "description": "冰淇淋品牌，越南工厂扩建中",
         "metadata": {"location": [105.8, 21], "location_name": "越南", "capacity_expansion": "+40%"}},
        {"name": "雀巢", "type": "customer", "aliases": ["Nestle", "Nestlé"],
         "description": "全球食品巨头，中国业务有调整",
         "metadata": {"location": [104, 30], "location_name": "中国", "business_change": "业务调整"}},
        {"name": "广东某食品厂", "type": "customer", "aliases": ["广东食品厂", "广州冰淇淋生产商"],
         "description": "中型冰淇淋生产商，月需求约5吨稳定剂",
         "metadata": {"location": [113.5, 23], "location_name": "广东，中国", "monthly_demand": "5吨"}},
        {"name": "越南市场", "type": "market", "aliases": ["Vietnam", "越南"],
         "description": "东南亚重点市场，冰淇淋产量增长快"},
        {"name": "冰淇淋稳定剂", "type": "product", "aliases": ["冰淇淋稳定剂", "ice cream stabilizer"],
         "description": "核心产品品类，关注配方创新和原料价格"},
        {"name": "李岩新工厂", "type": "investment", "aliases": ["李岩泰国工厂", "理研新工厂"],
         "description": "李岩在泰国罗勇府投资新建工厂",
         "metadata": {"location": [100.5, 14], "location_name": "泰国", "investment": "1.2亿美元"}},
        {"name": "Golden Flavors", "type": "investment", "aliases": ["Golden Flavors Inc"],
         "description": "菲律宾调味品制造商，被凯瑞收购",
         "metadata": {"location": [122, 13], "location_name": "菲律宾", "acquisition": "凯瑞收购"}},
    ],

    default_data_sources=[
        {"name": "丹尼斯克官网", "type": "website", "url": "https://www.danisco.com",
         "indicators": ["新产品发布", "客户案例", "新闻动态"], "schedule": "daily"},
        {"name": "食品行业展会网", "type": "website", "url": "https://www.food-expo.com",
         "indicators": ["展商列表", "新品发布", "行业趋势"], "schedule": "weekly"},
        {"name": "越南海关数据", "type": "api", "url": "https://customs.vn/api",
         "indicators": ["冰淇淋进出口量", "月度趋势"], "schedule": "weekly"},
        {"name": "凯瑞集团官网", "type": "website", "url": "https://www.kerry.com",
         "indicators": ["财报", "收购动态", "新品发布"], "schedule": "daily"},
    ],

    target_types=[
        "competitor",
        "market",
        "customer",
        "supplier",
        "investment",
        "product",
    ],

    target_type_initial_data=[
        {"slug": "competitor", "label": "竞争对手", "description": "同行业竞争对手动态、产品发布、市场策略", "color": "#b33a3a", "sort_order": 1},
        {"slug": "market", "label": "市场", "description": "目标市场规模、增长趋势、区域分布", "color": "#3b6ea5", "sort_order": 2},
        {"slug": "customer", "label": "客户", "description": "潜在客户、现有客户业务变化、采购需求", "color": "#2a7d4f", "sort_order": 3},
        {"slug": "supplier", "label": "供应商", "description": "原材料供应商、价格波动、供应风险", "color": "#b8862d", "sort_order": 4},
        {"slug": "investment", "label": "投资", "description": "行业投资、并购重组、新厂建设", "color": "#722ed1", "sort_order": 5},
        {"slug": "product", "label": "产品", "description": "竞品产品、新品发布、技术升级", "color": "#3b4f8c", "sort_order": 6},
    ],
)