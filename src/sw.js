const CACHE_NAME = 'genealogy-pwa-v1';
const ASSETS = [
    '/',
    '/index.html',
    '/main.js',
    '/tree_viewer.js',
    '/manifest.json'
];

self.addEventListener('install', event => {
    // Try to cache listed assets but do not fail installation if some are missing
    event.waitUntil((async () => {
        const cache = await caches.open(CACHE_NAME);
        await Promise.all(ASSETS.map(async (asset) => {
            try {
                const res = await fetch(asset, {cache: 'no-cache'});
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                await cache.put(asset, res.clone());
            } catch (err) {
                // Log and continue — a single missing/404 asset must not block SW install
                console.warn('SW: failed to cache', asset, err && err.message);
            }
        }));
        await self.skipWaiting();
    })());
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
