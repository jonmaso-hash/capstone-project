"""
Task 6: corroboration in the evidence model.

A source can contribute evidence without becoming the factual authority:
    CAN_ESTABLISH      decides verified / contradicted
    CAN_CORROBORATE    attaches as agreeing or dissenting; never decides
    INFORMATIONAL_ONLY labelled context; never compared
    UNAVAILABLE        never stored
Decided rules (2026-10-03): corroboration alone leaves a claim INSUFFICIENT
with reason 'corroboration_only'; an establishing verdict stands against a
dissenting corroborator, which is recorded; same-origin evidence is not
independent.
"""
import importlib
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from zelda_api.grounded_context import CORROBORATES, ESTABLISHES, INSUFFICIENT, VERIFIED, GroundedContext
from zelda_api.principal import ORIGIN_TASK, Principal
from zelda_api.source_capabilities import (
    CAN_CORROBORATE, CAN_ESTABLISH, CAPABILITIES, EVIDENCE_ORIGINS, INFORMATIONAL_ONLY, LINKEDIN_DERIVED,
    SEC_FILING, SOURCE_ORIGINS, THIRD_PARTY_DATABASE, UNAVAILABLE, capability_for, may_establish, may_store,
    origin_for,
)
from zelda_api.truth_delta_engine import TruthDeltaEngine
from zelda_api.truth_delta_models import (
    ClaimedDatapoint, ExternalDataSource, ObservedDatapoint, TruthDeltaReport,
)
from zelda_api.vector_models import DocumentSource


class RegistryTests(TestCase):

    def test_every_source_declares_an_origin(self):
        self.assertEqual(set(SOURCE_ORIGINS), set(CAPABILITIES))
        for source, origin in SOURCE_ORIGINS.items():
            with self.subTest(source=source):
                self.assertIn(origin, EVIDENCE_ORIGINS)

    def test_undeclared_origin_raises(self):
        with self.assertRaises(KeyError):
            origin_for('a_source_nobody_declared')

    def test_store_and_establish_are_different_gates(self):
        for source, categories in CAPABILITIES.items():
            for category, role in categories.items():
                with self.subTest(source=source, category=category):
                    self.assertEqual(may_store(source, category), role != UNAVAILABLE)
                    self.assertEqual(may_establish(source, category), role == CAN_ESTABLISH)


class _Evidence(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user('corr_owner', password='x')
        self.doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Corr Co', uploaded_by=self.user,
            document_type='pitch_deck', status='analyzed')
        self.sources = {
            name: ExternalDataSource.objects.get_or_create(
                source_type=name, defaults={'source_name': label, 'is_active': True})[0]
            for name, label in (('sec', 'SEC EDGAR'), ('crunchbase', 'Crunchbase'), ('news', 'NewsAPI'))
        }

    def claim(self, category='funding_raised', value=25e6):
        return ClaimedDatapoint.objects.create(
            document=self.doc, category=category, claimed_value=f'{category} {value}',
            claimed_value_numeric=value, page_number=3, chunk_hash='h', confidence_in_extraction=90.0)

    def observe(self, value, role, origin, source='crunchbase', category='funding_raised', credibility=0.8):
        return ObservedDatapoint.objects.create(
            document=self.doc, category=category, observed_value=str(value), observed_value_numeric=value,
            source=self.sources[source], source_credibility=credibility, role=role, evidence_origin=origin,
            time_period='FY2025')

    def report(self):
        """The real engine's pairing, stored the way verify_document stores it."""
        engine = TruthDeltaEngine()
        claims = list(ClaimedDatapoint.objects.filter(document=self.doc))
        observed = list(ObservedDatapoint.objects.filter(document=self.doc))
        rows = engine._build_comparison(claims, observed)
        return TruthDeltaReport.objects.create(
            document=self.doc, overall_truth_score=50.0, credibility_risk='medium', summary='s',
            details={'claims': [], 'per_claim': [], 'comparison': rows,
                     'observed': engine._serialize_observed(observed)})


