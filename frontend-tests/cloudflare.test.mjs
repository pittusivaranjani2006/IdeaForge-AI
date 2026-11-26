import test from "node:test";
import assert from "node:assert/strict";

const { onRequest: onApiRequest } = await import(new URL("../functions/api/[[path]].js", import.meta.url));
const { onRequest: onHealthRequest } = await import(new URL("../functions/health.js", import.meta.url));

const ENV = { BACKEND_ORIGIN: "https://render.example/" };

function apiRequest(url = "https://ideaforge.pages.dev/api/ideas", init = {}) {
  return new Request(url, init);
}

async function readJson(response) {
  return JSON.parse(await response.text());
}

test("api proxy returns controlled 503 when backend origin is missing", async () => {
  const response = await onApiRequest({
    request: apiRequest(),
    env: {},
    params: { path: ["ideas"] },
  });
  assert.equal(response.status, 503);
  assert.deepEqual(await readJson(response), { detail: "Backend origin is not configured." });
});

test("api proxy forwards method, query, auth, and body to Render", async () => {
  let captured;
  globalThis.fetch = async (url, init) => {
    captured = { url, init };
    return new Response(JSON.stringify({ ok: true }), {
      status: 201,
      headers: {
        "content-type": "application/json",
        "access-control-allow-origin": "*",
      },
    });
  };

  const response = await onApiRequest({
    request: apiRequest("https://ideaforge.pages.dev/api/auth/login?x=1", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: "Bearer tok-123",
      },
      body: JSON.stringify({ email: "user@example.com" }),
    }),
    env: ENV,
    params: { path: ["auth", "login"] },
  });

  assert.equal(captured.url, "https://render.example/api/auth/login?x=1");
  assert.equal(captured.init.method, "POST");
  assert.equal(captured.init.headers.get("authorization"), "Bearer tok-123");
  assert.equal(await new Response(captured.init.body).text(), JSON.stringify({ email: "user@example.com" }));
  assert.equal(response.status, 201);
  assert.equal(response.headers.get("access-control-allow-origin"), null);
});

test("api proxy preserves query parameters", async () => {
  let captured;
  globalThis.fetch = async (url, init) => {
    captured = url;
    return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
  };
  await onApiRequest({
    request: apiRequest("https://ideaforge.pages.dev/api/ideas?page=2&q=a%20b&sort=latest"),
    env: ENV,
    params: { path: ["ideas"] },
  });
  assert.equal(captured, "https://render.example/api/ideas?page=2&q=a%20b&sort=latest");
});

test("api proxy forwards GET, POST, PUT, PATCH, and DELETE", async () => {
  const methods = ["GET", "POST", "PUT", "PATCH", "DELETE"];
  for (const method of methods) {
    let captured;
    globalThis.fetch = async (url, init) => {
      captured = { url, init };
      return new Response(null, { status: 204 });
    };
    const init = method === "GET"
      ? {}
      : { method, body: "{}", headers: { "content-type": "application/json" } };
    const response = await onApiRequest({
      request: apiRequest("https://ideaforge.pages.dev/api/projects/1?x=1", init),
      env: ENV,
      params: { path: ["projects", "1"] },
    });
    assert.equal(captured.init.method, method);
    assert.equal(captured.url, "https://render.example/api/projects/1?x=1");
    assert.equal(response.status, 204);
  }
});

test("api proxy rejects plain and encoded traversal attempts", async () => {
  const attempts = [
    ["..", "ideas"],
    ["auth", "..", "..", "health"],
    ["%2e%2e", "ideas"],
    ["auth", "%2E%2E", "%2e%2e", "health"],
    ["%252e%252e", "ideas"],
    ["..%2fhealth"],
    ["auth", "\\", "me"],
  ];
  let called = false;
  globalThis.fetch = async () => {
    called = true;
    return new Response("{}", { status: 200 });
  };
  for (const path of attempts) {
    const response = await onApiRequest({
      request: apiRequest("https://ideaforge.pages.dev/api/x"),
      env: ENV,
      params: { path },
    });
    assert.equal(response.status, 400);
    assert.deepEqual(await readJson(response), { detail: "Invalid API path." });
  }
  assert.equal(called, false);
});

test("api proxy rejects malicious external destination attempts", async () => {
  let called = false;
  globalThis.fetch = async () => {
    called = true;
    return new Response("{}", { status: 200 });
  };
  const response = await onApiRequest({
    request: apiRequest("https://ideaforge.pages.dev/api/https://evil.example/x", {
      headers: { "x-forwarded-host": "evil.example" },
    }),
    env: ENV,
    params: { path: ["https:", "evil.example", "x"] },
  });
  assert.equal(response.status, 400);
  assert.equal(called, false);
});

