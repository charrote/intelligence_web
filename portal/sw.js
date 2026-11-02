/* 业务情报社 PWA service worker
 * 目标：秒开 + 断网可打开外壳；数据接口永远走网络、绝不缓存。
 * 策略：静态资源/页面 = 网络优先，失败回退缓存（保持"改完即生效"）；
 *       /api/ /s/ /sales/ = 只走网络。
 */
const CACHE = 'intel-pwa-v5';  // UA107: 登录页改版（验证码登录/忘记密码），强制换缓存
const PRECACHE = [
  '/portal/shell.html',
  '/portal/login.html',
  '/portal/manifest.json',
  '/portal/icons/icon-192.png',
  '/portal/icons/icon-512.png',
  '/portal/icons/apple-touch-icon.png',
  '/portal/css/variables.css',
  '/portal/css/reset.css',
  '/portal/css/header.css',
  '/portal/css/sidebar.css',
  '/portal/css/layout.css',
  '/portal/css/components.css',
  '/portal/css/responsive.css',
  '/portal/js/dom.js',
  '/portal/js/auth.js',
  '/portal/js/init.js',
  '/portal/js/tabs.js'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// 绝不缓存的路径：API、分享页、销售域接口
// 网关模式下 API 带域前缀（/research/api/、/sales/api/、/d/<slug>/api/），
// 必须一并列入，否则 API 响应会被写进 Cache Storage。
const NETWORK_ONLY = [/^\/api\//, /^\/s\//, /^\/sales\/api\//, /^\/_auth/,
                      /^\/(research|sales)\/api\//, /^\/d\/[^/]+\/api\//];

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (NETWORK_ONLY.some((re) => re.test(url.pathname))) return;

  const sameOrigin = url.origin === self.location.origin;
  if (!sameOrigin && !/cdn\.(jsdelivr|unpkg)\.net$/.test(url.hostname)) return;

  // 网络优先，失败回退缓存（离线也能打开外壳与已访问过的页面）
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.ok && (sameOrigin || /cdn\.jsdelivr\.net$/.test(url.hostname))) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() =>
        caches.match(req).then((hit) => {
          if (hit) return hit;
          // 离线导航回退到外壳
          if (req.mode === 'navigate') {
            return caches.match('/portal/shell.html').then((shell) =>
              shell || new Response('离线且无缓存', { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } })
            );
          }
          return Response.error();
        })
      )
  );
});
