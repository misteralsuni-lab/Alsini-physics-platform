# Handoff — Session 4

## EDU-VLE Implementation Roadmap

**Branch:** `multimodalragsystem`
**Date:** July 14, 2026
**Session 3 Status:** ✅ Complete — all acceptance tests pass

---

## Executive Summary

Session 3 transformed the EDU-VLE from a chatbot-with-document-viewer into an intelligent educational workspace. The AI tutor now retrieves relevant knowledge chunks via hybrid search (RAG) instead of injecting the entire OpenKB JSON. The document viewer displays the authentic PDF (Mode A) alongside an interactive knowledge panel (Mode B) with bidirectional synchronization. A new search panel exposes hybrid retrieval to the learner. All assets render from Supabase Storage URLs with graceful retry fallback.

---

## Completed Work

### Stage 1: True RAG Tutor
- Replaced `fetch_forcing_and_motion_data()` with `_retrieve_relevant_chunks()` in `/api/tutor`
- New functions: `_retrieve_relevant_chunks()`, `_format_chunks_as_context()`, `_chunks_to_sources()`
- New Pydantic models: `TutorSource`, `TutorResponse` (with `sources` field)
- Context reduced 93% (8,000+ chars → ~500 chars)

### Stage 2: InteractiveTutor Frontend
- Switched from Express `/api/chat` (port 5000) to FastAPI `/api/tutor` (port 8000)
- Added RAG citation chips under AI messages
- Preserved `[SWITCH_TAB]` parsing and conversation history

### Stage 3: Hybrid Document Viewer
- Mode A: original PDF rendered via Supabase Storage public URL in an iframe
- Mode B: interactive knowledge panel with focus-driven affordances
- PDF uploaded to `resource-assets/{resource_id}/original.pdf` (517KB, public)

### Stage 4: Synchronization
- Single `focus` state in InteractiveTutor propagates to viewer and chat
- Click concept → context chip → prefixed tutor question
- Click asset → context chip → prefixed tutor question
- Related concept chips are clickable
- Focused concept card gets emerald ring highlight

### Stage 5: Search Experience
- New `SearchPanel.jsx` component
- Calls `/api/search/hybrid` with chunk type filters
- Displays relevance bars, similarity %, chunk type, concept, page
- Clicking a result navigates to the concept (sets focus)

### Stage 6: Asset Rendering Hardening
- `AssetCard` now has retry button on image load failure
- `key={retryCount}` forces re-mount to re-fetch
- All assets load from Supabase Storage URLs (no local paths)

### Stage 7: QA + Deliverables
- All 14 acceptance tests pass
- 5 deliverable docs produced (this is one of them)

---

## Files Modified

| File | Change | Stage |
|------|--------|-------|
| `backend/main.py` | RAG helper functions, TutorSource/TutorResponse models, endpoint body replaced | 1 |
| `frontend/src/components/InteractiveTutor.jsx` | FastAPI switch, citation chips, focus state, search toggle | 2, 4, 5 |
| `frontend/src/components/HybridDocumentViewer.jsx` | PDF iframe (Mode A), focus-driven cards (Mode B), asset retry | 3, 4, 6 |
| `frontend/src/components/SearchPanel.jsx` | NEW — hybrid search UI | 5 |
| `INTELLIGENT_LEARNING_ARCHITECTURE.md` | NEW — architecture doc | 7 |
| `FRONTEND_INTEGRATION.md` | NEW — frontend changes doc | 7 |
| `RAG_INTEGRATION.md` | NEW — RAG documentation | 7 |
| `QA_REPORT.md` | NEW — QA report | 7 |
| `HANDOFF_SESSION_4.md` | NEW — this document | 7 |

---

## API Changes

### `POST /api/tutor`

**Response model updated:**
- Before: `{response: str, model_used: str}` (plain dict)
- After: `TutorResponse{response: str, model_used: str, sources: List[TutorSource]}`

**New `TutorSource` model:**
```python
class TutorSource(BaseModel):
    chunk_id: str
    concept: Optional[str] = None
    page: Optional[int] = None
    chunk_type: str
    similarity: float
```

**Backward compatible:** `sources` is additive. Existing consumers that ignore unknown fields are unaffected.

### No other endpoints changed
- `/api/search` — unchanged
- `/api/search/hybrid` — unchanged
- `/api/question` — unchanged
- `/api/grade` — unchanged (tech debt)
- `/api/resources/{id}/assets` — unchanged

---

## Frontend Changes

- `InteractiveTutor.jsx` — FastAPI `/api/tutor` call, citation chips, focus state + context chip, search toggle
- `HybridDocumentViewer.jsx` — PDF iframe (Mode A), focus-driven concept cards (Mode B), asset retry fallback
- `SearchPanel.jsx` (new) — hybrid search UI with relevance indicators, chunk type filters, navigation

---

## Tutor Changes

- **Before:** Full OpenKB JSON injected into LLM prompt (~8,000+ chars)
- **After:** Top-5 relevant chunks retrieved via pgvector, formatted as compact context (~500 chars)
- **Citations:** `TutorSource[]` returned with every response, rendered as chips in the frontend
- **Routing:** Unchanged (NVIDIA Llama 3.3 for complex, Gemini Flash for simple)
- **Fallback:** Non-fatal — if retrieval fails, tutor answers without context

---

## Acceptance Test Results

