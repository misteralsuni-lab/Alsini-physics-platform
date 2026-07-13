# HANDOFF_SESSION_2.md

## Session 2 Handoff Document — Visual Asset Infrastructure

**Milestone:** 1 — Asset Infrastructure (COMPLETE)
**Date:** 2026-07-13
**Branch:** `multimodalragsystem`
**Previous commits:** `c0c9d6f` (HEAD before this session)

---

## Executive Summary

Milestone 1 is complete. A production-ready visual asset infrastructure has
been built and validated against the Golden Dataset (IGCSE Physics Worksheet 1:
Movement and Position).

The infrastructure consists of:
1. A normalized `resource_assets` database table (15 columns, 4 custom indexes,
   1 FK with CASCADE, RLS with 2 policies).
2. A public Supabase Storage bucket (`resource-assets`) hosting uploaded PNG
   assets with permanent public URLs.
3. A Python pipeline (3 modules) that extracts visual assets from PDFs via
   PyMuPDF, uploads them to Storage, and registers them in the database.
4. Four documentation files (architecture, migration, pipeline, this handoff).

All 8 acceptance tests pass. The existing parser and semantic pipeline remain
unmodified. No frontend work was performed.

---

## Completed Work

### 1. Database Migration — `resource_assets` table

- **Status:** Applied and verified.
- **Schema:** 15-column normalized table with UUID primary key, FK to
  `resources(id)` with `ON DELETE CASCADE`, JSONB bounding_box and metadata
  columns.
- **Indexes:** 4 custom B-Tree indexes (resource_id, asset_type, page_number,
  linked_question_id partial) + primary key.
- **RLS:** Enabled with public-read and authenticated-write policies.
- **Additional:** Added `content_markdown` TEXT column to `resources` (nullable,
  not populated — for future milestones).

### 2. Supabase Storage Bucket

- **Bucket name:** `resource-assets`
- **Public:** Yes (public read, no auth needed for GET).
- **File size limit:** 10 MB per file.
- **Storage count:** 2 assets uploaded from Golden Dataset.
- **URLs:** Public, CDN-accessible, no auth headers required.

### 3. Asset Extraction + Upload Pipeline

- **3 Python modules** in `backend/pipeline/`:
  - `asset_extractor.py` — PyMuPDF-based extraction, classification, content
    verification, caption generation.
  - `storage_uploader.py` — Supabase Storage REST API upload.
  - `run_asset_pipeline.py` — CLI orchestrator with built-in acceptance
    verification.
- **No new dependencies:** Uses PyMuPDF (already in venv) and `requests` (already
  in project). Pillow used for content verification (already installed).
- **No modifications** to `master_ingestion.py`, `resource_ingestion.py`,
  `main.py`, or any existing file.

### 4. Documentation

- `ASSET_ARCHITECTURE.md` — Storage design, asset lifecycle, DB relationships,
  implementation decisions.
- `DATABASE_MIGRATION.md` — Schema, indexes, FKs, migration order, RLS.
- `ASSET_PIPELINE.md` — Parser output, upload process, metadata generation,
  failure handling.
- `HANDOFF_SESSION_2.md` — This document.

---

## Files Modified

| File | Action | Description |
|---|---|---|
| `backend/pipeline/__init__.py` | NEW | Pipeline package marker |
| `backend/pipeline/asset_extractor.py` | NEW | PyMuPDF asset extraction + classification |
| `backend/pipeline/storage_uploader.py` | NEW | Supabase Storage upload module |
| `backend/pipeline/run_asset_pipeline.py` | NEW | CLI orchestrator + acceptance verification |
| `migrations/mig_5_resource_assets.sql` | NEW | SQL migration file (already applied) |
| `ASSET_ARCHITECTURE.md` | NEW | Architecture documentation |
| `DATABASE_MIGRATION.md` | NEW | Migration documentation |
| `ASSET_PIPELINE.md` | NEW | Pipeline documentation |
| `HANDOFF_SESSION_2.md` | NEW | This handoff document |

**No existing files were modified.**

---

## Database Changes

### New Table: `resource_assets`

```
Column                  Type                    Nullable  Default
──────────────────────  ──────────────────────  ────────  ─────────────────────
id                      UUID                    NO        gen_random_uuid()
resource_id             UUID                    NO        — (FK → resources.id, CASCADE)
page_number             INTEGER                 NO        —
asset_type              VARCHAR(50)             NO        —
storage_path            TEXT                    NO        —
storage_url             TEXT                    NO        —
mime_type               VARCHAR(100)            NO        'image/png'
width                   INTEGER                 YES       —
height                  INTEGER                 YES       —
bounding_box            JSONB                   YES       —
caption                 TEXT                    YES       —
linked_question_id      TEXT                    YES       —
content_verified        BOOLEAN                 YES       false
metadata                JSONB                   YES       '{}'::jsonb
created_at              TIMESTAMP WITH TIME ZONE  YES     NOW()
```

