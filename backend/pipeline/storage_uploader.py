"""
storage_uploader.py — Supabase Storage Upload for Visual Assets

Uploads extracted visual assets to the 'resource-assets' Supabase Storage bucket
and returns permanent public storage references (path + URL) for each asset.

Prerequisites:
  - Storage bucket 'resource-assets' must exist (created via DATABASE_MIGRATION.md)
  - SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in environment

Key design:
  - Uploads via the Supabase Storage REST API (no SDK dependency — matches
    the project's existing pattern of using raw REST/requests).
  - Generates durable storage paths: {resource_id}/{page}_{asset_type}_{index}.png
  - Returns (storage_path, storage_url) for each uploaded asset.
  - Storage URLs are public (bucket is public) — the frontend can <img src=…>
    them directly with no auth header.
"""

import os
import requests
from typing import Optional

BUCKET_NAME = "resource-assets"

_STORAGE_BASE = "{supabase_url}/storage/v1/object/public/{bucket}/{path}"
_UPLOAD_BASE = "{supabase_url}/storage/v1/object/{bucket}/{path}"


def upload_asset(image_bytes: bytes,
                 storage_path: str,
                 mime_type: str,
                 supabase_url: str,
                 supabase_key: str) -> tuple[str, str]:
    """
    Upload image bytes to the Supabase Storage bucket.

    Args:
        image_bytes:  PNG-encoded image data.
        storage_path: Key within the bucket (e.g. '{resource_id}/page2_graph.png').
        mime_type:    MIME type (e.g. 'image/png').
        supabase_url: Project URL (no trailing slash).
        supabase_key: Service-role key (bypasses RLS).

    Returns:
        (storage_path, public_storage_url) — both strings.

    Raises:
        RuntimeError on upload failure.
    """
    upload_url = _UPLOAD_BASE.format(
        supabase_url=supabase_url.rstrip("/"),
        bucket=BUCKET_NAME,
        path=storage_path,
    )

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": mime_type,
        # x-upsert ensures re-running the pipeline overwrites cleanly (idempotent)
        "x-upsert": "true",
    }

    resp = requests.post(upload_url, headers=headers, data=image_bytes)

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Storage upload failed ({resp.status_code}) for '{storage_path}': "
            f"{resp.text[:300]}"
        )

    public_url = _STORAGE_BASE.format(
        supabase_url=supabase_url.rstrip("/"),
        bucket=BUCKET_NAME,
        path=storage_path,
    )

    return storage_path, public_url


def generate_storage_path(resource_id: str, page_number: int,
                           asset_type: str, index: int,
                           extension: str = "png") -> str:
    """
    Generate a deterministic storage path for an asset.

    Format: {resource_id}/page{N}_{asset_type}_{index}.{ext}
    """
    return f"{resource_id}/page{page_number}_{asset_type}_{index}.{extension}"
