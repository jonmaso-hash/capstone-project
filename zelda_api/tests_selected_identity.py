"""
A selected SEC registrant is the identity decision; nothing downstream re-decides it.

External company search lets a user pick one issuer from the SEC's own index,
and the document stores that CIK. Before this, both evidence consumers ignored
it and searched the document's name again: Truth Delta through
resolve_company_identity, the identity report through find_sec_filer. A name
search can only re-decide an identity the user already made -- returning
ambiguous for a registrant named exactly, or a different registrant sharing
the name -- and then present findings about it under the user's selection.

So the tests below forbid the name resolver outright whenever a selection is
present (it raises if called), and prove the negative the principle needs:
when the selected record cannot be read, the consumer reports an unreachable
source and produces nothing, never a name-search answer of its own. Positive
controls show the name path still runs for documents without a selection.
"""
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from . import sec_identity
from .sec_company_identity import FOUND, identity_from_selected_record, resolve_selected_identity
from .truth_delta_sources import DataSourceManager, SECFilingsIntegration

SELECTED_CIK = '0000829224'

# Deliberately shares nothing with the document's name ("Harbor Brand"), so
# any name matching on the selected path would reject it.
SELECTED_RECORD = {
    'cik': SELECTED_CIK.lstrip('0'), 'name': 'HARBOR HOLDINGS GROUP INC', 'tickers': ['HBG'],
    'formerNames': [], 'stateOfIncorporation': 'DE',
    'filings': {'recent': {
        'form': ['10-K', '10-Q'], 'filingDate': ['2026-03-01', '2026-08-01'], 'accessionNumber': ['a', 'b'],
    }},
}

NAME_SEARCH_FORBIDDEN = mock.patch(
    'zelda_api.sec_company_identity.resolve_company_identity',
    side_effect=AssertionError('a selected registrant must not be re-resolved by name'),
)


class SelectedIdentityTests(SimpleTestCase):

    def setUp(self):
        cache.clear()

    def test_selected_record_becomes_a_found_identity_without_name_matching(self):
        identity = identity_from_selected_record(SELECTED_CIK, SELECTED_RECORD)
        self.assertEqual(identity.status, FOUND)
        self.assertEqual(identity.cik, SELECTED_CIK)
        self.assertEqual(identity.name, 'HARBOR HOLDINGS GROUP INC')
        self.assertEqual(identity.matched_on, 'selected')
        self.assertTrue(identity.files_periodically)
        self.assertTrue(identity.can_establish_revenue)

    def test_a_record_for_another_cik_is_a_failed_attempt_not_evidence(self):
        with self.assertRaises(sec_identity.SecUnavailable):
            identity_from_selected_record('0000887557', SELECTED_RECORD)
        with self.assertRaises(ValueError):
            identity_from_selected_record('not-a-cik', SELECTED_RECORD)

    def test_truth_delta_uses_the_selected_registrant(self):
        with NAME_SEARCH_FORBIDDEN, mock.patch.object(sec_identity, 'company_record', return_value=SELECTED_RECORD):
            cik, reason = SECFilingsIntegration().resolve_with_diagnostics('Harbor Brand', selected_cik=SELECTED_CIK)
        self.assertEqual((cik, reason), (SELECTED_CIK, None))

    def test_unreadable_selection_is_unavailable_and_never_falls_back_to_the_name(self):
        unreachable = sec_identity.SecUnavailable(sec_identity.UNREACHABLE, reason='timeout')
        with NAME_SEARCH_FORBIDDEN, mock.patch.object(sec_identity, 'company_record', side_effect=unreachable):
            cik, reason = SECFilingsIntegration().resolve_with_diagnostics('Harbor Brand', selected_cik=SELECTED_CIK)
        self.assertEqual((cik, reason), (None, 'timeout'))

    def test_without_a_selection_the_name_resolver_still_decides(self):
        from .sec_company_identity import AMBIGUOUS, CompanyIdentity
        with mock.patch('zelda_api.sec_company_identity.resolve_company_identity',
                        return_value=CompanyIdentity(status=AMBIGUOUS)) as by_name:
            cik, reason = SECFilingsIntegration().resolve_with_diagnostics('Harbor Brand')
        by_name.assert_called_once_with('Harbor Brand')
        self.assertEqual((cik, reason), (None, 'ambiguous'))

    def test_settled_selected_identity_is_cached_per_cik(self):
        with mock.patch.object(sec_identity, 'company_record', return_value=SELECTED_RECORD) as fetch:
            resolve_selected_identity(SELECTED_CIK)
            resolve_selected_identity(SELECTED_CIK)
        fetch.assert_called_once()

    def test_document_selection_reaches_only_the_sec_integration(self):
        calls = {}

        def fake(source_type):
            def fetch(company_name, domain=None, **kwargs):
                calls[source_type] = kwargs
                return {}
            return SimpleNamespace(source_type=source_type, source_name=source_type,
                                   last_failure_reason=None, fetch_company_data=fetch)

        with mock.patch.object(DataSourceManager, 'get_all_active', return_value=[fake('sec'), fake('news')]):
            DataSourceManager.create_observed_datapoints(
                SimpleNamespace(external_cik=SELECTED_CIK), 'Harbor Brand')
            self.assertEqual(calls, {'sec': {'selected_cik': SELECTED_CIK}, 'news': {}})
            calls.clear()
            DataSourceManager.create_observed_datapoints(SimpleNamespace(external_cik=''), 'Harbor Brand')
            self.assertEqual(calls, {'sec': {}, 'news': {}})  # positive control: no selection, old call


