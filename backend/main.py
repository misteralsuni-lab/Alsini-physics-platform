import json
import logging
import os
import re
import uuid
from typing import List, Optional

import google.generativeai as genai
import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from openai import OpenAI
from pydantic import BaseModel, Field

try:
    from backend.chapter_context import (
        ACTIVE_EMBEDDING_MODEL,
        ALL_CANONICAL_CITATION_PREFIXES,
        CHAPTER1_FORMULA_ALLOWLIST,
        FORMULA_REF_ALLOWLIST,
        CanonicalFormula,
        InteractiveState,
        UnknownFormulaRefError,
        assign_canonical_citation_labels,
        build_interactive_state_preamble,
        canonical_citation_label,
        canonical_citation_prefix,
        extract_citation_labels,
        formula_to_synthetic_chunk,
        rank_chunks_lexically,
        resolve_formula_ref,
        tokenize_lexical_query,
        verify_response_citations,
    )
except ImportError:
    from chapter_context import (  # type: ignore[no-redef]
        ACTIVE_EMBEDDING_MODEL,
        ALL_CANONICAL_CITATION_PREFIXES,
        CHAPTER1_FORMULA_ALLOWLIST,
        FORMULA_REF_ALLOWLIST,
        CanonicalFormula,
        InteractiveState,
        UnknownFormulaRefError,
        assign_canonical_citation_labels,
        build_interactive_state_preamble,
        canonical_citation_label,
        canonical_citation_prefix,
        extract_citation_labels,
        formula_to_synthetic_chunk,
        rank_chunks_lexically,
        resolve_formula_ref,
        tokenize_lexical_query,
        verify_response_citations,
    )

# Load environment variables
load_dotenv()

logger = logging.getLogger("alsini.backend")

# Initialize FastAPI
app = FastAPI(title="Alsini Physics VLE - AI Tutor API", version="1.0")


def _env_str(name: str, default: str = "") -> str:
    """Return a trimmed environment variable string or default if unset/blank."""
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def _env_float(name: str, default: float, min_val: float, max_val: float) -> float:
    """Parse a bounded float environment variable safely."""
    raw = _env_str(name)
    if not raw:
        return default
    try:
        parsed = float(raw)
    except ValueError:
        return default
    return max(min_val, min(max_val, parsed))


# Environment Variables
GEMINI_API_KEY = _env_str("GEMINI_API_KEY") or None
NVIDIA_API_KEY = _env_str("NVIDIA_API_KEY") or None
OPENCODE_ZEN_API_KEY = _env_str("OPENCODE_ZEN_API_KEY") or None
SUPABASE_URL = _env_str("SUPABASE_URL").rstrip("/") or None
SUPABASE_KEY = _env_str("SUPABASE_SERVICE_ROLE_KEY") or _env_str("SUPABASE_SERVICE_KEY") or None
SUPABASE_ANON_KEY = _env_str("SUPABASE_ANON_KEY") or None

OPENCODE_ZEN_MODEL = _env_str("OPENCODE_ZEN_MODEL", "deepseek-v4.1-flash-free")
NVIDIA_CHAT_MODEL = _env_str("NVIDIA_CHAT_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b")
NVIDIA_FALLBACK_CHAT_MODEL = _env_str("NVIDIA_FALLBACK_CHAT_MODEL", "nvidia/nemotron-3.5-bolt-e4b")
GEMINI_CHAT_MODEL = _env_str("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
EMBED_MODEL = _env_str("NVIDIA_EMBED_MODEL", "nvidia/nemotron-3.5-embed-1b")
EMBED_DIM = 1024
LLM_TIMEOUT_SECONDS = _env_float("LLM_TIMEOUT_SECONDS", 30.0, 5.0, 90.0)


def _sanitize_error_text(exc: Exception) -> str:
    """Return a secret-redacted short description suitable for server logs."""
    msg = str(exc)
    for secret in (GEMINI_API_KEY, NVIDIA_API_KEY, OPENCODE_ZEN_API_KEY, SUPABASE_KEY, SUPABASE_ANON_KEY):
        if secret:
            msg = msg.replace(secret, "[REDACTED]")
    msg = re.sub(r"(Bearer\s+)[A-Za-z0-9._-]+", r"\1[REDACTED]", msg, flags=re.IGNORECASE)
    msg = re.sub(r"([?&]key=)[^&\s]+", r"\1[REDACTED]", msg, flags=re.IGNORECASE)
    return f"{type(exc).__name__}: {msg[:180]}" if msg else type(exc).__name__


def _normalize_optional_uuid(value: Optional[str], field_name: str) -> Optional[str]:
    """Validate and normalize an optional UUID string; empty strings become None."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return str(uuid.UUID(cleaned))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format.") from exc


def _validate_asset_type(value: str) -> str:
    """Validate asset_type against a safe identifier allowlist."""
    cleaned = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", cleaned):
        raise HTTPException(status_code=400, detail="Invalid asset_type.")
    return cleaned


def _safe_json_list(resp: requests.Response) -> list[dict]:
    """Parse a PostgREST JSON array response safely without raising ValueError."""
    try:
        data = resp.json()
    except ValueError:
        return []
    return data if isinstance(data, list) else []


# Register the inner error-catching middleware BEFORE CORSMiddleware so any
# unexpected error returns JSON inside CORSMiddleware (preserving CORS headers
# and never leaking Python stack traces).
@app.middleware("http")
async def safe_error_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.error(
            "Unhandled error on %s %s: %s",
            request.method,
            request.url.path,
            _sanitize_error_text(exc),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred."},
        )


# Configure CORS for the known frontend origins. The API carries privileged
# server-side credentials, so wildcard origins are intentionally not allowed.
frontend_url = _env_str("FRONTEND_URL", "http://localhost:5173").rstrip("/")
default_origins = [
    frontend_url,
    "http://localhost:5174",
    "http://localhost:3000",
    "https://eduvle.vercel.app",
    "https://alsini-physics-platform.vercel.app",
]
configured_origins_raw = _env_str("CORS_ORIGINS")
raw_origin_list = configured_origins_raw.split(",") if configured_origins_raw else default_origins
allowed_origins: list[str] = []
for origin in raw_origin_list:
    normalized = origin.strip().rstrip("/")
    if not normalized or normalized == "*":
        continue
    if normalized not in allowed_origins:
        allowed_origins.append(normalized)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# The browser must present a Supabase access token before any /api route can
# use the service-role-backed data and LLM clients. Token validation is
# delegated to Supabase Auth so this remains compatible with projects using
# either legacy or asymmetric JWT signing keys.
bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Validate the caller's Supabase access token and return its user."""
    if not SUPABASE_URL or not (SUPABASE_ANON_KEY or SUPABASE_KEY):
        raise HTTPException(status_code=503, detail="Authentication service is not configured.")

    token = (credentials.credentials or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="A valid Supabase access token is required.")

    try:
        response = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": SUPABASE_ANON_KEY or SUPABASE_KEY,
                "Authorization": f"Bearer {token}",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning("Auth service request error: %s", _sanitize_error_text(exc))
        raise HTTPException(status_code=503, detail="Authentication service is unavailable.") from exc

    if response.status_code in (401, 403):
        body_lower = (response.text or "")[:300].lower()
        if "invalid api key" in body_lower or "no api key" in body_lower:
            logger.error("Supabase auth rejected server apikey (status %s).", response.status_code)
            raise HTTPException(status_code=503, detail="Authentication service configuration error.")
        raise HTTPException(status_code=401, detail="A valid Supabase access token is required.")

    if response.status_code == 404 or response.status_code == 429 or response.status_code >= 500:
        logger.warning("Supabase auth upstream returned status %s.", response.status_code)
        raise HTTPException(status_code=503, detail="Authentication service is unavailable.")

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="A valid Supabase access token is required.")

    try:
        user = response.json()
    except ValueError as exc:
        logger.warning("Supabase auth returned non-JSON body on 200 OK.")
        raise HTTPException(status_code=503, detail="Authentication service returned an invalid response.") from exc

    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(status_code=401, detail="Authentication service returned no user identity.")
    return user


# Initialize APIs (max_retries=0 so multi-tier fallback does not multiply latency)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

nvidia_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
    timeout=LLM_TIMEOUT_SECONDS,
    max_retries=0,
) if NVIDIA_API_KEY else None

opencode_zen_client = OpenAI(
    base_url="https://opencode.ai/zen/v1",
    api_key=OPENCODE_ZEN_API_KEY,
    timeout=LLM_TIMEOUT_SECONDS,
    max_retries=0,
) if OPENCODE_ZEN_API_KEY else None

# Pydantic Models for Request Validation
class Message(BaseModel):
    role: str
    content: str

# --- Learning Context -------------------------------------------------
# Generic learning-context carrier passed from whichever surface the
# student is viewing (worksheet, lesson, practical, quiz). This keeps
# the tutor API stable as new surfaces come online in Session 4B and
# beyond — each surface populates the fields it knows about, the rest
# stay null.
#
# Spec alignment:
#   - PEDAGOGICAL_ARCHITECTURE.md §Curriculum Hierarchy — Unit → Chapter
#     → Lesson → Block → Worksheet → Practical → Quiz.
#   - SYSTEM_ARCHITECTURE.md §7 — Focus state as single source of truth.
class LearningContext(BaseModel):
    resource_id: Optional[str] = None
    chapter_id: Optional[str] = None
    lesson_id: Optional[str] = None
    block_id: Optional[str] = None
    worksheet_id: Optional[str] = None
    focused_chunk: Optional[str] = None
    focused_asset: Optional[str] = None
    # DEPRECATED (Session 4A.2): The backend now generates canonical citation
    # labels server-side via _canonical_asset_label(). This field is retained
    # on the model for backward API compatibility but is NEVER used by the
    # backend — it is not trusted and not read. The frontend no longer sends
    # it. New code MUST NOT use this field; use the asset_label returned in
    # TutorSource instead.
    focused_asset_label: Optional[str] = None
    focused_asset_type: Optional[str] = None
    focused_question: Optional[str] = None
    page: Optional[int] = None
    # Strictly typed interactive telemetry (Chapter 1 Vertical Slice — ADR-0002).
    # Optional for full backwards compatibility when omitted (None).
    interactive_state: Optional[InteractiveState] = None

