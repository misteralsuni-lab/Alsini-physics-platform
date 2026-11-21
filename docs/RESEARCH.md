# Read-Only Codebase, Branch & Deployment Audit

**Repository:** `misteralsuni-lab/Alsini-physics-platform`  
**Local root:** `/mnt/d/Alsini-physics-platform` (`d:/Alsini-physics-platform`)  
**Audit date:** 2026-11-21  
**Audit branch:** `multimodalragsystem`  
**Audit HEAD:** `04b90f4895908450865293c8f94ac733f10c232f`  
**Source-equivalent remote HEAD:** `origin/multimodalragsystem` = `83af05d585a80ec83126a599dfd5970c650e69a9`  
**Remote default:** `origin/main` = `6090fa192f1992645ba1c8ed5be11c80a5ff81c7`  
**Mode:** read-only. No application source, dependency manifest/lockfile, database schema, or `.env` file was changed. Build output and dependency installation were redirected outside the repository (see §4.5).

> This report replaced the untracked task brief at the same path, as requested. It is the only intentional repository write. It contains no secret values.

---

## Executive Verdict

**The current application source is the most complete worksheet/RAG vertical slice in the repository, but it is not release-ready.** The frontend builds, and the FastAPI app installs and boots in a clean Python 3.11 environment, but:

1. `multimodalragsystem` is an **unrelated orphan history** to `main`, not an ahead/behind branch.
2. The local branch HEAD `04b90f4` contains **only a compiled `.pyc` update** over the publishable source commit `83af05d`.
3. Frontend lint fails with **9 errors**, and the checked-in Playwright suite is **stale** (asserts fields/UI labels that no longer exist) and is missing its browser, auth state, and credentials.
4. No deployment configuration exists: no `vercel.json`, `render.yaml`, `Dockerfile`, `Procfile`, `runtime.txt`, or `pyproject.toml`.
5. The checked-in SQL is not a complete fresh-database migration: base tables have no RLS/content column in `scratch/mig_1_tables.sql`, while the app selects `resources.content`.
6. The only simulation surface is the **`Simulation` tab placeholder**. There is no Three.js dependency, no `HookesLaw.jsx`, and no `simulation_state` in the tutor contract.
7. A committed E2E test-account credential pair remains in `docs/gemini.md:151` and must be rotated/removed.
8. Render 512 MB compatibility is **plausible**: the API loads no local ML models; idle RSS measured ~107.5 MiB. This does not make the current repository deployable.

**Recommendation:** **NO-GO for production** in the current state. **CONDITIONAL GO for staging/manual QA** after the P0 items in §5.9 are addressed and the release commit is chosen explicitly.

---

## 1. Git & GitHub Branch Inventory

### 1.1 Audit baseline

The audit was performed on the checked-out branch, not by merging or resetting anything.

```text
Branch:  multimodalragsystem
HEAD:    04b90f4895908450865293c8f94ac733f10c232f
Upstream: none configured
Worktree: clean except ?? docs/RESEARCH.md.md
```

The local HEAD is **one commit ahead** of the remote branch, and that commit changes only tracked bytecode:

```text
04b90f4  build: update compiled Python bytecode for main module
         backend/__pycache__/main.cpython-314.pyc | Bin 58011 -> 62885 bytes
```

`git diff --stat origin/multimodalragsystem..HEAD` reports nothing when `backend/__pycache__` is excluded. The source tree is therefore equivalent to:

```text
origin/multimodalragsystem  83af05d585a80ec83126a599dfd5970c650e69a9
docs: organise handoff reports into docs/, add DESIGN.md,
      marketing strategy and onboarding-video sources
2026-10-20T16:51:04+02:00
```

### 1.2 Commands run

```bash
cd /mnt/d/Alsini-physics-platform
git fetch --all --prune
git branch -a
git branch -vv
git tag -l --format='%(refname:short) %(objectname:short) %(creatordate:iso8601)'
git log --all --graph --oneline --decorate -n 45
git merge-base main multimodalragsystem
git merge-base --is-ancestor <ref> <ref>
git rev-list --left-right --count main...<branch>
git ls-remote --heads origin
git ls-remote --tags origin
git status --porcelain=v2
```

`git fetch --all --prune` succeeded. It deleted two remote-tracking refs that are no longer advertised by `origin`:

```text
- [deleted] origin/jules-16984982520254157577-700be255
- [deleted] origin/jules-18444275450632772586-85575033
```

The commits they pointed to remain in the local object database and are inspected below, but they are **not live remote branches** today.

### 1.3 Local branches

| Branch | HEAD | Date | Upstream / state | Role |
|---|---|---|---|---|
| `main` | `037c8ee9429b5aaabca0f5c2fbecd57652d51d57` | 2026-11-19 | `origin/main`, **ahead 1** | Old application lineage plus a new docs-only `AGENTS.md` / `docs/prd/.gitkeep` commit. Not the current worksheet slice. |
| `multimodalragsystem` | `04b90f4895908450865293c8f94ac733f10c232f` | 2026-11-17 | **none** | Current checkout. Source-equivalent to `83af05d`; local HEAD adds only tracked `.pyc`. |
| `multimodal-rag-system` | `c1292c745e40396907f36091152c59287ddc9509` | 2026-10-16 | `origin/multimodal-rag-system` | Divergent side branch from `6090fa1`; 4 unique commits, including an inline `ErrorBoundary` and onboarding-video work. |
| `nemotron-3-super` | `0b1b65096aefb7fd831023f3fe3cc812f769063a` | 2026-05-02 | none | Fully merged ancestor of `main`; no unique work. |

### 1.4 Remote branches on `origin`

`git ls-remote --heads origin` returned:

| Remote branch | HEAD |
|---|---|
| `refs/heads/main` | `6090fa192f1992645ba1c8ed5be11c80a5ff81c7` |
| `refs/heads/multimodal-rag-system` | `c1292c745e40396907f36091152c59287ddc9509` |
| `refs/heads/multimodalragsystem` | `83af05d585a80ec83126a599dfd5970c650e69a9` |

`origin/HEAD` points at `origin/main`.

The two Jules commits are now **not remote branches**:

| Former remote-tracking ref | Commit | Date | Description |
|---|---|---|---|
| `jules-16984982520254157577-700be255` | `1a5cff199dc5e47f1dceb08662948bdbf89122bc` | 2026-04-15 | “Add tests for frontend components” |
| `jules-18444275450632772586-85575033` | `3bcaddd7c7fc674b25846a495682c8a8fbea02be` | 2026-04-15 | “Sentinel: Fix reverse tabnabbing vulnerability in Button” |

These are abandoned/historical commits, not candidates for deployment.

### 1.5 Tags

```text
v0.4-worksheet-rag  6e929914fba1c879d8767255dff6ce0466f5fbf6  2026-07-18
```

- Tag kind: lightweight commit tag.
- HEAD is **8 commits after** the tag; the deployable source commit `83af05d` is **7 commits after** it.
- It exists on `origin`.
- It is **not on `main`**: `git merge-base --is-ancestor v0.4-worksheet-rag main` exits 1.
- It must not be treated as the current release candidate.

### 1.6 Divergence and ancestry

There is **no merge base** between `main` and `multimodalragsystem`:

```bash
$ git merge-base main multimodalragsystem
$ echo $?
1
```

`git log --all --graph` confirms two separate roots:

- `main` lineage roots: `1a9832a18d53ff57e0c1ffea2d23b34eff6072a2`, `086522530757e9db2025623be5a16460b30a4413`.
- `multimodalragsystem` root: `6395cd0247aa5236156cd35863ce6a09f31377aa` (“Add Supabase integration and ingestion pipeline”).

Symmetric difference (these are **exclusive commit counts**, not ahead/behind figures):

| Comparison | Only on left | Only on right |
|---|---:|---:|
| `main` vs `multimodalragsystem` | 27 | 34 |
| `main` vs `multimodal-rag-system` | 1 | 4 |
| `main` vs `nemotron-3-super` | 4 | 0 |

`origin/main` is the merge base for `multimodal-rag-system`; `main` is one local docs commit ahead of `origin/main`.

`git branch -a --contains v0.4-worksheet-rag` returns only:

```text
multimodalragsystem
remotes/origin/multimodalragsystem
```

### 1.7 Which branch contains the most complete code?

**`multimodalragsystem`, source-equivalent to `origin/multimodalragsystem` at `83af05d585a80ec83126a599dfd5970c650e69a9`.**

Evidence:

- It contains all current Session 4A.1 and 4A.2 worksheet changes, `LearningContext`, canonical citations, focused-asset grounding, route reset/stale-response guards, hybrid retrieval, asset infrastructure, and the current architecture docs.
- `SearchPanel.jsx` exists only on this branch: 226 lines.
- Current backend `main.py` is 1427 lines versus 287 on `main`, `multimodal-rag-system`, and `nemotron-3-super`.
- Current `HybridDocumentViewer.jsx` is 613 lines versus 241 on the older branches.
- Current `InteractiveTutor.jsx` is 718 lines versus 369 on the older branches.
- `main` is the default branch, but its latest commit (`037c8ee`) only adds `AGENTS.md` and `docs/prd/.gitkeep`; it does not contain the current application.
- The local checkout is not tracking the remote; set the upstream only after choosing the release branch.

**Caveat:** “most complete” is a code-inventory judgment, not a production sign-off. The current source builds, but live E2E is stale/blocked and no end-to-end RAG request was executed in this audit.

### 1.8 Unmerged work and consolidation recommendation

Do **not** merge `main` into `multimodalragsystem` with `--allow-unrelated-histories`; that would attempt to reconcile two different roots and would drag old/irrelevant app code into the release. Consolidate selectively:

| Source | Useful unmerged work | Recommendation |
|---|---|---|
| `main` `037c8ee` | `AGENTS.md`, `docs/prd/.gitkeep` (GitHub Issues workflow) | Port as a docs-only commit onto the release branch. |
| `multimodal-rag-system` `38b348f`, `c1292c7` | Inline `ErrorBoundary` in `frontend/src/App.jsx`; consistent min-height layout; onboarding-video sources | Port only the ErrorBoundary/wrapper; current branch already has onboarding-video sources. Re-check the layout diff against the current 718-line tutor before applying anything. |
| `jules-184...` `3bcaddd` | Default `rel="noopener noreferrer"` when `target="_blank"` in `Button.jsx` | Port the small hardening; current `Button.jsx` accepts `rel` but does not enforce it. |
| `jules-169...` `1a5cff1` | Older Vitest/RTL tests | Do not merge wholesale; they target an older tree. Recreate tests against the current exports if test coverage is desired. |
| `nemotron-3-super` `0b1b650` | Historical semantic-routing backend | No action; already an ancestor of `main`. |
| local HEAD `04b90f4` | Tracked `.pyc` update | Discard or stop tracking; do not deploy. |

### 1.9 Worktree and repository hygiene

- Worktree state: only `?? docs/RESEARCH.md.md`. No tracked source changes.
- Current branch has no upstream; `git push` would need `--set-upstream`.
- Tracked generated files exist: `backend/__pycache__/main.cpython-314.pyc`, `backend/__pycache__/master_ingestion.cpython-314.pyc`, `backend/pipeline/__pycache__/asset_extractor.cpython-314.pyc`, `backend/pipeline/__pycache__/storage_uploader.cpython-314.pyc`, `scripts/__pycache__/supabase_mcp.cpython-312.pyc`, and `test-results/.last-run.json`.
- `scratch/supabase.tar.gz` is tracked at 31,130,854 bytes and contains `LICENSE`, `README.md`, `supabase.exe`. It is an operational binary, not an application dependency shipped to Vercel/Render.
- Root `.gitignore` contains four duplicate `package.json` ignore entries. Existing manifests remain tracked, but new manifests would be silently ignored; this is a release-process footgun.
- No CI workflow is present in `multimodalragsystem` (no `.github/workflows`); the local `main` commit `037c8ee` adds `AGENTS.md` / `docs/prd/.gitkeep`, but no workflow file.

