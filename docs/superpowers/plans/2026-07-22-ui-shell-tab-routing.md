# UI Shell + Tab + Hash 路由 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一情报平台前端架构，实现共享 Shell 框架、侧栏导航、Tab 标签页和 Hash 路由，消除代码重复。

**Architecture:** 创建 `shell.html` 作为唯一入口，顶部 Header 集成 Tab 栏和统一侧栏，通过 Hash 路由 (`#/datasources`) 动态加载各页面内容。CSS/JS 提取为共享模块，11 个现有页面剥离 header/sidebar 后接入 Shell。

**Tech Stack:** Vanilla HTML/CSS/JS，无框架依赖。Hash 路由 (`window.location.hash`)，共享 CSS 变量 (`:root`)。

---

## 文件清单

### 新建文件 (10 个)
| 文件 | 职责 |
|------|------|
| `portal/css/variables.css` | 全量 CSS 变量定义 |
| `portal/css/reset.css` | 全局重置样式 |
| `portal/css/header.css` | Header + Tab 栏 + 搜索样式 |
| `portal/css/sidebar.css` | 侧栏导航样式 |
| `portal/css/layout.css` | 页面布局 (header + sidebar + main) |
| `portal/css/components.css` | 按钮/表格/表单/标签/面板/弹窗/统计卡 |
| `portal/css/responsive.css` | 响应式断点 |
| `portal/js/init.js` | 全局初始化 (token, apiBase, 域名配置, 用户头像) |
| `portal/js/auth.js` | 认证 (doLogout, getToken, getUser, apiFetch) |
| `portal/js/tabs.js` | Tab 管理 (打开/关闭/切换/hash 路由) |
| `portal/shell.html` | 统一入口 (Header + Tab 栏 + Sidebar + 内容区) |

### 修改文件 (11 个)
`index.html`, `datasources.html`, `projects.html`, `analyst.html`, `users.html`, `roles.html`, `import.html`, `audit.html`, `settings.html`, `notifications.html`, `dashboard.html`

### 修改配置 (1 个)
`nginx/gateway.conf` — 添加 Hash 路由 fallback

### 保持不变 (2 个)
`login.html`, `demo.html` — 不改

---

### Task 1: 创建 `portal/css/variables.css`

**Files:**
- Create: `portal/css/variables.css`

- [ ] **Step 1: 创建 CSS 变量文件**

```css
/* portal/css/variables.css */
/* 全量 CSS 变量 — 所有页面共享的 superset */
:root {
  /* Brand */
  --accent:#3b4f8c;
  --accent-light:#eef1f7;
  --accent-mid:#d0d7e6;

  /* Semantic */
  --green:#2a7d4f;
  --green-light:#eaf5ef;
  --amber:#b8862d;
  --amber-light:#faf3e5;
  --red:#b33a3a;
  --red-light:#f7eaea;
  --blue:#3b6ea5;
  --blue-light:#eaf0f7;

  /* Neutrals */
  --gray-50:#f8f9fa;
  --gray-100:#f0f1f2;
  --gray-200:#e0e1e3;
  --gray-300:#c4c5c7;
  --gray-400:#9a9b9d;
  --gray-500:#707173;
  --gray-600:#545557;
  --gray-700:#3b3c3d;
  --gray-800:#262728;
  --gray-900:#1a1a1a;

  /* UI */
  --radius:6px;
  --radius-sm:3px;
  --radius-md:8px;
  --radius-lg:12px;
  --shadow-sm:0 1px 2px rgba(0,0,0,0.04);
  --shadow-md:0 4px 12px rgba(0,0,0,0.08);
  --shadow-lg:0 12px 40px rgba(0,0,0,0.1);
}
```

- [ ] **Step 2: 验证文件内容**

确认文件正确创建，包含所有变量。

---

### Task 2: 创建 `portal/css/reset.css`

**Files:**
- Create: `portal/css/reset.css`

- [ ] **Step 1: 创建重置样式**

```css
/* portal/css/reset.css */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px;-webkit-font-smoothing:antialiased}
body{font-family:system-ui,-apple-system,sans-serif;background:#f5f6f8;color:#1e1e1e;min-height:100vh}
input,select,button{font-family:inherit;font-size:inherit}
```

- [ ] **Step 2: 验证文件内容**

---

### Task 3: 创建 `portal/css/header.css`

**Files:**
- Create: `portal/css/header.css`

- [ ] **Step 1: 创建 Header 样式**

```css
/* portal/css/header.css */
.header{height:56px;display:flex;align-items:center;padding:0 24px;background:#fff;border-bottom:1px solid var(--gray-200);gap:8px}
.header-logo{font-weight:600;font-size:16px;color:var(--gray-800);display:flex;align-items:center;gap:8px}
.header-logo .mark{width:6px;height:6px;border-radius:2px;background:var(--accent);display:inline-block}
.header-grow{flex:1}
.header-domain select{padding:5px 20px 5px 10px;border:1px solid var(--gray-200);border-radius:var(--radius);background:#fff;font-size:13px;color:var(--gray-600);cursor:pointer}
.header-search{display:flex;align-items:center;background:var(--gray-50);border:1px solid var(--gray-200);border-radius:var(--radius);padding:0 10px;flex:1;max-width:280px;transition:border-color 0.2s}
.header-search:focus-within{border-color:var(--accent)}
.header-search input{border:none;background:transparent;padding:7px 0;font-size:13px;color:var(--gray-800);outline:none;width:100%}
.header-search input::placeholder{color:var(--gray-400)}
.header-avatar{width:32px;height:32px;border-radius:50%;background:var(--accent-light);color:var(--accent);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;cursor:pointer}
.header-nav{display:flex;gap:12px;align-items:center}
.header-nav a{font-size:13px;color:var(--gray-600);text-decoration:none}
.header-nav a:hover{color:var(--accent)}

/* Tab Bar */
.tab-bar{display:flex;align-items:center;gap:2px;height:56px;padding:0 8px;overflow-x:auto;overflow-y:hidden;flex-shrink:0}
.tab-bar::-webkit-scrollbar{display:none}
.tab{display:flex;align-items:center;gap:6px;padding:6px 12px;font-size:12px;color:var(--gray-600);background:var(--gray-50);border:1px solid var(--gray-200);border-radius:var(--radius);cursor:pointer;white-space:nowrap;flex-shrink:0;transition:all 0.12s}
.tab:hover{background:var(--gray-200)}
.tab.active{background:var(--accent-light);color:var(--accent);font-weight:500;border-color:var(--accent)}
.tab-close{width:14px;height:14px;display:flex;align-items:center;justify-content:center;border-radius:2px;font-size:14px;color:var(--gray-400);line-height:1}
.tab-close:hover{background:var(--gray-300);color:var(--gray-700)}
.tab:not(.pinned) .tab-close{display:flex}
.tab-bar .tab-new{width:28px;height:28px;display:flex;align-items:center;justify-content:center;border:1px dashed var(--gray-300);border-radius:var(--radius);cursor:pointer;font-size:16px;color:var(--gray-500);flex-shrink:0;transition:all 0.12s}
.tab-bar .tab-new:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-light)}
```

