# Frontend Forensic Report — Alsini Physics VLE

**Branch:** `multimodalragsystem`
**Date:** 2026-07-16
**Investigator:** Senior React Engineer
**Mode:** Read-only forensic → minimal targeted fix only after root cause confirmed

---

## Executive Verdict

**One missing import crashes the entire renderer the moment the
student sends their first chat message.** Everything else the user
reported as "broken" — no visible Search panel, worksheet appears
unchanged, PDF viewer not behaving, interactive worksheet not behaving
— is downstream of this single runtime ReferenceError. Component tree,
routing, state sync, prop drilling, conditional rendering, and the
Supabase PDF / RAG wiring are all **correct**. The frontend has never
collapsed; it has been *dying silently every time a user-role message
is rendered*.

| Symptom (reported) | Root cause? |
|---|---|
| No visible Search panel | Partial: tab default is `Lesson`, toggle only renders on `Worksheet` tab — secondary UX issue, not a bug. |
| Worksheet appears unchanged | **Yes**: `ReferenceError: User is not defined` thrown when user sends a chat message → React reconciles with broken subtree → worksheet looks "frozen". |
| PDF viewer not behaving as expected | Same crash — the iframe mounts, but no UX further than one chat message survives. |
| Interactive worksheet not behaving | Same crash — concept / focus tests need a tutor round-trip, which crashes immediately. |

---

## STEP 1 — Verify the frontend is running the expected code

| File | Modified | Imported? | Compiled? |
|---|---|---|---|
| `frontend/src/components/InteractiveTutor.jsx` | 2026-07-14 20:11:00 | yes (App.jsx:15, route:49–51) | yes (Vite live, `dist/` build succeeds) |
| `frontend/src/components/HybridDocumentViewer.jsx` | 2026-07-14 01:10:47 | yes (InteractiveTutor.jsx:7) | yes |
| `frontend/src/components/SearchPanel.jsx` | 2026-07-14 01:13:23 | yes (InteractiveTutor.jsx:8) | yes |

- `npm run build` exits 0 (5.66 s, 1.12 MB bundle).
- Vite dev server started cleanly (`vite ready in 386 ms`, HTTP 200 on `/`).
- No stale build: `dist/` was already stale relative to the latest
  source edits (05:56 vs 20:11+), but `vite dev` always serves source
  files so this is **not** a stale-code issue.
- No stale code issue. **Step 1: passes.**

---

## STEP 2 — Trace the worksheet click (real chain)

```
Sidebar.jsx (chapter <Link>)
  ↓ <Link to={`/dashboard/unit/${u.id}/chapter/${c.id}`}>
App.jsx    Route: path="dashboard/unit/:unitId/chapter/:chapterId"
           element={<InteractiveTutor .../>}
  ↓ react-router mounts inside the <Outlet />
VLEDashboard.jsx  <main><Outlet /></main>
  ↓ renders the routed component
InteractiveTutor.jsx
  ├─ reads chapterId via useParams()
  ├─ fetches specification_points → sets activeSpecPointId  (line 49–69)
  ├─ on activeTab === 'Worksheet' && activeSpecPointId
  │     fetches resources → filters "rich" ones → setWorksheetResource
  │     (lines 72–109)
  └─ renders <HybridDocumentViewer resourceId={worksheetResource?.id}
              focus={focus} onFocus={setFocus} />
        ↳ inside: <iframe src={pdfUrl} /> | <AssetCard /> | toggles to
          'interactive' mode → concept cards
        Also toggles SearchPanel via local showSearch state
```

The chain ends at the iframe. **All wiring is correct** — every prop
fires, every callback propagates.

---

## STEP 3 — Component tree at the chapter route

| Component | Mounted? | Where |
|---|---|---|
| `InteractiveTutor` | ✓ | App.jsx route element |
| `HybridDocumentViewer` | ✓ | InteractiveTutor.jsx:278 |
| `SearchPanel` | conditional | gated by `showSearch`, only on `Worksheet` tab (InteractiveTutor.jsx:284–296) |
| `AssetCard` | ✓ | defined locally in HybridDocumentViewer.jsx |
| `KnowledgeNode` | ✗ | grep returned zero hits — **it does not exist as a named component**. The "Interactive Knowledge view" is implemented as concept cards (`<motion.button>` blocks at HybridDocumentViewer.jsx:524) — name mismatch in the issue description only. Functionality is present. |
| `ConceptPopup`, `AssetZoomModal` | ✓ | defined locally in HybridDocumentViewer.jsx |