test("api proxy handles OPTIONS explicitly without calling upstream", async () => {
  let called = false;
  globalThis.fetch = async () => {
    called = true;
    return new Response(null, { status: 200 });
  };
  const response = await onApiRequest({
    request: apiRequest("https://ideaforge.pages.dev/api/ideas", { method: "OPTIONS" }),
    env: ENV,
    params: { path: ["ideas"] },
  });
  assert.equal(response.status, 204);
  assert.equal(called, false);
  assert.match(response.headers.get("allow"), /GET/);
  assert.match(response.headers.get("allow"), /DELETE/);
});

test("api proxy forwards upstream 4xx responses with backend detail", async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Invalid input" }), {
    status: 422,
    headers: { "content-type": "application/json" },
  });
  const response = await onApiRequest({
    request: apiRequest(),
    env: ENV,
    params: { path: ["ideas"] },
  });
  assert.equal(response.status, 422);
  assert.deepEqual(await readJson(response), { detail: "Invalid input" });
});

test("api proxy converts upstream 5xx responses to controlled JSON", async () => {
  globalThis.fetch = async () => new Response("SECRET_SHOULD_NOT_LEAK stack trace", {
    status: 500,
    headers: { "content-type": "text/plain" },
  });
  const response = await onApiRequest({
    request: apiRequest(),
    env: ENV,
    params: { path: ["ideas"] },
  });
  assert.equal(response.status, 502);
  const body = await response.text();
  assert.equal(body, JSON.stringify({ detail: "Upstream service error." }));
  assert.doesNotMatch(body, /SECRET_SHOULD_NOT_LEAK/);
});

test("api proxy handles network failures with controlled JSON", async () => {
  globalThis.fetch = async () => {
    throw new Error("connection refused");
  };
  const response = await onApiRequest({
    request: apiRequest(),
    env: ENV,
    params: { path: ["ideas"] },
  });
  assert.equal(response.status, 502);
  assert.deepEqual(await readJson(response), { detail: "Upstream service unavailable." });
});

test("api proxy filters sensitive request and response headers", async () => {
  let captured;
  globalThis.fetch = async (url, init) => {
    captured = init;
    return new Response("{}", {
      status: 200,
      headers: {
        "content-type": "application/json",
        "set-cookie": "session=secret",
        location: "https://render.example/internal",
        "access-control-allow-origin": "*",
        server: "internal-server",
      },
    });
  };
  const response = await onApiRequest({
    request: apiRequest("https://ideaforge.pages.dev/api/auth/me", {
      headers: {
        authorization: "Bearer tok-123",
        cookie: "legacy=secret",
        "x-forwarded-host": "evil.example",
        connection: "keep-alive",
      },
    }),
    env: ENV,
    params: { path: ["auth", "me"] },
  });
  assert.equal(captured.headers.get("authorization"), "Bearer tok-123");
  assert.equal(captured.headers.get("cookie"), null);
  assert.equal(captured.headers.get("x-forwarded-host"), null);
  assert.equal(captured.headers.get("connection"), null);
  assert.equal(captured.headers.get("host"), null);
  assert.equal(response.headers.get("set-cookie"), null);
  assert.equal(response.headers.get("location"), null);
  assert.equal(response.headers.get("access-control-allow-origin"), null);
  assert.equal(response.headers.get("server"), null);
});

test("health proxy returns controlled ok response for available backend", async () => {
  let captured;
  globalThis.fetch = async url => {
    captured = url;
    return new Response(JSON.stringify({
      status: "ok",
      version: "internal-version",
      environment: "production",
    }), { status: 200, headers: { "content-type": "application/json" } });
  };
  const response = await onHealthRequest({ env: ENV });
  assert.equal(captured, "https://render.example/health");
  assert.equal(response.status, 200);
  assert.deepEqual(await readJson(response), { status: "ok" });
});

test("health proxy returns controlled 503 when backend origin is missing", async () => {
  const response = await onHealthRequest({ env: {} });
  assert.equal(response.status, 503);
  assert.deepEqual(await readJson(response), { status: "unavailable" });
});

test("health proxy returns controlled 503 when backend reports failure", async () => {
  globalThis.fetch = async () => new Response("internal failure", { status: 500 });
  const response = await onHealthRequest({ env: ENV });
  assert.equal(response.status, 503);
  assert.deepEqual(await readJson(response), { status: "unavailable" });
});

test("health proxy handles network failures with controlled JSON", async () => {
  globalThis.fetch = async () => {
    throw new Error("offline");
  };
  const response = await onHealthRequest({ env: ENV });
  assert.equal(response.status, 503);
  assert.deepEqual(await readJson(response), { status: "unavailable" });
});

test("health proxy has no authentication side effects", async () => {
  const calls = [];
  globalThis.localStorage = new Proxy({}, {
    get(_target, prop) {
      return () => calls.push(`local:${String(prop)}`);
    },
  });
  globalThis.sessionStorage = new Proxy({}, {
    get(_target, prop) {
      return () => calls.push(`session:${String(prop)}`);
    },
  });
  globalThis.fetch = async () => {
    throw new Error("offline");
  };
  await onHealthRequest({ env: ENV });
  assert.deepEqual(calls, []);
});
