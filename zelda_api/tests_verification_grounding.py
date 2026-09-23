"""
"Verified" must mean Zelda fetched evidence, not that Zelda wrote a sentence.

Truth Delta asks Claude to compare a deck's claims against datapoints the
pipeline gathered from public sources, and returns a per_claim table whose
`observed` field is free text. Every surface then decided a claim was
"verified against external data" by looking at that text: non-empty, and not
containing "no external data", counted as verified.

That makes the model's prose the evidence. With CRUNCHBASE_API_KEY and
NEWS_API_KEY unset, SEC EDGAR is the only live source, and a private company
returns nothing from it -- exactly the case where a model has the most room to
restate the deck's own numbers in the observed column. The deck says $4M ARR,
the report says "Verified against public sources: 1", and an investor reads
corroboration that never happened.

The rule these tests pin:

    A claim category counts as verified only when the pipeline stored an
    ObservedDatapoint in that category. Model prose may describe evidence.
    It may never create it.

News headlines deliberately do not qualify: Truth Delta's own prompt says
headlines corroborate a narrative but never confirm a figure, and they are
never stored as observed datapoints.

Each negative is paired with a positive control on the same surface with the
same shape of data, differing only in whether real evidence exists -- so a
surface that renders nothing, or counts nothing, cannot pass by being dead.
"""
import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .truth_delta_models import (
    ClaimedDatapoint, ExternalDataSource, ObservedDatapoint, TruthDeltaReport,
)
from .vector_models import DocumentSource

# What Claude returned for a company with no external data at all: an observed
# column filled in from the deck itself. Nothing in the JSON marks it as
# ungrounded -- that is the point.
FABRICATED_PER_CLAIM = [
    {'category': 'arr', 'claimed': '$4M ARR', 'observed': 'Crunchbase reports $4.2M ARR',
     'assessment': 'Consistent with external data.'},
    {'category': 'funding_raised', 'claimed': '$2M seed', 'observed': '$2M seed round (SEC EDGAR Form D)',
     'assessment': 'Corroborated.'},
]


