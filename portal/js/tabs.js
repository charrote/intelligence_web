// portal/js/tabs.js
// Tab management and hash routing

var ROUTES = {
  'home': { page: 'home.html', label: '工作台', pinned: true },
  '': { page: 'index.html', label: '情报列表' },
  'dashboard': { page: 'dashboard.html', label: '数据看板' },
  'datasources': { page: 'datasources.html', label: '数据源管理' },
  'target_types': { page: 'target_types.html', label: '目标类型' },
  'projects': { page: 'projects.html', label: '采集项目' },
  'analyst': { page: 'analyst.html', label: 'AI 分析师' },
  'intel-extract': { page: 'intel-extract.html', label: '抽取规则' },
  'reports': { page: 'reports.html', label: '报告模板' },
  'report-view': { page: 'report-view.html', label: '查看报告' },
  'users': { page: 'users.html', label: '用户管理' },
  'roles': { page: 'roles.html', label: '角色管理' },
  'import': { page: 'import.html', label: '批量导入' },
  'audit': { page: 'audit.html', label: '操作日志' },
  'settings': { page: 'settings.html', label: '个人设置' },
  'sys-settings': { page: 'settings.html', label: '系统设置' },
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
  updateBreadcrumb(hash);
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
  updateBreadcrumb(getHash());
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
    return;
  }

  var tab = TABS.find(function(t) { return t.id === tabId; });
  if (!tab) return;

  // Activate tab bar item
  var tabItem = document.querySelector('.tab[data-tab-id="' + tabId + '"]');
  if (tabItem) tabItem.classList.add('active');

  // Update hash
  window.location.hash = tab.hash;

  // Always recreate iframe to avoid stale cache (force fresh load)
  var mainEl = document.getElementById('tabContent');
  if (mainEl) {
    // Remove old iframe if exists
    if (tab.iframe && tab.iframe.parentNode) {
      tab.iframe.parentNode.removeChild(tab.iframe);
    }
    var iframe = document.createElement('iframe');
    var cacheBust = '?_=' + Date.now();
    iframe.src = tab.page + cacheBust;
    iframe.style.width = '100%';
    iframe.style.height = '100%';
    iframe.style.border = 'none';
    iframe.style.display = 'block';
    mainEl.innerHTML = '';
    mainEl.appendChild(iframe);
    tab.iframe = iframe;

    // 加载动效：iframe 未加载完 或 数据请求在途 时显示
    _tabIframeLoaded = false;
    _tabDataLoading = false;
    _showTabLoading(true);
    var onIframeLoad = function () {
      _tabIframeLoaded = true;
      _updateTabLoading();
    };
    iframe.addEventListener('load', onIframeLoad);
    // 兜底：若 load 永不触发（离线/被拦截），15s 后强制收起
    setTimeout(function () { _tabIframeLoaded = true; _updateTabLoading(); }, 15000);
  }
}

// ---- 加载动效状态机（由 tabs.js + shell postMessage 信号共同驱动） ----
var _tabIframeLoaded = true;   // 当前 iframe 是否已加载完
var _tabDataLoading = false;   // 是否还有数据请求在途
var _tabLoadingTimer = null;

function _updateTabLoading() {
  _showTabLoading(!(_tabIframeLoaded && !_tabDataLoading));
}

function _showTabLoading(show) {
  var overlay = document.getElementById('tabLoading');
  if (!overlay) return;
  if (show) {
    // 最小展示时长 120ms，避免快速切换时闪现
    clearTimeout(_tabLoadingTimer);
    overlay.classList.remove('hidden');
    overlay.style.display = 'flex';
  } else {
    clearTimeout(_tabLoadingTimer);
    _tabLoadingTimer = setTimeout(function () {
      overlay.classList.add('hidden');
      setTimeout(function () { if (overlay) overlay.style.display = 'none'; }, 260);
    }, 120);
  }
}

// 监听子页面（iframe 内 auth.js 的 apiFetch）发来的数据加载信号
if (typeof window !== 'undefined') {
  window.addEventListener('message', function (e) {
    var d = e.data;
    if (!d || d.type !== 'qm-loading') return;
    _tabDataLoading = !!d.loading;
    _updateTabLoading();
  });
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

  bar.innerHTML = html;
}

function updateBreadcrumb(hash) {
  var bc = document.getElementById('breadcrumb');
  if (!bc) return;
  var currentLabel = '工作台';
  if (hash && ROUTES[hash]) {
    currentLabel = ROUTES[hash].label;
  }
  if (hash === 'home') {
    bc.innerHTML = '<a href="#" onclick="openTab(\'home\');return false;">工作台</a>';
  } else {
    bc.innerHTML = '<a href="#" onclick="openTab(\'home\');return false;">工作台</a><span class="sep">&gt;</span>' + escapeHtml(currentLabel);
  }
}

function initTabs() {
  // Listen for hash changes
  window.addEventListener('hashchange', function() {
    var hash = getHash();
    setActiveSidebar(hash);
    updateBreadcrumb(hash);
    var existing = TABS.find(function(t) { return t.hash === hash; });
    if (existing) {
      switchToTab(existing.id);
    } else if (ROUTES[hash]) {
      openTab(hash);
    }
  });

  // Initial load — 默认落在工作台
  var initialHash = getHash();
  if (initialHash && ROUTES[initialHash]) {
    openTab(initialHash);
  } else {
    openTab('home');
  }
}