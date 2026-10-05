# zelda_api/entity_verification.py
"""
Entity Integrity: what public sources show about a business, next to what its
Interlink profile says.

For one business (a startup Application or a SellerApplication) this compares:

- the profile's website  -> does it load (fetched through safe_fetch)
- the company name       -> does it appear on that site
- the founder or seller  -> does that person's name appear on that site
- years in business      -> the domain's registration date (WHOIS)

Each comparison becomes a row with the claim, where Interlink got it, the
evidence, a result (Matches, Doesn't match, Not found, Not applicable, Couldn't
check, Public record) and when it was checked. Absence of evidence is "Not
found", never an accusation; nothing is called verified and nothing is scored.

SEC EDGAR and Form D rows (filer, incorporation, the people listed, the year
formed) come from sec_identity.py through the same row function, as do the
financing history, the fundraising total beside the profile's prior raise,
and revenue evidence (sec_financing.py). Editing revenue or prior capital
changes the inputs hash, so the next request runs a fresh check.

One external check per business runs at most once per REUSE_WINDOW; later
requests in that window reuse it and are simply granted access to that report.
"""
import hashlib
import ipaddress
import json
import logging
import re
import unicodedata
from datetime import date, timedelta
from urllib.parse import urlparse

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from . import sec_identity
from .safe_fetch import FetchError, fetch_public_page
from .sec_financing import money

logger = logging.getLogger(__name__)

REUSE_WINDOW = timedelta(days=7)
# A check still marked pending after this long is assumed abandoned (a worker
# died) rather than shared with every later request forever.
PENDING_SHARE_WINDOW = timedelta(minutes=15)
CHECK_FAILED_MESSAGE = (
    "The company identity check did not finish. This is not a finding about "
    "the business. Please try checking again."
)


def extract_domain(url_or_domain):
    """Reduces a company_website URL (or a bare domain) to its host for WHOIS lookup."""
    if not url_or_domain:
        return None
    value = url_or_domain.strip()
    if not value:
        return None
    if '://' not in value:
        value = f'//{value}'
    try:
        host = (urlparse(value).hostname or '').rstrip('.')
    except ValueError:
        return None
    if host.startswith('www.'):
        host = host[len('www.'):]
    if not host or host == 'localhost' or host.endswith('.localhost'):
        return None
    try:
        ipaddress.ip_address(host)
        return None  # an IP address isn't a company domain
    except ValueError:
        return host


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
    The original domain-age report for one document's uploader, kept for
    uploaders with no business profile. Returns an unsaved report.
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


# --------------------------------------------------------------------------
# The business being checked
# --------------------------------------------------------------------------

def _describe(subject):
    """Where the subject's fields live, whichever side of the marketplace it is on."""
    from matchmaking.models import SellerApplication
    if isinstance(subject, SellerApplication):
        return {'field': 'seller_profile', 'source': 'Business-for-sale profile',
                'person_label': 'Owner', 'person': subject.seller_name,
                'revenue': subject.annual_revenue, 'revenue_is_annual': True, 'prior_raised': None}
    # A founder's "current revenue" has no stated period; a blank or zero prior raise is no claim.
    return {'field': 'founder_profile', 'source': 'Startup profile',
            'person_label': 'Founder', 'person': subject.founder_name,
            'revenue': subject.current_revenue, 'revenue_is_annual': False,
            'prior_raised': subject.prior_amount_raised or 0}


def _amount_input(value):
    return f'{value:.2f}' if value is not None else ''


def subject_for_document(document):
    """The business a document belongs to, or None when its uploader has no business profile."""
    user = document.uploaded_by
    founder = getattr(user, 'match_founder_profile', None)
    seller = getattr(user, 'match_seller_profile', None)
    if document.document_type == 'business_valuation':
        return seller or founder
    return founder or seller


