"""
Filed: business-entity corroboration, gated on source authority.

Deliberately NOT named for the Secretary of State, because a state query is not
necessarily state-registration evidence. Measured on a trial key (2026-10-01):
`state=WA` returned `meta.source = "IRS Exempt Organizations Business Master
File"` for Costco, Microsoft, Starbucks and Nordstrom, with `type` values
including `FCC Licensee` and `Sole Proprietorship`. Washington has no state
registration coverage and Filed answers the state query with blended federal
data under one federal label. A module named `secretary_of_state` would have
asserted in its own name the thing this one has to check.

The hierarchy this module keeps:

    SEC                         authoritative for SEC registrant facts
    a real state authority      corroborates state registration facts
    a federal substitution      data, but NOT state-registration evidence
    an officer record from a
      qualifying state source   corroborates officer / agent facts

Filed is the retrieval path; the state is the authority. Provenance therefore
reads "Florida Division of Corporations (Sunbiz)", never "Filed".

THE DOCS ARE WRONG IN FOUR WAYS, so this is written against the observed API:
the search parameter is `name` (documented `q` returns 400 `invalid_params`),
detail is `/entity/<bare uuid>` (documented `/entity/FL:F05000002957` returns
404), the envelope is `{data, meta}` (not `{results, count}`), and `lastUpdated`
sits in `meta` on detail rather than in `data`.

TWO STEPS, NOT ONE, and the gate is what forces it. Neither Application nor
SellerApplication carries any geographic field, so the query has to be
nationwide by name -- which sets `meta.source = "Cross-state search"`, not a
state authority, so no finding may rest on it. `/entity/<uuid>` restores the
real authority, the record date, `stateEntityId`, officers and agent. The
flow that satisfies the gate is also the flow that yields the officers.

A HIT IS A CANDIDATE. Nationwide search is a fuzzy token match: "Publix Super
Markets" ranked `ALLAN, JOHN S DBA PUBLIX SUPER MARKET` above `PUBLIX SUPER
MARKETS, INC.`, and "Coastal 321" returned `321 COASTAL CLEANERS LLC`. So
selection is an exact normalised legal-name match, or nothing -- taking the top
hit would attribute one company's officers to another.
"""
import logging
import re
from datetime import datetime, timezone

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SEARCH_ENDPOINT = 'https://filed.dev/api/v1/search'
ENTITY_ENDPOINT = 'https://filed.dev/api/v1/entity/%s'
TIMEOUT_SECONDS = 20

# Lookup outcomes. Four, not two: "no record", "could not look" and "the
# integration is off" are different states and only the first says anything
# about the company -- and even then, very little.
FOUND = 'found'
NO_RECORD = 'no_record'
UNAVAILABLE = 'unavailable'
UNCONFIGURED = 'unconfigured'

# What a name-only (nationwide) search reports as its source. A search mode, not
# a registry.
CROSS_STATE_SOURCE = 'Cross-state search'

# Recognised state registration authorities, DECLARED rather than pattern
# matched. A pattern would have accepted "IRS Exempt Organizations Business
# Master File" the moment someone wrote a rule like "contains a state name", and
# a default is not a decision -- it is the omission source_capabilities.py
# exists to prevent. Each entry below was observed answering a state query with
# genuine registration data. Adding a state means probing that state first:
# "all 50 states" means every state code returns something.
STATE_REGISTRATION_SOURCES = frozenset({
    'Florida Division of Corporations (Sunbiz)',
    'Delaware DOS',
    'California SOS',
    'Texas SOS',
    'New York Department of State',
})

# Sources seen standing in for a state registry. Listed explicitly so the
# substitution is visible in the source, not merely excluded by omission.
KNOWN_NON_STATE_SOURCES = frozenset({
    'IRS Exempt Organizations Business Master File',
    CROSS_STATE_SOURCE,
})

# How fresh a record must be before it may CONTRADICT a company's own account.
# Measured staleness ran from same-day (NY) to roughly six months (FL), and the
# docs' "real-time... not stale caches" is false. A record of any age can still
# support a statement of what the registry said and when; only a recent one may
# be used against a business, because a company that reinstated last month would
# otherwise be reported as dissolved.
CONTRADICTION_MAX_AGE_DAYS = 120

# Statuses that describe an entity no longer in good standing. Only consulted
# when `may_contradict` already holds.
DISSOLVED_STATUSES = ('inactive', 'dissolved', 'administratively dissolved',
                      'revoked', 'void', 'forfeited', 'withdrawn', 'cancelled',
                      'canceled', 'terminated', 'expired')


def _normalise_name(name):
    """Case, punctuation and spacing folded; legal suffixes KEPT.

    Suffixes are meaning here, not noise: "Acme AI Inc" and "Acme AI LLC" are
    different registrations. Dropping them is how a fuzzy match becomes a
    confident wrong answer.
    """
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', (name or '').lower())).strip()


def classify(status_code, body):
    """
    FOUND / NO_RECORD / UNAVAILABLE for one response.

    401 is deliberately UNAVAILABLE rather than NO_RECORD: a revoked or expired
    key would otherwise turn a billing event into findings about companies.
    """
    if status_code != 200 or not isinstance(body, dict):
        return UNAVAILABLE
    return FOUND if (body.get('data') or []) else NO_RECORD


def is_state_registration_source(source):
    """Whether this source may ground a statement about state registration."""
    return bool(source) and source in STATE_REGISTRATION_SOURCES


def _meta(detail):
    return (detail or {}).get('meta') or {}


def _data(detail):
    data = (detail or {}).get('data')
    if isinstance(data, list):
        return data[0] if data else {}
    return data or {}


