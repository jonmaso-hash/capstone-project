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
                recommendation='consider',
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

    def test_html_view_returns_200_for_owner(self):
        doc = self._make_pitch_deck_doc(with_memo=True)
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('zelda_api:ic_memo', args=[doc.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MemoCo')

    def test_html_view_returns_404_for_unrelated_investor(self):
        doc = self._make_pitch_deck_doc(with_memo=True)
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('zelda_api:ic_memo', args=[doc.id]))
        self.assertEqual(response.status_code, 404)

    def test_html_view_returns_200_for_accepted_connection_investor(self):
        from matchmaking.models import Connection
        doc = self._make_pitch_deck_doc(with_memo=True)
        Connection.objects.create(
            investor=self.investor_app, founder=self.application, status='ACCEPTED', initiated_by='INVESTOR',
        )
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('zelda_api:ic_memo', args=[doc.id]))
        self.assertEqual(response.status_code, 200)

    def test_markdown_download_returns_correct_content_type_and_filename(self):
        doc = self._make_pitch_deck_doc(with_memo=True)
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
        """
        from .vector_models import DocumentSource
        content = b'We build infrastructure tooling for SaaS teams.'
        with mock.patch('zelda_api.pipeline_views.process_document_pipeline.delay'):
            r1 = self._post(SimpleUploadedFile('deck.txt', content, content_type='text/plain'))
            r2 = self._post(SimpleUploadedFile('deck.txt', content, content_type='text/plain'))

        id1, id2 = r1.json()['document_id'], r2.json()['document_id']
        self.assertNotEqual(id1, id2)
        self.assertEqual(DocumentSource.objects.filter(id__in=[id1, id2]).count(), 2)

        # Simulate each finishing with its own distinct memo (as two real
        # pipeline runs would) and confirm they don't collide.
        doc1, doc2 = DocumentSource.objects.get(id=id1), DocumentSource.objects.get(id=id2)
        IntelligenceMemo.objects.create(document=doc1, executive_summary='First run summary.', recommendation='consider')
        IntelligenceMemo.objects.create(document=doc2, executive_summary='Second run summary.', recommendation='consider')
        self.assertEqual(doc1.memo.executive_summary, 'First run summary.')
        self.assertEqual(doc2.memo.executive_summary, 'Second run summary.')


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
            document=self.doc, executive_summary='We build developer tools.', recommendation='consider',
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
        from .truth_delta_models import TruthDeltaReport
        self.user = User.objects.create_user('scoreview_owner', password='x')
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
        result, confidence = self.pipeline._smart_extract('Funding', 'No relevant content here.', 'funding raise capital')
        self.assertIsNone(result)
        self.assertEqual(confidence, 0.0)

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
