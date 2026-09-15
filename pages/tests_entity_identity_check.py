"""
Entity Integrity foundation (PR A).

Zelda compares what an Interlink business profile says about itself -- company
name, website, founder or seller name, years in business -- with what public
sources show, and records each comparison as a row:

    claim -> Interlink source -> external evidence -> result -> checked date

Results are Matches, Doesn't match, Not found, Not applicable, Couldn't check
and Public record. Nothing says "Verified" and nothing is scored.

- The subject is the business (a startup Application or a SellerApplication),
  never the founder's user account.
- Websites are fetched through zelda_api/safe_fetch.py, which refuses internal
  addresses before sending anything and connects to the address it checked.
- One external check per business per 7 days; later requests reuse it.
- Access is per report: the owner and staff always, anyone else only with a
  grant for that exact report. The founder's Premium plays no part.

Every external call is mocked. SEC and Form D evidence are PR B.
"""
import json
import socket
import tempfile
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from matchmaking.models import Application, BuyerApplication, InvestorApplication, SellerApplication
from matchmaking.tests import _mock_embedding_generation
from zelda_api.vector_models import DocumentSource

User = get_user_model()

PUBLIC_IP = '93.184.216.34'
HTML = {'Content-Type': 'text/html; charset=utf-8'}
MATCHING_PAGE = (
    '<html><head><title>Acme Robotics</title></head>'
    '<body><p>Founded by Jane Rivera. We build warehouse robots.</p></body></html>'
)


# --------------------------------------------------------------------------
# Safe outbound fetching
# --------------------------------------------------------------------------

def _addrinfo(ips):
    return [
        (socket.AF_INET6 if ':' in ip else socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 443))
        for ip in ips
    ]


