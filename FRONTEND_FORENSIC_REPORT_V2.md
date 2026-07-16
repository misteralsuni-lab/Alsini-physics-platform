# Frontend Forensic Report V2 — Alsini Physics VLE

**Branch:** `multimodalragsystem`
**Date:** 2026-07-16
**Investigators:** 7 specialist agents (Senior React Engineer, Frontend Architect, UX Engineer, Accessibility Engineer, Senior Full Stack Engineer, Code Reviewer, Incident Response Commander)
**Mode:** Read-only forensic investigation — no fixes applied
**Prior report:** `FRONTEND_FORENSIC_REPORT.md` (found missing `User` import — FIXED in commit c9616f2)

---

## Executive Verdict

The previous forensic report identified a single missing `User` icon import as the root cause of all frontend crashes. That fix has been applied (commit c9616f2). **The frontend no longer crashes on user chat messages.**

However, the worksheet rendering pipeline still has **8 confirmed bugs** (2 high severity, 4 medium, 2 low) that collectively explain the "inconsistent behaviour" the user reports. The dominant failure is **NOT a crash** — it is a **state-synchronization gap between two independent tab systems** that makes the worksheet appear unreachable or empty depending on the user's navigation path.

---

## 1. ARCHITECTURE VALIDATION

### Component Tree (verified by source inspection)

```
App.jsx
 ├─ <Router>
 └─ <AppContent session activeTab setActiveTab>
     ├─ <Navbar/>           (hidden on /dashboard)
     ├─ <Routes>
     │   ├─ "/"            → <Home/> | <Navigate to="/dashboard">
     │   ├─ "/auth"        → <Auth/> | <Navigate to="/dashboard">
     │   └─ "/dashboard"  → <VLEDashboard session>    [PROTECTED]
     │       ├─ index                → <DashboardHome/>
     │       └─ "unit/:u/chapter/:c" → <InteractiveTutor activeTab setActiveTab/>
     │           ├─ <HybridDocumentViewer resourceId focus onFocus/>
     │           │   ├─ <iframe src={pdfUrl}/>           [Document mode]
     │           │   ├─ <AssetCard/> × N                 [Document mode]
     │           │   ├─ <ReactMarkdown/>                 [Document mode]
     │           │   ├─ <motion.button/> × N (concept cards) [Interactive mode]
     │           │   ├─ <ConceptPopup/>                   [Interactive mode]
     │           │   └─ <AssetZoomModal/>                 [both modes]
     │           ├─ <SearchPanel resourceId onNavigate/>  [conditional: showSearch && Worksheet tab]
     │           └─ <QuizEngine resourceId activeSpecPointId/> [conditional: Quiz tab]
     └─ <Footer/>           (hidden on /dashboard)
```

### Verdict: Architecture is SOUND

- Routing: correct nested routes, `<Outlet/>` pattern works
- Session gating: correct — `loading` state prevents null-session redirect
- Component boundaries: correct — each component has a single responsibility
- No missing components (the "KnowledgeNode" from the prior report is the concept cards, which DO exist)

---

## 2. RENDERING PIPELINE DIAGRAM

```
User clicks chapter in Sidebar
  │
  ▼
URL: /dashboard/unit/:unitId/chapter/:chapterId
  │
  ▼
InteractiveTutor mounts
  │
  ├─ useEffect[chapterId] → fetch spec_points from Supabase
  │    └─ setActiveSpecPointId(data[0].id)                    ← FIRST spec point only
  │
  ├─ activeTab = 'Lesson' (DEFAULT, from App.jsx useState)
  │
  └─ RENDER:
       activeTab === 'Worksheet'?  → NO (default is 'Lesson')
       activeTab === 'Quiz'?      → NO
       else                       → PLACEHOLDER (grey box, "Document will render here...")
  │
  ▼
User must manually click "Worksheet" tab
  │
  ▼
setActiveTab('Worksheet')
  │
  ├─ useEffect[activeTab, activeSpecPointId] fires
  │    └─ if activeTab === 'Worksheet' && activeSpecPointId:
  │         fetch resources WHERE specification_point_id = activeSpecPointId
  │         └─ setWorksheetResource(rich resource or data[0])
  │
  ▼
HybridDocumentViewer receives resourceId = worksheetResource?.id
  │
  ├─ useEffect[resourceId] → setPdfUrl(Supabase Storage URL)
  ├─ useEffect[resourceId] → fetch resources.content + resource_assets
  │    └─ setData(content) + setAssets([])
  │
  └─ RENDER (viewMode = 'document' by default):
       ├─ <iframe src={pdfUrl} sandbox="allow-scripts allow-same-origin"/>
       ├─ <AssetCard> × assets.length
       ├─ <ReactMarkdown> if data.content_markdown exists
       └─ fallback if no content
  │
  ▼
User can toggle viewMode to 'interactive' → concept cards + ConceptPopup
User can toggle showSearch → SearchPanel renders alongside
```