def identity_inputs(subject):
    described = _describe(subject)
    return {
        'company_name': (subject.company_name or '').strip(),
        # The DERIVED jurisdiction, not the raw `geography` text, so a cosmetic
        # edit ('Denver, CO' -> 'Boulder, CO') does not invalidate a check and
        # spend a credit re-deriving the same answer -- while a correction that
        # changes which register is queried ('san diego' -> 'San Diego, CA')
        # does. This sits inside inputs_hash, which is what decides reuse.
        'jurisdiction': state_from_geography(getattr(subject, 'geography', '')),
        'website': (subject.company_website or '').strip(),
        'person_name': (described['person'] or '').strip(),
        'years_in_business': subject.years_in_business or 0,
        'revenue': _amount_input(described['revenue']),
        'prior_amount_raised': _amount_input(described['prior_raised']),
    }


def inputs_hash(subject):
    return hashlib.sha256(json.dumps(identity_inputs(subject), sort_keys=True).encode('utf-8')).hexdigest()


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------

_LEGAL_SUFFIXES = {
    'inc', 'incorporated', 'llc', 'l', 'c', 'ltd', 'limited', 'corp', 'corporation',
    'co', 'company', 'plc', 'lp', 'llp', 'pllc', 'gmbh',
}


def _normalize(text):
    text = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode('ascii').lower()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', text).split())


def _company_core(name):
    words = _normalize(name).split()
    while len(words) > 1 and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return ' '.join(words)


def _page_text(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or '', 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'template']):
        tag.decompose()
    parts = [soup.title.get_text(' ') if soup.title else '']
    for meta in soup.find_all('meta'):
        if (meta.get('property') or meta.get('name') or '').lower() in ('og:site_name', 'og:title', 'application-name', 'author'):
            parts.append(meta.get('content') or '')
    parts.append(soup.get_text(' '))
    return f" {_normalize(' '.join(parts))} "


from . import companyenrich, filed, filed_authority
from .jurisdiction import state_from_geography


