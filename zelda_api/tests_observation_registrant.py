"""
An observed fact carries which entity it was observed about.

PR #103 made identity singular upstream: one authority decides which SEC
registrant a company is, and Truth Delta consumes that decision. This is the
other half of the boundary -- whether the OBSERVATION retains it.

    #103   Can Truth Delta consume the identity decision?
           company -> identity authority -> CIK -> Truth Delta

    here   Does the observation retain it?
           CIK -> SEC observation -> ObservedDatapoint(registrant=CIK)

`ObservedDatapoint.source` is a foreign key to ExternalDataSource. It names
WHICH SOURCE -- "SEC EDGAR" -- and never WHICH COMPANY AT THAT SOURCE. So a
stored datapoint currently cannot say whose revenue it is. Recovering that by
parsing `source_url` would be the inference this whole line of work exists to
remove.

The invariant:

    Every ObservedDatapoint carrying an SEC observation carries the
    registrant selected by the identity authority that produced that
    observation. The datapoint cannot silently lose that registrant or
    acquire a different one through an independent identity lookup.

Two ways that fails, and both need a test that notices:

LOSING IT. The write path stops propagating the registrant and every
numeric assertion still passes -- the shape `engine_version` shipped in,
inert, with a green suite.

REPLACING IT. Something re-resolves the company while building the datapoint
and substitutes its own answer. The field would hold a plausible CIK, which
is worse than holding none. It is not enough that the field holds the RIGHT
registrant; it must be unable to hold one the authority did not choose.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from .sec_company_identity import CompanyIdentity, FOUND
from .truth_delta_models import ObservedDatapoint
from .truth_delta_sources import DataSourceManager, SECFilingsIntegration
from .vector_models import DocumentSource

User = get_user_model()

CHOSEN = '0000829224'      # what the identity authority selected
SOMEONE_ELSE = '0000887557'  # what an independent lookup would find

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


class AnObservationNamesItsRegistrantTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('reg_owner', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Starbucks Corporation',
            uploaded_by=self.user, document_type='pitch_deck', status='analyzed',
        )

    def observe(self, chosen=CHOSEN, independent=None):
        """
        Runs the real write path with the authority having chosen `chosen`.

        `independent` is what a second, unauthorised lookup would return. It
        is wired into resolve_company_identity so that any code re-resolving
        the company mid-write gets a DIFFERENT answer -- which is what makes
        the substitution detectable rather than invisible.
        """
        payload = dict(FACTS)
        payload['_cik'] = chosen

        identity = CompanyIdentity(
            status=FOUND, cik=independent or chosen, name='STARBUCKS CORP',
            matched_on='current_name', files_periodically=True)

        with mock.patch.object(DataSourceManager, 'INTEGRATIONS',
                               {'sec': SECFilingsIntegration}), \
             mock.patch.object(DataSourceManager, 'fetch_news_headlines', return_value=[]), \
             mock.patch.object(SECFilingsIntegration, 'fetch_company_data',
                               return_value=payload), \
             mock.patch('zelda_api.sec_company_identity.resolve_company_identity',
                        return_value=identity):
            DataSourceManager.create_observed_datapoints(
                self.document, 'Starbucks Corporation')
        return list(ObservedDatapoint.objects.filter(document=self.document))

    def test_the_harness_stores_an_observation_at_all(self):
        """
        Positive control. Every assertion below is about a stored row, so a
        harness that stores nothing would make them all vacuous.
        """
        stored = self.observe()
        self.assertTrue(stored, 'no observation was stored, so nothing was tested')
        self.assertEqual({row.category for row in stored}, {'revenue'})

    def test_an_observation_carries_the_registrant_it_was_observed_about(self):
        for row in self.observe():
            with self.subTest(category=row.category):
                self.assertEqual(row.registrant, CHOSEN)

    def test_the_registrant_is_not_left_blank(self):
        """
        The inert-field failure, stated separately: a write path that drops
        the registrant leaves every numeric assertion passing. engine_version
        shipped exactly this way, with a green suite.
        """
        for row in self.observe():
            self.assertTrue(row.registrant,
                            'the observation lost the registrant it was about')

    def test_a_second_lookup_cannot_substitute_its_own_registrant(self):
        """
        The contract, not a value check. The authority chose one registrant
        and an independent lookup would return another; the stored row must
        follow the authority. A field holding a plausible but unauthorised
        CIK is worse than one holding none.
        """
        for row in self.observe(chosen=CHOSEN, independent=SOMEONE_ELSE):
            with self.subTest(category=row.category):
                self.assertEqual(
                    row.registrant, CHOSEN,
                    'the observation was attributed to a registrant the '
                    'identity authority did not choose')

    def test_a_source_with_no_registrant_concept_stores_none(self):
        """
        Only SEC observations have a registrant. A source that does not
        identify companies must leave it blank rather than borrow one.
        """
        payload = dict(FACTS)  # no _cik
        with mock.patch.object(DataSourceManager, 'INTEGRATIONS',
                               {'sec': SECFilingsIntegration}), \
             mock.patch.object(DataSourceManager, 'fetch_news_headlines', return_value=[]), \
             mock.patch.object(SECFilingsIntegration, 'fetch_company_data',
                               return_value=payload):
            DataSourceManager.create_observed_datapoints(
                self.document, 'Starbucks Corporation')
        for row in ObservedDatapoint.objects.filter(document=self.document):
            self.assertEqual(row.registrant, '')

    def test_the_registrant_reads_back_as_attribution(self):
        """
        The point of storing it: a finding can say which entity the figure
        was observed about, rather than only which source it came from.
        """
        row = self.observe()[0]
        self.assertIn(CHOSEN, row.describes_registrant)
        self.assertIn('SEC', row.describes_registrant)
