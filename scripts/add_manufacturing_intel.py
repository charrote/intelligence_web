#!/usr/bin/env python3
"""
模拟制造情报域数据脚本
- 补全表结构（添加缺失列）
- 插入18条模拟情报数据
- 为关键情报添加 Agent 评论和历史记录
"""

import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'intelligence_web', 'data', 'intelligence')

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_columns():
    """确保 intelligence 表有所有需要的列"""
    conn = get_conn()
    cursor = conn.cursor()

    # Check which columns exist
    cursor.execute("PRAGMA table_info(intelligence)")
    existing_cols = {row['name'] for row in cursor.fetchall()}

    additions = [
        ("contact_name", "TEXT DEFAULT ''"),
        ("company", "TEXT DEFAULT ''"),
        ("deal_value", "REAL DEFAULT 0"),
        ("industry", "TEXT DEFAULT ''"),
    ]

    added = []
    for col_name, col_type in additions:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE intelligence ADD COLUMN {col_name} {col_type}")
            added.append(col_name)

    if added:
        print(f"[+] 已添加列: {', '.join(added)}")
    else:
        print("[*] 表结构已是最新")

    conn.commit()
    conn.close()

def add_intelligence(conn, title, content, category, company, contact_name, deal_value, industry, status, opinion, created_at):
    """Insert a single intelligence record"""
    updated_at = created_at
    try:
        conn.execute('''
            INSERT INTO intelligence (title, content, category, status, opinion, contact_name, company, deal_value, industry, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, content, category, status, opinion, contact_name, company, deal_value, industry, created_at, updated_at))
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except sqlite3.IntegrityError:
        print(f"  [!] 跳过重复: {title}")
        return None

def add_comment(conn, intel_id, agent_name, content, agent_id=''):
    now = datetime.now().isoformat()
    conn.execute('''
        INSERT INTO comments (intelligence_id, agent_name, agent_id, content, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (intel_id, agent_name, agent_id, content, now))
    conn.commit()

def add_history(conn, intel_id, action, detail=''):
    now = datetime.now().isoformat()
    conn.execute('''
        INSERT INTO history (intelligence_id, action, detail, file_location, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (intel_id, action, detail, '', now))
    conn.commit()

def add_summary(conn, intel_id, content):
    now = datetime.now().isoformat()
    conn.execute('DELETE FROM summaries WHERE intelligence_id = ?', (intel_id,))
    conn.execute('''
        INSERT INTO summaries (intelligence_id, content, updated_at)
        VALUES (?, ?, ?)
    ''', (intel_id, content, now))
    conn.commit()

def main():
    print("=" * 60)
    print("制造情报域 — 模拟数据填充")
    print("=" * 60)

    # Step 1: Ensure columns
    print("\n[1] 补全表结构...")
    ensure_columns()

    # Step 2: Add simulated intelligence
    print("\n[2] 插入模拟情报数据...")

    now = datetime.now()
    base_date = now - timedelta(days=30)

    intelligences = [
        # --- MES 系统相关 ---
        {
            "title": "Siemens Xcelerator 工业软件平台发布 2026 新版本",
            "content": "西门子推出 Xcelerator 开放数字商业平台 2026 年度更新，重点强化边缘计算与 AI 驱动的预测性维护能力。新版本集成 Teamcenter 2208 和 SIMATIC IT，支持多租户 SaaS 模式，面向中小制造企业的 MES 部署成本降低 40%。平台新增对 OPC UA over TSN 的原生支持，实现设备层到云端的统一数据管道。据 Siemens 财报，工业软件收入同比增长 22%，其中中国市场贡献超过 15%。",
            "category": "产品",
            "company": "Siemens AG",
            "contact_name": "王明辉",
            "deal_value": 0,
            "industry": "工业自动化",
            "status": "active",
            "opinion": "关注 Siemens 在中小制造企业 MES 市场的下沉策略，可能与我们的目标客户群高度重合。建议持续跟踪其定价策略和合作伙伴渠道。",
            "created_at": (base_date + timedelta(days=28)).isoformat(),
            "agent_comments": [
                {"agent": "贾维斯", "content": "Siemens 在 MES 领域的持续投入值得重视，特别是 SaaS 模式的定价策略。他们的目标客户群体与我们的 1-5 亿营收制造企业高度重合。"},
                {"agent": "美雪", "content": "OPC UA over TSN 的标准化是工业通信的重要里程碑，建议关注国内 PLC 厂商的跟进情况。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
                {"action": "状态变更: pending -> active", "detail": "与目标客户关注方向一致"},
            ],
        },
        {
            "title": "华为 FusionPlant 工业 IoT 平台在东南亚制造业落地",
            "content": "华为 FusionPlant 平台宣布在泰国、越南、印尼等东南亚制造业密集地区完成首批部署。平台采用边缘+云协同架构，支持实时数据采集频率达毫秒级，已接入超过 200 万台工业设备。华为与泰国 EEIO（东部经济走廊）合作建设智慧工厂标杆项目，涵盖汽车制造、食品加工两大行业。平台集成华为昇腾 AI 芯片，提供本地化推理能力，满足数据主权要求。",
            "category": "技术",
            "company": "华为技术有限公司",
            "contact_name": "张磊",
            "deal_value": 0,
            "industry": "工业物联网",
            "status": "active",
            "opinion": "华为在东南亚的布局对国产工业软件出海有参考价值。其边缘+云架构和本地化推理能力是差异化优势。",
            "created_at": (base_date + timedelta(days=25)).isoformat(),
            "agent_comments": [
                {"agent": "南希", "content": "东南亚是制造转移的热土，华为选择这个时机切入工业 IoT 很有战略眼光。昇腾 AI 的本地推理能力对数据敏感的制造业客户有吸引力。"},
                {"agent": "马格南", "content": "EEIO 智慧工厂标杆项目值得关注，如果能拿到具体部署细节，可以评估我们产品的对标空间。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
                {"action": "标记: 重点关注", "detail": "东南亚制造业数字化趋势"},
            ],
        },
        {
            "title": "GE Digital Predix 平台转型为 Industry 4.0 开放生态",
            "content": "通用电气宣布 Predix 平台从封闭式 SaaS 模式转向开放生态战略，引入第三方开发者和合作伙伴，支持多厂商设备接入。新平台命名为 'GE Digital Open'，兼容 MQTT、OPC UA、Modbus 等主流工业协议，提供容器化部署选项。GE 同时与 PTC 达成合作，整合 ThingWorx 的 AR 远程运维能力。市场分析机构 IDC 预测，到 2028 年工业 IoT 平台市场将突破 250 亿美元。",
            "category": "产品",
            "company": "GE Digital",
            "contact_name": "David Chen",
            "deal_value": 0,
            "industry": "工业软件",
            "status": "done",
            "opinion": "Predix 的开放转型反映了工业软件从封闭走向生态的大趋势。这对我们产品架构的设计有启发：需要优先考虑协议兼容性和第三方集成能力。",
            "created_at": (base_date + timedelta(days=22)).isoformat(),
            "agent_comments": [
                {"agent": "贾维斯", "content": "GE 从封闭到开放的转变很典型，说明工业软件行业正在从厂商锁定转向生态竞争。我们的架构也需要做好开放集成准备。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
                {"action": "状态变更: pending -> active -> done", "detail": "已完成跟踪，趋势已明确"},
            ],
        },
        {
            "title": "中国 '十四五' 智能制造发展规划中期评估报告发布",
            "content": "工信部发布《'十四五'智能制造发展规划》中期评估报告。报告显示，截至 2025 年底，全国已建成智能化工厂超过 3000 家，智能制造装备市场满足率超过 50%，关键工序数控化率达到 62%。报告指出，工业软件国产化率不足 20% 仍是最大瓶颈，特别是在 MES、ERP、PLM 等核心领域。国家发改委同步启动新一轮智能制造试点示范项目申报，预计投入财政补贴超 10 亿元。",
            "category": "政策",
            "company": "工业和信息化部",
            "contact_name": "李建国",
            "deal_value": 0,
            "industry": "智能制造",
            "status": "active",
            "opinion": "政策风向非常明确：MES/ERP 国产化是重点扶持方向。关注 10 亿财政补贴的具体分配，可能对目标客户预算产生直接影响。",
            "created_at": (base_date + timedelta(days=20)).isoformat(),
            "agent_comments": [
                {"agent": "美雪", "content": "工业软件国产化率不足 20% 这个数据很关键，说明市场空间巨大。10 亿补贴如果能定向支持 MES 采购，将直接拉动目标客户预算。"},
                {"agent": "贾维斯", "content": "政策窗口期宝贵，建议快速制定针对智能制造试点示范企业的专项推广方案。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
                {"action": "标记: 政策利好", "detail": "工业软件国产化率不足 20%"},
            ],
            "summary": "工信部评估显示国内已建成 3000+ 智能工厂，但工业软件国产化率不足 20%。10 亿财政补贴即将启动，MES 等核心工业软件是重点扶持方向。这为国产 MES 厂商创造了重要的政策窗口期。",
        },
        {
            "title": "Rockwell Automation 推出 factoryTalk Analytics AI 增强版",
            "content": "罗克韦尔自动化发布 factoryTalk Analytics 2026 AI 增强版，集成大语言模型能力，支持自然语言查询工厂运营数据。新功能包括：AI 驱动的设备故障根因分析、自动化的产能优化建议、以及基于历史数据的维护策略推荐。该版本支持在边缘端部署轻量模型（<2GB），满足工厂本地化数据处理需求。Rockwell 同时宣布与微软 Azure 深化合作，提供混合云数据分析方案。",
            "category": "产品",
            "company": "Rockwell Automation",
            "contact_name": "Sarah Johnson",
            "deal_value": 0,
            "industry": "工业自动化",
            "status": "pending",
            "opinion": "",
            "created_at": (base_date + timedelta(days=18)).isoformat(),
            "agent_comments": [
                {"agent": "马格南", "content": "factoryTalk Analytics 的 AI 增强版很有意思，特别是自然语言查询和边缘端轻量模型。这代表了 MES 产品的发展方向：从数据采集走向智能决策。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
            ],
        },
        {
            "title": "施耐德 Electric 推出 EcoStruxure 工业 AI 质检解决方案",
            "content": "施耐德电气发布 EcoStruxure Machine 系列 AI 视觉质检方案，基于深度学习的表面缺陷检测精度达到 99.7%，检测速度提升至 0.3 秒/件，适用于汽车、电子、食品包装等行业。方案集成施耐德 Modicon PLC 和 Magelis HMI，支持边缘部署和云端训练。首次部署案例为比亚迪新能源汽车电池产线，缺陷检出率较传统机器视觉提升 35%。",
            "category": "技术",
            "company": "Schneider Electric",
            "contact_name": "赵鹏飞",
            "deal_value": 0,
            "industry": "工业 AI",
            "status": "active",
            "opinion": "AI 质检是制造业的高频刚需，施耐德以比亚迪为标杆案例很有说服力。0.3 秒/件的检测速度在行业中处于领先水平。",
            "created_at": (base_date + timedelta(days=15)).isoformat(),
            "agent_comments": [
                {"agent": "美雪", "content": "99.7% 的精度和 0.3 秒/件的速度在 AI 质检领域确实是领先水平。比亚迪案例很有说服力，尤其是新能源汽车电池产线的场景。"},
                {"agent": "南希", "content": "这个方案与我们关注的 AI 质检方向高度一致。需要评估其定价和部署门槛，看是否能作为我们的竞品对标对象。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
                {"action": "标记: 技术标杆", "detail": "AI 质检 99.7% 精度"},
            ],
        },
        {
            "title": "中国工业互联网产业规模突破 1.2 万亿元",
            "content": "中国信通院发布《2025 中国工业互联网产业经济发展报告》，显示 2025 年中国工业互联网产业规模达 1.23 万亿元，同比增长 18.6%。其中，工业软件（含 MES、SCADA、APS 等）市场规模达 2800 亿元，同比增长 22%。报告指出，离散制造业的数字化渗透率仍不足 30%，是下一阶段增长的主要驱动力。长三角和珠三角地区贡献了全国 55% 的工业互联网产值。",
            "category": "市场",
            "company": "中国信息通信研究院",
            "contact_name": "陈思远",
            "deal_value": 0,
            "industry": "工业互联网",
            "status": "done",
            "opinion": "市场规模数据证实了制造数字化的巨大潜力。离散制造业 30% 的渗透率意味着 70% 的增量空间，这正是我们的目标市场。",
            "created_at": (base_date + timedelta(days=12)).isoformat(),
            "agent_comments": [
                {"agent": "贾维斯", "content": "1.2 万亿的产业规模和 22% 的工业软件增速很有说服力。离散制造 30% 的渗透率意味着 70% 的增量市场，这正是我们的核心目标。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
                {"action": "状态变更: pending -> active -> done", "detail": "市场数据已确认"},
            ],
        },
        {
            "title": "PTC 收购工业 AR 初创公司 Wiliot，布局数字孪生生态",
            "content": "PTC 以 3.2 亿美元收购以色列工业物联网初创公司 Wiliot，后者擅长基于蓝牙信标的资产追踪和数字孪生技术。交易完成后，PTC 的 Vuforia 平台将集成 Wiliot 的实时定位能力，实现物理工厂与数字孪生的秒级同步。PTC 同时宣布其 ThingWorx 平台已接入超过 500 万个工业设备，覆盖汽车、制药、食品加工等行业。",
            "category": "公司",
            "company": "PTC Inc.",
            "contact_name": "Michael Lee",
            "deal_value": 0,
            "industry": "工业软件",
            "status": "done",
            "opinion": "PTC 通过收购快速补齐数字孪生能力，这种 M&A 策略值得跟踪。工业 AR+数字孪生可能是下一代 MES 的差异化方向。",
            "created_at": (base_date + timedelta(days=10)).isoformat(),
            "agent_comments": [
                {"agent": "马格南", "content": "3.2 亿美元收购 Wiliot，PTC 在数字孪生领域的野心很大。工业 AR+数字孪生确实是下一代 MES 的差异化方向，值得关注。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
                {"action": "状态变更: pending -> done", "detail": "收购已完成"},
            ],
        },
        {
            "title": "Bosch 博世推出工业 5G 专网解决方案",
            "content": "博世发布工业 5G 专网解决方案，基于 Private 5G 技术，为制造工厂提供超低延迟、高可靠性的无线网络覆盖。方案支持同时连接超过 100 万台设备，端到端延迟低于 1ms，适用于 AGV 调度、AR 辅助装配、实时质检等场景。博世在苏州工厂完成首条 5G 专网产线部署，覆盖汽车发动机装配线，设备连接密度达到每平方公里 100 万。",
            "category": "技术",
            "company": "Bosch GmbH",
            "contact_name": "刘洋",
            "deal_value": 0,
            "industry": "工业通信",
            "status": "active",
            "opinion": "工业 5G 是智能制造基础设施的重要一环。博世苏州工厂的标杆案例证明了技术可行性，关注国内运营商的跟进情况。",
            "created_at": (base_date + timedelta(days=8)).isoformat(),
            "agent_comments": [
                {"agent": "南希", "content": "工业 5G 专网是智能制造的基础设施升级，1ms 延迟对实时控制场景至关重要。苏州工厂的标杆案例很有说服力。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
            ],
        },
        {
            "title": "国家智能制造标准体系 2026 版正式发布",
            "content": "全国智能制造标准化技术委员会发布《智能制造标准体系建设指南（2026 版）》，新增 38 项标准，重点覆盖工业数据安全、AI 质量控制、数字孪生、边缘计算等领域。新标准与 ISO/IEC 23247（数字孪生制造框架）和 IEC 63278（工业 AI 系统评估）等国际标准的对标关系更加清晰。标准实施日期为 2026 年 10 月 1 日，要求重点行业规模以上企业完成标准符合性评估。",
            "category": "标准",
            "company": "全国智能制造标准化技术委员会",
            "contact_name": "周志远",
            "deal_value": 0,
            "industry": "智能制造",
            "status": "pending",
            "opinion": "",
            "created_at": (base_date + timedelta(days=5)).isoformat(),
            "agent_comments": [],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
            ],
        },
        {
            "title": "达索系统 3DEXPERIENCE 平台深化中国本土化战略",
            "content": "达索系统宣布 3DEXPERIENCE 平台中国本土化升级，推出中文版 AI 助手和国产云部署选项（支持阿里云、腾讯云）。新平台集成 PLM、MES、ERP 全生命周期管理，支持汽车行业从产品设计到生产制造的全链路数字化。达索同时与中国汽车工程学会合作，制定新能源汽车数字孪生标准。据达索中国区财报，2025 年收入同比增长 28%，其中汽车行业贡献超过 45%。",
            "category": "公司",
            "company": "Dassault Systèmes",
            "contact_name": "Pierre Dupont",
            "deal_value": 0,
            "industry": "工业软件",
            "status": "active",
            "opinion": "达索在中国市场的本土化策略很激进，国产云部署和 AI 助手都是针对中国客户痛点的改进。汽车行业 45% 的收入贡献说明汽车是核心战场。",
            "created_at": (base_date + timedelta(days=3)).isoformat(),
            "agent_comments": [
                {"agent": "贾维斯", "content": "达索的本土化策略很激进：国产云部署、AI 助手、行业标准合作。汽车行业 45% 的收入说明他们把中国作为核心市场。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
            ],
        },
        {
            "title": "ABB 推出 AI 驱动的工厂能效优化系统",
            "content": "ABB 发布 Ability 平台 AI 能效优化模块，通过机器学习分析工厂能耗数据，自动优化设备运行参数，实现综合能耗降低 15-25%。系统已在中信泰富特钢、海尔智家等中国企业完成部署，年节省电费超 500 万元。ABB 与施耐德达成合作，将双方电气设备的能耗数据统一接入 Ability 平台，提供跨品牌能效管理。",
            "category": "技术",
            "company": "ABB Ltd.",
            "contact_name": "何晓明",
            "deal_value": 0,
            "industry": "工业节能",
            "status": "active",
            "opinion": "AI 能效优化是一个很好的切入点，15-25% 的节能效果对制造企业有直接的经济吸引力。海尔和中信的案例很有说服力。",
            "created_at": (base_date + timedelta(days=2)).isoformat(),
            "agent_comments": [
                {"agent": "美雪", "content": "AI 能效优化 15-25% 的节能效果很有吸引力，尤其是年节省 500 万电费这种具体数字。海尔和中信的案例很有说服力。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
            ],
        },
        {
            "title": "国内 MES 厂商竞业分析报告：用友、金蝶、黑湖等动态",
            "content": "综合监测到以下国内 MES 厂商最新动态：用友 YonSuite 发布 2026 Q2 更新，强化离散制造 MES 能力，新增 APS 高级排产模块；金蝶云·星辰推出面向 100 人以下小微企业的轻量化 MES，定价 3 万/年；黑湖科技完成 C 轮融资 2 亿元，估值超 20 亿元，计划拓展汽车零部件行业；鼎捷软件与用友达成战略合作，共同推进制造业数字化转型。",
            "category": "公司",
            "company": "多厂商综合",
            "contact_name": "",
            "deal_value": 0,
            "industry": "工业软件",
            "status": "active",
            "opinion": "国内 MES 市场竞争加剧，用友和金蝶在低端市场的定价策略（3 万/年）对 1-5 亿营收的中小企业有吸引力。黑湖的 C 轮融资说明资本市场对 MES 赛道仍有信心。",
            "created_at": (base_date + timedelta(days=1)).isoformat(),
            "agent_comments": [
                {"agent": "南希", "content": "竞品动态汇总很有价值。金蝶 3 万/年的定价对小微企业很有吸引力，黑湖 C 轮 2 亿说明资本市场看好 MES 赛道。需要持续跟踪用友和鼎捷的动向。"},
                {"agent": "马格南", "content": "这个综合报告很实用，一次性看清了主要竞品动态。金蝶的轻量化策略和用友的高端化策略形成鲜明对比。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
                {"action": "标记: 竞品综合", "detail": "用友、金蝶、黑湖、鼎捷动态"},
            ],
        },
        {
            "title": "工业数据安全法草案征求意见：制造数据出境须审批",
            "content": "国家网信办发布《工业数据安全管理办法（征求意见稿）》，要求工业数据出境须经安全评估审批，关键信息基础设施运营者的核心数据禁止出境。草案同时提出数据分类分级制度，将工业数据分为一般、重要、核心三个级别。征求意见截止日期为 2026 年 9 月 30 日。行业普遍认为，该办法将对跨国工业软件厂商的数据策略产生重大影响。",
            "category": "政策",
            "company": "国家网信办",
            "contact_name": "吴伟",
            "deal_value": 0,
            "industry": "工业安全",
            "status": "pending",
            "opinion": "",
            "created_at": (now - timedelta(days=1)).isoformat(),
            "agent_comments": [],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
            ],
        },
        {
            "title": "三菱电机 PLC 新品 FX5U 系列集成边缘 AI 推理功能",
            "content": "三菱电机发布 FX5U 系列 PLC 新品，首次将边缘 AI 推理功能集成到小型 PLC 中，支持 TensorFlow Lite 模型部署，可在 PLC 本地完成简单视觉检测和预测性维护推理。新系列支持 CC-Link IE TSN 工业以太网协议，最大 I/O 点数达 1024 点。三菱同时宣布与 SoftBank 合作，在日本汽车工厂部署基于 FX5U 的智能产线方案。",
            "category": "产品",
            "company": "Mitsubishi Electric",
            "contact_name": "田中太郎",
            "deal_value": 0,
            "industry": "工业自动化",
            "status": "done",
            "opinion": "三菱在小型 PLC 中集成 AI 推理是一个重要信号：边缘智能正在下沉到最底层的控制设备。这可能会改变 MES 与 PLC 之间的数据交互模式。",
            "created_at": (now - timedelta(days=3)).isoformat(),
            "agent_comments": [
                {"agent": "马格南", "content": "三菱 FX5U 集成 AI 推理是个重要信号，边缘智能正在下沉到 PLC 层面。这可能会改变 MES 与设备层之间的数据交互架构。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
                {"action": "状态变更: pending -> done", "detail": "产品发布已完成"},
            ],
        },
        {
            "title": "全球半导体设备市场 2026 年 Q1 报告显示对华出口管制升级",
            "content": "SEMCO 最新报告显示，2026 年 Q1 全球半导体设备市场规模达 218 亿美元，同比增长 12%。美国商务部升级对华出口管制，限制先进制程（<7nm）设备出口，同时扩大对国产替代设备的监控范围。中国半导体设备自主化率从 2020 年的 15% 提升至 2025 的 32%，但在光刻、刻蚀等核心环节仍严重依赖进口。国内设备厂商北方华创、中微公司在刻蚀和薄膜沉积领域取得突破。",
            "category": "市场",
            "company": "SEMICO",
            "contact_name": "林正刚",
            "deal_value": 0,
            "industry": "半导体",
            "status": "active",
            "opinion": "半导体设备出口管制升级对国内制造企业有双重影响：供应链风险和国产替代机会。关注北方华创、中微在刻蚀领域的进展。",
            "created_at": (now - timedelta(days=5)).isoformat(),
            "agent_comments": [
                {"agent": "贾维斯", "content": "出口管制升级对半导体制造有双重影响：供应链风险和国产替代机会。32% 的自主化率说明替代空间仍然很大。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
            ],
        },
        {
            "title": "GE 与 PTC 合作推进工业 AI 安全标准制定",
            "content": "GE Digital 与 PTC 联合发布《工业 AI 系统安全框架白皮书》，提出工业 AI 系统的安全评估标准，涵盖模型可解释性、数据隐私保护、系统鲁棒性等维度。白皮书建议工业 AI 系统应通过 IEC 62443 网络安全认证，并在部署前完成第三方安全审计。两大厂商同时承诺将开源部分安全评估工具，推动行业标准化进程。",
            "category": "标准",
            "company": "GE Digital & PTC",
            "contact_name": "",
            "deal_value": 0,
            "industry": "工业安全",
            "status": "done",
            "opinion": "工业 AI 安全标准是行业规范化发展的重要一步，GE 和 PTC 联合推动说明主流厂商开始重视这个问题。",
            "created_at": (now - timedelta(days=7)).isoformat(),
            "agent_comments": [
                {"agent": "南希", "content": "工业 AI 安全框架白皮书很有价值，GE 和 PTC 联合推动说明主流厂商开始重视 AI 安全问题。IEC 62443 认证将成为工业 AI 系统的标配。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
                {"action": "状态变更: pending -> done", "detail": "白皮书已发布"},
            ],
        },
        {
            "title": "富士康工业互联网平台飞虎云 2026 战略升级",
            "content": "富士康旗下工业互联网平台'飞虎云'发布 2026 战略升级计划，从单一制造执行扩展为'制造+供应链+服务'一体化平台。新平台集成数字孪生、AI 质检、供应链协同三大核心模块，已服务富士康全球 200+ 工厂。富士康同时宣布与百度合作，基于文心大模型打造工业 AI 助手，支持中文自然语言操作工厂系统。",
            "category": "公司",
            "company": "富士康/飞虎云",
            "contact_name": "黄伟明",
            "deal_value": 0,
            "industry": "工业互联网",
            "status": "active",
            "opinion": "富士康从制造执行扩展到供应链+服务的策略值得借鉴。与百度合作的大模型工业助手是差异化亮点。",
            "created_at": (now - timedelta(days=9)).isoformat(),
            "agent_comments": [
                {"agent": "美雪", "content": "飞虎云从单一 MES 扩展到一体化平台，这个战略方向很清晰。与百度合作的工业 AI 助手是差异化亮点，值得深入跟踪。"},
            ],
            "history": [
                {"action": "新增情报", "detail": "来自 scout 自动采集"},
            ],
        },
    ]

    conn = get_conn()
    created_ids = []
    for intel in intelligences:
        intel_id = add_intelligence(
            conn,
            title=intel["title"],
            content=intel["content"],
            category=intel["category"],
            company=intel["company"],
            contact_name=intel["contact_name"],
            deal_value=intel["deal_value"],
            industry=intel["industry"],
            status=intel["status"],
            opinion=intel["opinion"],
            created_at=intel["created_at"],
        )
        if intel_id:
            created_ids.append((intel_id, intel["title"]))

            # Add comments if specified
            if "agent_comments" in intel:
                for c in intel["agent_comments"]:
                    add_comment(conn, intel_id, c["agent"], c["content"])

            # Add history if specified
            if "history" in intel:
                for h in intel["history"]:
                    add_history(conn, intel_id, h["action"], h["detail"])

            # Add summary if specified
            if "summary" in intel:
                add_summary(conn, intel_id, intel["summary"])

    print(f"  [+] 成功插入 {len(created_ids)} 条情报")

    # Step 3: Summary
    print("\n[3] 数据统计:")
    total = conn.execute("SELECT COUNT(*) FROM intelligence").fetchone()[0]
    by_status = conn.execute("SELECT status, COUNT(*) FROM intelligence GROUP BY status").fetchall()
    by_category = conn.execute("SELECT category, COUNT(*) FROM intelligence GROUP BY category").fetchall()

    print(f"  总计: {total} 条情报")
    print(f"\n  按状态分布:")
    for row in by_status:
        print(f"    {row[0]}: {row[1]}")
    print(f"\n  按类别分布:")
    for row in by_category:
        print(f"    {row[0]}: {row[1]}")

    # Comments and history counts
    total_comments = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    total_history = conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
    total_summaries = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
    print(f"\n  Agent 评论: {total_comments} 条")
    print(f"  操作历史: {total_history} 条")
    print(f"  AI 摘要: {total_summaries} 个")

    conn.close()
    print("\n" + "=" * 60)
    print("模拟数据填充完成！")
    print("=" * 60)


if __name__ == '__main__':
    main()