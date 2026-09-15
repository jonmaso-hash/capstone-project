"""
Entity Integrity: SEC EDGAR and Form D evidence (PR B).

A business's company name is looked up on SEC EDGAR with no form-type filter --
the old Truth Delta resolver searched only annual-report (10-K) filers, so a
private company whose only filing is a Form D was never found. When exactly one
filer has that name (legal suffixes ignored), its company record and newest
Form D add rows in the same claim -> evidence -> result shape:

- SEC filer         -> Matches / Not found / Couldn't check (several filers share
                       the name, or SEC can't be reached)
- incorporation     -> Public record (entity type, jurisdiction, year)
- founder or owner  -> Matches / Not found against the Form D's related persons
- founding year     -> Matches / Doesn't match against the year of incorporation

Street addresses and phone numbers from filings are never shown. Every SEC
request declares Interlink's user agent and requests are spaced out, per SEC's
fair-access policy. Fixtures are trimmed copies of real EDGAR responses for a
Form D-only filer; nothing here reaches the network.
"""
import json
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import requests
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from matchmaking.models import Application, SellerApplication
from matchmaking.tests import _mock_embedding_generation
from zelda_api.vector_models import DocumentSource

User = get_user_model()

CIK = '0002153610'
ACCESSION = '0002153610-26-000001'

SEARCH_ONE_FILER = {
    'hits': {'total': {'value': 1}, 'hits': [{
        '_id': f'{ACCESSION}:primary_doc.xml',
        '_source': {
            'ciks': [CIK], 'display_names': [f'Akil-Abree Consulting, LLC  (CIK {CIK})'],
            'form': 'D', 'root_forms': ['D'], 'file_date': '2026-09-04', 'adsh': ACCESSION, 'inc_states': ['IL'],
        },
    }]},
}

COMPANY_RECORD = {
    'cik': CIK, 'name': 'Akil-Abree Consulting, LLC', 'entityType': 'other',
    'stateOfIncorporation': 'IL', 'stateOfIncorporationDescription': 'IL',
    'addresses': {'business': {'street1': '746 W. SUNSET DRIVE', 'city': 'GLENWOOD', 'stateOrCountry': 'IL', 'zipCode': '60425'}},
    'filings': {'recent': {
        'accessionNumber': [ACCESSION], 'filingDate': ['2026-09-04'], 'form': ['D'],
        'primaryDocument': ['xslFormDX01/primary_doc.xml'],
    }},
}

FORM_D_XML = """<?xml version="1.0"?>
<edgarSubmission>
    <primaryIssuer>
        <cik>0002153610</cik>
        <entityName>Akil-Abree Consulting, LLC</entityName>
        <issuerAddress>
            <street1>746 W. SUNSET DRIVE</street1>
            <city>GLENWOOD</city>
            <stateOrCountry>IL</stateOrCountry>
            <stateOrCountryDescription>ILLINOIS</stateOrCountryDescription>
            <zipCode>60425</zipCode>
        </issuerAddress>
        <issuerPhoneNumber>872-222-6287</issuerPhoneNumber>
        <jurisdictionOfInc>ILLINOIS</jurisdictionOfInc>
        <entityType>Limited Liability Company</entityType>
        <yearOfInc>
            <withinFiveYears>true</withinFiveYears>
            <value>2021</value>
        </yearOfInc>
    </primaryIssuer>
    <relatedPersonsList>
        <relatedPersonInfo>
            <relatedPersonName>
                <firstName>David</firstName>
                <lastName>Lockman</lastName>
            </relatedPersonName>
            <relatedPersonAddress>
                <street1>746 W. Sunset Drive</street1>
                <city>Glenwood</city>
            </relatedPersonAddress>
            <relatedPersonRelationshipList>
                <relationship>Executive Officer</relationship>
            </relatedPersonRelationshipList>
        </relatedPersonInfo>
    </relatedPersonsList>
</edgarSubmission>
"""


