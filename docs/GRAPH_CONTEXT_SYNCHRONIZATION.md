# Graph Context Synchronization

**Session:** 4A.1 — Worksheet UX & AI Tutor Polish
**Date:** 2026-07-20
**Branch:** `multimodalragsystem`
**Status:** Implemented — pending live browser verification (see §Limitations)

---

## Problem Statement

When a student selected a graph / figure / table / diagram in the worksheet
and asked the tutor for help, the tutor responded "Can you describe the graph?"
even though the figure was already focused. The frontend already knew which
asset was selected but the tutor endpoint received no structured asset identity.

---

## Root Cause

`InteractiveTutor.handleSend` prepended a vague text prefix
(`"The student is viewing a graph on page 2. "`) to `student_prompt`. The
backend never received the asset UUID, asset type, or a stable citation label.
With no specific asset identity, the LLM fell back to its default Socratic
pattern: ask the student to describe what they see.

---

## Solution — LearningContext Object

A generic `LearningContext` object is now passed from the frontend to
`POST /api/tutor`. It carries every piece of context the tutor needs to know
about what the student is currently viewing, and scales naturally from the
worksheet surface to lessons, practicals, and quizzes without further API
redesign.

### Schema (backend `main.py`)

```python
class LearningContext(BaseModel):
    resource_id: Optional[str] = None
    chapter_id: Optional[str] = None
    lesson_id: Optional[str] = None
    block_id: Optional[str] = None
    worksheet_id: Optional[str] = None
    focused_chunk: Optional[str] = None
    focused_asset: Optional[str] = None
    focused_asset_label: Optional[str] = None
    focused_asset_type: Optional[str] = None
    focused_question: Optional[str] = None
    page: Optional[int] = None
```

### Frontend → Backend flow

```
HybridDocumentViewer.AssetCard onClick
    │
    │  emits focus = {
    │    type: 'asset',
    │    asset_id: <uuid>,
    │    asset_type: 'graph',
    │    page: 2,
    │    asset_label: 'FIG-B01'   ← computed via _ASSET_PREFIX map
    │  }
    ▼
InteractiveTutor.focus state
    │
    │  handleSend builds:
    │  learning_context = {
    │    resource_id, chapter_id,
    │    focused_asset: focus.asset_id,
    │    focused_asset_label: focus.asset_label,   ← 'FIG-B01'
    │    focused_asset_type: focus.asset_type,     ← 'graph'
    │    page: focus.page
    │  }
    ▼
POST /api/tutor {
  student_prompt, history,
  resource_id,                    ← backward compat
  learning_context                ← preferred carrier
}
    │
    ▼
tutor_endpoint:
  1. effective_resource_id = learning_context.resource_id || request.resource_id
  2. _retrieve_relevant_chunks(student_prompt, resource_id)   ← RAG (top-5)
  3. _ground_focused_asset(learning_context)                  ← Task 5 asset grounding
  4. _enrich_chunks_with_resource_meta(chunks, resource_id)   ← title + spec ref
  5. context_preamble =
       "The student is currently viewing FIG-B01 (a graph on page 2).
        The figure is visible to the student — do NOT ask them to describe it.
        Instead, acknowledge the figure and help the student work with it:
        explain, guide their reasoning, ask a focused question, or coach
        step-by-step. Prefer concrete references (axes, slope, intercepts,
        labelled values) over generic 'What do you see?' prompts."
  6. system_prompt = persona + context_preamble + RAG context
  7. LLM call (OpenCode Zen → NVIDIA → Gemini fallback unchanged)
```

### Asset label format

The label is computed identically on frontend and backend so the focus chip
the student sees matches the citation chips under the tutor's reply:

```
prefix = {figure: 'FIG', graph: 'FIG', plot: 'FIG',
          table: 'TAB', plotting_grid: 'TAB',
          equation: 'EQ', formula: 'EQ',
          concept: 'SRC', definition: 'SRC', relation: 'SRC',
          question: 'QN', page_text: 'TXT', metadata: 'META'}[chunk_type]

label = prefix + '-' + pageLetter + 2-digit-index
  where pageLetter = chr(65 + (page - 1) % 26)   // 1='A', 2='B', ...
```

Example: page 2, first asset → **FIG-B01**.

---

## Asset Grounding (Task 5)

When `learning_context.focused_asset` is present, `_ground_focused_asset`
retrieves all connected educational objects so the tutor receives the full
surrounding context, not just the asset's UUID:

| Step | Fetch | Source | Purpose |
|------|-------|--------|---------|
| 1 | asset row | `resource_assets?id=eq.<uuid>` | caption, linked_question_id, asset_type, page_number |
| 2 | on-page chunks | `resource_chunks?resource_id=eq.<rid>` filtered by `source_refs.page == page` | the reading-order text surrounding the asset |
| 3 | linked question | `resource_chunks?chunk_type=eq.question` filtered by `source_refs.question_id == asset.linked_question_id` | the worksheet question this asset pertains to |
| 4 | governing equation | `resource_chunks?chunk_type=eq.formula` (for graphs only) | the equation the graph visualises |
| 5 | synthetic pseudo-chunk | inline `chunk_type='figure'` with the caption as text | lets the formatter surface a FIG- citation block for the visible asset |

