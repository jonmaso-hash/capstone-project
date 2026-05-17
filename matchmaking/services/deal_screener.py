import os
from google import genai
from google.genai import types
from django.conf import settings
from matchmaking.models import Application

def get_gemini_client():
    """Initializes the official standard Google GenAI Client wrapper."""
    return genai.Client(api_key=settings.GEMINI_API_KEY)

def index_founder_pitch_deck(application_id: int):
    """
    Spins up a unique managed Gemini File Search store container, 
    uploads the raw layout (PDF/charts), and computes multimodal vectors.
    """
    client = get_gemini_client()
    application = Application.objects.get(id=application_id)
    
    if not application.pitch_deck:
        return None

    # 1. Create a dedicated container for this startup's multimodal files
    store_name = f"store-founder-{application.id}"
    file_search_store = client.file_search_stores.create(
        config={
            'display_name': store_name,
            'embedding_model': 'models/gemini-embedding-2' # Forces cross-modal processing
        }
    )
    
    # Save the store references on our local Django DB row record
    application.file_search_store_id = file_search_store.name
    application.save()

    # 2. Upload file straight into the managed workspace pipeline
    absolute_file_path = application.pitch_deck.path
    
    # upload_to_file_search_store automatically handles chunking and vector indexing
    client.file_search_stores.upload_to_file_search_store(
        file_search_store_name=file_search_store.name,
        file=absolute_file_path
    )
    
    return file_search_store.name

def analyze_deck_against_investor(application: Application, investor_focus_thesis: str) -> dict:
    """
    Queries the multi-modal document store using the investor's focus parameters 
    and returns an automated analysis with absolute citation alignment.
    """
    if not application.file_search_store_id:
        return {"eligible": False, "score": 0, "rationale": "No pitch deck file indexed."}

    client = get_gemini_client()
    
    prompt = (
        f"You are an expert deal-screening analyst at an elite venture studio. "
        f"Analyze this company pitch deck against the following investment thesis:\n"
        f"INVESTOR THESIS: \"{investor_focus_thesis}\"\n\n"
        f"Evaluate the fit. Provide your evaluation in the following strict JSON format:\n"
        f"{{\n"
        f"  \"score\": <integer score from 0 to 100>,\n"
        f"  \"eligible\": <true or false>,\n"
        f"  \"key_findings\": \"Summarize structural highlights or risks found across the deck visual graphics and text pages.\"\n"
        f"}}"
    )

    try:
        # Request context-grounded analysis using the file_search tool mechanism
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[application.file_search_store_id]
                        )
                    )
                ]
            )
        )
        
        # Safe structural type evaluation
        import json
        return json.loads(response.text)
        
    except Exception as e:
        return {
            "eligible": False, 
            "score": 50, 
            "rationale": f"Automated screen process error occurred: {str(e)}"
        }