class TutorRequest(BaseModel):
    student_prompt: str
    history: Optional[List[Message]] = Field(default_factory=list)
    # Dynamic RAG scope — the frontend passes the currently selected
    # worksheet's resource_id so retrieval is scoped to it. If absent,
    # retrieval runs unscoped (returns chunks across all resources).
    # NOTE: superseded by `learning_context.resource_id` when present.
    # Kept for backward compatibility with older frontends that have
    # not migrated to the LearningContext object yet.
    resource_id: Optional[str] = None
    # Structured learning context — the single carrier for everything
    # the tutor should know about what the student is currently viewing.
    learning_context: Optional[LearningContext] = None

class TutorSource(BaseModel):
    chunk_id: str
    concept: Optional[str] = None
    page: Optional[int] = None
    chunk_type: str
    similarity: Optional[float] = None
    # Traceability fields — exposed for developer-mode citation expansion.
    resource_id: Optional[str] = None
    resource_title: Optional[str] = None
    specification_point_id: Optional[str] = None
    specification_point_ref: Optional[str] = None
    chunk_index: Optional[int] = None
    # Focused visual-asset provenance. These fields are populated only for
    # the verified synthetic asset source and let the UI use one identity.
    asset_id: Optional[str] = None
    asset_url: Optional[str] = None
    asset_label: Optional[str] = None
    # Server-canonical citation provenance (Chapter 1 Unified RAG — ADR-0002).
    citation_label: Optional[str] = None
    source_type: Optional[str] = None
    chapter_id: Optional[str] = None
    block_id: Optional[str] = None
    spec_refs: Optional[List[str]] = None
    embedding_model: Optional[str] = None

class TutorResponse(BaseModel):
    response: str
    model_used: str
    sources: List[TutorSource] = []

class GradeRequest(BaseModel):
    student_id: str
    resource_id: Optional[str] = None
    question_index: int
    student_answer: str
    max_score: int
    question_text: str

class GradeResponse(BaseModel):
    marks_awarded: int
    total_marks: int
    explanation: str

# Constants
# NOTE: TARGET_RESOURCE_ID is retained ONLY for /api/grade's legacy
# full-context fetch (fetch_forces_and_motion_data). The RAG /api/tutor
# endpoint no longer uses this — it receives resource_id dynamically
# from the frontend. Do NOT add new uses of this constant.
TARGET_RESOURCE_ID = "5729d034-a6c7-4f35-b81c-fcac447289c7" # Forces and Motion Resource
TUTOR_CHUNK_COUNT = 5  # top-N chunks to inject as RAG context
VECTOR_MIN_RELEVANCE = 0.15  # guard against cross-embedding-space cosine noise
_LEXICAL_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "could",
    "describe", "do", "does", "explain", "for", "from", "hello", "help",
    "hey", "hi", "how", "in", "is", "it", "me", "my", "of", "on", "or",
    "please", "tell", "thanks", "thank", "that", "the", "this", "to",
    "what", "when", "where", "which", "who", "why", "with", "would",
    "you", "your",
})

# -------------------------------------------------------------------
# RAG Retrieval Helpers (reuse existing _embed_query and _supabase_headers)
# -------------------------------------------------------------------


_ALLOWED_SOURCE_TYPES = frozenset({
    "worksheet",
    "lesson_block",
    "practical",
    "examiner_note",
    "worked_example",
})


def _validate_source_types(source_types: Optional[list[str]]) -> Optional[list[str]]:
    if not source_types:
        return None
    cleaned: list[str] = []
    for raw in source_types:
        val = (raw or "").strip().lower()
        if not val:
            continue
        if val not in _ALLOWED_SOURCE_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid source_type: {val}")
        if val not in cleaned:
            cleaned.append(val)
    return cleaned or None


def _tokenize_search_query(query: str) -> list[str]:
    """Extract meaningful lowercase tokens for lexical chunk matching."""
    return tokenize_lexical_query(query)


def _lexical_search_chunks(
    query: str,
    match_count: int = 10,
    resource_id: Optional[str] = None,
    chunk_type: Optional[str] = None,
    resource_ids: Optional[list[str]] = None,
    chapter_id: Optional[str] = None,
    source_types: Optional[list[str]] = None,
    target_spec_refs: Optional[list[str]] = None,
) -> tuple[list[dict], bool]:
    """
    Deterministic fallback lexical/relational retrieval over `resource_chunks` via PostgREST.

    Used when vector embedding fails (e.g. upstream provider outage/EOL), when
    `embedding_model` mismatches stored chunk vectors, or when vector retrieval
    returns zero model-matched hits. Ranks deterministically via normalized
    token + spec_refs overlap with stable `(similarity DESC, chunk_index ASC, id ASC)`
    tie-breaking. Returns (ranked_chunks, supabase_reachable).
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return [], False

    tokens = _tokenize_search_query(query)
    if not tokens and not target_spec_refs:
        return [], True

    if chapter_id:
        params: dict[str, str] = {
            "select": (
                "id,resource_id,chapter_id,block_id,source_type,spec_refs,"
                "embedding_model,chunk_index,chunk_text,chunk_type,source_refs,token_count"
            ),
            "chapter_id": f"eq.{chapter_id}",
            "order": "chunk_index.asc,id.asc",
            "limit": "200",
        }
        validated_types = _validate_source_types(source_types)
        if validated_types:
            params["source_type"] = f"in.({','.join(validated_types)})"
    else:
        params = {
            "select": "id,resource_id,chunk_index,chunk_text,chunk_type,source_refs,token_count",
            "order": "chunk_index.asc",
            "limit": "200",
        }

    if resource_id:
        params["resource_id"] = f"eq.{resource_id}"
    elif resource_ids:
        params["resource_id"] = f"in.({','.join(resource_ids)})"
    if chunk_type:
        params["chunk_type"] = f"eq.{chunk_type}"

    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/resource_chunks",
            headers=_supabase_headers(),
            params=params,
            timeout=12,
        )
    except (requests.RequestException, HTTPException) as exc:
        logger.warning("[RAG] Lexical chunk fetch error: %s", _sanitize_error_text(exc))
        return [], False

    if resp.status_code != 200:
        logger.warning("[RAG] Lexical chunk fetch returned status %s.", resp.status_code)
        return [], False

    rows = _safe_json_list(resp)
    ranked = rank_chunks_lexically(
        rows,
        query,
        target_spec_refs=target_spec_refs,
        match_count=match_count,
    )
    return ranked, True


def _retrieve_chapter_chunks(
    query: str,
    chapter_id: str,
    match_count: int = TUTOR_CHUNK_COUNT,
    source_types: Optional[list[str]] = None,
    spec_refs: Optional[list[str]] = None,
    embedding_model: Optional[str] = None,
    match_threshold: float = VECTOR_MIN_RELEVANCE,
) -> list[dict]:
    """
    Chapter-scoped, model-tagged Unified RAG retrieval via `match_chapter_chunks`.

    Strictly filters vectors by `filter_chapter_id` and `filter_embedding_model`
    (defaulting to the active `EMBED_MODEL`, e.g. `nvidia/nemotron-3.5-embed-1b`).
    If embedding fails, returns zero model-matched hits, or encounters any
    `embedding_model` mismatch, deterministically falls back to lexical +
    `spec_refs` ranking over chapter chunks rather than returning mixed-model
    cosine noise.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("[RAG] Supabase credentials not configured — skipping chapter retrieval.")
        return []

    active_model = (embedding_model or EMBED_MODEL or ACTIVE_EMBEDDING_MODEL).strip()
    validated_types = _validate_source_types(source_types)
    vector_chunks: list[dict] = []

    if nvidia_client:
        try:
            query_vec = _embed_query(query)
            vec_str = _vector_to_pg_str(query_vec)

            rpc_body: dict = {
                "query_embedding": vec_str,
                "filter_chapter_id": chapter_id,
                "filter_embedding_model": active_model,
                "match_threshold": match_threshold,
                "match_count": min(match_count, 10),
            }
            if validated_types:
                rpc_body["filter_source_types"] = validated_types
            if spec_refs:
                rpc_body["filter_spec_refs"] = list(spec_refs)

            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/rpc/match_chapter_chunks",
                headers=_supabase_headers(),
                json=rpc_body,
                timeout=12,
            )
            if resp.status_code == 200:
                raw_chunks = _safe_json_list(resp)
                # Defense-in-depth: reject any chunk whose embedding_model does
                # not strictly match the active query embedding model.
                for chunk in raw_chunks:
                    if chunk.get("embedding_model") == active_model:
                        chunk.setdefault("chapter_id", chapter_id)
                        vector_chunks.append(chunk)
                dropped = len(raw_chunks) - len(vector_chunks)
                if dropped > 0:
                    logger.warning(
                        "[RAG] Dropped %d chapter chunk(s) due to embedding_model mismatch (expected %s).",
                        dropped,
                        active_model,
                    )
            else:
                logger.warning(
                    "[RAG] Chapter vector RPC failed with status %s; falling back to lexical.",
                    resp.status_code,
                )
        except (HTTPException, Exception) as exc:
            logger.warning(
                "[RAG] Chapter vector retrieval error (non-fatal): %s",
                _sanitize_error_text(exc),
            )
    else:
        logger.warning("[RAG] NVIDIA API not configured — using deterministic lexical chapter fallback.")

    max_vector_sim = max(
        (c.get("similarity") or 0.0 for c in vector_chunks),
        default=0.0,
    )
    if vector_chunks and max_vector_sim >= match_threshold:
        vector_chunks.sort(
            key=lambda c: (
                -(c.get("similarity") or 0.0),
                int(c["chunk_index"]) if c.get("chunk_index") is not None else 10**9,
                str(c.get("id") or ""),
            )
        )
        return vector_chunks[:match_count]

    lexical_chunks, _ = _lexical_search_chunks(
        query,
        match_count=match_count,
        chapter_id=chapter_id,
        source_types=validated_types,
        target_spec_refs=spec_refs,
    )
    return lexical_chunks


