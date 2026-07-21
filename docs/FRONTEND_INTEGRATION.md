# Frontend Integration

## Session 3 — Frontend Changes Documentation

**Branch:** `multimodalragsystem`
**Date:** July 14, 2026

---

## Executive Summary

Three frontend components were modified/created in Session 3:
1. `InteractiveTutor.jsx` — switched from Express `/api/chat` to FastAPI `/api/tutor`, added citation chips, context sync, search toggle
2. `HybridDocumentViewer.jsx` — added Mode A (PDF iframe), Mode B focus-driven affordances, asset retry fallback
3. `SearchPanel.jsx` (new) — hybrid search UI with relevance indicators and navigation

---

## Completed Work

### 1. InteractiveTutor.jsx

**File:** `frontend/src/components/InteractiveTutor.jsx`

#### Changes:

**a) Backend switch (Stage 2)**
- Changed `fetch('http://localhost:5000/api/chat', ...)` → `fetch('http://localhost:8000/api/tutor', ...)`
- Request payload: `{student_prompt, history}` (was `{message, history}` with Gemini-formatted parts)
- Response: now extracts `data.sources` alongside `data.response` and `data.model_used`

**b) RAG citation chips (Stage 2)**
- AI messages now render `msg.sources` as small citation chips below the response text
- Each chip shows: source number `[N]`, concept name, page number (when available), chunk type
- Tooltip: `chunk_type · similarity: 0.XX`
- Styled: `bg-[#151515]`, `border border-white/10`, emerald source number

**c) Focus state + synchronization (Stage 4)**
- New state: `const [focus, setFocus] = useState(null)`
- Passed to HybridDocumentViewer as `focus` and `onFocus`
- Context chip rendered above chat input when `focus` is non-null:
  - Shows: "Context | Concept: Acceleration" (or asset/spec-point)
  - Clearable with ✕ button
- `handleSend()` prefixes the question with focus context:
  - `"The student is looking at the concept 'Acceleration'. {user question}"`
  - Focus is consumed (cleared) after sending

**d) Search panel toggle (Stage 5)**
- New state: `const [showSearch, setShowSearch] = useState(false)`
- Toggle button in the tab bar (only visible on Worksheet tab)
- When open, renders SearchPanel in a 320px side panel alongside HybridDocumentViewer
- SearchPanel's `onNavigate` callback sets focus to the clicked result's concept

**e) Import updates**
- Added: `Search` icon from lucide-react
- Added: `import SearchPanel from './SearchPanel'`
- Added: `import QuizEngine from './QuizEngine'` (re-added after accidental removal)

---

### 2. HybridDocumentViewer.jsx

**File:** `frontend/src/components/HybridDocumentViewer.jsx`

#### Changes:

**a) Component signature (Stage 3/4)**
- Before: `const HybridDocumentViewer = ({ resourceId })`
- After: `const HybridDocumentViewer = ({ resourceId, focus, onFocus })`

**b) PDF URL derivation (Stage 3)**
- New state: `const [pdfUrl, setPdfUrl] = useState(null)`
- `useEffect` derives the public URL from `VITE_SUPABASE_URL` + `resourceId`:
  ```
  {SUPABASE_URL}/storage/v1/object/public/resource-assets/{resourceId}/original.pdf
  ```
- No backend endpoint needed — the bucket is public

**c) Mode A: Original PDF (Stage 3)**
- Replaced the markdown-only view with an iframe rendering the authentic PDF:
  ```jsx
  <iframe src={pdfUrl} className="w-full h-[70vh]" sandbox="allow-scripts allow-same-origin" />
  ```
- Visual assets (AssetCard grid) now render below the PDF
- Markdown content (data.content_markdown) renders as a "Text Interpretation" secondary block
- Graceful fallback if no PDF, no content, no assets

**d) Mode B: Focus-driven concept cards (Stage 4)**
- Concept cards now call `onFocus({ concept, block_index, type })` on click
- Focused card gets emerald ring highlight: `border-emerald-500/60 bg-emerald-500/5 ring-1 ring-emerald-500/30`
- Related concept chips are now clickable: `onFocus({ concept: rc, type: 'concept' })`
- Hover state: `hover:border-emerald-500/30 hover:text-emerald-400`

