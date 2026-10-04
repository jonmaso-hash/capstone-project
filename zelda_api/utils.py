# zelda_api/utils.py
"""
Zelda AI Analysis Engine Utilities
Core functions for document parsing, text analysis, and AI memo generation.
"""
import re
import logging
from typing import Dict, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class AnalyzedPitch:

    def __init__(self, summary="", metrics=None, sections=None):

        if isinstance(summary, dict):

            self.summary = summary.get("summary", "")
            self.metrics = summary.get("metrics", {})
            self.sections = summary.get("sections", {})

        else:

            self.summary = summary
            self.metrics = metrics or {}
            self.sections = sections or {}

    def to_foundry_envelope(self):

        return {
            "origin": "pitch_analysis",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {
                "summary": self.summary,
                "metrics": self.metrics,
                "sections": self.sections
            }
        }


def scan_pitch_deck(uploaded_file) -> Dict:
    """
    Parses pitch deck files (PDF, PPTX, TXT) and extracts structured data.
    
    Args:
        uploaded_file: Django UploadedFile object
        
    Returns:
        dict: Extracted text, metrics, and structured data from the pitch
    """
    try:
        # Get file extension
        filename = uploaded_file.name.lower()
        
        # Read file content
        if filename.endswith('.pdf'):
            extracted_text, _page_count = _extract_pdf_text(uploaded_file)
        elif filename.endswith('.pptx'):
            extracted_text, _page_count = _extract_pptx_text(uploaded_file)
        elif filename.endswith('.txt'):
            extracted_text = uploaded_file.read().decode('utf-8')
        else:
            return {"error": "Unsupported file format. Use PDF, PPTX, or TXT."}
        
        extracted_text = strip_page_markers(extracted_text)
        if not extracted_text.strip():
            return {"error": "No readable text found in document."}
        
        # Extract key metrics and sections
        metrics = _extract_metrics(extracted_text)
        sections = _extract_sections(extracted_text)
        
        return {
            "status": "success",
            "summary": extracted_text[:2000],  # First 2000 chars as summary
            "full_text": extracted_text,
            "metrics": metrics,
            "sections": sections,
            "confidence": 0.85
        }
        
    except Exception as e:
        logger.error(f"Pitch deck parsing error: {str(e)}")
        return {"error": "Failed to parse document."}


class ExtractionError(Exception):
    """
    Extraction failed. Never text: before this, a missing parser returned the
    sentence "PPTX parsing requires python-pptx..." AS the document, to be
    chunked and analyzed, and any other failure returned "" with nothing to
    tell it from an image-only deck (Nike baseline L-001).

    reason: 'dependency_missing' -- the server cannot read this type at all
            'unreadable_file'    -- this file could not be opened or parsed
            'unsupported_format' -- not a type Zelda extracts
    """
    REASONS = ('dependency_missing', 'unreadable_file', 'unsupported_format')

    def __init__(self, reason, detail=''):
        assert reason in self.REASONS, reason
        super().__init__(f'{reason}: {detail}' if detail else reason)
        self.reason = reason


# What each failure tells the person who uploaded the file. No exception text.
EXTRACTION_FAILURE_MESSAGES = {
    'dependency_missing': "Zelda can't read this file type right now. Please try again later.",
    'unreadable_file': "Zelda couldn't open this file. It may be damaged or password-protected "
                       "-- please upload it again or export a fresh copy.",
    'unsupported_format': "Zelda can read PDF, PowerPoint (.pptx) and text files.",
}


# Page/slide provenance, decided where it is known: at extraction. Each page
# or slide begins with a reserved marker line naming its REAL number, and the
# chunker splits on these markers instead of guessing boundaries afterwards
# (the old heuristic made "page 4" mean "the fourth thing a regex split off").
# Kept inside the text so extract_text_from_file's (text, pages) contract and
# raw_text_full -- which reprocessing feeds back in -- carry provenance as-is.
# Anything that checks, counts or displays text strips them first.
PAGE_MARKER_RE = re.compile(r'^\[\[zelda:(slide|page) (\d+)\]\]$', re.MULTILINE)


def page_marker(kind, number):
    return f'[[zelda:{kind} {number}]]'


def strip_page_markers(text):
    return PAGE_MARKER_RE.sub('', text or '')


def split_pages(text):
    """
    [(page_number, segment), ...] in document order. Text before the first
    marker, or text with no markers at all, has page_number None: unknown,
    never a number made up from its position.
    """
    text = text or ''
    markers = list(PAGE_MARKER_RE.finditer(text))
    if not markers:
        return [(None, text)]
    segments = []
    if text[:markers[0].start()].strip():
        segments.append((None, text[:markers[0].start()]))
    for i, marker in enumerate(markers):
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        segments.append((int(marker.group(2)), text[marker.end():end]))
    return segments


