"""
The identity decision survives every boundary, or the chain fails.

Three PRs built the pieces:

    #102  one authority decides which registrant a company is
    #103  Truth Delta consumes that decision instead of re-resolving
    #104  the observation persists the registrant it was observed about
    here  every boundary between them preserves it, all the way to a reader

The invariant:

    resolved.cik
        == ObservedDatapoint.registrant
        == finding provenance registrant
        == rendered identity

Asserted at EVERY arrow, never only at the ends. A test comparing the
resolver's answer to the rendered page passes while a middle layer
substitutes and a later one restores -- which is the exact shape of the
defect the live walk found one layer up, where Entity Integrity and Truth
Delta each arrived at 0000829224 by separate routes and nothing noticed
the routes were separate.

Two things this file is careful about:

RENDERED MEANS READ, NOT SHIPPED. `details` is serialised into the page
through json_script, so once the comparison row carries a registrant the
CIK appears in the HTML whether or not anything displays it. Every
rendering assertion therefore runs against the page with its <script>
blocks removed, so it is about what a founder can actually read.

MATCHING IS NOT PROPAGATING. Equal values prove the chain agreed, not
that propagation is the only way an identity can arrive. The second class
takes the authority's answer away entirely: nothing downstream may
manufacture a replacement.
"""
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .sec_company_identity import CompanyIdentity, FOUND, NOT_FOUND
from .truth_delta_engine import TruthDeltaEngine
from .truth_delta_models import ClaimedDatapoint, ObservedDatapoint
from .truth_delta_sources import DataSourceManager, SECFilingsIntegration
from .vector_models import DocumentSource

User = get_user_model()

CHOSEN = '0000829224'        # what the identity authority selected
NEVER_CHOSEN = '0000887557'  # what an independent lookup would have found

FACTS = {
    'facts': {
        'us-gaap': {'Revenues': {'units': {'USD': [
            {'val': 37_184_400_000, 'form': '10-K', 'fy': 2025, 'fp': 'FY',
             'start': '2024-10-01', 'end': '2025-09-28'},
        ]}}},
        'dei': {},
    },
    'entityName': 'STARBUCKS CORP',
}

SCRIPTS = re.compile(r'<script\b.*?</script>', re.DOTALL | re.IGNORECASE)

# The sentence that attributes evidence to an entity. Presence and absence
# are both asserted against this one constant, so a typo cannot quietly
# turn "the page says nothing" into "the test looked for the wrong thing".
ATTRIBUTION_LEAD = 'External figures were observed about'


def readable(html):
    """
    The page with its <script> blocks removed.

    `details` reaches the browser through json_script, so a CIK embedded
    there would satisfy `assertIn` without a single pixel changing. What
    the chain has to prove is that a reader is told which entity the
    figures belong to, so the script payload is not evidence of that.
    """
    return SCRIPTS.sub('', html)


class ChainHarness(TestCase):
    """Shared harness: the real pipeline, with only its two edges stubbed."""

    username = 'chain_user'

    def setUp(self):
        # Staff, so the report renders at full tier and the last link is
        # actually on the page rather than behind the Zelda Lite cut.
        self.user = User.objects.create_user(self.username, password='x', is_staff=True)
        self.client.force_login(self.user)
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Starbucks Corporation',
            uploaded_by=self.user, document_type='pitch_deck', status='analyzed',
        )
        ClaimedDatapoint.objects.create(
            document=self.document, category='revenue',
            claimed_value='$36.2 billion', claimed_value_numeric=36_200_000_000.0,
            unit='$', source_chunk='Insight: Revenue',
            text_excerpt='Total net revenue for fiscal 2025 was approximately $36.2 billion.',
        )

    def run_pipeline(self, authority_cik=CHOSEN):
        """
        The shipping engine. Only the identity authority and the SEC payload
        are stubbed -- datapoint creation, comparison building, report
        persistence and rendering are all the real code.
        """
        payload = dict(FACTS)
        if authority_cik:
            payload['_cik'] = authority_cik
        identity = (
            CompanyIdentity(status=FOUND, cik=authority_cik, name='STARBUCKS CORP',
                            matched_on='current_name', files_periodically=True)
            if authority_cik else CompanyIdentity(status=NOT_FOUND)
        )

        with mock.patch.object(DataSourceManager, 'INTEGRATIONS',
                               {'sec': SECFilingsIntegration}), \
             mock.patch.object(DataSourceManager, 'fetch_news_headlines', return_value=[]), \
             mock.patch('zelda_api.sec_company_identity.resolve_company_identity',
                        return_value=identity), \
             mock.patch.object(SECFilingsIntegration, 'fetch_company_data',
                               return_value=payload if authority_cik else {}), \
             mock.patch.object(TruthDeltaEngine, '_call_claude_for_verification',
                               return_value=None):
            return TruthDeltaEngine().verify_document(self.document.id)

    def page(self):
        response = self.client.get(
            reverse('zelda_api:truth_delta_ui', args=[self.document.id]))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    @staticmethod
    def compared_rows(report):
        return [row for row in ((report.details or {}).get('comparison') or [])
                if row.get('observed_value_numeric')]


