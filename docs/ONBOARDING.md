# Onboarding Guide: Alsini Physics Platform (EDU-VLE)

## Project Overview

| Field | Value |
|---|---|
| **Name** | `alsini-physics-platform` |
| **Description** | Physics education platform with React frontend (Vite + TailwindCSS), dual backend (Express.js + FastAPI), Supabase auth/storage, and Google Generative AI for interactive tutoring and quiz grading. |
| **Languages** | CSS, HTML, JavaScript, JSON, Markdown, Python, Shell, SQL, YAML |
| **Frameworks** | Express, FastAPI, Framer Motion, Google Generative AI, Playwright, Pydantic, React, Supabase, TailwindCSS, Uvicorn, Vite |
| **Files Analyzed** | 291 |
| **Repository Commit** | `0b1b65096aefb7fd831023f3fe3cc812f769063a` |

---

## Architecture Layers (8 layers)

### 1. Frontend UI Layer
React SPA components, page layouts, stylesheets, and the application shell (App.jsx, main.jsx) forming the VLE's client-side interface with Supabase auth and AI tutor integration.

**Key files:** `Auth.jsx`, `InteractiveTutor.jsx`, `HybridDocumentViewer.jsx`, `QuizEngine.jsx`, `Sidebar.jsx`, `VLEDashboard.jsx`, `Hero.jsx`, `Features.jsx`, `App.jsx`, `main.jsx`, `supabaseClient.js`

### 2. Backend Services Layer
Express.js chat server with Gemini AI integration and FastAPI Python services for AI tutoring, quiz grading, and physics content processing.

**Key files:** `backend/server.js`, `backend/main.py`, `backend/requirements.txt`

### 3. Data Layer
PostgreSQL database schemas, SQL migration scripts, Edexcel IGCSE physics curriculum seed data, quiz attempts table.

**Key files:** `scratch/mig_1_tables.sql` → `mig_4_activities_resources.sql`, `Alsini_Physics_Schema_V1_Seed.sql`, `database/quiz_attempts_migration.sql`

### 4. Scripts & Tooling Layer
Data ingestion pipeline scripts, Supabase MCP server, Scheme of Work parsers, and RLS test utilities.

**Key files:** `scripts/ingest_pipeline.js`, `scripts/supabase_mcp.py`, `scratch/parse_sow.js`, `scratch/parse_sow.py`, `scratch/test_rls.js`

### 5. Project Configuration Layer
Root and sub-project build manifests, bundler settings (Vite, PostCSS, Tailwind, ESLint), Git ignore rules, VS Code settings.

**Key files:** Root `package.json`, `frontend/package.json`, `frontend/vite.config.js`, `frontend/tailwind.config.js`, `frontend/eslint.config.js`

### 6. Testing Layer
Playwright end-to-end test specifications for the VLE Dashboard.

**Key files:** `frontend/tests/worksheet-tab.spec.js`

### 7. Documentation Layer
Project-level documentation including gemini.md summary, MCP Supabase configuration guide, and engineering role definitions.

**Key files:** `gemini.md`, `mcp_configuration_for_supabase.md`

### 8. Agency AI Agents Layer (external repo)
200+ specialized AI agent personality documents spanning 12 divisions (engineering, design, marketing, sales, game development, spatial computing, etc.) with multi-tool integration scripts.

**Key files:** `agency-agents-main/README.md`

---

## Key Concepts

### Dual-Backend Architecture
The platform uses **two backend servers** running simultaneously:
- **Express.js** (port 5000) — handles `/api/chat` for Gemini AI chat, simple conversational flow
- **FastAPI** (port 8000) — handles `/api/tutor` (semantic router), `/api/grade` (AI grading), `/api/question` — more powerful, async

### Semantic Router (FastAPI)
The `/api/tutor` endpoint evaluates query complexity:
- **Simple/conversational** — routes to Gemini 2.5 Flash (cost-efficient)
- **Complex/reasoning/grading** — routes to NVIDIA Llama 3.3 70B Instruct (higher capability)
- Trigger keywords: "grade", "assess", "calculate", "derive", "prove", "solve"

### Socratic AI Tutor Persona
Both backends define a **Socratic Physics Tutor** persona that:
- Never gives direct answers — guides students through questions
- Targets Edexcel IGCSE and A-Level Physics curriculum
- Returns responses as Markdown with KaTeX math rendering

### Agentic UI Navigation
The AI can control the frontend UI by emitting `[SWITCH_TAB: Quiz]` or `[SWITCH_TAB: Worksheet]` tags in its responses. The `InteractiveTutor.jsx` component parses these tags and switches tabs automatically — giving the AI agentic control over the student's learning flow.

### AI Grading Engine (3-Mark Protocol)
The `/api/grade` endpoint uses Llama 3.3 with a strict examiner persona:
1. Internally solves the question from scratch
2. Applies standard 3-mark scheme: Formula → Substitution → Accuracy
3. Produces JSON: `{marks_awarded, total_marks, explanation}`
4. Zero leniency — no rounding-error excuses, no follow-through credit

### OpenKB Knowledge Graph
Content resources can be rendered in two modes:
- **Document View** — flat Markdown rendering
- **Interactive Tutor View** — recursive expandable tree of JSON knowledge graph nodes (via `HybridDocumentViewer.jsx`)

### Supabase + RLS
Supabase PostgreSQL with Row-Level Security:
- All authenticated users can SELECT curriculum tables
- Per-user access on `quiz_attempts` via `auth.uid() = user_id`
- MCP (Model Context Protocol) server at `scripts/supabase_mcp.py` for AI-assisted DB management

