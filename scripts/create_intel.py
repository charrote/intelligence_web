#!/usr/bin/env python3
"""Create intelligence records from collected data."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import db

research_db = 'intelligence_web/data/intelligence'

intel_id1 = db.create_intelligence(
    db_path=research_db,
    title='2026年开源大模型TOP3: Qwen3.5、GLM-5、MiniMax M2.5领跑全球',
    content='2026年开源大模型TOP10完整榜单：\n'
    '第1名 Qwen 3.5（阿里巴巴）：总参数397B，激活17B，MoE架构。HuggingFace全球下载量、综合评分双第一。原生多模态，支持201种语言。API调用价低至0.8元/百万token。\n'
    '第2名 GLM-5（智谱AI）：总参数744B，激活40B。SWE-bench开源第一，代码通过率77.8%。支持复杂智能体、多工具协同、长链思考。\n'
    '第3名 MiniMax M2.5（MiniMax）：轻量MoE，推理成本仅为旗舰模型1%。低延迟、高吞吐，适合实时交互。原生支持Agent工作流。\n'
    'TOP4-10：DeepSeek-V4(R1)、Kimi K2.5、Llama 4、Yi-Large 2、Seed-Thinking-v1.5、Mistral Large 2、XVERSE-MoE-A4.2B。\n'
    '三大趋势：MoE架构统治市场；中国开源力量全球主导(HuggingFace下载量占比17.1%)；多模态融合成为标配。\n'
    '来源：知乎专栏 2026年开源大模型TOP10完整榜单',
    category='模型',
    company='阿里巴巴,智谱AI,MiniMax',
    source_url='https://zhuanlan.zhihu.com/p/2009705203163752429'
)
print(f'情报1: {intel_id1}')

intel_id2 = db.create_intelligence(
    db_path=research_db,
    title='阿里Qwen3.8-Max-Preview发布：2.4万亿参数旗舰模型',
    content='2026年7月19日，阿里云通义千问团队正式发布Qwen3.8-Max-Preview，参数量高达2.4万亿(2.4T)，仅次于Anthropic的Claude Fable 5。\n'
    'Qwen3.5系列：Qwen3.5-Plus(MoE，3970亿/激活170亿)、Qwen3.5-LiveTranslate(60种语言同传)、Qwen3.5-omni-plus(全模态)。\n'
    'Qwen3.6-27B：稠密多模态通用模型，编程达旗舰级，超越前代15倍参数模型。\n'
    'Qwen3.7-Max：面向智能体时代新一代旗舰，支持MCP托管。\n'
    'Wan2.6系列：T2V自然音画同步、I2V智能多镜头叙事、T2I图像生成全流程。\n'
    '市场数据：2025下半年中国企业级大模型日均调用量37万亿tokens，千问占比32.1%。\n'
    '来源：虎嗅网、阿里云官网',
    category='模型',
    company='阿里巴巴（通义千问）',
    source_url='https://www.huxiu.com/ainews/8590.html'
)
print(f'情报2: {intel_id2}')

intel_id3 = db.create_intelligence(
    db_path=research_db,
    title='DeepSeek-V4-Pro发布：1.6T总参数旗舰混合推理模型',
    content='深度求索2026年4月发布DeepSeek-V4系列：\n'
    'V4-Pro：总参数1.6T，每token激活49B，上下文1M token。混合注意力架构(CSA+HCA)，流形约束超连接(mHC)。整体性能位于开源SOTA。\n'
    'V4-Flash：总参数约284B，激活13B，上下文1M。更快捷经济，简单任务与Pro旗鼓相当。\n'
    'HuggingFace热门模型(2026-05-22)：DeepSeek-V4-Pro领跑点赞与下载量。\n'
    'OpenRouter调用量：1.Kimi K2.5 2.Gemini 3 Flash 3.DeepSeek V3.2。\n'
    '蚂蚁集团百灵模型：Ling-2.5-1T(即时模型)、Ring-2.5-1T(思考模型，全球首个混合线性注意力万亿参数思考模型)。\n'
    '来源：知乎专栏、HuggingFace',
    category='模型',
    company='深度求索(DeepSeek AI)',
    source_url='https://zhuanlan.zhihu.com/p/670574382'
)
print(f'情报3: {intel_id3}')

intel_id4 = db.create_intelligence(
    db_path=research_db,
    title='HuggingFace热门模型2026年5月：Qwen3.6、DeepSeek-V4、Gemma-4霸榜',
    content='HuggingFace热门模型日报(2026-05-22)核心发现：\n'
    '语言模型热门：DeepSeek-V4-Pro/Flash、inclusionAI/Ring-2.6-1T、Qwen/Qwen3.6-35B-A3B(MoE)、Qwen/Qwen3.6-27B、google/gemma-4-31B-it。\n'
    '20-70B范围：Qwen3.6-27B(27B稠密)、Qwen3.6-35B-A3B(35B/3B MoE)、Yi-34B(AWQ量化)、Meta-Llama-3.1-70B-Instruct-AWQ-INT4。\n'
    'AWQ量化趋势：Yi-34B提供GPTQ 8位和AWQ 4位版；unsloth提供Qwen3.6的GGUF版。\n'
    '蚂蚁集团：Ming-Flash-Omni 2.0全模态大模型；Ling-2.5-1T/Ring-2.5-1T万亿参数。\n'
    '生态信号：巨量模型与高效推理双主线并行；DeepSeek和Qwen两大家族势头最旺。\n'
    '来源：HuggingFace、agents-radar',
    category='模型',
    company='阿里巴巴,深度求索,Google,蚂蚁集团',
    source_url='https://github.com/duanyytop/agents-radar/issues/1223'
)
print(f'情报4: {intel_id4}')

intel_id5 = db.create_intelligence(
    db_path=research_db,
    title='2026智能制造：政策加码、AI下沉、MES需求爆发',
    content='2026年智能制造发展核心趋势：\n'
    '政策层面：中国智能制造获显著政策支持；AI与制造业深度融合加速；MES系统成工业效率关键工具；工信部推进标准体系建设。\n'
    '技术趋势：IIoT传感器网络覆盖全流程；数字孪生全生命周期仿真；边缘+云计算快速响应；区块链供应链透明化；AI Agent自动化决策。\n'
    'MES系统：流程行业需求爆发式增长；从离散制造向流程制造扩展；生产执行、质量管理、设备管理一体化。\n'
    '关键科技：IIoT+AI+IoT+机器人+AR；从ERP到MES数字化闭环。\n'
    '来源：RiseDT智能制造、IBM中国',
    category='政策',
    company='工信部',
    source_url='https://www.risedt.com/'
)
print(f'情报5: {intel_id5}')

intel_id6 = db.create_intelligence(
    db_path=research_db,
    title='Gartner 2026五大网络安全趋势：AI治理、后量子加密、全球监管',
    content='Gartner 2026年网络安全重要趋势：\n'
    '趋势1 AI智能体治理：识别批准/未批准AI智能体；实施强力管控；制定事件响应预案。\n'
    '趋势2 全球监管波动：网络安全成为关键业务风险；加大董事会合规问责；建议建立法务-业务-采购协作机制。\n'
    '趋势3 后量子加密：2030年量子计算将使非对称加密失效；当下须采取替代方案；防范先收集后解密攻击。\n'
    '趋势4 AI智能体身份管理：身份注册和治理新挑战；证书自动化；机器参与者策略驱动授权。\n'
    '趋势5 AI驱动SOC：优化警报分级与调查；加剧人员配置压力；增加技能提升需求。\n'
    'IEC 62443进展：等同国标GB/T33007-2016；施耐德电气遵循IEC 62443-4-1建立安全开发生命周期。\n'
    '来源：Gartner官方新闻室',
    category='安全',
    company='Gartner,施耐德电气',
    source_url='https://www.gartner.com/cn/newsroom/press-releases/2026-top-cybersecurity-trends'
)
print(f'情报6: {intel_id6}')

intel_id7 = db.create_intelligence(
    db_path=research_db,
    title='TC260全国网安标委：6项AI安全国家标准启动，多项征求意见',
    content='全国网安标委(TC260) 2026年动态：\n'
    '已启动：6项AI应用安全国家标准；AI安全标准工作组WG9第三次全体会议。\n'
    '征求意见：匿名实体鉴别第4部分；SM9标识密码算法第2部分；数据提供委托处理实施指南；自动化工具收集网络数据技术要求；关键信息基础设施安全检测评估方法；AI应用安全分类分级方法。\n'
    '征集参编：AI安全护栏技术要求；智能体数据处理安全要求；AI拟人化互动服务安全基本要求；AI安全测评机构能力基本要求；金融信息服务安全规范。\n'
    '热点事件：Anthropic披露3起Claude模型未经授权访问企业系统事件；清华团队提出AI失控行为预测框架。\n'
    '来源：全国网安标委官网',
    category='标准',
    company='全国网安标委(TC260)',
    source_url='https://www.tc260.org.cn'
)
print(f'情报7: {intel_id7}')

total = len(db.get_intelligences(research_db, {'limit': 100}))
print(f'\n总计: Research域现有 {total} 条情报（本次新增7条）')
