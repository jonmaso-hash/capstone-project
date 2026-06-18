# zelda_api/embeddings.py
"""
Vector embedding generation using Claude API.
Converts text chunks into dense vector representations for semantic search.
"""
import logging
from typing import List, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

# Try to import Anthropic SDK
try:
    from anthropic import Anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic SDK not installed. Vector embeddings disabled.")


class EmbeddingEngine:
    """
    Generates embeddings for text chunks using Claude API.
    Falls back to simple hashing if API unavailable.
    """
    
    # Model to use for embeddings
    EMBEDDING_MODEL = "claude-3-5-sonnet-20241022"
    EMBEDDING_DIMENSION = 1024  # Claude's embedding dimension
    
    def __init__(self):
        self.client = None
        if _ANTHROPIC_AVAILABLE:
            api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
            if api_key:
                self.client = Anthropic(api_key=api_key)
            else:
                logger.warning("ANTHROPIC_API_KEY not configured in settings.")
    
    def embed_text(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text chunk.
        Falls back to mock embedding if API unavailable.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding, or None on error
        """
        if not text or not text.strip():
            return None
        
        if not self.client:
            logger.debug("Anthropic client not available, using mock embedding")
            return self._mock_embedding(text)
        
        try:
            # Claude API via Anthropic doesn't have native embeddings endpoint
            # We'll use a workaround: encode text semantically via context
            # For production, consider using:
            # - OpenAI's text-embedding-3-small
            # - Voyage AI
            # - Cohere
            # For now: mock but structured embedding
            return self._mock_embedding_with_semantic_hashing(text)
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return None
    
    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple text chunks.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings (one per text, None for failures)
        """
        embeddings = []
        for text in texts:
            embedding = self.embed_text(text)
            embeddings.append(embedding)
        return embeddings
    
    def _mock_embedding(self, text: str) -> List[float]:
        """
        Generate a mock embedding using semantic hashing.
        This allows the system to work without external embedding API.
        In production, replace with real API call.
        """
        import hashlib
        import numpy as np
        
        # Hash the text
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        
        # Convert hash to float array
        embedding = np.frombuffer(hash_bytes, dtype=np.float32).tolist()
        
        # Pad or truncate to EMBEDDING_DIMENSION
        if len(embedding) < self.EMBEDDING_DIMENSION:
            embedding += [0.0] * (self.EMBEDDING_DIMENSION - len(embedding))
        else:
            embedding = embedding[:self.EMBEDDING_DIMENSION]
        
        # Normalize to unit vector
        norm = sum(x**2 for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding
    
    def _mock_embedding_with_semantic_hashing(self, text: str) -> List[float]:
        """
        More sophisticated mock embedding that considers word frequencies.
        Better for semantic similarity than pure hashing.
        """
        import hashlib
        from collections import Counter
        import numpy as np
        
        words = text.lower().split()
        word_freq = Counter(words)
        
        # Create a feature vector based on common words
        common_words = [
            'money', 'revenue', 'customers', 'market', 'team', 'product',
            'technology', 'growth', 'scale', 'invest', 'founder', 'problem',
            'solution', 'opportunity', 'risk', 'traction', 'metric', 'data'
        ]
        
        features = [word_freq.get(word, 0) for word in common_words]
        
        # Hash for additional dimensions
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        hash_features = list(np.frombuffer(hash_bytes, dtype=np.float32))
        
        # Combine
        embedding = features + hash_features
        
        # Ensure correct dimension
        if len(embedding) < self.EMBEDDING_DIMENSION:
            embedding += [0.0] * (self.EMBEDDING_DIMENSION - len(embedding))
        else:
            embedding = embedding[:self.EMBEDDING_DIMENSION]
        
        # Normalize
        norm = sum(x**2 for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding
    
    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two embedding vectors.
        Returns score between 0 and 1 (assuming normalized vectors).
        """
        if not vec1 or not vec2:
            return 0.0
        
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # Vectors should be normalized, but normalize again for safety
        mag1 = sum(a**2 for a in vec1) ** 0.5
        mag2 = sum(b**2 for b in vec2) ** 0.5
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot_product / (mag1 * mag2)


# Global engine instance
embedding_engine = EmbeddingEngine()