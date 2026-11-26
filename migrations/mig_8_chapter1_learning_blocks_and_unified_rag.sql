-- =====================================================================================
-- MIGRATION 8: Chapter 1 Learning Blocks, Student Progress, and Unified Model-Tagged RAG
-- =====================================================================================
-- SAFETY (NON-DESTRUCTIVE & STRICTLY IDEMPOTENT)
--   This migration contains NO `DROP TABLE`, NO `TRUNCATE`, NO `DELETE`, and NO
--   embedding mutation. Existing vectors (including the 21 Chapter 1 worksheet rows
--   anchored on 5729d034-a6c7-4f35-b81c-fcac447289c7) are preserved untouched.
--   Legacy 3-arg `public.match_resource_chunks(vector(1024), INTEGER, UUID)` is
--   preserved completely intact.
--
-- PURPOSE (GitHub Issue #13 — Chapter 1 Vertical Slice Foundation)
--   1. Extend `public.resources` with `chapter_id`, constrained `resource_type`
--      ('worksheet', 'lesson', 'practical', 'examiner_note'), and `spec_refs`.
--      Backfill `chapter_id` from `public.specification_points.chapter_id`.
--   2. Create `public.lessons`, `public.learning_blocks`, and owner-scoped RLS
--      `public.student_block_progress` with flat per-block `xp_awarded` (ADR-0003;
--      no separate `xp_events` ledger; total XP computed via `SUM(xp_awarded)`).
--   3. Extend `public.resource_chunks` with `chapter_id`, `source_type`, `block_id`,
--      `spec_refs`, and `embedding_model` (ADR-0002). Backfill existing rows'
--      `chapter_id`, `source_type`, and tag existing Chapter 1 rows (chapter
--      b95f8fac-355e-4037-bc1f-2d3b2bf77140 / resource 5729d034-a6c7-4f35-b81c-fcac447289c7)
--      with `embedding_model = 'nvidia/nemotron-3.5-embed-1b'` without re-embedding.
--   4. Drop redundant B-tree indexes `idx_resource_chunks_resource_id` and
--      `idx_spec_points_code` (ADR-0002), and add non-redundant indexes for
--      `match_chapter_chunks` and progress lookups.
--   5. Create chapter-scoped, model-tagged RPC `public.match_chapter_chunks`
--      returning citation metadata (`BLK-`, `PRC-`, `EXM-`, `WE-`, `SRC-`, etc.).
--   6. Enable RLS and install deterministic policies on `lessons`, `learning_blocks`,
--      and `student_block_progress`.
--
-- CURRICULUM ANCHORS
--   - Unit 1 (Forces and motion):   2cf312d3-0f4b-4339-84f3-97b10b2907ea
--   - Chapter 1 (Movement & pos.):  b95f8fac-355e-4037-bc1f-2d3b2bf77140
--   - Chapter 1 slice specs:        1.3–1.10 (Spec 1.1 remains legacy worksheet anchor
--                                   on 5729d034-a6c7-4f35-b81c-fcac447289c7)
--
-- PREREQUISITES
--   - migrations/mig_0_verify_and_harden_rls.sql
-- =====================================================================================

BEGIN;

-- -------------------------------------------------------------------------------------
-- 0. Shared `updated_at` trigger helper (idempotent)
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- -------------------------------------------------------------------------------------
-- 1. Extend `public.resources` (unified parent spine for worksheets, lessons,
--    practicals, and examiner notes)
-- -------------------------------------------------------------------------------------
ALTER TABLE public.resources
    ADD COLUMN IF NOT EXISTS chapter_id UUID REFERENCES public.chapters(id) ON DELETE SET NULL;

ALTER TABLE public.resources
    ADD COLUMN IF NOT EXISTS resource_type VARCHAR(40) NOT NULL DEFAULT 'worksheet';

ALTER TABLE public.resources
    ADD COLUMN IF NOT EXISTS spec_refs TEXT[] NOT NULL DEFAULT '{}'::text[];

-- Defensive normalization if columns pre-existed with NULL values
UPDATE public.resources
SET resource_type = 'worksheet'
WHERE resource_type IS NULL OR btrim(resource_type) = '';

UPDATE public.resources
SET spec_refs = '{}'::text[]
WHERE spec_refs IS NULL;

-- Backfill `resources.chapter_id` from `specification_points.chapter_id`
UPDATE public.resources r
SET chapter_id = sp.chapter_id
FROM public.specification_points sp
WHERE r.specification_point_id = sp.id
  AND r.chapter_id IS NULL
  AND sp.chapter_id IS NOT NULL;

-- Constrain `resources.resource_type` idempotently
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_resources_resource_type'
          AND conrelid = 'public.resources'::regclass
    ) THEN
        ALTER TABLE public.resources
            ADD CONSTRAINT chk_resources_resource_type
            CHECK (resource_type IN ('worksheet', 'lesson', 'practical', 'examiner_note'));
    END IF;