def collect_findings(subject):
    """Consults the website and WHOIS for one business and returns its finding rows."""
    from .entity_verification_models import EntityVerificationReport as R

    described = _describe(subject)
    inputs = identity_inputs(subject)
    checked_at = timezone.now().isoformat()
    rows = []

    def add(check, claim, evidence_source, evidence, result, source_url=''):
        rows.append({
            'check': check, 'claim': claim, 'interlink_source': described['source'],
            'evidence_source': evidence_source, 'evidence': evidence, 'result': result,
            'source_url': source_url, 'checked_at': checked_at,
        })

    website = inputs['website']
    company_claim = f"Company name: {inputs['company_name']}"
    person_claim = (f"{described['person_label']}: {inputs['person_name']}" if inputs['person_name']
                    else f"{described['person_label']}: not on the profile")
    years = inputs['years_in_business']
    claimed_year = date.today().year - years if years else None
    founding_claim = (f"Founded around {claimed_year} ({years} years in business)" if claimed_year
                      else 'Founding year: not on the profile')

    revenue = described['revenue']
    if described['revenue_is_annual']:
        revenue_claim = f'Annual revenue: {money(revenue)}' if revenue is not None else 'Annual revenue: not on the profile'
    else:
        revenue_claim = (f'Current revenue: {money(revenue)} (period not stated on the profile)' if revenue is not None
                         else 'Current revenue: not on the profile')
    prior_raised = described['prior_raised']
    if prior_raised is None:
        capital_claim = 'Prior capital raised: not on the profile'
    elif prior_raised > 0:
        capital_claim = f'Prior capital raised: {money(prior_raised)}'
    else:
        capital_claim = 'Prior capital raised: not claimed on the profile'

    def add_filed_rows():
        # State business registration, via Filed. Runs on EVERY path: a company
        # can be registered without a website, and the query is by name, so the
        # no-website branch has no reason to skip it.
        #
        # GATED ON SOURCE AUTHORITY, not on getting an answer. A `state=WA`
        # query returns IRS Exempt Organizations data under a federal label, so
        # "Filed returned something" is not "a state register says so" -- see
        # zelda_api/filed.py. Absence is never a finding: a name we spelled
        # differently is the ordinary reason for a miss.
        outcome, detail = filed.company_record(
            inputs['company_name'], state=inputs['jurisdiction'])

        # Only NO_RECORD is silence from the register, and silence is the
        # ordinary state of a name we spelled differently -- it never earns a
        # line in an investor-facing report. The other two are failures to
        # resolve the QUERY, which are worth saying out loud because a reader
        # would otherwise assume the business was checked and cleared.
        # NO_JURISDICTION is silent for the same reason as UNCONFIGURED: nothing
        # was asked. Before it existed this path sent a cross-state search that
        # timed out into UNAVAILABLE, so the report reads exactly as it did --
        # without the 5 credits and the 20-second wait.
        if outcome in (filed.NO_RECORD, filed.UNAVAILABLE, filed.UNCONFIGURED, filed.NO_JURISDICTION):
            return
        if outcome == filed.UNRESOLVED:
            add('business_registration', company_claim,
                'Business registration record',
                'Business records were returned for this name, but none matched '
                'the company name exactly, so no record could be attributed to '
                'this business. This is not evidence about whether it is '
                'registered.',
                R.COULDNT_CHECK)
            return
        if outcome == filed.AMBIGUOUS:
            add('business_registration', company_claim,
                'Business registration record',
                'More than one registered business matches this name exactly, so '
                'none was attributed to this company. A company can also be '
                'registered under one name in several states.',
                R.COULDNT_CHECK)
            return
        source = (detail.get('meta') or {}).get('source')
        if not filed.is_state_registration_source(source):
            # Measured in 37 of 51 jurisdictions. Naming the substitution keeps
            # the row from reading as though a state register had answered.
            add('business_registration', company_claim,
                'Business registration record',
                'A business record was returned for this name, but it came from '
                '%s rather than a state register of companies, so it is not '
                'evidence about whether this business is registered.'
                % (source or 'an unnamed source'),
                R.COULDNT_CHECK)
            return

        record_state = (detail.get('data') or {}).get('state')
        evidence = filed.describe_record(detail)
        if record_state and filed_authority.coverage_for(record_state) == 'partial':
            evidence += (' This register is only partly carried by the source '
                         'used, so a business missing from it may still be '
                         'registered there.')
        add('business_registration', company_claim, source, evidence, R.PUBLIC_RECORD)

        # Officers exist in FL (10/10) and TX (8/10) and in none of the other
        # eleven registrars. Present officers are used wherever they come from;
        # what the capability gates is the INFERENCE FROM ABSENCE. Reporting
        # that Delaware does not list a founder, when Delaware lists no officers
        # for anyone, would be a fabricated adverse finding about a person.
        officers = filed.officer_names(detail)
        if not officers and not filed.officer_absence_is_meaningful(detail):
            return
        if officers and inputs['person_name']:
            named = _normalize(inputs['person_name'])
            matched = [o for o in officers if _normalize(o) == named]
            add('officer_of_record', person_claim, source,
                '%s is listed as an officer of record.' % inputs['person_name'] if matched else
                'The register lists %s as officer%s of record, and does not list %s. '
                'Officers of record are not the same list as a company\'s founders, '
                'so this is not evidence that the person is unconnected to the business.' % (
                    ', '.join(officers[:4]), '' if len(officers) == 1 else 's',
                    inputs['person_name']),
                R.MATCHES if matched else R.PUBLIC_RECORD)

    def add_sec_rows():
        # A business with no website can still have SEC filings, so this runs on every path.
        sec_identity.sec_findings(
            add, company_name=inputs['company_name'], company_claim=company_claim,
            person_name=inputs['person_name'], person_claim=person_claim,
            claimed_year=claimed_year, founding_claim=founding_claim,
            capital_claim=capital_claim, revenue_claim=revenue_claim,
            revenue_amount=revenue, revenue_is_annual=described['revenue_is_annual'],
        )

    if not website:
        no_site = 'The profile has no website to check.'
        add('website', 'Website: not on the profile', 'Company website', no_site, R.NOT_APPLICABLE)
        add('company_name', company_claim, 'Company website', no_site, R.NOT_APPLICABLE)
        add('person_name', person_claim, 'Company website', no_site, R.NOT_APPLICABLE)
        add('founding_year', founding_claim, 'Domain registration', no_site, R.NOT_APPLICABLE)
        add_filed_rows()
        add_sec_rows()
        return rows

    # 1. The website itself, fetched only through the public-address checks.
    page = None
    try:
        page = fetch_public_page(website if '://' in website else f'https://{website}')
        add('website', f'Website: {website}', 'Company website',
            f'The site loaded at {page.final_url}.', R.MATCHES, page.final_url)
    except FetchError as error:
        add('website', f'Website: {website}', 'Company website', error.reason, R.COULDNT_CHECK)

    # 2 and 3. The company and person named on that site.
    if page is None:
        unread = "The website couldn't be read."
        add('company_name', company_claim, 'Company website', unread, R.COULDNT_CHECK)
        add('person_name', person_claim, 'Company website', unread, R.COULDNT_CHECK)
    else:
        text = _page_text(page.text)
        core = _company_core(inputs['company_name'])
        if len(core) < 3:
            add('company_name', company_claim, 'Company website',
                'The company name is too short to search for reliably.', R.NOT_APPLICABLE)
        elif f' {core} ' in text:
            add('company_name', company_claim, 'Company website',
                'The company name appears on the website.', R.MATCHES, page.final_url)
        else:
            add('company_name', company_claim, 'Company website',
                'The company name does not appear on the page that loaded.', R.NOT_FOUND, page.final_url)

        person = _normalize(inputs['person_name'])
        if len(person.split()) < 2:
            add('person_name', person_claim, 'Company website',
                'A full name is needed to search for this person.', R.NOT_APPLICABLE)
        elif f' {person} ' in text:
            add('person_name', person_claim, 'Company website',
                'This name appears on the website.', R.MATCHES, page.final_url)
        else:
            add('person_name', person_claim, 'Company website',
                'This name does not appear on the page that loaded.', R.NOT_FOUND, page.final_url)

    # 4. The domain's age against the claimed founding year.
    domain = extract_domain(website)
    if not domain:
        add('founding_year', founding_claim, 'Domain registration',
            "The website address isn't a public domain name.", R.COULDNT_CHECK)
    else:
        registered, lookup_error = lookup_domain_creation_date(domain)
        lookup_url = f'https://lookup.icann.org/en/lookup?name={domain}'
        if not registered:
            add('founding_year', founding_claim, 'Domain registration',
                lookup_error or 'No registration date was found for this domain.', R.COULDNT_CHECK)
        elif claimed_year is None:
            add('founding_year', founding_claim, 'Domain registration',
                f"{domain} was registered in {registered:%B %Y}.", R.PUBLIC_RECORD, lookup_url)
        elif registered.year - claimed_year >= 2:
            gap = registered.year - claimed_year
            add('founding_year', founding_claim, 'Domain registration',
                f"{domain} was registered in {registered:%B %Y}, {gap} years after the claimed founding year. "
                "A company can move to a newer domain, so this is worth asking about.",
                R.DOESNT_MATCH, lookup_url)
        elif claimed_year - registered.year >= 2:
            # An older domain neither contradicts nor confirms the founding
            # year -- companies buy existing domains -- so it's reported, not matched.
            gap = claimed_year - registered.year
            add('founding_year', founding_claim, 'Domain registration',
                f"{domain} was registered in {registered:%B %Y}, {gap} years before the claimed founding year. "
                "The company may have acquired an existing domain.",
                R.PUBLIC_RECORD, lookup_url)
        else:
            add('founding_year', founding_claim, 'Domain registration',
                f"{domain} was registered in {registered:%B %Y}, in line with the claimed founding year.",
                R.MATCHES, lookup_url)

    # 5. An independent commercial footprint, from CompanyEnrich.
    #
    # CORROBORATION ONLY. This is a B2B aggregator, not a registry: its own
    # docs describe the inputs as public databases, partner feeds, user-
    # submitted data and scraped web pages, with no per-field provenance. The
    # first record we pulled put Stripe in the Netherlands with a South San
    # Francisco postal code and called it "Stripe, LLC". So only four fields
    # are carried (see zelda_api/companyenrich.py), and absence NEVER becomes
    # a finding: a two-year-old private LLC missing from a sales database is
    # the ordinary case, not evidence about the company.
    footprint = companyenrich.company_footprint(website)
    status = companyenrich.lookup_status(website)
    if status == companyenrich.FOUND and footprint:
        detail = []
        if footprint.get('founded_year'):
            detail.append('founded %s' % footprint['founded_year'])
        if footprint.get('industry'):
            detail.append(str(footprint['industry']).lower())
        described_as = ' (%s)' % ', '.join(detail) if detail else ''
        add('commercial_footprint', f"Website: {website}",
            'CompanyEnrich (aggregated business data)',
            'An independent business record is associated with %s%s. This is '
            'aggregated commercial data, not a government registry, so it '
            'corroborates that the business has a public footprint rather '
            'than establishing its legal identity.' % (
                footprint.get('domain') or website, described_as),
            R.PUBLIC_RECORD)
    elif status == companyenrich.NO_RECORD:
        add('commercial_footprint', f"Website: {website}",
            'CompanyEnrich (aggregated business data)',
            'No business record was found for this domain. Aggregated '
            'commercial databases do not cover every company, and smaller or '
            'newer businesses are routinely absent, so this is not evidence '
            'about whether the business exists.',
            R.COULDNT_CHECK)
    elif status == companyenrich.UNAVAILABLE:
        add('commercial_footprint', f"Website: {website}",
            'CompanyEnrich (aggregated business data)',
            'The business-data service could not be reached, so this check '
            'did not complete.',
            R.COULDNT_CHECK)
    # UNCONFIGURED adds nothing: the integration being off is not evidence and
    # should not occupy a line in an investor-facing report.

    add_filed_rows()
    add_sec_rows()
    return rows