### Modified Table: `resources`

- Added column: `content_markdown TEXT` (nullable, not populated in M1).

### Indexes Created

- `idx_resource_assets_resource_id` (B-Tree)
- `idx_resource_assets_asset_type` (B-Tree)
- `idx_resource_assets_page_number` (B-Tree)
- `idx_resource_assets_linked_q` (B-Tree, partial — WHERE NOT NULL)

### RLS Policies

- `resource_assets_public_read` — SELECT for public/anon
- `resource_assets_authenticated_write` — ALL for authenticated

### Current Data

- `resource_assets` contains **2 rows** for the Golden Dataset resource:
  - **Row 1:** page=2, type=graph, "Distance-time graph of Usain Bolt's 100m
    training run (page 2, Q4)", content_verified=true
  - **Row 2:** page=3, type=plotting_grid, "Blank velocity-time plotting grid
    for Paul's ramp experiment (page 3, Q5a)", content_verified=true

---

## Storage Changes

### New Bucket: `resource-assets`

- **Public:** Yes
- **File size limit:** 10 MB
- **Objects stored:** 2

### Storage Paths

```
5729d034-a6c7-4f35-b81c-fcac447289c7/page2_graph_0.png           (20,443 bytes, valid PNG)
5729d034-a6c7-4f35-b81c-fcac447289c7/page3_plotting_grid_1.png    (8,170 bytes, valid PNG)
```

### Public URLs

```
https://miezybwngeqdyqvvqcrl.supabase.co/storage/v1/object/public/resource-assets/5729d034-a6c7-4f35-b81c-fcac447289c7/page2_graph_0.png
https://miezybwngeqdyqvvqcrl.supabase.co/storage/v1/object/public/resource-assets/5729d034-a6c7-4f35-b81c-fcac447289c7/page3_plotting_grid_1.png
```

Both URLs return HTTP 200 without authentication.

---

## API Impact

### What Changed

- **No existing API endpoints were modified or broken.**
- The FastAPI backend (`main.py`) is unchanged.
- The semantic retrieval pipeline is unchanged.
- `resources.content` JSON is unchanged.

### What's New (not yet exposed via API)

- `resource_assets` table is accessible via PostgREST (`/rest/v1/resource_assets`)
  but has no dedicated FastAPI endpoint yet.
- Storage URLs are publicly accessible directly from Supabase Storage CDN.

### What Session 2 Should Add

- `GET /api/resources/{resource_id}/assets` — List all visual assets for a
  resource (queries `resource_assets` table, returns array of asset objects
  with storage_url).
- Integration into the existing resource detail endpoint to include assets
  in the response payload.

---

## Remaining Limitations

1. **`linked_question_id` is NULL for all assets.** The semantic pipeline's
   relationship map (in `resources.content` JSON) already encodes which question
   links to which asset, but populating this column requires cross-referencing
   the semantic JSON. This is left for a future milestone.

2. **Vector-drawn graphs are not extracted.** The current pipeline only
   extracts embedded raster images. If a worksheet contains a vector-drawn
   graph (PDF drawing commands, not an embedded raster), it would be missed.
   The infrastructure has a placeholder for this (Pass 2 in `asset_extractor.py`)
   but it is not implemented. The Golden Dataset's graph IS an embedded raster,
   so this works correctly for it.

3. **Asset type classification is heuristic-based.** The current classifier
   uses page text keywords and aspect ratio. More complex worksheets may
   misclassify diagrams, apparatus, or photographs. The default is `figure`
   for unknown types — this is safe but imprecise.

4. **Storage cleanup on resource deletion is not automatic.** Deleting a
   resource cascades to delete `resource_assets` rows (via FK CASCADE), but
   the Storage objects remain in the bucket. A Storage API cleanup function
   should be added in a future milestone.

5. **Pipeline is not integrated into `master_ingestion.py`.** The asset
   pipeline runs as a standalone CLI. A future milestone should call it from
   within the master ingestion flow so assets are extracted automatically when
   a new worksheet is ingested.

6. **No duplicate detection.** Re-running the pipeline on the same resource
   creates new rows (delete-then-insert). The storage upload is idempotent
   (overwrite via `x-upsert`), but the DB rows are not deduplicated. Currently
   this is handled by deleting old rows before re-running.

7. **No bounding boxes for vector graphics.** The bounding_box column is
   populated only for embedded raster images. Vector graphics would need
   `page.get_drawings()` bounding box derivation.

