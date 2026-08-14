#!/usr/bin/env bash
# 使用 officecli 创建 Intelligence Web 功能使用说明书

FILE="/Users/Yoo/SVN/00.GITHUB/Intelligence_Web/docs/Intelligence_Web_功能使用说明书.docx"
SS_DIR="/Users/Yoo/SVN/00.GITHUB/Intelligence_Web/docs/screenshots"
SS_BASE="Intelligence_Web"

rm -f "$FILE"
officecli open "$FILE"
officecli add "$FILE" / --prop pageWidth=12240 --prop pageHeight=15840 --prop marginTop=1440 --prop marginBottom=1440 --prop marginLeft=1440 --prop marginRight=1440

# ========== COVER PAGE ==========
officecli add "$FILE" /body --type paragraph --prop text="CONFIDENTIAL" --prop align=center --prop size=9pt --prop color=C00000 --prop bold=true --prop spaceAfter=36pt
officecli add "$FILE" /body --type paragraph --prop text="" --prop spaceAfter=48pt
officecli add "$FILE" /body --type paragraph --prop text="Intelligence Web" --prop align=center --prop size=36pt --prop bold=true --prop spaceAfter=8pt
officecli add "$FILE" /body --type paragraph --prop text="企业情报智能管理平台" --prop align=center --prop italic=true --prop size=20pt --prop spaceAfter=24pt
officecli add "$FILE" /body --type paragraph --prop text="功能使用说明书" --prop align=center --prop size=28pt --prop bold=true --prop spaceAfter=36pt
officecli add "$FILE" /body --type paragraph --prop text="v1.0" --prop align=center --prop size=14pt --prop spaceAfter=6pt
officecli add "$FILE" /body --type paragraph --prop text="2026-08-03" --prop align=center --prop size=14pt --prop spaceAfter=48pt
officecli add "$FILE" /body --type pagebreak --prop pageBreakBefore=true

# ========== TABLE OF CONTENTS HEADER ==========
officecli add "$FILE" /body --type paragraph --prop text="目 录" --prop style=Heading1 --prop size=22pt --prop bold=true --prop align=center --prop spaceAfter=12pt --prop spaceBefore=24pt
officecli add "$FILE" /body --type paragraph --prop text="1.  登录与认证" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type paragraph --prop text="2.  主框架布局" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type paragraph --prop text="3.  情报列表" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type paragraph --prop text="4.  数据看板" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type paragraph --prop text="5.  采集项目管理" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type paragraph --prop text="6.  数据源管理" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type paragraph --prop text="7.  目标类型管理" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type paragraph --prop text="8.  AI 智能分析师" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type paragraph --prop text="9.  用户管理" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type paragraph --prop text="10. 角色管理" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type paragraph --prop text="11. 批量导入" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type paragraph --prop text="12. 操作日志" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type paragraph --prop text="13. 通知中心" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type paragraph --prop text="14. 系统设置" --prop size=12pt --prop spaceAfter=4pt
officecli add "$FILE" /body --type pagebreak --prop pageBreakBefore=true

# ========== HELPER: add section with screenshot and description ==========
# Section 1: Login
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="1. 登录与认证"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="系统通过用户名和密码进行身份认证。用户登录后系统自动生成 JWT Token，后续所有 API 请求均需在 Header 中携带该 Token。Token 存储在浏览器 localStorage 中，过期后自动跳转回登录页。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="支持功能："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="用户名 / 密码登录"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="JWT Token 认证（后端签发，前端管理）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="登录过期自动跳转"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="错误提示（登录失败/未登录）"
add /body --type picture --prop src="$SS_DIR/login.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 1-1：登录页面"
OFFICECLI

# Section 2: Shell
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="2. 主框架布局"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="系统采用经典 SPA 布局：顶部 Header + 左侧 Sidebar + 右侧 Tab 内容区。支持多 Tab 标签页切换，每个 Tab 加载一个功能页面。系统支持多域切换（制造情报 / 销售情报），通过右上角域名选择器切换后端数据源。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="主要区域："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="顶部 Header：品牌 Logo、Tab 标签栏、域名切换器、全局搜索、用户头像"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="左侧 Sidebar：导航菜单，按模块分组（全部情报 / 系统 / 其他）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="右侧内容区：Tab 标签切换，每个 Tab 加载独立 HTML 页面"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="详情面板：点击情报条目后弹出右侧详情页"
add /body --type picture --prop src="$SS_DIR/shell.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 2-1：主框架布局"
OFFICECLI