---

## 2. Synthesis of Existing Docs & Architecture Map

### 2.1 Document inventory

| Path | Lines / bytes | What it actually is | Reliability for this audit |
|---|---:|---|---|
| `DESIGN.md` (root) | 228 lines / 9.5 KB | Visual/design specification for the **onboarding video series**, not the VLE UI or code architecture | Accurate for video work only |
| `docs/DESIGN.md` | absent / 0 | Path requested by the task brief | Missing |
| `gemini.md` (root) | absent / 0 | Path requested by the task brief | Moved to `docs/gemini.md` |
| `docs/gemini.md` | 228 lines / 29.9 KB | Historical project summary and backup plan through Session 3/4A | Useful history; stale claims; contains a test credential at line 151 |
| `docs/architecture/SYSTEM_ARCHITECTURE.md` | 192 lines / 10.8 KB | Current high-level stack, endpoints, flows, env table | Mostly accurate; model names/env table/asset flow stale |
| `docs/architecture/RAG_ARCHITECTURE.md` | 162 lines / 4.2 KB | Retrieve-first philosophy, pipeline, chunk types, traceability | Accurate concept; implementation details lag 4A.2 |
| `docs/architecture/AI_SYSTEM_ARCHITECTURE.md` | 132 lines / 3.6 KB | Personas, retrieval rules, citations, guardrails | Aspirational; only AI Tutor is partially implemented |
| `docs/architecture/PEDAGOGICAL_ARCHITECTURE.md` | 146 lines / 4.1 KB | Hierarchy, learning blocks, progress, equity, reflection | Aspirational; Lesson/Block/Progress not implemented |
| `docs/architecture/PROJECT_ROADMAP.md` | 167 lines / 5.7 KB | Phases 1–8, current status, debt/risk | Mixed current/stale; CORS and test claims outdated |
| `docs/WORKSHEET_STABILIZATION_REPORT.md` | 302 lines / 12.5 KB | Session 4A root-cause fixes | Historical; accurate for 4A |
| `docs/WORKSHEET_UX_POLISH_REPORT.md` | 296 lines / 13.2 KB | 4A.1 graph awareness, citations, focus, LearningContext | Historical; some claims contradicted by later code/tests |
| `docs/GRAPH_CONTEXT_SYNCHRONIZATION.md` | 265 lines / 10.2 KB | LearningContext schema and asset-flow design | **Outdated** in key places (see §2.2) |
| `docs/SESSION_4A1_VERIFICATION_REPORT.md` | 452 lines / 20.0 KB | Release-gate review; `NO-GO` with blockers | Historical; useful evidence of unresolved risks |
| `docs/SESSION_4A2_QA_REPORT.md` | 154 lines / 7.3 KB | 4A.2 blocker fixes; `CONDITIONAL GO` | Closest status document; live verification still missing |
| `HANDOFF_SESSION_4B_FINAL.md` | 86 lines / 4.0 KB | Handoff summary; conditional GO | Consistent with 4A.2, but relies on unexecuted live tests |
| `docs/QA_REPORT.md` | 191 lines / 8.8 KB | Claims 14/14 acceptance tests pass on live Supabase + NVIDIA | Not reproducible from the checked-in tree |
| `docs/manual test report.txt` | 2.9 KB | Student-side manual notes: tutor asks student to describe a graph, citations too verbose | Confirms the old graph-context failure and citation UX issue |
| `docs/FRONTEND_FORENSIC_REPORT_V2.md` | 514 lines / 26.9 KB | 9-bug taxonomy, BUG-1..BUG-9 | Historical root-cause evidence |
| `docs/DATABASE_MIGRATION.md` | 206 lines / 7.0 KB | `resource_assets` schema/run order | Incomplete for a fresh DB; says migrations 2–4 out of scope |
| `docs/ASSET_ARCHITECTURE.md` / `docs/ASSET_PIPELINE.md` | 251 / 284 lines | Asset storage and extraction design | Good design history; runtime pipeline not in server requirements |
| `docs/ONBOARDING.md` | 118 lines / 8.4 KB | Developer tour/file map | Stale path references (`tests/worksheet-tab.spec.js`, removed) |

### 2.2 What the docs say vs. what the code does

| Claim in docs | Current code / evidence | Impact |
|---|---|---|
| `docs/DESIGN.md` is a platform design source | Only `DESIGN.md` at repo root exists; it is the onboarding-video style guide (`DESIGN.md:1-228`) | The task’s doc path is wrong; do not treat it as app UI spec. |
| `gemini.md` is at repo root | It is `docs/gemini.md` | Path drift in the task brief. |
| Frontend can focus a graph and the tutor “sees” it | Only text/caption/OCR/page chunks are sent; no image pixels reach any provider (`backend/main.py:880-904`) | The prompt must not claim visual inspection beyond verified text. This is still a pedagogical risk. |
| Focused-asset labels are generated on the frontend | Current code removes that path; backend generates canonical `asset_label` (`backend/main.py:323-367`) and frontend reads `src.asset_label` (`InteractiveTutor.jsx:21-80`) | `docs/GRAPH_CONTEXT_SYNCHRONIZATION.md` is stale, especially lines 48-113 and the block-4 formula description. |
| Graph formula grounding retrieves `chunk_type=eq.formula` | Current block 4 uses only `metadata.linked_formula_chunk_id`, and fails closed with `no_linked_formula` (`backend/main.py:500-594`) | Doc describes a removed, non-deterministic behavior. |
| CORS is wildcard / permissive | Current code uses an exact allowlist from `FRONTEND_URL` + `CORS_ORIGINS`; no `*` (`backend/main.py:19-33`) | Roadmap debt item and `gemini.md` are stale. |
| Express is the backend bridge | Express `backend/server.js:39` remains, but the frontend calls FastAPI (`InteractiveTutor.jsx:354`, `SearchPanel.jsx:56`, `QuizEngine.jsx:26/70`) | Express is legacy/dead for the app. |
| “15-check” Playwright suite passes | `frontend/tests/regression.spec.js` has 14 `test()` + 1 `setup()`; it cannot exercise the current contract as written | The count may include auth setup, but the behavior claims are stale. |
| All 14 acceptance tests pass live | `docs/QA_REPORT.md:14` says so; current repo has no browser, auth state, or env credentials | Not reproducible; treat as unverified historical claim. |
| `source_refs.page` exists for most chunks | Roadmap lists it as missing (`PROJECT_ROADMAP.md:112`); frontend handles null (`InteractiveTutor.jsx:101`) | Page navigation is not reliable. |
| `/api/grade` uses RAG/current resource | It still calls `fetch_forces_and_motion_data()` -> `TARGET_RESOURCE_ID`; request `resource_id` is ignored (`backend/main.py:675-702, 1338-1371`) | Quiz grading is not resource-scoped. |
| Frontend fetches assets via `/api/resources/.../assets` | `HybridDocumentViewer` queries Supabase directly (`HybridDocumentViewer.jsx:274-285`); FastAPI asset endpoints exist but have no UI caller | Backend visual-asset endpoints are effectively unused. |
| VLE includes simulations/lessons | Both tabs render the same placeholder (`InteractiveTutor.jsx:552-568`); no `three` or simulation component exists | The “simulation-to-tutor multiplier” premise is not implemented. |

### 2.3 Backend map (FastAPI)

**Entry point:** `backend/main.py`.

- App: `backend/main.py:17`.
- CORS: `backend/main.py:19-33`.
- Env loading: `backend/main.py:13-14` (`load_dotenv()`, default `.env` relative to cwd).
- Supabase Auth gate: `backend/main.py:43-79` (`HTTPBearer(auto_error=True)`, `GET {SUPABASE_URL}/auth/v1/user`).
- Pydantic models: `backend/main.py:97-180`.
  - `Message`: `:97`.
  - `LearningContext`: `:112-129`.
  - `TutorRequest`: `:131-143`.
  - `TutorSource`: `:145-161`.
  - `TutorResponse`: `:163-166`.
  - `GradeRequest`: `:168-174`.
  - `GradeResponse`: `:176-179`.
- RAG helpers:
  - `_retrieve_relevant_chunks`: `backend/main.py:193-253`. Embeds query via NVIDIA, calls `rpc/match_resource_chunks`, optional `filter_resource_id`, top-5; failures are returned as empty context.
  - `_format_chunks_as_context`: `:255-279`.
  - `_chunks_to_sources`: `:281-321`.
  - `_canonical_asset_label`: `:323-367`.
  - `_ground_focused_asset`: `:369-594`. Verifies asset belongs to `resource_id`; fetches page chunks, linked question, explicit formula link; prepends synthetic asset chunk.
  - `_enrich_chunks_with_resource_meta`: `:596-671`.
  - `fetch_forces_and_motion_data`: `:675-702`. Legacy full-context fetch for grading, hardcoded `TARGET_RESOURCE_ID`.
- Provider routing:
  - `evaluate_routing`: `backend/main.py:705-716`. Despite the name/docstring, this is **availability routing**, not prompt classification: OpenCode Zen if configured, else NVIDIA, else Gemini. The `prompt` argument is unused.
  - `_call_opencode_zen`: `:719-732`; model `deepseek-v4-flash-free`; 120s timeout.
  - `_call_nvidia`: `:735-748`; model `nvidia/nemotron-3-super-120b-a12b`; 120s timeout.
  - Gemini fallback: `:945-968`; model `gemini-2.5-flash`.
- Endpoints:

| Method / path | Handler | Auth | Notes |
|---|---|---|---|
| `POST /api/tutor` (`backend/main.py:750-968`) | `tutor_endpoint` | `get_current_user` | Resolves `learning_context` + legacy `resource_id`; RAG; focused-asset grounding; provider fallback; returns `sources`. |
| `GET /health` (`:970-972`) | `health_check` | public | Process health only; no Supabase/provider readiness check. |
| `GET /api/resources/{resource_id}/assets` (`:990-1020`) | `get_resource_assets` | bearer | PostgREST `resource_assets`; returns `{resource_id, assets, count}`. No UI caller. |
| `GET /api/resources/{resource_id}/assets/{asset_type}` (`:1023-1056`) | `get_resource_assets_by_type` | bearer | Filtered assets. No UI caller. |
| `POST /api/search` (`:1100-1150`) | `semantic_search` | bearer | Pure pgvector search. No UI caller. |
| `POST /api/search/hybrid` (`:1153-1309`) | `hybrid_search` | bearer | Vector + PostgREST relational merge; +0.1 boost; used by `SearchPanel`. |
| `GET /api/question` (`:1312-1324`) | `get_question` | bearer | **Hardcoded** car-acceleration question; ignores `resource_id`. |
| `POST /api/grade` (`:1326-1427`) | `grade_endpoint` | bearer | Checks `student_id` == auth user; uses hardcoded Forces & Motion context, not `request.resource_id`; prompt trusts client `question_text`/`max_score`; OpenCode/NVIDIA only. |
| `POST /api/chat` (`backend/server.js:39-68`) | Express | none | Legacy Gemini passthrough on port 5000; no frontend caller. |

