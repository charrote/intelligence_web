# UI Shell + Tab + Hash Routing 设计文档

> 2026-07-22 · 情报平台前端架构重构

## 问题

当前 portal 有 13 个独立 HTML 页面，每个页面自包含 header + sidebar + main + CSS + JS。存在三个核心问题：

1. **无返回路径**：点击侧栏进入子页面（如数据源管理）后，没有返回方式，只能依赖浏览器后退按钮。
2. **无多页并行**：不支持 Tab 打开多个功能页，无法同时对比数据源和项目等信息。
3. **严重代码重复**：CSS 变量、header、sidebar、表格、按钮、表单等样式在每个页面重复定义，总计 3,485 行中有约 655 行（19%）可提取为共享资源。

## 方案

采用 **Shared Shell + Hash 路由** 架构，创建一个统一的 `shell.html` 作为唯一入口，通过 hash 路由动态加载各页面内容，顶部 Header 集成 Tab 标签栏。

## 架构

```
shell.html (唯一入口)
├── 共享层 (Header + Tab 栏 + Sidebar)
│   ├── Header: Logo, 搜索, 域名切换, 用户头像, Tab 标签栏, 新 Tab 按钮
│   ├── Sidebar: 统一侧栏导航 (所有页面都有)
│   └── 共享 CSS/JS: css/*.css, js/*.js
│
├── Hash 路由层
│   ├── # → 情报列表 (首页 Tab，不可关闭)
│   ├── #datasources → 数据源管理
│   ├── #projects → 采集项目
│   ├── #analyst → AI 分析师
│   ├── #users → 用户管理
│   ├── #import → 批量导入
│   ├── #audit → 操作日志
│   ├── #settings → 个人设置
│   ├── #notifications → 通知中心
│   ├── #roles → 角色管理
│   └── #dashboard → 数据看板
│
└── 内容区
    └── 按 Hash 动态加载对应页面的 main 内容 + 脚本
```

## 页面改造方式

每个现有页面需要做的改动（每页约 10-15 行）：

1. **剥离** 自包含的 header/sidebar CSS（改为引用共享 CSS）
2. **保留** 各自独立的 `<main>` 内容区
3. **保留** 各自独立的 `<script>` 逻辑
4. **添加** 共享 CSS/JS 引用
5. **适配** 全局 namespace（`APP_TOKEN`, `APP_API_BASE` 等）

核心业务逻辑完全不动。

## 共享资源目录

```
portal/
├── shell.html              ← 新：统一入口
├── css/
│   ├── variables.css       ← 全量 CSS 变量 (从 demo.html 提取 superset)
│   ├── reset.css           ← 全局重置
│   ├── header.css          ← Header 样式 (含 Tab 栏样式)
│   ├── sidebar.css         ← Sidebar 样式
│   ├── layout.css          ← 布局 (header + sidebar + main)
│   ├── components.css      ← 按钮、表格、表单、标签、面板、弹窗
│   └── responsive.css      ← 响应式
├── js/
│   ├── init.js             ← 全局初始化 (token, apiBase, 域名配置加载)
│   ├── auth.js             ← 认证 (doLogout, getToken, apiFetch)
│   ├── dom.js              ← 工具 (escapeHtml, formatDate)
│   └── tabs.js             ← Tab 管理 (打开/关闭/切换)
├── index.html              ← 改造：保留 main + script
├── datasources.html        ← 改造
├── projects.html           ← 改造
├── analyst.html            ← 改造
├── users.html              ← 改造
├── roles.html              ← 改造
├── import.html             ← 改造
├── audit.html              ← 改造
├── settings.html           ← 改造
├── notifications.html      ← 改造
├── dashboard.html          ← 改造
├── demo.html               ← 保留不变
└── login.html              ← 保留不变（独立于 Shell）
```

## 路由表

```javascript
const ROUTES = {
  '':             { page: 'index.html',         label: '情报列表',         group: '导航' },
  'dashboard':    { page: 'dashboard.html',     label: '数据看板',         group: '导航' },
  'datasources':  { page: 'datasources.html',   label: '数据源管理',       group: '系统' },
  'projects':     { page: 'projects.html',      label: '采集项目',         group: '系统' },
  'analyst':      { page: 'analyst.html',       label: 'AI 分析师',        group: '系统' },
  'users':        { page: 'users.html',         label: '用户管理',         group: '系统' },
  'roles':        { page: 'roles.html',         label: '角色管理',         group: '系统' },
  'import':       { page: 'import.html',        label: '批量导入',         group: '系统' },
  'audit':        { page: 'audit.html',         label: '操作日志',         group: '系统' },
  'settings':     { page: 'settings.html',      label: '个人设置',         group: '系统' },
  'notifications':{ page: 'notifications.html', label: '通知中心',         group: '系统' },
};
```

## Tab 管理

| 功能 | 实现 |
|------|------|
| 打开 Tab | 点击侧栏 → 检查 Hash → 已有 Tab 则切换，无则新建 |
| 关闭 Tab | 点击 Tab × → 移除 Tab + 清空内容区 + 跳转最近 Tab |
| 首页保护 | 情报列表 Tab 无 × 按钮，不可关闭 |
| Tab 标题 | 显示功能名称，如 `情报列表` 或 `数据源管理` |
| 新 Tab 按钮 | Header 右侧 `+` 按钮快速打开首页 |

## Hash 路由

- 使用 `location.hash`（如 `#/datasources`），不需要服务端配置
- 监听 `hashchange` 事件驱动页面切换
- nginx 配置 `try_files` fallback 到 `shell.html`

## nginx 配置

```nginx
location /portal/ {
    alias /var/www/portal/;
    try_files $uri $uri/ /portal/shell.html;
}
```

## CSS 变量统一

取所有页面的 superset 变量，写入 `variables.css`。当前 13 个页面使用的变量覆盖度为：

- 核心变量（`--accent`, `--green`, `--red`, `--gray-*`, `--radius`）在所有页面一致
- `demo.html` 拥有最完整的变量集，作为 `variables.css` 的基础

## 侧栏统一

所有页面（包括当前无侧栏的 `datasources.html`、`users.html`、`roles.html`、`audit.html`、`settings.html`、`notifications.html`、`analyst.html` 等）统一使用同一套侧栏导航。

## 不改动的内容

- 每个页面的核心 JS（API 调用、数据渲染、业务逻辑）完全不动
- `login.html` 保持独立，不进入 Shell 系统
- `demo.html` 保持不变
- 后端 API 完全不动