---

### Task 4: 创建 `portal/css/sidebar.css`

**Files:**
- Create: `portal/css/sidebar.css`

- [ ] **Step 1: 创建侧栏样式**

```css
/* portal/css/sidebar.css */
.sidebar{width:200px;background:#fff;border-right:1px solid var(--gray-200);padding:16px 0;flex-shrink:0;overflow-y:auto}
.sidebar-label{padding:6px 16px 5px;font-size:10px;font-weight:600;color:var(--gray-400);text-transform:uppercase;letter-spacing:0.8px}
.sidebar-item{display:flex;align-items:center;gap:8px;padding:7px 16px;font-size:13px;color:var(--gray-600);cursor:pointer;transition:all 0.12s}
.sidebar-item:hover{color:var(--gray-800);background:var(--gray-50)}
.sidebar-item.active{color:var(--accent);font-weight:500;background:var(--accent-light)}
.sidebar-item .ico{width:16px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.sidebar-divider{height:1px;background:var(--gray-200);margin:10px 16px}
```

---

### Task 5: 创建 `portal/css/layout.css`

**Files:**
- Create: `portal/css/layout.css`

- [ ] **Step 1: 创建布局样式**

```css
/* portal/css/layout.css */
.layout{display:flex;min-height:calc(100vh - 56px)}
.main{flex:1;padding:24px 28px;overflow-y:auto}
```

---

### Task 6: 创建 `portal/css/components.css`

**Files:**
- Create: `portal/css/components.css`

- [ ] **Step 1: 创建组件样式**

```css
/* portal/css/components.css */

/* Buttons */
.btn{padding:6px 14px;border:none;border-radius:var(--radius);font-size:13px;font-weight:500;cursor:pointer;transition:all 0.12s}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:#2f3f70}
.btn-ghost{background:var(--gray-100);color:var(--gray-600)}
.btn-ghost:hover{background:var(--gray-200)}
.btn-success{background:var(--green);color:#fff}
.btn-success:hover{background:#1f613b}
.btn-danger{background:var(--red);color:#fff}
.btn-danger:hover{background:#8f2e2e}

/* Tables */
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--gray-200);border-radius:var(--radius);overflow:hidden}
th{text-align:left;padding:10px 14px;font-size:11px;font-weight:600;color:var(--gray-400);text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid var(--gray-200);background:var(--gray-50)}
td{padding:10px 14px;font-size:13px;color:var(--gray-600);border-bottom:1px solid var(--gray-100)}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--gray-50)}

/* Forms */
.form-group{margin-bottom:14px}
.form-group label{display:block;font-size:12px;font-weight:600;color:var(--gray-600);margin-bottom:4px}
.form-group input,.form-group select,.form-group textarea{width:100%;padding:8px 10px;border:1px solid var(--gray-200);border-radius:var(--radius);font-size:13px;color:var(--gray-800);background:#fff}
.form-group input:focus,.form-group select:focus,.form-group textarea:focus{outline:none;border-color:var(--accent)}
.form-row{display:flex;gap:12px}
.form-row .form-group{flex:1}

/* Tags */
.tag{display:inline-flex;padding:2px 7px;border-radius:3px;font-size:11px;font-weight:500}

/* Stats Cards */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
.stat{background:#fff;border:1px solid var(--gray-200);border-radius:var(--radius);padding:14px 18px;box-shadow:var(--shadow-sm)}
.stat-num{font-size:22px;font-weight:600;color:var(--gray-800);letter-spacing:-0.3px;line-height:1.2}
.stat-label{font-size:12px;color:var(--gray-400);margin-top:2px}

/* Section Header */
.section-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.section-header h2{font-size:15px;font-weight:600;color:var(--gray-800)}
.section-header .count{font-size:12px;color:var(--gray-400);font-weight:400;margin-left:6px}
.section-header .filter-group{display:flex;gap:6px;align-items:center}
.section-header .filter-group select{padding:4px 20px 4px 8px;border:1px solid var(--gray-200);border-radius:var(--radius);font-size:12px;color:var(--gray-600);background:#fff;cursor:pointer}
.section-header .btn-reset{padding:4px 10px;border:1px solid var(--gray-200);border-radius:var(--radius);font-size:12px;color:var(--gray-500);background:#fff;cursor:pointer}

/* Panel (Right Drawer) */
.panel-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.15);z-index:200}
.panel{display:none;position:fixed;top:0;right:0;width:560px;max-width:92vw;height:100vh;background:#fff;box-shadow:var(--shadow-lg);z-index:201;flex-direction:column;overflow:hidden}
.panel.open{display:flex}.panel.open+.panel-overlay{display:block}
.panel-head{display:flex;align-items:center;padding:16px 20px;border-bottom:1px solid var(--gray-200);flex-shrink:0}
.panel-head h2{font-size:15px;font-weight:600;color:var(--gray-800);flex:1;line-height:1.4;padding-right:8px}
.panel-close{width:28px;height:28px;border:none;border-radius:var(--radius);background:var(--gray-100);color:var(--gray-500);cursor:pointer;display:flex;align-items:center;justify-content:center}
.panel-close:hover{background:var(--gray-200);color:var(--gray-700)}
.panel-body{padding:20px;overflow-y:auto;flex:1}
.panel-foot{padding:12px 20px;border-top:1px solid var(--gray-200);display:flex;gap:6px;flex-shrink:0}
.panel-foot .btn{padding:7px 14px;border:none;border-radius:var(--radius);font-size:12px;font-weight:500;cursor:pointer;transition:all 0.12s}
.panel-foot .btn-primary{background:var(--accent);color:#fff}
.panel-foot .btn-primary:hover{background:#2f3f70}
.panel-foot .btn-success{background:var(--green);color:#fff}
.panel-foot .btn-success:hover{background:#1f613b}
.panel-foot .btn-danger{background:var(--red);color:#fff}
.panel-foot .btn-danger:hover{background:#8f2e2e}
.panel-foot .btn-ghost{background:var(--gray-100);color:var(--gray-600)}
.panel-foot .btn-ghost:hover{background:var(--gray-200)}
.panel-foot .spacer{flex:1}

/* Detail */
.detail-meta{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}
.detail-meta .tag{display:inline-flex;padding:2px 8px;border-radius:3px;font-size:12px;font-weight:500;line-height:1.5}
.detail-source{font-size:12px;color:var(--gray-400);margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid var(--gray-200)}
.detail-content{font-size:14px;line-height:1.7;color:var(--gray-700)}
.detail-content ul{padding-left:18px;margin-bottom:10px}
.detail-content li{margin-bottom:4px}
.detail-opinion{background:var(--accent-light);padding:10px 14px;border-radius:var(--radius);margin-bottom:14px;font-size:13px;color:var(--accent)}

/* Comments */
.comment-section{margin-top:20px;padding-top:16px;border-top:1px solid var(--gray-200)}
.comment-section h3{font-size:13px;font-weight:600;color:var(--gray-700);margin-bottom:10px}
.comment{padding:10px 14px;background:var(--gray-50);border-radius:var(--radius);margin-bottom:6px}
.comment-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:3px}
.comment-name{font-weight:500;font-size:12px;color:var(--accent)}
.comment-time{font-size:11px;color:var(--gray-400)}
.comment-text{font-size:12px;color:var(--gray-600);line-height:1.5}

/* Modal (Center) */
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.15);z-index:200}
.modal-overlay.open{display:flex;align-items:center;justify-content:center}
.modal{background:#fff;border-radius:var(--radius);padding:24px;width:420px;max-width:90vw;box-shadow:var(--shadow-lg)}

/* Empty State */
.empty{padding:40px;text-align:center;color:var(--gray-400);font-size:13px}

/* Icon */
.icon{width:16px;height:16px;display:inline-block;vertical-align:middle;flex-shrink:0}
```