class TheIdentitySurvivesEveryBoundaryTests(ChainHarness):

    username = 'chain_owner'

    def test_the_harness_produces_something_to_test(self):
        """
        Positive control. Every assertion below is about a stored row, a
        compared finding or a rendered page; a harness that produces none of
        them would make the whole file vacuously green.
        """
        report = self.run_pipeline()
        self.assertIsNotNone(report, 'the engine produced no report')
        self.assertTrue(ObservedDatapoint.objects.filter(document=self.document).exists(),
                        'no observation was stored, so nothing was tested')
        self.assertTrue(self.compared_rows(report),
                        'nothing was actually compared against evidence')

    # --- link 1: authority -> observation --------------------------------
    def test_the_observation_carries_the_chosen_registrant(self):
        self.run_pipeline()
        for row in ObservedDatapoint.objects.filter(document=self.document):
            with self.subTest(category=row.category):
                self.assertEqual(row.registrant, CHOSEN)

    # --- link 2: observation -> finding provenance -----------------------
    def test_the_finding_provenance_names_the_same_registrant(self):
        report = self.run_pipeline()
        for row in self.compared_rows(report):
            with self.subTest(category=row.get('category')):
                self.assertEqual(row.get('observed_registrant'), CHOSEN)

    def test_the_finding_names_the_registrant_as_well_as_the_source(self):
        """
        `observed_source` is "SEC EDGAR" -- WHICH SOURCE, never WHICH COMPANY
        AT THAT SOURCE. Both have to be present: a finding attributed only to
        a source cannot be audited back to an entity, which is the whole
        reason the registrant is stored.
        """
        report = self.run_pipeline()
        for row in self.compared_rows(report):
            with self.subTest(category=row.get('category')):
                self.assertTrue(row.get('observed_source'), 'the finding named no source')
                self.assertTrue(row.get('observed_registrant'),
                                'the finding named a source but no entity at it')
                self.assertNotEqual(row.get('observed_registrant'), row.get('observed_source'))

    # --- link 3: finding -> reader ---------------------------------------
    def test_a_reader_is_told_which_registrant_the_evidence_is_about(self):
        self.run_pipeline()
        page = readable(self.page())
        self.assertIn(ATTRIBUTION_LEAD, page,
                      'the page never attributed the evidence to an entity')
        self.assertIn(CHOSEN, page)

    def test_the_reader_is_not_shown_a_registrant_nobody_chose(self):
        self.run_pipeline()
        self.assertNotIn(NEVER_CHOSEN, self.page())

    # --- the whole chain, one registrant ---------------------------------
    def test_one_registrant_from_authority_to_screen(self):
        report = self.run_pipeline()
        observation = ObservedDatapoint.objects.filter(document=self.document).first()
        finding = self.compared_rows(report)[0]

        self.assertEqual(observation.registrant, CHOSEN)
        self.assertEqual(finding.get('observed_registrant'), observation.registrant)
        self.assertIn(observation.registrant, readable(self.page()))


