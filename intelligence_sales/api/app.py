"""Sales domain — Flask application entry point."""

import os, sys
# In Docker: /app is the project root. Local dev: project root is one level up.
if os.path.isdir("/app/api"):
    _PROJECT_ROOT = "/app"
else:
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DOMAIN_DIR = _PROJECT_ROOT
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, _DOMAIN_DIR)

from core.app import create_app
from core.db import init_db, get_db_path, create_intelligence
from domain_spec import SPEC

# Init DB
init_db(_PROJECT_ROOT, SPEC)

# Seed demo data
db_path = get_db_path(_PROJECT_ROOT, SPEC["slug"])
import sqlite3
conn = sqlite3.connect(db_path)
count = conn.execute("SELECT COUNT(*) FROM intelligence").fetchone()[0]
conn.close()

if count == 0:
    demos = [
        ("丹尼斯克在越南推出新型冰淇淋稳定剂", "丹尼斯克（Danisco）近日在越南市场推出两款新型冰淇淋稳定剂，针对东南亚高温运输环境优化。新配方可减少30%的冷链依赖性，降低物流成本。\n\n**关键信息**\n- 产品：IceStab Pro-V 系列\n- 目标市场：越南、泰国、印尼\n- 竞争优势：耐高温、降低成本\n- 上市时间：2026年Q3", "竞品动态", "丹尼斯克", "食品配料", 0),
        ("凯瑞集团收购菲律宾调味品公司", "凯瑞（Kerry）集团宣布以2.3亿欧元收购菲律宾调味品制造商Golden Flavors Inc.，加速亚太区布局。\n\n**影响分析**\n- 增强本地化研发能力\n- 扩大东南亚市场份额\n- 对华策略：或通过菲律宾基地辐射中国市场", "行业动态", "凯瑞", "食品配料", 0),
        ("帕斯嘉2026上半年财报发布", "帕斯嘉（Pascall）发布2026上半年财报，亚太区营收增长15.3%，其中中国区增长12.8%。\n\n**核心数据**\n- 全球营收：48.6亿欧元（+8.2%）\n- 亚太区：12.3亿欧元（+15.3%）\n- 研发投入：2.8亿欧元（+11.5%）\n- 净利润：6.2亿欧元（+9.1%）", "竞品动态", "帕斯嘉", "食品配料", 0),
        ("越南冰淇淋市场2026年需求预测", "据行业报告，2026年越南冰淇淋市场规模预计达到4.8亿美元，同比增长12.5%。\n\n**市场数据**\n- 人均消费：1.2kg/年（vs 中国2.8kg/年）\n- 增长驱动：年轻人口、旅游经济、零售渠道扩张\n- 主要品牌：Kido、Vinamilk、雀巢、和路雪\n- 进口依赖：高端原料60%依赖进口\n\n**机会点**\n越南冰淇淋市场处于快速增长期，高端原料进口需求旺盛，是进入该市场的好时机。", "市场情报", "", "冰淇淋", 8000000),
        ("和路雪越南工厂扩建完成", "联合利华旗下和路雪（Wall's）越南工厂扩建项目完工，产能提升40%。新生产线将专注于高端冰淇淋产品。\n\n**项目细节**\n- 投资额：5000万美元\n- 新增产能：2万吨/年\n- 投产时间：2026年8月\n- 供应范围：越南、柬埔寨、老挝\n\n**对供应商影响**\n新产线投入使用后将增加对香精香料、稳定剂等原料的采购需求。", "客户情报", "和路雪", "冰淇淋", 0),
        ("雀巢中国冰淇淋业务调整", "雀巢中国宣布重组冰淇淋业务，将高端品牌Movenpick（莫凡彼）的经销权从上海迁至广州，并计划在华南新增3个经销商。\n\n**调整详情**\n- 经销中心：上海→广州\n- 新增经销商：华南区3家\n- 目标：辐射粤港澳大湾区\n\n**切入点**\n经销商变更期是切入雀巢供应链的最佳时机，建议尽快接触新的经销商体系。", "客户情报", "雀巢", "冰淇淋", 0),
        ("中国冰淇淋稳定剂市场分析", "2026年中国冰淇淋稳定剂市场规模约12.5亿元，同比增长8.3%。\n\n**竞争格局**\n| 厂商 | 份额 | 定位 |\n|------|------|------|\n| 丹尼斯克 | 22% | 高端 |\n| 凯瑞 | 18% | 中高端 |\n| 帕斯嘉 | 15% | 中端 |\n| 国内厂商 | 35% | 中低端 |\n\n**趋势**\n- 清洁标签产品需求增长\n- 植物基稳定剂受青睐\n- 功能性冰淇淋（高蛋白/低糖）带动特种原料需求", "市场情报", "", "稳定剂", 0),
        ("李岩在泰国新建工厂", "理研（李岩）在泰国罗勇府投资建设新工厂，预计2027年初投产，主要生产冰淇淋用香精和稳定剂。\n\n**项目概况**\n- 投资额：1.2亿美元\n- 产能：1.5万吨/年\n- 产品：冰淇淋香精、乳品稳定剂\n- 目标市场：东南亚、南亚", "竞品动态", "李岩", "食品配料", 0),
        ("广东某食品厂寻冰淇淋稳定剂供应商", "广州某中型冰淇淋生产商因产能扩张，急需寻找新的稳定剂供应商。月需求约5吨，要求产品符合清洁标签标准，价格有竞争力。\n\n**客户画像**\n- 年产能：3万吨\n- 月需求：5吨稳定剂\n- 关注点：品质稳定、价格合理、交货及时\n- 现有供应商：丹尼斯克（占比60%）、国内厂商（40%）\n\n**切入点**\n该客户对丹尼斯克的供货价不满意，正在寻找替代方案，是切入的好机会。", "商机线索", "广东某食品厂", "食品", 500000),
        ("2026亚洲食品配料展（FIA）参展商名单", "2026年亚洲食品配料展（Food Ingredients Asia）将于9月在曼谷举办，预计参展商超过800家。\n\n**相关参展商**\n- 丹尼斯克（展位B12）\n- 凯瑞（展位C45）\n- 帕斯嘉（展位A78）\n- 国内主要厂商（展位D区）\n\n**建议**\n参加该展会是了解竞争对手最新产品和接触潜在客户的最佳机会。建议安排销售团队参加。", "展会信息", "", "展会", 15000),
    ]
    for title, content, category, company, industry, value in demos:
        create_intelligence(db_path, title, content, category, "", {
            "company": company,
            "contact_name": "",
            "deal_value": value,
            "industry": industry,
        })

# Create app
app = create_app(_PROJECT_ROOT, SPEC)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=SPEC["port"], debug=True)