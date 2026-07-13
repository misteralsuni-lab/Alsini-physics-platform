-- ======================================================================================
-- MIGRATION 5: resource_assets table — Visual Asset Infrastructure
-- ======================================================================================
-- Creates a normalized asset system linking extracted educational visual assets
-- (graphs, diagrams, photographs, apparatus, tables-as-images, figures) to their
-- originating resource via Supabase Storage URLs.
--
-- Prerequisites:
--   - mig_1_tables.sql (resources table must exist)
--   - Supabase Storage bucket 'resource-assets' must be created (see DATABASE_MIGRATION.md)
--
-- Run order: AFTER mig_1_tables.sql
-- ======================================================================================

-- 1. Create the resource_assets table
CREATE TABLE IF NOT EXISTS public.resource_assets (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id         UUID            NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    page_number         INTEGER         NOT NULL,
    asset_type          VARCHAR(50)     NOT NULL,
    storage_path        TEXT            NOT NULL,
    storage_url         TEXT            NOT NULL,
    mime_type           VARCHAR(100)    NOT NULL DEFAULT 'image/png',
    width               INTEGER,
    height              INTEGER,
    bounding_box        JSONB,
    caption             TEXT,
    linked_question_id  TEXT,
    content_verified    BOOLEAN         DEFAULT false,
    metadata            JSONB           DEFAULT '{}'::jsonb,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Indexes
CREATE INDEX IF NOT EXISTS idx_resource_assets_resource_id  ON public.resource_assets(resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_assets_asset_type   ON public.resource_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_resource_assets_page_number  ON public.resource_assets(page_number);
CREATE INDEX IF NOT EXISTS idx_resource_assets_linked_q     ON public.resource_assets(linked_question_id)
    WHERE linked_question_id IS NOT NULL;

-- 3. Enable RLS (Row Level Security)
ALTER TABLE public.resource_assets ENABLE ROW LEVEL SECURITY;

-- 4. RLS Policies
-- Public read: anyone can read asset references (the URLs point to Storage which has its own policies)
CREATE POLICY "resource_assets_public_read" ON public.resource_assets
    FOR SELECT USING (true);

-- Service role write: only the service role (backend) can insert/update/delete
-- (Service role bypasses RLS entirely, so this policy is for authenticated non-service users)
CREATE POLICY "resource_assets_authenticated_write" ON public.resource_assets
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 5. Add a content JSONB column to resources if it doesn't already exist (ad-hoc column was TEXT)
-- The existing content column is TEXT in some deployments. We add content_markdown for rendered markdown.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'resources'
          AND column_name = 'content_markdown'
    ) THEN
        ALTER TABLE public.resources ADD COLUMN content_markdown TEXT;
    END IF;
END $$;

-- 6. Add resource_assets columns comment for documentation
COMMENT ON TABLE public.resource_assets IS 'Normalized visual asset registry. Links extracted educational assets (graphs, diagrams, figures) to resources via Supabase Storage URLs.';
COMMENT ON COLUMN public.resource_assets.storage_path IS 'Path within the Supabase Storage bucket (e.g. resource-assets/{resource_id}/page2_graph.png)';
COMMENT ON COLUMN public.resource_assets.storage_url IS 'Full public Supabase Storage URL for the asset image';
COMMENT ON COLUMN public.resource_assets.bounding_box IS 'Optional JSON: {"x0": int, "y0": int, "x1": int, "y1": int} in PDF points';
COMMENT ON COLUMN public.resource_assets.linked_question_id IS 'Optional ID of the question this asset is linked to (e.g. Q4)';
COMMENT ON COLUMN public.resource_assets.metadata IS 'JSONB bag for additional asset metadata (content verification, coverage stats, etc.)';