class _GroundingCast(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('grounding_owner', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Ungrounded Co',
            uploaded_by=self.owner, document_type='pitch_deck',
        )

    def report(self, per_claim=None, observed=None, claims=None, **extra):
        """A stored report. `observed` is what the pipeline actually gathered."""
        fields = dict(
            document=self.document, overall_truth_score=88.0, credibility_risk='low',
            summary='test', details={
                'claims': claims if claims is not None else [
                    {'category': 'arr', 'claimed_value': '$4M ARR'},
                    {'category': 'funding_raised', 'claimed_value': '$2M seed'},
                ],
                'per_claim': per_claim if per_claim is not None else FABRICATED_PER_CLAIM,
                'observed': observed or [],
            },
        )
        fields.update(extra)
        return TruthDeltaReport.objects.create(**fields)

    def evidence(self, category, value='$4.2M', source='SEC EDGAR'):
        """One serialized observed row, shaped as the engine stores it."""
        return {'category': category, 'observed_value': value, 'source': source, 'time_period': 'FY2025'}

    def datapoint(self, category, value='$4.2M', numeric=4200000.0):
        source, _ = ExternalDataSource.objects.get_or_create(
            source_type='sec_edgar', defaults={'source_name': 'SEC EDGAR'},
        )
        return ObservedDatapoint.objects.create(
            document=self.document, category=category, observed_value=value,
            observed_value_numeric=numeric, source=source,
        )


class CategoryStatesAreGroundedInEvidenceTests(_GroundingCast):
    """The single authority every surface reads."""

    def test_model_prose_alone_does_not_verify_a_claim(self):
        report = self.report()  # observed: nothing was gathered
        self.assertEqual(report.category_states(), {'arr': 'no_data', 'funding_raised': 'no_data'})

    def test_real_evidence_verifies_the_claim(self):
        """Control: identical prose, with datapoints the pipeline actually stored."""
        report = self.report(observed=[self.evidence('arr'), self.evidence('funding_raised', '$2M')])
        self.assertEqual(report.category_states(), {'arr': 'verified', 'funding_raised': 'verified'})

    def test_grounding_is_per_category(self):
        """Evidence for one claim must not verify the other."""
        report = self.report(observed=[self.evidence('arr')])
        self.assertEqual(report.category_states(), {'arr': 'verified', 'funding_raised': 'no_data'})

    def test_evidence_counts_even_where_the_model_reported_none(self):
        """
        The pipeline gathered a datapoint; the model's row says it found
        nothing. Evidence decides, so this is verified. Pinned deliberately:
        it is the direct consequence of the rule, and the one case where
        grounding is more generous than the old text check.
        """
        report = self.report(
            per_claim=[{'category': 'arr', 'claimed': '$4M ARR', 'observed': 'no external data found'}],
            observed=[self.evidence('arr')],
        )
        self.assertEqual(report.category_states(), {'arr': 'verified'})

    def test_verified_counts_follow_the_same_rule(self):
        # Compared key by key rather than as a whole dict: the stats grew a
        # `contradicted` and a `no_data` count when grounding became
        # three-state, and this test is about what counts as VERIFIED.
        ungrounded = self.report().verifiability_stats()
        self.assertEqual((ungrounded['total'], ungrounded['verified'], ungrounded['pct']), (2, 0, 0.0))
        grounded = self.report(observed=[self.evidence('arr')]).verifiability_stats()
        self.assertEqual((grounded['total'], grounded['verified'], grounded['pct']), (2, 1, 50.0))

    def test_prose_alone_is_not_a_contradiction_either(self):
        """
        The mirror of this file's rule under three-state grounding: a model
        writing a disagreement into `observed` must not produce `contradicted`
        any more than it could produce `verified`. Only a stored comparison
        can, and these reports have none.
        """
        stats = self.report().verifiability_stats()
        self.assertEqual(stats['contradicted'], 0)
        self.assertEqual(stats['no_data'], 2)

    def test_a_report_with_no_per_claim_breakdown_is_still_all_unchecked(self):
        report = self.report(per_claim=[])
        self.assertEqual(report.category_states(), {'arr': 'no_data', 'funding_raised': 'no_data'})


class EngineDoesNotPromoteProseToEvidenceTests(_GroundingCast):
    """
    End to end through TruthDeltaEngine, with Claude stubbed: no network, no
    API spend. The engine stores what the model said -- it must not let that
    become a verification count.
    """

    def run_engine(self, claude_result):
        from .truth_delta_engine import TruthDeltaEngine
        ClaimedDatapoint.objects.create(
            document=self.document, category='arr', claimed_value='$4M ARR', claimed_value_numeric=4000000.0,
        )
        ClaimedDatapoint.objects.create(
            document=self.document, category='funding_raised', claimed_value='$2M seed',
            claimed_value_numeric=2000000.0,
        )
        engine = TruthDeltaEngine()
        with mock.patch.object(engine, '_call_claude_for_verification', return_value=claude_result), \
             mock.patch('zelda_api.truth_delta_engine.data_source_manager') as sources:
            sources.create_observed_datapoints.return_value = None
            sources.fetch_news_headlines.return_value = ['Ungrounded Co raises $2M seed round']
            return engine.verify_document(self.document.id)

    CLAUDE_RESULT = {
        'overall_truth_score': 88.0, 'credibility_risk': 'low',
        'summary': 'Claims are consistent with external data.',
        'per_claim': FABRICATED_PER_CLAIM,
    }

    def test_a_report_built_on_no_datapoints_verifies_nothing(self):
        report = self.run_engine(self.CLAUDE_RESULT)
        self.assertIsNotNone(report)
        self.assertEqual(report.verifiability_stats()['verified'], 0)

    def test_the_same_run_with_real_datapoints_does_verify(self):
        """Control: same claims, same model output, one real datapoint stored."""
        self.datapoint('arr')
        report = self.run_engine(self.CLAUDE_RESULT)
        self.assertEqual(report.category_states()['arr'], 'verified')

    def test_headlines_alone_never_verify_a_claim(self):
        """
        A news headline is narrative corroboration, never a confirmed figure --
        Truth Delta's own prompt says so. The run above supplies a headline and
        no datapoints.
        """
        report = self.run_engine(self.CLAUDE_RESULT)
        self.assertEqual(report.category_states(), {'arr': 'no_data', 'funding_raised': 'no_data'})


class ServedPayloadsCarryTheGroundedAnswerTests(_GroundingCast):
    """
    Both dashboard payloads. The page must not have to re-derive grounding
    from the prose it is handed -- that is how it drifted from the stat cards
    in the first place.
    """

    def payload_api(self, report):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('zelda_api:truth_delta_score', args=[self.document.id]))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_the_api_reports_no_verified_claims_without_evidence(self):
        self.report()
        body = self.payload_api(None)
        self.assertEqual(body['verified_count'], 0)
        self.assertEqual(body['category_states'], {'arr': 'no_data', 'funding_raised': 'no_data'})

    def test_the_api_reports_verified_claims_with_evidence(self):
        self.report(observed=[self.evidence('arr')])
        body = self.payload_api(None)
        self.assertEqual(body['verified_count'], 1)

    def test_every_served_row_states_whether_it_is_grounded(self):
        """
        The row the page renders carries the server's answer, so the claim
        list and the stat cards cannot disagree.
        """
        self.report(observed=[self.evidence('arr')])
        rows = self.payload_api(None)['details']['per_claim']
        by_category = {row['category']: row for row in rows}
        self.assertIs(by_category['arr']['grounded'], True)
        self.assertIs(by_category['funding_raised']['grounded'], False)

    def test_the_dashboard_page_carries_the_same_answer(self):
        self.report(observed=[self.evidence('arr')])
        self.client.force_login(self.owner)
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.document.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['verified_count'], 1)
        self.assertEqual(response.context['unverified_count'], 1)
        rows = response.context['details']['per_claim']
        self.assertEqual({r['category']: r['grounded'] for r in rows},
                         {'arr': True, 'funding_raised': False})