8. **Content verification is limited.** The non-white pixel ratio check detects
   blank images but does not verify the image is actually a graph (vs. a
   diagram or photo). True semantic content verification requires vision-model
   analysis (future milestone).

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Header/logo heuristic may fail on new worksheets with different layouts | LOW | Heuristic is based on placement (top-of-page + full-width), not hardcoded xref. Most publisher logos match this pattern. |
| Asset type misclassification for worksheets without "distance-time" keywords | MEDIUM | Default falls to `figure`, which is safe. Can be refined with ML classification later. |
| Storage bucket is public — no access control on assets | LOW | Assets are educational worksheets (not sensitive). Public reads match the existing resources.content pattern. |
| No automatic Storage cleanup on resource deletion | MEDIUM | Manual cleanup possible via Storage API. Add a trigger or cleanup function in future milestone. |
| Pipeline is not run automatically during ingestion | MEDIUM | Must be run manually via CLI. Integrate into master_ingestion.py in next milestone. |
| Supabase Management API access token may expire | LOW | Token is in root `.env`. Pipeline uses service-role key for Storage and DB, which does not expire. |
| Pillow (`PIL`) dependency for content verification | LOW | Pillow is already installed in the venv (used by PyMuPDF ecosystem). Not a new external dependency. |

---

## Acceptance Tests

All tests verified at end of session:

| # | Test | Result | Evidence |
|---|---|---|---|
| 1 | Golden worksheet ingests successfully | **PASS** | PDF opened, 2 assets extracted from 3 pages |
| 2 | Graph extracted | **PASS** | page=2, asset_type=graph, 557x360, bbox preserved |
| 3 | Graph uploaded to Supabase Storage | **PASS** | HTTP 200 on public URL, 20,443 bytes, valid PNG header |
| 4 | resource_assets populated | **PASS** | 2 rows in table (graph + plotting_grid) |
| 5 | No local filesystem dependency | **PASS** | All storage_paths are bucket-relative (no absolute paths) |
| 6 | Existing semantic JSON still generated | **PASS** | resources.content JSON unchanged (9 items, verified via REST API) |
| 7 | Existing parser behavior preserved | **PASS** | master_ingestion.py / resource_ingestion.py NOT modified |
| 8 | Existing retrieval remains functional | **PASS** | resources endpoint returns same data as before |

### Reproducing the Acceptance Tests

```bash
# Run the pipeline (includes built-in verification)
cd /home/alsuni/Alsini-physics-platform
backend/.venv/bin/python backend/pipeline/run_asset_pipeline.py

# Or independently verify the DB + Storage state:
backend/.venv/bin/python -c "
import os, requests
from dotenv import load_dotenv
load_dotenv('backend/.env')
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
h = {'apikey': key, 'Authorization': f'Bearer {key}'}
r = requests.get(f'{url}/rest/v1/resource_assets?resource_id=eq.5729d034-a6c7-4f35-b81c-fcac447289c7&select=*', headers=h)
for row in r.json():
    accessible = requests.head(row['storage_url']).status_code == 200
    print(f'  {row[\"asset_type\"]} page {row[\"page_number\"]}: URL accessible={accessible} verified={row[\"content_verified\"]}')
"
```

---

## Known Issues

1. **Pyright type warnings in `asset_extractor.py`** (lines 226, 229): The
   `page.get_text()` return type annotation in PyMuPDF's stub is
   `list | str | dict` but the runtime always returns `str`. The code works
   correctly at runtime. These are false-positive type-checker warnings, not
   bugs.

2. **The `content_markdown` column** on `resources` was created as part of
   this migration but is not populated. It exists for future milestones where
   the semantic JSON can be rendered as markdown.

3. **No `__pycache__` cleanup.** Running the pipeline creates Python bytecode
   cache files in `backend/pipeline/`. These are harmless and standard.

---

## Repository Status

```
Branch: multimodalragsystem
Ahead of origin by: 1 commit (pre-existing, not from this session)

Untracked files (new in this session):
  ASSET_ARCHITECTURE.md
  ASSET_PIPELINE.md
  DATABASE_MIGRATION.md
  HANDOFF_SESSION_2.md
  backend/pipeline/__init__.py
  backend/pipeline/asset_extractor.py
  backend/pipeline/storage_uploader.py
  backend/pipeline/run_asset_pipeline.py
  migrations/mig_5_resource_assets.sql

Modified files: NONE
```

**No commits were made during this session.** All files are untracked.
Session 2 should review and commit.

---

## Git Branch

```
Branch:  multimodalragsystem
Remote:  origin/multimodalragsystem
Status: 1 commit ahead (pre-existing)
```

The work in this session is in untracked files. Suggested commit message:

```
feat(assets): implement visual asset infrastructure — Milestone 1

- Add resource_assets table (15 cols, 4 indexes, FK CASCADE, RLS)
- Create Supabase Storage bucket 'resource-assets' (public, 10MB)
- Build backend/pipeline/ package: extractor, uploader, orchestrator
- Extract graph + plotting grid from Golden Dataset, upload to Storage
- All 8 acceptance tests pass; existing pipeline unmodified
- Add ASSET_ARCHITECTURE.md, DATABASE_MIGRATION.md, ASSET_PIPELINE.md, HANDOFF_SESSION_2.md
```

---

## Suggested First Task For Session 2

**Integrate the asset pipeline into the FastAPI backend.**

The infrastructure is built but not yet exposed via the API. The frontend
cannot access `resource_assets` without a new endpoint.

Suggested implementation:

1. Add a new endpoint to `backend/main.py`:
   ```
   GET /api/resources/{resource_id}/assets
   ```
   Returns an array of asset objects from `resource_assets` (including
   `storage_url` for frontend rendering).

2. Integrate the asset pipeline call into `master_ingestion.py` so that assets
   are extracted automatically when a new PDF is ingested (after the semantic
   pipeline completes).

3. Populate `linked_question_id` in `resource_assets` by cross-referencing the
   semantic JSON's relationship map (the `resources.content` field maps
   question IDs to asset references).

---

## Recommended Reading Before Session 2

1. **`ASSET_ARCHITECTURE.md`** — Understand the storage design, asset lifecycle,
   and DB relationships. Essential for designing the API endpoint.

2. **`backend/pipeline/asset_extractor.py`** — Read the `AssetRecord` dataclass
   and `to_db_payload()` method. This defines the shape of what the API endpoint
   will return from `resource_assets`.

3. **`backend/pipeline/run_asset_pipeline.py`** — Read the `verify_asset_rows()`
   and `insert_asset_row()` functions. These show how to query
   `resource_assets` via the PostgREST API. The new FastAPI endpoint should use
   the same query pattern.

4. **`experiment/evidence/pipeline_results.json`** — Review the forensic
   findings from the original investigation. The `frontend.status: FAIL` entry
   documents WHY the graph wasn't rendering (no `<img>` tag in
   HybridDocumentViewer.jsx). This is the problem Session 2's frontend work
   will solve.

5. **`backend/main.py`** — Read the existing FastAPI endpoints to match the
   project's API conventions (response format, error handling, CORS).

6. **`DATABASE_MIGRATION.md`** — Review the schema and RLS policies to
   understand what the API endpoint can and cannot do without the service
   role key.

---

## Any Assumptions Made

1. **The Golden Dataset resource_id is `5729d034-a6c7-4f35-b81c-fcac447289c7`.**
   This assumption is based on the existing database state — this resource
   row was already present with title "Chapter 1 TRP worksheet" and a
   populated `content` JSON field (9 semantic concept nodes). It was confirmed
   via the Supabase REST API.

2. **The Pearson header logo should be excluded from assets.** The header
   image (xref=9, 1782x197) appears on all 3 pages. The heuristic filters it
   based on placement (y < 90pt, width > 85% of page width). This was not
   explicitly requested but is the only sane behavior — the header is not an
   educational asset.

3. **PNG is the appropriate output format.** The Golden Dataset's graph is
   a raster image. Converting to PNG preserves quality and ensures browser
   compatibility. If JPEG2000 or other formats are encountered in future
   worksheets, they are converted to PNG.

4. **Pillow (PIL) is available.** The venv has Pillow installed (part of
   PyMuPDF's ecosystem). It is used only for content verification (non-white
   pixel ratio). If Pillow were absent, content verification would need to
   fall back to PyMuPDF-only methods.

5. **Supabase REST API is sufficient.** No `supabase-py` SDK is used, matching
   the existing project pattern. If the project later adopts the SDK, the
   pipeline can be refactored — the module boundaries make this straightforward.

6. **The Supabase Management API access token** (`SUPABASE_ACCESS_TOKEN` in
   root `.env`) is valid and has permissions to run SQL and create buckets.
   This was confirmed by successful execution.

7. **Public storage is acceptable for educational worksheet assets.** The
   assets are derivative educational content, not sensitive data. The existing
   `resources.content` JSON is also publicly accessible via the REST API with
   no authentication, so public storage is consistent with the existing
   security posture.

8. **The PDF filename "IGCSE_Physics_Worksheet 1_Movement and Position.pdf"**
   is the original 3-page worksheet referenced in the session brief. It was
   confirmed to be 3 pages, 530,137 bytes, containing the distance-time graph
   (page 2) and blank plotting grid (page 3) described in the forensic
   investigation.