- Supabase/pgvector:
  - `migrations/mig_5_resource_assets.sql:16-56` creates `resource_assets`, indexes, RLS (public read; authenticated write).
  - `migrations/mig_6_resource_chunks.sql:18-67` enables `vector`, creates `resource_chunks` with `vector(1024)`, HNSW `vector_cosine_ops` (`m=16`, `ef_construction = 200`), RLS.
  - `migrations/mig_7_match_function.sql:20-46` creates `match_resource_chunks(query_embedding, match_count, filter_resource_id)`; returns `similarity = 1 - (embedding <=> query_embedding)`; grants execute to `anon, authenticated`.
  - `database/quiz_attempts_migration.sql:4-41` creates `quiz_attempts` + owner-only RLS.
- Offline ingestion:
  - `backend/master_ingestion.py` (`OpenAI` client pointed at `https://integrate.api.nvidia.com/v1`; `pdf2image` with a Windows Poppler path; PDF vision + Nemotron JSON compile; optional embedding/asset pipelines).
  - `backend/pipeline/embedding_pipeline.py` (`EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"`, `EMBED_DIM = 1024`, deletes then re-inserts chunks).
  - `backend/pipeline/asset_extractor.py` imports `fitz`/`PIL`; not in `backend/requirements.txt`.
  - `backend/pipeline/run_asset_pipeline.py`, `storage_uploader.py`, `linked_question_resolver.py`.
  - `backend/resource_ingestion.py` uses `google.genai`, which is **not** in `requirements.txt`; superseded legacy path.

### 2.4 Frontend map (React / Vite, not Next.js)

**Actual stack:** React `19.2.4` + Vite `8.0.0` + Tailwind `3.4.19` + React Router `7.13.1` + Framer Motion `12.38` + GSAP `3.14.2` + KaTeX/ReactMarkdown. There is no Next.js, no `three`, no `@react-three/*`.

**Routing:** `frontend/src/App.jsx:36-53` with `BrowserRouter`.

| Path | Element | Notes |
|---|---|---|
| `/` | `Home` or redirect to `/dashboard` | Marketing landing. |
| `/auth` | `Auth` or redirect | Login/register/reset. |
| `/update-password` | `UpdatePassword` | Public; used by Supabase reset. |
| `/dashboard` | `VLEDashboard` (protected) | Nested shell; `DashboardHome` at index. |
| `/dashboard/unit/:unitId/chapter/:chapterId` | `InteractiveTutor` | `:unitId` is parsed by the route but `InteractiveTutor` only reads `:chapterId` (`useParams` at `InteractiveTutor.jsx:124`). |

- `App.jsx:62` defaults `activeTab` to `'Worksheet'`.
- `App.jsx:79-84` gates rendering on session restore to preserve deep links.
- `VLEDashboard.jsx:35` renders the route content via `<Outlet />`.
- `Sidebar.jsx:168-171` builds the only chapter links: `/dashboard/unit/${unit.id}/chapter/${chapter.id}`. It fetches `units`/`chapters` from Supabase. `Sidebar.jsx:162-165` only uses the Triple Science toggle to show a “TS” badge; it does not remove/filter chapters. The toggle is cosmetic/misleading relative to its docs.
- There is no React `LearningContext` provider/context file. The string “LearningContext” appears as comments and as the inline request object in `InteractiveTutor.jsx:344-352`.

**InteractiveTutor.jsx:**

- API base: `frontend/src/components/InteractiveTutor.jsx:14` (`VITE_API_URL` fallback `http://localhost:8000`).
- Local `focus` state: `:131`.
- Reset on chapter change: `:180-198` (messages, focus, worksheetResource, isLoading, showSearch, activeSpecPointId, concept refs; aborts fetch; invalidates tutor generation).
- Spec-point resolution: `:204-227` (first spec point only).
- Resource fetch: `:232-298` (resources by spec point, rich-content preference, AbortController).
- Send / payload: `:308-424`; payload builds `learningContext` at `:344-352`; POST at `:354-361`.
- `[SWITCH_TAB]` interception: `:382-395`; calls `setActiveTab(newTab)` without validating against the four known tabs.
- FAB: `:431-439`; visible label “Ask Tutor” at `:437`, accessible name is **“Open AI Tutor”** from `aria-label` at `:434`.
- Tabs: `:466-475` (`Lesson`, `Worksheet`, `Simulation`, `Quiz`).
- Worksheet branch: `:511-547`; Quiz branch: `:548-550`; everything else: `:552-568` placeholder.
- Focus chip: `:673-685`; shows `Viewing` + asset type/page or `Concept:`.

**HybridDocumentViewer.jsx:**

- Component: `:225`.
- PDF URL inferred from public storage convention: `:238-242`; hardcoded Supabase project fallback at `:240`.
- Parallel fetch of `resources(content,title,content_markdown)` and `resource_assets`: `:262-306`.
- PDF iframe: `:402-407`; title `Original worksheet PDF`; sandbox `allow-scripts allow-same-origin`.
- Asset cards (document mode): `:417-440`; asset focus payload: `:45-50` (`asset_id`, `asset_type`, `page`).
- Interactive asset focus: `:493-503`.
- Concept cards focus payload: `:545-547` (`concept`, `block_index`, `type: 'concept'`).
- Concept popup: `ConceptPopup` around `:165-223`.

**SearchPanel.jsx:** API base `:6`; body `:49-55`; POST `/api/search/hybrid` `:56`; result focus includes `focused_chunk`, `page`, `concept` at parent `InteractiveTutor.jsx:532-542`.

**QuizEngine.jsx:** API base `:10`; unused `activeSpecPointId` prop `:12`; fetch `/api/question` `:26`; payload `:61-68`; POST `/api/grade` `:70-73`; client insert into `quiz_attempts` `:84-95` (insert error not checked); hardcoded “Graded by Llama-3.3-70b-instruct” `:221`.

**Auth:** `frontend/src/components/Auth.jsx:65-67` uses `window.location.origin + '/update-password'` for reset redirect. Supabase project Auth URL configuration is therefore part of deployment.

**API client:** `frontend/src/lib/apiClient.js:7-19` requires a Supabase session and sets `Authorization: Bearer <access_token>` + `Content-Type: application/json`. `frontend/src/lib/supabaseClient.js:3-10bef` reads `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` and warns if missing.

**Simulation components:** none. `find`/`git grep` found no `HookesLaw.jsx`, no `three`, no `@react-three/*`, no `simulation_state` or `SimulationContext`. The words “PhET Simulation” in `Features.jsx:58/171` and “interactive simulations” in `Protocol.jsx:106` are marketing copy only.

### 2.5 Database map and fresh-deploy gap

- Base curriculum schema: `scratch/mig_1_tables.sql`; seed: `scratch/mig_2_units_chapters.sql`, `scratch/mig_3_specs.sql`, `scratch/mig_4_activities_resources.sql`.
- `scratch/mig_1_tables.sql:6-12` begins with `DROP TABLE ... CASCADE`; never run it against production.
- `scratch/mig_1_tables.sql:44-49` defines `resources(id, specification_point_id, title, created_at)`.
- `migrations/mig_5_resource_assets.sql:54-65` adds `content_markdown` only. **No checked-in migration adds `resources.content`**, although the frontend selects it (`HybridDocumentViewer.jsx:277`) and the ingestion code writes it. A fresh DB from these files cannot run the worksheet viewer.
- `scratch/mig_1_tables.sql` does not enable RLS or create policies for `units`, `chapters`, `specification_points`, `activities`, `resources`, or `questions`. The docs claim RLS is enforced everywhere (`SYSTEM_ARCHITECTURE.md:82,118,189`; `ONBOARDING.md:31-33`). `migrations/mig_5` and `mig_6` add RLS only for their new tables, and `database/quiz_attempts_migration.sql` only for `quiz_attempts`.
- `docs/DATABASE_MIGRATION.md:17-24` says migrations 2–4 were not in scope, but `scratch/mig_2_units_chapters.sql`, `mig_3_specs.sql`, and `mig_4_activities_resources.sql` are present and non-empty. The migration order is undocumented/ambiguous.
- `Alsini_Physics_Schema_V1_Seed.sql` is an older `courses -> chapters -> topics -> subtopics` seed (lines 1-12+). It does not match the `units -> chapters -> specification_points -> activities/resources/questions` schema and should not be run against this database.
- `resource_assets.metadata.linked_formula_chunk_id` is required for deterministic graph -> formula grounding, but no pipeline population is evident. The backend therefore fails closed (`no_linked_formula`) for most graphs.
- `resource_chunks.source_refs.page` is not populated for most chunks per the roadmap, so citation pages are often null and PDF page jumping is not wired.

### 2.6 Environment variables/config

| Consumer | Variable | Code reference | Local state |
|---|---|---|---|
| Frontend | `VITE_SUPABASE_URL` | `frontend/src/lib/supabaseClient.js:3`; fallback in `HybridDocumentViewer.jsx:240` | present in ignored `frontend/.env.local` |
| Frontend | `VITE_SUPABASE_ANON_KEY` | `frontend/src/lib/supabaseClient.js:4` | present locally |
| Frontend | `VITE_API_URL` | `InteractiveTutor.jsx:14`, `SearchPanel.jsx:6`, `QuizEngine.jsx:10` | present locally, set to `http://localhost:8000` |
| Backend | `FRONTEND_URL` | `backend/main.py:21` | **not set** in `backend/.env`; falls back to localhost |
| Backend | `CORS_ORIGINS` | `backend/main.py:22-25` | not set; comma-list supported but undocumented in `SYSTEM_ARCHITECTURE.md` |
| Backend | `GEMINI_API_KEY` | `backend/main.py:36` | present locally |
| Backend | `NVIDIA_API_KEY` | `backend/main.py:37` | present locally |
| Backend | `OPENCODE_ZEN_API_KEY` | `backend/main.py:38` | not present in `backend/.env`; Zen path not exercised in this audit |
| Backend | `SUPABASE_URL` | `backend/main.py:39` | present locally |
| Backend | `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_SERVICE_KEY` | `backend/main.py:40` | service role present locally (value not copied) |
| Backend | `SUPABASE_ANON_KEY` | `backend/main.py:41` | not set locally; auth validation falls back to service key as `apikey` |

All three local env files are ignored/untracked: `git ls-files | grep -E '(^|/)\.env'` returns nothing. Their values were not copied into this report.

### 2.7 Missing/incorrect paths from the task brief

- `docs/DESIGN.md` — **absent**; actual `DESIGN.md` is at repository root and covers onboarding-video design.
- `gemini.md` — **absent** at root; actual `docs/gemini.md`.
- `Next.js` — **not used**; actual frontend is Vite SPA.
- `Three.js` — **not installed/used**.
- `HookesLaw.jsx` — **absent**.
- `LearningContext` — **not a React context/component file**; it is `backend/main.py:112-129` (Pydantic) plus an inline JS object at `InteractiveTutor.jsx:344-352`.
- Simulation tab — **placeholder only**, `InteractiveTutor.jsx:552-568`.

---

## 3. Simulation-to-Tutor Multiplier Readiness

### 3.1 How worksheet/graph context flows today

