# PRD: Chapter 1 Vertical Slice — Movement and Position

- **Tracking Issue (Docs & Plan):** `#12`
- **Wayfinder Implementation Issues:** `#13` (Slice 1) → `#14` (Slice 2, blocked by `#13`) → `#15` (Slice 3, blocked by `#14`)
- **Primary Content Source:** [G9-T1-W1-movement-and-position-slides.md](../../content/lessons/G9-T1-W1-movement-and-position-slides.md)
- **Visual System:** [DESIGN.md](../../DESIGN.md)

---

## 1. Scope & Curriculum Boundary

- **Target Chapter:** Unit 1 (*Forces and motion*, `2cf312d3-0f4b-4339-84f3-97b10b2907ea`) → Chapter 1 (*Movement and position*, `b95f8fac-355e-4037-bc1f-2d3b2bf77140`).
- **Specification Boundary:** Strictly **Edexcel International GCSE Physics (Modular) 4XPH1 specs `1.3–1.10`** per `SOW.md` and the Marp slide deck.
- **Explicit Deferrals:**
  - Spec `1.1` remains the legacy worksheet anchor on `5729d034-a6c7-4f35-b81c-fcac447289c7` and is excluded from Learning Block 1.
  - Migrating `/api/grade` to Unified RAG and replacing hardcoded `/api/question` with a Chapter 1 exam question bank are deferred to a separate follow-up ticket.
  - Refactoring legacy VLE chrome (`Sidebar.jsx`, `QuizEngine.jsx`) to `DESIGN.md` is deferred.

---

## 2. Canonical Domain Vocabulary

| Canonical Term | Definition & Boundary |
|---|---|
| **Learning Block** | One vertical, self-contained solo-student unit inside a Lesson (`4` blocks in Ch. 1 covering `1.3–1.4`, `1.5–1.6`, `1.7–1.9`, `1.10`). |
| **Self-Check** (`Mini Quiz`) | Inline low-stakes retrieval check closing a block; `<80%` triggers a calm inline solo remediation card without hard-locking navigation. |
| **Guided Practice** | Step-by-step `I Do / We Do / You Do` worked examples embedded inside a Learning Block. |
| **Worksheet** | The PDF + OpenKB practice surface (`HybridDocumentViewer` tab), distinct from Guided Practice. |
| **Practical** | The curriculum/domain surface for required experimental investigations (e.g. Spec `1.5`). |
| **Simulation** | The interactive physics canvas/widget embedded inside a Practical or Learning Block. |
| **Examiner Alert** | Verbatim Edexcel examiner report warning surfaced on Guided Practice / Worksheet items and indexed into RAG (`EXM-`). |
| **Resource** | Unified database/RAG parent spine (`resources` table typed by `resource_type`) backing `resource_chunks`. |

---

## 3. Architecture Decision Records

- [ADR-0001: Marp Markdown as Single Authoring Source of Truth](../adr/0001-marp-single-authoring-source.md)
- [ADR-0002: Direct Structured Context and Model-Tagged Hybrid RAG](../adr/0002-direct-context-and-model-tagged-rag.md)
- [ADR-0003: Calm XP and Soft-Gated Completion on `student_block_progress`](../adr/0003-calm-xp-on-student-block-progress.md)
- [ADR-0004: Client-Side Physics Simulations and VMR AI Tutor Debrief](../adr/0004-client-side-physics-sim-and-vmr-debrief.md)

---

## 4. Wayfinder Implementation Slices

1. **`#13` — Marp Parser, XP/Progress Schema, and Unified Model-Tagged RAG Ingestion**
   - Non-destructive `mig_8`: extend `resources` (`chapter_id`, `resource_type`, `spec_refs`), create `lessons`, `learning_blocks`, and owner-only RLS `student_block_progress` (`xp_awarded`, `SUM(xp_awarded)`), extend `resource_chunks` (`chapter_id`, `source_type`, `block_id`, `spec_refs`, `embedding_model`), add `match_chapter_chunks` RPC, and drop redundant B-tree indexes (`idx_resource_chunks_resource_id`, `idx_spec_points_code`) without re-embedding the 21 existing Chapter 1 rows.
   - Marp parser stripping teacher choreography cues, converting `Gate:` lines to solo remediation, and reading progressive HTML comment directives.
   - Unified ingestion (`nvidia/nemotron-3.5-embed-1b`, `1024-dim`) + `LearningContext.interactive_state` Pydantic contract + fail-closed allowlisted `formula_ref` grounding + server-canonical citation prefixes (`BLK-`, `PRC-`, `EXM-`, `WE-`).
2. **`#14` — Calm Vertical Learning Block Player, Self-Checks, and Touchable `d-t`/`v-t` Graphs**
   - `start.dev` / `supabase.com`-style calm vertical player (`DESIGN.md` tokens), quiet header bar (`Blocks completed · Spec objectives (1.3–1.10) · Total XP`), 4 blocks with 8-part cadence, Guided Practice, Examiner Alerts, Self-Check (`<80%` solo remediation), and 1-line Reflection.
   - Zero-dependency SVG Touchable Graphs (`InteractiveKinematicsGraph` + unit-tested `kinematicsMath.js`): time scrubber, gradient calipers ($\Delta y/\Delta x$), selectable $v$-$t$ area shading, synchronized $d$-$t \leftrightarrow v$-$t$ view, and drag-to-match motion stories wired to `InteractiveTutor.jsx` + chapter-change state reset.
3. **`#15` — Spec 1.5 Ramp / Trolley / 50 Hz Ticker-Timer Simulation + VMR AI Tutor Debrief**
   - Zero-dependency lazy-loaded Dual-Mode Spec 1.5 Simulation (`Spec15MotionLab` + unit-tested `spec15Physics.js`): Mode A (Ramp + Toy Car / Tennis Ball / Trolley, stopwatch reaction jitter + front-of-car rule vs. light gates, repeat trials & anomaly strike-through) and Mode B (50 Hz ticker-timer + interactive 10-space strip cutter → $v$-$t$ bar chart), with one-click export to `InteractiveKinematicsGraph`.
   - Structured **VMR (Vary, Measure, Repeat)** Edexcel AO3 AI Tutor debrief passing live trial telemetry via `LearningContext.interactive_state`.
