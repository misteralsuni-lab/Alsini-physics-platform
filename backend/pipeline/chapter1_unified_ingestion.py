"""
chapter1_unified_ingestion.py — Idempotent Unified RAG Ingestion for Chapter 1.

Parses the canonical Chapter 1 Marp slide deck (`content/lessons/G9-T1-W1-movement-and-position-slides.md`)
via `marp_parser.parse_marp_lesson`, constructs deterministic payloads for:
  - `public.resources` (`lesson`, `practical`, `examiner_note`)
  - `public.lessons` (Chapter 1 lesson)
  - `public.learning_blocks` (4 blocks covering specs `1.3–1.4`, `1.5–1.6`, `1.7–1.9`, `1.10`)
  - `public.resource_chunks` (`lesson_block` including `WE-` worked examples, `practical`,
    and verbatim `examiner_note` alerts), tagged with `chapter_id`, `source_type`,
    `block_id`, `spec_refs`, and `embedding_model = 'nvidia/nemotron-3.5-embed-1b'` (1024-dim).

Hard safety invariants:
  1. Curriculum boundary is strictly Edexcel 4XPH1 Chapter 1 specs `1.3–1.10`.
     Spec `1.1` (`5729d034-a6c7-4f35-b81c-fcac447289c7`) is NEVER included in Block 1
     or touched by this pipeline.
  2. Existing `worksheet` rows in `public.resource_chunks` (the 21 Chapter 1 rows)
     are NEVER modified, deleted, or re-embedded.
  3. Re-running this script is 100% idempotent via deterministic UUIDv5 identifiers
     plus scoped delete+insert restricted strictly to
     `chapter_id = CHAPTER_1_ID AND source_type IN ('lesson_block', 'practical', 'examiner_note')`.
  4. Secrets/API keys are read strictly from environment variables (never hardcoded)
     and redacted from error messages.

CLI usage:
    python backend/pipeline/chapter1_unified_ingestion.py --dry-run
    python backend/pipeline/chapter1_unified_ingestion.py --source content/lessons/G9-T1-W1-movement-and-position-slides.md
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

import requests
from dotenv import load_dotenv

# Ensure `backend/` is on sys.path when invoked directly as a script
# (e.g. `python backend/pipeline/chapter1_unified_ingestion.py --dry-run`).
_BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

try:
    from pipeline.embedding_pipeline import (
        DEFAULT_EMBED_MODEL,
        EMBED_DIM,
        _embed_texts,
        _resolve_embed_model,
        _sanitize_error,
        _vector_to_pg_string,
    )
except ImportError:
    from backend.pipeline.embedding_pipeline import (
        DEFAULT_EMBED_MODEL,
        EMBED_DIM,
        _embed_texts,
        _resolve_embed_model,
        _sanitize_error,
        _vector_to_pg_string,
    )

# ---------------------------------------------------------------------------
# Canonical Curriculum & Pipeline Constants
# ---------------------------------------------------------------------------

CHAPTER_1_UNIT_ID = "2cf312d3-0f4b-4339-84f3-97b10b2907ea"
CHAPTER_1_ID = "b95f8fac-355e-4037-bc1f-2d3b2bf77140"
LEGACY_WORKSHEET_RESOURCE_ID = "5729d034-a6c7-4f35-b81c-fcac447289c7"

CHAPTER_1_ALLOWED_SPECS: tuple[str, ...] = (
    "1.3",
    "1.4",
    "1.5",
    "1.6",
    "1.7",
    "1.8",
    "1.9",
    "1.10",
)
CHAPTER_1_EXCLUDED_SPECS: tuple[str, ...] = ("1.1",)

CHAPTER_1_BLOCK_EXPECTED_SPECS: dict[int, tuple[str, ...]] = {
    1: ("1.3", "1.4"),
    2: ("1.5", "1.6"),
    3: ("1.7", "1.8", "1.9"),
    4: ("1.10",),
}

# Canonical Edexcel 4XPH1 Chapter 1 specification_points UUIDs (specs 1.3–1.10 only;
# spec 1.1 is intentionally excluded).
CHAPTER_1_SPEC_POINT_IDS: dict[str, str] = {
    "1.3": "a70040ee-4978-4c1c-a4f5-6afd8988e530",
    "1.4": "a05e4b11-189e-4a59-b4b0-1f843f98182c",
    "1.5": "61d1267f-c37c-4be0-ac9d-1917f211a0d8",
    "1.6": "0c1f4ba4-2937-4a12-aa6f-e254c3df71cf",
    "1.7": "481c1a7b-9d28-4588-b10f-a3969c0974d9",
    "1.8": "62fb1516-d743-44d9-9707-7dc9df2a6cfd",
    "1.9": "2c68d80c-547c-42f1-a196-f084d403c4e2",
    "1.10": "09347dbc-72bb-4abc-9699-6cc411ba59e6",
}

INGESTED_RESOURCE_TYPES: tuple[str, ...] = ("lesson", "practical", "examiner_note")
INGESTED_CHUNK_SOURCE_TYPES: tuple[str, ...] = (
    "lesson_block",
    "practical",
    "examiner_note",
)

DEFAULT_SOURCE_RELATIVE_PATH = Path(
    "content/lessons/G9-T1-W1-movement-and-position-slides.md"
)
DEFAULT_BLOCK_XP_VALUE = 25
MAX_CHUNK_CHARS = 1200

# Deterministic UUIDv5 namespace anchored to Chapter 1's canonical UUID.
_CHAPTER1_UUID_NAMESPACE = uuid.UUID(CHAPTER_1_ID)


# ---------------------------------------------------------------------------
# Data Container for Built Payloads
# ---------------------------------------------------------------------------

@dataclass
class Chapter1IngestionBundle:
    """Complete, validated set of Chapter 1 payloads ready for embedding & upsert."""

    chapter_id: str
    embedding_model: str
    embedding_dim: int
    source_path: str
    resources: list[dict[str, Any]] = field(default_factory=list)
    lesson: dict[str, Any] = field(default_factory=dict)
    learning_blocks: list[dict[str, Any]] = field(default_factory=list)
    chunks: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        counts_by_source_type: dict[str, int] = {}
        counts_by_chunk_type: dict[str, int] = {}
        for chunk in self.chunks:
            st = str(chunk.get("source_type", ""))
            ct = str(chunk.get("chunk_type", ""))
            counts_by_source_type[st] = counts_by_source_type.get(st, 0) + 1
            counts_by_chunk_type[ct] = counts_by_chunk_type.get(ct, 0) + 1

        return {
            "chapter_id": self.chapter_id,
            "source_path": self.source_path,
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim,
            "resources_count": len(self.resources),
            "resource_types": [r["resource_type"] for r in self.resources],
            "lesson_id": self.lesson.get("id"),
            "lesson_slug": self.lesson.get("slug"),
            "learning_blocks_count": len(self.learning_blocks),
            "chunks_count": len(self.chunks),
            "chunks_by_source_type": counts_by_source_type,
            "chunks_by_chunk_type": counts_by_chunk_type,
            "spec_refs": list(self.lesson.get("spec_refs", [])),
        }


# ---------------------------------------------------------------------------
# Deterministic IDs, Serialization, and Validation Helpers
# ---------------------------------------------------------------------------

def deterministic_uuid(key: str) -> str:
    """Generate a deterministic UUIDv5 scoped to Chapter 1."""
    if not key or not key.strip():
        raise ValueError("Deterministic UUID key must be a non-empty string.")
    return str(uuid.uuid5(_CHAPTER1_UUID_NAMESPACE, key.strip()))


def _repo_root() -> Path:
    """Resolve repository root from `backend/pipeline/chapter1_unified_ingestion.py`."""
    return Path(__file__).resolve().parent.parent.parent


def resolve_source_path(source: str | Path | None = None) -> Path:
    """Resolve the Marp lesson source path (defaulting to the canonical Ch. 1 deck)."""
    if source is None:
        return (_repo_root() / DEFAULT_SOURCE_RELATIVE_PATH).resolve()
    candidate = Path(source)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate.resolve()
    repo_candidate = _repo_root() / candidate
    if repo_candidate.exists():
        return repo_candidate.resolve()
    return candidate.resolve()


def _normalize_source_path_label(path: str | Path) -> str:
    """Return a clean repo-relative POSIX path when inside the repo, else POSIX string."""
    p = Path(path)
    try:
        rel = p.resolve().relative_to(_repo_root().resolve())
        return rel.as_posix()
    except (ValueError, OSError):
        return p.as_posix()


def _as_dict(obj: Any) -> Any:
    """Convert parser dataclasses (via `.to_dict()`, `dataclasses.asdict`, or mapping) to plain JSON types."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, Mapping):
        return {str(k): _as_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_as_dict(item) for item in obj]
    return obj


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    """Read an attribute or mapping key uniformly."""
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def validate_spec_refs(
    spec_refs: Iterable[str],
    *,
    context: str,
    allow_empty: bool = False,
    enforce_chapter1_boundary: bool = True,
) -> list[str]:
    """
    Validate and normalize Edexcel 4XPH1 Chapter 1 spec references (`1.3–1.10`).
    Explicitly rejects Spec `1.1` and any out-of-boundary spec point.
    """
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in spec_refs or []:
        ref = str(raw).strip()
        if not ref:
            continue
        if enforce_chapter1_boundary:
            if ref in CHAPTER_1_EXCLUDED_SPECS:
                raise ValueError(
                    f"Curriculum boundary violation in {context}: Spec '{ref}' is excluded "
                    f"from Chapter 1 Learning Blocks and Unified RAG (legacy worksheet anchor only)."
                )
            if ref not in CHAPTER_1_ALLOWED_SPECS:
                raise ValueError(
                    f"Curriculum boundary violation in {context}: Spec '{ref}' is outside "
                    f"allowed Chapter 1 specs {CHAPTER_1_ALLOWED_SPECS}."
                )
        if ref not in seen:
            seen.add(ref)
            normalized.append(ref)

    if not normalized and not allow_empty:
        raise ValueError(f"Empty spec_refs in {context}: at least one valid spec ref is required.")

    # Preserve canonical curriculum order for Chapter 1 specs.
    order_index = {spec: idx for idx, spec in enumerate(CHAPTER_1_ALLOWED_SPECS)}
    normalized.sort(key=lambda s: (order_index.get(s, 999), s))
    return normalized