class StateRuleTests(_Evidence):

    def test_corroboration_alone_never_verifies(self):
        self.claim()
        self.observe(25e6, CAN_CORROBORATE, LINKEDIN_DERIVED)
        report = self.report()
        self.assertEqual(report.category_states()['funding_raised'], 'no_data')
        self.assertEqual(report.grounding_reasons()['funding_raised'], 'corroboration_only')
        row = report.details['comparison'][0]
        self.assertIsNone(row['observed_value'])
        self.assertTrue(row['corroboration'][0]['agrees'])

    def test_corroboration_alone_never_contradicts(self):
        self.claim()
        self.observe(5e6, CAN_CORROBORATE, LINKEDIN_DERIVED)
        report = self.report()
        self.assertEqual(report.category_states()['funding_raised'], 'no_data')
        self.assertFalse(report.details['comparison'][0]['corroboration'][0]['agrees'])

    def test_establishing_verdict_stands_and_dissent_is_recorded(self):
        self.claim('revenue', 46.4e9)
        self.observe(46.398e9, CAN_ESTABLISH, SEC_FILING, source='sec', category='revenue', credibility=0.95)
        self.observe(60e9, CAN_CORROBORATE, LINKEDIN_DERIVED, category='revenue')
        report = self.report()
        self.assertEqual(report.category_states()['revenue'], 'verified')
        row = report.details['comparison'][0]
        self.assertEqual(row['observed_source'], 'SEC EDGAR')
        self.assertEqual(len(row['corroboration']), 1)
        self.assertFalse(row['corroboration'][0]['agrees'])

    def test_a_more_credible_corroborator_never_becomes_the_evidence(self):
        self.claim('revenue', 46.4e9)
        self.observe(46.398e9, CAN_ESTABLISH, SEC_FILING, source='sec', category='revenue', credibility=0.5)
        self.observe(99e9, CAN_CORROBORATE, THIRD_PARTY_DATABASE, category='revenue', credibility=0.99)
        row = self.report().details['comparison'][0]
        self.assertEqual(row['observed_value_numeric'], 46.398e9)
        self.assertEqual(row['observed_role'], CAN_ESTABLISH)

    def test_informational_is_context_and_moves_nothing(self):
        self.claim('employees', 81500.0)
        self.observe(106208.0, INFORMATIONAL_ONLY, LINKEDIN_DERIVED, source='news', category='employees')
        report = self.report()
        self.assertEqual(report.category_states()['employees'], 'no_data')
        self.assertNotEqual(report.grounding_reasons()['employees'], 'corroboration_only')
        row = report.details['comparison'][0]
        self.assertIsNone(row['observed_value'])
        self.assertEqual(row['corroboration'], [])
        self.assertEqual(row['context'][0]['origin'], LINKEDIN_DERIVED)

    def test_only_establishing_rows_ground_a_category(self):
        self.claim()
        self.observe(25e6, CAN_CORROBORATE, LINKEDIN_DERIVED)
        self.assertEqual(self.report().grounded_categories(), set())


class IndependenceTests(_Evidence):

    def corroboration(self, corroborator_origin):
        self.claim('revenue', 46.4e9)
        self.observe(46.398e9, CAN_ESTABLISH, SEC_FILING, source='sec', category='revenue', credibility=0.95)
        self.observe(46.4e9, CAN_CORROBORATE, corroborator_origin, category='revenue')
        return self.report().details['comparison'][0]['corroboration'][0]

    def test_same_origin_is_not_independent(self):
        self.assertFalse(self.corroboration(SEC_FILING)['independent'])

    def test_different_origin_is_independent(self):
        ObservedDatapoint.objects.all().delete()
        ClaimedDatapoint.objects.all().delete()
        self.assertTrue(self.corroboration(LINKEDIN_DERIVED)['independent'])


