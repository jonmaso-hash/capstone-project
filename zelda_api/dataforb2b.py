"""
DataForB2B: the only production HTTP boundary to api.dataforb2b.ai.

Measured contract (2026-10-03 probe; docs at docs.dataforb2b.ai):
    auth        header `api_key: <key>` -- never a URL parameter
    401         missing or invalid key (JSON `detail`)
    404         enrich: company not found (not charged)
    422         malformed request body
    500         seen for an empty identifier -- so one is never sent
    429         rate limited (search 10/s, enrichment 30/s)

Endpoints used, and what they cost:
    GET  /account           free     validity and remaining credits
    POST /search/count      free     how many companies match a filter
    POST /search/companies  0.75     per RESULT returned; zero results are free
    POST /enrich/company    1.5      per enriched company; not-found is free

Resolution order -- deterministic identifiers only, never fuzzy names:
    1. provider id (`org_...`)        enrich directly                  1.5
    2. LinkedIn company URL or slug   enrich directly                  1.5
    3. domain                         free count first:
                                        0  -> NOT_FOUND                   0
                                        >1 -> AMBIGUOUS                   0
                                        1  -> search (1 result), enrich   2.25
    4. name only                      UNRESOLVABLE, no call           0
A domain is candidate generation, not identity: `nike.com` matches ten
organisations and the first-ranked is "Nike Elite HS Basketball". Only a
unique match proceeds; several plausible ones are AMBIGUOUS, never "the first".

What a record may contain is decided by source_capabilities, not here:
    revenue, customers   UNAVAILABLE    never produced, never requested
    employees            INFORMATIONAL  LinkedIn-associated profiles, not headcount
    funding_raised       CORROBORATING  sum of equity rounds; never for a public company
Origin: linkedin_derived. Nothing from this provider establishes a fact.

Failures are outcomes, never findings: a timeout, an expired key or exhausted
credits says nothing about the company and must not be read as if it did.
The key is read from settings, sent only in the header, and redacted from
anything this module logs or returns.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from typing import Optional, Tuple

import requests
from django.conf import settings

from .source_capabilities import capability_for, may_store, origin_for

logger = logging.getLogger(__name__)

SOURCE_TYPE = 'dataforb2b'
BASE_URL = 'https://api.dataforb2b.ai'
# Enrichment was measured at up to ~20 s for a live fetch.
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 25


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    credits: float
    per_result: bool = False


ENDPOINTS = {
    'account': Endpoint('GET', '/account', 0.0),
    'count_companies': Endpoint('POST', '/search/count', 0.0),
    'search_companies': Endpoint('POST', '/search/companies', 0.75, per_result=True),
    'enrich_company': Endpoint('POST', '/enrich/company', 1.5),
}

# Outcomes. The first group is about the lookup; the rest are failures of the
# attempt and say nothing about the company.
SUCCESS = 'success'
NOT_FOUND = 'not_found'
AMBIGUOUS = 'ambiguous'
UNRESOLVABLE = 'unresolvable'          # no deterministic identifier was given
UNSUPPORTED = 'unsupported'            # a category this source may not provide
UNCONFIGURED = 'unconfigured'          # no API key
AUTH_FAILED = 'auth_failed'
CREDITS_EXHAUSTED = 'credits_exhausted'
RATE_LIMITED = 'rate_limited'
TIMEOUT = 'timeout'
UNAVAILABLE = 'unavailable'            # network failure
PROVIDER_ERROR = 'provider_error'
MALFORMED = 'malformed'
FAILURES = frozenset({UNCONFIGURED, AUTH_FAILED, CREDITS_EXHAUSTED, RATE_LIMITED, TIMEOUT,
                      UNAVAILABLE, PROVIDER_ERROR, MALFORMED})

# Funding rounds that are not equity raised by the company.
NON_EQUITY_ROUNDS = frozenset({'debt_financing', 'secondary_market'})

_ORG_ID = re.compile(r'^org_[A-Za-z0-9]+$')
_SLUG = re.compile(r'^[a-z0-9][a-z0-9._-]*$')
_LINKEDIN = re.compile(r'linkedin\.com/company/([^/?#\s]+)', re.IGNORECASE)
_DOMAIN = re.compile(r'^(?=.{4,253}$)([a-z0-9-]+\.)+[a-z]{2,}$')


@dataclass(frozen=True)
class ProviderFact:
    """One value this source may supply, with its declared role and origin."""
    category: str
    value: float
    unit: str
    role: str
    origin: str
    field: str                       # provider field path, for provenance
    note: str = ''
    detail: Tuple = ()


@dataclass(frozen=True)
class CompanyRecord:
    provider: str
    provider_id: str
    name: str
    lookup_method: str               # org_id | linkedin | domain
    lookup_identifier: str
    retrieved_at: datetime
    company_type: str = ''
    is_public: bool = False
    hq_country: str = ''
    hq_region: str = ''
    hq_city: str = ''
    founded_year: Optional[int] = None
    linkedin_url: str = ''
    website: str = ''
    # Raw provider metadata. `page_verified` is LinkedIn's page verification,
    # not independent verification of any value in this record.
    page_verified: Optional[bool] = None
    facts: Tuple[ProviderFact, ...] = ()
    withheld: Tuple[Tuple[str, str], ...] = ()   # (category, why) -- e.g. funding of a public company

    def fact(self, category):
        return next((f for f in self.facts if f.category == category), None)


@dataclass(frozen=True)
class Result:
    outcome: str
    record: Optional[CompanyRecord] = None
    candidates: Optional[int] = None
    reason: str = ''
    credits_used: float = 0.0
    credits_remaining: Optional[float] = None

    @property
    def ok(self):
        return self.outcome == SUCCESS

    @property
    def failed(self):
        return self.outcome in FAILURES


class _Failure(Exception):
    def __init__(self, outcome, reason=''):
        super().__init__(outcome)
        self.outcome, self.reason = outcome, reason


def supports(category):
    """Whether Zelda may consume this category from DataForB2B at all -- asked before spending a credit."""
    return may_store(SOURCE_TYPE, category)


def estimated_credits(*, org_id=None, linkedin=None, domain=None):
    """Upper bound for one company_facts() call with these identifiers."""
    enrich = ENDPOINTS['enrich_company'].credits
    if org_id or linkedin:
        return enrich
    if domain:
        return ENDPOINTS['search_companies'].credits + enrich
    return 0.0


def normalize_domain(value):
    text = (value or '').strip().lower()
    text = re.sub(r'^[a-z]+://', '', text).split('/')[0].split('?')[0]
    text = text[4:] if text.startswith('www.') else text
    return text if _DOMAIN.match(text) else ''


def linkedin_slug(value):
    text = (value or '').strip()
    match = _LINKEDIN.search(text)
    slug = (match.group(1) if match else text).strip('/').lower()
    return slug if _SLUG.match(slug) else ''


class DataForB2BClient:

    def __init__(self, api_key=None, session=None):
        self._key = api_key if api_key is not None else (getattr(settings, 'DATA4B2B_API_KEY', '') or '')
        self._session = session or requests.Session()

    @property
    def configured(self):
        return bool(self._key)

    def _redact(self, text):
        text = str(text)
        return text.replace(self._key, '[REDACTED]') if self._key else text

    # -- the one network call ------------------------------------------------------

    def _request(self, endpoint_name, body=None):
        endpoint = ENDPOINTS[endpoint_name]
        if not self._key:
            raise _Failure(UNCONFIGURED, 'DATA4B2B_API_KEY is not set')
        try:
            response = self._session.request(
                endpoint.method, BASE_URL + endpoint.path,
                headers={'api_key': self._key, 'Content-Type': 'application/json'},
                json=body, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        except requests.Timeout:
            self._log(endpoint, TIMEOUT)
            raise _Failure(TIMEOUT, 'timed out')
        except requests.RequestException as exc:
            self._log(endpoint, UNAVAILABLE, type(exc).__name__)
            raise _Failure(UNAVAILABLE, type(exc).__name__)

        try:
            payload = response.json()
        except ValueError:
            payload = None
        detail = payload.get('detail') if isinstance(payload, dict) else None
        status = response.status_code
        if status == 200:
            if not isinstance(payload, dict):
                self._log(endpoint, MALFORMED)
                raise _Failure(MALFORMED, 'response was not a JSON object')
            return payload
        outcome = self._classify(status, detail)
        reason = self._redact(f'HTTP {status}' + (f': {detail}' if isinstance(detail, str) else ''))[:200]
        self._log(endpoint, outcome, f'HTTP {status}')
        raise _Failure(outcome, reason)

    @staticmethod
    def _classify(status, detail):
        mentions_credit = isinstance(detail, str) and 'credit' in detail.lower()
        if status == 402 or (status in (400, 403) and mentions_credit):
            return CREDITS_EXHAUSTED
        if status in (401, 403):
            return AUTH_FAILED
        if status == 404:
            return NOT_FOUND
        if status == 429:
            return RATE_LIMITED
        return PROVIDER_ERROR

    def _log(self, endpoint, outcome, extra=''):
        # Method, path and outcome only. Never headers, never response text.
        logger.warning(self._redact(f'[DataForB2B] {endpoint.method} {endpoint.path} -> {outcome} {extra}'.rstrip()))

    # -- free -------------------------------------------------------------------------------

    def account(self):
        """Key validity and remaining credits. Free."""
        try:
            payload = self._request('account')
        except _Failure as failure:
            return Result(failure.outcome, reason=failure.reason)
        credits = payload.get('credits')
        if not isinstance(credits, (int, float)):
            return Result(MALFORMED, reason='account response had no credit balance')
        if credits <= 0:
            return Result(CREDITS_EXHAUSTED, credits_remaining=float(credits))
        return Result(SUCCESS, credits_remaining=float(credits))

    # -- resolution + facts ---------------------------------------------------------------

    def company_facts(self, *, org_id=None, linkedin=None, domain=None, name=None, categories=None):
        """
        Resolve one company deterministically and return the facts Zelda may
        consume from this source. `categories` narrows them; asking for one
        this source may not provide (revenue, customers) returns UNSUPPORTED
        before anything is spent.
        """
        wanted = tuple(categories) if categories is not None else ('employees', 'funding_raised')
        unsupported = [c for c in wanted if not supports(c)]
        if unsupported:
            return Result(UNSUPPORTED, reason=f'DataForB2B may not provide: {", ".join(unsupported)}')
        spent = 0.0
        try:
            identifier, method, spent = self._resolve(org_id=org_id, linkedin=linkedin, domain=domain, name=name)
            payload = self._request('enrich_company', {'company_identifier': identifier})
        except _Failure as failure:
            # A failed enrichment after a paid search still spent the search.
            return Result(failure.outcome, candidates=getattr(failure, 'candidates', None),
                          reason=failure.reason, credits_used=getattr(failure, 'spent', spent))
        spent += float(payload.get('credits_used') or 0)
        try:
            record = self._normalize(payload, method, identifier, wanted)
        except _Failure as failure:
            return Result(failure.outcome, reason=failure.reason, credits_used=spent)
        return Result(SUCCESS, record=record, credits_used=spent)

    def _resolve(self, *, org_id, linkedin, domain, name):
        """(identifier, method, credits spent) or _Failure. See the module docstring for the order."""
        if org_id:
            if not _ORG_ID.match(str(org_id)):
                raise _Failure(UNRESOLVABLE, 'malformed provider id')
            return org_id, 'org_id', 0.0
        if linkedin:
            slug = linkedin_slug(linkedin)
            if not slug:
                raise _Failure(UNRESOLVABLE, 'malformed LinkedIn identifier')
            return slug, 'linkedin', 0.0
        if domain:
            clean = normalize_domain(domain)
            if not clean:
                raise _Failure(UNRESOLVABLE, 'malformed domain')
            filters = {'op': 'and', 'conditions': [{'column': 'domain', 'type': '=', 'value': clean}]}
            count = self._request('count_companies', {'category': 'company', 'filters': filters})
            total = count.get('total_results')
            if not isinstance(total, int):
                raise _Failure(MALFORMED, 'count response had no total')
            if total == 0:
                raise _Failure(NOT_FOUND, f'no company has the domain {clean}')
            if total > 1:
                failure = _Failure(AMBIGUOUS, f'{total} companies share the domain {clean}')
                failure.candidates = total
                raise failure
            search = self._request('search_companies', {'filters': filters, 'count': 1})
            spent = float(search.get('credits_used') or 0)
            results = search.get('results')
            if not isinstance(results, list) or len(results) != 1 or not _ORG_ID.match(str(results[0].get('id', ''))):
                failure = _Failure(MALFORMED, 'search did not return exactly one company id')
                failure.spent = spent
                raise failure
            return results[0]['id'], 'domain', spent
        if name:
            raise _Failure(UNRESOLVABLE, 'a name alone is not a deterministic identifier')
        raise _Failure(UNRESOLVABLE, 'no identifier given')

    def _normalize(self, payload, method, identifier, wanted):
        company = payload.get('company')
        if not isinstance(company, dict) or not company.get('id') or not company.get('name'):
            raise _Failure(MALFORMED, 'enrichment had no company id and name')
        company_type = str(company.get('company_type') or '')
        is_public = 'public' in company_type.lower()
        hq = company.get('headquarters') if isinstance(company.get('headquarters'), dict) else {}
        links = company.get('links') if isinstance(company.get('links'), dict) else {}
        signals = company.get('signals') if isinstance(company.get('signals'), dict) else {}
        origin = origin_for(SOURCE_TYPE)

        facts, withheld = [], []
        if 'employees' in wanted:
            size = company.get('size') if isinstance(company.get('size'), dict) else {}
            employees = size.get('employees')
            if isinstance(employees, (int, float)) and employees > 0:
                facts.append(ProviderFact(
                    category='employees', value=float(employees), unit='linkedin_associated_profiles',
                    role=capability_for(SOURCE_TYPE, 'employees'), origin=origin, field='size.employees',
                    note='LinkedIn-associated profiles; not company headcount',
                    detail=(('range_min', size.get('range_min')), ('range_max', size.get('range_max'))),
                ))
        if 'funding_raised' in wanted:
            funding = company.get('funding') if isinstance(company.get('funding'), dict) else None
            if is_public:
                withheld.append(('funding_raised', 'public company: provider funding is not used'))
            elif funding:
                fact = self._funding_fact(funding, origin)
                if fact:
                    facts.append(fact)

        return CompanyRecord(
            provider=SOURCE_TYPE, provider_id=str(company['id']), name=str(company['name']),
            lookup_method=method, lookup_identifier=identifier,
            retrieved_at=datetime.now(dt_timezone.utc),
            company_type=company_type, is_public=is_public,
            hq_country=str(hq.get('country') or ''), hq_region=str(hq.get('region') or ''),
            hq_city=str(hq.get('city') or ''),
            founded_year=company.get('founded_year') if isinstance(company.get('founded_year'), int) else None,
            linkedin_url=str(links.get('linkedin') or ''), website=str(links.get('website') or ''),
            page_verified=signals.get('verified') if isinstance(signals.get('verified'), bool) else None,
            facts=tuple(facts), withheld=tuple(withheld),
        )

    @staticmethod
    def _funding_fact(funding, origin):
        rounds = funding.get('rounds') if isinstance(funding.get('rounds'), list) else []
        equity = [r for r in rounds if isinstance(r, dict) and r.get('round') not in NON_EQUITY_ROUNDS]
        amounts = [r.get('amount_usd') for r in equity if isinstance(r.get('amount_usd'), (int, float))]
        if not amounts:
            return None
        return ProviderFact(
            category='funding_raised', value=float(sum(amounts)), unit='USD',
            role=capability_for(SOURCE_TYPE, 'funding_raised'), origin=origin, field='funding.rounds',
            note=('Sum of equity rounds with a stated amount; debt and secondary rounds excluded'
                  + ('; some rounds had no amount' if len(amounts) < len(equity) else '')),
            detail=tuple((r.get('round'), r.get('amount_usd'), r.get('date')) for r in equity),
        )
