"""
Filed: a business-entity corroboration provider, gated on source authority.

NOT a Secretary of State provider, and the name matters. A `state=WA` business
search returned `meta.source = "IRS Exempt Organizations Business Master File"`
for Costco, Microsoft, Starbucks and Nordstrom, with `type` values including
`FCC Licensee` and `Sole Proprietorship`. Washington has no state-registration
coverage, and Filed answers the state query with blended federal data under one
federal label. So:

    a state query is NOT necessarily state-registration evidence

and the provider decides, per response, whether what came back is authoritative
for the claim at hand. A module called `secretary_of_state` would have smuggled
that conclusion into its own name.

Every rule here was measured against the live API on a trial key (2026-10-01),
because the published documentation is wrong in four separate ways: the search
parameter is `name` (the documented `q` returns 400), detail is
`/entity/<bare uuid>` (the documented `/entity/FL:F05000002957` returns 404),
the envelope is `{data, meta}` rather than `{results, count}`, and the credit
quotas are a fifth of the blog's. Tests are therefore written against the
observed contract, and the fixtures below are trimmed real payloads.

Four properties the tests exist to hold:

  SOURCE AUTHORITY IS ALLOWLISTED, NOT INFERRED. An unrecognised source is
  `couldnt_check` with the source named, never a finding. Declared rather than
  pattern-matched, for the reason source_capabilities.py exists: a default is
  not a decision, it is an omission.

  RECORD AGE QUALIFIES WHAT A RECORD CAN DO. Measured staleness ran from
  same-day (NY) to ~6 months (FL). A record always supports a `public_record`
  statement of what the registry said and when; only a FRESH record from a
  recognised authority may contradict a profile. Otherwise a company that
  reinstated last month gets called dissolved.

  A HIT IS A CANDIDATE. Nationwide search is fuzzy -- "Publix Super Markets"
  put a DBA above `PUBLIX SUPER MARKETS, INC.`, and "Coastal 321" returned
  `321 COASTAL CLEANERS LLC`. Selection is an exact normalised legal-name
  match or nothing.

  ABSENCE IS NOT A FINDING. `total: 0` is the ordinary state of a company whose
  name we spelled differently, and it may never become "this business does not
  exist".
"""
from datetime import datetime, timezone
from unittest import mock

from django.test import SimpleTestCase, TestCase

from .filed import (
    CROSS_STATE_SOURCE, FOUND, NO_RECORD, UNAVAILABLE, UNCONFIGURED,
    CONTRADICTION_MAX_AGE_DAYS, candidate_for, classify, describe_record,
    is_state_registration_source, officer_names, record_age_days,
    may_contradict,
)

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)

# A trimmed real detail payload: Publix, fetched by bare UUID.
FL_DETAIL = {
    'data': {
        'id': '15f837e4-f32a-4b74-8ecc-a1e93af1daae',
        'name': 'PUBLIX SUPER MARKETS, INC.',
        'state': 'FL',
        'stateEntityId': '163450',
        'type': 'Corporation',
        'status': 'Active',
        'formedDate': '1921-12-27',
        'registeredAgent': {'name': 'Network, Inc. Corporate Creations',
                            'address': '801 US Highway 1, North Palm Beach, FL, 33408'},
        'officers': [{'name': 'MERRIANN M METZ', 'title': 'SVP,', 'source': 'state'},
                     {'name': 'DAVID P PHILLIPS', 'title': 'Executive', 'source': 'state'}],
        'filings': [],
    },
    'meta': {'source': 'Florida Division of Corporations (Sunbiz)',
             'lastUpdated': '2026-05-18T15:20:59.912746+00:00'},
}

# The Washington response, which is the reason this module is gated at all.
WA_DETAIL = {
    'data': {'id': 'w-1', 'name': 'COSTCO WHOLESALE', 'state': 'WA',
             'type': 'FCC Licensee', 'status': 'Active', 'officers': [],
             'registeredAgent': None},
    'meta': {'source': 'IRS Exempt Organizations Business Master File',
             'lastUpdated': '2026-09-30T00:00:00+00:00'},
}


class SourceAuthorityIsAllowlistedTests(SimpleTestCase):
    """
    The WA measurement in test form. Filed returning data is not Filed
    returning state-registration data.
    """

    def test_the_measured_state_authorities_are_recognised(self):
        for source in ('Florida Division of Corporations (Sunbiz)',
                       'Delaware DOS', 'California SOS', 'Texas SOS',
                       'New York Department of State'):
            with self.subTest(source=source):
                self.assertTrue(is_state_registration_source(source))

    def test_the_irs_substitution_is_not_a_state_authority(self):
        """
        Measured on WA for four separate large companies. If this ever passes,
        federal nonprofit records are being presented as state registration
        evidence.
        """
        self.assertFalse(is_state_registration_source(
            'IRS Exempt Organizations Business Master File'))

    def test_a_nationwide_search_is_not_a_state_authority(self):
        """
        A name-only query sets this source. It is a search mode, not a
        registry, so a finding may never rest on it -- which is what forces the
        two-step search-then-detail flow.
        """
        self.assertFalse(is_state_registration_source(CROSS_STATE_SOURCE))

    def test_an_unrecognised_source_is_refused_rather_than_assumed(self):
        for source in ('SAM.gov', 'FCC Licensee Database', 'Some New Feed',
                       '', None):
            with self.subTest(source=source):
                self.assertFalse(is_state_registration_source(source))