# Section 3: Intelligence List
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="3. 情报列表"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="情报列表是系统的核心页面，展示所有已采集的情报条目。支持多维筛选、搜索和状态流转。每条情报可点击查看详情，进行状态变更（待处理→合格→激活→完结→废止）。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能特性："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="顶部统计卡片：全部情报 / 待处理 / 处理中 / 已完成数量汇总"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="多维筛选：关键词搜索、状态筛选、分类筛选、项目筛选"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="情报卡片：显示标题、分类标签、公司、金额、项目、评论数、创建时间"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="详情面板：点击情报卡片弹出详情，显示完整内容、评论、附件上传"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="状态流转：待处理 → 合格（建议跟进）→ 激活 → 完结 / 废止"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="后端 API："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop text="GET /api/intelligence — 获取情报列表"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop text="GET /api/intelligence/{id} — 获取单条情报详情"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop text="PUT /api/intelligence/{id}/status — 更新情报状态"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop text="POST/GET /api/intelligence/{id}/comments — 评论管理"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop text="POST/GET /api/intelligence/{id}/attachments — 附件上传"
add /body --type picture --prop src="$SS_DIR/index.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 3-1：情报列表页面"
OFFICECLI

# Section 4: Dashboard
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="4. 数据看板"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="数据看板通过可视化图表和统计卡片，帮助用户快速掌握全局业务态势。当前已实现全球供应链布局地图（基于 ECharts），展示供应商、客户、投资/新工厂的地理分布及供应流向。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="展示内容："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="统计卡片：追踪供应商数、关注市场区域、全球总产能、全球总需求"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="世界地图：供应商（蓝色）、客户（绿色）、投资/新工厂（橙色）的地理分布"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="供应流向线：不同节点之间的供应关系"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="供应商产能对比表：各供应商总部、年产能、同比变化"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="区域供需平衡表：各区域供应量、需求量、供需状态"
add /body --type picture --prop src="$SS_DIR/dashboard.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 4-1：数据看板（全球供应布局）"
OFFICECLI

# Section 5: Projects
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="5. 采集项目管理"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="采集项目将数据源和目标类型组合，定义 AI Agent 的具体采集任务。每个项目指定采集目标（如某类竞品公司、某行业领域），关联一个或多个数据源，设定采集频率（日/周/月）。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="项目配置字段："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="项目名称（必填）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="目标类型（必填）：如"竞争对手"、"市场动态"、"供应链"等"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="目标名称（选填）：具体的目标对象描述"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="采集范围（选填）：描述采集的信息范围"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="采集频率（默认 weekly）：daily / weekly / monthly / oneshot"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="指令说明（选填）：给 AI Agent 的采集策略提示"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="数据源关联（选填）：选择该项目关联的数据源"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="项目生命周期："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="创建项目 → 关联数据源 → 启用采集 → 产生情报 → 查看关联情报"
add /body --type picture --prop src="$SS_DIR/projects.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 5-1：采集项目页面"
OFFICECLI

# Section 6: Data Sources
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="6. 数据源管理"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="数据源是 AI Agent 进行信息采集的目标地址。支持网站（Website）、RSS 订阅、API 接口等多种类型。每个数据源可设定采集频率、关注指标、启用/禁用状态。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="数据源字段："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="名称（必填）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="类型：website / rss / api"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="URL（必填）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="采集频率：daily / weekly / monthly"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="状态：active / inactive"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="关注指标（逗号分隔）：描述该数据源重点关注的关键信息"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="描述（选填）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="数据源操作："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="新建 / 编辑 / 删除 / 启用 / 禁用 / 筛选（按类型 / 状态）"
add /body --type picture --prop src="$SS_DIR/datasources.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 6-1：数据源管理页面"
OFFICECLI

# Section 7: Target Types
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="7. 目标类型管理"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="目标类型是采集项目的分类维度，定义了情报的归属类别。例如：竞争对手、供应商、客户、市场动态、政策法规等。每个目标类型可设定独立颜色和图标，用于在前端区分展示。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="目标类型字段："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="标识（slug，必填）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="显示名称（label，必填）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="描述"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="颜色（用于前端标签渲染）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="图标（SVG 路径）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="排序号 / 启用状态"
add /body --type picture --prop src="$SS_DIR/target_types.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 7-1：目标类型管理页面"
OFFICECLI

# Section 8: AI Analyst
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="8. AI 智能分析师"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="AI 分析师基于已采集的情报数据，通过自然语言问答为用户提供智能分析服务。用户输入问题后，系统从情报库中检索相关数据，调用 AI 模型进行综合分析并返回结构化结果。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="使用方式："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="直接输入问题，按 Enter 发送"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="使用快捷提示词（当前竞争格局 / 本月新增情报 / 重点关注客户动态 / 供应商产能变化）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="支持多轮对话，问题基于已采集的情报数据上下文"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="结果支持 Markdown 格式渲染（标题、列表、代码块等）"
add /body --type picture --prop src="$SS_DIR/analyst.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 8-1：AI 智能分析师页面"
OFFICECLI

