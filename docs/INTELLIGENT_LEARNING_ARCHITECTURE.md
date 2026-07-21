# Intelligent Learning Architecture

## Session 3 — Architecture Document

**Branch:** `multimodalragsystem`
**Date:** July 14, 2026
**Status:** Complete — all acceptance tests pass

---

## Executive Summary

Session 3 transforms the EDU-VLE from a chatbot-with-document-viewer into an intelligent educational workspace. The key architectural shift: the AI tutor now retrieves relevant knowledge chunks via hybrid search instead of injecting the entire OpenKB JSON blob into the LLM prompt. The document viewer now displays the authentic PDF alongside an interactive knowledge panel, with bidirectional synchronization between the two representations.

---

## Architectural Decisions Made

### 1. RAG Replaces Full-Context Dump

**Before:** `fetch_forcing_and_motion_data()` → entire JSON → LLM prompt
**After:** `_retrieve_relevant_chunks(query)` → top-5 chunks → compact context string → LLM prompt

**Rationale:** Reduces prompt size from thousands of chars to ~400-600 chars. Preserves citations. Maintains traceability via `TutorSource` metadata.

**Decision:** Use existing `match_resource_chunks` RPC (Session 2 infrastructure). No new schema, no new endpoints. The tutor endpoint reuses `_embed_query()` and `_supabase_headers()` already in `main.py`.

### 2. FastAPI /api/tutor (Port 8000) — Express /api/chat (Port 5000) Untouched

**Decision:** Switch `InteractiveTutor.jsx` to call FastAPI `/api/tutor` directly. Express server stays as-is (out of scope). No server merging.

**Rationale:** FastAPI already has the RAG retrieval pipeline, pgvector integration, and search endpoints. Express is a Gemini-only passthrough with no retrieval.

### 3. PDF Rendered via Public Supabase URL — No Local Filesystem

**Decision:** Upload the Golden Dataset PDF to `resource-assets/{resource_id}/original.pdf` in Supabase Storage. Render via `<iframe src="{public URL}">`.

**Rationale:** Handoff requires "Never use local filesystem paths." The bucket is already public. No schema changes needed — the URL is derived from `SUPABASE_URL + resource_id`.

### 4. Bidirectional Sync via Focus State

**Decision:** Single `focus` state in `InteractiveTutor.jsx` propagates to both `HybridDocumentViewer` and the chat input. Clicking a concept/asset in the viewer sets `focus`, which:
- Highlights the matching concept card in Mode B
- Shows a context chip above the chat input
- Prefixes the next tutor question with the focused context

**Rationale:** Avoids event-bus complexity. Single source of truth. The focus is consumed (cleared) after the question is sent.

### 5. Search Panel as Side-Panel Toggle

**Decision:** `SearchPanel.jsx` is a new component rendered alongside `HybridDocumentViewer` in a split layout. Toggled by a button in the tab bar.

**Rationale:** Keeps the worksheet as the primary view. Search is contextual, not a separate page.

### 6. Asset Retry Fallback

**Decision:** `AssetCard` component now includes a retry button on image load failure. Uses `key={retryCount}` to force re-mount of the `<img>` element.

**Rationale:** Handoff requires "Broken links must fail gracefully."

---

## System Architecture

```
┌─────────────────────────────────────────────┐
│           Frontend (React + Vite)            │
│                                              │
│  ┌────────────┐  ┌──────────────────────┐   │
│  │ InteractiveTutor.jsx                   │   │
│  │  ├─ focus state (sync hub)            │   │
│  │  ├─ Chat (FastAPI /api/tutor)        │   │
│  │  ├─ HybridDocumentViewer              │   │
│  │  │   ├─ Mode A: PDF iframe            │   │
│  │  │   └─ Mode B: Interactive Knowledge │   │
│  │  └─ SearchPanel (toggle)              │   │
│  └────────────┘  └──────────────────────┘   │
│         │                    │               │
└─────────┼────────────────────┼───────────────┘
          │                    │
          ▼                    ▼
┌─────────────────────────────────────────────┐
│         Backend (FastAPI, port 8000)         │
│                                              │
│  /api/tutor          → RAG retrieval + LLM  │
│  /api/search         → Semantic search       │
│  /api/search/hybrid  → Hybrid search        │
│  /api/question       → Question generation   │
│  /api/grade          → Grading (full ctx)    │
│  /api/resources/{id}/assets → Asset URLs     │
│                                              │
│  RAG Pipeline:                               │
│    _embed_query() → NVIDIA NV-EmbedQA        │
│    match_resource_chunks() → pgvector RPC    │
│    _format_chunks_as_context() → compact str │
│    _chunks_to_sources() → TutorSource[]      │
└─────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────┐
│    Supabase (Postgres + Storage)            │
│                                              │
│  resource_chunks (21 chunks, pgvector)      │
│  resource_assets (3 PNGs)                    │
│  resource-assets bucket (public)             │
│    └─ {resource_id}/original.pdf (517KB)     │
│  match_resource_chunks RPC                   │
└─────────────────────────────────────────────┘
```