class SelectedIdentityReportTests(TestCase):

    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('selected_identity_owner', password='x')

    def document(self, external_cik):
        from .vector_models import DocumentSource
        return DocumentSource.objects.create(
            uploaded_by=self.user, filename='SEC registration snapshot.txt', source_entity='Harbor Brand',
            document_type='research_report', is_external_subject=True, external_cik=external_cik,
        )

    def filer_row(self, report):
        return next(row for row in report.findings if row['check'] == 'sec_filer')

    def test_identity_report_describes_the_selected_registrant(self):
        from .entity_verification import build_document_identity_report
        from .entity_verification_models import EntityVerificationReport as R
        unavailable = sec_identity.SecUnavailable(sec_identity.UNREACHABLE)
        with NAME_SEARCH_FORBIDDEN, \
                mock.patch.object(sec_identity, 'company_record', return_value=SELECTED_RECORD), \
                mock.patch.object(sec_identity, 'company_facts', side_effect=unavailable):
            report = build_document_identity_report(self.document(SELECTED_CIK))
        self.assertEqual(report.status, R.COMPLETE)
        row = self.filer_row(report)
        self.assertEqual(row['result'], R.MATCHES)
        self.assertIn(f'CIK {SELECTED_CIK}', row['evidence'])
        self.assertIn('HARBOR HOLDINGS GROUP INC', row['evidence'])

    def test_unreadable_selection_cannot_check_and_never_searches_the_name(self):
        from .entity_verification import build_document_identity_report
        from .entity_verification_models import EntityVerificationReport as R
        unavailable = sec_identity.SecUnavailable(sec_identity.UNREACHABLE)
        with NAME_SEARCH_FORBIDDEN, mock.patch.object(sec_identity, 'company_record', side_effect=unavailable):
            report = build_document_identity_report(self.document(SELECTED_CIK))
        row = self.filer_row(report)
        self.assertEqual(row['result'], R.COULDNT_CHECK)
        self.assertNotIn('CIK', row['evidence'])

    def test_document_without_a_selection_still_resolves_by_name(self):
        from .entity_verification import build_document_identity_report
        from .entity_verification_models import EntityVerificationReport as R
        from .sec_company_identity import NOT_FOUND, CompanyIdentity
        with mock.patch('zelda_api.sec_company_identity.resolve_company_identity',
                        return_value=CompanyIdentity(status=NOT_FOUND)) as by_name:
            report = build_document_identity_report(self.document(''))
        by_name.assert_called_once_with('Harbor Brand')
        self.assertEqual(self.filer_row(report)['result'], R.NOT_FOUND)