### Critical observation
The worksheet does NOT render by default. The user lands on a **placeholder** (Lesson tab). They must click "Worksheet" to trigger the resource fetch and rendering. This is the #1 source of "worksheet not rendering" complaints.

---

## 3. SYNCHRONIZATION DIAGRAM

```
┌─────────────────────────────────────────────────────────┐
│  TWO INDEPENDENT TAB SYSTEMS (ROOT CAUSE #1)            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  System A: InteractiveTutor activeTab (App.jsx:62)     │
│    Values: 'Lesson' | 'Worksheet' | 'Simulation' | 'Quiz'
│    Owner: App.jsx useState, passed as props             │
│    Controls: which BODY renders (placeholder vs HDV vs Quiz)
│                                                         │
│  System B: HybridDocumentViewer viewMode (line 221)    │
│    Values: 'document' | 'interactive'                  │
│    Owner: HybridDocumentViewer local useState           │
│    Controls: which VIEW inside HDV renders (PDF vs concepts)
│                                                         │
│  ⚠ NO SYNCHRONIZATION between A and B                   │
│  ⚠ AI tutor [SWITCH_TAB:] tag only talks to System A    │
│  ⚠ System B is only reachable INSIDE System A's 'Worksheet' │
│                                                         │
└─────────────────────────────────────────────────────────┘

Focus State Sync (CORRECT):
  InteractiveTutor.focus (line 26)
    ├─ → HybridDocumentViewer.focus (prop, line 280)
    │    └─ highlights concept card (line 522-534)
    │    └─ triggers ConceptPopup via selectedIdx
    ├─ → Chat input context chip (lines 427-443)
    └─ → consumed in tutor prompt (lines 138-145)

  HybridDocumentViewer.onFocus (prop, line 281)
    ├─ ← concept card click (line 529)
    ├─ ← asset card click (line 45)
    └─ → setFocus({concept/asset_type/page}) in InteractiveTutor

  SearchPanel.onNavigate (prop, line 288-293)
    └─ → setFocus({concept}) in InteractiveTutor
       ⚠ Only sets concept focus — does NOT scroll HDV to concept
```

---

## 4. RAG FLOW DIAGRAM

```
Student Question
  │
  ▼
InteractiveTutor.handleSend() (line 111)
  ├─ Build contextualPrompt (line 138)
  │    └─ prepend focus context if exists (concept/asset/spec_point)
  │
  ▼
POST http://localhost:8000/api/tutor
  Body: { student_prompt, history: [{role, content}] }
  │
  ▼
FastAPI /api/tutor (main.py:216)
  ├─ _retrieve_relevant_chunks(student_prompt)
  │    ├─ _embed_query() → NVIDIA NV-EmbedQA-E5-V5 (1024-dim)
  │    ├─ _vector_to_pg_str() → pgvector literal
  │    └─ POST Supabase RPC match_resource_chunks
  │         ⚠ filter_resource_id = TARGET_RESOURCE_ID (HARDCODED)
  │              = "5729d034-a6c7-4f35-b81c-fcac447289c7"
  │
  ├─ _format_chunks_as_context(chunks)
  │    └─ Build citation-rich context block
  │
  ├─ evaluate_routing(student_prompt)
  │    ├─ complex keywords or len > 100 → NVIDIA Llama 3.3 70b
  │    └─ simple/conversational → Gemini 2.5 Flash
  │
  ▼
LLM Response
  ├─ Extract sources from chunks → TutorSource[]
  ├─ Strip [SWITCH_TAB:TabName] tag if present
  │
  ▼
TutorResponse { response, model_used, sources }
  │
  ▼
InteractiveTutor setMessages([...prev, {role:'ai', text, modelUsed, sources}])
  ├─ Render ReactMarkdown (line 375)
  ├─ Render citation chips (lines 380-395)
  └─ Render model badge (lines 396-400)
```