def _retrieve_relevant_chunks(
    query: str,
    match_count: int = TUTOR_CHUNK_COUNT,
    resource_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    source_types: Optional[list[str]] = None,
    spec_refs: Optional[list[str]] = None,
) -> list[dict]:
    """
    Embed the student's question and return ranked chunks for RAG context.

    Retrieval scope:
      - If `chapter_id` is provided, uses chapter-scoped model-tagged retrieval
        (`match_chapter_chunks` filtered by active `EMBED_MODEL`) with
        deterministic lexical fallback on mismatch or empty vector results.
      - Otherwise, preserves the legacy 3-arg `match_resource_chunks` RPC path
        scoped to `resource_id` (or unscoped when absent).

    Returns empty list on any failure (non-fatal — tutor still works).
    """
    if chapter_id:
        return _retrieve_chapter_chunks(
            query=query,
            chapter_id=chapter_id,
            match_count=match_count,
            source_types=source_types,
            spec_refs=spec_refs,
        )

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("[RAG] Supabase credentials not configured — skipping retrieval.")
        return []

    vector_chunks: list[dict] = []
    if nvidia_client:
        try:
            query_vec = _embed_query(query)
            vec_str = _vector_to_pg_str(query_vec)

            headers = _supabase_headers()
            rpc_body = {
                "query_embedding": vec_str,
                "match_count": min(match_count, 10),
            }
            # Dynamic RAG scope: filter by the frontend-supplied resource_id
            # if present. This is the root-cause fix for the "tutor always
            # answers from Unit 1 / Forces and Motion" bug — retrieval is now
            # scoped to whatever worksheet the student is viewing.
            if resource_id:
                rpc_body["filter_resource_id"] = resource_id

            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/rpc/match_resource_chunks",
                headers=headers,
                json=rpc_body,
                timeout=12,
            )
            if resp.status_code == 200:
                vector_chunks = _safe_json_list(resp)
                if resource_id:
                    for c in vector_chunks:
                        c.setdefault("resource_id", resource_id)
            else:
                logger.warning("[RAG] Vector RPC failed with status %s.", resp.status_code)
        except (HTTPException, Exception) as exc:
            logger.warning("[RAG] Vector retrieval error (non-fatal): %s", _sanitize_error_text(exc))
    else:
        logger.warning("[RAG] NVIDIA API not configured — using lexical retrieval fallback.")

    max_vector_sim = max(
        (c.get("similarity") or 0.0 for c in vector_chunks),
        default=0.0,
    )
    if vector_chunks and max_vector_sim >= VECTOR_MIN_RELEVANCE:
        return vector_chunks[:match_count]

    lexical_chunks, _ = _lexical_search_chunks(
        query,
        match_count=match_count,
        resource_id=resource_id,
    )
    if lexical_chunks:
        return lexical_chunks

    # If lexical found nothing (e.g., conversational greeting), avoid injecting
    # cross-model noise (< VECTOR_MIN_RELEVANCE) into the tutor prompt.
    return []


def _format_chunks_as_context(chunks: list[dict]) -> str:
    """Build a compact, citation-rich context block from retrieved chunks."""
    if not chunks:
        return ""
    assign_canonical_citation_labels(chunks)
    lines = ["Retrieved educational context:"]
    for i, c in enumerate(chunks):
        label = c.get("citation_label") or canonical_citation_label(c, i + 1)
        ctype = c.get("source_type") or c.get("chunk_type", "concept")
        text = c.get("chunk_text", "")
        sources = c.get("source_refs", {}) or {}
        concept = sources.get("concept", "")
        page = sources.get("page")
        spec_refs = c.get("spec_refs")

        # Build a tight citation suffix
        cite_parts = []
        if concept:
            cite_parts.append(f"concept: {concept}")
        if spec_refs:
            cite_parts.append(f"spec: {', '.join(str(s) for s in spec_refs)}")
        elif sources.get("spec_point"):
            cite_parts.append(f"spec: {sources.get('spec_point')}")
        if page is not None:
            cite_parts.append(f"page {page}")
        cite_str = f" [{', '.join(cite_parts)}]" if cite_parts else ""

        lines.append(f"  [{label}] ({ctype}){cite_str}  {text}")
    return "\n".join(lines)


def _chunks_to_sources(chunks: list[dict]) -> list[TutorSource]:
    """Extract source metadata and server-canonical citation labels from chunks."""
    assign_canonical_citation_labels(chunks)
    results: list[TutorSource] = []
    for i, c in enumerate(chunks):
        sr = c.get("source_refs") or {}
        raw_spec_refs = c.get("spec_refs")
        spec_refs_list = (
            [str(s) for s in raw_spec_refs if s]
            if isinstance(raw_spec_refs, list) and raw_spec_refs
            else None
        )
        spec_point_ref = (
            c.get("specification_point_ref")
            or sr.get("spec_point")
            or (", ".join(spec_refs_list) if spec_refs_list else None)
        )
        results.append(
            TutorSource(
                chunk_id=str(c.get("id", "")),
                concept=sr.get("concept"),
                page=sr.get("page"),
                chunk_type=c.get("chunk_type", "concept"),
                similarity=c.get("similarity"),
                # Traceability fields for developer-mode citation expansion.
                resource_id=c.get("resource_id"),
                resource_title=c.get("resource_title"),
                specification_point_id=c.get("specification_point_id"),
                specification_point_ref=spec_point_ref,
                chunk_index=c.get("chunk_index"),
                asset_id=c.get("asset_id"),
                asset_url=c.get("asset_url"),
                asset_label=c.get("asset_label"),
                citation_label=c.get("citation_label") or canonical_citation_label(c, i + 1),
                source_type=c.get("source_type"),
                chapter_id=c.get("chapter_id"),
                block_id=c.get("block_id"),
                spec_refs=spec_refs_list,
                embedding_model=c.get("embedding_model"),
            )
        )
    return results


# -------------------------------------------------------------------
# Asset Grounding (Session 4A.1 — Task 5)
# -------------------------------------------------------------------
# When the student has focused a visual asset (graph / figure / table /
# diagram / equation), we retrieve all connected educational objects
# so the tutor has the full surrounding context:
#   - the asset itself (caption, type, page, linked question id)
#   - chunks on the same page (so the tutor can read the on-page text
#     the asset sits next to)
#   - chunks mentioning the same concept (if the asset's metadata or
#     the reading-order chunks expose one)
#   - linked worksheet question chunk (resource_assets.linked_question_id
#     → resource_chunks.source_refs.question_id)
# Reuses the existing Supabase PostgREST path — no new RPC, no new
# schema. Non-fatal: any failure returns an empty list so the tutor
# still answers from general RAG retrieval.
def _canonical_asset_label(asset_row: dict) -> Optional[str]:
    """
    Generate a canonical citation label for a visual asset from its
    VERIFIED asset row, so the same id appears in:

      - the tutor context preamble
      - the synthetic TutorSource
      - the frontend focus chip
      - developer mode
      - audit reports

    The label is derived from the asset's verified `asset_type` and
    `page_number` plus a deterministic 1-based ordinal within the asset's
    page. This is the single source of truth; the frontend MUST render
    only this value and never invent one.

    Format: PREFIX-LNN where L is a page letter (1=A, 2=B, ...) and NN is
    a zero-padded ordinal of the asset within its page. The ordinal is
    precomputed by the caller from the page-ordered asset set returned by
    PostgREST, so reordering a client-side array cannot change ids.

    Returns None if the asset row is malformed; the caller must then
    omit the label rather than fall back to a client-supplied one.
    """
    asset_type = (asset_row.get("asset_type") or "").lower()
    prefix = {
        "figure": "FIG", "graph": "FIG", "plot": "FIG",
        "table": "TAB", "plotting_grid": "TAB",
        "equation": "EQ", "formula": "EQ",
    }.get(asset_type, "FIG")

    page = asset_row.get("page_number")
    ordinal = asset_row.get("_page_ordinal") or 1
    try:
        ordinal_int = int(ordinal)
    except (TypeError, ValueError):
        ordinal_int = 1
    if page is None:
        return f"{prefix}-{ordinal_int:02d}"
    try:
        page_letter = chr(ord("A") + ((int(page) - 1) % 26))
    except (TypeError, ValueError):
        page_letter = ""
    return f"{prefix}-{page_letter}{ordinal_int:02d}"