---

## Guided Tour (11 Steps)

| Step | Title | Key Files |
|---|---|---|
| 1 | **Project Overview** | `gemini.md` |
| 2 | **Backend Server & AI Chat** | `backend/server.js`, `backend/package.json` |
| 3 | **Python Backend Requirements** | `backend/requirements.txt` |
| 4 | **Frontend Entry Point & App Shell** | `frontend/src/main.jsx`, `frontend/src/App.jsx` |
| 5 | **Supabase Client & Authentication** | `frontend/src/lib/supabaseClient.js`, `frontend/src/components/Auth.jsx` |
| 6 | **VLE Dashboard & Syllabus Navigation** | `frontend/src/components/VLEDashboard.jsx`, `frontend/src/components/Sidebar.jsx` |
| 7 | **AI Interactive Tutor** | `frontend/src/components/InteractiveTutor.jsx`, `frontend/src/components/HybridDocumentViewer.jsx` |
| 8 | **Quiz Engine & Assessment** | `frontend/src/components/QuizEngine.jsx`, `database/quiz_attempts_migration.sql` |
| 9 | **Database Schema & Curriculum Seed** | `Alsini_Physics_Schema_V1_Seed.sql`, `scratch/mig_1_tables.sql` |
| 10 | **Data Ingestion Pipeline** | `scripts/ingest_pipeline.js`, `scripts/supabase_mcp.py` |
| 11 | **Agency AI Agents Collection** | `agency-agents-main/README.md` |

---

## File Map (by Layer)

### Frontend UI Layer
| File | Purpose | Complexity |
|---|---|---|
| `App.jsx` | Root component with router, session listener, protected routes | moderate |
| `main.jsx` | React DOM bootstrap + KaTeX CSS import | simple |
| `supabaseClient.js` | Singleton Supabase client (fan-in: 8 — most-depended-upon file) | simple |
| `Auth.jsx` | Login/signup/password-reset with GSAP glassmorphic animations | moderate |
| `VLEDashboard.jsx` | Authenticated dashboard shell with sidebar + routes | moderate |
| `Sidebar.jsx` | Curriculum hierarchy fetcher (units → chapters) from Supabase | moderate |
| `InteractiveTutor.jsx` | **Flagship: AI chat + tabbed resource views + SWITCH_TAB parsing** | **complex** |
| `HybridDocumentViewer.jsx` | Dual-mode viewer: Markdown or interactive OpenKB tree | moderate |
| `QuizEngine.jsx` | Quiz UI: fetch question → user answers → AI grading → save attempt | moderate |
| `Hero.jsx` | Landing page hero with GSAP animations | simple |
| `Features.jsx` | Animated card shuffler + value props | moderate |

### Backend Services Layer
| File | Purpose | Complexity |
|---|---|---|
| `backend/server.js` | Express server with Gemini chat endpoint, Socratic persona | moderate |
| `backend/main.py` | **FastAPI server with semantic router + AI grading + question endpoint** | **complex** |

### Data Layer
| File | Purpose | Complexity |
|---|---|---|
| `Alsini_Physics_Schema_V1_Seed.sql` | Original 4-tier course→chapter→topic→subtopic schema + seed data | simple |
| `scratch/mig_1_tables.sql` → `mig_4_*.sql` | Incremental migrations to unified schema | moderate |
| `database/quiz_attempts_migration.sql` | Quiz attempts table with RLS policies | simple |

### Scripts & Tooling Layer
| File | Purpose | Complexity |
|---|---|---|
| `scripts/ingest_pipeline.js` | **MinerU PDF → Supabase ingestion pipeline** | **complex** |
| `scripts/supabase_mcp.py` | Custom MCP server for AI-assisted DB queries | moderate |

---

## Complexity Hotspots

These are the areas new developers should approach with care:

| File | Why It's Complex |
|---|---|
| `frontend/src/components/InteractiveTutor.jsx` | 366-line flagship component. Manages split-screen chat + 4-tab resource views + AI SWITCH_TAB parsing + FastAPI integration + floating action button. Heavy state management with `useReducer`. |
| `backend/main.py` | FastAPI orchestrator with semantic router (Gemini vs. Llama), 3 endpoints, strict AI grading protocol, Supabase context injection. Two different AI SDKs in one file. |
| `scripts/ingest_pipeline.js` | Full data pipeline: walks directories, calls MinerU/OpenKB API, maps extracted JSON to Supabase tables with fuzzy name matching. |
| `scripts/supabase_mcp.py` | Custom MCP server implementing the Model Context Protocol — non-trivial async tool registration. |

> Note: 76 of the 80 "complex" file-level nodes are from the `agency-agents-main/` third-party repo. These are agent prompt documents, not runtime code. The 4 project-specific complex files listed above are the ones to focus on.

---

## Quick Start

```bash
# Frontend
cd frontend && npm install && npm run dev         # → localhost:5173

# Backend (Express)
cd backend && npm install && node server.js        # → localhost:5000

# Backend (FastAPI)
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000              # → localhost:8000

# Tests
cd frontend && npx playwright test
```

### Required Environment Variables

**`backend/.env`**
```
GEMINI_API_KEY=<your-key>
NVIDIA_API_KEY=<your-key>
SUPABASE_URL=<your-url>
SUPABASE_SERVICE_ROLE_KEY=<your-key>
```

**`frontend/.env.local`**
```
VITE_SUPABASE_URL=<your-url>
VITE_SUPABASE_ANON_KEY=<your-anon-key>
VITE_API_URL=http://localhost:5000
```
