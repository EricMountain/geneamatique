const { DynamoDBClient, GetItemCommand } = require('@aws-sdk/client-dynamodb');
let OAuth2Client = null;
try {
    OAuth2Client = require('google-auth-library').OAuth2Client;
} catch (err) {
    console.warn('google-auth-library not available; Google OAuth verification will be disabled in local runs');
}
const fs = require('fs').promises;
const path = require('path');
const mime = require('mime-types');
const sqlite3 = (() => {
    try {
        return require('sqlite3').verbose();
    } catch (err) {
        console.warn('sqlite3 not available; api endpoints will return errors until sqlite3 is installed');
        return null;
    }
})();

const DB_PATH = process.env.GENEALOGY_DB || path.join(__dirname, 'dist', 'data', 'genealogy.db');

const TABLE = process.env.API_KEYS_TABLE; // legacy api-key table
const ALLOWED_USERS_TABLE = process.env.ALLOWED_USERS_TABLE; // DynamoDB table that contains allowed Google user emails (partition key: "email")
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID; // Google OAuth Client ID used to validate ID tokens
const dynamo = new DynamoDBClient({});

// Safety: prevent LOCAL_DEV mode from being enabled in production Lambda environments.
// This protects against accidentally deploying with authentication disabled.
if (process.env.LOCAL_DEV === '1' && process.env.AWS_LAMBDA_FUNCTION_NAME) {
    console.error('LOCAL_DEV must not be set in production Lambda environment');
    throw new Error('LOCAL_DEV must not be set in production Lambda environment');
}

function corsHeaders() {
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,x-api-key,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    };
}

async function checkApiKey(key) {
    if (!TABLE) return false;
    try {
        const command = new GetItemCommand({
            TableName: TABLE,
            Key: { api_key: { S: key } }
        });
        const res = await dynamo.send(command);
        return !!res.Item;
    } catch (err) {
        console.error('DynamoDB error', err);
        return false;
    }
}

const COOKIE_NAME = 'api_key';
const COOKIE_MAX_AGE = 400 * 24 * 60 * 60; // 400 days in seconds

function getApiKeyFromHeaders(headers) {
    if (!headers) return null;
    const x = headers['x-api-key'] || headers['X-API-Key'] || headers['authorization'] || headers['Authorization'];
    if (!x) return null;
    if (x.startsWith('ApiKey ')) return x.slice('ApiKey '.length);
    return x;
}

function getApiKeyFromCookies(headers) {
    if (!headers) return null;
    const cookieHeader = headers.cookie || headers.Cookie || headers.COOKIE;
    if (!cookieHeader) return null;
    const pairs = cookieHeader.split(/;\s*/);
    for (const p of pairs) {
        const [name, ...rest] = p.split('=');
        if (!name) continue;
        if (name.trim() === COOKIE_NAME) {
            return rest.join('=').trim();
        }
    }
    return null;
}

function getApiKeyFromQuery(event) {
    // Lambda Function URL events may include queryStringParameters
    if (event.queryStringParameters && event.queryStringParameters.api_key) return event.queryStringParameters.api_key;
    // Fallback to rawQueryString if provided
    if (event.rawQueryString) {
        const params = new URLSearchParams(event.rawQueryString);
        if (params.has('api_key')) return params.get('api_key');
    }
    return null;
}

function makeSetCookieHeader(key) {
    // HttpOnly for security; Secure when served over HTTPS (Function URL is HTTPS)
    // Using SameSite=Lax to allow simple navigation while providing CSRF protection
    return `${COOKIE_NAME}=${key}; Max-Age=${COOKIE_MAX_AGE}; Path=/; SameSite=Lax; Secure; HttpOnly`;
}

function normalizePath(event) {
    // function url events use rawPath, API GW may use path
    return (event.rawPath || event.path || '/');
}

