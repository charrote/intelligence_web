#!/usr/bin/env python3
"""
Intelligence Web — PPT 生成器（基于 GordenPPTSkill 模板引擎）
使用 GordenPPTSkill 的模板 + build_pptx.py 生成专业 PPT

用法:
  python scripts/gen_ppt_template.py                    # 生成麦肯锡风 PPT (默认)
  python scripts/gen_ppt_template.py --template mckinsey  # 生成麦肯锡风 PPT
  python scripts/gen_ppt_template.py --template minimal   # 生成简约商务风 PPT
  python scripts/gen_ppt_template.py --preview            # 同时渲染预览图
"""
from __future__ import annotations
import json
import sys
import shutil
from pathlib import Path

# ============================================================
# 路径配置
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent
THIRD_PARTY = PROJECT_ROOT / "third_party" / "GordenPPTSkill"
TEMPLATES_DIR = THIRD_PARTY / "templates"
# scripts 在 third_party/GordenPPTSkill/scripts/ 下
SCRIPTS_DIR = THIRD_PARTY / "scripts"
BUILD_SCRIPT = SCRIPTS_DIR / "build_pptx.py"
RENDER_SCRIPT = SCRIPTS_DIR / "render_slides.py"
OUTPUT_DIR = PROJECT_ROOT / "docs"

# ============================================================
# 模板选择（默认 mckinsey）
# ============================================================
TEMPLATES = {
    "mckinsey": "mckinsey-style",
    "minimal": "minimal-business-summary",
}

# ============================================================
# Intelligence Web 内容数据
# ============================================================
PRODUCT_NAME = "Intelligence Web"
SUBTITLE = "企业情报智能管理平台"
TAGLINE = "从情报采集到行动闭环\n让每一个决策都有据可依"

# 四章节结构
CHAPTERS = [
    {
        "cn": "市场洞察",
        "en": "Market Insight",
        "slides": ["cover", "intro", "pains", "what_is"],
        "description": "信息就是竞争力",
    },
    {
        "cn": "产品定义",
        "en": "Product Definition",
        "slides": ["capabilities", "manufacturing", "sales"],
        "description": "五大核心能力",
    },
    {
        "cn": "技术底座",
        "en": "Technology Stack",
        "slides": ["architecture", "lightweight", "ai_agent", "security"],
        "description": "轻而不薄",
    },
    {
        "cn": "商业价值",
        "en": "Business Value",
        "slides": ["cost", "roi", "who_for", "comparison", "deploy", "ending"],
        "description": "投资回报",
    },
]

# ============================================================
# 各页内容（对应 minimal-business-summary 模板 slot）
# ============================================================

