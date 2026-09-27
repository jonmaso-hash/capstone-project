"""
One component decides which SEC registrant a company is.

PR #102 gave Entity Integrity a shared resolver. Truth Delta still resolved
independently, through `_find_cik_exact`, and reached the same answer for
Starbucks -- but only because that search passes `type=10-K`, which excluded
the dormant registrant by luck of a query parameter rather than by any rule.

Two decisions that happen to agree are not one decision. They can diverge the
moment the accident stops holding: a shell that files a 10-K, a foreign
private issuer filing 20-F, a newly public company with no 10-K yet.

So the invariant:

    There is exactly one component responsible for deciding which SEC
    registrant represents the company, and every SEC-consuming subsystem
    receives that decision.

    was:  company -> _find_cik_exact() -> CIK
    is:   company -> resolve_company_identity() -> CIK -> Truth Delta

Capability is NOT identity. Whether that registrant can supply revenue
evidence remains Truth Delta's question; which registrant it is, is not.

The adversarial fixture below is built so the old crutch cannot rescue it:
BOTH registrants file 10-Ks. Only consuming the resolver's decision picks
correctly, and a subsystem that re-searches independently is free to choose
the other one.
"""
from unittest import mock

from django.test import SimpleTestCase

from . import sec_identity
from .sec_company_identity import resolve_from_candidates
from .truth_delta_sources import SECFilingsIntegration


def submissions(cik, name, forms, tickers=(), former=()):
    return {
        'cik': cik.lstrip('0'), 'name': name, 'tickers': list(tickers),
        'exchanges': ['Nasdaq'] if tickers else [], 'sic': '5810',
        'formerNames': [{'name': n} for n in former],
        'filings': {'recent': {
            'form': [f for f, _ in forms], 'filingDate': [d for _, d in forms]}},
    }


# Both file 10-Ks, so a `type=10-K` filter cannot separate them. The intended
# registrant wins only on the resolver's own signals -- a current-name match
# against a former-name one.
INTENDED = submissions('0000829224', 'HARBOR BAKERY CORP',
                       [('10-K', '2026-03-01'), ('10-Q', '2026-08-01')], tickers=['HBC'])
DECOY = submissions('0000887557', 'SOMETHING ELSE INC',
                    [('10-K', '2026-02-01')], former=['HARBOR BAKERY CORPORATION'])


class OneDecisionNotTwoAgreeingTests(SimpleTestCase):

    def test_the_resolver_picks_the_intended_registrant(self):
        """Control: the fixture is decidable, so the assertions below mean
        something."""
        identity = resolve_from_candidates('Harbor Bakery Corporation', [DECOY, INTENDED])
        self.assertEqual(identity.cik, '0000829224')

    def test_truth_delta_returns_the_registrant_the_resolver_chose(self):
        with mock.patch('zelda_api.sec_company_identity.resolve_company_identity',
                        return_value=resolve_from_candidates(
                            'Harbor Bakery Corporation', [DECOY, INTENDED])):
            cik, reason = SECFilingsIntegration().resolve_with_diagnostics(
                'Harbor Bakery Corporation')
        self.assertEqual(cik, '0000829224')
        self.assertIsNone(reason)

    def test_both_subsystems_return_the_same_registrant(self):
        """
        The invariant, asserted across the two consumers that diverged live
        on 2026-09-26.
        """
        identity = resolve_from_candidates('Harbor Bakery Corporation', [DECOY, INTENDED])
        with mock.patch('zelda_api.sec_company_identity.resolve_company_identity',
                        return_value=identity):
            truth_delta_cik, _ = SECFilingsIntegration().resolve_with_diagnostics(
                'Harbor Bakery Corporation')
            entity_integrity = sec_identity.find_sec_filer('Harbor Bakery Corporation')
        self.assertEqual(truth_delta_cik, entity_integrity.cik)
        self.assertEqual(truth_delta_cik, '0000829224')

    def test_truth_delta_cannot_resolve_what_the_resolver_refused(self):
        """
        A refusal must propagate. If Truth Delta can still reach a CIK when
        the resolver declined to choose, it has an independent path.
        """
        ambiguous = resolve_from_candidates('Harbor Bakery Corp', [
            submissions('0000000001', 'HARBOR BAKERY CORP', [('10-K', '2026-03-01')]),
            submissions('0000000002', 'HARBOR BAKERY CORP', [('10-K', '2026-03-01')]),
        ])
        with mock.patch('zelda_api.sec_company_identity.resolve_company_identity',
                        return_value=ambiguous):
            cik, reason = SECFilingsIntegration().resolve_with_diagnostics('Harbor Bakery Corp')
        self.assertIsNone(cik)
        self.assertEqual(reason, 'ambiguous')

    def test_an_absent_registrant_is_not_found(self):
        absent = resolve_from_candidates('Pamelas Pizza', [])
        with mock.patch('zelda_api.sec_company_identity.resolve_company_identity',
                        return_value=absent):
            cik, reason = SECFilingsIntegration().resolve_with_diagnostics('Pamelas Pizza')
        self.assertIsNone(cik)
        self.assertEqual(reason, 'not_found')