END $$;

-- -------------------------------------------------------------------------------------
-- 2. Create `public.lessons`, `public.learning_blocks`, and `public.student_block_progress`
-- -------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.lessons (
    id                UUID                     PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id        UUID                     NOT NULL REFERENCES public.chapters(id) ON DELETE CASCADE,
    resource_id       UUID                     REFERENCES public.resources(id) ON DELETE SET NULL,
    slug              VARCHAR(120)             NOT NULL,
    title             VARCHAR(255)             NOT NULL,
    subtitle          TEXT,
    source_path       TEXT,
    spec_refs         TEXT[]                   NOT NULL DEFAULT '{}'::text[],
    duration_minutes  INTEGER                  CHECK (duration_minutes IS NULL OR duration_minutes > 0),
    vocabulary        JSONB                    NOT NULL DEFAULT '[]'::jsonb,
    metadata          JSONB                    NOT NULL DEFAULT '{}'::jsonb,
    is_published      BOOLEAN                  NOT NULL DEFAULT true,
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_lessons_chapter_slug UNIQUE (chapter_id, slug)
);

CREATE TABLE IF NOT EXISTS public.learning_blocks (
    id                 UUID                     PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id          UUID                     NOT NULL REFERENCES public.lessons(id) ON DELETE CASCADE,
    chapter_id         UUID                     NOT NULL REFERENCES public.chapters(id) ON DELETE CASCADE,
    block_index        INTEGER                  NOT NULL CHECK (block_index >= 1),
    slug               VARCHAR(120)             NOT NULL,
    title              VARCHAR(255)             NOT NULL,
    spec_refs          TEXT[]                   NOT NULL DEFAULT '{}'::text[],
    content_markdown   TEXT                     NOT NULL DEFAULT '',
    sections           JSONB                    NOT NULL DEFAULT '[]'::jsonb,
    guided_practice    JSONB                    NOT NULL DEFAULT '[]'::jsonb,
    self_check         JSONB                    NOT NULL DEFAULT '{}'::jsonb,
    examiner_alerts    JSONB                    NOT NULL DEFAULT '[]'::jsonb,
    analogies          JSONB                    NOT NULL DEFAULT '[]'::jsonb,
    reflection_prompt  TEXT,
    widgets            JSONB                    NOT NULL DEFAULT '[]'::jsonb,
    xp_value           INTEGER                  NOT NULL DEFAULT 25 CHECK (xp_value >= 0),
    metadata           JSONB                    NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_learning_blocks_lesson_index UNIQUE (lesson_id, block_index),
    CONSTRAINT uq_learning_blocks_lesson_slug  UNIQUE (lesson_id, slug)
);

