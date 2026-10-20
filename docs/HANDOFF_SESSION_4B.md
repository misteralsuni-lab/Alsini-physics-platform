# Handoff — Session 4B (Lesson Vertical Slice)

**From:** Session 4A.1 (Worksheet UX & AI Tutor Polish)
**To:** Session 4B (Lesson Vertical Slice)
**Date:** 2026-07-20
**Branch:** `multimodalragsystem` (one clean commit ahead of origin after 4A.1)

---

## What 4A.1 Delivered

1. **LearningContext object** — generic context carrier on `POST /api/tutor`
   (`backend/main.py`). Replace `focused_asset`-only scaffolding with a
   structured object that scales to lessons, practicals, quizzes.
2. **Graph context synchronization** — frontend sends `focused_asset` +
   `focused_asset_label` + `focused_asset_type` + `page` + `resource_id`
   so the tutor knows EXACTLY which figure the student is viewing and
   never asks them to "describe the graph" again.
3. **Asset grounding** — `_ground_focused_asset()` fetches the asset row
   + on-page chunks + linked question chunk + governing equation (for
   graphs) and prepends them to the RAG context.
4. **Simplified student citations** — student mode shows only
   Resource/Page/SpecRef; dev mode keeps full provenance.
5. **Spec-point dropdown removed** — spec points are internal curriculum
   references, no longer the student's primary navigation.
6. **Tutor prompt improved** — permanent persona line + dynamic
   `context_preamble` enforce explain/guide/question/coach from the
   visible figure.

Full details: `WORKSHEET_UX_POLISH_REPORT.md` and
`GRAPH_CONTEXT_SYNCHRONIZATION.md`.

---

## What 4B Should Reuse (No Redesign Needed)

### LearningContext is the integration point

Session 4B's lesson surface should populate the same `LearningContext`
object the worksheet surface now populates. The tutor endpoint,
asset grounding, and citation enrichment already consume it — no
API changes needed for the lesson surface.

Fields 4B should populate from the lesson surface:

```python
learning_context = {
    "resource_id": <lesson's source resource>,
    "chapter_id": <chapter>,
    "lesson_id": <lesson uuid>,              # NEW — 4B introduces lessons
    "block_id": <learning block uuid>,      # NEW — 4B introduces blocks
    "focused_chunk": <chunk id if a block is focused>,
    "page": <page if a PDF block is visible>,
    # focused_asset_* stay null unless a lesson embeds an asset
}
```

`PEDAGOGICAL_ARCHITECTURE.md §Learning Blocks` defines the block shape:
each block has Objectives, Explanation, Examples, Analogy, Mini Activity,
Reflection, Mini Quiz, Completion. The tutor should receive `block_id` so
its preamble can say "The student is on Block 3 of Lesson 2 —
Acceleration" instead of the current generic prompt.

### `_ground_focused_asset` is extensible

The helper currently keys off `focused_asset`. For lessons, an analogous
`_ground_focused_block` could retrieve the block's concepts, linked
formulas, and linked mini-quiz question — reusing the same PostgREST +
non-fatal pattern. Do NOT rewrite `_ground_focused_asset`; add a sibling
helper and call whichever matches `learning_context` shape.

### Citation policy is stable

Student-mode shows Resource/Page/SpecRef. Dev mode shows full provenance.
4B should NOT change this — it is aligned with
`AI_SYSTEM_ARCHITECTURE.md §Citation Policy` and
`RAG_ARCHITECTURE.md §Developer Mode`. New surfaces emit the same
`TutorSource` shape.

---

## Known Limitations Deferred to 4B

1. **Live browser verification of the tutor's graph-awareness reply**
   could not be completed in 4A.1 because the WSL session lacked the
   FastAPI backend + Supabase + NVIDIA NIM stack. 4B (or a deployment
   with the full stack) should run the acceptance test:
   - Focus a graph in the worksheet
   - Ask "Help me answer."
   - Verify the tutor reply references FIG-XX (not "describe the graph")
   - Verify the citation chips under the reply include the grounded asset
     chunk as `[Source 1]`

2. **`resource_assets.linked_question_id` population** — the asset
   grounding helper reads this field, but `PROJECT_ROADMAP.md` notes it
   is not yet populated for most assets. 4B should run
   `backend/pipeline/linked_question_resolver.py` to populate it so the
   linked-question grounding path activates at runtime.

3. **Pre-existing ESLint `motion` false-positive** in
   `HybridDocumentViewer.jsx:3`. 4A.1 did NOT touch this (per "no
   drive-by cleanup" git rule). 4B may address it as part of normal
   maintenance.

4. **`/api/grade` still uses full-context dump** (`fetch_forces_and_motion_data`).
   This is pre-existing technical debt tracked in
   `PROJECT_ROADMAP.md §Technical Debt Register`. 4A.1 did not migrate it
   (out of scope — no architectural changes). 4B may migrate it to RAG
   using the same `_retrieve_relevant_chunks` helper.

---

## Source-of-Truth Documents (Unchanged by 4A.1)

4A.1 made NO changes to the architecture documents. They remain the
source of truth for 4B:

- `docs/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/architecture/PEDAGOGICAL_ARCHITECTURE.md`
- `docs/architecture/AI_SYSTEM_ARCHITECTURE.md`
- `docs/architecture/RAG_ARCHITECTURE.md`
- `docs/architecture/PROJECT_ROADMAP.md`

If 4B's lesson implementation conflicts with any of them, STOP and report
the conflict before proceeding (per the standing instruction).

---

## Git State After 4A.1

- Branch: `multimodalragsystem`
- One logical commit: `feat: worksheet UX polish + graph context sync + LearningContext (Session 4A.1)`
- Working tree clean before commit
- No new dependencies
- No unrelated refactoring
- No drive-by cleanup
- All static acceptance tests pass; live browser verification deferred
  (documented in `SESSION_4A1_QA_REPORT.md`)

---

## Suggested First Steps for 4B

1. Read `WORKSHEET_UX_POLISH_REPORT.md` and `GRAPH_CONTEXT_SYNCHRONIZATION.md`
   to understand the LearningContext contract.
2. Run `linked_question_resolver.py` to populate `linked_question_id` so
   the grounding path activates.
3. Implement the Lesson surface, populating `LearningContext.lesson_id`
   and `LearningContext.block_id` as the student navigates blocks.
4. Add `_ground_focused_block` as a sibling of `_ground_focused_asset`
   (same PostgREST + non-fatal pattern) for block-level grounding.
5. Run the deferred live acceptance test (graph focus → tutor reply
   references FIG-XX) once the full stack is available.
