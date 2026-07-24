---
title: Intelligence Web
subtitle: 企业情报智能管理平台
info: |
  从情报采集到行动闭环，让每一个决策都有据可依
theme: default
class: text-center
highlighter: shiki
lineNumbers: false
colorScheme: light
drawings:
  enabled: false
slideNumber: true
asideLayout: default
---

<style>
:root {
  --font-cn: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", "Heiti SC", sans-serif;
  --font-en: "Helvetica Neue", Arial, sans-serif;
}
body, .slide-content, h1, h2, h3, h4, h5, h6, p, span, div, a, li, td, th, label, input, button {
  font-family: var(--font-cn) !important;
}
.slide-content {
  font-size: 14px !important;
  line-height: 1.5 !important;
  max-height: 100vh !important;
  overflow: hidden !important;
}
.slide-content > div, .slide-content > section {
  max-height: 90vh !important;
  overflow: hidden !important;
}
code, pre, .shiki {
  font-family: var(--font-en) !important;
}
/* 紧凑布局 */
.compact-grid {
  gap: 0.5rem !important;
}
.compact-card {
  padding: 0.5rem 0.75rem !important;
  margin-bottom: 0.25rem !important;
}
</style>

<!-- SVG 图标定义 -->
<svg style="display:none" xmlns="http://www.w3.org/2000/svg">
  <symbol id="icon-globe" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><ellipse cx="12" cy="12" rx="4" ry="10" fill="none" stroke="currentColor" stroke-width="2"/><line x1="2" y1="12" x2="22" y2="12" stroke="currentColor" stroke-width="2"/></symbol>
  <symbol id="icon-robot" viewBox="0 0 24 24"><rect x="4" y="8" width="16" height="12" rx="2" fill="currentColor"/><circle cx="9" cy="13" r="1.5" fill="white"/><circle cx="15" cy="13" r="1.5" fill="white"/><rect x="10" y="4" width="4" height="4" rx="1" fill="currentColor"/><line x1="12" y1="2" x2="12" y2="4" stroke="currentColor" stroke-width="2"/></symbol>
  <symbol id="icon-chart" viewBox="0 0 24 24"><rect x="3" y="12" width="4" height="9" rx="1" fill="currentColor"/><rect x="10" y="6" width="4" height="15" rx="1" fill="currentColor"/><rect x="17" y="3" width="4" height="18" rx="1" fill="currentColor"/></symbol>
  <symbol id="icon-rocket" viewBox="0 0 24 24"><path d="M12 2L8 8l-2 6 6 4 6-4-2-6z" fill="currentColor"/><circle cx="12" cy="10" r="2" fill="white"/></symbol>
  <symbol id="icon-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><line x1="16" y1="16" x2="21" y2="21" stroke="currentColor" stroke-width="2"/></symbol>
  <symbol id="icon-brain" viewBox="0 0 24 24"><path d="M12 2a7 7 0 0 0-7 7c0 2.5 1.5 5 3.5 6.5L9 22h6l2.5-6.5C18.5 14 20 11.5 20 9a7 7 0 0 0-8-7z" fill="none" stroke="currentColor" stroke-width="2"/></symbol>
  <symbol id="icon-target" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="5" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></symbol>
  <symbol id="icon-gear" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" fill="currentColor"/><path d="M12 2v4m0 12v4m10-10h-4M6 12H2m15.1-7.1l-2.8 2.8M9.7 14.3l-2.8 2.8m12.2 0l-2.8-2.8M9.7 9.7L6.9 6.9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></symbol>
  <symbol id="icon-link" viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" fill="none" stroke="currentColor" stroke-width="2"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" fill="none" stroke="currentColor" stroke-width="2"/></symbol>
  <symbol id="icon-doc" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="none" stroke="currentColor" stroke-width="2"/><polyline points="14,2 14,8 20,8" fill="none" stroke="currentColor" stroke-width="2"/></symbol>
  <symbol id="icon-bank" viewBox="0 0 24 24"><rect x="2" y="6" width="20" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><polyline points="2,10 12,4 22,10" fill="none" stroke="currentColor" stroke-width="2"/><rect x="6" y="12" width="3" height="3" fill="currentColor"/><rect x="11" y="12" width="3" height="3" fill="currentColor"/><rect x="16" y="12" width="3" height="3" fill="currentColor"/></symbol>
  <symbol id="icon-people" viewBox="0 0 24 24"><circle cx="12" cy="7" r="4" fill="none" stroke="currentColor" stroke-width="2"/><path d="M5.5 21a6.5 6.5 0 0 1 13 0" fill="none" stroke="currentColor" stroke-width="2"/></symbol>
  <symbol id="icon-ok" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="icon-cross" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></symbol>
  <symbol id="icon-arrow" viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><polyline points="12,5 19,12 12,19" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="icon-check" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></symbol>
</svg>

# Intelligence Web

## 企业情报智能管理平台

