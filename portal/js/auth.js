// portal/js/auth.js
// Authentication helpers

function getToken() {
  return localStorage.getItem('token');
}

function getUser() {
  try { return JSON.parse(localStorage.getItem('user')); }
  catch(e) { return null; }
}

function getDomainPort() {
  return parseInt(localStorage.getItem('domainPort')) || 8766;
}

// Legacy port -> gateway prefix map (research/sales). Dynamic domains
// (port >= 8770) use their registry gateway_prefix (/d/<slug>) — see
// loadEnabledDomains in shell.html which stores it in localStorage.
var LEGACY_PREFIXES = { 8766: '/research', 8767: '/sales' };

function getDomainPrefix() {
  var port = getDomainPort();
  return localStorage.getItem('domainPrefix') || LEGACY_PREFIXES[port] || '/research';
}

// 网关模式判定：只要页面不是直接开在后端自己的端口上（8766/8767/动态域端口），
// 就认为走 Nginx 网关——API 与页面【同源】，只需拼上域前缀。
// 同源写法对任何网关端口自动生效（80 / 8765 / 8443 / 以后新增的端口都行）。
// 旧实现按端口白名单（8765/80）判定，漏了 HTTPS 网关 8443：PWA 从 8443 打开时，
// API 被拼成 https://host:8766 —— 对明文端口做 TLS 握手，请求永远挂起，
// 表现为"页面能打开、数据永远加载不出来"。
function isDirectBackendPort() {
  return window.location.port === String(getDomainPort());
}

function apiBase() {
  if (isDirectBackendPort()) {
    // 直连后端端口（开发/内网调试）：API 就在本端口，无域前缀
    return window.location.protocol + '//' + window.location.hostname + ':' + getDomainPort();
  }
  // 网关模式：同源 + 域前缀（/research、/sales 或动态域 /d/<slug>）
  return window.location.origin + getDomainPrefix();
}

// System API base (always uses research domain for system-level APIs)
function systemApiBase() {
  if (window.location.port === '8766') {
    return window.location.protocol + '//' + window.location.hostname + ':8766';
  }
  // 网关模式：同源走 /research（CORS 天然兼容）
  return window.location.origin + '/research';
}

var APP_API_BASE = apiBase();

// 在途 GET 请求计数（用于向父窗口发加载信号）
var __inflight = 0;

function _loadingNotify() {
  if (window.parent && window.parent !== window) {
    try {
      window.parent.postMessage({ type: 'qm-loading', loading: __inflight > 0 }, '*');
    } catch (e) {}
  }
}

function apiFetch(url, options) {
  options = options || {};
  options.headers = options.headers || {};
  var token = getToken();
  if (token) {
    // Ensure Content-Type is preserved, then add Authorization
    if (!options.headers['Content-Type'] && !options.headers['content-type']) {
      options.headers['Content-Type'] = 'application/json';
    }
    options.headers['Authorization'] = 'Bearer ' + token;
  }
  // 加载信号：仅 GET（数据拉取）计入在途请求；POST/PUT/DELETE 是用户操作，不触发加载动效
  var isGet = !(options.method && String(options.method).toUpperCase() !== 'GET');
  var p = fetch(url, options);
  if (isGet) __inflight++;
  return p.then(function(response) {
    if (response.status === 401) {
      console.warn('[auth] 401 Unauthorized — redirecting to login');
      doLogout();
    }
    return response;
  }).finally(function() {
    if (isGet) {
      __inflight = Math.max(0, __inflight - 1);
      _loadingNotify();
    }
  });
}

function checkAuth() {
  var token = getToken();
  if (!token) {
    window.location.href = '/portal/login.html';
    return false;
  }
  return true;
}

function doLogout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  window.location.href = '/portal/login.html';
}

function toggleUserMenu() {
  var dd = document.getElementById('userDropdown');
  if (!dd) return;
  if (dd.style.display === 'none') {
    dd.style.display = 'block';
    // Close on outside click
    setTimeout(function() {
      document.addEventListener('click', closeUserMenuOnce);
    }, 0);
  } else {
    dd.style.display = 'none';
    document.removeEventListener('click', closeUserMenuOnce);
  }
}

function closeUserMenuOnce(e) {
  var dd = document.getElementById('userDropdown');
  var av = document.getElementById('userAvatar');
  if (dd && av && !dd.contains(e.target) && !av.contains(e.target)) {
    dd.style.display = 'none';
    document.removeEventListener('click', closeUserMenuOnce);
  }
}

function showSwitchAccountConfirm() {
  closeUserMenuOnce({target: document.body}); // close dropdown
  if (confirm('切换帐号将退出当前登录，是否继续？')) {
    doLogout();
  }
}