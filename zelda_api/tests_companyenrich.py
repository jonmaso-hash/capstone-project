"""
CompanyEnrich corroborates a company's footprint. It never establishes one,
and it can never deny one.

CompanyEnrich is a B2B/GTM aggregator -- 33M companies blended from, in its own
documentation, "Public Databases... Partnered Data Providers... User-Generated
Data... Open Web Data: Scraped data from publicly available websites" -- with
no per-field provenance. You cannot tell whether a value came from a
regulatory filing, a partner feed or a scraped page.

The first record we pulled (stripe.com) demonstrated the limits concretely:

    location    country=Netherlands, city=Amsterdam,
                postal_code=94080-1912   <- South San Francisco, CA
                phone=+1 415-298-5539    <- a US number
    legalName   "Stripe, LLC"            <- Stripe is Stripe, Inc.
    employees   "over-10K" while reported_employees said "5K-10K"
    revenue     "over-1b"                <- a band, not a figure
    founded_year 2010                    <- correct

So this module takes four fields and structurally refuses the rest.

THE THREE RULES THIS FILE EXISTS TO HOLD:

    ABSENCE IS NOT A FINDING. A 404 means CompanyEnrich has no record. For a
    two-year-old private LLC that is the normal case. It may never become
    "this company does not exist" -- the same trap as reading SEC not_found
    as non-existence, with a weaker source.

    THE DOMAIN IS A RETRIEVAL KEY, NOT AN IDENTITY ASSERTION. "CompanyEnrich
    found a company associated with this domain", never "CompanyEnrich has
    identified this legal entity". The identity authority stays where it is;
    an aggregator with its own matching would recreate the dual-resolution
    defect PRs #102-#105 removed.

    THE UNSAFE FIELDS ARE STRUCTURALLY ABSENT, not merely unused. Omitting
    them from the first implementation invites a future developer to reach
    for location or employees because they are sitting there in the payload.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from . import companyenrich, sec_identity
from .safe_fetch import FetchError

KEY = 'ce-test-key-not-real'

SAMPLE = {
    'id': '0192577c-1d7a-715c-a5b7-1b9b530445e0',
    'name': 'Stripe',
    'legalName': 'Stripe, LLC',
    'domain': 'stripe.com',
    'website': 'https://stripe.com',
    'founded_year': 2010,
    'industry': 'Finance',
    'employees': 'over-10K',
    'reported_employees': '5K-10K',
    'revenue': 'over-1b',
    'location': {'country': {'name': 'Netherlands'}, 'postal_code': '94080-1912'},
    'type': 'private',
}


def _response(status=200, payload=None):
    response = mock.Mock()
    response.status_code = status
    response.json.return_value = payload if payload is not None else SAMPLE
    response.headers = {'x-credit-cost': '1', 'x-credit-remaining': '498'}
    return response


class CompanyEnrichTestCase(SimpleTestCase):
    """
    Base that clears the cache.

    The provider caches settled lookups, so without this a value stored by one
    test leaks into the next. The first mutation battery proved it: mutations
    were killed by tests unrelated to what they changed, and the caching test
    that should have caught `outage_is_cached` never fired. A kill from
    contamination is not evidence that the right test works.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        super().setUp()


class TheUnsafeFieldsAreStructurallyAbsentTests(CompanyEnrichTestCase):
    """
    The boundary is encoded, not merely unimplemented. A future developer
    reading the provider must not find location or employees sitting in the
    returned object waiting to be used.
    """

    def footprint(self):
        with override_settings(COMPANYENRICH_API_KEY=KEY), \
             mock.patch.object(companyenrich.requests, 'get', return_value=_response()):
            return companyenrich.company_footprint('stripe.com')

    def test_the_harness_returns_a_footprint_at_all(self):
        """Positive control: the assertions below inspect this object."""
        self.assertIsNotNone(self.footprint())

    def test_the_four_corroborating_fields_are_present(self):
        footprint = self.footprint()
        for field in ('domain', 'website', 'founded_year', 'industry'):
            with self.subTest(field=field):
                self.assertIn(field, footprint)

    def test_the_unsafe_fields_are_not_carried_at_all(self):
        """
        Each of these was shown wrong or unusable in the sample record.
        Carrying them makes it one keystroke to turn aggregator noise into an
        adverse finding about a real business.
        """
        footprint = self.footprint()
        for field in ('location', 'legalName', 'employees', 'reported_employees',
                      'revenue', 'phone', 'postal_code'):
            with self.subTest(field=field):
                self.assertNotIn(field, footprint)

    def test_the_forbidden_set_is_declared_not_implied(self):
        self.assertTrue(companyenrich.NEVER_CORROBORATE)
        for field in ('location', 'legalName', 'employees', 'revenue'):
            self.assertIn(field, companyenrich.NEVER_CORROBORATE)