| # | Test | Result |
|---|------|--------|
| 1 | Tutor uses hybrid retrieval instead of full JSON | ✅ PASS |
| 2 | Tutor answers using retrieved chunks only | ✅ PASS |
| 3 | Graph renders | ✅ PASS |
| 4 | Diagram renders | ✅ PASS |
| 5 | Table renders | ✅ PASS |
| 6 | Equations render correctly | ✅ PASS |
| 7 | Original PDF displays correctly | ✅ PASS |
| 8 | Interactive Knowledge view displays correctly | ✅ PASS |
| 9 | Search retrieves relevant content | ✅ PASS |
| 10 | Search navigates correctly | ✅ PASS |
| 11 | Source references remain intact | ✅ PASS |
| 12 | Specification-point navigation remains correct | ✅ PASS |
| 13 | Existing Session 2 endpoints remain functional | ✅ PASS |
| 14 | No regressions introduced | ✅ PASS |

---

## Remaining Technical Debt

| # | Item | Severity | Notes |
|---|------|----------|-------|
| 1 | `/api/grade` still uses full-context | Medium | Should migrate to RAG in Session 4 |
| 2 | `source_refs.page` is `None` for most chunks | Low | Embedding pipeline needs to populate page numbers |
| 3 | PDF iframe page navigation (`#page=N`) not wired | Low | Needs page numbers in source_refs first |
| 4 | Backend URL hardcoded as `localhost:8000` | Medium | Extract to env var for deployment |
| 5 | `FRONTEND_URL` env var unset — CORS permissive | Medium | Lock down for production |
| 6 | Pre-existing lint errors (5 unused vars) | Low | Cleanup pass |
| 7 | `google.generativeai` deprecated | Low | Migrate to `google.genai` |
| 8 | Frontend bundle 1.1MB | Medium | Code-splitting recommended |

---

## Known Issues

1. **Hardcoded localhost URLs** — `InteractiveTutor.jsx` and `SearchPanel.jsx` both hardcode `http://localhost:8000`. Must be env-var-ized before deployment.
2. **Page numbers missing** — most `TutorSource.page` values are `null` because the embedding pipeline doesn't populate `source_refs.page` for concept/relation chunks.
3. **Similarity scores appear moderate** (0.3-0.5) — this is normal for NV-EmbedQA with a 21-chunk corpus. Not a bug.

---

## Performance Observations

| Metric | Before (Session 2) | After (Session 3) |
|--------|--------------------|--------------------|
| Tutor prompt size | ~8,000+ chars | ~500 chars |
| Context reduction | — | 93% |
| RAG retrieval latency | N/A | 200-400ms |
| Frontend build | 3.5s | 2.0s |
| Bundle size | 1.1MB | 1.1MB (unchanged) |

---

## Risks

1. **NVIDIA embedding API** — if down, tutor falls back to no-context mode (non-fatal by design)
2. **PDF iframe sandbox** — `allow-scripts allow-same-origin` needed; tighten if concerns arise
3. **Hardcoded URLs** — will break on deployment; must env-var-ize

---

## Repository Status

- **Branch:** `multimodalragsystem`
- **Commits ahead of origin:** 4
- **Working tree:** clean (changes auto-committed during session)
- **Commit log (top 4):**
  - `bca1dac` feat: Add search panel toggle and integrate with Hybrid Document Viewer
  - `93750db` feat: Enhance technology stack documentation and add new features
  - `c22323c` feat: Implement hybrid retrieval search panel and integrate with document viewer
  - `b49440d` feat: Add compiled Python bytecode for master ingestion module

---

## Git Branch

`multimodalragsystem` → `origin/multimodalragsystem` (4 commits ahead)

---

## Architectural Decisions Made

1. **RAG over full-JSON** — use existing `match_resource_chunks` RPC, no new infra
2. **FastAPI for tutor, Express untouched** — no server merging
3. **PDF via public Supabase URL** — no local filesystem paths, no schema changes
4. **Single `focus` state for sync** — avoids event-bus complexity
5. **SearchPanel as side-panel toggle** — contextual, not a separate page
6. **Non-fatal RAG** — tutor works even if retrieval fails
7. **Asset retry via `key` remount** — simple, no external retry library

---

## Suggested First Task for Session 4

**Migrate `/api/grade` to RAG retrieval.**

The grading endpoint still injects the full OpenKB JSON context (the same pattern the tutor had before Session 3). This is the highest-severity technical debt item. The fix follows the exact same pattern as the tutor:

1. Call `_retrieve_relevant_chunks()` with the student's answer as the query
2. Format the retrieved chunks as context using `_format_chunks_as_context()`
3. Inject the compact context into the grading LLM prompt
4. Return `sources` in the grading response

This should take ~30 minutes and closes the last full-context-dump endpoint in the system.

---

## Session 4 Roadmap (Proposed)

1. **Migrate `/api/grade` to RAG** (highest priority — tech debt #1)
2. **Env-var-ize backend URLs** — extract `http://localhost:8000` to `VITE_BACKEND_URL`
3. **Wire PDF page navigation** — `#page=N` fragment on the iframe when a concept with page metadata is focused
4. **Populate `source_refs.page`** in the embedding pipeline (requires touching `resource_ingestion.py`)
5. **Migrate `google.generativeai` → `google.genai`** (deprecation warning)
6. **Frontend code-splitting** — reduce bundle from 1.1MB to <500KB
7. **Lock down CORS** — set `FRONTEND_URL` env var and restrict origins