# --------------------------------------------------------------------------
# Requesting, reusing and running a check
# --------------------------------------------------------------------------

def _find_or_start(subject, document=None):
    """
    The report to use for this business right now: a finished check from the
    reuse window, a check still running, or a new pending report. Returns
    (report, created). Callers decide whether a new report runs inline or in a worker.
    """
    from .entity_verification_models import EntityVerificationReport as R

    field = _describe(subject)['field']
    digest = inputs_hash(subject)
    now = timezone.now()
    # Lock the business row so two simultaneous requests can't both start a check.
    type(subject).objects.select_for_update().filter(pk=subject.pk).exists()
    same_inputs = R.objects.filter(**{field: subject}, inputs_hash=digest)
    same_inputs.filter(status=R.PENDING, created_at__lt=now - PENDING_SHARE_WINDOW).update(status=R.FAILED)
    report = (
        same_inputs.filter(status=R.COMPLETE, checked_at__gte=now - REUSE_WINDOW).order_by('-checked_at').first()
        or same_inputs.filter(status=R.PENDING, created_at__gte=now - PENDING_SHARE_WINDOW).order_by('-created_at').first()
    )
    if report is not None:
        return report, False
    return R.objects.create(**{field: subject}, document=document, inputs_hash=digest, status=R.PENDING), True