### ⚠ RAG Scope Bug (Bug #6 below)
The backend RAG retrieval is **hardcoded** to `TARGET_RESOURCE_ID = "5729d034-..."` (main.py:78, 106). The frontend sends the student's question from whatever chapter the student is viewing, but the backend ALWAYS retrieves chunks from the "Forces and Motion" resource only. If the student is in Chapter 1 (TRP), the tutor still grounds its answers in Forces and Motion data.

---

## 5. ASSET RENDERING DIAGRAM

```
Supabase Storage: resource-assets bucket (public)
  └─ {resource_id}/original.pdf       ← PDF source
  └─ {resource_id}/page{N}_{type}_{i}.png  ← extracted assets

PDF Flow:
  HybridDocumentViewer useEffect[resourceId] (line 233)
    └─ pdfUrl = `${VITE_SUPABASE_URL}/storage/v1/object/public/resource-assets/${resourceId}/original.pdf`
    └─ <iframe src={pdfUrl} sandbox="allow-scripts allow-same-origin"/>
    │
    ▼
  Browser → GET pdfUrl → Supabase Storage → 200 OK → renders PDF

Asset Flow:
  HybridDocumentViewer useEffect[resourceId] (line 257)
    └─ Promise.all:
         ├─ supabase.from('resources').select('content,title,content_markdown').eq('id',resourceId)
         └─ supabase.from('resource_assets').select('*').eq('resource_id',resourceId).order('page_number')
    │
    ▼
  setData(resourceRes.data)     ← resource content (concepts, formulae)
  setAssets(assetsRes.data)     ← array of asset objects with storage_url
  │
  ▼
  Document mode:
    └─ <AssetCard asset={asset}/> for each asset
         └─ <img src={asset.storage_url} onLoad onError retry/>

  Interactive mode:
    └─ <button> with <img src={asset.storage_url}/> (smaller grid)
```

### Asset Flow Status: CORRECT
The asset rendering pipeline works. Assets fetch from Supabase Storage, render as `<img>` elements, and include error/retry handling. The PDF iframe also works (verified by Playwright check 3).

---

## 6. ROOT CAUSE ANALYSIS

### Root Cause #1 (HIGH): Dual tab systems with no sync
**What:** Two independent tab systems control what the user sees:
- System A (`activeTab` in App.jsx): Lesson | Worksheet | Simulation | Quiz
- System B (`viewMode` in HybridDocumentViewer): document | interactive

**Why it breaks:** The default `activeTab` is `'Lesson'` (App.jsx:62). The Lesson tab renders **a placeholder** (InteractiveTutor.jsx:302-317). The HybridDocumentViewer — which contains all the worksheet content — only mounts when `activeTab === 'Worksheet'` (line 274). No code ever sets `activeTab` to `'Worksheet'` automatically.

**User experience:** Student clicks a chapter → sees a grey placeholder → concludes "worksheet not rendering". They must discover the `Worksheet` tab on their own.

**Evidence:**
- App.jsx:62 — `useState('Lesson')` (default)
- InteractiveTutor.jsx:274 — `activeTab === 'Worksheet' ?` (only path to HybridDocumentViewer)
- InteractiveTutor.jsx:302-317 — placeholder renders for Lesson/Simulation
- No useEffect, no auto-navigation, no derived state sets activeTab to 'Worksheet'

### Root Cause #2 (HIGH): specPoints fetched but never rendered
**What:** InteractiveTutor fetches specification_points for the chapter (line 49-69) and stores them in `specPoints` state. This array is **never used in the render output**. ESLint confirms: `'specPoints' is assigned a value but never used` (InteractiveTutor.jsx:32).