-- ADR-0003: Flat `xp_awarded` directly on `student_block_progress`; total XP is
-- computed via `SUM(xp_awarded)` (no separate `xp_events` ledger table).
CREATE TABLE IF NOT EXISTS public.student_block_progress (
    id                     UUID                     PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id             UUID                     NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    chapter_id             UUID                     NOT NULL REFERENCES public.chapters(id) ON DELETE CASCADE,
    lesson_id              UUID                     NOT NULL REFERENCES public.lessons(id) ON DELETE CASCADE,
    block_id               UUID                     NOT NULL REFERENCES public.learning_blocks(id) ON DELETE CASCADE,
    status                 VARCHAR(30)              NOT NULL DEFAULT 'not_started'
                               CHECK (status IN ('not_started', 'in_progress', 'needs_remediation', 'completed')),
    is_completed           BOOLEAN                  NOT NULL DEFAULT false,
    completed_at           TIMESTAMP WITH TIME ZONE,
    xp_awarded             INTEGER                  NOT NULL DEFAULT 0 CHECK (xp_awarded >= 0),
    self_check_score       NUMERIC(5, 2)            CHECK (self_check_score IS NULL OR (self_check_score >= 0 AND self_check_score <= 100)),
    self_check_attempts    INTEGER                  NOT NULL DEFAULT 0 CHECK (self_check_attempts >= 0),
    self_check_results     JSONB                    NOT NULL DEFAULT '{}'::jsonb,
    remediation_triggered  BOOLEAN                  NOT NULL DEFAULT false,
    reflection_text        TEXT                     CHECK (reflection_text IS NULL OR char_length(reflection_text) <= 500),
    created_at             TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_student_block_progress_student_block UNIQUE (student_id, block_id)
);

-- Idempotent `updated_at` triggers
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_lessons_set_updated_at'
          AND tgrelid = 'public.lessons'::regclass
    ) THEN
        CREATE TRIGGER trg_lessons_set_updated_at
            BEFORE UPDATE ON public.lessons
            FOR EACH ROW
            EXECUTE FUNCTION public.set_updated_at();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_learning_blocks_set_updated_at'
          AND tgrelid = 'public.learning_blocks'::regclass
    ) THEN
        CREATE TRIGGER trg_learning_blocks_set_updated_at
            BEFORE UPDATE ON public.learning_blocks
            FOR EACH ROW
            EXECUTE FUNCTION public.set_updated_at();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_student_block_progress_set_updated_at'
          AND tgrelid = 'public.student_block_progress'::regclass
    ) THEN
        CREATE TRIGGER trg_student_block_progress_set_updated_at
            BEFORE UPDATE ON public.student_block_progress
            FOR EACH ROW
            EXECUTE FUNCTION public.set_updated_at();
    END IF;
END $$;

-- -------------------------------------------------------------------------------------
-- 3. Extend `public.resource_chunks` & non-destructive metadata backfill (ADR-0002)
-- -------------------------------------------------------------------------------------
ALTER TABLE public.resource_chunks
    ADD COLUMN IF NOT EXISTS chapter_id UUID REFERENCES public.chapters(id) ON DELETE SET NULL;

ALTER TABLE public.resource_chunks
    ADD COLUMN IF NOT EXISTS source_type VARCHAR(40) NOT NULL DEFAULT 'worksheet';

ALTER TABLE public.resource_chunks
    ADD COLUMN IF NOT EXISTS block_id UUID REFERENCES public.learning_blocks(id) ON DELETE SET NULL;

ALTER TABLE public.resource_chunks
    ADD COLUMN IF NOT EXISTS spec_refs TEXT[] NOT NULL DEFAULT '{}'::text[];

ALTER TABLE public.resource_chunks
    ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(120);

-- Defensive normalization for pre-existing NULLs (never modifies `embedding`)
UPDATE public.resource_chunks
SET source_type = 'worksheet'
WHERE source_type IS NULL OR btrim(source_type) = '';

UPDATE public.resource_chunks
SET spec_refs = '{}'::text[]
WHERE spec_refs IS NULL;

-- Constrain `resource_chunks.source_type` idempotently
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_resource_chunks_source_type'
          AND conrelid = 'public.resource_chunks'::regclass
    ) THEN
        ALTER TABLE public.resource_chunks
            ADD CONSTRAINT chk_resource_chunks_source_type
            CHECK (source_type IN ('worksheet', 'lesson_block', 'practical', 'examiner_note', 'worked_example'));
    END IF;
END $$;

-- Backfill `resource_chunks.chapter_id` via `resources` (and fallback via `specification_points`)
UPDATE public.resource_chunks rc
SET chapter_id = COALESCE(r.chapter_id, sp.chapter_id)
FROM public.resources r
LEFT JOIN public.specification_points sp
       ON sp.id = r.specification_point_id
WHERE rc.resource_id = r.id
  AND rc.chapter_id IS NULL
  AND COALESCE(r.chapter_id, sp.chapter_id) IS NOT NULL;

