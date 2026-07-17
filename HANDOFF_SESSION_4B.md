# Handoff — Session 4B

## Worksheet Stabilization Complete → Lesson Experience

**Branch:** `multimodalragsystem`
**Date:** 2026-07-17
**Previous session:** 4A (Worksheet Stabilization)
**Next session:** 4B (Lesson Experience)

---

## Architecture Summary

The EDU-VLE is a React (Vite) frontend + FastAPI backend + Supabase
(Postgres + Storage) system with a hybrid RAG pipeline.

```
Frontend (React 19 + Vite, port 5173)
  App.jsx → VLEDashboard → InteractiveTutor
    ├─ HybridDocumentViewer (PDF iframe + assets + concept cards)
    ├─ SearchPanel (hybrid search side panel)
    ├─ QuizEngine (Quiz tab)
    └─ AI Tutor chat (FastAPI /api/tutor)

Backend (FastAPI, port 8000)
  /api/tutor     → RAG retrieval + LLM (OpenCode Zen → NVIDIA → Gemini)
  /api/search    → Pure vector search
  /api/search/hybrid → Vector + relational merge
  /api/grade     → Grading (legacy full-context, NOT RAG)
  /api/question  → Question fetch
  /api/resources/{id}/assets → Asset listing

Supabase
  resources (content JSON)
  resource_chunks (pgvector 1024-dim, HNSW index)
  resource_assets (storage_url → Supabase Storage)
  specification_points, chapters, units
  resource-assets bucket (public, PDFs + PNGs)
```

**Key architectural decision (Session 4A):** The RAG retrieval scope
is now fully dynamic. The frontend sends `resource_id` in the
`/api/tutor` POST body. The backend passes it to the
`match_resource_chunks` RPC as `filter_resource_id`. No hardcoded
resource ids in the tutor path.

---

## Completed Work (Session 4A)

1. **Default tab fixed** — App.jsx now defaults to 'Worksheet'.
2. **Resource pre-fetch** — guard removed; fetches on activeSpecPointId.
3. **Spec-point selector UI** — dropdown in InteractiveTutor header.
4. **Dynamic RAG scope** — resource_id flows from frontend → backend → RPC.
5. **Backend URL extraction** — VITE_API_URL env var (no more hardcode).
6. **Citation improvements** — compact labels (SRC-A12, EQ-03, FIG-04,
   TAB-02), clickable, expandable, traceable. Developer mode toggle.
7. **Focus sync** — SearchPanel navigation scrolls to concept card.
8. **Dead code removed** — unused Square import, QuizEngine hardcode.
9. **ESLint hardening** — react/jsx-no-undef rule prevents the
   original "User is not defined" class of bug.

---

## Remaining Work

### Session 4B: Lesson Experience (NOT STARTED)

The following are explicitly out of scope for 4A and belong to 4B+:

- Lesson experience implementation
- Quiz experience implementation (beyond what exists)
- Progress tracking
- Learning blocks
- Teacher analytics
- ZPD (Zone of Proximal Development)
- AFL (Assessment for Learning)
- Yearly planner
- Markdown workflow
- Adaptive tutoring

### Technical Debt for 4B+

1. **`/api/grade` still uses `TARGET_RESOURCE_ID`** — the grading
   endpoint's `fetch_forces_and_motion_data()` still hardcodes the
   Forces and Motion resource. Needs the same dynamic resource_id
   treatment as `/api/tutor`. The QuizEngine.jsx no longer has the
   hardcoded fallback (fixed in 4A), but the backend grade endpoint
   does.

2. **`source_refs.page` is `None` for most chunks** — embedding
   pipeline doesn't populate page numbers for concept/relation types.
   Citation labels fall back to sequential indices. Needs embedding
   pipeline improvement.

3. **PDF iframe page navigation (`#page=N`)** — not wired. The iframe
   shows the full PDF but doesn't jump to pages on focus events.

4. **Express server.js is dead code** — not removed. Frontend no
   longer references it. Consider archiving or deleting in 4B.

5. **`google.generativeai` deprecation** — migrate to `google.genai`.

6. **Bundle size** — 1.13 MB. Code-splitting recommended.

7. **Playwright tests need NSS libs** — ensure the CI environment has
   `libnspr4` and `libnss3` installed.

---

## Recommendations

1. **Start 4B with the Lesson tab.** The Worksheet slice is now
   stable. The Lesson tab currently renders a placeholder. The
   architecture (InteractiveTutor orchestrator + HDV + focus state)
   is reusable for the Lesson experience.

2. **Reuse the dynamic RAG pattern.** The `resource_id` → backend →
   RPC filter pattern established in 4A should be reused for any
   new tab that needs RAG retrieval (Lessons, Simulations).

