"""
Phase 1 close-out: the remaining boundary findings from the Nike baseline.

L-016  an anonymous caller of analyze/founder got a 500, not a refusal
L-015  hash vectors were labelled "claude-3-5-sonnet"
L-013  retrieval returned chunks that matched nothing (score 0, or only on
       "the"/"on") as sources, and never said "nothing relevant"
"""
import importlib
import json

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application
from matchmaking.tests import _mock_embedding_generation
from zelda_api.embeddings import EmbeddingEngine
from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
from zelda_api.principal import ORIGIN_TASK, Principal
from zelda_api.retrieval import VectorRetriever, meaningful_terms
from zelda_api.vector_models import DocumentChunk, DocumentSource

User = get_user_model()


class _Doc(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('closeout_owner', password='x')
        Application.objects.create(user=self.owner, company_name='Closeout Co', founder_name='F',
                                    email='c@t.test', description='d', sector='SaaS', stage='Seed')
        self.doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Closeout Co', uploaded_by=self.owner,
            document_type='pitch_deck', status='analyzed')
        for i, text in enumerate(('Annual revenue reached four million dollars.',
                                  'The team ships product weekly.')):
            DocumentChunk.objects.create(document=self.doc, chunk_index=i, page_number=i + 1,
                                         token_count=6, raw_text=text)
        self.principal = Principal.for_user(self.owner, ORIGIN_TASK)


class AnonymousRefusalTests(_Doc):
    """L-016: a refusal, never a crash."""

    def test_anonymous_analyze_is_a_403_not_a_500(self):
        response = self.client.get(reverse('zelda_api:analyze_founder', args=['closeout_owner']))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['status'], 'error')

    def test_anonymous_confirm_is_a_403_not_a_500(self):
        response = self.client.post(reverse('zelda_api:analyze_founder_confirm', args=['closeout_owner']))
        self.assertEqual(response.status_code, 403)

    def test_a_signed_in_non_investor_is_still_refused(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('zelda_api:analyze_founder', args=['closeout_owner']))
        self.assertEqual(response.status_code, 403)


class EmbeddingLabelTests(_Doc):
    """L-015: the label names the scheme that actually produced the vector."""

    def test_engine_labels_are_hash_schemes(self):
        engine = EmbeddingEngine()
        engine.client = None
        self.assertEqual(engine.label(), EmbeddingEngine.PLAIN_HASH_LABEL)
        engine.client = object()
        self.assertEqual(engine.label(), EmbeddingEngine.SEMANTIC_HASH_LABEL)
        self.assertFalse(hasattr(EmbeddingEngine, 'EMBEDDING_MODEL'))

    def test_embedding_records_the_label(self):
        pipeline = ZeldaIntelligencePipelineV2()
        pipeline.embedding_engine.client = None
        pipeline._embed_chunks(self.doc)
        labels = set(DocumentChunk.objects.filter(document=self.doc).values_list('embedding_model', flat=True))
        self.assertEqual(labels, {EmbeddingEngine.PLAIN_HASH_LABEL})

    def test_new_chunks_claim_no_model(self):
        chunk = DocumentChunk.objects.filter(document=self.doc).first()
        self.assertEqual(chunk.embedding_model, '')

    def test_migration_relabels_old_rows(self):
        DocumentChunk.objects.filter(document=self.doc).update(embedding_model='claude-3-5-sonnet')
        migration = importlib.import_module('zelda_api.migrations.0033_honest_embedding_label')
        migration.relabel(django_apps, None)
        labels = set(DocumentChunk.objects.filter(document=self.doc).values_list('embedding_model', flat=True))
        self.assertEqual(labels, {migration.LEGACY_LABEL})


class RelevanceTests(_Doc):
    """L-013: only chunks that share a meaningful term are evidence; none is said out loud."""

    def texts(self, query):
        return [r['text'] for r in VectorRetriever(top_k=5).retrieve(self.principal, query, self.doc)]

    def test_filler_words_are_not_matches(self):
        self.assertEqual(meaningful_terms('What did the CEO say on the call?'), {'what', 'call'})

    def test_a_question_the_document_cannot_answer_returns_nothing(self):
        self.assertEqual(self.texts('What did the CEO say on the latest earnings call?'), [])

    def test_a_relevant_question_still_finds_its_chunk(self):
        self.assertEqual(self.texts('What was the annual revenue?'), ['Annual revenue reached four million dollars.'])

    def test_vector_path_drops_zero_relevance_chunks(self):
        """
        Production-shaped: every chunk has a stored vector (a JSON string, as
        the pipeline writes it), so retrieval takes the VECTOR path, not the
        keyword fallback. A chunk sharing no meaningful term scores 0 there
        and must not be returned. (A fixture without vectors only ever
        exercised the fallback, and let a mutation removing this rule survive.)
        """
        DocumentChunk.objects.filter(document=self.doc).update(embedding_vector=json.dumps([0.1] * 8))
        self.assertEqual(self.texts('What did the CEO say on the latest earnings call?'), [])
        self.assertEqual(self.texts('What was the annual revenue?'), ['Annual revenue reached four million dollars.'])

    def test_short_word_queries_match_nothing_in_the_fallback(self):
        from unittest import mock
        with mock.patch('zelda_api.retrieval.embedding_engine.embed_text', return_value=None):
            self.assertEqual(self.texts('on the a'), [])
            self.assertEqual(self.texts('revenue'), ['Annual revenue reached four million dollars.'])

    def test_endpoints_say_when_nothing_is_relevant(self):
        self.client.force_login(self.owner)
        for name, count_key in (('zelda_api:document_search', 'results_count'), ('zelda_api:document_rag', 'source_count')):
            with self.subTest(view=name):
                post = lambda q: self.client.post(reverse(name, args=[self.doc.pk]),
                                                  data=json.dumps({'query': q}), content_type='application/json').json()
                empty = post('What did the CEO say on the latest earnings call?')
                self.assertEqual((empty[count_key], empty['no_relevant_evidence']), (0, True))
                found = post('annual revenue')
                self.assertEqual(found['no_relevant_evidence'], False)
                self.assertGreater(found[count_key], 0)
        rag = self.client.post(reverse('zelda_api:document_rag', args=[self.doc.pk]),
                               data=json.dumps({'query': 'earnings call'}), content_type='application/json').json()
        self.assertIn('No relevant evidence', rag['context'])