class SafeFetchTests(SimpleTestCase):

    def _fetch(self, url, dns=None, responses=None):
        """dns: {host: [ips]}; responses: [(status, headers, [chunks])] served in order."""
        from zelda_api import safe_fetch

        dns = dns or {'example.com': [PUBLIC_IP]}
        responses = list(responses or [(200, HTML, [MATCHING_PAGE.encode()])])
        sent = []

        def fake_getaddrinfo(host, *args, **kwargs):
            return _addrinfo(dns.get(host, [PUBLIC_IP]))

        def fake_send(ip, url, host):
            sent.append({'ip': ip, 'url': url, 'host': host})
            return responses.pop(0)

        with mock.patch.object(safe_fetch.socket, 'getaddrinfo', side_effect=fake_getaddrinfo) as lookup, \
                mock.patch.object(safe_fetch, '_send', side_effect=fake_send):
            try:
                return safe_fetch.fetch_public_page(url), None, sent, lookup
            except safe_fetch.FetchError as error:
                return None, error, sent, lookup

    def test_a_public_page_is_fetched_through_the_address_that_was_checked(self):
        result, error, sent, _ = self._fetch('https://example.com/')
        self.assertIsNone(error)
        self.assertIn('Acme Robotics', result.text)
        self.assertEqual(sent[0]['ip'], PUBLIC_IP)
        self.assertEqual(sent[0]['host'], 'example.com')

    def test_unsupported_schemes_are_refused_before_any_lookup(self):
        for url in ('ftp://example.com/', 'file:///etc/passwd', 'javascript:alert(1)', 'gopher://example.com/'):
            with self.subTest(url=url):
                result, error, sent, lookup = self._fetch(url)
                self.assertIsNotNone(error)
                self.assertEqual(sent, [])
                lookup.assert_not_called()

    def test_non_standard_ports_are_refused(self):
        result, error, sent, _ = self._fetch('http://example.com:8080/')
        self.assertIsNotNone(error)
        self.assertEqual(sent, [])

    def test_internal_addresses_are_refused_before_any_request(self):
        from zelda_api.safe_fetch import UnsafeAddress
        for ip in ('127.0.0.1', '10.0.0.5', '172.16.0.1', '192.168.1.1', '169.254.169.254',
                   '0.0.0.0', '100.64.0.1', '::1', 'fc00::1', 'fe80::1'):
            with self.subTest(ip=ip):
                result, error, sent, _ = self._fetch('https://example.com/', dns={'example.com': [ip]})
                self.assertIsInstance(error, UnsafeAddress)
                self.assertEqual(sent, [])
                self.assertNotIn(ip, error.reason)

    def test_a_host_with_any_internal_address_is_refused(self):
        result, error, sent, _ = self._fetch('https://example.com/', dns={'example.com': [PUBLIC_IP, '10.0.0.5']})
        self.assertIsNotNone(error)
        self.assertEqual(sent, [])

    def test_literal_internal_addresses_are_refused_whatever_dns_says(self):
        for url in ('http://127.0.0.1/', 'http://[::1]/', 'http://169.254.169.254/latest/meta-data/', 'http://localhost/'):
            with self.subTest(url=url):
                result, error, sent, _ = self._fetch(url, dns={'localhost': ['127.0.0.1']})
                self.assertIsNotNone(error)
                self.assertEqual(sent, [])

    def test_every_redirect_is_checked_again(self):
        result, error, sent, _ = self._fetch(
            'https://example.com/',
            dns={'example.com': [PUBLIC_IP], 'internal.example.com': ['10.0.0.5']},
            responses=[(302, {'Location': 'http://internal.example.com/admin'}, [])],
        )
        self.assertIsNotNone(error)
        self.assertEqual(len(sent), 1)

    def test_a_redirect_to_another_public_page_is_followed(self):
        result, error, sent, _ = self._fetch(
            'http://example.com/',
            responses=[(301, {'Location': 'https://www.example.com/home'}, []), (200, HTML, [MATCHING_PAGE.encode()])],
        )
        self.assertIsNone(error)
        self.assertEqual(result.final_url, 'https://www.example.com/home')
        self.assertEqual([s['host'] for s in sent], ['example.com', 'www.example.com'])

    def test_redirect_loops_stop(self):
        loop = [(302, {'Location': 'https://example.com/'}, [])] * 10
        result, error, sent, _ = self._fetch('https://example.com/', responses=loop)
        self.assertIsNotNone(error)
        self.assertLessEqual(len(sent), 4)

    def test_only_web_pages_are_accepted(self):
        result, error, _, _ = self._fetch(
            'https://example.com/', responses=[(200, {'Content-Type': 'application/pdf'}, [b'%PDF-1.4'])])
        self.assertIsNotNone(error)

    def test_the_body_is_capped(self):
        from zelda_api.safe_fetch import MAX_BYTES
        chunks = [b'<p>' + b'a' * (400 * 1024) + b'</p>'] * 10
        result, error, _, _ = self._fetch('https://example.com/', responses=[(200, HTML, chunks)])
        self.assertIsNone(error)
        self.assertLessEqual(len(result.text.encode('utf-8')), MAX_BYTES)


class DomainHelperTests(SimpleTestCase):

    def test_ip_addresses_and_localhost_are_not_treated_as_company_domains(self):
        from zelda_api.entity_verification import extract_domain
        for value in ('http://127.0.0.1/', 'http://[::1]:8000/', 'localhost', 'http://10.0.0.5', '192.168.1.1'):
            with self.subTest(value=value):
                self.assertIsNone(extract_domain(value))
        self.assertEqual(extract_domain('https://www.acmerobotics.com/about'), 'acmerobotics.com')


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------

