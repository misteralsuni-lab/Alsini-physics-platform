import os
import requests
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai
from typing import List, Optional
import json
import re
# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="Alsini Physics VLE - AI Tutor API", version="1.0")

# Configure CORS for the known frontend origins. The API carries privileged
# server-side credentials, so wildcard origins are intentionally not allowed.
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
configured_origins = os.getenv(
    "CORS_ORIGINS",
    ",".join([frontend_url, "http://localhost:5174", "http://localhost:3000"]),
)
allowed_origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

# Environment Variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
OPENCODE_ZEN_API_KEY = os.getenv("OPENCODE_ZEN_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

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

    try:
        response = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": SUPABASE_ANON_KEY or SUPABASE_KEY,
                "Authorization": f"Bearer {credentials.credentials}",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="Authentication service is unavailable.") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="A valid Supabase access token is required.")

    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Authentication service returned an invalid user.") from exc


# Initialize APIs
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

nvidia_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
) if NVIDIA_API_KEY else None

opencode_zen_client = OpenAI(
    base_url="https://opencode.ai/zen/v1",
    api_key=OPENCODE_ZEN_API_KEY
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
    # Human-readable asset label when the student is viewing a graph /
    # figure / table / diagram / equation asset (e.g. "FIG-04"). When
    # present the tutor must acknowledge the visible asset and guide
    # from it rather than asking the student to describe it.
    focused_asset_label: Optional[str] = None
    focused_asset_type: Optional[str] = None
    focused_question: Optional[str] = None
    page: Optional[int] = None

class TutorRequest(BaseModel):
    student_prompt: str
    history: Optional[List[Message]] = []
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

class TutorResponse(BaseModel):
    response: str
    model_used: str
    sources: List[TutorSource] = []

class GradeRequest(BaseModel):
    student_id: str
    resource_id: str
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

# -------------------------------------------------------------------
# RAG Retrieval Helpers (reuse existing _embed_query and _supabase_headers)
# -------------------------------------------------------------------

def _retrieve_relevant_chunks(
    query: str,
    match_count: int = TUTOR_CHUNK_COUNT,
    resource_id: Optional[str] = None,
) -> list[dict]:
    """
    Embed the student's question, call match_resource_chunks RPC, and
    return ranked chunks for RAG context.

    Retrieval scope is dynamic:
      - If `resource_id` is provided, the RPC's `filter_resource_id`
        parameter is set to it so chunks are scoped to the CURRENTLY
        SELECTED worksheet only (dynamic tutor scope).
      - If `resource_id` is None, retrieval is unscoped (returns chunks
        across all resources) — used as a fallback when the frontend
        has not resolved a worksheet yet.

    Returns empty list on any failure (non-fatal — tutor still works).
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[RAG] Supabase credentials not configured — skipping retrieval.")
        return []
    if not nvidia_client:
        print("[RAG] NVIDIA API not configured — skipping embedding.")
        return []

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
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[RAG] RPC failed ({resp.status_code}): {resp.text[:120]}")
            return []
        chunks = resp.json()
        # Attach resource_id onto each chunk for traceability in TutorSource.
        if resource_id:
            for c in chunks:
                c.setdefault("resource_id", resource_id)
        return chunks
    except Exception as e:
        print(f"[RAG] Retrieval error (non-fatal): {e}")
        return []


def _format_chunks_as_context(chunks: list[dict]) -> str:
    """Build a compact, citation-rich context block from retrieved chunks."""
    if not chunks:
        return ""
    lines = ["Retrieved educational context:"]
    for i, c in enumerate(chunks):
        idx = i + 1
        ctype = c.get("chunk_type", "concept")
        text = c.get("chunk_text", "")
        sources = c.get("source_refs", {}) or {}
        concept = sources.get("concept", "")
        page = sources.get("page")
        sim = c.get("similarity")

        # Build a tight citation suffix
        cite_parts = []
        if concept:
            cite_parts.append(f"concept: {concept}")
        if page is not None:
            cite_parts.append(f"page {page}")
        cite_str = f" [{', '.join(cite_parts)}]" if cite_parts else ""

        lines.append(f"  [{idx}] ({ctype}){cite_str}  {text}")
    return "\n".join(lines)


def _chunks_to_sources(chunks: list[dict]) -> list[TutorSource]:
    """Extract source metadata from retrieved chunks for the response."""
    return [
        TutorSource(
            chunk_id=c.get("id", ""),
            concept=(c.get("source_refs") or {}).get("concept"),
            page=(c.get("source_refs") or {}).get("page"),
            chunk_type=c.get("chunk_type", "concept"),
            similarity=c.get("similarity"),
            # Traceability fields for developer-mode citation expansion.
            resource_id=c.get("resource_id"),
            resource_title=c.get("resource_title"),
            specification_point_id=c.get("specification_point_id"),
            specification_point_ref=(
                c.get("specification_point_ref")
                or (c.get("source_refs") or {}).get("spec_point")
            ),
            chunk_index=c.get("chunk_index"),
            asset_id=c.get("asset_id"),
            asset_url=c.get("asset_url"),
            asset_label=c.get("asset_label"),
        )
        for c in chunks
    ]


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

    resource_id = learning_context.resource_id
    page = learning_context.page
    if not resource_id:
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

    # 1. Fetch the asset itself so we can read its caption / linked question.
    asset_endpoint = f"{SUPABASE_URL}/rest/v1/resource_assets"
    asset_caption: Optional[str] = None
    linked_question_id: Optional[str] = None
    asset_type: Optional[str] = learning_context.focused_asset_type
    asset_url: Optional[str] = None
    asset_id: Optional[str] = None
    try:
        ar = requests.get(
            asset_endpoint,
            headers=headers,
            params={
                "id": f"eq.{learning_context.focused_asset}",
                # The asset and selected worksheet must belong to the same
                # resource before either can enter tutor context.
                "resource_id": f"eq.{resource_id}",
                "select": "id,resource_id,page_number,asset_type,storage_url,caption,linked_question_id,metadata",
                "limit": "1",
            },
            timeout=10,
        )
        if ar.status_code != 200:
            raise HTTPException(status_code=502, detail="Unable to verify the focused asset.")
        rows = ar.json()
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
        # Never trust client-supplied type/page when the asset row is known.
        asset_type = a.get("asset_type") or asset_type
        page = a.get("page_number") if a.get("page_number") is not None else page
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="Asset verification service is unavailable.") from exc

    # 2. On-page chunks — the reading-order text that surrounds the asset.
    if page is not None:
        page_endpoint = f"{SUPABASE_URL}/rest/v1/resource_chunks"
        try:
            pr = requests.get(
                page_endpoint,
                headers=headers,
                params={
                    "resource_id": f"eq.{resource_id}",
                    "source_refs->>page": f"eq.{page}",
                    "select": "id,resource_id,chunk_index,chunk_text,chunk_type,source_refs,token_count",
                    "order": "chunk_index.asc",
                    "limit": "50",
                },
                timeout=12,
            )
            if pr.status_code == 200:
                for c in pr.json():
                    c.setdefault("resource_id", resource_id)
                    _append_chunk(c)
        except requests.RequestException as exc:
            raise HTTPException(status_code=503, detail="Page grounding service is unavailable.") from exc

    # 3. Linked worksheet question chunk (asset → question id → chunk).
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
                for c in qr.json():
                    sr = c.get("source_refs") or {}
                    if str(sr.get("question_id", "")).strip() == qid:
                        c.setdefault("resource_id", resource_id)
                        _append_chunk(c)
        except requests.RequestException:
            pass

    # 4. Linked equation / formula chunks — when the asset is a graph,
    #    the governing equation is the most pedagogically valuable link.
    #    We pull formula chunks for the same resource; the tutor's
    #    system prompt stresses figure+equation reasoning.
    if asset_type and "graph" in (asset_type or "").lower():
        eq_endpoint = f"{SUPABASE_URL}/rest/v1/resource_chunks"
        try:
            er = requests.get(
                eq_endpoint,
                headers=headers,
                params={
                    "resource_id": f"eq.{resource_id}",
                    "chunk_type": "eq.formula",
                    "select": "id,resource_id,chunk_index,chunk_text,chunk_type,source_refs,token_count",
                    "limit": "3",
                },
                timeout=12,
            )
            if er.status_code == 200:
                for c in er.json():
                    c.setdefault("resource_id", resource_id)
                    _append_chunk(c)
        except requests.RequestException:
            pass

    # 5. Synthetic "asset" pseudo-chunk — lets the formatter surface the
    #    caption as a citation-friendly block. Tagged as a figure chunk so
    #    it picks up the FIG- prefix in the citation label.
    if asset_caption or asset_type:
        grounded.insert(0, {
            "id": f"asset:{learning_context.focused_asset}",
            "resource_id": resource_id,
            "chunk_index": -1,
            "chunk_text": asset_caption or f"{asset_type or 'asset'} on page {page}",
            "chunk_type": "figure",
            "source_refs": {"page": page, "concept": "focused asset"},
            "similarity": None,
            "asset_id": asset_id,
            "asset_url": asset_url,
            "asset_label": learning_context.focused_asset_label,
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

    headers = None
    title: Optional[str] = None
    spec_by_id: dict[str, tuple[str, str]] = {}

    try:
        headers = _supabase_headers()
    except HTTPException:
        return  # Supabase not configured — non-fatal

    # 1. Resolve the resource title — single GET.
    if resource_id:
        try:
            r_ep = (
                f"{SUPABASE_URL}/rest/v1/resources"
                f"?id=eq.{resource_id}&select=id,title,specification_point_id"
            )
            r_resp = requests.get(r_ep, headers=headers, timeout=10)
            if r_resp.status_code == 200 and r_resp.json():
                row = r_resp.json()[0]
                title = row.get("title")
                spec_pt_id = row.get("specification_point_id")
                # Pre-populate the spec cache if the resource carries one.
                if spec_pt_id:
                    spec_by_id.setdefault(spec_pt_id, (spec_pt_id, ""))
        except requests.RequestException:
            pass

    # 2. Resolve specification-point references (reference_code + description)
    #    for every spec id mentioned in chunk source_refs. Single batched GET.
    spec_ids_to_resolve: set[str] = set()
    for c in chunks:
        sid = c.get("specification_point_id") or (c.get("source_refs") or {}).get("spec_point_id")
        if sid:
            spec_ids_to_resolve.add(str(sid))
    if spec_ids_to_resolve:
        id_filter = ",".join(sorted(spec_ids_to_resolve))
        sp_ep = (
            f"{SUPABASE_URL}/rest/v1/specification_points"
            f"?id=in.({id_filter})&select=id,reference_code,description"
        )
        try:
            sp_resp = requests.get(sp_ep, headers=headers, timeout=10)
            if sp_resp.status_code == 200:
                for row in sp_resp.json():
                    rid = str(row.get("id"))
                    ref = row.get("reference_code") or ""
                    desc = row.get("description") or ""
                    spec_by_id[rid] = (rid, f"{ref}: {desc}" if ref or desc else ref or desc)
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
        print("Warning: Supabase credentials not found.")
        return None
        
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    endpoint = f"{SUPABASE_URL}/rest/v1/resources?id=eq.{TARGET_RESOURCE_ID}&select=content"
    
    try:
        response = requests.get(endpoint, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data[0].get("content")
    except Exception as e:
        print(f"Error fetching Supabase data: {e}")
    
    return None

# Semantic Router Logic
def evaluate_routing(prompt: str) -> str:
    """
    Routes all queries to OpenCode Zen (primary) with NVIDIA as fallback.
    Gemini is removed due to quota limits — all traffic goes through OpenCode Zen.
    """
    if opencode_zen_client:
        print("Semantic Router: Routing to OPENCODE_ZEN")
        return "OPENCODE_ZEN"
    if nvidia_client:
        print("Semantic Router: Routing to NVIDIA")
        return "NVIDIA"
    return "GEMINI"


def _call_opencode_zen(messages: list, system_prompt: str) -> tuple[str, str]:
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    response = opencode_zen_client.chat.completions.create(
        model="deepseek-v4-flash-free",
        messages=full_messages,
        temperature=0.2,
        max_tokens=4096,
        timeout=120,
    )
    content = response.choices[0].message.content
    if not content:
        raise HTTPException(status_code=502, detail="OpenCode Zen returned empty response")
    return content, "OPENCODE_ZEN_DEEPSEEK_V4_FLASH_FREE"


def _call_nvidia(messages: list, system_prompt: str) -> tuple[str, str]:
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    response = nvidia_client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        messages=full_messages,
        temperature=0.2,
        max_tokens=4096,
        timeout=120,
    )
    content = response.choices[0].message.content
    if not content:
        raise HTTPException(status_code=502, detail="NVIDIA returned empty response")
    return content, "NVIDIA_NEMOTRON_3_SUPER_120B"

@app.post("/api/tutor", response_model=TutorResponse)
async def tutor_endpoint(
    request: TutorRequest,
    _user: dict = Depends(get_current_user),
):
    if not request.student_prompt:
        raise HTTPException(status_code=400, detail="student_prompt is required.")

    # Resolve the effective learning context. The frontend may send
    # either the new structured `learning_context` object (preferred),
    # or the legacy bare `resource_id` field (backward compatibility).
    ctx = request.learning_context
    if ctx and ctx.resource_id and request.resource_id and ctx.resource_id != request.resource_id:
        raise HTTPException(
            status_code=400,
            detail="resource_id conflicts with learning_context.resource_id.",
        )
    effective_resource_id = (
        (ctx.resource_id if ctx and ctx.resource_id else None)
        or request.resource_id
    )
    if ctx and ctx.focused_asset and not effective_resource_id:
        raise HTTPException(status_code=400, detail="A focused asset requires a resource_id.")
    if ctx and effective_resource_id and not ctx.resource_id:
        # Keep the legacy top-level field compatible with asset grounding.
        ctx.resource_id = effective_resource_id

    # --- RAG Retrieval ---
    # Replace the old full-JSON dump with targeted hybrid retrieval.
    # Dynamic scope: pass the effective resource_id so the tutor
    # grounds its answer in the CURRENTLY SELECTED worksheet, not a
    # hardcoded resource.
    retrieved_chunks = _retrieve_relevant_chunks(
        request.student_prompt,
        resource_id=effective_resource_id,
    )

    # --- Asset Grounding (Task 5) ---
    # When the student is focused on a graph / figure / table / diagram
    # / equation, fetch the connected educational objects (caption,
    # on-page chunks, linked question, governing equation) and prepend
    # them to the RAG context so the tutor can reason from the visible
    # asset directly.
    grounded_chunks: list[dict] = []
    if ctx and ctx.focused_asset:
        grounded_chunks = _ground_focused_asset(ctx)
        if grounded_chunks:
            # Grounded chunks come first — they describe the thing the
            # student is actually looking at. RAG chunks fill in the
            # surrounding curriculum context.
            deduped = list(grounded_chunks)
            existing_ids = {c.get("id") for c in deduped if c.get("id")}
            for rc in retrieved_chunks:
                if rc.get("id") not in existing_ids:
                    deduped.append(rc)
            retrieved_chunks = deduped

    # Enrich chunks with resource title + specification-point reference
    # so student-mode citations can show "Resource title · p.N · spec"
    # without a second round-trip on the frontend.
    _enrich_chunks_with_resource_meta(retrieved_chunks, effective_resource_id)

    rag_context = _format_chunks_as_context(retrieved_chunks)
    sources = _chunks_to_sources(retrieved_chunks)

    print(f"[RAG] Retrieved {len(retrieved_chunks)} chunks for tutor context"
          f" (grounded={len(grounded_chunks)}).")

    route_target = evaluate_routing(request.student_prompt)

    # --- Tutor context preamble (Tasks 1 & 4) ---
    # When a focused asset is present, tell the tutor EXACTLY which
    # figure the student is viewing and instruct it to explain / guide /
    # coach / question from that figure rather than asking the student
    # to "describe the graph". This is the root-cause fix for the
    # "Can you describe the graph?" regression.
    context_preamble = ""
    if ctx:
        if ctx.focused_asset_label:
            asset_kind = ctx.focused_asset_type or "asset"
            context_preamble = (
                f"The student is currently viewing {ctx.focused_asset_label} "
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
        "The UI has 4 tabs: Lesson, Worksheet, Simulation, and Quiz. If a student asks to view a resource, take a quiz, or use a simulation, you must append a navigation tag to the end of your response in the exact format: [SWITCH_TAB: TabName] (e.g., [SWITCH_TAB: Quiz]).\n"
    )

    if context_preamble:
        system_prompt += "\n" + context_preamble

    if rag_context:
        system_prompt += (
            "\n"
            "When citing a fact from the retrieved context below, reference the source number "
            "in brackets (e.g. [Source 1]).  Do NOT invent or guess page numbers — only use "
            "information explicitly present in the retrieved context.\n"
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

    if route_target == "OPENCODE_ZEN":
        # Route to OpenCode Zen (primary) with NVIDIA fallback
        messages = []
        for msg in request.history:
            messages.append({"role": "user" if msg.role == "user" else "assistant", "content": msg.content})
        messages.append({"role": "user", "content": request.student_prompt})

        try:
            reply, model_used = _call_opencode_zen(messages, system_prompt)
            return TutorResponse(response=reply, model_used=model_used, sources=sources)
        except Exception as e:
            print(f"OpenCode Zen failed, falling back to NVIDIA: {e}")
            if not nvidia_client:
                raise
            reply, model_used = _call_nvidia(messages, system_prompt)
            return TutorResponse(response=reply, model_used=model_used, sources=sources)

    elif route_target == "NVIDIA":
        if not nvidia_client:
            raise HTTPException(status_code=500, detail="NVIDIA API is not configured.")

        messages = []
        for msg in request.history:
            messages.append({"role": "user" if msg.role == "user" else "assistant", "content": msg.content})
        messages.append({"role": "user", "content": request.student_prompt})

        try:
            reply, model_used = _call_nvidia(messages, system_prompt)
            return TutorResponse(response=reply, model_used=model_used, sources=sources)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"NVIDIA API Error: {str(e)}")

    else:
        # Route to Gemini Flash for simple/conversational tasks (last resort)
        if not GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="GEMINI API is not configured.")

        try:
            gemini_history = []
            for msg in request.history:
                role = "user" if msg.role == "user" else "model"
                gemini_history.append({"role": role, "parts": [{"text": msg.content}]})

            local_model = genai.GenerativeModel(
                'gemini-2.5-flash',
                system_instruction=system_prompt
            )

            chat = local_model.start_chat(history=gemini_history)
            result = chat.send_message(request.student_prompt)
            reply_text = result.text or ""

            return TutorResponse(response=reply_text, model_used="GEMINI_FLASH", sources=sources)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gemini API Error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "OK", "message": "FastAPI Backend is running"}


# -------------------------------------------------------------------
# Visual Asset Endpoints (Milestone 2 — Resource Delivery Layer)
# -------------------------------------------------------------------

def _supabase_headers() -> dict:
    """Build the standard PostgREST headers using the service-role key."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured.")
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