-- Backfill existing Chapter 1 rows (including the 21 legacy worksheet chunks anchored on
-- resource 5729d034-a6c7-4f35-b81c-fcac447289c7 / chapter b95f8fac-355e-4037-bc1f-2d3b2bf77140)
-- with `embedding_model = 'nvidia/nemotron-3.5-embed-1b'` WITHOUT touching or re-embedding vectors.
UPDATE public.resource_chunks
SET embedding_model = 'nvidia/nemotron-3.5-embed-1b'
WHERE embedding_model IS NULL
  AND (
      chapter_id = 'b95f8fac-355e-4037-bc1f-2d3b2bf77140'::uuid
      OR resource_id = '5729d034-a6c7-4f35-b81c-fcac447289c7'::uuid
  );

-- -------------------------------------------------------------------------------------
-- 4. Drop redundant B-tree indexes & install targeted non-redundant indexes (ADR-0002)
-- -------------------------------------------------------------------------------------
-- `idx_resource_chunks_resource_id` is redundant with `idx_resource_chunks_chunk_index(resource_id, chunk_index)`.
-- `idx_spec_points_code` is redundant with the UNIQUE constraint on `specification_points(reference_code)`.
DROP INDEX IF EXISTS public.idx_resource_chunks_resource_id;
DROP INDEX IF EXISTS public.idx_spec_points_code;

-- `resources` indexes (leading `chapter_id` covers chapter-scoped queries without a second index)
CREATE INDEX IF NOT EXISTS idx_resources_chapter_type
    ON public.resources(chapter_id, resource_type);

CREATE INDEX IF NOT EXISTS idx_resources_spec_refs_gin
    ON public.resources USING gin (spec_refs);

-- `lessons` indexes (`uq_lessons_chapter_slug` already indexes `(chapter_id, slug)`)
CREATE INDEX IF NOT EXISTS idx_lessons_resource_id
    ON public.lessons(resource_id)
    WHERE resource_id IS NOT NULL;

-- `learning_blocks` indexes (`uq_learning_blocks_lesson_index` & `_slug` already cover `lesson_id`)
CREATE INDEX IF NOT EXISTS idx_learning_blocks_chapter_order
    ON public.learning_blocks(chapter_id, block_index);

CREATE INDEX IF NOT EXISTS idx_learning_blocks_spec_refs_gin
    ON public.learning_blocks USING gin (spec_refs);

-- `student_block_progress` indexes (`uq_student_block_progress_student_block` already covers `(student_id, block_id)`)
CREATE INDEX IF NOT EXISTS idx_student_block_progress_student_chapter
    ON public.student_block_progress(student_id, chapter_id);

CREATE INDEX IF NOT EXISTS idx_student_block_progress_student_lesson
    ON public.student_block_progress(student_id, lesson_id);

CREATE INDEX IF NOT EXISTS idx_student_block_progress_block_id
    ON public.student_block_progress(block_id);

-- `resource_chunks` indexes for `match_chapter_chunks` and deterministic lexical fallback
CREATE INDEX IF NOT EXISTS idx_resource_chunks_chapter_model_source
    ON public.resource_chunks(chapter_id, embedding_model, source_type);

CREATE INDEX IF NOT EXISTS idx_resource_chunks_block_id
    ON public.resource_chunks(block_id)
    WHERE block_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_resource_chunks_spec_refs_gin
    ON public.resource_chunks USING gin (spec_refs);

