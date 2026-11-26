/**
 * IdeaForge AI — Backend API Client
 *
 * Thin wrapper around the FastAPI backend.
 * Keeps all backend URLs, auth headers, and error handling in one place.
 *
 * Usage:
 *   import { api } from './api.js';
 *   const token = await api.auth.login(email, password);
 */

// ── Configuration ─────────────────────────────────────────────────────────────
function isLocalOrigin() {
  if (typeof location === "undefined") return true;
  if (location.protocol === "file:") return true;
  return /^(localhost|127\.0\.0\.1|0\.0\.0\.0)$/i.test(location.hostname || "");
}

function normalizeUrl(value, fallback) {
  if (typeof value !== "string") return fallback;
  const normalized = value.trim().replace(/\/+$/, "");
  if (!normalized) return fallback;
  if (normalized.startsWith("/") || /^https?:\/\//i.test(normalized)) return normalized;
  return fallback;
}

const localOrigin = isLocalOrigin();
const runtimeConfig = typeof window !== "undefined" ? window.__IDEAFORGE_CONFIG__ || {} : {};
const API_BASE_URL = normalizeUrl(
  runtimeConfig.apiBaseUrl || (localOrigin ? "http://127.0.0.1:8000/api" : "/api"),
  localOrigin ? "http://127.0.0.1:8000/api" : "/api"
);
const HEALTH_URL = normalizeUrl(
  runtimeConfig.healthUrl || (localOrigin ? "http://127.0.0.1:8000/health" : "/health"),
  localOrigin ? "http://127.0.0.1:8000/health" : "/health"
);

// ── Token management ──────────────────────────────────────────────────────────
const TOKEN_KEY = "if_access_token";
try {
  localStorage.removeItem(TOKEN_KEY);
} catch {}
let memoryToken = null;
const TokenStore = {
  get() {
    try {
      return sessionStorage.getItem(TOKEN_KEY) || memoryToken;
    } catch {
      return memoryToken;
    }
  },
  set(token) {
    memoryToken = token;
    try {
      sessionStorage.setItem(TOKEN_KEY, token);
    } catch {}
  },
  clear() {
    memoryToken = null;
    try {
      sessionStorage.removeItem(TOKEN_KEY);
    } catch {}
  },
};

// ── Core fetch wrapper ────────────────────────────────────────────────────────

/**
 * @param {string} path   - e.g. "/auth/login"
 * @param {RequestInit} options
 * @returns {Promise<any>}
 */
async function request(path, options = {}) {
  const { auth = true, ...fetchOptions } = options;
  const token = auth ? TokenStore.get() : null;
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(fetchOptions.headers || {}),
  };

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...fetchOptions,
    headers,
  });

  // Handle token expiry
  if (res.status === 401 && auth) {
    TokenStore.clear();
    window.dispatchEvent(new CustomEvent("ideaforge:auth-expired"));
    throw new ApiError(401, "Session expired. Please log in again.");
  }

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new ApiError(res.status, data.detail || "An error occurred");
  }

  return data;
}

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

