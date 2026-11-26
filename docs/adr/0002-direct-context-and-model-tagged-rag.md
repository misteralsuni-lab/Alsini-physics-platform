# ADR-0002: Direct Structured Context and Model-Tagged Hybrid RAG

- **Status:** Accepted
- **Date:** 2026-11-26

## Decision

Keep `LearningContext` as the single AI Tutor context carrier by adding a strictly typed `interactive_state` payload (for live graph calipers, self-checks, and simulation trials, with allowlisted server-resolved `formula_ref` while preserving fail-closed static PDF `focused_asset` verification). Add `embedding_model VARCHAR(120)` to `resource_chunks` so chapter-scoped hybrid retrieval (`match_chapter_chunks`) matches only active-model vectors (`nvidia/nemotron-3.5-embed-1b`) with deterministic lexical fallback, and drop the redundant B-tree indexes `idx_resource_chunks_resource_id` and `idx_spec_points_code`.

## Considered Options

- **Parallel context endpoints or channels per UI surface:** Rejected because it fragments provenance and breaks Session 4A.2 single-carrier guarantees.
- **Heuristic similarity-floor filtering (`VECTOR_MIN_RELEVANCE = 0.15`) without tracking `embedding_model`:** Rejected because mixed embedding spaces can still inject cosine noise or mask retrieval failures.
- **Polymorphic RAG tables decoupled from `resources`:** Rejected to avoid rewriting existing search, asset, and citation joins.