class RecordAgeQualifiesTheFindingTests(SimpleTestCase):
    """
    Filed's docs say "Real-time data -- Sourced directly from state databases,
    not stale caches". Measured `lastUpdated`: NY same-day, TX 2026-04-30,
    FL 2026-04-21 to 2026-05-18, DE 2026-03-22. So the claim is false, but the
    staleness is DISCLOSED per record, which is what makes it usable.
    """

    def test_the_age_is_read_from_the_meta_block(self):
        """Measured: lastUpdated lives in `meta`, not in `data`."""
        self.assertEqual(record_age_days(FL_DETAIL, now=NOW), 136)

    def test_a_record_with_no_date_has_an_unknown_age(self):
        self.assertIsNone(record_age_days({'data': {}, 'meta': {}}, now=NOW))

    def test_a_stale_record_may_not_contradict(self):
        """
        The Florida record is ~4.5 months old. A company that reinstated last
        month would be called dissolved on the strength of it.
        """
        self.assertFalse(may_contradict(FL_DETAIL, now=NOW))

    def test_a_fresh_record_from_a_recognised_authority_may_contradict(self):
        fresh = {'data': dict(FL_DETAIL['data']),
                 'meta': dict(FL_DETAIL['meta'], lastUpdated='2026-09-28T00:00:00+00:00')}
        self.assertTrue(may_contradict(fresh, now=NOW))

    def test_a_fresh_record_from_an_UNRECOGNISED_authority_may_not_contradict(self):
        """
        The WA payload is one day old and still inadmissible. Freshness is not
        authority -- without this, recent IRS nonprofit data could contradict a
        company's own account of itself.
        """
        self.assertFalse(may_contradict(WA_DETAIL, now=NOW))

    def test_an_undated_record_may_not_contradict(self):
        undated = {'data': dict(FL_DETAIL['data']), 'meta': {'source': FL_DETAIL['meta']['source']}}
        self.assertFalse(may_contradict(undated, now=NOW))

    def test_the_threshold_is_a_declared_number(self):
        self.assertIsInstance(CONTRADICTION_MAX_AGE_DAYS, int)
        self.assertGreater(CONTRADICTION_MAX_AGE_DAYS, 0)


class AHitIsOnlyACandidateTests(SimpleTestCase):
    """
    Nationwide search is a fuzzy token match. Real measurements:
    "Publix Super Markets" ranked `ALLAN, JOHN S DBA PUBLIX SUP...` first, and
    "Coastal 321" returned `321 COASTAL CLEANERS LLC`.
    """

    ROWS = [
        {'id': 'a', 'name': 'ALLAN, JOHN S DBA PUBLIX SUPER MARKET', 'state': 'NC'},
        {'id': 'b', 'name': 'PUBLIX SUPER MARKETS, INC.', 'state': 'FL'},
        {'id': 'c', 'name': 'PUBLIX SUPER MARKETS CHARITIES INC', 'state': 'FL'},
    ]

    def test_the_exact_legal_name_is_chosen_over_the_top_hit(self):
        self.assertEqual(candidate_for(self.ROWS, 'Publix Super Markets, Inc.')['id'], 'b')

    def test_a_legal_suffix_difference_still_matches(self):
        self.assertEqual(candidate_for(self.ROWS, 'Publix Super Markets Inc')['id'], 'b')

    def test_no_exact_match_selects_nothing(self):
        """
        The "Coastal 321" case: every row is a near miss. Picking the closest
        would attribute one company's officers to another.
        """
        rows = [{'id': 'x', 'name': '321 COASTAL CLEANERS LLC', 'state': 'FL'},
                {'id': 'y', 'name': '321 COASTAL CRUISIN LLC', 'state': 'FL'}]
        self.assertIsNone(candidate_for(rows, 'Coastal 321 LLC'))

    def test_two_exact_matches_in_different_states_select_nothing(self):
        """A company registered under one name in two states is not resolved by name."""
        rows = [{'id': 'p', 'name': 'ACME AI, INC.', 'state': 'DE'},
                {'id': 'q', 'name': 'ACME AI INC', 'state': 'CA'}]
        self.assertIsNone(candidate_for(rows, 'Acme AI, Inc.'))

    def test_an_empty_result_selects_nothing(self):
        self.assertIsNone(candidate_for([], 'Acme AI, Inc.'))


