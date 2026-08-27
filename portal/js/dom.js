// portal/js/dom.js
// DOM utility functions

function escapeHtml(s) {
  if (!s) return '';
  return String(s).replace(/[&<>\"']/g, function(c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
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

// ===== 外链安全打开（情报详情超链接统一走这里）=====
// 规则：情报详情里的超链接一律【不在系统内导航】——
// 先弹出提示告知用户"这是外部链接、将在新标签页打开、会离开当前系统"，
// 用户确认后，用 window.open(..., 'noopener,noreferrer') 在【新标签页】打开。
// 附件（系统自身 API 的文件下载）不属于"外部链接"，不经过此流程。

var _extLinkModal = null;

function _ensureExtLinkModal() {
  if (_extLinkModal) return _extLinkModal;
  var ov = document.createElement('div');
  ov.id = 'extLinkOverlay';
  ov.style.cssText = 'position:fixed;inset:0;z-index:99999;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,0.35)';
  var box = document.createElement('div');
  box.style.cssText = 'background:#fff;border:1px solid var(--gray-200);border-radius:10px;box-shadow:0 12px 40px rgba(0,0,0,0.18);width:440px;max-width:90vw;max-height:80vh;overflow:auto;box-sizing:border-box';
  ov.appendChild(box);
  document.body.appendChild(ov);
  _extLinkModal = { ov: ov, box: box };
  return _extLinkModal;
}

// url: 目标地址；label: 提示标题（如"打开原文链接"）
function openExternalLink(url, label) {
  if (!url) return;
  url = String(url);
  var m = _ensureExtLinkModal();
  var host = url;
  try { host = new URL(url, location.href).host; } catch (e) {}
  var title = label || '即将打开外部链接';

  m.box.innerHTML =
    '<div style="padding:20px">'
    + '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'
    + '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>'
    + '<h3 style="margin:0;font-size:15px;font-weight:600;color:var(--gray-800)">' + escapeHtml(title) + '</h3>'
    + '</div>'
    + '<div style="font-size:13px;color:var(--gray-600);line-height:1.7;margin-bottom:10px">该链接为<strong>外部链接</strong>，将在<strong>新标签页</strong>中打开，会离开当前系统。是否继续？</div>'
    + '<div style="font-size:12px;color:var(--gray-400);word-break:break-all;background:var(--gray-50);border:1px solid var(--gray-200);border-radius:6px;padding:8px 10px;margin-bottom:16px">' + escapeHtml(host) + '</div>'
    + '<div style="display:flex;justify-content:flex-end;gap:8px">'
    + '<button id="extLinkCancel" style="padding:8px 16px;border:1px solid var(--gray-200);background:#fff;border-radius:6px;font-size:13px;color:var(--gray-600);cursor:pointer">取消</button>'
    + '<button id="extLinkOk" style="padding:8px 16px;border:1px solid var(--accent);background:var(--accent);border-radius:6px;font-size:13px;color:#fff;cursor:pointer">在新标签页打开</button>'
    + '</div>'
    + '</div>';
  m.ov.style.display = 'flex';

  var cancel = document.getElementById('extLinkCancel');
  var ok = document.getElementById('extLinkOk');
  var closed = false;
  function close() {
    if (closed) return;
    closed = true;
    m.ov.style.display = 'none';
    if (cancel) cancel.onclick = null;
    if (ok) ok.onclick = null;
    document.removeEventListener('keydown', onKey, true);
  }
  function onKey(e) { if (e.key === 'Escape') { e.stopPropagation(); close(); } }
  document.addEventListener('keydown', onKey, true);
  cancel.onclick = close;
  ok.onclick = function () {
    close();
    window.open(url, '_blank', 'noopener,noreferrer');
  };
}

// 事件委托：拦截所有 a[data-ext="1"] 链接（情报详情里的超链接），
// 阻止其默认行为（避免在系统 iframe 内导航），改走"提示 + 新标签页打开"。
// 幂等——每个页面调用一次即可。
function initExternalLinkGuard() {
  if (document.__extLinkGuard) return;
  document.__extLinkGuard = true;
  document.addEventListener('click', function (e) {
    var t = e.target;
    while (t && t.nodeType !== 1) t = t.parentElement; // 文本节点 → 父元素
    if (!t || !t.closest) return;
    var a = t.closest('a[data-ext="1"]');
    if (!a) return;
    e.preventDefault();
    e.stopPropagation();
    openExternalLink(a.getAttribute('href'), a.getAttribute('data-label'));
  }, true);
}