# EDGAR company search (output=atom). An exact name returns one top-level
# company-info with the real conformed name; a name several companies share
# returns entries whose names EDGAR renders as "ARRAY(0x...)", so they can't be
# told apart; no match returns an empty feed.
COMPANY_SEARCH_ONE = """<?xml version="1.0" encoding="ISO-8859-1" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
<company-info>
<cik>0002153610</cik>
<conformed-name>Akil-Abree Consulting, LLC</conformed-name>
<state-of-incorporation>IL</state-of-incorporation>
</company-info>
<entry><category term="D" /><content type="text/xml"><accession-number>0002153610-26-000001</accession-number></content></entry>
</feed>
"""
COMPANY_SEARCH_SEVERAL = """<?xml version="1.0" encoding="ISO-8859-1" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>EDGAR Company Search Results</title>
<entry title="ARRAY(0x55abb3cf8d58)"><content type="text/xml"><company-info name="ARRAY(0x55abb3dbdb28)"><cik>0000000001</cik><state>NV</state></company-info></content></entry>
<entry title="ARRAY(0x55abb3cf9058)"><content type="text/xml"><company-info name="ARRAY(0x55abb3d46b10)"><cik>0000000002</cik><state>NM</state></company-info></content></entry>
</feed>
"""
COMPANY_SEARCH_NONE = """<?xml version="1.0" encoding="ISO-8859-1" ?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>EDGAR Company Search Results</title></feed>
"""


class _Response:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload)
        self.content = self.text.encode('iso-8859-1', errors='replace')

    def json(self):
        if self._payload is None:
            raise ValueError('not json')
        return self._payload


class _Sec:
    """Answers SEC requests from fixtures and records what was asked."""

    def __init__(self, search=SEARCH_ONE_FILER, record=COMPANY_RECORD, form_d=FORM_D_XML, fail=None,
                 company_search=COMPANY_SEARCH_ONE):
        self.search, self.record, self.form_d, self.fail = search, record, form_d, fail
        self.company_search = company_search
        self.calls = []

    def __call__(self, url, params=None, headers=None, timeout=None, **kwargs):
        self.calls.append({'url': url, 'params': dict(params or {}), 'headers': dict(headers or {}), 'timeout': timeout})
        if self.fail == 'timeout':
            raise requests.exceptions.Timeout('slow')
        if self.fail == 'error':
            return _Response(503, text='Service Unavailable')
        if 'browse-edgar' in url:
            return _Response(text=self.company_search)
        if 'efts.sec.gov' in url:
            return _Response(payload=self.search)
        if 'data.sec.gov/submissions' in url:
            return _Response(payload=self.record)
        if url.endswith('primary_doc.xml'):
            return _Response(text=self.form_d)
        return _Response(404, text='not found')


def _patched_sec(sec):
    from zelda_api import sec_identity
    return mock.patch.object(sec_identity.requests, 'get', side_effect=sec)


# --------------------------------------------------------------------------
# Looking a company up on EDGAR
# --------------------------------------------------------------------------