class AbsenceIsNeverAFindingTests(CompanyEnrichTestCase):

    def test_a_404_yields_no_footprint_rather_than_a_denial(self):
        """
        CompanyEnrich having no record of a two-year-old LLC is the normal
        case, not evidence about the company.
        """
        with override_settings(COMPANYENRICH_API_KEY=KEY), \
             mock.patch.object(companyenrich.requests, 'get',
                               return_value=_response(status=404, payload={})):
            self.assertIsNone(companyenrich.company_footprint('joytoys.example'))

    def test_a_404_is_reported_as_no_record_not_as_absent_company(self):
        with override_settings(COMPANYENRICH_API_KEY=KEY), \
             mock.patch.object(companyenrich.requests, 'get',
                               return_value=_response(status=404, payload={})):
            status = companyenrich.lookup_status('joytoys.example')
        self.assertEqual(status, companyenrich.NO_RECORD)
        self.assertNotEqual(status, 'not_a_company')

    def test_an_unconfigured_key_is_unconfigured_not_a_failed_check(self):
        """
        No key means the integration is off. That is a configuration state,
        not evidence about any company.
        """
        with override_settings(COMPANYENRICH_API_KEY=''):
            self.assertIsNone(companyenrich.company_footprint('stripe.com'))
            self.assertEqual(companyenrich.lookup_status('stripe.com'),
                             companyenrich.UNCONFIGURED)

    def test_a_transient_failure_is_distinct_from_no_record(self):
        """
        A timeout is not a statement about the company. Collapsing the two
        would let a ten-second outage read as "no commercial footprint".
        """
        with override_settings(COMPANYENRICH_API_KEY=KEY), \
             mock.patch.object(companyenrich.requests, 'get',
                               side_effect=companyenrich.requests.Timeout('slow')):
            self.assertEqual(companyenrich.lookup_status('stripe.com'),
                             companyenrich.UNAVAILABLE)


class TheDomainIsARetrievalKeyTests(CompanyEnrichTestCase):

    def test_domains_are_normalised_before_lookup(self):
        """
        https://WWW.Stripe.com/pricing and stripe.com are the same retrieval
        key. Without this, trivial URL differences spend separate credits and
        can produce different findings for one company.
        """
        for raw in ('https://WWW.Stripe.com/pricing', 'stripe.com',
                    'http://stripe.com/', 'Stripe.com'):
            with self.subTest(raw=raw):
                self.assertEqual(companyenrich.normalise_domain(raw), 'stripe.com')

    def test_a_non_public_host_is_refused_without_calling_out(self):
        """
        The JoyToys profile's website is http://127.0.0.1:8000. There is
        nothing to look up, and a credit must not be spent discovering that.
        """
        with override_settings(COMPANYENRICH_API_KEY=KEY), \
             mock.patch.object(companyenrich.requests, 'get') as get:
            result = companyenrich.company_footprint('http://127.0.0.1:8000')
        self.assertIsNone(result)
        self.assertFalse(get.called, 'a credit was spent on a localhost address')


class SettledResultsAreCachedTests(CompanyEnrichTestCase):
    """
    The allowance is ~500 credits. A second Zelda run on the same company must
    not spend another one. Settled outcomes cache; transient failures never do
    -- the rule already proven for SEC identity, where a ten-second outage
    must not become a durable answer.
    """

    def test_a_second_lookup_does_not_spend_another_credit(self):
        with override_settings(COMPANYENRICH_API_KEY=KEY), \
             mock.patch.object(companyenrich.requests, 'get',
                               return_value=_response()) as get:
            companyenrich.company_footprint('stripe.com')
            companyenrich.company_footprint('https://www.stripe.com/')
        self.assertEqual(get.call_count, 1,
                         'the same company was fetched twice, spending two credits')

    def test_a_transient_failure_is_not_cached(self):
        with override_settings(COMPANYENRICH_API_KEY=KEY), \
             mock.patch.object(companyenrich.requests, 'get',
                               side_effect=companyenrich.requests.Timeout('slow')) as get:
            companyenrich.lookup_status('stripe.com')
            companyenrich.lookup_status('stripe.com')
        self.assertEqual(get.call_count, 2,
                         'an outage was cached as though it were an answer')


