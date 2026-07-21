# DATABASE_MIGRATION.md

## Schema, Indexes, Foreign Keys, Migration Order

**Milestone:** 1 — Asset Infrastructure
**Date:** 2026-07-13

---

## 1. Migration Overview

A single migration file creates the `resource_assets` table and adds the
`content_markdown` column to the existing `resources` table.

| Migration | File | Description |
|---|---|---|
| mig_1_tables | (already applied) | Creates base tables: resources, chapters, units, etc. |
| **mig_5_resource_assets** | `migrations/mig_5_resource_assets.sql` | Creates resource_assets table + indexes + RLS + content_markdown column |

Note: Migrations 2–4 were not part of this project's scope. The numbering
follows the convention in the existing codebase.

---

## 2. Schema: resource_assets

```sql
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
```

### Column Reference

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | Primary key |
| `resource_id` | UUID | NO | — | FK to `resources.id` (CASCADE) |
| `page_number` | INTEGER | NO | — | 1-indexed page number in source PDF |
| `asset_type` | VARCHAR(50) | NO | — | `graph`, `diagram`, `photograph`, `apparatus`, `table_image`, `figure`, `plotting_grid` |
| `storage_path` | TEXT | NO | — | Bucket-relative path (e.g., `{resource_id}/page2_graph_0.png`) |
| `storage_url` | TEXT | NO | — | Full public Supabase Storage URL |
| `mime_type` | VARCHAR(100) | NO | `'image/png'` | MIME type of stored asset |
| `width` | INTEGER | YES | — | Pixel width (null if unknown) |
| `height` | INTEGER | YES | — | Pixel height (null if unknown) |
| `bounding_box` | JSONB | YES | — | `{"x0","y0","x1","y1"}` in PDF points |
| `caption` | TEXT | YES | — | Human-readable description |
| `linked_question_id` | TEXT | YES | — | Question identifier (e.g., "Q4") if linked |
| `content_verified` | BOOLEAN | YES | `false` | True if non-white pixel ratio > 0.5% |
| `metadata` | JSONB | YES | `'{}'::jsonb` | Additional metadata bag |
| `created_at` | TIMESTAMP WITH TIME ZONE | YES | `NOW()` | Row creation timestamp |

---

## 3. Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_resource_assets_resource_id
    ON public.resource_assets(resource_id);

CREATE INDEX IF NOT EXISTS idx_resource_assets_asset_type
    ON public.resource_assets(asset_type);

CREATE INDEX IF NOT EXISTS idx_resource_assets_page_number
    ON public.resource_assets(page_number);

CREATE INDEX IF NOT EXISTS idx_resource_assets_linked_q
    ON public.resource_assets(linked_question_id)
    WHERE linked_question_id IS NOT NULL;
```

| Index | Type | Purpose |
|---|---|---|
| `resource_assets_pkey` | B-Tree (implicit) | Primary key on `id` |
| `idx_resource_assets_resource_id` | B-Tree | FK joins, per-resource asset listing |
| `idx_resource_assets_asset_type` | B-Tree | Filter by asset type (e.g., "all graphs") |
| `idx_resource_assets_page_number` | B-Tree | Page-scoped queries |
| `idx_resource_assets_linked_q` | B-Tree (partial) | Question-asset link queries (skips NULLs) |

---

## 4. Foreign Keys

```sql
resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE
```

| Constraint | From | To | On Delete |
|---|---|---|---|
| `resource_assets_resource_id_fkey` | `resource_assets.resource_id` | `resources.id` | CASCADE |

When a resource is deleted, all its asset rows are automatically deleted.
Storage objects in the bucket are NOT automatically deleted (requires a
Storage API cleanup call — see Known Issues in HANDOFF_SESSION_2.md).

---

## 5. Row Level Security (RLS)

```sql
ALTER TABLE public.resource_assets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "resource_assets_public_read" ON public.resource_assets
    FOR SELECT USING (true);

CREATE POLICY "resource_assets_authenticated_write" ON public.resource_assets
    FOR ALL TO authenticated USING (true) WITH CHECK (true);
```

| Policy | Command | Role | Effect |
|---|---|---|---|
| `resource_assets_public_read` | SELECT | `public` (anon) | Anyone can read asset rows — storage URLs are public |
| `resource_assets_authenticated_write` | ALL | `authenticated` | Authenticated users can insert/update/delete |

The service role key (used by the backend pipeline) bypasses RLS entirely.

---

## 6. Additional Column: resources.content_markdown

```sql
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
```

This column was added to support future milestones where the semantic JSON
content can also be rendered as markdown for the frontend. It is nullable and
not populated by Milestone 1.

---

## 7. Migration Order

```
1. Ensure Supabase project is running
2. Execute mig_5_resource_assets.sql via Management API or psql:

   POST https://api.supabase.com/v1/projects/{ref}/database/query
   Body: {"query": "<full SQL file content>"}
   Headers: Authorization: Bearer {SUPABASE_ACCESS_TOKEN}

3. Create the 'resource-assets' storage bucket:

   POST https://{project}.supabase.co/storage/v1/bucket
   Body: {"name": "resource-assets", "public": true, "file_size_limit": 10485760}
   Headers: apikey + Authorization (service-role key)
```

### Verification Commands

After migration, verify with:

```sql
-- Table exists
SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema='public' AND table_name='resource_assets'
ORDER BY ordinal_position;

-- Indexes
SELECT indexname FROM pg_indexes WHERE tablename='resource_assets';

-- FK
SELECT conname, confrelid::regclass FROM pg_constraint
WHERE conrelid='public.resource_assets'::regclass AND contype='f';

-- RLS
SELECT relrowsecurity FROM pg_class WHERE relname='resource_assets';

-- Policies
SELECT policyname, cmd FROM pg_policies WHERE tablename='resource_assets';
```

---

## 8. Migration File Location

The migration SQL file is at:
```
migrations/mig_5_resource_assets.sql
```

It was applied via the Supabase Management API (`POST /v1/projects/{ref}/database/query`)
using the `SUPABASE_ACCESS_TOKEN` from the project's root `.env` file.
