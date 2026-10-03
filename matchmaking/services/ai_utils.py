# ai_utils.py
import threading

import numpy as np

# Loaded lazily on first use, not at import time — this module gets pulled
# in transitively by ai_engine.py (imported by models.py/views.py, i.e. almost
# every request), so a module-level SentenceTransformer(...) call would make
# every process start (manage.py check, tests, runserver) pay for a model
# load/download even when nothing ever generates an embedding.
_model = None
# gunicorn runs threaded workers: without the lock, the first requests to reach
# a fresh worker at the same moment would each load their own copy.
_model_lock = threading.Lock()


# THE CANONICAL MODEL IDENTITY. One place, because it is consumed from four:
# this loader, CI's preload step, CI's cache key, and the test that checks a
# real embedding was produced. Repeating it as literals across YAML and Python
# is the next drift surface, and it already bit once.
#
# THE REVISION IS PINNED HERE AND NOT ONLY IN CI, which is the part that
# matters. CI preloading a pinned SHA while this loader asked for the default
# `main` is what broke the build: fetching by SHA writes snapshots/<sha> but no
# refs/main pointer, so an offline resolution of `main` finds nothing and the
# whole suite reports "couldn't find them in the cached files". Measured against
# an empty HF_HOME, not deduced. A pin the consumer ignores protects nothing.
#
# Changing the revision changes the embeddings, so it also changes what the
# semantic-ordering tests measure and what is stored in the 384-dimension
# pgvector columns (see migration 0051). Treat a bump as a data migration, not
# a dependency bump.
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
EMBEDDING_REVISION = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(EMBEDDING_MODEL,
                                             revision=EMBEDDING_REVISION)
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
