# Core Release Blockers Report — Session 4A.2

**Branch:** `multimodalragsystem`
**Date:** 2026-07-22
**Scope:** Worksheet Vertical Slice stabilization — three release blockers only.
**Base commit:** `a54f959`
**Review method:** Serial agency review loop (Architect → Backend → Frontend → RAG → QA → Code Reviewer)

---

## Executive Summary

Three release blockers identified in the Session 4A.1 Verification Report have been root-cause fixed:

1. **Backend Canonical Citation IDs** — The frontend no longer invents citation labels. The backend generates canonical IDs from verified asset metadata and returns them in `TutorSource.asset_label`. The same ID is used in the tutor preamble, synthetic source, and citation chips.

2. **Deterministic Graph → Formula Relationship** — Graphs no longer guess formulas via arbitrary `chunk_type=eq.formula` retrieval. Formula context is retrieved ONLY through an explicit `metadata.linked_formula_chunk_id` relationship on the asset. If no relationship exists, the tutor fails closed with an honest disclosure.

3. **Route State Reset** — Every chapter/resource transition now completely resets LearningContext, focus, worksheet resource, search results, citations, active graph, chat history, and pending requests. Stale-request guards (`AbortController` + generation counter) prevent cross-chapter response leakage.

---

## Issue 1 — Backend Canonical Citation IDs

### Root Cause

The frontend generated citation labels via `assetCitationLabel()` in `HybridDocumentViewer.jsx` and `citationLabel()` in `InteractiveTutor.jsx`. The label was derived from array index position and passed as `focused_asset_label` to the backend, which accepted it after verifying only the asset/resource relationship. A reordered asset list or crafted request could produce a label that did not identify the verified asset.

### Implementation

**Backend (`backend/main.py`):**
- Added `_canonical_asset_label(asset_row)` function (line ~321) that generates a `PREFIX-LNN` label from the verified asset row's `asset_type`, `page_number`, and a deterministic `_page_ordinal` computed from the page-ordered asset set.
- The ordinal is computed by fetching ALL assets for the resource ordered by `page_number.asc, created_at.asc` and counting the asset's position within its page. This is immune to client-side reordering.
- The synthetic asset pseudo-chunk now carries `canonical_asset_label` instead of `learning_context.focused_asset_label`.
- The tutor context preamble derives `effective_label` from the grounded chunks' `asset_label` only — the client-supplied `focused_asset_label` is never used as a fallback (Issue 1 compliance).
- The `LearningContext.focused_asset_label` field is deprecated with a clear DEPRECATED comment, retained for API backward compatibility, and never read in any code path.

**Frontend (`frontend/src/components/InteractiveTutor.jsx`):**
- `learningContext` construction no longer sends `focused_asset_label`.
- `CitationChip` still uses `src.asset_label` (the backend-returned value) — this was already correct; the comment was updated to clarify it is server-canonical.
- The focus chip in the chat input no longer shows `asset_label` — it shows only `asset_type` + `page` (verified viewer metadata). Citation IDs appear only in response citation chips, rendered from backend values.

**Frontend (`frontend/src/components/HybridDocumentViewer.jsx`):**
- Removed `ASSET_TYPE_PREFIX` and `assetCitationLabel()` functions.
- Removed `_assetLabel` computation from `AssetCard`.
- Both viewer modes (document + interactive) no longer pass `asset_label` in the focus callback — only `asset_id`, `asset_type`, and `page`.

### Files Changed
- `backend/main.py` — new `_canonical_asset_label()`; modified `_ground_focused_asset()`; modified tutor preamble
- `frontend/src/components/InteractiveTutor.jsx` — removed `focused_asset_label` from LearningContext; updated focus chip
- `frontend/src/components/HybridDocumentViewer.jsx` — removed label generation; removed `asset_label` from focus calls

### Architectural Impact
No architectural change. The backend remains the source of truth for all citation data. The frontend renders only what the backend returns. The `TutorSource` model and `LearningContext` shape are unchanged.

---

## Issue 2 — Deterministic Graph → Formula Relationship

### Root Cause

When a graph was selected, `_ground_focused_asset` block 4 retrieved up to 3 formula chunks for the entire resource using `chunk_type=eq.formula`. This was non-deterministic: an unrelated equation could be presented as the governing formula, or the intended formula could be silently omitted.

### Implementation

**Backend (`backend/main.py`):**
- Block 4 in `_ground_focused_asset` now reads `metadata.linked_formula_chunk_id` from the asset's verified `metadata` JSONB column.
- If `linked_formula_chunk_id` is present, it retrieves ONLY that specific chunk (by `id` + `resource_id` for verification).
- If `linked_formula_chunk_id` is absent, a `no_linked_formula = True` marker is set on the synthetic asset chunk.
- The tutor preamble includes an explicit disclosure when `no_linked_formula` is true: "No governing formula is linked to this graph. Do NOT invent or guess an equation."
- The old arbitrary `chunk_type=eq.formula` retrieval with `limit=3` has been removed entirely.

