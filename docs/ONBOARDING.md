# Alsini Physics Platform — Developer Onboarding Guide

> Generated from the project knowledge graph (commit `0b1b650`, analyzed 2026-05-27).

## 1. Project Overview

**Alsini Physics Platform** is a physics education Virtual Learning Environment (VLE) for the Edexcel IGCSE/A-Level curriculum.

- **Languages:** JavaScript, Python, SQL, HTML, CSS, YAML, JSON, Shell, Markdown
- **Frameworks:** React (Vite + TailwindCSS), Express.js, FastAPI, Supabase, Google Generative AI, Framer Motion, Pydantic, Uvicorn, Playwright
- **Architecture:** A React SPA frontend talks to a **dual backend** — Express.js handles real-time Gemini chat, while FastAPI powers the AI tutor conversation engine and quiz grading (Examiner API). Supabase provides auth + PostgreSQL storage. Content is seeded from Pearson's Edexcel specification via PDF/OCR pipelines.

> **Start here:** `gemini.md` — a 13-phase project summary and the roadmap for everything below.

## 2. Architecture Layers

| Layer | Purpose |
|-------|---------|
| **Frontend UI** | React SPA: components, landing pages, Supabase auth, AI tutor UI |
| **Backend Services** | Express.js chat server + FastAPI Python tutor/grading services |
| **Data** | PostgreSQL schemas, migrations, Edexcel curriculum seed data (Supabase) |
| **Scripts & Tooling** | Data ingestion pipeline, Supabase MCP server, SoW parsers, RLS tests |
| **Configuration** | package.json manifests, Vite/Tailwind/ESLint/PostCSS, VS Code settings |
| **Testing** | Playwright E2E specs for VLE Dashboard worksheet tab |
| **Documentation** | gemini.md, MCP config guide, frontend README, engineering role docs |
| **Agency AI Agents** | Third-party collection of 200+ AI agent personalities (separate subtree) |

## 3. Key Concepts

- **Dual backend split:** Express.js (live Gemini chat) vs FastAPI (tutor engine + quiz grading via Examiner API).
- **Supabase as the spine:** Auth, PostgreSQL, and Row-Level Security (RLS) — the `supabaseClient.js` singleton (fan-in: 8) is imported by nearly every component.
- **Protected routing:** `App.jsx` centralizes auth state and guards VLE routes.
- **RLS-first data access:** Curriculum and `quiz_attempts` tables filter rows per `auth.uid()` at the DB level — never bypass on the client.
- **Curriculum hierarchy:** `units → chapters → specification_points → activities/resources → questions` mirrors the IGCSE syllabus; UUID PKs (not auto-increment) for enumeration safety.
- **MCP-driven DB ops:** `supabase_mcp.py` exposes Supabase as tools for agentic management.
- **Content lifecycle:** Pearson PDF → MinerU OCR (`MinerU_SOW__*.json`) → `parse_sow`/ingest scripts → Supabase tables.

## 4. Guided Tour (11 steps)

1. **Project Overview** — read `gemini.md` for the full architecture and 13-phase roadmap.
2. **Backend Server & AI Chat** — `backend/server.js` (Gemini chat + health route) and `backend/package.json`.
3. **Python Backend** — `backend/requirements.txt` (FastAPI, Uvicorn, OpenAI/Gemini SDKs, PDF libs).
4. **App Shell** — `frontend/src/main.jsx` (mount + KaTeX CSS) and `frontend/src/App.jsx` (auth session + routing).
5. **Supabase & Auth** — `frontend/src/lib/supabaseClient.js` (singleton client) and `frontend/src/components/Auth.jsx`.
6. **VLE Dashboard** — `frontend/src/components/VLEDashboard.jsx` + `Sidebar.jsx` (syllabus nav from Supabase).
7. **AI Tutor** — `frontend/src/components/InteractiveTutor.jsx` + `HybridDocumentViewer.jsx`.
8. **Quiz Engine** — `frontend/src/components/QuizEngine.jsx` + `quiz_attempts` table (RLS).
9. **Schema & Seed** — `Alsini_Physics_Schema_V1_Seed.sql` + `mig_1_tables.sql` (`units`).
10. **Ingestion Pipeline** — `scripts/ingest_pipeline.js` + `scripts/supabase_mcp.py`.
11. **Agency Agents** — `agency-agents-main/README.md` + `lint-agents.yml` workflow.

## 5. File Map

