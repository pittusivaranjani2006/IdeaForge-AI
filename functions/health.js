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

function unavailable() {
  return new Response(JSON.stringify({ status: "unavailable" }), {
    status: 503,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

export async function onRequest({ env }) {
  const origin = getBackendOrigin(env);
  if (!origin) return unavailable();

  let response;
  try {
    response = await fetch(`${origin}/health`, {
      method: "GET",
      headers: { accept: "application/json" },
      redirect: "manual",
    });
  } catch {
    return unavailable();
  }

  if (!response.ok) return unavailable();
  return new Response(JSON.stringify({ status: "ok" }), {
    status: 200,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
