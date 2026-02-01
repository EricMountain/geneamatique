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
    
    // Create lightweight spinner elements (added to DOM if not present)
    let searchSpinner = document.getElementById('search-spinner');
    if (!searchSpinner) {
        searchSpinner = document.createElement('span');
        searchSpinner.id = 'search-spinner';
        searchSpinner.className = 'spinner';
        searchSpinner.style.display = 'none';
        btn.parentNode.insertBefore(searchSpinner, btn.nextSibling);
    }

    let chartSpinner = document.getElementById('chart-spinner');
    const chart = document.getElementById('chart');
    if (!chartSpinner) {
        chartSpinner = document.createElement('div');
        chartSpinner.id = 'chart-spinner';
        chartSpinner.className = 'chart-spinner';
        chartSpinner.style.display = 'none';
        chartSpinner.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px"></span><span>Loading…</span>';
        chart.appendChild(chartSpinner);
    }

    function setSearchLoading(loading) {
        if (loading) {
            searchSpinner.style.display = 'inline-block';
            btn.disabled = true;
        } else {
            searchSpinner.style.display = 'none';
            btn.disabled = false;
        }
    }

    function setChartLoading(loading) {
        if (loading) {
            chartSpinner.style.display = 'flex';
            // also hide results to reduce flicker
            results.style.display = 'none';
            btn.disabled = true;
            input.disabled = true;
        } else {
            chartSpinner.style.display = 'none';
            btn.disabled = false;
            input.disabled = false;
        }
    }

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
            // Do not show family_tree information here — keep results focused on the canonical individual
            el.textContent = `${item.canonical_name} (DB:${item.id}${item.date_of_birth ? ' • ' + item.date_of_birth : ''})`;
            el.onclick = () => {
                results.style.display = 'none';
                input.value = item.canonical_name;
                // We deliberately pass only the db id; the server will pick an instance if family_tree is not supplied
                fetchTreeFor(item.id);
            };
            results.appendChild(el);
        });
        results.style.display = 'block';
    }

    async function searchIndividuals(q) {
        setSearchLoading(true);
        try {
            const res = await fetch('/api/individuals?q=' + encodeURIComponent(q));
            if (!res.ok) throw new Error(await res.text());
            return await res.json();
        } catch (err) {
            console.warn('Search failed', err);
            return [];
        } finally {
            setSearchLoading(false);
        }
    }

    async function fetchTreeFor(id) {
        setChartLoading(true);
        try {
            // API now serves only ancestor trees; no type or max_depth query params
            const res = await fetch(`/api/tree?id=${encodeURIComponent(id)}`);
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
            // Persist last successful id so we can rehydrate the last view on reload
            try {
                localStorage.setItem('last_db_id', String(id));
            } catch (err) {
                // ignore storage errors (e.g., private mode)
            }
        } catch (err) {
            window.showTreeError('Failed to fetch tree: ' + err.message);
        } finally {
            setChartLoading(false);
        }
    }

    btn.addEventListener('click', async () => {
        const q = input.value.trim();
        if (!q) return;
        const list = await searchIndividuals(q);
        if (list.length === 1) {
            fetchTreeFor(list[0].id);
        } else if (list.length === 0) {
            showNoMatches(q);
        } else {
            showResults(list);
        }
    });

    input.addEventListener('input', async (e) => {
        const q = input.value.trim();
        if (!q) { results.style.display = 'none'; return; }
        const list = await searchIndividuals(q);
        if (list.length === 0) {
            showNoMatches(q);
        } else {
            showResults(list);
        }
    });

    // Show friendly UI when no matches are found for a query. Also offer "Show similar" suggestions
    async function showNoMatches(q) {
        results.innerHTML = '';
        const msg = document.createElement('div');
        msg.style.padding = '12px';
        msg.style.color = '#555';
        msg.innerHTML = `<div style="font-weight:600; margin-bottom:6px;">No matches found for “${q}”.</div>`;

        const tips = document.createElement('div');
        tips.style.marginBottom = '8px';
        tips.style.fontSize = '13px';
        tips.innerHTML = `Try adjusting the name, searching by ID, or click <strong>Show similar</strong> to see close matches.`;
        msg.appendChild(tips);

        const actions = document.createElement('div');
        actions.style.display = 'flex';
        actions.style.gap = '8px';

        const btnSimilar = document.createElement('button');
        btnSimilar.textContent = 'Show similar';
        btnSimilar.onclick = async () => {
            btnSimilar.disabled = true;
            btnSimilar.textContent = 'Searching...';
            const suggestions = await gatherSimilar(q);
            btnSimilar.disabled = false;
            btnSimilar.textContent = 'Show similar';
            if (suggestions && suggestions.length) {
                showResults(suggestions);
            } else {
                results.innerHTML = '';
                const none = document.createElement('div');
                none.style.padding = '12px';
                none.textContent = 'No similar matches found.';
                results.appendChild(none);
                results.style.display = 'block';
            }
        };
        actions.appendChild(btnSimilar);

        const btnById = document.createElement('button');
        btnById.textContent = 'Search by ID';
        btnById.onclick = async () => {
            const id = prompt('Enter the DB id to fetch:');
            if (!id) return;
            fetchTreeFor(id);
            results.style.display = 'none';
        };
        actions.appendChild(btnById);

        const btnClear = document.createElement('button');
        btnClear.textContent = 'Clear';
        btnClear.onclick = () => {
            input.value = '';
            input.focus();
            results.style.display = 'none';
        };
        actions.appendChild(btnClear);

        msg.appendChild(actions);
        results.appendChild(msg);
        results.style.display = 'block';
    }

    // Attempt to find similar matches by tokenizing the query and searching tokens individually
    async function gatherSimilar(q) {
        const tokens = q.split(/\s+/).filter(Boolean);
        const seen = new Map();
        for (const t of tokens) {
            try {
                const sub = await searchIndividuals(t);
                sub.forEach(it => {
                    if (!seen.has(it.id)) seen.set(it.id, it);
                });
            } catch (err) {
                // ignore token errors
            }
        }
        // Also try fuzzy single-character edits (simple heuristic): drop one character and search
        if (tokens.length === 1 && tokens[0].length > 3) {
            const s = tokens[0];
            for (let i = 0; i < Math.min(3, s.length - 2); i++) {
                const edit = s.slice(0, i) + s.slice(i + 1);
                try {
                    const sub = await searchIndividuals(edit);
                    sub.forEach(it => { if (!seen.has(it.id)) seen.set(it.id, it); });
                } catch (err) { }
            }
        }
        return Array.from(seen.values()).slice(0, 50);
    }

    // If the input had a value on page load, run the search automatically. If it matches one
    // record, fetch and display the tree; if multiple, show the results; if none, show the
    // friendly "no matches" UI. Also, if no input is provided but a last-db-id was stored,
    // rehydrate the last view automatically.
    (async () => {
        const initialQ = input.value.trim();
        if (initialQ) {
            const list = await searchIndividuals(initialQ);
            if (list.length === 1) {
                fetchTreeFor(list[0].id);
            } else if (list.length === 0) {
                showNoMatches(initialQ);
            } else {
                showResults(list);
            }
        } else {
            const last = localStorage.getItem('last_db_id');
            if (last) {
                try {
                    fetchTreeFor(last);
                } catch (err) {
                    // ignore
                }
            }
        }
    })();

};

document.body.appendChild(script);
