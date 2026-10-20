# ASSET_PIPELINE.md

## Parser Output, Upload Process, Metadata Generation, Failure Handling

**Milestone:** 1 — Asset Infrastructure
**Date:** 2026-07-13

---

## 1. Pipeline Flow

```
┌──────────────┐
│  PDF File     │  raw_materials/IGCSE_Physics_Worksheet 1_Movement and Position.pdf
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  PyMuPDF     │  Parser (fitz.open)
│  (Parser)    │  page.get_images(full=True) → xref list
│              │  page.get_image_rects(xref) → placement bbox
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Asset        │  asset_extractor.extract_assets()
│  Extraction   │  - Header/logo filtering (placement heuristic)
│              │  - Asset type classification (text context + aspect ratio)
│              │  - Content verification (non-white pixel ratio via PIL)
│              │  - Caption generation (page text context)
│              │  - Output: List[AssetRecord] with PNG bytes + metadata
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Storage      │  storage_uploader.upload_asset()
│  Upload       │  POST https://{project}.supabase.co/storage/v1/object/resource-assets/{path}
│              │  Headers: x-upsert: true (idempotent)
│              │  Body: raw PNG bytes
│              │  Output: (storage_path, public_storage_url)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  DB Insert    │  run_asset_pipeline.insert_asset_row()
│  (REST API)  │  POST https://{project}.supabase.co/rest/v1/resource_assets
│              │  Headers: Prefer: return=representation
│              │  Body: JSON payload (storage_path + url + metadata, no bytes)
│              │  Output: inserted row with generated UUID
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Existing     │  resources.content JSON (semantic pipeline) — UNCHANGED
│  Semantic     │  master_ingestion.py / resource_ingestion.py — UNMODIFIED
│  JSON         │  Retrieval via REST API — UNCHANGED
└──────────────┘
```

---

## 2. Parser Output

### Input

The parser operates on the Golden Dataset:
```
raw_materials/IGCSE_Physics_Worksheet 1_Movement and Position.pdf
```

- 3 pages, 530,137 bytes
- Standard A4 size (595.25 x 842.0 pt)

### Extraction Process

For each page, the parser:

1. `page.get_images(full=True)` — Retrieves all embedded raster images with
   their xref, dimensions, and color space.

2. `page.get_image_rects(xref)` — Retrieves the placement rectangle(s) for
   each image on the page (bounding box in PDF points).

3. `fitz.Pixmap(doc, xref)` — Extracts the raw pixel data from the embedded
   image at its original resolution. CMYK colorspaces are converted to RGB.

4. `pix.tobytes("png")` — Encodes the image as PNG bytes.

### Output: AssetRecord objects

Each extracted asset is returned as an `AssetRecord` dataclass:

```python
AssetRecord(
    resource_id="5729d034-a6c7-4f35-b81c-fcac447289c7",
    page_number=2,
    asset_type="graph",
    image_bytes=b'\x89PNG\r\n...',       # PNG-encoded bytes
    mime_type="image/png",
    width=557,
    height=360,
    bounding_box=BoundingBox(x0=193.0, y0=130.0, x1=402.0, y1=265.0),
    caption="Distance-time graph of Usain Bolt's 100m training run (page 2, Q4)",
    linked_question_id=None,
    content_verified=True,
    metadata={"non_white_pct": 12.34, "source_xref": 19, "extraction_method": "embedded_raster"}
)
```

### Golden Dataset Extraction Results

| # | Page | Asset Type | Dimensions | Bounding Box | Content Verified |
|---|---|---|---|---|---|
| 1 | 2 | graph | 557x360 | (193.0, 130.0, 402.0, 265.0) | True |
| 2 | 3 | plotting_grid | 650x557 | (175.5, 130.0, 419.5, 339.0) | True |

The Pearson header logo (xref=9, 1782x197, on all 3 pages) was correctly
filtered out by the header-detection heuristic.

---

## 3. Upload Process

### Storage Path Generation

```python
generate_storage_path(resource_id, page_number, asset_type, index) → str
```

Format: `{resource_id}/page{N}_{asset_type}_{index}.png`

### Upload Request

```
POST https://{project}.supabase.co/storage/v1/object/resource-assets/{storage_path}

Headers:
  apikey: {service_role_key}
  Authorization: Bearer {service_role_key}
  Content-Type: image/png
  x-upsert: true                          ← idempotent overwrite

Body: raw PNG bytes
```

### Response

```
200 OK
{"Key": "resource-assets/{storage_path}", "Id": "..."}

Public URL (constructed):
https://{project}.supabase.co/storage/v1/object/public/resource-assets/{storage_path}
```

### Idempotency

