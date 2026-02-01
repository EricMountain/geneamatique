// Register service worker for PWA
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(err => console.warn('SW registration failed', err));
}

// Load the in-repo tree_viewer script (we put it in public root so it's available at /tree_viewer.js)
// The legacy ui/tree_viewer.js expects global d3 and ELK and will fetch demo_tree.json itself.
const script = document.createElement('script');
script.src = '/tree_viewer.js';
script.defer = true;
document.body.appendChild(script);
