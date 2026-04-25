import os
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
from google.genai import types

# 1. Load Environment Variables
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_KEY:
    SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Initialize Clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

def process_and_upload_worksheet(pdf_path: str, resource_id: str):
    print(f"Uploading '{pdf_path}' to Gemini...")
    
    # 2. Upload the PDF to Gemini's File API
    gemini_file = ai_client.files.upload(file=pdf_path)
    
    print("Analysing worksheet and generating mark scheme. This may take a few seconds...")
    
    # 3. The Engineered Prompt
    system_instruction = """
    You are an expert Edexcel IGCSE Physics Teacher and a precise data extraction assistant. 
    Your task is to analyze the provided images of a physics worksheet and extract all questions, generating a complete, step-by-step mark scheme for each.

    Follow these strict guidelines to format your output:

    1. **Structure:** For every single question and sub-question (a, b, c), use the exact following Markdown structure:

       ### Question [Number][Part]
       **Question:** [Extract the exact text from the worksheet]
       **Data:** [If the question contains a table, reproduce it perfectly using a Markdown table. If no table, omit this section.]
       **Step-by-Step Solution:** [Generate a clear, logical progression of steps to solve the problem, exactly as you would teach a student. Explicitly state the formula used.]
       **Final Answer:** [The final numerical answer with correct units, or the concise text answer].

    2. **LaTeX Formatting:** You MUST use standard LaTeX formatting for ALL units, variables, and equations. Enclose inline math in single `$` and display math in double `$$`. Ensure there are no spaces between the `$` and the math. 
       - Good examples: $m/s^{2}$, $v^{2}=u^{2}+2as$, $1500\text{ m}$.

    3. **Graph Analysis:** If a question requires reading a graph, carefully analyze the visual data to extract the necessary coordinates. Briefly explain how you used the graph in your solution.

    4. **Completeness:** Do not skip any questions. If a question asks for a definition or reasoning, provide the standard Edexcel accepted answer.
    """
    
    # 4. Generate the Content
    response = ai_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[gemini_file, "Please extract the questions from this worksheet and generate the mark scheme."],
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.1, 
        )
    )
    
    markdown_content = response.text
    print("Extraction complete! Pushing to Supabase...")
    
    # 5. Update the Database
    result = supabase.table('resources').update(
        {'content': markdown_content}
    ).eq('id', resource_id).execute()
    
    print("Success! Your VLE dashboard has been updated with the new content.")

if __name__ == "__main__":
    # Ensure the PDF is accessible to the script
    FILE_NAME = "IGCSE_Physics_Worksheet 1_Movement and Position.pdf" 
    TARGET_ID = "5729d034-a6c7-4f35-b81c-fcac447289c7"
    
    process_and_upload_worksheet(FILE_NAME, TARGET_ID)