class DashboardCountsFromEvidenceNotProseTests(TestCase):
    """
    The claim list's rollup and per-claim icon are JavaScript, which no Django
    test executes. A source check instead: the page must not decide what is
    verified by testing the observed string, and must use the server's answer.
    """

    PROSE_TEST = '/noexternaldata/i.test'   # the old rule, whitespace removed

    def source(self):
        from pathlib import Path
        from django.conf import settings
        return (Path(settings.BASE_DIR) / 'templates' / 'truth_delta_dashboard.html').read_text(
            encoding='utf-8', errors='ignore')

    def squeezed(self):
        """Whitespace removed, so reformatting the script cannot hide a match."""
        import re
        return re.sub(r'\s+', '', self.source())

    def test_the_page_does_not_derive_verification_from_the_observed_text(self):
        self.assertNotIn(self.PROSE_TEST, self.squeezed())

    def test_the_page_uses_the_servers_grounded_answer(self):
        body = self.squeezed()
        self.assertIn('rows.filter(r=>r.grounded)', body)          # the rollup count
        self.assertIn('row.grounded?row.observed:null', body)      # the observed cell

    def test_the_scanner_would_catch_the_old_rule(self):
        """
        Positive control for the scanner itself, not just the file: the needle
        must match the mutated form. Written as a plain assertion on a sample
        because a check that cannot fire is indistinguishable from a clean file
        -- which is exactly how the first version of this test passed while a
        mutation restoring the prose count survived.
        """
        import re
        sample = 'const n = rows.filter(r => r.observed && !/no external data/i.test(r.observed)).length;'
        self.assertIn(self.PROSE_TEST, re.sub(r'\s+', '', sample))

    def test_the_scanner_sees_the_file_it_guards(self):
        """A scanner reading an empty string would pass the checks above."""
        self.assertIn('buildClaimItem', self.source())


class MemoDoesNotClaimExternalBackingTests(_GroundingCast):
    """The IC memo asserts "External data backs N of M claims" in prose."""

    def memo_section(self, report):
        from .ic_memo import truth_delta_signal
        return truth_delta_signal(self.document)

    def test_no_evidence_produces_no_backing_claim(self):
        section = self.memo_section(self.report())
        self.assertEqual(section['coverage']['verified'], 0)
        self.assertEqual(section['no_data_count'], 2)

    def test_evidence_produces_a_backing_claim(self):
        section = self.memo_section(self.report(observed=[self.evidence('arr')]))
        self.assertEqual(section['coverage']['verified'], 1)
        self.assertEqual(section['no_data_count'], 1)
