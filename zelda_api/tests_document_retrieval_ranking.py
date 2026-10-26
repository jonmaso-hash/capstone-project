"""
RA-114, part 2: which passages a document question reaches.

Memo 104's own deck (document 3146, frozen in data/document_retrieval/
memo104_chunks.json from f73bef5) ranked every chunk alike for most of the
fixed questions: the stored vectors contribute nothing (a JSON string never
matches the query vector's length, so similarity is 0), leaving keyword
overlap, and in that overlap

  - the subject's own name matched every chunk ("angel.co/manychat" is on
    every slide), so it could not tell one passage from another;
  - question words counted ("with" put page 2 first for the SEC question);
  - "raise" did not match "raised" (Q6 tied pages 1 and 2);
  - the deck reports adoption under "Traction" and never says "users", so Q2
    could not reach page 10 at all.

These tests pin the corrected ranking on that recorded deck, the same rules on
a second, synthetic deck (nothing here is specific to one company), and the
controls: unrelated questions reach nothing, and another document's chunks
are never evidence.

Reaching a passage is not the same as passing a question's grounding
criterion; the live plan grades that against the answer key.
"""
import json
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from zelda_api.embeddings import EmbeddingEngine
from zelda_api.principal import ORIGIN_TASK, Principal
from zelda_api.retrieval import VectorRetriever
from zelda_api.vector_models import DocumentChunk, DocumentSource

DATA = Path(__file__).resolve().parent / 'data' / 'document_retrieval' / 'memo104_chunks.json'
RECORDED = json.loads(DATA.read_text(encoding='utf-8'))

QUESTIONS = {
    'Q1': 'How much has ManyChat raised?',
    'Q2': 'How many users does ManyChat have?',
    'Q3': 'How many messages does ManyChat send?',
    'Q4': 'Is ManyChat registered with the SEC?',
    'Q5': "What is ManyChat's current revenue?",
    'Q6': 'When did ManyChat raise its Series A?',
    'Q7': 'Should I invest in ManyChat?',
}


_HASHING = EmbeddingEngine.__new__(EmbeddingEngine)   # the scheme only; no client is built


def _production_shaped_vector(text):
    # What the pipeline stores: json.dumps of the semantic-hash vector.
    return json.dumps(_HASHING._mock_embedding_with_semantic_hashing(text))


def _add_chunks(doc, chunks):
    for c in chunks:
        DocumentChunk.objects.create(document=doc, chunk_index=c['chunk_index'], page_number=c['page_number'],
                                     section_title=c['section_title'], raw_text=c['raw_text'],
                                     token_count=c['token_count'], embedding_vector=_production_shaped_vector(c['raw_text']))


class _Decks(TestCase):

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user('ranking_owner', password='x')
        self.doc = DocumentSource.objects.create(uploaded_by=self.owner, filename='deck.pptx',
                                                 source_entity=RECORDED['provenance']['source_entity'],
                                                 document_type='pitch_deck', status='analyzed')
        _add_chunks(self.doc, RECORDED['chunks'])
        # The same owner's other document says "users", "raised" and
        # "Traction" outright: it must never answer a question about self.doc.
        self.other = DocumentSource.objects.create(uploaded_by=self.owner, filename='other.pdf', source_entity='Other Co',
                                                   document_type='pitch_deck', status='analyzed')
        self.other_text = 'Traction: Other Co has 40,000 users and raised $5M in its Series A from ManyChat investors.'
        _add_chunks(self.other, [{'chunk_index': 0, 'page_number': 1, 'section_title': 'Traction',
                                  'raw_text': self.other_text, 'token_count': 20}])
        self.principal = Principal.for_user(self.owner, ORIGIN_TASK)

    def results(self, question, doc=None):
        return VectorRetriever(top_k=5).retrieve(self.principal, question, doc or self.doc)

    def pages(self, question, doc=None):
        return [r['page'] for r in self.results(question, doc)]