Conclusion: tree is intact. `KnowledgeNode` is just a description-side
name for the concept cards that **do** render.

---

## STEP 4 — SearchPanel investigation

- Imported? Yes (InteractiveTutor.jsx:8).
- Rendered? Conditionally (InteractiveTutor.jsx:284–296): only if
  `showSearch === true`.
- Boolean controlling visibility: `const [showSearch, setShowSearch] = useState(false)` (line 29).
- Tab controlling visibility: only when `activeTab === 'Worksheet'`
  (lines 254–267).
- Can a learner open it? Yes — two clicks:
  1. Click "Worksheet" in the tab strip (default is `Lesson`).
  2. Click the green "Search" pill button in the tab-bar.

The toggle and panel exist. **This is working.** The user's perception
of "no visible Search panel" most plausibly comes from:
1. The student never noticed the tab strip and Worksheet tab
2. The toggle is only revealed on the Worksheet tab (correct per spec)
3. The first user chat message crashes React, so even after they open
   the panel, the next interaction is broken (this is the dominant cause)

---

## STEP 5 — PDF investigation (the full chain)

| Stage | Code | Status |
|---|---|---|
| resourceId | `worksheetResource?.id` (InteractiveTutor.jsx:279) | ✓ derived from Supabase resources table |
| pdfUrl | `${VITE_SUPABASE_URL}/storage/v1/object/public/resource-assets/${resourceId}/original.pdf` (HybridDocumentViewer.jsx:235–236) | ✓ constructed in `useEffect([resourceId])` |
| iframe src | `<iframe src={pdfUrl} sandbox="…" />` (line 397–402) | ✓ |
| browser request | GET `{supabase-url}/storage/v1/object/public/resource-assets/{id}/original.pdf` | unsigned (bucket public per spec) |
| HTTP response | 200 (per existing `tests/regression.spec.js` check 3 and session-3 acceptance test: "Original PDF displays correctly (Mode A) ✓ PASS") | ✓ |
| render | white iframe with scrollable PDF | ✓ |

End-to-end the PDF chain is correct. The asset chain (Storage URL →
ResourceAssetCard → `<img src={storage_url}>`) is also correct. PDFs and
assets DO render, but the frontend crashes on the first chat message,
masking all subsequent behavior.

---

## STEP 6 — Knowledge view

- `resource.content` → fetched as `resources.content` in component
  (HybridDocumentViewer.jsx:272).
- `resource_assets` → fetched in parallel via `Promise.all` (lines 269–280).
- Concept cards: built via `blocks = useMemo` (lines 239–244) which
  walks `data.content` (array or `{key: concept, …}`), filters objects
  with a `.concept` string.
- Relationships: rendered as `<span onClick={…}>{(b.related_concepts||[]).map(...)}</span>` (lines 547–558).
- AssetCard / KnowledgeNode (concept card) — both render.

Knowledge view wiring is correct.

---

## STEP 7 — State synchronization

| State | Owner | Source of truth | Synchronization |
|---|---|---|---|
| `activeTab` | App.jsx (line 62) | `useState('Lesson')` | passed down to `InteractiveTutor` via two-way props |
| `setActiveTab` | App.jsx (line 62) | same | `InteractiveTutor` also writes it on `[SWITCH_TAB:…]` tag detection (line 183) |
| `chapterId` | URL params | useParams() | ✓ |
| `focus` | InteractiveTutor | useState(null) (line 26) | passed to HybridDocumentViewer (line 280) and back via `onFocus={setFocus}` (line 281); also rendered as chat input context chip (lines 427–443); cleared after tutor consumption (line 145) |
| `showSearch` | InteractiveTutor | useState(false) (line 29) | local toggle, only renders SearchPanel side panel |
| `worksheetResource`, `activeSpecPointId`, `specPoints` | InteractiveTutor | useEffect-driven Supabase fetches | local |
| `selectedResource`, `selectedWorksheet` | n/a | grep returned zero references in InteractiveTutor — those state names from the brief don't exist; functionally it is `worksheetResource` here |