def validate_embedding_model(model_name: str) -> str:
    """Validate that an embedding model tag is non-empty and properly formatted."""
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("embedding_model must be a non-empty string.")
    cleaned = model_name.strip()
    if len(cleaned) > 120:
        raise ValueError(
            f"embedding_model exceeds VARCHAR(120) column limit ({len(cleaned)} chars)."
        )
    return cleaned


def validate_embedding_vector(
    vector: Sequence[float],
    *,
    expected_dim: int = EMBED_DIM,
    context: str = "chunk",
) -> list[float]:
    """Validate that an embedding vector has exact dimension (1024), finite floats, and non-zero L2 norm."""
    if isinstance(vector, (str, bytes)) or not isinstance(vector, Sequence):
        raise ValueError(f"Invalid embedding for {context}: expected a sequence of floats.")
    if len(vector) != expected_dim:
        raise ValueError(
            f"Embedding dimension mismatch for {context}: expected {expected_dim}, got {len(vector)}."
        )
    floats: list[float] = []
    norm_sq = 0.0
    for idx, val in enumerate(vector):
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(
                f"Invalid embedding coordinate at index {idx} for {context}: {type(val).__name__}"
            )
        fval = float(val)
        if not math.isfinite(fval):
            raise ValueError(
                f"Non-finite embedding coordinate at index {idx} for {context}."
            )
        floats.append(fval)
        norm_sq += fval * fval
    if norm_sq <= 0.0:
        raise ValueError(f"Zero-norm embedding vector for {context}.")
    return floats