class _Businesses(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('ei_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='Acme Robotics, Inc.', founder_name='Jane Rivera', email='j@t.com',
            description='test', sector='Robotics', stage='Seed', years_in_business=3,
            company_website='https://acmerobotics.com',
        )

    def _collect(self, subject=None, page=MATCHING_PAGE, fetch_error=None, domain_date=None, whois_error=''):
        from zelda_api import entity_verification
        from zelda_api.safe_fetch import FetchError, FetchResult

        fetch = mock.Mock()
        if fetch_error:
            fetch.side_effect = FetchError(fetch_error)
        else:
            fetch.return_value = FetchResult(final_url='https://acmerobotics.com/', status=200, text=page)
        whois = mock.Mock(return_value=(domain_date, whois_error))
        with mock.patch.object(entity_verification, 'fetch_public_page', fetch), \
                mock.patch.object(entity_verification, 'lookup_domain_creation_date', whois):
            rows = entity_verification.collect_findings(subject or self.founder)
        self.fetch, self.whois = fetch, whois
        return {row['check']: row for row in rows}


class FindingsTests(_Businesses):

    def test_a_site_naming_the_company_and_the_founder_matches(self):
        rows = self._collect()
        self.assertEqual(rows['website']['result'], 'matches')
        self.assertEqual(rows['company_name']['result'], 'matches')
        self.assertEqual(rows['person_name']['result'], 'matches')

    def test_names_missing_from_the_site_are_not_found_rather_than_mismatched(self):
        rows = self._collect(page='<html><title>Welcome</title><body>Our homepage.</body></html>')
        self.assertEqual(rows['company_name']['result'], 'not_found')
        self.assertEqual(rows['person_name']['result'], 'not_found')

    def test_without_a_website_the_website_checks_are_not_applicable(self):
        self.founder.company_website = ''
        self.founder.save()
        rows = self._collect()
        for check in ('website', 'company_name', 'person_name', 'founding_year'):
            with self.subTest(check=check):
                self.assertEqual(rows[check]['result'], 'not_applicable')
        self.fetch.assert_not_called()
        self.whois.assert_not_called()

    def test_a_site_that_cannot_be_fetched_couldnt_be_checked(self):
        rows = self._collect(fetch_error="That website address isn't a public web address.")
        for check in ('website', 'company_name', 'person_name'):
            with self.subTest(check=check):
                self.assertEqual(rows[check]['result'], 'couldnt_check')

    def test_a_domain_registered_years_after_the_claimed_founding_doesnt_match(self):
        claimed = date.today().year - 3
        rows = self._collect(domain_date=date(claimed + 2, 5, 1))
        self.assertEqual(rows['founding_year']['result'], 'doesnt_match')

    def test_a_domain_consistent_with_the_claimed_founding_matches(self):
        claimed = date.today().year - 3
        rows = self._collect(domain_date=date(claimed - 1, 5, 1))
        self.assertEqual(rows['founding_year']['result'], 'matches')

    def test_a_domain_registered_years_before_the_claimed_founding_is_reported_not_matched(self):
        # Found in the browser walk: a 1995 domain against a 2021 founding read
        # "in line with the claimed founding year" and Matches.
        claimed = date.today().year - 3
        rows = self._collect(domain_date=date(claimed - 10, 5, 1))
        self.assertEqual(rows['founding_year']['result'], 'public_record')
        self.assertIn('10 years before', rows['founding_year']['evidence'])
        self.assertNotIn('in line with', rows['founding_year']['evidence'])

    def test_a_domain_date_without_a_founding_claim_is_a_public_record(self):
        self.founder.years_in_business = 0
        self.founder.save()
        rows = self._collect(domain_date=date(2019, 5, 1))
        self.assertEqual(rows['founding_year']['result'], 'public_record')
        self.assertIn('2019', rows['founding_year']['evidence'])

    def test_a_failed_domain_lookup_couldnt_be_checked(self):
        rows = self._collect(domain_date=None, whois_error='Domain lookup unavailable right now.')
        self.assertEqual(rows['founding_year']['result'], 'couldnt_check')

    def test_every_row_carries_claim_source_evidence_result_and_date(self):
        rows = self._collect(domain_date=date(2021, 1, 1))
        for check, row in rows.items():
            with self.subTest(check=check):
                for key in ('claim', 'interlink_source', 'evidence_source', 'evidence', 'result', 'checked_at'):
                    self.assertIn(key, row)
                self.assertIn(row['result'], {
                    'matches', 'doesnt_match', 'not_found', 'not_applicable', 'couldnt_check', 'public_record'})

    def test_a_business_for_sale_is_checked_with_the_sellers_name(self):
        seller_user = User.objects.create_user('ei_seller', password='x')
        seller = SellerApplication.objects.create(
            user=seller_user, company_name='Harbor Bakery LLC', seller_name='Sam Lee', email='s@t.com',
            description='test', industry='Food', years_in_business=10, company_website='https://harborbakery.com',
        )
        rows = self._collect(subject=seller, page='<title>Harbor Bakery</title><p>Owned by Sam Lee.</p>')
        self.assertEqual(rows['company_name']['result'], 'matches')
        self.assertEqual(rows['person_name']['result'], 'matches')


class SubjectTests(_Businesses):

    def test_a_report_belongs_to_exactly_one_business(self):
        from zelda_api.entity_verification_models import EntityVerificationReport
        seller_user = User.objects.create_user('ei_both', password='x')
        seller = SellerApplication.objects.create(
            user=seller_user, company_name='S', seller_name='S', email='s@t.com', description='d', industry='Food')
        with self.assertRaises(IntegrityError), transaction.atomic():
            EntityVerificationReport.objects.create(founder_profile=self.founder, seller_profile=seller)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EntityVerificationReport.objects.create()

    def test_the_subject_accessor_returns_the_business(self):
        from zelda_api.entity_verification_models import EntityVerificationReport
        seller_user = User.objects.create_user('ei_subject_seller', password='x')
        seller = SellerApplication.objects.create(
            user=seller_user, company_name='S', seller_name='S', email='s@t.com', description='d', industry='Food')
        self.assertEqual(EntityVerificationReport.objects.create(founder_profile=self.founder).subject, self.founder)
        self.assertEqual(EntityVerificationReport.objects.create(seller_profile=seller).subject, seller)


# --------------------------------------------------------------------------
# Requesting, reuse and report-specific access
# --------------------------------------------------------------------------

class _Requests(_Businesses):

    def setUp(self):
        super().setUp()
        self.investor_user = User.objects.create_user('ei_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com', company_name='Harbor Capital',
            investment_focus='Robotics', investment_stage='Seed',
        )
        self.second_investor = User.objects.create_user('ei_investor_two', password='x')
        InvestorApplication.objects.create(
            user=self.second_investor, full_name='I2', email='i2@t.com', company_name='North Capital',
            investment_focus='Robotics', investment_stage='Seed',
        )
        self.deck = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='Acme Robotics', document_type='pitch_deck',
        )

    def _external(self):
        """Patches the website fetch and WHOIS, and runs queued checks immediately."""
        from zelda_api import entity_verification, entity_verification_tasks
        from zelda_api.safe_fetch import FetchResult

        self.fetch = mock.Mock(return_value=FetchResult(
            final_url='https://acmerobotics.com/', status=200, text=MATCHING_PAGE))
        self.whois = mock.Mock(return_value=(date(2020, 1, 1), ''))
        patches = [
            mock.patch.object(entity_verification, 'fetch_public_page', self.fetch),
            mock.patch.object(entity_verification, 'lookup_domain_creation_date', self.whois),
            mock.patch.object(entity_verification_tasks.run_entity_check, 'delay',
                              side_effect=lambda report_id: entity_verification_tasks.run_entity_check.run(report_id)),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def _request(self, user, profile=None):
        self.client.force_login(user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse('zelda_api:identity_check_request', args=[(profile or self.founder).id]),
                HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def _finding(self, **overrides):
        finding = {
            'check': 'company_name', 'claim': 'Company name: Acme Robotics, Inc.',
            'interlink_source': 'Startup profile', 'evidence_source': 'Company website',
            'evidence': 'Named on acmerobotics.com', 'result': 'matches', 'source_url': 'https://acmerobotics.com/',
            'checked_at': timezone.now().isoformat(),
        }
        finding.update(overrides)
        return finding

    def _report(self, **fields):
        from zelda_api.entity_verification import inputs_hash
        from zelda_api.entity_verification_models import EntityVerificationReport
        defaults = {
            'founder_profile': self.founder, 'status': 'complete', 'checked_at': timezone.now(),
            'inputs_hash': inputs_hash(self.founder), 'findings': [self._finding()],
        }
        defaults.update(fields)
        return EntityVerificationReport.objects.create(**defaults)

    def _page(self, user):
        self.client.force_login(user)
        html = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.deck.id])).content.decode()
        start = html.find('data-section="entity-integrity"')
        return html[start:html.find('<!-- /entity-integrity -->', start)] if start != -1 else ''


