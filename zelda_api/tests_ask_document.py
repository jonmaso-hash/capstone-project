"""
RA-114: a question about a document, sent to Ask Zelda (/api/v1/zelda/ask/), got the marketplace fallback.

Cause: the view read only `q` and the requester's role. It had no document input, so every question went to the
marketplace query extraction, which finds no founder/seller criteria in "How much has ManyChat raised?" and answers
"I couldn't find specific search criteria in that ..." (memo 104's run, Q1-Q7).

A question sent with a `document_id` is now answered from that document's own text through the same principal-scoped
retrieval as /documents/<id>/search/: the same authorization (owner and staff; everyone else 403), only that
document's chunks, `no_relevant_evidence` said outright, and no model call. Without a `document_id` the view is the
marketplace search it was. Built on AuthorizationFixture, so the private document, the hidden document and the
connected investor are present.
"""
import json
from unittest import mock

from django.urls import reverse

from zelda_api.tests_authorization import AuthorizationFixture
from zelda_api.vector_models import DocumentChunk

EXTRACTION = 'zelda_api.intelligence_pipeline._call_claude_for_query_extraction'
FALLBACK = "I couldn't find specific search criteria"
RAISED = 'Pitch Deck Hunt lists AuthzCo A as a Series A deck with $23.1M raised.'


class _Ask(AuthorizationFixture):

    def setUp(self):
        super().setUp()
        DocumentChunk.objects.create(document=self.docs['a'], chunk_index=1, page_number=2, token_count=12, raw_text=RAISED)
        # Another document holds the same words: it must never answer a question about deck A.
        DocumentChunk.objects.create(document=self.docs['p'], chunk_index=1, page_number=2, token_count=12,
                                     raw_text='AuthzCo P raised $9M in its Series A.')
        DocumentChunk.objects.update(embedding_vector=json.dumps([0.1] * 8))

    def ask(self, user, body, extraction=None):
        self.client.logout()
        if user is not None:
            self.client.force_login(user)
        with mock.patch(EXTRACTION, return_value=extraction or {'constraints': []}) as extract:
            response = self.client.post(reverse('zelda_api:ask'), data=json.dumps(body), content_type='application/json')
        return response, extract


class DocumentQuestionTests(_Ask):

    def test_a_document_question_is_answered_from_the_document(self):
        """The RA-114 reproduction: memo 104's Q1, asked about its document."""
        response, extract = self.ask(self.users['a'], {'q': 'How much has AuthzCo A raised?', 'document_id': self.docs['a'].pk})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotIn(FALLBACK, data['response'])
        self.assertEqual(data['document_id'], self.docs['a'].pk)
        self.assertFalse(data['no_relevant_evidence'])
        self.assertEqual([(e['page'], e['text']) for e in data['evidence']], [(2, RAISED)])
        self.assertEqual(data['results'], [])            # no marketplace cards
        extract.assert_not_called()                     # no model call

    def test_the_answer_is_the_documents_own_text_never_composed(self):
        response, _ = self.ask(self.users['a'], {'q': 'How much has AuthzCo A raised?', 'document_id': self.docs['a'].pk})
        data = response.json()
        self.assertNotIn('$23.1M', data['response'])     # the figure is only in the cited excerpt
        for item in data['evidence']:
            self.assertEqual(set(item), {'chunk_id', 'page', 'section', 'text', 'relevance'})
            self.assertEqual(DocumentChunk.objects.get(pk=item['chunk_id']).document_id, self.docs['a'].pk)

    def test_insufficient_evidence_is_said_outright(self):
        response, extract = self.ask(self.users['a'], {'q': 'What did the CEO say on the latest earnings call?',
                                                       'document_id': self.docs['a'].pk})
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual((data['evidence'], data['no_relevant_evidence']), ([], True))
        self.assertIn('No relevant evidence', data['response'])
        self.assertNotIn(FALLBACK, data['response'])
        extract.assert_not_called()

    def test_only_that_documents_chunks_are_used(self):
        response, _ = self.ask(self.users['a'], {'q': 'Series A raised', 'document_id': self.docs['a'].pk})
        evidence = response.json()['evidence']
        self.assertIn(RAISED, [e['text'] for e in evidence])
        self.assertEqual({DocumentChunk.objects.get(pk=e['chunk_id']).document_id for e in evidence}, {self.docs['a'].pk})

    def test_staff_who_may_read_every_document_get_only_the_one_asked_about(self):
        """Staff may read deck P's text too, which holds the same words: the question about deck A still uses deck
        A alone (an owner cannot tell a document-scoped retrieval from one over all they may read)."""
        response, _ = self.ask(self.staff, {'q': 'Series A raised', 'document_id': self.docs['a'].pk})
        evidence = response.json()['evidence']
        self.assertIn(RAISED, [e['text'] for e in evidence])
        self.assertEqual({DocumentChunk.objects.get(pk=e['chunk_id']).document_id for e in evidence}, {self.docs['a'].pk})


