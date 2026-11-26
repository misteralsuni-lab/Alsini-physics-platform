# ADR-0001: Marp Markdown as Single Authoring Source of Truth

- **Status:** Accepted
- **Date:** 2026-11-26

## Decision

Use a single Marp Markdown file per lesson in `content/lessons/` as the canonical authoring source for both interactive student Learning Blocks and RAG chunks. The parser automatically strips teacher choreography cues (such as `"Hands down"` and partner prompts) and converts `Gate:` lines into inline solo remediation, while supporting progressive zero-render HTML comment directives (`<!-- student:analogy -->`, `<!-- student:reflection -->`, `<!-- widget:... -->`, `<!-- teacher-only -->`) so classroom slide projection remains intact.

## Considered Options

- **Dual-source authoring (separate Marp slides and VLE JSON files):** Rejected because curriculum edits rapidly drift across two representations.
- **Pure Marp + companion `.vle.json` sidecar files:** Rejected because separating analogies, reflections, and widget bindings from the `.md` lesson file reintroduces cross-file synchronization overhead.