def _ground_focused_asset(learning_context: "LearningContext") -> list[dict]:
    """
    Retrieve connected educational objects for a focused visual asset.

    Returns a list of chunk-shaped dicts (compatible with the existing
    `_format_chunks_as_context` formatter) covering the asset's
    on-page text, linked question, and concept neighbours.
    """
    if not learning_context or not learning_context.focused_asset:
        return []
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []

    resource_id = _normalize_optional_uuid(learning_context.resource_id, "learning_context.resource_id")
    focused_asset = _normalize_optional_uuid(learning_context.focused_asset, "learning_context.focused_asset")
    page = learning_context.page
    if not resource_id or not focused_asset:
        return []

    headers = _supabase_headers()
    grounded: list[dict] = []
    seen_chunk_ids: set[str] = set()

    def _append_chunk(c: dict) -> None:
        cid = c.get("id")
        if cid and cid in seen_chunk_ids:
            return
        if cid:
            seen_chunk_ids.add(cid)
        grounded.append(c)

    # 1. Fetch the asset row AND resource's full asset list to compute
    #    the canonical citation ordinal. The single-asset query verifies
    #    the asset belongs to the resource; the full-list query computes
    #    a stable 1-based ordinal within the asset's page so the label
    #    cannot be changed by client-side reordering.
    asset_endpoint = f"{SUPABASE_URL}/rest/v1/resource_assets"
    asset_caption: Optional[str] = None
    linked_question_id: Optional[str] = None
    asset_type: Optional[str] = learning_context.focused_asset_type
    asset_url: Optional[str] = None
    asset_id: Optional[str] = None
    asset_row: Optional[dict] = None
    # The canonical asset_label is generated ONLY by the backend from the
    # verified asset row. The client-supplied `focused_asset_label` is
    # ignored (SESSION_4A1_VERIFICATION_REPORT.md section 8 release blocker).
    canonical_asset_label: Optional[str] = None
    try:
        ar = requests.get(
            asset_endpoint,
            headers=headers,
            params={
                "id": f"eq.{focused_asset}",
                "resource_id": f"eq.{resource_id}",
                "select": "id,resource_id,page_number,asset_type,storage_url,caption,linked_question_id,metadata",
                "limit": "1",
            },
            timeout=10,
        )
        if ar.status_code != 200:
            raise HTTPException(status_code=502, detail="Unable to verify the focused asset.")
        rows = _safe_json_list(ar)
        if not rows:
            raise HTTPException(
                status_code=400,
                detail="The focused asset does not belong to the selected resource.",
            )
        a = rows[0]
        asset_id = a.get("id")
        asset_url = a.get("storage_url")
        asset_caption = a.get("caption")
        linked_question_id = a.get("linked_question_id")
        asset_type = a.get("asset_type") or asset_type
        page = a.get("page_number") if a.get("page_number") is not None else page
        asset_row = a
    except requests.RequestException as exc:
        logger.warning("Asset verification request error: %s", _sanitize_error_text(exc))
        raise HTTPException(status_code=503, detail="Asset verification service is unavailable.") from exc

    # Compute the canonical citation label from the verified asset row.
    # The ordinal is the 1-based position within the asset's page in the
    # page_number.asc, created_at.asc ordering returned by PostgREST.
    if asset_row is not None:
        try:
            ordered = requests.get(
                asset_endpoint,
                headers=headers,
                params={
                    "resource_id": f"eq.{resource_id}",
                    "select": "id,page_number,asset_type,created_at",
                    "order": "page_number.asc,created_at.asc",
                    "limit": "500",
                },
                timeout=10,
            )
            if ordered.status_code == 200:
                assets_list = _safe_json_list(ordered)
                page_counter: dict[int, int] = {}
                for item in assets_list:
                    pn = item.get("page_number")
                    if pn is None:
                        continue
                    try:
                        pn_int = int(pn)
                    except (TypeError, ValueError):
                        continue
                    page_counter[pn_int] = page_counter.get(pn_int, 0) + 1
                    if item.get("id") == asset_id:
                        asset_row["_page_ordinal"] = page_counter[pn_int]
        except requests.RequestException:
            pass
        canonical_asset_label = _canonical_asset_label(asset_row)

    # 2. On-page chunks - the reading-order text that surrounds the asset.
    if page is not None:
        page_endpoint = f"{SUPABASE_URL}/rest/v1/resource_chunks"
        try:
            pr = requests.get(
                page_endpoint,
                headers=headers,
                params={
                    "resource_id": f"eq.{resource_id}",
                    "source_refs->>page": f"eq.{int(page)}",
                    "select": "id,resource_id,chunk_index,chunk_text,chunk_type,source_refs,token_count",
                    "order": "chunk_index.asc",
                    "limit": "50",
                },
                timeout=12,
            )
            if pr.status_code == 200:
                for c in _safe_json_list(pr):
                    c.setdefault("resource_id", resource_id)
                    _append_chunk(c)
        except requests.RequestException as exc:
            logger.warning("Page grounding request error: %s", _sanitize_error_text(exc))
            raise HTTPException(status_code=503, detail="Page grounding service is unavailable.") from exc

    # 3. Linked worksheet question chunk (asset -> question id -> chunk).
    if linked_question_id:
        qid = linked_question_id.strip()
        q_endpoint = f"{SUPABASE_URL}/rest/v1/resource_chunks"
        try:
            qr = requests.get(
                q_endpoint,
                headers=headers,
                params={
                    "resource_id": f"eq.{resource_id}",
                    "chunk_type": "eq.question",
                    "select": "id,resource_id,chunk_index,chunk_text,chunk_type,source_refs,token_count",
                    "limit": "20",
                },
                timeout=12,
            )
            if qr.status_code == 200:
                for c in _safe_json_list(qr):
                    sr = c.get("source_refs") or {}
                    if str(sr.get("question_id", "")).strip() == qid:
                        c.setdefault("resource_id", resource_id)
                        _append_chunk(c)
        except requests.RequestException:
            pass

    # 4. Linked formula chunk - DETERMINISTIC, fail-closed.
    #    When the asset is a graph, the governing equation must come from
    #    an EXPLICIT relationship stored in the asset's metadata JSONB
    #    (metadata.linked_formula_chunk_id). If no explicit link exists,
    #    we OMIT the formula entirely and set a no-formula marker so the
    #    tutor honestly says "No governing formula is linked to this graph"
    #    instead of guessing from unrelated formula chunks.
    #
    #    NEVER use semantic similarity or arbitrary formula retrieval as a
    #    substitute for an explicit relationship (Issue 2, Session 4A.2).
    no_linked_formula = False
    if asset_type and "graph" in (asset_type or "").lower():
        metadata = (asset_row or {}).get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (ValueError, TypeError):
                metadata = {}
        raw_formula_id = metadata.get("linked_formula_chunk_id") if isinstance(metadata, dict) else None
        linked_formula_chunk_id = None
        if raw_formula_id:
            try:
                linked_formula_chunk_id = str(uuid.UUID(str(raw_formula_id).strip()))
            except ValueError:
                linked_formula_chunk_id = None
        if linked_formula_chunk_id:
            # Retrieve ONLY the explicitly linked formula chunk.
            eq_endpoint = f"{SUPABASE_URL}/rest/v1/resource_chunks"
            try:
                er = requests.get(
                    eq_endpoint,
                    headers=headers,
                    params={
                        "id": f"eq.{linked_formula_chunk_id}",
                        "resource_id": f"eq.{resource_id}",
                        "select": "id,resource_id,chunk_index,chunk_text,chunk_type,source_refs,token_count",
                        "limit": "1",
                    },
                    timeout=12,
                )
                if er.status_code == 200:
                    for c in _safe_json_list(er):
                        c.setdefault("resource_id", resource_id)
                        _append_chunk(c)
            except requests.RequestException:
                pass
        else:
            # No explicit formula link - fail closed. The tutor must
            # honestly state that no governing formula is linked rather
            # than hallucinate one from unrelated chunks.
            no_linked_formula = True

    # 5. Synthetic "asset" pseudo-chunk - lets the formatter surface the
    #    caption as a citation-friendly block. Tagged as a figure chunk so
    #    it picks up the FIG- prefix. The asset_label is the SERVER-CANONICAL
    #    value generated above, never the client-supplied label.
    if asset_caption or asset_type:
        grounded.insert(0, {
            "id": f"asset:{focused_asset}",
            "resource_id": resource_id,
            "chunk_index": -1,
            "chunk_text": asset_caption or f"{asset_type or 'asset'} on page {page}",
            "chunk_type": "figure",
            "source_refs": {"page": page, "concept": "focused asset"},
            "similarity": None,
            "asset_id": asset_id,
            "asset_url": asset_url,
            "asset_label": canonical_asset_label,
            "no_linked_formula": no_linked_formula,
        })

    return grounded


