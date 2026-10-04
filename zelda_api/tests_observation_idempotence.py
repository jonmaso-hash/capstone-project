"""
Phase 1 close-out PR 3, part 2: re-verification is idempotent.

create_observed_datapoints appended on every run, so verifying a document
twice stored its SEC revenue twice. The Nike rerun's reprocessing check
(layer 11) needs "verify twice == verify once". Each source now replaces only
its own previous rows for the document; a source that did not answer keeps
them; other providers' rows are never touched.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from zelda_api.source_capabilities import CAN_CORROBORATE, CAN_ESTABLISH, LINKEDIN_DERIVED, THIRD_PARTY_DATABASE
from zelda_api.truth_delta_engine import TruthDeltaEngine
from zelda_api.truth_delta_models import ClaimedDatapoint, ExternalDataSource, ObservedDatapoint
from zelda_api.truth_delta_sources import DataSourceManager
from zelda_api.vector_models import DocumentSource

JUDGMENT = {'overall_truth_score': 60.0, 'credibility_risk': 'medium', 'summary': 'judged', 'per_claim': []}


def fake_sec(revenue):
    class FakeSEC:
        source_name = 'SEC EDGAR'
        source_type = 'sec'
        last_failure_reason = None

        def authenticate(self):
            return True

        def fetch_company_data(self, company_name, domain=None):
            return {'_cik': '0000320187'} if revenue is not None else {}

        def extract_time_period(self, data):
            return 'FY2026 10-K (period ending 2026-05-31)'

        def extract_revenue(self, data):
            return (revenue, '$')

        def extract_customers(self, data):
            return None

        def extract_employees(self, data):
            return None

        def extract_funding(self, data):
            return None
    return FakeSEC


class IdempotenceTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user('idem_owner', password='x')
        self.doc = DocumentSource.objects.create(
            filename='nike.pptx', source_entity='NIKE, Inc.', uploaded_by=self.user,
            document_type='pitch_deck', status='analyzed')
        ClaimedDatapoint.objects.create(
            document=self.doc, category='revenue', claimed_value='$52.8 billion',
            claimed_value_numeric=52.8e9, page_number=3, chunk_hash='h', confidence_in_extraction=95.0)

    def verify(self, revenue=46.398e9):
        with mock.patch.object(DataSourceManager, 'INTEGRATIONS', {'sec': fake_sec(revenue)}), \
                mock.patch.object(DataSourceManager, 'fetch_news_headlines', return_value=[]), \
                mock.patch.object(TruthDeltaEngine, '_call_claude_for_verification', return_value=dict(JUDGMENT)):
            return TruthDeltaEngine().verify_document(self.doc.id)

    def sec_rows(self):
        return list(ObservedDatapoint.objects.filter(document=self.doc, source__source_type='sec')
                    .values_list('category', 'observed_value_numeric', 'role', 'registrant'))

    def test_verifying_twice_equals_verifying_once(self):
        first = self.verify()
        rows_once = self.sec_rows()
        second = self.verify()
        self.assertEqual(self.sec_rows(), rows_once)
        self.assertEqual(len(rows_once), 1)
        self.assertEqual(second.category_states(), first.category_states())
        self.assertEqual(second.grounding_reasons(), first.grounding_reasons())
        self.assertEqual(second.details['comparison'], first.details['comparison'])
        self.assertEqual(second.verifiability_stats(), first.verifiability_stats())

    def test_a_changed_answer_replaces_the_old_one(self):
        self.verify(revenue=46.398e9)
        self.verify(revenue=46.309e9)
        self.assertEqual([value for _, value, _, _ in self.sec_rows()], [46.309e9])

    def test_a_source_that_does_not_answer_keeps_its_earlier_evidence(self):
        self.verify(revenue=46.398e9)
        self.verify(revenue=None)                      # SEC returned nothing this run
        self.assertEqual([value for _, value, _, _ in self.sec_rows()], [46.398e9])

    def test_other_providers_are_untouched(self):
        d4b, _ = ExternalDataSource.objects.get_or_create(source_type='dataforb2b', defaults={'source_name': 'DataForB2B'})
        cb, _ = ExternalDataSource.objects.get_or_create(source_type='crunchbase', defaults={'source_name': 'Crunchbase'})
        kept = [
            ObservedDatapoint.objects.create(document=self.doc, category='funding_raised', observed_value='$865,000,000',
                                             observed_value_numeric=865e6, source=d4b, role=CAN_CORROBORATE,
                                             evidence_origin=LINKEDIN_DERIVED),
            ObservedDatapoint.objects.create(document=self.doc, category='revenue', observed_value='$1',
                                             observed_value_numeric=1.0, source=cb, role=CAN_CORROBORATE,
                                             evidence_origin=THIRD_PARTY_DATABASE),
        ]
        self.verify()
        self.verify()
        for row in kept:
            with self.subTest(source=row.source.source_type):
                self.assertTrue(ObservedDatapoint.objects.filter(pk=row.pk).exists())

    def test_other_documents_are_untouched(self):
        other = DocumentSource.objects.create(filename='o.pdf', source_entity='Other', uploaded_by=self.user,
                                              document_type='pitch_deck', status='analyzed')
        sec, _ = ExternalDataSource.objects.get_or_create(source_type='sec', defaults={'source_name': 'SEC EDGAR'})
        theirs = ObservedDatapoint.objects.create(document=other, category='revenue', observed_value='5',
                                                  observed_value_numeric=5.0, source=sec, role=CAN_ESTABLISH)
        self.verify()
        self.assertTrue(ObservedDatapoint.objects.filter(pk=theirs.pk).exists())