def record_age_days(detail, now=None):
    """
    Age of the record in whole days, or None when undated.

    Read from `meta.lastUpdated`: on detail responses the field is in `meta`,
    and a `data.lastUpdated` read returns None. Compared as DATES, because a
    record date is a date and a part-day should not round an answer down.
    """
    stamp = _meta(detail).get('lastUpdated')
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
    except ValueError:
        return None
    now = now or datetime.now(timezone.utc)
    return (now.date() - parsed.date()).days


def may_contradict(detail, now=None):
    """
    Whether this record is admissible AGAINST the company's own account.

    Three conditions, all required: a recognised state authority, a date at all,
    and a date inside the window. Freshness is not authority -- the Washington
    payload was one day old and is still inadmissible.
    """
    if not is_state_registration_source(_meta(detail).get('source')):
        return False
    age = record_age_days(detail, now=now)
    return age is not None and age <= CONTRADICTION_MAX_AGE_DAYS


def candidate_for(rows, company_name):
    """
    The one row whose legal name matches exactly, or None.

    None when nothing matches and also when SEVERAL do: a name registered in two
    states is not resolved by name, and choosing between them here would be an
    identity decision this module has no standing to make.
    """
    wanted = _normalise_name(company_name)
    if not wanted:
        return None
    exact = [row for row in (rows or []) if _normalise_name(row.get('name')) == wanted]
    return exact[0] if len(exact) == 1 else None


def officer_names(detail):
    """
    Officer names, but only from a qualifying state source.

    Officer corroboration is the strongest thing this provider offers -- nothing
    else in the suite can speak to a named founder of a private company -- which
    makes it the most damaging to take from the wrong dataset.
    """
    if not is_state_registration_source(_meta(detail).get('source')):
        return []
    return [o.get('name') for o in (_data(detail).get('officers') or []) if o.get('name')]


def registered_agent(detail):
    """The registered agent dict from a qualifying source, else None."""
    if not is_state_registration_source(_meta(detail).get('source')):
        return None
    agent = _data(detail).get('registeredAgent')
    return agent if isinstance(agent, dict) and agent.get('name') else None


def describe_record(detail):
    """
    What the registry said, and when it last said it.

    Names the state authority and never this provider: Filed retrieves, the
    state establishes. The record date is part of the sentence because a status
    without one is a claim about today that the data cannot support.
    """
    data = _data(detail)
    source = _meta(detail).get('source') or 'an unnamed source'
    bits = ['%s lists %s' % (source, data.get('name') or 'this entity')]
    if data.get('type'):
        bits.append('as a %s' % data['type'])
    if data.get('status'):
        bits.append('in %s standing' % data['status'] if data['status'] == 'Active'
                    else 'with status %s' % data['status'])
    sentence = ' '.join(bits)
    if data.get('formedDate'):
        sentence += ', formed %s' % data['formedDate']
    stamp = _meta(detail).get('lastUpdated')
    if stamp:
        sentence += '. Record last updated %s' % str(stamp)[:10]
    age = record_age_days(detail)
    if age is not None and age > CONTRADICTION_MAX_AGE_DAYS:
        sentence += (', so it describes the register as of that date rather '
                     'than today')
    return sentence + '.'


def status_is_dissolved(detail):
    return (_data(detail).get('status') or '').strip().lower() in DISSOLVED_STATUSES


# --------------------------------------------------------------------------
# The two HTTP calls. Patched wholesale in tests; nothing else here reaches out.
# --------------------------------------------------------------------------
def _key():
    return getattr(settings, 'FILED_API_KEY', '') or ''


def _get(url, **params):
    try:
        response = requests.get(
            url, params=params or None,
            headers={'Authorization': 'Bearer %s' % _key(),
                     'accept': 'application/json'},
            timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.warning('[Filed] %s for %s', type(exc).__name__, url)
        return None, None
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def _search(company_name, state=None):
    """
    Name search. One credit.

    With a state the response names the real registrar and ranks the exact
    company higher; without one it is a cross-state search whose `meta.source`
    is "Cross-state search" and whose ranking is measurably worse -- nationwide
    put `ALLAN, JOHN S DBA PUBLIX SUPER MARKET` above `PUBLIX SUPER MARKETS,
    INC.`. The parameter is OMITTED rather than passed as None, because its
    absence is what selects the nationwide mode.
    """
    params = {'name': company_name}
    if state:
        params['state'] = state
    return _get(SEARCH_ENDPOINT, **params)[1]


def _detail(entity_id):
    """One entity by its bare UUID. One to three credits."""
    return _get(ENTITY_ENDPOINT % entity_id)[1]


def company_record(company_name, state=None):
    """
    (outcome, detail) for one company name, optionally scoped to a state.

    Two steps either way: a cross-state search carries no state authority, and
    even a state-scoped one is only a search. The authoritative record always
    comes from the detail call, whose `meta.source` is the only field that says
    which registrar answered -- measured, a `state=GA` query returns rows
    stamped `GA` sourced from the IRS Exempt Organizations file, so neither the
    requested state nor `data[].state` is evidence of a state register.

    `state` narrows and ranks; it never decides identity or authority.
    """
    if not _key():
        return UNCONFIGURED, None
    if not (company_name or '').strip():
        return NO_RECORD, None

    body = _search(company_name, state=state)
    if not isinstance(body, dict) or body.get('error'):
        return UNAVAILABLE, None
    if not (body.get('data') or []):
        return NO_RECORD, None

    candidate = candidate_for(body.get('data') or [], company_name)
    if candidate is None:
        # Rows came back but none is this company, or several are. Absence of a
        # confident match is not absence of the company.
        return NO_RECORD, None

    detail = _detail(candidate.get('id'))
    if not isinstance(detail, dict) or not _data(detail):
        return UNAVAILABLE, None
    return FOUND, detail