def _enrich_chunks_with_resource_meta(chunks: list[dict], resource_id: Optional[str]) -> None:
    """
    Attach `resource_title`, `specification_point_id`, and
    `specification_point_ref` to each chunk in-place, so student-mode
    citations can show "Resource title · p.N · spec ref" without a
    second round-trip on the frontend, and developer mode still exposes
    the full traceability required by RAG_ARCHITECTURE.md §Traceability.

    Reuses the existing PostgREST path. Non-fatal: any failure leaves
    the chunks unchanged (the tutor still answers from RAG retrieval).
    """
    if not chunks or not SUPABASE_URL or not SUPABASE_KEY:
        return

    title: Optional[str] = None
    spec_by_id: dict[str, tuple[str, str]] = {}

    try:
        headers = _supabase_headers()
    except HTTPException:
        return  # Supabase not configured — non-fatal

    # 1. Resolve the resource title — single GET.
    if resource_id:
        try:
            r_resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/resources",
                headers=headers,
                params={
                    "id": f"eq.{resource_id}",
                    "select": "id,title,specification_point_id",
                },
                timeout=10,
            )
            rows = _safe_json_list(r_resp) if r_resp.status_code == 200 else []
            if rows:
                row = rows[0]
                title = row.get("title")
                spec_pt_id = row.get("specification_point_id")
                # Pre-populate the spec cache if the resource carries one.
                if spec_pt_id:
                    spec_by_id.setdefault(str(spec_pt_id), (str(spec_pt_id), ""))
        except requests.RequestException:
            pass

    # 2. Resolve specification-point references (reference_code + description)
    #    for every spec id mentioned in chunk source_refs. Single batched GET.
    spec_ids_to_resolve: set[str] = set()
    for c in chunks:
        sid = c.get("specification_point_id") or (c.get("source_refs") or {}).get("spec_point_id")
        if sid:
            try:
                spec_ids_to_resolve.add(str(uuid.UUID(str(sid).strip())))
            except ValueError:
                continue
    if spec_ids_to_resolve:
        id_filter = ",".join(sorted(spec_ids_to_resolve))
        try:
            sp_resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/specification_points",
                headers=headers,
                params={
                    "id": f"in.({id_filter})",
                    "select": "id,reference_code,description",
                },
                timeout=10,
            )
            if sp_resp.status_code == 200:
                for row in _safe_json_list(sp_resp):
                    rid = str(row.get("id"))
                    ref = row.get("reference_code") or ""
                    desc = row.get("description") or ""
                    spec_by_id[rid] = (rid, f"{ref}: {desc}" if ref and desc else ref or desc)
        except requests.RequestException:
            pass

    # 3. Attach the resolved metadata back onto each chunk.
    for c in chunks:
        if title and not c.get("resource_title"):
            c["resource_title"] = title
        sid = c.get("specification_point_id") or (c.get("source_refs") or {}).get("spec_point_id")
        if sid and str(sid) in spec_by_id:
            _, ref = spec_by_id[str(sid)]
            c.setdefault("specification_point_id", str(sid))
            if ref and not c.get("specification_point_ref"):
                # Carry it on the chunk for _chunks_to_sources to pick up.
                (c.setdefault("source_refs", {}))["spec_point"] = ref