def build_edits_minimal() -> dict:
    """为 minimal-business-summary 模板生成 edits.json"""
    return {
        "template_slug": "minimal-business-summary",
        "selected_slides": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        "edits": [
            # ---- Slide 1: 封面 ----
            {"slide": 1, "slot_id": "cover_title_en", "new_text": "INTELLIGENCE"},
            {"slide": 1, "slot_id": "cover_title_cn", "new_text": "企业情报智能管理平台"},

            # ---- Slide 2: 目录 ----
            {"slide": 2, "slot_id": "agenda_title_cn", "new_text": "目录"},
            {"slide": 2, "slot_id": "agenda_title_en", "new_text": "Contents"},
            {"slide": 2, "slot_id": "agenda_ch1_cn", "new_text": "市场洞察"},
            {"slide": 2, "slot_id": "agenda_ch1_en", "new_text": "Market Insight"},
            {"slide": 2, "slot_id": "agenda_ch2_cn", "new_text": "产品定义"},
            {"slide": 2, "slot_id": "agenda_ch2_en", "new_text": "Product Definition"},
            {"slide": 2, "slot_id": "agenda_ch3_cn", "new_text": "技术底座"},
            {"slide": 2, "slot_id": "agenda_ch3_en", "new_text": "Technology"},
            {"slide": 2, "slot_id": "agenda_ch4_cn", "new_text": "商业价值"},
            {"slide": 2, "slot_id": "agenda_ch4_en", "new_text": "Business Value"},

            # ---- Slide 3: 章节 1 扉页 ----
            {"slide": 3, "slot_id": "div1_cn", "new_text": "市场洞察"},
            {"slide": 3, "slot_id": "div1_en", "new_text": "Market Insight"},

            # ---- Slide 4: 信息痛点（3列要点） ----
            {"slide": 4, "slot_id": "p4_breadcrumb_cn", "new_text": "市场洞察 · 痛点分析"},
            {"slide": 4, "slot_id": "p4_breadcrumb_en", "new_text": "Pain Points"},
            {"slide": 4, "slot_id": "p4_item1_title", "new_text": "信息碎片化"},
            {"slide": 4, "slot_id": "p4_item1_body", "new_text": "各部门各管一套数据系统，情报散落各处，90% 的信息被淹没、遗忘或被竞争对手捷足先登"},
            {"slide": 4, "slot_id": "p4_item2_title", "new_text": "响应滞后"},
            {"slide": 4, "slot_id": "p4_item2_body", "new_text": "竞争对手出手后才反应过来，市场变化从月级缩短到天级，传统方式永远慢半拍"},
            {"slide": 4, "slot_id": "p4_item3_title", "new_text": "决策靠直觉"},
            {"slide": 4, "slot_id": "p4_item3_body", "new_text": "管理层拍板靠经验和感觉，缺乏系统化平台把散落的线索变成可行动的洞察"},

            # ---- Slide 5: 产品定义（4列卡片） ----
            {"slide": 5, "slot_id": "p5_breadcrumb_cn", "new_text": "产品定义 · 核心能力"},
            {"slide": 5, "slot_id": "p5_breadcrumb_en", "new_text": "Core Capabilities"},
            {"slide": 5, "slot_id": "p5_card1_title", "new_text": "AI 智能分析"},
            {"slide": 5, "slot_id": "p5_card1_body", "new_text": "AI Agent 自动阅读、摘要、分析、留批注，人机协同知识积累"},
            {"slide": 5, "slot_id": "p5_card2_title", "new_text": "多渠道采集"},
            {"slide": 5, "slot_id": "p5_card2_body", "new_text": "网站抓取、API 对接，按日/周/月灵活设定采集频率"},
            {"slide": 5, "slot_id": "p5_card3_title", "new_text": "数据看板"},
            {"slide": 5, "slot_id": "p5_card3_body", "new_text": "仪表盘统计、多维筛选排序，Meilisearch 毫秒级全文搜索"},
            {"slide": 5, "slot_id": "p5_card4_title", "new_text": "系统管控"},
            {"slide": 5, "slot_id": "p5_card4_body", "new_text": "RBAC 四级权限、审计日志、通知中心、个性化配置"},

            # ---- Slide 6: 四大情报域（4列图标） ----
            {"slide": 6, "slot_id": "p6_breadcrumb_cn", "new_text": "产品定义 · 情报域"},
            {"slide": 6, "slot_id": "p6_breadcrumb_en", "new_text": "Intelligence Domains"},
            {"slide": 6, "slot_id": "p6_col1_title", "new_text": "制造情报"},
            {"slide": 6, "slot_id": "p6_col1_body", "new_text": "看见趋势\n竞品动态、技术演进、政策变化"},
            {"slide": 6, "slot_id": "p6_col2_title", "new_text": "销售情报"},
            {"slide": 6, "slot_id": "p6_col2_body", "new_text": "抓住机会\n客户扩产、竞对投资、商机漏斗"},
            {"slide": 6, "slot_id": "p6_col3_title", "new_text": "供应链情报"},
            {"slide": 6, "slot_id": "p6_col3_body", "new_text": "扩展领域\n寻源评估、供应商监控"},
            {"slide": 6, "slot_id": "p6_col4_title", "new_text": "金融市场情报"},
            {"slide": 6, "slot_id": "p6_col4_body", "new_text": "扩展领域\n投融资动态、并购重组"},

            # ---- Slide 7: 章节 2 扉页 ----
            {"slide": 7, "slot_id": "div2_cn", "new_text": "产品定义"},
            {"slide": 7, "slot_id": "div2_en", "new_text": "Product Definition"},

            # ---- Slide 8: 共享内核架构（2x2 拼图） ----
            {"slide": 8, "slot_id": "p8_breadcrumb_cn", "new_text": "产品定义 · 共享内核"},
            {"slide": 8, "slot_id": "p8_breadcrumb_en", "new_text": "Shared Core Architecture"},
            {"slide": 8, "slot_id": "p8_block1_title", "new_text": "情报采集引擎"},
            {"slide": 8, "slot_id": "p8_block1_body", "new_text": "多渠道数据源统一接入，支持网站抓取、API 对接、定时调度，AI Agent 自动巡检"},
            {"slide": 8, "slot_id": "p8_pic1_caption", "new_text": "结构化存储"},
            {"slide": 8, "slot_id": "p8_pic2_caption", "new_text": "AI 分析层"},
            {"slide": 8, "slot_id": "p8_block2_title", "new_text": "行动闭环"},
            {"slide": 8, "slot_id": "p8_block2_body", "new_text": "从线索到行动的全流程追踪，销售域专属商机管理，从线索到成交"},

            # ---- Slide 9: 技术栈四支柱（METHOD 轮） ----
            {"slide": 9, "slot_id": "p9_breadcrumb_cn", "new_text": "技术底座 · 架构"},
            {"slide": 9, "slot_id": "p9_breadcrumb_en", "new_text": "Tech Stack"},
            {"slide": 9, "slot_id": "p9_wheel_center", "new_text": "CORE"},
            {"slide": 9, "slot_id": "p9_q1_title", "new_text": "Flask + Python"},
            {"slide": 9, "slot_id": "p9_q1_body", "new_text": "Research API (8766) + Sales API (8767)\n轻量级业务引擎，Gunicorn 部署"},
            {"slide": 9, "slot_id": "p9_q2_title", "new_text": "Meilisearch"},
            {"slide": 9, "slot_id": "p9_q2_body", "new_text": "全文检索引擎 (7700)\n毫秒级搜索，支持多维筛选排序"},
            {"slide": 9, "slot_id": "p9_q3_title", "new_text": "MCP Server"},
            {"slide": 9, "slot_id": "p9_q3_body", "new_text": "18 个工具方法，标准化协议\n支持 Claude / Hermes / OpenClaw 多 Agent"},
            {"slide": 9, "slot_id": "p9_q4_title", "new_text": "Nginx Gateway"},
            {"slide": 9, "slot_id": "p9_q4_body", "new_text": "反向代理 (8765)\nJWT 鉴权、CORS 白名单控制"},

            # ---- Slide 10: 章节 3 扉页 ----
            {"slide": 10, "slot_id": "div3_cn", "new_text": "技术底座"},
            {"slide": 10, "slot_id": "div3_en", "new_text": "Technology"},

            # ---- Slide 11: AI Agent 工作流（4列） ----
            {"slide": 11, "slot_id": "p11_breadcrumb_cn", "new_text": "技术底座 · AI Agent"},
            {"slide": 11, "slot_id": "p11_breadcrumb_en", "new_text": "AI Agent Workflow"},
            {"slide": 11, "slot_id": "p11_col1_title", "new_text": "自动巡检"},
            {"slide": 11, "slot_id": "p11_col1_body", "new_text": "AI Agent 每日自动巡检指定数据源，捕获最新动态"},
            {"slide": 11, "slot_id": "p11_col2_title", "new_text": "智能分析"},
            {"slide": 11, "slot_id": "p11_col2_body", "new_text": "AI 对采集内容初步分析和归类，留下观察和建议"},
            {"slide": 11, "slot_id": "p11_col3_title", "new_text": "人机协同"},
            {"slide": 11, "slot_id": "p11_col3_body", "new_text": "人类做出最终判断和行动决策，不是工具而是伙伴"},
            {"slide": 11, "slot_id": "p11_col4_title", "new_text": "持续进化"},
            {"slide": 11, "slot_id": "p11_col4_body", "new_text": "人类反馈反哺 AI，每一次反馈都在提升精度，形成正向飞轮"},

            # ---- Slide 12: 安全体系（4关键词网格） ----
            {"slide": 12, "slot_id": "p12_breadcrumb_cn", "new_text": "技术底座 · 安全"},
            {"slide": 12, "slot_id": "p12_breadcrumb_en", "new_text": "Security"},
            {"slide": 12, "slot_id": "p12_key1", "new_text": "JWT 认证"},
            {"slide": 12, "slot_id": "p12_body1", "new_text": "HS256 Bearer Token，密码 SHA-256 + 随机盐存储"},
            {"slide": 12, "slot_id": "p12_key2", "new_text": "RBAC 权限"},
            {"slide": 12, "slot_id": "p12_body2", "new_text": "Admin / Manager / Analyst / Viewer 四级角色，精细到菜单级"},
            {"slide": 12, "slot_id": "p12_key3", "new_text": "密钥保护"},
            {"slide": 12, "slot_id": "p12_body3", "new_text": "API Key / Agent Key XOR 混淆，API 响应脱敏"},
            {"slide": 12, "slot_id": "p12_key4", "new_text": "审计日志"},
            {"slide": 12, "slot_id": "p12_body4", "new_text": "所有变更操作记录操作人身份和时间戳，满足合规追溯"},

            # ---- Slide 13: 章节 4 扉页 ----
            {"slide": 13, "slot_id": "div4_cn", "new_text": "商业价值"},
            {"slide": 13, "slot_id": "div4_en", "new_text": "Business Value"},

            # ---- Slide 14: 成本对比路线图（4里程碑） ----
            {"slide": 14, "slot_id": "p14_breadcrumb_cn", "new_text": "商业价值 · 成本对比"},
            {"slide": 14, "slot_id": "p14_breadcrumb_en", "new_text": "Cost Comparison"},
            {"slide": 14, "slot_id": "p14_q1_title", "new_text": "数据库许可"},
            {"slide": 14, "slot_id": "p14_q1_body", "new_text": "传统：Oracle/PostgreSQL 10-50万/年\nIntelligence Web：SQLite 零许可费"},
            {"slide": 14, "slot_id": "p14_q2_title", "new_text": "运维人力"},
            {"slide": 14, "slot_id": "p14_q2_body", "new_text": "传统：专职 DBA + DevOps 30-60万/年\nIntelligence Web：容器化一键部署，无需专人"},
            {"slide": 14, "slot_id": "p14_q3_title", "new_text": "框架工具"},
            {"slide": 14, "slot_id": "p14_q3_body", "new_text": "传统：React/Angular 企业版 + BI 许可\nIntelligence Web：Vanilla JS + Flask，全部开源"},
            {"slide": 14, "slot_id": "p14_q4_title", "new_text": "部署周期"},
            {"slide": 14, "slot_id": "p14_q4_body", "new_text": "传统：数周至数月\nIntelligence Web：docker compose up，分钟级上线"},

            # ---- Slide 15: ROI 统计 ----
            {"slide": 15, "slot_id": "p15_breadcrumb_cn", "new_text": "商业价值 · ROI"},
            {"slide": 15, "slot_id": "p15_breadcrumb_en", "new_text": "Return on Investment"},
            {"slide": 15, "slot_id": "p15_pct_label", "new_text": "投资回报周期：1-3 个月"},
            {"slide": 15, "slot_id": "p15_stat1_title", "new_text": "效率提升"},
            {"slide": 15, "slot_id": "p15_stat1_body", "new_text": "信息采集 10x · 情报分析 50x\n信息检索 100x · 商机响应 10x"},
            {"slide": 15, "slot_id": "p15_stat2_title", "new_text": "收入引擎"},
            {"slide": 15, "slot_id": "p15_stat2_body", "new_text": "转化率提升 20% + 销售周期缩短 20%\n年新增收入 50-100 万\n零系统部署成本"},

            # ---- Slide 16: 结尾 ----
            {"slide": 16, "slot_id": "end_en", "new_text": "Intelligence Web"},
            {"slide": 16, "slot_id": "end_cn", "new_text": "让情报成为您的核心竞争力"},
        ],
    }