3. **Wire `/api/grade` to dynamic resource_id** early in 4B — the
   QuizEngine already sends it dynamically; the backend just needs
   to accept and use it.

4. **Run the Playwright suite in an environment with NSS libs**
   before merging 4B — the tests are designed to pass and passed in
   Session 3. The only blocker is the system library availability.

---

## Risks

1. **Playwright regression not verified in this environment.** The
   NSS library limitation means the 14-test regression suite hasn't
   been re-run against the 4A changes. The build and lint pass, and
   the changes are surgical, but full E2E verification requires the
   libraries.

2. **`/api/grade` hardcoded resource** — if a student uses the Quiz
   tab with a non-Forces-and-Motion worksheet, grading still uses
   Forces and Motion context. This is a known limitation, not a
   regression (it was hardcoded before 4A too).

3. **Citation labels are generated client-side** — the label format
   (SRC-A12, EQ-03) is computed in `citationLabel()`. If the backend
   adds new chunk types, the `CHUNK_TYPE_PREFIX` map needs updating.

---

## Important Files

| File | Role |
|------|------|
| `frontend/src/App.jsx` | Root — default tab state (now 'Worksheet') |
| `frontend/src/components/InteractiveTutor.jsx` | Orchestrator — chat, HDV, search, focus, spec-point selector, dev mode, CitationChip |
| `frontend/src/components/HybridDocumentViewer.jsx` | PDF iframe + assets + concept cards (conceptCardRefs for scroll sync) |
| `frontend/src/components/SearchPanel.jsx` | Hybrid search side panel (VITE_API_URL) |
| `frontend/src/components/QuizEngine.jsx` | Quiz tab (hardcode removed, VITE_API_URL) |
| `frontend/src/lib/supabaseClient.js` | Supabase client init |
| `frontend/.env.local` | VITE_API_URL (port 8000), Supabase URL + anon key |
| `frontend/eslint.config.js` | react/jsx-no-undef rule |
| `backend/main.py` | FastAPI — /api/tutor (dynamic resource_id), TutorRequest, TutorSource |
| `backend/pipeline/embedding_pipeline.py` | Chunking + embedding (unchanged in 4A) |
| `tests/regression.spec.js` | 14-test Playwright suite |

---

## Important Commits

| Commit | Description |
|--------|-------------|
| c9616f2 | (Session 3) Fixed missing `User` import — the original crash |
| 2fb20c9 | (Session 3) OpenCode Zen integration |
| **4A commit** | Worksheet stabilization — all 4A changes |

---

## Testing Instructions

### Prerequisites

1. Backend running: `cd backend && .venv/bin/python -m uvicorn main:app --port 8000`
2. Frontend running: `cd frontend && npm run dev`
3. For Playwright: `sudo apt-get install -y libnspr4 libnss3`

### Manual smoke test

1. Open `http://localhost:5173` → login
2. Click a chapter in the sidebar
3. Verify: Worksheet tab is active by default (not Lesson)
4. Verify: PDF iframe loads in the worksheet area
5. Verify: Spec-point selector dropdown is visible in the header
6. Select a different spec point → worksheet updates
7. Click "Search" button → SearchPanel opens
8. Type "velocity" + Enter → results appear
9. Click a result → concept card scrolls into view + context chip appears
10. Open AI Tutor (right drawer) → send a message
11. Verify: AI response has citation chips (SRC-XX, EQ-XX format)
12. Click a citation chip → expands to show traceability
13. Click the Code2 icon (dev mode) → click chip again → shows full traceability

### Automated regression

```bash
cd frontend && npx playwright test
```

---

## Lessons Learned

1. **A single missing import can mask all other bugs.** The `User`
   crash (Session 3) made every downstream symptom look like a
   different bug. The forensic methodology (isolate trigger vs root
   cause) was essential.

2. **Default tab choice is a UX-critical decision.** Defaulting to
   'Lesson' (a placeholder) made the entire worksheet look broken.
   The worksheet was there all along — just hidden behind a tab
   the user had to discover.

3. **Static analysis gates prevent classes of bugs.** The
   `react/jsx-no-undef` rule would have caught the original `User`
   bug at lint time. Adding it is a one-time investment that pays
   off forever.

4. **Dynamic scoping must flow end-to-end.** Half-dynamic
   (frontend sends question, backend hardcodes resource_id) is worse
   than fully static — it creates a false sense of dynamic behavior.
   The fix required changes in the frontend payload, the backend
   model, and the retrieval function signature.

5. **Citation traceability is a UX feature, not just a technical one.**
   Compact labels (SRC-A12) + expandable detail gives students a
   clean view and developers a full audit trail. The developer mode
   toggle avoids overwhelming students with metadata.