**Why it breaks:** The code auto-selects `data[0].id` as `activeSpecPointId` (line 62) — always the FIRST spec point. The user has no UI to switch between spec points. If the chapter's first spec point has no resource in the `resources` table, `worksheetResource` stays `null`, and HybridDocumentViewer renders with `resourceId={undefined}` → the "No resource selected" error state (HybridDocumentViewer.jsx:258-262).

**Evidence:**
- InteractiveTutor.jsx:32 — `const [specPoints, setSpecPoints] = useState([])`
- InteractiveTutor.jsx:62 — `setActiveSpecPointId(data[0].id)` (always first)
- No `specPoints.map()` anywhere in the render output (confirmed by search)
- ESLint unused-vars error on line 32

### Root Cause #3 (MEDIUM): RAG retrieval hardcoded to single resource
**What:** The backend `/api/tutor` endpoint retrieves RAG context using `TARGET_RESOURCE_ID = "5729d034-a6c7-4f35-b81c-fcac447289c7"` (main.py:78, 106). This is the Forces and Motion resource specifically.

**Why it breaks:** When a student is in a different chapter and asks the tutor a question, the tutor grounds its answer in Forces and Motion data — not the chapter the student is viewing. The answer may reference concepts/pages that don't match the worksheet on screen.

**Evidence:**
- main.py:78 — `TARGET_RESOURCE_ID = "5729d034-..."` (hardcoded)
- main.py:106 — `rpc_body["filter_resource_id"] = TARGET_RESOURCE_ID`
- Frontend sends `student_prompt` only — no `resource_id` param in `/api/tutor` request body
- QuizEngine also hardcodes a fallback: `resource_id: resourceId || "5729d034-..."` (QuizEngine.jsx:56)

### Root Cause #4 (MEDIUM): Resource fetch only triggers on Worksheet tab
**What:** The useEffect that fetches the worksheet resource (InteractiveTutor.jsx:72-109) has a guard: `if (activeTab === 'Worksheet' && activeSpecPointId)`. This means no resource is fetched until the user explicitly clicks the Worksheet tab.

**Why it breaks:** Combined with Root Cause #1, this creates a chicken-and-egg problem. The worksheet never pre-loads. If the tutor sends a `[SWITCH_TAB: Worksheet]` tag, the resource fetch finally triggers — but only after the user has already been confused by the placeholder.

**Evidence:** InteractiveTutor.jsx:74 — `if (activeTab === 'Worksheet' && activeSpecPointId)`

---

## 7. EVIDENCE CHAIN

| # | Finding | File:Line | Code Evidence | Severity |
|---|---------|-----------|---------------|----------|
| E1 | Default tab renders placeholder, not worksheet | App.jsx:62 | `useState('Lesson')` | HIGH |
| E2 | Worksheet only mounts on explicit tab click | InteractiveTutor.jsx:274 | `activeTab === 'Worksheet' ?` | HIGH |
| E3 | specPoints state fetched but never rendered | InteractiveTutor.jsx:32 | ESLint: `specPoints is assigned but never used` | HIGH |
| E4 | Only first spec point auto-selected, no UI to change | InteractiveTutor.jsx:62 | `setActiveSpecPointId(data[0].id)` | MEDIUM |
| E5 | Dual tab systems (activeTab vs viewMode) unsynchronized | InteractiveTutor.jsx:243 + HybridDocumentViewer.jsx:221 | Two independent useState for tabs | MEDIUM |
| E6 | RAG retrieval hardcoded to Forces and Motion | main.py:78,106 | `TARGET_RESOURCE_ID = "5729d034-..."` | MEDIUM |
| E7 | Resource fetch gated behind Worksheet tab | InteractiveTutor.jsx:74 | `if (activeTab === 'Worksheet' && activeSpecPointId)` | MEDIUM |
| E8 | SearchPanel onNavigate only sets concept focus, no scroll | InteractiveTutor.jsx:288-293 | `setFocus({concept})` only | LOW |
| E9 | "Simulation" tab renders placeholder | InteractiveTutor.jsx:302-317 | `else` branch = placeholder | LOW |
| E10 | Backend URLs hardcoded to localhost:8000 | InteractiveTutor.jsx:148, SearchPanel.jsx:52, QuizEngine.jsx:22,63 | `fetch('http://localhost:8000/...')` | MEDIUM |
| E11 | Express server.js port 5000 is dead code | server.js:39 | `/api/chat` not called by any frontend component | LOW |
| E12 | `Square` icon imported but never used | InteractiveTutor.jsx:3 | Import includes `Square`, no usage | LOW |