class IdentityCheckLimited(Exception):
    """
    Too many new checks, per user or across the platform. `retry_phrase` is
    the wording the sign-in limits use and is safe to show the requester.
    """

    def __init__(self, scope, identifier):
        from accounts.rate_limits import retry_phrase

        self.scope = scope
        self.retry_phrase = retry_phrase(scope, identifier)
        super().__init__(f'identity check limit reached ({scope})')


def request_identity_check(subject, user, document=None, counts_against_limits=True):
    """
    An investor, buyer or staff member asks about a business. Reuses a recent
    check or queues a new one, and grants `user` access to that report.

    A new check is expensive -- about 45 SEC requests, a website fetch and a
    WHOIS lookup -- so it counts against this user's daily allowance and the
    platform's hourly ceiling (accounts/rate_limits.py), and raises
    IdentityCheckLimited when either is reached. A reuse runs nothing and
    releases its slot. Staff are exempt, and so is the check that comes with a
    paid analysis: pass counts_against_limits=False, as the credit already
    paid for it.
    """
    from accounts import rate_limits
    from .entity_verification_models import EntityReportAccessGrant
    from .entity_verification_tasks import run_entity_check

    counted = (
        counts_against_limits and user is not None
        and user.is_authenticated and not user.is_staff
    )
    tokens = []
    if counted:
        tokens, refused = rate_limits.reserve_all([
            ('identity_check_user', str(user.id)),
            ('identity_check_global', rate_limits.GLOBAL_KEY),
        ])
        if refused is not None:
            raise IdentityCheckLimited(*refused)

    with transaction.atomic():
        report, created = _find_or_start(subject, document)
        if created:
            def enqueue():
                try:
                    run_entity_check.delay(report.id)
                except Exception:
                    mark_identity_check_failed(report)
                    logger.exception('Could not queue company identity check %s', report.id)
            transaction.on_commit(enqueue)
        if user is not None and user.is_authenticated:
            EntityReportAccessGrant.objects.get_or_create(report=report, user=user)

    if counted and not created:
        # Reusing a report inside the 7-day window runs no check at all.
        for token in tokens:
            rate_limits.release(token)
    return report, created


