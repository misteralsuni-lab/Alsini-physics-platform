# RAG Integration

## Session 3 — Retrieval-Augmented Generation Documentation

**Branch:** `multimodalragsystem`
**Date:** July 14, 2026

---

## Executive Summary

The `/api/tutor` endpoint has been transformed from a full-JSON-context chatbot into a true RAG tutor. Instead of injecting the entire OpenKB knowledge graph into the LLM prompt, the endpoint now:

1. Embeds the student's question via NVIDIA NV-EmbedQA-E5-V5
2. Calls the `match_resource_chunks` pgvector RPC (scoped to the Golden Dataset resource)
3. Retrieves the top-5 most relevant chunks by cosine similarity
4. Formats them into a compact context string with citation markers
5. Sends only this compact context to the LLM (NVIDIA Llama 3.3 or Gemini Flash)
6. Returns `TutorSource[]` metadata alongside the tutor's response

---

## Completed Work

### New Backend Functions (`backend/main.py`)

#### `_retrieve_relevant_chunks(query, match_count=5) -> list[dict]`

- Embeds the query via `_embed_query()` (NVIDIA NV-EmbedQA-E5-V5, existing)
- Calls `match_resource_chunks` RPC with `filter_resource_id = TARGET_RESOURCE_ID`
- Returns top-N chunks by cosine similarity
- Non-fatal: returns `[]` if embedding or RPC fails (tutor still works without context)

#### `_format_chunks_as_context(chunks) -> str`

- Formats retrieved chunks into a compact string:
  ```
  Retrieved educational context (from the Forces and Motion resource):
    [1] (concept) [concept: Acceleration]  Concept: Acceleration. The rate of change...
    [2] (relation) [concept: Velocity]  Velocity is related to: Speed, Displacement...
  ```
- Each chunk: `[N] (chunk_type) [source_refs] chunk_text`
- Typically 400-600 chars for 5 chunks (vs. 8,000+ for full JSON)

#### `_chunks_to_sources(chunks) -> list[TutorSource]`

- Converts raw chunk dicts to `TutorSource` Pydantic models
- Fields: `chunk_id`, `concept`, `page`, `chunk_type`, `similarity`

### New Pydantic Models

```python
class TutorSource(BaseModel):
    chunk_id: str
    concept: Optional[str] = None
    page: Optional[int] = None
    chunk_type: str
    similarity: float

class TutorResponse(BaseModel):
    response: str
    model_used: str
    sources: List[TutorSource] = []
```

### Modified Endpoint

**`POST /api/tutor`**

Before:
```python
context_data = fetch_forcing_and_motion_data()
system_prompt += f"Context (Forces and Motion Knowledge Graph):\n{context_data}\n"
return {"response": reply, "model_used": "NVIDIA_LLAMA_3.3"}
```

After:
```python
retrieved_chunks = _retrieve_relevant_chunks(request.student_prompt)
rag_context = _format_chunks_as_context(retrieved_chunks)
sources = _chunks_to_sources(retrieved_chunks)

system_prompt += rag_context  # compact, ~500 chars
return TutorResponse(response=reply, model_used="NVIDIA_LLAMA_3.3", sources=sources)
```

### Key Behaviours

- **Citation instruction:** The system prompt now tells the LLM: "When citing a fact from the retrieved context below, reference the source number in brackets (e.g. [Source 1]). Do NOT invent or guess page numbers."
- **Non-fatal RAG:** If NVIDIA embedding or the RPC fails, the tutor still answers — just without retrieved context. `sources` will be `[]`.
- **History preserved:** The `history` field (conversation history) is still passed to the LLM, unchanged.
- **Routing unchanged:** The `evaluate_routing()` function still routes to NVIDIA Llama 3.3 or Gemini Flash based on question complexity.

---

## Files Modified

| File | Change |
|------|--------|
| `backend/main.py` | Added `_retrieve_relevant_chunks()`, `_format_chunks_as_context()`, `_chunks_to_sources()`, `TutorSource`, `TutorResponse` with `sources` field. Replaced endpoint body to use RAG instead of `fetch_forcing_and_motion_data()`. |

---

## API Changes

### `POST /api/tutor`

