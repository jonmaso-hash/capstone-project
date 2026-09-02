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
import re
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .intelligence_pipeline import ZeldaIntelligencePipelineV2
from .vector_models import DocumentSource, IntelligenceMemo, BusinessValuationReport
from .circuit_breaker import (
    call_with_breaker, is_open, record_failure, record_success,
    CircuitOpenError, FAILURE_THRESHOLD, _opened_until_key,
)

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

    def test_memo_generation_persists_new_structured_fields(self):
        """intelligence_pipeline.py structured-fields pass: Key Strengths/
        Concerns/What Would Change the Decision/Bull-Base-Bear/Zelda
        Advantage all get persisted onto the memo when Claude returns them."""
        import json
        payload = {
            'executive_summary': 'Great company.',
            'recommendation': 'STRONG_INVEST',
            'key_strengths': 'Strong ARR growth.',
            'key_concerns': 'Thin team disclosure.',
            'what_would_change_decision': 'A signed LOI from an anchor customer.',
            'bull_case': 'Bull case text.',
            'base_case': 'Base case text.',
            'bear_case': 'Bear case text.',
            'zelda_advantage': 'Cross-checked claim X against Y; consistent.',
        }
        fake_response = mock.Mock()
        fake_response.content = [mock.Mock(text=json.dumps(payload))]

        with mock.patch('anthropic.Anthropic') as mock_anthropic_cls:
            mock_anthropic_cls.return_value.messages.create.return_value = fake_response
            doc = self._doc()
            result = self.pipeline._generate_memo(doc, {'confidence': 0.5})

        self.assertNotIn('error', result)
        memo = IntelligenceMemo.objects.get(document=doc)
        self.assertEqual(memo.key_strengths, 'Strong ARR growth.')
        self.assertEqual(memo.key_concerns, 'Thin team disclosure.')
        self.assertEqual(memo.what_would_change_decision, 'A signed LOI from an anchor customer.')
        self.assertEqual(memo.bull_case, 'Bull case text.')
        self.assertEqual(memo.base_case, 'Base case text.')
        self.assertEqual(memo.bear_case, 'Bear case text.')
        self.assertEqual(memo.zelda_advantage, 'Cross-checked claim X against Y; consistent.')

    def test_memo_generation_defaults_new_fields_to_blank_when_claude_omits_them(self):
        """Backward compatibility: a response missing the new keys (e.g. an
        older cached response, or a model that ignores the new instructions)
        must not error — new fields just stay blank, never fabricated."""
        fake_response = mock.Mock()
        fake_response.content = [mock.Mock(text='{"executive_summary": "Great company.", "recommendation": "STRONG_INVEST"}')]

        with mock.patch('anthropic.Anthropic') as mock_anthropic_cls:
            mock_anthropic_cls.return_value.messages.create.return_value = fake_response
            doc = self._doc()
            result = self.pipeline._generate_memo(doc, {'confidence': 0.5})

        self.assertNotIn('error', result)
        memo = IntelligenceMemo.objects.get(document=doc)
        self.assertEqual(memo.key_strengths, '')
        self.assertEqual(memo.zelda_advantage, '')

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


class CircuitBreakerTests(TestCase):
    """
    zelda_api.circuit_breaker: prevents worker threads from piling up
    against a degraded Claude API by short-circuiting after consecutive
    failures, rather than letting every request attempt (and wait on) a
    doomed network call.
    """

    def setUp(self):
        cache.clear()

    def test_closed_by_default(self):
        self.assertFalse(is_open('test_circuit_default'))

    def test_opens_after_threshold_consecutive_failures(self):
        def always_fails():
            raise ValueError('boom')

        for _ in range(FAILURE_THRESHOLD):
            with self.assertRaises(ValueError):
                call_with_breaker('test_circuit_opens', always_fails)

        self.assertTrue(is_open('test_circuit_opens'))

    def test_open_circuit_short_circuits_without_calling_func(self):
        for _ in range(FAILURE_THRESHOLD):
            record_failure('test_circuit_short')
        self.assertTrue(is_open('test_circuit_short'))

        calls = []

        def func():
            calls.append(1)
            return 'ok'

        with self.assertRaises(CircuitOpenError):
            call_with_breaker('test_circuit_short', func)
        self.assertEqual(calls, [])  # func must never actually run while open

    def test_success_resets_failure_count(self):
        record_failure('test_circuit_reset')
        record_failure('test_circuit_reset')
        call_with_breaker('test_circuit_reset', lambda: 'ok')  # success clears the counter

        def always_fails():
            raise ValueError('boom')

        # Takes a full new threshold's worth of failures to open again, not
        # just the 1 remaining from before the reset.
        for _ in range(FAILURE_THRESHOLD - 1):
            with self.assertRaises(ValueError):
                call_with_breaker('test_circuit_reset', always_fails)
        self.assertFalse(is_open('test_circuit_reset'))

    def test_half_open_after_cooldown_allows_trial_call(self):
        for _ in range(FAILURE_THRESHOLD):
            record_failure('test_circuit_half_open')
        self.assertTrue(is_open('test_circuit_half_open'))

        # Simulate the cooldown having already elapsed.
        cache.set(_opened_until_key('test_circuit_half_open'), 0, 60)

        self.assertFalse(is_open('test_circuit_half_open'))
        result = call_with_breaker('test_circuit_half_open', lambda: 'ok')
        self.assertEqual(result, 'ok')
        self.assertFalse(is_open('test_circuit_half_open'))


class ICMemoTests(TestCase):
    """
    IC Memo Generator (zelda_api/ic_memo.py) — a synthesis/export layer
    over existing memo/truth-delta/valuation/deck-analytics data, gated
    tighter than the existing DocumentMemoView (owner + staff + only
    ACCEPTED-connection investors, not any authenticated investor).
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

        from matchmaking.models import Application, InvestorApplication
        self.founder_user = User.objects.create_user('ic_memo_founder', password='x')
        self.application = Application.objects.create(
            user=self.founder_user, company_name='MemoCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', raising_amount=500000,
        )
        self.investor_user = User.objects.create_user('ic_memo_investor', password='x')
        self.investor_app = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.staff_user = User.objects.create_user('ic_memo_staff', password='x', is_staff=True)
        self.stranger_user = User.objects.create_user('ic_memo_stranger', password='x')

    def _make_pitch_deck_doc(self, with_memo=True):
        doc = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='MemoCo',
            document_type='pitch_deck', status='analyzed',
        )
        if with_memo:
            IntelligenceMemo.objects.create(
                document=doc,
                executive_summary='We build developer tools.',
                investment_thesis='Strong team, growing market.',
                recommendation='NEEDS_REVIEW',
                completeness_score=0.8,
                citations_count=3,
            )
        return doc

    # --- can_view_ic_memo ---

    def test_owner_can_view(self):
        from .ic_memo import can_view_ic_memo
        self.assertTrue(can_view_ic_memo(self.founder_user, self.application))

    def test_staff_can_view(self):
        from .ic_memo import can_view_ic_memo
        self.assertTrue(can_view_ic_memo(self.staff_user, self.application))

    def test_accepted_connection_investor_can_view(self):
        from .ic_memo import can_view_ic_memo
        from matchmaking.models import Connection
        Connection.objects.create(
            investor=self.investor_app, founder=self.application, status='ACCEPTED', initiated_by='INVESTOR',
        )
        self.assertTrue(can_view_ic_memo(self.investor_user, self.application))

    def test_pending_connection_investor_cannot_view(self):
        from .ic_memo import can_view_ic_memo
        from matchmaking.models import Connection
        Connection.objects.create(
            investor=self.investor_app, founder=self.application, status='PENDING', initiated_by='INVESTOR',
        )
        self.assertFalse(can_view_ic_memo(self.investor_user, self.application))

    def test_unrelated_investor_cannot_view(self):
        from .ic_memo import can_view_ic_memo
        self.assertFalse(can_view_ic_memo(self.investor_user, self.application))

    def test_stranger_cannot_view(self):
        from .ic_memo import can_view_ic_memo
        self.assertFalse(can_view_ic_memo(self.stranger_user, self.application))

    # --- ic_memo_unlocked ---
    # IC Memo content is a founder-controlled asset: gated on the FOUNDER's
    # own Premium, not the viewing investor's, so a founder can't ask to be
    # connected and have investors keep consuming it for free forever.

    def test_unlocked_false_for_non_premium_founder(self):
        from .ic_memo import ic_memo_unlocked
        self.assertFalse(ic_memo_unlocked(self.founder_user, self.application))

    def test_unlocked_true_for_premium_founder(self):
        from .ic_memo import ic_memo_unlocked
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        self.assertTrue(ic_memo_unlocked(self.founder_user, self.application))

    def test_unlocked_true_for_staff_regardless_of_premium(self):
        from .ic_memo import ic_memo_unlocked
        self.assertFalse(self.application.is_premium)
        self.assertTrue(ic_memo_unlocked(self.staff_user, self.application))

    def test_unlocked_false_for_connected_investor_when_founder_not_premium(self):
        from .ic_memo import ic_memo_unlocked
        self.assertFalse(ic_memo_unlocked(self.investor_user, self.application))

    def test_unlocked_true_for_connected_investor_when_founder_premium(self):
        from .ic_memo import ic_memo_unlocked
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        # Deliberately not gated on the investor's own premium status.
        self.assertFalse(self.investor_app.is_premium)
        self.assertTrue(ic_memo_unlocked(self.investor_user, self.application))

    # --- build_ic_memo_context ---

    def test_context_handles_missing_memo_gracefully(self):
        from .ic_memo import build_ic_memo_context
        context = build_ic_memo_context(self.application)
        self.assertIsNone(context['memo_sections'])
        self.assertIsNone(context['truth_delta'])
        self.assertIsNone(context['valuation'])
        self.assertEqual(context['company_name'], 'MemoCo')

    def test_context_assembles_memo_sections_when_present(self):
        from .ic_memo import build_ic_memo_context
        self._make_pitch_deck_doc(with_memo=True)
        context = build_ic_memo_context(self.application)
        self.assertIsNotNone(context['memo_sections'])
        labels = [s['label'] for s in context['memo_sections']]
        self.assertIn('Executive Summary', labels)
        self.assertIn('Investment Thesis', labels)
        # Sections with blank text (never set) should be omitted, not shown empty.
        self.assertNotIn('Problem & Solution', labels)
        self.assertEqual(context['memo_meta']['citations_count'], 3)

    def test_context_includes_truth_delta_when_present(self):
        from .ic_memo import build_ic_memo_context
        from .truth_delta_models import TruthDeltaReport
        doc = self._make_pitch_deck_doc(with_memo=True)
        TruthDeltaReport.objects.create(document=doc, overall_truth_score=85.0, summary='Looks consistent.')
        context = build_ic_memo_context(self.application)
        self.assertEqual(context['truth_delta']['overall_truth_score'], 85.0)

    def test_markdown_renders_without_error_for_bare_founder(self):
        from .ic_memo import build_ic_memo_context, render_ic_memo_markdown
        context = build_ic_memo_context(self.application)
        markdown_text = render_ic_memo_markdown(context)
        self.assertIn('MemoCo', markdown_text)
        self.assertIn('No intelligence memo has been generated', markdown_text)

    # --- views ---

    def test_html_view_shows_lite_tier_for_owner_when_not_premium(self):
        doc = self._make_pitch_deck_doc(with_memo=True)
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('zelda_api:ic_memo', args=[doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Zelda Lite Memo')
        self.assertContains(response, 'Upgrade to Zelda AI')
        # Investment Thesis is a Lite-tier section...
        self.assertContains(response, 'Strong team, growing market.')
        # ...but the deeper sections (Executive Summary, etc.) are Zelda AI-only.
        self.assertNotContains(response, 'We build developer tools.')

    def test_html_view_returns_full_memo_for_premium_owner(self):
        doc = self._make_pitch_deck_doc(with_memo=True)
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('zelda_api:ic_memo', args=[doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'We build developer tools.')

    def test_structured_fields_split_between_lite_and_full(self):
        """
        Key Strengths/Concerns/What Would Change the Decision are Zelda
        Lite; Bull/Base/Bear and Zelda Advantage are Zelda AI-only — the
        intelligence_pipeline.py structured-fields pass.

        Asserts against build_ic_memo_context's section labels directly
        (not raw HTTP response text) for the exclusion checks — the global
        Zelda sidebar widget included on every authenticated page carries
        its own hardcoded loadMemo() section labels (including the literal
        strings "Bull Case" and "Zelda Advantage"), which would false-
        positive an HTML-substring assertion regardless of memo tier.
        """
        from .ic_memo import build_ic_memo_context
        doc = self._make_pitch_deck_doc(with_memo=False)
        IntelligenceMemo.objects.create(
            document=doc,
            executive_summary='We build developer tools.',
            investment_thesis='Strong team, growing market.',
            key_strengths='Disclosed $2M ARR with 120% net revenue retention.',
            key_concerns='No customer concentration data disclosed.',
            what_would_change_decision='Audited financials showing gross margin.',
            bull_case='If retention holds, this is a durable, capital-efficient business.',
            base_case='Growth continues at the current disclosed pace.',
            bear_case='Customer concentration risk is entirely unknown.',
            zelda_advantage='Cross-checked ARR claim against the disclosed cohort data; no contradiction found.',
            recommendation='NEEDS_REVIEW', completeness_score=0.8, citations_count=3,
        )

        lite_context = build_ic_memo_context(self.application, tier='lite')
        lite_labels = [s['label'] for s in lite_context['memo_sections']]
        self.assertIn('Key Strengths', lite_labels)
        self.assertIn('Key Concerns', lite_labels)
        self.assertIn('What Would Change the Decision', lite_labels)
        self.assertNotIn('Bull Case', lite_labels)
        self.assertNotIn('Base Case', lite_labels)
        self.assertNotIn('Bear Case', lite_labels)
        self.assertNotIn('Zelda Advantage', lite_labels)
        self.assertNotIn('Executive Summary', lite_labels)

        full_context = build_ic_memo_context(self.application, tier='full')
        full_labels = [s['label'] for s in full_context['memo_sections']]
        self.assertIn('Bull Case', full_labels)
        self.assertIn('Base Case', full_labels)
        self.assertIn('Bear Case', full_labels)
        self.assertIn('Zelda Advantage', full_labels)

        # Content-level check via the real page render — these exact
        # sentences are unique to this test's fixture data, unlike the
        # generic section labels above, so a substring match here can't
        # collide with the sidebar widget's own hardcoded strings.
        self.client.force_login(self.founder_user)
        lite_response = self.client.get(reverse('zelda_api:ic_memo', args=[doc.id]))
        self.assertContains(lite_response, 'Disclosed $2M ARR with 120% net revenue retention.')
        self.assertNotContains(lite_response, 'If retention holds, this is a durable')
        self.assertNotContains(lite_response, 'Cross-checked ARR claim')

        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        full_response = self.client.get(reverse('zelda_api:ic_memo', args=[doc.id]))
        self.assertContains(full_response, 'If retention holds, this is a durable')
        self.assertContains(full_response, 'Cross-checked ARR claim')

    def test_html_view_returns_404_for_unrelated_investor(self):
        doc = self._make_pitch_deck_doc(with_memo=True)
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('zelda_api:ic_memo', args=[doc.id]))
        self.assertEqual(response.status_code, 404)

    def test_html_view_shows_lite_tier_for_connected_investor_when_founder_not_premium(self):
        from matchmaking.models import Connection
        doc = self._make_pitch_deck_doc(with_memo=True)
        Connection.objects.create(
            investor=self.investor_app, founder=self.application, status='ACCEPTED', initiated_by='INVESTOR',
        )
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('zelda_api:ic_memo', args=[doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hasn't upgraded to Zelda AI yet")
        self.assertContains(response, 'Strong team, growing market.')
        self.assertNotContains(response, 'We build developer tools.')

    def test_html_view_returns_full_memo_for_connected_investor_when_founder_premium(self):
        from matchmaking.models import Connection
        doc = self._make_pitch_deck_doc(with_memo=True)
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        Connection.objects.create(
            investor=self.investor_app, founder=self.application, status='ACCEPTED', initiated_by='INVESTOR',
        )
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('zelda_api:ic_memo', args=[doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'We build developer tools.')

    def test_html_view_returns_full_memo_for_staff_regardless_of_premium(self):
        doc = self._make_pitch_deck_doc(with_memo=True)
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('zelda_api:ic_memo', args=[doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'We build developer tools.')

    def test_markdown_download_redirects_when_not_premium(self):
        doc = self._make_pitch_deck_doc(with_memo=True)
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('zelda_api:ic_memo_download', args=[doc.id]))
        self.assertRedirects(response, reverse('zelda_api:ic_memo', args=[doc.id]))

    def test_markdown_download_returns_correct_content_type_and_filename(self):
        doc = self._make_pitch_deck_doc(with_memo=True)
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('zelda_api:ic_memo_download', args=[doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/markdown')
        self.assertIn('memoco-ic-memo.md', response['Content-Disposition'])
        self.assertIn(b'MemoCo', response.content)

    def test_markdown_download_404s_for_unauthorized_viewer(self):
        doc = self._make_pitch_deck_doc(with_memo=True)
        self.client.force_login(self.stranger_user)
        response = self.client.get(reverse('zelda_api:ic_memo_download', args=[doc.id]))
        self.assertEqual(response.status_code, 404)


class ApplyConstraintsToQuerysetTests(TestCase):
    """
    intelligence_pipeline.py::_apply_constraints_to_queryset — pure,
    deterministic constraint-application logic. No Claude call involved
    here; ZeldaAskAPIView's own tests below mock the extraction call and
    exercise the view wiring instead.
    """

    def setUp(self):
        from matchmaking.models import Application
        self.Application = Application
        u1 = User.objects.create_user('cq_f1', password='x')
        u2 = User.objects.create_user('cq_f2', password='x')
        self.f1 = Application.objects.create(
            user=u1, company_name='F1', founder_name='F', email='f1@t.com',
            description='test', sector='Healthcare', stage='Series C',
            raising_amount=3000000, years_in_business=5, monthly_burn_rate=40000,
        )
        self.f2 = Application.objects.create(
            user=u2, company_name='F2', founder_name='F', email='f2@t.com',
            description='test', sector='SaaS', stage='Seed',
            raising_amount=100000, years_in_business=1, monthly_burn_rate=5000,
        )

    def _apply(self, constraints):
        from .intelligence_pipeline import _apply_constraints_to_queryset
        qs = self.Application.objects.all()
        return list(_apply_constraints_to_queryset(qs, constraints))

    def test_string_field_icontains(self):
        results = self._apply([{'field': 'sector', 'qualifier': 'exact', 'value': 'health'}])
        self.assertEqual(results, [self.f1])

    def test_number_at_least(self):
        results = self._apply([{'field': 'years_in_business', 'qualifier': 'at_least', 'value': 3}])
        self.assertEqual(results, [self.f1])

    def test_number_at_most(self):
        results = self._apply([{'field': 'monthly_burn_rate', 'qualifier': 'at_most', 'value': 10000}])
        self.assertEqual(results, [self.f2])

    def test_number_about_tolerance_band(self):
        # 3,000,000 +/- 15% = [2,550,000, 3,450,000] — f1's raising_amount qualifies
        results = self._apply([{'field': 'raising_amount', 'qualifier': 'about', 'value': 3000000}])
        self.assertEqual(results, [self.f1])

    def test_number_exact(self):
        results = self._apply([{'field': 'years_in_business', 'qualifier': 'exact', 'value': 5}])
        self.assertEqual(results, [self.f1])

    def test_unknown_field_is_ignored(self):
        results = self._apply([{'field': 'is_staff', 'qualifier': 'exact', 'value': True}])
        self.assertEqual(len(results), 2)

    def test_non_numeric_value_for_number_field_is_ignored(self):
        results = self._apply([{'field': 'years_in_business', 'qualifier': 'exact', 'value': 'not-a-number'}])
        self.assertEqual(len(results), 2)

    def test_blank_string_value_is_ignored(self):
        results = self._apply([{'field': 'sector', 'qualifier': 'exact', 'value': '  '}])
        self.assertEqual(len(results), 2)

    def test_relax_widens_at_most_band(self):
        # f2's burn rate is 5000 — a strict at_most of 4000 excludes it, but
        # relax=True adds 20% slack (4000 * 1.2 = 4800, still excludes it);
        # use 4200 so the widened band (5040) includes it but the strict one doesn't.
        strict = self._apply([{'field': 'monthly_burn_rate', 'qualifier': 'at_most', 'value': 4200}])
        self.assertEqual(strict, [])
        from .intelligence_pipeline import _apply_constraints_to_queryset
        qs = self.Application.objects.all()
        relaxed = list(_apply_constraints_to_queryset(
            qs, [{'field': 'monthly_burn_rate', 'qualifier': 'at_most', 'value': 4200}], relax=True,
        ))
        self.assertEqual(relaxed, [self.f2])

    def test_relax_widens_exact_numeric_into_a_band(self):
        # years_in_business is an IntegerField — Django truncates a float
        # like 5.4 to 5 before filtering, which would make "exact" match
        # f1 (5) even unrelaxed and defeat this test. Use a DecimalField
        # (monthly_burn_rate) instead, where no such truncation happens:
        # f1's burn rate is 40000, so exact=40500 fails strict but falls
        # inside the relaxed +/-15% band (34425-46575).
        strict = self._apply([{'field': 'monthly_burn_rate', 'qualifier': 'exact', 'value': 40500}])
        self.assertEqual(strict, [])
        from .intelligence_pipeline import _apply_constraints_to_queryset
        qs = self.Application.objects.all()
        relaxed = list(_apply_constraints_to_queryset(
            qs, [{'field': 'monthly_burn_rate', 'qualifier': 'exact', 'value': 40500}], relax=True,
        ))
        self.assertEqual(relaxed, [self.f1])

    def test_relax_never_widens_string_fields(self):
        from .intelligence_pipeline import _apply_constraints_to_queryset
        qs = self.Application.objects.all()
        relaxed = list(_apply_constraints_to_queryset(
            qs, [{'field': 'sector', 'qualifier': 'exact', 'value': 'Fintech'}], relax=True,
        ))
        self.assertEqual(relaxed, [])


class SearchWithRelaxationTests(TestCase):
    """
    intelligence_pipeline.py::_search_with_relaxation — the "closest match"
    fallback: widen numeric tolerances, then drop constraints (numeric
    before string) one at a time, reporting exactly what was relaxed.
    """

    def setUp(self):
        from matchmaking.models import Application
        self.Application = Application
        u = User.objects.create_user('relax_f1', password='x')
        self.f1 = Application.objects.create(
            user=u, company_name='RelaxCo', founder_name='F', email='relax@t.com',
            description='test', sector='Healthcare', stage='Series C',
            raising_amount=3000000, years_in_business=5, monthly_burn_rate=40000,
        )

    def _search(self, constraints):
        from .intelligence_pipeline import _search_with_relaxation
        qs = self.Application.objects.all()
        return _search_with_relaxation(qs, constraints)

    def test_exact_match_needs_no_relaxation(self):
        matches, dropped, widened = self._search([{'field': 'sector', 'qualifier': 'exact', 'value': 'Healthcare'}])
        self.assertEqual(matches, [self.f1])
        self.assertEqual(dropped, [])
        self.assertFalse(widened)

    def test_widening_alone_finds_a_close_match(self):
        # f1's burn rate is 40000: strict at_most(35000) fails (40000 > 35000),
        # but relax=True widens the ceiling to 35000*1.2=42000, which f1 clears.
        matches, dropped, widened = self._search(
            [{'field': 'monthly_burn_rate', 'qualifier': 'at_most', 'value': 35000}]
        )
        self.assertEqual(matches, [self.f1])
        self.assertEqual(dropped, [])
        self.assertTrue(widened)

    def test_drops_numeric_constraint_before_string_constraint(self):
        # sector=Healthcare matches; years_in_business=exact(1) never matches
        # this founder even relaxed (5 is too far from 1) — so the numeric
        # constraint must be the one dropped, not the sector constraint.
        matches, dropped, widened = self._search([
            {'field': 'sector', 'qualifier': 'exact', 'value': 'Healthcare'},
            {'field': 'years_in_business', 'qualifier': 'exact', 'value': 1},
        ])
        self.assertEqual(matches, [self.f1])
        self.assertEqual(len(dropped), 1)
        self.assertIn('years in business', dropped[0])
        self.assertFalse(widened)

    def test_drops_string_constraint_only_as_last_resort(self):
        matches, dropped, widened = self._search([
            {'field': 'sector', 'qualifier': 'exact', 'value': 'Fintech'},  # no founder matches this
            {'field': 'years_in_business', 'qualifier': 'exact', 'value': 1},  # nor this
        ])
        self.assertEqual(matches, [self.f1])
        self.assertEqual(len(dropped), 2)

    def test_no_match_at_all_returns_empty(self):
        from .intelligence_pipeline import _search_with_relaxation
        matches, dropped, widened = _search_with_relaxation(self.Application.objects.none(), [
            {'field': 'sector', 'qualifier': 'exact', 'value': 'Healthcare'},
        ])
        self.assertEqual(matches, [])


class AskZeldaAPIViewTests(TestCase):
    """
    zelda_api/views.py::ZeldaAskAPIView — natural-language founder search.
    Claude's extraction call is mocked throughout so these never hit the
    real API; the goal is to verify the view's own wiring: privacy
    filtering, rate limiting, and circuit-breaker error handling.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('ask_zelda_user', password='x')
        self.client.force_login(self.user)

    def _make_founder(self, username, **kwargs):
        from matchmaking.models import Application
        u = User.objects.create_user(username, password='x')
        defaults = dict(
            company_name=f'{username}Co', founder_name='F', email=f'{username}@t.com',
            description='test', sector='SaaS', stage='Series C',
        )
        defaults.update(kwargs)
        return Application.objects.create(user=u, **defaults)

    def _post(self, question):
        import json as json_module
        return self.client.post(
            reverse('zelda_api:ask'), data=json_module.dumps({'q': question}), content_type='application/json',
        )

    def test_empty_question_returns_prompt_with_no_results(self):
        response = self._post('')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'], [])

    def test_extraction_with_no_constraints_returns_helpful_message(self):
        with mock.patch(
            'zelda_api.intelligence_pipeline._call_claude_for_query_extraction',
            return_value={'constraints': []},
        ):
            response = self._post('hello there')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'], [])

    def test_matching_founder_is_returned(self):
        self._make_founder(
            'matchfounder', stage='Series C', raising_amount=3000000,
            years_in_business=5, monthly_burn_rate=40000,
        )
        self._make_founder(
            'nomatchfounder', stage='Seed', raising_amount=100000,
            years_in_business=1, monthly_burn_rate=5000,
        )
        extraction = {'constraints': [
            {'field': 'stage', 'qualifier': 'exact', 'value': 'Series C'},
            {'field': 'monthly_burn_rate', 'qualifier': 'at_most', 'value': 40000},
        ]}
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction', return_value=extraction):
            response = self._post('series c founder burning under 40k/mo')

        data = response.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['username'], 'matchfounder')

    def test_private_founder_is_excluded_from_results(self):
        self._make_founder('privatefounder', stage='Series C', is_private=True)
        extraction = {'constraints': [{'field': 'stage', 'qualifier': 'exact', 'value': 'Series C'}]}
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction', return_value=extraction):
            response = self._post('series c founders')
        self.assertEqual(response.json()['results'], [])

    def test_denied_founder_is_excluded_from_results(self):
        self._make_founder('deniedfounder', stage='Series C', review_status='DENIED')
        extraction = {'constraints': [{'field': 'stage', 'qualifier': 'exact', 'value': 'Series C'}]}
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction', return_value=extraction):
            response = self._post('series c founders')
        self.assertEqual(response.json()['results'], [])

    def test_no_exact_match_falls_back_to_close_founder_and_says_so(self):
        self._make_founder(
            'closefounder', stage='Series C', raising_amount=3000000,
            years_in_business=5, monthly_burn_rate=40000,
        )
        # at_most 30000 excludes this founder's 40000 burn even relaxed
        # (40000*0.8=32000 > 30000), forcing the constraint to be dropped.
        extraction = {'constraints': [
            {'field': 'stage', 'qualifier': 'exact', 'value': 'Series C'},
            {'field': 'monthly_burn_rate', 'qualifier': 'at_most', 'value': 30000},
        ]}
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction', return_value=extraction):
            response = self._post('series c founder burning under 30k/mo')

        data = response.json()
        self.assertEqual(len(data['results']), 1)
        self.assertIn('No exact match', data['response'])
        self.assertIn('burn rate', data['response'])

    def test_no_match_even_after_relaxation_says_so_plainly(self):
        extraction = {'constraints': [{'field': 'sector', 'qualifier': 'exact', 'value': 'Aerospace'}]}
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction', return_value=extraction):
            response = self._post('aerospace founders')
        data = response.json()
        self.assertEqual(data['results'], [])
        self.assertIn('No founders currently match', data['response'])

    def test_daily_rate_limit_enforced(self):
        from matchmaking.models import SearchEvent
        for _ in range(30):
            SearchEvent.objects.create(user=self.user, source='zelda_ask', query_summary='x')
        response = self._post('series c founders')
        self.assertEqual(response.status_code, 429)

    def test_circuit_open_returns_503(self):
        from .circuit_breaker import CircuitOpenError
        with mock.patch(
            'zelda_api.intelligence_pipeline._call_claude_for_query_extraction',
            side_effect=CircuitOpenError('open'),
        ):
            response = self._post('series c founders')
        self.assertEqual(response.status_code, 503)

    def test_unauthenticated_request_is_rejected(self):
        self.client.logout()
        response = self._post('series c founders')
        self.assertIn(response.status_code, (401, 403))

    def test_out_of_scope_role_query_degrades_gracefully(self):
        """
        Ask Zelda only queries founder (Application) records — it has no
        InvestorApplication/SellerApplication search path. A prompt like
        "which founders match an investor interested in biotech" or "HVAC
        companies for sale" should never crash; Claude's extraction for an
        out-of-scope question naturally yields no allowlisted founder
        fields, which the view already handles as "no criteria found".
        """
        with mock.patch(
            'zelda_api.intelligence_pipeline._call_claude_for_query_extraction',
            return_value={'constraints': []},
        ):
            response = self._post('find HVAC companies for sale under $5M EBITDA')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'], [])

    def test_real_post_logs_a_search_event(self):
        """
        views.py:425 calls log_search_event(request, 'zelda_ask', question)
        on every non-empty query — this is the actual side effect the daily
        rate limit (test_daily_rate_limit_enforced) depends on counting,
        but no test previously drove it through a real POST.
        """
        from matchmaking.models import SearchEvent
        with mock.patch(
            'zelda_api.intelligence_pipeline._call_claude_for_query_extraction',
            return_value={'constraints': []},
        ):
            self._post('series c founders')
        self.assertTrue(
            SearchEvent.objects.filter(user=self.user, source='zelda_ask', query_summary='series c founders').exists()
        )