def _extract_pdf_text(pdf_file):
    """Extract text from PDF files. Returns (text, page_count)."""
    try:
        import PyPDF2
        pdf_file.seek(0)
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for number, page in enumerate(reader.pages, start=1):
            text += page_marker('page', number) + "\n" + (page.extract_text() or '') + "\n"
        return text, len(reader.pages)
    except ImportError:
        logger.error("PyPDF2 is not installed; PDF extraction is unavailable.")
        raise ExtractionError('dependency_missing', 'PyPDF2')
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise ExtractionError('unreadable_file', type(e).__name__) from e


def _extract_pptx_text(pptx_file):
    """Extract text from PowerPoint files. Returns (text, slide_count)."""
    try:
        from pptx import Presentation
        pptx_file.seek(0)
        prs = Presentation(pptx_file)
        text = ""
        for number, slide in enumerate(prs.slides, start=1):
            text += page_marker('slide', number) + "\n"
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += shape.text + "\n"
        return text, len(prs.slides)
    except ImportError:
        logger.error("python-pptx is not installed; PPTX extraction is unavailable.")
        raise ExtractionError('dependency_missing', 'python-pptx')
    except Exception as e:
        logger.error(f"PPTX extraction failed: {e}")
        raise ExtractionError('unreadable_file', type(e).__name__) from e


def _extract_metrics(text: str) -> Dict:
    """
    Extract quantitative metrics from pitch deck text.
    Looks for revenue, funding, growth rates, etc.
    """
    metrics = {
        "revenue": None,
        "users": None,
        "growth_rate": None,
        "team_size": None,
        "funding_raised": None
    }
    
    # Find dollar amounts (revenue, funding)
    dollar_pattern = r'\$[\d.,]+[MK]?'
    dollar_matches = re.findall(dollar_pattern, text)
    if dollar_matches:
        metrics["funding_raised"] = dollar_matches[0]
        if len(dollar_matches) > 1:
            metrics["revenue"] = dollar_matches[1]
    
    # Find growth rates (e.g., "200% growth")
    growth_pattern = r'(\d+)%\s+(?:growth|increase|expansion)'
    growth_match = re.search(growth_pattern, text, re.IGNORECASE)
    if growth_match:
        metrics["growth_rate"] = f"{growth_match.group(1)}%"
    
    # Find user/customer counts
    user_pattern = r'(\d+(?:,\d+)?)\s+(?:users|customers|clients)'
    user_match = re.search(user_pattern, text, re.IGNORECASE)
    if user_match:
        metrics["users"] = user_match.group(1)
    
    # Find team size
    team_pattern = r'(?:team|staff)\s+of\s+(\d+)'
    team_match = re.search(team_pattern, text, re.IGNORECASE)
    if team_match:
        metrics["team_size"] = int(team_match.group(1))
    
    return {k: v for k, v in metrics.items() if v is not None}


def _extract_sections(text: str) -> Dict:
    """
    Identify and extract major sections from pitch deck.
    """
    sections = {}
    
    # Common pitch sections
    section_patterns = {
        "problem": r"(?:problem|challenge|market pain).*?(?=(?:solution|approach|our))",
        "solution": r"(?:solution|approach|our solution).*?(?=(?:market|business model|traction))",
        "market": r"(?:market|tam|market size|addressable).*?(?=(?:business model|competitors|traction))",
        "traction": r"(?:traction|metrics|results|achievements).*?(?=(?:team|funding|ask))",
        "team": r"(?:team|founders|management).*?(?=(?:funding|ask|conclusion))",
        "ask": r"(?:ask|funding|investment).*?(?=(?:conclusion|thank|contact))"
    }
    
    for section_name, pattern in section_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            section_text = match.group(0)[:200]  # First 200 chars
            sections[section_name] = section_text.strip()
    
    return sections


def analyze_web_text(page_text: str) -> Dict:
    """
    Analyzes raw webpage or document text to extract startup intelligence.
    Used by the on-page summarizer widget.
    
    Args:
        page_text: Raw text content from a webpage or document
        
    Returns:
        dict: Structured analysis with traction, tech stack, and investment ask
    """
    try:
        analysis = {
            "traction": _extract_traction(page_text),
            "tech_stack": _extract_tech_stack(page_text),
            "investment_ask": _extract_investment_ask(page_text),
            "confidence_score": 0.75
        }
        return analysis
        
    except Exception as e:
        logger.error(f"Web text analysis failed: {str(e)}")
        return {
            "traction": "Analysis failed",
            "tech_stack": "Analysis failed",
            "investment_ask": "Analysis failed",
            "confidence_score": 0.0
        }


