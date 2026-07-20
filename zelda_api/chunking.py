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
        """
        Split on slide boundaries for PPTX content. PPTX exports commonly
        repeat the company name as a running header at the top of every
        slide — detected here dynamically (any short line recurring 3+
        times verbatim), not hardcoded to any one company. (An earlier
        version of this literally hardcoded the string 'Qibby Saves LLC' —
        a single test document's company name — as the split boundary,
        which meant every OTHER real deck's slides never split on their
        own running header at all, and worse, every chunk's title ended up
        being that header line itself rather than the real heading, e.g.
        "Traction" or "Problem".)
        """
        from collections import Counter

        stripped_lines = [line.strip() for line in text.split('\n') if line.strip()]
        short_line_counts = Counter(line for line in stripped_lines if len(line) <= 60)
        running_header = next((line for line, count in short_line_counts.most_common() if count >= 3), None)

        if running_header:
            slides = re.split(r'\n(?=' + re.escape(running_header) + r'\n)', text)
        else:
            # Fallback: no repeated header found — split on any ALL-CAPS or Title Case line.
            slides = re.split(r'\n(?=[A-Z][^\n]{2,40}\n)', text)

        chunks = []
        for idx, slide_text in enumerate(slides):
            slide_text = slide_text.strip()
            if len(slide_text) < 20:
                continue
            slide_lines = [line.strip() for line in slide_text.split('\n') if line.strip()]
            # Skip the running-header line itself when picking a title —
            # the real heading is usually the next line, not the company
            # name repeated at the top of every slide.
            title_candidates = [line for line in slide_lines if line != running_header] if running_header else slide_lines
            title = title_candidates[0] if title_candidates else (slide_lines[0] if slide_lines else f"Slide {idx+1}")
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