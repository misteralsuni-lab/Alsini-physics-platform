-- ======================================================================================
-- MIGRATION 6: resource_chunks — pgvector Embeddings for Hybrid Retrieval
-- ======================================================================================
-- Creates a chunked-embedding table linked to resources for pgvector-based
-- semantic search. Each row holds a text chunk from a resource's semantic
-- content, its 1024-dimensional embedding vector (NVIDIA NV-Embed-QA), and
-- metadata for source traceability.
--
-- Prerequisites:
--   - mig_1_tables.sql (resources table must exist)
--   - pgvector extension must be enabled on the Supabase project
--     (CREATE EXTENSION IF NOT EXISTS vector;)
--
-- Run order: AFTER mig_5_resource_assets.sql
-- ======================================================================================

-- 1. Enable pgvector extension (idempotent)
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

-- 2. Create the resource_chunks table
CREATE TABLE IF NOT EXISTS public.resource_chunks (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id     UUID            NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    chunk_index     INTEGER         NOT NULL,
    chunk_text      TEXT            NOT NULL,
    chunk_type      VARCHAR(50)     NOT NULL DEFAULT 'concept',
    -- chunk_types: 'concept', 'question', 'formula', 'definition',
    --              'relation', 'page_text', 'metadata'
    embedding       vector(1024)    NOT NULL,
    source_refs     JSONB           DEFAULT '{}'::jsonb,
    -- source_refs: {"concept_id": "...", "question_id": "Q4", "page": 2, ...}
    token_count     INTEGER,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Foreign key: each chunk MUST belong to an existing resource
-- (inline FK above)

-- 4. Indexes
-- B-tree for relational lookups
CREATE INDEX IF NOT EXISTS idx_resource_chunks_resource_id  ON public.resource_chunks(resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_chunks_chunk_type   ON public.resource_chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_resource_chunks_chunk_index  ON public.resource_chunks(resource_id, chunk_index);

-- HNSW (Hierarchical Navigable Small World) index for fast approximate nearest-neighbor search
-- Uses cosine distance operator (<=>) which is the pgvector default.
-- m=16 is a good balance for up to ~100K vectors; ef_construction=200 for build quality.
CREATE INDEX IF NOT EXISTS idx_resource_chunks_embedding_hnsw
    ON public.resource_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- 5. Enable RLS (Row Level Security)
ALTER TABLE public.resource_chunks ENABLE ROW LEVEL SECURITY;

-- 6. RLS Policies
-- Public read: anyone can read chunks + embeddings (needed for vector search)
CREATE POLICY "resource_chunks_public_read" ON public.resource_chunks
    FOR SELECT USING (true);

-- Authenticated write: backend service role can insert/update/delete
CREATE POLICY "resource_chunks_authenticated_write" ON public.resource_chunks
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 7. Column comments for documentation
COMMENT ON TABLE public.resource_chunks IS 'Chunked embeddings of resource semantic content for pgvector hybrid retrieval. Each row = one text chunk + its 1024-dim NV-Embed-QA vector.';
COMMENT ON COLUMN public.resource_chunks.chunk_index IS 'Position of this chunk within the resource (0-based, for ordering)';
COMMENT ON COLUMN public.resource_chunks.chunk_text IS 'The raw text chunk that was embedded';
COMMENT ON COLUMN public.resource_chunks.chunk_type IS 'Type tag for filtering: concept, question, formula, definition, relation, page_text, metadata';
COMMENT ON COLUMN public.resource_chunks.embedding IS '1024-dimensional embedding vector from NVIDIA NV-Embed-QA (or compatible model)';
COMMENT ON COLUMN public.resource_chunks.source_refs IS 'JSONB tracing info: concept_id, question_id, page, spec_point, etc.';
COMMENT ON COLUMN public.resource_chunks.token_count IS 'Approximate token count of chunk_text (pre-embedding diagnostic)';