# Section 9: User Management
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="9. 用户管理"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="用户管理模块管理系统的认证用户。支持用户的增删改查、角色分配、状态管理。每个用户关联一个系统角色，决定其操作权限。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="用户管理功能："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="新建用户：用户名、显示名称、密码、角色、状态"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="编辑用户：修改显示名称、密码重置、角色变更、状态启用/禁用"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="删除用户：软删除，保留历史数据"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="用户列表展示：用户名、显示名称、角色标签、状态（启用/禁用）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="搜索过滤"
add /body --type picture --prop src="$SS_DIR/users.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 9-1：用户管理页面"
OFFICECLI

# Section 10: Role Management
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="10. 角色管理"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="角色管理定义系统的权限分层体系。每个角色可关联多个用户，管理员可通过角色管理批量查看各角色下的用户分布。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="角色操作："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="新建角色"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="编辑角色名称"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="查看各角色下的用户数量"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="删除角色"
add /body --type picture --prop src="$SS_DIR/roles.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 10-1：角色管理页面"
OFFICECLI

# Section 11: Batch Import
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="11. 批量导入"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="批量导入功能支持通过上传 Excel (.xlsx) 或 CSV 文件，快速向系统中导入大量情报数据。系统自动识别文件列头并与系统字段进行映射匹配，用户确认后可执行导入。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="导入流程（三步走）："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="步骤一：上传文件 — 拖拽或点击上传 Excel/CSV 文件"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="步骤二：字段映射 — 系统自动识别列头与字段的对应关系（标题/内容/分类/状态/公司/意见），用户可手动调整"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="步骤三：预览确认 — 预览前 20 行数据，标记有效/无效行（缺少标题或内容），确认后导入"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="自动匹配规则："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="标题 → 匹配关键词：标题、title、name、主题、名称、subject"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="内容 → 匹配关键词：内容、content、正文、body、描述、description、详情"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="分类 → 匹配关键词：分类、category、类型、type、类别"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="状态 → 匹配关键词：状态、status、stage"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="公司 → 自动映射为 company 字段"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="来源链接 → 匹配关键词：来源链接、url、链接、原文链接"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="重复检测：相同标题的情报将跳过导入"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="自动项目匹配：如果文件中包含 URL，系统会自动关联到对应数据源所属的项目"
add /body --type picture --prop src="$SS_DIR/import.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 11-1：批量导入页面"
OFFICECLI

# Section 12: Audit Logs
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="12. 操作日志"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="操作日志记录系统中所有数据变更的历史轨迹。包括情报的创建、状态变更、评论添加、项目修改、数据源变更等操作。支持按操作类型、资源类型、时间范围进行筛选。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="日志记录内容："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="操作类型：情报新增 / 状态变更 / 评论 / 导入 / 项目变更 / 数据源变更"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="操作详情：记录了变更的具体内容"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="时间戳：精确到秒的操作时间"
add /body --type picture --prop src="$SS_DIR/audit.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 12-1：操作日志页面"
OFFICECLI

# Section 13: Notifications
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="13. 通知中心"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="通知中心集中展示系统产生的各类通知消息。包括情报状态变更、AI 分析完成、项目触发等事件的推送通知。支持未读计数和已读/全部已读标记功能。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能特性："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="通知列表展示"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="未读通知计数"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="全部已读标记"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="筛选未读通知"
add /body --type picture --prop src="$SS_DIR/notifications.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 13-1：通知中心页面"
OFFICECLI

# Section 14: Settings
cat <<'OFFICECLI' | officecli batch "$FILE"
add /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=8pt --prop text="14. 系统设置"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="功能概述："
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="系统设置提供平台级的配置管理能力。管理员可在此配置 AI 模型参数、MCP Server 连接、JWT 密钥、域名开关等关键系统参数。敏感字段（如 API Key）在界面上以掩码形式展示。"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="设置类别："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="AI 模型配置：模型名称、API Key、最大 Tokens、温度参数"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="MCP Server 配置：Agent Key、Server URL"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="系统配置：JWT Secret、CORS 白名单"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="服务健康检查：查看制造情报 API、销售情报 API、Meilisearch 服务状态"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="域名管理：启用/禁用各业务域（制造情报/销售情报）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="安全机制："
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="敏感字段掩码显示（只展示首尾各 3 个字符 + ***）"
add /body --type paragraph --prop size=12pt --prop spaceAfter=4pt --prop listStyle=bullet --prop text="所有配置变更需通过 PUT /api/system/settings 提交"
add /body --type picture --prop src="$SS_DIR/settings.png" --prop width=8in
add /body --type paragraph --prop size=10pt --prop italic=true --prop align=center --prop spaceAfter=12pt --prop text="图 14-1：系统设置页面"
OFFICECLI

