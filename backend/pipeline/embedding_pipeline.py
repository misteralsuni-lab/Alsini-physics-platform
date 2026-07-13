"""
embedding_pipeline.py — Resource Chunk Embedding Pipeline (pgvector)

Chunks the semantic JSON content of a resource into text segments,
generates 1024-dimensional embeddings via NVIDIA NV-EmbedQA-E5-V5,
and stores them in the `resource_chunks` table for pgvector cosine
similarity search.

This is the embedding half of the hybrid retrieval architecture:
    resources.content JSON
        → chunker (split by concepts, questions, formulas)
        → NVIDIA embedding API
        → resource_chunks table (with HNSW index)

The retrieval half lives in the FastAPI search endpoints (main.py).

Usage:
    from pipeline.embedding_pipeline import embed_resource
    embed_resource(resource_id, supabase_url, supabase_key, nvidia_key)

Or CLI:
    python backend/pipeline/embedding_pipeline.py --resource-id <uuid>
"""

import json
import os
import sys
import argparse
import requests
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

# ------------------------------------------------------------------
# Tunables
# ------------------------------------------------------------------

EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"
EMBED_DIM = 1024
MAX_CHUNK_CHARS = 1000  # rough boundary — chunk before this length

# ------------------------------------------------------------------
# Chunking logic
# ------------------------------------------------------------------

def _chunk_openkb_list(content: list) -> list[dict]:
    """
    Chunk a list of OpenKB concept nodes (the format produced by
    master_ingestion.py's compile_openkb()).

    Each concept node becomes one chunk. If a definition is long,
    it is split across multiple chunks.
    """
    chunks: list[dict] = []
    idx = 0

    for node in content:
        if not isinstance(node, dict):
            continue

        concept = node.get("concept", "")
        definition = node.get("definition", "")
        formula = node.get("formula", "")
        related = node.get("related_concepts", [])

        # --- Concept title chunk ---
        chunks.append({
            "chunk_index": idx,
            "chunk_text": f"Concept: {concept}. {definition[:MAX_CHUNK_CHARS]}",
            "chunk_type": "concept",
            "source_refs": {
                "concept": concept,
                "has_formula": bool(formula),
                "related": related[:5],
            },
        })
        idx += 1

        # --- Formula chunk (if present) ---
        if formula and formula.strip():
            chunks.append({
                "chunk_index": idx,
                "chunk_text": f"Formula for {concept}: {formula}",
                "chunk_type": "formula",
                "source_refs": {"concept": concept, "formula": formula},
            })
            idx += 1

        # --- Long definition splits ---
        remaining_def = definition[MAX_CHUNK_CHARS:]
        while len(remaining_def) > 100:
            chunks.append({
                "chunk_index": idx,
                "chunk_text": remaining_def[:MAX_CHUNK_CHARS],
                "chunk_type": "definition",
                "source_refs": {"concept": concept},
            })
            remaining_def = remaining_def[MAX_CHUNK_CHARS:]
            idx += 1

        # --- Related concepts chunk ---
        if related:
            chunks.append({
                "chunk_index": idx,
                "chunk_text": f"{concept} is related to: {', '.join(related)}",
                "chunk_type": "relation",
                "source_refs": {"concept": concept, "related": related},
            })
            idx += 1

    return chunks


def _chunk_generic_content(content) -> list[dict]:
    """
    Fallback chunker for content that isn't the expected OpenKB list
    format (dicts, strings, etc.).
    """
    if isinstance(content, str):
        # Split the string into ~MAX_CHUNK_CHARS segments
        chunks = []
        for i in range(0, len(content), MAX_CHUNK_CHARS):
            seg = content[i:i + MAX_CHUNK_CHARS]
            if seg.strip():
                chunks.append({
                    "chunk_index": i // MAX_CHUNK_CHARS,
                    "chunk_text": seg,
                    "chunk_type": "page_text",
                    "source_refs": {},
                })
        return chunks

    if isinstance(content, dict):
        chunks = []
        idx = 0
        for key, val in content.items():
            text = str(val)[:MAX_CHUNK_CHARS]
            if text.strip():
                chunks.append({
                    "chunk_index": idx,
                    "chunk_text": f"[{key}]: {text}",
                    "chunk_type": "metadata",
                    "source_refs": {"key": key},
                })
                idx += 1
        return chunks

    # Unrecognised → single chunk
    return [{
        "chunk_index": 0,
        "chunk_text": str(content)[:MAX_CHUNK_CHARS],
        "chunk_type": "page_text",
        "source_refs": {},
    }]