def build_edits_mckinsey() -> dict:
    """为 mckinsey-style 模板生成 edits.json（选择核心 slides）"""
    return {
        "template_slug": "mckinsey-style",
        "selected_slides": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37],
        "edits": [
            # Slide 1: 三段内容页 - 市场洞察
            {"slide": 1, "slot_id": "s1_sh4_p0r0", "new_text": "市场洞察"},
            {"slide": 1, "slot_id": "s1_sh50_p0r0", "new_text": "信息碎片化，决策靠直觉"},
            {"slide": 1, "slot_id": "s1_sh69_p0r0", "new_text": "90% 的信息被淹没、遗忘或被竞争对手捷足先登，传统方式永远慢半拍"},
            {"slide": 1, "slot_id": "s1_sh3_p0r0", "new_text": "信息孤岛"},
            {"slide": 1, "slot_id": "s1_sh12_p0r0", "new_text": "响应滞后"},
            {"slide": 1, "slot_id": "s1_sh14_p0r0", "new_text": "决策靠直觉"},
            {"slide": 1, "slot_id": "s1_sh17_p0r0", "new_text": "重复劳动"},
            {"slide": 1, "slot_id": "s1_sh70_p0r0", "new_text": "市场变化从月级缩短到天级"},
            {"slide": 1, "slot_id": "s1_sh71_p0r0", "new_text": "缺乏系统化平台把散落的线索变成可行动的洞察"},
            {"slide": 1, "slot_id": "s1_sh38_p0r0", "new_text": "人工成本"},
            {"slide": 1, "slot_id": "s1_sh40_p0r0", "new_text": "制造成本"},
            {"slide": 1, "slot_id": "s1_sh42_p0r0", "new_text": "其他成本"},
            {"slide": 1, "slot_id": "s1_sh119_p0r0", "new_text": "原材料采购"},
            {"slide": 1, "slot_id": "s1_sh120_p0r0", "new_text": "设备折旧"},
            {"slide": 1, "slot_id": "s1_sh121_p0r0", "new_text": "能源消耗"},
            {"slide": 1, "slot_id": "s1_sh122_p0r0", "new_text": "质量损耗"},
            {"slide": 1, "slot_id": "s1_sh72_p0r0", "new_text": "运输费用"},
            {"slide": 1, "slot_id": "s1_sh78_p0r0", "new_text": "仓储租金"},
            {"slide": 1, "slot_id": "s1_sh81_p0r0", "new_text": "库存损耗"},
            {"slide": 1, "slot_id": "s1_sh84_p0r0", "new_text": "保险及税费"},

            # Slide 2: 阶段对比页 - 产品定义
            {"slide": 2, "slot_id": "s2_sh62_p0r0", "new_text": "产品定义"},
            {"slide": 2, "slot_id": "s2_sh4_p0r0", "new_text": "Intelligence Web 产品路径规划"},
            {"slide": 2, "slot_id": "s2_sh24_p0r0", "new_text": "Q1 需求调研"},
            {"slide": 2, "slot_id": "s2_sh213_p0r0", "new_text": "2026.01"},
            {"slide": 2, "slot_id": "s2_sh214_p0r0", "new_text": "MVP 开发"},
            {"slide": 2, "slot_id": "s2_sh215_p0r0", "new_text": "2026.04"},
            {"slide": 2, "slot_id": "s2_sh216_p0r0", "new_text": "内测发布"},
            {"slide": 2, "slot_id": "s2_sh217_p0r0", "new_text": "2026.07"},
            {"slide": 2, "slot_id": "s2_sh218_p0r0", "new_text": "公测上线"},
            {"slide": 2, "slot_id": "s2_sh219_p0r0", "new_text": "2026.10"},
            {"slide": 2, "slot_id": "s2_sh26_p0r0", "new_text": "完成核心功能开发与种子用户测试"},
            {"slide": 2, "slot_id": "s2_sh223_p0r0", "new_text": "启动小批量生产，收集反馈"},
            {"slide": 2, "slot_id": "s2_sh224_p0r0", "new_text": "占领细分市场，拓展产品线"},
            {"slide": 2, "slot_id": "s2_sh225_p0r0", "new_text": "全量上线，规模化推广"},
            {"slide": 2, "slot_id": "s2_sh226_p0r0", "new_text": "核心功能完善，用户留存率≥60%"},
            {"slide": 2, "slot_id": "s2_sh227_p0r0", "new_text": "NPS≥40，用户满意度高"},
            {"slide": 2, "slot_id": "s2_sh229_p0r0", "new_text": "关键指标"},
            {"slide": 2, "slot_id": "s2_sh82_p0r0", "new_text": "释放 15% 人力，投入建立供应链及团队扩张"},
            {"slide": 2, "slot_id": "s2_sh83_p0r0", "new_text": "估值锚定 5000 万"},
            {"slide": 2, "slot_id": "s2_sh84_p0r0", "new_text": "投资策略"},
            {"slide": 2, "slot_id": "s2_sh87_p0r0", "new_text": "通过电商 + 线下商铺货，月销突破 5000 台"},
            {"slide": 2, "slot_id": "s2_sh88_p0r0", "new_text": "年营收 3000 万，再增长 25%"},
            {"slide": 2, "slot_id": "s2_sh63_p0r0", "new_text": "目标"},

            # Slide 3: 木桶效应页 - 技术底座
            {"slide": 3, "slot_id": "s3_sh137_p0r0", "new_text": "技术底座怎么构建？"},
            {"slide": 3, "slot_id": "s3_sh136_p0r0", "new_text": "长板怎么维持？"},
            {"slide": 3, "slot_id": "s3_sh4_p0r0", "new_text": "技术底座架构"},
            {"slide": 3, "slot_id": "s3_sh114_p0r0", "new_text": "Flask + Python"},
            {"slide": 3, "slot_id": "s3_sh117_p0r0", "new_text": "Meilisearch"},
            {"slide": 3, "slot_id": "s3_sh118_p0r0", "new_text": "MCP Server"},
            {"slide": 3, "slot_id": "s3_sh119_p0r0", "new_text": "Nginx Gateway"},
            {"slide": 3, "slot_id": "s3_sh120_p0r0", "new_text": "Research API"},
            {"slide": 3, "slot_id": "s3_sh121_p0r0", "new_text": "Sales API"},
            {"slide": 3, "slot_id": "s3_sh132_p0r0", "new_text": "2026"},
            {"slide": 3, "slot_id": "s3_sh142_p0r0", "new_text": "方法 1："},
            {"slide": 3, "slot_id": "s3_sh143_p0r0", "new_text": "持续投入研发，每年 30% 营收用于技术迭代，保持技术壁垒。"},
            {"slide": 3, "slot_id": "s3_sh150_p0r0", "new_text": "方法 2："},
            {"slide": 3, "slot_id": "s3_sh151_p0r0", "new_text": "绑定头部供应商，签订 2 年协议，确保供应链稳定性。"},
            {"slide": 3, "slot_id": "s3_sh152_p0r0", "new_text": "方法 3："},
            {"slide": 3, "slot_id": "s3_sh153_p0r0", "new_text": "建立用户社区，每月举办产品共创会，强化品牌忠诚度。"},
            {"slide": 3, "slot_id": "s3_sh154_p0r0", "new_text": "方法 4："},
            {"slide": 3, "slot_id": "s3_sh155_p0r0", "new_text": "提前布局海外专利，规避技术抄袭风险。"},
            {"slide": 3, "slot_id": "s3_sh197_p0r0", "new_text": "方法 1："},
            {"slide": 3, "slot_id": "s3_sh198_p0r0", "new_text": "引入战略出资人，以资源置换估值，缓解资金压力。"},
            {"slide": 3, "slot_id": "s3_sh202_p0r0", "new_text": "方法 2："},
            {"slide": 3, "slot_id": "s3_sh203_p0r0", "new_text": "高薪招募 2 名行业资深顾问，补齐管理短板。"},
            {"slide": 3, "slot_id": "s3_sh206_p0r0", "new_text": "方法 3："},
            {"slide": 3, "slot_id": "s3_sh210_p0r0", "new_text": "与高校联合培养管培生，低成本储备技术人才。"},
            {"slide": 3, "slot_id": "s3_sh212_p0r0", "new_text": "方法 4："},
            {"slide": 3, "slot_id": "s3_sh230_p0r0", "new_text": "推行轻资产运营，将 30% 非核心业务外包。"},
            {"slide": 3, "slot_id": "s3_sh23_p0r0", "new_text": "核心技术优势 + 市场先发优势"},
            {"slide": 3, "slot_id": "s3_sh253_p0r0", "new_text": "现金流紧张 + 团队经验不足"},

            # Slide 4-37: 更多 slides 编辑 (简化处理)
            {"slide": 4, "slot_id": "s4_sh4_p0r0", "new_text": "商业价值分析"},
            {"slide": 4, "slot_id": "s4_sh23_p0r0", "new_text": "成本对比"},
            {"slide": 4, "slot_id": "s4_sh24_p0r0", "new_text": "效率提升"},
            {"slide": 5, "slot_id": "s5_sh4_p0r0", "new_text": "风险分析与应对"},
            {"slide": 5, "slot_id": "s5_sh52_p0r0", "new_text": "风险 01：技术集成复杂度"},
            {"slide": 5, "slot_id": "s5_sh87_p0r0", "new_text": "多系统对接，需要充分的技术评估和测试"},
            {"slide": 6, "slot_id": "s6_sh86_p0r0", "new_text": "半年工作总结与计划"},
            {"slide": 6, "slot_id": "s6_sh2_p0r0", "new_text": "业绩达成"},
            {"slide": 6, "slot_id": "s6_sh3_p0r0", "new_text": "上半年工作总结"},
            {"slide": 37, "slot_id": "s37_sh11_p0r0", "new_text": "Thank You"},
            {"slide": 37, "slot_id": "s37_sh13_p0r0", "new_text": "感谢聆听"},
        ],
    }


