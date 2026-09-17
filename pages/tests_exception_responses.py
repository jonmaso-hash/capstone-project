"""
Internal exception text never reaches a response (PR #57).

These routed views put str(e) -- or a message built from it -- into what the
caller receives: database errors, SDK errors, parser internals. Each now
answers with a generic message and keeps the detail in the server log.

Every test forces a failure carrying SECRET, asserts SECRET is absent from the
response, and asserts it was logged -- the log assertion also proves the forced
failure really happened, so a response can't pass by failing somewhere else.
"""
import json
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from matchmaking.models import Application, InvestorApplication
from matchmaking.tests import _mock_embedding_generation
from zelda_api.models import AnalysisCreditCharge
from zelda_api.vector_models import DocumentSource

User = get_user_model()
SECRET = 'SECRET-INTERNAL-DETAIL-7f3a'


class _Leaks(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('leak_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='Northwind Grid', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.investor_user = User.objects.create_user('leak_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com', company_name='Harbor Capital',
            investment_focus='SaaS', investment_stage='Seed',
        )

    def assertSecretOnlyInTheLog(self, response, logs):
        self.assertNotIn(SECRET, response.content.decode())
        logged = [
            r for r in logs.records
            if SECRET in r.getMessage() or (r.exc_info and SECRET in str(r.exc_info[1]))
        ]
        self.assertTrue(logged, 'the forced failure was not logged')


class ExceptionTextStaysInTheLogTests(_Leaks):

    def test_privacy_and_direct_message_toggles(self):
        self.client.force_login(self.founder_user)
        for url_name, logger in (
            ('accounts:toggle_privacy', 'accounts.views'),
            ('accounts:toggle_dm', 'accounts.views'),
            ('matchmaking:toggle_privacy', 'matchmaking.views'),
        ):
            with self.subTest(url=url_name):
                with self.assertLogs(logger, level='ERROR') as logs, \
                        mock.patch.object(Application.objects, 'filter', side_effect=RuntimeError(SECRET)):
                    response = self.client.post(
                        reverse(url_name), data=json.dumps({'is_private': True, 'dm_enabled': True}),
                        content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertSecretOnlyInTheLog(response, logs)

    def test_introduction_actions(self):
        self.client.force_login(self.investor_user)
        for url_name in ('matchmaking:connection_action', 'matchmaking:acquisition_connection_action'):
            with self.subTest(url=url_name):
                with self.assertLogs('matchmaking.views', level='ERROR') as logs, \
                        mock.patch('matchmaking.views.get_object_or_404', side_effect=RuntimeError(SECRET)):
                    response = self.client.post(
                        reverse(url_name), data=json.dumps({'id': 1, 'action': 'ACCEPTED'}),
                        content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertSecretOnlyInTheLog(response, logs)

    @override_settings(STREAM_API_KEY='stream-key', STREAM_API_SECRET='stream-secret')
    def test_chat_token(self):
        self.client.force_login(self.founder_user)
        with self.assertLogs('accounts.views', level='ERROR') as logs, \
                mock.patch('accounts.views.StreamChat', side_effect=RuntimeError(SECRET)):
            response = self.client.get(reverse('accounts:stream_token'))
        self.assertEqual(response.status_code, 500)
        self.assertSecretOnlyInTheLog(response, logs)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_starting_a_paid_analysis(self):
        # The failure is forced after the deck has been read: since D9 an
        # extraction failure is answered as an unreadable deck (see the next
        # test), so this is what exercises the step's own error handler.
        self.founder.pitch_deck = SimpleUploadedFile('deck.pdf', b'%PDF-1.4 deck', content_type='application/pdf')
        self.founder.save()
        self.client.force_login(self.investor_user)
        with self.assertLogs('zelda_api.views', level='WARNING') as logs, \
                mock.patch('zelda_api.quotas.has_credits_for', return_value=True), \
                mock.patch('zelda_api.utils._extract_pdf_text', return_value=('Deck text about the product.', 3)), \
                mock.patch.object(DocumentSource.objects, 'create', side_effect=RuntimeError(SECRET)):
            response = self.client.post(
                reverse('zelda_api:analyze_founder_confirm', args=[self.founder_user.username]))
        self.assertEqual(response.status_code, 500)
        self.assertSecretOnlyInTheLog(response, logs)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_an_extraction_failure_on_a_paid_analysis_is_refused_without_leaking(self):
        # The shared extractor (zelda_api/utils.py::extract_text_from_file) logs
        # the failure and returns no text, so the step refuses the deck as
        # unreadable: the detail stays in the log and nothing is charged.
        self.founder.pitch_deck = SimpleUploadedFile('deck.pdf', b'%PDF-1.4 deck', content_type='application/pdf')
        self.founder.save()
        self.client.force_login(self.investor_user)
        with self.assertLogs('zelda_api.utils', level='ERROR') as logs, \
                mock.patch('zelda_api.quotas.has_credits_for', return_value=True), \
                mock.patch('zelda_api.utils._extract_pdf_text', side_effect=RuntimeError(SECRET)):
            response = self.client.post(
                reverse('zelda_api:analyze_founder_confirm', args=[self.founder_user.username]))
        self.assertEqual(response.status_code, 422)
        self.assertSecretOnlyInTheLog(response, logs)
        self.assertFalse(DocumentSource.objects.filter(uploaded_by=self.founder_user).exists())
        self.assertFalse(AnalysisCreditCharge.objects.exists())

    def test_ingesting_a_document(self):
        self.client.force_login(self.founder_user)
        upload = SimpleUploadedFile('deck.pdf', b'%PDF-1.4 deck', content_type='application/pdf')
        with self.assertLogs('zelda_api.pipeline_views', level='ERROR') as logs, \
                mock.patch('zelda_api.quotas.has_credits_for', return_value=True), \
                mock.patch('zelda_api.utils.extract_text_from_file', side_effect=RuntimeError(SECRET)):
            response = self.client.post(
                reverse('zelda_api:document_ingest'), {'file': upload, 'document_type': 'pitch_deck'})
        self.assertEqual(response.status_code, 500)
        self.assertSecretOnlyInTheLog(response, logs)

    def test_pitch_analysis_parse_failure(self):
        self.client.force_login(self.founder_user)
        deck = SimpleUploadedFile('deck.pdf', b'%PDF-1.4 deck', content_type='application/pdf')
        with self.assertLogs('zelda_api.utils', level='ERROR') as logs, \
                mock.patch('zelda_api.utils._extract_pdf_text', side_effect=RuntimeError(SECRET)):
            response = self.client.post(reverse('zelda_api:pitch_analysis'), {'pitch_deck': deck})
        self.assertEqual(response.status_code, 422)
        self.assertSecretOnlyInTheLog(response, logs)


class IntelligenceMemoEndpointRemovedTests(_Leaks):
    """
    The intelligence-memo endpoint, once covered above for leaking its compile
    error, is removed: it returned boilerplate ("engagement_score": 85, fixed
    recommendations) as if it were analysis, and nothing called it. There is
    no response left to leak from.
    """

    def test_the_intelligence_memo_endpoint_is_gone(self):
        self.client.force_login(self.founder_user)
        with self.assertRaises(NoReverseMatch):
            reverse('zelda_api:intelligence_memo')
        response = self.client.get('/api/v1/zelda/intelligence-memo/')
        self.assertEqual(response.status_code, 404)

    def test_the_memo_compiler_is_gone(self):
        import zelda_api.utils
        for name in (
            'compile_executive_intelligence_memo', '_generate_executive_summary',
            '_generate_market_position', '_generate_recommendations',
            '_generate_metrics_dashboard', '_calculate_completeness',
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(zelda_api.utils, name))