class RecordedDeckTests(_Decks):
    """Memo 104's Q1-Q7 on memo 104's own chunks."""

    def test_the_recorded_deck_is_the_one_the_run_chunked(self):
        self.assertEqual(RECORDED['provenance']['commit'], 'f73bef5')
        self.assertEqual(len(RECORDED['chunks']), 12)
        self.assertEqual(DocumentChunk.objects.filter(document=self.doc).count(), 12)

    def test_q1_reaches_the_raised_figure_first(self):
        results = self.results(QUESTIONS['Q1'])
        self.assertEqual(results[0]['page'], 2)
        self.assertIn('$23.1M raised', results[0]['text'])

    def test_q2_reaches_the_traction_slide(self):
        # The deck never says "users"; it reports adoption under "Traction".
        results = self.results(QUESTIONS['Q2'])
        self.assertEqual(results[0]['page'], 10)
        self.assertIn('140 000+ bots', results[0]['text'])

    def test_q3_reaches_both_message_figures_first(self):
        self.assertEqual(sorted(self.pages(QUESTIONS['Q3'])[:2]), [10, 12])

    def test_q6_puts_the_page_that_says_raised_first(self):
        self.assertEqual(self.pages(QUESTIONS['Q6'])[0], 2)

    def test_questions_the_deck_cannot_answer_reach_nothing(self):
        # The subject's name and question words are not evidence.
        self.assertEqual(self.pages(QUESTIONS['Q4']), [])
        self.assertEqual(self.pages(QUESTIONS['Q7']), [])

    def test_the_full_ranking_is_pinned(self):
        """The observed ranking at the fix, for review; the tests above carry the criteria."""
        observed = {q: self.pages(text) for q, text in QUESTIONS.items()}
        self.assertEqual(observed, {
            'Q1': [2], 'Q2': [10], 'Q3': [10, 12], 'Q4': [], 'Q5': [2], 'Q6': [2, 1], 'Q7': [],
        })

    def test_relevance_orders_the_results(self):
        for text in QUESTIONS.values():
            relevance = [r['relevance'] for r in self.results(text)]
            self.assertEqual(relevance, sorted(relevance, reverse=True))
            self.assertTrue(all(0 < r <= 1 for r in relevance))


class UnrelatedQuestionTests(_Decks):

    def test_unrelated_questions_reach_nothing(self):
        for question in ('What is the weather in Paris?', "Who is ManyChat's CEO?", 'ManyChat',
                         'What did the CEO say on the latest earnings call?', 'Tell me about it.'):
            with self.subTest(question=question):
                self.assertEqual(self.pages(question), [])

    def test_the_endpoint_says_so(self):
        self.client.force_login(self.owner)
        body = self.client.post(reverse('zelda_api:ask'), content_type='application/json',
                                data=json.dumps({'q': "Who is ManyChat's CEO?", 'document_id': self.doc.pk})).json()
        self.assertEqual((body['evidence'], body['no_relevant_evidence']), ([], True))
        self.assertEqual(body['response'], 'No relevant evidence was found in this document for that question.')


class CrossDocumentTests(_Decks):

    def test_another_documents_chunks_are_never_evidence(self):
        for text in list(QUESTIONS.values()) + ['users traction raised Series A']:
            with self.subTest(question=text):
                self.assertNotIn(self.other_text, [r['text'] for r in self.results(text)])
                self.assertTrue(all(r['document'] == self.doc.source_entity for r in self.results(text)))

    def test_the_other_document_answers_its_own_question(self):
        # Positive control: the same rules find "users" where it is stated.
        self.assertEqual([r['text'] for r in self.results(QUESTIONS['Q2'], self.other)], [self.other_text])

    def test_across_documents_a_name_still_counts(self):
        # The subject's name is set aside only inside its own document; a
        # search across documents may still find a document by name.
        staff = get_user_model().objects.create_user('ranking_staff', password='x', is_staff=True)
        results = VectorRetriever(top_k=20).retrieve(Principal.for_user(staff, ORIGIN_TASK), 'Other Co')
        self.assertIn(self.other_text, [r['text'] for r in results])