class AskZeldaBuyerSellerSearchTests(TestCase):
    """
    zelda_api/views.py::ZeldaAskAPIView routing for buyers — a user with a
    BuyerApplication profile searches SellerApplication listings instead
    of founders, using the seller schema (industry/asking_price/ebitda/
    etc.) for extraction and filtering. Mirrors AskZeldaAPIViewTests'
    structure; Claude's extraction call is mocked throughout.
    """

    def setUp(self):
        cache.clear()
        from matchmaking.models import BuyerApplication
        self.buyer_user = User.objects.create_user('ask_zelda_buyer', password='x')
        BuyerApplication.objects.create(
            user=self.buyer_user, full_name='Buyer', email='buyer@t.com',
            company_name='Acquisitions LLC', acquisition_thesis='We acquire manufacturing businesses',
            budget_min=500000, budget_max=1500000,
        )
        self.client.force_login(self.buyer_user)

    def _make_seller(self, username, **kwargs):
        from matchmaking.models import SellerApplication
        u = User.objects.create_user(username, password='x')
        defaults = dict(
            company_name=f'{username}Co', seller_name='S', email=f'{username}@t.com',
            description='A steady regional business.', industry='Manufacturing',
        )
        defaults.update(kwargs)
        return SellerApplication.objects.create(user=u, **defaults)

    def _post(self, question):
        import json as json_module
        return self.client.post(
            reverse('zelda_api:ask'), data=json_module.dumps({'q': question}), content_type='application/json',
        )

    def test_buyer_question_searches_sellers_not_founders(self):
        self._make_seller(
            'matchingseller', industry='Manufacturing', asking_price=9500000,
            years_in_business=8, ebitda=1100000,
        )
        extraction = {'constraints': [
            {'field': 'industry', 'qualifier': 'exact', 'value': 'Manufacturing'},
            {'field': 'asking_price', 'qualifier': 'at_most', 'value': 9500000},
        ]}
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction', return_value=extraction) as mock_extract:
            response = self._post('manufacturing business under $9.5M')

        # target='seller' must reach the extraction call for a buyer.
        self.assertEqual(mock_extract.call_args.kwargs.get('target') or mock_extract.call_args.args[1], 'seller')
        data = response.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['type'], 'Business Listing')
        self.assertEqual(data['results'][0]['username'], 'matchingseller')

    def test_non_buyer_question_still_searches_founders(self):
        """A plain investor (or any non-buyer) hitting the same endpoint keeps the original founder-search behavior."""
        self.client.logout()
        investor_user = User.objects.create_user('ask_zelda_plain_investor', password='x')
        self.client.force_login(investor_user)

        from matchmaking.models import Application
        founder_user = User.objects.create_user('plainfounder', password='x')
        Application.objects.create(
            user=founder_user, company_name='PlainCo', founder_name='F', email='pf@t.com',
            description='test', sector='SaaS', stage='Series C',
        )
        extraction = {'constraints': [{'field': 'stage', 'qualifier': 'exact', 'value': 'Series C'}]}
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction', return_value=extraction) as mock_extract:
            response = self._post('series c founders')

        target_arg = mock_extract.call_args.kwargs.get('target') or (
            mock_extract.call_args.args[1] if len(mock_extract.call_args.args) > 1 else 'founder'
        )
        self.assertEqual(target_arg, 'founder')
        data = response.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['type'], 'Founder Profile')

    def test_private_seller_is_excluded_from_results(self):
        self._make_seller('privateseller', industry='Manufacturing', is_private=True)
        extraction = {'constraints': [{'field': 'industry', 'qualifier': 'exact', 'value': 'Manufacturing'}]}
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction', return_value=extraction):
            response = self._post('manufacturing businesses')
        self.assertEqual(response.json()['results'], [])

    def test_denied_seller_is_excluded_from_results(self):
        self._make_seller('deniedseller', industry='Manufacturing', review_status='DENIED')
        extraction = {'constraints': [{'field': 'industry', 'qualifier': 'exact', 'value': 'Manufacturing'}]}
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction', return_value=extraction):
            response = self._post('manufacturing businesses')
        self.assertEqual(response.json()['results'], [])

    def test_no_seller_match_says_so_with_business_wording(self):
        extraction = {'constraints': [{'field': 'industry', 'qualifier': 'exact', 'value': 'Aerospace'}]}
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction', return_value=extraction):
            response = self._post('aerospace businesses for sale')
        data = response.json()
        self.assertEqual(data['results'], [])
        self.assertIn('businesses for sale', data['response'])

    def test_hvac_under_ebitda_example_prompt_maps_to_ebitda_field(self):
        """
        The exact example prompt this feature was requested for: "Find HVAC
        companies for sale under $5M EBITDA." Confirms ebitda is in the
        seller allowlist and an at_most constraint on it actually filters.
        """
        self._make_seller('hvaclow', industry='HVAC', ebitda=4000000)
        self._make_seller('hvachigh', industry='HVAC', ebitda=8000000)
        extraction = {'constraints': [
            {'field': 'industry', 'qualifier': 'exact', 'value': 'HVAC'},
            {'field': 'ebitda', 'qualifier': 'at_most', 'value': 5000000},
        ]}
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction', return_value=extraction):
            response = self._post('HVAC companies for sale under $5M EBITDA')
        data = response.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['username'], 'hvaclow')


class DocumentIngestViewTests(TestCase):
    """
    zelda_api/pipeline_views.py::DocumentIngestView — the actual public
    entry point for both the memo and valuation pipelines had no test
    coverage at all before this. Celery's .delay() is mocked throughout
    since these tests target the view's own validation/routing, not an
    actual broker connection.
    """

    def setUp(self):
        self.user = User.objects.create_user('ingest_user', password='x')
        self.client.force_login(self.user)

    def _post(self, file_obj, document_type='pitch_deck', source_entity='TestCo'):
        return self.client.post(
            reverse('zelda_api:document_ingest'),
            data={'file': file_obj, 'document_type': document_type, 'source_entity': source_entity},
        )

    def test_no_file_returns_400(self):
        response = self.client.post(reverse('zelda_api:document_ingest'), data={})
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_request_is_rejected(self):
        self.client.logout()
        f = SimpleUploadedFile('deck.txt', b'some pitch deck content', content_type='text/plain')
        response = self._post(f)
        self.assertIn(response.status_code, (401, 403))

    def test_empty_file_returns_400_not_500(self):
        f = SimpleUploadedFile('empty.txt', b'', content_type='text/plain')
        response = self._post(f)
        self.assertEqual(response.status_code, 400)

    def test_oversized_file_returns_400_not_500(self):
        # 26MB — over the 25MB cap MaxFileSizeValidator enforces here.
        f = SimpleUploadedFile('huge.txt', b'x' * (26 * 1024 * 1024), content_type='text/plain')
        response = self._post(f)
        self.assertEqual(response.status_code, 400)
        self.assertIn('too large', response.json()['error'].lower())

    def test_valid_upload_creates_document_and_queues_pipeline_task(self):
        from .vector_models import DocumentSource
        f = SimpleUploadedFile('deck.txt', b'We build infrastructure tooling for SaaS teams.', content_type='text/plain')
        with mock.patch('zelda_api.pipeline_views.process_document_pipeline.delay') as mock_delay:
            response = self._post(f, document_type='pitch_deck')

        self.assertEqual(response.status_code, 201)
        doc = DocumentSource.objects.get(id=response.json()['document_id'])
        self.assertEqual(doc.uploaded_by, self.user)
        self.assertEqual(doc.status, 'ingested')
        mock_delay.assert_called_once()

    def test_txt_upload_records_a_page_count(self):
        """
        Regression test: extract_text_from_file used to discard the page/
        slide count PyPDF2/python-pptx already compute, so total_pages was
        silently stuck at its model default of 0 for every real upload —
        surfacing as a "0 Pages Analyzed" stat that looked like the
        pipeline had failed. .txt has no real pagination, so it counts as
        a single "page" rather than 0, as long as there's real content.
        """
        from .vector_models import DocumentSource
        f = SimpleUploadedFile('deck.txt', b'We build infrastructure tooling for SaaS teams.', content_type='text/plain')
        with mock.patch('zelda_api.pipeline_views.process_document_pipeline.delay'):
            response = self._post(f, document_type='pitch_deck')

        doc = DocumentSource.objects.get(id=response.json()['document_id'])
        self.assertEqual(doc.total_pages, 1)

    def test_pdf_upload_records_the_real_page_count(self):
        from .vector_models import DocumentSource
        f = SimpleUploadedFile('deck.pdf', b'fake pdf bytes', content_type='application/pdf')
        with mock.patch('zelda_api.pipeline_views.process_document_pipeline.delay'), \
             mock.patch('zelda_api.utils._extract_pdf_text', return_value=('Extracted deck text.', 14)):
            response = self._post(f, document_type='pitch_deck')

        doc = DocumentSource.objects.get(id=response.json()['document_id'])
        self.assertEqual(doc.total_pages, 14)

    def test_business_valuation_type_routes_to_valuation_task_not_pipeline_task(self):
        f = SimpleUploadedFile('cim.txt', b'Annual revenue is six million dollars.', content_type='text/plain')
        with mock.patch('zelda_api.pipeline_views.process_document_pipeline.delay') as mock_pipeline_delay, \
             mock.patch('zelda_api.pipeline_views.process_valuation_document_task.delay') as mock_valuation_delay:
            response = self._post(f, document_type='business_valuation')

        self.assertEqual(response.status_code, 201)
        mock_valuation_delay.assert_called_once()
        mock_pipeline_delay.assert_not_called()

    def test_duplicate_upload_creates_independent_documents_no_cross_contamination(self):
        """
        Nothing dedupes uploads today — confirm that's at least safe: two
        uploads of the same content produce two independent DocumentSource
        rows and two independent memos, not a shared/overwritten one.
        FREE_DEEP_ANALYSIS_LIMIT is 1/month, so the second call needs the
        quota check bypassed — this test is about dedup, not quotas (see
        DeepAnalysisQuotaTests for quota coverage).
        """
        from .vector_models import DocumentSource
        content = b'We build infrastructure tooling for SaaS teams.'
        # Two memo uploads cost 2 of the 3 free monthly credits — no bypass needed.
        with mock.patch('zelda_api.pipeline_views.process_document_pipeline.delay'):
            r1 = self._post(SimpleUploadedFile('deck.txt', content, content_type='text/plain'))
            r2 = self._post(SimpleUploadedFile('deck.txt', content, content_type='text/plain'))

        id1, id2 = r1.json()['document_id'], r2.json()['document_id']
        self.assertNotEqual(id1, id2)
        self.assertEqual(DocumentSource.objects.filter(id__in=[id1, id2]).count(), 2)

        # Simulate each finishing with its own distinct memo (as two real
        # pipeline runs would) and confirm they don't collide.
        doc1, doc2 = DocumentSource.objects.get(id=id1), DocumentSource.objects.get(id=id2)
        IntelligenceMemo.objects.create(document=doc1, executive_summary='First run summary.', recommendation='NEEDS_REVIEW')
        IntelligenceMemo.objects.create(document=doc2, executive_summary='Second run summary.', recommendation='NEEDS_REVIEW')
        self.assertEqual(doc1.memo.executive_summary, 'First run summary.')
        self.assertEqual(doc2.memo.executive_summary, 'Second run summary.')


class AICreditsQuotaTests(TestCase):
    """
    zelda_api/quotas.py — the only guard against unlimited free Claude
    spend on memos/Truth-Delta verification. Weighted credits (memo=1,
    truth_delta_verify=1), not a flat action count: FREE_CREDITS=3 gives a
    free user room to feel more than one feature before hitting a wall,
    while still capping total spend. Business valuation has its own
    separate role-based pricing — see ValuationAccessTests. Covers the
    real trigger points: DocumentIngestView.post, TruthDeltaVerifyView.post
    (explicitly re-runnable per its own docstring — this is the test that
    confirms that no longer means unlimited free re-runs), and
    analyze_founder_profile.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('quota_user', password='x')

    def _existing_memo(self, user, n=1, filename_prefix='existing'):
        for i in range(n):
            DocumentSource.objects.create(
                filename=f'{filename_prefix}{i}.pdf', source_entity='QuotaCo',
                uploaded_by=user, document_type='pitch_deck',
            )

    def test_free_user_first_upload_allowed(self):
        self.client.force_login(self.user)
        f = SimpleUploadedFile('deck.txt', b'We build tools for SaaS teams.', content_type='text/plain')
        with mock.patch('zelda_api.pipeline_views.process_document_pipeline.delay'):
            response = self.client.post(
                reverse('zelda_api:document_ingest'),
                data={'file': f, 'document_type': 'pitch_deck', 'source_entity': 'QuotaCo'},
            )
        self.assertEqual(response.status_code, 201)

    def test_free_user_third_memo_allowed_fourth_blocked(self):
        self.client.force_login(self.user)
        self._existing_memo(self.user, n=2)  # 2 credits used, memo cost 1 -> 3rd allowed

        f3 = SimpleUploadedFile('deck3.txt', b'We build tools for SaaS teams.', content_type='text/plain')
        with mock.patch('zelda_api.pipeline_views.process_document_pipeline.delay'):
            response3 = self.client.post(
                reverse('zelda_api:document_ingest'),
                data={'file': f3, 'document_type': 'pitch_deck', 'source_entity': 'QuotaCo'},
            )
        self.assertEqual(response3.status_code, 201)  # 3 credits used, exactly at the free cap

        f4 = SimpleUploadedFile('deck4.txt', b'We build tools for SaaS teams.', content_type='text/plain')
        response4 = self.client.post(
            reverse('zelda_api:document_ingest'),
            data={'file': f4, 'document_type': 'pitch_deck', 'source_entity': 'QuotaCo'},
        )
        self.assertEqual(response4.status_code, 402)
        self.assertEqual(response4.json()['code'], 'quota_exceeded')

    def test_valuation_no_longer_shares_the_memo_credit_pool(self):
        """
        Business valuation moved to its own role-based pricing (see
        zelda_api/quotas.py::valuation_tier_for_new_upload) — it no
        longer costs 2 of the shared memo/Truth-Delta credits, and isn't
        gated at upload time at all. A role-less user (same "no role yet
        lands on the founder track" convention used elsewhere) can still
        always upload; they just get the free-preview tier rather than
        the memo pool's 402.
        """
        self.client.force_login(self.user)
        f = SimpleUploadedFile('cim.txt', b'Annual revenue is six million dollars.', content_type='text/plain')
        with mock.patch('zelda_api.pipeline_views.process_valuation_document_task.delay'):
            response = self.client.post(
                reverse('zelda_api:document_ingest'),
                data={'file': f, 'document_type': 'business_valuation', 'source_entity': 'QuotaCo'},
            )
        self.assertEqual(response.status_code, 201)
        doc = DocumentSource.objects.get(id=response.json()['document_id'])
        self.assertEqual(doc.valuation_tier, 'preview')

    def test_premium_founder_gets_a_much_higher_limit(self):
        from matchmaking.models import Application
        Application.objects.create(user=self.user, company_name='QuotaCo', is_premium=True)
        self.client.force_login(self.user)
        self._existing_memo(self.user, n=10)  # well past the free cap of 3, still under the premium cap of 100
        f = SimpleUploadedFile('deck.txt', b'We build tools for SaaS teams.', content_type='text/plain')
        with mock.patch('zelda_api.pipeline_views.process_document_pipeline.delay'):
            response = self.client.post(
                reverse('zelda_api:document_ingest'),
                data={'file': f, 'document_type': 'pitch_deck', 'source_entity': 'QuotaCo'},
            )
        self.assertEqual(response.status_code, 201)

    def test_staff_user_exempt_from_quota(self):
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        self._existing_memo(self.user, n=5)  # already over the free cap of 3
        f = SimpleUploadedFile('deck.txt', b'We build tools for SaaS teams.', content_type='text/plain')
        with mock.patch('zelda_api.pipeline_views.process_document_pipeline.delay'):
            response = self.client.post(
                reverse('zelda_api:document_ingest'),
                data={'file': f, 'document_type': 'pitch_deck', 'source_entity': 'QuotaCo'},
            )
        self.assertEqual(response.status_code, 201)

    def test_truth_delta_first_verify_allowed(self):
        doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='QuotaCo', uploaded_by=self.user, document_type='pitch_deck',
        )
        self.client.force_login(self.user)
        # Explicit new= (rather than letting mock.patch auto-spec off the
        # original) — auto-specing off Celery's task Proxy from inside a
        # live view call (as opposed to calling the task function directly,
        # like other mocks of this same target elsewhere in this file do)
        # hangs under this environment's mock/Celery/Python combination.
        fake_delay = mock.Mock(return_value=mock.Mock(id='fake-task-id'))
        with mock.patch('zelda_api.truth_delta_tasks.verify_document_truth_delta.delay', new=fake_delay):
            response = self.client.post(reverse('zelda_api:truth_delta_verify', args=[doc.id]))
        self.assertEqual(response.status_code, 202)

    def test_truth_delta_reverify_blocked_once_free_credits_are_used(self):
        """
        TruthDeltaScoreView's own docstring notes verification can be
        re-run with nothing enforcing one report per document — this is
        the test that confirms that no longer means unlimited free re-runs.
        """
        from .truth_delta_models import TruthDeltaReport
        doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='QuotaCo', uploaded_by=self.user, document_type='pitch_deck',
        )
        for _ in range(3):  # 3 prior verifications = 3 credits used, exactly at the free cap
            TruthDeltaReport.objects.create(document=doc, overall_truth_score=80.0, credibility_risk='low', summary='ok')
        self.client.force_login(self.user)
        response = self.client.post(reverse('zelda_api:truth_delta_verify', args=[doc.id]))
        self.assertEqual(response.status_code, 402)

    def test_analyze_founder_profile_returns_confirm_required_without_spending_anyone_credits(self):
        """
        analyze_founder_profile no longer generates on the spot — it never
        even reaches a quota check, for either side. The founder having
        used all their own credits on unrelated actions must not affect
        this response at all (see confirm_analyze_founder_profile for
        where the actual spend, charged to the investor, is checked).
        """
        from matchmaking.models import Application, InvestorApplication
        founder_user = User.objects.create_user('quota_founder', password='x')
        Application.objects.create(
            user=founder_user, company_name='QuotaCo',
            pitch_deck=SimpleUploadedFile('deck.pdf', b'fake pdf bytes', content_type='application/pdf'),
        )
        for i in range(5):  # founder's own credits fully spent on unrelated uploads
            DocumentSource.objects.create(
                filename=f'other{i}.pdf', source_entity='QuotaCo',
                uploaded_by=founder_user, document_type='other',
            )
        investor_user = User.objects.create_user('quota_investor', password='x')
        InvestorApplication.objects.create(user=investor_user)
        self.client.force_login(investor_user)

        response = self.client.get(reverse('zelda_api:analyze_founder', args=[founder_user.username]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'confirm_required')
        self.assertEqual(data['analysis_cost'], 1)
        self.assertFalse(DocumentSource.objects.filter(uploaded_by=founder_user, document_type='pitch_deck').exists())

    def test_confirm_analyze_founder_profile_charges_the_investor_not_the_founder(self):
        from matchmaking.models import Application, InvestorApplication
        founder_user = User.objects.create_user('confirm_founder', password='x')
        Application.objects.create(
            user=founder_user, company_name='ConfirmCo',
            pitch_deck=SimpleUploadedFile('deck.pdf', b'fake pdf bytes', content_type='application/pdf'),
        )
        investor_user = User.objects.create_user('confirm_investor', password='x')
        InvestorApplication.objects.create(user=investor_user)
        self.client.force_login(investor_user)

        with mock.patch('zelda_api.utils._extract_pdf_text', return_value=('Some deck text about our SaaS product.', 5)), \
             mock.patch('zelda_api.tasks.process_document_pipeline.delay', new=mock.Mock()):
            response = self.client.post(reverse('zelda_api:analyze_founder_confirm', args=[founder_user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'processing')
        doc = DocumentSource.objects.get(uploaded_by=founder_user, document_type='pitch_deck')
        self.assertIsNotNone(doc)

        # The document has to stay owned by the founder (everything else about
        # ownership/visibility depends on it), but the credit spend must land
        # on the investor who confirmed, not silently on the founder — that
        # was a real bug: uploaded_by=founder_user made credits_used(founder)
        # count this document even though the founder never clicked anything.
        from zelda_api.quotas import credits_used
        self.assertEqual(credits_used(founder_user), 0)
        self.assertEqual(credits_used(investor_user), 1)

    def test_confirm_analyze_founder_profile_blocked_when_investor_credits_exhausted(self):
        """The investor's own quota gates this now — the founder's is never checked."""
        from matchmaking.models import Application, InvestorApplication
        founder_user = User.objects.create_user('confirm_founder2', password='x')
        Application.objects.create(
            user=founder_user, company_name='ConfirmCo2',
            pitch_deck=SimpleUploadedFile('deck.pdf', b'fake pdf bytes', content_type='application/pdf'),
        )
        investor_user = User.objects.create_user('confirm_investor2', password='x')
        InvestorApplication.objects.create(user=investor_user)
        for i in range(3):  # investor's own 3 free credits already used elsewhere
            DocumentSource.objects.create(
                filename=f'other{i}.pdf', source_entity='InvestorSelfUpload',
                uploaded_by=investor_user, document_type='other',
            )
        self.client.force_login(investor_user)

        response = self.client.post(reverse('zelda_api:analyze_founder_confirm', args=[founder_user.username]))
        self.assertEqual(response.status_code, 402)
        self.assertFalse(DocumentSource.objects.filter(uploaded_by=founder_user, document_type='pitch_deck').exists())

    def test_confirm_analyze_founder_profile_requires_post(self):
        from matchmaking.models import Application, InvestorApplication
        founder_user = User.objects.create_user('confirm_founder3', password='x')
        Application.objects.create(user=founder_user, company_name='ConfirmCo3')
        investor_user = User.objects.create_user('confirm_investor3', password='x')
        InvestorApplication.objects.create(user=investor_user)
        self.client.force_login(investor_user)

        response = self.client.get(reverse('zelda_api:analyze_founder_confirm', args=[founder_user.username]))
        self.assertEqual(response.status_code, 405)


class WeeklyAICreditCapTests(TestCase):
    """
    zelda_api/quotas.py's weekly soft cap — layered on top of the existing
    30-day monthly allowance, sized as a fraction of it (WEEKLY_CREDIT_
    FRACTION) so a user can't burn a whole month's credits in one week.
    Floored at FREE_CREDITS so the free tier (already tiny) isn't made more
    restrictive than its own monthly cap for no real benefit.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('weekly_quota_user', password='x')

    def _memo(self, user, n=1, created_days_ago=0):
        from django.utils import timezone
        from datetime import timedelta
        for i in range(n):
            doc = DocumentSource.objects.create(
                filename=f'wk{i}.pdf', source_entity='WeeklyCo', uploaded_by=user, document_type='pitch_deck',
            )
            if created_days_ago:
                doc.created_at = timezone.now() - timedelta(days=created_days_ago)
                doc.save(update_fields=['created_at'])

    def test_weekly_limit_is_a_fraction_of_the_monthly_limit(self):
        from matchmaking.models import Application
        from zelda_api.quotas import weekly_credit_limit
        Application.objects.create(user=self.user, company_name='WeeklyCo', is_premium=True)
        self.assertEqual(weekly_credit_limit(self.user), 40)  # ceil(100 * 0.4)

    def test_free_tier_weekly_limit_floors_at_free_credits(self):
        from zelda_api.quotas import weekly_credit_limit, FREE_CREDITS
        self.assertEqual(weekly_credit_limit(self.user), FREE_CREDITS)  # ceil(3*0.4)=2, floored back up to 3

    def test_premium_user_blocked_by_weekly_cap_despite_monthly_room(self):
        """40 credits used this week (at the weekly cap) but nowhere near the 100 monthly cap — still blocked."""
        from matchmaking.models import Application
        from zelda_api.quotas import has_credits_for
        Application.objects.create(user=self.user, company_name='WeeklyCo', is_premium=True)
        self._memo(self.user, n=40)
        self.assertFalse(has_credits_for(self.user, 'memo'))

    def test_credits_older_than_a_week_do_not_count_against_the_weekly_cap(self):
        """Same 40 credits, but all 8+ days old — outside the 7-day window, so the weekly cap doesn't see them."""
        from matchmaking.models import Application
        from zelda_api.quotas import has_credits_for
        Application.objects.create(user=self.user, company_name='WeeklyCo', is_premium=True)
        self._memo(self.user, n=40, created_days_ago=8)
        self.assertTrue(has_credits_for(self.user, 'memo'))

    def test_document_ingest_blocked_by_weekly_cap_returns_quota_exceeded(self):
        from matchmaking.models import Application
        Application.objects.create(user=self.user, company_name='WeeklyCo', is_premium=True)
        self._memo(self.user, n=40)
        self.client.force_login(self.user)
        f = SimpleUploadedFile('deck.txt', b'We build tools for SaaS teams.', content_type='text/plain')
        response = self.client.post(
            reverse('zelda_api:document_ingest'),
            data={'file': f, 'document_type': 'pitch_deck', 'source_entity': 'WeeklyCo'},
        )
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()['code'], 'quota_exceeded')

    def test_upgrade_message_names_the_weekly_window_when_that_is_the_blocker(self):
        from matchmaking.models import Application
        from zelda_api.quotas import upgrade_message
        Application.objects.create(user=self.user, company_name='WeeklyCo', is_premium=True)
        self._memo(self.user, n=40)
        self.assertIn("this week", upgrade_message(self.user))

    def test_usage_nearing_limit_true_past_80_percent_weekly(self):
        from matchmaking.models import Application
        from zelda_api.quotas import usage_nearing_limit
        Application.objects.create(user=self.user, company_name='WeeklyCo', is_premium=True)
        self._memo(self.user, n=33)  # 33/40 = 82.5%, past the 80% soft-warning threshold
        self.assertTrue(usage_nearing_limit(self.user))

    def test_usage_nearing_limit_false_well_under_80_percent(self):
        from matchmaking.models import Application
        from zelda_api.quotas import usage_nearing_limit
        Application.objects.create(user=self.user, company_name='WeeklyCo', is_premium=True)
        self._memo(self.user, n=5)
        self.assertFalse(usage_nearing_limit(self.user))