# ===== retained for /api/grade compatibility (still dumps full JSON) =====
def fetch_forces_and_motion_data():
    """
    Fetches the JSON OpenKB structure for the "Forces and Motion" resource
    directly from Supabase.  NOTE: /api/tutor no longer calls this — it uses
    RAG retrieval instead.  This helper is retained for /api/grade which
    still requires full-spec grading context.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase credentials not configured for grading context.")
        return None

    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/resources",
            headers=_supabase_headers(),
            params={"id": f"eq.{TARGET_RESOURCE_ID}", "select": "content"},
            timeout=15,
        )
        if response.status_code == 200:
            data = _safe_json_list(response)
            if data:
                return data[0].get("content")
    except (requests.RequestException, HTTPException) as exc:
        logger.warning("Error fetching Supabase grading context: %s", _sanitize_error_text(exc))

    return None


def _model_tag(model_name: str) -> str:
    """Normalize a model identifier into a compact uppercase badge tag."""
    return re.sub(r"[^A-Za-z0-9]+", "_", (model_name or "").upper()).strip("_")


# Semantic Router Logic
def evaluate_routing(prompt: str) -> str:
    """Return the highest-priority configured LLM provider name."""
    if opencode_zen_client:
        return "OPENCODE_ZEN"
    if nvidia_client:
        return "NVIDIA"
    if GEMINI_API_KEY:
        return "GEMINI"
    return "NONE"


def _build_chat_messages(history: Optional[List[Message]], user_prompt: str) -> list[dict]:
    """Convert chat history + current prompt into OpenAI-style chat messages."""
    messages: list[dict] = []
    for msg in history or []:
        content = (msg.content or "").strip()
        if not content:
            continue
        messages.append({
            "role": "user" if msg.role == "user" else "assistant",
            "content": content,
        })
    messages.append({"role": "user", "content": user_prompt})
    return messages


def _call_opencode_zen(
    messages: list,
    system_prompt: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> tuple[str, str]:
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = opencode_zen_client.chat.completions.create(
        model=OPENCODE_ZEN_MODEL,
        messages=full_messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=LLM_TIMEOUT_SECONDS,
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("OpenCode Zen returned empty response")
    return content, f"OPENCODE_ZEN_{_model_tag(OPENCODE_ZEN_MODEL)}"


def _call_nvidia(
    messages: list,
    system_prompt: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> tuple[str, str]:
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    candidate_models = list(dict.fromkeys([NVIDIA_CHAT_MODEL, NVIDIA_FALLBACK_CHAT_MODEL]))
    last_exc: Optional[Exception] = None

    for model_name in candidate_models:
        if not model_name:
            continue
        try:
            response = nvidia_client.chat.completions.create(
                model=model_name,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=LLM_TIMEOUT_SECONDS,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise RuntimeError(f"NVIDIA model {model_name} returned empty response")
            return content, _model_tag(model_name)
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "NVIDIA model %s failed (%s); trying next NVIDIA model if available.",
                model_name,
                _sanitize_error_text(exc),
            )

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("No NVIDIA chat model configured")


def _call_gemini(
    history: Optional[List[Message]],
    user_prompt: str,
    system_prompt: str,
    *,
    temperature: float = 0.2,
) -> tuple[str, str]:
    gemini_history = []
    for msg in history or []:
        content = (msg.content or "").strip()
        if not content:
            continue
        role = "user" if msg.role == "user" else "model"
        gemini_history.append({"role": role, "parts": [{"text": content}]})

    local_model = genai.GenerativeModel(
        GEMINI_CHAT_MODEL,
        system_instruction=system_prompt,
        generation_config={"temperature": temperature},
    )
    chat = local_model.start_chat(history=gemini_history)
    result = chat.send_message(
        user_prompt,
        request_options={"timeout": LLM_TIMEOUT_SECONDS},
    )
    try:
        reply_text = (result.text or "").strip()
    except ValueError as exc:
        raise RuntimeError("Gemini response had no text content") from exc
    if not reply_text:
        raise RuntimeError("Gemini returned empty response")
    return reply_text, "GEMINI_FLASH"


def _call_llm_with_fallback(
    history: Optional[List[Message]],
    user_prompt: str,
    system_prompt: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    validator=None,
):
    """
    Execute an LLM request across configured providers in strict priority order:
    OpenCode Zen -> NVIDIA NIM -> Gemini 2.5 Flash.

    Never leaks raw upstream error details or keys to the caller.
    """
    providers: list[str] = []
    if opencode_zen_client:
        providers.append("OPENCODE_ZEN")
    if nvidia_client:
        providers.append("NVIDIA")
    if GEMINI_API_KEY:
        providers.append("GEMINI")

    if not providers:
        raise HTTPException(status_code=503, detail="AI service is not configured.")

    messages = _build_chat_messages(history, user_prompt)

    for provider in providers:
        try:
            if provider == "OPENCODE_ZEN":
                raw_reply, model_used = _call_opencode_zen(
                    messages, system_prompt, temperature=temperature, max_tokens=max_tokens
                )
            elif provider == "NVIDIA":
                raw_reply, model_used = _call_nvidia(
                    messages, system_prompt, temperature=temperature, max_tokens=max_tokens
                )
            else:
                raw_reply, model_used = _call_gemini(
                    history, user_prompt, system_prompt, temperature=temperature
                )

            if validator is not None:
                return validator(raw_reply), model_used
            return raw_reply, model_used
        except Exception as exc:
            logger.warning(
                "LLM provider %s failed (%s); falling back if another provider is available.",
                provider,
                _sanitize_error_text(exc),
            )

    raise HTTPException(
        status_code=502,
        detail="AI service is temporarily unavailable. Please try again shortly.",
    )


@app.post("/api/tutor", response_model=TutorResponse)
def tutor_endpoint(
    request: TutorRequest,
    _user: dict = Depends(get_current_user),
):
    student_prompt = (request.student_prompt or "").strip()
    if not student_prompt:
        raise HTTPException(status_code=400, detail="student_prompt is required.")
    if len(student_prompt) > 16000:
        raise HTTPException(status_code=400, detail="student_prompt exceeds maximum length.")

    # Resolve the effective learning context. The frontend may send
    # either the new structured `learning_context` object (preferred),
    # or the legacy bare `resource_id` field (backward compatibility).
    ctx = request.learning_context
    top_resource_id = _normalize_optional_uuid(request.resource_id, "resource_id")
    ctx_resource_id = (
        _normalize_optional_uuid(ctx.resource_id, "learning_context.resource_id")
        if ctx
        else None
    )
    if ctx_resource_id and top_resource_id and ctx_resource_id != top_resource_id:
        raise HTTPException(
            status_code=400,
            detail="resource_id conflicts with learning_context.resource_id.",
        )
    effective_resource_id = ctx_resource_id or top_resource_id
    effective_chapter_id = (
        _normalize_optional_uuid(ctx.chapter_id, "learning_context.chapter_id")
        if ctx
        else None
    )
    interactive_state = ctx.interactive_state if ctx else None
    effective_block_id = (
        (interactive_state.block_id if interactive_state and interactive_state.block_id else None)
        or (ctx.block_id if ctx else None)
    )

    # Fail-closed server-side formula_ref resolution (ADR-0002).
    # Pydantic already validates InteractiveState.formula_ref against the server
    # allowlist; this defense-in-depth check ensures no unapproved or spoofed
    # formula_ref can ever enter the prompt even if constructed bypassingly.
    resolved_formula: Optional[CanonicalFormula] = None
    if interactive_state and interactive_state.formula_ref:
        try:
            resolved_formula = resolve_formula_ref(interactive_state.formula_ref, fail_closed=True)
        except UnknownFormulaRefError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if ctx and ctx.focused_asset:
        ctx.focused_asset = _normalize_optional_uuid(ctx.focused_asset, "learning_context.focused_asset")
    if ctx and ctx.focused_asset and not effective_resource_id:
        raise HTTPException(status_code=400, detail="A focused asset requires a resource_id.")
    if ctx and effective_resource_id and not ctx.resource_id:
        # Keep the legacy top-level field compatible with asset grounding.
        ctx.resource_id = effective_resource_id

    # --- RAG Retrieval ---
    # When chapter_id is present, use chapter-scoped model-tagged retrieval
    # (`match_chapter_chunks` filtered by active EMBED_MODEL) with deterministic
    # lexical fallback. Otherwise preserve the legacy resource-scoped
    # `match_resource_chunks` path.
    effective_spec_refs = (
        list(interactive_state.spec_refs)
        if (interactive_state and interactive_state.spec_refs)
        else None
    )
    retrieved_chunks = _retrieve_relevant_chunks(
        student_prompt,
        resource_id=effective_resource_id,
        chapter_id=effective_chapter_id,
        spec_refs=effective_spec_refs,
    )

    # --- Asset Grounding (Task 5) ---
    # Static PDF focused_asset verification remains 100% fail-closed.
    grounded_chunks: list[dict] = []
    if ctx and ctx.focused_asset:
        grounded_chunks = _ground_focused_asset(ctx)

    # Prepend server-grounded chunks (focused asset + allowlisted formula)
    # before retrieved RAG chunks, deduplicated by chunk id.
    prefix_chunks: list[dict] = list(grounded_chunks)
    if resolved_formula is not None:
        prefix_chunks.append(
            formula_to_synthetic_chunk(
                resolved_formula,
                chapter_id=effective_chapter_id,
                block_id=effective_block_id,
            )
        )
    if prefix_chunks:
        deduped = list(prefix_chunks)
        existing_ids = {c.get("id") for c in deduped if c.get("id")}
        for rc in retrieved_chunks:
            if rc.get("id") not in existing_ids:
                deduped.append(rc)
        retrieved_chunks = deduped

    # Enrich chunks with resource title + specification-point reference
    # so student-mode citations can show "Resource title · p.N · spec"
    # without a second round-trip on the frontend.
    _enrich_chunks_with_resource_meta(retrieved_chunks, effective_resource_id)

    assign_canonical_citation_labels(retrieved_chunks)
    rag_context = _format_chunks_as_context(retrieved_chunks)
    sources = _chunks_to_sources(retrieved_chunks)

    logger.info(
        "[RAG] Retrieved %d chunks for tutor context (grounded=%d, formula_grounded=%s).",
        len(retrieved_chunks),
        len(grounded_chunks),
        bool(resolved_formula),
    )

    # --- Tutor context preamble (Tasks 1 & 4) ---
    # When a focused asset is present, tell the tutor EXACTLY which
    # figure the student is viewing and instruct it to explain / guide /
    # coach / question from that figure rather than asking the student
    # to "describe the graph". This is the root-cause fix for the
    # "Can you describe the graph?" regression.
    context_preamble = ""
    if ctx:
        # Derive the canonical asset label from the grounded chunks (the
        # synthetic asset chunk at index 0 carries the backend-generated
        # canonical label). Fall back to the context label only if no
        # grounded chunks were produced (non-fatal path).
        canonical_label = None
        no_linked_formula = False
        if grounded_chunks:
            for gc in grounded_chunks:
                if gc.get("asset_label"):
                    canonical_label = gc["asset_label"]
                    no_linked_formula = gc.get("no_linked_formula", False)
                    break
        # ISSUE 1 (Session 4A.2): The canonical label comes ONLY from the
        # backend-grounded asset row. We do NOT fall back to the client-
        # supplied focused_asset_label — the frontend no longer sends it,
        # and trusting a client label would re-introduce the source-of-truth
        # violation. If no grounded chunk carries a canonical label, the
        # preamble simply uses the asset type without a citation ID.
        effective_label = canonical_label
        if effective_label:
            asset_kind = ctx.focused_asset_type or "asset"
            context_preamble = (
                f"The student is currently viewing {effective_label} "
                f"(a {asset_kind}"
                + (f" on page {ctx.page}" if ctx.page is not None else "")
                + "). The figure is visible to the student — do NOT ask them "
                f"to describe it. Instead, acknowledge the figure and help the "
                f"student work with it: explain what it shows, guide their "
                f"reasoning, ask a focused question about the figure, or coach "
                f"them step-by-step. Prefer concrete references to the visible "
                f"figure (axes, slope, intercepts, labelled values) over "
                f"generic 'What do you see?' prompts.\n\n"
            )
            if no_linked_formula:
                context_preamble += (
                    "No governing formula is linked to this graph. Do NOT "
                    "invent or guess an equation. If the student asks about "
                    "the governing formula, state honestly that no verified "
                    "governing formula is linked to this graph.\n\n"
                )
        elif ctx.focused_question:
            context_preamble = (
                f"The student is currently working on question "
                f"'{ctx.focused_question}'. Help them reason through it "
                f"socratically without revealing the final answer.\n\n"
            )
        elif ctx.focused_chunk:
            context_preamble = (
                f"The student is currently viewing chunk {ctx.focused_chunk}. "
                f"Ground your guidance in that content.\n\n"
            )

        if interactive_state is not None:
            context_preamble += build_interactive_state_preamble(
                interactive_state,
                resolved_formula=resolved_formula,
            )

    # Build system prompt — tutor persona + context preamble + RAG context
    # (NOT the full JSON). The persona follows AI_SYSTEM_ARCHITECTURE.md:
    # teach, guide, question, support — never simply give answers.
    system_prompt = (
        "You are an expert, encouraging Edexcel IGCSE and A-Level Physics Tutor.\n"
        "You are an Edexcel IGCSE Physics Examiner. Never ask hybrid coordinate-graphing questions. Questions must be EITHER a pure mathematical calculation OR a conceptual explanation. Do not deviate from official past-paper formats.\n"
        "You guide students using Socratic questioning and never give the final answer immediately.\n"
        "When the student asks 'Help me answer', do NOT respond by asking them to describe a graph or figure that they are already viewing. The visible figure is provided to you in the context — use it.\n"
        "Prefer responses like: \"I can see you're looking at Figure FIG-04. Let's examine it together. What happens to the slope between 2 s and 4 s?\" over generic \"Describe the graph.\" prompts.\n"
        "Format mathematical explanations cleanly.\n"
        "Stacked Fractions Only: Always write physics formulas and worked calculation divisions using stacked LaTeX fractions (\\dfrac{numerator}{denominator} inline or \\frac{...}{...} in $$ ... $$ display blocks), never slash notation like s/t or (v-u)/t. Keep standard Edexcel SI unit notation (m/s, m/s^2, m/s²) as written on exam papers.\n"
        "ZPD-Calibrated Socratic Hints: Start with the smallest helpful nudge rather than dumping full solutions; when a student struggles to rearrange an equation, scaffold step-by-step (identifying knowns $u, v, a, s, t$ or offering a formula-triangle cue) before revealing the final arithmetic.\n"
        "The UI has 4 tabs: Lesson, Worksheet, Simulation, and Quiz. If a student asks to view a resource, take a quiz, or use a simulation, you must append a navigation tag to the end of your response in the exact format: [SWITCH_TAB: TabName] (e.g., [SWITCH_TAB: Quiz]).\n"
    )

    if context_preamble:
        system_prompt += "\n" + context_preamble

    if rag_context:
        system_prompt += (
            "\n"
            "When citing a fact from the retrieved context below, reference its server-canonical "
            "citation ID in brackets (e.g. [BLK-01], [PRC-01], [EXM-01], [WE-01], [EQ-CH1-01], "
            "[FIG-A01], [TAB-01], [QN-01], [SRC-A01]). Do NOT invent citation IDs or page numbers "
            "— only use information explicitly present in the retrieved context.\n"
            "\n"
            + rag_context + "\n"
        )
    else:
        system_prompt += (
            "\nNo verified curriculum context was retrieved for this request. "
            "Do not present remembered or inferred curriculum facts as verified. "
            "Be explicit that the answer could not be grounded and ask the student "
            "for a narrower question or suggest retrying when the worksheet context is available.\n"
        )

    reply, model_used = _call_llm_with_fallback(
        request.history,
        student_prompt,
        system_prompt,
        temperature=0.2,
        max_tokens=4096,
    )
    return TutorResponse(response=reply, model_used=model_used, sources=sources)


@app.get("/health")
async def health_check():
    return {"status": "OK", "message": "FastAPI Backend is running"}


# -------------------------------------------------------------------
# Visual Asset Endpoints (Milestone 2 — Resource Delivery Layer)
# -------------------------------------------------------------------

def _supabase_headers() -> dict:
    """Build the standard PostgREST headers using the service-role key."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=503, detail="Database service is not configured.")
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _fetch_resource_assets(resource_id: str, asset_type: Optional[str] = None) -> list[dict]:
    """Query visual assets for a validated resource_id safely via PostgREST params."""
    headers = _supabase_headers()
    params = {
        "resource_id": f"eq.{resource_id}",
        "select": (
            "id,page_number,asset_type,storage_url,mime_type,width,height,"
            "bounding_box,caption,linked_question_id,content_verified,metadata,created_at"
        ),
        "order": "page_number.asc,created_at.asc" if asset_type is None else "page_number.asc",
    }
    if asset_type is not None:
        params["asset_type"] = f"eq.{asset_type}"

    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/resource_assets",
            headers=headers,
            params=params,
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.warning("Supabase asset request error: %s", _sanitize_error_text(exc))
        raise HTTPException(status_code=503, detail="Database service is temporarily unavailable.") from exc

    if resp.status_code != 200:
        logger.warning("Supabase asset query failed with status %s.", resp.status_code)
        raise HTTPException(status_code=502, detail="Failed to retrieve visual assets.")

    return _safe_json_list(resp)


