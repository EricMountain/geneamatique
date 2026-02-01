const { DynamoDBClient, GetItemCommand } = require('@aws-sdk/client-dynamodb');
const fs = require('fs').promises;
const path = require('path');
const mime = require('mime-types');

const TABLE = process.env.API_KEYS_TABLE;
const dynamo = new DynamoDBClient({});

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
    const unauthenticated = reqPath === '/favicon.ico' || reqPath.startsWith('/icons') || reqPath.endsWith('.png') || reqPath.endsWith('.ico') || reqPath.startsWith('/assets/icons');

    let setCookieHeader = null;

    if (!unauthenticated) {
        const headerKey = getApiKeyFromHeaders(headers);
        const cookieKey = getApiKeyFromCookies(headers);
        const queryKey = getApiKeyFromQuery(event);

        const key = headerKey || cookieKey || queryKey;

        if (!key) return { statusCode: 401, headers: corsHeaders(), body: 'Missing API key' };

        const ok = await checkApiKey(key);
        if (!ok) return { statusCode: 403, headers: corsHeaders(), body: 'Invalid API key' };

        // If the client provided the key via query param and there is no cookie, set a cookie so future requests are authenticated
        if (queryKey && !cookieKey) {
            setCookieHeader = makeSetCookieHeader(key);
        }
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
