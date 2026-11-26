import test from "node:test";
import assert from "node:assert/strict";

let caseCounter = 0;

async function loadApi(options = {}) {
  const {
    hostname = "localhost",
    protocol = "http:",
    config = {},
    token = null,
    legacyToken = null,
    response = { status: 200, ok: true, json: async () => ({}) },
    fetchImpl,
  } = options;

  const events = [];
  const calls = [];
  const session = new Map();
  const local = new Map();
  if (token) session.set("if_access_token", token);
  if (legacyToken) local.set("if_access_token", legacyToken);

  globalThis.location = { hostname, protocol, href: `${protocol}//${hostname}/` };
  globalThis.CustomEvent = class {
    constructor(type) {
      this.type = type;
    }
  };
  globalThis.window = {
    __IDEAFORGE_CONFIG__: config,
    addEventListener() {},
    dispatchEvent(event) {
      events.push(event.type);
    },
  };
  globalThis.sessionStorage = {
    getItem: key => (session.has(key) ? session.get(key) : null),
    setItem: (key, value) => session.set(key, String(value)),
    removeItem: key => session.delete(key),
  };
  globalThis.localStorage = {
    getItem: key => (local.has(key) ? local.get(key) : null),
    setItem: (key, value) => local.set(key, String(value)),
    removeItem: key => local.delete(key),
  };
  globalThis.fetch = fetchImpl || (async (url, init) => {
    calls.push({ url, init });
    return response;
  });

  const module = await import(`../IdeaForge AI_files/api.js?case=${++caseCounter}`);
  return { api: module.api, events, calls, session, local };
}

test("local development uses the local backend URLs", async () => {
  const { api } = await loadApi({ hostname: "127.0.0.1" });
  assert.equal(api.config.apiBaseUrl, "http://127.0.0.1:8000/api");
  assert.equal(api.config.healthUrl, "http://127.0.0.1:8000/health");
});

test("file origin uses the local backend URLs", async () => {
  const { api } = await loadApi({ hostname: "", protocol: "file:" });
  assert.equal(api.config.apiBaseUrl, "http://127.0.0.1:8000/api");
  assert.equal(api.config.healthUrl, "http://127.0.0.1:8000/health");
});

test("production uses same-origin API and health paths", async () => {
  const { api } = await loadApi({ hostname: "ideaforge.pages.dev", protocol: "https:" });
  assert.equal(api.config.apiBaseUrl, "/api");
  assert.equal(api.config.healthUrl, "/health");
});

test("runtime config overrides URLs and strips trailing slashes", async () => {
  const { api } = await loadApi({
    hostname: "ideaforge.pages.dev",
    protocol: "https:",
    config: {
      apiBaseUrl: "https://render.example/api/",
      healthUrl: "https://render.example/health/",
    },
  });
  assert.equal(api.config.apiBaseUrl, "https://render.example/api");
  assert.equal(api.config.healthUrl, "https://render.example/health");
});

test("requests use the configured base URL and bearer token", async () => {
  const { api, calls } = await loadApi({
    hostname: "ideaforge.pages.dev",
    protocol: "https:",
    token: "tok-123",
  });
  await api.ideas.list({ page: 2, page_size: 10 });
  assert.equal(calls[0].url, "/api/ideas?page=2&page_size=10");
  assert.equal(calls[0].init.headers["Content-Type"], "application/json");
  assert.equal(calls[0].init.headers.Authorization, "Bearer tok-123");
});

test("failed login does not clear the token or dispatch auth-expired", async () => {
  const { api, events, session } = await loadApi({
    token: "old-token",
    response: {
      status: 401,
      ok: false,
      json: async () => ({ detail: "Invalid credentials" }),
    },
  });

  await assert.rejects(
    api.auth.login("user@example.com", "wrongpassword"),
    error => error instanceof api.ApiError && error.status === 401 && error.message === "Invalid credentials"
  );
  assert.equal(events.length, 0);
  assert.equal(session.get("if_access_token"), "old-token");
});