exports.handler = async function (event) {
    const reqPath = normalizePath(event);
    const headers = event.headers || {};
    const method = event.requestContext?.http?.method || event.httpMethod || 'GET';

    // Allow simple preflight
    if (method === 'OPTIONS') {
        return { statusCode: 204, headers: { ...corsHeaders() }, body: '' };
    }

    // allow unauthenticated access to icons and favicon
    let unauthenticated = reqPath === '/favicon.ico' || reqPath.startsWith('/icons') || reqPath.endsWith('.png') || reqPath.endsWith('.ico') || reqPath.startsWith('/assets/icons');

    // In local dev, allow un-authenticated access to /api/* for convenience (set LOCAL_DEV=1)
    if (process.env.LOCAL_DEV === '1') {
        if (reqPath.startsWith('/api/')) unauthenticated = true;
    }

    let setCookieHeader = null;

    if (!unauthenticated) {
        // If an Authorization: Bearer <id_token> header is present, prefer Google OAuth verification
        const getBearerToken = (headers) => {
            if (!headers) return null;
            const a = headers['authorization'] || headers['Authorization'] || headers['AUTHORIZATION'];
            if (!a) return null;
            if (a.startsWith('Bearer ')) return a.slice('Bearer '.length).trim();
            return null;
        };

        const verifyGoogleIdToken = async (idToken) => {
            if (!OAuth2Client) throw new Error('google-auth-library not installed');
            if (!GOOGLE_CLIENT_ID) throw new Error('GOOGLE_CLIENT_ID not configured');
            const client = new OAuth2Client(GOOGLE_CLIENT_ID);
            const ticket = await client.verifyIdToken({ idToken, audience: GOOGLE_CLIENT_ID });
            return ticket.getPayload();
        };

        const checkAllowedUser = async (email) => {
            if (!ALLOWED_USERS_TABLE) return false;
            try {
                const command = new GetItemCommand({ TableName: ALLOWED_USERS_TABLE, Key: { email: { S: email } } });
                const res = await dynamo.send(command);
                return !!res.Item;
            } catch (err) {
                console.error('DynamoDB error (allowed users)', err);
                return false;
            }
        };

        const bearer = getBearerToken(headers);
        if (bearer) {
            try {
                const payload = await verifyGoogleIdToken(bearer);
                const email = payload && payload.email && String(payload.email).toLowerCase();
                if (!email) return { statusCode: 403, headers: corsHeaders(), body: 'Invalid token: no email' };
                const allowed = await checkAllowedUser(email);
                if (!allowed) return { statusCode: 403, headers: corsHeaders(), body: 'Unauthorized user' };
                // authenticated via Google; continue
            } catch (err) {
                console.error('Google auth error', err);
                return { statusCode: 401, headers: corsHeaders(), body: 'Invalid or expired token' };
            }
        } else {
            // fallback to API key behavior for backwards compatibility
            const headerKey = getApiKeyFromHeaders(headers);
            const cookieKey = getApiKeyFromCookies(headers);
            const queryKey = getApiKeyFromQuery(event);

            const key = headerKey || cookieKey || queryKey;

            if (!key) return { statusCode: 401, headers: corsHeaders(), body: 'Missing API key or Authorization token' };

            const ok = await checkApiKey(key);
            if (!ok) return { statusCode: 403, headers: corsHeaders(), body: 'Invalid API key' };

            // If the client provided the key via query param and there is no cookie, set a cookie so future requests are authenticated
            if (queryKey && !cookieKey) {
                setCookieHeader = makeSetCookieHeader(key);
            }
        }
    }

    // API endpoints under /api/*
    if (reqPath.startsWith('/api/')) {
        // Basic JSON helpers
        const jsonHeaders = { 'Content-Type': 'application/json', ...corsHeaders() };

        if (!sqlite3) {
            return { statusCode: 500, headers: jsonHeaders, body: JSON.stringify({ error: 'sqlite3 not installed on this build' }) };
        }

        const dbOpen = () => new sqlite3.Database(DB_PATH, sqlite3.OPEN_READONLY);
        const dbAll = (db, sql, params) => new Promise((resolve, reject) => db.all(sql, params || [], (err, rows) => err ? reject(err) : resolve(rows)));
        const dbGet = (db, sql, params) => new Promise((resolve, reject) => db.get(sql, params || [], (err, row) => err ? reject(err) : resolve(row)));

        // GET /api/individuals?q=...  -- simple search
        if (reqPath.startsWith('/api/individuals')) {
            const q = (event.queryStringParameters && event.queryStringParameters.q) || '';
            const db = dbOpen();
            try {
                let rows;
                // Simple distinct individuals list that queries only the individuals table
                if (!q) {
                    rows = await dbAll(db, `SELECT id, canonical_name, name_comment, date_of_birth FROM individuals ORDER BY canonical_name LIMIT 100`, []);
                } else {
                    const maybeId = parseInt(q, 10);
                    if (!isNaN(maybeId)) {
                        rows = await dbAll(db, `SELECT id, canonical_name, name_comment, date_of_birth FROM individuals WHERE id = ? LIMIT 100`, [maybeId]);
                    } else {
                        rows = await dbAll(db, `SELECT id, canonical_name, name_comment, date_of_birth FROM individuals WHERE canonical_name LIKE ? ORDER BY canonical_name LIMIT 200`, [`%${q}%`]);
                    }
                }

                // Map results to the simplified shape expected by the client
                rows = rows.map(r => ({
                    id: r.id,
                    canonical_name: r.canonical_name,
                    name_comment: r.name_comment,
                    date_of_birth: r.date_of_birth
                }));

                db.close();
                return { statusCode: 200, headers: jsonHeaders, body: JSON.stringify(rows) };
            } catch (err) {
                db.close();
                console.error('search error', err);
                return { statusCode: 500, headers: jsonHeaders, body: JSON.stringify({ error: err && err.message }) };
            }
        }

        // GET /api/tree?id=123&type=ancestor|descendant&family_tree=...&max_depth=6
        if (reqPath.startsWith('/api/tree')) {
            const params = event.queryStringParameters || {};
            const id = params.id ? parseInt(params.id, 10) : NaN;
            const family_tree = params.family_tree || null;
            if (isNaN(id)) return { statusCode: 400, headers: jsonHeaders, body: JSON.stringify({ error: 'missing or invalid id' }) };

            const requestStart = process.hrtime.bigint();
            const db = dbOpen();

            // Track DB timings and counts for metadata
            const dbQueryTimes = [];
            let dbQueryCount = 0;
            let parentsCacheHits = 0;
            let parentsCacheMisses = 0;

            // Measured run for arbitrary SQL (used for PRAGMA)
            const runStmt = (sql, params) => new Promise((resolve, reject) => {
                const qStart = process.hrtime.bigint();
                db.run(sql, params || [], function (err) {
                    const qEnd = process.hrtime.bigint();
                    const ms = Number(qEnd - qStart) / 1e6;
                    dbQueryTimes.push(ms);
                    dbQueryCount++;
                    err ? reject(err) : resolve(this);
                });
            });

            // Prefer in-memory temporary storage for GROUP BY / ORDER BY temp tables used by queries
            try { await runStmt('PRAGMA temp_store = MEMORY'); } catch (e) { /* ignore if not supported */ }

            const max_depth = process.env.GENEALOGY_MAX_DEPTH ? parseInt(process.env.GENEALOGY_MAX_DEPTH, 10) : 10;

            const recordToNode = (row, family_tree) => ({
                db_id: row.id,
                name: row.canonical_name,
                name_comment: row.name_comment,
                date_of_birth: row.date_of_birth,
                birth_location: row.birth_location,
                birth_comment: row.birth_comment,
                date_of_death: row.date_of_death,
                death_location: row.death_location,
                death_comment: row.death_comment,
                marriage_date: row.marriage_date,
                marriage_location: row.marriage_location,
                marriage_comment: row.marriage_comment,
                family_tree: family_tree,
                sosa: null,
                children: []
            });

            // Prepare commonly-used statements and small helpers (per-request)
            const stmtAll = (stmt, params) => new Promise((resolve, reject) => {
                const qStart = process.hrtime.bigint();
                const sname = stmtToName.get(stmt);
                if (sname) stmtCounts[sname] = (stmtCounts[sname] || 0) + 1;
                stmt.all(params || [], (err, rows) => {
                    const qEnd = process.hrtime.bigint();
                    const ms = Number(qEnd - qStart) / 1e6;
                    dbQueryTimes.push(ms);
                    dbQueryCount++;
                    if (sname) stmtTimeSamples[sname].push(ms);
                    err ? reject(err) : resolve(rows);
                });
            });
            const stmtGet = (stmt, params) => new Promise((resolve, reject) => {
                const qStart = process.hrtime.bigint();
                const sname = stmtToName.get(stmt);
                if (sname) stmtCounts[sname] = (stmtCounts[sname] || 0) + 1;
                stmt.get(params || [], (err, row) => {
                    const qEnd = process.hrtime.bigint();
                    const ms = Number(qEnd - qStart) / 1e6;
                    dbQueryTimes.push(ms);
                    dbQueryCount++;
                    if (sname) stmtTimeSamples[sname].push(ms);
                    err ? reject(err) : resolve(row);
                });
            });

            const baseSelect = `SELECT i.id as id, i.canonical_name as canonical_name, i.name_comment as name_comment, i.date_of_birth, i.birth_location, i.birth_comment, i.date_of_death, i.death_location, i.death_comment, i.marriage_date, i.marriage_location, i.marriage_comment, r.relationship_type as relationship_type, r.family_tree as family_tree FROM relationships r JOIN individuals i ON r.parent_id = i.id`;

            const stmts = {
                getParentsWithTree: db.prepare(`${baseSelect} WHERE r.child_id = ? AND r.family_tree = ? GROUP BY i.id, r.relationship_type ORDER BY r.relationship_type DESC`),
                getParents: db.prepare(`${baseSelect} WHERE r.child_id = ? GROUP BY i.id, r.relationship_type ORDER BY r.relationship_type DESC`),
                getIndividualById: db.prepare(`SELECT i.id as id, i.canonical_name as canonical_name, i.name_comment as name_comment, i.date_of_birth, i.birth_location, i.birth_comment, i.date_of_death, i.death_location, i.death_comment, i.marriage_date, i.marriage_location, i.marriage_comment FROM individuals i WHERE i.id = ?`),
                findOthersByNameDob: db.prepare(`SELECT DISTINCT i.id as id FROM individuals i WHERE i.canonical_name = ? AND i.date_of_birth = ? AND i.id != ?`),
                findTreesForIndividual: db.prepare(`SELECT DISTINCT family_tree as family_tree FROM relationships WHERE parent_id = ? OR child_id = ?`)
            };

            // Map prepared stmts -> name and initialize counters and timing
            const stmtToName = new Map();
            const stmtCounts = {};
            const stmtTimeSamples = {};
            for (const [k, v] of Object.entries(stmts)) {
                stmtToName.set(v, k);
                stmtCounts[k] = 0;
                stmtTimeSamples[k] = [];
            };

            const parentsCache = new Map(); // memoize getParents for this request

            // Prefetch all individuals for this request into an in-memory cache so that
            // we perform a single read instead of many repeated `getIndividualById` calls.
            // Record timing under the synthetic key 'getAllIndividuals' so it appears in metrics.
            stmtTimeSamples['getAllIndividuals'] = stmtTimeSamples['getAllIndividuals'] || [];
            const individualsCache = new Map();
            try {
                const qStartAll = process.hrtime.bigint();
                const allRows = await dbAll(db, `SELECT id as id, canonical_name as canonical_name, name_comment as name_comment, date_of_birth, birth_location, birth_comment, date_of_death, death_location, death_comment, marriage_date, marriage_location, marriage_comment FROM individuals`);
                const qEndAll = process.hrtime.bigint();
                const msAll = Number(qEndAll - qStartAll) / 1e6;
                dbQueryTimes.push(msAll);
                dbQueryCount++;
                stmtTimeSamples['getAllIndividuals'].push(msAll);
                // Record this as one invocation so counts reflect the prefetch
                stmtCounts['getAllIndividuals'] = (stmtCounts['getAllIndividuals'] || 0) + 1;
                for (const r of allRows) individualsCache.set(r.id, r);
            } catch (e) {
                console.error('failed to prefetch individuals', e);
            }

            // Prefetch all parent relationships joined to parent individual data
            // Map: child_id -> [ { id, canonical_name, ..., relationship_type, family_tree } ]
            stmtTimeSamples['getAllRelationships'] = stmtTimeSamples['getAllRelationships'] || [];
            const parentsByChild = new Map();
            // Flag which indicates whether the prefetch completed (even if it returned 0 rows).
            // If true, we can trust parentsByChild to represent the full set and avoid DB fallbacks.
            let relationshipsPrefetched = false;
            try {
                const qStartRel = process.hrtime.bigint();
                // const relRows = await dbAll(db, `SELECT r.child_id as child_id, r.family_tree as family_tree, r.relationship_type as relationship_type, i.id as id, i.canonical_name as canonical_name, i.name_comment as name_comment, i.date_of_birth as date_of_birth, i.birth_location as birth_location, i.birth_comment as birth_comment, i.date_of_death as date_of_death, i.death_location as death_location, i.death_comment as death_comment, i.marriage_date as marriage_date, i.marriage_location as marriage_location, i.marriage_comment as marriage_comment FROM relationships r JOIN individuals i ON r.parent_id = i.id`);
                const relRows = await dbAll(db, `SELECT r.child_id as child_id, r.family_tree as family_tree, r.relationship_type as relationship_type, i.id as id, i.canonical_name as canonical_name, i.name_comment as name_comment, i.date_of_birth as date_of_birth, i.birth_location as birth_location, i.birth_comment as birth_comment, i.date_of_death as date_of_death, i.death_location as death_location, i.death_comment as death_comment, i.marriage_date as marriage_date, i.marriage_location as marriage_location, i.marriage_comment as marriage_comment FROM relationships r JOIN individuals i ON r.parent_id = i.id`);
                const qEndRel = process.hrtime.bigint();
                const msRel = Number(qEndRel - qStartRel) / 1e6;
                dbQueryTimes.push(msRel);
                dbQueryCount++;
                stmtTimeSamples['getAllRelationships'].push(msRel);
                // Count this prefetch
                stmtCounts['getAllRelationships'] = (stmtCounts['getAllRelationships'] || 0) + 1;
                for (const r of relRows) {
                    const arr = parentsByChild.get(r.child_id) || [];
                    arr.push(r);
                    parentsByChild.set(r.child_id, arr);
                }
                // Mark successful prefetch (even if relRows.length === 0)
                relationshipsPrefetched = true;
            } catch (e) {
                console.error('failed to prefetch relationships', e);
            }

            const getParents = async (individual_id, fam_tree) => {
                const key = `${individual_id}|${fam_tree || ''}`;
                if (parentsCache.has(key)) {
                    parentsCacheHits++;
                    return parentsCache.get(key);
                }

                // Cache miss
                parentsCacheMisses++;

                // If we prefetched relationships, use that definitive result (empty => no parents)
                if (relationshipsPrefetched) {
                    const byChild = parentsByChild.get(individual_id) || [];
                    if (fam_tree) {
                        const rows = byChild.filter(r => (r.family_tree || '') === (fam_tree || ''));
                        // If we found parents in the requested family_tree, return them.
                        // Otherwise fall back to parents from any tree (to allow crossing trees),
                        // matching the fallback behavior when prefetch did not run.
                        if (rows && rows.length) {
                            parentsCache.set(key, rows);
                            return rows;
                        }
                        parentsCache.set(key, byChild);
                        return byChild;
                    }
                    parentsCache.set(key, byChild);
                    return byChild;
                }

                // Prefetch did not complete; fall back to prepared statements
                if (fam_tree) {
                    let rows = await stmtAll(stmts.getParentsWithTree, [individual_id, fam_tree]);
                    if (rows && rows.length) {
                        parentsCache.set(key, rows);
                        return rows;
                    }
                    rows = await stmtAll(stmts.getParents, [individual_id]);
                    parentsCache.set(key, rows || []);
                    return rows;
                } else {
                    const rows = await stmtAll(stmts.getParents, [individual_id]);
                    parentsCache.set(key, rows || []);
                    return rows;
                }
            };

            // recursive builders
            const buildAncestor = async (individual_id, fam_tree, maxDepth, visited = new Set(), depth = 0, sosa = 1) => {
                if (visited.has(individual_id) || depth > maxDepth) return null;
                visited.add(individual_id);

                // Fetch canonical individual data from per-request cache (prefetched), falling back to prepared stmt
                let row = individualsCache.get(individual_id);
                if (!row) {
                    row = await stmtGet(stmts.getIndividualById, [individual_id]);
                }
                if (!row) return null;

                const node = recordToNode(row, fam_tree);
                node.sosa = sosa;

                // get parents
                let parents = await getParents(individual_id, fam_tree);
                if (!parents || !parents.length) {
                    if (node.date_of_birth && node.name) {
                        const others = await stmtAll(stmts.findOthersByNameDob, [node.name, node.date_of_birth, individual_id]);
                        for (const o of others) {
                            const trees = await stmtAll(stmts.findTreesForIndividual, [o.id, o.id]);
                            for (const t of trees) {
                                parents = await getParents(o.id, t.family_tree);
                                if (parents && parents.length) {
                                    const otherNode = await buildAncestor(o.id, t.family_tree, maxDepth, visited, depth, sosa);
                                    return otherNode;
                                }
                            }
                        }
                    }
                }

                if (parents && parents.length) {
                    let mother = null, father = null;
                    for (const p of parents) {
                        const rel_type = p.relationship_type || null;
                        if (rel_type === 'father') father = p; else mother = p;
                    }
                    const toAdd = [];
                    if (mother) toAdd.push([mother, sosa * 2 + 1]);
                    if (father) toAdd.push([father, sosa * 2]);
                    for (const [p, parentSosa] of toAdd) {
                        const childNode = await buildAncestor(p.id, p.family_tree || fam_tree, maxDepth, visited, depth + 1, parentSosa);
                        if (childNode) node.children.push(childNode);
                    }
                }
                return node;
            };

            const computeDbStats = (times) => {
                if (!times || times.length === 0) return { min: 0, max: 0, avg: 0, stddev: 0 };
                const n = times.length;
                const min = Math.min(...times);
                const max = Math.max(...times);
                const sum = times.reduce((a, b) => a + b, 0);
                const avg = sum / n;
                const variance = times.reduce((acc, x) => acc + Math.pow(x - avg, 2), 0) / n;
                const stddev = Math.sqrt(variance);
                const round = (v) => Number(v.toFixed(3));
                return { min: round(min), max: round(max), avg: round(avg), stddev: round(stddev) };
            };

            const finalizeStmts = () => {
                try {
                    for (const s of Object.values(stmts)) {
                        try { s.finalize(); } catch (e) { /* ignore */ }
                    }
                } catch (e) { /* ignore */ }
            };

            try {
                // Always build ancestor tree (descendants not supported anymore)
                const tree = await buildAncestor(id, family_tree, max_depth);

                // Compute timing/DB metadata
                finalizeStmts();
                try { db.close(); } catch (e) { /* ignore */ }
                const requestEnd = process.hrtime.bigint();
                const responseTimeMs = Number(requestEnd - requestStart) / 1e6;
                const dbStats = computeDbStats(dbQueryTimes);
                const preparedStatementMetrics = Object.fromEntries(Object.entries(stmtTimeSamples).map(([k, arr]) => {
                    const total = Number(arr.reduce((a, b) => a + b, 0).toFixed(3));
                    const stats = computeDbStats(arr);
                    return [k, { count: stmtCounts[k] || 0, total_ms: total, min: stats.min, max: stats.max, avg: stats.avg, stddev: stats.stddev }];
                }));
                const meta = {
                    response_time_ms: Number(responseTimeMs.toFixed(3)),
                    db_queries: dbQueryCount,
                    db_time_ms: dbStats,
                    parents_cache: {
                        hits: parentsCacheHits,
                        misses: parentsCacheMisses
                    },
                    prepared_statement_metrics: preparedStatementMetrics
                };

                if (!tree) return { statusCode: 404, headers: jsonHeaders, body: JSON.stringify({ error: 'not found', meta }) };
                return { statusCode: 200, headers: jsonHeaders, body: JSON.stringify({ tree, meta }) };
            } catch (err) {
                finalizeStmts();
                try { db.close(); } catch (e) { /* ignore */ }
                const requestEnd = process.hrtime.bigint();
                const responseTimeMs = Number(requestEnd - requestStart) / 1e6;
                const dbStats = computeDbStats(dbQueryTimes);
                const preparedStatementMetrics = Object.fromEntries(Object.entries(stmtTimeSamples).map(([k, arr]) => {
                    const total = Number(arr.reduce((a, b) => a + b, 0).toFixed(3));
                    const stats = computeDbStats(arr);
                    return [k, { count: stmtCounts[k] || 0, total_ms: total, min: stats.min, max: stats.max, avg: stats.avg, stddev: stats.stddev }];
                }));
                const meta = {
                    response_time_ms: Number(responseTimeMs.toFixed(3)),
                    db_queries: dbQueryCount,
                    db_time_ms: dbStats,
                    parents_cache: {
                        hits: parentsCacheHits,
                        misses: parentsCacheMisses
                    },
                    prepared_statement_metrics: preparedStatementMetrics
                };
                console.error('tree error', err);
                return { statusCode: 500, headers: jsonHeaders, body: JSON.stringify({ error: err && err.message, meta }) };
            }
        }

        // unknown API
        return { statusCode: 404, headers: { ...corsHeaders() }, body: 'Not Found' };
    }

    // Map / to index.html
    let filePath = reqPath === '/' ? '/index.html' : reqPath;
    // disallow path traversal
    if (filePath.includes('..')) return { statusCode: 400, headers: corsHeaders(), body: 'Bad Request' };

    const localPath = path.join(__dirname, 'dist', decodeURIComponent(filePath.replace(/^\//, '')));
    try {
        const data = await fs.readFile(localPath);
        const contentType = mime.lookup(localPath) || 'application/octet-stream';

        const headersOut = { 'Content-Type': contentType, ...corsHeaders() };
        if (setCookieHeader) {
            headersOut['Set-Cookie'] = setCookieHeader;
        }

        return {
            statusCode: 200,
            headers: headersOut,
            body: data.toString('base64'),
            isBase64Encoded: true
        };
    } catch (err) {
        console.error('File read error', localPath, err && err.message);
        return { statusCode: 404, headers: corsHeaders(), body: 'Not Found' };
    }
};
