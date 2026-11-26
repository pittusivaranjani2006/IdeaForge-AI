/**
 * IdeaForge AI — Main Application
 *
 * Architecture:
 *  - Hash-based SPA router (unchanged from original)
 *  - All data operations go through api.js (backend)
 *  - localStorage used only for theme + UI preferences
 *  - Existing UI rendering functions preserved and extended
 */

import api from "./api.js";

// ─────────────────────────────────────────────────────────────────────────────
// Constants (preserved from original)
// ─────────────────────────────────────────────────────────────────────────────
const app = document.getElementById("app");

const domains = [
  "Web Development", "AI/ML", "Cybersecurity",
  "IoT", "Blockchain", "FinTech",
];

const ideaTypes = ["Latest", "Trending", "Innovative"];

const starterSnippet = `<div class="problem-solution">
  <h2>Prototype</h2>
  <button id="runBtn">Test Idea</button>
</div>
<script>
document.getElementById("runBtn").addEventListener("click", () => {
  alert("Prototype interaction works!");
});
<\/script>`;

// ─────────────────────────────────────────────────────────────────────────────
// Local state (non-sensitive UI state only)
// ─────────────────────────────────────────────────────────────────────────────
const store = {
  get: (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};

const state = {
  user: null,          // populated from api.auth.getMe() after login
  theme: store.get("if_theme", "dark"),
  filter: { q: "", domain: "All", difficulty: "All", sort: "popular" },
  // cached from last API call to avoid re-fetching on every render
  ideasCache: [],
  generatedIdeasCache: [],
  savedIdeaIds: new Set(),
};

function saveTheme() { store.set("if_theme", state.theme); }

// ─────────────────────────────────────────────────────────────────────────────
// Theme
// ─────────────────────────────────────────────────────────────────────────────
function setTheme() {
  document.body.classList.toggle("light", state.theme === "light");
}

// ─────────────────────────────────────────────────────────────────────────────
// Utilities (preserved)
// ─────────────────────────────────────────────────────────────────────────────
function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function debounce(fn, ms = 300) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

function buildTechBadges(tech) {
  return (tech || []).map(t => `<span class="pill tech">${escapeHtml(t)}</span>`).join("");
}

function diffClass(d) {
  return `difficulty-${(d || "medium").toLowerCase()}`;
}

function toast(msg, type = "info") {
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function showLoader(container) {
  if (container) container.innerHTML = `<div class="loader-wrap"><div class="loader"></div></div>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Auth pages (rewritten to use backend)
// ─────────────────────────────────────────────────────────────────────────────
function showAuth(mode = "login") {
  setTheme();
  app.innerHTML = `
    <div class="auth-wrap">
      <div class="auth-card glass">
        <h1 class="auth-title">IdeaForge AI</h1>
        <p class="muted">${mode === "login" ? "Welcome back — sign in to continue" : "Create your innovation account"}</p>
        <div id="authError" class="auth-error" style="display:none;"></div>
        <form id="authForm">
          <input type="email" name="email" placeholder="Email address" required autocomplete="email"/>
          <input type="password" name="password" placeholder="Password (min 8 chars, uppercase + number)" required autocomplete="${mode === "login" ? "current-password" : "new-password"}"/>
          ${mode === "signup" ? '<input type="text" name="name" placeholder="Your full name" required/>' : ""}
          <button class="btn btn-primary" type="submit" id="authSubmit">
            ${mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>
        <p class="muted" style="margin-top:14px;">
          ${mode === "login" ? "New here?" : "Already have an account?"}
          <a href="#" id="switchAuth">${mode === "login" ? "Sign up" : "Sign in"}</a>
        </p>
      </div>
    </div>`;

  document.getElementById("switchAuth").onclick = e => { e.preventDefault(); showAuth(mode === "login" ? "signup" : "login"); };

  document.getElementById("authForm").onsubmit = async e => {
    e.preventDefault();
    const form = new FormData(e.target);
    const email = String(form.get("email") || "").trim().toLowerCase();
    const password = String(form.get("password") || "");
    const name = String(form.get("name") || "").trim();
    const btn = document.getElementById("authSubmit");
    const errEl = document.getElementById("authError");

    // Basic client-side validation (matches backend rules)
    const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    const validPassword = /^(?=.*[A-Z])(?=.*\d).{8,}$/.test(password);
    if (!validEmail) { showAuthError("Please enter a valid email address."); return; }
    if (!validPassword) { showAuthError("Password needs 8+ chars, one uppercase letter, and one number."); return; }
    if (mode === "signup" && !name) { showAuthError("Please enter your name."); return; }

    btn.disabled = true;
    btn.textContent = mode === "login" ? "Signing in…" : "Creating account…";
    errEl.style.display = "none";

    try {
      if (mode === "signup") {
        await api.auth.register(email, password, name);
      } else {
        await api.auth.login(email, password);
      }
      state.user = await api.auth.getMe();
      window.location.hash = "#/explorer";
      render();
    } catch (err) {
      showAuthError(err.message || "Something went wrong. Please try again.");
      btn.disabled = false;
      btn.textContent = mode === "login" ? "Sign In" : "Create Account";
    }
  };

  function showAuthError(msg) {
    const el = document.getElementById("authError");
    el.textContent = msg;
    el.style.display = "block";
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Base layout (preserved nav + extended with new links)
// ─────────────────────────────────────────────────────────────────────────────
function baseLayout(content) {
  const links = [
    ["#/explorer",   "Explorer"],
    ["#/generator",  "AI Generator"],
    ["#/evaluator",  "AI Evaluator"],
    ["#/workspace",  "Workspace"],
    ["#/community",  "Community"],
    ["#/dashboard",  "Dashboard"],
  ];
  const hash = location.hash || "#/explorer";
  return `
    <div class="container topbar glass">
      <div class="row">
        <strong class="brand">IdeaForge AI</strong>
        <nav>
          ${links.map(([href, label]) =>
            `<a class="nav-link ${hash.startsWith(href) ? "active" : ""}" href="${href}">${label}</a>`
          ).join("")}
        </nav>
        <div class="row">
          <button class="btn btn-ghost" id="themeBtn">${state.theme === "dark" ? "Light" : "Dark"} Mode</button>
          <span class="user-chip" id="userChip">${escapeHtml(state.user?.name?.split(" ")[0] || "")}</span>
          <button class="btn btn-ghost" id="logoutBtn">Logout</button>
        </div>
      </div>
    </div>
    <main class="container">
      ${content}
    </main>
    ${chatUI()}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Explorer page (preserved + wired to backend)
// ─────────────────────────────────────────────────────────────────────────────
function explorerPage() {
  return `
    <section class="hero glass glow">
      <h1>Discover Real-World Problem Statements</h1>
      <p>Search, filter, save, discuss, and build. Your innovation journey starts here.</p>
    </section>

    <section class="toolbar glass">
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));align-items:end;gap:16px;">
        <div class="field">
          <label>Search</label>
          <input id="searchInput" placeholder="Search by title or tags…" value="${escapeHtml(state.filter.q)}"/>
        </div>
        <div class="field">
          <label>Domain</label>
          <select id="domainSelect">
            <option>All</option>
            ${domains.map(d => `<option ${d === state.filter.domain ? "selected" : ""}>${escapeHtml(d)}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label>Difficulty</label>
          <select id="difficultySelect">
            <option>All</option>
            ${["Easy","Medium","Hard"].map(d => `<option ${d === state.filter.difficulty ? "selected" : ""}>${d}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label>Sort</label>
          <select id="sortSelect">
            <option value="popular" ${state.filter.sort === "popular" ? "selected" : ""}>Popular</option>
            <option value="latest"  ${state.filter.sort === "latest"  ? "selected" : ""}>Latest</option>
          </select>
        </div>
      </div>
    </section>

    <h3 class="section-title">Problem Explorer</h3>
    <div class="grid cards" id="explorerList">
      <div class="loader-wrap"><div class="loader"></div></div>
    </div>
    <p class="muted" id="explorerEmpty" style="display:none;margin-top:10px;">
      No matches. Try clearing filters or searching different tags.
    </p>`;
}

async function loadExplorerIdeas() {
  const list = document.getElementById("explorerList");
  const empty = document.getElementById("explorerEmpty");
  if (!list) return;

  try {
    const { items, total } = await api.ideas.list({
      domain:     state.filter.domain !== "All" ? state.filter.domain : undefined,
      difficulty: state.filter.difficulty !== "All" ? state.filter.difficulty : undefined,
      q:          state.filter.q || undefined,
      sort:       state.filter.sort,
      page_size:  30,
    });
    state.ideasCache = items;
    items.forEach(i => { if (i.is_saved) state.savedIdeaIds.add(i.id); });

    list.innerHTML = items.length
      ? items.map(p => renderProblemCard(p)).join("")
      : "";
    if (empty) empty.style.display = items.length ? "none" : "block";

    list.querySelectorAll(".favorite-btn").forEach(btn => {
      btn.onclick = () => toggleSave(Number(btn.dataset.id), btn);
    });
  } catch (err) {
    list.innerHTML = `<p class="muted">Could not load ideas: ${escapeHtml(err.message)}</p>`;
  }
}

function renderProblemCard(p, { compact = false } = {}) {
  const isSaved = state.savedIdeaIds.has(p.id);
  const tags = `<span class="pill">${escapeHtml(p.domain)}</span>`;
  const techTags = (p.tech_stack || p.tags || []).slice(0, compact ? 2 : 4)
    .map(t => `<span class="pill ghost">${escapeHtml(t)}</span>`).join("");
  const cardClass = compact ? "mini-card glass" : "problem-card glass";
  return `
    <article class="${cardClass}">
      <div class="row">
        <strong>${escapeHtml(p.title)}</strong>
        <span class="${diffClass(p.difficulty)}">${escapeHtml(p.difficulty)}</span>
      </div>
      <div class="muted">${escapeHtml(p.short_description || p.short || "")}</div>
      <div>${tags}${techTags}</div>
      <div class="row">
        <a class="btn btn-ghost" href="#/problem/${p.id}">Open</a>
        <div class="row" style="justify-content:flex-end;gap:8px;">
          <span class="muted" title="Popularity">▲ ${p.popularity_score || 0}</span>
          <button class="btn ${isSaved ? "btn-saved" : "btn-primary"} favorite-btn" data-id="${p.id}">
            ${isSaved ? "Saved ✓" : "Save"}
          </button>
        </div>
      </div>
    </article>`;
}

async function toggleSave(ideaId, btn) {
  const isSaved = state.savedIdeaIds.has(ideaId);
  try {
    if (isSaved) {
      await api.ideas.unsave(ideaId);
      state.savedIdeaIds.delete(ideaId);
      btn.textContent = "Save";
      btn.className = "btn btn-primary favorite-btn";
      toast("Removed from saved ideas", "info");
    } else {
      await api.ideas.save(ideaId);
      state.savedIdeaIds.add(ideaId);
      btn.textContent = "Saved ✓";
      btn.className = "btn btn-saved favorite-btn";
      toast("Idea saved!", "success");
    }
  } catch (err) {
    toast(err.message, "error");
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Problem Detail page (preserved + wired to backend)
// ─────────────────────────────────────────────────────────────────────────────
async function detailPage(id) {
  // Show skeleton while loading
  app.innerHTML = baseLayout(`
    <section class="detail glass glow">
      <div class="skeleton" style="height:120px;margin-bottom:14px;"></div>
      <div class="skeleton" style="height:200px;"></div>
    </section>`);
  wireBaseEvents();

  try {
    const p = await api.ideas.get(Number(id));
    const isSaved = state.savedIdeaIds.has(p.id);
    if (p.is_saved) state.savedIdeaIds.add(p.id);

    // Related ideas from cache
    const related = state.ideasCache
      .filter(x => x.id !== p.id && x.domain === p.domain)
      .slice(0, 4);

    // Comments for this idea from community
    let comments = [];
    try {
      const postsRes = await api.community.listPosts({ q: p.title, page_size: 1 });
      if (postsRes.items.length) {
        comments = await api.community.getComments(postsRes.items[0].id);
      }
    } catch {}

    app.innerHTML = baseLayout(renderDetailHTML(p, isSaved || p.is_saved, related, comments));
    wireBaseEvents();
    wireDetailEvents(p, comments);
  } catch (err) {
    app.innerHTML = baseLayout(`
      <div class="glass detail panel">
        <h2>Could not load idea</h2>
        <p class="muted">${escapeHtml(err.message)}</p>
        <a class="btn btn-primary" href="#/explorer">Back to Explorer</a>
      </div>`);
    wireBaseEvents();
  }
}

function renderDetailHTML(p, isSaved, related, comments) {
  const steps = p.implementation_steps || [];
  const tech  = p.tech_stack || [];
  const future = p.future_enhancements || [];

  return `
    <section class="detail glass glow">
      <div class="two-col">
        <div class="list">
          <div class="glass panel">
            <div class="row">
              <div>
                <div class="muted">${escapeHtml(p.domain)} • <span class="${diffClass(p.difficulty)}">${escapeHtml(p.difficulty)}</span></div>
                <h2 style="margin:6px 0 0;">${escapeHtml(p.title)}</h2>
              </div>
              <button class="btn ${isSaved ? "btn-saved" : "btn-primary"} favorite-btn" data-id="${p.id}">
                ${isSaved ? "Saved ✓" : "Save"}
              </button>
            </div>
            <div class="divider"></div>
            <div class="muted">${escapeHtml(p.short_description || "")}</div>
          </div>

          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">🧠</div><h3>Description</h3></div>
            <p class="muted" style="margin:0;">${escapeHtml(p.full_description || "")}</p>
          </div>

          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">🧩</div><h3>Problem Statement</h3></div>
            <p style="margin:0;">${escapeHtml(p.problem_statement || `Build a solution that solves: ${p.short_description}`)}</p>
          </div>

          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">🌍</div><h3>Real-world Use Case</h3></div>
            <p class="muted" style="margin:0;">${escapeHtml(p.relevance || "")}</p>
          </div>

          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">🛠️</div><h3>Step-by-step Implementation</h3></div>
            <ol style="margin:0;padding-left:18px;">${steps.map(s => `<li>${escapeHtml(s)}</li>`).join("")}</ol>
          </div>

          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">🧰</div><h3>Tech Stack</h3></div>
            <div>${buildTechBadges(tech)}</div>
          </div>

          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">✨</div><h3>Future Scope</h3></div>
            <ul style="margin:0;padding-left:18px;">${future.map(f => `<li>${escapeHtml(f)}</li>`).join("")}</ul>
          </div>

          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">💻</div><h3>Starter Code Snippet</h3></div>
            <pre>${escapeHtml(starterSnippet)}</pre>
            <div class="row" style="margin-top:10px;">
              <button class="btn btn-ghost" id="shareBtn">Share</button>
              <button class="btn btn-ghost" id="pdfBtn">Export PDF</button>
              <button class="btn btn-primary" id="createProjectBtn">Create Project →</button>
            </div>
          </div>
        </div>

        <div class="list">
          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">🖼️</div><h3>UI Preview</h3></div>
            <div class="mock-ui">
              <div class="pill">Header + Search</div>
              <div class="pill">Key Insights</div>
              <div class="pill">Primary CTA</div>
              <div class="pill">Activity + Comments</div>
            </div>
          </div>

          ${related.length ? `
          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">🔁</div><h3>Related Ideas</h3></div>
            <div class="list">
              ${related.map(r => `
                <a class="mini-card glass" href="#/problem/${r.id}">
                  <strong>${escapeHtml(r.title)}</strong>
                  <div class="muted">${escapeHtml(r.short_description || "")}</div>
                </a>`).join("")}
            </div>
          </div>` : ""}

          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">🤖</div><h3>AI Tech Stack</h3></div>
            <div id="techStackPanel">
              <button class="btn btn-ghost" id="getTechBtn" style="width:100%;">
                Get AI Tech Stack Recommendation
              </button>
            </div>
          </div>

          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">💬</div><h3>Discussion</h3></div>
            <form id="commentForm">
              <textarea name="comment" placeholder="Ask a question, share an approach, or post resources…" required></textarea>
              <button class="btn btn-primary" type="submit">Post Comment</button>
            </form>
            <div class="divider"></div>
            <div class="list" id="commentsList">
              ${renderComments(comments)}
            </div>
          </div>
        </div>
      </div>
    </section>`;
}

function renderComments(comments) {
  if (!comments.length) return `<p class="muted">No comments yet. Be the first!</p>`;
  return comments.map(c => `
    <div class="comment">
      <div class="comment-meta">${escapeHtml(c.author?.name || "User")} · ${timeAgo(c.created_at)}</div>
      <div>${escapeHtml(c.content)}</div>
    </div>`).join("");
}

function wireDetailEvents(p, existingComments) {
  document.querySelector(".favorite-btn")?.addEventListener("click", async e => {
    const btn = e.currentTarget;
    await toggleSave(p.id, btn);
  });

  document.getElementById("shareBtn")?.addEventListener("click", async () => {
    try {
      if (navigator.share) await navigator.share({ title: p.title, url: location.href });
      else { await navigator.clipboard.writeText(location.href); toast("Link copied!", "success"); }
    } catch {}
  });

  document.getElementById("pdfBtn")?.addEventListener("click", () => window.print());

  document.getElementById("createProjectBtn")?.addEventListener("click", async () => {
    try {
      const proj = await api.projects.create({
        title: p.title,
        description: p.short_description,
        domain: p.domain,
        tech_stack: p.tech_stack || [],
      });
      toast("Project created!", "success");
      window.location.hash = `#/project/${proj.id}`;
      render();
    } catch (err) { toast(err.message, "error"); }
  });

  document.getElementById("getTechBtn")?.addEventListener("click", async () => {
    const panel = document.getElementById("techStackPanel");
    panel.innerHTML = `<div class="loader-wrap"><div class="loader"></div></div>`;
    try {
      const res = await api.ai.recommendTechStack({
        project_description: `${p.title}: ${p.full_description}`,
        domain: p.domain,
      });
      panel.innerHTML = `
        <p class="muted" style="font-size:.85rem;">${escapeHtml(res.summary || "")}</p>
        ${(res.recommendations || []).map(r => `
          <div style="margin-top:10px;">
            <strong style="font-size:.9rem;">${escapeHtml(r.category)}</strong>
            <div>${(r.technologies || []).map(t => `<span class="pill tech">${escapeHtml(t)}</span>`).join("")}</div>
            <div class="muted" style="font-size:.8rem;margin-top:4px;">${escapeHtml(r.reason || "")}</div>
          </div>`).join("")}
        <p class="muted" style="font-size:.75rem;margin-top:12px;">${escapeHtml(res.disclaimer || "")}</p>`;
    } catch (err) {
      panel.innerHTML = `<p class="muted">${escapeHtml(err.message)}</p>`;
    }
  });

  // Comment form — posts to community
  document.getElementById("commentForm")?.addEventListener("submit", async e => {
    e.preventDefault();
    const text = String(new FormData(e.target).get("comment") || "").trim();
    if (!text) return;
    try {
      // Find or create a post for this idea
      let postId = null;
      try {
        const postsRes = await api.community.listPosts({ q: p.title, page_size: 1 });
        if (postsRes.items.length && postsRes.items[0].title === p.title) {
          postId = postsRes.items[0].id;
        }
      } catch {}
      if (!postId) {
        const post = await api.community.createPost({
          title: p.title,
          content: `Discussion for: ${p.short_description}`,
          idea_id: p.id,
          post_type: "discussion",
        });
        postId = post.id;
      }
      await api.community.createComment({ post_id: postId, content: text });
      toast("Comment posted!", "success");
      e.target.reset();
      // Refresh comments
      const comments = await api.community.getComments(postId);
      document.getElementById("commentsList").innerHTML = renderComments(comments);
    } catch (err) { toast(err.message, "error"); }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Generator page
// ─────────────────────────────────────────────────────────────────────────────
function generatorPage() {
  return `
    <section class="hero glass glow">
      <h1>AI Idea Generator</h1>
      <p>Describe what you want to build and get detailed, actionable project ideas powered by AI.</p>
    </section>

    <section class="glass panel">
      <h3 style="margin:0 0 16px;">Configure Your Idea</h3>
      <div class="generator-grid">
        <div class="field">
          <label>Domain</label>
          <select id="genDomain">
            ${domains.map(d => `<option>${escapeHtml(d)}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label>Difficulty</label>
          <select id="genDifficulty">
            ${["Easy","Medium","Hard"].map(d => `<option>${d}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label>Purpose</label>
          <select id="genPurpose">
            ${["Mini Project","Major Project","Hackathon","Startup"].map(p => `<option>${p}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label>Team Size</label>
          <select id="genTeam">
            <option value="1">Solo (1)</option>
            <option value="2">2 people</option>
            <option value="3">3 people</option>
            <option value="4">4 people</option>
            <option value="5" selected>5 people</option>
          </select>
        </div>
        <div class="field">
          <label>Duration</label>
          <select id="genDuration">
            <option value="2">2 weeks</option>
            <option value="4" selected>4 weeks</option>
            <option value="8">8 weeks</option>
            <option value="12">12 weeks</option>
            <option value="24">6 months</option>
          </select>
        </div>
        <div class="field">
          <label>Budget</label>
          <select id="genBudget">
            <option>Free / No budget</option>
            <option>Low (&lt;$100)</option>
            <option>Medium ($100-$500)</option>
            <option>High ($500+)</option>
          </select>
        </div>
        <div class="field">
          <label>Preferred Language</label>
          <select id="genLang">
            <option value="">Any</option>
            ${["Python","JavaScript","TypeScript","Java","Kotlin","Swift","Go","Rust","C++","C#"].map(l => `<option>${l}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label>Number of Ideas</label>
          <select id="genCount">
            ${[3,5,7,10].map(n => `<option value="${n}" ${n===5?"selected":""}>${n} ideas</option>`).join("")}
          </select>
        </div>
      </div>
      <button class="btn btn-primary" id="generateBtn" style="margin-top:16px;width:100%;padding:14px;">
        ✨ Generate Ideas with AI
      </button>
    </section>

    <div id="generatedResults"></div>`;
}

async function wireGeneratorEvents() {
  document.getElementById("generateBtn")?.addEventListener("click", async () => {
    const btn = document.getElementById("generateBtn");
    const results = document.getElementById("generatedResults");
    btn.disabled = true;
    btn.textContent = "Generating…";
    results.innerHTML = `
      <div class="glass panel" style="margin-top:14px;">
        <div class="loader-wrap"><div class="loader"></div></div>
        <p class="muted" style="text-align:center;margin-top:12px;">AI is generating personalized ideas for you…</p>
      </div>`;

    try {
      const payload = {
        domain:            document.getElementById("genDomain").value,
        difficulty:        document.getElementById("genDifficulty").value,
        purpose:           document.getElementById("genPurpose").value,
        team_size:         Number(document.getElementById("genTeam").value),
        duration_weeks:    Number(document.getElementById("genDuration").value),
        budget:            document.getElementById("genBudget").value,
        preferred_language: document.getElementById("genLang").value || undefined,
        count:             Number(document.getElementById("genCount").value),
      };
      const { items } = await api.ideas.generate(payload);
      state.generatedIdeasCache = items;

      results.innerHTML = `
        <h3 class="section-title">Generated Ideas (${items.length})</h3>
        <div class="grid cards">
          ${items.map(idea => renderGeneratedIdeaCard(idea)).join("")}
        </div>`;

      results.querySelectorAll(".open-idea-btn").forEach(btn => {
        btn.onclick = () => { window.location.hash = `#/idea/${btn.dataset.id}`; render(); };
      });
      results.querySelectorAll(".create-project-btn").forEach(btn => {
        btn.onclick = () => createProjectFromIdea(btn.dataset.id);
      });
      toast(`${items.length} ideas generated!`, "success");
    } catch (err) {
      results.innerHTML = `
        <div class="glass panel" style="margin-top:14px;">
          <p class="muted">⚠️ ${escapeHtml(err.message)}</p>
          ${err.message.includes("not configured") ? `<p class="muted">Add your <strong>OPENAI_API_KEY</strong> to <code>backend/.env</code> to enable AI features.</p>` : ""}
        </div>`;
    }
    btn.disabled = false;
    btn.textContent = "✨ Generate Ideas with AI";
  });
}

function renderGeneratedIdeaCard(idea) {
  return `
    <article class="problem-card glass">
      <div class="row">
        <strong>${escapeHtml(idea.title)}</strong>
        <span class="${diffClass(idea.difficulty)}">${escapeHtml(idea.difficulty)}</span>
      </div>
      <div class="muted">${escapeHtml(idea.problem_statement || "")}</div>
      <div class="muted" style="font-size:.82rem;margin-top:4px;">${escapeHtml(idea.proposed_solution || "")}</div>
      <div>${buildTechBadges(idea.tech_stack || [])}</div>
      <div class="row" style="margin-top:8px;">
        <button class="btn btn-ghost open-idea-btn" data-id="${idea.id}">View Details</button>
        <button class="btn btn-primary create-project-btn" data-id="${idea.id}">Create Project</button>
      </div>
    </article>`;
}

async function createProjectFromIdea(ideaId) {
  const idea = state.generatedIdeasCache.find(i => String(i.id) === String(ideaId));
  if (!idea) return;
  try {
    const proj = await api.projects.create({
      title: idea.title,
      description: idea.problem_statement || idea.proposed_solution || "",
      domain: idea.domain,
      tech_stack: idea.tech_stack || [],
      generated_idea_id: idea.id,
    });
    toast("Project created from idea!", "success");
    window.location.hash = `#/project/${proj.id}`;
    render();
  } catch (err) { toast(err.message, "error"); }
}

// ─────────────────────────────────────────────────────────────────────────────
// Generated Idea Detail page
// ─────────────────────────────────────────────────────────────────────────────
async function ideaDetailPage(id) {
  app.innerHTML = baseLayout(`<div class="glass panel"><div class="loader-wrap"><div class="loader"></div></div></div>`);
  wireBaseEvents();
  try {
    // Try cache first
    let idea = state.generatedIdeasCache.find(i => String(i.id) === String(id));
    if (!idea) {
      const { items } = await api.ideas.myGenerated({ page_size: 50 });
      idea = items.find(i => String(i.id) === String(id));
    }
    if (!idea) throw new Error("Idea not found");
    app.innerHTML = baseLayout(renderGeneratedDetailHTML(idea));
    wireBaseEvents();
    document.getElementById("createProjFromIdea")?.addEventListener("click", () => createProjectFromIdea(id));
    document.getElementById("evaluateIdeaBtn")?.addEventListener("click", () => {
      window.location.hash = `#/evaluator?id=${id}`;
      render();
    });
  } catch (err) {
    app.innerHTML = baseLayout(`
      <div class="glass panel detail">
        <h2>Idea not found</h2>
        <p class="muted">${escapeHtml(err.message)}</p>
        <a class="btn btn-primary" href="#/generator">Generate New Ideas</a>
      </div>`);
    wireBaseEvents();
  }
}

function renderGeneratedDetailHTML(idea) {
  return `
    <section class="detail glass glow">
      <div class="two-col">
        <div class="list">
          <div class="glass panel">
            <div class="row">
              <div>
                <div class="muted">${escapeHtml(idea.domain)} • <span class="${diffClass(idea.difficulty)}">${escapeHtml(idea.difficulty)}</span> • ${escapeHtml(idea.purpose || "")}</div>
                <h1 style="margin:8px 0 0;font-size:clamp(1.4rem,3vw,2rem);">${escapeHtml(idea.title)}</h1>
              </div>
              <a class="btn btn-ghost" href="#/generator">← Back</a>
            </div>
          </div>

          ${idea.problem_statement ? `<div class="glass panel"><div class="icon-title"><div class="icon-badge">🧩</div><h3>Problem Statement</h3></div><p style="margin:0;">${escapeHtml(idea.problem_statement)}</p></div>` : ""}
          ${idea.proposed_solution ? `<div class="glass panel"><div class="icon-title"><div class="icon-badge">💡</div><h3>Proposed Solution</h3></div><p class="muted" style="margin:0;">${escapeHtml(idea.proposed_solution)}</p></div>` : ""}
          ${idea.innovation ? `<div class="glass panel"><div class="icon-title"><div class="icon-badge">🚀</div><h3>Innovation</h3></div><p class="muted" style="margin:0;">${escapeHtml(idea.innovation)}</p></div>` : ""}
          ${idea.target_audience ? `<div class="glass panel"><div class="icon-title"><div class="icon-badge">🎯</div><h3>Target Audience</h3></div><p class="muted" style="margin:0;">${escapeHtml(idea.target_audience)}</p></div>` : ""}

          ${idea.implementation_roadmap?.length ? `
          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">🗺️</div><h3>Implementation Roadmap</h3></div>
            <ol style="margin:0;padding-left:18px;">${idea.implementation_roadmap.map(s => `<li>${escapeHtml(s)}</li>`).join("")}</ol>
          </div>` : ""}

          ${idea.tech_stack?.length ? `
          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">🧰</div><h3>Tech Stack</h3></div>
            ${buildTechBadges(idea.tech_stack)}
          </div>` : ""}

          <div class="glass panel">
            <div class="row">
              <button class="btn btn-primary" id="createProjFromIdea">Create Project</button>
              <button class="btn btn-ghost" id="evaluateIdeaBtn">Evaluate with AI</button>
            </div>
          </div>
        </div>

        <div class="list">
          ${idea.real_world_applications ? `<div class="glass panel"><div class="icon-title"><div class="icon-badge">🌍</div><h3>Real-world Applications</h3></div><p class="muted" style="margin:0;">${escapeHtml(idea.real_world_applications)}</p></div>` : ""}
          ${idea.expected_outcomes ? `<div class="glass panel"><div class="icon-title"><div class="icon-badge">📊</div><h3>Expected Outcomes</h3></div><p class="muted" style="margin:0;">${escapeHtml(idea.expected_outcomes)}</p></div>` : ""}
          ${idea.future_enhancements?.length ? `
          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">✨</div><h3>Future Enhancements</h3></div>
            <ul style="margin:0;padding-left:18px;">${idea.future_enhancements.map(f => `<li>${escapeHtml(f)}</li>`).join("")}</ul>
          </div>` : ""}
          ${idea.requirements?.length ? `
          <div class="glass panel">
            <div class="icon-title"><div class="icon-badge">📋</div><h3>Requirements</h3></div>
            <ul style="margin:0;padding-left:18px;">${idea.requirements.map(r => `<li>${escapeHtml(r)}</li>`).join("")}</ul>
          </div>` : ""}
        </div>
      </div>
    </section>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Evaluator page
// ─────────────────────────────────────────────────────────────────────────────
function evaluatorPage(params) {
  const ideaId = params?.get("id");
  const prefilledIdea = ideaId ? state.generatedIdeasCache.find(i => String(i.id) === ideaId) : null;

  return `
    <section class="hero glass glow">
      <h1>AI Idea Evaluator</h1>
      <p>Get an objective AI-powered assessment of your project idea across 6 key dimensions.</p>
    </section>

    <section class="glass panel">
      <h3 style="margin:0 0 16px;">Describe Your Idea</h3>
      <form id="evalForm">
        <div class="field">
          <label>Project Title</label>
          <input type="text" id="evalTitle" placeholder="e.g. Smart Traffic Management System" required value="${escapeHtml(prefilledIdea?.title || "")}"/>
        </div>
        <div class="field">
          <label>Project Description</label>
          <textarea id="evalDescription" rows="5" placeholder="Describe your idea in detail — the problem it solves, your proposed approach, target users, and key features…" required>${escapeHtml(prefilledIdea ? `${prefilledIdea.problem_statement || ""}\n\n${prefilledIdea.proposed_solution || ""}` : "")}</textarea>
        </div>
        <button class="btn btn-primary" type="submit" style="width:100%;padding:14px;">
          🔍 Evaluate My Idea
        </button>
      </form>
    </section>

    <div id="evalResults"></div>`;
}

async function wireEvaluatorEvents(params) {
  const ideaId = params?.get("id");
  document.getElementById("evalForm")?.addEventListener("submit", async e => {
    e.preventDefault();
    const title = document.getElementById("evalTitle").value.trim();
    const description = document.getElementById("evalDescription").value.trim();
    const results = document.getElementById("evalResults");
    const btn = e.target.querySelector("button[type=submit]");
    btn.disabled = true;
    btn.textContent = "Evaluating…";
    results.innerHTML = `
      <div class="glass panel" style="margin-top:14px;">
        <div class="loader-wrap"><div class="loader"></div></div>
        <p class="muted" style="text-align:center;margin-top:12px;">AI is analysing your idea…</p>
      </div>`;

    try {
      const ev = await api.ideas.evaluate({
        title,
        description,
        generated_idea_id: ideaId ? Number(ideaId) : undefined,
      });
      results.innerHTML = renderEvaluationHTML(ev);
    } catch (err) {
      results.innerHTML = `<div class="glass panel" style="margin-top:14px;"><p class="muted">⚠️ ${escapeHtml(err.message)}</p></div>`;
    }
    btn.disabled = false;
    btn.textContent = "🔍 Evaluate My Idea";
  });
}

function renderEvaluationHTML(ev) {
  const scores = [
    { label: "Innovation",           val: ev.innovation_score },
    { label: "Feasibility",          val: ev.feasibility_score },
    { label: "Technical Complexity", val: ev.technical_complexity_score },
    { label: "Social Impact",        val: ev.social_impact_score },
    { label: "Scalability",          val: ev.scalability_score },
    { label: "Cost Effectiveness",   val: ev.cost_effectiveness_score },
  ];

  const scoreColor = v => v >= 70 ? "var(--accent)" : v >= 45 ? "var(--primary)" : "var(--danger)";

  return `
    <div class="glass panel" style="margin-top:14px;">
      <h3>Evaluation Results: ${escapeHtml(ev.idea_title)}</h3>
      <div class="eval-overall">
        <div class="eval-score-ring" style="--score:${ev.overall_score};">
          <span>${Math.round(ev.overall_score)}</span>
          <small>/100</small>
        </div>
        <div>
          <strong>Overall Score</strong>
          <div class="muted">AI-generated estimate</div>
        </div>
      </div>

      <div class="eval-scores">
        ${scores.map(s => `
          <div class="eval-score-row">
            <span>${escapeHtml(s.label)}</span>
            <div class="score-bar-wrap">
              <div class="score-bar" style="width:${s.val}%;background:${scoreColor(s.val)};"></div>
            </div>
            <span style="color:${scoreColor(s.val)};font-weight:600;">${Math.round(s.val)}</span>
          </div>`).join("")}
      </div>

      <div class="two-col" style="margin-top:20px;">
        <div class="list">
          ${renderEvalSection("💪 Strengths", ev.strengths)}
          ${renderEvalSection("⚠️ Weaknesses", ev.weaknesses)}
          ${renderEvalSection("🔧 Missing Features", ev.missing_features)}
        </div>
        <div class="list">
          ${renderEvalSection("💡 Improvement Suggestions", ev.improvement_suggestions)}
          ${renderEvalSection("⚡ Technical Challenges", ev.technical_challenges)}
          ${renderEvalSection("🔴 Potential Risks", ev.potential_risks)}
          ${renderEvalSection("🔗 Similar Solutions", ev.similar_solutions)}
        </div>
      </div>

      <div class="disclaimer-box">${escapeHtml(ev.ai_disclaimer)}</div>
    </div>`;
}

function renderEvalSection(title, items) {
  if (!items?.length) return "";
  return `
    <div class="glass panel">
      <strong>${title}</strong>
      <ul style="margin:8px 0 0;padding-left:18px;">
        ${items.map(i => `<li class="muted">${escapeHtml(i)}</li>`).join("")}
      </ul>
    </div>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Workspace page
// ─────────────────────────────────────────────────────────────────────────────
async function workspacePage() {
  app.innerHTML = baseLayout(`
    <section class="hero glass">
      <h1>My Workspace</h1>
      <p>All your projects, generated ideas, and saved problems in one place.</p>
    </section>
    <div class="workspace-tabs">
      <button class="tab-btn active" data-tab="projects">Projects</button>
      <button class="tab-btn" data-tab="ideas">Generated Ideas</button>
      <button class="tab-btn" data-tab="saved">Saved Problems</button>
    </div>
    <div id="workspaceContent">
      <div class="loader-wrap"><div class="loader"></div></div>
    </div>`);
  wireBaseEvents();
  wireWorkspaceTabs();
  await loadWorkspaceTab("projects");
}

function wireWorkspaceTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.onclick = async () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      await loadWorkspaceTab(btn.dataset.tab);
    };
  });
}

async function loadWorkspaceTab(tab) {
  const content = document.getElementById("workspaceContent");
  showLoader(content);
  try {
    if (tab === "projects") {
      const { items } = await api.projects.list({ page_size: 50 });
      content.innerHTML = renderProjectsTab(items);
      content.querySelector("#newProjectBtn")?.addEventListener("click", showNewProjectModal);
      content.querySelectorAll(".open-project-btn").forEach(btn => {
        btn.onclick = () => { window.location.hash = `#/project/${btn.dataset.id}`; render(); };
      });
      content.querySelectorAll(".delete-project-btn").forEach(btn => {
        btn.onclick = () => deleteProject(btn.dataset.id);
      });
    } else if (tab === "ideas") {
      const { items } = await api.ideas.myGenerated({ page_size: 50 });
      state.generatedIdeasCache = items;
      content.innerHTML = renderGeneratedIdeasTab(items);
      content.querySelectorAll(".open-idea-btn").forEach(btn => {
        btn.onclick = () => { window.location.hash = `#/idea/${btn.dataset.id}`; render(); };
      });
      content.querySelectorAll(".create-project-btn").forEach(btn => {
        btn.onclick = () => createProjectFromIdea(btn.dataset.id);
      });
    } else if (tab === "saved") {
      const { items } = await api.ideas.list({ page_size: 50 });
      const saved = items.filter(i => i.is_saved);
      content.innerHTML = renderSavedTab(saved);
      content.querySelectorAll(".favorite-btn").forEach(btn => {
        btn.onclick = () => toggleSave(Number(btn.dataset.id), btn);
      });
    }
  } catch (err) {
    content.innerHTML = `<p class="muted" style="padding:20px;">${escapeHtml(err.message)}</p>`;
  }
}

function renderProjectsTab(projects) {
  if (!projects.length) return `
    <div class="empty-state glass">
      <div class="empty-icon">🚀</div>
      <h3>No projects yet</h3>
      <p class="muted">Create your first project to start tracking your development journey.</p>
      <button class="btn btn-primary" id="newProjectBtn">Create Project</button>
    </div>`;

  return `
    <div class="row" style="margin-bottom:14px;">
      <h3 style="margin:0;">Projects (${projects.length})</h3>
      <button class="btn btn-primary" id="newProjectBtn">+ New Project</button>
    </div>
    <div class="grid cards">
      ${projects.map(p => `
        <article class="problem-card glass">
          <div class="row">
            <strong>${escapeHtml(p.title)}</strong>
            <span class="status-badge status-${p.status}">${escapeHtml(p.status)}</span>
          </div>
          <div class="muted">${escapeHtml(p.description || "")}</div>
          <div class="progress-wrap">
            <div class="progress-bar" style="width:${p.progress_pct}%;"></div>
          </div>
          <div class="muted" style="font-size:.8rem;">${p.progress_pct}% complete</div>
          <div>${buildTechBadges(p.tech_stack || [])}</div>
          <div class="row" style="margin-top:8px;">
            <button class="btn btn-ghost open-project-btn" data-id="${p.id}">Open</button>
            <button class="btn btn-ghost delete-project-btn" data-id="${p.id}" style="color:var(--danger);">Delete</button>
          </div>
        </article>`).join("")}
    </div>`;
}

function renderGeneratedIdeasTab(ideas) {
  if (!ideas.length) return `
    <div class="empty-state glass">
      <div class="empty-icon">💡</div>
      <h3>No generated ideas yet</h3>
      <p class="muted">Use the AI Generator to create personalized project ideas.</p>
      <a class="btn btn-primary" href="#/generator">Go to AI Generator</a>
    </div>`;

  return `
    <h3 style="margin:0 0 14px;">Generated Ideas (${ideas.length})</h3>
    <div class="grid cards">
      ${ideas.map(i => `
        <article class="problem-card glass">
          <div class="row">
            <strong>${escapeHtml(i.title)}</strong>
            <span class="${diffClass(i.difficulty)}">${escapeHtml(i.difficulty)}</span>
          </div>
          <div class="muted">${escapeHtml(i.problem_statement || "")}</div>
          <div class="muted" style="font-size:.8rem;">${escapeHtml(i.domain)} · ${timeAgo(i.created_at)}</div>
          <div>${buildTechBadges(i.tech_stack || [])}</div>
          <div class="row" style="margin-top:8px;">
            <button class="btn btn-ghost open-idea-btn" data-id="${i.id}">View</button>
            <button class="btn btn-primary create-project-btn" data-id="${i.id}">Create Project</button>
          </div>
        </article>`).join("")}
    </div>`;
}

function renderSavedTab(saved) {
  if (!saved.length) return `
    <div class="empty-state glass">
      <div class="empty-icon">🔖</div>
      <h3>No saved problems yet</h3>
      <p class="muted">Browse the Explorer and save problems that interest you.</p>
      <a class="btn btn-primary" href="#/explorer">Browse Explorer</a>
    </div>`;

  return `
    <h3 style="margin:0 0 14px;">Saved Problems (${saved.length})</h3>
    <div class="grid cards">
      ${saved.map(p => renderProblemCard(p)).join("")}
    </div>`;
}

async function deleteProject(id) {
  if (!confirm("Delete this project? This cannot be undone.")) return;
  try {
    await api.projects.delete(Number(id));
    toast("Project deleted", "info");
    await loadWorkspaceTab("projects");
  } catch (err) { toast(err.message, "error"); }
}

function showNewProjectModal() {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.innerHTML = `
    <div class="modal-card glass">
      <h3 style="margin:0 0 16px;">Create New Project</h3>
      <form id="newProjectForm">
        <div class="field"><label>Title</label><input name="title" placeholder="Project title" required/></div>
        <div class="field"><label>Description</label><textarea name="description" rows="3" placeholder="What is this project about?"></textarea></div>
        <div class="field"><label>Domain</label>
          <select name="domain">
            ${domains.map(d => `<option>${d}</option>`).join("")}
          </select>
        </div>
        <div class="field"><label>Duration (weeks)</label><input type="number" name="duration" placeholder="e.g. 4" min="1" max="52"/></div>
        <div class="row" style="margin-top:8px;">
          <button class="btn btn-ghost" type="button" id="cancelModal">Cancel</button>
          <button class="btn btn-primary" type="submit">Create Project</button>
        </div>
      </form>
    </div>`;
  document.body.appendChild(modal);
  document.getElementById("cancelModal").onclick = () => modal.remove();
  document.getElementById("newProjectForm").onsubmit = async e => {
    e.preventDefault();
    const form = new FormData(e.target);
    try {
      await api.projects.create({
        title: form.get("title"),
        description: form.get("description") || undefined,
        domain: form.get("domain"),
        duration_weeks: form.get("duration") ? Number(form.get("duration")) : undefined,
      });
      toast("Project created!", "success");
      modal.remove();
      await loadWorkspaceTab("projects");
    } catch (err) { toast(err.message, "error"); }
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Project Detail page (with Roadmap)
// ─────────────────────────────────────────────────────────────────────────────
async function projectDetailPage(id) {
  app.innerHTML = baseLayout(`<div class="glass panel"><div class="loader-wrap"><div class="loader"></div></div></div>`);
  wireBaseEvents();
  try {
    const proj = await api.projects.get(Number(id));
    app.innerHTML = baseLayout(renderProjectDetailHTML(proj));
    wireBaseEvents();
    wireProjectDetailEvents(proj);
  } catch (err) {
    app.innerHTML = baseLayout(`<div class="glass panel detail"><h2>Project not found</h2><p class="muted">${escapeHtml(err.message)}</p><a class="btn btn-primary" href="#/workspace">Back to Workspace</a></div>`);
    wireBaseEvents();
  }
}

function renderProjectDetailHTML(proj) {
  const roadmap = proj.roadmaps?.[0];
  const tasks = roadmap?.tasks || [];
  const weeks = [...new Set(tasks.map(t => t.week_number))].sort((a, b) => a - b);

  return `
    <div class="glass panel" style="margin-bottom:14px;">
      <div class="row">
        <div>
          <div class="muted"><a href="#/workspace">Workspace</a> → Projects</div>
          <h2 style="margin:4px 0 0;">${escapeHtml(proj.title)}</h2>
        </div>
        <span class="status-badge status-${proj.status}">${escapeHtml(proj.status)}</span>
      </div>
      <div class="muted" style="margin-top:8px;">${escapeHtml(proj.description || "")}</div>
      <div class="progress-wrap" style="margin:14px 0 6px;">
        <div class="progress-bar" style="width:${proj.progress_pct}%;"></div>
      </div>
      <div class="muted" style="font-size:.85rem;">${proj.progress_pct}% complete</div>
      <div style="margin-top:12px;">${buildTechBadges(proj.tech_stack || [])}</div>
    </div>

    ${roadmap ? renderRoadmapHTML(roadmap, weeks, tasks) : `
      <div class="glass panel">
        <h3>No Roadmap Yet</h3>
        <p class="muted">Generate an AI-powered roadmap for this project.</p>
        <button class="btn btn-primary" id="generateRoadmapBtn">Generate Roadmap with AI</button>
      </div>`}`;
}

function renderRoadmapHTML(roadmap, weeks, tasks) {
  return `
    <div class="glass panel">
      <div class="row">
        <h3 style="margin:0;">${escapeHtml(roadmap.title)}</h3>
        <span class="muted">${roadmap.total_weeks} weeks</span>
      </div>
      ${weeks.map(week => {
        const weekTasks = tasks.filter(t => t.week_number === week);
        return `
          <div class="week-block">
            <h4 class="week-title">Week ${week}</h4>
            ${weekTasks.map(task => `
              <div class="task-row ${task.status === "completed" ? "task-done" : ""}">
                <input type="checkbox" class="task-check" data-id="${task.id}" ${task.status === "completed" ? "checked" : ""}/>
                <div class="task-info">
                  <span>${task.is_milestone ? "🏁 " : ""}${escapeHtml(task.title)}</span>
                  ${task.phase ? `<span class="pill ghost" style="font-size:.75rem;">${escapeHtml(task.phase)}</span>` : ""}
                </div>
                ${task.estimated_hours ? `<span class="muted" style="font-size:.8rem;">${task.estimated_hours}h</span>` : ""}
              </div>`).join("")}
          </div>`;
      }).join("")}
      ${roadmap.learning_resources?.length ? `
        <div class="divider"></div>
        <strong>Learning Resources</strong>
        <ul style="margin:8px 0 0;padding-left:18px;">
          ${roadmap.learning_resources.map(r => `<li class="muted">${escapeHtml(r)}</li>`).join("")}
        </ul>` : ""}
    </div>`;
}

function wireProjectDetailEvents(proj) {
  document.getElementById("generateRoadmapBtn")?.addEventListener("click", async () => {
    const btn = document.getElementById("generateRoadmapBtn");
    btn.disabled = true;
    btn.textContent = "Generating…";
    try {
      await api.projects.generateRoadmap(proj.id);
      toast("Roadmap generated!", "success");
      await projectDetailPage(proj.id);
    } catch (err) {
      toast(err.message, "error");
      btn.disabled = false;
      btn.textContent = "Generate Roadmap with AI";
    }
  });

  document.querySelectorAll(".task-check").forEach(cb => {
    cb.onchange = async () => {
      const taskId = Number(cb.dataset.id);
      const newStatus = cb.checked ? "completed" : "todo";
      try {
        await api.projects.updateTask(taskId, { status: newStatus });
        const row = cb.closest(".task-row");
        if (row) row.classList.toggle("task-done", cb.checked);
        // Refresh project progress bar
        const updated = await api.projects.get(proj.id);
        const bar = document.querySelector(".progress-bar");
        if (bar) bar.style.width = `${updated.progress_pct}%`;
        const pctEl = document.querySelector(".progress-wrap + .muted");
        if (pctEl) pctEl.textContent = `${updated.progress_pct}% complete`;
      } catch (err) {
        toast(err.message, "error");
        cb.checked = !cb.checked; // revert
      }
    };
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Community page
// ─────────────────────────────────────────────────────────────────────────────
async function communityPage() {
  app.innerHTML = baseLayout(`
    <section class="hero glass glow">
      <h1>Community</h1>
      <p>Share projects, ask questions, and collaborate with other innovators.</p>
    </section>
    <div class="row" style="margin-bottom:14px;">
      <div class="row" style="gap:8px;">
        ${["All","discussion","question","showcase"].map((t,i) =>
          `<button class="tab-btn ${i===0?"active":""}" data-type="${t === "All" ? "" : t}">${t.charAt(0).toUpperCase()+t.slice(1)}</button>`
        ).join("")}
      </div>
      <button class="btn btn-primary" id="newPostBtn">+ New Post</button>
    </div>
    <div id="communityList"><div class="loader-wrap"><div class="loader"></div></div></div>`);
  wireBaseEvents();

  await loadCommunityPosts();

  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.onclick = async () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      await loadCommunityPosts(btn.dataset.type || undefined);
    };
  });

  document.getElementById("newPostBtn")?.addEventListener("click", showNewPostModal);
}

async function loadCommunityPosts(postType) {
  const list = document.getElementById("communityList");
  if (!list) return;
  showLoader(list);
  try {
    const { items } = await api.community.listPosts({ post_type: postType, page_size: 30 });
    list.innerHTML = items.length
      ? `<div class="grid" style="gap:12px;">${items.map(renderPostCard).join("")}</div>`
      : `<p class="muted" style="padding:20px;">No posts yet. Be the first to share!</p>`;

    list.querySelectorAll(".like-post-btn").forEach(btn => {
      btn.onclick = async () => {
        try {
          const res = await api.community.toggleLike("post", Number(btn.dataset.id));
          btn.textContent = res.liked ? `❤️ ${res.like_count}` : `🤍 ${res.like_count}`;
        } catch (err) { toast(err.message, "error"); }
      };
    });
    list.querySelectorAll(".open-post-btn").forEach(btn => {
      btn.onclick = () => { window.location.hash = `#/post/${btn.dataset.id}`; render(); };
    });
  } catch (err) {
    list.innerHTML = `<p class="muted">${escapeHtml(err.message)}</p>`;
  }
}

function renderPostCard(p) {
  return `
    <article class="problem-card glass">
      <div class="row">
        <span class="pill ghost">${escapeHtml(p.post_type)}</span>
        <span class="muted" style="font-size:.8rem;">${timeAgo(p.created_at)}</span>
      </div>
      <strong>${escapeHtml(p.title)}</strong>
      <p class="muted" style="margin:4px 0;font-size:.9rem;">${escapeHtml(p.content.slice(0, 140))}${p.content.length > 140 ? "…" : ""}</p>
      <div class="muted" style="font-size:.82rem;">by ${escapeHtml(p.author?.name || "")}</div>
      <div class="row" style="margin-top:8px;">
        <button class="btn btn-ghost open-post-btn" data-id="${p.id}">Read & Comment</button>
        <button class="btn btn-ghost like-post-btn" data-id="${p.id}">${p.is_liked ? "❤️" : "🤍"} ${p.like_count}</button>
      </div>
    </article>`;
}

function showNewPostModal() {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.innerHTML = `
    <div class="modal-card glass">
      <h3 style="margin:0 0 16px;">Create New Post</h3>
      <form id="newPostForm">
        <div class="field"><label>Title</label><input name="title" placeholder="What would you like to share?" required/></div>
        <div class="field"><label>Type</label>
          <select name="post_type">
            <option value="discussion">Discussion</option>
            <option value="question">Question</option>
            <option value="showcase">Showcase</option>
          </select>
        </div>
        <div class="field"><label>Content</label><textarea name="content" rows="5" placeholder="Share your thoughts, questions, or project…" required></textarea></div>
        <div class="row" style="margin-top:8px;">
          <button class="btn btn-ghost" type="button" id="cancelPostModal">Cancel</button>
          <button class="btn btn-primary" type="submit">Post</button>
        </div>
      </form>
    </div>`;
  document.body.appendChild(modal);
  document.getElementById("cancelPostModal").onclick = () => modal.remove();
  document.getElementById("newPostForm").onsubmit = async e => {
    e.preventDefault();
    const form = new FormData(e.target);
    try {
      await api.community.createPost({
        title: form.get("title"),
        content: form.get("content"),
        post_type: form.get("post_type"),
      });
      toast("Post published!", "success");
      modal.remove();
      await loadCommunityPosts();
    } catch (err) { toast(err.message, "error"); }
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Post Detail page
// ─────────────────────────────────────────────────────────────────────────────
async function postDetailPage(id) {
  app.innerHTML = baseLayout(`<div class="glass panel"><div class="loader-wrap"><div class="loader"></div></div></div>`);
  wireBaseEvents();
  try {
    const post = await api.community.getPost(Number(id));
    const comments = await api.community.getComments(Number(id));
    app.innerHTML = baseLayout(renderPostDetailHTML(post, comments));
    wireBaseEvents();
    wirePostDetailEvents(post);
  } catch (err) {
    app.innerHTML = baseLayout(`<div class="glass panel detail"><h2>Post not found</h2><p class="muted">${escapeHtml(err.message)}</p><a class="btn btn-primary" href="#/community">Back to Community</a></div>`);
    wireBaseEvents();
  }
}

function renderPostDetailHTML(post, comments) {
  return `
    <div class="glass panel" style="margin-bottom:14px;">
      <div class="row">
        <div>
          <div class="muted"><a href="#/community">Community</a> · <span class="pill ghost">${escapeHtml(post.post_type)}</span></div>
          <h2 style="margin:6px 0 0;">${escapeHtml(post.title)}</h2>
        </div>
        <button class="btn btn-ghost like-post-btn" data-id="${post.id}">${post.is_liked ? "❤️" : "🤍"} ${post.like_count}</button>
      </div>
      <div class="muted" style="margin:8px 0;font-size:.85rem;">by ${escapeHtml(post.author?.name || "")} · ${timeAgo(post.created_at)} · ${post.view_count} views</div>
      <div class="divider"></div>
      <p style="line-height:1.7;">${escapeHtml(post.content)}</p>
    </div>

    <div class="glass panel">
      <h3 style="margin:0 0 14px;">Comments (${comments.length})</h3>
      <form id="postCommentForm">
        <textarea name="content" rows="3" placeholder="Add a comment…" required></textarea>
        <button class="btn btn-primary" type="submit">Post Comment</button>
      </form>
      <div class="divider"></div>
      <div class="list" id="postCommentsList">
        ${renderComments(comments)}
      </div>
    </div>`;
}

function wirePostDetailEvents(post) {
  document.querySelector(".like-post-btn")?.addEventListener("click", async btn => {
    const el = btn.currentTarget;
    try {
      const res = await api.community.toggleLike("post", post.id);
      el.textContent = `${res.liked ? "❤️" : "🤍"} ${res.like_count}`;
    } catch (err) { toast(err.message, "error"); }
  });

  document.getElementById("postCommentForm")?.addEventListener("submit", async e => {
    e.preventDefault();
    const content = new FormData(e.target).get("content")?.trim();
    if (!content) return;
    try {
      await api.community.createComment({ post_id: post.id, content });
      toast("Comment posted!", "success");
      e.target.reset();
      const comments = await api.community.getComments(post.id);
      document.getElementById("postCommentsList").innerHTML = renderComments(comments);
    } catch (err) { toast(err.message, "error"); }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Dashboard page (real data from backend)
// ─────────────────────────────────────────────────────────────────────────────
async function dashboardPage() {
  app.innerHTML = baseLayout(`
    <section class="hero glass">
      <h1>Hello, ${escapeHtml(state.user?.name?.split(" ")[0] || "Innovator")} 👋</h1>
      <p>Your personalized innovation dashboard.</p>
    </section>
    <div id="dashContent"><div class="loader-wrap"><div class="loader"></div></div></div>`);
  wireBaseEvents();

  try {
    const [userRes, projectsRes, generatedRes, ideasRes] = await Promise.all([
      api.auth.getMe(),
      api.projects.list({ page_size: 50 }),
      api.ideas.myGenerated({ page_size: 50 }),
      api.ideas.list({ page_size: 50 }),
    ]);

    state.user = userRes;
    const projects = projectsRes.items;
    const generated = generatedRes.items;
    const savedCount = ideasRes.items.filter(i => i.is_saved).length;
    const activeProjects = projects.filter(p => p.status === "active" || p.status === "planning").length;
    const completedProjects = projects.filter(p => p.status === "completed").length;

    // Recommendations
    let recommendations = [];
    try {
      const recRes = await api.ai.getRecommendations(4);
      recommendations = recRes.ideas || [];
    } catch {}

    document.getElementById("dashContent").innerHTML = `
      <section class="stats">
        <article class="stat glass">
          <strong>Points</strong>
          <div class="stat-num">${userRes.points}</div>
        </article>
        <article class="stat glass">
          <strong>Badges</strong>
          <div class="stat-num">${userRes.badges.length ? userRes.badges.join(", ") : "—"}</div>
        </article>
        <article class="stat glass">
          <strong>Ideas Generated</strong>
          <div class="stat-num">${generated.length}</div>
        </article>
        <article class="stat glass">
          <strong>Saved Problems</strong>
          <div class="stat-num">${savedCount}</div>
        </article>
        <article class="stat glass">
          <strong>Active Projects</strong>
          <div class="stat-num">${activeProjects}</div>
        </article>
        <article class="stat glass">
          <strong>Completed</strong>
          <div class="stat-num">${completedProjects}</div>
        </article>
      </section>

      ${projects.length ? `
      <h3 class="section-title">Recent Projects</h3>
      <div class="grid cards">
        ${projects.slice(0, 3).map(p => `
          <article class="problem-card glass">
            <div class="row">
              <strong>${escapeHtml(p.title)}</strong>
              <span class="status-badge status-${p.status}">${escapeHtml(p.status)}</span>
            </div>
            <div class="progress-wrap"><div class="progress-bar" style="width:${p.progress_pct}%;"></div></div>
            <div class="muted" style="font-size:.8rem;">${p.progress_pct}% complete</div>
            <a class="btn btn-ghost" href="#/project/${p.id}" style="margin-top:8px;">Open Project</a>
          </article>`).join("")}
      </div>` : ""}

      ${recommendations.length ? `
      <h3 class="section-title">Recommended For You</h3>
      <div class="grid cards">
        ${recommendations.slice(0,4).map(r => `
          <article class="problem-card glass">
            <strong>${escapeHtml(r.title)}</strong>
            <div class="muted">${escapeHtml(r.short_description || r.short || "")}</div>
            ${r.id ? `<a class="btn btn-ghost" href="#/problem/${r.id}">Explore</a>` : ""}
          </article>`).join("")}
      </div>` : ""}

      <h3 class="section-title">Quick Actions</h3>
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;">
        <a href="#/generator" class="quick-action glass">
          <div class="qa-icon">✨</div>
          <strong>Generate Ideas</strong>
          <div class="muted">AI-powered project ideas</div>
        </a>
        <a href="#/evaluator" class="quick-action glass">
          <div class="qa-icon">🔍</div>
          <strong>Evaluate Idea</strong>
          <div class="muted">Score your concept</div>
        </a>
        <a href="#/workspace" class="quick-action glass">
          <div class="qa-icon">🗂️</div>
          <strong>My Workspace</strong>
          <div class="muted">Projects & saved ideas</div>
        </a>
        <a href="#/community" class="quick-action glass">
          <div class="qa-icon">💬</div>
          <strong>Community</strong>
          <div class="muted">Share & collaborate</div>
        </a>
      </div>`;
  } catch (err) {
    document.getElementById("dashContent").innerHTML = `<p class="muted">${escapeHtml(err.message)}</p>`;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Chat widget (preserved + wired to backend)
// ─────────────────────────────────────────────────────────────────────────────
function chatUI() {
  return `
    <aside class="chatbox glass" id="chatbox">
      <div class="row">
        <strong>AI Mentor</strong>
        <button class="btn btn-ghost" id="chatToggle">−</button>
      </div>
      <div class="chat-messages" id="chatMessages">
        <div class="chat-msg bot">
          <div class="chat-msg-label">Mentor AI</div>
          Ask about tech stack, implementation steps, algorithms, challenges, or how to improve your project.
        </div>
      </div>
      <form id="chatForm" class="row">
        <input name="msg" placeholder="Ask anything about your project…" required/>
        <button class="btn btn-primary">Send</button>
      </form>
    </aside>`;
}

function wireChatEvents() {
  const toggle = document.getElementById("chatToggle");
  const msgs = document.getElementById("chatMessages");
  const form = document.getElementById("chatForm");
  if (!toggle || !msgs || !form) return;

  toggle.onclick = () => {
    const hidden = msgs.style.display === "none";
    msgs.style.display = hidden ? "grid" : "none";
    form.style.display = hidden ? "flex" : "none";
    toggle.textContent = hidden ? "−" : "+";
  };

  form.onsubmit = async e => {
    e.preventDefault();
    const msg = String(new FormData(form).get("msg") || "").trim();
    if (!msg) return;
    appendChatMsg("user", msg);
    form.reset();
    const typing = showTypingIndicator();

    // Determine context from current route
    const hash = location.hash;
    let projectId, ideaId;
    if (hash.startsWith("#/project/")) projectId = Number(hash.split("/")[2]);
    if (hash.startsWith("#/idea/")) ideaId = Number(hash.split("/")[2]);

    try {
      const res = await api.ai.chat(msg, { project_id: projectId, idea_id: ideaId });
      typing?.remove();
      appendChatMsg("bot", res.reply);
    } catch (err) {
      typing?.remove();
      appendChatMsg("bot", `⚠️ ${err.message}`);
    }
  };
}

function appendChatMsg(role, text) {
  const msgs = document.getElementById("chatMessages");
  if (!msgs) return;
  const div = document.createElement("div");
  div.className = `chat-msg ${role}`;
  const label = role === "bot" ? "Mentor AI" : (state.user?.name || "You");
  div.innerHTML = `<div class="chat-msg-label">${escapeHtml(label)}</div>${escapeHtml(text).replace(/\n/g, "<br>")}`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function showTypingIndicator() {
  const msgs = document.getElementById("chatMessages");
  if (!msgs) return null;
  const el = document.createElement("div");
  el.className = "chat-msg bot typing-msg";
  el.innerHTML = `<div class="chat-msg-label">Mentor AI</div><span class="typing-dots"><span></span><span></span><span></span></span>`;
  msgs.appendChild(el);
  msgs.scrollTop = msgs.scrollHeight;
  return el;
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared event wiring (topbar — preserved)
// ─────────────────────────────────────────────────────────────────────────────
function wireBaseEvents() {
  document.getElementById("themeBtn")?.addEventListener("click", () => {
    state.theme = state.theme === "dark" ? "light" : "dark";
    saveTheme();
    setTheme();
    document.getElementById("themeBtn").textContent = `${state.theme === "dark" ? "Light" : "Dark"} Mode`;
  });

  document.getElementById("logoutBtn")?.addEventListener("click", () => {
    api.auth.logout();
    state.user = null;
    showAuth("login");
  });

  wireChatEvents();
}

// ─────────────────────────────────────────────────────────────────────────────
// Router
// ─────────────────────────────────────────────────────────────────────────────
async function render() {
  setTheme();

  // Check auth
  if (!api.auth.isLoggedIn()) {
    return showAuth("login");
  }

  // Load user if not already loaded
  if (!state.user) {
    try {
      state.user = await api.auth.getMe();
    } catch {
      api.auth.logout();
      return showAuth("login");
    }
  }

  const hash = location.hash || "#/explorer";
  const [route, search] = hash.split("?");
  const params = search ? new URLSearchParams(search) : null;

  if (route.startsWith("#/problem/")) {
    await detailPage(route.split("/")[2]);
  } else if (route.startsWith("#/idea/")) {
    await ideaDetailPage(route.split("/")[2]);
  } else if (route.startsWith("#/project/")) {
    await projectDetailPage(route.split("/")[2]);
  } else if (route.startsWith("#/post/")) {
    await postDetailPage(route.split("/")[2]);
  } else if (route === "#/generator") {
    app.innerHTML = baseLayout(generatorPage());
    wireBaseEvents();
    await wireGeneratorEvents();
  } else if (route === "#/evaluator") {
    app.innerHTML = baseLayout(evaluatorPage(params));
    wireBaseEvents();
    await wireEvaluatorEvents(params);
  } else if (route === "#/workspace") {
    await workspacePage();
  } else if (route === "#/community") {
    await communityPage();
  } else if (route === "#/dashboard") {
    await dashboardPage();
  } else {
    // Explorer (default)
    app.innerHTML = baseLayout(explorerPage());
    wireBaseEvents();
    wireExplorerFilters();
    await loadExplorerIdeas();
  }
}

function wireExplorerFilters() {
  const search = document.getElementById("searchInput");
  if (!search) return;

  const applySearch = debounce(async () => {
    state.filter.q = search.value;
    await loadExplorerIdeas();
  }, 350);
  search.oninput = applySearch;

  document.getElementById("domainSelect")?.addEventListener("change", async e => {
    state.filter.domain = e.target.value;
    await loadExplorerIdeas();
  });
  document.getElementById("difficultySelect")?.addEventListener("change", async e => {
    state.filter.difficulty = e.target.value;
    await loadExplorerIdeas();
  });
  document.getElementById("sortSelect")?.addEventListener("change", async e => {
    state.filter.sort = e.target.value;
    await loadExplorerIdeas();
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────────────────────
function timeAgo(isoString) {
  if (!isoString) return "";
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Auth expiry handling
// ─────────────────────────────────────────────────────────────────────────────
window.addEventListener("ideaforge:auth-expired", () => {
  state.user = null;
  showAuth("login");
});

// ─────────────────────────────────────────────────────────────────────────────
// Bootstrap
// ─────────────────────────────────────────────────────────────────────────────
window.addEventListener("hashchange", render);
render();
