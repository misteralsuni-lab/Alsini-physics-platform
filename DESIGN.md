# DESIGN.md — Alsini Physics Platform Onboarding Video Series

## Style Prompt

**Mood:** Technical, cinematic, educational, precision-engineered — the visual language of a physics lab meets modern dev tooling.

**Light/Dark:** Dark canvas (physics simulation aesthetic — dark backgrounds make visualizations pop like oscilloscope traces).

**Visual References:**
- NASA mission control / JPL mission videos (clean data displays, purposeful motion)
- 3Blue1Brown manim aesthetic (elegant math animations, dark backgrounds)
- Linear/Stripe docs (crisp typography, purposeful color, no decoration)
- Physics simulation renders (particle trails, field lines, wave interference)

---

## Colors

| Role | Hex | Usage |
|------|-----|-------|
| **Canvas** | `#050505` | Page background — near-black, not pure black |
| **Surface** | `#0D0D0D` | Cards, panels, code blocks |
| **Surface Elevated** | `#141414` | Hover states, modals, elevated panels |
| **Primary Accent** | `#00D4AA` | Physics green — momentum, energy, "go" — primary CTAs, links, active states |
| **Secondary Accent** | `#FF6B35` | Physics orange — heat, radiation, warning — highlights, warnings, key metrics |
| **Tertiary Accent** | `#6C5CE7` | Physics purple — quantum, waves — secondary actions, tags |
| **Text Primary** | `#F5F5F5` | Primary text, headings |
| **Text Secondary** | `#9CA3AF` | Secondary text, descriptions, muted labels |
| **Text Muted** | `#6B7280` | Placeholder, disabled, timestamps |
| **Border** | `#1F1F1F` | Subtle borders, dividers |
| **Border Accent** | `#00D4AA33` | Focus rings, active borders |
| **Error** | `#EF4444` | Errors, destructive actions |
| **Success** | `#22C55E` | Success states, passing tests |
| **Code Background** | `#0A0A0A` | Code blocks, terminal blocks |
| **Code Border** | `#1A1A1A` | Code block borders |

---

## Typography

| Role | Font | Weight | Size Scale |
|------|------|--------|------------|
| **Display / Hero** | `Space Grotesk` | 700 | `clamp(2.5rem, 6vw, 5rem)` |
| **Headline / Section** | `Space Grotesk` | 600 | `clamp(1.75rem, 3.5vw, 3rem)` |
| **Subhead** | `Space Grotesk` | 500 | `clamp(1.125rem, 2vw, 1.5rem)` |
| **Body** | `IBM Plex Sans` | 400 | `1rem` (16px base) |
| **Body Small** | `IBM Plex Sans` | 400 | `0.875rem` |
| **Code / Mono** | `JetBrains Mono` | 400 | `0.875rem` |
| **Code Small** | `JetBrains Mono` | 400 | `0.75rem` |

**Font Loading:**
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

---

## Motion Character

**Personality:** Precise, deliberate, physics-accurate. No bounce, no elastic, no "playful" overshoot. Motion feels like a simulation — forces, damping, equilibrium.

| Easing | Use Case |
|--------|----------|
| `power2.out` | Standard entrances (0.5–0.8s) — smooth deceleration to rest |
| `power2.inOut` | Transitions between scenes — symmetric, cinematic |
| `power3.out` | Hero reveals, emphasis moments — slower, more deliberate |
| `expo.out` | Data reveals, counter animations — rapid initial, smooth settle |
| `linear` | Continuous animations (orbiting, rotating, scanning) |

**Duration Scale:**
- Micro: 0.15s (hover, focus)
- Standard: 0.5s (entrance/exit)
- Major: 0.8–1.2s (scene transitions, hero builds)
- Cinematic: 1.5–2s (opening title, closing)

**Stagger:** `0.08s` per element (tight, military precision)

---

## What NOT To Do

1. **No pure black (`#000`)** — use `#050505` canvas, `#0D0D0D` surfaces
2. **No generic blue (`#3B82F6`)** — physics green `#00D4AA` is the primary action color
3. **No Roboto / Inter / system UI fonts** — Space Grotesk + IBM Plex Sans + JetBrains Mono only
4. **No bounce/elastic/back easings** — physics simulation aesthetic: `power2`, `expo`, `linear`
5. **No drop shadows on text** — use `text-shadow` only for glow effects on accent text
6. **No rounded corners > 8px** — `rounded-lg` (8px) max; cards use `rounded-md` (6px)
7. **No gradient backgrounds** — solid surfaces only; gradients only for accent lines, progress bars, or scan lines
8. **No decorative particles/confetti** — every visual element must convey information
9. **No centered body text** — left-aligned always; centered only for display headlines < 2 lines
10. **No "loading spinners" without progress** — use skeleton screens or progress bars with real data

---

## Component Visual Rules

### Code Blocks
```css
background: #0A0A0A;
border: 1px solid #1A1A1A;
border-radius: 6px;
font-family: 'JetBrains Mono', monospace;
font-size: 0.875rem;
line-height: 1.6;
padding: 1rem;
color: #E5E7EB;
```

### Terminal / CLI Blocks
```css
background: #050505;
border: 1px solid #00D4AA33;
border-radius: 6px;
font-family: 'JetBrains Mono', monospace;
color: #00D4AA;
```

