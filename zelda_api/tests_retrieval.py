"""
Phase 1 Task 3: principal-scoped retrieval. Bypass tests that ship with it.

Built on AuthorizationFixture (tests_authorization), so the private
document, hidden field and Lite-gated finding are present: retrieval must
not be able to escape what the resolver authorizes, and must apply that
scope BEFORE ranking -- an unauthorized chunk may not even be scored.
"""
import ast
import inspect
import json
from unittest import mock

from django.urls import reverse

from zelda_api import retrieval as retrieval_module
from zelda_api.principal import PrincipalRequired
from zelda_api.retrieval import (
    MAX_TOP_K, ContextAssembler, RetrievalRefused, VectorRetriever, validate_top_k,
)
from zelda_api.tests_authorization import AuthorizationFixture
from zelda_api.vector_models import DocumentChunk


class _Retrieval(AuthorizationFixture):

    def setUp(self):
        super().setUp()
        # Give every fixture chunk a vector so the vector path, not just the
        # keyword fallback, is exercised.
        DocumentChunk.objects.update(embedding_vector=json.dumps([0.1] * 8))

    def texts(self, results):
        return sorted(r['text'] for r in results)


class NoPrincipalRefusesTests(_Retrieval):

    def test_retrieve_without_principal_refuses(self):
        for value in (None, self.users['a'], {'user_id': self.users['a'].pk}):
            with self.subTest(value=value), self.assertRaises(PrincipalRequired):
                VectorRetriever().retrieve(value, 'text', self.docs['a'])
            with self.subTest(value=value, scope='all'), self.assertRaises(PrincipalRequired):
                VectorRetriever().retrieve(value, 'text')

    def test_context_assembler_requires_a_principal(self):
        with self.assertRaises(PrincipalRequired):
            ContextAssembler().assemble_context(None, self.docs['a'])
        with self.assertRaises(PrincipalRequired):
            ContextAssembler().retrieve_for_category(None, self.docs['a'], 'Team')


class DocumentOutsideScopeRefusesTests(_Retrieval):

    def test_refuses_rather_than_returning_empty(self):
        cases = [('investor', 'a'), ('connected', 'a'), ('roleless', 'a'),
                 ('staff_as_investor', 'a'), ('owner_a', 'x'), ('investor', 'x')]
        for name, key in cases:
            with self.subTest(principal=name, doc=key), self.assertRaises(RetrievalRefused):
                VectorRetriever().retrieve(self.principals[name], 'text', self.docs[key])

    def test_owner_and_staff_retrieve(self):
        self.assertEqual(self.texts(VectorRetriever().retrieve(self.principals['owner_x'], 'text', self.docs['x'])),
                         ['text of x'])
        self.assertEqual(self.texts(VectorRetriever().retrieve(self.principals['staff'], 'text', self.docs['x'])),
                         ['text of x'])


class ScopeAppliedBeforeRankingTests(_Retrieval):
    """Unauthorized chunks are never loaded, scored or keyword-matched."""

    def scored_texts(self, name):
        scored = []
        original = retrieval_module.VectorRetriever._keyword_boost

        def record(retriever_self, query, text):
            scored.append(text)
            return original(retriever_self, query, text)

        with mock.patch.object(retrieval_module.VectorRetriever, '_keyword_boost', record):
            VectorRetriever(top_k=MAX_TOP_K).retrieve(self.principals[name], 'text of')
        return sorted(scored)

    def test_vector_path_scores_only_authorized_chunks(self):
        self.assertEqual(self.scored_texts('investor'), [])
        self.assertEqual(self.scored_texts('staff_as_investor'), [])
        self.assertEqual(self.scored_texts('owner_a'), ['text of a'])
        self.assertEqual(self.scored_texts('staff'), ['text of a', 'text of h', 'text of p', 'text of x'])

    def test_keyword_fallback_matches_only_authorized_chunks(self):
        with mock.patch.object(retrieval_module.embedding_engine, 'embed_text', return_value=None):
            for name, expected in (('investor', []), ('owner_a', ['text of a']), ('owner_x', ['text of x'])):
                with self.subTest(principal=name):
                    results = VectorRetriever(top_k=MAX_TOP_K).retrieve(self.principals[name], 'text')
                    self.assertEqual(self.texts(results), expected)

    def test_fallback_after_no_vectors_stays_scoped(self):
        DocumentChunk.objects.update(embedding_vector=None)
        results = VectorRetriever(top_k=MAX_TOP_K).retrieve(self.principals['owner_a'], 'text')
        self.assertEqual(self.texts(results), ['text of a'])

    def test_context_assembler_cites_only_authorized_pages(self):
        context = ContextAssembler().assemble_context(self.principals['owner_a'], self.docs['a'])
        cited = {r['text'] for topic in context['context_by_topic'].values() for r in topic['retrieved']}
        self.assertTrue(cited <= {'text of a'})