```text
HybridDocumentViewer
  ├─ asset card click -> onFocus({type:'asset', asset_id, asset_type, page})
  ├─ concept card click -> onFocus({concept, block_index, type:'concept'})
  └─ search result click (InteractiveTutor) -> setFocus({
        concept, focused_chunk: result.id, page, type: chunk_type
     })
        │
        ▼
InteractiveTutor.focus (React state, InteractiveTutor.jsx:131)
        │
        ├─ focus chip: "Viewing" + asset_type/page, or "Concept: X" (:673-685)
        │
        └─ handleSend (:308) builds LearningContext inline (:344-352):
             {
               resource_id: worksheetResource?.id || null,
               chapter_id: chapterId || null,
               focused_chunk: focus.focused_chunk || null,
               focused_asset: focus.asset_id || focus.focused_asset || null,
               focused_asset_type: focus.asset_type || null,
               focused_question: focus.focused_question || null,
               page: focus.page ?? null
             }
             (null when no focus exists)
        │
        ▼
POST ${VITE_API_URL}/api/tutor
{
  student_prompt: inputValue,
  history: formattedHistory,   // {role:'user'|'model', content}
  resource_id: worksheetResource?.id || null,
  learning_context: learningContext
}
        │
        ▼
backend/main.py:750 tutor_endpoint
  ├─ validate context/resource conflict (:758-778)
  ├─ _retrieve_relevant_chunks(prompt, resource_id) (:787)
  ├─ if focused_asset: _ground_focused_asset(ctx) (:796-808)
  ├─ _enrich_chunks_with_resource_meta (:812)
  ├─ _format_chunks_as_context + _chunks_to_sources (:814-815)
  ├─ context preamble from canonical asset label (:826-878)
  ├─ system prompt + RAG context (:880-911)
  └─ evaluate_routing -> OpenCode Zen / NVIDIA / Gemini (:913-968)
        │
        ▼
TutorResponse { response, model_used, sources[] }
        │
        ▼
InteractiveTutor renders Markdown/KaTeX + CitationChip; focus is not consumed/cleared
```

### 3.2 What is working in the current context path

- Structured `learning_context` is accepted, and the legacy top-level `resource_id` remains supported.
- When both are supplied and disagree, the backend returns HTTP 400.
- A focused asset requires an effective `resource_id`.
- Focused asset grounding verifies that the asset belongs to the selected resource before using it.
- Canonical asset labels are generated server-side from page order, not client array order.
- Grounded chunks are deduplicated and prepended to RAG chunks.
- `TutorSource` exposes traceability fields (`resource_id`, `resource_title`, `specification_point_*`, `chunk_index`, asset fields).
- Chapter changes reset focus, chat, resource, search, spec point, and invalidate in-flight tutor responses.
- No focus context is passed for a plain worksheet question with `focus === null`; RAG still scopes by worksheet `resource_id`.

### 3.3 What is missing for a simulation multiplier

1. No `simulation_state` field in `LearningContext` (`backend/main.py:112-129`) or in the frontend object (`InteractiveTutor.jsx:344-352`).
2. No simulation tab/component to emit state. The `Simulation` tab is a string in the tab row (`:466-475`) and resolves to the generic placeholder (`:552-568`).
3. No contract for which numerical quantities a simulation owns, their units, or their provenance.
4. No server-side validation/limits; arbitrary client text in a prompt would be a prompt-injection and cost risk.
5. No test hooks for simulation context. Existing E2E tests are stale even for asset labels (`regression.spec.js:256,272`).
6. No mechanism for a simulation to indicate its own grounding `resource_id`; the current `resource_id` is inherited from the worksheet fetched from the first chapter spec point.
7. No update/throttle semantics; React state changes at render rate would be inappropriate to send per frame.
8. The backend already accepts `lesson_id`, `block_id`, and `worksheet_id`, and declares `focused_asset_label` deprecated, but the frontend populates none of them. Only `resource_id`, `chapter_id`, `focused_chunk`, `focused_asset`, `focused_asset_type`, `focused_question`, and `page` are sent (`InteractiveTutor.jsx:344-352`).

### 3.4 Minimal contract (proposed)

Add exactly one nullable object to the existing carrier. Do not create a parallel channel, endpoint, or table for the MVP.

```json
{
  "student_prompt": "Why does the extension double when I double the force?",
  "history": [],
  "resource_id": "5729d034-a6c7-4f35-b81c-fcac447289c7",
  "learning_context": {
    "resource_id": "5729d034-a6c7-4f35-b81c-fcac447289c7",
    "chapter_id": "b95f8fac-355e-4037-bc1f-2d3b2bf77140",
    "focused_chunk": null,
    "focused_asset": null,
    "focused_asset_type": null,
    "focused_question": null,
    "page": null,
    "simulation_state": {
      "sim_id": "hookes-law",
      "sim_version": 1,
      "sim_type": "hookes_law",
      "units": {
        "spring_constant": "N/m",
        "extension": "m",
        "force": "N"
      },
      "parameters": {
        "spring_constant": 50.0
      },
      "observations": {
        "extension": 0.12,
        "force": 6.0
      },
      "active": "extension"
    }
  }
}
```

Contract rules:

| Field | Required | Type | Rule |
|---|---|---|---|
| `sim_id` | yes | string | Stable registry key, e.g. `hookes-law`; max 64 chars; `[a-z0-9-]` |
| `sim_version` | yes | integer | Schema version; the MVP supports exactly `1`; missing/other values are rejected |
| `sim_type` | yes | string | Physics family, e.g. `hookes_law`; max 64 chars |
| `units` | no | object<string,string> | Only SI/display units used by the sim; max 16 keys |
| `parameters` | yes | object<string,number> | Student-controlled inputs; finite numbers only; max 24 keys |
| `observations` | yes | object<string,number> | Derived/measured outputs; finite numbers only; max 24 keys |
| `active` | no | string | Currently focused quantity; must be a key in `parameters` or `observations` |
| key format | - | string | Map keys must match `^[a-z0-9_]{1,64}$`. |
| unit format | - | string | Unit values must match `^[A-Za-z0-9/%^*._-]{1,24}$` (e.g., `N/m`, `m/s^2`, `degC`). |

Explicit non-goals for the MVP:

- No canvas screenshot, base64 image, or WebGL pixels are sent to the LLM. The tutor must reason from verified numeric state plus retrieved curriculum text, not from an image it cannot inspect.
- No client-generated citation label. `sim_id` is an identity, not a curriculum citation.
- No free-form “simulation description” prompt text. Everything is structured, bounded, and server-serialized.
- No new database migration. Simulation state is request-scoped telemetry/context. If analytics are later needed, add a separate table.
- No synthetic `TutorSource` for the simulation unless a curriculum asset is actually retrieved. State is not a source.

### 3.5 Backend change

Insert before `LearningContext` in `backend/main.py` (around line 112):

```python
import math
from pydantic import Field, field_validator, model_validator

class SimulationState(BaseModel):
    sim_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    sim_version: int = Field(ge=1, le=1)
    sim_type: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    units: dict[str, str] = Field(default_factory=dict)
    parameters: dict[str, float]
    observations: dict[str, float]
    active: Optional[str] = None

    @field_validator("parameters", "observations")
    @classmethod
    def _bounded_numbers(cls, value: dict[str, float]) -> dict[str, float]:
        if len(value) > 24:
            raise ValueError("too many simulation values")
        for key, number in value.items():
            if not re.fullmatch(r"[a-z0-9_]{1,64}", key) or not math.isfinite(number):
                raise ValueError("invalid simulation value")
        return value

    @field_validator("units")
    @classmethod
    def _bounded_units(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 16:
            raise ValueError("too many simulation units")
        for key, unit in value.items():
            if not re.fullmatch(r"[a-z0-9_]{1,64}", key):
                raise ValueError("invalid simulation unit key")
            if not re.fullmatch(r"[A-Za-z0-9/%^*._-]{1,24}", unit):
                raise ValueError("invalid simulation unit")
        return value

    @model_validator(mode="after")
    def _bounded_state(self) -> "SimulationState":
        if self.active and self.active not in {*self.parameters, *self.observations}:
            raise ValueError("active quantity is not present in simulation state")
        raw = json.dumps(self.model_dump(exclude_none=True), separators=(",", ":"))
        if len(raw.encode("utf-8")) > 2048:
            raise ValueError("simulation state exceeds 2 KB")
        return self
```

Add to `LearningContext` after `page`:

```python
    simulation_state: Optional[SimulationState] = None
```

Backend verification rules:

1. Reject `simulation_state` when `effective_resource_id` is absent. The state must be scoped to a worksheet/resource; unscoped simulation context is not allowed.
2. Reject a `resource_id` conflict as today (`backend/main.py:758-766`).
3. If `simulation_state` is present, require the corresponding simulation surface to have a verified grounding resource. For the MVP, that resource is the current worksheet/lesson `resource_id`; if a simulation needs its own source, the client passes that source’s `resource_id` explicitly and the backend verifies it the same way.
4. Serialize with `json.dumps(sim.model_dump(exclude_none=True), separators=(",", ":"), ensure_ascii=True)`, enforce a final byte limit (e.g., 2 KB), and place it between explicit delimiters. Never interpolate raw student text into the simulation block.
5. Keep RAG retrieval driven by `student_prompt` + `resource_id`; simulation state is context, not a retrieval query. Do not embed a 2 KB state blob on every request.

### 3.6 Prompt preamble change

In `tutor_endpoint`, after the existing focused-asset/request branches around `backend/main.py:818-878`, add a higher-priority branch:

```python
if ctx and ctx.simulation_state:
    sim = ctx.simulation_state
    sim_json = json.dumps(sim.model_dump(exclude_none=True), separators=(",", ":"))
    context_preamble = (
        f"The student is currently using the '{sim.sim_type}' simulation "
        f"(sim_id={sim.sim_id}, schema_version={sim.sim_version}). "
        f"Verified simulation state (numeric, authoritative): {sim_json}. "
        "Use these values exactly. Do NOT ask the student to restate them. "
        "Do NOT invent readings, axes, labels, or relationships not present in "
        "this state or in the retrieved curriculum context. If the student "
        "asks for a quantity that is not in the state, say it is not currently "
        "exposed and ask them to change the simulation. Explain the physics "
        "Socratically and cite only retrieved curriculum sources."
    )
```

Priority order: `simulation_state` > `focused_asset` > `focused_question` > `focused_chunk`. If simulation state and asset focus can coexist, the simulation block should include the focused asset only if it was explicitly verified and is relevant; for the MVP, the simulation surface clears `focus` on entering the Simulation tab.

### 3.7 Frontend change

In `InteractiveTutor.jsx`, around `:344-352`:

```js
const simulationState =
  focus?.type === 'simulation' && focus.simulation_state
    ? focus.simulation_state
    : null;

const learningContext = (focus || simulationState) ? {
  resource_id: worksheetResource?.id || null,
  chapter_id: chapterId || null,
  focused_chunk: focus?.focused_chunk || null,
  focused_asset: focus?.asset_id || focus?.focused_asset || null,
  focused_asset_type: focus?.asset_type || null,
  focused_question: focus?.focused_question || null,
  page: focus?.page ?? null,
  simulation_state: simulationState,
} : null;
```

Keep sending the top-level `resource_id` as today. A future simulation should emit only:

```js
onFocus({
  type: 'simulation',
  simulation_state: {
    sim_id: 'hookes-law',
    sim_version: 1,
    sim_type: 'hookes_law',
    units: { spring_constant: 'N/m', extension: 'm', force: 'N' },
    parameters: { spring_constant: k },
    observations: { extension: x, force: F },
    active: 'extension',
  },
});
```