def chunk_resource_content(content) -> list[dict]:
    """
    Entry point: accept any content shape and return a list of
    {chunk_index, chunk_text, chunk_type, source_refs} dicts.
    """
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return _chunk_generic_content(content)
        content = parsed

    if isinstance(content, list):
        return _chunk_openkb_list(content)

    return _chunk_generic_content(content)


# ------------------------------------------------------------------
# Embedding helpers
# ------------------------------------------------------------------

def _embed_texts(texts: list[str], nvidia_key: str,
                 model: str = EMBED_MODEL) -> list[list[float]]:
    """
    Call NVIDIA embedding API to vectorise a batch of texts.
    Returns a list of embedding vectors (each a list of floats).
    """
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=nvidia_key,
    )

    all_vectors: list[list[float]] = []
    batch_size = 32

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = client.embeddings.create(
            model=model,
            input=batch,
            encoding_format="float",
            extra_body={"input_type": "passage", "truncate": "END"},
        )
        for item in resp.data:
            all_vectors.append(item.embedding)

    return all_vectors


def _vector_to_pg_string(vec: list[float]) -> str:
    """Convert a float list to pgvector literal format: '[0.1,0.2,...]'"""
    return f"[{','.join(str(round(v, 8)) for v in vec)}]"


# ------------------------------------------------------------------
# DB operations (via PostgREST — matching existing project pattern)
# ------------------------------------------------------------------

def _supabase_headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _delete_existing_chunks(resource_id: str, supabase_url: str,
                            supabase_key: str) -> int:
    """Delete existing chunks for a resource (idempotent re-embed)."""
    h = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    endpoint = f"{supabase_url}/rest/v1/resource_chunks?resource_id=eq.{resource_id}"
    resp = requests.delete(endpoint, headers=h, timeout=15)
    return 0 if resp.status_code in (200, 204) else resp.status_code


def _insert_chunks(chunks_with_vecs: list[dict], supabase_url: str,
                   supabase_key: str) -> int:
    """
    Insert rows into resource_chunks. Each item must have:
      resource_id, chunk_index, chunk_text, chunk_type, embedding (as pg string), source_refs
    Returns count of successfully inserted rows.
    """
    if not chunks_with_vecs:
        return 0

    h = _supabase_headers(supabase_key)
    endpoint = f"{supabase_url}/rest/v1/resource_chunks"

    inserted = 0
    # PostgREST supports batch insert as JSON array
    payload = []
    for c in chunks_with_vecs:
        payload.append({
            "resource_id": c["resource_id"],
            "chunk_index": c["chunk_index"],
            "chunk_text": c["chunk_text"],
            "chunk_type": c["chunk_type"],
            "embedding": c["embedding"],  # pgvector literal string
            "source_refs": c.get("source_refs", {}),
            "token_count": len(c["chunk_text"].split()) if "token_count" not in c else c["token_count"],
        })

    # PostgREST can handle arrays of up to ~50 rows comfortably
    batch_size = 40
    for i in range(0, len(payload), batch_size):
        batch = payload[i:i + batch_size]
        resp = requests.post(endpoint, headers=h, json=batch, timeout=30)
        if resp.status_code == 201:
            inserted += len(resp.json())
        else:
            # Fall back to single inserts if batch fails
            for row in batch:
                resp2 = requests.post(endpoint, headers=h, json=row, timeout=15)
                if resp2.status_code == 201:
                    inserted += 1

    return inserted


# ------------------------------------------------------------------
# Main pipeline
# ------------------------------------------------------------------