-- -------------------------------------------------------------------------------------
-- 5. Chapter-scoped, model-tagged pgvector RPC: `public.match_chapter_chunks`
--    (Legacy 3-arg `public.match_resource_chunks` is intentionally left untouched.)
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.match_chapter_chunks(
    query_embedding         vector(1024),
    filter_chapter_id       UUID,
    filter_embedding_model  TEXT    DEFAULT 'nvidia/nemotron-3.5-embed-1b',
    filter_source_types     TEXT[]  DEFAULT NULL,
    filter_spec_refs        TEXT[]  DEFAULT NULL,
    match_threshold         FLOAT   DEFAULT 0.0,
    match_count             INTEGER DEFAULT 10
)
RETURNS TABLE (
    id               UUID,
    resource_id      UUID,
    resource_title   VARCHAR(255),
    resource_type    VARCHAR(40),
    chapter_id       UUID,
    block_id         UUID,
    block_index      INTEGER,
    block_slug       VARCHAR(120),
    block_title      VARCHAR(255),
    source_type      VARCHAR(40),
    chunk_index      INTEGER,
    chunk_text       TEXT,
    chunk_type       VARCHAR(50),
    source_refs      JSONB,
    spec_refs        TEXT[],
    embedding_model  VARCHAR(120),
    token_count      INTEGER,
    similarity       FLOAT
)
LANGUAGE plpgsql
STABLE
SET search_path = public
AS $$
BEGIN
    IF filter_chapter_id IS NULL OR filter_embedding_model IS NULL OR btrim(filter_embedding_model) = '' THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        rc.id,
        rc.resource_id,
        r.title                                    AS resource_title,
        r.resource_type                            AS resource_type,
        rc.chapter_id,
        rc.block_id,
        lb.block_index,
        lb.slug                                    AS block_slug,
        lb.title                                   AS block_title,
        rc.source_type,
        rc.chunk_index,
        rc.chunk_text,
        rc.chunk_type,
        rc.source_refs,
        rc.spec_refs,
        rc.embedding_model,
        rc.token_count,
        1 - (rc.embedding <=> query_embedding)     AS similarity
    FROM public.resource_chunks rc
    LEFT JOIN public.resources r
           ON r.id = rc.resource_id
    LEFT JOIN public.learning_blocks lb
           ON lb.id = rc.block_id
    WHERE rc.chapter_id = filter_chapter_id
      AND rc.embedding_model IS NOT NULL
      AND rc.embedding_model = filter_embedding_model
      AND (
          filter_source_types IS NULL
          OR cardinality(filter_source_types) = 0
          OR rc.source_type = ANY(filter_source_types)
      )
      AND (
          filter_spec_refs IS NULL
          OR cardinality(filter_spec_refs) = 0
          OR rc.spec_refs && filter_spec_refs
      )
      AND (
          match_threshold IS NULL
          OR (1 - (rc.embedding <=> query_embedding)) >= match_threshold
      )
    ORDER BY
        rc.embedding <=> query_embedding ASC,
        rc.chunk_index ASC,
        rc.id ASC
    LIMIT GREATEST(1, LEAST(COALESCE(match_count, 10), 100));
END;
$$;

GRANT EXECUTE ON FUNCTION public.match_chapter_chunks(
    vector(1024), UUID, TEXT, TEXT[], TEXT[], FLOAT, INTEGER
) TO anon, authenticated;

-- -------------------------------------------------------------------------------------
-- 6. Row Level Security (RLS) on new tables
-- -------------------------------------------------------------------------------------
ALTER TABLE public.lessons                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_blocks         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.student_block_progress  ENABLE ROW LEVEL SECURITY;

-- 6a. Catalog read policies for `lessons` and `learning_blocks`
--     Matches `mig_0` curriculum catalog pattern: authenticated read-only.
--     No browser write policies; ingestion writes via service-role key.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'lessons'
          AND policyname = 'Enable read access for authenticated users only'
    ) THEN
        CREATE POLICY "Enable read access for authenticated users only"
            ON public.lessons
            FOR SELECT
            TO authenticated
            USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'learning_blocks'
          AND policyname = 'Enable read access for authenticated users only'
    ) THEN
        CREATE POLICY "Enable read access for authenticated users only"
            ON public.learning_blocks
            FOR SELECT
            TO authenticated
            USING (true);
    END IF;
END $$;

-- 6b. Owner-scoped RLS policies for `student_block_progress` (ADR-0003)
--     Each authenticated student may only read/insert/update/delete their own rows.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'student_block_progress'
          AND policyname = 'Users can view their own block progress'
    ) THEN
        CREATE POLICY "Users can view their own block progress"
            ON public.student_block_progress
            FOR SELECT
            TO authenticated
            USING (auth.uid() = student_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'student_block_progress'
          AND policyname = 'Users can insert their own block progress'
    ) THEN
        CREATE POLICY "Users can insert their own block progress"
            ON public.student_block_progress
            FOR INSERT
            TO authenticated
            WITH CHECK (auth.uid() = student_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'student_block_progress'
          AND policyname = 'Users can update their own block progress'
    ) THEN
        CREATE POLICY "Users can update their own block progress"
            ON public.student_block_progress
            FOR UPDATE
            TO authenticated
            USING (auth.uid() = student_id)
            WITH CHECK (auth.uid() = student_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'student_block_progress'
          AND policyname = 'Users can delete their own block progress'
    ) THEN
        CREATE POLICY "Users can delete their own block progress"
            ON public.student_block_progress
            FOR DELETE
            TO authenticated
            USING (auth.uid() = student_id);
    END IF;