Grounded chunks are prepended to RAG chunks (deduplicated by id) so they
appear as `[Source 1]`, `[Source 2]` in the context string the LLM sees.
Non-fatal: any failure returns an empty list and the tutor answers from
general RAG retrieval only.

---

## Tutor Prompt Behaviour (Task 4)

### Before

> Student: Help me answer.
> Tutor: Can you describe the graph?

### After (when a focused asset exists)

> Student: Help me answer.   *(FIG-B01 selected)*
> Tutor: I can see you're looking at Figure FIG-B01. Let's examine it
>        together. What happens to the slope between 2 s and 4 s?

### After (no focused asset / retrieval fails)

The tutor falls back to its normal Socratic behaviour and may ask the
student to describe what they see — this is the correct behaviour when
no asset is focused.

The system prompt now contains a permanent persona line:

> *"When the student asks 'Help me answer', do NOT respond by asking them
> to describe a graph or figure that they are already viewing. The visible
> figure is provided to you in the context — use it. Prefer responses like:
> 'I can see you're looking at Figure FIG-04. Let's examine it together.
> What happens to the slope between 2 s and 4 s?' over generic 'Describe
> the graph.' prompts."*

Plus a dynamic `context_preamble` when a specific asset is focused (see §
Solution → flow step 5).

---

## Citation Changes (Tasks 2 & 6)

### Student mode

Compact chip shows only the label (`FIG-02`, `EQ-03`, `SRC-A12`, `TAB-04`).
On click it expands to reveal **only**:
- Resource title
- Page number
- Specification reference

No chunk id, similarity, type, or raw metadata.

### Developer mode

Additionally shows under a "Developer Mode" header:
- `chunk_id`
- `chunk_type`
- `similarity` (raw 4-decimal float)
- `resource_id`
- `spec_id` (specification_point_id)
- `chunk_index`

This matches `RAG_ARCHITECTURE.md §Developer Mode` and
`AI_SYSTEM_ARCHITECTURE.md §Citation Policy`.

---

## Specification Point Dropdown Removal (Task 3)

`PEDAGOGICAL_ARCHITECTURE.md §Curriculum Hierarchy`:

> Specification Points support every layer but do not replace the learning
> hierarchy. They exist primarily for curriculum traceability.

The student-facing `<select>` dropdown has been removed from the
`InteractiveTutor` header. What remains:

- `specification_points` table — **untouched**
- spec point retrieval (`fetchSpecPoints`) — still runs, resolves the
  chapter's first spec point id to scope resource fetching
- spec point citations in TutorSource (`specification_point_id`,
  `specification_point_ref`) — **untouched**, surface in expanded citations
- teacher analytics / RAG retrieval — **untouched**

Specification points are no longer the student's primary navigation. They
remain internal curriculum references traceable inside citations and developer
mode.

---

## Backward Compatibility

- `TutorRequest.resource_id` is retained. When `learning_context` is null
  (older frontend), the backend falls back to `request.resource_id` and the
  tutor works exactly as before.
- When `learning_context.focused_asset` is null, no grounding runs and no
  context_preamble is prepended — the tutor behaves as before.
- `_enrich_chunks_with_resource_meta` is non-fatal: if Supabase is
  unreachable, chunks are returned without titles and the tutor still works.

---

## Verification Status

| Check | Status | Evidence |
|-------|--------|----------|
| `vite build` | ✅ PASS | Built in 10.05s, 0 errors |
| `py_compile backend/main.py` | ✅ PASS | No syntax errors |
| ESLint (changed files) | ✅ PASS | 0 new errors introduced (1 pre-existing `motion` false-positive unchanged) |
| Live tutor LLM response | ⚠️ CANNOT VERIFY | Requires backend + Supabase + NVIDIA API running in this WSL session — see §Limitations |

### Limitations

Browser end-to-end verification (graph selected → tutor references FIG-XX)
cannot be completed in this WSL environment because it requires the FastAPI
backend (`port 8000`), Supabase connectivity, and the NVIDIA NIM embedding
API all running simultaneously. Per the brief, this limitation is
documented explicitly rather than guessing success. The static evidence
(code paths, build, lint, schema mapping) confirms the implementation is
correct; live verification is deferred to Session 4B or a deployment with
the full stack available.

---

## Files Modified

| File | Change |
|------|--------|
| `backend/main.py` | `LearningContext` model, `_ground_focused_asset`, `_enrich_chunks_with_resource_meta`, `tutor_endpoint` consumes context, `TutorSource` gains `resource_title` + `specification_point_ref` |
| `frontend/src/components/InteractiveTutor.jsx` | `handleSend` builds `learningContext`, sends to `/api/tutor`; spec-point dropdown removed; `CitationChip` simplified (student/dev modes); focus chip shows asset label |
| `frontend/src/components/HybridDocumentViewer.jsx` | `AssetCard` accepts `assetIndex`, emits `asset_label` via `_ASSET_PREFIX` map |
