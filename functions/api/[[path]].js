const REQUEST_HEADERS = new Set([
  "accept",
  "authorization",
  "content-type",
  "if-match",
  "if-none-match",
]);
const RESPONSE_HEADERS = new Set([
  "content-type",
  "cache-control",
  "etag",
  "last-modified",
  "retry-after",
]);
const SAFE_SEGMENT = /^[A-Za-z0-9._~-]+$/;
const ALLOWED_METHODS = new Set(["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"]);

function getBackendOrigin(env) {
  const raw = typeof env?.BACKEND_ORIGIN === "string" ? env.BACKEND_ORIGIN.trim().replace(/\/+$/, "") : "";
  if (!raw) return null;
  try {
    const parsed = new URL(raw);
    if (!["http:", "https:"].includes(parsed.protocol)) return null;
    if (parsed.username || parsed.password) return null;
    if (parsed.search || parsed.hash) return null;
    if (parsed.pathname !== "/") return null;
    return parsed.origin;
  } catch {
    return null;
  }
}

function getSafePath(rawPath) {
  if (!Array.isArray(rawPath) || rawPath.length === 0) return null;
  const segments = [];
  for (const raw of rawPath) {
    if (typeof raw !== "string") return null;
    let segment;
    try {
      segment = decodeURIComponent(raw);
    } catch {
      return null;
    }
    if (!segment || segment === "." || segment === "..") return null;
    if (/[\/\\\u0000-\u001F\u007F?#]/.test(segment)) return null;
    if (!SAFE_SEGMENT.test(segment)) return null;
    segments.push(encodeURIComponent(segment));
  }
  return segments.join("/");
}

function jsonResponse(detail, status) {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function buildRequestHeaders(request) {
  const headers = new Headers();
  for (const name of REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  if (!headers.has("accept")) headers.set("accept", "application/json");
  return headers;
}

function buildResponseHeaders(response) {
  const headers = new Headers();
  for (const name of RESPONSE_HEADERS) {
    const value = response.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  if (!headers.has("content-type")) headers.set("content-type", "application/json; charset=utf-8");
  return headers;
}

export async function onRequest({ request, env, params }) {
  const origin = getBackendOrigin(env);
  if (!origin) return jsonResponse("Backend origin is not configured.", 503);

  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        Allow: "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Methods": "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "authorization, content-type",
        "Access-Control-Max-Age": "86400",
      },
    });
  }

  const method = request.method.toUpperCase();
  if (!ALLOWED_METHODS.has(method)) return jsonResponse("Method not allowed.", 405);

  const path = getSafePath(params?.path);
  if (!path) return jsonResponse("Invalid API path.", 400);

  let query = "";
  try {
    query = new URL(request.url).search;
  } catch {
    return jsonResponse("Invalid request URL.", 400);
  }

  const target = `${origin}/api/${path}${query}`;
  let response;
  try {
    response = await fetch(target, {
      method,
      headers: buildRequestHeaders(request),
      body: ["GET", "HEAD"].includes(method) ? undefined : await request.arrayBuffer(),
      redirect: "manual",
    });
  } catch {
    return jsonResponse("Upstream service unavailable.", 502);
  }

  if (response.status >= 500 || response.status === 0) {
    return jsonResponse("Upstream service error.", 502);
  }
  if (response.status >= 300 && response.status < 400) {
    return jsonResponse("Upstream redirect is not supported.", 502);
  }

  const body = [204, 205, 304].includes(response.status) ? null : response.body;
  return new Response(body, {
    status: response.status,
    statusText: response.statusText,
    headers: buildResponseHeaders(response),
  });
}
