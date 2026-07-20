# System Architecture

## Alsini Physics Platform — Edexcel IGCSE/A-Level Physics VLE

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     Frontend (React 19 + Vite)                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     App.jsx                               │   │
│  │  ├─ Auth.jsx (login/register/password reset)             │   │
│  │  ├─ VLEDashboard (authenticated shell)                   │   │
│  │  │   ├─ Sidebar (syllabus nav + Triple Science toggle)   │   │
│  │  │   ├─ Navbar (search, user menu)                       │   │
│  │  │   └─ Outlet: InteractiveTutor                         │   │
│  │  │       ├─ HybridDocumentViewer                          │   │
│  │  │       │   ├─ Mode A: PDF iframe (Supabase Storage)    │   │
│  │  │       │   ├─ Mode B: Interactive Knowledge (concepts) │   │
│  │  │       │   └─ AssetCard (images with retry fallback)   │   │
│  │  │       ├─ SearchPanel (hybrid search side panel)        │   │
│  │  │       ├─ QuizEngine (quiz tab)                         │   │
│  │  │       └─ AI Tutor chat (FastAPI /api/tutor)           │   │
│  │  ├─ Landing pages (Hero, Features, Philosophy, etc.)     │   │
│  │  └─ UpdatePassword                                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Styling: TailwindCSS + Framer Motion + GSAP                     │
│  State: React useState/useReducer + supabaseClient singleton    │
│  Rendering: KaTeX (math) + ReactMarkdown                        │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           │ POST /api/tutor  │  POST /api/search
                           │ GET  /api/question│  GET  /api/resources/{id}/assets
                           │ POST /api/grade
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                  Backend (FastAPI, port 8000)                     │
│                                                                  │
│  /api/tutor              → RAG retrieval + LLM (NVIDIA/Gemini)  │
│  /api/search             → Pure vector search                    │
│  /api/search/hybrid      → Vector + relational merge             │
│  /api/question           → Question fetch                        │
│  /api/grade              → Grading (legacy full-context)         │
│  /api/resources/{id}/assets → Asset metadata                    │
│  /api/resources/{id}/assets/{type} → Filtered assets            │
│                                                                  │
│  RAG Pipeline:                                                   │
│    _embed_query() → NVIDIA NV-EmbedQA-E5-V5 (1024-dim)          │
│    match_resource_chunks RPC → pgvector cosine similarity         │
│    _format_chunks_as_context() → compact string (~500 chars)      │
│    _chunks_to_sources() → TutorSource[] with citations           │
│                                                                  │
│  Model routing: evaluate_routing() → NVIDIA Llama 3.3 or Gemini  │
│                                                                  │
│  — Legacy Express server (port 5000) available but deprecated — │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Supabase (Postgres + Storage)                   │
│                                                                  │
│  Tables:                                                         │
│    units, chapters, specification_points                         │
│    activities, resources, questions                              │
│    resource_chunks (pgvector 1024-dim, HNSW index)               │
│    resource_assets (storage URLs, bounding boxes)                │
│    quiz_attempts (RLS per user)                                  │
│    profiles (linked to auth.users via trigger)                   │
│                                                                  │
│  RPC Functions:                                                  │
│    match_resource_chunks(query_embedding, match_count,           │
│                          filter_resource_id)                     │
│                                                                  │
│  Storage Buckets:                                                │
│    resource-assets (public) → PDFs + PNGs                        │
│      └─ {resource_id}/page{N}_{type}_{index}.png                 │
│                                                                  │
│  Auth: Supabase Auth (email/password) + RLS policies            │
│                                                                  │
│  MCP: supabase_mcp.py (local) + Supabase Remote MCP (SSE)       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | React + Vite | React 19 |
| Styling | TailwindCSS | Latest |
| Animations | Framer Motion, GSAP | Latest |
| Icons | Lucide React | Latest |
| Math Rendering | KaTeX | Latest |
| Backend (primary) | FastAPI + Uvicorn | Python 3.x |
| Backend (legacy) | Express.js | Node.js |
| AI Models | NVIDIA Llama 3.3, Gemini 2.5 Flash, NVIDIA NV-EmbedQA-E5-V5 | — |
| Database | PostgreSQL (via Supabase) | Latest |
| Vector Search | pgvector (HNSW, cosine, 1024-dim) | Latest |
| Storage | Supabase Storage (S3-compatible) | Latest |
| Auth | Supabase Auth (email/password, RLS) | Latest |
| CI/CD | MCP (Model Context Protocol) | — |
| Testing | Playwright | Latest |

