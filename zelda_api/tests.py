"""
Regression coverage for a real bug fixed this session: when the Anthropic
API call inside _call_claude_for_memo/_call_claude_for_valuation failed
(e.g. exhausted credits), the exception was swallowed into a dict under
the wrong key (e.g. 'executive_summary' instead of 'error'), so the
calling code's `if 'error' in result: raise` check never fired — the
pipeline would silently write a "successful" memo/report whose content
was literally the error message, and mark the document 'analyzed'.

NOTE: zelda_api/test_views.py is NOT a test file despite its name — it's
a real production view (SandboxScanView). Don't confuse it with this file.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from .intelligence_pipeline import ZeldaIntelligencePipelineV2
from .vector_models import DocumentSource, IntelligenceMemo, BusinessValuationReport

User = get_user_model()


class AnthropicFailureDetectionTests(TestCase):
    """
    Simulates a real Anthropic API failure (mocked, not dependent on the
    account's actual credit balance) and confirms the pipeline correctly
    detects and propagates it instead of faking success.
    """

    def setUp(self):
        self.user = User.objects.create_user('doc_owner', password='x')
        self.pipeline = ZeldaIntelligencePipelineV2()

    def _doc(self, document_type='pitch_deck'):
        return DocumentSource.objects.create(
            filename='test.pdf', source_entity='Test Co',
            uploaded_by=self.user, document_type=document_type,
        )

    @mock.patch('anthropic.Anthropic')
    def test_memo_generation_failure_returns_error_key(self, mock_anthropic_cls):
        mock_anthropic_cls.return_value.messages.create.side_effect = Exception('simulated API failure')
        doc = self._doc()

        result = self.pipeline._generate_memo(doc, {'confidence': 0.5})

        self.assertIn('error', result)
        self.assertIn('simulated API failure', result['error'])

    @mock.patch('anthropic.Anthropic')
    def test_memo_generation_failure_does_not_create_fake_memo(self, mock_anthropic_cls):
        mock_anthropic_cls.return_value.messages.create.side_effect = Exception('simulated API failure')
        doc = self._doc()

        self.pipeline._generate_memo(doc, {'confidence': 0.5})

        # Before the fix, this would exist with 'simulated API failure' baked
        # into executive_summary as if it were real memo content.
        self.assertFalse(IntelligenceMemo.objects.filter(document=doc).exists())

    @mock.patch('anthropic.Anthropic')
    def test_valuation_generation_failure_returns_error_key(self, mock_anthropic_cls):
        mock_anthropic_cls.return_value.messages.create.side_effect = Exception('simulated API failure')
        doc = self._doc(document_type='business_valuation')

        result = self.pipeline._generate_valuation_report(doc, {'confidence': 0.5})

        self.assertIn('error', result)
        self.assertIn('simulated API failure', result['error'])

    @mock.patch('anthropic.Anthropic')
    def test_valuation_generation_failure_does_not_create_fake_report(self, mock_anthropic_cls):
        mock_anthropic_cls.return_value.messages.create.side_effect = Exception('simulated API failure')
        doc = self._doc(document_type='business_valuation')

        self.pipeline._generate_valuation_report(doc, {'confidence': 0.5})

        self.assertFalse(BusinessValuationReport.objects.filter(document=doc).exists())

    def test_memo_generation_succeeds_when_claude_returns_valid_json(self):
        """Sanity check the mock itself is exercising the real code path, not just always-erroring."""
        fake_response = mock.Mock()
        fake_response.content = [mock.Mock(text='{"executive_summary": "Great company.", "recommendation": "STRONG_INVEST"}')]

        with mock.patch('anthropic.Anthropic') as mock_anthropic_cls:
            mock_anthropic_cls.return_value.messages.create.return_value = fake_response
            doc = self._doc()
            result = self.pipeline._generate_memo(doc, {'confidence': 0.5})

        self.assertNotIn('error', result)
        memo = IntelligenceMemo.objects.get(document=doc)
        self.assertEqual(memo.executive_summary, 'Great company.')

    @mock.patch('zelda_api.intelligence_pipeline.logger')
    def test_successful_call_logs_token_usage(self, mock_logger):
        fake_response = mock.Mock()
        fake_response.content = [mock.Mock(text='{"executive_summary": "Great company.", "recommendation": "STRONG_INVEST"}')]
        fake_response.usage.input_tokens = 1234
        fake_response.usage.output_tokens = 567

        with mock.patch('anthropic.Anthropic') as mock_anthropic_cls:
            mock_anthropic_cls.return_value.messages.create.return_value = fake_response
            doc = self._doc()
            self.pipeline._generate_memo(doc, {'confidence': 0.5})

        logged_messages = [call.args[0] for call in mock_logger.info.call_args_list]
        self.assertTrue(any('input_tokens=1234' in msg and 'output_tokens=567' in msg for msg in logged_messages))