<div class="pt-6">
  <span class="text-base opacity-50">从情报采集到行动闭环</span><br/>
  <span class="text-base opacity-50">让每一个决策都有据可依</span>
</div>

<div class="grid grid-cols-3 gap-3 pt-4 text-xs">
  <div class="px-3 py-1.5 bg-blue-100 rounded-full">
    <span class="font-bold text-blue-700">开源免费</span>
  </div>
  <div class="px-3 py-1.5 bg-green-100 rounded-full">
    <span class="font-bold text-green-700">AI 驱动</span>
  </div>
  <div class="px-3 py-1.5 bg-purple-100 rounded-full">
    <span class="font-bold text-purple-700">容器化部署</span>
  </div>
</div>

<div class="abs-br m-4 flex gap-2">
  <span class="text-xs opacity-50">Intelligence Web · 产品宣发</span>
</div>

---

# 我们正处在一个<br/>信息就是竞争力的时代

<div class="grid grid-cols-2 gap-6 pt-4">
<div>
<div class="text-red-500 font-bold text-sm mb-2">关键数据</div>
<div class="text-5xl font-bold text-red-600">90%</div>
<div class="text-gray-500 mt-1">信息被淹没或遗忘</div>
</div>
<div class="space-y-2 text-sm">
<p class="text-gray-700 leading-relaxed">
  全球商业环境变化速度加快，竞争对手的动作从<strong>"月级"</strong>缩短到<strong>"天级"</strong>
</p>
<p class="text-gray-700 leading-relaxed">
  企业每年在信息采集上投入大量人力，但 <strong>90%</strong> 的信息被淹没、遗忘或被竞争对手捷足先登
</p>
<p class="text-gray-700 leading-relaxed">
  传统的信息搜集方式：碎片化、被动式、依赖个人经验
</p>
<p class="text-gray-700 leading-relaxed">
  市场空白：缺乏一套系统化的平台，把"散落的线索"变成"可行动的洞察"
</p>
</div>
</div>

---

# 企业情报管理的三大顽疾

<div class="grid grid-cols-3 gap-4 pt-4">
<div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-red-500">
  <div class="text-3xl font-bold text-red-500 mb-2">01</div>
  <div class="text-lg font-bold mb-2">信息孤岛</div>
  <div class="text-gray-600 text-sm mb-3">各部门各管一套<br/>重要情报反复丢失</div>
  <div class="text-red-500 font-semibold text-xs">错失机会 · 重复劳动</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-pink-500">
  <div class="text-3xl font-bold text-pink-500 mb-2">02</div>
  <div class="text-lg font-bold mb-2">被动应对</div>
  <div class="text-gray-600 text-sm mb-3">竞争对手出手后才<br/>反应过来</div>
  <div class="text-pink-500 font-semibold text-xs">永远慢半拍</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-purple-500">
  <div class="text-3xl font-bold text-purple-500 mb-2">03</div>
  <div class="text-lg font-bold mb-2">决策靠直觉</div>
  <div class="text-gray-600 text-sm mb-3">管理层拍板靠经验和<br/>感觉</div>
  <div class="text-purple-500 font-semibold text-xs">高风险 · 事后才知</div>
</div>
</div>

---

# Intelligence Web 是什么？

<div class="bg-blue-50 rounded-lg p-5 mb-5 border-l-4 border-blue-600">
  <div class="text-xl font-bold">情报采集 → 结构化存储 → AI 分析 → 行动闭环</div>
  <div class="text-base text-blue-700 mt-1">一体化平台</div>
</div>

<div class="grid grid-cols-3 gap-4">
<div class="bg-white rounded-lg shadow-sm p-4">
  <div class="text-blue-600 font-bold text-sm mb-2">[搜索] 系统追踪</div>
  <div class="text-gray-700 text-sm">行业动态、竞争对手动向、客户需求变化和潜在商业机会</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-4">
  <div class="text-green-600 font-bold text-sm mb-2">[大脑] 不再依赖</div>
  <div class="text-gray-700 text-sm">碎片化信息搜集和个人经验判断</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-4">
  <div class="text-purple-600 font-bold text-sm mb-2">[图表] 数据驱动</div>
  <div class="text-gray-700 text-sm">让每一个决策都有据可依，而非直觉</div>
</div>
</div>

<div class="flex items-center justify-center gap-3 mt-6 text-sm">
  <div class="bg-blue-600 text-white px-3 py-1.5 rounded-md font-bold">[采集]</div>
  <span class="text-gray-400">→</span>
  <div class="bg-blue-500 text-white px-3 py-1.5 rounded-md font-bold">[存储]</div>
  <span class="text-gray-400">→</span>
  <div class="bg-blue-400 text-white px-3 py-1.5 rounded-md font-bold">[分析]</div>
  <span class="text-gray-400">→</span>
  <div class="bg-blue-300 text-white px-3 py-1.5 rounded-md font-bold">[行动]</div>
