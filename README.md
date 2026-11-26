# IdeaForge AI

> From Ideas to Innovation.

An AI-powered innovation platform for engineering students, hackathon participants, developers, and startup enthusiasts. Helps users discover real-world problems, generate project ideas, evaluate feasibility, build roadmaps, and collaborate with other innovators.

---

## Project Structure

```
FSD2 PROJECT/
├── .python-version
├── IdeaForge AI.html
├── IdeaForge AI_files/
│   ├── app.js
│   ├── styles.css
│   ├── css2
│   ├── api.js
│   └── security.js
├── functions/
│   ├── api/
│   │   └── [[path]].js
│   └── health.js
├── _headers
├── frontend-tests/
│   ├── api.test.mjs
│   ├── security.test.mjs
│   ├── cloudflare.test.mjs
│   └── csp.test.mjs
├── package.json
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   └── dependencies.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── idea.py
│   │   │   ├── project.py
│   │   │   ├── community.py
│   │   │   └── chat.py
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── idea.py
│   │   │   ├── project.py
│   │   │   ├── community.py
│   │   │   └── ai.py
│   │   ├── api/routes/
│   │   │   ├── auth.py
│   │   │   ├── ideas.py
│   │   │   ├── projects.py
│   │   │   ├── community.py
│   │   │   └── ai.py
│   │   └── services/
│   │       └── ai_service.py
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       └── 002_create_post_reports.py
│   ├── alembic.ini
│   ├── seed_data.py
│   ├── requirements.txt
│   ├── .env.example
│   └── .gitignore
└── README.md
```

---

## Phase 1 — What Was Implemented

✅ **Backend Foundation**
- FastAPI application with CORS, rate limiting, and request timing middleware
- Modular router structure for auth, ideas, projects, community, AI

✅ **Database Architecture**
- 16 normalized PostgreSQL tables with proper relationships, indexes, and foreign keys
- Alembic migrations with upgrade/downgrade support
- Database seeder for all 15 existing problem statements

✅ **Authentication**
- JWT-based auth (access tokens, configurable expiry)
- bcrypt password hashing (12 rounds)
- Register, login, get profile, update profile endpoints
- Auth middleware with clean error responses

✅ **AI Integration**
- OpenAI-compatible LLM client (swappable provider via AI_BASE_URL)
- AI Idea Generator with structured JSON responses
- AI Idea Evaluator with 6-dimension scoring
- AI Tech Stack Recommender
- AI Roadmap Generator
- AI Mentor Chat with conversation history
- AI Recommendations based on user interests
- API key stored server-side only — never exposed to frontend

✅ **All Core API Endpoints**
- `/api/auth/*` — registration, login, profile
- `/api/ideas/*` — list, get, save, generate, evaluate
- `/api/projects/*` — full CRUD, roadmap generation, task management
- `/api/community/*` — posts, comments, likes, notifications
- `/api/ai/*` — chat, tech stack, recommendations

✅ **Frontend API Client** (`api.js`)
- Thin fetch wrapper for all backend endpoints
- Tokens are stored in `sessionStorage` with an in-memory fallback; no JWT is written to `localStorage`
- Legacy `if_access_token` values in `localStorage` are removed during API initialization and are not migrated
- Automatic bearer-token injection for authenticated requests
- Session expiry handling

---

## Setup Instructions

### Prerequisites
- Python 3.12 recommended for Render and local development; Python 3.11 is also supported
- Python 3.14 may have missing binary wheels for `psycopg2-binary`
- Render uses the repository-root `.python-version` file containing `3.12` unless overridden by `PYTHON_VERSION`
- PostgreSQL 15+
- An OpenAI API key (or compatible provider)

> **Python 3.14 note**: If `psycopg2-binary` fails to install, use `pip install psycopg[binary]` instead and update `DATABASE_URL` to use the `postgresql+psycopg` dialect.

### 1. Set up PostgreSQL

```sql
CREATE DATABASE ideaforge;
```

### 2. Configure environment

```bash
cd backend
copy .env.example .env
# Edit .env with your database URL and API key
```

### 3. Install Python dependencies

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 4. Run database migrations

```bash
cd backend
alembic upgrade head
```

### 5. Seed initial data

```bash
cd backend
python seed_data.py
```

### 6. Start the backend server

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now running at `http://localhost:8000`  
Interactive docs: `http://localhost:8000/docs`

### 7. Open the frontend locally