@app.get("/api/resources/{resource_id}/assets")
def get_resource_assets(
    resource_id: str,
    _user: dict = Depends(get_current_user),
):
    """
    List all visual assets registered for a given resource.

    Queries the `resource_assets` table via PostgREST and returns an
    array of asset objects with public `storage_url`s ready for
    frontend <img> rendering.
    """
    normalized_id = _normalize_optional_uuid(resource_id, "resource_id")
    if not normalized_id:
        raise HTTPException(status_code=400, detail="resource_id is required.")
    assets = _fetch_resource_assets(normalized_id)
    return {"resource_id": normalized_id, "assets": assets, "count": len(assets)}


@app.get("/api/resources/{resource_id}/assets/{asset_type}")
def get_resource_assets_by_type(
    resource_id: str,
    asset_type: str,
    _user: dict = Depends(get_current_user),
):
    """
    List visual assets of a specific type for a resource
    (e.g. /api/resources/{id}/assets/graph).
    """
    normalized_id = _normalize_optional_uuid(resource_id, "resource_id")
    if not normalized_id:
        raise HTTPException(status_code=400, detail="resource_id is required.")
    normalized_type = _validate_asset_type(asset_type)
    assets = _fetch_resource_assets(normalized_id, asset_type=normalized_type)
    return {
        "resource_id": normalized_id,
        "asset_type": normalized_type,
        "assets": assets,
        "count": len(assets),
    }

# -------------------------------------------------------------------
# Hybrid Retrieval Endpoints (Session 2 — Hybrid Retrieval Foundation)
# -------------------------------------------------------------------


def _embed_query(text: str) -> list[float]:
    """Embed a natural-language query via active NVIDIA NIM embedding model."""
    if not nvidia_client:
        raise HTTPException(status_code=503, detail="Embedding service is not configured.")

    kwargs: dict = {
        "model": EMBED_MODEL,
        "input": text,
        "encoding_format": "float",
        "extra_body": {"input_type": "query", "truncate": "END"},
        "timeout": 10.0,
    }
    if "nemotron-3.5-embed" in EMBED_MODEL.lower():
        kwargs["dimensions"] = EMBED_DIM

    resp = nvidia_client.embeddings.create(**kwargs)
    vec = resp.data[0].embedding
    if len(vec) != EMBED_DIM:
        raise ValueError(f"Embedding dimension mismatch: expected {EMBED_DIM}, got {len(vec)}")
    return vec


def _vector_to_pg_str(vec: list[float]) -> str:
    """Convert a float list to a pgvector literal: [0.1,0.2,...]"""
    return f"[{','.join(str(round(v, 8)) for v in vec)}]"


class SearchRequest(BaseModel):
    query: str
    match_count: int = 10
    filter_resource_id: Optional[str] = None


class HybridSearchRequest(BaseModel):
    query: str
    match_count: int = 10
    resource_id: Optional[str] = None
    chapter_id: Optional[str] = None
    source_types: Optional[List[str]] = None
    spec_refs: Optional[List[str]] = None
    # Relational filters
    spec_point_id: Optional[str] = None
    chunk_type: Optional[str] = None


@app.post("/api/search")
def semantic_search(
    request: SearchRequest,
    _user: dict = Depends(get_current_user),
):
    """
    Pure vector (semantic) search over resource_chunks.

    Embeds the query via NVIDIA NIM and calls the `match_resource_chunks`
    Postgres RPC function for cosine similarity ranking.
    """
    query = (request.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required.")
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=503, detail="Database service is not configured.")

    filter_resource_id = _normalize_optional_uuid(request.filter_resource_id, "filter_resource_id")
    match_count = max(1, min(request.match_count, 50))

    # 1. Embed query safely (never allow upstream exceptions to escape CORSMiddleware)
    try:
        query_vec = _embed_query(query)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Semantic search embedding error: %s", _sanitize_error_text(exc))
        raise HTTPException(
            status_code=503,
            detail="Semantic vector search is temporarily unavailable.",
        ) from exc

    vec_str = _vector_to_pg_str(query_vec)

    # 2. Call RPC function
    headers = _supabase_headers()
    rpc_body = {
        "query_embedding": vec_str,
        "match_count": match_count,
    }
    if filter_resource_id:
        rpc_body["filter_resource_id"] = filter_resource_id

    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/match_resource_chunks",
            headers=headers,
            json=rpc_body,
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.warning("Vector search RPC network error: %s", _sanitize_error_text(exc))
        raise HTTPException(status_code=503, detail="Database service is temporarily unavailable.") from exc

    if resp.status_code != 200:
        logger.warning("Vector search RPC failed with status %s.", resp.status_code)
        raise HTTPException(status_code=502, detail="Vector search query failed.")

    results = _safe_json_list(resp)
    return {
        "query": query,
        "results": results,
        "count": len(results),
        "search_type": "semantic",
    }