class ValuationTierTests(TestCase):
    """
    zelda_api/quotas.py's free-preview paywall: everyone can always
    generate a valuation now (no more upload-time block) — the tier
    ('preview' vs 'full') decides whether DocumentValuationView renders
    the complete report or redacts it. Investor/Buyer Premium get
    30/month at 'full' (250/month per Firm seat); everyone else always
    gets 'preview', unlockable per-document via valuation_unlock_price's
    role-based discount ladder (Firm cheapest, Investor/Buyer next, flat
    rate for Founder/Seller/role-less).
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def _valuation_doc(self, user, n=1, status='analyzed', valuation_tier='full'):
        for i in range(n):
            DocumentSource.objects.create(
                filename=f'val{i}.pdf', source_entity='ValCo', uploaded_by=user,
                document_type='business_valuation', status=status, valuation_tier=valuation_tier,
            )

    # -- valuation_tier_for_new_upload --

    def test_investor_premium_within_allowance_gets_full(self):
        from zelda_api.quotas import valuation_tier_for_new_upload
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('val_investor_ok', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        self._valuation_doc(user, n=5)

        self.assertEqual(valuation_tier_for_new_upload(user), 'full')

    def test_investor_free_tier_always_gets_preview(self):
        from zelda_api.quotas import valuation_tier_for_new_upload
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('val_investor_free', password='x')
        InvestorApplication.objects.create(user=user, is_premium=False)

        self.assertEqual(valuation_tier_for_new_upload(user), 'preview')

    def test_investor_premium_at_limit_falls_back_to_preview(self):
        from zelda_api.quotas import valuation_tier_for_new_upload
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('val_investor_limit', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        self._valuation_doc(user, n=30)

        self.assertEqual(valuation_tier_for_new_upload(user), 'preview')

    def test_buyer_premium_within_allowance_gets_full(self):
        from zelda_api.quotas import valuation_tier_for_new_upload
        from matchmaking.models import BuyerApplication
        user = User.objects.create_user('val_buyer_ok', password='x')
        BuyerApplication.objects.create(user=user, is_premium=True)
        self._valuation_doc(user, n=10)

        self.assertEqual(valuation_tier_for_new_upload(user), 'full')

    def test_firm_seat_within_allowance_gets_full(self):
        from zelda_api.quotas import valuation_tier_for_new_upload
        from matchmaking.models import Firm, FirmMembership, InvestorApplication
        user = User.objects.create_user('val_firm_ok', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        firm = Firm.objects.create(name='Acme Capital', verified_domain='acme.com', owner=user)
        FirmMembership.objects.create(firm=firm, user=user)
        self._valuation_doc(user, n=100)

        self.assertEqual(valuation_tier_for_new_upload(user), 'full')

    def test_firm_seat_at_limit_falls_back_to_preview(self):
        from zelda_api.quotas import valuation_tier_for_new_upload
        from matchmaking.models import Firm, FirmMembership, InvestorApplication
        user = User.objects.create_user('val_firm_limit', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        firm = Firm.objects.create(name='Acme Capital', verified_domain='acme.com', owner=user)
        FirmMembership.objects.create(firm=firm, user=user)
        self._valuation_doc(user, n=250)

        self.assertEqual(valuation_tier_for_new_upload(user), 'preview')

    def test_founder_premium_still_gets_preview_not_bundled(self):
        """Explicit per the original request: valuation is never bundled into Founder/Seller's monthly price."""
        from zelda_api.quotas import valuation_tier_for_new_upload
        from matchmaking.models import Application
        user = User.objects.create_user('val_founder_premium', password='x')
        Application.objects.create(user=user, company_name='FounderCo', is_premium=True)

        self.assertEqual(valuation_tier_for_new_upload(user), 'preview')

    def test_seller_gets_preview_same_as_founder(self):
        from zelda_api.quotas import valuation_tier_for_new_upload
        from matchmaking.models import SellerApplication
        user = User.objects.create_user('val_seller', password='x')
        SellerApplication.objects.create(user=user, company_name='SellerCo')

        self.assertEqual(valuation_tier_for_new_upload(user), 'preview')

    def test_role_less_user_gets_preview(self):
        """Same 'no role yet lands on the founder track' convention JourneyStatusAPIView uses."""
        from zelda_api.quotas import valuation_tier_for_new_upload
        user = User.objects.create_user('val_roleless', password='x')

        self.assertEqual(valuation_tier_for_new_upload(user), 'preview')

    def test_staff_always_gets_full(self):
        from zelda_api.quotas import valuation_tier_for_new_upload
        user = User.objects.create_user('val_staff', password='x', is_staff=True)

        self.assertEqual(valuation_tier_for_new_upload(user), 'full')

    def test_errored_valuation_documents_do_not_count_against_monthly_allowance(self):
        from zelda_api.quotas import valuation_tier_for_new_upload
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('val_investor_errors', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        self._valuation_doc(user, n=30, status='error')

        self.assertEqual(valuation_tier_for_new_upload(user), 'full')

    def test_preview_tier_documents_do_not_count_against_monthly_allowance(self):
        """A free preview never draws down a plan's included allowance — only a full unlock does."""
        from zelda_api.quotas import valuation_tier_for_new_upload
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('val_investor_previews', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        self._valuation_doc(user, n=30, valuation_tier='preview')

        self.assertEqual(valuation_tier_for_new_upload(user), 'full')

    # -- valuation_tier_status --

    def test_tier_status_reports_remaining_allowance_for_premium(self):
        from zelda_api.quotas import valuation_tier_status
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('val_status_investor', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        self._valuation_doc(user, n=5)

        result = valuation_tier_status(user)
        self.assertEqual(result, {'tier': 'full', 'remaining': 25, 'limit': 30, 'is_plan_premium': True})

    def test_tier_status_for_free_user_has_no_allowance_fields(self):
        from zelda_api.quotas import valuation_tier_status
        user = User.objects.create_user('val_status_free', password='x')

        result = valuation_tier_status(user)
        self.assertEqual(result, {'tier': 'preview', 'remaining': None, 'limit': None, 'is_plan_premium': False})

    # -- valuation_unlock_price --

    def test_unlock_price_for_founder_seller_and_roleless_is_flat_report_rate(self):
        from zelda_api.quotas import valuation_unlock_price
        from matchmaking.models import Application
        user = User.objects.create_user('val_unlock_founder', password='x')
        Application.objects.create(user=user, company_name='FounderCo')

        self.assertEqual(valuation_unlock_price(user), ('report', 9.99))

    def test_unlock_price_for_investor_buyer_is_overage_rate(self):
        from zelda_api.quotas import valuation_unlock_price
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('val_unlock_investor', password='x')
        InvestorApplication.objects.create(user=user, is_premium=False)

        self.assertEqual(valuation_unlock_price(user), ('overage', 5.00))

    def test_unlock_price_for_firm_member_is_firm_overage_rate(self):
        from zelda_api.quotas import valuation_unlock_price
        from matchmaking.models import Firm, FirmMembership, InvestorApplication
        user = User.objects.create_user('val_unlock_firm', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        firm = Firm.objects.create(name='Acme Capital', verified_domain='acme.com', owner=user)
        FirmMembership.objects.create(firm=firm, user=user)

        self.assertEqual(valuation_unlock_price(user), ('firm_overage', 1.99))

    # -- unlock_valuation_document --

    def test_unlock_flips_tier_and_creates_redeemed_purchase(self):
        from zelda_api.quotas import unlock_valuation_document
        from matchmaking.models import Application
        user = User.objects.create_user('val_unlock_flip', password='x')
        Application.objects.create(user=user, company_name='FounderCo')
        doc = DocumentSource.objects.create(
            filename='val.pdf', source_entity='FounderCo', uploaded_by=user,
            document_type='business_valuation', status='analyzed', valuation_tier='preview',
        )

        purchase = unlock_valuation_document(doc, 'report', 'cs_test_123')

        doc.refresh_from_db()
        self.assertEqual(doc.valuation_tier, 'full')
        self.assertEqual(purchase.user, user)
        self.assertEqual(purchase.purchase_type, 'report')
        self.assertEqual(purchase.redeemed_document_id, doc.id)
        self.assertIsNotNone(purchase.redeemed_at)
        self.assertEqual(purchase.stripe_checkout_session_id, 'cs_test_123')


class ValuationIngestGatingTests(TestCase):
    """
    API-level coverage: DocumentIngestView.post never blocks a
    business_valuation upload — every role always gets a 201 — but
    stamps the new document's valuation_tier from
    valuation_tier_for_new_upload so DocumentValuationView knows whether
    to render it in full or redact it to a preview.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def _upload(self, user, source_entity='FounderCo'):
        f = SimpleUploadedFile('cim.txt', b'Revenue is $2M.', content_type='text/plain')
        with mock.patch('zelda_api.pipeline_views.process_valuation_document_task.delay'):
            return self.client.post(
                reverse('zelda_api:document_ingest'),
                data={'file': f, 'document_type': 'business_valuation', 'source_entity': source_entity},
            )

    def test_founder_upload_always_succeeds_as_preview(self):
        from matchmaking.models import Application
        user = User.objects.create_user('ingest_founder_unpaid', password='x')
        Application.objects.create(user=user, company_name='FounderCo')
        self.client.force_login(user)

        response = self._upload(user)

        self.assertEqual(response.status_code, 201)
        doc = DocumentSource.objects.get(id=response.json()['document_id'])
        self.assertEqual(doc.valuation_tier, 'preview')

    def test_investor_premium_within_allowance_uploads_as_full(self):
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('ingest_investor_ok', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        self.client.force_login(user)

        response = self._upload(user, source_entity='ValCo')

        self.assertEqual(response.status_code, 201)
        doc = DocumentSource.objects.get(id=response.json()['document_id'])
        self.assertEqual(doc.valuation_tier, 'full')

    def test_investor_free_tier_upload_succeeds_as_preview_not_blocked(self):
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('ingest_investor_free', password='x')
        InvestorApplication.objects.create(user=user, is_premium=False)
        self.client.force_login(user)

        response = self._upload(user, source_entity='ValCo')

        self.assertEqual(response.status_code, 201)
        doc = DocumentSource.objects.get(id=response.json()['document_id'])
        self.assertEqual(doc.valuation_tier, 'preview')

    def test_memo_uploads_unaffected_still_use_shared_credit_pool(self):
        """Regression guard: only business_valuation gets the tier treatment — memo uploads must keep using has_credits_for."""
        user = User.objects.create_user('ingest_memo_unaffected', password='x')
        self.client.force_login(user)

        f = SimpleUploadedFile('deck.txt', b'We build tools for SaaS teams.', content_type='text/plain')
        with mock.patch('zelda_api.pipeline_views.process_document_pipeline.delay'):
            response = self.client.post(
                reverse('zelda_api:document_ingest'),
                data={'file': f, 'document_type': 'pitch_deck', 'source_entity': 'FounderCo'},
            )
        self.assertEqual(response.status_code, 201)


class ValuationRequestViewTests(TestCase):
    """Template-level coverage: valuation_request_view always renders the upload form, with a tier-status banner that varies by role/allowance."""

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def test_investor_premium_within_allowance_sees_form_and_remaining_count(self):
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('view_investor_ok', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:valuation_request'))

        self.assertContains(response, 'id="valuation-upload-form"')
        self.assertContains(response, '30 of 30 full valuations remaining this month')

    def test_founder_without_premium_still_sees_form_with_preview_notice(self):
        from matchmaking.models import Application
        user = User.objects.create_user('view_founder_unpaid', password='x')
        Application.objects.create(user=user, company_name='FounderCo')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:valuation_request'))

        self.assertContains(response, 'id="valuation-upload-form"')
        self.assertContains(response, 'Every upload gets a free preview')

    def test_investor_free_tier_sees_form_with_upgrade_link_not_blocked(self):
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('view_investor_free', password='x')
        InvestorApplication.objects.create(user=user, is_premium=False)
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:valuation_request'))

        self.assertContains(response, 'id="valuation-upload-form"')
        self.assertContains(response, 'upgrade to Premium')

    def test_investor_premium_at_limit_sees_form_with_preview_fallback_notice(self):
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('view_investor_limit', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        for i in range(30):
            DocumentSource.objects.create(
                filename=f'v{i}.pdf', source_entity='ValCo', uploaded_by=user,
                document_type='business_valuation', status='analyzed', valuation_tier='full',
            )
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:valuation_request'))

        self.assertContains(response, 'id="valuation-upload-form"')
        self.assertContains(response, 'this one will be a free preview')


class ValuationHistoryViewTests(TestCase):
    """
    zelda_api:valuation_history — the permanent library of a user's own
    valuation reports. Distinguishes purchased-per-report from
    included-with-a-plan purely from whether a redeemed ValuationPurchase
    row points at the document (see quotas.unlock_valuation_document —
    no purchase row exists at all for included-allowance runs), and
    numbers repeat uploads for the same company as versions rather than
    silently overwriting.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def _analyzed_doc(self, user, source_entity='TestCo'):
        return DocumentSource.objects.create(
            filename='deck.txt', source_entity=source_entity, uploaded_by=user,
            document_type='business_valuation', status='analyzed',
        )

    def test_shows_purchased_report_with_price_and_date(self):
        from django.utils import timezone
        from matchmaking.models import Application
        from zelda_api.models import ValuationPurchase

        user = User.objects.create_user('history_founder', password='x')
        Application.objects.create(user=user, company_name='FounderCo')
        doc = self._analyzed_doc(user, source_entity='FounderCo')
        purchase = ValuationPurchase.objects.create(
            user=user, purchase_type='report', redeemed_document=doc, redeemed_at=timezone.now(),
        )
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:valuation_history'))

        self.assertEqual(response.status_code, 200)
        reports = response.context['reports']
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]['purchase'], purchase)
        self.assertEqual(reports[0]['provenance_label'], 'Purchased — $9.99')
        self.assertContains(response, 'Purchased — $9.99')
        self.assertContains(response, purchase.paid_at.strftime('%b'))

    def test_shows_included_with_plan_label_when_no_purchase_record(self):
        from matchmaking.models import InvestorApplication

        user = User.objects.create_user('history_investor', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        self._analyzed_doc(user, source_entity='InvestorTargetCo')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:valuation_history'))

        reports = response.context['reports']
        self.assertEqual(len(reports), 1)
        self.assertIsNone(reports[0]['purchase'])
        self.assertEqual(reports[0]['provenance_label'], 'Included with Investor Premium')
        self.assertContains(response, 'Included with Investor Premium')

    def test_shows_included_with_firm_plan_label_for_firm_member(self):
        from django.utils import timezone
        from matchmaking.models import InvestorApplication, Firm, FirmMembership, BusinessEmailVerification

        user = User.objects.create_user('history_firm_member', password='x')
        InvestorApplication.objects.create(user=user, is_premium=False)
        BusinessEmailVerification.objects.create(
            user=user, business_email='history@acme.com', status='VERIFIED', verified_at=timezone.now(),
        )
        firm = Firm.objects.create(name='Acme Capital', verified_domain='acme.com', owner=user)
        FirmMembership.objects.create(firm=firm, user=user)
        self._analyzed_doc(user, source_entity='FirmTargetCo')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:valuation_history'))

        reports = response.context['reports']
        self.assertEqual(reports[0]['provenance_label'], "Included with your Firm plan")
        self.assertContains(response, "Included with your Firm plan")

    def test_repeat_uploads_for_same_company_number_as_versions(self):
        from matchmaking.models import Application

        user = User.objects.create_user('history_versions', password='x')
        Application.objects.create(user=user, company_name='RepeatCo')
        first = self._analyzed_doc(user, source_entity='Repeat Target Inc')
        second = self._analyzed_doc(user, source_entity='Repeat Target Inc.')  # same company, normalized
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:valuation_history'))

        by_id = {r['document'].id: r['version'] for r in response.context['reports']}
        self.assertEqual(by_id[first.id], 1)
        self.assertEqual(by_id[second.id], 2)

    def test_excludes_other_users_documents(self):
        from matchmaking.models import Application

        owner = User.objects.create_user('history_owner', password='x')
        other = User.objects.create_user('history_other', password='x')
        Application.objects.create(user=owner, company_name='OwnerCo')
        self._analyzed_doc(owner, source_entity='OwnerCo')
        self._analyzed_doc(other, source_entity='OtherCo')
        self.client.force_login(owner)

        response = self.client.get(reverse('zelda_api:valuation_history'))

        reports = response.context['reports']
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]['document'].source_entity, 'OwnerCo')

    def test_excludes_errored_documents(self):
        from matchmaking.models import Application

        user = User.objects.create_user('history_errored', password='x')
        Application.objects.create(user=user, company_name='ErrorCo')
        DocumentSource.objects.create(
            filename='bad.txt', source_entity='ErrorCo', uploaded_by=user,
            document_type='business_valuation', status='error',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:valuation_history'))

        self.assertEqual(len(response.context['reports']), 0)
        self.assertContains(response, "haven't generated a business valuation yet")

    def _full_doc(self, user, source_entity, low, high):
        doc = DocumentSource.objects.create(
            filename='deck.txt', source_entity=source_entity, uploaded_by=user,
            document_type='business_valuation', status='analyzed', valuation_tier='full',
        )
        BusinessValuationReport.objects.create(document=doc, valuation_low=low, valuation_high=high, confidence_score=0.5)
        return doc

    def test_second_full_version_shows_trend_vs_first(self):
        from matchmaking.models import Application
        user = User.objects.create_user('history_trend_founder', password='x')
        Application.objects.create(user=user, company_name='TrendCo', is_premium=True)
        self._full_doc(user, 'TrendCo', 1_000_000, 2_000_000)  # midpoint 1.5M
        self._full_doc(user, 'TrendCo', 1_500_000, 2_500_000)  # midpoint 2M -> +33%
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:valuation_history'))

        reports = {r['version']: r for r in response.context['reports']}
        self.assertIsNone(reports[1]['trend'])
        self.assertEqual(reports[2]['trend']['direction'], 'up')
        self.assertEqual(reports[2]['trend']['pct_change'], 33)
        self.assertEqual(reports[2]['previous_full_version'], 1)
        self.assertContains(response, 'since Version 1')

    def test_trend_skips_over_an_intervening_preview_version(self):
        """A locked preview version between two full ones must not become the trend's "previous" reference."""
        from matchmaking.models import Application
        user = User.objects.create_user('history_trend_skip', password='x')
        Application.objects.create(user=user, company_name='SkipCo', is_premium=True)
        self._full_doc(user, 'SkipCo', 1_000_000, 1_000_000)  # version 1, midpoint 1M
        DocumentSource.objects.create(
            filename='preview.txt', source_entity='SkipCo', uploaded_by=user,
            document_type='business_valuation', status='analyzed', valuation_tier='preview',
        )  # version 2, locked — no report to compare against
        self._full_doc(user, 'SkipCo', 1_100_000, 1_100_000)  # version 3, midpoint 1.1M -> +10% vs version 1

        self.client.force_login(user)
        response = self.client.get(reverse('zelda_api:valuation_history'))

        reports = {r['version']: r for r in response.context['reports']}
        self.assertIsNone(reports[2]['trend'])
        self.assertEqual(reports[3]['trend']['pct_change'], 10)
        self.assertEqual(reports[3]['previous_full_version'], 1)
        self.assertContains(response, 'since Version 1')

    def test_first_version_never_shows_a_trend(self):
        from matchmaking.models import Application
        user = User.objects.create_user('history_trend_first', password='x')
        Application.objects.create(user=user, company_name='FirstCo', is_premium=True)
        self._full_doc(user, 'FirstCo', 1_000_000, 2_000_000)
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:valuation_history'))

        self.assertIsNone(response.context['reports'][0]['trend'])


class ValuationTrendTests(TestCase):
    """zelda_api/valuation_trend.py — the "up/down X% since your last valuation" comparison, pure functions."""

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def _full_doc(self, user, source_entity, low, high, created_days_ago=0):
        from django.utils import timezone
        from datetime import timedelta
        doc = DocumentSource.objects.create(
            filename='deck.txt', source_entity=source_entity, uploaded_by=user,
            document_type='business_valuation', status='analyzed', valuation_tier='full',
        )
        if created_days_ago:
            DocumentSource.objects.filter(pk=doc.pk).update(created_at=timezone.now() - timedelta(days=created_days_ago))
            doc.refresh_from_db()
        report = BusinessValuationReport.objects.create(document=doc, valuation_low=low, valuation_high=high, confidence_score=0.5)
        return doc, report

    def test_get_previous_full_valuation_finds_earlier_same_company(self):
        from matchmaking.models import Application
        from zelda_api.valuation_trend import get_previous_full_valuation
        user = User.objects.create_user('trend_finder', password='x')
        Application.objects.create(user=user, company_name='FinderCo')
        first_doc, first_report = self._full_doc(user, 'FinderCo', 1_000_000, 1_000_000, created_days_ago=10)
        second_doc, _second_report = self._full_doc(user, 'FinderCo', 1_500_000, 1_500_000)

        found_doc, found_report = get_previous_full_valuation(second_doc)

        self.assertEqual(found_doc.id, first_doc.id)
        self.assertEqual(found_report.id, first_report.id)

    def test_get_previous_full_valuation_ignores_preview_tier_documents(self):
        from matchmaking.models import Application
        from zelda_api.valuation_trend import get_previous_full_valuation
        user = User.objects.create_user('trend_finder_preview', password='x')
        Application.objects.create(user=user, company_name='PreviewFinderCo')
        DocumentSource.objects.create(
            filename='preview.txt', source_entity='PreviewFinderCo', uploaded_by=user,
            document_type='business_valuation', status='analyzed', valuation_tier='preview',
        )
        second_doc, _ = self._full_doc(user, 'PreviewFinderCo', 1_000_000, 1_000_000)

        found_doc, found_report = get_previous_full_valuation(second_doc)

        self.assertIsNone(found_doc)
        self.assertIsNone(found_report)

    def test_get_previous_full_valuation_ignores_other_users_documents(self):
        from matchmaking.models import Application
        from zelda_api.valuation_trend import get_previous_full_valuation
        owner = User.objects.create_user('trend_owner', password='x')
        other = User.objects.create_user('trend_other', password='x')
        Application.objects.create(user=owner, company_name='SharedNameCo')
        Application.objects.create(user=other, company_name='SharedNameCo')
        self._full_doc(other, 'SharedNameCo', 1_000_000, 1_000_000, created_days_ago=10)
        second_doc, _ = self._full_doc(owner, 'SharedNameCo', 1_000_000, 1_000_000)

        found_doc, found_report = get_previous_full_valuation(second_doc)

        self.assertIsNone(found_doc)
        self.assertIsNone(found_report)

    def test_get_previous_full_valuation_ignores_different_company(self):
        from matchmaking.models import Application
        from zelda_api.valuation_trend import get_previous_full_valuation
        user = User.objects.create_user('trend_diff_company', password='x')
        Application.objects.create(user=user, company_name='CompanyA')
        self._full_doc(user, 'CompanyA', 1_000_000, 1_000_000, created_days_ago=10)
        second_doc, _ = self._full_doc(user, 'CompanyB', 1_000_000, 1_000_000)

        found_doc, found_report = get_previous_full_valuation(second_doc)

        self.assertIsNone(found_doc)
        self.assertIsNone(found_report)

    def test_compute_valuation_trend_up_and_down_and_flat(self):
        from zelda_api.valuation_trend import compute_valuation_trend
        user = User.objects.create_user('trend_compute', password='x')
        _doc_a, up_previous = self._full_doc(user, 'A', 1_000_000, 1_000_000)
        _doc_b, up_current = self._full_doc(user, 'A', 1_500_000, 1_500_000)
        up = compute_valuation_trend(up_current, up_previous)
        self.assertEqual(up['direction'], 'up')
        self.assertEqual(up['pct_change'], 50)

        _doc_c, down_previous = self._full_doc(user, 'B', 2_000_000, 2_000_000)
        _doc_d, down_current = self._full_doc(user, 'B', 1_000_000, 1_000_000)
        down = compute_valuation_trend(down_current, down_previous)
        self.assertEqual(down['direction'], 'down')
        self.assertEqual(down['pct_change'], -50)

        _doc_e, flat_previous = self._full_doc(user, 'C', 1_000_000, 1_000_000)
        _doc_f, flat_current = self._full_doc(user, 'C', 1_000_000, 1_000_000)
        flat = compute_valuation_trend(flat_current, flat_previous)
        self.assertEqual(flat['direction'], 'flat')
        self.assertEqual(flat['pct_change'], 0)

    def test_compute_valuation_trend_none_when_previous_missing_range(self):
        from zelda_api.valuation_trend import compute_valuation_trend
        user = User.objects.create_user('trend_missing_range', password='x')
        _doc, current = self._full_doc(user, 'A', 1_000_000, 1_000_000)
        no_range_doc = DocumentSource.objects.create(
            filename='x.txt', source_entity='A', uploaded_by=user,
            document_type='business_valuation', status='analyzed', valuation_tier='full',
        )
        no_range_report = BusinessValuationReport.objects.create(document=no_range_doc, confidence_score=0.5)

        self.assertIsNone(compute_valuation_trend(current, no_range_report))


class MalformedClaudeResponseTests(TestCase):
    """
    _call_claude_for_memo / _call_claude_for_valuation both catch
    json.JSONDecodeError specifically (as distinct from the generic
    Exception path AnthropicFailureDetectionTests already covers) when
    Claude returns truncated or non-JSON text — e.g. a response cut off
    by max_tokens mid-object. Confirms that branch is hit and handled
    the same way: an 'error' key, no fake row created.
    """

    def setUp(self):
        self.user = User.objects.create_user('malformed_doc_owner', password='x')
        self.pipeline = ZeldaIntelligencePipelineV2()

    def _doc(self, document_type='pitch_deck'):
        return DocumentSource.objects.create(
            filename='test.pdf', source_entity='Test Co',
            uploaded_by=self.user, document_type=document_type,
        )

    def _truncated_response(self):
        fake_response = mock.Mock()
        fake_response.content = [mock.Mock(text='{"executive_summary": "We build tools for teams that need to sca')]
        return fake_response

    def test_truncated_memo_json_returns_parsing_error(self):
        with mock.patch('anthropic.Anthropic') as mock_anthropic_cls:
            mock_anthropic_cls.return_value.messages.create.return_value = self._truncated_response()
            doc = self._doc()
            result = self.pipeline._generate_memo(doc, {'confidence': 0.5})

        self.assertIn('error', result)
        self.assertIn('parsing error', result['error'])
        self.assertFalse(IntelligenceMemo.objects.filter(document=doc).exists())

    def test_truncated_valuation_json_returns_parsing_error(self):
        with mock.patch('anthropic.Anthropic') as mock_anthropic_cls:
            mock_anthropic_cls.return_value.messages.create.return_value = self._truncated_response()
            doc = self._doc(document_type='business_valuation')
            result = self.pipeline._generate_valuation_report(doc, {'confidence': 0.5})

        self.assertIn('error', result)
        self.assertIn('parsing error', result['error'])
        self.assertFalse(BusinessValuationReport.objects.filter(document=doc).exists())

    def test_valuation_generation_succeeds_when_claude_returns_valid_json(self):
        """
        Positive-path sibling to AnthropicFailureDetectionTests'
        memo-success sanity check — no equivalent existed for valuation,
        so a valuation-specific JSON-shape regression could have slipped
        through undetected.
        """
        fake_response = mock.Mock()
        fake_response.content = [mock.Mock(text='{"business_overview": "Steady regional manufacturer.", "valuation_low": 3000000, "valuation_high": 7000000}')]

        with mock.patch('anthropic.Anthropic') as mock_anthropic_cls:
            mock_anthropic_cls.return_value.messages.create.return_value = fake_response
            doc = self._doc(document_type='business_valuation')
            result = self.pipeline._generate_valuation_report(doc, {'confidence': 0.5})

        self.assertNotIn('error', result)
        report = BusinessValuationReport.objects.get(document=doc)
        self.assertEqual(report.business_overview, 'Steady regional manufacturer.')


class DocumentMemoViewAnalyticsTests(TestCase):
    """
    Regression test for a real double-counting bug fixed this session:
    DocumentMemoView.get() called log_investor_event(..., 'memo_view')
    twice on every successful view by a non-owner investor (once right
    after the authorization check, again right before returning the
    response) — inflating deck-engagement/investor-interest analytics
    2x for the common case. Fixed to log exactly once, only on an actual
    successful view (not on the 202 "memo not generated yet" branch).
    """

    def setUp(self):
        from matchmaking.models import Application, InvestorApplication
        self.founder_user = User.objects.create_user('memo_analytics_founder', password='x')
        self.application = Application.objects.create(
            user=self.founder_user, company_name='AnalyticsCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.investor_user = User.objects.create_user('memo_analytics_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.doc = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='AnalyticsCo',
            document_type='pitch_deck', status='analyzed',
        )
        IntelligenceMemo.objects.create(
            document=self.doc, executive_summary='We build developer tools.', recommendation='NEEDS_REVIEW',
        )
        self.client.force_login(self.investor_user)

    def test_successful_view_logs_exactly_one_memo_view_event(self):
        from matchmaking.models import InvestorInterestEvent
        response = self.client.get(reverse('zelda_api:document_memo', args=[self.doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            InvestorInterestEvent.objects.filter(
                investor=self.investor_user, founder=self.application, event_type='memo_view',
            ).count(),
            1,
        )

    def test_pending_memo_logs_no_event(self):
        """The 202 "not yet generated" branch shouldn't count as a view."""
        from matchmaking.models import InvestorInterestEvent
        self.doc.memo.delete()
        response = self.client.get(reverse('zelda_api:document_memo', args=[self.doc.id]))
        self.assertEqual(response.status_code, 202)
        self.assertFalse(
            InvestorInterestEvent.objects.filter(investor=self.investor_user, founder=self.application).exists()
        )


class DocumentMemoViewPaywallTests(TestCase):
    """
    The base Intelligence Memo (executive summary, strengths/weaknesses,
    improvement recommendations) is Premium — same founder/seller-
    controlled-asset model as the IC Memo and Truth Delta: gated on the
    document owner's own Premium, not the viewer's. Sensitive fields are
    omitted entirely from the locked response (server-side redaction),
    not just hidden client-side.
    """

    def setUp(self):
        from matchmaking.models import Application, InvestorApplication
        self.founder_user = User.objects.create_user('memo_paywall_founder', password='x')
        self.application = Application.objects.create(
            user=self.founder_user, company_name='MemoPaywallCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.doc = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='MemoPaywallCo',
            document_type='pitch_deck', status='analyzed',
        )
        IntelligenceMemo.objects.create(
            document=self.doc, executive_summary='Secret summary text.', recommendation='NEEDS_REVIEW',
            completeness_score=0.8, citations_count=3,
        )
        self.investor_user = User.objects.create_user('memo_paywall_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.staff_user = User.objects.create_user('memo_paywall_staff', password='x', is_staff=True)

    def test_owner_gets_locked_response_when_not_premium(self):
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('zelda_api:document_memo', args=[self.doc.id]))
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['locked'])
        self.assertTrue(data['is_owner'])
        self.assertNotIn('sections', data)
        self.assertNotIn('recommendation', data)

    def test_owner_gets_full_response_when_premium(self):
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('zelda_api:document_memo', args=[self.doc.id]))
        data = response.json()
        self.assertFalse(data['locked'])
        self.assertEqual(data['sections']['executive_summary'], 'Secret summary text.')

    def test_investor_gets_locked_response_when_founder_not_premium(self):
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('zelda_api:document_memo', args=[self.doc.id]))
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['locked'])
        self.assertFalse(data['is_owner'])
        self.assertNotIn('sections', data)

    def test_investor_gets_full_response_when_founder_premium_without_investor_premium(self):
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('zelda_api:document_memo', args=[self.doc.id]))
        data = response.json()
        self.assertFalse(data['locked'])
        self.assertEqual(data['sections']['executive_summary'], 'Secret summary text.')

    def test_staff_gets_full_response_regardless_of_premium(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('zelda_api:document_memo', args=[self.doc.id]))
        data = response.json()
        self.assertFalse(data['locked'])
        self.assertEqual(data['sections']['executive_summary'], 'Secret summary text.')