Recommended integration shape:

- Every simulation module exports `getTutorState(): SimulationState`.
- A shared `SimulationHost` calls `getTutorState()` on `pointerup`, `change` committed events, or a 250–500 ms debounce; never on every animation frame.
- Entering the Simulation tab clears any worksheet asset/concept focus.
- Leaving the Simulation tab clears simulation focus.
- The existing chapter reset at `InteractiveTutor.jsx:180-198` must also clear the simulation state; if a separate state variable is used, add it to that reset and to the generation guard.
- If a simulation has its own curriculum resource, it passes that `resource_id` in the same `learning_context`; otherwise it inherits the chapter worksheet resource. The contract does not change.

### 3.8 Acceptance tests for the contract

Static/server:

1. `POST /api/tutor` with a valid `simulation_state` returns 200 when providers are configured, and the server prompt contains the serialized numeric block.
2. Same request with no `learning_context.resource_id` returns 400.
3. Two different `resource_id` values or nested/top-level conflicts return 400.
4. Unknown `sim_version` (e.g. `99`) returns 422/400 at schema boundary.
5. `NaN`, `Infinity`, non-numeric values, >24 keys, >2 KB state return 422 and never reach a provider.
6. `active` not present in parameters/observations returns 422.
7. `simulation_state` does not create a synthetic `TutorSource` and does not alter RAG chunk selection except through the normal `student_prompt`/`resource_id`.
8. With `simulation_state` present and no asset/chunk focus, the preamble does not mention “visible figure” or claim image inspection.

Browser/Playwright:

1. Open a simulation, change a parameter, ask “Help me answer”, and capture the `/api/tutor` request body; assert `learning_context.simulation_state.sim_id`, `parameters`, and `observations`.
2. Assert the state reflects the latest committed interaction, not an intermediate slider frame.
3. Switch chapters and assert simulation state is cleared; in-flight stale response is discarded.
4. Ask a question with a quantity omitted from state; assert the tutor says it is not exposed rather than inventing it (requires live LLM; mark as manual/live).
5. Assert the worksheet path still sends no `simulation_state` and its existing payload is unchanged.

Do not claim these pass until the fresh browser suite is run against a real backend. The checked-in suite is not a valid gate.

---

## 4. Feature Status & Verification Health

### 4.1 Classification rules used

- **Working** — complete code path exists; static contract is coherent; at least one non-live check passed if possible.
- **Half-Wired** — a real path exists, but a consumer, data dependency, or contract is missing/mismatched.
- **Unused/Stub** — hardcoded, placeholder, no app caller, or dead legacy path.
- “Live” is reported separately. No live LLM/Supabase/embedding call was made in this audit.

### 4.2 Backend endpoints

| Endpoint | Status | Evidence / limitation |
|---|---|---|
| `GET /health` | **Working** | Booted locally; HTTP 200 `{"status":"OK",...}`. Process-only health; no dependency check. |
| `POST /api/tutor` | **Working** | Full RAG + grounding + provider fallback (`main.py:750-968`). Anonymous probe returned 401. Authorized live call not run. Prompt claims “visible figure” although only text is passed. |
| `POST /api/search` | **Working** | Pure vector search (`:1100-1150`); no frontend caller; live embedding not run. |
| `POST /api/search/hybrid` | **Working** | Vector + relational merge (`:1153-1309`); called by `SearchPanel.jsx:56`; live not run. |
| `GET /api/resources/{id}/assets` | **Working** | PostgREST asset list (`:990-1020`); no UI caller (viewer queries Supabase directly). |
| `GET /api/resources/{id}/assets/{type}` | **Working** | Filtered asset list (`:1023-1056`); no UI caller. |
| `GET /api/question` | **Unused/Stub** | Hardcoded car question, fixed mark, fixed hint; ignores `resource_id` (`:1312-1324`). |
| `POST /api/grade` | **Half-Wired** | Auth identity check works; but ignores `request.resource_id`, grades against `TARGET_RESOURCE_ID` Forces & Motion (`:1338`), trusts client `question_text`/`max_score` (`:1373-1377`), and the UI claims Llama-3.3 while provider is OpenCode/NVIDIA (`QuizEngine.jsx:221`). |
| `POST /api/chat` (Express) | **Unused/Stub** | Legacy Gemini endpoint (`backend/server.js:39`); CORS `*`; no frontend caller. |
| Ingestion/asset CLI | **Half-Wired** | Offline scripts only; Windows Poppler path in `master_ingestion.py:48`; PyMuPDF (`fitz`) is not in `requirements.txt` (Pillow is transitive via `pdf2image`); hardcoded Golden IDs. Not part of web runtime. |
| Embedding pipeline | **Working (code)** | External NVIDIA embed API (`pipeline/embedding_pipeline.py:181-198`); not re-run in this audit. |
| Provider routing | **Working (availability)** | `evaluate_routing` (`:705-716`) always chooses OpenCode if key, else NVIDIA, else Gemini. Not semantic/prompt-based; OpenCode Zen path not exercised in this audit because no key is defined in `backend/.env`. |

### 4.3 Frontend surfaces

| Surface | Status | Evidence / limitation |
|---|---|---|
| Supabase Auth (login/register/reset/update) | **Working** | `Auth.jsx`, `UpdatePassword.jsx`; reset redirect uses origin (`Auth.jsx:65-67`); no live auth. |
| Protected routing / deep-link restore | **Working** | `App.jsx:36-53,79-84`; waits for session restore. |
| Dashboard shell | **Working** | `VLEDashboard.jsx:16-40`, `<Outlet />` at `:35`; `session` prop unused (`:16`). |
| Sidebar syllabus nav | **Working** | `Sidebar.jsx:14-57` Supabase fetch; links `:168-171`. No live data. |
| Triple Science toggle | **Half-Wired** | Toggle state `:11/114`; “filter” only drives a `TS` badge at `:162-165`; chapters are never removed. |
| Worksheet PDF viewer | **Working** | `HybridDocumentViewer.jsx:238-242,402-407`; URL inferred from `{resource_id}/original.pdf`, not authoritative metadata; no live Storage fetch. |
| Interactive knowledge concepts | **Working** | `HybridDocumentViewer.jsx:244-306,532-607`; concept popup `:165-223`. |
| Visual asset cards/zoom | **Working** | `AssetCard` `:26-121`; retry; focus `:45-50`; zoom modal. |
| Search panel | **Working (code)** | `SearchPanel.jsx:40-73`, `/api/search/hybrid:56`; check 5 was already reported hanging; live not run. |
| AI tutor chat | **Working (code)** | `InteractiveTutor.jsx:308-424`, `/api/tutor:354`; live not run. |
| Focus/citation chips | **Working (code)** | `CitationChip` `:74-121`; backend `asset_label`; student/dev split. E2E assertions stale. |
| `[SWITCH_TAB]` agentic navigation | **Working** | Regex `:382-395`; strips tag and calls `setActiveTab`; no validation of tab names. |
| Chapter state reset/stale guards | **Working** | `:180-198`, `tutorGenRef:160`, AbortController `:153-155`; static. |
| Quiz engine | **Half-Wired** | `QuizEngine.jsx:26,70`; static question + hardcoded grading context; model badge at `:221` is wrong; DB insert error ignored. |
| Lesson tab | **Unused/Stub** | Same placeholder as Simulation (`InteractiveTutor.jsx:552-568`); no lesson component or route. |
| Simulation tab | **Unused/Stub** | Placeholder; no `three`, no sim component, no `simulation_state`. |
| Progress tracking | **Unused/Stub** | No table, endpoint, component, or state. |
| Teacher analytics | **Unused/Stub** | No UI, endpoint, or aggregation. |
| Error boundary | **Absent (gap)** | Not in current `App.jsx`; exists only on unmerged `multimodal-rag-system` branch. |
| Developer citation mode | **Working** | `devMode` state `:137`; expanded provenance in `CitationChip`; static. |

### 4.4 TODO/FIXME inventory

No `TODO`, `FIXME`, `HACK`, or `XXX` comments exist in application source. A broader working-tree grep only matched the untracked audit brief itself; a tracked binary archive also matched but is not source. The source-only command below returns no hits.

```bash
git grep -nE '\b(TODO|FIXME|HACK|XXX)\b' -- \
  '*.py' '*.js' '*.jsx' '*.ts' '*.tsx' '*.sql' '*.md' '*.json' '*.html' '*.css'
```

Documented debt lives in prose instead, principally `docs/architecture/PROJECT_ROADMAP.md:110-172`:

- `/api/grade` still uses full-context, not RAG.
- `source_refs.page` is mostly unset.
- Playwright check 5 hangs.
- CORS wildcard claim (now stale; code is allowlisted).
- Express `server.js` is dead code.
- Bundle is 1.1 MB with no code-splitting.
- `linked_formula_chunk_id` population is a data-pipeline task (`HANDOFF_SESSION_4B_FINAL.md:81-86`).

### 4.5 Exact commands and observed results

#### Git inventory

```bash
cd /mnt/d/Alsini-physics-platform
GIT_TERMINAL_PROMPT=0 git fetch --all --prune
git branch -a
git branch -vv
git tag -l
git log --all --graph --oneline --decorate -n 45
git merge-base main multimodalragsystem
git rev-list --left-right --count main...multimodalragsystem
git ls-remote --heads origin
git ls-remote --tags origin
git status --porcelain=v2
```

Observed:

- `fetch_exit=0`.
- Fetch pruned `origin/jules-16984982520254157577-700be255` and `origin/jules-18444275450632772586-85575033`.
- `main` tracks `origin/main`, ahead 1.
- `multimodalragsystem` has no upstream.
- `merge-base main multimodalragsystem` exits 1.
- Symmetric difference: `27 34` exclusive commits.
- Remote heads: `main`, `multimodal-rag-system`, `multimodalragsystem`.
- Remote tag: `v0.4-worksheet-rag`.
- Worktree: `?? docs/RESEARCH.md.md` only.

#### Frontend lint/build/typecheck

```bash
cd /mnt/d/Alsini-physics-platform/frontend
npm run lint
npm run build -- --outDir /tmp/alsini-research-dist --emptyOutDir
npm ls --depth=0
```

Observed:

- `npm run lint`: **FAIL**, exit 1, **9 problems (9 errors, 0 warnings)**:
  - `frontend/playwright.config.js:32:12` — `process` not defined in `no-undef` (test config is linted by app config).
  - `frontend/src/components/HybridDocumentViewer.jsx:3:10` — `motion` unused.
  - `frontend/src/components/QuizEngine.jsx:12:35` — `activeSpecPointId` unused.
  - `frontend/src/components/VLEDashboard.jsx:16:25` — `session` unused.
  - `frontend/tests/auth.setup.js:5:15`, `6:18` — `process` not defined (2).
  - `frontend/tests/regression.spec.js:25:19`, `26:22` — `process` not defined (2).
  - `frontend/tests/regression.spec.js:227:9` — `firstConcept` unused.
- `npm run build`: **PASS**, exit 0, built in **3m 42s** on this `/mnt/d` mount.
  - 2,385 modules transformed.
  - JS: **1,128.30 kB** (`index-C5eudaXb.js`), gzip **344.88 kB**.
  - CSS: **77.95 kB**, gzip **17.06 kB**.
  - Output: `/tmp/alsini-research-dist` (not `frontend/dist`).
  - Warnings: Browserslist/caniuse-lite data 8 months old; chunks >500 kB; rolldown plugin timing breakdown. No build error.