</div>

---

# 五大能力，覆盖情报管理全链路

<div class="grid grid-cols-5 gap-3 pt-4 text-xs">
<div class="bg-white rounded-lg shadow-sm p-3 text-center">
  <div class="text-purple-500 font-bold text-base mb-1">[AI]</div>
  <div class="font-bold text-gray-800 mb-1">AI 智能分析</div>
  <div class="text-gray-600">自动阅读、摘要、分析、留批注</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-3 text-center">
  <div class="text-blue-500 font-bold text-base mb-1">[搜索]</div>
  <div class="font-bold text-gray-800 mb-1">多渠道采集</div>
  <div class="text-gray-600">网站抓取、API 对接，灵活设定频率</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-3 text-center">
  <div class="text-cyan-500 font-bold text-base mb-1">[图表]</div>
  <div class="font-bold text-gray-800 mb-1">数据看板</div>
  <div class="text-gray-600">Meilisearch 毫秒级全文搜索</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-3 text-center">
  <div class="text-green-500 font-bold text-base mb-1">[目标]</div>
  <div class="font-bold text-gray-800 mb-1">商机管理</div>
  <div class="text-gray-600">线索到成交的全生命周期追踪</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-3 text-center">
  <div class="text-amber-500 font-bold text-base mb-1">[齿轮]</div>
  <div class="font-bold text-gray-800 mb-1">系统管控</div>
  <div class="text-gray-600">RBAC 四级权限、审计日志</div>
</div>
</div>

---

# 制造情报域 — "看见趋势"

<div class="grid grid-cols-2 gap-6 pt-4">
<div>
<div class="text-green-600 font-bold text-sm mb-3">核心数据流</div>
<div class="space-y-2">
<div class="bg-white rounded-lg shadow-sm p-3 border-l-4 border-green-500">
  <div class="text-sm text-gray-700">竞品发布新产品 → <strong>AI 5 分钟内捕获、摘要、推送预警</strong></div>
</div>
<div class="bg-white rounded-lg shadow-sm p-3 border-l-4 border-green-500">
  <div class="text-sm text-gray-700">国家发布智能制造补贴政策 → <strong>自动抓取、分析、标记关联度</strong></div>
</div>
<div class="bg-white rounded-lg shadow-sm p-3 border-l-4 border-green-500">
  <div class="text-sm text-gray-700">行业论坛讨论下一代工艺 → <strong>实时追踪、归类、形成趋势报告</strong></div>
</div>
</div>
</div>
<div>
<div class="text-green-600 font-bold text-sm mb-3">价值体现</div>
<div class="space-y-2">
<div class="bg-green-50 rounded-lg p-3">
  <div class="text-sm text-gray-700">[ok] 实时监控竞品产品线调整和产能扩张计划</div>
</div>
<div class="bg-green-50 rounded-lg p-3">
  <div class="text-sm text-gray-700">[ok] 预判下一代制造技术的商业化时间表</div>
</div>
<div class="bg-green-50 rounded-lg p-3">
  <div class="text-sm text-gray-700">[ok] 从"事后追悔"到"事前预判"</div>
</div>
</div>
</div>
</div>

<div class="bg-green-50 rounded-lg p-4 mt-5 text-center">
  <div class="text-lg font-bold text-green-600">看见趋势 · 看见未来 · 看见机会</div>
</div>

---

# 销售情报域 — "抓住机会"

<div class="grid grid-cols-3 gap-4 pt-4">
<div class="bg-white rounded-lg shadow-sm p-4">
  <div class="text-blue-500 font-bold text-sm mb-1">[目标] 客户扩产预警</div>
  <div class="text-gray-700 text-sm">客户宣布扩产 → 第一时间触发跟进流程</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-4">
  <div class="text-amber-500 font-bold text-sm mb-1">[工厂] 竞对投资信号</div>
  <div class="text-gray-700 text-sm">竞争对手新建工厂前就被捕捉到投资信号</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-4">
  <div class="text-green-500 font-bold text-sm mb-1">[趋势] 商机漏斗可视化</div>
  <div class="text-gray-700 text-sm">销售主管通过数据看板掌握团队商机漏斗健康度</div>
</div>
</div>

<div class="mt-5">
<div class="text-gray-500 font-bold text-xs mb-3">商机全生命周期</div>
<div class="flex items-center gap-1">
  <div class="bg-gray-300 text-gray-700 px-3 py-1.5 rounded-md font-bold text-xs">待核实</div>
  <span class="text-gray-400">→</span>
  <div class="bg-blue-500 text-white px-3 py-1.5 rounded-md font-bold text-xs">合格商机</div>
  <span class="text-gray-400">→</span>
  <div class="bg-cyan-500 text-white px-3 py-1.5 rounded-md font-bold text-xs">方案报价</div>
  <span class="text-gray-400">→</span>
  <div class="bg-green-500 text-white px-3 py-1.5 rounded-md font-bold text-xs">商务谈判</div>
  <span class="text-gray-400">→</span>
  <div class="bg-amber-500 text-white px-3 py-1.5 rounded-md font-bold text-xs">成交/丢标</div>
