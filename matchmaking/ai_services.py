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
        # Client automatically reads the GEMINI_API_KEY environment variable
        client = genai.Client()
        
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
                temperature=0.1,  # Lower values keep the extraction factual and grounded
            ),
        )
        
        # Clean up the file storage object from Google's temporary servers immediately after execution
        client.files.delete(name=uploaded_file.name)
        
        # Return cleanly parsed JSON output data matching our Pydantic schema
        return json.loads(response.text)
        
    except Exception as e:
        logger.error(f"Failed to extract payload insights from Gemini API: {str(e)}")
        return None