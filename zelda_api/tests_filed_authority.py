"""
Filed's authority is a measurement, not a constant.

The provider shipped with five hard-coded trusted sources -- the five states I
had happened to probe. A sweep of all 51 jurisdictions on 2026-10-02 found
thirteen genuine registrars, thirty-seven jurisdictions answering a state query
with the IRS Exempt Organizations file, and one (Iowa) returning nothing at all
despite being listed as covered in Filed's own March post.

So the knowledge moves into `zelda_api/data/filed_state_authority.json`, with
`observed_at` on every entry. A fixture makes the next sweep show DRIFT instead
of silently replacing today's API behaviour with permanent product truth, and
it stops an unfamiliar source being promoted into an accepted registrar by
someone editing a tuple.

FOUR CLASSIFICATIONS, because "Filed returned something" and "a state register
says so" are different facts:

    state_registry        meta.source is a measured government registrar
    federal_substitution  the IRS Exempt Organizations file answered a state
                          query -- data, never registration evidence
    no_data               no rows for any probe query
    unknown_source        anything else; never implicitly trusted

AUTHORITY AND COVERAGE ARE SEPARATE AXES. `Delaware DOS` is a real registrar
and carries 51 records for a query that returns 3,420 in Florida, despite
Delaware having comparable real-world registrations. So a Delaware HIT is real
evidence while a Delaware MISS says almost nothing -- and Delaware is where
startups incorporate. One boolean could not express that.

CAPABILITY IS PER REGISTRAR. Officer records exist in FL (10/10) and TX (8/10)
and in none of the other eleven, including Delaware, California and New York.
Agent records exist in five. So the officer dimension is OMITTED where
unsupported rather than rendered as empty or failed, because absence from a
registrar that never publishes officers is not evidence about a company.
"""
from django.test import SimpleTestCase

from .filed_authority import (
    FEDERAL_SUBSTITUTION, NO_DATA, STATE_REGISTRY, UNKNOWN_SOURCE,
    accepted_sources, authority_for, classification_for, coverage_for,
    is_state_registration_source, jurisdictions, observed_at,
    publishes_agent, publishes_officers,
)


class TheFixtureIsCompleteAndShapedTests(SimpleTestCase):

    def test_every_us_jurisdiction_is_characterised(self):
        """
        51 entries, because an unlisted jurisdiction would fall through to a
        default -- and a default is the silent narrowing this file exists to
        prevent.
        """
        from .jurisdiction import US_STATES
        self.assertEqual(set(jurisdictions()), set(US_STATES))

    def test_the_measured_counts_are_what_the_sweep_found(self):
        counts = {}
        for state in jurisdictions():
            counts[classification_for(state)] = counts.get(classification_for(state), 0) + 1
        self.assertEqual(counts.get(STATE_REGISTRY), 13)
        self.assertEqual(counts.get(FEDERAL_SUBSTITUTION), 37)
        self.assertEqual(counts.get(NO_DATA), 1)

    def test_every_entry_records_when_it_was_observed(self):
        """
        Registrar coverage is an empirical capability that changes
        independently of this code -- Iowa was covered in March and is not now.
        An entry without a date could not be told from a current one.
        """
        for state in jurisdictions():
            with self.subTest(state=state):
                self.assertTrue(observed_at(state))

    def test_iowa_is_recorded_as_a_regression_not_a_failure(self):
        self.assertEqual(classification_for('IA'), NO_DATA)
        self.assertIsNone(authority_for('IA'))

    def test_an_unknown_jurisdiction_raises_rather_than_defaulting(self):
        for bogus in ('ZZ', '', None, 'CALIFORNIA'):
            with self.subTest(value=bogus):
                with self.assertRaises(KeyError):
                    classification_for(bogus)


