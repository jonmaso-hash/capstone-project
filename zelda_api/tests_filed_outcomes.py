"""
Three outcomes where there was one, and an absence that may not be inferred.

`company_record` used to return NO_RECORD whenever no single exact name match
was found, directly against the comment sitting beside it: absence of a
confident match is not absence of the company. Three different facts shared one
answer, and only one of them is about the register at all:

    no rows at all          NO_RECORD   the register was silent
    rows, no exact match    UNRESOLVED  a misspelling or an abbreviation
    rows, several exact     AMBIGUOUS   one name, two registrations

The distinction is not cosmetic. NO_RECORD earns no line in an investor-facing
report, because a name we spelled differently is the ordinary reason for it.
UNRESOLVED and AMBIGUOUS must be said out loud, because a reader who sees
nothing will assume the business was checked and cleared.

The second half is the officer rule. Officers exist in FL (10/10) and TX (8/10)
and in none of the other eleven measured registrars, Delaware included. So
present officers are used wherever they come from, while ABSENCE may only be
reported where the registrar publishes officers at all -- otherwise "the
register does not list this founder" is manufactured from a registrar that
lists no founders for anyone.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from . import filed
from .entity_verification_models import EntityVerificationReport as R

User = get_user_model()

FL_META = {'source': 'Florida Division of Corporations (Sunbiz)',
           'lastUpdated': '2026-09-28T00:00:00+00:00'}
DE_META = {'source': 'Delaware DOS',
           'lastUpdated': '2026-09-28T00:00:00+00:00'}


def detail(state, meta, officers=(), name='Northwind Grid, Inc.'):
    return {'data': {'id': 'x', 'name': name, 'state': state, 'status': 'Active',
                     'type': 'Corporation', 'formedDate': '2021-04-01',
                     'officers': [{'name': n, 'source': 'state'} for n in officers],
                     'registeredAgent': None, 'filings': []},
            'meta': dict(meta)}


class TheThreeOutcomesAreDistinctTests(SimpleTestCase):

    ROWS_NO_EXACT = [{'id': 'a', 'name': '321 COASTAL CLEANERS LLC', 'state': 'FL'},
                     {'id': 'b', 'name': '321 COASTAL CRUISIN LLC', 'state': 'FL'}]
    ROWS_TWO_EXACT = [{'id': 'p', 'name': 'ACME AI, INC.', 'state': 'DE'},
                      {'id': 'q', 'name': 'ACME AI INC', 'state': 'CA'}]
    ROWS_ONE_EXACT = [{'id': 'r', 'name': 'NORTHWIND GRID, INC.', 'state': 'FL'},
                      {'id': 's', 'name': 'NORTHWIND GRID HOLDINGS LLC', 'state': 'FL'}]

    def test_no_rows_is_the_only_no_record(self):
        self.assertEqual(filed.resolve_candidate([], 'Acme AI, Inc.')[0], filed.NO_RECORD)

    def test_rows_without_an_exact_match_are_unresolved(self):
        outcome, candidate = filed.resolve_candidate(self.ROWS_NO_EXACT, 'Coastal 321 LLC')
        self.assertEqual(outcome, filed.UNRESOLVED)
        self.assertIsNone(candidate)

    def test_several_exact_matches_are_ambiguous(self):
        outcome, candidate = filed.resolve_candidate(self.ROWS_TWO_EXACT, 'Acme AI, Inc.')
        self.assertEqual(outcome, filed.AMBIGUOUS)
        self.assertIsNone(candidate)

    def test_one_exact_match_is_found_and_returns_that_row(self):
        outcome, candidate = filed.resolve_candidate(self.ROWS_ONE_EXACT, 'Northwind Grid, Inc.')
        self.assertEqual(outcome, filed.FOUND)
        self.assertEqual(candidate['id'], 'r')

    def test_the_four_outcomes_are_four_distinct_values(self):
        """A split that reused a value would read as done and behave as before."""
        self.assertEqual(len({filed.NO_RECORD, filed.UNRESOLVED,
                              filed.AMBIGUOUS, filed.FOUND}), 4)

    def test_candidate_for_still_answers_the_old_question(self):
        """The simpler helper stays usable for callers that only want the row."""
        self.assertIsNone(filed.candidate_for(self.ROWS_TWO_EXACT, 'Acme AI, Inc.'))
        self.assertEqual(
            filed.candidate_for(self.ROWS_ONE_EXACT, 'Northwind Grid, Inc.')['id'], 'r')


class AbsenceOfOfficersIsNotEvidenceEverywhereTests(SimpleTestCase):

    def test_officers_present_are_used_even_from_a_registrar_that_usually_has_none(self):
        """
        Delaware publishes none in the sample, but data that IS there is real
        corroboration and must not be discarded.
        """
        self.assertEqual(
            filed.officer_names(detail('DE', DE_META, officers=['JANE DOE'])),
            ['JANE DOE'])

    def test_absence_is_meaningful_only_where_the_registrar_publishes_officers(self):
        self.assertTrue(filed.officer_absence_is_meaningful(detail('FL', FL_META)))
        self.assertFalse(filed.officer_absence_is_meaningful(detail('DE', DE_META)))

    def test_officers_are_still_refused_from_a_non_state_source(self):
        federal = {'source': 'IRS Exempt Organizations Business Master File'}
        self.assertEqual(filed.officer_names(detail('WA', federal, officers=['SOMEONE'])), [])


class TheRowsSayWhatWasEstablishedTests(TestCase):
    """
    End to end through `collect_findings`, because the wording is the product.
    """

    def setUp(self):
        from matchmaking.models import Application
        self.user = User.objects.create_user('outcomes_owner', password='x')
        self.subject = Application.objects.create(
            user=self.user, company_name='Northwind Grid, Inc.',
            founder_name='Jane Doe', email='o@t.invalid', description='test',
            sector='Energy', stage='Seed', years_in_business=4,
            company_website='', geography='Jacksonville, FL')

    def _rows(self, outcome, detail_body):
        from . import entity_verification
        with mock.patch('zelda_api.sec_identity.sec_findings'), \
             mock.patch.object(filed, 'company_record',
                               return_value=(outcome, detail_body)):
            found = entity_verification.collect_findings(self.subject)
        return {r['check']: r for r in found}

    def test_no_record_adds_no_row(self):
        self.assertNotIn('business_registration', self._rows(filed.NO_RECORD, None))

    def test_coverage_constrains_negative_inference_independently_of_authority(self):
        """
        The lesson the Delaware probe cost six credits to find, pinned.

        A future refactor could correctly observe that Delaware's
        classification is `state_registry` and conclude that a Delaware miss is
        authoritative. It is not: Delaware carries 51 records for a query
        returning 3,420 in Florida. So for a subject whose jurisdiction is
        partly covered, NO_RECORD must produce no adverse finding, no claim
        that the business is unregistered, and no suggestion that existence
        could not be verified.

        Authority says whether a HIT counts. Coverage says whether a MISS
        counts. They are different questions and this test fails if they are
        ever merged.
        """
        from .filed_authority import STATE_REGISTRY, classification_for, coverage_for
        # The premise: Delaware really is authoritative AND partly covered.
        self.assertEqual(classification_for('DE'), STATE_REGISTRY)
        self.assertEqual(coverage_for('DE'), 'partial')

        self.subject.geography = 'Wilmington, DE'
        self.subject.save(update_fields=['geography'])
        rows = self._rows(filed.NO_RECORD, None)

        self.assertNotIn('business_registration', rows)
        adverse = [r for r in rows.values()
                   if r.get('result') in (R.DOESNT_MATCH, R.NOT_FOUND)
                   and r.get('check') in ('business_registration', 'officer_of_record')]
        self.assertEqual(adverse, [])
        blob = ' '.join(str(r.get('evidence', '')) for r in rows.values()).lower()
        for forbidden in ('not registered', 'no registration',
                          'could not verify existence', 'does not exist'):
            self.assertNotIn(forbidden, blob)

    def test_unresolved_says_the_query_could_not_be_attributed(self):
        row = self._rows(filed.UNRESOLVED, None)['business_registration']
        self.assertEqual(row['result'], R.COULDNT_CHECK)
        self.assertIn('none matched', row['evidence'])
        self.assertIn('not evidence', row['evidence'])

    def test_ambiguous_says_more_than_one_business_matches(self):
        row = self._rows(filed.AMBIGUOUS, None)['business_registration']
        self.assertEqual(row['result'], R.COULDNT_CHECK)
        self.assertIn('More than one', row['evidence'])

    def test_a_state_record_is_a_public_record_naming_the_registrar(self):
        row = self._rows(filed.FOUND, detail('FL', FL_META))['business_registration']
        self.assertEqual(row['result'], R.PUBLIC_RECORD)
        self.assertIn('Florida Division of Corporations', row['evidence_source'])
        self.assertNotIn('Filed', row['evidence'])

    def test_a_partly_carried_register_says_so(self):
        """
        Delaware: 51 records for a query returning 3,420 in Florida. Without
        this sentence a Delaware hit reads as though the whole register was
        searched.
        """
        row = self._rows(filed.FOUND, detail('DE', DE_META))['business_registration']
        self.assertIn('only partly carried', row['evidence'])

    def test_a_broad_register_does_not_carry_that_caveat(self):
        row = self._rows(filed.FOUND, detail('FL', FL_META))['business_registration']
        self.assertNotIn('only partly carried', row['evidence'])

    def test_no_officer_row_where_the_registrar_publishes_none(self):
        """
        The founder is not named in a Delaware record, and Delaware names no
        officers for anyone -- so there must be no row implying otherwise.
        """
        self.assertNotIn('officer_of_record', self._rows(filed.FOUND, detail('DE', DE_META)))

    def test_an_officer_match_is_reported_where_the_registrar_publishes_them(self):
        rows = self._rows(filed.FOUND, detail('FL', FL_META, officers=['JANE DOE']))
        self.assertEqual(rows['officer_of_record']['result'], R.MATCHES)

    def test_a_registration_row_never_implies_the_founder_was_checked(self):
        """
        The claim is legal existence, jurisdiction, type, formation date and
        status -- not management identity.
        """
        row = self._rows(filed.FOUND, detail('FL', FL_META))['business_registration']
        lowered = row['evidence'].lower()
        for overclaim in ('founder', 'owner', 'management', 'verified'):
            self.assertNotIn(overclaim, lowered)