- `npm ls --depth=0`: **PASS**, exit 0; React 19.2.4, Vite 8.0.0, Playwright 1.59.1, etc.
- Typecheck: **N/A**. There is no `tsconfig.json`, no `tsconfig.*.json`, no `typecheck` script, and the source is `.jsx`/`.js`. `vite build` does not typecheck.
- Existing `frontend/dist` is stale (mtime 2026-07-14); this audit built to `/tmp`, so no workspace artifact was overwritten.

#### Backend static and smoke

```bash
cd /mnt/d/Alsini-physics-platform
python3 - <<'PY'
import ast, pathlib
ast.parse(pathlib.Path('backend/main.py').read_text(encoding='utf-8'))
print('AST OK')
PY

cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -c 'import main'
# -> ModuleNotFoundError: No module named 'requests'

python3.11 -m venv /tmp/alsini-research-venv
/tmp/alsini-research-venv/bin/pip install -q -r backend/requirements.txt
/tmp/alsini-research-venv/bin/pip check
/tmp/alsini-research-venv/bin/pip freeze
cd backend
PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  /tmp/alsini-research-venv/bin/python -B -m uvicorn main:app \
  --host 127.0.0.1 --port 8011 --log-level info

curl -i http://127.0.0.1:8011/health
curl -i -X OPTIONS http://127.0.0.1:8011/api/tutor \
  -H 'Origin: http://localhost:5173' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: authorization,content-type'
curl -i -X OPTIONS http://127.0.0.1:8011/api/tutor \
  -H 'Origin: https://evil.example' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: authorization,content-type'
curl -i -X POST http://127.0.0.1:8011/api/tutor \
  -H 'Content-Type: application/json' --data '{"student_prompt":"test"}'
ps -o pid,rss,etime,args -p <uvicorn-pid>
```

Observed:

- `backend/main.py` AST parse: **PASS**.
- Repo `backend/.venv`: Python **3.14.4**; `import main` **FAILS** at `requests` because the app dependencies are not provisioned. `fastapi`, `requests`, `python-dotenv`, `openai`, and `google.generativeai` are absent from that venv. Do not use it for release verification.
- Temp `/tmp` env: Python **3.11.15**; `pip install -r backend/requirements.txt`: **PASS**; `pip check`: **No broken requirements found**.
- Uvicorn startup: **PASS**; `Application startup complete`.
- `/health`: **200 OK**, `{"status":"OK","message":"FastAPI Backend is running"}`.
- CORS preflight from `http://localhost:5173`: **200 OK**, `access-control-allow-origin: http://localhost:5173`, `access-control-allow-credentials: true`.
- CORS preflight from `https://evil.example`: **400 Bad Request**, `Disallowed CORS origin`.
- Anonymous `POST /api/tutor`: **401 Unauthorized**, `{"detail":"Not authenticated"}`.
- Idle RSS after health/CORS: **110,044 KiB (~107.5 MiB)**.
- Import warning: `google.generativeai` is end-of-life/deprecated.
- No live LLM, embeddings, Supabase database, or Storage request was made.

Key resolved versions from the temp install (unpinned requirements; not a recommendation):

```text
fastapi==0.165.0
uvicorn==0.54.0
pydantic==2.14.4
requests==2.34.2
python-dotenv==1.2.4
openai==3.57.0
google-generativeai==0.8.6
Pillow==13.0.0
PyPDF2==3.0.1
pdf2image==1.17.0
```

#### Playwright E2E

```bash
cd /mnt/d/Alsini-physics-platform/frontend
E2E_EMAIL='...' E2E_PASSWORD='...' npm test
# or
E2E_EMAIL='...' E2E_PASSWORD='...' npx playwright test
```

Observed inventory and static health:

- `frontend/tests/regression.spec.js`: **14** `test()` cases.
- `frontend/tests/auth.setup.js`: **1** `setup()` auth case.
- Total: **15** Playwright test entries (the “15-check” count likely includes auth setup).
- `test-results/.last-run.json`: `{"status":"failed","failedTests":[]}`.
- `frontend/playwright/.auth/user.json`: **absent**.
- Configured Chromium binary: **absent**.
- `/tmp/chromelibs/usr/lib/x86_64-linux-gnu`: **absent**.
- Config root hardcodes `/home/alsuni/Alsini-physics-platform` (`frontend/playwright.config.js:3`), which is a different checkout from the audited `/mnt/d` tree.
- Config requires `E2E_EMAIL` / `E2E_PASSWORD` (`frontend/tests/auth.setup.js:5-9`; `regression.spec.js:25-29`).
- E2E was **not executed** under the chosen verification scope.

Static suite mismatches (these would fail even with a browser):

| Test | Problem |
|---|---|
| `openTutor` (`regression.spec.js:64-68`) | Looks for button name `Ask Tutor`; current FAB accessible name is `Open AI Tutor` (`InteractiveTutor.jsx:434`). |
| `[A]` (`regression.spec.js:221-237`) | Expects text `/Context/i`; current chip renders `Viewing` (`:675`). Never clicks a concept card; locates a `div`. |
| `[B]` (`:242-257`) | Asserts `capturedRequest.learning_context.focused_asset_label` matches `FIG-`; the frontend intentionally no longer sends that field (`InteractiveTutor.jsx:339-352`). |
| `[D]` (`:262-277`) | Same `focused_asset_label` assertion; expects citation button `Citation`, which may still pass, but the payload assertion cannot. |
| Test count | 14 regression tests + 1 auth setup; docs often call it a 15-check suite. |

#### Backend source health

- No `pytest` suite, no `tests/` directory, no test runner config.
- No Python type checker config (`mypy`, `pyright`), no dependency pin file, no lockfile for Python.
- No server-side validation tests for `/api/tutor`, `/api/search`, or `/api/grade`.

### 4.6 Current health summary

| Area | Status | Evidence |
|---|---|---|
| Frontend production build | **PASS** | Vite 8, 2,385 modules, exit 0 |
| Frontend lint | **FAIL** | 9 errors / 0 warnings |
| Frontend typecheck | **N/A** | JS-only; no tsconfig/script |
| Dependency tree | **PASS** | `npm ls --depth=0` exit 0 |
| Backend syntax | **PASS** | AST parse |
| Repo-local backend runtime | **FAIL** | `backend/.venv` missing app deps; `import main` fails on `requests` |
| Clean temp backend install/boot | **PASS** | Python 3.11.15, uvicorn, `/health` |
| CORS policy behavior | **PASS** | allowed 200; disallowed 400 |
| Anonymous API protection | **PASS** | `/api/tutor` 401 |
| Live RAG/LLM/Supabase | **NOT RUN** | no provider call/database query in audit |
| Playwright E2E | **BLOCKED / STALE** | browser/auth state/env absent; assertions conflict with current code |
| TODO/FIXME markers | **NONE** | `git grep` no app-source hits |
| Deployment configs | **MISSING** | no Vercel/Render/Docker/Heroku/Python manifest |
| Fresh DB reproducibility | **FAIL** | no `resources.content`; no base-table RLS in checked-in SQL |
| Simulation feature | **NOT IMPLEMENTED** | tab placeholder; no Three.js; no HookesLaw |

---

## 5. Deployment Readiness Checklist (Vercel + FastAPI Host + Supabase)

### 5.1 Manifests and configuration paths

| Item | Exact path | Present? | Notes |
|---|---|---|---|
| Frontend package manifest | `/mnt/d/Alsini-physics-platform/frontend/package.json` | Yes | React/Vite app; has `dev`, `build`, `lint`, `preview`, `test` scripts. |
| Frontend lockfile | `frontend/package-lock.json` | Yes | npm lockfile; `frontend@0.0.0`. |
| Backend Python requirements | `/mnt/d/Alsini-physics-platform/backend/requirements.txt` | Yes | 9 unpinned lines. |
| Backend Python project manifest | `backend/pyproject.toml` | **No** | No build system/version pins/extras/ASGI metadata. |
| Root workspace manifest | `/mnt/d/Alsini-physics-platform/package.json` | Yes | Dependencies only; no scripts; `packageManager` says `pnpm@11.11.0`; root `package-lock.json` is npm. |
| Backend Node manifest | `backend/package.json` | Yes | Legacy Express scripts; `start` hardcodes `0.0.0.0:8000` via Python module. |
| Vercel config | `vercel.json` | **No** | Root directory/build/rewrites must be configured in the dashboard or added. |
| Render config | `render.yaml` / `render.yml` | **No** | Must be configured manually. |
| Dockerfile | any `Dockerfile` | **No** | No container path. |
| Procfile / runtime.txt | either | **No** | Render/Python runtime must be set externally. |
| CI workflow | `.github/workflows/*` | **No** | No automated gate. |
| Env example | `.env.example` | **No** | Variables are documented inconsistently and in prose. |
| Frontend local env | `frontend/.env.local` | Yes, ignored | `VITE_API_URL=http://localhost:8000`; Supabase URL/anon key present locally. |
| Backend local env | `backend/.env` | Yes, ignored | Supabase/Google/NVIDIA keys; no `OPENCODE_ZEN_API_KEY`; no `FRONTEND_URL`/`CORS_ORIGINS`. |
| Root local env | `.env` | Yes, ignored | Supabase access token/service-role configuration for tooling. |

There is no Next.js app, no `next.config.*`, no `three` package, and no simulation source.

### 5.2 Frontend API base URL

All three API consumers use the same build-time Vite env and fallback:

| File | Line | Expression |
|---|---|---|
| `frontend/src/components/InteractiveTutor.jsx` | 14 | `const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';` |
| `frontend/src/components/SearchPanel.jsx` | 6 | same |
| `frontend/src/components/QuizEngine.jsx` | 10 | same |
| `frontend/.env.local` | 3 | `VITE_API_URL=http://localhost:8000` (ignored, local only) |
| `frontend/tests/regression.spec.js` | 23 | `const BACKEND = 'http://localhost:8000';` hardcoded test value |

Implications:

- `VITE_API_URL` must be set in Vercel for Production/Preview and must be an absolute HTTPS origin, with **no trailing slash** because callers concatenate `/api/...` directly.
- Vite replaces `import.meta.env.VITE_*` at build time; changing the Vercel env requires a redeploy.
- If unset, production browsers will try `http://localhost:8000`, fail, and (on HTTPS pages) be blocked as mixed content.
- The Playwright config also hardcodes backend/frontend localhost and an absolute checkout path; it is not deployment configuration.

Supabase frontend config:

- `frontend/src/lib/supabaseClient.js:3-10` requires `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`; there is no fallback.
- `frontend/src/components/HybridDocumentViewer.jsx:240` has a hardcoded Supabase project URL fallback for the PDF path. Vercel must set `VITE_SUPABASE_URL`; the fallback should be removed to avoid sending traffic to a different project.
- `frontend/src/components/Auth.jsx:65-67` uses `window.location.origin + '/update-password'`; Supabase Auth **Site URL** and **Redirect URLs** must allow the Vercel production domain and `/update-password`.

### 5.3 CORS inspection (`backend/main.py:19-33`)

```python
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
configured_origins = os.getenv(
    "CORS_ORIGINS",
    ",".join([frontend_url, "http://localhost:5174", "http://localhost:3000"]),
)
allowed_origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
```

Facts:

- No wildcard `*`. This is a hardened allowlist, not the old permissive state described in `docs/gemini.md`/roadmap.
- Default allowed origins are localhost:5173, localhost:5174, localhost:3000.
- `FRONTEND_URL` is the primary production variable; `CORS_ORIGINS` is a comma-separated override.
- **If `CORS_ORIGINS` is set, `FRONTEND_URL` is not automatically included.** Include the production URL explicitly in the list.
- `allow_credentials=True`; exact origin match required.
- Allowed headers: `Authorization`, `Content-Type`. The frontend uses both.
- Allowed methods: all.
- Verified: allowed origin preflight 200; disallowed origin preflight 400; no wildcard fallback.
- Not verified: Vercel production origin, Vercel preview origin(s), custom domain. Until set, production browser calls will be rejected.
- CORS does not protect the API by itself; bearer validation does. CORS only controls browser cross-origin calls.

**Production configuration requirement:** set either

```text
FRONTEND_URL=https://<production-vercel-domain>
```

or, for multiple exact origins:

```text
CORS_ORIGINS=https://<production-vercel-domain>,https://<preview-domain>
```

No trailing slash; no path; no wildcard. Preview domains are per-deployment random, so either use a stable preview alias or add an origin proxy; do not wildcard the API.

### 5.4 Backend dependency/model profile and Render 512 MB

Inspection of `backend/main.py` imports:

```text
os, requests, fastapi, pydantic, dotenv, openai, google.generativeai,
typing, json, re
```

No `torch`, `transformers`, `sentence_transformers`, `tensorflow`, `numpy`,
`sklearn`, `onnx`, local embedding model, or local LLM runtime. RAG query
embeddings and generation are external:

- `_embed_query`: NVIDIA `nvidia/nv-embedqa-e5-v5` via the OpenAI-compatible
  `https://integrate.api.nvidia.com/v1` endpoint (`backend/main.py:1067-1077`).
- OpenCode Zen: `https://opencode.ai/zen/v1`, model `deepseek-v4-flash-free`
  (`backend/main.py:91-94, 719-732`).
- NVIDIA: `nvidia/nemotron-3-super-120b-a12b` (`:735-748`).
- Gemini: `gemini-2.5-flash` (`:945-968`).
- Ingestion uses remote Gemini/NVIDIA vision endpoints; no local model weights.

Measured smoke profile (Python 3.11.15, WSL/Linux, app idle, `.env` loaded):

| Metric | Value |
|---|---:|
| RSS after `/health` + CORS probes | **110,044 KiB / ~107.5 MiB** |
| Percent of 512 MiB budget | **~21%** |
| Temp venv disk size | 278 MB (disk, not RSS) |
| Runtime worker | 1 uvicorn process |

Verdict: **512 MB is code-compatible** for the API process; the app does not load local ML models. It is not a Render capacity guarantee: this was not measured on Render, and concurrent requests, Python allocator behavior, or expensive provider responses could increase RSS. Do **not** run the ingestion/asset-extraction pipelines inside the Render web service; they require PyMuPDF (`fitz`, not in requirements; Pillow is transitive via `pdf2image`) and a Windows Poppler path in `master_ingestion.py:48`.

Operational caveats:

- `google-generativeai==0.8.6` is end-of-life and printed a deprecation warning at import. Migrate to `google-genai` separately; do not combine it with this deployment.
- Provider calls allow 120s timeouts; confirm the hosting platform's request timeout and whether the frontend needs streaming. Render free tier cold starts after idle will add latency.
- One uvicorn worker plus synchronous `requests` calls into Supabase inside `async def` handlers means provider/DB latency blocks the event loop. It is adequate for single-class QA, not a throughput claim.
- No rate limiting; `/api/tutor` and `/api/grade` can spend provider credits per authenticated call.

### 5.5 Vercel checklist