</div>
</div>

---

# "共享内核 + 任意域扩展"

<div class="bg-purple-50 rounded-lg p-4 mb-5 border-l-4 border-purple-600">
  <div class="text-sm">平台不设固定的业务边界，客户需要什么领域，就搭建什么领域</div>
</div>

<div class="grid grid-cols-2 gap-6">
<div>
<div class="text-green-600 font-bold text-sm mb-3">已验证领域</div>
<div class="bg-white rounded-lg shadow-sm p-4">
  <div class="text-gray-800 mb-1">[ok] <strong>制造情报</strong> — "看见趋势"</div>
  <div class="text-gray-800">[ok] <strong>销售情报</strong> — "抓住机会"</div>
</div>
</div>
<div>
<div class="text-blue-600 font-bold text-sm mb-3">可快速扩展领域</div>
<div class="space-y-2">
<div class="text-gray-700 text-sm">[link] <strong>供应链管理</strong> — 寻源、评估、批准、监控</div>
<div class="text-gray-700 text-sm">[doc] <strong>知识产权监控</strong> — 专利追踪、侵权预警</div>
<div class="text-gray-700 text-sm">[bank] <strong>金融市场追踪</strong> — 投融资动态、并购重组</div>
<div class="text-gray-700 text-sm">[people] <strong>人力资源情报</strong> — 竞对人事变动、人才流动</div>
</div>
</div>
</div>

<div class="bg-green-50 rounded-lg p-4 mt-5 text-center">
  <div class="text-base font-bold text-green-700">一份配置文件 + 一个前端模板 → 数天内上线新域</div>
</div>

---

# 为 IT 负责人准备的架构透明度

<div class="bg-white rounded-lg shadow-sm p-4 mb-5 overflow-x-auto">
<table class="w-full text-xs">
  <thead>
    <tr class="bg-cyan-600 text-white">
      <th class="p-2 text-left">服务</th>
      <th class="p-2 text-left">端口</th>
      <th class="p-2 text-left">技术栈</th>
      <th class="p-2 text-left">角色</th>
    </tr>
  </thead>
  <tbody>
    <tr class="border-b"><td class="p-2 font-bold">Research API</td><td class="p-2">8766</td><td class="p-2">Flask + Python 3.11</td><td class="p-2">制造情报业务引擎</td></tr>
    <tr class="border-b bg-gray-50"><td class="p-2 font-bold">Sales API</td><td class="p-2">8767</td><td class="p-2">Gunicorn + Python 3.11</td><td class="p-2">销售情报业务引擎</td></tr>
    <tr class="border-b"><td class="p-2 font-bold">Gateway</td><td class="p-2">8765</td><td class="p-2">Nginx Alpine</td><td class="p-2">反向代理 + JWT 鉴权</td></tr>
    <tr class="border-b bg-gray-50"><td class="p-2 font-bold">Meilisearch</td><td class="p-2">7700</td><td class="p-2">Meilisearch v1.12</td><td class="p-2">全文检索引擎</td></tr>
  </tbody>
</table>
</div>

<div class="grid grid-cols-2 gap-4 text-xs">
<div class="space-y-2">
<div class="text-cyan-600 font-bold text-sm">关键架构原则</div>
<div class="bg-white rounded-lg shadow-sm p-3">[共享] <strong>共享内核</strong> — 所有业务域通过 Docker Volume 挂载同一 core/ 目录</div>
<div class="bg-white rounded-lg shadow-sm p-3">[分离] <strong>分离领域</strong> — 各域数据完全隔离，通过 SQLite 独立文件实现</div>
</div>
<div class="space-y-2">
<div class="bg-white rounded-lg shadow-sm p-3">[接口] <strong>MCP Server</strong> — 18 个工具方法，AI Agent 通过标准化协议直接访问数据</div>
<div class="bg-white rounded-lg shadow-sm p-3">[轻量] <strong>零外部数据库依赖</strong> — 除 Meilisearch 外无需任何额外服务</div>
</div>
</div>

---

# "轻"而不"薄"的技术底座

