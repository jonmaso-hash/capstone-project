# zelda_api/retrieval.py
"""
Vector retrieval and context assembly for RAG (Retrieval-Augmented Generation).
Finds relevant document chunks and assembles contextual information for analysis.

Principal-scoped (Phase 1 Task 3). Every retrieval names the Principal it is
for, and the candidate chunks are restricted to what authorize(principal)
permits BEFORE anything is loaded, embedded, scored or keyword-matched --
retrieve-then-filter is never the security model. There is no unscoped
retrieval: no principal refuses, and a document outside the principal's
scope refuses rather than returning an empty result.
"""
import logging
import re
from typing import List, Dict, Tuple, Optional
from django.db.models import Q
from .authorization import authorize
from .principal import PrincipalRequired, require_principal
from .vector_models import DocumentChunk, DocumentSource
from .embeddings import embedding_engine, EmbeddingEngine

logger = logging.getLogger(__name__)

MAX_TOP_K = 20


class RetrievalRefused(PrincipalRequired):
    """The principal may not retrieve this document's text."""


def meaningful_terms(text):
    """
    Lowercase words longer than three characters, punctuation stripped -- the
    rule the keyword fallback always used. Counting "on" or "the" as a match
    is how an unrelated question returned chunks with a non-zero relevance.
    """
    return {w for w in re.findall(r"[a-z0-9]+", (text or '').lower()) if len(w) > 3}


def validate_top_k(value, default=5):
    """
    An int in 1..MAX_TOP_K, or ValueError. Booleans and strings are not
    numbers here: top_k arrives from request bodies.
    """
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_TOP_K:
        raise ValueError(f'top_k must be an integer from 1 to {MAX_TOP_K}.')
    return value


class VectorRetriever:
    """
    Retrieves relevant document chunks based on semantic similarity.
    Uses vector search with fallback to keyword search.
    """

    def __init__(self, top_k: int = 5):
        self.top_k = validate_top_k(top_k)
        self.embedding_engine = embedding_engine

    def retrieve(self, principal, query: str, document_source: Optional[DocumentSource] = None) -> List[Dict]:
        """
        Retrieve top-k relevant chunks for a query, for this principal.

        Args:
            principal: Who the retrieval is for. Required; None refuses.
            query: The search query
            document_source: Optional filter to single document. Refuses if
                the principal may not read its text.

        Returns:
            List of dicts with chunk info and relevance scores
        """
        candidates = self._candidates(principal, document_source)

        # Generate query embedding
        query_embedding = self.embedding_engine.embed_text(query)

        if not query_embedding:
            logger.warning(f"Failed to embed query: {query}")
            return self._keyword_fallback_search(query, candidates)

        return self._vector_search(query_embedding, query, candidates)

    @staticmethod
    def _candidates(principal, document_source: Optional[DocumentSource]):
        """
        The only place this module reads DocumentChunk: the chunks of the
        documents authorize(principal) permits, narrowed to one document if
        asked. Built before any ranking, so nothing outside scope is loaded.
        """
        auth = authorize(require_principal(principal))
        if document_source is not None and not auth.text_permitted(document_source):
            raise RetrievalRefused('This principal may not retrieve this document.')
        candidates = DocumentChunk.objects.filter(document__in=auth.text_documents())
        if document_source is not None:
            candidates = candidates.filter(document=document_source)
        return candidates

    def _vector_search(self, query_embedding: List[float], query: str, candidates) -> List[Dict]:
        """
        Search using vector similarity over the authorized candidates.
        """
        chunks = list(candidates.filter(embedding_vector__isnull=False).select_related('document'))

        if not chunks:
            logger.debug("No embedded chunks found, falling back to keyword search")
            return self._keyword_fallback_search(query, candidates)

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
                if final_score <= 0:
                    # Nothing in this chunk bears on the query. Returning it
                    # anyway, ranked, is how a question the document cannot
                    # answer got five "sources".
                    continue

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

    def _keyword_fallback_search(self, query: str, candidates) -> List[Dict]:
        """
        Fallback keyword search when vector search unavailable, over the same
        authorized candidates -- never over every chunk.
        """
        # Search for chunks containing any meaningful query term. No term
        # means nothing to match: an empty Q() would match every chunk.
        terms = meaningful_terms(query)
        if not terms:
            return []
        q_objects = Q()
        for word in terms:
            q_objects |= Q(raw_text__icontains=word)

        chunks = list(candidates.filter(q_objects).select_related('document')[:self.top_k])

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
        query_words = meaningful_terms(query)
        text_words = meaningful_terms(text)

        matches = len(query_words & text_words)
        max_matches = len(query_words)

        if max_matches == 0:
            return 0.0

        return min(matches / max_matches, 1.0)


def document_chunks(principal, document_source: DocumentSource):
    """
    Every chunk of one document, in order, for a principal who may read its
    text. The same candidate scope as retrieval; out of scope refuses.
    """
    return VectorRetriever._candidates(principal, document_source).order_by('chunk_index')


class ContextAssembler:
    """
    Assembles contextual information from retrieved chunks.
    Produces structured context for memo generation.
    """

    def __init__(self):
        self.retriever = VectorRetriever(top_k=7)

    def assemble_context(self, principal, document_source: DocumentSource) -> Dict:
        """
        Assemble comprehensive context for a document, for this principal.
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
            results = self.retriever.retrieve(principal, topic, document_source)
            context_map[topic] = {
                'retrieved': results,
                'count': len(results),
            }

            for result in results:
                all_cited_chunks.add(result['id'])

        # Citation metadata from the chunks already retrieved for this
        # principal, not a second, unscoped read.
        cited_pages = {
            result['page']
            for topic_context in context_map.values()
            for result in topic_context['retrieved']
            if result['page']
        }

        return {
            'document_id': document_source.id,
            'source_entity': document_source.source_entity,
            'context_by_topic': context_map,
            'total_cited_chunks': len(all_cited_chunks),
            'total_chunks': document_source.chunks.count(),
            'cited_pages': sorted(cited_pages),
        }

    def retrieve_for_category(self, principal, document_source: DocumentSource, category: str) -> Tuple[List[Dict], str]:
        """
        Retrieve context for a specific insight category, for this principal.

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
        results = self.retriever.retrieve(principal, query, document_source)

        # Assemble into readable text
        context_text = f"Context for {category}:\n\n"
        for i, result in enumerate(results, 1):
            context_text += f"[Source {i} - {result['section'] or 'General'}]:\n"
            context_text += result['text'][:300] + "...\n\n"

        return results, context_text


# Global instances
retriever = VectorRetriever()
context_assembler = ContextAssembler()
