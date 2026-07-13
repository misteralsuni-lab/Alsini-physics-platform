# HANDOFF_SESSION_3.md

## Session 3 Handoff Document — Hybrid Retrieval Foundation

**Milestone:** 2 — Resource Delivery Layer (Hybrid Retrieval Foundation — COMPLETE)
**Date:** 2026-07-13
**Branch:** `multimodalragsystem`
**Previous commits:** `b871b9f` (embedding pipeline + mig_6), `cc9f2b1` (search endpoints + mig_7)

---

## Executive Summary

The hybrid retrieval foundation is complete. The system can now perform both
pure semantic (vector) search and combined relational + vector search over
resource content chunks stored in pgvector.

The infrastructure consists of:
1. A `resource_chunks` database table with a 1024-dimensional `vector` column
   for embeddings, HNSW index for fast approximate nearest-neighbor search, and
   RLS policies (mig_6, applied).
2. A `match_resource_chunks` Postgres RPC function that performs cosine
   similarity search and returns ranked results with similarity scores
   (mig_7, applied).
3. An embedding pipeline module (`embedding_pipeline.py`) that chunks resource
   semantic JSON content, generates embeddings via NVIDIA NV-EmbedQA-E5-V5
   (1024-dim), and stores them in `resource_chunks`.
4. Two FastAPI search endpoints:
   - `POST /api/search` — pure vector (semantic) search
   - `POST /api/search/hybrid` — combined relational + vector search with
     merge, deduplication, and relevance boosting
5. Integration into `master_ingestion.py` — embeddings are auto-generated
   after the semantic JSON push, alongside the visual asset pipeline.

All searches were verified end-to-end against the Golden Dataset (21 chunks
embedded, query "How does velocity relate to displacement?" correctly returned
velocity/displacement-related chunks with similarity scores 0.34–0.50).

---

## Completed Work

### 1. Database Migration — `resource_chunks` table (mig_6)

- **Status:** Applied and verified.
- **Schema:** 8-column table with UUID primary key, FK to `resources(id)` with
  `ON DELETE CASCADE`, `vector(1024)` embedding column, JSONB `source_refs`
  for source traceability.
- **Index:** HNSW (Hierarchical Navigable Small World) index with
  `vector_cosine_ops` operator class, `m=16`, `ef_construction=200`.
- **RLS:** Public read + authenticated write policies.
- **File:** `migrations/mig_6_resource_chunks.sql`

### 2. Database Migration — `match_resource_chunks` RPC (mig_7)

- **Status:** Applied and verified.
- **Function:** `match_resource_chunks(query_embedding vector(1024), match_count integer, filter_resource_id uuid)`
- **Returns:** Top-N chunks with `similarity` score (1 - cosine_distance, higher = better).
- **Callable via:** `POST /rest/v1/rpc/match_resource_chunks`
- **File:** `migrations/mig_7_match_function.sql`

### 3. Embedding Pipeline — `embedding_pipeline.py`

- **Status:** Complete and tested.
- **Model:** `nvidia/nv-embedqa-e5-v5` (1024-dim embeddings via NVIDIA API).
   - Note: `nvidia/embed-qa-4` returned 404 on this account; `nv-embed-v1` works
     but produces 4096-dim vectors which would need a schema change. The
     `nv-embedqa-e5-v5` model is the correct choice for 1024-dim.
- **Chunking strategy:** OpenKB concept nodes are split by type:
  - `concept` — title + definition (≤1000 chars)
  - `formula` — formula text
  - `definition` — long definition splits (>1000 chars)
  - `relation` — related concepts
- **Idempotent:** Re-running deletes existing chunks before re-embedding.
- **CLI:** `python backend/pipeline/embedding_pipeline.py --resource-id <uuid>`
  or `--verify` to inspect existing chunks.
- **File:** `backend/pipeline/embedding_pipeline.py`

### 4. FastAPI Search Endpoints

#### `POST /api/search` — Pure Vector (Semantic) Search

- **Request:** `{"query": "natural language text", "match_count": 10, "filter_resource_id": null}`
- **Flow:** Embed query → call `match_resource_chunks` RPC → return ranked chunks.
- **Response:** `{"query": "...", "results": [...], "count": N, "search_type": "semantic"}`

#### `POST /api/search/hybrid` — Combined Relational + Vector Search

- **Request:** `{"query": "...", "match_count": 10, "resource_id": null, "spec_point_id": null, "chunk_type": null}`
- **Flow:**
  1. Vector search via RPC (fetches 2× match_count for merge headroom)
  2. Relational search via PostgREST (filter by `chunk_type` and/or `spec_point_id`)
  3. Merge & deduplicate by chunk ID
  4. Boost: chunks appearing in both result sets get +0.1 similarity
  5. Sort: boosted first, then by similarity descending
- **Response:** `{"query": "...", "results": [...], "count": N, "search_type": "hybrid", "vector_count": V, "relational_count": R}`