class TopKTests(_Retrieval):

    def test_validate_top_k(self):
        self.assertEqual(validate_top_k(None), 5)
        self.assertEqual(validate_top_k(1), 1)
        self.assertEqual(validate_top_k(MAX_TOP_K), MAX_TOP_K)
        for bad in (0, -1, MAX_TOP_K + 1, 10 ** 9, '5', 5.0, True, False, [5], {'n': 5}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_top_k(bad)

    def test_retriever_constructor_validates(self):
        with self.assertRaises(ValueError):
            VectorRetriever(top_k=10 ** 6)


class EndpointTests(_Retrieval):
    """The two views keep their answers: owner/staff 200, everyone else refused."""

    def post(self, user, name, doc_key, body):
        if user is not None:
            self.client.force_login(user)
        return self.client.post(reverse(name, args=[self.docs[doc_key].pk]),
                                data=json.dumps(body), content_type='application/json')

    def test_search_and_rag_boundaries(self):
        for name in ('zelda_api:document_search', 'zelda_api:document_rag'):
            with self.subTest(view=name):
                self.assertEqual(self.post(self.users['a'], name, 'a', {'query': 'text'}).status_code, 200)
                self.client.logout()
                self.assertEqual(self.post(self.staff, name, 'x', {'query': 'text'}).status_code, 200)
                self.client.logout()
                for stranger in (self.investor, self.connected, self.roleless, self.users['x']):
                    self.assertEqual(self.post(stranger, name, 'a', {'query': 'text'}).status_code, 403)
                    self.client.logout()
                self.assertIn(self.post(None, name, 'a', {'query': 'text'}).status_code, (401, 403))

    def test_owner_sees_only_their_chunks(self):
        response = self.post(self.users['a'], 'zelda_api:document_search', 'a', {'query': 'text'})
        self.assertEqual([r['text'] for r in response.json()['results']], ['text of a'])

    def test_rag_rejects_bad_top_k_before_retrieval(self):
        with mock.patch.object(retrieval_module.VectorRetriever, 'retrieve') as retrieve:
            for bad in ('abc', 0, 1000, True, None.__class__.__name__, [3]):
                with self.subTest(top_k=bad):
                    response = self.post(self.users['a'], 'zelda_api:document_rag', 'a', {'query': 'text', 'top_k': bad})
                    self.assertEqual(response.status_code, 400)
            retrieve.assert_not_called()

    def test_rag_honours_valid_top_k(self):
        response = self.post(self.users['a'], 'zelda_api:document_rag', 'a', {'query': 'text', 'top_k': 1})
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(response.json()['source_count'], 1)

    def test_non_string_query_is_a_400_not_a_500(self):
        for name in ('zelda_api:document_search', 'zelda_api:document_rag'):
            with self.subTest(view=name):
                self.assertEqual(self.post(self.users['a'], name, 'a', {'query': ['text']}).status_code, 400)

    def test_staff_viewing_as_investor_cannot_retrieve(self):
        self.client.force_login(self.investor)
        session = self.client.session
        session['impersonator_id'] = self.staff.pk
        session.save()
        for name in ('zelda_api:document_search', 'zelda_api:document_rag'):
            with self.subTest(view=name):
                response = self.client.post(reverse(name, args=[self.docs['a'].pk]),
                                            data=json.dumps({'query': 'text'}), content_type='application/json')
                self.assertNotEqual(response.status_code, 200)
                self.assertNotIn('text of a', response.content.decode())


# -- structural guard (module-local; Task 4 extends this repo-wide) -------------

def chunk_reads_outside_candidates(source):
    """`DocumentChunk.objects` uses in `source` outside VectorRetriever._candidates."""
    tree = ast.parse(source)
    allowed = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_candidates':
            allowed.update(id(n) for n in ast.walk(node))
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and node.attr == 'objects'
                and isinstance(node.value, ast.Name) and node.value.id == 'DocumentChunk'
                and id(node) not in allowed):
            found.append(node.lineno)
    return found


class StructuralTests(_Retrieval):

    def test_chunks_are_read_only_through_candidates(self):
        self.assertEqual(chunk_reads_outside_candidates(inspect.getsource(retrieval_module)), [])

    def test_the_scan_can_fail(self):
        source = inspect.getsource(retrieval_module)
        mutated = source.replace(
            "        chunks = list(candidates.filter(q_objects)",
            "        chunks = list(DocumentChunk.objects.all().filter(q_objects)",
        )
        self.assertNotEqual(mutated, source, 'mutation did not apply')
        self.assertTrue(chunk_reads_outside_candidates(mutated))
