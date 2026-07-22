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
  return p + '//' + h + ':' + port;
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
  return fetch(url, options);
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