### Fail-Closed Behavior
- No heuristic matching.
- No semantic similarity as a substitute.
- No guesswork.
- The tutor honestly states no verified formula is linked, rather than hallucinating one.

### Files Changed
- `backend/main.py` — block 4 of `_ground_focused_asset`; preamble disclosure

### Migration Note
The `resource_assets.metadata` JSONB column (mig_5) already supports storing `linked_formula_chunk_id`. Populating this field for graph assets is a data-pipeline task (embedding pipeline or a migration script), not a code change in this session. Until populated, graph focus will honestly report no linked formula — which is the correct behavior per the fail-closed requirement.

---

## Issue 3 — Route State Reset

### Root Cause

Changing chapter/resource could leak: focus, LearningContext, citations, tutor history, and stale requests. The `chapterId` change triggered `fetchSpecPoints` which reset `activeSpecPointId`, but no other state was cleared. Stale async responses from a previous chapter could overwrite newer state.

### Implementation

**Frontend (`frontend/src/components/InteractiveTutor.jsx`):**

- **Chapter-change reset effect** (new `useEffect` on `[chapterId]`):
  - Aborts any in-flight resource fetch via `resourceAbortRef.current.abort()`.
  - Increments `tutorGenRef.current` to invalidate in-flight tutor responses.
  - Resets: `messages` → `[INITIAL_MESSAGE]`, `focus` → `null`, `worksheetResource` → `null`, `isLoading` → `false`, `showSearch` → `false`, `activeSpecPointId` → `null`.
  - Clears `conceptCardRefs.current = {}`.

- **Resource fetch with AbortController:**
  - `resourceAbortRef` (an `AbortController` ref) is assigned for each fetch.
  - The Supabase client receives `.abortSignal(controller.signal)`.
  - On abort, the response is discarded (early return).
  - The cleanup function aborts the controller on unmount or re-trigger.

- **Tutor request generation counter:**
  - `tutorGenRef` is incremented at the start of each `handleSend`.
  - The response handler checks `myGen !== tutorGenRef.current` — if they differ, a chapter/resource transition occurred during the fetch and the response is discarded.
  - The error handler and `finally` block also check the generation before applying state mutations.

- **Spec-point transition:**
  - The resource fetch immediately clears `worksheetResource` before the new fetch resolves, so the viewer doesn't render a previous chapter's content while loading.

### Files Changed
- `frontend/src/components/InteractiveTutor.jsx` — reset effect, AbortController, generation counter, resource fetch guard

### Architectural Impact
No architectural change. `LearningContext` remains the universal carrier. The state machine is still: Chapter → SpecPoint → Resource → Worksheet → Tutor. No new state object was introduced.

---

## Verification

### Build
```
cd frontend && npm run build
✓ built in 6.87s
```
Build passes — no errors, no new warnings.

### Lint
```
cd frontend && npm run lint
✖ 9 problems (9 errors, 0 warnings)
```
All 9 errors are **pre-existing** (documented in WORKSHEET_STABILIZATION_REPORT.md Session 4A). Zero new lint errors introduced.

### Backend Validation
- Python AST parse: ✓ SYNTAX OK
- `_canonical_asset_label` function: ✓ present, correct signature
- `_ground_focused_asset` block 4: ✓ `linked_formula_chunk_id` explicit lookup, `no_linked_formula` marker
- Tutor preamble: ✓ no-formula disclosure present
- Old `chunk_type=eq.formula` arbitrary retrieval: ✓ removed

### Not Verified (Environment Limitations)
- Vite production build in Windows-native environment (build ran in WSL successfully)
- Playwright browser regression (NSS libraries unavailable in this WSL session — pre-existing)
- Live Supabase Auth + RAG verification (FastAPI not installed in this session)
- Live NVIDIA embedding/RAG verification
- Live LLM graph-grounding verification

---

## Remaining Technical Debt

1. **`resource_assets.metadata.linked_formula_chunk_id` population** — the fail-closed path is implemented, but the field is not yet populated for most assets. A data-pipeline task (not code) must populate this for graph assets to activate the formula grounding path.

2. **`backend/__pycache__/main.cpython-314.pyc`** — compiled bytecode appears as a tracked file modified by Python syntax checks. This is pre-existing (commit `e722c00`).

3. **Pre-existing lint errors (9)** — same as Session 4A. Out of scope.

4. **`/api/grade` still uses `TARGET_RESOURCE_ID`** — pre-existing, out of scope (Quiz vertical).

5. **Playwright regression** — cannot run in WSL without NSS libraries. Pre-existing.

6. **Live browser verification** — deferred to a deployment with the full FastAPI + Supabase + NVIDIA stack.

---

## Lines Changed Summary

```
 backend/main.py                                  | 200 +++++++++++++++----
 frontend/src/components/HybridDocumentViewer.jsx |  31 +---
 frontend/src/components/InteractiveTutor.jsx     | 129 +++++++++++--
 3 files changed (excluding __pycache__), 281 insertions(+), 79 deletions(-)
```