### 5. Master Ingestion Integration

- **Status:** Complete.
- **Location:** `master_ingestion.py`, section "3b. Chunk Embedding Pipeline"
- **Behaviour:** After `push_to_supabase()`, the embedding pipeline runs
  automatically. It is non-fatal — if NVIDIA API is unavailable, the rest
  of the pipeline (visual assets) continues.

---

## Verified Test Results

### Test 1: Semantic Search
- **Query:** "How does velocity relate to displacement?"
- **Results:** 5 chunks, similarity 0.34–0.50
- **Top match:** "Displacement is related to: Velocity, Speed" (sim=0.4970)
- **Verdict:** Correctly identifies velocity/displacement/relation chunks.

### Test 2: Hybrid Search (chunk_type=formula filter)
- **Query:** same
- **Vector results:** 10, Relational results (formulas): 3
- **Merged:** 10 chunks (deduplication working correctly)
- **Boosting:** Formula chunks that appeared in both sets were boosted +0.1

---

## What Was NOT Done (Out of Scope for Session 2)

These items are candidates for Session 3:

1. **Frontend search UI** — the search endpoints exist but the frontend
   (`InteractiveTutor.jsx`) doesn't call them yet. The chat still uses
   `fetch_forces_and_motion_data()` which returns the entire resource content
   as context. A search bar or context-aware retreival could call
   `/api/search` to fetch only relevant chunks.

2. **Tutor integration with RAG** — the `/api/tutor` endpoint currently dumps
   the entire OpenKB JSON into the system prompt. With hybrid search now
   available, the tutor could embed the student's question, search for
   relevant chunks, and inject only those chunks as context (true RAG).

3. **Express-FastAPI unification** — Express (`server.js`) and FastAPI
  (`main.py`) run on separate ports (5000 vs 8000). The Express server
  routes `/api/chat` to the chatbot. The frontend calls both directly.
  Consider unifying or adding a reverse proxy.

4. **Resource listing/search endpoint** — no `GET /api/resources` endpoint
   exists for listing all resources or searching by title. The frontend
   fetches by `specification_point_id` via Supabase directly.

5. **Re-embedding on update** — the embedding pipeline runs during
   `master_ingestion.py` but there's no hook for re-embedding when a
   resource's content is updated outside the ingestion pipeline.

---

## Database Migrations Applied

| Migration | Description | Status |
|-----------|-------------|--------|
| mig_6_resource_chunks.sql | resource_chunks table + HNSW index | Applied |
| mig_7_match_function.sql | match_resource_chunks RPC function | Applied |

## Commit History (Session 2)

| Commit | Description |
|--------|-------------|
| `b871b9f` | feat: Add resource chunk embedding pipeline and migration for pgvector support |
| `cc9f2b1` | feat: Add hybrid retrieval endpoints (semantic + hybrid search) and integrate embedding pipeline into master ingestion |

---

## Architecture Diagram (Text)

```
PDF → master_ingestion.py → ┌→ Semantic JSON → push_to_supabase() → resources.content
                             │
                             ├→ embedding_pipeline.py → chunk → NVIDIA embed → resource_chunks
                             │
                             └→ run_asset_pipeline.py → Storage → resource_assets


                     ┌─ POST /api/search ──────────────────────────────────────┐
                     │  query → NVIDIA embed → match_resource_chunks RPC      │
                     │  → top-N chunks with similarity scores                 │
                     └────────────────────────────────────────────────────────┘

                     ┌─ POST /api/search/hybrid ─────────────────────────────┐
                     │  query → NVIDIA embed → match_resource_chunks RPC      │
                     │  + relational filters (chunk_type, spec_point_id)    │
                     │  → merge + dedup + boost → sorted combined results    │
                     └────────────────────────────────────────────────────────┘
```

---

## Quick Start for Session 3

1. **Verify the server starts:**
   ```bash
   cd /home/alsuni/Alsini-physics-platform
   backend/.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```

2. **Test semantic search:**
   ```bash
   curl -X POST http://localhost:8000/api/search \
     -H "Content-Type: application/json" \
     -d '{"query": "What is Newton second law?", "match_count": 5}'
   ```

3. **Test hybrid search:**
   ```bash
   curl -X POST http://localhost:8000/api/search/hybrid \
     -H "Content-Type: application/json" \
     -d '{"query": "acceleration formula", "match_count": 5, "chunk_type": "formula"}'
   ```

4. **Re-embed a resource:**
   ```bash
   backend/.venv/bin/python backend/pipeline/embedding_pipeline.py \
     --resource-id 5729d034-a6c7-4f35-b81c-fcac447289c7
   ```

5. **Verify existing chunks:**
   ```bash
   backend/.venv/bin/python backend/pipeline/embedding_pipeline.py \
     --resource-id 5729d034-a6c7-4f35-b81c-fcac447289c7 --verify
   ```