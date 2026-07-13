import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# Configure CORS for React frontend
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:5174", "http://localhost:3000", "*"],  # Permissive for dev, lock down in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment Variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")

# Initialize APIs
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

nvidia_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
) if NVIDIA_API_KEY else None

# Pydantic Models for Request Validation
class Message(BaseModel):
    role: str
    content: str

class TutorRequest(BaseModel):
    student_prompt: str
    history: Optional[List[Message]] = []

class TutorSource(BaseModel):
    chunk_id: str
    concept: Optional[str] = None
    page: Optional[int] = None
    chunk_type: str
    similarity: Optional[float] = None

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
TARGET_RESOURCE_ID = "5729d034-a6c7-4f35-b81c-fcac447289c7" # Forces and Motion Resource
TUTOR_CHUNK_COUNT = 5  # top-N chunks to inject as RAG context

# -------------------------------------------------------------------
# RAG Retrieval Helpers (reuse existing _embed_query and _supabase_headers)
# -------------------------------------------------------------------

def _retrieve_relevant_chunks(query: str, match_count: int = TUTOR_CHUNK_COUNT) -> list[dict]:
    """
    Embed the student's question, call match_resource_chunks RPC scoped to
    the Golden Dataset resource, and return ranked chunks for RAG context.
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
            "filter_resource_id": TARGET_RESOURCE_ID,
        }
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/match_resource_chunks",
            headers=headers,
            json=rpc_body,
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[RAG] RPC failed ({resp.status_code}): {resp.text[:120]}")
            return []
        return resp.json()
    except Exception as e:
        print(f"[RAG] Retrieval error (non-fatal): {e}")
        return []


def _format_chunks_as_context(chunks: list[dict]) -> str:
    """Build a compact, citation-rich context block from retrieved chunks."""
    if not chunks:
        return ""
    lines = ["Retrieved educational context (from the Forces and Motion resource):"]
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
        )
        for c in chunks
    ]


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
    Evaluates the prompt to determine whether it should be routed to Gemini Flash or Nvidia Llama 3.3.
    """
    complex_keywords = [
        "grade", "assess", "mark", "calculate", "derive", 
        "evaluate", "worksheet", "forces and motion", 
        "deep", "complex", "reasoning", "why does", "prove",
        "solve"
    ]
    
    prompt_lower = prompt.lower()
    
    # If the prompt is long or contains complex reasoning/grading keywords, route to Nvidia
    if any(keyword in prompt_lower for keyword in complex_keywords) or len(prompt) > 100:
        print("Semantic Router: Routing to NVIDIA (Llama 3.3)")
        return "NVIDIA"
    
    # Otherwise, simple/conversational goes to Gemini
    print("Semantic Router: Routing to GEMINI (Flash 2.5)")
    return "GEMINI"

