import os
import base64
import PyPDF2
import requests
from pdf2image import convert_from_path
from openai import OpenAI
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

client = OpenAI(
  base_url="https://integrate.api.nvidia.com/v1",
  api_key=NVIDIA_API_KEY
)

def has_images(pdf_path):
    print(f"Scouting {pdf_path} for visual elements...")
    try:
        reader = PyPDF2.PdfReader(pdf_path)
        for page in reader.pages:
            if '/Resources' in page and '/XObject' in page['/Resources']:
                x_objects = page['/Resources']['/XObject'].get_object()
                for obj in x_objects:
                    if x_objects[obj]['/Subtype'] == '/Image':
                        return True
        return False
    except Exception as e:
        print(f"Scout error, defaulting to Vision: {e}")
        return True

def extract_text_fast(pdf_path):
    print("Pure text detected. Extracting fast text...")
    text = ""
    reader = PyPDF2.PdfReader(pdf_path)
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def extract_markdown_with_vision(pdf_path):
    print("Images detected! Converting to Base64 and triggering Vision Model...")
    poppler_bin = os.path.join(os.environ.get("LOCALAPPDATA", ""), "poppler", "poppler-25.07.0", "Library", "bin")
    images = convert_from_path(pdf_path, poppler_path=poppler_bin)
    base64_images = []
    
    for i, image in enumerate(images):
        temp_path = f"temp_page_{i}.jpg"
        image.save(temp_path, "JPEG")
        with open(temp_path, "rb") as img_file:
            base64_images.append(base64.b64encode(img_file.read()).decode("utf-8"))
        os.remove(temp_path)
        
    print(f"Extracting visual physics data via Llama 3.2 90B Vision ({len(base64_images)} pages)...")
    all_markdown = []
    for i, b64_img in enumerate(base64_images):
        print(f"  Processing page {i + 1}/{len(base64_images)}...")
        content_payload = [
            {"type": "text", "text": "Extract all text, physics formulas (in LaTeX), and describe any graphs from this page into clean Markdown."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
        ]
        response = client.chat.completions.create(
            model="meta/llama-3.2-90b-vision-instruct",
            messages=[{"role": "user", "content": content_payload}],
            temperature=0.1,
            max_tokens=2048,
        )
        all_markdown.append(response.choices[0].message.content)
    return "\n\n---\n\n".join(all_markdown)

def compile_openkb(text_content):
    print("Compiling into OpenKB JSON Graph via Nemotron 70B...")
    system_prompt = """
    You are an OpenKB Compiler. Read the content and extract physics concepts into a JSON array of nodes.
    Format: [{"concept": "Name", "definition": "Description", "formula": "LaTeX or null", "related_concepts": ["concept1"]}]
    Output ONLY valid JSON.
    """
    
    response = client.chat.completions.create(
     model="meta/llama-3.3-70b-instruct",
      messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text_content}
      ],
      temperature=0.1,
      max_tokens=2048,
    )
    return response.choices[0].message.content

def push_to_supabase(resource_id, content):
    print(f"Pushing OpenKB data to Supabase (Resource ID: {resource_id})...")
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    endpoint = f"{SUPABASE_URL}/rest/v1/resources?id=eq.{resource_id}"
    payload = {"content": content}
    
    db_response = requests.patch(endpoint, headers=headers, json=payload)
    
    if db_response.status_code in [200, 204]:
        print("\n🎉 Success! Database updated with OpenKB structure.")
    else:
        print(f"\n❌ Error: {db_response.status_code}\n{db_response.text}")

if __name__ == "__main__":
    PDF_FILE = "backend/IGCSE_Physics_Worksheet 1_Movement and Position.pdf"
    TARGET_ID = "5729d034-a6c7-4f35-b81c-fcac447289c7"
    
    try:
        # 1. Smart Triage & Extraction
        if has_images(PDF_FILE):
            content = extract_markdown_with_vision(PDF_FILE)
        else:
            content = extract_text_fast(PDF_FILE)
            
        # 2. OpenKB Compilation
        kb_json = compile_openkb(content)
        
        # 3. Database Injection
        push_to_supabase(TARGET_ID, kb_json)
        
    except Exception as e:
        print(f"Pipeline Error: {e}")
        if "poppler" in str(e).lower():
            print("\nWINDOWS FIX: You need to install Poppler for Windows to convert PDFs to images.")
