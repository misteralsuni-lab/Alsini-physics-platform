"""
linked_question_resolver.py — Populate linked_question_id on resource_assets

Cross-references the semantic JSON in `resources.content` (the OpenKB concept
graph produced by master_ingestion.py / resource_ingestion.py) with the
extracted visual asset rows in `resource_assets` to populate the
`linked_question_id` column.

The resolver works in two complementary ways:

1. CAPTION PARSING  —  The asset_extractor's `_build_caption()` function
   already embeds question IDs in caption text (e.g. "...page 2, Q4").
   A regex extracts `Q{n}` (optionally followed by a sub-letter).

2. SEMANTIC JSON MATCHING  —  If `resources.content` contains the structured
   educational JSON produced by the experiment pipeline (with a
   `relationships` array that maps question IDs to asset references), this
   module matches asset rows to question IDs using page_number overlap.

Usage:
    from pipeline.linked_question_resolver import resolve_linked_questions
    updated_count = resolve_linked_questions(resource_id, supabase_url, supabase_key)
"""

import re
import json
import requests
from typing import Optional


# Regex for question IDs in caption text: "Q4", "Q5a", "Q12c"
_QID_PATTERN = re.compile(r"Q(\d+[a-z]?)", re.IGNORECASE)


# ------------------------------------------------------------------
# Supabase helpers
# ------------------------------------------------------------------

def _supabase_headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _fetch_resource_content(resource_id: str, supabase_url: str,
                            key: str) -> Optional[list | dict]:
    """Fetch resources.content JSON for the given resource."""
    h = _supabase_headers(key)
    endpoint = (
        f"{supabase_url}/rest/v1/resources"
        f"?id=eq.{resource_id}&select=content"
    )
    resp = requests.get(endpoint, headers=h, timeout=15)
    if resp.status_code != 200 or not resp.json():
        return None
    return resp.json()[0].get("content")


def _fetch_asset_rows(resource_id: str, supabase_url: str,
                      key: str) -> list[dict]:
    """Fetch resource_assets rows where linked_question_id IS NULL."""
    h = _supabase_headers(key)
    endpoint = (
        f"{supabase_url}/rest/v1/resource_assets"
        f"?resource_id=eq.{resource_id}&linked_question_id=is.null&select=*"
    )
    resp = requests.get(endpoint, headers=h, timeout=15)
    if resp.status_code != 200:
        return []
    return resp.json()


def _update_linked_qid(asset_id: str, linked_qid: str,
                      supabase_url: str, key: str) -> bool:
    """Patch a single resource_assets row to set linked_question_id."""
    h = _supabase_headers(key)
    endpoint = f"{supabase_url}/rest/v1/resource_assets?id=eq.{asset_id}"
    resp = requests.patch(endpoint, headers=h,
                          json={"linked_question_id": linked_qid},
                          timeout=15)
    return resp.status_code in (200, 204)


# ------------------------------------------------------------------
# Resolution logic
# ------------------------------------------------------------------

def _parse_qid_from_caption(caption: Optional[str]) -> Optional[str]:
    """Extract a question ID (e.g. 'Q4', 'Q5a') from a caption string."""
    if not caption:
        return None
    matches = _QID_PATTERN.findall(caption)
    if matches:
        # Normalize to uppercase Q + lowercase sub-letter (e.g. "q4a" → "Q4a")
        qid = matches[0]
        return f"Q{qid[0]}{qid[1:].lower()}" if len(qid) > 1 else f"Q{qid}"
    return None


def _build_qid_to_page_map(content: Optional[list | dict]) -> dict[str, int]:
    """
    Build a {question_id: page_number} map from the structured educational
    JSON content (if it contains a 'questions' or 'relationships' array).
    """
    qid_map: dict[str, int] = {}
    if not content:
        return qid_map

    # Handle list-of-concepts (the OpenKB format) — no question IDs here.
    # Handle structured_educational.json format (dict with 'questions' key)
    if isinstance(content, dict):
        questions = content.get("questions", [])
        for q in questions:
            qid = q.get("qid") or q.get("id")
            page = q.get("page") or q.get("source_page")
            if qid and page:
                qid_map[qid] = int(page)
            # Also map sub-questions if present
            for sub in q.get("sub_questions", []):
                sub_match = re.match(r"(\d+[a-z]?)", sub.strip())
                if sub_match:
                    sub_qid = f"Q{sub_match.group(1)}"
                    if page:
                        qid_map[sub_qid] = int(page)

    elif isinstance(content, list):
        # The experiment's structured output stores questions inside a list
        for item in content:
            if isinstance(item, dict):
                qid = item.get("qid")
                page = item.get("page") or item.get("source_page")
                if qid and page:
                    qid_map[qid] = int(page)

    return qid_map


def resolve_linked_questions(resource_id: str, supabase_url: str,
                             supabase_key: str) -> dict:
    """
    Populate `linked_question_id` on resource_assets rows that are currently
    NULL, using the following strategy:

    1. Parse the question ID from the asset caption (primary method).
    2. Cross-reference with the semantic JSON's question→page map if
       a structured educational JSON is found in resources.content.

    Returns a summary dict: {resolved: int, unresolved: int, total: int}
    """
    # Fetch unlinked asset rows
    asset_rows = _fetch_asset_rows(resource_id, supabase_url, supabase_key)
    total = len(asset_rows)
    if total == 0:
        return {"resolved": 0, "unresolved": 0, "total": 0}

    # Fetch semantic content for cross-referencing
    content = _fetch_resource_content(resource_id, supabase_url, supabase_key)
    qid_page_map = _build_qid_to_page_map(content)

    resolved = 0
    unresolved = 0

    for row in asset_rows:
        asset_id = row["id"]
        caption = row.get("caption")
        page_number = row.get("page_number")
        linked_qid = None

        # Strategy 1: parse from caption
        caption_qid = _parse_qid_from_caption(caption)
        if caption_qid:
            linked_qid = caption_qid

        # Strategy 2: cross-reference page_number with semantic JSON
        if not linked_qid and qid_page_map and page_number is not None:
            # Find question IDs that belong to the same page
            page_qids = [
                qid for qid, pg in qid_page_map.items()
                if pg == page_number
            ]
            if len(page_qids) == 1:
                linked_qid = page_qids[0]
            elif len(page_qids) > 1:
                # Ambiguous — pick the one whose sub-question matches caption
                # e.g. "Q5a" on the same page as Q5
                if caption_qid:
                    for pqid in page_qids:
                        if pqid.startswith(caption_qid.rstrip("a-z")):
                            linked_qid = caption_qid
                            break
                if not linked_qid:
                    # Default to the parent Q (first in list)
                    linked_qid = page_qids[0]

        if linked_qid:
            _update_linked_qid(asset_id, linked_qid, supabase_url, supabase_key)
            resolved += 1
        else:
            unresolved += 1

    return {"resolved": resolved, "unresolved": unresolved, "total": total}