def identity_check_now(subject, document=None):
    """The owner's Verify button, already inside a worker: reuse a recent check or run one here."""
    with transaction.atomic():
        report, created = _find_or_start(subject, document)
    if created:
        run_identity_check(report)
    return report


def run_identity_check(report):
    from .entity_verification_models import EntityVerificationReport as R

    refresh_identity_check_status(report)
    if report.status != R.PENDING:
        return report
    try:
        subject = report.subject
        if subject is None:
            raise ValueError('Company identity check has no business subject')
        findings = collect_findings(subject)
        digest = inputs_hash(subject)
        # A late worker must not overwrite an expired or failed attempt.
        R.objects.filter(pk=report.pk, status=R.PENDING).update(
            findings=findings, inputs_hash=digest, checked_at=timezone.now(), status=R.COMPLETE,
        )
        report.refresh_from_db()
    except Exception:
        mark_identity_check_failed(report)
        logger.exception('Company identity check %s failed', report.id)
        raise
    return report


def mark_identity_check_failed(report):
    """Record a failed attempt without turning it into evidence or a check date."""
    from .entity_verification_models import EntityVerificationReport as R
    R.objects.filter(pk=report.pk, status=R.PENDING).update(status=R.FAILED)
    report.refresh_from_db()
    return report


def refresh_identity_check_status(report):
    """Recover an abandoned queued/running check when an authorized viewer reads it."""
    from .entity_verification_models import EntityVerificationReport as R
    if report.status == R.PENDING:
        R.objects.filter(
            pk=report.pk, status=R.PENDING,
            created_at__lt=timezone.now() - PENDING_SHARE_WINDOW,
        ).update(status=R.FAILED)
        report.refresh_from_db()
    return report


# --------------------------------------------------------------------------
# Who sees what
# --------------------------------------------------------------------------

def can_view_entity_report(user, report):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user == report.owner:
        return True
    return report.access_grants.filter(user=user).exists()


def latest_viewable_report(user, document):
    """The newest Entity Integrity report for this document's business that `user` may see."""
    from .entity_verification_models import EntityVerificationReport

    if not user or not user.is_authenticated:
        return None
    subject = subject_for_document(document)
    scope = Q(document=document)
    if subject is not None:
        scope |= Q(**{_describe(subject)['field']: subject})
    reports = EntityVerificationReport.objects.filter(scope).order_by('-created_at', '-id')
    if user.is_staff or user == document.uploaded_by:
        report = reports.first()
    else:
        report = reports.filter(access_grants__user=user).first()
    return refresh_identity_check_status(report) if report else None


def can_request_identity_check(user, subject):
    """Investors, buyers and staff looking at a startup they can see. The owner uses Verify."""
    from matchmaking.models import Application, founder_is_visible_to

    if not user or not user.is_authenticated or not isinstance(subject, Application):
        return False
    if user == subject.user or not founder_is_visible_to(user, subject):
        return False
    return bool(
        user.is_staff
        or getattr(user, 'match_investor_profile', None)
        or getattr(user, 'accounts_investor_profile', None)
        or getattr(user, 'match_buyer_profile', None)
    )


def display_rows(report):
    from .entity_verification_models import EntityVerificationReport as R
    return [dict(row, result_label=R.RESULT_LABELS.get(row.get('result'), '')) for row in (report.findings or [])]