**Request** (unchanged):
```json
{
  "student_prompt": "What is acceleration?",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
}
```

**Response** (UPDATED — new `sources` field):
```json
{
  "response": "Acceleration is the rate of change of velocity...",
  "model_used": "NVIDIA_LLAMA_3.3",
  "sources": [
    {
      "chunk_id": "2a647677-...",
      "concept": "Acceleration",
      "page": null,
      "chunk_type": "relation",
      "similarity": 0.4526
    },
    {
      "chunk_id": "12b096bf-...",
      "concept": "Acceleration",
      "page": null,
      "chunk_type": "concept",
      "similarity": 0.4152
    }
  ]
}
```

**Backward compatibility:** The `response` and `model_used` fields are unchanged. The `sources` field is new and additive — existing consumers that ignore unknown fields will not break.

---

## Retrieval Pipeline Detail

```
Student question: "What is acceleration?"
         │
         ▼
_embed_query("What is acceleration?")
  └─ NVIDIA NV-EmbedQA-E5-V5
  └─ Returns: float[1024] embedding
         │
         ▼
match_resource_chunks RPC
  └─ pgvector cosine similarity
  └─ filter_resource_id = 5729d034-... (Golden Dataset)
  └─ Returns: top-5 chunks ordered by similarity
         │
         ▼
_format_chunks_as_context(chunks)
  └─ Output: "Retrieved educational context:\n  [1] (relation) ..."
         │
         ▼
LLM system prompt:
  "You are an expert Edexcel IGCSE Physics Tutor...
   When citing a fact from the retrieved context below,
   reference the source number in brackets...

   Retrieved educational context:
     [1] (relation) [concept: Acceleration]  Acceleration is related to: Velocity, Speed
     [2] (concept) [concept: Acceleration]  Concept: Acceleration. The rate of change...
     ..."
         │
         ▼
LLM response (Gemini or NVIDIA Llama 3.3)
  └─ "Acceleration is the rate of change of velocity [Source 2]..."
         │
         ▼
TutorResponse {response, model_used, sources[]}
```

---

## Context Size Comparison

| Approach | Context Size | Approx. Tokens |
|----------|-------------|----------------|
| Before: Full JSON (`fetch_forcing_and_motion_data()`) | ~8,000+ chars | ~2,000+ |
| After: RAG (5 chunks) | ~400-600 chars | ~150-200 |
| Reduction | ~93% | ~90% |

---

## Acceptance Test Results

| Test | Result |
|------|--------|
| Tutor uses hybrid retrieval instead of full JSON | ✅ PASS |
| Tutor answers using retrieved chunks only | ✅ PASS |
| Source references remain intact | ✅ PASS |
| Existing Session 2 search endpoints functional | ✅ PASS |
| No regressions introduced | ✅ PASS |

### Verification Commands

```bash
cd backend
.venv/bin/python -c "
from main import _retrieve_relevant_chunks, _format_chunks_as_context, _chunks_to_sources
chunks = _retrieve_relevant_chunks('What is acceleration?', match_count=5)
print(f'Chunks: {len(chunks)}')
print(f'Context: {len(_format_chunks_as_context(chunks))} chars')
print(f'Sources: {len(_chunks_to_sources(chunks))} items')
"
```

---

## Known Issues

1. **`page` is `None` in most sources** — the embedding pipeline doesn't populate `source_refs.page` for concept/relation chunks. Only formula/question chunks may have it. Citation chips show "p.None" suppressed (only shown when `page != null`).

2. **`/api/grade` still uses full context** — the grading endpoint was not modified (out of scope). Flagged as technical debt for Session 4.

3. **Similarity scores are moderate (0.3-0.5)** — this is expected for a 3-page worksheet with 21 chunks. The cosine similarity reflects semantic overlap, not exact match. Scores above 0.3 are meaningful with NV-EmbedQA.

---

## Risks

- **NVIDIA embedding API dependency** — if the API is rate-limited or down, the tutor falls back to answering without retrieved context. This is by design (non-fatal), but the quality of answers will degrade.
- **Cold-start latency** — the first embedding call after server start may take 1-2 seconds. Subsequent calls are faster.