@app.post("/api/tutor", response_model=TutorResponse)
async def tutor_endpoint(request: TutorRequest):
    if not request.student_prompt:
        raise HTTPException(status_code=400, detail="student_prompt is required.")

    # --- RAG Retrieval ---
    # Replace the old full-JSON dump with targeted hybrid retrieval.
    # Embed the student's question, search resource_chunks scoped to the
    # Golden Dataset resource, and inject only the top-N relevant chunks.
    retrieved_chunks = _retrieve_relevant_chunks(request.student_prompt)
    rag_context = _format_chunks_as_context(retrieved_chunks)
    sources = _chunks_to_sources(retrieved_chunks)

    print(f"[RAG] Retrieved {len(retrieved_chunks)} chunks for tutor context.")

    route_target = evaluate_routing(request.student_prompt)

    # Build system prompt — tutor persona + RAG context (NOT the full JSON)
    system_prompt = (
        "You are an expert, encouraging Edexcel IGCSE and A-Level Physics Tutor.\n"
        "You are an Edexcel IGCSE Physics Examiner. Never ask hybrid coordinate-graphing questions. Questions must be EITHER a pure mathematical calculation OR a conceptual explanation. Do not deviate from official past-paper formats.\n"
        "You guide students using Socratic questioning and never give the final answer immediately.\n"
        "Format mathematical explanations cleanly.\n"
        "The UI has 4 tabs: Lesson, Worksheet, Simulation, and Quiz. If a student asks to view a resource, take a quiz, or use a simulation, you must append a navigation tag to the end of your response in the exact format: [SWITCH_TAB: TabName] (e.g., [SWITCH_TAB: Quiz]).\n"
    )

    if rag_context:
        system_prompt += (
            "\n"
            "When citing a fact from the retrieved context below, reference the source number "
            "in brackets (e.g. [Source 1]).  Do NOT invent or guess page numbers — only use "
            "information explicitly present in the retrieved context.\n"
            "\n"
            + rag_context + "\n"
        )

    if route_target == "NVIDIA":
        # Route to Nvidia Llama 3.3 for complex/grading tasks
        if not nvidia_client:
            raise HTTPException(status_code=500, detail="NVIDIA API is not configured.")

        messages = [{"role": "system", "content": system_prompt}]

        # Add history
        for msg in request.history:
            messages.append({"role": "user" if msg.role == "user" else "assistant", "content": msg.content})

        # Add current message
        messages.append({"role": "user", "content": request.student_prompt})

        try:
            response = nvidia_client.chat.completions.create(
                model="meta/llama-3.3-70b-instruct",
                messages=messages,
                temperature=0.2,
                max_tokens=2048,
            )
            reply = response.choices[0].message.content
            return TutorResponse(response=reply, model_used="NVIDIA_LLAMA_3.3", sources=sources)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Nvidia API Error: {str(e)}")

    else:
        # Route to Gemini Flash for simple/conversational tasks
        if not GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="GEMINI API is not configured.")

        try:
            # Format history for Gemini API
            gemini_history = []
            for msg in request.history:
                # Map role correctly ('user' or 'model')
                role = "user" if msg.role == "user" else "model"
                gemini_history.append({"role": role, "parts": [{"text": msg.content}]})

            # Initialize model with system instruction
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
async def get_resource_assets(resource_id: str):
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
async def get_resource_assets_by_type(resource_id: str, asset_type: str):
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
async def semantic_search(request: SearchRequest):
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
async def hybrid_search(request: HybridSearchRequest):
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
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Network error reaching Supabase (vector): {exc}")

    # --- 2. Relational search (optional filters) ---
    relational_results: list[dict] = []

    # If we have chunk_type filter, fetch matching chunks relationally
    if request.chunk_type and not request.resource_id:
        try:
            rel_endpoint = (
                f"{SUPABASE_URL}/rest/v1/resource_chunks"
                f"?chunk_type=eq.{request.chunk_type}"
                f"&select=id,resource_id,chunk_index,chunk_text,chunk_type,source_refs,token_count"
                f"&limit={request.match_count * 2}"
            )
            rel_resp = requests.get(rel_endpoint, headers=headers, timeout=15)
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
                        f"&select=id,resource_id,chunk_index,chunk_text,chunk_type,source_refs,token_count"
                        f"&limit={request.match_count * 2}"
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
async def get_question(resource_id: Optional[str] = None):
    # This simulates fetching a question and its examiner report hint from OpenKB
    # based on the resource_id.
    return {
        "question_index": 1,
        "question_text": "A car accelerates uniformly from rest to 20 m/s in 5 seconds. Calculate the acceleration of the car. Show your working. $a = \\frac{\\Delta v}{\\Delta t}$",
        "max_score": 3,
        "examiner_hint": "**Examiner Report Highlight:** Many students forget that 'from rest' implies an initial velocity ($u$) of 0 m/s. Ensure you state the formula clearly before substituting values. Remember $a = \\frac{v - u}{t}$."
    }

@app.post("/api/grade", response_model=GradeResponse)
async def grade_endpoint(request: GradeRequest):
    if not nvidia_client:
        raise HTTPException(status_code=500, detail="NVIDIA API is not configured.")
        
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
    
    try:
        response = nvidia_client.chat.completions.create(
            model="meta/llama-3.3-70b-instruct",
            messages=messages,
            temperature=0.1,
            max_tokens=1024,
        )
        reply = response.choices[0].message.content
        
        # Robust parsing for JSON
        # Attempt to parse directly first
        try:
            parsed_json = json.loads(reply)
        except json.JSONDecodeError:
            # Fallback regex if LLM wraps in ```json ... ```
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
        
    except Exception as e:
        print(f"Grading Error: {e}")
        raise HTTPException(status_code=500, detail=f"Grading Engine Error: {str(e)}")
