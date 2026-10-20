# ASSET_ARCHITECTURE.md

## Visual Asset Infrastructure — Storage Design, Lifecycle, Relationships

**Milestone:** 1 — Asset Infrastructure
**Status:** Production-ready
**Date:** 2026-07-13

---

## 1. Overview

The visual asset infrastructure provides a normalized, persistent system for
storing and retrieving educational visual assets (graphs, diagrams, photographs,
apparatus images, tables-rendered-as-images, figures) extracted from PDF
worksheets.

Prior to this milestone, extracted graph assets existed only as local filesystem
paths embedded in a JSON `content` column. The frontend could not access them,
and there was no normalized asset registry. This milestone closes that gap.

### Design Principles

1. **No local filesystem dependency** — all assets live in Supabase Storage;
   the database stores bucket-relative paths and public URLs, never absolute
   filesystem paths.
2. **Parser preserved** — the existing parser (PyMuPDF) is reused, not replaced.
   The asset pipeline extends it; it does not modify `master_ingestion.py` or
   `resource_ingestion.py`.
3. **Normalized schema** — a dedicated `resource_assets` table with foreign keys,
   indexes, and RLS policies; no JSON-blob hacks.
4. **REST-only** — uses Supabase REST API and Storage API via `requests` (no
   SDK dependency), matching the existing project pattern.

---

## 2. Storage Design

### Supabase Storage Bucket

| Property | Value |
|---|---|
| Bucket name | `resource-assets` |
| Public | Yes (public read, no auth needed for GET) |
| File size limit | 10 MB per file |
| MIME types | `image/png` (default), `image/jpeg` (future) |

### Storage Path Convention

```
{resource_id}/page{N}_{asset_type}_{index}.{ext}
```

Example:
```
5729d034-a6c7-4f35-b81c-fcac447289c7/page2_graph_0.png
5729d034-a6c7-4f35-b81c-fcac447289c7/page3_plotting_grid_1.png
```

Paths are deterministic and idempotent — re-running the pipeline with the same
resource_id overwrites the same storage objects (via `x-upsert: true` header).

### Public URL Format

```
https://{project}.supabase.co/storage/v1/object/public/resource-assets/{storage_path}
```

These URLs are publicly accessible without authentication, allowing the frontend
to render them via `<img src="...">` directly.

---

## 3. Asset Lifecycle

```
┌──────────────────────────────────────────────────────────────────────┐
│                        ASSET LIFECYCLE                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. INGESTION                                                        │
│     PDF worksheet uploaded to raw_materials/                         │
│     Resource row created in `resources` table (existing pipeline)   │
│                                                                      │
│  2. EXTRACTION (asset_extractor.py)                                  │
│     PyMuPDF opens PDF, iterates pages                                │
│     Embedded raster images extracted via xref                        │
│     Header/logo images filtered out by heuristic                     │
│     Each remaining image classified (graph, diagram, figure, etc.)   │
│     Bounding boxes preserved from PDF coordinates                     │
│     Content verification (non-white pixel ratio)                     │
│     Caption generated from page text context                          │
│                                                                      │
│  3. STORAGE UPLOAD (storage_uploader.py)                             │
│     PNG bytes uploaded to Supabase Storage bucket                     │
│     x-upsert: true (idempotent overwrite)                            │
│     Returns (storage_path, public_url)                               │
│                                                                      │
│  4. DATABASE REGISTRATION (run_asset_pipeline.py)                    │
│     Row inserted into resource_assets with:                          │
│       - resource_id (FK to resources)                                │
│       - page_number, asset_type, storage_path, storage_url           │
│       - width, height, bounding_box, mime_type                       │
│       - caption, content_verified, metadata                          │
│                                                                      │
│  5. RETRIEVAL (future milestones)                                    │
│     Frontend queries resource_assets via REST API                    │
│     Receives storage_url → renders via <img src="...">               │
│     No local filesystem access needed                                │
│                                                                      │
│  6. DELETION                                                          │
│     ON DELETE CASCADE on resource_assets.resource_id FK              │
│     Deleting a resource automatically deletes its asset rows         │
│     Storage objects should be cleaned via Storage API (future)        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Database Relationships

```
┌─────────────────┐       ┌──────────────────────┐
│   resources      │       │  resource_assets     │
│─────────────────│       │──────────────────────│
│ id (UUID) PK    │◄──────│ resource_id (FK)      │
│ specification_  │  1:N  │ id (UUID) PK          │
│   point_id      │       │ page_number (INT)     │
│ title           │       │ asset_type (VARCHAR)  │
│ content (JSON)  │       │ storage_path (TEXT)   │
│ content_markdown│       │ storage_url (TEXT)    │
│ created_at      │       │ mime_type (VARCHAR)   │
└─────────────────┘       │ width (INT)           │
                          │ height (INT)          │
                          │ bounding_box (JSONB)  │
                          │ caption (TEXT)        │
                          │ linked_question_id    │
                          │ content_verified      │
                          │ metadata (JSONB)      │
                          │ created_at            │
                          └──────────────────────┘
