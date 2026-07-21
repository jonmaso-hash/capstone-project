# zelda_api/entity_verification.py
"""
Entity Integrity v1 (Sprint 1): domain-age lookup + timeline-consistency
checks. Founder digital-footprint search and corporate-registry matching
are later sprints, not built here — see entity_verification_models.py.
"""
import logging
from datetime import date
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def extract_domain(url_or_domain):
    """Reduces a company_website URL (or a bare domain) to its host for WHOIS lookup."""
    if not url_or_domain:
        return None
    value = url_or_domain.strip()
    if not value:
        return None
    if '://' not in value:
        value = f'//{value}'
    netloc = (urlparse(value).netloc or '').split(':')[0].split('/')[0]
    if netloc.startswith('www.'):
        netloc = netloc[len('www.'):]
    return netloc or None


def lookup_domain_creation_date(domain):
    """
    WHOIS lookup for a domain's registration date. Returns (date, error) —
    error is a short, user-facing string on failure (no company website
    on file, domain not found, WHOIS server unreachable), never a raw
    exception message.
    """
    if not domain:
        return None, 'No company website on file.'
    try:
        import whois
        result = whois.whois(domain)
        creation = result.creation_date
        if isinstance(creation, list):
            creation = creation[0] if creation else None
        if creation is None:
            return None, 'No registration date found for this domain.'
        return (creation.date() if hasattr(creation, 'date') else creation), ''
    except Exception as e:
        logger.warning(f"WHOIS lookup failed for domain {domain}: {str(e)}")
        return None, 'Domain lookup unavailable right now.'


def compute_timeline_flags(claimed_founding_year, domain_registered_date):
    """
    Pure-logic timeline consistency check — no external call needed here,
    just comparing two dates already gathered. A domain registered well
    after the claimed founding year is one of the cheapest, hardest-to-
    fake signals in this whole feature. Worded as something to review,
    never an accusation — a legitimate company can rebrand onto a new
    domain years after actually founding.
    """
    flags = []
    if claimed_founding_year and domain_registered_date:
        domain_year = domain_registered_date.year
        gap = domain_year - claimed_founding_year
        if gap >= 2:
            flags.append(
                f"Domain registered in {domain_year}, {gap} years after the claimed founding year "
                f"({claimed_founding_year}) — may warrant a closer look."
            )
    return flags


def _owner_profile(user):
    """Same founder/seller resolution as truth_delta_models._owner_is_premium."""
    application = getattr(user, 'match_founder_profile', None)
    if application:
        return application
    return getattr(user, 'match_seller_profile', None)


def build_entity_verification_report(document):
    """
    Runs the Sprint 1 pillars for one document's uploader and returns an
    unsaved EntityVerificationReport. Caller decides whether/when to
    persist it — kept separate so tests can inspect the built object
    without touching the database.
    """
    from .entity_verification_models import EntityVerificationReport

    profile = _owner_profile(document.uploaded_by)
    domain = extract_domain(getattr(profile, 'company_website', None)) if profile else None
    domain_registered_date, domain_lookup_error = lookup_domain_creation_date(domain)

    claimed_founding_year = None
    years_in_business = getattr(profile, 'years_in_business', None) if profile else None
    if years_in_business:
        claimed_founding_year = date.today().year - years_in_business

    timeline_flags = compute_timeline_flags(claimed_founding_year, domain_registered_date)

    return EntityVerificationReport(
        document=document,
        domain=domain or '',
        domain_registered_date=domain_registered_date,
        domain_lookup_error=domain_lookup_error,
        claimed_founding_year=claimed_founding_year,
        timeline_flags=timeline_flags,
    )