# ============================================================
# 主函数
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Intelligence Web PPT 生成器")
    parser.add_argument("--template", choices=["minimal", "mckinsey"], default="mckinsey",
                        help="选择模板（默认 mckinsey）")
    parser.add_argument("--preview", action="store_true",
                        help="生成后渲染预览图")
    parser.add_argument("--output", default=None,
                        help="自定义输出文件名")
    args = parser.parse_args()

    template_slug = TEMPLATES[args.template]
    template_dir = TEMPLATES_DIR / template_slug
    template_pptx = template_dir / "template.pptx"
    detail_json = template_dir / "detail.json"

    # 检查模板文件
    if not template_pptx.exists():
        print(f"错误：模板文件不存在 {template_pptx}")
        print(f"请确保已下载模板到 third_party/GordenPPTSkill/templates/{template_slug}/")
        sys.exit(1)

    if not BUILD_SCRIPT.exists():
        print(f"错误：build_pptx.py 不存在 {BUILD_SCRIPT}")
        sys.exit(1)

    # 生成 edits.json（根据模板选择不同内容）
    print(f"📐 使用模板：{template_slug}")
    if args.template == "mckinsey":
        edits = build_edits_mckinsey()
    else:
        edits = build_edits_minimal()

    # 保存 edits.json 到临时位置
    edits_file = PROJECT_ROOT / "docs" / "_current_edits.json"
    edits_file.write_text(json.dumps(edits, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📝 edits.json 已生成：{edits_file}")

    # 输出文件
    if args.output:
        output_pptx = PROJECT_ROOT / "docs" / args.output
    else:
        output_pptx = PROJECT_ROOT / "docs" / f"{PRODUCT_NAME}_产品宣发_{template_slug}.pptx"

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 构建命令
    cmd = [
        sys.executable, str(BUILD_SCRIPT),
        str(template_pptx),
        str(edits_file),
        str(output_pptx),
        "--detail", str(detail_json),
    ]

    print(f"🔨 正在构建 PPT...")
    print(f"   命令: {' '.join(cmd)}")

    import subprocess
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(THIRD_PARTY))

    if result.returncode != 0:
        print(f"❌ 构建失败:")
        print(result.stderr)
        sys.exit(1)

    print(f"✅ PPT 已生成：{output_pptx}")
    print(f"   文件大小：{output_pptx.stat().st_size / 1024:.1f} KB")
    print(result.stdout)

    # 可选：渲染预览
    if args.preview and RENDER_SCRIPT.exists():
        print(f"\n🖼️  正在渲染预览图...")
        preview_dir = PROJECT_ROOT / "docs" / "ppt_preview"
        preview_dir.mkdir(parents=True, exist_ok=True)

        render_cmd = [
            sys.executable, str(RENDER_SCRIPT),
            str(output_pptx),
            str(preview_dir),
            "--dpi", "144",
        ]
        render_result = subprocess.run(render_cmd, capture_output=True, text=True, cwd=str(THIRD_PARTY))
        if render_result.returncode == 0:
            print(f"✅ 预览图已保存到：{preview_dir}")
            # 列出预览文件
            png_files = sorted(preview_dir.glob("*.png"))
            for pf in png_files[:5]:
                print(f"   {pf.name} ({pf.stat().st_size / 1024:.0f} KB)")
            if len(png_files) > 5:
                print(f"   ... 共 {len(png_files)} 页")
        else:
            print(f"⚠️  预览图渲染失败（可能需要 LibreOffice）: {render_result.stderr}")

    # 清理临时 edits
    # edits_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()