class SecLookupTests(SimpleTestCase):

    def _lookup(self, name, sec):
        from zelda_api import sec_identity
        with _patched_sec(sec), mock.patch.object(sec_identity.time, 'sleep'):
            return sec_identity.find_sec_filer(name)

    def test_a_form_d_only_private_company_is_found_without_an_annual_report_filter(self):
        sec = _Sec()
        lookup = self._lookup('Akil-Abree Consulting, LLC', sec)
        self.assertEqual(lookup.status, 'found')
        self.assertEqual(lookup.cik, CIK)
        self.assertIn('browse-edgar', sec.calls[0]['url'])
        for call in sec.calls:
            self.assertNotIn('forms', call['params'])
            self.assertNotIn('type', call['params'])
            self.assertNotIn('10-K', json.dumps(call))

    def test_a_widely_mentioned_public_company_is_found_by_its_exact_company_record(self):
        # Found against live EDGAR: full-text search for "Apple" returned only
        # other companies' filings that mention Apple, and the row said no SEC
        # filer used the name.
        apple = COMPANY_SEARCH_ONE.replace('0002153610', '0000320193').replace('Akil-Abree Consulting, LLC', 'Apple Inc.')
        noisy = {'hits': {'hits': [{'_source': {
            'ciks': ['0001111111'], 'display_names': ['Some Supplier Corp  (CIK 0001111111)'], 'adsh': 'z'}}]}}
        sec = _Sec(search=noisy, company_search=apple)
        lookup = self._lookup('Apple Inc.', sec)
        self.assertEqual(lookup.status, 'found')
        self.assertEqual(lookup.cik, '0000320193')
        self.assertFalse(any('efts.sec.gov' in call['url'] for call in sec.calls))

    def test_a_single_company_search_result_with_a_different_name_is_not_taken(self):
        other = COMPANY_SEARCH_ONE.replace('Akil-Abree Consulting, LLC', 'Akil-Abree Consulting Group Inc')
        sec = _Sec(company_search=other)
        lookup = self._lookup('Akil-Abree Consulting, LLC', sec)
        self.assertEqual(lookup.status, 'found')
        self.assertTrue(any('efts.sec.gov' in call['url'] for call in sec.calls))

    def test_names_match_exactly_with_legal_suffixes_ignored(self):
        search = {'hits': {'hits': [
            {'_source': {'ciks': [CIK], 'display_names': [f'Akil-Abree Consulting, LLC  (CIK {CIK})'], 'adsh': ACCESSION}},
            {'_source': {'ciks': ['0009999999'], 'display_names': ['Akil-Abree Consulting Group Inc  (CIK 0009999999)'], 'adsh': 'x'}},
        ]}}
        lookup = self._lookup('Akil-Abree Consulting Inc.', _Sec(search=search, company_search=COMPANY_SEARCH_SEVERAL))
        self.assertEqual(lookup.status, 'found')
        self.assertEqual(lookup.cik, CIK)

    def test_two_filers_with_the_same_name_are_ambiguous_and_neither_is_chosen(self):
        search = {'hits': {'hits': [
            {'_source': {'ciks': ['0000000001'], 'display_names': ['Harbor Bakery LLC  (CIK 0000000001)'], 'adsh': 'a'}},
            {'_source': {'ciks': ['0000000002'], 'display_names': ['Harbor Bakery, Inc.  (CIK 0000000002)'], 'adsh': 'b'}},
        ]}}
        lookup = self._lookup('Harbor Bakery', _Sec(search=search, company_search=COMPANY_SEARCH_SEVERAL))
        self.assertEqual(lookup.status, 'ambiguous')
        self.assertIsNone(lookup.cik)

    def test_no_filer_with_the_name_is_not_found(self):
        lookup = self._lookup('Nobody Filed Co', _Sec(
            search={'hits': {'total': {'value': 0}, 'hits': []}}, company_search=COMPANY_SEARCH_NONE))
        self.assertEqual(lookup.status, 'not_found')

    def test_sec_errors_and_timeouts_are_reported_as_unavailable(self):
        from zelda_api.sec_identity import SecUnavailable
        for fail in ('error', 'timeout'):
            with self.subTest(fail=fail), self.assertRaises(SecUnavailable):
                self._lookup('Akil-Abree Consulting', _Sec(fail=fail))

    def test_every_request_declares_interlinks_user_agent_and_a_timeout(self):
        from zelda_api import sec_identity
        sec = _Sec()
        with _patched_sec(sec), mock.patch.object(sec_identity.time, 'sleep'):
            filer = sec_identity.find_sec_filer('Akil-Abree Consulting, LLC')
            record = sec_identity.company_record(filer.cik)
            sec_identity.fetch_form_d(filer.cik, sec_identity.latest_form_d(record)['accession'])
        self.assertEqual(len(sec.calls), 3)
        for call in sec.calls:
            self.assertIn('@', call['headers'].get('User-Agent', ''))
            self.assertTrue(call['timeout'])

    def test_requests_are_spaced_out(self):
        from zelda_api import sec_identity
        slept = []
        with _patched_sec(_Sec()), \
                mock.patch.object(sec_identity, '_last_request_at', 0.0), \
                mock.patch.object(sec_identity.time, 'monotonic', return_value=1000.0), \
                mock.patch.object(sec_identity.time, 'sleep', side_effect=slept.append):
            sec_identity.find_sec_filer('Akil-Abree Consulting')
            sec_identity.find_sec_filer('Akil-Abree Consulting')
        self.assertTrue(slept)
        # The wait is computed from float times, so allow rounding error.
        self.assertLessEqual(max(slept), sec_identity.MIN_INTERVAL_SECONDS + 1e-6)


