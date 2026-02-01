// Register service worker for PWA
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(err => console.warn('SW registration failed', err));
}

// Load the public tree viewer script and wire up the search UI to new API endpoints
const script = document.createElement('script');
script.src = '/tree_viewer.js';
script.defer = true;
script.onload = () => {
    // once viewer is loaded, attach UI behaviors
    const input = document.getElementById('person-search');
    const btn = document.getElementById('search-btn');
    const results = document.getElementById('search-results');

    function showResults(list) {
        results.innerHTML = '';
        if (!list || list.length === 0) {
            results.style.display = 'none';
            return;
        }
        list.forEach(item => {
            const el = document.createElement('div');
            el.style.padding = '8px';
            el.style.borderBottom = '1px solid #eee';
            el.style.cursor = 'pointer';
            el.textContent = `${item.canonical_name} (DB:${item.id}${item.family_tree ? ' / ' + item.family_tree : ''}${item.date_of_birth ? ' • ' + item.date_of_birth : ''})`;
            el.onclick = () => {
                results.style.display = 'none';
                input.value = el.textContent;
                fetchTreeFor(item.id);
            };
            results.appendChild(el);
        });
        results.style.display = 'block';
    }

    async function searchIndividuals(q) {
        try {
            const res = await fetch('/api/individuals?q=' + encodeURIComponent(q));
            if (!res.ok) throw new Error(await res.text());
            return await res.json();
        } catch (err) {
            console.warn('Search failed', err);
            return [];
        }
    }

    async function fetchTreeFor(id) {
        const type = document.getElementById('tree-type').value;
        const maxDepth = document.getElementById('max-depth').value || 6;
        try {
            const res = await fetch(`/api/tree?id=${encodeURIComponent(id)}&type=${encodeURIComponent(type)}&max_depth=${encodeURIComponent(maxDepth)}`);
            if (!res.ok) {
                const txt = await res.text();
                window.showTreeError('Server error: ' + txt);
                return;
            }
            const data = await res.json();
            if (!data) {
                window.showTreeError('No tree data returned');
                return;
            }
            window.setTreeRoot(data);
        } catch (err) {
            window.showTreeError('Failed to fetch tree: ' + err.message);
        }
    }

    btn.addEventListener('click', async () => {
        const q = input.value.trim();
        if (!q) return;
        const list = await searchIndividuals(q);
        if (list.length === 1) {
            fetchTreeFor(list[0].id);
        } else {
            showResults(list);
        }
    });

    input.addEventListener('input', async (e) => {
        const q = input.value.trim();
        if (!q) { results.style.display = 'none'; return; }
        const list = await searchIndividuals(q);
        showResults(list);
    });

};

document.body.appendChild(script);
