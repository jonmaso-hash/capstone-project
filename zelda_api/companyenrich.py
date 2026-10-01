"""
CompanyEnrich: a corroboration provider. Never an identity authority.

CompanyEnrich is a B2B/GTM aggregator whose own documentation describes its
inputs as "Public Databases... Partnered Data Providers... User-Generated
Data... Open Web Data: Scraped data from publicly available websites", with no
per-field provenance. A returned value cannot be traced to a filing, a partner
or a scraped page.

The first record we pulled (stripe.com) showed what that costs:

    location     country=Netherlands, city=Amsterdam, postal_code=94080-1912
                 (South San Francisco), phone=+1 415-298-5539
    legalName    "Stripe, LLC" -- Stripe is Stripe, Inc.
    employees    "over-10K" while reported_employees said "5K-10K"
    revenue      "over-1b" -- a band, not a figure
    founded_year 2010 -- correct

So this module carries FOUR fields and structurally refuses the rest. The
refusal is declared in NEVER_CORROBORATE rather than achieved by omission,
because a field sitting unused in a payload is an invitation.

Three rules:

  ABSENCE IS NOT A FINDING. A 404 means no record. For a young private LLC
  that is the ordinary case, and it may never become "this company does not
  exist" -- the same trap as reading SEC not_found as non-existence, from a
  weaker source.

  THE DOMAIN IS A RETRIEVAL KEY, NOT AN IDENTITY ASSERTION. This module says
  "a company is associated with this domain", never "this is the legal
  entity". Identity resolution stays with the identity authority; an
  aggregator doing its own matching would recreate the dual-resolution defect
  PRs #102-#105 removed.

  SETTLED OUTCOMES CACHE, TRANSIENT FAILURES NEVER. The allowance is small
  (~500 credits), and a ten-second outage must not become a durable answer --
  the rule already proven in sec_company_identity.
"""
import logging
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

ENDPOINT = 'https://api.companyenrich.com/companies/enrich'
TIMEOUT_SECONDS = 10
CACHE_PREFIX = 'companyenrich_v1'
CACHE_SECONDS = 60 * 60 * 24 * 7

# Lookup outcomes. Deliberately four, not two: "we have no record", "we could
# not look", and "the integration is off" are different states, and only the
# first says anything at all about the company -- and even then, very little.
FOUND = 'found'
NO_RECORD = 'no_record'
UNAVAILABLE = 'unavailable'
UNCONFIGURED = 'unconfigured'

# The only fields permitted to inform a finding.
CORROBORATING_FIELDS = ('domain', 'website', 'founded_year', 'industry')

# Declared, not merely unused. Every one of these was observed wrong, banded
# or internally inconsistent in the sample record, and each is the kind of
# field a future developer would reasonably reach for. Feeding any of them
# into contradiction logic would publish aggregator noise as an adverse
# finding about a real business.
NEVER_CORROBORATE = frozenset({
    'legalName',           # "Stripe, LLC" for Stripe, Inc. -- looks registry-grade, is not
    'location',            # Netherlands + a South San Francisco postal code
    'city', 'state', 'country', 'postal_code', 'address', 'phone',
    'employees',           # banded, and disagreed with reported_employees
    'reported_employees',
    'revenue',             # banded ("over-1b")
    'type', 'naics_codes', 'categories', 'technologies', 'keywords',
    'subsidiaries', 'page_rank', 'socials',
})


def normalise_domain(url_or_domain):
    """
    The retrieval key. One company, one key, one credit.

    https://WWW.Stripe.com/pricing and stripe.com are the same lookup; without
    normalising, trivial URL differences spend separate credits and can yield
    different findings for one company.
    """
    raw = (url_or_domain or '').strip()
    if not raw:
        return ''
    if '://' not in raw:
        raw = 'https://' + raw
    host = (urlparse(raw).hostname or '').lower()
    return host[4:] if host.startswith('www.') else host


def _is_public_host(host):
    """
    A host worth spending a credit on.

    The JoyToys profile's website is http://127.0.0.1:8000. There is nothing
    to enrich, and discovering that should not cost a credit.
    """
    if not host or '.' not in host:
        return False
    if host.endswith('.local') or host.endswith('.localhost') or host.endswith('.test'):
        return False
    if host in ('localhost', '127.0.0.1', '0.0.0.0', '::1'):
        return False
    return not (host.startswith('127.') or host.startswith('10.')
                or host.startswith('192.168.') or host.startswith('169.254.'))


def _safe_subset(payload):
    """Only the corroborating fields. Everything else is dropped here."""
    return {
        field: payload.get(field)
        for field in CORROBORATING_FIELDS
        if payload.get(field) not in (None, '')
    }


def _fetch(domain):
    """(status, footprint-or-None). Spends at most one credit."""
    key = getattr(settings, 'COMPANYENRICH_API_KEY', '') or ''
    if not key:
        return UNCONFIGURED, None
    if not _is_public_host(domain):
        return NO_RECORD, None

    try:
        response = requests.get(
            ENDPOINT,
            # waitForEnrichment=false: a company we have not stored returns 404
            # WITHOUT charging a credit, rather than blocking on an on-demand
            # enrichment we would pay for.
            params={'domain': domain, 'waitForEnrichment': 'false'},
            headers={'Authorization': 'Bearer %s' % key, 'accept': 'application/json'},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.warning('[CompanyEnrich] %s unreachable for %s', type(exc).__name__, domain)
        return UNAVAILABLE, None

    if response.status_code == 404:
        return NO_RECORD, None
    if response.status_code != 200:
        logger.warning('[CompanyEnrich] HTTP %s for %s', response.status_code, domain)
        return UNAVAILABLE, None

    try:
        payload = response.json() or {}
    except ValueError:
        return UNAVAILABLE, None
    return FOUND, _safe_subset(payload)


def _lookup(url_or_domain):
    domain = normalise_domain(url_or_domain)
    cache_key = '%s:%s' % (CACHE_PREFIX, domain)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    status, footprint = _fetch(domain)
    # Settled outcomes only. UNAVAILABLE is a statement about the request, not
    # about the company, and caching it would turn an outage into an answer.
    if status in (FOUND, NO_RECORD):
        cache.set(cache_key, (status, footprint), CACHE_SECONDS)
    return status, footprint


def lookup_status(url_or_domain):
    """FOUND / NO_RECORD / UNAVAILABLE / UNCONFIGURED, without the payload."""
    return _lookup(url_or_domain)[0]


def company_footprint(url_or_domain):
    """
    The corroborating fields for this domain, or None.

    None means "nothing to corroborate with" in every case -- no record, no
    key, or no answer. It never means the company does not exist, and callers
    must not render it that way. Use `lookup_status` when the reason matters.
    """
    return _lookup(url_or_domain)[1]