### Architecture Diagrams
- Dark background (`#050505`)
- Boxes: `#0D0D0D` fill, `#1F1F1F` border, `#00D4AA` accent border on hover/focus
- Arrows: `#6B7280` default, `#00D4AA` on highlight
- Text: `#F5F5F5` primary, `#9CA3AF` secondary

### Data Tables
- Header: `#0D0D0D` background, `#00D4AA` bottom border (1px)
- Rows: `#050505` / `#0D0D0D` alternating
- Hover: `#141414`
- Border: `#1F1F1F` horizontal only

### Cards / Panels
```css
background: #0D0D0D;
border: 1px solid #1F1F1F;
border-radius: 8px;
transition: border-color 0.2s power2.out, transform 0.2s power2.out;
```
Hover: `border-color: #00D4AA33; transform: translateY(-2px);`

### Progress / Scan Lines
- Primary: `#00D4AA` 
- Background: `#1A1A1A`
- Height: 2px (thin, precise)

---

## Scene Templates

### Title Card (Opening)
- Canvas: `#050505`
- Centered display text: `Space Grotesk 700`, `#F5F5F5`
- Accent line: `#00D4AA`, 2px height, 60% width, animated draw-in
- Subtitle: `IBM Plex Sans 400`, `#9CA3AF`
- Subtle scan line sweep across background (20s loop, linear)

### Section Divider
- Canvas: `#050505`
- Large section number: `Space Grotesk 700`, `#00D4AA`, `0.15` opacity
- Section title: `Space Grotesk 600`, `#F5F5F5`
- Horizontal rule: `#00D4AA`, 2px, animated width 0→100%

### Code Walkthrough
- Terminal-style header bar: `#0D0D0D`, `#1F1F1F` border bottom
- Window controls (macOS style): `#FF5F57`, `#FFBD2E`, `#28CA42` (subtle)
- Code lines reveal line-by-line with `power2.out` stagger 0.05s
- Highlighted line: `#00D4AA22` background, `#00D4AA` left border 3px

### Architecture Diagram Build
- Nodes appear with `expo.out` 0.6s stagger
- Edges draw with `stroke-dashoffset` animation (linear, 0.8s)
- Labels fade in after node settles (0.2s delay)

### Metrics / KPI Cards
- Grid layout, 3-4 columns
- Large number: `Space Grotesk 700`, `#00D4AA`, `clamp(2.5rem, 5vw, 4rem)`
- Label: `IBM Plex Sans 400`, `#9CA3AF`
- Trend indicator: `#22C55E` up, `#EF4444` down

---

## Video Series Structure

### Video 1: "Architecture & Foundations" (~8-10 min)
**Scenes:**
1. Title card — "Alsini Physics Platform: Developer Onboarding"
2. Project overview — what this platform is, who it's for
3. Repository tour — directory structure, key files
4. Architecture diagram build — dual backend, Supabase spine, frontend
5. Tech stack deep-dive — React/FastAPI/Express/Supabase
6. Getting started — clone, env, install, dev servers
7. Closing — "Next: The AI Tutor Pipeline"

### Video 2: "The AI Tutor — RAG, Assets & Intelligence" (~10-12 min)
**Scenes:**
1. Title card — "Session 3: Intelligent Learning Architecture"
2. Before/After — full JSON dump → RAG retrieval (93% context reduction)
3. RAG pipeline diagram — embed → pgvector → chunks → LLM
4. Backend walkthrough — `_retrieve_relevant_chunks`, `_format_chunks_as_context`, `_chunks_to_sources`
5. Frontend walkthrough — `InteractiveTutor.jsx`, focus state, `HybridDocumentViewer`
6. Visual asset pipeline — PDF → PyMuPDF → Supabase Storage → `resource_assets`
7. Citation system — `SRC-A12`, `FIG-04`, developer mode
8. Search panel — hybrid search, concept navigation
9. Closing — "Next: Worksheet Stabilization & Quiz Engine"

### Video 3: "Worksheet Stabilization, Quiz Engine & Production Readiness" (~8-10 min)
**Scenes:**
1. Title card — "Session 4A/4B: Worksheet Stabilization"
2. Bug forensic recap — 10 bugs, root causes, fixes
3. Dynamic RAG scope fix — hardcoded `TARGET_RESOURCE_ID` → dynamic `resource_id`
4. Spec-point selector UI — chapter → spec point → worksheet flow
5. Quiz engine — `QuizEngine.jsx`, `quiz_attempts` table, RLS policies
6. Asset pipeline integration — Milestone 1 complete, 3 assets extracted
7. API URL extraction — `VITE_API_URL` env var, 4 files fixed
8. ESLint hardening — `react/jsx-no-undef` catches `User` undefined
9. Test infrastructure — Playwright E2E, CI/CD, NSS library issue
10. Closing — "You're ready. Welcome to the team."

---

## Audio / Narration

**TTS Voice:** `af_nova` (Kokoro, English, natural, professional)
**Pacing:** Measured, technical — ~150 wpm
**Style:** Documentary narration, not marketing. "The system retrieves..." not "Our amazing system retrieves..."

**Music:** None (clean technical presentation). Optional: subtle ambient hum (40Hz) under title cards only.

**SFX:** Subtle UI sounds on diagram builds (soft "tick" on node appear, "whoosh" on edge draw) — very low mix (-24dB).