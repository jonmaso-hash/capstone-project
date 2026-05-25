import os
import logging
import pdfplumber
from pptx import Presentation
from .protocol import FoundryStandardMixin

logger = logging.getLogger(__name__)

def scan_pitch_deck(file_path):
    """
    Extracts text from either a PDF or a PPTX/PPTM file layout.
    """
    extracted_text = []
    
    # Extract filename from path string or file object
    filename = getattr(file_path, 'name', str(file_path)).lower()
    
    try:
        # Handle PowerPoint format
        if filename.endswith('.pptx') or filename.endswith('.pptm'):
            prs = Presentation(file_path)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        extracted_text.append(shape.text.strip())
                        
        # Handle PDF format
        else:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text.append(text)
        
        full_text = "\n".join(extracted_text)
        
        return {
            "summary": full_text[:500] if full_text else "No text extracted from presentation layout.",
            "revenue_metrics": "Pending LLM Analysis", 
            "market_size": "Pending LLM Analysis",
            "parsed_at": None,
            "score": 0.0
        }
        
    except Exception as e:
        logger.error(f"Failed to scan file {filename}: {e}")
        return {"error": f"Extraction failed: {str(e)}"}

class AnalyzedPitch(FoundryStandardMixin):
    source_name = "pitch_deck_scanner"

    def __init__(self, raw_data):
        self.raw_data = raw_data
        self.updated_at = raw_data.get('parsed_at')
        self.zelda_score = raw_data.get('score', 0.0)

    def get_serialized_data(self):
        return {
            "summary": self.raw_data.get("summary"),
            "revenue": self.raw_data.get("revenue_metrics"),
            "market": self.raw_data.get("market_size")
        }

    def get_essential_summary(self):
        summary = self.raw_data.get("summary", "")
        return {
            "summary": (summary[:97] + "...") if len(summary) > 100 else summary
        }