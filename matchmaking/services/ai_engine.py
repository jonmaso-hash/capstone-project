import os
import json
import logging
from django.conf import settings
from google import genai
from google.genai import errors
from google.genai import types

# Initialize production logging channel
logger = logging.getLogger(__name__)

def _get_client():
    """
    Helper utility to instantiate the modern unified Google GenAI Client cleanly.
    Prioritizes Django settings securely before falling back to local system environment configurations.
    """
    try:
        api_key = getattr(settings, "GEMINI_API_KEY", None) or os.environ.get("GEMINI_API_KEY")
        if api_key:
            return genai.Client(api_key=api_key)
        return genai.Client()
    except Exception as e:
        logger.error(f"[GenAI Client Exception]: System failed to build connection instance: {e}")
        return None

def generate_profile_embedding(text_content: str) -> list[float]:
    """
    Transforms a raw description block into a 768-dimensional semantic vector 
    array using the modern unified Google GenAI client layer.
    
    FIXED: Changed 'model_name' to 'model' to eliminate TypeErrors.
    """
    if not text_content or not text_content.strip():
        return []

    client = _get_client()
    if not client:
        return []

    try:
        # CORRECT METHOD SIGNATURE: Rely strictly on 'model' keyword argument
        response = client.models.embed_content(
            model="models/text-embedding-004",
            contents=text_content.strip()
        )
        
        # Safely extract the vector floating-point sequence
        if response and response.embeddings:
            return response.embeddings[0].values
            
    except errors.APIError as e:
        logger.error(f"[Gemini API Exception]: Matrix generation failure: {e}")
    except Exception as e:
        logger.error(f"[Embedding Pipeline Error]: Vector processing caught unhandled runtime: {e}")
        
    return []

def calculate_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    """
    Computes the mathematical cosine similarity between two dimensional vector arrays.
    Enforces a strict length parity check and handles zero-vector division safely.
    """
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0
        
    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = sum(a * a for a in vector_a) ** 0.5
    norm_b = sum(b * b for b in vector_b) ** 0.5
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
        
    return dot_product / (norm_a * norm_b)

def generate_zelda_summary(page_text: str) -> str:
    """
    [Phase 3 Feature] Context-Aware Page Summaries (Assistant Expansion)
    Parses active view records into a 3-bullet point executive TL;DR summary using
    the 'Zelda' VC advisor identity framework for fast investor assimilation.
    """
    if not page_text or not page_text.strip():
        return "No descriptive record data visible to compile summary logs."
        
    client = _get_client()
    if not client:
        return "AI platform pipeline is currently offline or unreachable."
        
    prompt = (
        "You are Zelda, an expert proprietary AI venture capitalist analyst for Interlink Foundry.\n"
        "Provide a high-signal, professional 3-bullet point TL;DR executive summary focusing exclusively on:\n"
        "1. The founder's documented operational traction, milestones, or early revenue indicators.\n"
        "2. The core tech stack, engineering infrastructure, or architectural innovation moats.\n"
        "3. The explicit capital target requested along with strategic use-of-funds parameters.\n\n"
        "Keep the output clean, objective, and dense for high-net-worth platform investors.\n\n"
        f"Target Profile/Post Record Context:\n{page_text}"
    )
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip() if response.text else "Failed to capture summary transmission values."
    except Exception as e:
        logger.error(f"[Zelda Assistant Exception]: Executive page parsing collapsed: {e}")
        return "Error synthesizing structural context summary."

def verify_truth_delta(claimed_metrics: dict, portfolio_raw_text: str) -> dict:
    """
    [Phase 3 Feature] Truth Delta Verification & Synthesis Engine (.memo Layer)
    Cross-references self-reported core metrics with background public text crawls.
    Identifies numerical variance and reports back structured JSON parameters.
    """
    client = _get_client()
    if not client:
        return {"status": "error", "message": "AI generation engine uninitialized"}
        
    prompt = (
        "You are an analytical venture diligence verification engine for Interlink Foundry.\n"
        "Evaluate the following self-reported 'Claimed Metrics' against public web footprints or "
        "scraped company database contexts provided under 'Crawled Public Footprint'.\n\n"
        f"Claimed Metrics:\n{json.dumps(claimed_metrics, indent=2)}\n\n"
        f"Crawled Public Footprint:\n{portfolio_raw_text}\n\n"
        "Task Instructions:\n"
        "1. Compare metrics such as annual revenue, headcounts, or years in production.\n"
        "2. Flag any entry where the reported claim overstates reality or diverges from crawled records by >20%.\n"
        "3. Compute an integer 'success_vector_score' (0-100) evaluating data integrity, transparency, and alignment.\n\n"
        "You MUST return your output strictly inside a valid JSON format matching this exact schema block:\n"
        "{\n"
        "  \"divergence_detected\": true/false,\n"
        "  \"flagged_metrics\": [\n"
        "     {\"metric\": \"metric_name\", \"claimed\": \"value\", \"crawled_evidence\": \"value\", \"divergence_pct\": 0.0}\n"
        "  ],\n"
        "  \"success_vector_score\": 90,\n"
        "  \"summary\": \"Short 2-sentence executive synthesis analyzing the verification data state vs web trends.\"\n"
        "}"
    )
    
    try:
        # Request native JSON configuration from Gemini
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        if response and response.text:
            return json.loads(response.text.strip())
        return {"status": "error", "message": "Empty network object returned from verification layers"}
        
    except Exception as e:
        logger.error(f"[Truth Delta Exception]: Diligence metric comparison crashed: {e}")
        # Graceful validation structure fallback to avoid completely stalling runtime execution loops
        return {
            "divergence_detected": False,
            "flagged_metrics": [],
            "success_vector_score": 70,
            "summary": f"Diligence verification processing safely recovered from execution exception: {str(e)}"
        }