@app.get("/api/resources/{resource_id}/assets")
async def get_resource_assets(
    resource_id: str,
    _user: dict = Depends(get_current_user),
):
    """
    List all visual assets registered for a given resource.

    Queries the `resource_assets` table via PostgREST and returns an
    array of asset objects with public `storage_url`s ready for
    frontend <img> rendering.
    """
    headers = _supabase_headers()
    endpoint = (
        f"{SUPABASE_URL}/rest/v1/resource_assets"
        f"?resource_id=eq.{resource_id}"
        f"&select=id,page_number,asset_type,storage_url,mime_type,width,height,"
        f"bounding_box,caption,linked_question_id,content_verified,metadata,created_at"
        f"&order=page_number.asc,created_at.asc"
    )
    try:
        resp = requests.get(endpoint, headers=headers, timeout=15)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Supabase query failed ({resp.status_code}): {resp.text[:200]}",
            )
        assets = resp.json()
        return {"resource_id": resource_id, "assets": assets, "count": len(assets)}
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Network error reaching Supabase: {exc}")


@app.get("/api/resources/{resource_id}/assets/{asset_type}")
async def get_resource_assets_by_type(
    resource_id: str,
    asset_type: str,
    _user: dict = Depends(get_current_user),
):
    """
    List visual assets of a specific type for a resource
    (e.g. /api/resources/{id}/assets/graph).
    """
    headers = _supabase_headers()
    endpoint = (
        f"{SUPABASE_URL}/rest/v1/resource_assets"
        f"?resource_id=eq.{resource_id}&asset_type=eq.{asset_type}"
        f"&select=id,page_number,asset_type,storage_url,mime_type,width,height,"
        f"bounding_box,caption,linked_question_id,content_verified,metadata,created_at"
        f"&order=page_number.asc"
    )
    try:
        resp = requests.get(endpoint, headers=headers, timeout=15)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Supabase query failed ({resp.status_code}): {resp.text[:200]}",
            )
        assets = resp.json()
        return {
            "resource_id": resource_id,
            "asset_type": asset_type,
            "assets": assets,
            "count": len(assets),
        }
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Network error reaching Supabase: {exc}")

