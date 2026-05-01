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

# Helper: Fetch Resource from Supabase
def fetch_forces_and_motion_data():
    """
    Fetches the JSON OpenKB structure for the "Forces and Motion" resource directly from Supabase.
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

@app.post("/api/tutor")
async def tutor_endpoint(request: TutorRequest):
    if not request.student_prompt:
        raise HTTPException(status_code=400, detail="student_prompt is required.")
        
    route_target = evaluate_routing(request.student_prompt)
    
    # Fetch Context Data (Vertical Slice: Forces and Motion)
    context_data = fetch_forces_and_motion_data()
    system_prompt = (
        "You are an expert, encouraging Edexcel IGCSE and A-Level Physics Tutor.\n"
        "You are an Edexcel IGCSE Physics Examiner. Never ask hybrid coordinate-graphing questions. Questions must be EITHER a pure mathematical calculation OR a conceptual explanation. Do not deviate from official past-paper formats.\n"
        "You guide students using Socratic questioning and never give the final answer immediately.\n"
        "Format mathematical explanations cleanly.\n"
        "The UI has 4 tabs: Lesson, Worksheet, Simulation, and Quiz. If a student asks to view a resource, take a quiz, or use a simulation, you must append a navigation tag to the end of your response in the exact format: [SWITCH_TAB: TabName] (e.g., [SWITCH_TAB: Quiz])."
    )
    
    if context_data:
        system_prompt += f"\n\nContext (Forces and Motion Knowledge Graph):\n{context_data}\n"
    
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
            return {"response": reply, "model_used": "NVIDIA_LLAMA_3.3"}
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
            
            return {"response": result.text, "model_used": "GEMINI_FLASH"}
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gemini API Error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "OK", "message": "FastAPI Backend is running"}

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
        "You are a Rigorous Edexcel Examiner marking a physics test.\n"
        "You MUST respond ONLY with a strict JSON object containing three keys: 'marks_awarded' (integer), 'total_marks' (integer), and 'explanation' (string).\n"
        "Your grading logic must strictly follow the Mark Scheme provided in the Context.\n"
        "If the student's answer includes coordinates from a GraphDraw canvas (e.g., a JSON array of points), evaluate the general trend and intercepts of the coordinates rather than demanding exact pixel-perfection.\n"
        "Do not include any other markdown text, code blocks, or greetings."
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