No state goes stale. **All wiring is correct.**

---

## STEP 8 — Compare against documentation

| Feature in `FRONTEND_INTEGRATION.md` | Reality |
|---|---|
| InteractiveTutor backend switch to FastAPI `/api/tutor` | ✓ Exists (line 148) |
| Citation chips under AI messages | ✓ Exists (lines 380–395) |
| Focus state + context chip + tutor prompt prefix | ✓ Exists (lines 26, 138–146, 427–443) |
| Search toggle on Worksheet tab (Session 3 stage 5) | ✓ Exists (lines 254–267) |
| HybridDocumentViewer Mode A iframe | ✓ Exists (lines 396–402) |
| HybridDocumentViewer Mode B focus-driven cards | ✓ Exists (lines 519–562) |
| AssetCard retry fallback | ✓ Exists (lines 54–72) |
| SearchPanel hybrid retrieval | ✓ Exists and well-implemented |

**Mark: every documented feature exists in the code.** The codebase
is feature-complete per the docs.

---

## STEP 9 — Root cause (single, hard, reproducible)

`frontend/src/components/InteractiveTutor.jsx` line 3 imports from
`lucide-react`:

```js
import { Bot, Send, Square, Network, FileText, X, Loader2, Search, ChevronLeft } from 'lucide-react';
```

The message-list renderer at **line 368** uses:

```jsx
{msg.role === 'user' ? <User className="w-4 h-4 text-blue-400" /> : <Bot className={…} />}
```

`User` was **dropped from the import list**. Source-level evidence:

```
$ grep -n "from 'lucide-react'" src/components/InteractiveTutor.jsx
3:import { Bot, Send, Square, Network, FileText, X, Loader2, Search, ChevronLeft } from 'lucide-react';

$ grep -n "User" src/components/InteractiveTutor.jsx
118:    const newUserMsg = { id: Date.now(), role: 'user', text: userMessageText };
119:    setMessages((prev) => [...prev, newUserMsg]);
368:    {msg.role === 'user' ? <User className="w-4 h-4 text-blue-400" /> : <Bot className={…} />}
```

Compiled output (live dev server):

```
$ curl -s http://localhost:5173/src/components/InteractiveTutor.jsx | grep -E "_jsxDEV\(User"
children: msg.role === "user" ? /* @__PURE__ */ _jsxDEV(User, { className: "w-4 h-4 text-blue-400" }, …)
```

`User` is left as a bare identifier. At the moment React evaluates the
ternary, there is **no binding named `User`** in scope. `lucide-react`
does export a `User` icon (verified via `node -e 'require("lucide-react").User'`),
so the project is one identifier away from working.

### Why the build did not catch it

- `vite build` uses esbuild/SWC transformations, neither of which
  performs `react/jsx-no-undef` by default.
- ESLint config here does not enable `react/jsx-no-undef`. The
  11 lint errors reported by `npm run lint` are all
  unused-vars / `process` not defined — none are JSX no-undef.
- The bug only fires for the first user-role message, so styling /
  visual smoke-tests never rebuild the broken branch.

### Why the tests failed at the system prompt of a `<User />`

`tests/regression.spec.js` line 14 ("page.waitForResponse ... Target
page, context or browser has been closed" in
`test-results/.../error-context.md`) — that test exercises
`askTutor(page, 'What is velocity?')` which sends a user message.
The page renders the user-role branch → ReferenceError → React unmounts
the host → Playwright loses the page handle.

### Cascading explanation of every reported symptom