class TheTenKCrutchIsGoneTests(SimpleTestCase):

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)

    def test_no_sec_request_filters_by_form_type(self):
        """
        `type=10-K` narrowed the search enough to exclude the dormant
        registrant, which made Truth Delta look correct while it was still
        guessing. It also drops foreign private issuers filing 20-F or 40-F
        and newly public companies with no annual report yet.

        The cache is cleared first and the call list asserted non-empty: the
        first version of this test passed while making no requests at all,
        because an earlier test had already cached the answer.
        """
        calls = []

        class FakeResponse:
            status_code = 200
            text = '<feed><cik>0000829224</cik></feed>'

            def json(self):
                return {}

        def record(url, params=None, **kwargs):
            calls.append(dict(params or {}))
            return FakeResponse()

        integration = SECFilingsIntegration()
        # The seam is sec_identity._get: identity resolution moved there, so
        # that is where SEC requests are now made.
        with mock.patch.object(sec_identity, '_get', side_effect=record):
            integration.resolve_with_diagnostics('Harbor Bakery Corporation')

        self.assertTrue(calls, 'no SEC request was made, so this test checked nothing')
        for params in calls:
            self.assertNotIn('type', params, 'a request still filters by form type')


class TransientFailuresStillSaySoTests(SimpleTestCase):
    """
    Regression for #98: an unreachable source is a statement about the
    attempt, never an absence of a registrant, and must not be cached.
    """

    def test_sec_unavailable_propagates_as_a_transient_reason(self):
        with mock.patch('zelda_api.sec_company_identity.resolve_company_identity',
                        side_effect=sec_identity.SecUnavailable('SEC timed out')):
            cik, reason = SECFilingsIntegration().resolve_with_diagnostics('Harbor Bakery Corp')
        self.assertIsNone(cik)
        self.assertIn(reason, SECFilingsIntegration.TRANSIENT_REASONS)


class NoIdentityMeansNoEvidenceTests(SimpleTestCase):
    """
    Ported from tests_sec_entity_identity, which pinned this at the feed
    level. The feed-level rules went with `_find_cik_exact`; this property
    did not, and nothing else asserts it: an unresolved company must
    contribute no company data, so it can never reach the comparison layer.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)

    def fetch_with(self, identity):
        integration = SECFilingsIntegration()
        facts = {'facts': {'us-gaap': {}}, 'entityName': 'SOMEONE ELSE INC', '_cik': 'x'}

        class FactsResponse:
            status_code = 200
            text = ''

            def json(self):
                return dict(facts)

        with mock.patch('zelda_api.sec_company_identity.resolve_company_identity',
                        return_value=identity), \
             mock.patch.object(integration.session, 'get', return_value=FactsResponse()):
            return integration.fetch_company_data('Harbor Bakery Corporation')

    def test_the_harness_can_see_a_resolved_company(self):
        """
        Positive control. Without it, the assertions below could pass because
        the harness never returns anything at all.
        """
        resolved = resolve_from_candidates('Harbor Bakery Corporation', [DECOY, INTENDED])
        self.assertEqual(self.fetch_with(resolved).get('_cik'), '0000829224')

    def test_an_ambiguous_company_yields_no_company_data(self):
        ambiguous = resolve_from_candidates('Harbor Bakery Corp', [
            submissions('0000000001', 'HARBOR BAKERY CORP', [('10-K', '2026-03-01')]),
            submissions('0000000002', 'HARBOR BAKERY CORP', [('10-K', '2026-03-01')]),
        ])
        self.assertEqual(self.fetch_with(ambiguous), {})

    def test_an_absent_company_yields_no_company_data(self):
        self.assertEqual(self.fetch_with(resolve_from_candidates('Nobody', [])), {})

    def test_a_candidate_with_no_name_of_its_own_is_never_resolved(self):
        """
        Also ported: a submissions payload carrying a CIK and no name cannot
        be matched to anyone, and an unverifiable registrant is exactly what
        identity resolution exists to refuse.
        """
        nameless = {'cik': '887557', 'tickers': [], 'formerNames': [],
                    'filings': {'recent': {'form': ['10-K'], 'filingDate': ['2026-01-01']}}}
        identity = resolve_from_candidates('Harbor Bakery Corporation', [nameless])
        self.assertIsNone(identity.cik)