def _extract_traction(text: str) -> str:
    """Extract traction signals from text."""
    traction_signals = []
    
    # Look for user/customer counts
    user_pattern = r'(\d+,?\d*)\s+(?:users|customers|signups|downloads)'
    user_matches = re.findall(user_pattern, text, re.IGNORECASE)
    if user_matches:
        traction_signals.append(f"{user_matches[0]} users")
    
    # Look for revenue
    revenue_pattern = r'\$(\d+[MK]?)\s+(?:revenue|ARR|MRR)'
    revenue_matches = re.findall(revenue_pattern, text, re.IGNORECASE)
    if revenue_matches:
        traction_signals.append(f"${revenue_matches[0]} revenue")
    
    # Look for growth rate
    growth_pattern = r'(\d+)%\s+(?:growth|increase|MoM|YoY)'
    growth_matches = re.findall(growth_pattern, text, re.IGNORECASE)
    if growth_matches:
        traction_signals.append(f"{growth_matches[0]}% growth rate")
    
    # Look for partnerships/integrations
    if re.search(r'(?:partnership|integration|partnership with|integrated with)', text, re.IGNORECASE):
        traction_signals.append("Strategic partnerships established")
    
    if traction_signals:
        return "• " + "\n• ".join(traction_signals[:3])  # Return top 3
    return "No specific traction metrics detected."


def _extract_tech_stack(text: str) -> str:
    """Extract technology stack from text."""
    tech_keywords = [
        'React', 'Node.js', 'Python', 'Django', 'PostgreSQL', 'MongoDB',
        'AWS', 'Google Cloud', 'Azure', 'Docker', 'Kubernetes', 'GraphQL',
        'TensorFlow', 'PyTorch', 'Machine Learning', 'AI', 'Blockchain',
        'Web3', 'Solidity', 'Ruby on Rails', 'Vue.js', 'Angular',
        'Next.js', 'FastAPI', 'Rust', 'Go', 'Java', 'Scala'
    ]
    
    found_techs = []
    for tech in tech_keywords:
        if re.search(rf'\b{tech}\b', text, re.IGNORECASE):
            found_techs.append(tech)
    
    if found_techs:
        return "• " + "\n• ".join(found_techs[:5])  # Return top 5
    return "Standard technology framework detected."


def _extract_investment_ask(text: str) -> str:
    """Extract investment amount being requested."""
    ask_pattern = r'(?:raising|seeking|fundraising|seeking|target)\s+\$(\d+[MK]?)'
    ask_match = re.search(ask_pattern, text, re.IGNORECASE)
    
    if ask_match:
        amount = ask_match.group(1)
        return f"Seeking ${amount} in funding"
    
    return "Target funding details not explicitly stated."


UNREADABLE_DOCUMENT_MESSAGE = (
    "Zelda couldn't find any readable text in this document. It may be made only of images "
    "— please upload a version with selectable text."
)


def has_usable_text(text):
    """
    Whether extraction produced anything to analyze. Whitespace doesn't count:
    a deck of empty text boxes extracts to newlines, an image-only deck to
    nothing, and analyzing either would be a paid call about no content.
    """
    return bool(strip_page_markers(text).strip())


def extract_text_from_file(uploaded_file):
    """
    Extracts raw text from an uploaded file, plus a page/slide count for
    display (e.g. the valuation preview's "N Pages Analyzed" stat, which
    was silently stuck at 0 before this — PyPDF2/python-pptx already know
    the count, it just wasn't being returned). Returns (text, page_count);
    .txt has no natural pagination, so it's always 1 "page."
    Used by the DocumentIngestView to get raw text for the pipeline.

    Raises ExtractionError when the file cannot be read; never returns
    an error message or an empty string in place of the document. ("" still
    means the file opened and holds no text, e.g. an image-only deck.)
    """
    try:
        filename = uploaded_file.name.lower()

        if filename.endswith('.pdf'):
            return _extract_pdf_text(uploaded_file)
        elif filename.endswith('.pptx'):
            return _extract_pptx_text(uploaded_file)
        elif filename.endswith('.txt'):
            uploaded_file.seek(0)
            text = uploaded_file.read().decode('utf-8', errors='ignore')
            return text, 1 if text else 0
        else:
            raise ExtractionError('unsupported_format', filename.rsplit('.', 1)[-1])
    except ExtractionError:
        raise
    except Exception as e:
        logger.error(f"Failed to extract text: {e}")
        raise ExtractionError('unreadable_file', type(e).__name__) from e