/* Local dev server for the Lambda handler
 * - Sets LOCAL_DEV=1 so the handler treats requests as unauthenticated (local only)
 * - Forwards HTTP requests to the Lambda-style handler and returns responses
 * - Intended for development only. The handler itself prevents LOCAL_DEV from
 *   being set in actual Lambda environments.
 */

process.env.LOCAL_DEV = '1';

const express = require('express');
const handler = require('./handler');

const app = express();
const PORT = process.env.PORT || 3001;

// Accept any body as raw so we forward it unchanged to the handler
app.use(express.raw({ type: '*/*', limit: '2mb' }));

// Helper to build a Lambda-style event from Express request
function buildEvent(req) {
    const parsed = new URL(req.originalUrl || req.url, `http://${req.headers.host || 'localhost'}`);
    const queryParams = parsed.searchParams.size ? Object.fromEntries(parsed.searchParams) : null;
    const rawQueryString = parsed.search ? parsed.search.slice(1) : '';
    const headers = Object.assign({}, req.headers);

    let body = null;
    if (req.body && req.body.length) {
        // body is Buffer from express.raw
        body = req.body.toString();
    }

    // Compatibility: Accept `/individuals` and `/tree` (without /api) when testing locally
    // and rewrite them to `/api/*`. This helps manual testing and curl invocations.
    let path = req.path;
    if (!path.startsWith('/api/') && (path === '/individuals' || path.startsWith('/individuals?') || path === '/tree' || path.startsWith('/tree?'))) {
        console.debug(`Rewriting local path ${path} -> /api${path}`);
        path = `/api${path}`;
    }

    return {
        rawPath: path,
        path: path,
        rawQueryString: rawQueryString,
        queryStringParameters: queryParams,
        headers: headers,
        requestContext: { http: { method: req.method } },
        httpMethod: req.method,
        body: body,
        isBase64Encoded: false
    };
}

async function handleRequest(req, res) {
    try {
        const event = buildEvent(req);
        const result = await handler.handler(event);

        const statusCode = result && result.statusCode ? result.statusCode : 200;
        const headers = (result && result.headers) ? result.headers : {};
        let body = result && result.body ? result.body : '';

        if (result && result.isBase64Encoded) {
            // send binary
            const buf = Buffer.from(body, 'base64');
            Object.entries(headers).forEach(([k, v]) => res.setHeader(k, v));
            res.status(statusCode).send(buf);
            return;
        }

        Object.entries(headers).forEach(([k, v]) => res.setHeader(k, v));
        res.status(statusCode).send(body);
    } catch (err) {
        console.error('dev server error', err && err.stack || err);
        res.status(500).send('dev server error: ' + (err && err.message));
    }
}

app.options('*', handleRequest);
app.all('*', handleRequest);

app.listen(PORT, () => {
    console.log(`Local lambda dev server listening on http://localhost:${PORT}`);
    console.log('Note: LOCAL_DEV=1 is set for this process; authentication is disabled locally.');
});