- [ ] Create the Vercel project with **Root Directory = `frontend`**. The repository root has a `package.json` with no scripts and cannot build the Vite app.
- [ ] Framework preset: Vite. Install: `npm ci` (or `npm install` if lockfile resolution is intentionally refreshed). Build: `npm run build`. Output: `dist`.
- [ ] Node.js: use 22.x (local 22.14.0; Vite 8 requires `^20.19.0 || >=22.12.0`).
- [ ] Set `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and `VITE_API_URL` for Production and any Preview environment used in QA. `VITE_API_URL` must be the HTTPS FastAPI origin, no trailing slash.
- [ ] Do **not** put `SUPABASE_SERVICE_ROLE_KEY`, `NVIDIA_API_KEY`, `GEMINI_API_KEY`, or `OPENCODE_ZEN_API_KEY` in Vercel.
- [ ] Add/verify an SPA rewrite/fallback to `/index.html` for `/dashboard/unit/:unitId/chapter/:chapterId`, `/auth`, and `/update-password`. No `vercel.json` is checked in; confirm the Vite preset handles direct deep links or add an explicit rewrite (exclude `/assets/*`).
- [ ] Fix or remove broken static references: `frontend/index.html:5` points to `/vite.svg` but `frontend/public/` only contains `favicon.svg` and `icons.svg`; `frontend/src/components/Hero.jsx:74` points to `/telegram-qr.png`, which is not present. Both 404 in a fresh build.
- [ ] Add the Vercel domain and `/update-password` to Supabase Auth **Site URL** / **Redirect URLs**.
- [ ] Remove/ignore `frontend/dbglogin.mjs`, `frontend/dbgsearch.mjs`, `frontend/build-log.txt`, `frontend/test-results/`, and root `test-results/` for release builds.
- [ ] Revisit bundle size: 1,128.30 kB raw / 344.88 kB gzip, >500 kB warning. This is a performance risk, not a build failure.
- [ ] Confirm browser-level verification against the deployed origin; local build success does not prove CORS, auth redirect, Storage, or provider calls.

### 5.6 FastAPI host checklist (Render free tier or equivalent)

- [ ] Root Directory: `backend`.
- [ ] Runtime: Python **3.11.x or 3.12.x**. Do not use the repo's local `.venv` (3.14.4) as the deployment interpreter; it is incomplete and the deprecated `google-generativeai` stack is not validated there.
- [ ] Build: `pip install -r requirements.txt`.
- [ ] Start: `uvicorn main:app --host 0.0.0.0 --port $PORT` (or `python -m uvicorn ...`). **Do not** use `backend/package.json` `start`; it hardcodes port 8000 and is not Render-port-aware.
- [ ] Health check path: `/health` (public, but process-only).
- [ ] Set:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY` (preferred) or `SUPABASE_SERVICE_KEY`
  - `SUPABASE_ANON_KEY` (recommended; otherwise auth validation uses the service key as `apikey`)
  - `NVIDIA_API_KEY` (required for RAG query embeddings and NVIDIA LLM fallback)
  - `OPENCODE_ZEN_API_KEY` (primary LLM when set; not present in `backend/.env`)
  - `GEMINI_API_KEY` (last-resort LLM; optional)
  - `FRONTEND_URL` or `CORS_ORIGINS` (must be set to the production Vercel origin; localhost defaults are not production)
- [ ] Pin dependency versions from a verified environment. Current requirements are unpinned; a fresh install pulled `fastapi 0.165.0`, `starlette 1.10.0`, `openai 3.57.0`, `pydantic 2.14.4`, etc. Reproducibility is not guaranteed.
- [ ] Keep one worker unless memory/CPU are re-measured. The service is stateless, but provider SDK clients and 120s calls are not a scaling freebie.
- [ ] Do not deploy the ingestion scripts to the web service. They need `PyMuPDF` (`fitz`, not in requirements) and Linux Poppler (`pdf2image`) if vision conversion is used; Pillow is transitive via `pdf2image`; `master_ingestion.py:48` currently assumes a Windows Poppler path.
- [ ] Treat `/api/grade` as non-production until it is resource-scoped and server-authoritative. It currently ignores `request.resource_id` and trusts client `question_text`/`max_score`.
- [ ] Add provider/database timeouts and a circuit breaker before public launch; current RAG failures degrade to empty context, but provider failures can surface as 500/502 after up to 120s.

### 5.7 Supabase checklist

- [ ] Confirm existing project schema already has `resources.content` (JSONB/text) in addition to `content_markdown`; the checked-in SQL does not add `content` for a fresh DB.
- [ ] Apply in order to a new project: base tables (`scratch/mig_1_tables.sql` — **destructive; never production**), seed (`mig_2`..`mig_4`), then `migrations/mig_5_resource_assets.sql`, `mig_6_resource_chunks.sql`, `mig_7_match_function.sql`, then `database/quiz_attempts_migration.sql`.
- [ ] For an existing project, apply only `mig_5`..`mig_7` + quiz migration if not already present. Do not run `mig_1` against production; it drops curriculum tables.
- [ ] Add base-table RLS policies if they are not already live in Supabase. The repository SQL does not enable RLS on `units`, `chapters`, `specification_points`, `activities`, `resources`, or `questions`; the architecture docs claim RLS-first. Verify in the project, not from the repo.
- [ ] Verify `resource_assets` and `resource_chunks` RLS policies match the intended exposure. Both currently allow public read; the service role bypasses RLS on the backend. Content is educational, but this is a deliberate data-exposure decision.
- [ ] Create/verify the public `resource-assets` Storage bucket (10 MB limit per `docs/DATABASE_MIGRATION.md:7`). Uploads are not in SQL; they are a manual/CLI step.
- [ ] Verify PDF objects exist at `resource-assets/{resource_id}/original.pdf`; the viewer infers this path and does not read a resource document URL (`HybridDocumentViewer.jsx:238-242`).
- [ ] Populate/verify `resource_assets.metadata.linked_formula_chunk_id` for graph assets. Without it, graph formula grounding intentionally fails closed and the tutor says no verified formula is linked.
- [ ] Verify `resource_chunks.source_refs.page`; without it, citation pages are blank and PDF page navigation cannot work.
- [ ] Do not apply `Alsini_Physics_Schema_V1_Seed.sql` to the unified database: it targets an older `courses -> chapters -> topics -> subtopics` schema, not `units -> chapters -> specification_points`.
- [ ] Rotate the Supabase service-role key if it has ever been pasted outside the secret store. It is server-only and must not be exposed to Vercel.

### 5.8 Render 512 MB conclusion

**Compatible in principle, conditionally approved for staging.** The app uses external NVIDIA/OpenCode/Gemini APIs for embeddings and generation, imports no local ML runtime, and measured **~107.5 MiB** idle RSS in a clean Python 3.11 install. That leaves substantial headroom in a 512 MiB budget.

Conditions:

1. Pin Python and packages; unpinned latest dependencies are not a capacity guarantee.
2. Keep the ingestion/asset pipeline off the web service.
3. Confirm the platform request timeout against the 120s provider timeouts.
4. Measure under the real provider latency/concurrency that QA will use.
5. Set production CORS and API URL env vars; otherwise the app is memory-compatible but functionally unreachable.

### 5.9 P0 blockers and recommended order

| Priority | Blocker | Evidence | Required action |
|---|---|---|---|
| P0 | Default branch `main` is not the current app | Unrelated histories; `main` 287-line backend, no `SearchPanel` | Create a release branch from `83af05d`; decide the default-branch migration separately. Do not merge unrelated histories blindly. |
| P0 | E2E suite is stale | `focused_asset_label` assertions; `Ask Tutor` name; `Context` text; 14 tests + setup | Update tests to current contract or mark them xfail; rerun against a real backend. |
| P0 | Frontend lint fails | 9 errors, exit 1 | Fix or explicitly waive each; add CI gate. |
| P0 | No production API/CORS config | fallback localhost; `FRONTEND_URL`/`CORS_ORIGINS` unset | Set Vercel `VITE_API_URL`; set Render `FRONTEND_URL`/`CORS_ORIGINS` to exact origin. |
| P0 | No SPA rewrite config | no `vercel.json` | Add/verify rewrite for deep links. |
| P0 | DB not reproducible fresh | no `resources.content`; no base RLS SQL | Capture/verify live schema; add idempotent migrations; never run `scratch/mig_1` against prod. |
| P0 | Committed E2E credentials | `docs/gemini.md:151` | Rotate credentials; remove the value; purge history if required by policy. |
| P1 | Quiz is not production grading | static question, hardcoded grade context, wrong badge | Scope question/grade to resource + server-side mark scheme; fix UI label. |
| P1 | Hidden test/infra drift | tracked `.pyc`, stale `dist`, debug scripts, root package/pnpm mismatch, duplicate `package.json` ignore | Clean repo; pin; document; add CI. |
| P1 | Simulation multiplier absent | tab placeholder, no Three.js, no `simulation_state` | Implement §3 contract only when the simulation exists. |
| P2 | Broken static references | `/vite.svg`, `/telegram-qr.png` 404 | Add assets or remove references. |

### 5.10 Release recommendation

- **Production:** NO-GO.
- **Staging:** CONDITIONAL GO after P0 items 1–7 and a live smoke of auth → worksheet PDF → search → tutor with citations.
- **Release source:** `83af05d585a80ec83126a599dfd5970c650e69a9` (or a new commit on top of it containing the selected doc/security ports), not `04b90f4`, not `main`, not `v0.4-worksheet-rag`.

---

## Appendix A — Branch/commit evidence

### A.1 Full heads observed

```text
main                          037c8ee9429b5aaabca0f5c2fbecd57652d51d57
multimodalragsystem           04b90f4895908450865293c8f94ac733f10c232f
origin/multimodalragsystem    83af05d585a80ec83126a599dfd5970c650e69a9
origin/main                   6090fa192f1992645ba1c8ed5be11c80a5ff81c7
multimodal-rag-system         c1292c745e40396907f36091152c59287ddc9509
origin/multimodal-rag-system  c1292c745e40396907f36091152c59287ddc9509
nemotron-3-super              0b1b65096aefb7fd831023f3fe3cc812f769063a
v0.4-worksheet-rag            6e929914fba1c879d8767255dff6ce0466f5fbf6
```

### A.2 Current-lineage root and tag position

```text
root(current) = 6395cd0247aa5236156cd35863ce6a09f31377aa
path(current root -> HEAD) = 34 commits
tag v0.4-worksheet-rag = 6e92991
commits tag..HEAD = 8
tag contains only multimodalragsystem / origin/multimodalragsystem
```

### A.3 Remote state at audit time

```text
refs/heads/main                          6090fa192f1992645ba1c8ed5be11c80a5ff81c7
refs/heads/multimodal-rag-system         c1292c745e40396907f36091152c59287ddc9509
refs/heads/multimodalragsystem           83af05d585a80ec83126a599dfd5970c650e69a9
refs/tags/v0.4-worksheet-rag             6e929914fba1c879d8767255dff6ce0466f5fbf6
```

### A.4 Unmerged/abandoned commits inspected

```text
main 037c8ee         AGENTS.md, docs/prd/.gitkeep
c1292c7              onboarding video rendering sources
38b348f              inline ErrorBoundary, VLEDashboard layout tweak, tutor min-height
f4c697e              .gitignore handoff entries
e37a58c              agents-orchestrator docs
1a5cff1              old frontend component tests
3bcaddd              Button target=_blank rel hardening
0b1b650              ancestor of main (semantic routing)
04b90f4              tracked .pyc update only
```

---

## Appendix B — Primary line references

### Backend

- `backend/main.py:13-14` — `load_dotenv()`.
- `backend/main.py:17` — FastAPI app.
- `backend/main.py:19-33` — CORS allowlist.
- `backend/main.py:35-41` — provider/Supabase env.
- `backend/main.py:43-79` — Supabase bearer validation.
- `backend/main.py:82-94` — provider clients.
- `backend/main.py:97-180` — Pydantic models.
- `backend/main.py:112-129` — `LearningContext`.
- `backend/main.py:131-143` — `TutorRequest`.
- `backend/main.py:145-161` — `TutorSource`.
- `backend/main.py:186-187` — `TARGET_RESOURCE_ID`, `TUTOR_CHUNK_COUNT`.
- `backend/main.py:193-253` — `_retrieve_relevant_chunks`.
- `backend/main.py:255-279` — `_format_chunks_as_context`.
- `backend/main.py:281-321` — `_chunks_to_sources`.
- `backend/main.py:323-367` — `_canonical_asset_label`.
- `backend/main.py:369-594` — `_ground_focused_asset`.
- `backend/main.py:596-671` — `_enrich_chunks_with_resource_meta`.
- `backend/main.py:675-702` — `fetch_forces_and_motion_data`.
- `backend/main.py:705-716` — `evaluate_routing`.
- `backend/main.py:719-732` — `_call_opencode_zen`.
- `backend/main.py:735-748` — `_call_nvidia`.
- `backend/main.py:750-968` — `tutor_endpoint`.
- `backend/main.py:970-972` — `/health`.
- `backend/main.py:990-1056` — asset endpoints.
- `backend/main.py:1067-1077` — `_embed_query`.
- `backend/main.py:1100-1150` — semantic search.
- `backend/main.py:1153-1309` — hybrid search.
- `backend/main.py:1312-1324` — `/api/question` stub.
- `backend/main.py:1326-1427` — `/api/grade`.
- `backend/server.js:39-68` — legacy Express `/api/chat`.

### Frontend

- `frontend/src/App.jsx:36-53` — routes.
- `frontend/src/App.jsx:62` — `activeTab = 'Worksheet'`.
- `frontend/src/App.jsx:79-84` — session-restore gate.
- `frontend/src/components/VLEDashboard.jsx:16-40` — dashboard shell; `:35` `<Outlet />`.
- `frontend/src/components/Sidebar.jsx:162-165` — cosmetic Triple Science logic.
- `frontend/src/components/Sidebar.jsx:168-171` — chapter links.
- `frontend/src/components/InteractiveTutor.jsx:14` — `API_BASE`.
- `frontend/src/components/InteractiveTutor.jsx:124` — `useParams()`.
- `frontend/src/components/InteractiveTutor.jsx:131` — `focus`.
- `frontend/src/components/InteractiveTutor.jsx:180-198` — route reset.
- `frontend/src/components/InteractiveTutor.jsx:204-227` — spec-point resolution.
- `frontend/src/components/InteractiveTutor.jsx:232-298` — resource fetch.
- `frontend/src/components/InteractiveTutor.jsx:308-424` — send.
- `frontend/src/components/InteractiveTutor.jsx:344-352` — inline `learningContext`.
- `frontend/src/components/InteractiveTutor.jsx:354-361` — `/api/tutor` payload.
- `frontend/src/components/InteractiveTutor.jsx:382-395` — `[SWITCH_TAB]`.
- `frontend/src/components/InteractiveTutor.jsx:434` — FAB accessible name.
- `frontend/src/components/InteractiveTutor.jsx:466-475` — tabs.
- `frontend/src/components/InteractiveTutor.jsx:511-568` — Worksheet/Quiz/placeholder branches.
- `frontend/src/components/InteractiveTutor.jsx:673-685` — focus chip.
- `frontend/src/components/HybridDocumentViewer.jsx:45-50,496-501` — asset focus payloads.
- `frontend/src/components/HybridDocumentViewer.jsx:238-242` — inferred PDF URL.
- `frontend/src/components/HybridDocumentViewer.jsx:262-306` — direct Supabase reads.
- `frontend/src/components/HybridDocumentViewer.jsx:402-407` — PDF iframe.
- `frontend/src/components/HybridDocumentViewer.jsx:532-547` — concept cards/focus.
- `frontend/src/components/SearchPanel.jsx:6,40-73` — search API.
- `frontend/src/components/QuizEngine.jsx:10,12,26,70,84-95,221` — quiz API/UI defects.
- `frontend/src/lib/apiClient.js:7-19` — bearer fetch.
- `frontend/src/lib/supabaseClient.js:3-10` — Supabase env client.
- `frontend/index.html:5` — missing `/vite.svg`.
- `frontend/src/components/Hero.jsx:74` — missing `/telegram-qr.png`.
- `frontend/playwright.config.js:3-5,25-33,47-56` — hardcoded test root/browser/auth.
- `frontend/tests/regression.spec.js:25-29,65,235,256,272` — env and stale assertions.

### Database

- `migrations/mig_5_resource_assets.sql:16-56,54-65` — assets + `content_markdown`.
- `migrations/mig_6_resource_chunks.sql:18-67` — vector extension, chunks, HNSW, RLS.
- `migrations/mig_7_match_function.sql:20-46,58` — match RPC + grant.
- `database/quiz_attempts_migration.sql:4-41` — quiz attempts + owner RW policies.
- `scratch/mig_1_tables.sql:6-12,44-49` — destructive base DDL; `resources` without `content`.
- `Alsini_Physics_Schema_V1_Seed.sql:1-12+` — old `courses/topics` seed, not unified schema.

### Deployment/config

- `frontend/package.json:6-14` — build/lint/test scripts.
- `frontend/package-lock.json:1-3` — `frontend@0.0.0`.
- `backend/requirements.txt:1-9` — unpinned Python deps.
- `backend/package.json:6-11` — Node/FastAPI/legacy start scripts.
- `package.json:1-9` — root deps + pnpm packageManager; no scripts.
- `frontend/.env.local:1-3` — local env (ignored).
- `backend/.env` — local env (ignored; keys not printed).
- `.env` — root tooling env (ignored; keys not printed).

---

## Appendix C — Method and limitations

- No live LLM, embedding, Supabase database, Supabase Storage, or deploy target was called.
- Backend smoke used a throwaway Python 3.11 venv under `/tmp` and port `8011`; it loaded the ignored local `.env` for import-time configuration but did not call any provider.
- Frontend build output was written to `/tmp/alsini-research-dist`; the tracked/source tree was not modified.
- The current local `backend/.venv` (Python 3.14.4) is incomplete and is not evidence that a fresh Render install will fail: a clean Python 3.11 install of `backend/requirements.txt` succeeded.
- Playwright was not run because the chosen scope excludes live E2E and the suite is additionally blocked by missing browser/auth/env and stale assertions. Its failures are classified from source inspection, not from a browser run.
- Render 512 MB is inferred from local RSS, not measured on Render. 107.5 MiB is idle RSS after health/CORS probes; provider calls can add memory.
- The no-`TODO`/`FIXME` claim applies to tracked text source; binaries and the untracked task brief are excluded.
- The secret-scan finding identifies a credential-like test-account entry at `docs/gemini.md:151` without reproducing it. Rotation and history review are required if that file has been pushed to a shared remote.
- The audit did not verify `origin` tags exist on GitHub beyond `git ls-remote`; the tag ref is confirmed on the audit remote.
- This report intentionally does not include `.env` values, service keys, anon keys, test passwords, or hardcoded project identifiers that are not already part of source paths.

---

**Report written:** `d:/Alsini-physics-platform/docs/RESEARCH.md.md`  
**Application source changes:** none  
**Dependency changes:** none  
**Database changes:** none  
**`.env` changes:** none  
**Commit:** none