// ── Auth ──────────────────────────────────────────────────────────────────────
const auth = {
  async register(email, password, name) {
    const data = await request("/auth/register", {
      method: "POST",
      auth: false,
      body: JSON.stringify({ email, password, name }),
    });
    TokenStore.set(data.access_token);
    return data;
  },

  async login(email, password) {
    const data = await request("/auth/login", {
      method: "POST",
      auth: false,
      body: JSON.stringify({ email, password }),
    });
    TokenStore.set(data.access_token);
    return data;
  },

  async getMe() {
    return request("/auth/me");
  },

  async updateProfile(payload) {
    return request("/auth/me", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  logout() {
    TokenStore.clear();
  },

  isLoggedIn() {
    return !!TokenStore.get();
  },
};

// ── Ideas ─────────────────────────────────────────────────────────────────────
const ideas = {
  async list({ domain, difficulty, q, sort, page = 1, page_size = 20 } = {}) {
    const params = new URLSearchParams();
    if (domain) params.set("domain", domain);
    if (difficulty) params.set("difficulty", difficulty);
    if (q) params.set("q", q);
    if (sort) params.set("sort", sort);
    params.set("page", page);
    params.set("page_size", page_size);
    return request(`/ideas?${params}`);
  },

  async get(id) {
    return request(`/ideas/${id}`);
  },

  async save(id) {
    return request(`/ideas/${id}/save`, { method: "POST" });
  },

  async unsave(id) {
    return request(`/ideas/${id}/save`, { method: "DELETE" });
  },

  async generate(params) {
    return request("/ideas/generate", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async evaluate(payload) {
    return request("/ideas/evaluate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async myGenerated({ page = 1, page_size = 20 } = {}) {
    const params = new URLSearchParams({ page, page_size });
    return request(`/ideas/generated/my?${params}`);
  },
};

// ── Projects ──────────────────────────────────────────────────────────────────
const projects = {
  async list({ page = 1, page_size = 20 } = {}) {
    const params = new URLSearchParams({ page, page_size });
    return request(`/projects?${params}`);
  },

  async create(payload) {
    return request("/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async get(id) {
    return request(`/projects/${id}`);
  },

  async update(id, payload) {
    return request(`/projects/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  async delete(id) {
    return request(`/projects/${id}`, { method: "DELETE" });
  },

  async generateRoadmap(projectId, payload = {}) {
    return request(`/projects/${projectId}/roadmap/generate`, {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, ...payload }),
    });
  },

  async getRoadmap(roadmapId) {
    return request(`/projects/roadmaps/${roadmapId}`);
  },

  async createTask(payload) {
    return request("/projects/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async updateTask(taskId, payload) {
    return request(`/projects/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
};

// ── Community ─────────────────────────────────────────────────────────────────
const community = {
  async listPosts({ post_type, q, sort, page = 1, page_size = 20 } = {}) {
    const params = new URLSearchParams({ page, page_size });
    if (post_type) params.set("post_type", post_type);
    if (q) params.set("q", q);
    if (sort) params.set("sort", sort);
    return request(`/community?${params}`);
  },

  async createPost(payload) {
    return request("/community/posts", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getPost(id) {
    return request(`/community/posts/${id}`);
  },

  async deletePost(id) {
    return request(`/community/posts/${id}`, { method: "DELETE" });
  },

  async reportPost(id) {
    return request(`/community/posts/${id}/report`, { method: "POST" });
  },

  async getComments(postId) {
    return request(`/community/posts/${postId}/comments`);
  },

  async createComment(payload) {
    return request("/community/comments", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async deleteComment(id) {
    return request(`/community/comments/${id}`, { method: "DELETE" });
  },

  async toggleLike(target_type, target_id) {
    return request("/community/likes", {
      method: "POST",
      body: JSON.stringify({ target_type, target_id }),
    });
  },

  async getNotifications() {
    return request("/community/notifications");
  },

  async markAllNotificationsRead() {
    return request("/community/notifications/read-all", { method: "POST" });
  },
};

// ── AI ────────────────────────────────────────────────────────────────────────
const ai = {
  async chat(message, { project_id, idea_id } = {}) {
    return request("/ai/chat", {
      method: "POST",
      body: JSON.stringify({ message, project_id, idea_id }),
    });
  },

  async recommendTechStack(payload) {
    return request("/ai/tech-stack", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getRecommendations(limit = 6) {
    return request("/ai/recommendations", {
      method: "POST",
      body: JSON.stringify({ limit }),
    });
  },
};

// ── Health check ──────────────────────────────────────────────────────────────
async function checkHealth({ timeoutMs = 4000 } = {}) {
  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
  try {
    const res = await fetch(HEALTH_URL, {
      method: "GET",
      ...(controller ? { signal: controller.signal } : {}),
    });
    return res.ok;
  } catch {
    return false;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

// ── Exports ───────────────────────────────────────────────────────────────────
export const api = {
  auth,
  ideas,
  projects,
  community,
  ai,
  checkHealth,
  ApiError,
  TokenStore,
  config: { apiBaseUrl: API_BASE_URL, healthUrl: HEALTH_URL },
};
export default api;