class TruthDeltaEngineTests(TestCase):
    """
    TruthDeltaEngine.verify_document previously always returned a
    hardcoded overall_truth_score=85.0 regardless of input — this covers
    the rebuilt engine: real numeric discrepancy detection, honest
    'unknown' framing when no external data is found (never a fabricated
    score), and a grounded numeric fallback when Claude itself fails.
    """

    def setUp(self):
        self.user = User.objects.create_user('truthdelta_owner', password='x')
        self.doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Truthy Co',
            uploaded_by=self.user, document_type='pitch_deck',
        )

    def _claim(self, category='customers', claimed_value='500', claimed_value_numeric=500.0):
        from .truth_delta_models import ClaimedDatapoint
        return ClaimedDatapoint.objects.create(
            document=self.doc, category=category, claimed_value=claimed_value,
            claimed_value_numeric=claimed_value_numeric,
        )

    def _observed(self, category='customers', observed_value='100', observed_value_numeric=100.0, credibility=0.9):
        from .truth_delta_models import ObservedDatapoint, ExternalDataSource
        source, _ = ExternalDataSource.objects.get_or_create(
            source_type='crunchbase', defaults={'source_name': 'Crunchbase'},
        )
        return ObservedDatapoint.objects.create(
            document=self.doc, category=category, observed_value=observed_value,
            observed_value_numeric=observed_value_numeric, source=source,
            source_credibility=credibility, extraction_method='api',
        )

    def test_no_claims_returns_none(self):
        from .truth_delta_engine import TruthDeltaEngine
        result = TruthDeltaEngine().verify_document(self.doc.id)
        self.assertIsNone(result)

    def test_no_external_data_found_is_honest_not_a_fabricated_score(self):
        """No observed data or news at all -> null score, 'unknown' risk, not the old hardcoded 85.0."""
        self._claim()
        with mock.patch('zelda_api.truth_delta_engine.data_source_manager') as mock_manager:
            mock_manager.create_observed_datapoints.return_value = []
            mock_manager.fetch_news_headlines.return_value = []
            from .truth_delta_engine import TruthDeltaEngine
            report = TruthDeltaEngine().verify_document(self.doc.id)

        self.assertIsNotNone(report)
        self.assertIsNone(report.overall_truth_score)
        self.assertEqual(report.credibility_risk, 'unknown')
        self.assertIn('No public data', report.summary)

    def test_claude_judgment_used_when_available(self):
        self._claim(claimed_value='500', claimed_value_numeric=500.0)
        self._observed(observed_value='480', observed_value_numeric=480.0)

        fake_response = mock.Mock()
        fake_response.content = [mock.Mock(text=(
            '{"overall_truth_score": 88, "credibility_risk": "low", '
            '"summary": "Claim is close to the observed figure.", "per_claim": []}'
        ))]

        with mock.patch('zelda_api.truth_delta_engine.data_source_manager') as mock_manager, \
             mock.patch('anthropic.Anthropic') as mock_anthropic_cls:
            mock_manager.create_observed_datapoints.return_value = []
            mock_manager.fetch_news_headlines.return_value = []
            mock_anthropic_cls.return_value.messages.create.return_value = fake_response
            from .truth_delta_engine import TruthDeltaEngine
            report = TruthDeltaEngine().verify_document(self.doc.id)

        self.assertEqual(report.overall_truth_score, 88.0)
        self.assertEqual(report.credibility_risk, 'low')
        self.assertEqual(report.summary, 'Claim is close to the observed figure.')
        self.assertEqual(len(report.details['claims']), 1)
        self.assertEqual(len(report.details['observed']), 1)

    def test_claude_failure_falls_back_to_grounded_numeric_score(self):
        """Claim=120 vs observed=100 -> 20% over -> numeric fallback score 80, 'low' risk. Never crashes, never invents a number."""
        self._claim(claimed_value='120', claimed_value_numeric=120.0)
        self._observed(observed_value='100', observed_value_numeric=100.0)

        with mock.patch('zelda_api.truth_delta_engine.data_source_manager') as mock_manager, \
             mock.patch('anthropic.Anthropic') as mock_anthropic_cls:
            mock_manager.create_observed_datapoints.return_value = []
            mock_manager.fetch_news_headlines.return_value = []
            mock_anthropic_cls.return_value.messages.create.side_effect = Exception('simulated API failure')
            from .truth_delta_engine import TruthDeltaEngine
            report = TruthDeltaEngine().verify_document(self.doc.id)

        self.assertEqual(report.overall_truth_score, 80.0)
        self.assertEqual(report.credibility_risk, 'low')
        self.assertIn('Claude was unavailable', report.summary)

    def test_claude_malformed_json_also_falls_back(self):
        self._claim(claimed_value='120', claimed_value_numeric=120.0)
        self._observed(observed_value='100', observed_value_numeric=100.0)

        fake_response = mock.Mock()
        fake_response.content = [mock.Mock(text='{"overall_truth_score": 8')]  # truncated

        with mock.patch('zelda_api.truth_delta_engine.data_source_manager') as mock_manager, \
             mock.patch('anthropic.Anthropic') as mock_anthropic_cls:
            mock_manager.create_observed_datapoints.return_value = []
            mock_manager.fetch_news_headlines.return_value = []
            mock_anthropic_cls.return_value.messages.create.return_value = fake_response
            from .truth_delta_engine import TruthDeltaEngine
            report = TruthDeltaEngine().verify_document(self.doc.id)

        self.assertEqual(report.overall_truth_score, 80.0)

    def test_unmatched_claim_never_penalizes_the_numeric_fallback(self):
        """A claim category with no observed match shouldn't drag the score down — absence of data isn't evidence of a lie."""
        self._claim(category='team_size', claimed_value='9000', claimed_value_numeric=9000.0)  # no matching observed row
        self._observed(category='customers', observed_value='100', observed_value_numeric=100.0)

        with mock.patch('zelda_api.truth_delta_engine.data_source_manager') as mock_manager, \
             mock.patch('anthropic.Anthropic') as mock_anthropic_cls:
            mock_manager.create_observed_datapoints.return_value = []
            mock_manager.fetch_news_headlines.return_value = []
            mock_anthropic_cls.return_value.messages.create.side_effect = Exception('simulated API failure')
            from .truth_delta_engine import TruthDeltaEngine
            report = TruthDeltaEngine().verify_document(self.doc.id)

        # No checked claims at all (the one claim has no matching category) -> unknown, not zero.
        self.assertIsNone(report.overall_truth_score)
        self.assertEqual(report.credibility_risk, 'unknown')


class TruthDeltaScoreViewTests(TestCase):
    """
    Regression test for a real bug: TruthDeltaScoreView.get() used a bare
    TruthDeltaReport.objects.get(document_id=...), which raises
    MultipleObjectsReturned (500s the endpoint) as soon as a document has
    been verified more than once, since nothing enforces one report per
    document. Fixed to always take the latest by created_at.
    """

    def setUp(self):
        from matchmaking.models import Application
        from .truth_delta_models import TruthDeltaReport
        self.user = User.objects.create_user('scoreview_owner', password='x')
        Application.objects.create(
            user=self.user, company_name='ScoreView Co', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', is_premium=True,
        )
        self.doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='ScoreView Co',
            uploaded_by=self.user, document_type='pitch_deck',
        )
        TruthDeltaReport.objects.create(document=self.doc, overall_truth_score=40.0, credibility_risk='high', summary='old run')
        TruthDeltaReport.objects.create(document=self.doc, overall_truth_score=90.0, credibility_risk='low', summary='latest run')
        self.client.force_login(self.user)

    def test_returns_latest_report_without_500ing(self):
        response = self.client.get(reverse('zelda_api:truth_delta_score', args=[self.doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['summary'], 'latest run')
        self.assertEqual(response.json()['overall_truth_score'], 90.0)


class TruthDeltaUIViewProvenanceTests(TestCase):
    """
    truth_delta_ui_view — confirms the per-claim provenance data
    (report.details) reaches the template as real, parseable JSON via the
    json_script tag, not just a Python dict that happens to render
    without erroring. This is what templates/truth_delta_dashboard.html's
    renderClaimsSection() reads client-side.
    """

    def setUp(self):
        from matchmaking.models import Application
        from .truth_delta_models import TruthDeltaReport
        self.user = User.objects.create_user('td_ui_owner', password='x')
        Application.objects.create(
            user=self.user, company_name='Apple Inc.', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', is_premium=True,
        )
        self.doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Apple Inc.',
            uploaded_by=self.user, document_type='pitch_deck',
        )
        self.report = TruthDeltaReport.objects.create(
            document=self.doc, overall_truth_score=97.0, credibility_risk='low',
            summary="Claim is directionally accurate.",
            details={
                'claims': [{'category': 'revenue', 'claimed_value': '$415 billion', 'unit': ''}],
                'observed': [{'category': 'revenue', 'observed_value': '416161000000.0', 'source': 'SEC EDGAR', 'time_period': 'FY2025 10-K'}],
                'per_claim': [{
                    'category': 'revenue', 'claimed': '$415 billion in revenue',
                    'observed': '$416.16 billion (SEC EDGAR, FY2025 10-K)',
                    'assessment': 'Directionally consistent, negligible rounding difference.',
                }],
            },
        )
        self.client.force_login(self.user)

    def test_details_context_matches_the_report(self):
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['details'], self.report.details)

    def test_per_claim_data_is_embedded_as_parseable_json(self):
        import json
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id]))
        html = response.content.decode()
        match = re.search(r'<script id="truth-delta-details-json"[^>]*>(.*?)</script>', html, re.DOTALL)
        self.assertIsNotNone(match, "json_script block for details not found in rendered page")
        parsed = json.loads(match.group(1))
        self.assertEqual(parsed['per_claim'][0]['category'], 'revenue')
        self.assertIn('416.16 billion', parsed['per_claim'][0]['observed'])

    def test_no_report_yet_renders_empty_details_without_error(self):
        doc2 = DocumentSource.objects.create(
            filename='pending.pdf', source_entity='Pending Co',
            uploaded_by=self.user, document_type='pitch_deck',
        )
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[doc2.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['details'], {})


