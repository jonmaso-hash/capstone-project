import os
import json
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from django.conf import settings
from matchmaking.models import Application, InvestorApplication

# Helper schema to represent granular matching evaluations for template rendering
class MatchPillar(BaseModel):
    title: str = Field(description="The matching metric name (e.g., 'Years in Business', 'Revenue Tier', 'Location Limit').")
    score: str = Field(description="The alignment assessment label. Strictly use 'Excellent', 'Match', 'Passed', or 'Mismatched'.")

# Explicit validation schemas for the venture screening engine
class ScreeningAnalysisSchema(BaseModel):
    score: int = Field(description="Integer score from 0 to 100 assessing complete hybrid/structural alignment.")
    eligible: bool = Field(description="True if company operational parameters match effectively to investor bounds, False otherwise.")
    pillars: list[MatchPillar] = Field(default=[], description="Array of calculated match pillars evaluating specific metrics against investor preferences.")
    key_findings: str = Field(description="Detailed summary of investment highlights, financial anomalies, or asset risks found across text, metrics, or visual assets.")

def get_gemini_client():
    """Initializes the official standard Google GenAI Client wrapper."""
    if not getattr(settings, 'GEMINI_API_KEY', None):
        raise ValueError("CRITICAL: GEMINI_API_KEY is missing from platform settings module configuration.")
    return genai.Client(api_key=settings.GEMINI_API_KEY)

def index_founder_pitch_deck(application_id: int) -> str | None:
    """
    Uploads the pitch deck asset to the managed Gemini File service API infrastructure,
    allowing context-grounded retrieval matching.
    """
    try:
        application = Application.objects.get(id=application_id)
    except Application.DoesNotExist:
        print(f"[Error] Application instance {application_id} missing from database context mapping.")
        return None
    
    if not application.pitch_deck:
        print(f"[Warning] Application {application_id} omitted file pitch deck target parameters.")
        return None

    client = get_gemini_client()
    absolute_file_path = application.pitch_deck.path

    if not os.path.exists(absolute_file_path):
        print(f"[Error] Physical pitch asset path not found on server disk array: {absolute_file_path}")
        return None

    try:
        # Uploading asset cleanly via official file service pipelines
        print(f"Uploading asset to remote Gemini processing store for application {application_id}...")
        uploaded_file = client.files.upload(
            file=absolute_file_path,
            config=types.UploadFileConfig(
                display_name=f"pitch-deck-app-{application.id}"
            )
        )
        
        # Save unique resource locator handle on local record model
        application.file_search_store_id = uploaded_file.name
        application.save()
        
        print(f"File search array initialized cleanly. Remote ID registered: {uploaded_file.name}")
        return uploaded_file.name

    except Exception as e:
        print(f"[Exception Failure] Error processing remote data ingestion stack: {str(e)}")
        return None

def analyze_deck_against_investor(application: Application, investor: InvestorApplication) -> dict:
    """
    Queries the multi-modal document profile using the investor's structural parameters and focus thesis.
    Injects precise operational metrics to return an automated analytical breakdown with absolute schema compliance.
    """
    if not application.file_search_store_id:
        return {
            "eligible": False, 
            "score": 0, 
            "pillars": [],
            "key_findings": "No pitch deck file indexed on remote file search stores for this startup record instance."
        }

    client = get_gemini_client()
    
    # Retrieve file state metrics to ensure availability
    try:
        remote_file_ref = client.files.get(name=application.file_search_store_id)
    except Exception as e:
        return {
            "eligible": False,
            "score": 0,
            "pillars": [],
            "key_findings": f"Could not pull matching remote asset index reference parameters: {str(e)}"
        }

    # Construct complete structural multi-metric prompt segment
    prompt = (
        f"You are an expert deal-screening analyst at an elite venture studio specializing in advanced market matching.\n"
        f"Analyze the attached company pitch deck asset thoroughly. Evaluate the fit against the following investment criterion, "
        f"weighting both the qualitative thesis and the structured database properties provided below.\n\n"
        f"INVESTOR MANDATE PROFILE:\n"
        f"- Target Thesis: \"{investor.investment_focus}\"\n"
        f"- Mandate Stage: {investor.investment_stage}\n"
        f"- Location Radius Restriction Limit: {investor.target_distance_range} (Investor Hub Location: {investor.location or 'Global'})\n\n"
        f"FOUNDER COMPANY METRICS (GROUND TRUTH):\n"
        f"- Company Name: {application.company_name}\n"
        f"- Operating Location: {application.location or 'Not Specified'}\n"
        f"- Years in Business: {application.years_in_business or 'Not Specified'}\n"
        f"- Company Size: {application.company_size or 'Not Specified'}\n"
        f"- Current Revenue / ARR Tier: {application.current_revenue or '0'}\n"
        f"- Prior Amount Raised: {application.prior_amount_raised or '0'}\n"
        f"- Target Raising Goal: {application.raising_amount or 'Not Specified'}\n\n"
        f"EVALUATION CRITERIA INSTRUCTIONS:\n"
        f"1. Compare Founder Operating Location against Investor Location Hub and Target Distance Range (e.g., if range is Local/Regional, flag proximity issues).\n"
        f"2. Audit if Company Size, Years in Business, and Revenue Tier are aligned with the Investor's target fund stage deployment mechanics.\n"
        f"3. Generate a Pydantic 'MatchPillar' entry for key criteria (Years in Business, Company Size, Revenue Tier, Location Fit, Thesis Fit) evaluating alignment.\n"
        f"4. Provide your final aggregate score (0-100), eligibility ruling, and an analytical narrative summary under 'key_findings'."
    )

    try:
        # Execute query passing the file handle inline for modern grounding processing
        response = client.models.generate_content(
            model="gemini-3-flash",
            contents=[remote_file_ref, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ScreeningAnalysisSchema,
                temperature=0.1,
            )
        )
        
        # Return cleanly structured response matrix directly
        return json.loads(response.text)
        
    except Exception as e:
        return {
            "eligible": False, 
            "score": 50, 
            "pillars": [],
            "key_findings": f"Automated screen process error occurred during API evaluation context pipeline: {str(e)}"
        }