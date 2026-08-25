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
  var d = new Date(iso);
  if (isNaN(d)) return iso;
  return (d.getMonth()+1)+'月'+d.getDate()+'日';
}

// ===== 未读/已读（本地浏览器缓存，同源 iframe 共享）=====
// 存 {id: 标记时间戳}；点开详情即标记已读；列表已读标题颜色浅一档
var READ_KEY = 'intel_read_ids';

function getReadMap() {
  try { return JSON.parse(localStorage.getItem(READ_KEY)) || {}; }
  catch (e) { return {}; }
}

function isRead(id) {
  return !!getReadMap()[id];
}

function markRead(id) {
  if (id == null) return;
  var m = getReadMap();
  if (m[id]) return;
  m[id] = Date.now();
  try { localStorage.setItem(READ_KEY, JSON.stringify(m)); } catch (e) {}
}