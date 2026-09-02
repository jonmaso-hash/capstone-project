import hashlib
import logging
from django.core.cache import cache
from matchmaking.services.ai_utils import generate_vector
from matchmaking.utils import clean_financial_input

# Initialize production logging channel
logger = logging.getLogger(__name__)

EMBEDDING_CACHE_TTL = 60 * 60 * 24 * 30  # 30 days, matches vector_fields_updated_at's staleness window
SPARSE_SIMILARITY_CACHE_TTL = 60 * 60 * 6  # 6 hours — called once per founder x investor pair on every dashboard render

# Fixed output size of the local all-MiniLM-L6-v2 model (matchmaking/services/ai_utils.py).
EMBEDDING_DIMENSIONS = 384


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()

def generate_profile_embedding(text_content: str) -> list[float]:
    """
    Generates a dense embedding locally via sentence-transformers
    (matchmaking/services/ai_utils.py) — no external API, no API key,
    no network call once the model weights are cached.
    """
    if not text_content or not text_content.strip():
        return []

    # Content-addressed cache key — naturally invalidates when the text
    # changes (no explicit invalidation needed), so a re-save with the same
    # description just gets a cache hit instead of re-running the model.
    cache_key = f"embedding:{_text_hash(text_content)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        vector = generate_vector(text_content.strip())
        if vector is None:
            return []
        vector = vector.tolist()
        cache.set(cache_key, vector, EMBEDDING_CACHE_TTL)
        return vector
    except Exception as e:
        logger.error(f"[Embedding Pipeline Error]: {e}")
        return []

def calculate_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    """
    Computes the mathematical cosine similarity between two dimensional vector arrays.
    Enforces a strict length parity check and handles zero-vector division safely.
    """
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0
        
    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = sum(a * a for a in vector_a) ** 0.5
    norm_b = sum(b * b for b in vector_b) ** 0.5
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
        
    return dot_product / (norm_a * norm_b)

def calculate_sparse_similarity(text_a: str, text_b: str) -> float:
    """
    Sparse/keyword-overlap signal for the hybrid scoring blend — TF-IDF +
    cosine similarity, fit locally over just this one pair (scikit-learn is
    already a dependency; no BM25 package needed). This is the exact-term
    complement to calculate_similarity's conceptual/semantic dense vector
    match: it catches cases where two texts share the same specific words
    (a named technology, a specific city) that a dense embedding can blur
    together with merely-similar concepts.
    """
    if not text_a or not text_a.strip() or not text_b or not text_b.strip():
        return 0.0

    cache_key = f"sparse_sim:{_text_hash(text_a)}:{_text_hash(text_b)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform([text_a, text_b])
        score = float(cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0])
        cache.set(cache_key, score, SPARSE_SIMILARITY_CACHE_TTL)
        return score
    except Exception as e:
        logger.error(f"[Sparse Similarity Error]: {e}")
        return 0.0

def calculate_zelda_advantage(application):
    # Retrieve sanitized values
    revenue = float(clean_financial_input(application.current_revenue) or 0)
    ask = float(clean_financial_input(application.raising_amount) or 0)
    burn = float(clean_financial_input(application.monthly_burn_rate) or 0)
    team_size = int(clean_financial_input(application.team_size) or 1)
    years = int(clean_financial_input(application.years_in_business) or 0)

    # 1. Efficiency Score (Higher revenue/team = better)
    efficiency = revenue / team_size if team_size > 0 else 0
    eff_pts = min(25, (efficiency / 250000) * 25)

    # 2. Runway Calculation (Formula: Cash on hand / Burn). Burn was previously
    # defaulted to $1 when undisclosed, which turned "unknown" into a division
    # by a near-zero number and produced fabricated figures like "999.9 months"
    # runway. Leave it unset instead of faking precision the input doesn't support.
    if burn > 0:
        runway = ((revenue / 12) + ask) / burn
        application.runway_months = min(round(runway, 1), 999.9)
    else:
        runway = 0
        application.runway_months = None

    # 3. Final Weighted Score
    # Stability (3pts/year) + Runway Score + Efficiency
    total_score = 40 + eff_pts + min(20, (runway / 36) * 20) + min(15, years * 3)
    application.zelda_score = int(max(1, min(99, total_score)))
    
    application.save()