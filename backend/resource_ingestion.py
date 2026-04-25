import os
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 1. Load Environment Variables
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Initialize Gemini Client
ai_client = genai.Client(api_key=GEMINI_API_KEY)

def process_and_upload_worksheet(pdf_path: str, resource_id: str):
    print(f"Uploading '{pdf_path}' to Gemini...")
    
    # 2. Upload the PDF to Gemini's File API
    gemini_file = ai_client.files.upload(file=pdf_path)
    
    print("Analysing worksheet and generating mark scheme via Gemini 2.0 Flash...")
    
    # 3. The Engineered Prompt
    system_instruction = """
    You are an expert Edexcel IGCSE Physics Teacher. Analyze the worksheet and extract all questions.
    For each question, provide:
    ### Question [Number]
    **Question:** [Text]
    **Step-by-Step Solution:** [Detailed explanation]
    **Final Answer:** [Answer with LaTeX units like $m/s^{2}$]
    """
    
    # 4. Generate the Content
    response = ai_client.models.generate_content(
        model='gemini-2.0-flash',
        contents=[gemini_file, "Extract questions and generate mark scheme."],
        config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.1)
    )
    
    markdown_content = response.text
    print("Extraction complete! Pushing to Supabase via REST API...")
    
    # 5. Update via REST API (Bypassing the official client library)
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    endpoint = f"{SUPABASE_URL}/rest/v1/resources?id=eq.{resource_id}"
    db_response = requests.patch(endpoint, headers=headers, json={"content": markdown_content})
    
    if db_response.status_code in [200, 204]:
        print("\n🎉 Success! VLE dashboard updated. Refresh your browser to see the content.")
    else:
        print(f"\n❌ Error: {db_response.status_code}\n{db_response.text}")

if __name__ == "__main__":
    # Ensure this matches the PDF path in your backend folder
    FILE_NAME = "IGCSE_Physics_Worksheet 1_Movement and Position.pdf"
    TARGET_ID = "5729d034-a6c7-4f35-b81c-fcac447289c7"
    process_and_upload_worksheet(FILE_NAME, TARGET_ID)