class SilenceAndFailureAreDifferentTests(SimpleTestCase):

    def test_rows_returned_is_found(self):
        self.assertEqual(classify(200, {'data': [{'id': 'a'}], 'meta': {'total': 1}}), FOUND)

    def test_total_zero_is_no_record(self):
        """Measured: HTTP 200 with meta.total 0 for an impossible name."""
        self.assertEqual(classify(200, {'data': [], 'meta': {'total': 0}}), NO_RECORD)

    def test_a_rejected_request_is_unavailable(self):
        self.assertEqual(classify(400, {'error': {'code': 'invalid_params'}}), UNAVAILABLE)

    def test_an_unauthorised_key_is_unavailable_not_absence(self):
        """
        401 is the shape a revoked or expired trial key produces. Reading it as
        "no record" would turn an expired subscription into findings about
        companies.
        """
        self.assertEqual(classify(401, {'error': {'code': 'unauthorized'}}), UNAVAILABLE)

    def test_a_server_error_is_unavailable(self):
        self.assertEqual(classify(503, None), UNAVAILABLE)


class WhatTheRecordIsAllowedToSayTests(SimpleTestCase):

    def test_the_description_names_the_state_authority_not_filed(self):
        """
        Provenance is the state; Filed is the retrieval path. A finding that
        said "Filed" would present an aggregator as the government.
        """
        text = describe_record(FL_DETAIL)
        self.assertIn('Florida Division of Corporations', text)
        self.assertNotIn('Filed', text)

    def test_the_description_states_when_the_record_was_last_updated(self):
        """
        A status without a date is a claim about now, which the data cannot
        support.
        """
        self.assertIn('2026', describe_record(FL_DETAIL))

    def test_the_description_carries_the_status_and_formation_date(self):
        text = describe_record(FL_DETAIL)
        self.assertIn('Active', text)
        self.assertIn('1921', text)

    def test_officers_are_only_read_from_a_qualifying_source(self):
        self.assertEqual(officer_names(FL_DETAIL), ['MERRIANN M METZ', 'DAVID P PHILLIPS'])

    def test_officers_are_refused_from_a_non_state_source(self):
        """
        Officer corroboration is the strongest thing this provider offers, so
        it is also the most damaging to get from the wrong dataset.
        """
        detail = {'data': dict(WA_DETAIL['data'],
                               officers=[{'name': 'SOMEONE', 'source': 'irs'}]),
                  'meta': dict(WA_DETAIL['meta'])}
        self.assertEqual(officer_names(detail), [])


class TheProviderIsWiredInTests(TestCase):
    """
    A provider that exists, is tested, and is never called passes every test
    above. That "present but inert" shape has appeared three times in this
    codebase -- a field written nowhere, a disclaimer only inside an attribute,
    a manifest entry for a module nobody ran -- so the call site is asserted
    behaviourally, with the network mocked.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from matchmaking.models import Application
        self.user = get_user_model().objects.create_user('filed_owner', password='x')
        # No website ON PURPOSE. A company can be registered without one, the
        # Filed query is by name, and this is the path collect_findings returns
        # from early -- so it is the path most likely to be forgotten. It also
        # means nothing here needs the website or WHOIS lookups mocked.
        self.subject = Application.objects.create(
            user=self.user, company_name='Publix Super Markets, Inc.',
            founder_name='A Founder', email='f@t.com', description='test',
            sector='Retail', stage='Seed', years_in_business=5,
            company_website='')

    def _collect(self, search_body, detail_body):
        from zelda_api import entity_verification
        with mock.patch('zelda_api.sec_identity.sec_findings'), \
             mock.patch('zelda_api.filed._key', return_value='test-key'), \
             mock.patch('zelda_api.filed._search', return_value=search_body), \
             mock.patch('zelda_api.filed._detail', return_value=detail_body):
            return entity_verification.collect_findings(self.subject)

    def test_the_website_path_is_not_required(self):
        """Positive control: this subject really has no website."""
        self.assertEqual(self.subject.company_website, '')

    def test_a_state_record_reaches_the_report(self):
        rows = self._collect({'data': [dict(FL_DETAIL['data'])],
                              'meta': {'total': 1, 'source': CROSS_STATE_SOURCE}},
                             FL_DETAIL)
        entity = [r for r in rows if r.get('check') == 'business_registration']
        self.assertTrue(entity, 'the Filed provider never reached collect_findings')
        self.assertIn('Florida Division of Corporations', entity[0]['evidence'])

    def test_a_non_state_source_reaches_the_report_as_couldnt_check(self):
        """
        The WA case end to end. It must appear, and it must not read as a
        finding about the business.
        """
        from .entity_verification_models import EntityVerificationReport as R
        rows = self._collect({'data': [dict(WA_DETAIL['data'], name='Publix Super Markets, Inc.')],
                              'meta': {'total': 1, 'source': CROSS_STATE_SOURCE}},
                             WA_DETAIL)
        entity = [r for r in rows if r.get('check') == 'business_registration']
        self.assertTrue(entity)
        self.assertEqual(entity[0]['result'], R.COULDNT_CHECK)

    def test_no_record_produces_no_finding_at_all(self):
        """
        Absence is the ordinary case for a name we spelled differently, so it
        may not occupy a line in an investor-facing report.
        """
        rows = self._collect({'data': [], 'meta': {'total': 0}}, None)
        self.assertEqual([r for r in rows if r.get('check') == 'business_registration'], [])
