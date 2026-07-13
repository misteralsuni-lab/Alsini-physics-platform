-- ======================================================================================
-- MIGRATION 7: match_resource_chunks — pgvector similarity search RPC function
-- ======================================================================================
-- Creates a Postgres function (callable via Supabase RPC / PostgREST) that performs
-- cosine similarity search against the resource_chunks table.
--
-- The function:
--   1. Takes a query embedding vector (1024-dim) and a match_count limit
--   2. Computes cosine distance (<=>) against all chunk embeddings
--   3. Returns the top-N nearest chunks with their distance scores and resource metadata
--
-- Called from FastAPI via: POST /rest/v1/rpc/match_resource_chunks
--
-- Prerequisites:
--   - mig_6_resource_chunks.sql (resource_chunks table + HNSW index)
--
-- Run order: AFTER mig_6_resource_chunks.sql
-- ======================================================================================

CREATE OR REPLACE FUNCTION public.match_resource_chunks(
    query_embedding    vector(1024),
    match_count        INTEGER DEFAULT 10,
    filter_resource_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id              UUID,
    resource_id     UUID,
    chunk_index     INTEGER,
    chunk_text      TEXT,
    chunk_type      VARCHAR(50),
    source_refs     JSONB,
    token_count     INTEGER,
    similarity      FLOAT  -- 1 - cosine_distance (higher = better)
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        rc.id,
        rc.resource_id,
        rc.chunk_index,
        rc.chunk_text,
        rc.chunk_type,
        rc.source_refs,
        rc.token_count,
        1 - (rc.embedding <=> query_embedding) AS similarity
    FROM public.resource_chunks rc
    WHERE
        (filter_resource_id IS NULL OR rc.resource_id = filter_resource_id)
    ORDER BY rc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Allow anon to call the function (search is public)
GRANT EXECUTE ON FUNCTION public.match_resource_chunks(vector(1024), INTEGER, UUID)
    TO anon, authenticated;

COMMENT ON FUNCTION public.match_resource_chunks IS 'pgvector cosine similarity search over resource_chunks. Returns top-N nearest chunks with similarity score (1=identical, 0=orthogonal). Pass NULL for filter_resource_id to search across all resources.';