**e) Asset click → focus (Stage 4)**
- AssetCard image area now has `onClick` that calls `onFocus({ type: 'asset', asset_id, asset_type, page })`

**f) Asset retry fallback (Stage 6)**
- New state: `const [retryCount, setRetryCount] = useState(0)`
- On image error: shows "Retry" button instead of just the error icon
- Retry forces re-mount via `key={retryCount}` on the `<img>` element
- Click on asset image area triggers `onFocus` (cursor-pointer)

---

### 3. SearchPanel.jsx (NEW)

**File:** `frontend/src/components/SearchPanel.jsx`

#### Purpose:
Exposes hybrid retrieval to the learner. Student can search across concepts, formulas, and relationships extracted from the worksheet.

#### Features:
- **Search input** with Enter-to-search
- **Chunk type filters**: All / Concepts / Formulas / Relations / Questions
- **Results** display:
  - Rank number (#1, #2, ...)
  - Chunk type badge
  - Similarity bar (emerald >60%, yellow >40%, gray <40%)
  - Similarity percentage
  - Chunk text preview (line-clamp-2)
  - Concept name, page number
  - "boosted" indicator when hybrid search boosted the result
  - "Open" affordance on hover
- **Navigation**: clicking a result calls `onNavigate(result)` which sets the focus to the result's concept
- **Loading/error states**: spinner, error message, empty state
- **Clear search**: ✕ button clears query and results

#### API Contract:
```json
POST /api/search/hybrid
{
  "query": "velocity",
  "match_count": 10,
  "resource_id": "5729d034-...",
  "chunk_type": "concept"  // optional
}
```

---

## Files Modified

| File | Status | Lines Changed |
|------|--------|---------------|
| `frontend/src/components/InteractiveTutor.jsx` | Modified | ~100 lines |
| `frontend/src/components/HybridDocumentViewer.jsx` | Modified | ~130 lines |
| `frontend/src/components/SearchPanel.jsx` | Created | 260 lines |

---

## Build Verification

```bash
cd frontend && npm run build
# ✓ built in 3.54s — no errors
```

```bash
cd frontend && npm run lint
# 5 pre-existing errors (unused vars) — none introduced by Session 3
```

---

## Acceptance Test Results

| Test | Result |
|------|--------|
| InteractiveTutor connects to FastAPI /api/tutor | ✅ PASS |
| Citation chips render under AI messages | ✅ PASS |
| Follow-up questions preserve chat behaviour | ✅ PASS |
| Original PDF displays correctly (Mode A) | ✅ PASS |
| Interactive Knowledge view displays correctly (Mode B) | ✅ PASS |
| Bidirectional sync (concept → tutor context) | ✅ PASS |
| Search retrieves relevant content | ✅ PASS |
| Search navigates to learning content | ✅ PASS |
| Source references remain intact | ✅ PASS |
| Graph renders (from Supabase Storage URL) | ✅ PASS |
| Diagram renders (from Supabase Storage URL) | ✅ PASS |
| Broken links fail gracefully (retry button) | ✅ PASS |

---

## Performance Observations

- **Frontend bundle:** 1.1MB (pre-existing, unchanged by Session 3)
- **SearchPanel:** Lazy-mounted only when toggled open (conditional render)
- **Asset images:** `loading="lazy"` on all `<img>` tags
- **Re-renders:** Focus state changes cause re-render of InteractiveTutor subtree only (HybridDocumentViewer receives `focus` prop). No unnecessary re-renders detected.
- **PDF iframe:** Loads the full 517KB PDF once. No re-fetch on view mode toggle.

---

## Known Issues

1. **Pre-existing lint errors** (5 unused vars) — not introduced by Session 3, left untouched to avoid drive-by refactors
2. **PDF page navigation** — the iframe does not jump to specific pages when a concept is focused. This would require `#page=N` fragment support, which needs page numbers in `source_refs` (currently not populated)
3. **Search panel width** — fixed at 320px (`w-80`). Not responsive on mobile. Acceptable for current scope.

---

## Risks

- **CORS** — frontend calls `http://localhost:8000` directly. If the deployment changes, the hardcoded URL needs updating. Recommend extracting to an env var in Session 4.
- **Bundle size** — 1.1MB is above the 500KB warning threshold. Code-splitting recommended for Session 4+.
