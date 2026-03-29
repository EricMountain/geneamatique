// Register service worker for PWA and enable immediate updates (skipWaiting)
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').then(reg => {
        // If there's already a waiting worker, ask it to activate
        if (reg.waiting) {
            reg.waiting.postMessage({ type: 'SKIP_WAITING' });
        }
        // When a new worker is found, ask it to skip waiting once installed
        reg.addEventListener('updatefound', () => {
            const newWorker = reg.installing;
            if (!newWorker) return;
            newWorker.addEventListener('statechange', () => {
                if (newWorker.state === 'installed') {
                    if (navigator.serviceWorker.controller) {
                        // New update available: ask it to activate immediately
                        newWorker.postMessage({ type: 'SKIP_WAITING' });
                    }
                }
            });
        });
    }).catch(err => console.warn('SW registration failed', err));

    // When the new service worker takes control, reload so we pick up updated assets
    navigator.serviceWorker.addEventListener('controllerchange', () => {
        window.location.reload();
    });
}

// View switcher - toggle between tree and map views
let currentView = 'tree'; // Default to tree view
let currentTreeData = null; // Store current tree data for map view
let mapInitialized = false;
let mapClustering = true; // Whether to cluster markers on the map

const chartContainer = document.getElementById('chart');
const mapContainer = document.getElementById('map-container');
const treeViewBtn = document.getElementById('tree-view-btn');
const mapViewBtn = document.getElementById('map-view-btn');
const clusterToggleBtn = document.getElementById('cluster-toggle-btn');

// Import map viewer module dynamically
let mapViewer = null;
import('./map_viewer.js').then(module => {
    mapViewer = module;
}).catch(err => {
    console.error('Failed to load map viewer module:', err);
});

function switchToTreeView() {
    if (currentView === 'tree') return;

    currentView = 'tree';
    chartContainer.style.display = 'block';
    mapContainer.style.display = 'none';

    // Show map button, hide tree button and cluster toggle
    treeViewBtn.style.display = 'none';
    mapViewBtn.style.display = 'flex';
    if (clusterToggleBtn) clusterToggleBtn.style.display = 'none';
}

function switchToMapView() {
    if (currentView === 'map') return;

    currentView = 'map';
    chartContainer.style.display = 'none';
    mapContainer.style.display = 'block';

    // Show tree button and cluster toggle, hide map button
    treeViewBtn.style.display = 'flex';
    mapViewBtn.style.display = 'none';
    if (clusterToggleBtn) clusterToggleBtn.style.display = 'flex';

    // Initialize map on first switch
    if (!mapInitialized && mapViewer) {
        try {
            mapViewer.initMap('map');
            mapInitialized = true;
        } catch (err) {
            console.error('Failed to initialize map:', err);
            alert('Failed to initialize map. Please check console for errors.');
            switchToTreeView();
            return;
        }
    }

    // Refresh map size after showing container
    if (mapViewer && mapInitialized) {
        mapViewer.refreshMap();

        // If we have tree data, display it on the map
        if (currentTreeData) {
            mapViewer.showEventsOnMap(currentTreeData, { cluster: mapClustering });
        }
    }
}