---

## 8. LIST OF BUGS (ranked by severity)

### SEV-1 (High — blocks core user flow)

**BUG-1: Worksheet not visible by default**
- Severity: HIGH
- File: App.jsx:62, InteractiveTutor.jsx:274, 302-317
- Default tab is 'Lesson'. Lesson renders a placeholder. Worksheet content (HybridDocumentViewer) only mounts when user clicks 'Worksheet' tab. No auto-navigation.
- User impact: Student clicks a chapter → sees grey placeholder → reports "worksheet not rendering"
- Evidence: `useState('Lesson')` at App.jsx:62, `activeTab === 'Worksheet' ?` gate at line 274

**BUG-2: No specification point selector UI**
- Severity: HIGH
- File: InteractiveTutor.jsx:32, 62
- `specPoints` array is fetched but never rendered. Only `data[0].id` is auto-selected. ESLint confirms unused state.
- User impact: If chapter's first spec point has no linked resource, worksheetResource stays null → HybridDocumentViewer shows "No resource selected" error (line 258-262).
- Evidence: ESLint error `'specPoints' is assigned a value but never used`

### SEV-2 (Medium — incorrect behavior, workarounds exist)

**BUG-3: RAG tutor retrieves from wrong resource**
- Severity: MEDIUM
- File: backend/main.py:78, 106
- `TARGET_RESOURCE_ID` hardcoded to Forces and Motion. Tutor always grounds answers in this resource regardless of which chapter the student is viewing.
- User impact: Tutor answers reference wrong concepts/pages for non-Forces chapters
- Evidence: `filter_resource_id = TARGET_RESOURCE_ID` (no dynamic resource scoping)

**BUG-4: Resource fetch only triggers on Worksheet tab**
- Severity: MEDIUM
- File: InteractiveTutor.jsx:74
- `if (activeTab === 'Worksheet' && activeSpecPointId)` guards the Supabase resource fetch
- User impact: No pre-loading. Combined with BUG-1, worksheet appears empty until correct tab clicked
- Evidence: line 74 guard condition

**BUG-5: Dual tab systems unsynchronized**
- Severity: MEDIUM
- File: InteractiveTutor.jsx:243, HybridDocumentViewer.jsx:221
- `activeTab` (Lesson/Worksheet/Simulation/Quiz) and `viewMode` (document/interactive) are independent. The AI tutor `[SWITCH_TAB:]` tag only talks to `activeTab`. If tutor switches to Worksheet, the HDV defaults to `document` mode — user must still click "Interactive Tutor" inside HDV to see concept cards.
- User impact: Confusion. Two layers of tabs for what feels like one action.
- Evidence: Two separate `useState` declarations, no cross-component sync

**BUG-6: Backend URLs hardcoded to localhost:8000**
- Severity: MEDIUM
- File: InteractiveTutor.jsx:148, SearchPanel.jsx:52, QuizEngine.jsx:22,63
- All fetch calls use `'http://localhost:8000/...'` string literals
- User impact: Breaks in any non-local deployment
- Evidence: 4 hardcoded URL references (confirmed by search)

### SEV-3 (Low — cosmetic, dead code, minor UX)

**BUG-7: SearchPanel navigation doesn't scroll to concept**
- Severity: LOW
- File: InteractiveTutor.jsx:288-293
- `onNavigate` sets `focus` with concept name but doesn't scroll HybridDocumentViewer to the matching concept card. The card highlights (line 522-534) but may be off-screen.
- User impact: Search result click sets a chip but nothing visibly scrolls