@app.post("/api/search/hybrid")
def hybrid_search(
    request: HybridSearchRequest,
    _user: dict = Depends(get_current_user),
):
    """
    Combined relational + vector (semantic) search.

    Runs both:
      - Relational + lexical: filter resources/chunks via PostgREST
      - Vector: pgvector cosine similarity via match_resource_chunks RPC (non-fatal)

    Merges results, deduplicating by chunk id and keeping the higher
    similarity score. Vector results that also appear in the relational
    results get a relevance boost. If vector search is unavailable or in a
    different embedding space, gracefully degrades to relational/lexical search.
    """
    query = (request.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required.")
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=503, detail="Database service is not configured.")

    resource_id = _normalize_optional_uuid(request.resource_id, "resource_id")
    chapter_id = _normalize_optional_uuid(request.chapter_id, "chapter_id")
    spec_point_id = _normalize_optional_uuid(request.spec_point_id, "spec_point_id")
    chunk_type = _validate_asset_type(request.chunk_type) if (request.chunk_type and request.chunk_type.strip()) else None
    source_types = _validate_source_types(request.source_types)
    spec_refs = [s.strip() for s in (request.spec_refs or []) if s and s.strip()] or None
    match_count = max(1, min(request.match_count, 50))

    headers = _supabase_headers()

    # --- 1. Vector search (non-fatal when embedding provider is unavailable) ---
    vector_results: list[dict] = []
    vector_ok = False
    if nvidia_client:
        try:
            query_vec = _embed_query(query)
            vec_str = _vector_to_pg_str(query_vec)

            if chapter_id:
                active_model = (EMBED_MODEL or ACTIVE_EMBEDDING_MODEL).strip()
                rpc_body = {
                    "query_embedding": vec_str,
                    "filter_chapter_id": chapter_id,
                    "filter_embedding_model": active_model,
                    "match_threshold": VECTOR_MIN_RELEVANCE,
                    "match_count": match_count * 2,
                }
                if source_types:
                    rpc_body["filter_source_types"] = source_types
                if spec_refs:
                    rpc_body["filter_spec_refs"] = spec_refs
                rpc_endpoint = f"{SUPABASE_URL}/rest/v1/rpc/match_chapter_chunks"
            else:
                rpc_body = {
                    "query_embedding": vec_str,
                    "match_count": match_count * 2,  # fetch more for merging
                }
                if resource_id:
                    rpc_body["filter_resource_id"] = resource_id
                rpc_endpoint = f"{SUPABASE_URL}/rest/v1/rpc/match_resource_chunks"

            rpc_resp = requests.post(
                rpc_endpoint,
                headers=headers,
                json=rpc_body,
                timeout=15,
            )
            if rpc_resp.status_code == 200:
                vector_results = _safe_json_list(rpc_resp)
                if chapter_id:
                    active_model = (EMBED_MODEL or ACTIVE_EMBEDDING_MODEL).strip()
                    vector_results = [
                        result for result in vector_results
                        if result.get("embedding_model") == active_model
                    ]
                vector_ok = True
                if chunk_type:
                    vector_results = [
                        result for result in vector_results
                        if result.get("chunk_type") == chunk_type
                    ]
            else:
                logger.warning("Hybrid vector RPC failed with status %s.", rpc_resp.status_code)
        except (HTTPException, Exception) as exc:
            logger.warning("Hybrid vector search degraded (non-fatal): %s", _sanitize_error_text(exc))

    # --- 2. Relational + lexical search (PostgREST) ---
    relational_results: list[dict] = []
    relational_ok = False

    # Resolve spec_point_id -> resource_ids if provided
    spec_resource_ids: Optional[list[str]] = None
    if spec_point_id:
        try:
            res_resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/resources",
                headers=headers,
                params={"specification_point_id": f"eq.{spec_point_id}", "select": "id"},
                timeout=15,
            )
            if res_resp.status_code == 200:
                relational_ok = True
                spec_resource_ids = [str(r["id"]) for r in _safe_json_list(res_resp) if r.get("id")]
                if resource_id:
                    spec_resource_ids = [rid for rid in spec_resource_ids if rid == resource_id]
        except requests.RequestException as exc:
            logger.warning("Hybrid spec_point lookup failed: %s", _sanitize_error_text(exc))

    # Lexical keyword retrieval (provides real matches even if vector embeddings
    # are unavailable or come from an incompatible embedding model space).
    lexical_results: list[dict] = []
    if spec_resource_ids is None or len(spec_resource_ids) > 0:
        lexical_results, lex_ok = _lexical_search_chunks(
            query,
            match_count=match_count * 2,
            resource_id=resource_id,
            chunk_type=chunk_type,
            resource_ids=spec_resource_ids,
            chapter_id=chapter_id,
            source_types=source_types,
            target_spec_refs=spec_refs,
        )
        relational_ok = relational_ok or lex_ok

    # Explicit chunk_type filter relational fetch (preserves boost when filter chip active)
    if chunk_type and (spec_resource_ids is None or len(spec_resource_ids) > 0):
        try:
            rel_params = {
                "chunk_type": f"eq.{chunk_type}",
                "select": "id,resource_id,chunk_index,chunk_text,chunk_type,source_refs,token_count",
                "limit": str(match_count * 2),
            }
            if resource_id:
                rel_params["resource_id"] = f"eq.{resource_id}"
            elif spec_resource_ids:
                rel_params["resource_id"] = f"in.({','.join(spec_resource_ids)})"
            rel_resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/resource_chunks",
                headers=headers,
                params=rel_params,
                timeout=15,
            )
            if rel_resp.status_code == 200:
                relational_ok = True
                relational_results.extend(_safe_json_list(rel_resp))
        except requests.RequestException:
            pass

    # If spec_point_id was filtered without chunk_type, include those scoped chunks too
    if spec_point_id and not chunk_type and spec_resource_ids:
        try:
            chunk_resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/resource_chunks",
                headers=headers,
                params={
                    "resource_id": f"in.({','.join(spec_resource_ids)})",
                    "select": "id,resource_id,chunk_index,chunk_text,chunk_type,source_refs,token_count",
                    "limit": str(match_count * 2),
                },
                timeout=15,
            )
            if chunk_resp.status_code == 200:
                relational_ok = True
                for c in _safe_json_list(chunk_resp):
                    c["similarity"] = None
                    relational_results.append(c)
        except requests.RequestException:
            pass

    if not vector_ok and not relational_ok:
        raise HTTPException(
            status_code=503,
            detail="Search service is temporarily unavailable.",
        )

    # Filter out low-confidence cross-model vector noise when lexical matches exist,
    # and clamp any negative cosine similarity so UI badges never show negative %.
    max_vec_sim = max((r.get("similarity") or 0.0 for r in vector_results), default=0.0)
    if lexical_results and max_vec_sim < VECTOR_MIN_RELEVANCE:
        vector_results = []
    else:
        for r in vector_results:
            if r.get("similarity") is not None and r["similarity"] < 0:
                r["similarity"] = 0.0

    # --- 3. Merge & deduplicate ---
    merged: dict[str, dict] = {}

    for r in vector_results:
        chunk_id = r.get("id")
        if chunk_id:
            r["source"] = "vector"
            r["boosted"] = False
            merged[chunk_id] = r

    for r in lexical_results:
        chunk_id = r.get("id")
        if not chunk_id:
            continue
        if chunk_id in merged:
            existing = merged[chunk_id]
            existing["similarity"] = min(1.0, max(existing.get("similarity") or 0.0, r.get("similarity") or 0.0) + 0.05)
            existing["boosted"] = True
            existing["source"] = "both"
        else:
            r["source"] = "lexical"
            r["boosted"] = False
            merged[chunk_id] = r

    for r in relational_results:
        chunk_id = r.get("id")
        if not chunk_id:
            continue
        if chunk_id in merged:
            existing = merged[chunk_id]
            if existing.get("similarity") is not None:
                existing["similarity"] = min(1.0, existing["similarity"] + 0.1)
            existing["boosted"] = True
            existing["source"] = "both"
        else:
            r["source"] = "relational"
            r["boosted"] = False
            r["similarity"] = 0.0
            merged[chunk_id] = r

    # Sort: boosted first, then by similarity descending with deterministic tie-breakers
    final = sorted(
        merged.values(),
        key=lambda x: (
            not x.get("boosted", False),
            -(x.get("similarity") or 0.0),
            int(x["chunk_index"]) if x.get("chunk_index") is not None else 10**9,
            str(x.get("id") or ""),
        ),
    )
    final = final[:match_count]
    assign_canonical_citation_labels(final)

    return {
        "query": query,
        "results": final,
        "count": len(final),
        "search_type": "hybrid",
        "vector_count": len(vector_results),
        "relational_count": len(relational_results) + len(lexical_results),
    }


@app.get("/api/question")
async def get_question(
    resource_id: Optional[str] = None,
    _user: dict = Depends(get_current_user),
):
    # This simulates fetching a question and its examiner report hint from OpenKB
    # based on the resource_id.
    _normalize_optional_uuid(resource_id, "resource_id")
    return {
        "question_index": 1,
        "question_text": "A car accelerates uniformly from rest to 20 m/s in 5 seconds. Calculate the acceleration of the car. Show your working. $a = \\frac{\\Delta v}{\\Delta t}$",
        "max_score": 3,
        "examiner_hint": "**Examiner Report Highlight:** Many students forget that 'from rest' implies an initial velocity ($u$) of 0 m/s. Ensure you state the formula clearly before substituting values. Remember $a = \\frac{v - u}{t}$."
    }


@app.post("/api/grade", response_model=GradeResponse)
def grade_endpoint(
    request: GradeRequest,
    _user: dict = Depends(get_current_user),
):
    authenticated_student_id = str(_user.get("id"))
    if request.student_id != authenticated_student_id:
        raise HTTPException(
            status_code=403,
            detail="student_id must match the authenticated user.",
        )

    _normalize_optional_uuid(request.resource_id, "resource_id")
    if request.max_score <= 0:
        raise HTTPException(status_code=400, detail="max_score must be positive.")
    if not (request.student_answer or "").strip():
        raise HTTPException(status_code=400, detail="student_answer is required.")
    if not (request.question_text or "").strip():
        raise HTTPException(status_code=400, detail="question_text is required.")

    context_data = fetch_forces_and_motion_data()

    system_prompt = (
        "You are a STRICT Edexcel IGCSE Physics Examiner. Your role is to grade student answers with zero leniency.\n"
        "You MUST respond ONLY with a valid JSON object with exactly three keys: 'marks_awarded' (integer), 'total_marks' (integer), and 'explanation' (string).\n"
        "Do NOT include any markdown, code fences, prose, or greetings outside the JSON object.\n\n"

        "=== MANDATORY GRADING PROTOCOL — FOLLOW IN STRICT ORDER ===\n\n"

        "STEP 1 — INTERNAL CALCULATION (Do this BEFORE reading the student's answer):\n"
        "  - Solve the question yourself from scratch using correct physics formulae.\n"
        "  - Compute the exact numerical result. Record this internally as the CORRECT ANSWER.\n"
        "  - Do NOT skip this step. Do NOT use the student's answer as a guide to what the answer should be.\n\n"

        "STEP 2 — APPLY THE STANDARD 3-MARK SCHEME:\n"
        "  - MARK 1 (Formula / Method): Award 1 mark if the student correctly states or implies the relevant formula or method (e.g. a = Δv/Δt). Penalise if the formula is wrong or missing.\n"
        "  - MARK 2 (Substitution / Working): Award 1 mark if the student correctly substitutes the given values into the formula and shows valid working. Penalise incorrect substitutions.\n"
        "  - MARK 3 (Accuracy / Final Answer): Award 1 mark ONLY if the student's final numerical answer EXACTLY matches your internally computed CORRECT ANSWER, to a reasonable number of significant figures (maximum 1 s.f. of rounding tolerance). The correct unit must also be present.\n\n"

        "=== ABSOLUTE PROHIBITIONS ===\n"
        "  - NEVER award MARK 3 if the student's number is mathematically wrong — even if it is 'close'.\n"
        "  - NEVER invent or accept excuses such as 'rounding error', 'close enough', 'approximately correct', or 'within acceptable range' to justify awarding MARK 3 for an incorrect value.\n"
        "  - NEVER give follow-through credit on MARK 3 if the formula or substitution was wrong.\n"
        "  - NEVER award more marks than the max_score field specifies.\n\n"

        "=== EXPLANATION FIELD ===\n"
        "  Your 'explanation' must:\n"
        "  1. State the correct answer you calculated in STEP 1.\n"
        "  2. State which marks were awarded and the precise reason for each.\n"
        "  3. If a mark was withheld, state the EXACT error the student made.\n"
    )

    if context_data:
        system_prompt += f"\n\nContext (Forces and Motion Knowledge Graph & Mark Scheme):\n{context_data}\n"

    user_prompt = (
        f"Question: {request.question_text}\n"
        f"Maximum marks available: {request.max_score}\n"
        f"Student's Answer: {request.student_answer}\n"
        "Please provide your strict JSON assessment."
    )

    def _parse_grade_reply(reply: str) -> GradeResponse:
        try:
            parsed_json = json.loads(reply)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", reply, re.DOTALL)
            if match:
                parsed_json = json.loads(match.group(0))
            else:
                raise ValueError("Could not extract JSON from LLM response.")
        raw_marks = int(parsed_json.get("marks_awarded", 0))
        clamped_marks = max(0, min(request.max_score, raw_marks))
        return GradeResponse(
            marks_awarded=clamped_marks,
            total_marks=request.max_score,
            explanation=str(parsed_json.get("explanation", "No explanation provided.")),
        )

    graded, _model_used = _call_llm_with_fallback(
        [],
        user_prompt,
        system_prompt,
        temperature=0.1,
        max_tokens=2048,
        validator=_parse_grade_reply,
    )
    return graded