# -------------------------------------------------------------------
# Hybrid Retrieval Endpoints (Session 2 — Hybrid Retrieval Foundation)
# -------------------------------------------------------------------

# Embedding model constants (must match pipeline/embedding_pipeline.py)
EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"
EMBED_DIM = 1024


def _embed_query(text: str) -> list[float]:
    """Embed a natural-language query via NVIDIA NV-EmbedQA-E5-V5."""
    if not nvidia_client:
        raise HTTPException(status_code=500, detail="NVIDIA API is not configured.")
    resp = nvidia_client.embeddings.create(
        model=EMBED_MODEL,
        input=text,
        encoding_format="float",
        extra_body={"input_type": "query", "truncate": "END"},
    )
    return resp.data[0].embedding


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
    # Relational filters
    spec_point_id: Optional[str] = None
    chunk_type: Optional[str] = None


@app.post("/api/search")
async def semantic_search(
    request: SearchRequest,
    _user: dict = Depends(get_current_user),
):
    """
    Pure vector (semantic) search over resource_chunks.

    Embeds the query via NVIDIA NV-EmbedQA-E5-V5 and calls the
    `match_resource_chunks` Postgres RPC function for cosine
    similarity ranking.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query is required.")
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured.")

    # 1. Embed query
    query_vec = _embed_query(request.query)
    vec_str = _vector_to_pg_str(query_vec)

    # 2. Call RPC function
    headers = _supabase_headers()
    rpc_body = {
        "query_embedding": vec_str,
        "match_count": request.match_count,
    }
    if request.filter_resource_id:
        rpc_body["filter_resource_id"] = request.filter_resource_id

    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/match_resource_chunks",
            headers=headers,
            json=rpc_body,
            timeout=15,
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Vector search RPC failed ({resp.status_code}): {resp.text[:200]}",
            )
        results = resp.json()
        return {
            "query": request.query,
            "results": results,
            "count": len(results),
            "search_type": "semantic",
        }
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Network error reaching Supabase: {exc}")


@app.post("/api/search/hybrid")
async def hybrid_search(
    request: HybridSearchRequest,
    _user: dict = Depends(get_current_user),
):
    """
    Combined relational + vector (semantic) search.

    Runs both:
      - Relational: filter resources by spec_point_id and/or chunk_type
        via PostgREST on the resources / resource_chunks tables
      - Vector: pgvector cosine similarity via match_resource_chunks RPC

    Merges results, deduplicating by chunk id and keeping the higher
    similarity score. Vector results that also appear in the relational
    results get a relevance boost.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query is required.")
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured.")

    headers = _supabase_headers()

    # --- 1. Vector search ---
    query_vec = _embed_query(request.query)
    vec_str = _vector_to_pg_str(query_vec)

    rpc_body = {
        "query_embedding": vec_str,
        "match_count": request.match_count * 2,  # fetch more for merging
    }
    if request.resource_id:
        rpc_body["filter_resource_id"] = request.resource_id

    try:
        rpc_resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/match_resource_chunks",
            headers=headers,
            json=rpc_body,
            timeout=15,
        )
        if rpc_resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Vector search RPC failed ({rpc_resp.status_code}): {rpc_resp.text[:200]}",
            )
        vector_results = rpc_resp.json()
        if request.chunk_type:
            # The existing RPC supports resource scoping but not chunk type;
            # enforce the UI's selected type before merging vector results.
            vector_results = [
                result for result in vector_results
                if result.get("chunk_type") == request.chunk_type
            ]
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Network error reaching Supabase (vector): {exc}")

    # --- 2. Relational search (optional filters) ---
    relational_results: list[dict] = []

    # If we have a chunk_type filter, fetch matching chunks relationally.
    # Apply resource scope here too; otherwise the UI filter is silently
    # ignored for the normal worksheet-scoped search.
    if request.chunk_type:
        try:
            rel_params = {
                "chunk_type": f"eq.{request.chunk_type}",
                "select": "id,resource_id,chunk_index,chunk_text,chunk_type,source_refs,token_count",
                "limit": str(request.match_count * 2),
            }
            if request.resource_id:
                rel_params["resource_id"] = f"eq.{request.resource_id}"
            rel_resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/resource_chunks",
                headers=headers,
                params=rel_params,
                timeout=15,
            )
            if rel_resp.status_code == 200:
                relational_results = rel_resp.json()
        except requests.RequestException:
            pass  # non-fatal — vector results still usable

    # If we have spec_point_id, fetch resources by spec_point and their chunks
    if request.spec_point_id:
        try:
            res_endpoint = (
                f"{SUPABASE_URL}/rest/v1/resources"
                f"?specification_point_id=eq.{request.spec_point_id}"
                f"&select=id"
            )
            res_resp = requests.get(res_endpoint, headers=headers, timeout=15)
            if res_resp.status_code == 200 and res_resp.json():
                res_ids = [r["id"] for r in res_resp.json()]
                # Fetch chunks for these resources
                if res_ids:
                    id_filter = ",".join(res_ids)
                    chunk_endpoint = (
                        f"{SUPABASE_URL}/rest/v1/resource_chunks"
                        f"?resource_id=in.({id_filter})"
                        + (f"&chunk_type=eq.{request.chunk_type}" if request.chunk_type else "")
                        + f"&select=id,resource_id,chunk_index,chunk_text,chunk_type,source_refs,token_count"
                        + f"&limit={request.match_count * 2}"
                    )
                    chunk_resp = requests.get(chunk_endpoint, headers=headers, timeout=15)
                    if chunk_resp.status_code == 200:
                        # Tag these as relational-only matches (no similarity score yet)
                        for c in chunk_resp.json():
                            c["similarity"] = None  # no vector score
                        relational_results.extend(chunk_resp.json())
        except requests.RequestException:
            pass

    # --- 3. Merge & deduplicate ---
    merged: dict[str, dict] = {}

    # Add vector results first (they have similarity scores)
    for r in vector_results:
        chunk_id = r.get("id")
        if chunk_id:
            r["source"] = "vector"
            r["boosted"] = False
            merged[chunk_id] = r

    # Add relational results, boosting existing entries
    for r in relational_results:
        chunk_id = r.get("id")
        if chunk_id in merged:
            # Already in vector results — boost it
            existing = merged[chunk_id]
            if existing.get("similarity") is not None:
                existing["similarity"] = min(1.0, existing["similarity"] + 0.1)
            existing["boosted"] = True
            existing["source"] = "both"
        else:
            r["source"] = "relational"
            r["boosted"] = False
            r["similarity"] = 0.0  # relational-only, no vector score
            merged[chunk_id] = r

    # Sort: boosted first, then by similarity descending
    final = sorted(
        merged.values(),
        key=lambda x: (x.get("boosted", False), x.get("similarity") or 0),
        reverse=True,
    )
    final = final[:request.match_count]

    return {
        "query": request.query,
        "results": final,
        "count": len(final),
        "search_type": "hybrid",
        "vector_count": len(vector_results),
        "relational_count": len(relational_results),
    }