<div class="bg-white rounded-lg shadow-sm p-4 overflow-x-auto">
<table class="w-full text-xs">
  <thead>
    <tr class="bg-green-600 text-white">
      <th class="p-2 text-left">维度</th>
      <th class="p-2 text-left">传统方案</th>
      <th class="p-2 text-left">Intelligence Web</th>
    </tr>
  </thead>
  <tbody>
    <tr class="border-b"><td class="p-2 font-bold">数据库</td><td class="p-2">Oracle/PostgreSQL<br/>年费 10-50 万</td><td class="p-2 text-green-600 font-bold">SQLite 单文件<br/>零许可费</td></tr>
    <tr class="border-b bg-gray-50"><td class="p-2 font-bold">运维</td><td class="p-2">专职 DBA + DevOps<br/>年成本 30-60 万</td><td class="p-2 text-green-600 font-bold">容器化一键部署<br/>无需专人运维</td></tr>
    <tr class="border-b"><td class="p-2 font-bold">框架</td><td class="p-2">React/Angular 企业版<br/>BI 工具许可</td><td class="p-2 text-green-600 font-bold">Vanilla JS + Flask<br/>全部开源免费</td></tr>
    <tr class="border-b bg-gray-50"><td class="p-2 font-bold">部署周期</td><td class="p-2">数周至数月</td><td class="p-2 text-green-600 font-bold">docker compose up<br/>分钟级上线</td></tr>
    <tr><td class="p-2 font-bold">扩展性</td><td class="p-2">改代码、重新部署测试</td><td class="p-2 text-green-600 font-bold">配置文件 + 前端模板<br/>数天上线新域</td></tr>
  </tbody>
</table>
</div>

<div class="bg-green-50 rounded-lg p-4 mt-4 text-center">
  <div class="text-base font-bold text-green-700">你不需要再养一个团队来维护这套系统</div>
</div>

---

# 不是工具，是协作伙伴

<div class="grid grid-cols-5 gap-2 pt-4 text-xs">
<div class="bg-white rounded-lg shadow-sm p-3 text-center">
  <div class="bg-blue-500 text-white px-2 py-0.5 rounded-full text-[10px] font-bold mb-1">[AI]</div>
  <div class="text-gray-700">AI Agent<br/>每日自动巡检</div>
</div>
<div class="flex items-center justify-center"><span class="text-lg">→</span></div>
<div class="bg-white rounded-lg shadow-sm p-3 text-center">
  <div class="bg-cyan-500 text-white px-2 py-0.5 rounded-full text-[10px] font-bold mb-1">[分析]</div>
  <div class="text-gray-700">AI 对采集内容<br/>初步分析</div>
</div>
<div class="flex items-center justify-center"><span class="text-lg">→</span></div>
<div class="bg-white rounded-lg shadow-sm p-3 text-center">
  <div class="bg-purple-500 text-white px-2 py-0.5 rounded-full text-[10px] font-bold mb-1">[建议]</div>
  <div class="text-gray-700">AI 留下<br/>观察和建议</div>
</div>
<div class="flex items-center justify-center"><span class="text-lg">→</span></div>
<div class="bg-white rounded-lg shadow-sm p-3 text-center">
  <div class="bg-green-500 text-white px-2 py-0.5 rounded-full text-[10px] font-bold mb-1">[决策]</div>
  <div class="text-gray-700">人类做出<br/>最终判断</div>
</div>
<div class="flex items-center justify-center"><span class="text-lg">→</span></div>
<div class="bg-white rounded-lg shadow-sm p-3 text-center">
  <div class="bg-amber-500 text-white px-2 py-0.5 rounded-full text-[10px] font-bold mb-1">[反馈]</div>
  <div class="text-gray-700">人类反馈<br/>反哺 AI</div>
</div>
</div>

<div class="bg-purple-50 rounded-lg p-4 mt-5">
<div class="space-y-2 text-gray-700 text-sm">
  <p>这不是一个"录入工具"，是让人类和 AI Agent 共同工作的平台</p>
  <p>每一次人工反馈都在训练 AI，形成正向飞轮</p>
  <p>18 个 MCP 工具方法，支持 Claude / Hermes / OpenClaw 等多 Agent 接入</p>
</div>
</div>

---

# 企业级安全，从第一天就内置

<div class="bg-white rounded-lg shadow-sm p-4 overflow-x-auto">
<table class="w-full text-xs">
  <thead>
    <tr class="bg-green-600 text-white">
      <th class="p-2 text-left">安全维度</th>
      <th class="p-2 text-left">实现方式</th>
    </tr>
  </thead>
  <tbody>
    <tr class="border-b"><td class="p-2 font-bold">认证</td><td class="p-2">JWT Bearer Token（HS256），密码 SHA-256 + 随机盐存储</td></tr>
    <tr class="border-b bg-gray-50"><td class="p-2 font-bold">密钥保护</td><td class="p-2">API Key / Agent Key 落地 XOR 混淆，API 响应中脱敏</td></tr>
    <tr class="border-b"><td class="p-2 font-bold">CORS</td><td class="p-2">环境变量严格白名单控制允许来源域名</td></tr>
    <tr class="border-b bg-gray-50"><td class="p-2 font-bold">RBAC 权限</td><td class="p-2">Admin / Manager / Analyst / Viewer 四级角色，精细到菜单级</td></tr>
    <tr><td class="p-2 font-bold">审计日志</td><td class="p-2">所有变更操作记录操作人身份和时间戳，满足合规追溯</td></tr>
  </tbody>
