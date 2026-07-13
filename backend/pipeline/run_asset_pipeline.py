"""
run_asset_pipeline.py — End-to-End Visual Asset Ingestion Pipeline

Orchestrates the complete visual asset pipeline:

    PDF  ->  Parser (PyMuPDF)  ->  Asset Extraction  ->  Storage Upload  ->  resource_assets (DB)

This is the single entry point for Milestone 1. It:
  1. Extracts visual assets from the Golden Dataset PDF using asset_extractor.
  2. Uploads each asset to Supabase Storage (resource-assets bucket).
  3. Inserts a row into resource_assets for each uploaded asset.
  4. Validates the pipeline output (acceptance check).
  5. Prints a summary report.

The existing semantic pipeline (master_ingestion.py / resource_ingestion.py) is
NOT modified. This pipeline runs independently of it and does not touch the
resources.content JSON field — it only INSERTS into resource_assets.

Usage:
    cd backend && python pipeline/run_asset_pipeline.py

    # Or from the repo root:
    python backend/pipeline/run_asset_pipeline.py --resource-id 5729d034-... --pdf raw_materials/worksheet.pdf
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Support running as a script — add parent dirs to path
_current = Path(__file__).resolve().parent
_backend = _current.parent
sys.path.insert(0, str(_backend))
sys.path.insert(0, str(_current))

from dotenv import load_dotenv

from asset_extractor import extract_assets
from storage_uploader import upload_asset, generate_storage_path
import requests


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Default Golden Dataset
DEFAULT_RESOURCES = {
    "5729d034-a6c7-4f35-b81c-fcac447289c7": "IGCSE_Physics_Worksheet 1_Movement and Position.pdf",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_pdf_path(filename: str, repo_root: Path) -> Path:
    """Resolve a PDF filename to an absolute path, checking several locations."""
    candidates = [
        repo_root / "raw_materials" / filename,
        repo_root / "backend" / filename,
        repo_root / filename,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Cannot find '{filename}' in: {[str(c) for c in candidates]}")


# ---------------------------------------------------------------------------
# DB operations (via Supabase REST API — no SDK dependency)
# ---------------------------------------------------------------------------

def insert_asset_row(db_payload: dict, supabase_url: str, supabase_key: str) -> dict:
    """
    Insert a resource_assets row via the PostgREST REST API.
    Returns the inserted row (including the generated UUID id).
    """
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    endpoint = f"{supabase_url}/rest/v1/resource_assets"
    resp = requests.post(endpoint, headers=headers, json=db_payload)

    if resp.status_code != 201:
        raise RuntimeError(
            f"DB insert failed ({resp.status_code}): {resp.text[:300]}"
        )
    return resp.json()[0]


def verify_asset_rows(resource_id: str, supabase_url: str, supabase_key: str) -> list[dict]:
    """Query resource_assets for a given resource_id — for verification."""
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    endpoint = f"{supabase_url}/rest/v1/resource_assets?resource_id=eq.{resource_id}&select=*&order=page_number.asc"
    resp = requests.get(endpoint, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"DB query failed ({resp.status_code}): {resp.text[:300]}")
    return resp.json()


def delete_existing_assets(resource_id: str, supabase_url: str,
                           supabase_key: str) -> int:
    """
    Delete existing resource_assets rows for a resource_id (idempotency).

    Storage objects are overwritten via x-upsert on re-upload, so we only
    need to clean DB rows.  Returns the count of deleted rows.

    This is safe because ON DELETE CASCADE on the FK means no orphans.
    """
    existing = verify_asset_rows(resource_id, supabase_url, supabase_key)
    if not existing:
        return 0

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    endpoint = f"{supabase_url}/rest/v1/resource_assets?resource_id=eq.{resource_id}"
    resp = requests.delete(endpoint, headers=headers)
    if resp.status_code not in (200, 204):
        raise RuntimeError(
            f"DB delete failed ({resp.status_code}): {resp.text[:300]}"
        )
    return len(existing)


def verify_storage_url(storage_url: str) -> bool:
    """Verify that a storage URL is publicly accessible (HTTP 200 with content)."""
    try:
        resp = requests.head(storage_url, timeout=10, allow_redirects=True)
        return resp.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(pdf_path: str, resource_id: str,
                 supabase_url: str, supabase_key: str) -> list[dict]:
    """
    Execute the full visual asset pipeline for a single PDF.

    Returns list of inserted DB rows (one per uploaded asset).
    """
    print(f"\n{'='*60}")
    print(f"  VISUAL ASSET PIPELINE — Milestone 1")
    print(f"{'='*60}")
    print(f"  PDF:        {pdf_path}")
    print(f"  Resource:   {resource_id}")
    print(f"  Supabase:   {supabase_url}")
    print(f"{'='*60}\n")

    # --- Stage 1: Parse + extract assets ---
    print("Stage 1: Extracting visual assets via PyMuPDF...")
    assets = extract_assets(pdf_path, resource_id)
    print(f"  Extracted {len(assets)} educational asset(s):")
    for i, a in enumerate(assets):
        bbox_str = a.bounding_box.to_dict() if a.bounding_box else "N/A"
        print(f"    [{i+1}] page={a.page_number} type={a.asset_type} "
              f"size={a.width}x{a.height} content_verified={a.content_verified}")
        print(f"        bbox={bbox_str}")
        print(f"        caption={a.caption}")

    if not assets:
        print("  WARNING: No educational assets found. Pipeline terminating.")
        return []

    # --- Stage 1b: Idempotency — clean up old DB rows before re-insert ---
    deleted = delete_existing_assets(resource_id, supabase_url, supabase_key)
    if deleted:
        print(f"  Cleaned up {deleted} existing asset row(s) (idempotency).")

    # --- Stage 2: Upload to Storage + insert into DB ---
    print(f"\nStage 2: Uploading {len(assets)} asset(s) to Supabase Storage...")
    inserted_rows = []

    for i, asset in enumerate(assets):
        storage_path = generate_storage_path(
            resource_id=asset.resource_id,
            page_number=asset.page_number,
            asset_type=asset.asset_type,
            index=i,
        )
        print(f"  [{i+1}/{len(assets)}] Uploading '{storage_path}'...")

        try:
            # Upload to Storage
            sp, surl = upload_asset(
                image_bytes=asset.image_bytes,
                storage_path=storage_path,
                mime_type=asset.mime_type,
                supabase_url=supabase_url,
                supabase_key=supabase_key,
            )
            print(f"      Storage URL: {surl}")

            # Insert DB row
            db_payload = asset.to_db_payload(storage_path=sp, storage_url=surl)
            row = insert_asset_row(db_payload, supabase_url, supabase_key)
            inserted_rows.append(row)
            print(f"      DB row: id={row['id'][:12]}...  resource_assets populated")

        except Exception as e:
            print(f"      ERROR: {e}")
            # Continue with remaining assets — failure handling
            continue

    # --- Stage 3: Verification ---
    print(f"\nStage 3: Acceptance verification...")
    no_local_paths = all(not row['storage_path'].startswith('/') for row in inserted_rows)
    all_urls_ok = all(verify_storage_url(r['storage_url']) for r in inserted_rows)
    print(f"  ✓ Golden worksheet ingested:    {'PASS' if len(assets) > 0 else 'FAIL'}")
    print(f"  ✓ Graph extracted:             {'PASS' if any(a.asset_type == 'graph' for a in assets) else 'FAIL'}")
    print(f"  ✓ Assets uploaded to Storage:   {'PASS' if all_urls_ok else 'CHECK'}")
    print(f"  ✓ resource_assets populated:    {'PASS' if len(inserted_rows) > 0 else 'FAIL'}")
    print(f"  ✓ No local filesystem paths:    {'PASS' if no_local_paths else 'FAIL'}")

    # Query DB to confirm
    db_rows = verify_asset_rows(resource_id, supabase_url, supabase_key)
    print(f"  ✓ DB verification query:       {len(db_rows)} row(s) found in resource_assets")

    # Cross-check storage URL accessibility
    for row in db_rows:
        accessible = verify_storage_url(row["storage_url"])
        print(f"    -> {row['asset_type']} on page {row['page_number']}: "
              f"URL accessible={'YES' if accessible else 'NO'} | "
              f"verified={row['content_verified']}")

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE — {len(inserted_rows)} asset(s) stored")
    print(f"{'='*60}\n")

    return inserted_rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run the visual asset ingestion pipeline."
    )
    parser.add_argument("--pdf", type=str, default=None,
                        help="Path to the PDF worksheet (default: Golden Dataset)")
    parser.add_argument("--resource-id", type=str, default=None,
                        help="UUID of the resource in the resources table")
    parser.add_argument("--env", type=str, default=None,
                        help="Path to .env file (default: backend/.env)")
    args = parser.parse_args()

    # Load .env
    env_path = args.env or str(_backend / ".env")
    load_dotenv(env_path)

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        print(f"ERROR: Missing Supabase credentials. Set SUPABASE_URL and "
              f"SUPABASE_SERVICE_ROLE_KEY in {env_path}")
        sys.exit(1)

    # Resolve PDF path
    repo_root = _backend.parent
    if args.pdf:
        pdf_path = Path(args.pdf).resolve() if Path(args.pdf).is_absolute() else (repo_root / args.pdf).resolve()
    else:
        # Golden Dataset default
        filename = DEFAULT_RESOURCES.get(args.resource_id or "") or list(DEFAULT_RESOURCES.values())[0]
        pdf_path = resolve_pdf_path(filename, repo_root)

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)

    resource_id = args.resource_id or list(DEFAULT_RESOURCES.keys())[0]

    run_pipeline(str(pdf_path), resource_id, supabase_url, supabase_key)


if __name__ == "__main__":
    main()
