-- =====================================================================================
-- MIGRATION 0: Baseline schema verification + RLS hardening (NON-DESTRUCTIVE)
-- =====================================================================================
-- SAFETY
--   This file contains NO `DROP TABLE`, NO `TRUNCATE`, and NO data deletion.
--   It is safe to run against the live Supabase project and against a fresh project.
--
--   NEVER run these files against Supabase:
--     - scratch/mig_1_tables.sql          (contains DROP TABLE ... CASCADE)
--     - Alsini_Physics_Schema_V1_Seed.sql (legacy courses -> topics schema)
--
-- PURPOSE
--   1. Recreate the unified curriculum schema on a fresh project without the
--      destructive scratch/mig_1_tables.sql.
--   2. Guarantee both `resources.content` (JSONB) and `resources.content_markdown`
--      (TEXT) exist. mig_5 only added content_markdown; the live project also has
--      an ad-hoc `content` column that the viewer selects.
--   3. Guarantee `resource_assets`, `resource_chunks`, `quiz_attempts`, and the
--      `match_resource_chunks` RPC exist.
--   4. Enable RLS on every application table and install deterministic policies.
--      Hardening: removes the broad `FOR ALL TO authenticated` write policies on
--      resource_assets/resource_chunks (the service role bypasses RLS, and no
--      client writes those tables). Drops the redundant live "New Policy" on
--      resources. Adds owner-only quiz_attempts policies.
--   5. Create/verify the public `resource-assets` Storage bucket (10 MB limit).
--
-- RUN ORDER
--   Fresh project   : run this file first, then the seed files
--                     scratch/mig_2_units_chapters.sql, scratch/mig_3_specs.sql,
--                     scratch/mig_4_activities_resources.sql.
--                     mig_5/mig_6/mig_7 and database/quiz_attempts_migration.sql are
--                     folded in here; do not run them afterwards (their
--                     CREATE POLICY statements are not idempotent).
--   Existing project: run this file alone. Every statement is idempotent and the
--                     policy cleanup is intentional.
--
-- VERIFIED LIVE (2026-11-23, read-only audit on project miezybwngeqdyqvvqcrl)
--   resources.content (jsonb) + content_markdown (text) present;
--   resource_assets/resource_chunks/match_resource_chunks present;
--   quiz_attempts MISSING; RLS enabled on the 8 existing app tables;
--   bucket resource-assets public, 10 MB, only 1/29 resources has original.pdf.
-- =====================================================================================

BEGIN;

-- -------------------------------------------------------------------------------------
-- 0. Extensions
-- -------------------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto') THEN
        CREATE EXTENSION pgcrypto;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        CREATE EXTENSION vector WITH SCHEMA public;
    END IF;
END $$;

