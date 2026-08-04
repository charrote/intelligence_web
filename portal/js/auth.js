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

function apiBase() {
  var p = window.location.protocol;
  var h = window.location.hostname;
  var port = getDomainPort();
  var locPort = window.location.port;
  // When accessed via Nginx gateway (port 8765 or default HTTP port with correct host),
  // prepend domain path prefix for correct API routing through gateway.
  var isGateway = (locPort === '8765' || locPort === '');
  if (isGateway) {
    var gwPort = locPort ? ':' + locPort : '';
    if (port === 8767) {
      return p + '//' + h + gwPort + '/sales';
    }
    return p + '//' + h + gwPort + '/research';
  }
  return p + '//' + h + ':' + port;
}

// System API base (always uses research domain for system-level APIs)
function systemApiBase() {
  var p = window.location.protocol;
  var h = window.location.hostname;
  var locPort = window.location.port;
  // When accessed via Nginx gateway (port 8765 or default HTTP port),
  // route through gateway for CORS compatibility
  var isGateway = (locPort === '8765' || locPort === '');
  if (isGateway) {
    var gwPort = locPort ? ':' + locPort : '';
    return p + '//' + h + gwPort + '/research';
  }
  return p + '//' + h + ':8766';
}

var APP_API_BASE = apiBase();

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
  return fetch(url, options).then(function(response) {
    if (response.status === 401) {
      console.warn('[auth] 401 Unauthorized — redirecting to login');
      doLogout();
    }
    return response;
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