import os
from google import genai
from google.genai import errors

def generate_profile_embedding(text_content: str) -> list[float]:
    """
    Transforms a raw description block into a semantic vector 
    array using the modern unified Google GenAI client.
    """
    if not text_content or not text_content.strip():
        return []

    try:
        # Client initializes automatically using the environment variable string
        client = genai.Client()
        
        # Invoke Google's native embedding standard layer model
        response = client.models.embed_content(
            model='text-embedding-004',
            contents=text_content.strip()
        )
        
        # Extract the sequence values array from the response object
        if response.embeddings:
            return response.embeddings[0].values
            
    except errors.APIError as e:
        print(f"[Gemini API Exception]: {e}")
    except Exception as e:
        print(f"[Embedding Pipeline Error]: {e}")
        
    return []


def calculate_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    """
    Computes the cosine similarity between two embedding vectors.
    """
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0
        
    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = sum(a * a for a in vector_a) ** 0.5
    norm_b = sum(b * b for b in vector_b) ** 0.5
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
        
    return dot_product / (norm_a * norm_b)