class RequestAndReuseTests(_Requests):

    def setUp(self):
        super().setUp()
        self._external()

    def test_an_investor_request_runs_one_check_and_grants_that_report(self):
        from zelda_api.entity_verification_models import EntityReportAccessGrant, EntityVerificationReport
        response = self._request(self.investor_user)
        self.assertIn(response.status_code, (200, 202))
        report = EntityVerificationReport.objects.get(founder_profile=self.founder)
        self.assertEqual(response.json()['report_id'], report.id)
        self.assertEqual(report.status, 'complete')
        self.assertIsNotNone(report.checked_at)
        self.assertTrue(report.findings)
        self.assertTrue(EntityReportAccessGrant.objects.filter(report=report, user=self.investor_user).exists())
        self.assertEqual(self.fetch.call_count, 1)

    def test_a_second_request_within_seven_days_reuses_the_check_and_grants_the_same_report(self):
        from zelda_api.entity_verification_models import EntityReportAccessGrant, EntityVerificationReport
        first = self._request(self.investor_user).json()['report_id']
        second = self._request(self.second_investor).json()['report_id']
        self.assertEqual(first, second)
        self.assertEqual(EntityVerificationReport.objects.filter(founder_profile=self.founder).count(), 1)
        self.assertEqual(self.fetch.call_count, 1)
        self.assertEqual(EntityReportAccessGrant.objects.filter(report_id=first).count(), 2)

    def test_a_check_still_running_is_shared_rather_than_started_twice(self):
        from zelda_api.entity_verification_models import EntityVerificationReport
        pending = self._report(status='pending', checked_at=None, findings=[])
        response = self._request(self.investor_user)
        self.assertEqual(response.json()['report_id'], pending.id)
        self.assertEqual(EntityVerificationReport.objects.filter(founder_profile=self.founder).count(), 1)
        self.fetch.assert_not_called()

    def test_a_request_after_seven_days_runs_a_new_check(self):
        from zelda_api.entity_verification import REUSE_WINDOW
        first = self._request(self.investor_user).json()['report_id']
        from zelda_api.entity_verification_models import EntityVerificationReport
        EntityVerificationReport.objects.filter(id=first).update(
            checked_at=timezone.now() - REUSE_WINDOW - timedelta(hours=1))
        second = self._request(self.second_investor).json()['report_id']
        self.assertNotEqual(first, second)
        self.assertEqual(self.fetch.call_count, 2)

    def test_changing_the_profile_identity_forces_a_new_check(self):
        first = self._request(self.investor_user).json()['report_id']
        self.founder.company_website = 'https://acme-robotics.io'
        self.founder.save()
        second = self._request(self.second_investor).json()['report_id']
        self.assertNotEqual(first, second)

    def test_investors_buyers_and_staff_can_request_and_others_cannot(self):
        buyer = User.objects.create_user('ei_buyer', password='x')
        BuyerApplication.objects.create(
            user=buyer, full_name='B', email='b@t.com', company_name='Buyer Co', acquisition_thesis='Robotics')
        staff = User.objects.create_user('ei_staff', password='x', is_staff=True)
        roleless = User.objects.create_user('ei_roleless', password='x')
        self.assertIn(self._request(buyer).status_code, (200, 202))
        self.assertIn(self._request(staff).status_code, (200, 202))
        self.assertEqual(self._request(roleless).status_code, 403)

    def test_a_hidden_business_answers_like_a_missing_one(self):
        self.founder.is_private = True
        self.founder.save()
        self.assertEqual(self._request(self.investor_user).status_code, 404)
        self.client.force_login(self.investor_user)
        missing = self.client.post(reverse('zelda_api:identity_check_request', args=[999999]))
        self.assertEqual(missing.status_code, 404)

    def test_requesting_only_accepts_post(self):
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('zelda_api:identity_check_request', args=[self.founder.id]))
        self.assertEqual(response.status_code, 405)