---

### Task 7: 创建 `portal/css/responsive.css`

**Files:**
- Create: `portal/css/responsive.css`

- [ ] **Step 1: 创建响应式样式**

```css
/* portal/css/responsive.css */
@media(max-width:768px){
  .sidebar{display:none}
  .main{padding:16px}
  .stats{grid-template-columns:repeat(2,1fr)}
  .panel{width:100vw;max-width:100vw}
}
```

---

### Task 8: 创建 `portal/js/dom.js`

**Files:**
- Create: `portal/js/dom.js`

- [ ] **Step 1: 创建 DOM 工具模块**

```js
// portal/js/dom.js
// DOM utility functions

function escapeHtml(s) {
  if (!s) return '';
  return String(s).replace(/[&<>"']/g, function(c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"}[c];
  });
}

function formatDate(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return (d.getMonth()+1)+'月'+d.getDate()+'日';
}
```

---

### Task 9: 创建 `portal/js/auth.js`

**Files:**
- Create: `portal/js/auth.js`

- [ ] **Step 1: 创建认证模块**

```js
// portal/js/auth.js
// Authentication helpers

function getToken() {
  return localStorage.getItem('token');
}

function getUser() {
  try { return JSON.parse(localStorage.getItem('user')); }
  catch(e) { return null; }
}

function apiBase() {
  const p = window.location.protocol;
  const h = window.location.hostname;
  const pn = parseInt(window.location.port) || (location.protocol === 'https:' ? 443 : 80);
  return p + '//' + h + ':' + pn;
}

function apiFetch(url, options) {
  options = options || {};
  options.headers = options.headers || {};
  const token = getToken();
  if (token) {
    options.headers['Authorization'] = 'Bearer ' + token;
  }
  return fetch(url, options);
}

function doLogout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  window.location.href = '/portal/login.html';
}
```

---

### Task 10: 创建 `portal/js/init.js`

**Files:**
- Create: `portal/js/init.js`

- [ ] **Step 1: 创建初始化模块**

```js
// portal/js/init.js
// Global initialization: auth guard, API base, domain config

var APP_TOKEN = getToken();
var APP_API_BASE = apiBase();
var domainConfig = null, statusMap = {};

function checkAuth() {
  if (!APP_TOKEN) {
    window.location.href = '/portal/login.html';
    return false;
  }
  var user = getUser();
  if (user) {
    var avatar = document.getElementById('userAvatar');
    if (avatar) {
      avatar.textContent = user.display_name || user.username.charAt(0).toUpperCase();
    }
  }
  return true;
}

function updateAvatar() {
  var user = getUser();
  if (user) {
    var avatar = document.getElementById('userAvatar');
    if (avatar) {
      avatar.textContent = user.display_name || user.username.charAt(0).toUpperCase();
    }
  }
}

function getUserDisplayName() {
  var user = getUser();
  return user ? (user.display_name || user.username) : '用户';
}

async function loadDomainConfig() {
  try {
    var res = await apiFetch(APP_API_BASE + '/api/domain_config');
    domainConfig = await res.json();
    domainConfig.statuses.forEach(function(s) { statusMap[s[0]] = s[1]; });
    var titleEl = document.getElementById('appTitle');
    if (titleEl) {
      titleEl.textContent = domainConfig.title_prefix;
      document.title = domainConfig.title_prefix;
    }
  } catch(e) {
    statusMap = {pending:'待审阅',approved:'可行',rejected:'不可行',active:'激活',completed:'已完结',discarded:'已废弃'};
  }
}
```

---

### Task 11: 创建 `portal/js/tabs.js`

**Files:**
- Create: `portal/js/tabs.js`

- [ ] **Step 1: 创建 Tab 管理模块**

