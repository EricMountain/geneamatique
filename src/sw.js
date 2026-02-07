const CACHE_NAME = 'genealogy-pwa-v1';
const ASSETS = [
    '/',
    '/index.html',
    '/main.js',
    '/tree_viewer.js',
    '/demo_tree.json',
    '/manifest.json'
];

self.addEventListener('install', event => {
    event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS)));
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    const req = event.request;
    const url = new URL(req.url);
    const isNavigation = req.mode === 'navigate' || url.pathname === '/' || url.pathname.endsWith('index.html');
    const isJSOrCSS = url.pathname.endsWith('.js') || url.pathname.endsWith('.css') || url.pathname.endsWith('.map');

    // For navigation and JS/CSS assets use network-first so new builds are served immediately
    if (isNavigation || isJSOrCSS) {
        event.respondWith(
            fetch(req).then(res => {
                // Update cache with fresh response
                const resClone = res.clone();
                caches.open(CACHE_NAME).then(cache => cache.put(req, resClone));
                return res;
            }).catch(() => caches.match(req).then(r => r || caches.match('/index.html')))
        );
        return;
    }

    // Default: cache-first for other static assets
    event.respondWith(caches.match(req).then(r => r || fetch(req)));
});

// Allow clients to tell the worker to activate immediately
self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