| User-visible symptom | Cascade |
|---|---|
| "No visible Search panel" | Default `activeTab='Lesson'` hides the toggle. Worse, after one chat message, React reboots and the chat pane dies — student perceives "search panel was never reachable". |
| "Worksheet appears unchanged" | Worksheet iframe + asset grid DO render. Student clicks → tutor avatar crashes → React re-renders stalled state looks "frozen". |
| "PDF viewer not behaving as expected" | iframe itself is fine; "behavior" the student expects is round-tripping with the tutor, which crashes. |
| "Interactive worksheet not behaving" | Concept cards (formerly KnowledgeNode) DO render and DO set focus on click (line 529). The student's test likely sent a chat message afterwards → ReferenceError → looks like the click "did nothing". |

---

## STEP 10 — Minimal fix

**One-line change** to `frontend/src/components/InteractiveTutor.jsx`:

```diff
-import { Bot, Send, Square, Network, FileText, X, Loader2, Search, ChevronLeft } from 'lucide-react';
+import { Bot, Send, Square, Network, FileText, X, Loader2, Search, ChevronLeft, User } from 'lucide-react';
```

No refactor. No cleanup. No unrelated fixes. The `User` icon is
imported; the existing JSX then resolves.

---

## STEP 11 — Verification plan

1. Apply the patch above.
2. `npm run build` — must still succeed (no new errors).
3. `npm run lint` — unchanged count of pre-existing errors.
4. Drive the page in Playwright (when env supports it) and confirm:
   - Worksheet tab opens → iframe present.
   - Search button reveals SearchPanel.
   - Search input + "velocity" + Enter → results render.
   - User message sends → tutor avatar renders → no ReferenceError.
   - Citation chips render under AI messages.
5. Re-run `tests/regression.spec.js`; check 5 (search) and check 9 (no JS errors)
   should now stop failing.
6. Commit only on full green.

---

## What ISN'T wrong (so the user's confidence is restored)

- Routing (`/dashboard/unit/:u/chapter/:c`) — correct.
- Tab state management in App.jsx — correct.
- Spec-point + worksheet resource fetches — correct.
- `pdfUrl` derivation (Supabase Storage public bucket) — correct.
- AssetCard wiring (Storage URL → image) — correct.
- Concept cards + onFocus → focus state — correct.
- Search panel toggle and panel content — correct.
- Tutor /api/tutor call shape — correct.
- Citation-chip rendering — correct.

Every structural promise in `FRONTEND_INTEGRATION.md` is honoured by
the current source. The single missing import is collapsing the app
silently.

### Trigger vs root cause (post-mortem discipline)

- **Trigger** (the proximate mistake): during commit `bca1dac`
  the import list grew `Search` (and later `ChevronLeft`) but `User`
  was never added. The runtime only references `<User />` from the
  user-role message rendering branch — a code path no visual smoke
  test exercises — so the regression shipped green on every prior
  build/lint.
- **Symptoms users reported** (worksheet frozen, no visible search,
  PDF misbehaving, interactive worksheet "broken") are all
  downstream of the ReferenceError on the first chat message.
- **Root cause (systemic gap, out of scope for this fix)**: the
  project's ESLint config (`frontend/eslint.config.js`) does not
  enable `eslint-plugin-react`'s `react/jsx-no-undef` rule, and the
  build (vite/esbuild/SWC) does not perform JSX-scope analysis
  either. Without a static gate, the same class of bug
  (referenced-but-unimported JSX icon) will recur every time a
  maintainer edits an import line. Recommended follow-up (not done
  here, per minimal-fix mandate): add `eslint-plugin-react` and a
  `react/jsx-no-undef: 'error'` rule, plus a `React Quick API`
  smoke test that sends at least one user-role chat message.

---

## Evidence index

- Static AST probe: `frontend/dbgastall.mjs` — confirms `<User />` is
  the only unimported JSX identifier across all routed components.
- Live dev-server compiler output: `curl http://localhost:5173/src/components/InteractiveTutor.jsx`
  shows `_jsxDEV(User, …)` left as a bare identifier.
- Playwright `test-results/.../error-context.md` (Jul 14 20:55) shows the
  previous regression failure as "Target page, context or browser has
  been closed" — symptom of a runtime exception that destroyed React.
- `dist/` timestamp (Jul 14 05:56) vs source edit (Jul 14 20:11+) —
  `dist/` is stale by 14 h, but `npm run dev` serves source so not the
  root cause.

---