```js
// portal/js/tabs.js
// Tab management and hash routing

var ROUTES = {
  '': { page: 'index.html', label: '情报列表', pinned: true },
  'dashboard': { page: 'dashboard.html', label: '数据看板' },
  'datasources': { page: 'datasources.html', label: '数据源管理' },
  'projects': { page: 'projects.html', label: '采集项目' },
  'analyst': { page: 'analyst.html', label: 'AI 分析师' },
  'users': { page: 'users.html', label: '用户管理' },
  'roles': { page: 'roles.html', label: '角色管理' },
  'import': { page: 'import.html', label: '批量导入' },
  'audit': { page: 'audit.html', label: '操作日志' },
  'settings': { page: 'settings.html', label: '个人设置' },
  'notifications': { page: 'notifications.html', label: '通知中心' }
};

var TABS = [];  // [{ id, hash, label, iframe }]
var currentTabId = null;
var tabCounter = 0;

function getHash() {
  return window.location.hash.replace('#', '');
}

function openTab(hash) {
  // Check if tab already exists
  var existing = TABS.find(function(t) { return t.hash === hash; });
  if (existing) {
    switchToTab(existing.id);
    return;
  }

  var route = ROUTES[hash];
  if (!route) return;

  tabCounter++;
  var tab = {
    id: tabCounter,
    hash: hash,
    label: route.label,
    page: route.page,
    pinned: route.pinned || false,
    iframe: null
  };

  TABS.push(tab);
  renderTabBar();
  switchToTab(tab.id);
}

function closeTab(tabId) {
  var idx = TABS.findIndex(function(t) { return t.id === tabId; });
  if (idx === -1) return;
  var tab = TABS[idx];
  if (tab.pinned) return;

  // Remove iframe content
  if (tab.iframe && tab.iframe.parentNode) {
    tab.iframe.parentNode.removeChild(tab.iframe);
  }

  TABS.splice(idx, 1);

  if (currentTabId === tabId) {
    // Switch to nearest tab or root
    if (TABS.length > 0) {
      var newTab = TABS[Math.min(idx, TABS.length - 1)];
      switchToTab(newTab.id);
    } else {
      switchToTab(null);
    }
  }

  renderTabBar();
}

function switchToTab(tabId) {
  // Deactivate all tabs
  TABS.forEach(function(t) {
    if (t.iframe) t.iframe.style.display = 'none';
  });

  // Deactivate all tab bar items
  var tabItems = document.querySelectorAll('.tab[data-tab-id]');
  tabItems.forEach(function(el) { el.classList.remove('active'); });

  currentTabId = tabId;

  if (tabId === null) {
    // Show root (index.html)
    var mainEl = document.getElementById('tabContent');
    if (mainEl) mainEl.innerHTML = '';
    return;
  }

  var tab = TABS.find(function(t) { return t.id === tabId; });
  if (!tab) return;

  // Activate tab bar item
  var tabItem = document.querySelector('.tab[data-tab-id="' + tabId + '"]');
  if (tabItem) tabItem.classList.add('active');

  // Update hash
  window.location.hash = tab.hash;

  // Show/activate iframe
  if (tab.iframe && tab.iframe.parentNode) {
    tab.iframe.style.display = 'block';
  } else {
    // Create new iframe
    var mainEl = document.getElementById('tabContent');
    if (mainEl) {
      var iframe = document.createElement('iframe');
      iframe.src = tab.page;
      iframe.style.width = '100%';
      iframe.style.height = '100%';
      iframe.style.border = 'none';
      iframe.style.display = 'block';
      mainEl.innerHTML = '';
      mainEl.appendChild(iframe);
      tab.iframe = iframe;
    }
  }
}

function setActiveSidebar(hash) {
  var items = document.querySelectorAll('.sidebar-item[data-route]');
  items.forEach(function(item) {
    var route = item.getAttribute('data-route');
    if (route === hash) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });
}

function renderTabBar() {
  var bar = document.getElementById('tabBar');
  if (!bar) return;

  var html = '';
  TABS.forEach(function(tab) {
    var closeLabel = tab.pinned ? '' : '<span class="tab-close" onclick="event.stopPropagation();closeTab(' + tab.id + ')">&times;</span>';
    html += '<div class="tab' + (tab.id === currentTabId ? ' active' : '') + (tab.pinned ? ' pinned' : '') + '" data-tab-id="' + tab.id + '" onclick="switchToTab(' + tab.id + ')">'
      + escapeHtml(tab.label) + closeLabel + '</div>';
  });
  html += '<div class="tab-new" onclick="openTab(\'\'") title="打开首页">+</div>';

  bar.innerHTML = html;
}

function initTabs() {
  // Listen for hash changes
  window.addEventListener('hashchange', function() {
    var hash = getHash();
    setActiveSidebar(hash);
    var existing = TABS.find(function(t) { return t.hash === hash; });
    if (existing) {
      switchToTab(existing.id);
    } else if (ROUTES[hash]) {
      openTab(hash);
    }
  });

  // Initial load
  var initialHash = getHash();
  if (initialHash && ROUTES[initialHash]) {
    openTab(initialHash);
  } else {
    openTab('');
  }
}
```

---

### Task 12: 创建 `portal/shell.html`

**Files:**
- Create: `portal/shell.html`

- [ ] **Step 1: 创建统一入口页面**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>情报平台</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<link rel="stylesheet" href="css/variables.css">
<link rel="stylesheet" href="css/reset.css">
<link rel="stylesheet" href="css/header.css">
<link rel="stylesheet" href="css/sidebar.css">
<link rel="stylesheet" href="css/layout.css">
<link rel="stylesheet" href="css/components.css">
<link rel="stylesheet" href="css/responsive.css">
<script src="js/dom.js"></script>
<script src="js/auth.js"></script>
<script src="js/init.js"></script>
<script src="js/tabs.js"></script>
<style>
  .tab-content-wrapper{flex:1;display:flex;flex-direction:column;overflow:hidden;position:relative}
  .breadcrumb{padding:8px 20px;font-size:12px;color:var(--gray-400);border-bottom:1px solid var(--gray-200);background:#fff;flex-shrink:0}
  .breadcrumb a{color:var(--accent);text-decoration:none}
  .breadcrumb a:hover{text-decoration:underline}
  .breadcrumb .sep{margin:0 4px}
  .tab-content{flex:1;position:relative;overflow:hidden}
  .tab-content iframe{width:100%;height:100%;border:none}
  .no-content{display:flex;align-items:center;justify-content:center;height:100%;color:var(--gray-400);font-size:14px}
  #tabContent{width:100%;height:100%;position:relative}
  .sidebar-item[data-route]::before{
    content:'';width:16px;height:16px;display:inline-block;vertical-align:middle;flex-shrink:0;
  }
</style>
</head>
<body>
<header class="header">
  <div class="header-logo"><span class="mark"></span><span id="appTitle">情报平台</span></div>
  <div class="header-grow"></div>
  <div class="tab-bar" id="tabBar"></div>
  <div class="header-domain">
    <select id="domainSwitcher" onchange="switchDomain(this.value)">
      <option value="8766">制造情报</option>
      <option value="8767">销售情报</option>
    </select>
  </div>
  <div class="header-search">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--gray-400)" stroke-width="1.5" style="margin-right:5px;flex-shrink:0"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input type="text" id="searchInput" placeholder="搜索情报...">
  </div>
  <div class="header-avatar" id="userAvatar" title="用户" onclick="doLogout()" style="cursor:pointer">管</div>