class WithoutTheAuthorityTheChainFailsTests(ChainHarness):
    """
    The architectural property, and the one a value comparison cannot reach.

    Every test above would still pass if a downstream component quietly
    resolved its own registrant and happened to agree. Here the authority
    returns nothing: the chain must FAIL rather than rediscover.
    """

    username = 'chain_none'

    def test_no_authority_means_no_observation(self):
        self.run_pipeline(authority_cik=None)
        self.assertFalse(
            ObservedDatapoint.objects.filter(document=self.document).exists(),
            'an observation was stored without an identity to attribute it to')

    def test_no_authority_means_no_finding_provenance(self):
        report = self.run_pipeline(authority_cik=None)
        for row in ((report.details or {}).get('comparison') or []):
            with self.subTest(category=row.get('category')):
                self.assertFalse(
                    row.get('observed_registrant'),
                    'a finding named a registrant the authority never chose')

    def test_no_entity_is_named_when_the_authority_chose_none(self):
        """
        The gap a surviving mutation exposed: it is not enough that the page
        avoids the two CIKs this file happens to know about. A layer that
        substitutes a placeholder when the stored registrant is blank puts a
        plausible entity in front of a reader, which is worse than putting
        none there -- an invented attribution is indistinguishable from a
        real one.

        So the requirement is that NO entity is named, not that the wrong
        ones are absent.
        """
        report = self.run_pipeline(authority_cik=None)
        self.assertEqual(report.evidence_registrants(), [],
                         'the report attributed evidence to an entity the '
                         'authority never chose')
        self.assertNotIn(ATTRIBUTION_LEAD, readable(self.page()),
                         'the page named an entity for evidence that has none')

    def test_nothing_downstream_invents_a_registrant_for_the_reader(self):
        self.run_pipeline(authority_cik=None)
        html = self.page()
        for cik in (CHOSEN, NEVER_CHOSEN):
            with self.subTest(cik=cik):
                self.assertNotIn(cik, html)

    def test_the_negative_case_still_produced_rows_to_check(self):
        """
        Positive control for this class. The assertions above are about
        comparison rows and page content; a run that produced no rows at all
        would make "no row names a registrant" true for the wrong reason.
        """
        report = self.run_pipeline(authority_cik=None)
        self.assertTrue((report.details or {}).get('comparison'),
                        'no comparison rows, so the absence assertions were vacuous')

    def test_the_report_still_explains_itself(self):
        """
        Failing the chain must not mean failing silently. With no identity
        there is no evidence, and the report has to say so rather than
        rendering an empty verdict a reader would read as a clean bill.
        """
        report = self.run_pipeline(authority_cik=None)
        self.assertIsNotNone(report, 'no identity produced no report at all')
        self.assertTrue((report.summary or '').strip(),
                        'the report carried no explanation of why nothing was checked')


class NothingDownstreamReResolvesTests(ChainHarness):
    """
    The substitution failure, which equal values cannot detect.

    Every assertion in the first class holds if a downstream layer throws
    away the stored registrant and looks the company up again -- because it
    would get the same answer. So these tests make the authority's CURRENT
    answer disagree with what was stored at observation time. A layer that
    re-resolves now returns the wrong registrant; a layer that propagates is
    unaffected.

    Which of those is correct is not a matter of taste. The stored value is
    the identity this evidence was actually gathered under; a fresh lookup is
    a different question asked at a different time, and answering it here
    would make the finding's provenance a guess about the present rather than
    a record of the past.
    """

    username = 'chain_reresolve'

    def observed_under(self, registrant):
        self.run_pipeline(authority_cik=registrant)
        rows = list(ObservedDatapoint.objects.filter(document=self.document))
        self.assertTrue(rows, 'no observation was stored, so nothing was tested')
        return rows

    def later_the_authority_says(self, cik):
        """The identity authority, re-asked now, answering differently."""
        return mock.patch(
            'zelda_api.sec_company_identity.resolve_company_identity',
            return_value=CompanyIdentity(status=FOUND, cik=cik, name='STARBUCKS CORP',
                                         matched_on='current_name', files_periodically=True))

    def test_the_finding_follows_the_observation_not_a_fresh_lookup(self):
        observed = self.observed_under(CHOSEN)
        claims = ClaimedDatapoint.objects.filter(document=self.document)

        with self.later_the_authority_says(NEVER_CHOSEN):
            rows = TruthDeltaEngine()._build_comparison(claims, observed)

        compared = [row for row in rows if row.get('observed_value_numeric')]
        self.assertTrue(compared, 'nothing was compared, so nothing was tested')
        for row in compared:
            with self.subTest(category=row.get('category')):
                self.assertEqual(row.get('observed_registrant'), CHOSEN)

    def test_the_page_follows_the_stored_finding_not_a_fresh_lookup(self):
        self.observed_under(CHOSEN)
        with self.later_the_authority_says(NEVER_CHOSEN):
            html = self.page()

        self.assertIn(CHOSEN, readable(html))
        self.assertNotIn(NEVER_CHOSEN, html)

    def test_a_blank_registrant_is_not_filled_in_by_looking_it_up(self):
        """
        The tempting repair, and the one that would quietly restore a second
        identity path: an observation with no registrant gets one by asking
        the authority while the row is rendered. A blank has to stay blank --
        it records that this evidence arrived without an identity, which is a
        fact about the evidence, not a gap to paper over.
        """
        observed = self.observed_under(CHOSEN)
        for row in observed:
            row.registrant = ''
            row.save(update_fields=['registrant'])
        claims = ClaimedDatapoint.objects.filter(document=self.document)

        with self.later_the_authority_says(NEVER_CHOSEN):
            rows = TruthDeltaEngine()._build_comparison(claims, observed)

        for row in rows:
            with self.subTest(category=row.get('category')):
                self.assertIsNone(row.get('observed_registrant'))
