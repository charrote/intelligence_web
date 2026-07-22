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