class TheFindingsCorroborateAndNeverDenyTests(TestCase):
    """
    The Entity Integrity wiring. These rows sit beside the website, domain-age
    and SEC rows, and must never be the one that tells an investor a real
    business does not exist.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        from matchmaking.models import Application
        _mock_embedding_generation(self)
        from django.core.cache import cache
        cache.clear()
        user = get_user_model().objects.create_user('ce_founder', password='x')
        self.subject = Application.objects.create(
            user=user, company_name='Stripe', founder_name='Pat Example',
            email='ce@example.invalid', description='Payments.',
            company_website='https://stripe.com', years_in_business=16)

    def rows(self, status, footprint):
        """
        The real collect_findings, with every outward edge stubbed. The
        site fetch raises FetchError -- the exception the code actually
        catches -- so these tests exercise the CompanyEnrich block without
        depending on a live site or a WHOIS lookup.
        """
        from .entity_verification import collect_findings
        patches = [
            mock.patch.object(companyenrich, 'lookup_status', return_value=status),
            mock.patch.object(companyenrich, 'company_footprint', return_value=footprint),
            mock.patch('zelda_api.entity_verification.fetch_public_page',
                       side_effect=FetchError('not fetched in this test')),
            mock.patch('zelda_api.entity_verification.lookup_domain_creation_date',
                       return_value=(None, 'skipped')),
            # SEC too: the docstring above used to claim only the network
            # edges were stubbed while this one was live, so every test here
            # called EDGAR. Stubbed at find_sec_filer rather than at
            # sec_findings, so the real not-found branch still runs and still
            # adds its row -- test_the_other_checks_still_run asserts that row
            # exists, and mocking one level higher silently deleted it.
            mock.patch('zelda_api.sec_identity.find_sec_filer',
                       return_value=sec_identity.FilerLookup('not_found')),
        ]
        for patch in patches:
            patch.start()
        try:
            found = collect_findings(self.subject)
        finally:
            for patch in reversed(patches):
                patch.stop()
        return {r['check']: r for r in found}

    def test_a_found_company_corroborates_the_footprint(self):
        rows = self.rows(companyenrich.FOUND,
                         {'domain': 'stripe.com', 'website': 'https://stripe.com',
                          'founded_year': 2010, 'industry': 'Finance'})
        row = rows.get('commercial_footprint')
        self.assertIsNotNone(row, 'no footprint row was produced')
        self.assertIn('CompanyEnrich', row['evidence_source'])

    def test_no_record_never_produces_an_adverse_result(self):
        """
        THE rule. A young private LLC absent from a B2B aggregator is the
        ordinary case. Whatever is rendered, it may not be a negative finding.
        """
        rows = self.rows(companyenrich.NO_RECORD, None)
        row = rows.get('commercial_footprint')
        if row is not None:
            from .entity_verification_models import EntityVerificationReport as R
            self.assertNotEqual(row['result'], R.DOESNT_MATCH)
            self.assertNotEqual(row['result'], R.NOT_FOUND)
            self.assertNotIn('does not exist', (row['evidence'] or '').lower())
            self.assertNotIn("doesn't exist", (row['evidence'] or '').lower())

    def test_no_record_says_what_it_actually_means(self):
        rows = self.rows(companyenrich.NO_RECORD, None)
        row = rows.get('commercial_footprint')
        if row is not None:
            self.assertIn('not', (row['evidence'] or '').lower())

    def test_an_unconfigured_integration_adds_no_row_at_all(self):
        """
        The integration being off is not evidence, and must not occupy a line
        in an investor-facing report.
        """
        rows = self.rows(companyenrich.UNCONFIGURED, None)
        self.assertNotIn('commercial_footprint', rows)

    def test_the_other_checks_still_run(self):
        """
        Positive control: adding this provider must not displace the website,
        founding-year or SEC rows.
        """
        rows = self.rows(companyenrich.FOUND,
                         {'domain': 'stripe.com', 'founded_year': 2010})
        for check in ('website', 'company_name', 'founding_year', 'sec_filer'):
            with self.subTest(check=check):
                self.assertIn(check, rows)