def embed_resource(resource_id: str, supabase_url: str,
                   supabase_key: str, nvidia_key: str) -> dict:
    """
    Chunk a resource's semantic content, embed the chunks, and store
    them in resource_chunks.

    Returns: {chunked: int, embedded: int, stored: int}
    """
    # 1. Fetch resource content
    h = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    endpoint = f"{supabase_url}/rest/v1/resources?id=eq.{resource_id}&select=content,title"
    resp = requests.get(endpoint, headers=h, timeout=15)
    if resp.status_code != 200 or not resp.json():
        raise RuntimeError(f"Cannot fetch resource {resource_id}")

    row = resp.json()[0]
    content = row.get("content")
    title = row.get("title", "")

    if not content:
        return {"chunked": 0, "embedded": 0, "stored": 0}

    # Parse content if needed
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            pass

    # 2. Chunk
    chunks = chunk_resource_content(content)
    print(f"  Chunked into {len(chunks)} segments "
          f"(types: {set(c['chunk_type'] for c in chunks)})")

    if not chunks:
        return {"chunked": 0, "embedded": 0, "stored": 0}

    # 3. Embed
    texts = [c["chunk_text"] for c in chunks]
    print(f"  Embedding {len(texts)} chunks via {EMBED_MODEL}...")
    vectors = _embed_texts(texts, nvidia_key)
    print(f"  Received {len(vectors)} embedding vectors (dim={len(vectors[0])})")

    # 4. Assemble payload
    rows = []
    for chunk, vec in zip(chunks, vectors):
        rows.append({
            "resource_id": resource_id,
            "chunk_index": chunk["chunk_index"],
            "chunk_text": chunk["chunk_text"],
            "chunk_type": chunk["chunk_type"],
            "embedding": _vector_to_pg_string(vec),
            "source_refs": chunk.get("source_refs", {}),
            "token_count": len(chunk["chunk_text"].split()),
        })

    # 5. Delete existing (idempotent)
    _delete_existing_chunks(resource_id, supabase_url, supabase_key)

    # 6. Insert
    print(f"  Inserting {len(rows)} rows into resource_chunks...")
    inserted = _insert_chunks(rows, supabase_url, supabase_key)
    print(f"  Inserted {inserted}/{len(rows)} rows")

    return {
        "chunked": len(chunks),
        "embedded": len(vectors),
        "stored": inserted,
    }


def verify_chunks(resource_id: str, supabase_url: str,
                  supabase_key: str) -> list[dict]:
    """Query resource_chunks for a given resource_id — for verification."""
    h = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    endpoint = (
        f"{supabase_url}/rest/v1/resource_chunks"
        f"?resource_id=eq.{resource_id}"
        f"&select=id,chunk_index,chunk_type,chunk_text,token_count"
        f"&order=chunk_index.asc"
    )
    resp = requests.get(endpoint, headers=h, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"Verify query failed ({resp.status_code}): {resp.text[:300]}")
    return resp.json()


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run the chunk embedding pipeline for a resource."
    )
    parser.add_argument("--resource-id", type=str,
                        default="5729d034-a6c7-4f35-b81c-fcac447289c7",
                        help="UUID of the resource to embed")
    parser.add_argument("--env", type=str, default=None,
                        help="Path to .env file")
    parser.add_argument("--verify", action="store_true",
                        help="Only verify existing chunks (no embedding)")
    args = parser.parse_args()

    # Load env
    _backend = Path(__file__).resolve().parent.parent
    env_path = args.env or str(_backend / ".env")
    load_dotenv(env_path)

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    nvidia_key = os.getenv("NVIDIA_API_KEY")

    if not supabase_url or not supabase_key:
        print("ERROR: Missing Supabase credentials in backend/.env")
        sys.exit(1)

    if args.verify:
        rows = verify_chunks(args.resource_id, supabase_url, supabase_key)
        print(f"resource_chunks for {args.resource_id}: {len(rows)} rows")
        for r in rows:
            print(f"  [{r['chunk_index']}] {r['chunk_type']}: "
                  f"{r['chunk_text'][:80]}... ({r['token_count']} tokens)")
        return

    if not nvidia_key:
        print("ERROR: Missing NVIDIA_API_KEY for embeddings")
        sys.exit(1)

    result = embed_resource(args.resource_id, supabase_url, supabase_key, nvidia_key)
    print(f"\nDone: {result}")


if __name__ == "__main__":
    main()