---

## Component Topology

| Component | File | Responsibility |
|-----------|------|----------------|
| InteractiveTutor | `InteractiveTutor.jsx` | Orchestrator: chat + viewer + search + focus state |
| HybridDocumentViewer | `HybridDocumentViewer.jsx` | Mode A (PDF) + Mode B (Knowledge) + asset rendering |
| SearchPanel | `SearchPanel.jsx` (new) | Hybrid search UI with relevance indicators |
| AssetCard | inside `HybridDocumentViewer.jsx` | Single asset render with retry fallback |

---

## Data Flow: RAG Tutor

```
Student types question
        │
        ▼
InteractiveTutor.handleSend()
        │
        ├─ If focus exists: prefix question with context
        │
        ▼
POST /api/tutor {student_prompt, history}
        │
        ▼
_retrieve_relevant_chunks(student_prompt)
        │
        ├─ _embed_query() → NVIDIA NV-EmbedQA-E5-V5
        │
        ├─ match_resource_chunks RPC (pgvector cosine)
        │   └─ filter_resource_id = TARGET_RESOURCE_ID
        │
        ▼
Top-5 chunks (by similarity)
        │
        ├─ _format_chunks_as_context() → compact string
        │
        ├─ _chunks_to_sources() → TutorSource[]
        │
        ▼
LLM (NVIDIA Llama 3.3 or Gemini Flash)
        │
        ▼
TutorResponse {response, model_used, sources[]}
        │
        ▼
InteractiveTutor renders:
  ├─ Response text (ReactMarkdown + KaTeX)
  └─ Source citation chips (concept, page, type, similarity)
```

---

## Performance Observations

| Metric | Before (Session 2) | After (Session 3) |
|--------|--------------------|--------------------|
| Tutor prompt size | ~8,000+ chars (full JSON) | ~400-600 chars (5 chunks) |
| LLM context tokens | ~2,000+ | ~150-200 |
| API round-trip | 1 call (LLM only) | 2 calls (embed + LLM) — embed cached |
| Asset failure handling | Static error icon | Retry button with re-mount |
| Search latency | N/A | ~200-400ms (NVIDIA embed + pgvector) |

---

## Remaining Technical Debt

1. `/api/grade` still uses full-context (not RAG). Flagged for Session 4.
2. `source_refs.page` is `None` for most chunks — the embedding pipeline doesn't populate page numbers. Search results show "p.None" in some cases.
3. PDF iframe navigation to specific pages (via `#page=N` fragment) is not wired — the iframe shows the full PDF but doesn't jump to pages on focus events.
4. `FRONTEND_URL` env var is unset — CORS is permissive. Should be locked down for production.
5. Pre-existing lint errors (5 unused vars) remain in HybridDocumentViewer, InteractiveTutor, QuizEngine, VLEDashboard.
6. `google.generativeai` package is deprecated — should migrate to `google.genai` in a future session.

---

## Risks

1. **NVIDIA embedding API rate limits** — if the embedding service is down, RAG retrieval silently returns empty (tutor still works, just without context). This is by design (non-fatal).
2. **PDF iframe sandbox** — `sandbox="allow-scripts allow-same-origin"` is needed for PDF rendering but could be tightened if security concerns arise.
3. **Bundle size** — frontend bundle is 1.1MB (pre-existing). Code-splitting is recommended for Session 4+.