Open `IdeaForge AI.html` in a browser (or serve via Live Server on port 5500). `api.js` uses `http://127.0.0.1:8000/api` automatically for `localhost`, `127.0.0.1`, `0.0.0.0`, and `file:` origins.

### 8. Run frontend regression tests

```bash
npm run test:frontend
```

---

## API Documentation

After starting the backend, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Health check**: `http://localhost:8000/health`

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | JWT signing secret (min 32 chars) |
| `OPENAI_API_KEY` | Yes | LLM API key |
| `AI_MODEL` | No | Model name (default: gpt-4o-mini) |
| `AI_BASE_URL` | No | Override for other providers |
| `ALLOWED_ORIGINS` | Yes | Comma-separated HTTPS CORS origins for Render |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | JWT expiry (default: 60) |
| `APP_ENV` | Yes | `development` or `production` |
| `APP_VERSION` | No | Reported API version |
| `RATE_LIMIT_PER_MINUTE` | No | General request limit |
| `AI_RATE_LIMIT_PER_MINUTE` | No | AI request limit |

Cloudflare Pages uses `BACKEND_ORIGIN` as a Pages environment variable. Set it to the Render service URL without a trailing slash. Never place backend secrets in frontend code or Pages build variables.

---

## Development Phases

| Phase | Status | Description |
|---|---|---|
| Phase 1 | ✅ Complete | Backend foundation, DB, authentication |
| Phase 2 | ✅ Complete | Idea management, frontend-backend integration |
| Phase 3 | ✅ Complete | AI Idea Generator + Evaluator |
| Phase 4 | ✅ Complete | Tech Stack Recommender + Roadmap Generator |
| Phase 5 | ✅ Complete | Hackathon Mode + AI Mentor |
| Phase 6 | ✅ Complete | Community, recommendations, dashboard |
| Phase 7 | ✅ Complete | Testing, security hardening, deployment |

---

## Security Notes

- Passwords are hashed with bcrypt (12 rounds) — plaintext passwords are never stored
- JWT tokens expire after 60 minutes by default
- API keys are stored server-side only — the frontend never sees them
- SQL injection is prevented by SQLAlchemy's parameterized queries
- CORS is restricted to configured origins only
- JWT access tokens are kept in `sessionStorage` with an in-memory fallback, not `localStorage`
- Legacy `if_access_token` values in `localStorage` are removed on startup and never migrated into `sessionStorage`
- Rate limiting middleware is configured; endpoint coverage is being hardened

---

## Deployment

### Render backend

1. Push this repository to GitHub
2. Create a new **Web Service** on Render, connect the repo, and set **Root Directory** to `backend`
3. Use the Python 3 runtime and keep the repository-root `.python-version` file containing `3.12`; alternatively set `PYTHON_VERSION=3.12` in the Render dashboard
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Add all environment variables in the Render dashboard
7. For Render Postgres, copy the internal connection URL to `DATABASE_URL`; for Neon, use the pooled connection URL with SSL parameters
8. Run migrations: `alembic upgrade head` (via Render Shell or as a pre-deploy command)
9. Seed initial data once: `python seed_data.py`
10. Set `APP_ENV=production` and `ALLOWED_ORIGINS` to the exact HTTPS Cloudflare Pages origin(s)

### Cloudflare Pages frontend

1. Deploy the repository root as a Cloudflare Pages site
2. Use the repository root as the output directory and leave the build command unset
3. Add a Pages environment variable named `BACKEND_ORIGIN` containing the bare Render service URL (`https://service.onrender.com`), without a path, query string, or credentials
4. Pages Functions proxy `/api/*` and `/health` to Render, so changing the Render URL requires no frontend source edit
5. The API proxy validates path segments, rejects plain and encoded traversal, and always targets `${BACKEND_ORIGIN}/api/...`; it never accepts a destination URL from the request
6. The API proxy forwards only an allowlist of request and response headers; cookies, connection headers, redirect locations, CORS headers, and backend server headers are not forwarded
7. `OPTIONS` is answered locally with `204` and an explicit `Allow` header; the browser application uses same-origin requests and does not require a preflight
8. Upstream network failures and 5xx responses return controlled JSON; 4xx responses preserve the backend `detail` contract
9. `/health` returns a controlled `{ "status": "ok" }` or `{ "status": "unavailable" }` response and has no authentication side effects
10. `_headers` applies a strict CSP and security headers to every Pages response; application styling uses classes and CSS custom-property classes, so no inline-style exception is needed
11. Use an HTTPS custom domain; include that domain in `ALLOWED_ORIGINS` only when calling Render directly from the browser