The `x-upsert: true` header ensures that re-running the pipeline with the same
resource_id overwrites existing storage objects rather than creating duplicates.
DB rows use upsert-like behavior via delete-then-insert or can be made
idempotent in a future milestone.

---

## 4. Metadata Generation

Every asset row in `resource_assets` includes the following metadata:

### Core Metadata (dedicated columns)

| Field | Source | Example |
|---|---|---|
| `page_number` | PyMuPDF page index + 1 | 2 |
| `asset_type` | Classification heuristic | `graph` |
| `storage_path` | Deterministic path generator | `{resource_id}/page2_graph_0.png` |
| `storage_url` | Storage API response | `https://{project}.supabase.co/storage/v1/object/public/resource-assets/...` |
| `mime_type` | Fixed for PNG output | `image/png` |
| `width` | PyMuPDF Pixmap width | 557 |
| `height` | PyMuPDF Pixmap height | 360 |
| `bounding_box` | PDF coordinates from `get_image_rects` | `{"x0": 193.0, "y0": 130.0, "x1": 402.0, "y1": 265.0}` |
| `caption` | Generated from page text context | Distance-time graph of Usain Bolt's 100m training run (page 2, Q4) |
| `content_verified` | Non-white pixel ratio > 0.5% | true |
| `linked_question_id` | Not populated in Milestone 1 (future) | None |

### Extended Metadata (JSONB metadata column)

```json
{
    "non_white_pct": 12.34,        // percentage of non-white pixels
    "source_xref": 19,              // PyMuPDF xref of the source image in the PDF
    "extraction_method": "embedded_raster"  // how the image was extracted
}
```

### Bounding Box

Bounding boxes are in PDF point coordinates (0,0 = top-left of page).
These are preserved from `page.get_image_rects(xref)` and stored as JSONB.

If a future worksheet has vector-drawn graphs (not embedded raster), bounding
boxes would be derived from the drawing rectangle instead. The metadata
`extraction_method` field would be `"vector_render"` to indicate this.

---

## 5. Failure Handling

### Extraction Failures

| Scenario | Handling |
|---|---|
| PDF cannot be opened | `fitz.open()` raises — propagated as pipeline exception |
| Image xref unreadable | Exception caught → falls back to high-DPI page region render (`page.get_pixmap(clip=bbox)`) |
| No images on page | Returns empty list for that page — not an error |
| All images filtered as headers | Returns empty asset list — flagged as WARNING in pipeline output |

### Upload Failures

| Scenario | Handling |
|---|---|
| Storage API returns 4xx/5xx | `RuntimeError` raised — pipeline logs error and CONTINUES to next asset |
| Network timeout | `requests` timeout — propagated as `RuntimeError` |
| Bucket missing | 404 from Storage API — `RuntimeError` with descriptive message |

### DB Insert Failures

| Scenario | Handling |
|---|---|
| PostgREST returns non-201 | `RuntimeError` raised — pipeline logs error and CONTINUES to next asset |
| FK violation (resource_id not in resources) | 409 from PostgREST — `RuntimeError` |
| RLS denial | 403 from PostgREST — `RuntimeError` |

### Content Verification Failures

If an extracted image has > 99.5% white pixels (blank/placeholder):
- `content_verified` is set to `false` in the DB row
- The asset is still uploaded to Storage (preserves evidence)
- `non_white_pct` is stored in metadata for auditing
- The pipeline does NOT fail — it flags for manual review

---

## 6. CLI Usage

```bash
# Default: uses Golden Dataset resource
cd backend && python pipeline/run_asset_pipeline.py

# Explicit PDF + resource_id
python backend/pipeline/run_asset_pipeline.py \
    --pdf raw_materials/worksheet.pdf \
    --resource-id 5729d034-a6c7-4f35-b81c-fcac447289c7

# Custom .env location
python backend/pipeline/run_asset_pipeline.py --env /path/to/.env
```

### Required Environment Variables

```
SUPABASE_URL=https://{project}.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbG...    # from backend/.env
```

---

## 7. Integration with Existing Pipeline

The asset pipeline is decoupled from the existing semantic pipeline:

- `master_ingestion.py` and `resource_ingestion.py` are NOT imported or modified.
- The `resources.content` JSON column is NOT touched.
- Semantic retrieval via the REST API remains functional.
- The asset pipeline can be run independently, before or after the semantic pipeline.

### Future Integration (not in Milestone 1)

A future milestone should:
1. Call `run_asset_pipeline.run_pipeline()` from within `master_ingestion.py`
   after the semantic pipeline completes.
2. Populate `linked_question_id` by cross-referencing the semantic JSON's
   relationship map with the extracted assets.
3. Update the FastAPI backend to expose `resource_assets` via a new endpoint
   (e.g., `GET /api/resources/{id}/assets`).
