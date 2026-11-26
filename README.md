# IdeaForge AI

> From Ideas to Innovation.

An AI-powered innovation platform for engineering students, hackathon participants, developers, and startup enthusiasts. Helps users discover real-world problems, generate project ideas, evaluate feasibility, build roadmaps, and collaborate with other innovators.

---

## Project Structure

```
FSD2 PROJECT/
├── IdeaForge AI.html          # Existing frontend (preserved)
├── IdeaForge AI_files/
│   ├── app.js                 # Existing frontend logic (preserved)
│   ├── styles.css             # Existing styles (preserved)
│   ├── css2                   # Google Fonts
│   └── api.js                 # NEW: Backend API client
├── backend/                   # NEW: FastAPI backend
│   ├── app/
│   │   ├── main.py            # FastAPI app entry point
│   │   ├── core/
│   │   │   ├── config.py      # Settings from .env
│   │   │   ├── database.py    # SQLAlchemy engine + session
│   │   │   ├── security.py    # JWT + bcrypt
│   │   │   └── dependencies.py# Auth + pagination dependencies
│   │   ├── models/            # SQLAlchemy ORM models
│   │   │   ├── user.py        # User, UserProfile
│   │   │   ├── idea.py        # Category, Idea, SavedIdea, GeneratedIdea, IdeaEvaluation
│   │   │   ├── project.py     # Project, Roadmap, Task
│   │   │   ├── community.py   # Post, Comment, Like, Notification
│   │   │   └── chat.py        # ChatMessage
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   │   ├── auth.py
│   │   │   ├── idea.py
│   │   │   ├── project.py
│   │   │   ├── community.py
│   │   │   └── ai.py
│   │   ├── api/routes/        # FastAPI route handlers
│   │   │   ├── auth.py        # POST /auth/register, /auth/login, GET /auth/me
│   │   │   ├── ideas.py       # GET/POST /ideas, /ideas/generate, /ideas/evaluate
│   │   │   ├── projects.py    # CRUD /projects, roadmaps, tasks
│   │   │   ├── community.py   # Posts, comments, likes, notifications
│   │   │   └── ai.py          # /ai/chat, /ai/tech-stack, /ai/recommendations
│   │   └── services/
│   │       └── ai_service.py  # All LLM API calls (OpenAI-compatible)
│   ├── alembic/               # Database migrations
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   ├── alembic.ini
│   ├── seed_data.py           # Seeds 15+ curated problem statements
│   ├── requirements.txt
│   ├── .env.example           # Copy to .env and fill in values
│   └── .gitignore
└── README.md
```

---

## Phase 1 — What Was Implemented

✅ **Backend Foundation**
- FastAPI application with CORS, rate limiting, and request timing middleware
- Modular router structure for auth, ideas, projects, community, AI

✅ **Database Architecture**
- 14 normalized PostgreSQL tables with proper relationships, indexes, and foreign keys
- Alembic migrations with upgrade/downgrade support
- Database seeder for all 26 existing problem statements

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
- Automatic token injection from localStorage
- Session expiry handling

---

## Setup Instructions

### Prerequisites
- Python 3.11+ (recommended 3.11 or 3.12; Python 3.14 may have missing binary wheels for psycopg2)
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

### 7. Open the frontend

Open `IdeaForge AI.html` in a browser (or serve via Live Server on port 5500).

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
| `ALLOWED_ORIGINS` | Yes | Comma-separated CORS origins |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | JWT expiry (default: 60) |

---

## Development Phases

| Phase | Status | Description |
|---|---|---|
| Phase 1 | ✅ Complete | Backend foundation, DB, authentication |
| Phase 2 | ⏳ Next | Idea management, frontend-backend integration |
| Phase 3 | ⏳ Pending | AI Idea Generator + Evaluator |
| Phase 4 | ⏳ Pending | Tech Stack Recommender + Roadmap Generator |
| Phase 5 | ⏳ Pending | Hackathon Mode + AI Mentor |
| Phase 6 | ⏳ Pending | Community, recommendations, dashboard |
| Phase 7 | ⏳ Pending | Testing, security hardening, deployment |

---

## Security Notes

- Passwords are hashed with bcrypt (12 rounds) — plaintext passwords are never stored
- JWT tokens expire after 60 minutes by default
- API keys are stored server-side only — the frontend never sees them
- SQL injection is prevented by SQLAlchemy's parameterized queries
- CORS is restricted to configured origins only
- Rate limiting is applied to all endpoints

---

## Deployment (Render)

1. Push the `backend/` folder to a GitHub repo
2. Create a new **Web Service** on Render, connect the repo
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add all environment variables in the Render dashboard
6. Create a **PostgreSQL** database on Render, copy the internal URL to `DATABASE_URL`
7. Run migrations: `alembic upgrade head` (via Render Shell or as a pre-deploy command)