---

## Data Flow Patterns

### Authentication Flow
```
User → Auth.jsx → supabase.auth.signInWithPassword()
       → Supabase Auth → JWT session
       → App.jsx session listener → VLEDashboard (protected)
       → RLS policies filter all queries per auth.uid()
```

### RAG Tutor Flow
```
Student question → InteractiveTutor.handleSend()
       → POST /api/tutor {student_prompt, history, resource_id}
       → _retrieve_relevant_chunks(query)
           → _embed_query() → NVIDIA NV-EmbedQA
           → match_resource_chunks RPC → top-5 chunks
       → _format_chunks_as_context(chunks) → compact string
       → LLM (NVIDIA/Gemini) → response + citations
       → InteractiveTutor renders: markdown + source chips
```

### Search Flow
```
Student query → SearchPanel
       → POST /api/search/hybrid {query, resource_id}
       → Vector search (pgvector) + Relational search (keyword)
       → Merge, dedup, boost cross-matches (+0.1)
       → Return ranked results with similarity scores
       → Student clicks → focus state → concept card + tutor
```

### Asset Flow
```
Worksheet render → GET /api/resources/{id}/assets
       → resource_assets table → storage URLs
       → <img src={storage_url}> fallback → retry on error
```

---

## Component Topology

| Component | File | Responsibility |
|-----------|------|---------------|
| App | `App.jsx` | Auth session, routing, loading gate |
| Auth | `Auth.jsx` | Login, register, password reset |
| VLEDashboard | `VLEDashboard.jsx` | Authenticated shell + tab state |
| Sidebar | `Sidebar.jsx` | Syllabus nav, Triple Science toggle |
| InteractiveTutor | `InteractiveTutor.jsx` | Chat + viewer + focus state orchestrator |
| HybridDocumentViewer | `HybridDocumentViewer.jsx` | PDF iframe + knowledge cards |
| SearchPanel | `SearchPanel.jsx` | Hybrid search UI |
| QuizEngine | `QuizEngine.jsx` | Quiz taking + grading |
| AssetCard | inside HybridDocumentViewer | Image render + retry |

---

## Environment Variables

| Variable | Used In | Purpose |
|----------|---------|---------|
| `VITE_SUPABASE_URL` | Frontend | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Frontend | Supabase anonymous key |
| `VITE_API_URL` | Frontend | Backend FastAPI URL (default: localhost:8000) |
| `SUPABASE_URL` | Backend | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend | Service role key for ingest pipelines |
| `NVIDIA_API_KEY` | Backend | NVIDIA NIM + embedding API |
| `GEMINI_API_KEY` | Backend | Google Gemini API |
| `FRONTEND_URL` | Backend | CORS allowed origin (production) |

---

## Key Architectural Decisions

1. **RAG replaces full-context dump** — prompt size reduced ~93%, citations preserved
2. **FastAPI supplants Express** — port 8000 is primary AI backend; port 5000 is legacy
3. **Supabase Storage for assets** — no local filesystem, public CDN URLs
4. **No SDK, REST-only** — `requests` library for Supabase API (matches existing pattern)
5. **RLS-first** — data access filtered at DB level per `auth.uid()`
6. **Focus state as single source of truth** — syncs SearchPanel → viewer → tutor
7. **Non-fatal RAG** — tutor still answers if embedding/RPC fails (degraded quality)
8. **Compact citation labels** — SRC-A12, EQ-03, FIG-04, TAB-02; expandable in dev mode