</table>
</div>

<div class="bg-green-50 rounded-lg p-4 mt-4 text-center">
  <div class="text-sm font-semibold text-green-700">每一个操作都被记录 · 每一个密钥都被保护 · 每一次访问都有据可查</div>
</div>

---

# 每一分钱，都能算得清楚

<div class="grid grid-cols-4 gap-4 pt-6">
<div class="text-center">
  <div class="text-4xl font-bold text-green-600">10x</div>
  <div class="text-gray-500 mt-1">信息采集</div>
</div>
<div class="text-center">
  <div class="text-4xl font-bold text-green-600">50x</div>
  <div class="text-gray-500 mt-1">情报分析</div>
</div>
<div class="text-center">
  <div class="text-4xl font-bold text-green-600">100x</div>
  <div class="text-gray-500 mt-1">信息检索</div>
</div>
<div class="text-center">
  <div class="text-4xl font-bold text-green-600">10x</div>
  <div class="text-gray-500 mt-1">商机响应</div>
</div>
</div>

<div class="bg-white rounded-lg shadow-sm p-4 mt-6 overflow-x-auto">
<table class="w-full text-xs">
  <thead>
    <tr class="bg-green-600 text-white">
      <th class="p-2 text-left">项目</th>
      <th class="p-2 text-left">传统方案</th>
      <th class="p-2 text-left">Intelligence Web</th>
      <th class="p-2 text-left">节省</th>
    </tr>
  </thead>
  <tbody>
    <tr class="border-b"><td class="p-2 font-bold">数据库许可</td><td class="p-2">10-50 万/年</td><td class="p-2 text-green-600 font-bold">0 元</td><td class="p-2 text-green-600">100%</td></tr>
    <tr class="border-b bg-gray-50"><td class="p-2 font-bold">运维人力</td><td class="p-2">30-60 万/年</td><td class="p-2 text-green-600 font-bold">0 元</td><td class="p-2 text-green-600">省去 1 个全职</td></tr>
    <tr class="border-b"><td class="p-2 font-bold">框架/工具许可</td><td class="p-2">10-30 万/年</td><td class="p-2 text-green-600 font-bold">0 元</td><td class="p-2 text-green-600">100%</td></tr>
    <tr class="border-b bg-gray-50"><td class="p-2 font-bold">部署周期</td><td class="p-2">数周至数月</td><td class="p-2 text-green-600 font-bold">分钟级</td><td class="p-2 text-green-600">90%+ 时间</td></tr>
  </tbody>
</table>
</div>

---

# 以中型企业销售团队为例，算一笔账

<div class="bg-blue-50 rounded-lg p-3 text-sm text-gray-600 mb-5">
  基准假设：一名年薪资 20 万的销售人员
</div>

<div class="grid grid-cols-3 gap-4 mb-6">
<div class="bg-white rounded-lg shadow-sm p-4 text-center border-t-4 border-green-500">
  <div class="text-3xl font-bold text-green-600">1-3 个月</div>
  <div class="text-gray-500 mt-1">投资回报周期</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-4 text-center border-t-4 border-blue-500">
  <div class="text-3xl font-bold text-blue-600">50-100 万</div>
  <div class="text-gray-500 mt-1">年新增收入</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-4 text-center border-t-4 border-purple-500">
  <div class="text-3xl font-bold text-purple-600">0.5-1 个</div>
  <div class="text-gray-500 mt-1">全职人力释放</div>
</div>
</div>

<div class="space-y-2">
<div class="bg-white rounded-lg shadow-sm p-3 flex gap-3">
  <div class="font-bold text-blue-600 w-16 shrink-0">人力释放</div>
  <div class="text-gray-700 text-sm">AI 替代 1-2 小时/天 → 相当于 0.5-1 个全职人力释放</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-3 flex gap-3">
  <div class="font-bold text-blue-600 w-16 shrink-0">新增商机</div>
  <div class="text-gray-700 text-sm">转化率提升 20% + 销售周期缩短 20% → 额外 50-100 万年收入</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-3 flex gap-3">
  <div class="font-bold text-blue-600 w-16 shrink-0">部署成本</div>
  <div class="text-gray-700 text-sm">几乎为零（开源 + 自有服务器）</div>
</div>
</div>

<div class="bg-green-50 rounded-lg p-4 mt-5 text-center">
  <div class="text-lg font-bold text-green-700">这不是一个成本中心，这是一个收入引擎</div>
</div>

---

# 为谁而建？

<div class="grid grid-cols-3 gap-4 pt-4">
<div class="bg-white rounded-lg shadow-sm p-4 border-t-4 border-blue-500">
  <div class="font-bold text-base mb-2 text-center">一线销售/商务经理</div>
  <div class="text-gray-600 text-sm mb-3 text-center">比竞对更快知道客户在哪<br/>需求是什么</div>
  <div class="bg-blue-500 text-white rounded-lg p-2 text-center text-xs font-bold">
    自动预警 + 客户画像 + 商机全追踪
  </div>