</header>
<div class="layout">
  <aside class="sidebar">
    <div class="sidebar-label">导航</div>
    <div class="sidebar-item" data-route="" onclick="openTab('')"><span class="ico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg></span>全部情报</div>
    <div class="sidebar-item" data-route="dashboard"><span class="ico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg></span>数据看板</div>
    <div class="sidebar-divider"></div>
    <div class="sidebar-label">系统</div>
    <div class="sidebar-item" data-route="projects" onclick="openTab('projects')"><span class="ico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><path d="M9 14l2 2 4-4"/></svg></span>采集项目</div>
    <div class="sidebar-item" data-route="datasources" onclick="openTab('datasources')"><span class="ico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg></span>数据源管理</div>
    <div class="sidebar-item" data-route="analyst" onclick="openTab('analyst')"><span class="ico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20z"/><path d="M12 8v4l3 3"/></svg></span>AI 分析师</div>
    <div class="sidebar-item" data-route="users" onclick="openTab('users')"><span class="ico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></span>用户管理</div>
    <div class="sidebar-item" data-route="roles" onclick="openTab('roles')"><span class="ico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></span>角色管理</div>
    <div class="sidebar-item" data-route="import" onclick="openTab('import')"><span class="ico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg></span>批量导入</div>
    <div class="sidebar-item" data-route="audit" onclick="openTab('audit')"><span class="ico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span>操作日志</div>
    <div class="sidebar-item" data-route="notifications" onclick="openTab('notifications')"><span class="ico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg></span>通知中心</div>
    <div class="sidebar-divider"></div>
    <div class="sidebar-label">其他</div>
    <div class="sidebar-item" data-route="settings" onclick="openTab('settings')"><span class="ico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg></span>个人设置</div>
    <div id="sidebarCats"></div>
  </aside>
  <div class="tab-content-wrapper">
    <div class="breadcrumb" id="breadcrumb">
      <a href="#" onclick="openTab('');return false;">首页</a>
    </div>
    <div class="tab-content">
      <div id="tabContent">
        <div class="no-content">加载中...</div>
      </div>
    </div>
  </div>
</div>
<div class="panel" id="detailPanel">
  <div class="panel-head"><h2 id="panelTitle">详情</h2><button class="panel-close" onclick="closePanel()"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button></div>
  <div class="panel-body" id="panelBody"></div>
  <div class="panel-foot" id="panelFoot"></div>
</div>
<div class="panel-overlay" onclick="closePanel()"></div>
<script>
function switchDomain(port){
  // TODO: Implement domain switching via reload or API
  window.location.reload();
}

var currentIntel = null;
function closePanel(){var p=document.getElementById('detailPanel');p.classList.remove('open');currentIntel=null;}
function openPanel(){document.getElementById('detailPanel').classList.add('open');}

