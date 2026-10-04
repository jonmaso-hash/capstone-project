"""
Task 7: the DataForB2B provider client. Every test injects a fake session;
none reaches the network (pages.tests_no_network_in_tests enforces that too).
Fixtures are shaped like the real 2026-10-03 probe responses.
"""
import json
import logging

import requests
from django.test import SimpleTestCase, override_settings

from zelda_api import dataforb2b as d4b
from zelda_api.source_capabilities import (
    CAN_CORROBORATE, CAN_ESTABLISH, CAPABILITIES, INFORMATIONAL_ONLY, LINKEDIN_DERIVED, UNAVAILABLE,
    capability_for, may_establish, origin_for,
)

KEY = 'dfb2b_TEST_SECRET_VALUE_9f8e7d'


class FakeResponse:
    def __init__(self, status, payload=None, malformed=False):
        self.status_code, self._payload, self._malformed = status, payload, malformed

    def json(self):
        if self._malformed:
            raise ValueError('not json')
        return self._payload


class FakeSession:
    """Answers by path; records every call so tests can assert what was (not) sent."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def request(self, method, url, headers=None, json=None, timeout=None):
        self.calls.append({'method': method, 'url': url, 'headers': dict(headers or {}), 'json': json,
                           'timeout': timeout})
        answer = self.routes[url.replace(d4b.BASE_URL, '')]
        if isinstance(answer, BaseException):
            raise answer
        return answer(json) if callable(answer) else answer


def company(**overrides):
    base = {
        'id': 'org_0lox54iG5IEZSb71mZWLR8z9CVPtpuHOmUOf', 'name': 'Ramp', 'industry': 'Financial Services',
        'headquarters': {'country': 'US', 'city': 'New York', 'region': 'New York'}, 'founded_year': 2019,
        'company_type': 'Privately Held',
        'links': {'website': 'ramp.com', 'linkedin': 'https://www.linkedin.com/company/ramp'},
        'size': {'employees': 6224, 'range_min': 1001, 'range_max': 5000},
        'signals': {'verified': True, 'actively_hiring': False},
        'funding': {'stage': 'series_f', 'total_rounds': 4, 'rounds': [
            {'round': 'series_f', 'amount_usd': 750_000_000, 'date': '2026-06-04'},
            {'round': 'secondary_market', 'amount_usd': 150_000_000, 'date': '2025-03-03'},
            {'round': 'debt_financing', 'amount_usd': 550_000_000, 'date': '2022-03-21'},
            {'round': 'series_b', 'amount_usd': 115_000_000, 'date': '2021-04-08'},
        ], 'investors': None},
        'growth': {'percent_1m': 0.66, 'percent_6m': 8.3, 'percent_12m': 22},
    }
    base.update(overrides)
    return {'company': base, 'credits_used': 1.5}


def enrich_ok(payload=None):
    return {'/enrich/company': FakeResponse(200, payload or company())}


def client(routes):
    session = FakeSession(routes)
    return d4b.DataForB2BClient(api_key=KEY, session=session), session


# -- authority: one canonical declaration ---------------------------------------------

class AuthorityTests(SimpleTestCase):

    def test_declared_roles_and_origin(self):
        self.assertEqual(CAPABILITIES['dataforb2b'], {
            'revenue': UNAVAILABLE, 'customers': UNAVAILABLE,
            'employees': INFORMATIONAL_ONLY, 'funding_raised': CAN_CORROBORATE})
        self.assertEqual(origin_for('dataforb2b'), LINKEDIN_DERIVED)

    def test_dataforb2b_establishes_nothing(self):
        for category in CAPABILITIES['dataforb2b']:
            with self.subTest(category=category):
                self.assertFalse(may_establish('dataforb2b', category))

    def test_not_wired_into_truth_delta_yet(self):
        from zelda_api.truth_delta_sources import DataSourceManager
        self.assertNotIn('dataforb2b', DataSourceManager.INTEGRATIONS)

    def test_fact_roles_come_from_the_registry(self):
        record = client(enrich_ok())[0].company_facts(org_id='org_abc').record
        for fact in record.facts:
            with self.subTest(category=fact.category):
                self.assertEqual(fact.role, capability_for('dataforb2b', fact.category))
                self.assertNotEqual(fact.role, CAN_ESTABLISH)
                self.assertEqual(fact.origin, LINKEDIN_DERIVED)


# -- normalization -------------------------------------------------------------------------

class NormalizationTests(SimpleTestCase):

    def test_success_is_a_zelda_object(self):
        result = client(enrich_ok())[0].company_facts(linkedin='https://www.linkedin.com/company/ramp/')
        self.assertTrue(result.ok)
        record = result.record
        self.assertIsInstance(record, d4b.CompanyRecord)
        self.assertEqual((record.provider, record.provider_id, record.name),
                         ('dataforb2b', 'org_0lox54iG5IEZSb71mZWLR8z9CVPtpuHOmUOf', 'Ramp'))
        self.assertEqual((record.lookup_method, record.lookup_identifier), ('linkedin', 'ramp'))
        self.assertEqual((record.hq_city, record.hq_region, record.hq_country, record.founded_year),
                         ('New York', 'New York', 'US', 2019))
        self.assertIsNotNone(record.retrieved_at.tzinfo)
        self.assertEqual(result.credits_used, 1.5)

    def test_employees_are_informational_profiles_not_headcount(self):
        fact = client(enrich_ok())[0].company_facts(org_id='org_abc').record.fact('employees')
        self.assertEqual((fact.value, fact.unit, fact.role), (6224.0, 'linkedin_associated_profiles', INFORMATIONAL_ONLY))
        self.assertIn('not company headcount', fact.note)

    def test_funding_is_corroborating_equity_only(self):
        fact = client(enrich_ok())[0].company_facts(org_id='org_abc').record.fact('funding_raised')
        self.assertEqual(fact.role, CAN_CORROBORATE)
        self.assertEqual(fact.value, 865_000_000.0)          # 750M + 115M; debt and secondary excluded
        self.assertEqual([r[0] for r in fact.detail], ['series_f', 'series_b'])

    def test_public_company_funding_is_withheld(self):
        nike = company(name='Nike', company_type='Public Company', funding={'rounds': [
            {'round': 'post_ipo_equity', 'amount_usd': 239_000_000, 'date': '2024-08-17'}]})
        record = client(enrich_ok(nike))[0].company_facts(linkedin='nike').record
        self.assertIsNone(record.fact('funding_raised'))
        self.assertEqual(record.withheld[0][0], 'funding_raised')
        self.assertTrue(record.is_public)

    def test_no_funding_produces_no_fact(self):
        record = client(enrich_ok(company(funding=None)))[0].company_facts(org_id='org_abc').record
        self.assertIsNone(record.fact('funding_raised'))

    def test_page_verification_is_raw_metadata_not_verification(self):
        record = client(enrich_ok())[0].company_facts(org_id='org_abc').record
        self.assertTrue(record.page_verified)
        for fact in record.facts:
            self.assertNotEqual(fact.role, CAN_ESTABLISH)

    def test_revenue_and_customers_cannot_be_requested(self):
        for category in ('revenue', 'customers'):
            with self.subTest(category=category):
                c, session = client(enrich_ok())
                result = c.company_facts(org_id='org_abc', categories=[category])
                self.assertEqual(result.outcome, d4b.UNSUPPORTED)
                self.assertEqual(session.calls, [], 'nothing may be spent on an unsupported category')
                self.assertFalse(d4b.supports(category))

    def test_never_produces_revenue_or_customers(self):
        record = client(enrich_ok(company(revenue=1e9, customers=70000)))[0].company_facts(org_id='org_abc').record
        self.assertEqual({f.category for f in record.facts}, {'employees', 'funding_raised'})


# -- resolution -------------------------------------------------------------------------------

def count_of(total):
    return FakeResponse(200, {'total_results': total, 'total_results_is_capped': False})


class ResolutionTests(SimpleTestCase):

    def test_domain_unique_match_searches_then_enriches(self):
        c, session = client({
            '/search/count': count_of(1),
            '/search/companies': FakeResponse(200, {'total': 1, 'results': [{'id': 'org_ramp1'}], 'credits_used': 0.75}),
            **enrich_ok(),
        })
        result = c.company_facts(domain='https://www.Ramp.com/pricing')
        self.assertTrue(result.ok)
        self.assertEqual([call['url'].replace(d4b.BASE_URL, '') for call in session.calls],
                         ['/search/count', '/search/companies', '/enrich/company'])
        self.assertEqual(session.calls[0]['json']['filters']['conditions'][0]['value'], 'ramp.com')
        self.assertEqual(session.calls[2]['json'], {'company_identifier': 'org_ramp1'})
        self.assertEqual(result.credits_used, 2.25)

    def test_domain_with_several_companies_is_ambiguous_and_free(self):
        c, session = client({'/search/count': count_of(10)})
        result = c.company_facts(domain='nike.com')
        self.assertEqual((result.outcome, result.candidates, result.credits_used), (d4b.AMBIGUOUS, 10, 0.0))
        self.assertEqual(len(session.calls), 1, 'never pick the first of several')

    def test_domain_with_no_company_is_not_found_and_free(self):
        c, session = client({'/search/count': count_of(0)})
        self.assertEqual(c.company_facts(domain='nope-48213.com').outcome, d4b.NOT_FOUND)
        self.assertEqual(len(session.calls), 1)

    def test_enrich_404_is_not_found(self):
        c, _ = client({'/enrich/company': FakeResponse(404, {'detail': 'Company not found: zzqxv'})})
        self.assertEqual(c.company_facts(linkedin='zzqxv').outcome, d4b.NOT_FOUND)

    def test_name_alone_is_unresolvable_without_a_call(self):
        c, session = client({})
        self.assertEqual(c.company_facts(name='Mercury').outcome, d4b.UNRESOLVABLE)
        self.assertEqual(c.company_facts().outcome, d4b.UNRESOLVABLE)
        self.assertEqual(session.calls, [])

    def test_malformed_identifiers_never_reach_the_provider(self):
        c, session = client({})
        for kwargs in ({'org_id': 'not-an-org'}, {'linkedin': '   '}, {'domain': 'not a domain'}, {'linkedin': ''}):
            with self.subTest(kwargs=kwargs):
                outcome = c.company_facts(**kwargs).outcome
                self.assertIn(outcome, (d4b.UNRESOLVABLE,))
        self.assertEqual(session.calls, [])

    def test_order_prefers_provider_id_then_linkedin_then_domain(self):
        c, session = client(enrich_ok())
        c.company_facts(org_id='org_first', linkedin='second', domain='third.com')
        self.assertEqual(session.calls[0]['json'], {'company_identifier': 'org_first'})
        c, session = client(enrich_ok())
        c.company_facts(linkedin='linkedin.com/company/second', domain='third.com')
        self.assertEqual(session.calls[0]['json'], {'company_identifier': 'second'})

    def test_estimated_credits(self):
        self.assertEqual(d4b.estimated_credits(org_id='org_a'), 1.5)
        self.assertEqual(d4b.estimated_credits(domain='a.com'), 2.25)
        self.assertEqual(d4b.estimated_credits(), 0.0)
        self.assertEqual({e.credits for name, e in d4b.ENDPOINTS.items() if name in ('account', 'count_companies')}, {0.0})


# -- failures are outcomes, never findings ------------------------------------------------------

class FailureTests(SimpleTestCase):

    def outcome(self, answer, **identifiers):
        c, _ = client({'/enrich/company': answer, '/search/count': answer, '/account': answer})
        return c.company_facts(**(identifiers or {'org_id': 'org_abc'}))

    def test_each_failure_is_distinguishable(self):
        cases = [
            (FakeResponse(401, {'detail': 'Invalid API key'}), d4b.AUTH_FAILED),
            (FakeResponse(403, {'detail': 'Forbidden'}), d4b.AUTH_FAILED),
            (FakeResponse(402, {'detail': 'Payment required'}), d4b.CREDITS_EXHAUSTED),
            (FakeResponse(403, {'detail': 'Insufficient credits'}), d4b.CREDITS_EXHAUSTED),
            (FakeResponse(429, {'detail': 'Too Many Requests'}), d4b.RATE_LIMITED),
            (FakeResponse(500, {'detail': 'Failed to fetch company: HTTP_400'}), d4b.PROVIDER_ERROR),
            (FakeResponse(503, None, malformed=True), d4b.PROVIDER_ERROR),
            (FakeResponse(422, {'detail': [{'msg': 'Field required'}]}), d4b.PROVIDER_ERROR),
            (FakeResponse(200, None, malformed=True), d4b.MALFORMED),
            (FakeResponse(200, ['not', 'an', 'object']), d4b.MALFORMED),
            (FakeResponse(200, {'company': {'name': 'no id'}}), d4b.MALFORMED),
            (requests.Timeout('read timed out'), d4b.TIMEOUT),
            (requests.ConnectionError('getaddrinfo failed'), d4b.UNAVAILABLE),
        ]
        for answer, expected in cases:
            with self.subTest(expected=expected, answer=repr(answer)[:60]):
                result = self.outcome(answer)
                self.assertEqual(result.outcome, expected)
                self.assertIsNone(result.record, 'a failure must never carry facts')
                if expected != d4b.NOT_FOUND:
                    self.assertTrue(result.failed)

    def test_missing_key_is_unconfigured_and_sends_nothing(self):
        session = FakeSession({})
        with override_settings(DATA4B2B_API_KEY=''):
            c = d4b.DataForB2BClient(session=session)
            self.assertFalse(c.configured)
            self.assertEqual(c.company_facts(org_id='org_abc').outcome, d4b.UNCONFIGURED)
            self.assertEqual(c.account().outcome, d4b.UNCONFIGURED)
        self.assertEqual(session.calls, [])

    def test_explicit_timeouts(self):
        c, session = client(enrich_ok())
        c.company_facts(org_id='org_abc')
        self.assertEqual(session.calls[0]['timeout'], (d4b.CONNECT_TIMEOUT, d4b.READ_TIMEOUT))

    def test_account_reports_balance_and_exhaustion(self):
        c, _ = client({'/account': FakeResponse(200, {'valid': True, 'credits': 2993.9})})
        result = c.account()
        self.assertEqual((result.outcome, result.credits_remaining), (d4b.SUCCESS, 2993.9))
        c, _ = client({'/account': FakeResponse(200, {'valid': True, 'credits': 0})})
        self.assertEqual(c.account().outcome, d4b.CREDITS_EXHAUSTED)

    def test_failed_enrich_after_paid_search_reports_the_spend(self):
        c, _ = client({
            '/search/count': count_of(1),
            '/search/companies': FakeResponse(200, {'results': [{'id': 'org_x'}], 'credits_used': 0.75}),
            '/enrich/company': requests.Timeout('slow'),
        })
        result = c.company_facts(domain='x.com')
        self.assertEqual((result.outcome, result.credits_used), (d4b.TIMEOUT, 0.75))


# -- the secret ------------------------------------------------------------------------------------

class SecretTests(SimpleTestCase):

    def test_key_only_in_the_documented_header(self):
        c, session = client(enrich_ok())
        c.company_facts(org_id='org_abc')
        call = session.calls[0]
        self.assertEqual(call['headers']['api_key'], KEY)
        self.assertNotIn(KEY, call['url'])
        self.assertNotIn(KEY, json.dumps(call['json']))

    def test_key_never_in_results_or_logs_even_when_errors_echo_it(self):
        leaking = [
            FakeResponse(401, {'detail': f'Invalid API key {KEY}'}),
            FakeResponse(500, {'detail': f'upstream said {KEY}'}),
            requests.ConnectionError(f'proxy rejected header api_key={KEY}'),
            requests.Timeout(f'timeout with {KEY}'),
        ]
        for answer in leaking:
            with self.subTest(answer=type(answer).__name__):
                c, _ = client({'/enrich/company': answer, '/account': answer})
                with self.assertLogs('zelda_api.dataforb2b', level='WARNING') as logs:
                    results = [c.company_facts(org_id='org_abc'), c.account()]
                self.assertNotIn(KEY, '\n'.join(logs.output))
                for result in results:
                    self.assertNotIn(KEY, repr(result))

    def test_key_not_in_the_client_repr(self):
        c, _ = client({})
        self.assertNotIn(KEY, repr(c))
        self.assertNotIn(KEY, str(vars(c).get('_session')))


class BoundaryTests(SimpleTestCase):
    """This module is the only production HTTP boundary to DataForB2B."""

    def test_no_other_module_calls_the_provider(self):
        import os
        from django.conf import settings
        from zelda_api.chunk_boundary import first_party_files
        offenders = []
        for path in first_party_files(str(settings.BASE_DIR)):
            if path.replace('\\', '/').endswith('zelda_api/dataforb2b.py'):
                continue
            with open(path, encoding='utf8') as handle:
                if 'dataforb2b.ai' in handle.read():
                    offenders.append(os.path.relpath(path, settings.BASE_DIR))
        self.assertEqual(offenders, [])
