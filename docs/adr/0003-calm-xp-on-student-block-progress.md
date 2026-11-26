# ADR-0003: Calm XP and Soft-Gated Completion on `student_block_progress`

- **Status:** Accepted
- **Date:** 2026-11-26

## Decision

Persist student Learning Block completion, self-check results, 1-line reflections, and flat per-block `xp_awarded` directly on an RLS owner-scoped `student_block_progress` table (`SUM(xp_awarded)`). Progress surfaces in one quiet `start.dev` / `supabase.com`-style lesson header bar with soft-gating (free browsing, inline `<80%` solo remediation, no streaks, no confetti, and no hard locks) to keep cognitive load low and schema minimal.

## Considered Options

- **Append-only `xp_events` ledger table + streak/badge engine:** Rejected as unnecessary schema complexity and distracting gamification for calm self-study.
- **Ephemeral client-side or session-only React state:** Rejected because students lose completion status and reflections across reloads.
- **Hard-gated linear unlocking between blocks:** Rejected because locking blocks prevents non-linear revision and undermines learner agency.