</div>
<div class="bg-white rounded-lg shadow-sm p-4 border-t-4 border-cyan-500">
  <div class="font-bold text-base mb-2 text-center">市场研究/战略规划</div>
  <div class="text-gray-600 text-sm mb-3 text-center">持续扫描行业全貌<br/>形成可指导决策的报告</div>
  <div class="bg-cyan-500 text-white rounded-lg p-2 text-center text-xs font-bold">
    多渠道采集 + AI 分析 + 趋势可视化
  </div>
</div>
<div class="bg-white rounded-lg shadow-sm p-4 border-t-4 border-green-500">
  <div class="font-bold text-base mb-2 text-center">企业管理者/决策层</div>
  <div class="text-gray-600 text-sm mb-3 text-center">一眼看清整体状况<br/>不做凭感觉的赌局</div>
  <div class="bg-green-500 text-white rounded-lg p-2 text-center text-xs font-bold">
    数据看板 + AI 摘要 + 组织级公共资产
  </div>
</div>
</div>

<div class="text-center text-gray-400 text-xs mt-5">
  不是给所有人的万能工具 — 是为情报驱动决策的团队量身定制的效率倍增器
</div>

---

# 为什么不是 CRM？不是 OA？不是 Excel？

<div class="bg-white rounded-lg shadow-sm p-4 overflow-x-auto">
<table class="w-full text-xs">
  <thead>
    <tr class="bg-amber-600 text-white">
      <th class="p-2 text-left">维度</th>
      <th class="p-2 text-left">通用 CRM</th>
      <th class="p-2 text-left">OA 系统</th>
      <th class="p-2 text-left">Excel</th>
      <th class="p-2 text-left">Intelligence Web</th>
    </tr>
  </thead>
  <tbody>
    <tr class="border-b"><td class="p-2 font-bold">定位</td><td class="p-2">客户关系管理</td><td class="p-2">办公流程管理</td><td class="p-2">临时记录</td><td class="p-2 text-amber-600 font-bold">企业情报智能管理</td></tr>
    <tr class="border-b bg-gray-50"><td class="p-2 font-bold">信息采集</td><td class="p-2 text-red-400"><svg class="w-4 h-4" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg></td><td class="p-2 text-red-400"><svg class="w-4 h-4" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg></td><td class="p-2 text-red-400"><svg class="w-4 h-4" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg></td><td class="p-2 text-green-600 font-bold">AI 自动采集</td></tr>
    <tr class="border-b"><td class="p-2 font-bold">AI 分析</td><td class="p-2 text-red-400"><svg class="w-4 h-4" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg></td><td class="p-2 text-red-400"><svg class="w-4 h-4" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg></td><td class="p-2 text-red-400"><svg class="w-4 h-4" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg></td><td class="p-2 text-green-600 font-bold">AI Agent 分析</td></tr>
    <tr class="border-b bg-gray-50"><td class="p-2 font-bold">多域扩展</td><td class="p-2">固定模块</td><td class="p-2">固定模块</td><td class="p-2">手动搭建</td><td class="p-2 text-green-600 font-bold">数天上线新域</td></tr>
    <tr class="border-b"><td class="p-2 font-bold">部署成本</td><td class="p-2">百万级</td><td class="p-2">十万级</td><td class="p-2">低</td><td class="p-2 text-green-600 font-bold">几乎为零</td></tr>
    <tr class="border-b bg-gray-50"><td class="p-2 font-bold">情报深度</td><td class="p-2">浅</td><td class="p-2">浅</td><td class="p-2">无</td><td class="p-2 text-green-600 font-bold">深（全链路）</td></tr>
  </tbody>
</table>
</div>

<div class="bg-blue-50 rounded-lg p-4 mt-4 border-l-4 border-blue-600">
  <div class="text-sm text-gray-700">Intelligence Web 只做一件事：帮企业把散落在各处的情报变成可行动的洞察。为此做了极深的垂直打磨。</div>
</div>

---

# 最快数分钟，启动您的企业情报系统

<div class="grid grid-cols-3 gap-4 pt-4">
<div class="bg-white rounded-lg shadow-sm p-4 border-t-4 border-blue-500">
  <div class="text-xl font-bold text-blue-500 text-center mb-2">Step 1</div>
  <div class="bg-blue-50 rounded-md p-2 text-center font-mono text-xs font-bold text-blue-700 mb-1">docker compose up -d</div>
  <div class="text-gray-500 text-center text-xs">一条命令启动全部服务</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-4 border-t-4 border-green-500">
  <div class="text-xl font-bold text-green-500 text-center mb-2">Step 2</div>
  <div class="bg-green-50 rounded-md p-2 text-center font-mono text-xs font-bold text-green-700 mb-1">浏览器访问 :8765</div>
  <div class="text-gray-500 text-center text-xs">登录，开始使用</div>