class DocumentAuthorizationTests(_Ask):
    """The same rule as /documents/<id>/search/: text_permitted. Refused before retrieval, with no text."""

    def test_owner_and_staff(self):
        self.assertEqual(self.ask(self.users['a'], {'q': 'text', 'document_id': self.docs['a'].pk})[0].status_code, 200)
        self.assertEqual(self.ask(self.staff, {'q': 'text', 'document_id': self.docs['x'].pk})[0].status_code, 200)

    def test_everyone_else_is_refused_without_text(self):
        for name, user, key in (('investor', self.investor, 'a'), ('connected', self.connected, 'a'),
                                ('roleless', self.roleless, 'a'), ('owner_x', self.users['x'], 'a'),
                                ('owner_a', self.users['a'], 'x')):
            with self.subTest(principal=name, doc=key):
                response, extract = self.ask(user, {'q': 'How much was raised? text', 'document_id': self.docs[key].pk})
                self.assertEqual(response.status_code, 403)
                self.assertNotIn('text of', response.content.decode())
                self.assertNotIn('23.1M', response.content.decode())
                extract.assert_not_called()

    def test_anonymous_is_refused(self):
        response, _ = self.ask(None, {'q': 'text', 'document_id': self.docs['a'].pk})
        self.assertIn(response.status_code, (401, 403))

    def test_staff_viewing_as_investor_cannot_ask_the_document(self):
        self.client.force_login(self.investor)
        session = self.client.session
        session['impersonator_id'] = self.staff.pk
        session.save()
        with mock.patch(EXTRACTION) as extract:
            response = self.client.post(reverse('zelda_api:ask'), content_type='application/json',
                                        data=json.dumps({'q': 'raised text', 'document_id': self.docs['a'].pk}))
        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn('text of a', response.content.decode())
        extract.assert_not_called()

    def test_retrieval_is_never_reached_when_refused(self):
        with mock.patch('zelda_api.retrieval.VectorRetriever.retrieve') as retrieve:
            response, _ = self.ask(self.investor, {'q': 'raised', 'document_id': self.docs['a'].pk})
        self.assertEqual(response.status_code, 403)
        retrieve.assert_not_called()


class DocumentInputTests(_Ask):

    def test_a_bad_document_id_is_a_400_and_a_missing_one_a_404(self):
        for bad in ('abc', '7', True, False, 1.5, [1], {'id': 1}):
            with self.subTest(document_id=bad):
                response, extract = self.ask(self.users['a'], {'q': 'raised', 'document_id': bad})
                self.assertEqual(response.status_code, 400)
                extract.assert_not_called()
        response, _ = self.ask(self.users['a'], {'q': 'raised', 'document_id': 10 ** 9})
        self.assertEqual(response.status_code, 404)

    def test_a_document_question_needs_a_question(self):
        for q in ('', '   ', ['raised'], None):
            with self.subTest(q=q):
                response, extract = self.ask(self.users['a'], {'q': q, 'document_id': self.docs['a'].pk})
                self.assertEqual(response.status_code, 400)
                extract.assert_not_called()


class MarketplaceUnchangedTests(_Ask):
    """Without a document_id, /ask/ is the marketplace search it was."""

    def test_no_document_id_still_goes_to_the_marketplace(self):
        for body in ({'q': 'How much has AuthzCo A raised?'}, {'q': 'How much has AuthzCo A raised?', 'document_id': None}):
            with self.subTest(body=body):
                response, extract = self.ask(self.users['a'], body)
                self.assertEqual(response.status_code, 200)
                self.assertIn(FALLBACK, response.json()['response'])
                self.assertNotIn('evidence', response.json())
                extract.assert_called_once()

    def test_a_marketplace_question_still_finds_founders(self):
        extraction = {'constraints': [{'field': 'stage', 'qualifier': 'exact', 'value': 'Seed'}]}
        response, extract = self.ask(self.investor, {'q': 'seed founders', 'currency': 'USD'}, extraction=extraction)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Found', response.json()['response'])
        self.assertTrue(response.json()['results'])
        extract.assert_called_once()