class WritePathTests(_Evidence):

    def write(self, source_type, extractors):
        from zelda_api.truth_delta_sources import DataSourceManager

        class Fake:
            source_name = 'Fake'
            last_failure_reason = None

            def authenticate(self):
                return True

            def fetch_company_data(self, company_name, domain=None):
                return {'x': True}

            def extract_time_period(self, data):
                return 'FY2025'
        Fake.source_type = source_type
        for name, value in extractors.items():
            setattr(Fake, name, (lambda v: (lambda self, data: v))(value))
        with mock.patch.object(DataSourceManager, 'INTEGRATIONS', {source_type: Fake}):
            DataSourceManager.create_observed_datapoints(self.doc, 'Corr Co')
        return list(ObservedDatapoint.objects.filter(document=self.doc).values_list('category', 'role', 'evidence_origin'))

    def test_unavailable_is_never_stored(self):
        rows = self.write('sec', {'extract_revenue': None, 'extract_customers': 218,
                                  'extract_employees': None, 'extract_funding': 5e6})
        self.assertEqual(rows, [])

    def test_rows_carry_role_and_origin(self):
        rows = self.write('crunchbase', {'extract_revenue': (1e6, '$'), 'extract_customers': None,
                                         'extract_employees': 30, 'extract_funding': None})
        self.assertEqual(sorted(rows), [('employees', CAN_CORROBORATE, THIRD_PARTY_DATABASE),
                                        ('revenue', CAN_CORROBORATE, THIRD_PARTY_DATABASE)])
        ObservedDatapoint.objects.all().delete()
        rows = self.write('sec', {'extract_revenue': (46.398e9, '$'), 'extract_customers': None,
                                  'extract_employees': None, 'extract_funding': None})
        self.assertEqual(rows, [('revenue', CAN_ESTABLISH, SEC_FILING)])

    def test_stored_role_matches_the_registry(self):
        self.write('news', {'extract_revenue': (1e6, '$'), 'extract_customers': 4,
                            'extract_employees': 7, 'extract_funding': 5e5})
        for category, role in ObservedDatapoint.objects.values_list('category', 'role'):
            with self.subTest(category=category):
                self.assertEqual(role, capability_for('news', category))


class GroundedContextTests(_Evidence):

    def context(self):
        self.report()
        return GroundedContext.build(Principal.for_user(self.user, ORIGIN_TASK), self.doc)

    def test_corroboration_only_reaches_the_memo_as_insufficient(self):
        self.claim()
        self.observe(25e6, CAN_CORROBORATE, LINKEDIN_DERIVED)
        item = next(i for i in self.context().items if i.kind == 'claim')
        self.assertEqual((item.status, item.reason), (INSUFFICIENT, 'corroboration_only'))
        self.assertEqual([(e.role, e.agrees, e.origin) for e in item.external],
                         [(CORROBORATES, True, LINKEDIN_DERIVED)])

    def test_roles_reach_the_prompt(self):
        self.claim('revenue', 46.4e9)
        self.observe(46.398e9, CAN_ESTABLISH, SEC_FILING, source='sec', category='revenue', credibility=0.95)
        self.observe(60e9, CAN_CORROBORATE, LINKEDIN_DERIVED, category='revenue')
        context = self.context()
        item = next(i for i in context.items if i.kind == 'claim')
        self.assertEqual(item.status, VERIFIED)
        payload = next(i for i in context.to_prompt_payload()['items'] if i['kind'] == 'claim')
        self.assertEqual([(e['role'], e.get('agrees')) for e in payload['external']],
                         [(ESTABLISHES, None), (CORROBORATES, False)])


class BackfillTests(_Evidence):

    def test_existing_rows_get_their_origin(self):
        row = self.observe(46.398e9, CAN_ESTABLISH, '', source='sec', category='revenue')
        migration = importlib.import_module('zelda_api.migrations.0031_observeddatapoint_role_and_origin')
        migration.backfill_origin(django_apps, None)
        row.refresh_from_db()
        self.assertEqual((row.role, row.evidence_origin), (CAN_ESTABLISH, SEC_FILING))