### Frontend (`frontend/`)
| File | Role | Complexity |
|------|------|-----------|
| `src/main.jsx` | App entry, mounts root, loads global/KaTeX CSS | simple |
| `src/App.jsx` | Root component: auth session state + protected/public routing | moderate |
| `src/lib/supabaseClient.js` | Singleton Supabase client from Vite env vars (fan-in: 8) | simple |
| `src/components/Auth.jsx` | Login/register/password-reset, GSAP glassmorphic UI | moderate |
| `src/components/UpdatePassword.jsx` | Secure password update page | moderate |
| `src/components/VLEDashboard.jsx` | Authenticated main shell (sidebar + routes) | simple |
| `src/components/Sidebar.jsx` | Syllabus hierarchy nav, Triple Science toggle, logout | moderate |
| `src/components/InteractiveTutor.jsx` | **Flagship** split-screen AI tutor + tabbed resources | **complex** |
| `src/components/HybridDocumentViewer.jsx` | Markdown / interactive JSON knowledge-graph viewer | moderate |
| `src/components/QuizEngine.jsx` | Quiz taking, AI grading, attempt recording | moderate |
| `src/components/NoiseOverlay.jsx` | SVG fractal noise background | simple |
| `src/components/{Hero,Features,Philosophy,Protocol,Navbar,Footer,CTA,Button}.jsx` | Landing page sections & UI primitives | simple–moderate |
| `src/{App.css,index.css}`, `index.html`, `public/*.svg`, `src/assets/*.svg` | Styles, HTML shell, SVG assets | — |
| `tests/worksheet-tab.spec.js` | Playwright E2E for Worksheet tab | simple |

### Backend (`backend/`)
| File | Role | Complexity |
|------|------|-----------|
| `server.js` | Express.js Gemini chat endpoint + health check | moderate |
| `requirements.txt` | FastAPI/Uvicorn/OpenAI/Gemini/PDF deps | simple |
| `package.json` | Express, Google GenAI SDK, CORS, dotenv | simple |

### Data (`scratch/`, `database/`)
| File | Role | Complexity |
|------|------|-----------|
| `mig_1_tables.sql` | Core 6-table schema (units, chapters, spec_points, activities, resources, questions) | simple |
| `mig_2_units_chapters.sql` | Seeds 9 units + 28 chapters | simple |
| `mig_3_specs.sql` | Seeds 190+ Edexcel specification points | moderate |
| `mig_4_activities_resources.sql` | Seeds activities + TRP resources per spec point | moderate |
| `save_my_exams_schema.sql` | Self-contained Save My Exams curriculum schema + data | **complex** |
| `Alsini_Physics_Schema_V1_Seed.sql` | Forces & Motion unit seed (courses/chapters/topics) | simple |
| `database/quiz_attempts_migration.sql` | `quiz_attempts` table + RLS policies | simple |

### Scripts (`scripts/`, `scratch/`)
| File | Role | Complexity |
|------|------|-----------|
| `scripts/ingest_pipeline.js` | Sends PDFs to MinerU, maps parsed content → Supabase | **complex** |
| `scripts/supabase_mcp.py` | MCP server exposing Supabase DB tools over stdio | moderate |
| `scratch/parse_sow.js` | One-time SoW HTML → normalized SQL | moderate |
| `scratch/parse_sow.py` | Python SoW parser (BeautifulSoup) → batched SQL | moderate |
| `scratch/test_rls.js` | Anonymous read test for RLS on `units` | simple |

### Configuration
| File | Role |
|------|------|
| `package.json` (root, `frontend/`, `backend/`) | Dependency manifests |
| `frontend/vite.config.js` | Vite + React plugin |
| `frontend/tailwind.config.js` | Dark theme palette, fonts, content paths |
| `frontend/eslint.config.js` | React hooks + Vite refresh lint rules |
| `.gitignore`, `.vscode/settings.json`, `MinerU_SOW__*.json` | Ignore rules, workspace, OCR metadata |

### Documentation
`gemini.md` (main roadmap), `mcp_configuration_for_supabase.md`, `frontend/README.md`, `frontend/build-log.txt`, and `frontend/engineering/*.md` role definitions.

## 6. Complexity Hotspots — approach carefully

- **`frontend/src/components/InteractiveTutor.jsx`** (complex) — Flagship feature; split-screen chat + tabbed views + dual backend integration. Use `useReducer` for chat state.
- **`scripts/ingest_pipeline.js`** (complex) — External MinerU dependency, PDF→DB mapping, fragile to OCR output changes.
- **`scratch/save_my_exams_schema.sql`** (complex) — Large self-contained schema/seed; review before applying to avoid clobbering live data.
- **`MinerU_SOW__20260412172453.json`** (complex) — 7 pages of OCR bounding boxes/spans; machine-generated, not hand-edited.
- **`HybridDocumentViewer.jsx`** (moderate) — Dual Markdown/JSON-graph render modes with Framer Motion; view-state juggling.
- **`backend/server.js`** + **FastAPI services** (moderate) — AI streaming + context management; watch token/cost limits.