class OnlyMeasuredRegistrarsAreAuthoritativeTests(SimpleTestCase):

    def test_the_thirteen_measured_sources_are_accepted(self):
        expected = {
            'Alaska Division of Corporations, Business and Professional Licensing',
            'California SOS', 'Colorado Secretary of State',
            'Connecticut Secretary of State',
            'DC Department of Licensing and Consumer Protection',
            'Delaware DOS', 'Florida Division of Corporations (Sunbiz)',
            'Maryland SDAT', 'New York Department of State',
            'Oregon Secretary of State', 'Pennsylvania Department of State',
            'Texas SOS', 'Virginia SCC',
        }
        self.assertEqual(accepted_sources(), expected)
        for source in expected:
            with self.subTest(source=source):
                self.assertTrue(is_state_registration_source(source))

    def test_the_federal_substitution_is_never_an_authority(self):
        """
        Measured in 37 jurisdictions. If this passes, federal nonprofit records
        are being presented as state registration evidence.
        """
        self.assertFalse(is_state_registration_source(
            'IRS Exempt Organizations Business Master File'))

    def test_a_nationwide_search_is_never_an_authority(self):
        self.assertFalse(is_state_registration_source('Cross-state search'))

    def test_an_unrecognised_source_is_refused_rather_than_assumed(self):
        for source in ('SAM.gov', 'FCC Licensee Database', 'Nevada SOS',
                       'Georgia Secretary of State', '', None):
            with self.subTest(source=source):
                self.assertFalse(is_state_registration_source(source))

    def test_a_plausible_but_unmeasured_registrar_is_still_refused(self):
        """
        'Georgia Secretary of State' reads exactly like an accepted entry. It
        is refused because Georgia was MEASURED to return the IRS file, and a
        name-shaped rule would have accepted all 37 substitutions.
        """
        self.assertFalse(is_state_registration_source('Georgia Secretary of State'))
        self.assertEqual(classification_for('GA'), FEDERAL_SUBSTITUTION)


class CoverageIsADifferentQuestionFromAuthorityTests(SimpleTestCase):

    def test_delaware_is_authoritative_and_thinly_covered(self):
        self.assertEqual(classification_for('DE'), STATE_REGISTRY)
        self.assertTrue(is_state_registration_source(authority_for('DE')))
        self.assertEqual(coverage_for('DE'), 'partial')

    def test_an_unmeasured_coverage_is_not_reported_as_broad(self):
        """
        Only Delaware has been measured. Reading a missing value as 'broad'
        would invent evidence for twelve registrars.
        """
        self.assertEqual(coverage_for('FL'), 'unmeasured')
        for state in jurisdictions():
            if classification_for(state) == STATE_REGISTRY:
                with self.subTest(state=state):
                    self.assertIn(coverage_for(state), ('partial', 'unmeasured', 'broad'))

    def test_coverage_is_not_asked_of_a_non_registry(self):
        self.assertIsNone(coverage_for('WA'))

    def test_an_entry_that_omits_coverage_still_reads_as_unmeasured(self):
        """
        The fallback, exercised with input that contains the case.

        Every entry in today's fixture sets `coverage` explicitly, so the
        `or 'unmeasured'` branch is unreachable against the real file -- a
        mutation changing that default to 'broad' survived the whole battery.
        A future entry added without a coverage key would take the branch, and
        reading silence as breadth would invent evidence about a registrar
        nobody measured.
        """
        from unittest import mock
        from . import filed_authority

        synthetic = {
            'schema': 1,
            'jurisdictions': {
                'FL': {'classification': 'state_registry',
                       'authority_source': 'Florida Division of Corporations (Sunbiz)',
                       'observed_at': '2026-10-02'},   # no `coverage` key
            },
        }
        with mock.patch.object(filed_authority, '_document', return_value=synthetic):
            self.assertEqual(filed_authority.coverage_for('FL'), 'unmeasured')


class OfficerCapabilityIsPerRegistrarTests(SimpleTestCase):
    """
    Officers were found in FL 10/10 and TX 8/10, and 0/10 in the other eleven.
    Earlier I generalised a Florida-only sample into a Filed-wide capability;
    this is the correction, pinned.
    """

    def test_only_florida_and_texas_publish_officers(self):
        publishing = {s for s in jurisdictions() if publishes_officers(s)}
        self.assertEqual(publishing, {'FL', 'TX'})

    def test_delaware_does_not_publish_officers(self):
        """The jurisdiction that matters most for founders, and it has none."""
        self.assertFalse(publishes_officers('DE'))

    def test_the_five_agent_registrars_are_recorded(self):
        self.assertEqual({s for s in jurisdictions() if publishes_agent(s)},
                         {'DC', 'FL', 'NY', 'OR', 'TX'})

    def test_a_federal_substitution_publishes_neither(self):
        for state in ('WA', 'GA', 'NV'):
            with self.subTest(state=state):
                self.assertFalse(publishes_officers(state))
                self.assertFalse(publishes_agent(state))