@app.get("/api/question")
async def get_question(
    resource_id: Optional[str] = None,
    _user: dict = Depends(get_current_user),
):
    # This simulates fetching a question and its examiner report hint from OpenKB
    # based on the resource_id.
    return {
        "question_index": 1,
        "question_text": "A car accelerates uniformly from rest to 20 m/s in 5 seconds. Calculate the acceleration of the car. Show your working. $a = \\frac{\\Delta v}{\\Delta t}$",
        "max_score": 3,
        "examiner_hint": "**Examiner Report Highlight:** Many students forget that 'from rest' implies an initial velocity ($u$) of 0 m/s. Ensure you state the formula clearly before substituting values. Remember $a = \\frac{v - u}{t}$."
    }

@app.post("/api/grade", response_model=GradeResponse)
async def grade_endpoint(
    request: GradeRequest,
    _user: dict = Depends(get_current_user),
):
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
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # Try OpenCode Zen first, fall back to NVIDIA
    def _parse_grade_reply(reply: str) -> GradeResponse:
        try:
            parsed_json = json.loads(reply)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', reply, re.DOTALL)
            if match:
                parsed_json = json.loads(match.group(0))
            else:
                raise ValueError("Could not extract JSON from LLM response.")
        return GradeResponse(
            marks_awarded=parsed_json.get("marks_awarded", 0),
            total_marks=request.max_score,
            explanation=parsed_json.get("explanation", "No explanation provided.")
        )

    if opencode_zen_client:
        try:
            response = opencode_zen_client.chat.completions.create(
                model="deepseek-v4-flash-free",
                messages=messages,
                temperature=0.1,
                max_tokens=2048,
            )
            reply = response.choices[0].message.content
            return _parse_grade_reply(reply)
        except Exception as e:
            print(f"OpenCode Zen grading failed, falling back to NVIDIA: {e}")

    if nvidia_client:
        try:
            response = nvidia_client.chat.completions.create(
                model="nvidia/nemotron-3-super-120b-a12b",
                messages=messages,
                temperature=0.1,
                max_tokens=2048,
            )
            reply = response.choices[0].message.content
            return _parse_grade_reply(reply)
        except Exception as e:
            print(f"NVIDIA grading also failed: {e}")

    raise HTTPException(status_code=500, detail="All grading providers failed.")
