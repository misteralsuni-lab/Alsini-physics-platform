# Project Roadmap

## Alsini Physics Platform — Edexcel IGCSE/A-Level Physics VLE

---

## Executive Summary

A modern, open-access physics education VLE with an AI tutor, RAG-powered retrieval, interactive worksheets, asset management, and a curriculum-aligned learning experience. The system uses React (Vite) + FastAPI + Supabase with hybrid vector search.

---

## Phase 1: Foundation (Complete)

- React SPA with Vite + TailwindCSS + Framer Motion
- Supabase auth (login, register, password reset)
- 6-tier curriculum schema → unified SaveMyExams hierarchy
- Row-Level Security on all curriculum tables
- Dark-mode glassmorphic UI

---

## Phase 2: Curriculum & Content (Complete)

- Edexcel IGCSE Physics curriculum seeded (9 units, 28+ chapters, 190+ spec points)
- PDF ingestion pipeline (MinerU OCR → `master_ingestion.py`)
- OpenKB semantic JSON knowledge graph in `resources.content`
- EDU-VLE Dashboard with sidebar navigation + Triple Science toggle

---

## Phase 3: AI Tutor & Chat (Complete)

- InteractiveTutor split-screen UI (document viewer + AI chat)
- Express.js backend → Gemini 2.5 Flash (Socratic tutor persona)
- Agentic tab switching via hidden `[SWITCH_TAB]` tags
- Sliding AI Tutor drawer + floating action button

---

## Phase 4: Asset Infrastructure (Complete)

- `resource_assets` table + Supabase Storage bucket
- Python extraction pipeline (PyMuPDF → classification → upload)
- Golden Dataset validated: 3-page worksheet, 2 extracted assets
- `GET /api/resources/{id}/assets` endpoints

---

## Phase 5: Hybrid Retrieval (Complete)

- `resource_chunks` table with `vector(1024)` + HNSW index
- `match_resource_chunks` RPC for pgvector cosine similarity
- `nvidia/nemotron-3.5-embed-1b` (`1024-dim`) embedding pipeline (in-place re-embedding completed in `#11`)
- Hybrid search endpoints (pure vector + relational merge)
- SearchPanel frontend component with chunk-type filters

---

## Phase 6: RAG Tutor & Backend Unification (Complete)

- FastAPI `/api/tutor` now uses RAG instead of full-JSON context dump
- Prompt size reduced ~93% (8,000+ chars → 400-600 chars)
- Cited sources with compact citation labels (SRC-A12, EQ-03, FIG-04, TAB-02)
- Dynamic `resource_id` scoping (no hardcoded singleton)
- Focus sync: SearchPanel → concept card → tutor context chip

---

## Phase 7: QA & Hardening (Complete)

- 15-check Playwright regression suite
- Forensic investigation resolved `User` import crash
- 9-bug taxonomy from 7-specialist review
- Engineering review score: **6.71 / 10 — Beta readiness**
- ESLint hardening (`react/jsx-no-undef`)
- Backend URL extraction to env var (`VITE_API_URL`)

---

## Phase 8: Worksheet Stabilization (Complete)

- Default tab changed to `Worksheet`
- Resource pre-fetch on spec point change
- Spec-point selector dropdown UI
- Asset cards with retry fallback
- Dead code removal (Square import, Express server identified as legacy)

---

## Current Status & Immediate Work

| Area | Status |
|------|--------|
| Core VLE UI | ✅ Complete |
| Auth & RLS | ✅ Complete |
| Curriculum data | ✅ Seeded |
| Asset pipeline | ✅ Complete |
| Hybrid search | ✅ Complete |
| RAG tutor | ✅ Complete |
| Regression suite | 🔶 Partial (check 5 hangs) |
| Quiz engine | 🔶 Basic implementation needs expansion |
| Lesson experience | 📋 Planned (Ch. 1 Vertical Slice: `#13`, `#14`; see [PRD](../prd/chapter-1-vertical-slice.md)) |
| Practical simulation | 📋 Planned (Ch. 1 Spec 1.5 + VMR debrief: `#15`; see [PRD](../prd/chapter-1-vertical-slice.md)) |
| Progress tracking | 📋 Planned (RLS `student_block_progress`: `#13`, `#14`) |
| Teacher analytics | ❌ Not started |
| Adaptive tutoring | ❌ Not started |

---

## Short-Term (Next Session)

- **Unstick Playwright check 5** — resolve the search-hang in the runner
- **Remove debug scripts** (`dbglogin.mjs`, `dbgsearch.mjs`) once regression is fully green
- **Migrate `/api/grade` to RAG** — replace full-context dump
- **Populate `source_refs.page`** — enable PDF page navigation via `#page=N`

---

## Medium-Term (Production Readiness)

- ✅ CORS allowlist locked down (`FRONTEND_URL` / `CORS_ORIGINS` env vars in `backend/main.py`, no wildcard)
- Rate limiting on `/api/tutor` (`slowapi` for FastAPI)
- Automated tests: `vitest` for citation chips & pure kinematics/physics math, `pytest` for retrieval
- Remove/archive Express `server.js` (port 5000 dead code)
- Populate `resource_assets.linked_question_id` from semantic JSON
- Chapter 1 Vertical Slice (`1.3–1.10`) — Wayfinder issues `#13` (Marp parser + schema + unified RAG), `#14` (Learning Block player + touchable graphs), `#15` (Spec 1.5 simulation + VMR debrief)
- Quiz experience expansion (`/api/grade` RAG migration + `/api/question` Chapter 1 bank — deferred follow-up)

---

## Long-Term (Vision)

- Content expansion across all Edexcel IGCSE and A-Level chapters
- Multimodal tutor (text + diagram + graph reasoning)
- Cross-resource retrieval (lesson, worksheet, quiz)
- Teacher analytics dashboard + AI Teacher Assistant
- Zone of Proximal Development (ZPD) detection
- Assessment for Learning (AFL) integration
- Adaptive tutoring with personalised pathways
- Frontend code-splitting (bundle < 500KB)
- Migrate `google.generativeai` → `google.genai`
- Interactive physics simulations

---

## Technical Debt Register

| Debt | Impact | Target Session |
|------|--------|---------------|
| `/api/grade` still uses full-context (not RAG) & `/api/question` is hardcoded | Prompt bloat, no citations, single sample question | Follow-up ticket (deferred from Ch. 1 Vertical Slice) |
| `source_refs.page` is None for most chunks | No PDF page jumping | Short-term |
| Playwright check 5 hangs | Incomplete test coverage | Short-term |
| Express `server.js` is dead code | Maintenance burden | Medium-term |
| Bundle is 1.1MB (no code-splitting) | Slow initial load | Long-term |

---

## Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| NVIDIA embedding API rate limits | Medium | Non-fatal fallback (tutor answers without context) |
| PDF iframe sandbox restrictions | Low | `sandbox="allow-scripts allow-same-origin"` |
| Hardcoded backend URLs in old code | Low | Now using `VITE_API_URL` env var |
| Missing JSX imports (class of bug) | Low | ESLint `react/jsx-no-undef` rule enforced |