// Wire up view switcher buttons
if (treeViewBtn) {
    treeViewBtn.addEventListener('click', switchToTreeView);
}
if (mapViewBtn) {
    mapViewBtn.addEventListener('click', switchToMapView);
}
if (clusterToggleBtn) {
    clusterToggleBtn.addEventListener('click', () => {
        mapClustering = !mapClustering;
        clusterToggleBtn.classList.toggle('active', !mapClustering);
        clusterToggleBtn.title = mapClustering ? 'Disable clustering' : 'Enable clustering';
        if (currentView === 'map' && mapViewer && mapInitialized && currentTreeData) {
            mapViewer.showEventsOnMap(currentTreeData, { cluster: mapClustering, preserveView: true });
        }
    });
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

    // --- Authentication helpers (Google Identity Services client-side flow)
    const authConfig = { clientId: null };
    const idTokenKey = 'id_token';

    function setIdToken(token) {
        if (!token) {
            localStorage.removeItem(idTokenKey);
            return;
        }
        localStorage.setItem(idTokenKey, token);
    }
    function getIdToken() {
        return localStorage.getItem(idTokenKey);
    }

    function decodeJwtPayload(jwt) {
        try {
            const b64 = jwt.split('.')[1];
            const padded = b64.padEnd(b64.length + (4 - (b64.length % 4)) % 4, '=');
            const json = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
            return JSON.parse(json);
        } catch (e) {
            return null;
        }
    }

    async function fetchConfig() {
        try {
            const res = await fetch('/api/config');
            if (!res.ok) return {};
            return await res.json();
        } catch (e) { return {}; }
    }

    function isIdTokenValid(token) {
        if (!token) return false;
        const p = decodeJwtPayload(token);
        if (!p) return false;
        if (!p.exp) return false;
        const now = Math.floor(Date.now() / 1000);
        return now < p.exp;
    }

    let pendingPrompt = false;

    // One-time prompt-moment listener helpers (used instead of calling deprecated
    // One-Tap notification status methods). Call `_registerPromptMomentListener`
    // before invoking `google.accounts.id.prompt()` when you need a per-call
    // decision based on the prompt moment.
    let _gsiPromptListeners = [];
    function _registerPromptMomentListener(cb) { _gsiPromptListeners.push(cb); }
    function _dispatchPromptMoment(moment) {
        _gsiPromptListeners.forEach(fn => { try { fn(moment); } catch (e) { /* ignore */ } });
        _gsiPromptListeners = [];
    }

    const loginBtn = document.getElementById('login-btn');
    if (loginBtn) {
        // attach click handler that tries GIS prompt first and falls back to redirect
        loginBtn.addEventListener('click', () => {
            const redirectTo = encodeURIComponent(window.location.pathname + window.location.search || '/');
            const redirectUri = `${window.location.origin}/oauth2callback`;
            const oauthUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${encodeURIComponent(authConfig.clientId || '')}&response_type=code&scope=openid%20email%20profile&redirect_uri=${encodeURIComponent(redirectUri)}&state=${redirectTo}&prompt=select_account`;

            pendingPrompt = true;
            let handled = false;
            // If GIS available, ask it to show prompt and use the global momentListener
            // (we register a one-time listener for this particular click). This avoids
            // calling deprecated `notif.*` status methods which trigger GSI warnings
            // and may be removed when FedCM is mandatory.
            if (window.google && window.google.accounts && window.google.accounts.id) {
                try {
                    _registerPromptMomentListener((moment) => {
                        try {
                            handled = true;
                            const t = (moment && moment.type) || '';
                            if (t === 'display') {
                                // prompt shown — leave flow to GIS
                            } else {
                                // any other moment (skipped / not_displayed / dismissed) -> fallback
                                window.location.href = oauthUrl;
                            }
                        } catch (e) { /* ignore */ }
                    });

                    window.google.accounts.id.prompt();
                } catch (e) {
                    // prompt failed synchronously – fallback
                    handled = true;
                    window.location.href = oauthUrl;
                }
                // After a short timeout, if nothing happened, redirect as fallback
                setTimeout(() => {
                    if (!handled) {
                        window.location.href = oauthUrl;
                    }
                }, 1200);
            } else {
                // GIS not loaded yet – do direct redirect
                window.location.href = oauthUrl;
            }
        });
    }

    function showLoginOnly() {
        document.body.classList.add('auth-required');
        // ensure sign-in UI visible, hide user email
        const loginBtnLocal = document.getElementById('login-btn'); if (loginBtnLocal) loginBtnLocal.style.display = '';
        const out = document.getElementById('user-email'); if (out) out.style.display = 'none';
    }

    function showAppUI() {
        document.body.classList.remove('auth-required');
        // show app components
        const loginBtn = document.getElementById('login-btn'); if (loginBtn) loginBtn.style.display = 'none';
        const out = document.getElementById('user-email'); if (out && out.textContent) out.style.display = 'inline-block';
        const s = document.getElementById('sign-out-btn'); if (s && out && out.textContent) s.style.display = 'inline-block';
    }

    async function initAuth() {
        const cfg = await fetchConfig();

        // Always store the client id so the login button works even after sign-out.
        if (cfg && cfg.google_client_id) {
            authConfig.clientId = cfg.google_client_id;
        }

        // First, probe whether an API key is already present (cookies or header). If so, hide GSI button and show app UI.
        try {
            const res = await fetch('/api/key_status', { credentials: 'include' });
            if (res.ok) {
                const j = await res.json().catch(() => ({}));
                if (j && j.email) showSignedIn(j.email);
                // Cookie-based auth (or API key) is active. Clear any stale
                // localStorage id_token so that authFetch does not send an
                // expired Bearer header that would override the valid cookie.
                setIdToken(null);
                // API key or id_token cookie present and valid — show app UI
                showAppUI();
                return;
            }
        } catch (e) {
            // ignore — proceed to GIS init
        }

        // Check for a locally stored id_token and validate it
        const existing = getIdToken();
        if (existing && isIdTokenValid(existing)) {
            const p = decodeJwtPayload(existing);
            if (p && p.email) {
                showSignedIn(p.email);
                showAppUI();
                return;
            }
        }

        // No API key and no valid id_token -> show login-only UI and initialize GIS if available
        showLoginOnly();

        if (authConfig.clientId) {
            // Load GIS script
            const s = document.createElement('script');
            s.src = 'https://accounts.google.com/gsi/client';
            s.defer = true;
            s.onload = () => {
                // Initialize GIS
                window.google.accounts.id.initialize({
                    client_id: authConfig.clientId,
                    callback: handleCredentialResponse,
                    // Use `momentListener` for One Tap prompt moments (FedCM migration
                    // friendly). Do NOT call deprecated notif.* methods anywhere in
                    // the app — instead use this listener or register one-time
                    // callbacks via `_registerPromptMomentListener` above.
                    momentListener: (moment) => {
                        try {
                            console.debug('[GSI moment]', moment);
                            // dispatch to any one-time listeners (login button flows)
                            _dispatchPromptMoment(moment);
                            const t = (moment && moment.type) || '';
                            if (t === 'not_displayed') {
                                console.warn('GSI not displayed (moment):', moment && moment.reason ? moment.reason : 'not_displayed');
                            } else if (t === 'skipped') {
                                console.warn('GSI skipped moment');
                            }
                        } catch (e) { /* ignore */ }
                    }
                });

                // Make sure the login button is visible and, if user clicked earlier, trigger the prompt now
                const loginBtnLocal = document.getElementById('login-btn');
                if (loginBtnLocal) loginBtnLocal.style.display = '';

                // Prompt (diagnostic / moment events are handled by the initialize() momentListener)
                try {
                    window.google.accounts.id.prompt();
                } catch (e) {
                    /* ignore prompt errors */
                }

                if (pendingPrompt) {
                    try { window.google.accounts.id.prompt(); } catch (e) { /* ignore */ }
                    pendingPrompt = false;
                }
            };
            document.head.appendChild(s);
        }
    }

    function handleCredentialResponse(resp) {
        if (!resp || !resp.credential) return;
        setIdToken(resp.credential);
        const payload = decodeJwtPayload(resp.credential);
        if (payload && payload.email) {
            showSignedIn(payload.email);
        }
        // Show main app UI and re-run initial hydration to fetch last viewed tree
        showAppUI();
        const last = localStorage.getItem('last_db_id');
        if (last) {
            try { fetchTreeFor(last); } catch (e) { /* ignore */ }
        }
    }

    function showSignedIn(email) {
        const out = document.getElementById('user-email');
        out.textContent = email;
        out.style.display = 'inline-block';
        // hide the login button to avoid double sign-in
        const loginBtn = document.getElementById('login-btn'); if (loginBtn) loginBtn.style.display = 'none';
    }

    function showSignedOut() {
        const out = document.getElementById('user-email');
        const signOut = document.getElementById('sign-out-btn');
        out.textContent = '';
        out.style.display = 'none';
        signOut.style.display = 'none';
        const loginBtn = document.getElementById('login-btn'); if (loginBtn) loginBtn.style.display = '';
    }

    // Make the user email label act as the sign-out control (app-only sign-out)
    const userEmailEl = document.getElementById('user-email');
    if (userEmailEl) {
        userEmailEl.addEventListener('click', async (e) => {
            const email = userEmailEl.textContent || '';
            if (!email) return;
            const ok = confirm(`Sign out of this app as ${email}?`);
            if (!ok) return;
            // Clear server-side HttpOnly id_token cookie
            try { await fetch('/api/logout', { credentials: 'include' }); } catch (err) { /* ignore */ }
            // Clear client-side state
            setIdToken(null);
            try { localStorage.removeItem('last_db_id'); } catch (err) { /* ignore */ }
            showLoginOnly();
        });
    }

    // Show a short status message under the login button (for diagnostic / user hints)

    // Auth-aware fetch wrapper
    async function authFetch(url, opts) {
        opts = opts || {};
        opts.headers = opts.headers || {};
        // ensure cookies (api_key cookie) are sent to the API
        opts.credentials = opts.credentials || 'include';
        const token = getIdToken();
        if (token) opts.headers['Authorization'] = 'Bearer ' + token;
        const res = await fetch(url, opts);
        if (res.status === 401) {
            // token may be invalid/expired — clear and prompt sign-in
            setIdToken(null);
            showSignedOut();

            if (window.google && window.google.accounts && window.google.accounts.id) {
                window.google.accounts.id.prompt();
            }
        }
        return res;
    }

    // Initialize client-side auth
    initAuth();

    // Small metadata display (response times, DB stats) — add to view-switcher button group
    const viewSwitcher = document.getElementById('view-switcher');
    let chartMeta = document.getElementById('chart-meta');
    if (!chartMeta) {
        chartMeta = document.createElement('div');
        chartMeta.id = 'chart-meta';
        chartMeta.style.display = 'none';
        chartMeta.classList.add('collapsed');
        chartMeta.dataset.expanded = 'false';
        // Toggle expand/collapse on click
        chartMeta.addEventListener('click', (e) => {
            const expanded = chartMeta.dataset.expanded === 'true';
            const next = expanded ? 'false' : 'true';
            chartMeta.dataset.expanded = next;
            chartMeta.classList.toggle('expanded', next === 'true');
            chartMeta.classList.toggle('collapsed', next !== 'true');
            if (chartMeta._meta) {
                renderChartMeta(chartMeta._meta, next === 'true');
            }
            e.stopPropagation();
        });

        // Helper to render (collapsed or expanded)
        const round = (v) => (Number(v).toFixed && Number(v).toFixed(3)) ? Number(v.toFixed(3)) : v;

        // Prefer explicit matchMedia checks, fallback to body class. Also observe body class changes.
        const isDarkMode = () => {
            try {
                if (window.matchMedia) {
                    const mqDark = window.matchMedia('(prefers-color-scheme: dark)');
                    const mqLight = window.matchMedia('(prefers-color-scheme: light)');
                    if (mqDark.matches) return true;
                    if (mqLight.matches) return false;
                }
            } catch (e) { /* ignore */ }
            return document.body && document.body.classList && document.body.classList.contains('dark');
        };

        // No runtime color application here; CSS handles light/dark styles. This function remains for backward compatibility if needed.
        const applyColorScheme = () => { /* noop — CSS handles scheme */ };

        const renderChartMeta = (meta, expanded) => {
            chartMeta._meta = meta;
            applyColorScheme();
            if (!meta) {
                chartMeta.style.display = 'none';
                return;
            }
            chartMeta.style.display = 'flex';

            if (!expanded) {
                // collapsed: icon-only compact badge
                chartMeta.innerHTML = `⏱`;
            } else {
                // expanded: show full metrics (no helper text)
                const db = meta.db_time_ms || {};
                // Build prepared statement metrics display as a table (one row per statement with all metrics)
                let stmtHtml = '';
                if (meta.prepared_statement_metrics) {
                    // Make the container responsive and allow it to expand up to viewport width
                    // Add bottom margin/padding so scrollbars don't overlap content
                    stmtHtml = `
                        <div style="overflow:auto; margin-top:6px; padding-bottom:12px; margin-bottom:6px; max-width:100%; max-height:60vh;">
                          <table style="min-width:1200px; font-size:11px; border-collapse:collapse; width:100%">
                            <thead><tr style="color:var(--meta-muted,#666); text-align:left">
                              <th style="padding:4px 6px; white-space:nowrap">statement</th>
                              <th style="padding:4px 6px; white-space:nowrap">count</th>
                              <th style="padding:4px 6px; white-space:nowrap">total ms</th>
                              <th style="padding:4px 6px; white-space:nowrap">min</th>
                              <th style="padding:4px 6px; white-space:nowrap">max</th>
                              <th style="padding:4px 6px; white-space:nowrap">avg</th>
                              <th style="padding:4px 6px; white-space:nowrap">std</th>
                            </tr></thead>
                            <tbody>
                              ${Object.entries(meta.prepared_statement_metrics).map(([k, m]) => `
                                <tr>
                                  <td style="padding:3px 6px; white-space:nowrap"><strong>${k}</strong></td>
                                  <td style="padding:3px 6px; white-space:nowrap">${m.count}</td>
                                  <td style="padding:3px 6px; white-space:nowrap">${round(m.total_ms)}</td>
                                  <td style="padding:3px 6px; white-space:nowrap">${m.min}</td>
                                  <td style="padding:3px 6px; white-space:nowrap">${m.max}</td>
                                  <td style="padding:3px 6px; white-space:nowrap">${m.avg}</td>
                                  <td style="padding:3px 6px; white-space:nowrap">${m.stddev}</td>
                                </tr>`).join('')}
                            </tbody>
                          </table>
                        </div>
                    `;
                } else {
                    stmtHtml = '<div style="font-size:11px; margin-top:6px; color:var(--meta-muted,#666)">No statement metrics available</div>';
                }
                chartMeta.innerHTML = `
                    <div style="font-weight:600; margin-bottom:6px;">⏱ ${round(meta.response_time_ms)}ms — ${meta.db_queries} DB queries</div>
                    <div style="font-size:11px; color:var(--meta-muted, #555); line-height:1.3">
                        DB time (ms): min <strong>${db.min}</strong>&nbsp; max <strong>${db.max}</strong>&nbsp; avg <strong>${db.avg}</strong>&nbsp; std <strong>${db.stddev}</strong><br/>
                        Parents cache: hits <strong>${meta.parents_cache.hits}</strong> / misses <strong>${meta.parents_cache.misses}</strong>
                    </div>
                    ${stmtHtml}
                `;
            }
        };

        // expose renderer so we can call it later when receiving data
        chartMeta.renderChartMeta = renderChartMeta;

        // Append to view-switcher instead of chart
        viewSwitcher.appendChild(chartMeta);
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
                // We deliberately pass only the db id; the server ignores any family_tree parameter and traces ancestry across all sources
                fetchTreeFor(item.id);
            };
            results.appendChild(el);
        });
        results.style.display = 'block';
    }

    async function searchIndividuals(q) {
        setSearchLoading(true);
        try {
            const res = await authFetch('/api/individuals?q=' + encodeURIComponent(q));
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
            const res = await authFetch(`/api/tree?id=${encodeURIComponent(id)}`);
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
            // Backwards compatible: if the server returns { tree, meta } unwrap it
            const root = (data && data.tree) ? data.tree : data;
            window.setTreeRoot(root);

            // Store tree data for map view
            currentTreeData = root;

            // If currently in map view, update the map
            if (currentView === 'map' && mapViewer && mapInitialized) {
                mapViewer.showEventsOnMap(currentTreeData);
            }

            // Expose metadata for debugging / display (collapsed by default)
            if (data && data.meta) {
                window.latestTreeMeta = data.meta;
                // default to collapsed view on new response
                chartMeta.dataset.expanded = 'false';
                if (chartMeta.renderChartMeta) chartMeta.renderChartMeta(data.meta, false);
            } else {
                if (chartMeta.renderChartMeta) chartMeta.renderChartMeta(null, false);
            }

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

    async function searchAndHandle(q) {
        if (!q) return;
        const list = await searchIndividuals(q);
        if (list.length === 1) {
            fetchTreeFor(list[0].id);
        } else if (list.length === 0) {
            showNoMatches(q);
        } else {
            showResults(list);
        }
    }

    btn.addEventListener('click', async () => {
        await searchAndHandle(input.value.trim());
    });

    input.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            await searchAndHandle(input.value.trim());
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
