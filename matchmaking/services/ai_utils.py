# ai_utils.py
import numpy as np
from sentence_transformers import SentenceTransformer

# Load model once globally
model = SentenceTransformer('all-MiniLM-L6-v2')

def generate_vector(text):
    """Converts text into a 384-dimensional vector."""
    if not text:
        return None
    return model.encode(text)

def calculate_similarity(vector1, vector2):
    """Calculates how close two users are (0 to 1)."""
    if vector1 is None or vector2 is None:
        return 0.0
    # Use Cosine Similarity formula
    dot_product = np.dot(vector1, vector2)
    norm1 = np.linalg.norm(vector1)
    norm2 = np.linalg.norm(vector2)
    return dot_product / (norm1 * norm2)