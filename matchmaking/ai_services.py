# matchmaking/ai_services.py
import json
import logging
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 1. Enforce a strict schema structure using Pydantic
class ExtractedStartupProfile(BaseModel):
    sector: str = Field(description="Primary sector classification. Must be exactly one of: SaaS, FinTech, AI/ML, HealthTech, Marketplace, Hardware, Web3.")
    stage: str = Field(description="Estimated current fundraising round (Pre-seed, Seed, Series A, Growth).")
    one_liner: str = Field(description="A clean, concise 1-sentence explanation of what the company does.")
    problem_solved: str = Field(description="A concise summary of the core friction or market problem they are addressing.")

def analyze_pitch_deck(file_path):
    """
    Ingests a pitch deck file path, uploads it securely to the Gemini File Engine,
    extracts target structural parameters using schema constraints, and purges the file.
    """
    try:
        client = genai.Client()  # Automatically defaults to stable v1 pathways
        
        # REMOVED: Redundant text-embedding-004 test block that was overwriting response
        
        # Upload the presentation document safely via the Files Engine
        logger.info(f"Uploading document to Gemini File Engine: {file_path}")
        uploaded_file = client.files.upload(file=file_path)
        
        # Prompt the model using a highly reliable, cost-efficient variant
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                uploaded_file,
                "Analyze this investment material and accurately populate the structural parameters."
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExtractedStartupProfile,
                temperature=0.1,
            ),
        )
        
        # Clean up the file storage object from Google's temporary servers immediately
        client.files.delete(name=uploaded_file.name)
        
        return json.loads(response.text)
        
    except Exception as e:
        logger.error(f"Failed to extract payload insights from Gemini API: {str(e)}")
        return None
    
def ai_search_endpoint(request):
    if request.method == "POST":
        user_prompt = request.POST.get('prompt', '')
        
        # 1. Retrieval Layer (Your existing functions)
        vector_context = get_vector_embeddings_context(user_prompt) 
        user_database_context = extract_and_enrich_usernames(user_prompt)
        
        # 2. Generative Layer
        client = genai.Client()
        
        system_instructions = (
            "You are Zelda, the Interlink Foundry assistant. Match founders/investors. "
            "Use the provided vector context and database context to answer the user's prompt. "
            "If a user asks for a profile, always provide the link in this format: "
            "[@username](/accounts/profile/username/)."
        )
        
        final_context_feed = f"{system_instructions}\n\nContext:\n{vector_context}\n{user_database_context}\n\nUser Query: {user_prompt}"
        
        try:
            # Use the model confirmed in your diagnostic list
            response = client.models.generate_content(
                model="models/gemini-2.0-flash", 
                contents=final_context_feed
            )
            
            # Parsing logic: Zelda returns the generated text and the links
            return JsonResponse({'response': response.text})
            
        except Exception as e:
            logger.error(f"Zelda Generative Search Error: {e}")
            return JsonResponse({'response': "I am currently calibrating my search vectors. Please try again."}, status=500)