class EndpointParityTests(_Decks):

    def test_ask_evidence_equals_search_results(self):
        self.client.force_login(self.owner)
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction') as extract:
            for q, text in QUESTIONS.items():
                with self.subTest(q=q):
                    ask = self.client.post(reverse('zelda_api:ask'), content_type='application/json',
                                           data=json.dumps({'q': text, 'document_id': self.doc.pk})).json()
                    search = self.client.post(reverse('zelda_api:document_search', args=[self.doc.pk]),
                                              content_type='application/json', data=json.dumps({'query': text})).json()
                    self.assertEqual([(e['chunk_id'], e['page'], e['text'], e['relevance']) for e in ask['evidence']],
                                     [(r['id'], r['page'], r['text'], r['relevance']) for r in search['results']])
                    self.assertEqual(ask['no_relevant_evidence'], search['no_relevant_evidence'])
        extract.assert_not_called()


class SyntheticDeckTests(TestCase):
    """The same rules on a deck with another name and other words."""

    def setUp(self):
        self.owner = get_user_model().objects.create_user('synthetic_owner', password='x')
        self.principal = Principal.for_user(self.owner, ORIGIN_TASK)

    def deck(self, entity, texts):
        doc = DocumentSource.objects.create(uploaded_by=self.owner, filename='s.pdf', source_entity=entity,
                                            document_type='pitch_deck', status='analyzed')
        _add_chunks(doc, [{'chunk_index': i, 'page_number': i + 1, 'section_title': '', 'raw_text': t,
                           'token_count': 10} for i, t in enumerate(texts)])
        return doc

    def pages(self, doc, question):
        return [r['page'] for r in VectorRetriever(top_k=5).retrieve(self.principal, question, doc)]

    def test_a_footer_name_on_every_page_selects_nothing(self):
        doc = self.deck('Brightline Robotics', ['Brightline Robotics | brightline.io | Our team',
                                                'Brightline Robotics | brightline.io | Traction: 2,000 paying customers',
                                                'Brightline Robotics | brightline.io | Revenue: $1.2M ARR'])
        self.assertEqual(self.pages(doc, 'How many users does Brightline Robotics have?'), [2])
        self.assertEqual(self.pages(doc, 'What is Brightline Robotics revenue?'), [3])
        self.assertEqual(self.pages(doc, 'Is Brightline Robotics profitable?'), [])

    def test_a_stated_figure_outranks_a_related_heading(self):
        doc = self.deck('Quill', ['Traction: growing fast', 'We have 12,000 monthly active users'])
        self.assertEqual(self.pages(doc, 'How many users does Quill have?'), [2, 1])

    def test_word_forms_match(self):
        doc = self.deck('Fernway', ['Fernway raised $4M', 'Fernway messages'])
        self.assertEqual(self.pages(doc, 'When did Fernway raise money?'), [1])
        self.assertEqual(self.pages(doc, 'How many message?'), [2])

    def test_a_heading_the_question_already_names_counts_once(self):
        # "revenue" is the Revenue topic's own name: it is a stated word here, not also a heading bonus, so the
        # passage with both of the question's topics outranks the one with only that word.
        doc = self.deck('Ledgerly', ['Revenue: $2M', 'Growth: 3x and strong traction'])
        self.assertEqual(self.pages(doc, 'revenue growth'), [2, 1])

    def test_equal_scores_come_back_in_document_order(self):
        # Stored out of order: equal scores come back in the document's order (DocumentChunk.Meta.ordering and a
        # stable sort), so /ask/ and /search/ list the same passages the same way.
        doc = DocumentSource.objects.create(uploaded_by=self.owner, filename='s.pdf', source_entity='Tidewell',
                                            document_type='pitch_deck', status='analyzed')
        _add_chunks(doc, [{'chunk_index': i, 'page_number': i + 1, 'section_title': '', 'raw_text': 'Revenue grew',
                           'token_count': 2} for i in (2, 0, 1)])
        self.assertEqual(self.pages(doc, 'revenue'), [1, 2, 3])

    def test_a_one_chunk_document_still_answers(self):
        doc = self.deck('Solo', ['Solo has revenue of $2M.'])
        self.assertEqual(self.pages(doc, 'revenue'), [1])