class AccessAndDisplayTests(_Requests):

    def test_the_owner_sees_the_rows_without_premium(self):
        self.assertFalse(self.founder.is_premium)
        self._report()
        section = self._page(self.founder_user)
        self.assertIn('Entity Integrity', section)
        self.assertIn('Matches', section)
        self.assertIn('Checked', section)
        self.assertIn('https://acmerobotics.com/', section)

    def test_a_granted_investor_sees_the_rows_and_an_ungranted_one_only_the_button(self):
        from zelda_api.entity_verification_models import EntityReportAccessGrant
        report = self._report()
        EntityReportAccessGrant.objects.create(report=report, user=self.investor_user)
        self.assertIn('Named on acmerobotics.com', self._page(self.investor_user))
        other = self._page(self.second_investor)
        self.assertNotIn('Named on acmerobotics.com', other)
        self.assertIn('Check company identity', other)

    def test_grants_are_for_one_report_not_the_whole_company(self):
        from zelda_api.entity_verification_models import EntityReportAccessGrant
        older = self._report(checked_at=timezone.now() - timedelta(days=10),
                             findings=[self._finding(evidence='first-check-marker')])
        newer = self._report(findings=[self._finding(evidence='second-check-marker')])
        EntityReportAccessGrant.objects.create(report=older, user=self.investor_user)
        EntityReportAccessGrant.objects.create(report=newer, user=self.second_investor)
        section = self._page(self.investor_user)
        self.assertIn('first-check-marker', section)
        self.assertNotIn('second-check-marker', section)

    def test_staff_see_the_rows(self):
        staff = User.objects.create_user('ei_staff_viewer', password='x', is_staff=True)
        self._report()
        self.assertIn('Named on acmerobotics.com', self._page(staff))

    def test_a_signed_in_user_without_a_role_sees_neither_rows_nor_the_button(self):
        roleless = User.objects.create_user('ei_roleless_viewer', password='x')
        self._report()
        section = self._page(roleless)
        self.assertNotIn('Named on acmerobotics.com', section)
        self.assertNotIn('Check company identity', section)

    def test_the_section_never_says_verified_and_shows_no_score(self):
        self._report()
        section = self._page(self.founder_user).lower()
        self.assertTrue(section)
        self.assertNotIn('verified', section)
        self.assertNotIn('score', section)

    def test_a_check_in_progress_says_so(self):
        self._report(status='pending', checked_at=None, findings=[])
        self.assertIn('Checking public sources', self._page(self.founder_user))

    def test_the_status_endpoint_follows_the_same_access_rule(self):
        from zelda_api.entity_verification_models import EntityReportAccessGrant
        report = self._report()
        url = reverse('zelda_api:identity_check_status', args=[report.id])
        self.client.force_login(self.second_investor)
        self.assertEqual(self.client.get(url).status_code, 404)
        EntityReportAccessGrant.objects.create(report=report, user=self.second_investor)
        self.assertEqual(self.client.get(url).json()['status'], 'complete')


