"""
A jurisdiction derived from the profile's own `geography`. No new field.

Both subjects of an Entity Integrity report already carry `geography`, and it
is already the profile's location authority -- in the visibility defaults, in
`DIRECTORY_DISCLOSING_FIELDS`, and in the match vectors. A second location
column would create two authorities for one fact, which is the defect class
this codebase keeps removing.

Every value in the live database, and what it must yield:

    'Denver, CO'       -> CO      'san diego'            -> None
    'Phoenix, AZ'      -> AZ      'Indiana'              -> IN
    'Portland, OR'     -> OR      'Seattle, Washington'  -> WA
    'Long Beach, CA'   -> CA      'Miami, Florida'       -> FL
    'Jacksonville, Fl' -> FL      'Atlanta, GA'          -> GA
    'Wichita, KS'      -> KS

Ten of eleven. The eleventh costs nothing: no jurisdiction means the nationwide
search that already works.

WHAT THIS IS FOR, and what it is not. It supplies SEARCH CONTEXT -- narrowing a
fuzzy nationwide query, and enabling the officer reverse lookup, which returns
zero rows without a state. It does NOT decide where a business is legally
registered, and it is not identity authority: the existing
nationwide-name -> exact candidate -> detail -> `meta.source` path still decides
whether a returned entity is the subject and whether its source may ground a
finding. A company whose profile says Atlanta may be a Delaware corporation,
and the detail record, not this parser, is what says so.

ONLY THE LAST COMMA-SEPARATED SEGMENT COUNTS, and it must match a code or a
state name in full. Scanning the string for any two-letter token would read OR
out of "Portland or Seattle" and IN out of "moved in 2024" -- both valid state
codes and common English words. The narrow rule is what makes a miss safe: it
degrades to nationwide rather than to the wrong jurisdiction, and guessing a
state from a city would attribute a company to a register it was never in.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from .jurisdiction import US_STATES, state_from_geography

User = get_user_model()


class TheLiveValuesParseTests(SimpleTestCase):
    """Fixtures are the actual rows in the database, not invented examples."""

    LIVE = (
        ('Denver, CO', 'CO'),
        ('Phoenix, AZ', 'AZ'),
        ('Portland, OR', 'OR'),
        ('Long Beach, CA', 'CA'),
        ('Jacksonville, Fl', 'FL'),
        ('Wichita, KS', 'KS'),
        ('Atlanta, GA', 'GA'),
        ('Seattle, Washington', 'WA'),
        ('Miami, Florida', 'FL'),
        ('Indiana', 'IN'),
        ('san diego', None),
    )

    def test_every_live_value_parses_as_measured(self):
        for text, expected in self.LIVE:
            with self.subTest(geography=text):
                self.assertEqual(state_from_geography(text), expected)

    def test_coverage_is_ten_of_eleven(self):
        """
        Stated as a number so a regression in the parser shows up as a coverage
        drop rather than as one subtest failing somewhere in a list.
        """
        parsed = [t for t, _ in self.LIVE if state_from_geography(t)]
        self.assertEqual(len(parsed), 10)


class AMissIsSaferThanAGuessTests(SimpleTestCase):
    """
    Each of these would be a wrong jurisdiction under a looser rule, and a
    wrong jurisdiction means searching a register the company was never in.
    """

    def test_a_state_code_that_is_also_an_english_word_is_not_matched_mid_string(self):
        self.assertIsNone(state_from_geography('Portland or Seattle'))
        self.assertIsNone(state_from_geography('We moved in 2024'))

    def test_a_city_named_after_another_state_is_not_that_state(self):
        self.assertIsNone(state_from_geography('Kansas City'))

    def test_washington_dc_is_dc_and_not_washington_state(self):
        """
        Worth pinning, but NOT evidence about precedence. Reordering the parser
        to check names before codes leaves this unchanged, because no US state
        name is two letters -- so a segment can match a code or a name, never
        both. A mutation swapping the order survived this test, and the honest
        reading is that the order is defensive rather than load-bearing.
        """
        self.assertEqual(state_from_geography('Washington, DC'), 'DC')
        self.assertEqual(state_from_geography('Seattle, Washington'), 'WA')

    def test_a_non_us_location_yields_nothing(self):
        self.assertIsNone(state_from_geography('London, England, United Kingdom'))

    def test_vague_or_empty_values_yield_nothing(self):
        for text in ('Remote', 'North America', 'Worldwide', '', None, '   ', ','):
            with self.subTest(geography=text):
                self.assertIsNone(state_from_geography(text))

    def test_case_and_whitespace_do_not_matter(self):
        self.assertEqual(state_from_geography('  denver ,  co  '), 'CO')
        self.assertEqual(state_from_geography('MIAMI, FLORIDA'), 'FL')

    def test_a_bare_state_name_counts(self):
        self.assertEqual(state_from_geography('New York'), 'NY')
        self.assertEqual(state_from_geography('New York, NY'), 'NY')


class TheTableIsCompleteTests(SimpleTestCase):

    def test_fifty_states_plus_dc(self):
        self.assertEqual(len(US_STATES), 51)
        self.assertIn('DC', US_STATES)

    def test_every_code_is_two_upper_case_letters(self):
        for code in US_STATES:
            with self.subTest(code=code):
                self.assertEqual(len(code), 2)
                self.assertTrue(code.isupper())

    def test_every_state_name_round_trips_to_its_code(self):
        for code, name in US_STATES.items():
            with self.subTest(code=code):
                self.assertEqual(state_from_geography(name), code)


class EditingGeographyInvalidatesTheCheckTests(TestCase):
    """
    The invariant that protects against a stale answer surviving a correction.

    Without it, fixing 'san diego' to 'San Diego, CA' would leave Zelda serving
    the cached nationwide lookup for the next seven days -- the profile says one
    thing and the report was built from another. `inputs_hash` is what decides
    whether a check is reused, so the derived jurisdiction has to be inside it.

    The derived value is hashed rather than the raw text, deliberately: moving
    'Denver, CO' to 'Boulder, CO' changes nothing about which register is
    queried, and re-running the check would spend a credit to produce the same
    answer.
    """

    def setUp(self):
        from matchmaking.models import Application
        self.user = User.objects.create_user('jurisdiction_owner', password='x')
        self.subject = Application.objects.create(
            user=self.user, company_name='Northwind Grid, Inc.',
            founder_name='A Founder', email='j@t.invalid', description='test',
            sector='Energy', stage='Seed', years_in_business=3,
            company_website='', geography='san diego')

    def _hash(self):
        from .entity_verification import inputs_hash
        return inputs_hash(self.subject)

    def _save(self, geography):
        self.subject.geography = geography
        self.subject.save(update_fields=['geography'])

    def test_the_jurisdiction_is_part_of_the_identity_inputs(self):
        from .entity_verification import identity_inputs
        self._save('Denver, CO')
        self.assertEqual(identity_inputs(self.subject).get('jurisdiction'), 'CO')

    def test_correcting_an_unparseable_value_forces_a_new_check(self):
        """The exact case: 'san diego' -> 'San Diego, CA' goes None -> CA."""
        before = self._hash()
        self._save('San Diego, CA')
        self.assertNotEqual(self._hash(), before)

    def test_moving_to_another_state_forces_a_new_check(self):
        self._save('Denver, CO')
        before = self._hash()
        self._save('Austin, TX')
        self.assertNotEqual(self._hash(), before)

    def test_a_different_city_in_the_same_state_does_not(self):
        """
        Positive control for the choice to hash the derived value. If this
        fails, every cosmetic edit spends a credit re-deriving the same answer.
        """
        self._save('Denver, CO')
        before = self._hash()
        self._save('Boulder, CO')
        self.assertEqual(self._hash(), before)

    def test_an_unparseable_value_is_still_a_stable_input(self):
        self._save('Remote')
        self.assertEqual(self._hash(), self._hash())


class TheJurisdictionNarrowsTheSearchTests(TestCase):
    """
    What the jurisdiction is actually used for: a better query. A state-scoped
    search ranks the exact company above fuzzy matches -- measured, nationwide
    put `ALLAN, JOHN S DBA PUBLIX SUPER MARKET` above `PUBLIX SUPER MARKETS,
    INC.` -- and the officer reverse lookup returns nothing at all without one.
    """

    def setUp(self):
        from matchmaking.models import Application
        self.user = User.objects.create_user('narrow_owner', password='x')
        self.subject = Application.objects.create(
            user=self.user, company_name='Publix Super Markets, Inc.',
            founder_name='A Founder', email='n@t.invalid', description='test',
            sector='Retail', stage='Seed', years_in_business=5,
            company_website='', geography='Lakeland, FL')

    def test_a_parseable_jurisdiction_scopes_the_search(self):
        from . import filed
        with mock.patch.object(filed, '_key', return_value='k'), \
             mock.patch.object(filed, '_search',
                               return_value={'data': [], 'meta': {'total': 0}}) as search:
            filed.company_record('Publix Super Markets, Inc.', state='FL')
        self.assertEqual(search.call_args.kwargs.get('state'), 'FL')

    def test_without_a_jurisdiction_the_search_stays_nationwide(self):
        """
        No state must mean no `state` argument, not `state=None` -- the API
        treats the parameter's absence as a cross-state search, and passing an
        empty one is a different request.
        """
        from . import filed
        with mock.patch.object(filed, '_key', return_value='k'), \
             mock.patch.object(filed, '_search',
                               return_value={'data': [], 'meta': {'total': 0}}) as search:
            filed.company_record('Publix Super Markets, Inc.')
        self.assertIsNone(search.call_args.kwargs.get('state'))

    def test_the_state_parameter_is_omitted_rather_than_sent_empty(self):
        """
        Checked at `_get`, where the params dict is actually built.

        The test above mocks `_search`, so it cannot see what `_search` does
        with its argument -- a mutation that sent `state: None` unconditionally
        survived it. That mutation is harmless today only because `requests`
        happens to drop None-valued params, which is a library detail this
        module should not depend on silently: the API treats the parameter's
        ABSENCE as the cross-state mode.
        """
        from . import filed
        with mock.patch.object(filed, '_get', return_value=(200, {})) as got:
            filed._search('Acme Inc')
        self.assertNotIn('state', got.call_args.kwargs)

        with mock.patch.object(filed, '_get', return_value=(200, {})) as got:
            filed._search('Acme Inc', state='FL')
        self.assertEqual(got.call_args.kwargs.get('state'), 'FL')

    def test_collect_findings_passes_the_profiles_jurisdiction(self):
        """
        End to end: the parser's output has to actually reach the provider. A
        derived value nothing consumes is the "present but inert" shape again.
        """
        from . import entity_verification, filed
        with mock.patch('zelda_api.sec_identity.sec_findings'), \
             mock.patch.object(filed, '_key', return_value='k'), \
             mock.patch.object(filed, 'company_record',
                               return_value=(filed.NO_RECORD, None)) as record:
            entity_verification.collect_findings(self.subject)
        self.assertEqual(record.call_args.kwargs.get('state'), 'FL')