**BUG-8: Express server.js is dead code**
- Severity: LOW
- File: backend/server.js (entire file)
- The `/api/chat` endpoint on port 5000 is never called by the frontend. FastAPI on port 8000 has replaced it entirely.
- User impact: Confusion, dual maintenance, unnecessary process

**BUG-9: `Square` and `motion` imported but unused**
- Severity: LOW
- Files: InteractiveTutor.jsx:3, HybridDocumentViewer.jsx:3
- ESLint flags: `Square` (InteractiveTutor), `motion` (HybridDocumentViewer — note: `motion` IS used from framer-motion, this is a false positive from the local import name)
- User impact: None (code cleanliness)

---

## 9. LIST OF TECHNICAL DEBT

| # | Debt Item | File | Impact |
|---|-----------|------|--------|
| TD-1 | No spec-point selector UI | InteractiveTutor.jsx | Students can't switch spec points |
| TD-2 | RAG hardcoded to single resource | main.py:78 | Tutor can't serve non-Forces chapters |
| TD-3 | Hardcoded localhost:8000 URLs | 4 files | Deployment blocker |
| TD-4 | Dead Express server | server.js | Maintenance overhead |
| TD-5 | No loading state for worksheetResource fetch | InteractiveTutor.jsx | User sees blank then content pops in |
| TD-6 | ESLint config missing react/jsx-no-undef | eslint.config.js | JSX undefined identifiers reach runtime (caused BUG in prior report) |
| TD-7 | `isFetchingResource` state set but never rendered | InteractiveTutor.jsx:35 | No spinner/feedback during fetch |
| TD-8 | `activeSpecPointId` passed to QuizEngine but never used | QuizEngine.jsx:8 | Dead prop |
| TD-9 | `VLEDashboard` receives `session` prop but never uses it | VLEDashboard.jsx:16 | Dead prop |
| TD-10 | No chunking / code splitting (1.1MB bundle) | vite.config.js | Slow initial load |

---

## 10. RECOMMENDED FIX ORDER

**These are recommendations ONLY. No fixes have been applied in this investigation.**

### Phase 1: Unblock the worksheet (2 changes)

1. **Change default tab to 'Worksheet'** — App.jsx:62
   `useState('Lesson')` → `useState('Worksheet')`
   Rationale: The worksheet is the primary content. Defaulting to it removes the "worksheet not rendering" complaint instantly.

2. **Pre-fetch resource regardless of tab** — InteractiveTutor.jsx:74
   Remove the `activeTab === 'Worksheet'` guard from the resource fetch effect.
   Rationale: Pre-loading the resource eliminates the empty-state flash when switching tabs.

### Phase 2: Fix RAG scope (1 change)

3. **Pass resource_id to /api/tutor** — InteractiveTutor.jsx:148-157 + main.py
   Add `resource_id: worksheetResource?.id` to the POST body. Update `_retrieve_relevant_chunks` to accept and use it instead of `TARGET_RESOURCE_ID`.
   Rationale: Tutor answers must match the chapter the student is viewing.

### Phase 3: Add spec-point selector (1 change)

4. **Render specPoints as a dropdown/list** — InteractiveTutor.jsx
   Add a `<select>` or pill-list that maps over `specPoints` and calls `setActiveSpecPointId`.
   Rationale: Students need to browse all spec points in a chapter, not just the first one.

### Phase 4: Clean up (optional, no user-facing impact)

5. Extract backend URLs to env var
6. Remove or archive `server.js`
7. Remove unused imports (`Square`, `isFetchingResource`)
8. Add `eslint-plugin-react` with `react/jsx-no-undef: error`

---

## 11. ACCEPTANCE TESTS

After fixes are applied, these tests MUST pass:

### Rendering Tests
- [ ] AT-1: User clicks a chapter → Worksheet renders immediately (no placeholder)
- [ ] AT-2: PDF iframe is visible and loads (HTTP 200) on chapter open
- [ ] AT-3: Asset images visible and decode successfully (naturalWidth > 0)
- [ ] AT-4: Concept cards visible when viewMode = 'interactive'
- [ ] AT-5: ConceptPopup opens on concept card click
- [ ] AT-6: No "No resource selected" error for chapters with resources
- [ ] AT-7: No "Failed to load asset" retry state visible