test("authenticated 401 clears the token and dispatches auth-expired", async () => {
  const { api, events, session } = await loadApi({
    token: "expired-token",
    response: {
      status: 401,
      ok: false,
      json: async () => ({ detail: "Unauthorized" }),
    },
  });

  await assert.rejects(
    api.auth.getMe(),
    error => error instanceof api.ApiError && error.message === "Session expired. Please log in again."
  );
  assert.deepEqual(events, ["ideaforge:auth-expired"]);
  assert.equal(session.has("if_access_token"), false);
});

test("checkHealth uses the configured health URL", async () => {
  const calls = [];
  const { api } = await loadApi({
    hostname: "ideaforge.pages.dev",
    protocol: "https:",
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return { ok: true };
    },
  });

  assert.equal(await api.checkHealth({ timeoutMs: 50 }), true);
  assert.equal(calls[0].url, "/health");
  assert.equal(calls[0].init.method, "GET");
  assert.ok(calls[0].init.signal);
});

test("checkHealth returns false when the backend is unreachable", async () => {
  const { api } = await loadApi({
    fetchImpl: async () => {
      throw new Error("offline");
    },
  });
  assert.equal(await api.checkHealth(), false);
});

test("legacy localStorage token is removed during startup", async () => {
  const { api, local, session } = await loadApi({ legacyToken: "legacy-jwt" });
  assert.equal(local.has("if_access_token"), false);
  assert.equal(session.has("if_access_token"), false);
  assert.equal(api.auth.isLoggedIn(), false);
});

test("login stores the token in sessionStorage only", async () => {
  const { api, local, session } = await loadApi({
    response: { status: 200, ok: true, json: async () => ({ access_token: "new-jwt" }) },
  });
  await api.auth.login("user@example.com", "Password1");
  assert.equal(session.get("if_access_token"), "new-jwt");
  assert.equal(local.has("if_access_token"), false);
});

test("registration stores the token in sessionStorage only", async () => {
  const { api, local, session } = await loadApi({
    response: { status: 200, ok: true, json: async () => ({ access_token: "registered-jwt" }) },
  });
  await api.auth.register("user@example.com", "Password1", "User");
  assert.equal(session.get("if_access_token"), "registered-jwt");
  assert.equal(local.has("if_access_token"), false);
});

test("existing sessionStorage authentication works with a legacy token present", async () => {
  const { api, calls, local } = await loadApi({ token: "session-jwt", legacyToken: "legacy-jwt" });
  assert.equal(api.auth.isLoggedIn(), true);
  await api.ideas.list();
  assert.equal(calls[0].init.headers.Authorization, "Bearer session-jwt");
  assert.equal(local.has("if_access_token"), false);
});

test("missing tokens do not break startup", async () => {
  const { api, local, session } = await loadApi();
  assert.equal(api.auth.isLoggedIn(), false);
  assert.equal(session.has("if_access_token"), false);
  assert.equal(local.has("if_access_token"), false);
  assert.equal(api.config.apiBaseUrl, "http://127.0.0.1:8000/api");
});

test("logout clears sessionStorage and does not restore the legacy token", async () => {
  const { api, local, session } = await loadApi({ token: "session-jwt", legacyToken: "legacy-jwt" });
  api.auth.logout();
  assert.equal(session.has("if_access_token"), false);
  assert.equal(local.has("if_access_token"), false);
  assert.equal(api.auth.isLoggedIn(), false);
});

test("health failure does not clear sessionStorage or dispatch auth-expired", async () => {
  const { api, events, session } = await loadApi({
    token: "session-jwt",
    fetchImpl: async () => {
      throw new Error("offline");
    },
  });
  assert.equal(await api.checkHealth(), false);
  assert.equal(session.get("if_access_token"), "session-jwt");
  assert.deepEqual(events, []);
});