# ========== APPENDIX: API Reference ==========
officecli add "$FILE" /body --type pagebreak --prop pageBreakBefore=true
officecli add "$FILE" /body --type paragraph --prop style=Heading1 --prop size=20pt --prop bold=true --prop spaceAfter=12pt --prop text="附录：API 接口总览"
officecli add "$FILE" /body --type paragraph --prop size=12pt --prop spaceAfter=6pt --prop text="以下为系统所有 API 接口的汇总："

# Table: API Reference
officecli add "$FILE" /body --type table --prop rows=22 --prop cols=3 --prop width=100%

# Table Header
officecli set "$FILE" "/body/tbl[1]/tr[1]" --prop header=true --prop c1=方法 --prop c2=接口路径 --prop c3=功能说明
for col in 1 2 3; do
  officecli set "$FILE" "/body/tbl[1]/tr[1]/tc[$col]" --prop fill=1F4E79
  officecli set "$FILE" "/body/tbl[1]/tr[1]/tc[$col]/p[1]/r[1]" --prop bold=true --prop color=FFFFFF
done

# Data rows
officecli set "$FILE" "/body/tbl[1]/tr[2]" --prop c1=GET --prop c2="/api/domain_config" --prop c3="获取当前域配置（主题色、状态、目标类型等）"
officecli set "$FILE" "/body/tbl[1]/tr[3]" --prop c1=GET --prop c2="/api/dashboard/stats" --prop c3="获取数据看板统计"
officecli set "$FILE" "/body/tbl[1]/tr[4]" --prop c1=GET --prop c2="/api/intelligence" --prop c3="获取情报列表（支持筛选）"
officecli set "$FILE" "/body/tbl[1]/tr[5]" --prop c1=POST --prop c2="/api/intelligence" --prop c3="创建情报条目"
officecli set "$FILE" "/body/tbl[1]/tr[6]" --prop c1=GET --prop c2="/api/intelligence/{id}" --prop c3="获取情报详情"
officecli set "$FILE" "/body/tbl[1]/tr[7]" --prop c1=PUT --prop c2="/api/intelligence/{id}/status" --prop c3="更新情报状态"
officecli set "$FILE" "/body/tbl[1]/tr[8]" --prop c1=POST --prop c2="/api/intelligence/{id}/comments" --prop c3="添加评论"
officecli set "$FILE" "/body/tbl[1]/tr[9]" --prop c1=GET --prop c2="/api/intelligence/{id}/comments" --prop c3="获取评论列表"
officecli set "$FILE" "/body/tbl[1]/tr[10]" --prop c1=GET --prop c2="/api/intelligence/{id}/history" --prop c3="获取变更历史"
officecli set "$FILE" "/body/tbl[1]/tr[11]" --prop c1=POST --prop c2="/api/intelligence/{id}/summary" --prop c3="添加摘要"
officecli set "$FILE" "/body/tbl[1]/tr[12]" --prop c1=GET --prop c2="/api/intelligence/{id}/summary" --prop c3="获取摘要"
officecli set "$FILE" "/body/tbl[1]/tr[13]" --prop c1=POST --prop c2="/api/intelligence/import" --prop c3="批量导入（Excel/CSV）"
officecli set "$FILE" "/body/tbl[1]/tr[14]" --prop c1=GET --prop c2="/api/categories" --prop c3="获取分类列表"
officecli set "$FILE" "/body/tbl[1]/tr[15]" --prop c1=GET --prop c2="/api/projects" --prop c3="获取项目列表"
officecli set "$FILE" "/body/tbl[1]/tr[16]" --prop c1=POST --prop c2="/api/projects" --prop c3="创建项目"
officecli set "$FILE" "/body/tbl[1]/tr[17]" --prop c1=PUT --prop c2="/api/projects/{id}" --prop c3="更新项目"
officecli set "$FILE" "/body/tbl[1]/tr[18]" --prop c1=DELETE --prop c2="/api/projects/{id}" --prop c3="删除项目"
officecli set "$FILE" "/body/tbl[1]/tr[19]" --prop c1=GET --prop c2="/api/datasources" --prop c3="获取数据源列表"
officecli set "$FILE" "/body/tbl[1]/tr[20]" --prop c1=POST --prop c2="/api/datasources" --prop c3="创建数据源"
officecli set "$FILE" "/body/tbl[1]/tr[21]" --prop c1=GET --prop c2="/api/target_types" --prop c3="获取目标类型列表"
officecli set "$FILE" "/body/tbl[1]/tr[22]" --prop c1=GET --prop c2="/api/system/settings" --prop c3="获取系统设置"

# Footer with page number
officecli add "$FILE" / --type footer --prop type=first --prop text=""
officecli add "$FILE" / --type footer --prop type=default --prop align=center --prop size=9pt --prop text="Page " --prop field=page

# Close and validate
officecli close "$FILE"
officecli validate "$FILE"

echo "=== Document created: $FILE ==="
