# zelda_api/chunking.py
"""
Intelligent document chunking with semantic awareness.
Breaks documents into overlapping chunks optimized for embedding and retrieval.
"""
import re
from typing import List, Tuple


class DocumentChunker:
    """
    Chunks documents into semantically meaningful pieces.
    Default: 400 tokens per chunk, 50 token overlap.
    """
    
    # Approximate tokens per word (English averages 1.3 tokens/word)
    TOKENS_PER_WORD = 1.3
    
    # Tuning parameters
    CHUNK_TOKEN_SIZE = 400  # Target chunk size
    CHUNK_OVERLAP_TOKENS = 50
    MIN_CHUNK_TOKENS = 50
    
    # Semantic section markers (detect chapter/section boundaries)
    SECTION_PATTERNS = [
        r'^#{1,3}\s+',  # Markdown headers
        r'^\d+\.\s+',  # Numbered sections
        r'^(Introduction|Executive Summary|Problem|Solution|Market|Team|Financial|Risk|Conclusion)[\s\:]',
        r'^(Overview|Background|Strategy|Implementation|Results|Next Steps)',
    ]
    
    def __init__(self, chunk_size_tokens: int = CHUNK_TOKEN_SIZE, overlap_tokens: int = CHUNK_OVERLAP_TOKENS):
        self.chunk_size_tokens = chunk_size_tokens
        self.overlap_tokens = overlap_tokens
        self.chunk_size_words = int(chunk_size_tokens / self.TOKENS_PER_WORD)
        self.overlap_words = int(overlap_tokens / self.TOKENS_PER_WORD)
    
    def chunk(self, text: str):
        """Split on slide boundaries for PPTX content."""
        # Split on 'Qibby Saves LLC' or any repeated title line acting as slide separator
        slides = re.split(r'\n(?=Qibby Saves LLC\n|(?:[A-Z][a-z]+ ){1,4}LLC\n)', text)
        
        # Fallback: if only 1 chunk, split on any ALL-CAPS or Title Case line
        if len(slides) <= 1:
            slides = re.split(r'\n(?=[A-Z][^\n]{2,40}\n)', text)
    
        chunks = []
        for idx, slide_text in enumerate(slides):
            slide_text = slide_text.strip()
            if len(slide_text) < 20:
                continue
            lines = slide_text.split('\n')
            title = lines[0].strip() if lines else f"Slide {idx+1}"
            chunks.append((slide_text, idx + 1, title))
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """Remove extra whitespace and normalize text."""
        # Remove multiple newlines
        text = re.sub(r'\n\n+', '\n', text)
        # Remove leading/trailing whitespace from lines
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        # Normalize spaces
        text = re.sub(r' +', ' ', text)
        return text
    
    def _detect_sections(self, text: str) -> List[Tuple[str, str]]:
        """Detect major section boundaries."""
        sections = []
        for line in text.split('\n')[:100]:  # Check first 100 lines
            for pattern in self.SECTION_PATTERNS:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    # Extract section title
                    title = line.replace('#', '').strip()
                    title = re.sub(r'^\d+\.\s+', '', title).strip()
                    if len(title) > 3:
                        sections.append((line, title))
                    break
        return sections
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using regex."""
        # Simple sentence splitter (can be improved)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _get_overlap_sentences(self, sentences: List[str], target_words: int) -> List[str]:
        """Get last N sentences from current chunk for overlap."""
        overlap = []
        word_count = 0
        for sentence in reversed(sentences):
            word_count += len(sentence.split())
            overlap.insert(0, sentence)
            if word_count >= target_words:
                break
        return overlap


def estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 0.75 words in English)."""
    words = len(text.split())
    return int(words / 0.75)