class TruthDeltaUnlockedTests(TestCase):
    """
    truth_delta_unlocked — Truth Delta content is Premium, gated on the
    document owner's own Premium (founder/seller-controlled asset, same
    model as the IC Memo), not the viewer's. Staff always bypass.
    """

    def setUp(self):
        from matchmaking.models import Application, InvestorApplication
        self.founder_user = User.objects.create_user('tdu_founder', password='x')
        self.application = Application.objects.create(
            user=self.founder_user, company_name='TDUCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.doc = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='TDUCo', document_type='pitch_deck',
        )
        self.investor_user = User.objects.create_user('tdu_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.staff_user = User.objects.create_user('tdu_staff', password='x', is_staff=True)

    def test_unlocked_false_for_non_premium_founder(self):
        from .truth_delta_models import truth_delta_unlocked
        self.assertFalse(truth_delta_unlocked(self.founder_user, self.doc))

    def test_unlocked_true_for_premium_founder(self):
        from .truth_delta_models import truth_delta_unlocked
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        self.assertTrue(truth_delta_unlocked(self.founder_user, self.doc))

    def test_unlocked_true_for_staff_regardless_of_premium(self):
        from .truth_delta_models import truth_delta_unlocked
        self.assertTrue(truth_delta_unlocked(self.staff_user, self.doc))

    def test_unlocked_false_for_investor_when_founder_not_premium(self):
        from .truth_delta_models import truth_delta_unlocked
        self.assertFalse(truth_delta_unlocked(self.investor_user, self.doc))

    def test_unlocked_true_for_investor_when_founder_premium_without_investor_premium(self):
        from .truth_delta_models import truth_delta_unlocked
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        self.assertTrue(truth_delta_unlocked(self.investor_user, self.doc))


class TruthDeltaUIViewPaywallTests(TestCase):
    """
    truth_delta_ui_view — Zelda Lite/AI split: a non-Premium owner still sees
    real content (score, summary, category breakdown, a few sample claims),
    not a bare paywall. Zelda AI-only pieces (entity report, full claim list,
    clarification tools) stay gated behind Premium.
    """

    def setUp(self):
        from matchmaking.models import Application
        from .truth_delta_models import TruthDeltaReport
        self.founder_user = User.objects.create_user('tdp_founder', password='x')
        self.application = Application.objects.create(
            user=self.founder_user, company_name='TDPCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.doc = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='TDPCo', document_type='pitch_deck',
        )
        TruthDeltaReport.objects.create(
            document=self.doc, overall_truth_score=90.0, credibility_risk='low', summary='Secret summary text.',
        )

    def test_owner_sees_lite_tier_with_real_content_when_not_premium(self):
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Zelda Lite Verification')
        self.assertContains(response, 'Secret summary text.')
        self.assertContains(response, 'Upgrade to Zelda AI')

    def test_owner_sees_full_dashboard_when_premium(self):
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Secret summary text.')
        self.assertContains(response, 'Zelda AI — Full Verification')
        self.assertNotContains(response, 'Upgrade to Zelda AI')

    def test_staff_sees_full_dashboard_regardless_of_premium(self):
        staff_user = User.objects.create_user('tdp_staff', password='x', is_staff=True)
        self.client.force_login(staff_user)
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Secret summary text.')


class TruthDeltaScoreViewPaywallTests(TestCase):
    """TruthDeltaScoreView.get() — Zelda Lite tier (real data, truncated details) when owner isn't Premium."""

    def setUp(self):
        from matchmaking.models import Application
        from .truth_delta_models import TruthDeltaReport
        self.founder_user = User.objects.create_user('tsv_founder', password='x')
        self.application = Application.objects.create(
            user=self.founder_user, company_name='TSVCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.doc = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='TSVCo', document_type='pitch_deck',
        )
        TruthDeltaReport.objects.create(
            document=self.doc, overall_truth_score=90.0, credibility_risk='low', summary='Real summary.',
            details={'per_claim': [{'category': f'cat{i}', 'claimed': 'x', 'observed': None, 'assessment': 'a'} for i in range(5)]},
        )

    def test_returns_lite_tier_with_truncated_details_when_not_premium(self):
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('zelda_api:truth_delta_score', args=[self.doc.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['tier'], 'lite')
        self.assertEqual(data['summary'], 'Real summary.')
        self.assertEqual(len(data['details']['per_claim']), 3)

    def test_returns_full_tier_once_premium(self):
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('zelda_api:truth_delta_score', args=[self.doc.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['tier'], 'full')
        self.assertEqual(data['summary'], 'Real summary.')
        self.assertEqual(len(data['details']['per_claim']), 5)


class CanRequestClarificationTests(TestCase):
    """can_request_clarification — same viewer gate as the Truth Delta page itself."""

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        from matchmaking.models import InvestorApplication, BuyerApplication
        self.founder_user = User.objects.create_user('crc_founder', password='x')
        self.doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='CRC Co', uploaded_by=self.founder_user, document_type='pitch_deck',
        )
        self.investor_user = User.objects.create_user('crc_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.buyer_user = User.objects.create_user('crc_buyer', password='x')
        BuyerApplication.objects.create(
            user=self.buyer_user, full_name='B', email='b@t.com', company_name='Acq LLC',
            acquisition_thesis='thesis', budget_min=100_000, budget_max=1_000_000,
        )
        self.staff_user = User.objects.create_user('crc_staff', password='x', is_staff=True)
        self.stranger_user = User.objects.create_user('crc_stranger', password='x')

    def test_owner_cannot_request_clarification_from_self(self):
        from zelda_api.truth_delta_models import can_request_clarification
        self.assertFalse(can_request_clarification(self.founder_user, self.doc))

    def test_investor_can_request(self):
        from zelda_api.truth_delta_models import can_request_clarification
        self.assertTrue(can_request_clarification(self.investor_user, self.doc))

    def test_buyer_can_request(self):
        from zelda_api.truth_delta_models import can_request_clarification
        self.assertTrue(can_request_clarification(self.buyer_user, self.doc))

    def test_staff_can_request(self):
        from zelda_api.truth_delta_models import can_request_clarification
        self.assertTrue(can_request_clarification(self.staff_user, self.doc))

    def test_stranger_with_no_role_cannot_request(self):
        from zelda_api.truth_delta_models import can_request_clarification
        self.assertFalse(can_request_clarification(self.stranger_user, self.doc))

    def test_anonymous_cannot_request(self):
        from django.contrib.auth.models import AnonymousUser
        from zelda_api.truth_delta_models import can_request_clarification
        self.assertFalse(can_request_clarification(AnonymousUser(), self.doc))


class FlagTruthDeltaClaimViewTests(TestCase):
    """flag_truth_delta_claim — an investor/buyer flagging a specific unverified claim."""

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        from matchmaking.models import InvestorApplication, Application
        from zelda_api.truth_delta_models import TruthDeltaReport

        self.founder_user = User.objects.create_user('flag_founder', password='x')
        Application.objects.create(
            user=self.founder_user, company_name='FlagCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='FlagCo', uploaded_by=self.founder_user, document_type='pitch_deck',
        )
        self.report = TruthDeltaReport.objects.create(
            document=self.doc, overall_truth_score=40.0, credibility_risk='high', summary='Funding claim unverified.',
            details={'per_claim': [{'category': 'funding_raised', 'claimed': '$5M raised', 'observed': 'no external data found', 'assessment': 'Unverifiable.'}]},
        )
        self.investor_user = User.objects.create_user('flag_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.stranger_user = User.objects.create_user('flag_stranger', password='x')
        self.client.force_login(self.investor_user)

    def _flag_url(self, category='funding_raised'):
        return reverse('zelda_api:truth_delta_claim_flag', args=[self.doc.id, category])

    def test_investor_can_flag_a_claim(self):
        from zelda_api.truth_delta_models import ClarificationRequest
        response = self.client.post(self._flag_url(), {'message': 'Can you share the term sheet?'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ClarificationRequest.objects.filter(report=self.report, category='funding_raised').count(), 1)
        cr = ClarificationRequest.objects.get(report=self.report)
        self.assertEqual(cr.requested_by, self.investor_user)
        self.assertEqual(cr.message, 'Can you share the term sheet?')
        self.assertEqual(cr.status, 'PENDING')

    def test_flagging_notifies_the_founder(self):
        from notifications.models import Notification
        self.client.post(self._flag_url(), {'message': 'Can you share the term sheet?'})
        self.assertTrue(
            Notification.objects.filter(recipient=self.founder_user, notification_type='CLARIFICATION_REQUEST').exists()
        )

    def test_unknown_category_rejected(self):
        response = self.client.post(self._flag_url(category='not_a_real_category'), {'message': 'x'})
        self.assertEqual(response.status_code, 400)

    def test_stranger_with_no_role_cannot_flag(self):
        self.client.force_login(self.stranger_user)
        response = self.client.post(self._flag_url(), {'message': 'x'})
        self.assertEqual(response.status_code, 403)

    def test_owner_cannot_flag_their_own_claim(self):
        self.client.force_login(self.founder_user)
        response = self.client.post(self._flag_url(), {'message': 'x'})
        self.assertEqual(response.status_code, 403)

    def test_no_report_yet_returns_404(self):
        doc2 = DocumentSource.objects.create(
            filename='pending.pdf', source_entity='FlagCo', uploaded_by=self.founder_user, document_type='pitch_deck',
        )
        response = self.client.post(
            reverse('zelda_api:truth_delta_claim_flag', args=[doc2.id, 'funding_raised']), {'message': 'x'}
        )
        self.assertEqual(response.status_code, 404)


class RespondToClarificationRequestViewTests(TestCase):
    """respond_to_clarification_request — only the document owner (or staff) can respond."""

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        from matchmaking.models import InvestorApplication, Application
        from zelda_api.truth_delta_models import TruthDeltaReport, ClarificationRequest

        self.founder_user = User.objects.create_user('respond_founder', password='x')
        Application.objects.create(
            user=self.founder_user, company_name='RespondCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='RespondCo', uploaded_by=self.founder_user, document_type='pitch_deck',
        )
        self.report = TruthDeltaReport.objects.create(document=self.doc, overall_truth_score=40.0, credibility_risk='high')
        self.investor_user = User.objects.create_user('respond_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.clarification = ClarificationRequest.objects.create(
            report=self.report, category='funding_raised', requested_by=self.investor_user, message='Term sheet?',
        )
        self.stranger_user = User.objects.create_user('respond_stranger', password='x')

    def _respond_url(self):
        return reverse('zelda_api:truth_delta_claim_respond', args=[self.clarification.id])

    def test_owner_can_respond(self):
        self.client.force_login(self.founder_user)
        response = self.client.post(self._respond_url(), {'response_text': 'Attached the signed term sheet.'})
        self.assertEqual(response.status_code, 200)
        self.clarification.refresh_from_db()
        self.assertEqual(self.clarification.status, 'RESPONDED')
        self.assertEqual(self.clarification.response_text, 'Attached the signed term sheet.')
        self.assertIsNotNone(self.clarification.responded_at)

    def test_responding_notifies_the_requester(self):
        from notifications.models import Notification
        self.client.force_login(self.founder_user)
        self.client.post(self._respond_url(), {'response_text': 'Attached the signed term sheet.'})
        self.assertTrue(
            Notification.objects.filter(recipient=self.investor_user, notification_type='CLARIFICATION_RESPONSE').exists()
        )

    def test_requester_cannot_respond_to_their_own_request(self):
        self.client.force_login(self.investor_user)
        response = self.client.post(self._respond_url(), {'response_text': 'x'})
        self.assertEqual(response.status_code, 403)

    def test_stranger_cannot_respond(self):
        self.client.force_login(self.stranger_user)
        response = self.client.post(self._respond_url(), {'response_text': 'x'})
        self.assertEqual(response.status_code, 403)

    def test_empty_response_rejected(self):
        self.client.force_login(self.founder_user)
        response = self.client.post(self._respond_url(), {'response_text': '   '})
        self.assertEqual(response.status_code, 400)
        self.clarification.refresh_from_db()
        self.assertEqual(self.clarification.status, 'PENDING')


class TruthDeltaUIViewClarificationContextTests(TestCase):
    """truth_delta_ui_view's clarification-related context: can_request_clarification, is_document_owner, clarification_requests."""

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        from matchmaking.models import InvestorApplication, Application
        from zelda_api.truth_delta_models import TruthDeltaReport, ClarificationRequest

        self.founder_user = User.objects.create_user('ctx_founder', password='x')
        Application.objects.create(
            user=self.founder_user, company_name='CtxCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', is_premium=True,
        )
        self.doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='CtxCo', uploaded_by=self.founder_user, document_type='pitch_deck',
        )
        self.report = TruthDeltaReport.objects.create(document=self.doc, overall_truth_score=40.0, credibility_risk='high')
        self.investor_user = User.objects.create_user('ctx_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        ClarificationRequest.objects.create(
            report=self.report, category='funding_raised', requested_by=self.investor_user, message='Term sheet?',
        )

    def test_owner_view_shows_is_document_owner_true_and_cannot_request(self):
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id]))
        self.assertTrue(response.context['is_document_owner'])
        self.assertFalse(response.context['can_request_clarification'])
        self.assertEqual(len(response.context['clarification_requests']), 1)

    def test_investor_view_shows_can_request_true_and_not_owner(self):
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id]))
        self.assertFalse(response.context['is_document_owner'])
        self.assertTrue(response.context['can_request_clarification'])
        self.assertEqual(response.context['clarification_requests'][0]['category'], 'funding_raised')


class TruthDeltaReportRollupAndTrendTests(TestCase):
    """
    TruthDeltaReport.category_states()/.verifiability_stats() and the
    module-level diff_verification_reports() — the "X% verifiable" rollup
    and the "what changed since last time" trend, both derived only from
    `details` (never a separately stored number that could drift out of
    sync with the per-claim table itself).
    """

    def setUp(self):
        self.user = User.objects.create_user('rollup_owner', password='x')
        self.doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Rollup Co',
            uploaded_by=self.user, document_type='pitch_deck',
        )

    def _report(self, per_claim=None, claims=None):
        from .truth_delta_models import TruthDeltaReport
        return TruthDeltaReport.objects.create(
            document=self.doc, overall_truth_score=80.0, credibility_risk='low', summary='test',
            details={'claims': claims or [], 'per_claim': per_claim or []},
        )

    def test_verifiability_stats_counts_only_claims_with_real_evidence(self):
        report = self._report(per_claim=[
            {'category': 'revenue', 'claimed': '$1M', 'observed': '$1.1M (SEC EDGAR)', 'assessment': 'ok'},
            {'category': 'funding', 'claimed': '$500K', 'observed': 'no external data found', 'assessment': 'unverifiable'},
        ])
        stats = report.verifiability_stats()
        self.assertEqual(stats, {'total': 2, 'verified': 1, 'pct': 50.0})

    def test_verifiability_stats_with_no_claims_at_all(self):
        report = self._report()
        self.assertEqual(report.verifiability_stats(), {'total': 0, 'verified': 0, 'pct': None})

    def test_category_states_without_per_claim_are_all_no_data(self):
        """The 'no external data found for this company at all' branch never sets per_claim — every claim is unchecked."""
        report = self._report(claims=[{'category': 'revenue'}, {'category': 'team'}])
        self.assertEqual(report.category_states(), {'revenue': 'no_data', 'team': 'no_data'})

    def test_diff_detects_newly_verified_category(self):
        from .truth_delta_models import diff_verification_reports
        older = self._report(per_claim=[{'category': 'funding', 'observed': 'no external data found'}])
        newer = self._report(per_claim=[{'category': 'funding', 'observed': '$2M (Crunchbase)'}])
        diff = diff_verification_reports(newer, older)
        self.assertEqual(diff['newly_verified'], ['funding'])
        self.assertEqual(diff['lost_verification'], [])

    def test_diff_detects_lost_verification_only_for_categories_checked_in_both(self):
        from .truth_delta_models import diff_verification_reports
        older = self._report(per_claim=[
            {'category': 'market', 'observed': '$50B (per prior filing)'},
            {'category': 'revenue', 'observed': '$1M (SEC EDGAR)'},
        ])
        newer = self._report(per_claim=[
            {'category': 'market', 'observed': 'no external data found'},
            # 'revenue' isn't mentioned in the newer report at all — must NOT count as "lost."
        ])
        diff = diff_verification_reports(newer, older)
        self.assertEqual(diff['lost_verification'], ['market'])
        self.assertNotIn('revenue', diff['lost_verification'])

    def test_diff_with_no_changes_is_empty(self):
        from .truth_delta_models import diff_verification_reports
        older = self._report(per_claim=[{'category': 'revenue', 'observed': '$1M (SEC EDGAR)'}])
        newer = self._report(per_claim=[{'category': 'revenue', 'observed': '$1.05M (SEC EDGAR)'}])
        diff = diff_verification_reports(newer, older)
        self.assertEqual(diff, {'newly_verified': [], 'lost_verification': []})


class EntityVerificationTests(TestCase):
    """
    Entity Integrity v1 (Sprint 1): domain-age lookup + timeline-
    consistency — a distinct question from Truth Delta's "are the claims
    internally consistent" ("does this company exist as claimed?").
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    # --- extract_domain ---

    def test_extract_domain_strips_scheme_and_www(self):
        from .entity_verification import extract_domain
        self.assertEqual(extract_domain('https://www.example.com/path'), 'example.com')

    def test_extract_domain_handles_bare_domain(self):
        from .entity_verification import extract_domain
        self.assertEqual(extract_domain('example.com'), 'example.com')

    def test_extract_domain_strips_port(self):
        from .entity_verification import extract_domain
        self.assertEqual(extract_domain('http://example.com:8080'), 'example.com')

    def test_extract_domain_does_not_over_strip_leading_w(self):
        # A real regression risk with naive prefix stripping (e.g. str.lstrip('www.'))
        # is eating legitimate leading characters from a domain like 'wex.com'.
        from .entity_verification import extract_domain
        self.assertEqual(extract_domain('https://wex.com'), 'wex.com')

    def test_extract_domain_none_for_blank(self):
        from .entity_verification import extract_domain
        self.assertIsNone(extract_domain(''))
        self.assertIsNone(extract_domain(None))

    # --- lookup_domain_creation_date ---

    def test_lookup_returns_error_for_no_domain(self):
        from .entity_verification import lookup_domain_creation_date
        result_date, error = lookup_domain_creation_date(None)
        self.assertIsNone(result_date)
        self.assertIn('No company website', error)

    def test_lookup_parses_single_creation_date(self):
        from datetime import datetime
        from unittest.mock import patch, MagicMock
        from .entity_verification import lookup_domain_creation_date
        mock_result = MagicMock(creation_date=datetime(2015, 3, 1))
        with patch('whois.whois', return_value=mock_result):
            result_date, error = lookup_domain_creation_date('example.com')
        self.assertEqual(result_date, datetime(2015, 3, 1).date())
        self.assertEqual(error, '')

    def test_lookup_parses_list_of_creation_dates(self):
        # Some WHOIS servers return multiple records; the earliest/first is used.
        from datetime import datetime
        from unittest.mock import patch, MagicMock
        from .entity_verification import lookup_domain_creation_date
        mock_result = MagicMock(creation_date=[datetime(2015, 3, 1), datetime(2015, 3, 2)])
        with patch('whois.whois', return_value=mock_result):
            result_date, error = lookup_domain_creation_date('example.com')
        self.assertEqual(result_date, datetime(2015, 3, 1).date())

    def test_lookup_handles_no_creation_date_found(self):
        from unittest.mock import patch, MagicMock
        from .entity_verification import lookup_domain_creation_date
        mock_result = MagicMock(creation_date=None)
        with patch('whois.whois', return_value=mock_result):
            result_date, error = lookup_domain_creation_date('example.com')
        self.assertIsNone(result_date)
        self.assertIn('No registration date found', error)

    def test_lookup_handles_exception_without_leaking_raw_error(self):
        from unittest.mock import patch
        from .entity_verification import lookup_domain_creation_date
        with patch('whois.whois', side_effect=Exception('socket timeout at 10.0.0.1:43')):
            result_date, error = lookup_domain_creation_date('example.com')
        self.assertIsNone(result_date)
        self.assertNotIn('10.0.0.1', error)
        self.assertIn('unavailable', error)

    # --- compute_timeline_flags ---

    def test_flags_large_gap_between_founding_and_domain(self):
        from datetime import date
        from .entity_verification import compute_timeline_flags
        flags = compute_timeline_flags(2016, date(2025, 1, 1))
        self.assertEqual(len(flags), 1)
        self.assertIn('2016', flags[0])
        self.assertIn('2025', flags[0])

    def test_no_flag_for_small_gap(self):
        from datetime import date
        from .entity_verification import compute_timeline_flags
        flags = compute_timeline_flags(2023, date(2024, 6, 1))
        self.assertEqual(flags, [])

    def test_no_flag_when_founding_year_missing(self):
        from datetime import date
        from .entity_verification import compute_timeline_flags
        self.assertEqual(compute_timeline_flags(None, date(2024, 1, 1)), [])

    def test_no_flag_when_domain_date_missing(self):
        from .entity_verification import compute_timeline_flags
        self.assertEqual(compute_timeline_flags(2016, None), [])

    # --- build_entity_verification_report ---

    def test_build_report_for_founder_with_website_and_history(self):
        from datetime import date
        from unittest.mock import patch, MagicMock
        from matchmaking.models import Application
        from .entity_verification import build_entity_verification_report

        founder_user = User.objects.create_user('entver_founder', password='x')
        Application.objects.create(
            user=founder_user, company_name='EntVerCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', years_in_business=8,
            company_website='https://www.entverco.com',
        )
        doc = DocumentSource.objects.create(
            uploaded_by=founder_user, filename='deck.pdf', source_entity='EntVerCo', document_type='pitch_deck',
        )
        mock_result = MagicMock(creation_date=date(2024, 1, 1))
        with patch('whois.whois', return_value=mock_result):
            report = build_entity_verification_report(doc)

        self.assertEqual(report.domain, 'entverco.com')
        self.assertEqual(report.domain_registered_date, date(2024, 1, 1))
        current_year = date.today().year
        self.assertEqual(report.claimed_founding_year, current_year - 8)
        self.assertEqual(len(report.timeline_flags), 1)

    def test_build_report_for_seller_uses_seller_profile(self):
        from datetime import date
        from unittest.mock import patch, MagicMock
        from matchmaking.models import SellerApplication
        from .entity_verification import build_entity_verification_report

        seller_user = User.objects.create_user('entver_seller', password='x')
        SellerApplication.objects.create(
            user=seller_user, company_name='SellCo', seller_name='S', email='s@t.com',
            description='test', industry='Retail', years_in_business=3,
            company_website='sellco.com',
        )
        doc = DocumentSource.objects.create(
            uploaded_by=seller_user, filename='cim.pdf', source_entity='SellCo', document_type='business_valuation',
        )
        mock_result = MagicMock(creation_date=None)
        with patch('whois.whois', return_value=mock_result):
            report = build_entity_verification_report(doc)

        self.assertEqual(report.domain, 'sellco.com')
        current_year = date.today().year
        self.assertEqual(report.claimed_founding_year, current_year - 3)

    def test_build_report_gracefully_handles_uploader_with_no_profile(self):
        from .entity_verification import build_entity_verification_report

        bare_user = User.objects.create_user('entver_bare', password='x')
        doc = DocumentSource.objects.create(
            uploaded_by=bare_user, filename='deck.pdf', source_entity='Bare', document_type='pitch_deck',
        )
        report = build_entity_verification_report(doc)

        self.assertEqual(report.domain, '')
        self.assertIsNone(report.claimed_founding_year)
        self.assertEqual(report.timeline_flags, [])
        self.assertIn('No company website', report.domain_lookup_error)

    # --- verify_entity_integrity task ---

    def test_task_saves_report(self):
        from datetime import date
        from unittest.mock import patch, MagicMock
        from matchmaking.models import Application
        from .entity_verification_models import EntityVerificationReport
        from .entity_verification_tasks import verify_entity_integrity

        founder_user = User.objects.create_user('entver_task_founder', password='x')
        Application.objects.create(
            user=founder_user, company_name='TaskCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', years_in_business=1,
            company_website='taskco.com',
        )
        doc = DocumentSource.objects.create(
            uploaded_by=founder_user, filename='deck.pdf', source_entity='TaskCo', document_type='pitch_deck',
        )
        mock_result = MagicMock(creation_date=date(2024, 1, 1))
        with patch('whois.whois', return_value=mock_result):
            result = verify_entity_integrity(doc.id)

        self.assertEqual(result['status'], 'success')
        self.assertTrue(EntityVerificationReport.objects.filter(document=doc).exists())

    def test_task_handles_missing_document(self):
        from .entity_verification_tasks import verify_entity_integrity
        result = verify_entity_integrity(999999)
        self.assertEqual(result['status'], 'error')

    # --- rendered in truth_delta_ui_view ---

    def test_dashboard_shows_entity_integrity_card_when_report_exists(self):
        from datetime import date
        from matchmaking.models import Application
        from .entity_verification_models import EntityVerificationReport

        founder_user = User.objects.create_user('entver_ui_founder', password='x')
        app = Application.objects.create(
            user=founder_user, company_name='UICo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', is_premium=True,
        )
        doc = DocumentSource.objects.create(
            uploaded_by=founder_user, filename='deck.pdf', source_entity='UICo', document_type='pitch_deck',
        )
        EntityVerificationReport.objects.create(
            document=doc, domain='uico.com', domain_registered_date=date(2020, 1, 1),
            claimed_founding_year=2016, timeline_flags=['Domain registered in 2020, 4 years after the claimed founding year (2016) — may warrant a closer look.'],
        )
        self.client.force_login(founder_user)
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Entity Integrity')
        self.assertContains(response, 'uico.com')
        self.assertContains(response, 'may warrant a closer look')

    def test_dashboard_omits_entity_integrity_card_when_no_report(self):
        from matchmaking.models import Application

        founder_user = User.objects.create_user('entver_ui_none_founder', password='x')
        Application.objects.create(
            user=founder_user, company_name='NoEntCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', is_premium=True,
        )
        doc = DocumentSource.objects.create(
            uploaded_by=founder_user, filename='deck.pdf', source_entity='NoEntCo', document_type='pitch_deck',
        )
        self.client.force_login(founder_user)
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Entity Integrity')

    # --- TruthDeltaVerifyView also queues entity verification ---

    def test_verify_view_queues_entity_integrity_task(self):
        from unittest.mock import patch
        from matchmaking.models import Application

        founder_user = User.objects.create_user('entver_verify_founder', password='x')
        Application.objects.create(
            user=founder_user, company_name='VerifyCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        doc = DocumentSource.objects.create(
            uploaded_by=founder_user, filename='deck.pdf', source_entity='VerifyCo', document_type='pitch_deck',
        )
        self.client.force_login(founder_user)
        with patch('zelda_api.truth_delta_tasks.verify_document_truth_delta.delay') as mock_td_delay, \
             patch('zelda_api.entity_verification_tasks.verify_entity_integrity.delay') as mock_ent_delay:
            response = self.client.post(reverse('zelda_api:truth_delta_verify', args=[doc.id]))
        self.assertEqual(response.status_code, 202)
        mock_td_delay.assert_called_once_with(doc.id)
        mock_ent_delay.assert_called_once_with(doc.id)


class SECEdgarIntegrationTests(TestCase):
    """
    SECFilingsIntegration._latest_annual_fact / extract_revenue against a
    realistic (trimmed) companyfacts payload shape — confirms the 10-K
    filtering and most-recent-period selection work without hitting the
    real SEC API.
    """

    def _companyfacts(self):
        return {
            'facts': {
                'us-gaap': {
                    'Revenues': {
                        'units': {
                            'USD': [
                                {'val': 900_000_000, 'end': '2023-12-31', 'form': '10-K', 'fy': 2023},
                                {'val': 1_100_000_000, 'end': '2024-12-31', 'form': '10-K', 'fy': 2024},
                                {'val': 300_000_000, 'end': '2025-03-31', 'form': '10-Q', 'fy': 2025},  # quarterly — must be ignored
                            ]
                        }
                    }
                },
                'dei': {
                    'EntityNumberOfEmployees': {
                        'units': {'pure': [{'val': 5200, 'end': '2024-12-31'}]}
                    }
                },
            }
        }

    def test_extract_revenue_picks_latest_10k_not_the_10q(self):
        from .truth_delta_sources import SECFilingsIntegration
        result = SECFilingsIntegration().extract_revenue(self._companyfacts())
        self.assertEqual(result, (1_100_000_000.0, '$'))

    def test_extract_revenue_prefers_most_recent_across_tags_not_first_tag_with_any_data(self):
        """
        Regression test for a real bug found via a live SEC EDGAR call
        during development: many filers switched from the 'Revenues' XBRL
        concept to 'RevenueFromContractWithCustomerExcludingAssessedTax'
        around 2018 (ASC 606 adoption). Picking the first tag in priority
        order that has ANY 10-K data returned multi-year-stale figures for
        a real company (Apple) even though the newer concept had current
        data. The most recent fact across ALL candidate tags must win.
        """
        from .truth_delta_sources import SECFilingsIntegration
        data = {
            'facts': {
                'us-gaap': {
                    # Checked first (higher priority tag) but only has old data.
                    'Revenues': {
                        'units': {'USD': [{'val': 200_000_000, 'end': '2017-09-30', 'form': '10-K', 'fy': 2017}]}
                    },
                    # Checked second, but has the genuinely current figure.
                    'RevenueFromContractWithCustomerExcludingAssessedTax': {
                        'units': {'USD': [{'val': 391_000_000_000, 'end': '2024-09-28', 'form': '10-K', 'fy': 2024}]}
                    },
                }
            }
        }
        result = SECFilingsIntegration().extract_revenue(data)
        self.assertEqual(result, (391_000_000_000.0, '$'))

    def test_extract_employees_reads_dei_concept(self):
        from .truth_delta_sources import SECFilingsIntegration
        self.assertEqual(SECFilingsIntegration().extract_employees(self._companyfacts()), 5200)

    def test_missing_concepts_return_none_not_a_crash(self):
        from .truth_delta_sources import SECFilingsIntegration
        integration = SECFilingsIntegration()
        self.assertIsNone(integration.extract_revenue({}))
        self.assertIsNone(integration.extract_employees({}))


class SECCompanyNameNormalizationTests(TestCase):
    """
    Regression coverage for a real bug found by the claim-extraction
    evaluation harness: SEC EDGAR's company search does a PREFIX match
    against its internal abbreviated "conformed name" ("MICROSOFT CORP",
    "STARBUCKS CORP", "COSTCO WHOLESALE CORP /NEW") — searching with the
    full legal name ("Microsoft Corporation") returned zero results,
    since "Corporation" never prefix-matches "CORP". Only 2 of 6 real
    companies in the evaluation corpus resolved before this fix.
    """

    def test_strips_trailing_inc(self):
        from .truth_delta_sources import SECFilingsIntegration
        self.assertEqual(SECFilingsIntegration._normalize_company_name_for_search('Apple Inc.'), 'Apple')

    def test_strips_trailing_corporation(self):
        from .truth_delta_sources import SECFilingsIntegration
        self.assertEqual(SECFilingsIntegration._normalize_company_name_for_search('Microsoft Corporation'), 'Microsoft')

    def test_strips_comma_inc(self):
        from .truth_delta_sources import SECFilingsIntegration
        self.assertEqual(SECFilingsIntegration._normalize_company_name_for_search('Nike, Inc.'), 'Nike')

    def test_strips_leading_the_and_trailing_company(self):
        from .truth_delta_sources import SECFilingsIntegration
        self.assertEqual(SECFilingsIntegration._normalize_company_name_for_search('The Coca-Cola Company'), 'Coca-Cola')

    def test_preserves_distinctive_middle_words(self):
        """Only the trailing legal suffix is stripped — "Wholesale" stays, since it's part of what makes the name findable."""
        from .truth_delta_sources import SECFilingsIntegration
        self.assertEqual(SECFilingsIntegration._normalize_company_name_for_search('Costco Wholesale Corporation'), 'Costco Wholesale')

    def test_name_with_no_suffix_is_unchanged(self):
        from .truth_delta_sources import SECFilingsIntegration
        self.assertEqual(SECFilingsIntegration._normalize_company_name_for_search('Nimbus Analytics'), 'Nimbus Analytics')

    def test_find_cik_retries_with_normalized_name_when_exact_name_finds_nothing(self):
        """
        Mocks the SEC HTTP call directly (no live network) — an empty feed
        for the exact legal name, a real result for the normalized name,
        confirming the fallback chain actually gets exercised end to end.
        """
        from .truth_delta_sources import SECFilingsIntegration
        empty_feed = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        found_feed = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><cik>0000789019</cik></entry></feed>'

        integration = SECFilingsIntegration()
        responses = [mock.Mock(status_code=200, text=empty_feed), mock.Mock(status_code=200, text=found_feed)]
        with mock.patch.object(integration.session, 'get', side_effect=responses) as mock_get:
            cik = integration._find_cik('Microsoft Corporation')

        self.assertEqual(cik, '0000789019')
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(mock_get.call_args_list[0].kwargs['params']['company'], 'Microsoft')
        self.assertEqual(mock_get.call_args_list[1].kwargs['params']['company'], 'Microsoft Corporation')