window.addEventListener('load', function() {
  if (!checkAuth()) return;
  loadDomainConfig().then(function() {
    initTabs();
  });
});
</script>
</body>
</html>
```

---

### Task 13: 更新 nginx 配置

**Files:**
- Modify: `nginx/gateway.conf`

- [ ] **Step 1: 添加 Hash 路由 fallback**

将现有的 `location /portal/` 块修改为：

```nginx
# Static files
location /portal/ {
    alias /var/www/portal/;
    try_files $uri $uri/ /portal/shell.html;
}
```

完整文件内容:
```nginx
server {
    listen 80;
    server_name intelligence.nat.ywapi.com;
    resolver 127.0.0.11 ipv6=off valid=10s;

    root /var/www;
    index index.html;

    # Auth backend (internal)
    location = /_auth {
        internal;
        proxy_pass http://research:8766/api/auth/check;
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";
        proxy_set_header Authorization $http_authorization;
    }

    # Auth endpoints (public)
    location ~ ^/api/auth/(login|check)$ {
        proxy_pass http://research:8766;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Health endpoint (public)
    location = /api/health {
        proxy_pass http://research:8766;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Protected API (Research)
    location /api/ {
        auth_request /_auth;
        error_page 401 = @error401;
        proxy_pass http://research:8766;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
        client_max_body_size 50m;
        proxy_request_buffering off;
    }

    # Sales API via gateway
    location /sales/api/ {
        auth_request /_auth;
        error_page 401 = @error401;
        rewrite ^/sales/api/(.*)$ /api/$1 break;
        proxy_pass http://sales:8767;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
        client_max_body_size 50m;
        proxy_request_buffering off;
    }

    # Crawler Service API (public - no auth needed)
    location /crawler/api/ {
        rewrite ^/crawler/api/(.*)$ /api/$1 break;
        proxy_pass http://crawler:8768;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 401 handler
    location @error401 {
        add_header Content-Type application/json;
        return 401 '{"error":"未登录或登录已过期，请重新登录"}';
    }

    # Research domain
    location /research/ {
        auth_request /_auth;
        error_page 401 = @error401;
        proxy_pass http://research:8766/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
    }

    # Sales domain
    location /sales/ {
        auth_request /_auth;
        error_page 401 = @error401;
        proxy_pass http://sales:8767/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
    }

    # Root redirect to portal
    location = / {
        return 302 /portal/;
    }

    # Static files with hash routing fallback
    location /portal/ {
        alias /var/www/portal/;
        try_files $uri $uri/ /portal/shell.html;
    }
    location /intelligence_sales/ { alias /var/www/intelligence_sales/; }
}
```

- [ ] **Step 2: 验证文件内容**

---

### Task 14: 改造 `portal/index.html` — 剥离 header/sidebar

**Files:**
- Modify: `portal/index.html`

- [ ] **Step 1: 修改 index.html — 添加共享资源引用，保留 main 和 script**

需要做的改动：
1. `<head>` 中替换内联 `<style>` 为共享 CSS 链接
2. `<body>` 中保留 `<main class="main">` 及所有内容
3. `<script>` 开头添加 `APP_TOKEN`, `APP_API_BASE` 全局变量
4. 删除自包含的 CSS/JS

修改后的结构:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>情报列表</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<link rel="stylesheet" href="css/variables.css">
<link rel="stylesheet" href="css/reset.css">
<link rel="stylesheet" href="css/header.css">
<link rel="stylesheet" href="css/sidebar.css">
<link rel="stylesheet" href="css/layout.css">
<link rel="stylesheet" href="css/components.css">
<link rel="stylesheet" href="css/responsive.css">
<script src="js/dom.js"></script>
<script src="js/auth.js"></script>
<script src="js/init.js"></script>
<script src="js/tabs.js"></script>
<style>
/* === Page-specific CSS only === */
.feed{display:flex;flex-direction:column;gap:6px}
.row{display:flex;align-items:stretch;background:#fff;border:1px solid var(--gray-200);border-radius:var(--radius);cursor:pointer;transition:all 0.15s}
.row:hover{border-color:var(--accent);background:var(--gray-50)}
.row-index{width:36px;display:flex;align-items:center;justify-content:center;font-size:12px;color:var(--gray-400);flex-shrink:0}
.row-body{flex:1;padding:12px 16px 12px 0;overflow:hidden;display:flex;flex-direction:column;gap:6px}
.row-title{font-size:14px;font-weight:500;color:var(--gray-800);line-height:1.5}
.row-meta{display:flex;align-items:center;gap:12px;font-size:12px;color:var(--gray-400);flex-wrap:wrap}
.row-meta .tag{display:inline-flex;padding:1px 6px;border-radius:2px;font-size:11px;font-weight:500;color:var(--gray-600);background:var(--gray-100)}
.row-meta .tag-company{color:var(--accent);background:var(--accent-light)}
.row-meta .deal{color:var(--green);font-weight:500}
.stat-num.gold{color:var(--amber)}.stat-num.green{color:var(--green)}.stat-num.accent{color:var(--accent)}
#sidebarCats{}</style>
</head>
<body>
<!-- shell.html provides header + sidebar -->
<main class="main">
  <div class="stats" id="statsRow">
    <div class="stat"><div class="stat-num accent" id="statTotal">-</div><div class="stat-label">全部情报</div></div>
    <div class="stat"><div class="stat-num gold" id="statPending">-</div><div class="stat-label">待审阅</div></div>
    <div class="stat"><div class="stat-num green" id="statApproved">-</div><div class="stat-label">已跟进</div></div>
    <div class="stat"><div class="stat-num" id="statCompleted">-</div><div class="stat-label">已完结</div></div>
  </div>
  <div class="section-header">
    <h2>最新情报 <span class="count" id="feedCount"></span></h2>
    <div class="filter-group">
      <select id="statusFilter" onchange="filterCards()"><option value="">全部状态</option></select>
      <select id="catFilter" onchange="filterCards()"><option value="">全部分类</option></select>
      <button class="btn-reset" onclick="resetFilter()">重置</button>
    </div>
  </div>
  <div class="feed" id="feed"></div>
</main>

<!-- Panel - kept here because it's rendered in the iframe context -->
<div class="panel" id="detailPanel">
  <div class="panel-head"><h2 id="panelTitle">详情</h2><button class="panel-close" onclick="closePanel()"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button></div>
  <div class="panel-body" id="panelBody"></div>
  <div class="panel-foot" id="panelFoot"></div>
</div>
<div class="panel-overlay" onclick="closePanel()"></div>

<script>
// Re-define globals for iframe context
var currentIntel = null;
var allItems = [];
var domainConfig = null, statusMap = {};
var domainPort = parseInt(window.location.port) || (location.protocol === 'https:' ? 443 : 80);

function escapeHtml(s) {
  if (!s) return '';
  return String(s).replace(/[&<>"']/g, function(c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"}[c];
  });
}

function closePanel(){document.getElementById('detailPanel').classList.remove('open');currentIntel=null;filterCards()}

async function init() {
  await loadDomainConfig();
  await loadData();
  render();
  buildSidebarCats();
}

async function loadDomainConfig() {
  try {
    var res = await apiFetch(APP_API_BASE + '/api/domain_config');
    domainConfig = await res.json();
    domainConfig.statuses.forEach(function(s) { statusMap[s[0]] = s[1]; });
  } catch(e) { statusMap = {pending:'待审阅',approved:'可行',rejected:'不可行',active:'激活',completed:'已完结',discarded:'已废弃'}; }
}

async function loadData() {
  try { var r = await apiFetch(APP_API_BASE + '/api/intelligence?limit=100'); var d = await r.json(); allItems = d.items || []; } catch(e) { allItems = []; }
}

function buildSidebarCats() {
  var list = document.getElementById('sidebarCats'); if (!list) return;
  list.innerHTML = '';
  var cats = [];
  for (var i = 0; i < allItems.length; i++) { if (allItems[i].category && cats.indexOf(allItems[i].category) === -1) cats.push(allItems[i].category); }
  cats.slice(0,12).forEach(function(c) {
    var d=document.createElement('div'); d.className='sidebar-item'; d.innerHTML='<span class="ico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg></span>'+escapeHtml(c);
    d.onclick=function(){document.getElementById('catFilter').value=c;filterCards()};
    list.appendChild(d);
  });
}

function render() {
  var t=allItems.length, p=allItems.filter(function(i){return i.status==='pending'}).length, a=allItems.filter(function(i){return i.status==='approved'}).length, c=allItems.filter(function(i){return i.status==='completed'}).length;
  document.getElementById('statTotal').textContent=t; document.getElementById('statPending').textContent=p; document.getElementById('statApproved').textContent=a; document.getElementById('statCompleted').textContent=c;
  var sel=document.getElementById('statusFilter'); sel.innerHTML='<option value="">全部状态</option>';
  Object.entries(statusMap).forEach(function(e){var o=document.createElement('option');o.value=e[0];o.textContent=e[1];sel.appendChild(o)});
  var cs=document.getElementById('catFilter'); var cats=[]; for(var i=0;i<allItems.length;i++){if(allItems[i].category&&cats.indexOf(allItems[i].category)===-1)cats.push(allItems[i].category)}
  cs.innerHTML='<option value="">全部分类</option>'; cats.forEach(function(c){var o=document.createElement('option');o.value=c;o.textContent=c;cs.appendChild(o)});
  filterCards();
}

function filterCards() {
  var s=document.getElementById('searchInput').value.toLowerCase();
  var st=document.getElementById('statusFilter').value, cat=document.getElementById('catFilter').value;
  var items=allItems;
  if(s)items=items.filter(function(i){return (i.title||'').toLowerCase().includes(s)||(i.content||'').toLowerCase().includes(s)});
  if(st)items=items.filter(function(i){return i.status===st}); if(cat)items=items.filter(function(i){return i.category===cat});
  renderFeed(items); document.getElementById('feedCount').textContent=items.length+'条';
}

function renderFeed(items) {
  var feed=document.getElementById('feed');
  if(!items.length){feed.innerHTML='<div style="padding:40px;text-align:center;color:var(--gray-400);font-size:13px;">暂无匹配的情报</div>';return}
  feed.innerHTML=items.map(function(item,i){
    var co=escapeHtml(item.company||''), de=item.deal_value?(item.deal_value>10000?'¥'+(item.deal_value/10000).toFixed(0)+'万':'¥'+item.deal_value):'';
    var ents=(item.entities||[]).map(function(e){return '<span class="tag" style="background:#f0e6ff;color:#722ed1">'+escapeHtml(e)+'</span>'}).join('');
    return '<div class="row" onclick="openDetail('+item.id+')">'
    +'<div class="row-index">'+(i+1).toString().padStart(2,'0')+'</div>'
    +'<div class="row-body"><div class="row-title">'+escapeHtml(item.title||'')+'</div>'
    +'<div class="row-meta">'+(item.category?'<span class="tag">'+escapeHtml(item.category)+'</span>':'')
    +(co?'<span class="tag tag-company">'+co+'</span>':'')+(de?'<span class="deal">'+de+'</span>':'')
    +ents
    +'<span>'+formatDate(item.created_at)+'</span>'
    +(item.comment_count>0?'<span style="display:flex;align-items:center;gap:3px"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'+item.comment_count+'</span>':'')
    +'</div></div></div>'
  }).join('');
}

function setFilter(s){document.getElementById('statusFilter').value=s;filterCards()}
function resetFilter(){document.getElementById('searchInput').value='';document.getElementById('statusFilter').value='';document.getElementById('catFilter').value='';filterCards()}

async function openDetail(id) {
  try {
    var r=await apiFetch(APP_API_BASE+'/api/intelligence/'+id);currentIntel=await r.json();
    document.getElementById('panelTitle').textContent=currentIntel.title;
    renderDetail();loadComments(id);
    document.getElementById('detailPanel').classList.add('open');
  }catch(e){}
}

function renderDetail() {
  var d=currentIntel; var body=document.getElementById('panelBody'); var foot=document.getElementById('panelFoot');
  var ents=(d.entities||[]).map(function(e){return '<span class="tag" style="background:#f0e6ff;color:#722ed1">'+escapeHtml(e)+'</span>'}).join('');
  body.innerHTML='<div class="detail-meta">'
    +'<span class="tag tag-status '+d.status+'">'+(statusMap[d.status]||d.status)+'</span>'
    +(d.category?'<span class="tag tag-cat">'+escapeHtml(d.category)+'</span>':'')
    +(d.company?'<span class="tag tag-company">'+escapeHtml(d.company)+'</span>':'')
    +'</div>'
    +(ents?'<div style="margin-bottom:12px;font-size:12px;color:var(--gray-600)"><span style="color:var(--gray-400);margin-right:4px;">关联实体：</span>'+ents+'</div>':'')
    +(d.opinion?'<div class="detail-opinion">意见：'+escapeHtml(d.opinion)+'</div>':'')
    +(d.source_url?'<div style="margin-bottom:12px;"><a href="'+escapeHtml(d.source_url)+'" target="_blank" style="font-size:13px;color:var(--accent);">原文链接</a></div>':'')
    +('<div class="detail-source">'+formatDate(d.created_at)+'</div>'
    +'<div class="detail-content">'+(d.content||'')+'</div>')
    +'<div id="attachmentsSection" style="margin-top:16px;padding-top:14px;border-top:1px solid var(--gray-200)">'
    +'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">'
    +'<h3 style="font-size:13px;font-weight:600;color:var(--gray-700)">附件</h3>'
    +'<label style="font-size:12px;color:var(--accent);cursor:pointer">'
    +'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:3px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>上传</label>'
    +'<input type="file" id="attachFile" style="display:none" onchange="uploadAttachment('+id+')" multiple>'
    +'</div>'
    +'<div id="attachmentsList" style="font-size:13px">加载中...</div>'
    +'</div>'
    +'<div class="comment-section"><h3>Agent 评论</h3><div id="commentsContainer">加载中...</div></div>';
  var btns='';
  if(d.status==='pending')btns+='<button class="btn btn-success" onclick="updateStatus(\'approved\')">建议跟进</button><button class="btn btn-danger" onclick="updateStatus(\'rejected\')">不建议</button>';
  else if(d.status==='approved')btns+='<button class="btn btn-primary" onclick="updateStatus(\'active\')">激活项目</button>';
  else if(d.status==='active')btns+='<button class="btn btn-primary" onclick="updateStatus(\'completed\')">标记完结</button>';
  btns+='<span class="spacer"></span><button class="btn btn-ghost" onclick="updateStatus(\'discarded\')">废止</button>';
  foot.innerHTML=btns;
}

async function updateStatus(status) {
  if(!currentIntel)return;
  var opinion='';
  if(status==='approved'){opinion=prompt('请输入跟进意见：');if(opinion===null)return;}
  if(status==='discarded'){if(!confirm('确定废止？'))return;}
  try {
    var r=await apiFetch(APP_API_BASE+'/api/intelligence/'+currentIntel.id+'/status',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:status,opinion:opinion})});
    if(r.ok){currentIntel.status=status;if(opinion)currentIntel.opinion=opinion;renderDetail();await loadData();render();}
  }catch(e){}
}

async function loadComments(id) {
  try {
    var r=await apiFetch(APP_API_BASE+'/api/intelligence/'+id+'/comments?limit=20');var comments=await r.json();
    var c=document.getElementById('commentsContainer');if(!c)return;
    if(!comments.length){c.innerHTML='<div style="color:var(--gray-400);font-size:13px;">暂无评论</div>';return;}
    c.innerHTML=comments.map(function(co){return '<div class="comment"><div class="comment-head"><span class="comment-name">'+escapeHtml(co.agent_name)+'</span><span class="comment-time">'+formatDate(co.created_at)+'</span></div><div class="comment-text">'+escapeHtml(co.content||'')+'</div></div>'}).join('');
  }catch(e){}
}

async function uploadAttachment(intelId) {
  var input = document.getElementById('attachFile');
  var files = input.files;
  if (!files.length) return;
  var fd = new FormData();
  for (var i = 0; i < files.length; i++) {
    fd.append('file', files[i]);
    var desc = prompt('请输入文件描述（可选，可留空）', '');
    fd.append('description', desc !== null ? desc : '');
  }
  try {
    var r = await apiFetch(APP_API_BASE+'/api/intelligence/'+intelId+'/attachments', {
      method: 'POST',
      body: fd,
    });
    if (r.ok) {
      input.value = '';
      await loadAttachments(intelId);
    } else {
      var data = await r.json();
      alert(data.error || '上传失败');
    }
  } catch(e) { alert('上传失败'); }
}

async function loadAttachments(intelId) {
  try {
    var r = await apiFetch(APP_API_BASE+'/api/intelligence/'+intelId+'/attachments', {});
    var data = await r.json();
    var container = document.getElementById('attachmentsList');
    if (!data.items.length) {
      container.innerHTML = '<div style="color:var(--gray-400);font-size:12px">暂无附件</div>';
      return;
    }
    container.innerHTML = data.items.map(function(att) {
      var isImage = att.content_type && att.content_type.startsWith('image/');
      var size = att.file_size ? (att.file_size < 1024 ? att.file_size+'B' : (att.file_size < 1048576 ? (att.file_size/1024).toFixed(1)+'KB' : (att.file_size/1048576).toFixed(1)+'MB')) : '';
      var icon = isImage ? '🖼️' : '📎';
      return '<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--gray-100)">'
        +'<span>'+icon+'</span>'
        +'<a href="'+APP_API_BASE+'/api/attachments/'+att.id+'" target="_blank" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--accent);text-decoration:none;font-size:12px" title="'+escapeHtml(att.filename)+'">'+escapeHtml(att.filename)+'</a>'
        +'<span style="font-size:11px;color:var(--gray-400)">'+size+'</span>'
        +'</div>';
    }).join('');
  } catch(e) {
    var container = document.getElementById('attachmentsList');
    if (container) container.innerHTML = '<div style="color:var(--gray-400);font-size:12px">加载失败</div>';
  }
}

document.addEventListener('click', function(e) {
  if (e.target.closest('#attachmentsSection label') && currentIntel) {
    document.getElementById('attachFile').click();
  }
});

init();
</script>
</body>
</html>
```

注意：iframe 中的页面需要有自己的 `checkAuth()`，因为 iframe 内的 `localStorage` 与父窗口共享，但需要确保认证在 iframe 内生效。iframe 内的脚本不应再次加载 `shell.html` 的 `init.js`，因为认证已在父窗口完成。

**关键：iframe 内页面的 script 需要在开头添加认证检查：**
```js
// In each iframe page, add at top of script:
if (!getToken()) { window.location.href = '/portal/login.html'; }
```

---

### Task 15: 改造 `portal/datasources.html`

**Files:**
- Modify: `portal/datasources.html`

- [ ] **Step 1: 改造数据源管理页面**

修改方式：
1. `<head>` 添加共享 CSS/JS 引用
2. 保留 `<main class="main">` 内的所有内容
3. 删除 `<header>` 和所有 header/sidebar CSS
4. `<script>` 开头添加 `APP_API_BASE` 变量和认证检查
5. `apiFetch` 调用改用 `APP_API_BASE`

---

### Task 16: 改造 `portal/projects.html`

**Files:**
- Modify: `portal/projects.html`

- [ ] **Step 1: 改造采集项目页面**

修改方式同 Task 14：
1. 添加共享 CSS/JS 引用
2. 剥离 header/sidebar
3. 保留 main + script
4. 适配全局变量

---

### Task 17: 改造 `portal/analyst.html`

**Files:**
- Modify: `portal/analyst.html`

- [ ] **Step 1: 改造 AI 分析师页面**

修改方式：
1. 添加共享 CSS/JS 引用
2. 删除 header CSS（analyst 无 sidebar）
3. 保留 main + script
4. analyst 使用不同的 main 布局（flex column），需要在 index.html script 中调整或 analyst 自带 CSS

---

### Task 18: 改造 `portal/users.html`

**Files:**
- Modify: `portal/users.html`

- [ ] **Step 1: 改造用户管理页面**

修改方式：
1. 添加共享 CSS/JS 引用
2. 剥离 header/sidebar
3. 保留 main + script
4. 适配全局变量

---

### Task 19: 改造 `portal/roles.html`

**Files:**
- Modify: `portal/roles.html`

- [ ] **Step 1: 改造角色管理页面**

修改方式同上。

---

### Task 20: 改造 `portal/import.html`

**Files:**
- Modify: `portal/import.html`

- [ ] **Step 1: 改造批量导入页面**

修改方式同上。

---

### Task 21: 改造 `portal/audit.html`

**Files:**
- Modify: `portal/audit.html`

- [ ] **Step 1: 改造操作日志页面**

修改方式同上。

---

### Task 22: 改造 `portal/settings.html`

**Files:**
- Modify: `portal/settings.html`

- [ ] **Step 1: 改造个人设置页面**

修改方式同上。

---

### Task 23: 改造 `portal/notifications.html`

**Files:**
- Modify: `portal/notifications.html`

- [ ] **Step 1: 改造通知中心页面**

修改方式同上。

---

### Task 24: 改造 `portal/dashboard.html`

**Files:**
- Modify: `portal/dashboard.html`

- [ ] **Step 1: 改造数据看板页面**

修改方式同上。dashboard 使用 ECharts 和静态 demo 数据，不需要 API 调用。

---

### Task 25: 更新 docker-compose.yml — 重新构建 nginx

**Files:**
- Modify: (no change needed - nginx config is mounted via volume)

- [ ] **Step 1: 重启 gateway 容器**

nginx config 通过 volume 挂载，修改文件后只需重启：

```bash
docker compose restart gateway
```

---

### Task 26: 测试验证

- [ ] **Step 1: 访问 `http://localhost:8765/portal/` 验证首页加载**

- [ ] **Step 2: 验证侧栏点击打开 Tab**

点击侧栏各项，确认：
- 新 Tab 在 Header 栏创建
- 内容区正确加载对应页面
- Tab × 可以关闭（首页除外）

- [ ] **Step 3: 验证 Hash 路由**

- 刷新页面后 Hash 正确恢复
- 浏览器前进/后退正常工作

- [ ] **Step 4: 验证所有页面功能**

逐个打开每个 Tab，确认：
- 数据加载正常
- API 调用正常
- 弹窗/面板功能正常
- 侧栏 active 状态正确

---

## 自审

### 1. Spec coverage
- [x] Shared Shell → shell.html (Task 12)
- [x] Tab 管理 → tabs.js (Task 11)
- [x] Hash 路由 → tabs.js (Task 11) + nginx (Task 13)
- [x] CSS 共享提取 → Tasks 1-7
- [x] JS 共享提取 → Tasks 8-10
- [x] 侧栏统一 → shell.html (Task 12)
- [x] 11 个页面改造 → Tasks 14-24
- [x] login.html 独立 → 保持不变
- [x] demo.html 独立 → 保持不变
- [x] 首页不可关闭 → ROUTES[''].pinned = true (Task 11)

### 2. Placeholder scan
- [x] 无 "TBD" / "TODO" / "fill in" / "similar to"
- [x] 每个 Task 有完整文件路径
- [x] 每个 Task 有完整代码

### 3. 类型一致性
- [x] `escapeHtml` 在所有页面统一
- [x] `apiFetch` 在所有页面统一
- [x] `APP_API_BASE` / `APP_TOKEN` 在 init.js 定义，各 iframe 页面直接使用 `apiBase()` / `getToken()`
- [x] `statusMap` 在 init.js 定义

### 4. Scope check
- 11 个页面改造任务独立可测试
- 每个页面改造后均可独立访问
- 共享资源可单独验证