```

### Cardinality

- One `resource` → zero or more `resource_assets` (1:N)
- Each `resource_asset` belongs to exactly one `resource`
- Deleting a resource cascades to delete its assets (`ON DELETE CASCADE`)

### Indexes

| Index | Column(s) | Purpose |
|---|---|---|
| `resource_assets_pkey` | `id` | Primary key lookup |
| `idx_resource_assets_resource_id` | `resource_id` | FK joins, per-resource queries |
| `idx_resource_assets_asset_type` | `asset_type` | Filter by type (e.g., "all graphs") |
| `idx_resource_assets_page_number` | `page_number` | Page-level queries |
| `idx_resource_assets_linked_q` | `linked_question_id` (partial) | Question-asset linkage queries |

### RLS Policies

| Policy | Command | Role | Effect |
|---|---|---|---|
| `resource_assets_public_read` | SELECT | public | Anyone can read asset metadata + URLs |
| `resource_assets_authenticated_write` | ALL | authenticated | Authenticated users can write (service role bypasses RLS) |

---

## 5. Implementation Decisions

### 5.1 Why Supabase Storage instead of base64-in-DB

Base64-encoding images into PostgreSQL JSONB columns would bloat the database,
slow down queries, and prevent CDN caching. Supabase Storage provides a
purpose-built object store with public URLs, automatic CDN distribution, and a
clean separation of metadata (DB) from binary data (Storage).

### 5.2 Why REST API instead of supabase-py SDK

The existing project codebase (`resource_ingestion.py`, `master_ingestion.py`)
uses raw REST API calls via `requests`. Adding the `supabase-py` SDK would
introduce a new dependency and diverge from the established pattern. The REST
API is fully capable for CRUD operations on tables and storage.

### 5.3 Why PNG instead of preserving original format

PDFs often embed images in various formats (JPEG, JPEG2000, FLATE). Converting
all extracted images to PNG ensures a uniform MIME type, lossless quality for
educational content (graphs, diagrams need sharp edges), and universal browser
support.

### 5.4 Header/logo filtering

The Pearson header logo appears on every page of the worksheet (xref=9,
1782x197, placed at y < 82pt, spanning nearly the full page width). Filtering
is based on placement heuristics — NOT hardcoded xref values — so it adapts to
other worksheets with different publisher headers.

### 5.5 Content verification

Each extracted image undergoes a non-white pixel ratio check (>0.5% non-white
= `content_verified=true`). This catches blank/placeholder images and flags them
in the database for manual review. The metadata column stores the exact
`non_white_pct` for auditing.

### 5.6 Asset type classification

Classification uses a heuristic combining page text context and image aspect
ratio:

| Condition | Classification |
|---|---|
| Page text contains "distance-time" / "velocity-time" + landscape aspect ratio | `graph` |
| Page text contains "plot a velocity" | `plotting_grid` |
| Square-ish (0.8 < aspect < 1.3) + size > 300px | `plotting_grid` |
| None of the above | `figure` (default) |

This is intentionally simple for Milestone 1. Future milestones may add
ML-based classification for diagrams, apparatus, and photographs.

### 5.7 linked_question_id

The `linked_question_id` column is populated as `None` for the Golden Dataset.
The existing semantic pipeline (OpenKB concept nodes in `resources.content`)
already encodes question→asset relationships. A future milestone can populate
this column by cross-referencing the semantic JSON's relationship map with the
extracted assets.

---

## 6. Module Architecture

```
backend/pipeline/
├── __init__.py              # Package marker
├── asset_extractor.py       # PyMuPDF extraction + classification
├── storage_uploader.py      # Supabase Storage upload
└── run_asset_pipeline.py    # CLI entry point — orchestrates all stages
```

### Responsibility Separation

| Module | Responsibility | Dependencies |
|---|---|---|
| `asset_extractor.py` | Open PDF, extract images, classify, verify content | PyMuPDF, Pillow |
| `storage_uploader.py` | Upload PNG bytes to Supabase Storage, return URLs | requests |
| `run_asset_pipeline.py` | Orchestrate extraction → upload → DB insert → verify | All above + dotenv |

No module imports from `master_ingestion.py` or `resource_ingestion.py`.
The asset pipeline is fully decoupled from the semantic pipeline.