class TriggerTests(_Requests):

    def setUp(self):
        super().setUp()
        self._external()

    def test_the_owners_verify_button_produces_a_business_report(self):
        from zelda_api.entity_verification_models import EntityVerificationReport
        from zelda_api.entity_verification_tasks import verify_entity_integrity
        result = verify_entity_integrity(self.deck.id)
        self.assertEqual(result['status'], 'success')
        report = EntityVerificationReport.objects.get(id=result['report_id'])
        self.assertEqual(report.subject, self.founder)
        self.assertEqual(report.document, self.deck)
        self.assertEqual(report.status, 'complete')
        self.assertTrue(report.findings)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_an_investor_confirming_an_analysis_is_granted_the_identity_check(self):
        from zelda_api.entity_verification_models import EntityReportAccessGrant
        self.deck.delete()
        self.founder.pitch_deck = SimpleUploadedFile('deck.pdf', b'%PDF-1.4 deck', content_type='application/pdf')
        self.founder.save()
        self.client.force_login(self.investor_user)
        with mock.patch('zelda_api.quotas.has_credits_for', return_value=True), \
                mock.patch('zelda_api.utils._extract_pdf_text', return_value=('deck text', 1)), \
                mock.patch('zelda_api.tasks.process_document_pipeline.delay'), \
                self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('zelda_api:analyze_founder_confirm', args=[self.founder_user.username]))
        self.assertEqual(response.json()['status'], 'processing')
        self.assertTrue(EntityReportAccessGrant.objects.filter(
            user=self.investor_user, report__founder_profile=self.founder).exists())