class ExtractNumericValueTests(TestCase):
    """
    Regression coverage for a real bug: the K/M/B multiplier used to be
    detected by scanning the ENTIRE insight sentence for the letter K/M/B
    anywhere, so a sentence like "...Marketing drove 500 signups" would
    spuriously multiply 500 by 1,000,000 just because "Marketing" contains
    an "M". Fixed to only read a multiplier immediately adjacent to the
    matched digits.
    """

    def test_million_suffix_directly_after_digits_applies(self):
        from .truth_delta_tasks import _extract_numeric_value
        self.assertEqual(_extract_numeric_value('$1M ARR'), 1_000_000.0)

    def test_unrelated_letter_m_elsewhere_in_sentence_does_not_multiply(self):
        from .truth_delta_tasks import _extract_numeric_value
        self.assertEqual(_extract_numeric_value('Programmatic Marketing drove 500 signups'), 500.0)

    def test_percentage_never_picks_up_a_stray_multiplier(self):
        from .truth_delta_tasks import _extract_numeric_value
        self.assertEqual(_extract_numeric_value('Grew 200% YoY, Marketing-led'), 200.0)

    def test_plain_count_with_no_suffix(self):
        from .truth_delta_tasks import _extract_numeric_value
        self.assertEqual(_extract_numeric_value('500 customers'), 500.0)

    def test_spelled_out_billion_applies_the_multiplier(self):
        """
        Regression test for a real bug found by the claim-extraction
        evaluation harness: real prose almost always spells out the
        multiplier ("$416 billion"), not the abbreviated form ("$416B").
        The single-letter-only check silently dropped the multiplier
        entirely, parsing "$416 billion" as bare 416 — not a missing
        claim, but one that looks successful and is off by 1e9.
        """
        from .truth_delta_tasks import _extract_numeric_value
        self.assertEqual(_extract_numeric_value('$416 billion in revenue for fiscal year 2025'), 416_000_000_000.0)

    def test_spelled_out_million_applies_the_multiplier(self):
        from .truth_delta_tasks import _extract_numeric_value
        self.assertEqual(_extract_numeric_value('generated $2.4 million in revenue last year'), 2_400_000.0)

    def test_spelled_out_thousand_applies_the_multiplier(self):
        from .truth_delta_tasks import _extract_numeric_value
        self.assertEqual(_extract_numeric_value('reached 500 thousand registered users'), 500_000.0)

    def test_spelled_out_multiplier_is_case_insensitive(self):
        from .truth_delta_tasks import _extract_numeric_value
        self.assertEqual(_extract_numeric_value('Revenue of $3 Billion was reported'), 3_000_000_000.0)

    def test_ambiguous_word_starting_with_billion_still_rejected(self):
        """A word merely starting with 'billion' (e.g. 'billionaire') must not be treated as the multiplier."""
        from .truth_delta_tasks import _extract_numeric_value
        self.assertEqual(_extract_numeric_value('backed by a $50 billionaire investor'), 50.0)


class ClaimExtractionCategoryMappingTests(TestCase):
    """
    Regression coverage for a real bug found by the claim-extraction
    evaluation harness: extract_claims_from_insights's category_mapping
    dict keys ('Customer', 'Growth', 'Users') never matched any category
    IntelligenceInsight actually produces (_analyze_document's real
    category names are Problem/Market/Revenue/Team/Product/Traction/
    Funding/Risk) — so Traction and Market insights, however well
    extracted, could never become a ClaimedDatapoint and reach Truth
    Delta at all. Fixed to a direct lookup against the real names.
    """

    def setUp(self):
        self.user = User.objects.create_user('category_mapping_owner', password='x')
        self.doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='MappingCo',
            uploaded_by=self.user, document_type='pitch_deck',
        )

    def _insight(self, category, insight_text):
        from .vector_models import IntelligenceInsight
        return IntelligenceInsight.objects.create(
            document=self.doc, insight_type='statement', category=category,
            insight_text=insight_text, confidence_score=90.0,
        )

    def test_traction_insight_reaches_a_claimed_datapoint(self):
        from .truth_delta_tasks import extract_claims_from_insights
        from .truth_delta_models import ClaimedDatapoint
        self._insight('Traction', 'The platform now serves 340 customers across North America.')
        with mock.patch('zelda_api.truth_delta_tasks.verify_document_truth_delta.delay'):
            result = extract_claims_from_insights.run(self.doc.id)
        self.assertEqual(result['claims_created'], 1)
        claim = ClaimedDatapoint.objects.get(document=self.doc)
        self.assertEqual(claim.category, 'customers')
        self.assertEqual(claim.claimed_value_numeric, 340.0)

    def test_market_insight_reaches_a_claimed_datapoint(self):
        from .truth_delta_tasks import extract_claims_from_insights
        from .truth_delta_models import ClaimedDatapoint
        self._insight('Market', 'Targeting a $50 billion addressable market in industrial IoT.')
        with mock.patch('zelda_api.truth_delta_tasks.verify_document_truth_delta.delay'):
            result = extract_claims_from_insights.run(self.doc.id)
        self.assertEqual(result['claims_created'], 1)
        claim = ClaimedDatapoint.objects.get(document=self.doc)
        self.assertEqual(claim.category, 'market_size')
        self.assertEqual(claim.claimed_value_numeric, 50_000_000_000.0)

    def test_narrative_categories_still_never_produce_a_claim(self):
        """Problem/Product/Risk are deliberately excluded — narrative, not verifiable numeric claims."""
        from .truth_delta_tasks import extract_claims_from_insights
        self._insight('Problem', 'The market is fragmented and inefficient.')
        self._insight('Product', 'Our platform centralizes the entire workflow.')
        self._insight('Risk', 'Competitive pressure from larger incumbents.')
        with mock.patch('zelda_api.truth_delta_tasks.verify_document_truth_delta.delay'):
            result = extract_claims_from_insights.run(self.doc.id)
        self.assertEqual(result['claims_created'], 0)


class ExtractionProvenanceTests(TestCase):
    """
    _smart_extract now returns a third value — {'rule', 'matched_keywords',
    'matched_sentence'} — alongside (value, confidence), and
    _analyze_document attaches it as a non-persisted attribute on the
    IntelligenceInsight instance it returns. Nothing here is written to
    the database; it exists purely so evaluate_claim_extraction --verbose
    can show exactly which rule/keyword/sentence produced (or
    mis-produced) a claim, rather than a future regression only being
    visible as "Revenue precision dropped" with no way to re-derive why.
    """

    def setUp(self):
        self.user = User.objects.create_user('provenance_owner', password='x')
        self.pipeline = ZeldaIntelligencePipelineV2()

    def test_primary_match_provenance_shape(self):
        result, confidence, provenance = self.pipeline._smart_extract(
            'Revenue', 'Acme Inc. generated $5 million in revenue last year.', 'revenue arr mrr'
        )
        self.assertIsNotNone(result)
        self.assertEqual(provenance['rule'], 'primary_match')
        self.assertIn('revenue', provenance['matched_keywords'])
        self.assertIn('revenue', provenance['matched_sentence'].lower())

    def test_fallback_match_provenance_shape(self):
        # 'employees' fallback path — the primary keyword list ('team
        # founder ceo experience background skill leadership') has no
        # match here, so this only succeeds via _extract_team_fallback.
        result, confidence, provenance = self.pipeline._smart_extract(
            'Team', 'The company has grown steadily and now lists 12 employees in its latest filing.', 'team founder ceo experience background skill leadership'
        )
        self.assertIsNotNone(result)
        self.assertEqual(provenance['rule'], 'fallback')
        self.assertEqual(provenance['matched_keywords'], [])

    def test_no_match_returns_none_provenance(self):
        result, confidence, provenance = self.pipeline._smart_extract('Funding', 'Nothing relevant here at all.', 'funding raise capital')
        self.assertIsNone(result)
        self.assertIsNone(provenance)

    def test_analyze_document_attaches_provenance_to_the_insight_without_persisting_it(self):
        from zelda_api.vector_models import DocumentSource
        doc = DocumentSource.objects.create(
            filename='test.pdf', source_entity='Acme Inc.', uploaded_by=self.user, document_type='pitch_deck',
        )
        text = "Acme Inc. generated $5 million in revenue last year."
        self.pipeline._chunk_document(doc, text)
        self.pipeline.used_chunks = set()
        analysis_result = self.pipeline._analyze_document(doc, text)

        revenue_insight = next(i for i in analysis_result['insights'] if i.category == 'Revenue')
        self.assertEqual(revenue_insight.extraction_provenance['rule'], 'primary_match')

        # Re-fetching from the DB must NOT have this attribute — it was
        # never a real model field, only an in-memory convenience.
        from zelda_api.vector_models import IntelligenceInsight
        refetched = IntelligenceInsight.objects.get(id=revenue_insight.id)
        self.assertFalse(hasattr(refetched, 'extraction_provenance'))


class EvaluationCorpusSchemaTests(TestCase):
    """
    Structural sanity checks for zelda_api/evaluation_corpus.py itself —
    catches a malformed entry (typo'd company_type, missing sector,
    duplicate id) before it silently produces a misleading eval report
    rather than a loud failure.
    """

    def test_every_entry_has_a_valid_company_type(self):
        from zelda_api.evaluation_corpus import CORPUS, COMPANY_TYPES
        for entry in CORPUS:
            self.assertIn(entry['company_type'], COMPANY_TYPES, f"{entry['id']} has an invalid company_type")

    def test_every_entry_has_a_sector(self):
        from zelda_api.evaluation_corpus import CORPUS
        for entry in CORPUS:
            self.assertTrue(entry.get('sector'), f"{entry['id']} is missing a sector tag")

    def test_no_duplicate_ids(self):
        from zelda_api.evaluation_corpus import CORPUS
        ids = [entry['id'] for entry in CORPUS]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate corpus entry id found")

    def test_business_for_sale_type_is_represented(self):
        """Regression guard: this document style was completely absent from the corpus until the stratification pass."""
        from zelda_api.evaluation_corpus import CORPUS
        business_for_sale_entries = [e for e in CORPUS if e['company_type'] == 'business_for_sale']
        self.assertGreaterEqual(len(business_for_sale_entries), 5)

    def test_every_annotation_covers_all_categories_exactly_once(self):
        from zelda_api.evaluation_corpus import CORPUS, ALL_CATEGORIES
        for entry in CORPUS:
            annotated_categories = [a['category'] for a in entry['annotations']]
            self.assertEqual(annotated_categories, ALL_CATEGORIES, f"{entry['id']} has a malformed annotation list")


class SmartExtractFallbackTests(TestCase):
    """
    Regression coverage for a real bug found via the live Truth Delta
    demo: ZeldaIntelligencePipelineV2's category fallbacks (used only when
    no sentence in the document matched a category's keywords at all)
    used to fabricate a claim regardless — e.g. the Funding fallback
    grabbed the FIRST dollar figure anywhere in the whole document (often
    an unrelated revenue number) and wrapped it in a templated "Secured
    $X in Series funding from institutional investors" sentence, even
    when the document never mentioned funding. Rebuilt to return None
    (no insight created for that category) unless a narrowly-scoped,
    literal fact is actually present — precision over recall.
    """

    def setUp(self):
        self.user = User.objects.create_user('fallback_doc_owner', password='x')
        self.pipeline = ZeldaIntelligencePipelineV2()

    def _analyze(self, raw_text, document_type='pitch_deck'):
        doc = DocumentSource.objects.create(
            filename='test.pdf', source_entity='Test Co',
            uploaded_by=self.user, document_type=document_type,
        )
        chunk_result = self.pipeline._chunk_document(doc, raw_text)
        self.assertNotIn('error', chunk_result)
        self.pipeline.used_chunks = set()
        analysis_result = self.pipeline._analyze_document(doc, raw_text)
        self.assertNotIn('error', analysis_result)
        return doc, {insight.category: insight for insight in analysis_result['insights']}

    def test_document_with_no_funding_mention_produces_no_funding_insight(self):
        """The exact scenario from the live demo: a revenue-only document must not fabricate a funding claim."""
        text = (
            "Acme Inc. generated approximately $415 billion in revenue for fiscal year 2025, "
            "driven by strong product performance across all geographic segments. "
            "Our team has grown to a global workforce spanning retail, engineering, and corporate functions."
        )
        doc, insights_by_category = self._analyze(text)
        self.assertNotIn('Funding', insights_by_category)
        self.assertIn('Revenue', insights_by_category)
        self.assertIn('$415', insights_by_category['Revenue'].insight_text)

    def test_dollar_amount_in_revenue_sentence_does_not_leak_into_funding_claim(self):
        """Direct regression test for the exact fabricated claim seen live: 'Secured $415 in Series funding...'."""
        text = "We generated $415 billion in revenue this year. No funding round has been announced."
        doc, insights_by_category = self._analyze(text)
        if 'Funding' in insights_by_category:
            self.assertNotIn('415', insights_by_category['Funding'].insight_text)

    def test_document_with_no_dollar_amounts_at_all_produces_no_fabricated_generic_claims(self):
        """Previously, an empty/irrelevant document still got generic filler claims for every category."""
        text = "This document contains no financial information of any kind whatsoever, only general prose."
        doc, insights_by_category = self._analyze(text)
        self.assertNotIn('Funding', insights_by_category)
        self.assertNotIn('Market', insights_by_category)
        self.assertNotIn('Revenue', insights_by_category)

    def test_genuine_funding_mention_is_still_captured(self):
        """The fix must not over-correct into never reporting funding at all when it's genuinely stated."""
        text = "The company raised $20M in Series B funding led by a top-tier venture fund."
        doc, insights_by_category = self._analyze(text)
        self.assertIn('Funding', insights_by_category)
        self.assertIn('20M', insights_by_category['Funding'].insight_text)

    def test_employee_count_fallback_still_recovers_a_real_literal_number(self):
        """Team's headcount fallback is safe to keep — it's a self-contained literal fact, not a borrowed number."""
        text = "This is a general company overview with no team-related keywords describing 45 employees on staff today."
        result = self.pipeline._get_smart_fallback('Team', text)
        self.assertEqual(result, "45 employees mentioned in the document.")

    def test_narrative_categories_never_fabricate_generic_filler(self):
        """Problem/Product/Risk previously always returned a canned sentence regardless of document content."""
        text = "Completely unrelated text with none of the expected keywords."
        self.assertIsNone(self.pipeline._get_smart_fallback('Problem', text))
        self.assertIsNone(self.pipeline._get_smart_fallback('Product', text))
        self.assertIsNone(self.pipeline._get_smart_fallback('Risk', text))

    def test_smart_extract_returns_none_confidence_zero_when_fallback_is_none(self):
        result, confidence, provenance = self.pipeline._smart_extract('Funding', 'No relevant content here.', 'funding raise capital')
        self.assertIsNone(result)
        self.assertEqual(confidence, 0.0)
        self.assertIsNone(provenance)

    def test_clean_value_extraction_preserves_decimal_and_spelled_out_multiplier(self):
        """
        Regression test for a bug the claim-extraction evaluation harness
        surfaced: _extract_clean_value's own Revenue/Funding/Market regexes
        used `[\\d,]+[MBK]?` with no decimal support, so "$2.4 million"
        matched only as far as "$2" — truncating both the decimal AND the
        multiplier word before _extract_numeric_value ever saw them,
        silently turning a $2.4M claim into a $2 claim two layers downstream.
        """
        cleaned = self.pipeline._extract_clean_value('Revenue', 'Nimbus Analytics generated $2.4 million in revenue last year.')
        self.assertIn('$2.4 million', cleaned)

    def test_revenue_sentence_does_not_also_produce_a_duplicate_traction_insight(self):
        """
        Regression test for a bug the claim-extraction evaluation harness
        surfaced after the category-mapping fix: Traction's own keyword
        list used to include 'revenue', so every revenue sentence also
        matched Traction's primary keyword scan and produced a second,
        mislabeled insight for the exact same figure — invisible until
        Traction claims started reaching ClaimedDatapoint at all.
        """
        text = "Acme Inc. generated approximately $416 billion in revenue for fiscal year 2025."
        doc, insights_by_category = self._analyze(text)
        self.assertIn('Revenue', insights_by_category)
        self.assertNotIn('Traction', insights_by_category)


class ThirdPartyAttributionTests(TestCase):
    """
    Regression coverage for a real false positive found by the
    claim-extraction evaluation harness: "Our largest competitor
    reported $200 million in revenue last year" was extracted as a
    Revenue claim about the SUBJECT company, when the number actually
    belongs to a named competitor. Pragmatic phrase-proximity check
    (competitor/rival/peer/industry leader), not full entity resolution —
    see ZeldaIntelligencePipelineV2.THIRD_PARTY_ATTRIBUTION_PATTERN.
    """

    def setUp(self):
        self.user = User.objects.create_user('attribution_doc_owner', password='x')
        self.pipeline = ZeldaIntelligencePipelineV2()

    def _analyze(self, raw_text):
        doc = DocumentSource.objects.create(
            filename='test.pdf', source_entity='Test Co',
            uploaded_by=self.user, document_type='pitch_deck',
        )
        self.pipeline._chunk_document(doc, raw_text)
        self.pipeline.used_chunks = set()
        analysis_result = self.pipeline._analyze_document(doc, raw_text)
        return doc, {insight.category: insight for insight in analysis_result['insights']}

    def test_competitor_revenue_is_not_attributed_to_the_subject_company(self):
        text = "Our largest competitor reported $200 million in revenue last year, while we are just getting started in this market."
        doc, insights_by_category = self._analyze(text)
        self.assertNotIn('Revenue', insights_by_category)

    def test_rival_funding_is_not_attributed_to_the_subject_company(self):
        text = "A rival in our space raised $50 million last quarter, well ahead of where we are today."
        doc, insights_by_category = self._analyze(text)
        self.assertNotIn('Funding', insights_by_category)

    def test_genuine_own_claim_still_extracted_when_no_third_party_language_present(self):
        """Sanity check that the guard doesn't over-suppress ordinary, unambiguous claims."""
        text = "We generated $5 million in revenue last year, up significantly from the prior year."
        doc, insights_by_category = self._analyze(text)
        self.assertIn('Revenue', insights_by_category)

    def test_narrative_categories_are_exempt_from_the_guard(self):
        """"Risk: competition from incumbents" is legitimate content, not a misattributed number, and Risk isn't numeric anyway."""
        text = "Our biggest risk is intense competition from a well-funded industry leader in this space."
        doc, insights_by_category = self._analyze(text)
        self.assertIn('Risk', insights_by_category)

    def test_fallback_path_also_respects_the_guard(self):
        """Directly exercises _find_amount_with_context, used by the Revenue/Funding/Market fallbacks."""
        text = "Unrelated filler sentence. A well-known industry leader posted $9 billion in revenue this year."
        result = self.pipeline._extract_revenue_fallback(text)
        self.assertIsNone(result)


class KeywordWordBoundaryMatchingTests(TestCase):
    """
    Regression coverage for a real precision regression the 98-document
    evaluation corpus surfaced: _smart_extract's keyword scan used plain
    substring containment (`kw in sentence_lower`), so Team's keyword
    "team" matched inside "teams" (e.g. "...for enterprise AI teams" in a
    funding sentence — nothing to do with headcount), and Funding's short
    keyword "ask" matched inside unrelated words like "task"/"basket".
    Precision dropped from 95.0% (25-doc corpus) to 86.6% (98-doc corpus)
    once sector diversity exposed how often this fired. Fixed to
    word-boundary matching.
    """

    def setUp(self):
        self.user = User.objects.create_user('word_boundary_owner', password='x')
        self.pipeline = ZeldaIntelligencePipelineV2()

    def _analyze(self, raw_text):
        doc = DocumentSource.objects.create(
            filename='test.pdf', source_entity='Test Co',
            uploaded_by=self.user, document_type='pitch_deck',
        )
        self.pipeline._chunk_document(doc, raw_text)
        self.pipeline.used_chunks = set()
        analysis_result = self.pipeline._analyze_document(doc, raw_text)
        return doc, {insight.category: insight for insight in analysis_result['insights']}

    def test_team_substring_inside_teams_does_not_trigger_team_category(self):
        text = "Cognivault raised $25 million in Series A funding to scale its model-evaluation infrastructure for enterprise AI teams."
        doc, insights_by_category = self._analyze(text)
        self.assertNotIn('Team', insights_by_category)
        self.assertIn('Funding', insights_by_category)

    def test_ask_substring_inside_task_does_not_trigger_funding_category(self):
        text = "Our top priority task this quarter is shipping the new onboarding flow ahead of schedule."
        doc, insights_by_category = self._analyze(text)
        self.assertNotIn('Funding', insights_by_category)

    def test_genuine_team_keyword_as_a_whole_word_still_matches(self):
        text = "Our founding team has deep experience building payments infrastructure at scale."
        doc, insights_by_category = self._analyze(text)
        self.assertIn('Team', insights_by_category)


class GrowthRevenueContextGuardTests(TestCase):
    """
    Regression coverage for the second half of the same precision
    regression: "growth" is a genuine, standalone Traction signal (e.g.
    "212% YoY growth in customers"), but the same word shows up
    constantly in ordinary revenue prose ("$270B... driven by growth in
    Azure"). Every observed false positive in the evaluation corpus
    (Microsoft, Visa, Netflix) was exactly a dollar-denominated revenue
    sentence that also happened to mention "growth." Fixed to suppress
    Traction only when 'growth' is the SOLE matching keyword AND the
    sentence carries revenue-dollar context — genuine traction claims
    with other traction language, or growth expressed as a bare
    percentage, are unaffected.
    """

    def setUp(self):
        self.user = User.objects.create_user('growth_guard_owner', password='x')
        self.pipeline = ZeldaIntelligencePipelineV2()

    def _analyze(self, raw_text):
        doc = DocumentSource.objects.create(
            filename='test.pdf', source_entity='Test Co',
            uploaded_by=self.user, document_type='pitch_deck',
        )
        self.pipeline._chunk_document(doc, raw_text)
        self.pipeline.used_chunks = set()
        analysis_result = self.pipeline._analyze_document(doc, raw_text)
        return doc, {insight.category: insight for insight in analysis_result['insights']}

    def test_revenue_sentence_mentioning_growth_does_not_also_trigger_traction(self):
        text = "Microsoft Corporation posted revenue of roughly $270 billion for its most recent fiscal year, led by growth in Azure, Microsoft 365, and LinkedIn."
        doc, insights_by_category = self._analyze(text)
        self.assertIn('Revenue', insights_by_category)
        self.assertNotIn('Traction', insights_by_category)

    def test_percentage_growth_claim_with_no_dollar_figure_still_triggers_traction(self):
        text = "Thistledown Analytics has seen 212% year-over-year growth in its customer base, with no paid marketing spend to date."
        doc, insights_by_category = self._analyze(text)
        self.assertIn('Traction', insights_by_category)

    def test_growth_alongside_genuine_traction_keyword_still_triggers_even_with_dollar_figure(self):
        """The guard only fires when 'growth' is the SOLE match — a sentence with real traction language alongside it is unaffected."""
        text = "We've seen strong growth this year: our platform now serves 500 customers who collectively pay us $2 million."
        doc, insights_by_category = self._analyze(text)
        self.assertIn('Traction', insights_by_category)


class SECAliasAndCachingTests(TestCase):
    """
    SECFilingsIntegration._find_cik's alias dictionary and caching layer
    — added alongside the company-name-normalization fix so brand names
    that don't share a root with their SEC legal name (Meta vs Meta
    Platforms, Google vs Alphabet) still resolve, and repeated lookups
    for the same company don't re-hit SEC every time.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_known_alias_is_tried_first(self):
        from zelda_api.truth_delta_sources import SECFilingsIntegration
        integration = SECFilingsIntegration()
        found_feed = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><cik>0001326801</cik></entry></feed>'
        with mock.patch.object(integration.session, 'get', return_value=mock.Mock(status_code=200, text=found_feed)) as mock_get:
            cik = integration._find_cik('Meta')
        self.assertEqual(cik, '0001326801')
        self.assertEqual(mock_get.call_args.kwargs['params']['company'], 'Meta Platforms')

    def test_successful_resolution_is_cached(self):
        from zelda_api.truth_delta_sources import SECFilingsIntegration
        integration = SECFilingsIntegration()
        found_feed = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><cik>0000320193</cik></entry></feed>'
        with mock.patch.object(integration.session, 'get', return_value=mock.Mock(status_code=200, text=found_feed)) as mock_get:
            integration._find_cik('Apple Inc.')
            integration._find_cik('Apple Inc.')
        self.assertEqual(mock_get.call_count, 1)

    def test_not_found_result_is_also_cached(self):
        from zelda_api.truth_delta_sources import SECFilingsIntegration
        integration = SECFilingsIntegration()
        empty_feed = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        with mock.patch.object(integration.session, 'get', return_value=mock.Mock(status_code=200, text=empty_feed)) as mock_get:
            first = integration._find_cik('Totally Fictional Startup Co')
            second = integration._find_cik('Totally Fictional Startup Co')
        self.assertIsNone(first)
        self.assertIsNone(second)
        # 2 real HTTP attempts (normalized + exact name) on the first call, 0 on the second (cached).
        self.assertEqual(mock_get.call_count, 2)


class SECResolverDiagnosticsTests(TestCase):
    """
    resolve_with_diagnostics — added so a coverage gap can be attributed
    to a specific cause (company genuinely not on SEC EDGAR vs. a
    transient network failure) rather than reported as one undifferentiated
    "not found," per the evaluation methodology point that a single
    coverage percentage conflates several very different failure modes.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_found_company_has_no_reason(self):
        from zelda_api.truth_delta_sources import SECFilingsIntegration
        integration = SECFilingsIntegration()
        found_feed = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><cik>0000320193</cik></entry></feed>'
        with mock.patch.object(integration.session, 'get', return_value=mock.Mock(status_code=200, text=found_feed)):
            cik, reason = integration.resolve_with_diagnostics('Apple Inc.')
        self.assertEqual(cik, '0000320193')
        self.assertIsNone(reason)

    def test_genuinely_absent_company_is_tagged_not_found(self):
        from zelda_api.truth_delta_sources import SECFilingsIntegration
        integration = SECFilingsIntegration()
        empty_feed = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        with mock.patch.object(integration.session, 'get', return_value=mock.Mock(status_code=200, text=empty_feed)):
            cik, reason = integration.resolve_with_diagnostics('Totally Fictional Startup Co')
        self.assertIsNone(cik)
        self.assertEqual(reason, 'not_found')

    def test_network_timeout_is_tagged_distinctly_from_not_found(self):
        import requests
        from zelda_api.truth_delta_sources import SECFilingsIntegration
        integration = SECFilingsIntegration()
        with mock.patch.object(integration.session, 'get', side_effect=requests.exceptions.Timeout('simulated timeout')):
            cik, reason = integration.resolve_with_diagnostics('Apple Inc.')
        self.assertIsNone(cik)
        self.assertEqual(reason, 'timeout')

    def test_timeout_stops_retrying_further_name_candidates(self):
        """A real network failure won't be fixed by trying a differently-worded name — shouldn't retry 3x against a dead connection."""
        import requests
        from zelda_api.truth_delta_sources import SECFilingsIntegration
        integration = SECFilingsIntegration()
        with mock.patch.object(integration.session, 'get', side_effect=requests.exceptions.Timeout('simulated timeout')) as mock_get:
            integration.resolve_with_diagnostics('Microsoft Corporation')
        self.assertEqual(mock_get.call_count, 1)