-- -------------------------------------------------------------------------------------
-- 1. Base curriculum tables (non-destructive equivalent of scratch/mig_1_tables.sql)
-- -------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.units (
    id          UUID PRIMARY KEY,
    title       VARCHAR(255) NOT NULL UNIQUE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.chapters (
    id          UUID PRIMARY KEY,
    unit_id     UUID REFERENCES public.units(id) ON DELETE CASCADE,
    title       VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (unit_id, title)
);

CREATE TABLE IF NOT EXISTS public.specification_points (
    id                UUID PRIMARY KEY,
    chapter_id        UUID REFERENCES public.chapters(id) ON DELETE CASCADE,
    reference_code    VARCHAR(50) NOT NULL UNIQUE,
    description       TEXT NOT NULL,
    is_physics_only   BOOLEAN DEFAULT false,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.activities (
    id                      UUID PRIMARY KEY,
    specification_point_id  UUID REFERENCES public.specification_points(id) ON DELETE CASCADE,
    description             TEXT NOT NULL,
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.resources (
    id                      UUID PRIMARY KEY,
    specification_point_id  UUID REFERENCES public.specification_points(id) ON DELETE CASCADE,
    title                   VARCHAR(255) NOT NULL,
    content                 JSONB,
    content_markdown        TEXT,
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.questions (
    id                      UUID PRIMARY KEY,
    specification_point_id  UUID REFERENCES public.specification_points(id) ON DELETE CASCADE,
    question_pdf_url        TEXT,
    mark_scheme_pdf_url     TEXT,
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Existing deployments may predate either resources column (mig_1 had neither,
-- mig_5 added only content_markdown, and `content` was added ad-hoc in live).
ALTER TABLE public.resources ADD COLUMN IF NOT EXISTS content JSONB;
ALTER TABLE public.resources ADD COLUMN IF NOT EXISTS content_markdown TEXT;

-- -------------------------------------------------------------------------------------
-- 2. Asset infrastructure (equivalent of migrations/mig_5_resource_assets.sql)
-- -------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.resource_assets (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id         UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    page_number         INTEGER NOT NULL,
    asset_type          VARCHAR(50) NOT NULL,
    storage_path        TEXT NOT NULL,
    storage_url         TEXT NOT NULL,
    mime_type           VARCHAR(100) NOT NULL DEFAULT 'image/png',
    width               INTEGER,
    height              INTEGER,
    bounding_box        JSONB,
    caption             TEXT,
    linked_question_id  TEXT,
    content_verified    BOOLEAN DEFAULT false,
    metadata            JSONB DEFAULT '{}'::jsonb,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.resource_assets ADD COLUMN IF NOT EXISTS content_verified BOOLEAN DEFAULT false;
ALTER TABLE public.resource_assets ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- -------------------------------------------------------------------------------------
-- 3. Chunked embeddings (equivalent of migrations/mig_6_resource_chunks.sql)
-- -------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.resource_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id     UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    chunk_text      TEXT NOT NULL,
    chunk_type      VARCHAR(50) NOT NULL DEFAULT 'concept',
    embedding       vector(1024) NOT NULL,
    source_refs     JSONB DEFAULT '{}'::jsonb,
    token_count     INTEGER,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- -------------------------------------------------------------------------------------
-- 4. Quiz attempts (equivalent of database/quiz_attempts_migration.sql)
-- -------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.quiz_attempts (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    resource_id          UUID NOT NULL,
    question_index       INTEGER NOT NULL,
    student_answer       TEXT,
    score                FLOAT,
    max_score            INTEGER,
    ai_feedback          TEXT,
    last_question_index  INTEGER,
    created_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Guard columns for older quiz_attempts deployments.
ALTER TABLE public.quiz_attempts ADD COLUMN IF NOT EXISTS student_answer TEXT;
ALTER TABLE public.quiz_attempts ADD COLUMN IF NOT EXISTS score FLOAT;
ALTER TABLE public.quiz_attempts ADD COLUMN IF NOT EXISTS max_score INTEGER;
ALTER TABLE public.quiz_attempts ADD COLUMN IF NOT EXISTS ai_feedback TEXT;
ALTER TABLE public.quiz_attempts ADD COLUMN IF NOT EXISTS last_question_index INTEGER;

-- -------------------------------------------------------------------------------------
-- 5. Indexes (all idempotent)
-- -------------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_chapters_unit_id              ON public.chapters(unit_id);
CREATE INDEX IF NOT EXISTS idx_spec_points_chapter_id        ON public.specification_points(chapter_id);
CREATE INDEX IF NOT EXISTS idx_spec_points_code              ON public.specification_points(reference_code);
CREATE INDEX IF NOT EXISTS idx_activities_spec_id            ON public.activities(specification_point_id);
CREATE INDEX IF NOT EXISTS idx_resources_spec_id             ON public.resources(specification_point_id);
CREATE INDEX IF NOT EXISTS idx_questions_spec_id             ON public.questions(specification_point_id);

CREATE INDEX IF NOT EXISTS idx_resource_assets_resource_id   ON public.resource_assets(resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_assets_asset_type    ON public.resource_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_resource_assets_page_number   ON public.resource_assets(page_number);
CREATE INDEX IF NOT EXISTS idx_resource_assets_linked_q      ON public.resource_assets(linked_question_id)
    WHERE linked_question_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_resource_chunks_resource_id   ON public.resource_chunks(resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_chunks_chunk_type    ON public.resource_chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_resource_chunks_chunk_index   ON public.resource_chunks(resource_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_resource_chunks_embedding_hnsw
    ON public.resource_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student_resource
    ON public.quiz_attempts(student_id, resource_id);

-- -------------------------------------------------------------------------------------
-- 6. pgvector similarity-search RPC (equivalent of migrations/mig_7_match_function.sql)
-- -------------------------------------------------------------------------------------
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
    similarity      FLOAT
)
LANGUAGE plpgsql
STABLE
SET search_path = public
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
    WHERE (filter_resource_id IS NULL OR rc.resource_id = filter_resource_id)
    ORDER BY rc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

GRANT EXECUTE ON FUNCTION public.match_resource_chunks(vector(1024), INTEGER, UUID)
    TO anon, authenticated;

COMMENT ON FUNCTION public.match_resource_chunks IS
    'pgvector cosine similarity search over resource_chunks. Returns top-N nearest chunks with similarity (1=identical, 0=orthogonal). Pass NULL filter_resource_id to search all resources.';

-- -------------------------------------------------------------------------------------
-- 7. Row Level Security
-- -------------------------------------------------------------------------------------
ALTER TABLE public.units                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chapters             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.specification_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.activities           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resources            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.questions            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resource_assets      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resource_chunks      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quiz_attempts        ENABLE ROW LEVEL SECURITY;

-- 7a. Curriculum read access for signed-in users (matches the auth-gated dashboard).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'units'
          AND policyname = 'Enable read access for authenticated users only'
    ) THEN
        CREATE POLICY "Enable read access for authenticated users only"
            ON public.units FOR SELECT TO authenticated USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'chapters'
          AND policyname = 'Enable read access for authenticated users only'
    ) THEN
        CREATE POLICY "Enable read access for authenticated users only"
            ON public.chapters FOR SELECT TO authenticated USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'activities'
          AND policyname = 'Enable read access for authenticated users only'
    ) THEN
        CREATE POLICY "Enable read access for authenticated users only"
            ON public.activities FOR SELECT TO authenticated USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'questions'
          AND policyname = 'Enable read access for authenticated users only'
    ) THEN
        CREATE POLICY "Enable read access for authenticated users only"
            ON public.questions FOR SELECT TO authenticated USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'resources'
          AND policyname = 'Enable read access for authenticated users only'
    ) THEN
        CREATE POLICY "Enable read access for authenticated users only"
            ON public.resources FOR SELECT TO authenticated USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'specification_points'
          AND policyname = 'Enable read access for authenticated users only'
    ) THEN
        CREATE POLICY "Enable read access for authenticated users only"
            ON public.specification_points FOR SELECT TO authenticated USING (true);
    END IF;
END $$;

-- 7b. Deliberate public read for educational metadata (matches live project).
--     The frontend marketing pages do not query these tables, but public read is
--     retained so resource/spec links remain shareable. Drop these policies if a
--     fully private curriculum is required.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'resources'
          AND policyname = 'Allow public read access to resources'
    ) THEN
        CREATE POLICY "Allow public read access to resources"
            ON public.resources FOR SELECT USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'specification_points'
          AND policyname = 'Allow public read access to specification_points'
    ) THEN
        CREATE POLICY "Allow public read access to specification_points"
            ON public.specification_points FOR SELECT USING (true);
    END IF;
END $$;

-- 7c. Asset/chunk read policies (public read is intentional; storage URLs are public).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'resource_assets'
          AND policyname = 'resource_assets_public_read'
    ) THEN
        CREATE POLICY "resource_assets_public_read"
            ON public.resource_assets FOR SELECT USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'resource_chunks'
          AND policyname = 'resource_chunks_public_read'
    ) THEN
        CREATE POLICY "resource_chunks_public_read"
            ON public.resource_chunks FOR SELECT USING (true);
    END IF;