</div>
<div class="bg-white rounded-lg shadow-sm p-4 border-t-4 border-cyan-500">
  <div class="text-xl font-bold text-cyan-500 text-center mb-2">Step 3</div>
  <div class="bg-cyan-50 rounded-md p-2 text-center font-mono text-xs font-bold text-cyan-700 mb-1">配置数据源 + 项目</div>
  <div class="text-gray-500 text-center text-xs">开始自动采集</div>
</div>
</div>

<div class="mt-5">
<div class="text-blue-600 font-bold text-sm mb-3">开箱即用的能力</div>
<div class="grid grid-cols-2 gap-3">
<div class="bg-white rounded-lg shadow-sm p-3 flex gap-2 items-center">
  <svg class="w-4 h-4 text-green-500 shrink-0" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
  <span class="text-gray-700 text-xs">15 个功能页面，即开即用</span>
</div>
<div class="bg-white rounded-lg shadow-sm p-3 flex gap-2 items-center">
  <svg class="w-4 h-4 text-green-500 shrink-0" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
  <span class="text-gray-700 text-xs">RBAC 权限体系，三级角色即刻生效</span>
</div>
<div class="bg-white rounded-lg shadow-sm p-3 flex gap-2 items-center">
  <svg class="w-4 h-4 text-green-500 shrink-0" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
  <span class="text-gray-700 text-xs">AI Agent 预设模板，配置即用</span>
</div>
<div class="bg-white rounded-lg shadow-sm p-3 flex gap-2 items-center">
  <svg class="w-4 h-4 text-green-500 shrink-0" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
  <span class="text-gray-700 text-xs">暗色模式、响应式设计，现代用户体验</span>
</div>
<div class="bg-white rounded-lg shadow-sm p-3 flex gap-2 items-center">
  <svg class="w-4 h-4 text-green-500 shrink-0" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
  <span class="text-gray-700 text-xs">新业务域：一份配置 + 一个模板 → 数天内上线</span>
</div>
</div>
</div>

---

# Intelligence Web

<div class="pt-6">
  <div class="text-2xl font-bold text-blue-600">让情报成为您的核心竞争力</div>
</div>

<div class="grid grid-cols-2 gap-4 pt-6 text-base">
<div class="flex items-center gap-2">
  <svg class="w-5 h-5 text-blue-500" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><ellipse cx="12" cy="12" rx="4" ry="10" fill="none" stroke="currentColor" stroke-width="2"/><line x1="2" y1="12" x2="22" y2="12" stroke="currentColor" stroke-width="2"/></svg>
  <span>开源 · 免费 · 可私有化部署</span>
</div>
<div class="flex items-center gap-2">
  <svg class="w-5 h-5 text-purple-500" viewBox="0 0 24 24"><rect x="4" y="8" width="16" height="12" rx="2" fill="currentColor"/><circle cx="9" cy="13" r="1.5" fill="white"/><circle cx="15" cy="13" r="1.5" fill="white"/><rect x="10" y="4" width="4" height="4" rx="1" fill="currentColor"/></svg>
  <span>AI 驱动 · 人机协同 · 持续进化</span>
</div>
<div class="flex items-center gap-2">
  <svg class="w-5 h-5 text-green-500" viewBox="0 0 24 24"><rect x="3" y="12" width="4" height="9" rx="1" fill="currentColor"/><rect x="10" y="6" width="4" height="15" rx="1" fill="currentColor"/><rect x="17" y="3" width="4" height="18" rx="1" fill="currentColor"/></svg>
  <span>1-3 个月投资回报 · 100 万年新增收入</span>
</div>
<div class="flex items-center gap-2">
  <svg class="w-5 h-5 text-amber-500" viewBox="0 0 24 24"><path d="M12 2L8 8l-2 6 6 4 6-4-2-6z" fill="currentColor"/><circle cx="12" cy="10" r="2" fill="white"/></svg>
  <span>一条命令启动 · 数天扩展新域</span>
</div>
</div>

<div class="bg-green-50 rounded-lg p-6 mt-8 text-center">
  <div class="text-xl font-bold text-green-700">准备好让您的企业情报管理升级了吗？</div>
</div>

<div class="text-center text-gray-400 text-xs mt-6">
  [官网]  [邮箱]  [电话]  [二维码]
</div>

<div class="abs-br m-4 flex gap-2">
  <span class="text-xs opacity-50">Intelligence Web · 让情报成为核心竞争力</span>
</div>

---

# The End

<div class="pt-12 text-center">
  <div class="text-5xl font-bold text-gray-800">Thank You</div>
  <div class="text-lg text-gray-500 mt-3">感谢聆听</div>
</div>

<div class="abs-br m-4 flex gap-2">
  <span class="text-xs opacity-50">Intelligence Web</span>
</div>