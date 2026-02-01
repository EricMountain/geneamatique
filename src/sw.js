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
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', event => {
    event.respondWith(caches.match(event.request).then(r => r || fetch(event.request)));
});