class FormDParsingTests(SimpleTestCase):

    def test_the_issuer_and_the_people_listed_are_read(self):
        from zelda_api.sec_identity import parse_form_d
        form_d = parse_form_d(FORM_D_XML)
        self.assertEqual(form_d.entity_name, 'Akil-Abree Consulting, LLC')
        self.assertEqual(form_d.entity_type, 'Limited Liability Company')
        self.assertEqual(form_d.jurisdiction, 'ILLINOIS')
        self.assertEqual(form_d.year_of_incorporation, 2021)
        self.assertEqual(form_d.people, [('David Lockman', ['Executive Officer'])])

    def test_the_newest_form_d_or_amendment_is_chosen(self):
        from zelda_api.sec_identity import latest_form_d
        record = {'filings': {'recent': {
            'accessionNumber': ['a-10k', 'a-d-old', 'a-d-amend', 'a-8k'],
            'filingDate': ['2026-01-01', '2023-05-01', '2025-02-01', '2026-03-01'],
            'form': ['10-K', 'D', 'D/A', '8-K'],
        }}}
        self.assertEqual(latest_form_d(record), {'accession': 'a-d-amend', 'filing_date': '2025-02-01'})
        self.assertIsNone(latest_form_d({'filings': {'recent': {'accessionNumber': ['x'], 'filingDate': ['2026-01-01'], 'form': ['10-K']}}}))

    def test_a_year_given_only_as_over_five_years_has_no_year(self):
        from zelda_api.sec_identity import parse_form_d
        xml = FORM_D_XML.replace(
            '<withinFiveYears>true</withinFiveYears>\n            <value>2021</value>', '<overFiveYears>true</overFiveYears>')
        form_d = parse_form_d(xml)
        self.assertIsNone(form_d.year_of_incorporation)
        self.assertTrue(form_d.over_five_years)

    def test_external_xml_entities_are_never_expanded(self):
        from zelda_api.sec_identity import SecUnavailable, parse_form_d
        secret = Path(tempfile.mkdtemp()) / 'secret.txt'
        secret.write_text('LOCAL-FILE-CONTENTS-7c1d')
        hostile = FORM_D_XML.replace(
            '<?xml version="1.0"?>',
            f'<?xml version="1.0"?><!DOCTYPE edgarSubmission [<!ENTITY leak SYSTEM "{secret.as_uri()}">]>',
        ).replace('<entityName>Akil-Abree Consulting, LLC</entityName>', '<entityName>&leak;</entityName>')
        try:
            form_d = parse_form_d(hostile)
        except SecUnavailable:
            return
        self.assertNotIn('LOCAL-FILE-CONTENTS', form_d.entity_name or '')


# --------------------------------------------------------------------------
# SEC rows in an Entity Integrity check
# --------------------------------------------------------------------------

class SecFindingsTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('sec_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='Akil-Abree Consulting, LLC', founder_name='David Lockman',
            email='d@t.com', description='test', sector='Consulting', stage='Seed',
            years_in_business=date.today().year - 2021, company_website='',
        )

    def _rows(self, subject=None, sec=None):
        from zelda_api import entity_verification, sec_identity
        with _patched_sec(sec or _Sec()), mock.patch.object(sec_identity.time, 'sleep'), \
                mock.patch.object(entity_verification, 'fetch_public_page') as fetch, \
                mock.patch.object(entity_verification, 'lookup_domain_creation_date', return_value=(None, '')):
            rows = entity_verification.collect_findings(subject or self.founder)
        self.fetch = fetch
        return {row['check']: row for row in rows}

    def test_a_matching_form_d_filer_adds_filer_incorporation_person_and_founding_rows(self):
        rows = self._rows()
        self.assertEqual(rows['sec_filer']['result'], 'matches')
        self.assertIn(CIK, rows['sec_filer']['evidence'])
        self.assertIn('sec.gov', rows['sec_filer']['source_url'])
        self.assertEqual(rows['sec_incorporation']['result'], 'public_record')
        self.assertIn('Illinois', rows['sec_incorporation']['evidence'])
        self.assertIn('2021', rows['sec_incorporation']['evidence'])
        self.assertIn(ACCESSION.replace('-', ''), rows['sec_incorporation']['source_url'])
        self.assertEqual(rows['sec_person']['result'], 'matches')
        self.assertIn('Executive Officer', rows['sec_person']['evidence'])
        self.assertEqual(rows['sec_founding_year']['result'], 'matches')

    def test_the_website_rows_are_still_there_alongside_the_sec_rows(self):
        rows = self._rows()
        self.assertEqual(rows['website']['result'], 'not_applicable')
        self.assertIn('sec_filer', rows)

    def test_a_founder_not_listed_on_the_form_d_is_not_found_and_the_listed_people_are_named(self):
        self.founder.founder_name = 'Jane Rivera'
        self.founder.save()
        rows = self._rows()
        self.assertEqual(rows['sec_person']['result'], 'not_found')
        self.assertIn('David Lockman', rows['sec_person']['evidence'])

    def test_an_incorporation_year_years_apart_from_the_claimed_founding_doesnt_match(self):
        self.founder.years_in_business = 1
        self.founder.save()
        rows = self._rows()
        self.assertEqual(rows['sec_founding_year']['result'], 'doesnt_match')
        self.assertIn('2021', rows['sec_founding_year']['evidence'])

    def test_no_sec_filer_is_not_found_and_adds_no_other_sec_rows(self):
        rows = self._rows(sec=_Sec(search={'hits': {'hits': []}}, company_search=COMPANY_SEARCH_NONE))
        self.assertEqual(rows['sec_filer']['result'], 'not_found')
        # EDGAR search has limits; the row says what wasn't found, not that no filer exists.
        self.assertNotIn('uses this name', rows['sec_filer']['evidence'])
        for check in ('sec_incorporation', 'sec_person', 'sec_founding_year'):
            self.assertNotIn(check, rows)

    def test_a_shared_name_couldnt_be_checked(self):
        search = {'hits': {'hits': [
            {'_source': {'ciks': ['0000000001'], 'display_names': ['Akil-Abree Consulting LLC  (CIK 0000000001)'], 'adsh': 'a'}},
            {'_source': {'ciks': ['0000000002'], 'display_names': ['Akil-Abree Consulting, Inc.  (CIK 0000000002)'], 'adsh': 'b'}},
        ]}}
        rows = self._rows(sec=_Sec(search=search, company_search=COMPANY_SEARCH_SEVERAL))
        self.assertEqual(rows['sec_filer']['result'], 'couldnt_check')
        self.assertNotIn('sec_person', rows)

    def test_sec_being_unreachable_couldnt_be_checked(self):
        rows = self._rows(sec=_Sec(fail='timeout'))
        self.assertEqual(rows['sec_filer']['result'], 'couldnt_check')
        self.assertNotIn('slow', rows['sec_filer']['evidence'])

    def test_a_filer_without_a_form_d_still_shows_its_state_of_incorporation(self):
        record = dict(COMPANY_RECORD, filings={'recent': {'accessionNumber': ['x'], 'filingDate': ['2026-01-01'], 'form': ['10-K']}})
        rows = self._rows(sec=_Sec(record=record))
        self.assertEqual(rows['sec_filer']['result'], 'matches')
        self.assertEqual(rows['sec_incorporation']['result'], 'public_record')
        self.assertIn('IL', rows['sec_incorporation']['evidence'])
        self.assertEqual(rows['sec_person']['result'], 'not_applicable')
        self.assertNotIn('sec_founding_year', rows)

    def test_addresses_and_phone_numbers_from_filings_are_never_shown(self):
        everything = json.dumps(list(self._rows().values()))
        for private in ('746', 'SUNSET', 'Sunset', '872-222', '60425'):
            self.assertNotIn(private, everything)

    def test_the_sec_rows_never_say_verified_or_score_anything(self):
        everything = json.dumps(list(self._rows().values())).lower()
        self.assertNotIn('verified', everything)
        self.assertNotIn('score', everything)

    def test_a_business_for_sale_gets_the_same_sec_rows(self):
        seller_user = User.objects.create_user('sec_seller', password='x')
        seller = SellerApplication.objects.create(
            user=seller_user, company_name='Akil-Abree Consulting LLC', seller_name='David Lockman', email='s@t.com',
            description='test', industry='Consulting', years_in_business=0, company_website='',
        )
        rows = self._rows(subject=seller)
        self.assertEqual(rows['sec_filer']['result'], 'matches')
        self.assertEqual(rows['sec_person']['result'], 'matches')
        self.assertNotIn('sec_founding_year', rows)

    def test_the_truth_delta_page_links_to_the_sec_filing(self):
        from zelda_api.entity_verification import inputs_hash
        from zelda_api.entity_verification_models import EntityVerificationReport
        rows = list(self._rows().values())
        EntityVerificationReport.objects.create(
            founder_profile=self.founder, status='complete', checked_at=timezone.now(),
            inputs_hash=inputs_hash(self.founder), findings=rows,
        )
        deck = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='Akil-Abree', document_type='pitch_deck')
        self.client.force_login(self.founder_user)
        html = self.client.get(reverse('zelda_api:truth_delta_ui', args=[deck.id])).content.decode()
        section = html[html.find('data-section="entity-integrity"'):html.find('<!-- /entity-integrity -->')]
        self.assertIn('Public record', section)
        self.assertIn('https://www.sec.gov/', section)
        self.assertNotIn('872-222', section)
