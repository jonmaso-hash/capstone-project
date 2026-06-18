# zelda_api/retrieval.py
"""
Vector retrieval and context assembly for RAG (Retrieval-Augmented Generation).
Finds relevant document chunks and assembles contextual information for analysis.
"""
import logging
from typing import List, Dict, Tuple, Optional
from django.db.models import Q
from .vector_models import DocumentChunk, DocumentSource
from .embeddings import embedding_engine, EmbeddingEngine

logger = logging.getLogger(__name__)


class VectorRetriever:
    """
    Retrieves relevant document chunks based on semantic similarity.
    Uses vector search with fallback to keyword search.
    """
    
    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self.embedding_engine = embedding_engine
    
    def retrieve(self, query: str, document_source: Optional[DocumentSource] = None) -> List[Dict]:
        """
        Retrieve top-k relevant chunks for a query.
        
        Args:
            query: The search query
            document_source: Optional filter to single document
            
        Returns:
            List of dicts with chunk info and relevance scores
        """
        # Generate query embedding
        query_embedding = self.embedding_engine.embed_text(query)
        
        if not query_embedding:
            logger.warning(f"Failed to embed query: {query}")
            return self._keyword_fallback_search(query, document_source)
        
        return self._vector_search(query_embedding, query, document_source)
    
    def _vector_search(self, query_embedding: List[float], query: str, document_source: Optional[DocumentSource]) -> List[Dict]:
        """
        Search using vector similarity.
        """
        # Get candidate chunks
        chunks_query = DocumentChunk.objects.filter(embedding_vector__isnull=False)
        
        if document_source:
            chunks_query = chunks_query.filter(document=document_source)
        
        chunks = list(chunks_query.select_related('document'))
        
        if not chunks:
            logger.debug("No embedded chunks found, falling back to keyword search")
            return self._keyword_fallback_search(query, document_source)
        
        # Calculate similarity scores
        scored_chunks = []
        for chunk in chunks:
            if not chunk.embedding_vector:
                continue
            
            try:
                similarity = self.embedding_engine.cosine_similarity(
                    query_embedding, 
                    chunk.embedding_vector
                )
                
                # Boost score if query keywords appear in chunk
                keyword_boost = self._keyword_boost(query, chunk.raw_text)
                
                final_score = (similarity * 0.7) + (keyword_boost * 0.3)
                
                scored_chunks.append({
                    'chunk': chunk,
                    'score': final_score,
                    'similarity': similarity,
                    'keyword_boost': keyword_boost,
                })
            except Exception as e:
                logger.error(f"Error scoring chunk {chunk.id}: {str(e)}")
        
        # Sort by score and return top-k
        scored_chunks.sort(key=lambda x: x['score'], reverse=True)
        
        return [
            {
                'id': s['chunk'].id,
                'text': s['chunk'].raw_text,
                'page': s['chunk'].page_number,
                'section': s['chunk'].section_title,
                'relevance': s['score'],
                'document': s['chunk'].document.source_entity,
            }
            for s in scored_chunks[:self.top_k]
        ]
    
    def _keyword_fallback_search(self, query: str, document_source: Optional[DocumentSource]) -> List[Dict]:
        """
        Fallback keyword search when vector search unavailable.
        """
        query_words = query.lower().split()
        
        chunks_query = DocumentChunk.objects.all()
        if document_source:
            chunks_query = chunks_query.filter(document=document_source)
        
        # Search for chunks containing multiple query terms
        q_objects = Q()
        for word in query_words:
            if len(word) > 3:  # Skip short words
                q_objects |= Q(raw_text__icontains=word)
        
        chunks = list(chunks_query.filter(q_objects).select_related('document')[:self.top_k])
        
        return [
            {
                'id': chunk.id,
                'text': chunk.raw_text,
                'page': chunk.page_number,
                'section': chunk.section_title,
                'relevance': 0.5,  # Neutral relevance for keyword matches
                'document': chunk.document.source_entity,
            }
            for chunk in chunks
        ]
    
    def _keyword_boost(self, query: str, text: str) -> float:
        """
        Calculate keyword match boost (0.0-1.0).
        """
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        
        matches = len(query_words & text_words)
        max_matches = len(query_words)
        
        if max_matches == 0:
            return 0.0
        
        return min(matches / max_matches, 1.0)


class ContextAssembler:
    """
    Assembles contextual information from retrieved chunks.
    Produces structured context for memo generation.
    """
    
    def __init__(self):
        self.retriever = VectorRetriever(top_k=7)
    
    def assemble_context(self, document_source: DocumentSource) -> Dict:
        """
        Assemble comprehensive context for a document.
        Retrieves context for key topics and organizes by section.
        """
        # Key analysis topics to retrieve context for
        topics = [
            "problem and market opportunity",
            "company revenue and financial metrics",
            "team experience and background",
            "technology and competitive advantage",
            "customer traction and use cases",
            "funding stage and investment ask",
            "risks and challenges",
        ]
        
        context_map = {}
        all_cited_chunks = set()
        
        for topic in topics:
            results = self.retriever.retrieve(topic, document_source)
            context_map[topic] = {
                'retrieved': results,
                'count': len(results),
            }
            
            for result in results:
                all_cited_chunks.add(result['id'])
        
        # Compile citation metadata
        cited_chunks = DocumentChunk.objects.filter(id__in=all_cited_chunks)
        
        return {
            'document_id': document_source.id,
            'source_entity': document_source.source_entity,
            'context_by_topic': context_map,
            'total_cited_chunks': len(all_cited_chunks),
            'total_chunks': document_source.chunks.count(),
            'cited_pages': sorted(set(c.page_number for c in cited_chunks if c.page_number)),
        }
    
    def retrieve_for_category(self, document_source: DocumentSource, category: str) -> Tuple[List[Dict], str]:
        """
        Retrieve context for a specific insight category.
        
        Returns:
            (retrieved_chunks, assembled_context_text)
        """
        # Map categories to search queries
        category_queries = {
            'TAM': "total addressable market market size opportunity",
            'Team': "team members founders experience background",
            'Revenue': "revenue income financial metrics traction",
            'Product': "product features technology solution",
            'Traction': "customers users adoption growth metrics",
            'Funding': "funding investment ask capital raise",
            'Risk': "risk challenges problems threats competition",
            'Other': "company business model vision",
        }
        
        query = category_queries.get(category, category)
        results = self.retriever.retrieve(query, document_source)
        
        # Assemble into readable text
        context_text = f"Context for {category}:\n\n"
        for i, result in enumerate(results, 1):
            context_text += f"[Source {i} - {result['section'] or 'General'}]:\n"
            context_text += result['text'][:300] + "...\n\n"
        
        return results, context_text


# Global instances
retriever = VectorRetriever()
context_assembler = ContextAssembler()