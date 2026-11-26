# ADR-0004: Client-Side Physics Simulations and VMR AI Tutor Debrief

- **Status:** Accepted
- **Date:** 2026-11-26

## Decision

Build zero-dependency client-side React/SVG/Canvas kinematics components (Touchable `d-t`/`v-t` Graphs and the Dual-Mode Spec 1.5 Ramp + 50 Hz Ticker-Timer Simulation) styled to `DESIGN.md` so the `1.1 MB` bundle does not grow and oscilloscope visuals stay exact. Pair every practical simulation with a structured **VMR (Vary, Measure, Repeat)** Edexcel AO3 AI Tutor debrief consuming live telemetry through `LearningContext.interactive_state`.

## Considered Options

- **Third-party charting or physics libraries:** Rejected because they add bundle bloat, conflict with `DESIGN.md` visual rules, and limit custom caliper and tape-cutter interactions.
- **Embedded external simulations or iframes:** Rejected because cross-origin sandboxes block live trial telemetry sync into `InteractiveTutor.jsx`.
- **Free-form post-lab chat without VMR AO3 scaffolding:** Rejected because students need structured coaching on Edexcel Vary, Measure, and Repeat marking points.