END $$;

-- 7d. HARDENING: remove broad authenticated write policies. The backend uses the
--     service-role key, which bypasses RLS; no browser client writes these tables.
DROP POLICY IF EXISTS resource_assets_authenticated_write ON public.resource_assets;
DROP POLICY IF EXISTS resource_chunks_authenticated_write ON public.resource_chunks;

-- 7e. Cleanup: live project has a redundant duplicate SELECT policy on resources.
DROP POLICY IF EXISTS "New Policy" ON public.resources;

-- 7f. Quiz attempts: each student may only read/insert/update their own rows.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'quiz_attempts'
          AND policyname = 'Users can view their own quiz attempts'
    ) THEN
        CREATE POLICY "Users can view their own quiz attempts"
            ON public.quiz_attempts FOR SELECT
            USING (auth.uid() = student_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'quiz_attempts'
          AND policyname = 'Users can insert their own quiz attempts'
    ) THEN
        CREATE POLICY "Users can insert their own quiz attempts"
            ON public.quiz_attempts FOR INSERT
            WITH CHECK (auth.uid() = student_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'quiz_attempts'
          AND policyname = 'Users can update their own quiz attempts'
    ) THEN
        CREATE POLICY "Users can update their own quiz attempts"
            ON public.quiz_attempts FOR UPDATE
            USING (auth.uid() = student_id);
    END IF;
END $$;

-- -------------------------------------------------------------------------------------
-- 8. Public Storage bucket `resource-assets` (10 MB per object)
-- -------------------------------------------------------------------------------------
-- Public read is required because `resource_assets.storage_url` stores public URLs.
-- Uploads are performed by the ingestion pipeline with the service-role key.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('resource-assets', 'resource-assets', true, 10485760, NULL)
ON CONFLICT (id) DO UPDATE
    SET public = EXCLUDED.public,
        file_size_limit = EXCLUDED.file_size_limit;

COMMIT;

-- =====================================================================================
-- POST-MIGRATION VERIFICATION (read-only; run manually)
-- =====================================================================================
-- SELECT table_name, column_name, data_type
-- FROM information_schema.columns
-- WHERE table_schema = 'public'
--   AND table_name IN ('resources','resource_assets','resource_chunks','quiz_attempts')
-- ORDER BY table_name, ordinal_position;
--
-- SELECT relname, relrowsecurity FROM pg_class c
-- JOIN pg_namespace n ON n.oid = c.relnamespace
-- WHERE n.nspname = 'public'
--   AND relname IN ('units','chapters','specification_points','activities',
--                   'resources','questions','resource_assets','resource_chunks','quiz_attempts')
-- ORDER BY relname;
--
-- SELECT tablename, policyname, cmd, roles::text FROM pg_policies
-- WHERE schemaname = 'public' ORDER BY tablename, policyname;
--
-- SELECT proname, pg_get_function_identity_arguments(oid) FROM pg_proc
-- WHERE proname = 'match_resource_chunks';
--
-- SELECT id, name, public, file_size_limit FROM storage.buckets
-- WHERE id = 'resource-assets';
-- =====================================================================================