### Tab Tests
- [ ] AT-8: Default tab is 'Worksheet' (not 'Lesson')
- [ ] AT-9: Clicking 'Lesson' shows placeholder (expected)
- [ ] AT-10: Clicking 'Quiz' shows QuizEngine
- [ ] AT-11: Clicking 'Worksheet' after visiting 'Quiz' shows worksheet immediately (pre-loaded)
- [ ] AT-12: viewMode toggle (Document/Interactive) works within Worksheet tab

### Spec Point Tests
- [ ] AT-13: Spec points selector is visible in the Worksheet tab
- [ ] AT-14: Selecting a different spec point fetches its resource
- [ ] AT-15: Selecting a spec point with no resource shows a graceful empty state

### Search Tests
- [ ] AT-16: Search button visible on Worksheet tab
- [ ] AT-17: Search toggle opens SearchPanel
- [ ] AT-18: Typing 'velocity' + Enter returns results
- [ ] AT-19: Clicking a search result sets focus context chip
- [ ] AT-20: Clicking a search result highlights the concept card in HDV

### Tutor Tests
- [ ] AT-21: Sending a message does NOT crash (no ReferenceError)
- [ ] AT-22: User avatar renders (no missing `User` icon)
- [ ] AT-23: AI response renders with markdown + LaTeX
- [ ] AT-24: Citation chips render under AI message
- [ ] AT-25: RAG sources match the CURRENT chapter's resource (not always Forces and Motion)
- [ ] AT-26: `[SWITCH_TAB:]` tag correctly switches activeTab

### Sync Tests
- [ ] AT-27: Clicking a concept card sets focus → context chip appears in chat input
- [ ] AT-28: Clicking an asset card sets focus → context chip appears
- [ ] AT-29: Focus is consumed after sending a tutor message
- [ ] AT-30: Focus can be manually cleared (✕ button)

### Network / Error Tests
- [ ] AT-31: No JS errors in console (non-benign)
- [ ] AT-32: No failed network requests (non-benign)
- [ ] AT-33: No CORS errors
- [ ] AT-34: No 404/500 on /api/tutor
- [ ] AT-35: No 404/500 on /api/search/hybrid

### Existing Playwright Regression Suite
- [ ] AT-36: All 10 checks + 4 sync tests in `frontend/tests/regression.spec.js` pass

---

## CONSISTENCY CHECK (multi-agent cross-validation)

All 7 specialist lenses agree on the following:
1. The User import crash is FIXED — no longer the root cause
2. The routing, component boundaries, and data flow wiring are CORRECT
3. The PDF and asset rendering chains work end-to-end
4. The SEARCH panel is correctly implemented but hidden behind two gates (Worksheet tab + explicit toggle)
5. The RAG backend is functionally correct but scoped to the wrong resource
6. The dominant user-facing failure is the 'Lesson' default tab showing a placeholder
7. The spec-point selector is the missing UI that makes multi-spec chapters partially broken

No contradictions found between agent findings.

---

## TRIGGER vs ROOT CAUSE (post-mortem discipline)

**Trigger (proximate):** The default `activeTab` is 'Lesson', which renders a placeholder. The worksheet is gated behind an explicit 'Worksheet' tab click.

**Root cause (systemic):** Two tab systems were designed independently — `activeTab` (app-level navigation) and `viewMode` (component-level view switching). No one reconciled their defaults: `activeTab` defaults to the only tab that has no real content ('Lesson'), and `viewMode` defaults correctly to 'document'. The user's journey requires crossing both tab boundaries to reach the worksheet, with no signposting.

**Why prior investigation missed it:** The prior investigation found a crash-level bug (missing `User` import) that masked everything. Once that crash was fixed, the state-synchronization design flaw became the dominant symptom. The prior report correctly identified the Search panel's discoverability as a "secondary UX issue" but did not flag the default-tab problem as a separate root cause.

---

**Investigation complete. No fixes applied. All findings are evidence-based and internally consistent.**
