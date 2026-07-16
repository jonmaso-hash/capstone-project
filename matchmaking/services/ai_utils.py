# ai_utils.py
import numpy as np

# Loaded lazily on first use, not at import time — this module gets pulled
# in transitively by ai_engine.py (imported by models.py/views.py, i.e. almost
# every request), so a module-level SentenceTransformer(...) call would make
# every process start (manage.py check, tests, runserver) pay for a model
# load/download even when nothing ever generates an embedding.
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def generate_vector(text):
    """Converts text into a 384-dimensional vector."""
    if not text:
        return None
    return _get_model().encode(text)


def calculate_similarity(vector1, vector2):
    """Calculates how close two users are (0 to 1)."""
    if vector1 is None or vector2 is None:
        return 0.0
    # Use Cosine Similarity formula
    dot_product = np.dot(vector1, vector2)
    norm1 = np.linalg.norm(vector1)
    norm2 = np.linalg.norm(vector2)
    return dot_product / (norm1 * norm2)
