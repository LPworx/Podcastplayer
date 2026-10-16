const CACHE = 'lps-podcast-v11';
const CORE = ['/', '/index.html', '/manifest.json', '/icon-192.png', '/icon-512.png', '/icon-maskable-512.png', '/apple-touch-icon.png'];
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/audio/')) return; // stream audio from network
  if (url.pathname === '/episodes.json') return; // always fetch the latest episode list
  if (e.request.mode === 'navigate') { // shortcuts open /?action=..., serve the one cached page
    e.respondWith(caches.match('/index.html').then((hit) => hit || fetch(e.request)));
    return;
  }
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      if (e.request.method === 'GET' && res.ok && url.origin === location.origin) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
      }
      return res;
    }).catch(() => caches.match('/index.html')))
  );
});