def _split_text_cleanly(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text into chunks <= max_chars on paragraph/line/word boundaries."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]

    segments: list[str] = []
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    current = ""

    def _flush() -> None:
        nonlocal current
        if current.strip():
            segments.append(current.strip())
        current = ""

    for para in paragraphs:
        if len(para) <= max_chars:
            if not current:
                current = para
            elif len(current) + 2 + len(para) <= max_chars:
                current = f"{current}\n\n{para}"
            else:
                _flush()
                current = para
        else:
            _flush()
            # Split long paragraph by lines, then words.
            for line in para.splitlines():
                line = line.strip()
                if not line:
                    continue
                if len(line) <= max_chars:
                    if not current:
                        current = line
                    elif len(current) + 1 + len(line) <= max_chars:
                        current = f"{current}\n{line}"
                    else:
                        _flush()
                        current = line
                else:
                    _flush()
                    words = line.split()
                    buf = ""
                    for word in words:
                        if not buf:
                            buf = word
                        elif len(buf) + 1 + len(word) <= max_chars:
                            buf = f"{buf} {word}"
                        else:
                            segments.append(buf)
                            buf = word
                    if buf:
                        segments.append(buf)
    _flush()
    return segments


def _resolve_marp_parser() -> Callable[..., Any]:
    """
    Dynamically import `parse_marp_lesson` from `marp_parser`.

    Kept lazy so tests and callers can also inject a parsed lesson or mock parser
    without breaking module import across isolated workspaces.
    """
    try:
        from pipeline.marp_parser import parse_marp_lesson  # type: ignore

        return parse_marp_lesson
    except ImportError:
        try:
            from backend.pipeline.marp_parser import parse_marp_lesson  # type: ignore

            return parse_marp_lesson
        except ImportError as exc:
            raise ImportError(
                "Could not import `parse_marp_lesson` from `pipeline.marp_parser` or "
                "`backend.pipeline.marp_parser`. Ensure `backend/pipeline/marp_parser.py` is present."
            ) from exc


# ---------------------------------------------------------------------------
# Payload Builders (Pure, Deterministic, DB-Independent)
# ---------------------------------------------------------------------------

def _build_block_chunk_text(block: Any, spec_refs: list[str]) -> str:
    """Assemble student-facing RAG text for a Learning Block."""
    citation_id = str(_get_attr(block, "citation_id") or f"BLK-{_get_attr(block, 'block_index')}")
    title = str(_get_attr(block, "title") or "").strip()
    parts: list[str] = [f"[{citation_id}] {title} (Specs: {', '.join(spec_refs)})"]

    textbook_refs = _get_attr(block, "textbook_refs") or []
    if textbook_refs:
        parts.append(f"Textbook: {'; '.join(str(r) for r in textbook_refs)}")

    objectives = _get_attr(block, "learning_objectives") or []
    if objectives:
        obj_lines = [
            f"- Spec {_get_attr(o, 'spec_ref')}: {_get_attr(o, 'text')}"
            for o in objectives
            if _get_attr(o, "text")
        ]
        if obj_lines:
            parts.append("Learning objectives:\n" + "\n".join(obj_lines))

    student_md = str(_get_attr(block, "student_markdown") or "").strip()
    foundation = str(_get_attr(block, "foundation") or "").strip()
    if foundation and foundation not in student_md:
        parts.append(f"Stage 1 Foundation (prerequisite):\n{foundation}")
    if student_md:
        parts.append(student_md)

    vocab = _get_attr(block, "vocabulary") or []
    if vocab:
        vocab_lines = [
            f"- {_get_attr(v, 'term')}: {_get_attr(v, 'definition')}"
            for v in vocab
            if _get_attr(v, "term")
        ]
        if vocab_lines:
            parts.append("Key vocabulary:\n" + "\n".join(vocab_lines))

    analogies = _get_attr(block, "analogies") or []
    if analogies:
        parts.append("Analogies:\n" + "\n".join(f"- {a}" for a in analogies if str(a).strip()))

    self_checks = _get_attr(block, "self_check") or []
    if self_checks:
        sc_lines: list[str] = []
        for item in self_checks:
            q = str(_get_attr(item, "question") or "").strip()
            a = str(_get_attr(item, "answer") or "").strip()
            rem = _get_attr(item, "solo_remediation")
            line = f"- Self-Check: {q}"
            if a:
                line += f" Answer: {a}"
            if rem:
                guidance = str(_get_attr(rem, "remediation_guidance") or "").strip()
                if guidance:
                    line += f" (Solo remediation if <{_get_attr(rem, 'threshold_percent', 80)}%: {guidance})"
            sc_lines.append(line)
        if sc_lines:
            parts.append("Self-Check:\n" + "\n".join(sc_lines))

    reflections = _get_attr(block, "reflections") or []
    if reflections:
        parts.append(
            "Reflection prompts:\n"
            + "\n".join(f"- {r}" for r in reflections if str(r).strip())
        )

    return "\n\n".join(p for p in parts if p.strip())


def _build_worked_example_chunk_text(
    example: Any,
    block_citation_id: str,
    spec_refs: list[str],
) -> str:
    """Assemble student-facing RAG text for a Worked Example (`WE-`)."""
    example_id = str(_get_attr(example, "example_id") or "").strip()
    stage = str(_get_attr(example, "stage") or "model").strip()
    title = str(_get_attr(example, "title") or "").strip()
    prompt = str(_get_attr(example, "prompt") or "").strip()
    solution = str(_get_attr(example, "solution") or "").strip()
    steps = _get_attr(example, "steps") or []

    header = f"[{example_id}] Worked Example ({stage}) — {title}" if title else f"[{example_id}] Worked Example ({stage})"
    parts: list[str] = [f"{header} | Block: {block_citation_id} | Specs: {', '.join(spec_refs)}"]
    if prompt:
        parts.append(f"Problem: {prompt}")
    if steps:
        parts.append("Steps:\n" + "\n".join(f"- {s}" for s in steps if str(s).strip()))
    if solution:
        parts.append(f"Solution: {solution}")
    return "\n\n".join(parts)


def _build_practical_method_chunk_text(practical: Any, method: Any) -> str:
    """Assemble RAG text for one Spec 1.5 practical method."""
    citation_id = str(_get_attr(practical, "citation_id") or "PRC-1.5").strip()
    name = str(_get_attr(method, "name") or "").strip()
    summary = str(_get_attr(method, "summary") or "").strip()
    steps = _get_attr(method, "procedure_steps") or []
    accuracy_notes = _get_attr(method, "accuracy_notes") or []
    measurements = _get_attr(method, "measurements") or []

    parts: list[str] = [f"[{citation_id}] Practical Method (Spec 1.5): {name}"]
    if summary:
        parts.append(summary)
    if steps:
        parts.append("Procedure:\n" + "\n".join(f"- {s}" for s in steps if str(s).strip()))
    if measurements:
        parts.append("Measurements:\n" + "\n".join(f"- {m}" for m in measurements if str(m).strip()))
    if accuracy_notes:
        parts.append(
            "Accuracy & exam notes:\n"
            + "\n".join(f"- {n}" for n in accuracy_notes if str(n).strip())
        )
    return "\n\n".join(parts)


def _build_examiner_alert_chunk_text(alert: Any, spec_refs: list[str]) -> str:
    """Assemble RAG text for a verbatim Edexcel Examiner Alert (`EXM-`)."""
    alert_id = str(_get_attr(alert, "alert_id") or "").strip()
    source_citation = str(_get_attr(alert, "source_citation") or "").strip()
    exam_session = str(_get_attr(alert, "exam_session") or "").strip()
    question_ref = str(_get_attr(alert, "question_ref") or "").strip()
    paper_code = str(_get_attr(alert, "paper_code") or "").strip()
    verbatim_text = str(_get_attr(alert, "verbatim_text") or "").strip()

    if not verbatim_text:
        raise ValueError(f"Examiner alert {alert_id or '<unnamed>'} is missing verbatim_text.")

    citation_label = source_citation or " ".join(
        p for p in (paper_code, exam_session, question_ref) if p
    )
    return (
        f"[{alert_id}] Edexcel Examiner Alert (Specs: {', '.join(spec_refs)}) — "
        f"{citation_label}\n"
        f'Verbatim Examiner Report: "{verbatim_text}"'
    )


def _collect_worked_examples(parsed_lesson: Any) -> list[Any]:
    """Collect and deduplicate WorkedExample objects in deterministic order."""
    collected: list[Any] = []
    seen_ids: set[str] = set()

    def _add(we: Any) -> None:
        eid = str(_get_attr(we, "example_id") or "").strip()
        if not eid:
            return
        if eid in seen_ids:
            return
        seen_ids.add(eid)
        collected.append(we)

    for we in _get_attr(parsed_lesson, "worked_examples") or []:
        _add(we)

    for block in _get_attr(parsed_lesson, "blocks") or []:
        for we in _get_attr(block, "guided_practice") or []:
            _add(we)

    collected.sort(
        key=lambda w: (
            int(_get_attr(w, "block_index") or 0),
            int(_get_attr(w, "slide_number") or 0),
            str(_get_attr(w, "example_id") or ""),
        )
    )
    return collected


def build_chapter1_ingestion_bundle(
    parsed_lesson: Any,
    *,
    chapter_id: str = CHAPTER_1_ID,
    embedding_model: Optional[str] = None,
    enforce_chapter1_boundary: bool = True,
) -> Chapter1IngestionBundle:
    """
    Build all deterministic Supabase payloads for Chapter 1 Unified RAG ingestion
    from a `ParsedLesson` produced by `marp_parser.parse_marp_lesson`.

    Performs strict validation of:
      - Chapter 1 curriculum boundary (specs `1.3–1.10`, excluding `1.1`)
      - 4 Learning Blocks covering `(1.3–1.4, 1.5–1.6, 1.7–1.9, 1.10)`
      - Spec 1.5 Practical Guide presence
      - Verbatim Examiner Alerts presence
      - Non-collision with legacy worksheet resource `5729d034-a6c7-4f35-b81c-fcac447289c7`
      - `embedding_model` tagging (`nvidia/nemotron-3.5-embed-1b` by default)
    """
    validated_chapter_id = str(uuid.UUID(str(chapter_id).strip()))
    active_model = validate_embedding_model(_resolve_embed_model(embedding_model))

    lesson_slug = str(_get_attr(parsed_lesson, "slug") or "movement-and-position").strip()
    lesson_title = str(_get_attr(parsed_lesson, "title") or "Movement and Position").strip()
    lesson_subtitle = str(_get_attr(parsed_lesson, "subtitle") or "").strip()
    raw_source_path = str(
        _get_attr(parsed_lesson, "source_path") or DEFAULT_SOURCE_RELATIVE_PATH.as_posix()
    ).strip()
    source_path_label = _normalize_source_path_label(raw_source_path)

    lesson_spec_refs = validate_spec_refs(
        _get_attr(parsed_lesson, "spec_refs") or [],
        context="ParsedLesson",
        enforce_chapter1_boundary=enforce_chapter1_boundary,
    )

    raw_blocks = list(_get_attr(parsed_lesson, "blocks") or [])
    if enforce_chapter1_boundary and len(raw_blocks) != 4:
        raise ValueError(
            f"Chapter 1 requires exactly 4 Learning Blocks, got {len(raw_blocks)}."
        )
    raw_blocks.sort(key=lambda b: int(_get_attr(b, "block_index") or 0))

    # Validate block indices and spec boundaries before constructing rows.
    validated_block_specs: dict[int, list[str]] = {}
    covered_specs: set[str] = set()
    for expected_idx, block in enumerate(raw_blocks, start=1):
        b_idx = int(_get_attr(block, "block_index") or 0)
        if enforce_chapter1_boundary and b_idx != expected_idx:
            raise ValueError(
                f"Expected Learning Block index {expected_idx}, got {b_idx}."
            )
        b_specs = validate_spec_refs(
            _get_attr(block, "spec_refs") or [],
            context=f"LearningBlock {b_idx}",
            enforce_chapter1_boundary=enforce_chapter1_boundary,
        )
        if enforce_chapter1_boundary:
            expected_specs = CHAPTER_1_BLOCK_EXPECTED_SPECS.get(b_idx)
            if expected_specs and tuple(b_specs) != expected_specs:
                raise ValueError(
                    f"Learning Block {b_idx} spec_refs mismatch: expected {list(expected_specs)}, got {b_specs}."
                )
        validated_block_specs[b_idx] = b_specs
        covered_specs.update(b_specs)

    if enforce_chapter1_boundary and set(CHAPTER_1_ALLOWED_SPECS) != covered_specs:
        missing = sorted(set(CHAPTER_1_ALLOWED_SPECS) - covered_specs)
        raise ValueError(
            f"Chapter 1 Learning Blocks must cover all specs 1.3–1.10; missing: {missing}."
        )

    practical = _get_attr(parsed_lesson, "practical")
    if enforce_chapter1_boundary and practical is None:
        raise ValueError("Chapter 1 requires a Spec 1.5 PracticalGuide from marp_parser.")

    examiner_alerts = list(_get_attr(parsed_lesson, "examiner_alerts") or [])
    if enforce_chapter1_boundary and len(examiner_alerts) < 3:
        raise ValueError(
            f"Chapter 1 requires all 3 verbatim Examiner Alerts, got {len(examiner_alerts)}."
        )

    # ------------------------------------------------------------------
    # 1. Deterministic IDs for Resources, Lesson, and Learning Blocks
    # ------------------------------------------------------------------
    lesson_resource_id = deterministic_uuid(f"resource:lesson:{lesson_slug}")
    practical_resource_id = deterministic_uuid(f"resource:practical:{lesson_slug}:1.5")
    examiner_resource_id = deterministic_uuid(f"resource:examiner_note:{lesson_slug}")
    lesson_id = deterministic_uuid(f"lesson:{validated_chapter_id}:{lesson_slug}")

    for rid, label in (
        (lesson_resource_id, "lesson"),
        (practical_resource_id, "practical"),
        (examiner_resource_id, "examiner_note"),
    ):
        if rid == LEGACY_WORKSHEET_RESOURCE_ID:
            raise RuntimeError(
                f"Safety violation: generated {label} resource_id collided with legacy worksheet resource."
            )

    block_id_by_index: dict[int, str] = {}
    block_citation_by_index: dict[int, str] = {}
    block_slug_by_index: dict[int, str] = {}
    for block in raw_blocks:
        b_idx = int(_get_attr(block, "block_index"))
        b_slug = str(_get_attr(block, "slug") or f"block-{b_idx}").strip()
        b_citation = str(_get_attr(block, "citation_id") or f"BLK-{b_idx}").strip()
        block_id_by_index[b_idx] = deterministic_uuid(
            f"learning_block:{lesson_id}:{b_idx}:{b_slug}"
        )
        block_citation_by_index[b_idx] = b_citation
        block_slug_by_index[b_idx] = b_slug

    # ------------------------------------------------------------------
    # 2. `public.resources` rows (`lesson`, `practical`, `examiner_note`)
    # ------------------------------------------------------------------
    resources_rows: list[dict[str, Any]] = []

    lesson_markdown_parts = [
        f"## {str(_get_attr(b, 'title') or '').strip()}\n\n{str(_get_attr(b, 'student_markdown') or '').strip()}"
        for b in raw_blocks
    ]
    lesson_resource_row = {
        "id": lesson_resource_id,
        "chapter_id": validated_chapter_id,
        "specification_point_id": CHAPTER_1_SPEC_POINT_IDS["1.3"],
        "title": f"Chapter 1 Lesson: {lesson_title} (Specs 1.3–1.10)",
        "resource_type": "lesson",
        "spec_refs": lesson_spec_refs,
        "content": {
            "lesson_id": lesson_id,
            "slug": lesson_slug,
            "title": lesson_title,
            "subtitle": lesson_subtitle,
            "source_path": source_path_label,
            "spec_refs": lesson_spec_refs,
            "learning_objectives": _as_dict(_get_attr(parsed_lesson, "learning_objectives") or []),
            "vocabulary": _as_dict(_get_attr(parsed_lesson, "vocabulary") or []),
            "formulas": _as_dict(_get_attr(parsed_lesson, "formulas") or []),
            "block_slugs": [block_slug_by_index[int(_get_attr(b, "block_index"))] for b in raw_blocks],
        },
        "content_markdown": "\n\n---\n\n".join(lesson_markdown_parts),
    }
    resources_rows.append(lesson_resource_row)

    if practical is not None:
        practical_spec_refs = validate_spec_refs(
            _get_attr(practical, "spec_refs") or ["1.5"],
            context="PracticalGuide",
            enforce_chapter1_boundary=enforce_chapter1_boundary,
        )
        practical_title = str(
            _get_attr(practical, "title")
            or "Chapter 1 Practical (Spec 1.5): Motion of Everyday Objects"
        ).strip()
        practical_resource_row = {
            "id": practical_resource_id,
            "chapter_id": validated_chapter_id,
            "specification_point_id": CHAPTER_1_SPEC_POINT_IDS["1.5"],
            "title": practical_title,
            "resource_type": "practical",
            "spec_refs": practical_spec_refs,
            "content": _as_dict(practical),
            "content_markdown": str(_get_attr(practical, "student_markdown") or "").strip(),
        }
        resources_rows.append(practical_resource_row)

    if examiner_alerts:
        all_alert_specs_raw: list[str] = []
        alert_md_lines: list[str] = []
        for alert in examiner_alerts:
            a_specs = validate_spec_refs(
                _get_attr(alert, "spec_refs") or [],
                context=f"ExaminerAlert {_get_attr(alert, 'alert_id')}",
                enforce_chapter1_boundary=enforce_chapter1_boundary,
            )
            all_alert_specs_raw.extend(a_specs)
            alert_md_lines.append(_build_examiner_alert_chunk_text(alert, a_specs))
        all_alert_specs = validate_spec_refs(
            all_alert_specs_raw,
            context="ExaminerNoteResource",
            enforce_chapter1_boundary=enforce_chapter1_boundary,
        )
        examiner_resource_row = {
            "id": examiner_resource_id,
            "chapter_id": validated_chapter_id,
            "specification_point_id": CHAPTER_1_SPEC_POINT_IDS[all_alert_specs[0]],
            "title": f"Chapter 1 Examiner Report Highlights ({lesson_title})",
            "resource_type": "examiner_note",
            "spec_refs": all_alert_specs,
            "content": [_as_dict(a) for a in examiner_alerts],
            "content_markdown": "\n\n".join(alert_md_lines),
        }
        resources_rows.append(examiner_resource_row)

    # ------------------------------------------------------------------
    # 3. `public.lessons` row (matches mig_8 schema)
    # ------------------------------------------------------------------
    raw_duration = _get_attr(parsed_lesson, "duration_minutes")
    duration_minutes = (
        raw_duration
        if isinstance(raw_duration, int) and not isinstance(raw_duration, bool) and raw_duration > 0
        else None
    )

    lesson_row = {
        "id": lesson_id,
        "chapter_id": validated_chapter_id,
        "resource_id": lesson_resource_id,
        "slug": lesson_slug,
        "title": lesson_title,
        "subtitle": lesson_subtitle or None,
        "source_path": source_path_label,
        "spec_refs": lesson_spec_refs,
        "duration_minutes": duration_minutes,
        "vocabulary": _as_dict(_get_attr(parsed_lesson, "vocabulary") or []),
        "metadata": {
            "qualification": _get_attr(parsed_lesson, "qualification"),
            "chapter_number": _get_attr(parsed_lesson, "chapter_number"),
            "chapter_title": _get_attr(parsed_lesson, "chapter_title"),
            "frontmatter": _as_dict(_get_attr(parsed_lesson, "frontmatter") or {}),
            "learning_objectives": _as_dict(
                _get_attr(parsed_lesson, "learning_objectives") or []
            ),
            "formulas": _as_dict(_get_attr(parsed_lesson, "formulas") or []),
            "excluded_teacher_slides": list(
                _get_attr(parsed_lesson, "excluded_teacher_slides") or []
            ),
        },
        "is_published": True,
    }

    # ------------------------------------------------------------------
    # 4. `public.learning_blocks` rows (4 blocks, matches mig_8 schema)
    # ------------------------------------------------------------------
    learning_block_rows: list[dict[str, Any]] = []
    for block in raw_blocks:
        b_idx = int(_get_attr(block, "block_index"))
        b_id = block_id_by_index[b_idx]
        b_slug = block_slug_by_index[b_idx]
        b_citation = block_citation_by_index[b_idx]
        b_specs = validated_block_specs[b_idx]
        reflections = [str(r).strip() for r in (_get_attr(block, "reflections") or []) if str(r).strip()]
        foundation_text = str(_get_attr(block, "foundation") or "").strip()

        learning_block_rows.append(
            {
                "id": b_id,
                "lesson_id": lesson_id,
                "chapter_id": validated_chapter_id,
                "block_index": b_idx,
                "slug": b_slug,
                "title": str(_get_attr(block, "title") or f"Block {b_idx}").strip(),
                "spec_refs": b_specs,
                "content_markdown": str(_get_attr(block, "student_markdown") or "").strip(),
                "sections": _as_dict(_get_attr(block, "sections") or []),
                "guided_practice": _as_dict(_get_attr(block, "guided_practice") or []),
                "self_check": _as_dict(_get_attr(block, "self_check") or []),
                "examiner_alerts": _as_dict(_get_attr(block, "examiner_alerts") or []),
                "analogies": [str(a) for a in (_get_attr(block, "analogies") or []) if str(a).strip()],
                "reflection_prompt": "\n".join(reflections) if reflections else None,
                "widgets": _as_dict(_get_attr(block, "widgets") or []),
                "xp_value": DEFAULT_BLOCK_XP_VALUE,
                "metadata": {
                    "citation_id": b_citation,
                    "textbook_refs": [str(r) for r in (_get_attr(block, "textbook_refs") or [])],
                    "learning_objectives": _as_dict(
                        _get_attr(block, "learning_objectives") or []
                    ),
                    "vocabulary": _as_dict(_get_attr(block, "vocabulary") or []),
                    "solo_remediation": _as_dict(
                        _get_attr(block, "solo_remediation") or []
                    ),
                    "source_slides": list(_get_attr(block, "source_slides") or []),
                    "reflections": reflections,
                    "foundation": foundation_text or None,
                    "has_foundation": bool(foundation_text),
                },
            }
        )

    # ------------------------------------------------------------------
    # 5. `public.resource_chunks` rows (pre-embedding)
    #    - `lesson_block` (4 blocks + `WE-` worked examples)
    #    - `practical` (Spec 1.5 Practical Guide overview + methods)
    #    - `examiner_note` (all verbatim Examiner Alerts)
    # ------------------------------------------------------------------
    chunks: list[dict[str, Any]] = []
    chunk_counter_by_resource: dict[str, int] = {}

    def _next_chunk_index(resource_id: str) -> int:
        idx = chunk_counter_by_resource.get(resource_id, 0)
        chunk_counter_by_resource[resource_id] = idx + 1
        return idx

    # 5a. Lesson Block chunks (`source_type = 'lesson_block'`, `chunk_type = 'lesson_block'`)
    for block in raw_blocks:
        b_idx = int(_get_attr(block, "block_index"))
        b_id = block_id_by_index[b_idx]
        b_slug = block_slug_by_index[b_idx]
        b_citation = block_citation_by_index[b_idx]
        b_title = str(_get_attr(block, "title") or f"Block {b_idx}").strip()
        b_specs = validated_block_specs[b_idx]
        full_text = _build_block_chunk_text(block, b_specs)
        segments = _split_text_cleanly(full_text, max_chars=MAX_CHUNK_CHARS)

        for part_idx, seg_text in enumerate(segments):
            c_idx = _next_chunk_index(lesson_resource_id)
            anchor = f"{b_citation}:part:{part_idx}"
            chunks.append(
                {
                    "id": deterministic_uuid(
                        f"chunk:{lesson_resource_id}:lesson_block:{anchor}"
                    ),
                    "resource_id": lesson_resource_id,
                    "chapter_id": validated_chapter_id,
                    "source_type": "lesson_block",
                    "block_id": b_id,
                    "chunk_index": c_idx,
                    "chunk_text": seg_text,
                    "chunk_type": "lesson_block",
                    "embedding_model": active_model,
                    "spec_refs": b_specs,
                    "source_refs": {
                        "citation_id": b_citation,
                        "citation_prefix": "BLK",
                        "block_index": b_idx,
                        "block_slug": b_slug,
                        "block_title": b_title,
                        "concept": b_title,
                        "spec_refs": b_specs,
                        "spec_point": ", ".join(b_specs),
                        "textbook_refs": [
                            str(r) for r in (_get_attr(block, "textbook_refs") or [])
                        ],
                        "source_slides": list(_get_attr(block, "source_slides") or []),
                        "part_index": part_idx,
                        "part_count": len(segments),
                    },
                    "token_count": len(seg_text.split()),
                }
            )

    # 5b. Worked Example chunks (`source_type = 'lesson_block'`, `chunk_type = 'worked_example'`, `WE-` anchors)
    worked_examples = _collect_worked_examples(parsed_lesson)
    for we in worked_examples:
        example_id = str(_get_attr(we, "example_id") or "").strip()
        if not example_id.startswith("WE-"):
            example_id = f"WE-{example_id}"
        b_idx = int(_get_attr(we, "block_index") or 1)
        b_id = block_id_by_index.get(b_idx)
        b_citation = block_citation_by_index.get(b_idx, f"BLK-{b_idx}")
        b_slug = block_slug_by_index.get(b_idx, f"block-{b_idx}")
        raw_we_specs = _get_attr(we, "spec_refs") or validated_block_specs.get(b_idx, [])
        we_specs = validate_spec_refs(
            raw_we_specs,
            context=f"WorkedExample {example_id}",
            enforce_chapter1_boundary=enforce_chapter1_boundary,
        )
        we_text = _build_worked_example_chunk_text(we, b_citation, we_specs)
        for part_idx, seg_text in enumerate(_split_text_cleanly(we_text, max_chars=MAX_CHUNK_CHARS)):
            c_idx = _next_chunk_index(lesson_resource_id)
            chunks.append(
                {
                    "id": deterministic_uuid(
                        f"chunk:{lesson_resource_id}:lesson_block:{example_id}:part:{part_idx}"
                    ),
                    "resource_id": lesson_resource_id,
                    "chapter_id": validated_chapter_id,
                    "source_type": "lesson_block",
                    "block_id": b_id,
                    "chunk_index": c_idx,
                    "chunk_text": seg_text,
                    "chunk_type": "worked_example",
                    "embedding_model": active_model,
                    "spec_refs": we_specs,
                    "source_refs": {
                        "citation_id": example_id,
                        "citation_prefix": "WE",
                        "example_id": example_id,
                        "stage": str(_get_attr(we, "stage") or "model"),
                        "title": str(_get_attr(we, "title") or "").strip(),
                        "concept": str(_get_attr(we, "title") or example_id).strip(),
                        "block_index": b_idx,
                        "block_citation_id": b_citation,
                        "block_slug": b_slug,
                        "spec_refs": we_specs,
                        "spec_point": ", ".join(we_specs),
                        "slide_number": _get_attr(we, "slide_number"),
                        "part_index": part_idx,
                    },
                    "token_count": len(seg_text.split()),
                }
            )

    # 5c. Spec 1.5 Practical Guide chunks (`source_type = 'practical'`, `chunk_type = 'practical'`, `PRC-` anchor)
    if practical is not None:
        prc_citation = str(_get_attr(practical, "citation_id") or "PRC-1.5").strip()
        prc_title = str(_get_attr(practical, "title") or "Spec 1.5 Practical").strip()
        prc_specs = validate_spec_refs(
            _get_attr(practical, "spec_refs") or ["1.5"],
            context="PracticalGuide chunks",
            enforce_chapter1_boundary=enforce_chapter1_boundary,
        )
        # Spec 1.5 is owned by Block 2 (1.5–1.6).
        practical_block_id = block_id_by_index.get(2)
        prc_statement = str(_get_attr(practical, "spec_statement") or "").strip()
        prc_md = str(_get_attr(practical, "student_markdown") or "").strip()
        prc_overview_parts = [f"[{prc_citation}] {prc_title} (Specs: {', '.join(prc_specs)})"]
        if prc_statement:
            prc_overview_parts.append(f"Specification requirement: {prc_statement}")
        if prc_md:
            prc_overview_parts.append(prc_md)
        prc_overview = "\n\n".join(prc_overview_parts)

        for part_idx, seg_text in enumerate(_split_text_cleanly(prc_overview, max_chars=MAX_CHUNK_CHARS)):
            c_idx = _next_chunk_index(practical_resource_id)
            chunks.append(
                {
                    "id": deterministic_uuid(
                        f"chunk:{practical_resource_id}:practical:{prc_citation}:overview:{part_idx}"
                    ),
                    "resource_id": practical_resource_id,
                    "chapter_id": validated_chapter_id,
                    "source_type": "practical",
                    "block_id": practical_block_id,
                    "chunk_index": c_idx,
                    "chunk_text": seg_text,
                    "chunk_type": "practical",
                    "embedding_model": active_model,
                    "spec_refs": prc_specs,
                    "source_refs": {
                        "citation_id": prc_citation,
                        "citation_prefix": "PRC",
                        "practical_id": prc_citation,
                        "concept": prc_title,
                        "spec_refs": prc_specs,
                        "spec_point": ", ".join(prc_specs),
                        "textbook_refs": [
                            str(r) for r in (_get_attr(practical, "textbook_refs") or [])
                        ],
                        "source_slides": list(_get_attr(practical, "source_slides") or []),
                        "part_index": part_idx,
                    },
                    "token_count": len(seg_text.split()),
                }
            )

        for m_idx, method in enumerate(_get_attr(practical, "methods") or [], start=1):
            method_name = str(_get_attr(method, "name") or f"Method {m_idx}").strip()
            method_text = _build_practical_method_chunk_text(practical, method)
            for part_idx, seg_text in enumerate(_split_text_cleanly(method_text, max_chars=MAX_CHUNK_CHARS)):
                c_idx = _next_chunk_index(practical_resource_id)
                chunks.append(
                    {
                        "id": deterministic_uuid(
                            f"chunk:{practical_resource_id}:practical:{prc_citation}:method:{m_idx}:{part_idx}"
                        ),
                        "resource_id": practical_resource_id,
                        "chapter_id": validated_chapter_id,
                        "source_type": "practical",
                        "block_id": practical_block_id,
                        "chunk_index": c_idx,
                        "chunk_text": seg_text,
                        "chunk_type": "practical",
                        "embedding_model": active_model,
                        "spec_refs": prc_specs,
                        "source_refs": {
                            "citation_id": prc_citation,
                            "citation_prefix": "PRC",
                            "practical_id": prc_citation,
                            "method": method_name,
                            "concept": f"{prc_title} — {method_name}",
                            "spec_refs": prc_specs,
                            "spec_point": ", ".join(prc_specs),
                            "slide_number": _get_attr(method, "slide_number"),
                            "part_index": part_idx,
                        },
                        "token_count": len(seg_text.split()),
                    }
                )

    # 5d. Verbatim Examiner Alert chunks (`source_type = 'examiner_note'`, `chunk_type = 'examiner_note'`, `EXM-`)
    for a_idx, alert in enumerate(examiner_alerts, start=1):
        alert_id = str(_get_attr(alert, "alert_id") or f"EXM-{a_idx}").strip()
        if not alert_id.startswith("EXM-"):
            alert_id = f"EXM-{alert_id}"
        a_specs = validate_spec_refs(
            _get_attr(alert, "spec_refs") or [],
            context=f"ExaminerAlert {alert_id}",
            enforce_chapter1_boundary=enforce_chapter1_boundary,
        )
        block_indices = [int(i) for i in (_get_attr(alert, "block_indices") or [])]
        linked_block_id = (
            block_id_by_index.get(block_indices[0]) if block_indices else None
        )
        alert_text = _build_examiner_alert_chunk_text(alert, a_specs)
        c_idx = _next_chunk_index(examiner_resource_id)

        exam_session = str(_get_attr(alert, "exam_session") or "").strip()
        question_ref = str(_get_attr(alert, "question_ref") or "").strip()
        paper_code = str(_get_attr(alert, "paper_code") or "").strip()
        source_citation = str(_get_attr(alert, "source_citation") or "").strip()
        verbatim_text = str(_get_attr(alert, "verbatim_text") or "").strip()

        chunks.append(
            {
                "id": deterministic_uuid(
                    f"chunk:{examiner_resource_id}:examiner_note:{alert_id}"
                ),
                "resource_id": examiner_resource_id,
                "chapter_id": validated_chapter_id,
                "source_type": "examiner_note",
                "block_id": linked_block_id,
                "chunk_index": c_idx,
                "chunk_text": alert_text,
                "chunk_type": "examiner_note",
                "embedding_model": active_model,
                "spec_refs": a_specs,
                "source_refs": {
                    "citation_id": alert_id,
                    "citation_prefix": "EXM",
                    "alert_id": alert_id,
                    "concept": f"Examiner Alert ({', '.join(a_specs)}) — {exam_session} {question_ref}".strip(),
                    "paper_code": paper_code,
                    "exam_session": exam_session,
                    "question_ref": question_ref,
                    "source_citation": source_citation,
                    "verbatim_text": verbatim_text,
                    "spec_refs": a_specs,
                    "spec_point": ", ".join(a_specs),
                    "block_indices": block_indices,
                },
                "token_count": len(alert_text.split()),
            }
        )

    bundle = Chapter1IngestionBundle(
        chapter_id=validated_chapter_id,
        embedding_model=active_model,
        embedding_dim=EMBED_DIM,
        source_path=source_path_label,
        resources=resources_rows,
        lesson=lesson_row,
        learning_blocks=learning_block_rows,
        chunks=chunks,
    )
    validate_ingestion_bundle(bundle, enforce_chapter1_boundary=enforce_chapter1_boundary)
    return bundle


def validate_ingestion_bundle(
    bundle: Chapter1IngestionBundle,
    *,
    enforce_chapter1_boundary: bool = True,
) -> None:
    """
    Validate bundle invariants before embedding or persistence:
      - No worksheet resource or chunk is ever included
      - No legacy worksheet ID (`5729d034-a6c7-4f35-b81c-fcac447289c7`) is touched
      - All spec_refs obey Chapter 1 `1.3–1.10` boundary (no Spec `1.1`)
      - All chunks carry `chapter_id`, valid `source_type`, and `embedding_model`
      - All chunk IDs are unique and valid UUIDs
    """
    if bundle.embedding_dim != EMBED_DIM:
        raise ValueError(
            f"Expected embedding_dim={EMBED_DIM}, got {bundle.embedding_dim}."
        )
    validate_embedding_model(bundle.embedding_model)

    resource_ids: set[str] = set()
    for res in bundle.resources:
        rid = str(uuid.UUID(str(res["id"])))
        if rid == LEGACY_WORKSHEET_RESOURCE_ID:
            raise ValueError(
                "Safety violation: bundle attempts to mutate legacy worksheet resource."
            )
        rtype = res.get("resource_type")
        if rtype not in INGESTED_RESOURCE_TYPES:
            raise ValueError(
                f"Invalid resource_type {rtype!r}; allowed: {INGESTED_RESOURCE_TYPES}."
            )
        validate_spec_refs(
            res.get("spec_refs") or [],
            context=f"resource:{rtype}",
            enforce_chapter1_boundary=enforce_chapter1_boundary,
        )
        resource_ids.add(rid)

    block_ids: set[str] = set()
    for blk in bundle.learning_blocks:
        bid = str(uuid.UUID(str(blk["id"])))
        block_ids.add(bid)
        validate_spec_refs(
            blk.get("spec_refs") or [],
            context=f"learning_block:{blk.get('block_index')}",
            enforce_chapter1_boundary=enforce_chapter1_boundary,
        )

    seen_chunk_ids: set[str] = set()
    for chunk in bundle.chunks:
        cid = str(uuid.UUID(str(chunk["id"])))
        if cid in seen_chunk_ids:
            raise ValueError(f"Duplicate chunk id detected: {cid}")
        seen_chunk_ids.add(cid)

        rid = str(chunk.get("resource_id"))
        if rid == LEGACY_WORKSHEET_RESOURCE_ID:
            raise ValueError(
                "Safety violation: chunk targets legacy worksheet resource."
            )
        if rid not in resource_ids:
            raise ValueError(f"Chunk {cid} references unknown resource_id {rid}.")

        stype = chunk.get("source_type")
        if stype not in INGESTED_CHUNK_SOURCE_TYPES:
            raise ValueError(
                f"Invalid chunk source_type {stype!r}; allowed: {INGESTED_CHUNK_SOURCE_TYPES}."
            )
        if chunk.get("chapter_id") != bundle.chapter_id:
            raise ValueError(
                f"Chunk {cid} chapter_id mismatch: {chunk.get('chapter_id')} != {bundle.chapter_id}."
            )
        if chunk.get("embedding_model") != bundle.embedding_model:
            raise ValueError(
                f"Chunk {cid} embedding_model mismatch: {chunk.get('embedding_model')} != {bundle.embedding_model}."
            )
        if chunk.get("block_id") is not None and chunk["block_id"] not in block_ids:
            raise ValueError(
                f"Chunk {cid} references unknown block_id {chunk['block_id']}."
            )
        if not str(chunk.get("chunk_text") or "").strip():
            raise ValueError(f"Chunk {cid} has empty chunk_text.")
        validate_spec_refs(
            chunk.get("spec_refs") or [],
            context=f"chunk:{cid}",
            enforce_chapter1_boundary=enforce_chapter1_boundary,
        )


def attach_validated_embeddings(
    chunks: list[dict[str, Any]],
    vectors: Sequence[Sequence[float]],
    *,
    expected_dim: int = EMBED_DIM,
) -> list[dict[str, Any]]:
    """
    Validate 1:1 alignment and 1024-dim vector integrity for every chunk,
    returning new chunk payloads with pgvector literal `embedding` strings.
    """
    if len(chunks) != len(vectors):
        raise ValueError(
            f"Embedding vector count mismatch: {len(chunks)} chunks vs {len(vectors)} vectors."
        )
    enriched: list[dict[str, Any]] = []
    for chunk, raw_vec in zip(chunks, vectors):
        cid = str(chunk.get("id", ""))
        vec = validate_embedding_vector(
            raw_vec,
            expected_dim=expected_dim,
            context=f"chunk {cid}",
        )
        row = dict(chunk)
        row["embedding"] = _vector_to_pg_string(vec)
        enriched.append(row)
    return enriched


# ---------------------------------------------------------------------------
# PostgREST / Supabase Persistence Helpers (Strictly Scoped & Idempotent)
# ---------------------------------------------------------------------------

def _postgrest_headers(supabase_key: str, *, prefer: Optional[str] = None) -> dict[str, str]:
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _upsert_table_rows(
    table: str,
    rows: list[dict[str, Any]],
    *,
    on_conflict: str,
    supabase_url: str,
    supabase_key: str,
    http_session: Any = requests,
) -> int:
    """Idempotently upsert rows into a Supabase PostgREST table."""
    if not rows:
        return 0
    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/{table}"
    headers = _postgrest_headers(
        supabase_key,
        prefer="resolution=merge-duplicates,return=representation",
    )
    resp = http_session.post(
        endpoint,
        headers=headers,
        params={"on_conflict": on_conflict},
        json=rows,
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to upsert {table} (HTTP {resp.status_code}): {resp.text[:250]}"
        )
    data = resp.json()
    return len(data) if isinstance(data, list) else len(rows)


def _delete_scoped_chapter_chunks(
    chapter_id: str,
    *,
    supabase_url: str,
    supabase_key: str,
    http_session: Any = requests,
) -> None:
    """
    Delete ONLY ingested non-worksheet chunks for the target chapter.

    Strictly scopes to:
      chapter_id = eq.<chapter_id> AND source_type = in.(lesson_block,practical,examiner_note)

    Existing `worksheet` chunks (the 21 Chapter 1 rows on
    `5729d034-a6c7-4f35-b81c-fcac447289c7`) are NEVER touched.
    """
    validated_chapter_id = str(uuid.UUID(chapter_id))
    allowed_csv = ",".join(INGESTED_CHUNK_SOURCE_TYPES)
    if "worksheet" in INGESTED_CHUNK_SOURCE_TYPES:
        raise RuntimeError("Safety violation: worksheet source_type cannot be deleted.")

    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/resource_chunks"
    headers = _postgrest_headers(supabase_key)
    resp = http_session.delete(
        endpoint,
        headers=headers,
        params={
            "chapter_id": f"eq.{validated_chapter_id}",
            "source_type": f"in.({allowed_csv})",
        },
        timeout=30,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(
            f"Failed to clear scoped chapter chunks (HTTP {resp.status_code}): {resp.text[:250]}"
        )


def _insert_chunk_rows(
    chunk_rows: list[dict[str, Any]],
    *,
    supabase_url: str,
    supabase_key: str,
    batch_size: int = 40,
    http_session: Any = requests,
) -> int:
    """Insert embedded `resource_chunks` rows in batches."""
    if not chunk_rows:
        return 0

    for row in chunk_rows:
        if row.get("source_type") == "worksheet" or row.get("resource_id") == LEGACY_WORKSHEET_RESOURCE_ID:
            raise RuntimeError(
                "Safety violation: refusing to write a worksheet chunk in Chapter 1 unified ingestion."
            )

    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/resource_chunks"
    headers = _postgrest_headers(
        supabase_key,
        prefer="resolution=merge-duplicates,return=representation",
    )

    inserted = 0
    for i in range(0, len(chunk_rows), batch_size):
        batch = chunk_rows[i : i + batch_size]
        resp = http_session.post(
            endpoint,
            headers=headers,
            params={"on_conflict": "id"},
            json=batch,
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to insert resource_chunks batch (HTTP {resp.status_code}): {resp.text[:250]}"
            )
        data = resp.json()
        inserted += len(data) if isinstance(data, list) else len(batch)
    return inserted


# ---------------------------------------------------------------------------
# End-to-End Orchestrator
# ---------------------------------------------------------------------------

def ingest_chapter1(
    source_path: str | Path | None = None,
    *,
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
    nvidia_key: Optional[str] = None,
    embedding_model: Optional[str] = None,
    dry_run: bool = False,
    parsed_lesson: Optional[Any] = None,
    parser_fn: Optional[Callable[..., Any]] = None,
    embed_fn: Optional[Callable[..., list[list[float]]]] = None,
    http_session: Any = requests,
) -> dict[str, Any]:
    """
    Run the complete Chapter 1 Unified RAG Ingestion pipeline.

    When `dry_run=True`:
      - Parses the source deck (or uses provided `parsed_lesson`)
      - Builds and validates all `resources`, `lessons`, `learning_blocks`, and `resource_chunks` payloads
      - Validates synthetic 1024-dim vector encoding without calling NVIDIA or writing to Supabase
      - Returns a rich summary dict (including `dry_run=True` and payload counts)
    """
    resolved_path = resolve_source_path(source_path)

    if parsed_lesson is None:
        active_parser = parser_fn or _resolve_marp_parser()
        parsed_lesson = active_parser(resolved_path, enforce_chapter1_boundary=True)

    bundle = build_chapter1_ingestion_bundle(
        parsed_lesson,
        chapter_id=CHAPTER_1_ID,
        embedding_model=embedding_model,
        enforce_chapter1_boundary=True,
    )

    summary = bundle.summary()
    summary["dry_run"] = dry_run

    if dry_run:
        # Validate 1024-dim vector validation & pgvector serialization path cleanly offline.
        probe_vec = [1.0 / math.sqrt(EMBED_DIM)] * EMBED_DIM
        validate_embedding_vector(probe_vec, expected_dim=EMBED_DIM, context="dry_run_probe")
        _vector_to_pg_string(probe_vec)
        summary.update(
            {
                "embedded": 0,
                "resources_upserted": 0,
                "lessons_upserted": 0,
                "learning_blocks_upserted": 0,
                "chunks_stored": 0,
            }
        )
        return summary

    if not supabase_url or not supabase_key:
        raise ValueError(
            "Missing Supabase credentials: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required."
        )
    if embed_fn is None and not nvidia_key:
        raise ValueError("Missing NVIDIA_API_KEY for embeddings.")

    texts = [c["chunk_text"] for c in bundle.chunks]
    active_embed_fn = embed_fn or _embed_texts

    try:
        vectors = active_embed_fn(
            texts,
            nvidia_key or "",
            model=bundle.embedding_model,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Embedding call failed: {_sanitize_error(exc, (supabase_key, nvidia_key))}"
        ) from exc

    embedded_chunks = attach_validated_embeddings(
        bundle.chunks,
        vectors,
        expected_dim=EMBED_DIM,
    )

    try:
        resources_upserted = _upsert_table_rows(
            "resources",
            bundle.resources,
            on_conflict="id",
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            http_session=http_session,
        )
        lessons_upserted = _upsert_table_rows(
            "lessons",
            [bundle.lesson],
            on_conflict="id",
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            http_session=http_session,
        )
        blocks_upserted = _upsert_table_rows(
            "learning_blocks",
            bundle.learning_blocks,
            on_conflict="id",
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            http_session=http_session,
        )
        _delete_scoped_chapter_chunks(
            bundle.chapter_id,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            http_session=http_session,
        )
        chunks_stored = _insert_chunk_rows(
            embedded_chunks,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            http_session=http_session,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Supabase persistence failed: {_sanitize_error(exc, (supabase_key, nvidia_key))}"
        ) from exc

    summary.update(
        {
            "embedded": len(embedded_chunks),
            "resources_upserted": resources_upserted,
            "lessons_upserted": lessons_upserted,
            "learning_blocks_upserted": blocks_upserted,
            "chunks_stored": chunks_stored,
        }
    )
    return summary


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Idempotently ingest Chapter 1 (Movement and Position, specs 1.3–1.10) "
            "into resources, lessons, learning_blocks, and model-tagged resource_chunks."
        )
    )
    parser.add_argument(
        "--source",
        type=str,
        default=str(DEFAULT_SOURCE_RELATIVE_PATH),
        help=(
            "Path to the canonical Marp Markdown lesson deck "
            f"(default: {DEFAULT_SOURCE_RELATIVE_PATH.as_posix()})"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Parse, build all payloads, and validate dimensions/metadata without "
            "calling NVIDIA or writing to Supabase."
        ),
    )
    parser.add_argument(
        "--env",
        type=str,
        default=None,
        help="Optional path to .env file (defaults to backend/.env).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"Optional embedding model override (default: {DEFAULT_EMBED_MODEL}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print summary result as JSON.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    backend_dir = Path(__file__).resolve().parent.parent
    if args.env:
        load_dotenv(args.env)
    elif not args.dry_run:
        load_dotenv(str(backend_dir / ".env"))

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    nvidia_key = os.getenv("NVIDIA_API_KEY")

    if not args.dry_run:
        if not supabase_url or not supabase_key:
            print(
                "ERROR: Missing Supabase credentials (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY).",
                file=sys.stderr,
            )
            return 1
        if not nvidia_key:
            print("ERROR: Missing NVIDIA_API_KEY for embeddings.", file=sys.stderr)
            return 1

    try:
        result = ingest_chapter1(
            source_path=args.source,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            nvidia_key=nvidia_key,
            embedding_model=args.model,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(
            f"ERROR: {_sanitize_error(exc, (supabase_key, nvidia_key))}",
            file=sys.stderr,
        )
        return 1

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        mode = "DRY-RUN" if result["dry_run"] else "LIVE"
        print(
            f"[{mode}] Chapter 1 Unified RAG Ingestion complete: "
            f"resources={result['resources_count']} "
            f"blocks={result['learning_blocks_count']} "
            f"chunks={result['chunks_count']} "
            f"model={result['embedding_model']} "
            f"dim={result['embedding_dim']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