END $$;

-- -------------------------------------------------------------------------------------
-- 7. Documentation comments
-- -------------------------------------------------------------------------------------
COMMENT ON COLUMN public.resources.chapter_id IS
    'Chapter owning this resource (backfilled from specification_points.chapter_id for existing rows).';
COMMENT ON COLUMN public.resources.resource_type IS
    'Unified resource classification: worksheet, lesson, practical, or examiner_note.';
COMMENT ON COLUMN public.resources.spec_refs IS
    'Edexcel specification reference codes covered by this resource (e.g. {1.3,1.4}).';

COMMENT ON TABLE public.lessons IS
    'Structured interactive lesson parsed from a canonical Marp Markdown file (ADR-0001).';
COMMENT ON TABLE public.learning_blocks IS
    'Ordered, self-contained solo-student learning units within a lesson (e.g. 4 blocks in Ch. 1 covering specs 1.3-1.10).';
COMMENT ON TABLE public.student_block_progress IS
    'Owner-scoped RLS progress for Learning Blocks with flat per-block xp_awarded (SUM(xp_awarded) for total XP; ADR-0003).';

COMMENT ON COLUMN public.resource_chunks.chapter_id IS
    'Denormalized chapter UUID for chapter-scoped hybrid RAG retrieval.';
COMMENT ON COLUMN public.resource_chunks.source_type IS
    'Retrieval source classification: worksheet, lesson_block, practical, examiner_note, or worked_example.';
COMMENT ON COLUMN public.resource_chunks.block_id IS
    'Optional reference to public.learning_blocks(id) when chunk originates from a Learning Block.';
COMMENT ON COLUMN public.resource_chunks.spec_refs IS
    'Edexcel specification reference codes attached to this chunk for overlap filtering and deterministic fallback.';
COMMENT ON COLUMN public.resource_chunks.embedding_model IS
    'Identifier of the embedding model that produced `embedding` (e.g. nvidia/nemotron-3.5-embed-1b). Prevents cross-model cosine noise (ADR-0002).';

COMMENT ON FUNCTION public.match_chapter_chunks IS
    'Chapter-scoped, model-tagged pgvector cosine similarity search over public.resource_chunks. Filters strictly by chapter_id and embedding_model with optional source_types, spec_refs overlap, and similarity threshold; returns citation metadata for BLK-/PRC-/EXM-/WE-/SRC- prefixes.';

COMMIT;

-- =====================================================================================
-- POST-MIGRATION VERIFICATION (read-only; run manually)
-- =====================================================================================
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_schema = 'public'
--   AND table_name IN ('resources', 'lessons', 'learning_blocks', 'student_block_progress', 'resource_chunks')
-- ORDER BY table_name, ordinal_position;
--
-- SELECT indexname FROM pg_indexes
-- WHERE schemaname = 'public'
--   AND indexname IN ('idx_resource_chunks_resource_id', 'idx_spec_points_code');
-- -- Expected: 0 rows
--
-- SELECT relname, relrowsecurity FROM pg_class c
-- JOIN pg_namespace n ON n.oid = c.relnamespace
-- WHERE n.nspname = 'public'
--   AND relname IN ('lessons', 'learning_blocks', 'student_block_progress')
-- ORDER BY relname;
--
-- SELECT tablename, policyname, cmd, roles::text, qual, with_check
-- FROM pg_policies
-- WHERE schemaname = 'public'
--   AND tablename IN ('lessons', 'learning_blocks', 'student_block_progress')
-- ORDER BY tablename, policyname;
--
-- SELECT proname, pg_get_function_identity_arguments(oid)
-- FROM pg_proc
-- WHERE proname IN ('match_resource_chunks', 'match_chapter_chunks')
-- ORDER BY proname;
-- =====================================================================================