class StructuredContextRevenueExtractionTests(TestCase):
    """
    Regression coverage for a real bug found live: uploading a pitch deck
    stating "Current Revenue: $4.5M" alongside "Seeking: $20M Series-C
    funding" produced a valuation built on $20M ARR instead of the deck's
    actual $4.5M — _build_structured_context's revenue_pattern had an
    optional trailing keyword group, so it matched ANY dollar figure in
    ANY insight (funding ask, prior capital raised, etc.), not just ones
    actually describing revenue. Fixed by requiring the keyword adjacent
    to the dollar figure and preferring Revenue-category insights first.
    Shared by both the memo and valuation generation paths.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def _doc_with_insights(self, insights_data):
        """insights_data: list of (category, text, confidence_score) tuples."""
        uploader = User.objects.create_user('structctx_uploader', password='x')
        doc = DocumentSource.objects.create(
            filename='deck.pptx', source_entity='Qibby Saves LLC', document_type='business_valuation',
            uploaded_by=uploader,
        )
        from zelda_api.vector_models import IntelligenceInsight
        for category, text, confidence in insights_data:
            IntelligenceInsight.objects.create(
                document=doc, category=category, insight_text=text, confidence_score=confidence,
            )
        return doc

    def test_higher_confidence_funding_dollar_amount_is_not_mistaken_for_arr(self):
        """The exact Qibby scenario: a higher-confidence Funding insight with $20M must not shadow the real $4.5M Revenue insight."""
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        doc = self._doc_with_insights([
            ('Funding', 'Seeking: $20M Series-C funding.', 0.95),
            ('Funding', 'Prior Capital Raised: $20M.', 0.90),
            ('Revenue', 'Current Revenue: $4.5M.', 0.70),
        ])
        insights = doc.insights.all().order_by('-confidence_score')

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        self.assertIn('4.5', facts['arr'])
        self.assertNotIn('20', facts['arr'])

    def test_bare_dollar_amount_with_no_revenue_keyword_is_not_captured(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        doc = self._doc_with_insights([
            ('Funding', 'The company raised $20M from investors.', 0.9),
        ])
        insights = doc.insights.all().order_by('-confidence_score')

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        self.assertIsNone(facts['arr'])

    def test_real_arr_phrasing_still_extracted(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        doc = self._doc_with_insights([
            ('Revenue', 'The company reports $2.3M in ARR as of this quarter.', 0.8),
        ])
        insights = doc.insights.all().order_by('-confidence_score')

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        self.assertIn('2.3', facts['arr'])

    def test_uploaders_unrelated_founder_profile_does_not_contaminate_facts(self):
        """
        Regression for a real bug found live: an admin account with its own
        unrelated "Gmail" founder profile (raising_amount=$50,000) uploaded
        a standalone valuation for "Qibby Saves LLC" — the Gmail profile's
        $50,000 leaked into the Qibby report as the raise amount, alongside
        the correctly-extracted $20M Series-C from the deck's own text.
        _build_structured_context must not trust an Application's fields
        unless it's actually about the company being analyzed.
        """
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        from matchmaking.models import Application

        uploader = User.objects.create_user('contamination_uploader', password='x')
        Application.objects.create(
            user=uploader, company_name='Gmail', founder_name='F', email='f@t.com',
            description='unrelated company', raising_amount=50000,
        )
        doc = DocumentSource.objects.create(
            filename='deck.pptx', source_entity='Qibby Saves LLC', document_type='business_valuation',
            uploaded_by=uploader,
        )
        # Deliberately no Funding-category insight here — this test isolates
        # "does the unrelated profile's own raise_amount leak in when the
        # document itself says nothing about it," which is the original
        # bug. See ProvenancePrecedenceTests for the separate, now-correct
        # behavior when the document DOES state its own raise amount
        # (document wins over any profile value, related or not).
        from zelda_api.vector_models import IntelligenceInsight
        IntelligenceInsight.objects.create(
            document=doc, category='Revenue', insight_text='Current Revenue: $4.5M', confidence_score=95,
        )
        insights = doc.insights.all()

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        self.assertIsNone(facts['raise_amount'])

    def test_uploaders_own_matching_founder_profile_is_still_trusted(self):
        """The legitimate case — a founder uploading their own deck through their own dashboard — must be unaffected."""
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        from matchmaking.models import Application

        founder = User.objects.create_user('self_upload_founder', password='x')
        Application.objects.create(
            user=founder, company_name='Qibby Saves LLC', founder_name='F', email='f@t.com',
            description='test', raising_amount=20_000_000,
        )
        doc = DocumentSource.objects.create(
            filename='deck.pptx', source_entity='Qibby Saves LLC', document_type='business_valuation',
            uploaded_by=founder,
        )
        insights = doc.insights.all()

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        self.assertEqual(facts['raise_amount'], '20000000.00')


class ProvenancePrecedenceTests(TestCase):
    """
    The broader principle behind the uploader-contamination fix: facts fed
    to Claude should be traceable to a specific source (the document being
    analyzed, or a company-matched profile), with a clear precedence rule
    when both exist, not just "whichever value happened to get written
    first." Five things this covers, per the user's own breakdown:
      1. Cross-company isolation (ValuationDataIsolationEndToEndTests, above).
      2. Self-upload enrichment still works (also covered above, and here).
      3. Document precedence over stale profile data.
      4. No leakage from unrelated Application/DocumentSource/
         BusinessValuationReport rows elsewhere in the database.
      5. Provenance is queryable, not just "the value looks right" —
         facts['_provenance'][field] names one of four mutually-exclusive
         states (confirmed/document_only/profile_only/conflict), the
         backing document, and (for document-sourced values) the
         confidence of the insight that produced it — richer than a flat
         "which source won" flag, since a genuine disagreement between
         the two sources is preserved rather than silently discarded once
         document precedence resolves it.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def _doc(self, uploader, source_entity='Qibby Saves LLC'):
        return DocumentSource.objects.create(
            filename='deck.pptx', source_entity=source_entity, document_type='business_valuation',
            uploaded_by=uploader,
        )

    def _insight(self, doc, category, text, confidence):
        from zelda_api.vector_models import IntelligenceInsight
        return IntelligenceInsight.objects.create(
            document=doc, category=category, insight_text=text, confidence_score=confidence,
        )

    # -- 3. Document precedence over stale profile data --

    def test_document_team_size_overrides_stale_profile_team_size(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        from matchmaking.models import Application

        founder = User.objects.create_user('precedence_founder', password='x')
        Application.objects.create(
            user=founder, company_name='Qibby Saves LLC', founder_name='F', email='f@t.com',
            description='test', team_size=120,  # stale — the deck says otherwise
        )
        doc = self._doc(founder)
        self._insight(doc, 'Traction', '200 employees supporting platform growth', 50)
        insights = doc.insights.all()

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        self.assertIn('200', facts['team_size'])
        self.assertNotIn('120', facts['team_size'])
        provenance = facts['_provenance']['team_size']
        self.assertEqual(provenance['source'], 'document')
        # Both sources had a value and they genuinely disagree (120 vs
        # 200) — 'conflict', not a plain 'document_only', since the
        # profile's competing value existed and is worth keeping visible.
        self.assertEqual(provenance['status'], 'conflict')
        self.assertEqual(provenance['profile_value'], '120')
        self.assertIn('200', provenance['document_value'])

    def test_no_document_team_size_falls_back_to_profile(self):
        """Self-upload enrichment, the opposite case — must keep working when the document says nothing about headcount."""
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        from matchmaking.models import Application

        founder = User.objects.create_user('precedence_founder2', password='x')
        Application.objects.create(
            user=founder, company_name='Qibby Saves LLC', founder_name='F', email='f@t.com',
            description='test', team_size=45,
        )
        doc = self._doc(founder)
        insights = doc.insights.all()  # no insights at all — nothing document-sourced

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        self.assertEqual(facts['team_size'], '45')
        provenance = facts['_provenance']['team_size']
        self.assertEqual(provenance['source'], 'profile')
        self.assertEqual(provenance['status'], 'profile_only')
        self.assertIsNone(provenance['document_value'])

    def test_document_raise_amount_overrides_stale_profile_raise_amount(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        from matchmaking.models import Application

        founder = User.objects.create_user('precedence_founder3', password='x')
        Application.objects.create(
            user=founder, company_name='Qibby Saves LLC', founder_name='F', email='f@t.com',
            description='test', raising_amount=500_000,  # stale
        )
        doc = self._doc(founder)
        self._insight(doc, 'Funding', 'Seeking: $20M Series-C funding.', 85)
        insights = doc.insights.all()

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        self.assertIn('20M', facts['raise_amount'])
        provenance = facts['_provenance']['raise_amount']
        self.assertEqual(provenance['source'], 'document')
        self.assertEqual(provenance['status'], 'conflict')  # $500K profile vs $20M document — genuinely disagree
        self.assertEqual(provenance['profile_value'], '500000.00')

    def test_confirmed_status_when_document_and_profile_agree(self):
        """The fourth state: both sources exist and actually agree — distinct from a conflict, and from either _only state."""
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        from matchmaking.models import Application

        founder = User.objects.create_user('precedence_founder4', password='x')
        Application.objects.create(
            user=founder, company_name='Qibby Saves LLC', founder_name='F', email='f@t.com',
            description='test', current_revenue=4_500_000,  # matches what the deck itself says
        )
        doc = self._doc(founder)
        self._insight(doc, 'Revenue', 'Current Revenue: $4.5M', 95)
        insights = doc.insights.all()

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        provenance = facts['_provenance']['revenue']
        self.assertEqual(provenance['status'], 'confirmed')
        self.assertEqual(provenance['source'], 'document')
        self.assertEqual(provenance['profile_value'], '4500000.00')

    # -- _values_agree unit coverage --

    def test_values_agree_across_different_formats_for_the_same_amount(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        self.assertTrue(ZeldaIntelligencePipelineV2._values_agree('$4.5M', '4500000.00'))
        self.assertTrue(ZeldaIntelligencePipelineV2._values_agree('200 employees', '200'))

    def test_values_disagree_for_genuinely_different_amounts(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        self.assertFalse(ZeldaIntelligencePipelineV2._values_agree('$20M', '500000.00'))
        self.assertFalse(ZeldaIntelligencePipelineV2._values_agree('200 employees', '120'))

    def test_values_agree_within_small_rounding_tolerance(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        self.assertTrue(ZeldaIntelligencePipelineV2._values_agree('$4.5M', '4500001.00'))

    def test_values_disagree_when_unparseable(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        self.assertFalse(ZeldaIntelligencePipelineV2._values_agree('unknown', '4500000.00'))

    # -- 4. No leakage from unrelated records elsewhere in the database --

    def test_unrelated_applications_and_documents_do_not_leak_in(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        from matchmaking.models import Application

        # An unrelated founder, an unrelated document, an unrelated
        # valuation report — none authored by or belonging to the actual
        # uploader/company below.
        other_founder = User.objects.create_user('unrelated_founder', password='x')
        Application.objects.create(
            user=other_founder, company_name='Totally Unrelated Inc', founder_name='X', email='x@t.com',
            description='unrelated', raising_amount=999_999, team_size=7,
        )
        other_doc = DocumentSource.objects.create(
            filename='other.pdf', source_entity='Totally Unrelated Inc', document_type='business_valuation',
            uploaded_by=other_founder,
        )
        BusinessValuationReport.objects.create(document=other_doc, confidence_score=0.9, valuation_low=1, valuation_high=2)
        self._insight(other_doc, 'Funding', 'Seeking: $999,999 in funding.', 85)

        # The actual document under test — a different uploader, no
        # founder profile at all, own insight text with its own figures.
        real_uploader = User.objects.create_user('real_uploader', password='x')
        doc = self._doc(real_uploader, source_entity='Qibby Saves LLC')
        self._insight(doc, 'Revenue', 'Current Revenue: $4.5M', 95)
        insights = doc.insights.all()

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        self.assertNotIn('999999', str(facts))
        self.assertNotIn('999,999', str(facts))
        self.assertNotEqual(facts.get('team_size'), '7')
        self.assertIn('4.5M', facts['revenue'])

    # -- 5. Provenance is queryable, not just implied by the final value --

    def test_provenance_names_source_document_and_confidence_for_document_sourced_field(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2

        uploader = User.objects.create_user('provenance_uploader', password='x')
        doc = self._doc(uploader, source_entity='Qibby Saves LLC')
        self._insight(doc, 'Revenue', 'Current Revenue: $4.5M', 95)
        insights = doc.insights.all()

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        provenance = facts['_provenance']['revenue']
        self.assertEqual(provenance['source'], 'document')
        self.assertEqual(provenance['status'], 'document_only')  # no company-matched profile at all here
        self.assertEqual(provenance['document_id'], doc.id)

    def test_revenue_provenance_populated_even_when_insight_text_is_already_a_bare_figure(self):
        """
        Regression: _extract_clean_value's own Revenue branch strips a
        Revenue-category insight down to close to a bare dollar figure
        before it's ever stored (e.g. "Current Revenue: $4.5M" ->
        "$4.5M" — no "revenue"/"ARR" keyword left adjacent to the number
        at all). revenue_pattern's keyword requirement (needed to stop a
        Funding-category insight's own figure from being misread as
        revenue) then made a real Revenue-category insight's own already-
        cleaned figure unmatchable, so revenue's provenance entry silently
        never got created for real, live-analyzed documents — found by
        checking Qibby's actual document after this feature shipped.
        """
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2

        uploader = User.objects.create_user('bare_figure_uploader', password='x')
        doc = self._doc(uploader, source_entity='Qibby Saves LLC')
        self._insight(doc, 'Revenue', '$4.5M', 95)  # exactly what _extract_clean_value actually stores
        insights = doc.insights.all()

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        self.assertIn('4.5M', facts['revenue'])
        self.assertIn('revenue', facts['_provenance'])
        provenance = facts['_provenance']['revenue']
        self.assertEqual(provenance['confidence'], 95)
        self.assertIsNone(provenance['profile_value'])

    def test_provenance_names_profile_source_with_no_document_id_or_confidence(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        from matchmaking.models import Application

        founder = User.objects.create_user('provenance_founder', password='x')
        Application.objects.create(
            user=founder, company_name='Qibby Saves LLC', founder_name='F', email='f@t.com',
            description='test', current_revenue=1_000_000,
        )
        doc = self._doc(founder, source_entity='Qibby Saves LLC')
        insights = doc.insights.all()  # nothing document-sourced

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        provenance = facts['_provenance']['revenue']
        self.assertEqual(provenance['source'], 'profile')
        self.assertEqual(provenance['status'], 'profile_only')
        self.assertIsNone(provenance['document_id'])
        self.assertIsNone(provenance['confidence'])
        self.assertIsNone(provenance['document_value'])

    def test_provenance_is_never_sent_to_claude(self):
        """The internal bookkeeping structure must not leak into the actual prompt."""
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2

        uploader = User.objects.create_user('provenance_prompt_uploader', password='x')
        doc = self._doc(uploader, source_entity='Qibby Saves LLC')
        self._insight(doc, 'Revenue', 'Current Revenue: $4.5M', 95)
        insights = doc.insights.all()

        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, insights)

        with mock.patch('anthropic.Anthropic') as mock_anthropic_cls:
            fake_response = mock.Mock()
            fake_response.content = [mock.Mock(text='{"business_overview": "x", "financial_summary": "x", "risk_report": "x", "valuation_summary": "x", "valuation_low": 1, "valuation_high": 2, "confidence": 0.5}')]
            mock_anthropic_cls.return_value.messages.create.return_value = fake_response
            pipeline._call_claude_for_valuation(doc, facts, list(insights))
            prompt_sent = str(mock_anthropic_cls.return_value.messages.create.call_args)

        self.assertNotIn('_provenance', prompt_sent)


class ValuationDataIsolationEndToEndTests(TestCase):
    """
    End-to-end regression for the uploader/subject cross-contamination bug
    (see StructuredContextRevenueExtractionTests for the unit-level
    coverage of the same fix) — this one goes through the real upload path
    a user actually hits: Founder A, authenticated, uploads a standalone
    valuation request for a DIFFERENT company (Founder B's), and none of
    Founder A's own founder-profile fields may leak into the facts Claude
    is asked to reason about. Captures the general requirement plainly:
    analysis is grounded in the company being analyzed, not in whoever
    happened to be logged in when they uploaded it.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

        from matchmaking.models import Application
        self.founder_a = User.objects.create_user('isolation_founder_a', password='x')
        Application.objects.create(
            user=self.founder_a, company_name='Acme Robotics', founder_name='A',
            email='a@t.com', description='Acme test', sector='Robotics', stage='Series B',
            raising_amount=5_000_000, current_revenue=1_000_000,
        )

    def _fake_claude_response(self):
        import json
        payload = {
            'business_overview': 'placeholder', 'financial_summary': 'placeholder',
            'risk_report': 'placeholder', 'valuation_summary': 'placeholder',
            'valuation_low': 1000000, 'valuation_high': 2000000, 'confidence': 0.5,
        }
        fake_response = mock.Mock()
        fake_response.content = [mock.Mock(text=json.dumps(payload))]
        return fake_response

    def test_founder_as_own_raise_amount_and_revenue_do_not_leak_into_founder_bs_valuation(self):
        self.client.force_login(self.founder_a)

        deck_text = (
            "Bright Health Analytics\n"
            "Current Revenue: $800K\n"
            "Seeking: $2M Series A funding.\n"
        )
        upload = SimpleUploadedFile('bright_health_deck.txt', deck_text.encode(), content_type='text/plain')

        with mock.patch('zelda_api.pipeline_views.process_valuation_document_task.delay'):
            response = self.client.post(
                reverse('zelda_api:document_ingest'),
                data={'file': upload, 'document_type': 'business_valuation', 'source_entity': 'Bright Health Analytics'},
            )
        self.assertEqual(response.status_code, 201)
        doc_id = response.json()['document_id']

        doc = DocumentSource.objects.get(id=doc_id)
        self.assertEqual(doc.uploaded_by, self.founder_a)  # Founder A uploaded it...
        self.assertEqual(doc.source_entity, 'Bright Health Analytics')  # ...about a different company entirely.

        # Run the real pipeline synchronously (mocking only the Claude
        # call, same pattern as MalformedClaudeResponseTests) so this
        # exercises the actual chunking -> analysis -> _build_structured_
        # context chain the async task would run, not a hand-built facts dict.
        with mock.patch('anthropic.Anthropic') as mock_anthropic_cls:
            mock_anthropic_cls.return_value.messages.create.return_value = self._fake_claude_response()
            from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
            pipeline = ZeldaIntelligencePipelineV2()
            pipeline.used_chunks = set()
            result = pipeline.process_valuation_document(doc, deck_text)
            self.assertEqual(result['status'], 'success')

            prompt_sent_to_claude = str(mock_anthropic_cls.return_value.messages.create.call_args)

        # Founder A's own figures must never reach the prompt...
        self.assertNotIn('5000000', prompt_sent_to_claude)
        self.assertNotIn('1000000', prompt_sent_to_claude)
        # ...while Bright Health's real figures do.
        self.assertIn('800K', prompt_sent_to_claude)
        self.assertIn('2M', prompt_sent_to_claude)


class AnalyzeDocumentCrossChunkTieBreakTests(TestCase):
    """
    Regression coverage for the second half of the same live bug: even
    after _build_structured_context stopped mistaking $20M-in-Funding for
    ARR, the actual $4.5M Revenue figure still never surfaced, because
    _analyze_document's cross-chunk loop had no tie-break at all — unlike
    _smart_extract's own within-chunk tie-break, which already prefers a
    sentence with a dollar figure over one without on an equal-confidence
    tie. Two chunks (a qualitative "Recurring subscription revenue model."
    and a later "$4.5M" chunk) both scored 95 confidence for the Revenue
    category, and the first one processed won purely by chunk order.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def test_dollar_figure_chunk_wins_tie_over_earlier_qualitative_chunk(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        from zelda_api.vector_models import DocumentChunk
        user = User.objects.create_user('tiebreak_uploader', password='x')
        doc = DocumentSource.objects.create(
            filename='deck.pptx', source_entity='Qibby Saves LLC', document_type='business_valuation',
            uploaded_by=user,
        )
        DocumentChunk.objects.create(
            document=doc, chunk_index=0, raw_text=(
                'Qibby Saves LLC\nBusiness Model\nEnterprise SaaS platform.\n'
                'Recurring subscription revenue.\nImplementation and onboarding services.'
            ), token_count=20,
        )
        DocumentChunk.objects.create(
            document=doc, chunk_index=1, raw_text=(
                'Qibby Saves LLC\nTraction\nCurrent Revenue: $4.5M\nPrior Capital Raised: $20M\n'
                '200 employees supporting platform growth.'
            ), token_count=20,
        )

        pipeline = ZeldaIntelligencePipelineV2()
        pipeline.used_chunks = set()
        result = pipeline._analyze_document(doc, 'unused raw text — chunks already exist')

        revenue_insight = next(i for i in result['insights'] if i.category == 'Revenue')
        self.assertIn('4.5', revenue_insight.insight_text)

    def test_earlier_dollar_figure_chunk_still_wins_when_no_tie(self):
        """Sanity check: the ordinary confidence > best_confidence path still works when there's no tie to break."""
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        from zelda_api.vector_models import DocumentChunk
        user = User.objects.create_user('tiebreak_uploader2', password='x')
        doc = DocumentSource.objects.create(
            filename='deck2.pptx', source_entity='Test Co', document_type='business_valuation',
            uploaded_by=user,
        )
        DocumentChunk.objects.create(
            document=doc, chunk_index=0, raw_text='Traction\nCurrent Revenue: $9M annual recurring revenue.',
            token_count=10,
        )

        pipeline = ZeldaIntelligencePipelineV2()
        pipeline.used_chunks = set()
        result = pipeline._analyze_document(doc, 'unused raw text — chunks already exist')

        revenue_insight = next(i for i in result['insights'] if i.category == 'Revenue')
        self.assertIn('9', revenue_insight.insight_text)


class ConfidenceBreakdownTests(TestCase):
    """
    zelda_api/confidence_breakdown.py — surfaces the per-category
    confidence Zelda already computes (zero additional Claude cost), and
    re-derives the overall score from those same categories instead of the
    old coverage-only "how many categories got any insight at all" count.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def _insight(self, category, confidence_score, text='some insight text', source='Extracted from: document'):
        return SimpleNamespace(category=category, confidence_score=confidence_score, insight_text=text, source_attribution=source)

    def test_breakdown_orders_by_canonical_category_not_insertion_order(self):
        from zelda_api.confidence_breakdown import compute_confidence_breakdown
        insights = [
            self._insight('Risk', 90, 'risk text'),
            self._insight('Problem', 80, 'problem text'),
        ]
        rows = compute_confidence_breakdown(insights)
        categories = [r['category'] for r in rows]
        self.assertEqual(categories, ['Problem', 'Risk'])  # Problem precedes Risk in ANALYSIS_CATEGORIES

    def test_missing_categories_are_omitted_not_zero_filled(self):
        from zelda_api.confidence_breakdown import compute_confidence_breakdown
        rows = compute_confidence_breakdown([self._insight('Revenue', 95)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['category'], 'Revenue')

    def test_confidence_scaled_to_zero_to_ten(self):
        from zelda_api.confidence_breakdown import compute_confidence_breakdown
        rows = compute_confidence_breakdown([self._insight('Revenue', 95)])
        self.assertEqual(rows[0]['confidence'], 9.5)

    def test_breakdown_includes_evidence_text_and_source(self):
        """The 'View evidence' expansion needs both the raw insight text and where it came from."""
        from zelda_api.confidence_breakdown import compute_confidence_breakdown
        rows = compute_confidence_breakdown([
            self._insight('Revenue', 95, text='Current Revenue: $4.5M', source='Extracted from: Traction'),
        ])
        self.assertEqual(rows[0]['insight_text'], 'Current Revenue: $4.5M')
        self.assertEqual(rows[0]['source_attribution'], 'Extracted from: Traction')

    def test_why_text_reflects_confidence_tier(self):
        from zelda_api.confidence_breakdown import compute_confidence_breakdown
        rows = compute_confidence_breakdown([
            self._insight('Revenue', 95, text='Current Revenue: $4.5M'),
            self._insight('Funding', 50),
        ])
        by_category = {r['category']: r['why'] for r in rows}
        self.assertIn('Current Revenue: $4.5M', by_category['Revenue'])
        self.assertIn('No clear figure found', by_category['Funding'])

    def test_why_text_uses_category_appropriate_language_not_figure_for_qualitative_categories(self):
        """Regression: 'specific figure' language was wrong for Problem/Product — there's no number to find in a qualitative category."""
        from zelda_api.confidence_breakdown import compute_confidence_breakdown
        rows = compute_confidence_breakdown([
            self._insight('Problem', 95, text='Healthcare operations are fragmented.'),
            self._insight('Product', 80, text='Centralizes healthcare operations.'),
        ])
        by_category = {r['category']: r['why'] for r in rows}
        self.assertNotIn('figure', by_category['Problem'])
        self.assertIn('described', by_category['Problem'])
        self.assertNotIn('figure', by_category['Product'])

    def test_why_text_includes_the_real_source_section(self):
        from zelda_api.confidence_breakdown import compute_confidence_breakdown
        rows = compute_confidence_breakdown([
            self._insight('Revenue', 95, text='$4.5M', source='Extracted from: Traction'),
        ])
        self.assertIn('Traction section', rows[0]['why'])

    def test_overall_confidence_averages_across_all_eight_not_just_present_ones(self):
        """
        A single 100%-confidence category out of 8 must NOT score as if it
        were the only category that mattered — this is exactly the old
        bug's inverse: coverage still counts, just weighted by quality.
        """
        from zelda_api.confidence_breakdown import compute_overall_confidence, CATEGORY_COUNT
        overall = compute_overall_confidence([self._insight('Revenue', 100)])
        self.assertAlmostEqual(overall, 100 / (CATEGORY_COUNT * 100.0))

    def test_overall_confidence_all_categories_present_and_perfect_is_one(self):
        from zelda_api.confidence_breakdown import compute_overall_confidence, ANALYSIS_CATEGORY_NAMES
        insights = [self._insight(c, 100) for c in ANALYSIS_CATEGORY_NAMES]
        self.assertEqual(compute_overall_confidence(insights), 1.0)

    def test_overall_confidence_low_quality_scores_lower_than_high_quality_same_coverage(self):
        from zelda_api.confidence_breakdown import compute_overall_confidence
        thin = compute_overall_confidence([self._insight('Revenue', 35), self._insight('Funding', 35)])
        strong = compute_overall_confidence([self._insight('Revenue', 95), self._insight('Funding', 95)])
        self.assertLess(thin, strong)

    def test_financial_completeness_counts_disclosed_fields(self):
        from zelda_api.confidence_breakdown import compute_financial_completeness, FINANCIAL_COMPLETENESS_FIELDS
        facts = {'arr': '$4.5M', 'raise_amount': None, 'market_size': None, 'use_of_proceeds': None,
                 'burn_rate': None, 'retention': None, 'growth_rate': None}
        result = compute_financial_completeness(facts)
        self.assertEqual(result['disclosed'], 1)
        self.assertEqual(result['total'], len(FINANCIAL_COMPLETENESS_FIELDS))

    def test_financial_completeness_all_missing_is_zero(self):
        from zelda_api.confidence_breakdown import compute_financial_completeness
        result = compute_financial_completeness({})
        self.assertEqual(result['disclosed'], 0)
        self.assertEqual(result['ratio'], 0.0)


class DocumentValuationViewConfidenceBreakdownTests(TestCase):
    """API-level coverage: DocumentValuationView's response includes the new confidence_breakdown/financial_completeness fields."""

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def test_response_includes_breakdown_and_completeness(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        user = User.objects.create_user('valuation_view_user', password='x')
        doc = DocumentSource.objects.create(
            filename='deck.pptx', source_entity='Test Co', document_type='business_valuation',
            uploaded_by=user, status='analyzed', raw_text_full='Current Revenue: $4.5M annual recurring revenue.',
        )
        BusinessValuationReport.objects.create(document=doc, confidence_score=0.5)
        from zelda_api.vector_models import IntelligenceInsight
        IntelligenceInsight.objects.create(
            document=doc, category='Revenue', insight_text='Current Revenue: $4.5M', confidence_score=95,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[doc.id]))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['confidence_breakdown']), 1)
        self.assertEqual(data['confidence_breakdown'][0]['category'], 'Revenue')
        self.assertIn('disclosed', data['financial_completeness'])
        # Freshly computed from insights, not the stale stored field (0.5)
        self.assertNotEqual(data['confidence_score'], 0.5)


class DocumentValuationViewTierRedactionTests(TestCase):
    """
    DocumentValuationView must redact a preview-tier report SERVER-SIDE —
    the whole point of the free-preview paywall breaks if a locked field
    is just hidden client-side, since anyone could read it straight out
    of the network tab. 'full' tier gets everything; 'preview' gets a
    trailer, not a censored document: business_overview in full,
    financial_completeness, trust_stats, a bare per-category letter-grade
    Scorecard (category names + grade only — no confidence score, no
    "why" text, no evidence; see DocumentValuationViewScorecardTests), and
    HOW MANY risks were found (a count only) — never the valuation range,
    methodology, financial summary, or any sample of the actual risk/
    confidence content itself.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def _doc_with_report(self, user, valuation_tier, risk_report='Risk one.\nRisk two.\nRisk three.'):
        from zelda_api.vector_models import IntelligenceInsight
        doc = DocumentSource.objects.create(
            filename='deck.pptx', source_entity='Test Co', document_type='business_valuation',
            uploaded_by=user, status='analyzed', total_pages=12, valuation_tier=valuation_tier,
        )
        BusinessValuationReport.objects.create(
            document=doc, confidence_score=0.7,
            business_overview='We build tools.', financial_summary='Revenue: $4.5M.',
            risk_report=risk_report, valuation_summary='Applied a revenue multiple.',
            valuation_low=1_000_000, valuation_high=2_000_000,
        )
        IntelligenceInsight.objects.create(document=doc, category='Revenue', insight_text='$4.5M', confidence_score=95)
        IntelligenceInsight.objects.create(document=doc, category='Team', insight_text='5 people', confidence_score=80)
        IntelligenceInsight.objects.create(document=doc, category='Market', insight_text='Large TAM', confidence_score=70)
        return doc

    def test_full_tier_includes_everything(self):
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('redact_full_user', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        doc = self._doc_with_report(user, 'full')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[doc.id]))
        data = response.json()

        self.assertEqual(data['valuation_tier'], 'full')
        self.assertEqual(data['valuation_low'], '1000000.00')
        self.assertEqual(data['valuation_high'], '2000000.00')
        self.assertEqual(data['sections']['financial_summary'], 'Revenue: $4.5M.')
        self.assertEqual(data['sections']['risk_report'], 'Risk one.\nRisk two.\nRisk three.')
        self.assertEqual(data['sections']['valuation_summary'], 'Applied a revenue multiple.')
        self.assertEqual(len(data['confidence_breakdown']), 3)
        self.assertNotIn('unlock_price', data)

    def test_preview_tier_omits_valuation_number_and_methodology(self):
        from matchmaking.models import Application
        user = User.objects.create_user('redact_preview_user', password='x')
        Application.objects.create(user=user, company_name='Test Co')
        doc = self._doc_with_report(user, 'preview')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[doc.id]))
        data = response.json()

        self.assertEqual(data['valuation_tier'], 'preview')
        self.assertIsNone(data.get('valuation_low'))
        self.assertIsNone(data.get('valuation_high'))
        self.assertNotIn('financial_summary', data['sections'])
        self.assertNotIn('risk_report', data['sections'])
        self.assertNotIn('valuation_summary', data['sections'])

    def test_preview_tier_still_shows_business_overview_and_trust_stats(self):
        from matchmaking.models import Application
        user = User.objects.create_user('redact_preview_trust', password='x')
        Application.objects.create(user=user, company_name='Test Co')
        doc = self._doc_with_report(user, 'preview')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[doc.id]))
        data = response.json()

        self.assertEqual(data['sections']['business_overview'], 'We build tools.')
        self.assertIn('financial_completeness', data)
        self.assertEqual(data['trust_stats']['pages_analyzed'], 12)
        self.assertEqual(data['trust_stats']['categories_analyzed'], 3)

    def test_preview_tier_never_exposes_the_detailed_confidence_breakdown(self):
        """
        The full per-category breakdown (why/insight_text/source_attribution
        alongside each category's exact confidence score) stays a full-tier
        exclusive — see UNLOCK_INCLUDES's "Full confidence breakdown". Since
        revision 3 (build_valuation_scorecard), category NAMES themselves
        are deliberately shown in preview via the bare-grade Scorecard —
        see DocumentValuationViewScorecardTests — but never alongside a
        `why`, an evidence excerpt, or the raw numeric confidence score.
        """
        from matchmaking.models import Application
        user = User.objects.create_user('redact_preview_categories', password='x')
        Application.objects.create(user=user, company_name='Test Co')
        doc = self._doc_with_report(user, 'preview')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[doc.id]))
        data = response.json()

        self.assertNotIn('confidence_breakdown', data)
        self.assertNotIn('category_findings', data)
        self.assertEqual(data['trust_stats']['categories_analyzed'], 3)
        for row in data['scorecard']:
            self.assertEqual(set(row.keys()), {'category', 'grade'})

    def test_preview_tier_shows_only_a_risk_count_never_risk_text(self):
        """
        A preview should tease "5 findings detected", never a sample of
        what any of them actually say — showing even one real risk gives
        away supporting analysis a full unlock pays for.
        """
        from matchmaking.models import Application
        user = User.objects.create_user('redact_preview_risks', password='x')
        Application.objects.create(user=user, company_name='Test Co')
        doc = self._doc_with_report(user, 'preview')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[doc.id]))
        data = response.json()

        self.assertNotIn('preview_risks', data)
        self.assertEqual(data['risk_count'], 3)

    def test_preview_tier_includes_unlock_price_for_founder(self):
        from matchmaking.models import Application
        user = User.objects.create_user('redact_preview_unlock', password='x')
        Application.objects.create(user=user, company_name='Test Co')
        doc = self._doc_with_report(user, 'preview')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[doc.id]))
        data = response.json()

        self.assertEqual(data['unlock_purchase_type'], 'report')
        self.assertEqual(data['unlock_price'], 9.99)

    def test_preview_tier_includes_unlock_includes_checklist(self):
        from matchmaking.models import Application
        user = User.objects.create_user('redact_preview_teaser', password='x')
        Application.objects.create(user=user, company_name='Test Co')
        doc = self._doc_with_report(user, 'preview')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[doc.id]))
        data = response.json()

        self.assertIn('Estimated valuation range', data['unlock_includes'])
        self.assertIn('Complete risk report', data['unlock_includes'])
        self.assertNotIn('preview_percent_visible', data)
        self.assertNotIn('premium_insights_waiting', data)


class ConfidenceGradeBandsTests(TestCase):
    """
    zelda_api.confidence_breakdown.grade_for_confidence — the deterministic
    confidence-to-letter-grade mapping backing the preview Scorecard.
    Exact boundary values matter here (this is a real product decision,
    not an implementation detail), so each band edge is tested explicitly.
    """

    def test_grade_boundaries(self):
        from zelda_api.confidence_breakdown import grade_for_confidence
        cases = [
            (10.0, 'A+'), (9.0, 'A+'), (8.9, 'A'), (8.0, 'A'),
            (7.9, 'B+'), (7.0, 'B+'), (6.9, 'B'), (6.0, 'B'),
            (5.9, 'C+'), (5.0, 'C+'), (4.9, 'C'), (4.0, 'C'),
            (3.9, 'D'), (3.0, 'D'), (2.9, 'F'), (0.0, 'F'),
        ]
        for score, expected_grade in cases:
            self.assertEqual(grade_for_confidence(score), expected_grade, f"score={score}")


class BuildValuationScorecardTests(TestCase):
    """
    zelda_api.valuation_preview.build_valuation_scorecard — unit-level
    proof that grades are derived from the actual per-category confidence
    scores (not hardcoded/random), and that nothing beyond {category,
    grade} ever comes out of it, regardless of what compute_confidence_
    breakdown's rows carry.
    """

    def test_grades_are_derived_from_the_actual_confidence_scores(self):
        from zelda_api.valuation_preview import build_valuation_scorecard
        breakdown = [
            {'category': 'Revenue', 'confidence': 9.5, 'why': 'irrelevant', 'insight_text': 'irrelevant', 'source_attribution': 'irrelevant'},
            {'category': 'Team', 'confidence': 8.0, 'why': 'irrelevant', 'insight_text': 'irrelevant', 'source_attribution': 'irrelevant'},
            {'category': 'Market', 'confidence': 7.0, 'why': 'irrelevant', 'insight_text': 'irrelevant', 'source_attribution': 'irrelevant'},
            {'category': 'Risk', 'confidence': 2.0, 'why': 'irrelevant', 'insight_text': 'irrelevant', 'source_attribution': 'irrelevant'},
        ]
        scorecard = build_valuation_scorecard(breakdown)
        self.assertEqual(scorecard, [
            {'category': 'Revenue', 'grade': 'A+'},
            {'category': 'Team', 'grade': 'A'},
            {'category': 'Market', 'grade': 'B+'},
            {'category': 'Risk', 'grade': 'F'},
        ])

    def test_no_underlying_findings_leak_into_the_scorecard(self):
        """Every row must be exactly {category, grade} — the why/insight_text/
        source_attribution compute_confidence_breakdown attaches must never
        survive into the scorecard, regardless of what's in the input rows."""
        from zelda_api.valuation_preview import build_valuation_scorecard
        breakdown = [{
            'category': 'Revenue', 'confidence': 9.0,
            'why': 'Explicitly reported as "$4.5M ARR" in the Revenue section.',
            'insight_text': '$4.5M ARR', 'source_attribution': 'Extracted from: Revenue',
        }]
        scorecard = build_valuation_scorecard(breakdown)
        self.assertEqual(scorecard, [{'category': 'Revenue', 'grade': 'A+'}])
        for row in scorecard:
            self.assertEqual(set(row.keys()), {'category', 'grade'})

    def test_empty_breakdown_produces_empty_scorecard(self):
        from zelda_api.valuation_preview import build_valuation_scorecard
        self.assertEqual(build_valuation_scorecard([]), [])


class DocumentValuationViewScorecardTests(TestCase):
    """
    End-to-end (view-level) coverage for the preview Scorecard: grades
    reflect the document's real insights, no underlying findings leak,
    and the full tier is unaffected (it keeps the real confidence_breakdown
    with full explanations — the redacted scorecard is a preview-only
    concept, so it doesn't need to appear in the full response at all).
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def _doc_with_insights(self, user, valuation_tier):
        from zelda_api.vector_models import IntelligenceInsight
        doc = DocumentSource.objects.create(
            filename='deck.pptx', source_entity='Scorecard Co', document_type='business_valuation',
            uploaded_by=user, status='analyzed', total_pages=10, valuation_tier=valuation_tier,
        )
        BusinessValuationReport.objects.create(
            document=doc, confidence_score=0.7, business_overview='We build tools.',
            financial_summary='Revenue: $4.5M.', risk_report='Risk one.\nRisk two.',
            valuation_summary='Applied a revenue multiple.', valuation_low=1_000_000, valuation_high=2_000_000,
        )
        IntelligenceInsight.objects.create(document=doc, category='Revenue', insight_text='$4.5M', confidence_score=95)
        IntelligenceInsight.objects.create(document=doc, category='Team', insight_text='5 people', confidence_score=80)
        IntelligenceInsight.objects.create(document=doc, category='Risk', insight_text='Some competition', confidence_score=25)
        return doc

    def test_preview_scorecard_grades_match_the_documents_real_insights(self):
        from matchmaking.models import Application
        user = User.objects.create_user('scorecard_preview_user', password='x')
        Application.objects.create(user=user, company_name='Scorecard Co')
        doc = self._doc_with_insights(user, 'preview')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[doc.id]))
        data = response.json()

        scorecard_by_category = {row['category']: row['grade'] for row in data['scorecard']}
        self.assertEqual(scorecard_by_category, {'Revenue': 'A+', 'Team': 'A', 'Risk': 'F'})

    def test_preview_scorecard_contains_no_evidence_or_explanation_fields(self):
        from matchmaking.models import Application
        user = User.objects.create_user('scorecard_no_leak_user', password='x')
        Application.objects.create(user=user, company_name='Scorecard Co')
        doc = self._doc_with_insights(user, 'preview')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[doc.id]))
        data = response.json()
        content = response.content.decode('utf-8')

        for row in data['scorecard']:
            self.assertEqual(set(row.keys()), {'category', 'grade'})
        # The real insight/evidence text must never appear anywhere in the
        # preview payload, scorecard included.
        self.assertNotIn('$4.5M', content)
        self.assertNotIn('5 people', content)
        self.assertNotIn('Some competition', content)

    def test_full_tier_does_not_need_the_redacted_scorecard(self):
        """The full tier already gets the real confidence_breakdown (with
        why/evidence) — the scorecard is a preview-only redaction concept,
        not an additional thing full-tier users need."""
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('scorecard_full_user', password='x')
        InvestorApplication.objects.create(user=user, is_premium=True)
        doc = self._doc_with_insights(user, 'full')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[doc.id]))
        data = response.json()

        self.assertNotIn('scorecard', data)
        self.assertEqual(len(data['confidence_breakdown']), 3)


class DocumentValuationViewTrendTests(TestCase):
    """
    DocumentValuationView surfaces a 'trend' key (see
    zelda_api/valuation_trend.py) for a full-tier report ONLY when a
    prior full-tier valuation of the same company exists — never for a
    preview (which has no real number of its own to compare from), and
    never for a document's own first full valuation.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def _full_doc(self, user, source_entity, low, high):
        doc = DocumentSource.objects.create(
            filename='deck.pptx', source_entity=source_entity, uploaded_by=user,
            document_type='business_valuation', status='analyzed', valuation_tier='full',
        )
        BusinessValuationReport.objects.create(
            document=doc, business_overview='x', financial_summary='x', risk_report='x',
            valuation_summary='x', valuation_low=low, valuation_high=high, confidence_score=0.5,
        )
        return doc

    def test_second_full_valuation_includes_trend(self):
        from matchmaking.models import Application
        user = User.objects.create_user('trend_api_user', password='x')
        Application.objects.create(user=user, company_name='TrendApiCo')
        self._full_doc(user, 'TrendApiCo', 1_000_000, 1_000_000)
        second = self._full_doc(user, 'TrendApiCo', 1_200_000, 1_200_000)
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[second.id]))
        data = response.json()

        self.assertEqual(data['trend']['direction'], 'up')
        self.assertEqual(data['trend']['pct_change'], 20)

    def test_first_full_valuation_has_no_trend(self):
        from matchmaking.models import Application
        user = User.objects.create_user('trend_api_first', password='x')
        Application.objects.create(user=user, company_name='FirstApiCo')
        doc = self._full_doc(user, 'FirstApiCo', 1_000_000, 1_000_000)
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[doc.id]))
        data = response.json()

        self.assertNotIn('trend', data)

    def test_preview_tier_never_includes_trend(self):
        from matchmaking.models import Application
        from zelda_api.vector_models import IntelligenceInsight
        user = User.objects.create_user('trend_api_preview', password='x')
        Application.objects.create(user=user, company_name='PreviewApiCo')
        self._full_doc(user, 'PreviewApiCo', 1_000_000, 1_000_000)
        preview_doc = DocumentSource.objects.create(
            filename='deck.pptx', source_entity='PreviewApiCo', uploaded_by=user,
            document_type='business_valuation', status='analyzed', valuation_tier='preview',
        )
        BusinessValuationReport.objects.create(
            document=preview_doc, business_overview='x', financial_summary='x', risk_report='x',
            valuation_summary='x', valuation_low=1_500_000, valuation_high=1_500_000, confidence_score=0.5,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:document_valuation', args=[preview_doc.id]))
        data = response.json()

        self.assertNotIn('trend', data)


class JourneyStatusAPIViewNextBestActionTests(TestCase):
    """
    JourneyStatusAPIView's profile_strength and next_best_action fields —
    the "outcome-oriented profile guidance" feature. next_best_action must
    always carry the real ACTION_INFO copy (never a raw invented number)
    for the first unfinished checklist item, across all four roles.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def test_founder_with_no_profile_gets_create_profile_action(self):
        user = get_user_model().objects.create_user('nba_founder_new', password='x')
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:journey_status'))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['next_best_action']['label'], 'Create your founder profile')
        self.assertIn('profile before I can start matching', data['next_best_action']['why_it_matters'])
        self.assertEqual(data['next_best_action']['action_label'], 'Create Profile')
        self.assertEqual(data['profile_strength'], {'ratio': 0.0, 'label': 'Just Started'})

    def test_founder_missing_pitch_asset_gets_upload_deck_action(self):
        from matchmaking.models import Application
        user = get_user_model().objects.create_user('nba_founder_yellow', password='x')
        Application.objects.create(
            user=user, company_name='Test Co', founder_name='Founder',
            email='f@test.com', description='A startup.',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:journey_status'))

        data = response.json()
        self.assertEqual(data['next_best_action']['label'], 'Upload a pitch deck or pitch video')
        self.assertIn('Zelda Intelligence Brief', data['next_best_action']['why_it_matters'])
        self.assertEqual(data['next_best_action']['estimated_minutes'], 2)
        self.assertEqual(data['profile_strength']['label'], 'Building')

    def test_founder_fully_complete_profile_has_no_next_best_action_and_is_strong(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from matchmaking.models import Application, Follow
        user = get_user_model().objects.create_user('nba_founder_green', password='x')
        app = Application.objects.create(
            user=user, company_name='Test Co', founder_name='Founder',
            email='f@test.com', description='A startup.', is_verified=True,
            pitch_deck=SimpleUploadedFile('deck.pdf', b'x' * 100, content_type='application/pdf'),
        )
        other = get_user_model().objects.create_user('nba_founder_green_other', password='x')
        Follow.objects.create(follower=user, following=other)
        user.articles.create(title='Post', body='body text')
        user.job_listings.create(title='Engineer', description='job', location='Remote', company_name='Test Co')
        from zelda_api.vector_models import DocumentSource
        DocumentSource.objects.create(
            uploaded_by=user, filename='plan.pdf', source_entity='Test Co', document_type='business_plan',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:journey_status'))

        data = response.json()
        self.assertIsNone(data['next_best_action'])
        self.assertEqual(data['profile_strength'], {'ratio': 1.0, 'label': 'Strong'})

    def test_investor_incomplete_mandate_gets_complete_mandate_action(self):
        from matchmaking.models import InvestorApplication
        user = get_user_model().objects.create_user('nba_investor_yellow', password='x')
        InvestorApplication.objects.create(
            user=user, full_name='', email='i@test.com',
            company_name='Test VC', investment_focus='SaaS', investment_stage='Seed',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:journey_status'))

        data = response.json()
        self.assertEqual(data['next_best_action']['label'], 'Complete every mandate field')
        self.assertEqual(data['next_best_action']['action_url'], reverse('usersettings:edit_investor_profile'))

    def test_seller_no_cim_gets_upload_cim_action(self):
        from matchmaking.models import SellerApplication
        user = get_user_model().objects.create_user('nba_seller_yellow', password='x')
        SellerApplication.objects.create(
            user=user, company_name='Test Widgets', seller_name='Seller',
            email='s@test.com', description='A business.',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:journey_status'))

        data = response.json()
        self.assertEqual(data['next_best_action']['label'], 'Upload a CIM document')
        self.assertIn('Zelda Intelligence Brief', data['next_best_action']['why_it_matters'])

    def test_buyer_incomplete_mandate_gets_complete_mandate_action(self):
        # A buyer is only routed to the buyer track once match_buyer_profile
        # exists (see JourneyStatusAPIView's is_buyer check) — a user with
        # no profile at all falls through to the founder track instead, so
        # this exercises the buyer checklist's "yellow" incomplete-mandate
        # state rather than the unreachable-via-this-view "red" state.
        from matchmaking.models import BuyerApplication
        user = get_user_model().objects.create_user('nba_buyer_yellow', password='x')
        BuyerApplication.objects.create(
            user=user, full_name='Buyer', email='b@test.com',
            company_name='Acquisitions LLC', acquisition_thesis='We acquire things.',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('zelda_api:journey_status'))

        data = response.json()
        self.assertEqual(data['next_best_action']['label'], 'Complete every mandate field')
        self.assertEqual(data['next_best_action']['action_label'], 'Complete Mandate')


class ZeldaGlobalSearchInvestorPrivacyTests(TestCase):
    """
    ZeldaGlobalSearchAPIView's investor branch previously had no is_private
    or archived_at filter at all — an inconsistent privacy boundary next to
    the founder branch's Application.objects.discoverable(). Confirms the
    fix: private and archived investors are excluded, a normal discoverable
    one still surfaces.
    """

    def setUp(self):
        from matchmaking.models import InvestorApplication
        self.InvestorApplication = InvestorApplication

        self.searcher = get_user_model().objects.create_user('search_seeker', password='x')
        self.client.force_login(self.searcher)

        self.public_investor_user = get_user_model().objects.create_user('search_pub_inv', password='x')
        self.public_investor = InvestorApplication.objects.create(
            user=self.public_investor_user, full_name='Pub Inv', company_name='SearchableFund',
            email='pub@t.com', investment_focus='SaaS', investment_stage='Seed',
        )

        self.private_investor_user = get_user_model().objects.create_user('search_priv_inv', password='x')
        self.private_investor = InvestorApplication.objects.create(
            user=self.private_investor_user, full_name='Priv Inv', company_name='SearchablePrivateFund',
            email='priv@t.com', investment_focus='SaaS', investment_stage='Seed', is_private=True,
        )

        self.archived_investor_user = get_user_model().objects.create_user('search_arch_inv', password='x')
        self.archived_investor = InvestorApplication.objects.create(
            user=self.archived_investor_user, full_name='Arch Inv', company_name='SearchableArchivedFund',
            email='arch@t.com', investment_focus='SaaS', investment_stage='Seed',
        )
        self.archived_investor.archive()

    def _search(self, query):
        return self.client.post(
            reverse('zelda_api:global_search_api'),
            data={'q': query, 'founders': False, 'investors': True, 'bulletins': False},
            content_type='application/json',
        )

    def test_public_investor_appears_in_search(self):
        response = self._search('SearchableFund')
        self.assertEqual(response.status_code, 200)
        urls = [r['url'] for r in response.json()['results']]
        self.assertTrue(any('search_pub_inv' in u for u in urls))

    def test_private_investor_excluded_from_search(self):
        response = self._search('SearchablePrivateFund')
        self.assertEqual(response.status_code, 200)
        urls = [r['url'] for r in response.json()['results']]
        self.assertFalse(any('search_priv_inv' in u for u in urls))

    def test_archived_investor_excluded_from_search(self):
        response = self._search('SearchableArchivedFund')
        self.assertEqual(response.status_code, 200)
        urls = [r['url'] for r in response.json()['results']]
        self.assertFalse(any('search_arch_inv' in u for u in urls))
