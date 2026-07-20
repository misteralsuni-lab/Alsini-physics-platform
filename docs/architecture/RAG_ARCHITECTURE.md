# Retrieval Architecture

---

## Philosophy

Retrieve first. Generate second.

Every AI response must be grounded in retrieved curriculum content. The RAG pipeline is the single source of truth for all curriculum knowledge. The LLM's role is to interpret, explain, and guide — not to recall.

---

## Pipeline

```
PDF
  ↓
Semantic Parser (PyMuPDF + master_ingestion.py)
  ↓
Structured JSON (OpenKB knowledge graph)
  ↓
Chunking (embedding_pipeline.py — by node type)
  ↓
Embedding (NVIDIA NV-EmbedQA-E5-V5, 1024-dim)
  ↓
pgvector (resource_chunks table, HNSW index)
  ↓
Hybrid Search (vector cosine similarity + relational/keyword)
  ↓
Context Assembly (top-5 chunks + figures + formulas + metadata)
  ↓
LLM (NVIDIA Llama 3.3 or Gemini 2.5 Flash)
  ↓
Student (response with compact citations)
```

---

## Retrieval

Uses:

- **Semantic similarity** — pgvector cosine similarity on 1024-dim embeddings
- **Metadata filtering** — `filter_resource_id` scopes retrieval to current resource
- **Specification point linking** — chunks retain spec point references
- **Chunk type filtering** — filter by concept, formula, definition, relation, question
- **Resource ID** — each chunk belongs to exactly one resource

---

## Chunk Types

| Type | Description | Example Citation |
|------|-------------|-----------------|
| Concept | Core concept explanation | SRC-C05 |
| Formula | Equation with variables defined | EQ-03 |
| Definition | Precise term definition | SRC-D12 |
| Relationship | How concepts relate | SRC-R07 |
| Question | Practice question | Q-04 |
| Worked Example | Step-by-step solution | WE-02 |
| Figure | Reference to diagram/graph | FIG-04 |
| Table | Reference to data table | TAB-01 |

---

## Context Assembly

```
Top chunks (top-5 by similarity)
  +
Relevant figures (matched from chunk metadata)
  +
Relevant formulas (matched from chunk metadata)
  +
Metadata (resource_id, spec point, page number)
  ↓
Formatted context string (~400-600 chars)
  ↓
Injected into LLM system prompt
```

**Context format:**
```
Retrieved educational context (from {resource_title}):
  [1] (concept) [concept: Acceleration]  Concept: Acceleration. The rate of change...
  [2] (relation) [concept: Velocity]  Velocity is related to: Speed, Displacement...
  [3] (formula) [concept: Acceleration]  Formula: a = Δv / Δt ...
```

---

## Assets

Assets are independent objects stored in Supabase Storage:

- PDF worksheets
- Graphs
- Figures
- Tables (rendered as images)
- Diagrams
- Photographs

Assets are retrieved separately via `GET /api/resources/{id}/assets` and linked to chunks via metadata.

---

## Traceability

Every answer must be traceable to:

- Original resource (UUID and title)
- Chunk (ID and type)
- Page number (PDF page)
- Specification point
- Asset (if applicable)
- Similarity score

---

## Developer Mode

Developer mode expands citations into full provenance:

```
Compact:  SRC-A12
Expanded: Resource: Forces and Motion (5729d034-...)
         Chunk: 2a647677-... (concept)
         Similarity: 0.4526
         Spec: 1.2.3 (Force and acceleration)
         Page: p.3
         Asset: FIG-04 (Distance-time graph)
```

**Display rules:**
- Students see only compact citations (clickable chips)
- Developers see expanded provenance when dev mode is enabled
- Toggle controlled by `devMode` state in InteractiveTutor

---

## Technical Details

| Component | Implementation |
|-----------|---------------|
| Embedding model | NVIDIA NV-EmbedQA-E5-V5 (1024-dim) |
| Vector index | pgvector HNSW (m=16, ef_construction=200) |
| Distance metric | Cosine similarity |
| Match count | 5 chunks per query (configurable) |
| Fallback | Empty context → tutor answers without retrieval |
| History | Conversation history passed separately (not RAG'd) |

---

## Future

- Cross-resource retrieval (search across all resources, not just current one)
- Lesson retrieval
- Worksheet retrieval
- Quiz retrieval
- Teacher analytics (misconception patterns across cohort)
- Curriculum analytics (which spec points are hardest for students)
- Multi-modal retrieval (text + diagram + graph reasoning)
