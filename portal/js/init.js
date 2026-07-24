// portal/js/init.js
// Global initialization: auth guard, API base, domain config

function checkAuth() {
  var token = localStorage.getItem('token');
  if (!token) {
    window.location.href = '/portal/login.html';
    return false;
  }
  var user = getUser();
  if (user) {
    var avatar = document.getElementById('userAvatar');
    if (avatar) {
      avatar.textContent = (user.display_name || user.username).charAt(0).toUpperCase();
    }
  }
  return true;
}

function updateAvatar() {
  var user = getUser();
  if (user) {
    var avatar = document.getElementById('userAvatar');
    if (avatar) {
      avatar.textContent = (user.display_name || user.username).charAt(0).toUpperCase();
    }
  }
}

function getUserDisplayName() {
  var user = getUser();
  return user ? (user.display_name || user.username) : '用户';
}

async function loadDomainConfig() {
  try {
    var res = await apiFetch(apiBase() + '/api/domain_config');
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