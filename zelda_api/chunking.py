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
    
    def chunk(self, text: str) -> List[Tuple[str, int, str]]:
        """
        Chunk text into overlapping semantic chunks.
        
        Returns:
            List of (chunk_text, page_number, section_title)
        """
        if not text or not text.strip():
            return []
        
        # Clean text
        text = self._clean_text(text)
        
        # Detect sections with confidence
        sections = self._detect_sections(text)
        
        # Break text into sentences for flexible boundaries
        sentences = self._split_into_sentences(text)
        
        chunks = []
        current_chunk = []
        current_chunk_words = 0
        current_section = "General"
        page_number = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_words = len(sentence.split())
            
            # Check if this sentence starts a new section
            for section_match, section_title in sections:
                if sentence.startswith(section_match[:20]):  # Match first 20 chars
                    current_section = section_title
                    break
            
            # If adding this sentence exceeds chunk size, save current chunk and start new
            if current_chunk_words + sentence_words > self.chunk_size_words and current_chunk:
                chunk_text = ' '.join(current_chunk)
                if len(chunk_text.split()) >= self.MIN_CHUNK_TOKENS / self.TOKENS_PER_WORD:
                    chunks.append((chunk_text, page_number, current_section))
                    chunk_index += 1
                
                # Start new chunk with overlap
                # Keep last few sentences for context
                overlap_sentences = self._get_overlap_sentences(current_chunk, self.overlap_words)
                current_chunk = overlap_sentences + [sentence]
                current_chunk_words = len(' '.join(current_chunk).split())
            else:
                current_chunk.append(sentence)
                current_chunk_words += sentence_words
        
        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            if len(chunk_text.split()) >= self.MIN_CHUNK_TOKENS / self.TOKENS_PER_WORD:
                chunks.append((chunk_text, page_number, current_section))
        
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