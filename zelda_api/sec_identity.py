# zelda_api/sec_identity.py
"""
SEC EDGAR and Form D evidence for Entity Integrity.

A company's name is looked up with no form-type filter. The older Truth Delta
resolver (truth_delta_sources.SECFilingsIntegration) searches only 10-K filers,
which misses a private company whose only filing is a Form D -- the notice
most startups raising a private round file. The lookup has two steps:

1. EDGAR company search, with the exact name and then without its legal
   suffix. When exactly one company matches, EDGAR returns its record with the
   real name. When several match, it garbles their names, so step 1 can't
   choose between them.
2. EDGAR full-text search, which keeps filer names intact. On its own it
   misses widely mentioned companies: a search for "Apple" returns other
   companies' filings that mention Apple, which is why step 1 comes first.

When exactly one filer's name matches (legal suffixes like Inc. and LLC
ignored), its company record and newest Form D add rows through the same
`add` function the website checks use:

- sec_filer          Matches / Not found / Couldn't check (shared name, SEC down)
- sec_incorporation  Public record: entity type, jurisdiction, year formed
- sec_person         Matches / Not found against the Form D's related persons
- sec_founding_year  Matches / Doesn't match against the year formed

Filings also carry street addresses and phone numbers; nothing here reads them.
Every request declares Interlink's user agent, has a timeout, and waits at
least MIN_INTERVAL_SECONDS after the previous one, per SEC's fair-access policy
(at most 10 requests a second). Form D XML is parsed with entity resolution,
DTD loading and network access all off.
"""
import logging
import re
import threading
import time
from dataclasses import dataclass, field

import requests
from lxml import etree

logger = logging.getLogger(__name__)

COMPANY_SEARCH_URL = 'https://www.sec.gov/cgi-bin/browse-edgar'
SEARCH_URL = 'https://efts.sec.gov/LATEST/search-index'
COMPANY_RECORD_URL = 'https://data.sec.gov/submissions/CIK{cik}.json'
FILING_FOLDER_URL = 'https://www.sec.gov/Archives/edgar/data/{cik_number}/{accession_digits}/'
COMPANY_PAGE_URL = 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}'
USER_AGENT = 'Interlink Foundry Entity Integrity (contact: admin@interlinkfoundry.com)'
TIMEOUT_SECONDS = 10
MIN_INTERVAL_SECONDS = 0.12
MAX_FILING_BYTES = 2 * 1024 * 1024
FORM_D_TYPES = {'D', 'D/A'}

UNREACHABLE = "SEC EDGAR couldn't be reached."

_request_lock = threading.Lock()
_last_request_at = 0.0

_DISPLAY_NAME_CIK = re.compile(r'\s*\(CIK\s*\d+\)\s*$', re.IGNORECASE)
_TRAILING_LEGAL_SUFFIX = re.compile(
    r'[\s,]+(inc|incorporated|llc|l\.l\.c|ltd|limited|corp|corporation|co|company|plc|lp|llp|pllc)\.?\s*$',
    re.IGNORECASE,
)
_XML_PARSER = etree.XMLParser(
    resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False, remove_comments=True,
)


class SecUnavailable(Exception):
    """SEC couldn't answer usefully. The message is safe to show a user."""


@dataclass
class FilerLookup:
    status: str  # 'found' | 'not_found' | 'ambiguous'
    cik: str = None
    name: str = None


@dataclass
class FormD:
    entity_name: str = None
    entity_type: str = None
    jurisdiction: str = None
    year_of_incorporation: int = None
    over_five_years: bool = False
    people: list = field(default_factory=list)  # [(first + last name, [relationships])]


def _get(url, params=None):
    global _last_request_at
    with _request_lock:
        wait = _last_request_at + MIN_INTERVAL_SECONDS - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()
    try:
        response = requests.get(url, params=params, headers={'User-Agent': USER_AGENT}, timeout=TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as error:
        logger.warning(f"SEC request failed for {url}: {error}")
        raise SecUnavailable(UNREACHABLE)
    if response.status_code != 200:
        logger.warning(f"SEC request to {url} answered {response.status_code}")
        raise SecUnavailable(UNREACHABLE)
    return response


def _json(response):
    try:
        return response.json()
    except ValueError:
        raise SecUnavailable(UNREACHABLE)


def _search_phrase(company_name):
    phrase = (company_name or '').replace('"', ' ').strip()
    while True:
        shorter = _TRAILING_LEGAL_SUFFIX.sub('', phrase).strip()
        if shorter == phrase or not shorter:
            return phrase
        phrase = shorter


def _single_company(name):
    """EDGAR company search: (cik, conformed name) when exactly one company comes back, otherwise None."""
    response = _get(COMPANY_SEARCH_URL, params={
        'action': 'getcompany', 'company': name, 'owner': 'include', 'count': '10', 'output': 'atom',
    })
    try:
        root = etree.fromstring(response.content, parser=_XML_PARSER)
    except (etree.XMLSyntaxError, ValueError):
        return None
    # One company: a top-level company-info. Several: entries, whose names EDGAR garbles.
    info = root.find('{*}company-info')
    if info is None:
        return None
    cik = (info.findtext('{*}cik') or '').strip()
    conformed_name = (info.findtext('{*}conformed-name') or '').strip()
    return (cik.zfill(10), conformed_name) if cik and conformed_name else None


def find_sec_filer(company_name):
    """The one EDGAR filer whose name matches, or why there isn't one."""
    from .entity_verification import _company_core

    wanted = _company_core(company_name)

    # 1. A company EDGAR can name on its own: exact name first, then without the legal suffix.
    for name in dict.fromkeys(filter(None, [(company_name or '').strip(), _search_phrase(company_name)])):
        single = _single_company(name)
        if single and _company_core(single[1]) == wanted:
            return FilerLookup('found', cik=single[0], name=single[1])

    # 2. Several companies share the name (or none matched): full-text search keeps filer names intact.
    response = _get(SEARCH_URL, params={'q': f'"{_search_phrase(company_name)}"'})
    hits = ((_json(response) or {}).get('hits') or {}).get('hits') or []

    matches = {}
    for hit in hits:
        source = hit.get('_source') or {}
        for cik, display_name in zip(source.get('ciks') or [], source.get('display_names') or []):
            name = _DISPLAY_NAME_CIK.sub('', display_name or '').strip()
            if cik and _company_core(name) == wanted:
                matches.setdefault(str(cik).zfill(10), name)

    if not matches:
        return FilerLookup('not_found')
    if len(matches) > 1:
        return FilerLookup('ambiguous')
    cik, name = next(iter(matches.items()))
    return FilerLookup('found', cik=cik, name=name)


def company_record(cik):
    return _json(_get(COMPANY_RECORD_URL.format(cik=str(cik).zfill(10))))


def latest_form_d(record):
    """{'accession', 'filing_date'} for the newest Form D or amendment, or None."""
    recent = ((record or {}).get('filings') or {}).get('recent') or {}
    newest = None
    for accession, filing_date, form in zip(
            recent.get('accessionNumber') or [], recent.get('filingDate') or [], recent.get('form') or []):
        if form in FORM_D_TYPES and (newest is None or filing_date > newest['filing_date']):
            newest = {'accession': accession, 'filing_date': filing_date}
    return newest


def _filing_folder(cik, accession):
    return FILING_FOLDER_URL.format(cik_number=int(cik), accession_digits=accession.replace('-', ''))


def filing_index_url(cik, accession):
    return f'{_filing_folder(cik, accession)}{accession}-index.htm'


def fetch_form_d(cik, accession):
    response = _get(f'{_filing_folder(cik, accession)}primary_doc.xml')
    if len(response.text or '') > MAX_FILING_BYTES:
        raise SecUnavailable("The Form D filing couldn't be read.")
    return parse_form_d(response.text)


def parse_form_d(xml_text):
    try:
        data = xml_text.encode('utf-8') if isinstance(xml_text, str) else xml_text
        root = etree.fromstring(data, parser=_XML_PARSER)
    except (etree.XMLSyntaxError, ValueError):
        raise SecUnavailable("The Form D filing couldn't be read.")

    def text(parent, path):
        node = parent.find(path) if parent is not None else None
        value = node.text if node is not None else None
        return value.strip() if isinstance(value, str) and value.strip() else None

    issuer = root.find('{*}primaryIssuer')
    year_block = issuer.find('{*}yearOfInc') if issuer is not None else None
    year_text = text(year_block, '{*}value')

    people = []
    for info in root.iterfind('{*}relatedPersonsList/{*}relatedPersonInfo'):
        name = ' '.join(part for part in (
            text(info, '{*}relatedPersonName/{*}firstName'), text(info, '{*}relatedPersonName/{*}lastName'),
        ) if part)
        if not name:
            continue
        roles = [role.text.strip() for role in info.iterfind('{*}relatedPersonRelationshipList/{*}relationship')
                 if isinstance(role.text, str) and role.text.strip()]
        people.append((name, roles))

    return FormD(
        entity_name=text(issuer, '{*}entityName'),
        entity_type=text(issuer, '{*}entityType'),
        jurisdiction=text(issuer, '{*}jurisdictionOfInc'),
        year_of_incorporation=int(year_text) if year_text and year_text.isdigit() else None,
        over_five_years=(text(year_block, '{*}overFiveYears') or '').lower() == 'true',
        people=people,
    )


def sec_findings(add, *, company_name, company_claim, person_name, person_claim, claimed_year, founding_claim):
    """Adds the SEC rows for one business through entity_verification.collect_findings's `add`."""
    from .entity_verification import _company_core, _normalize
    from .entity_verification_models import EntityVerificationReport as R

    if len(_company_core(company_name)) < 3:
        add('sec_filer', company_claim, 'SEC EDGAR',
            'The company name is too short to search SEC filings reliably.', R.NOT_APPLICABLE)
        return
    try:
        filer = find_sec_filer(company_name)
    except SecUnavailable as error:
        add('sec_filer', company_claim, 'SEC EDGAR', str(error), R.COULDNT_CHECK)
        return
    if filer.status == 'not_found':
        add('sec_filer', company_claim, 'SEC EDGAR',
            'No SEC filer with this name was found on EDGAR. Most private companies never file with the SEC.',
            R.NOT_FOUND)
        return
    if filer.status == 'ambiguous':
        add('sec_filer', company_claim, 'SEC EDGAR',
            'More than one SEC filer uses this name, so none was chosen.', R.COULDNT_CHECK)
        return

    company_url = COMPANY_PAGE_URL.format(cik=filer.cik)
    add('sec_filer', company_claim, 'SEC EDGAR', f'SEC lists {filer.name} (CIK {filer.cik}).', R.MATCHES, company_url)

    incorporation_claim = 'Incorporation: not on the profile'
    try:
        record = company_record(filer.cik)
        latest = latest_form_d(record)
        form_d = fetch_form_d(filer.cik, latest['accession']) if latest else None
    except SecUnavailable as error:
        add('sec_incorporation', incorporation_claim, 'SEC EDGAR', str(error), R.COULDNT_CHECK, company_url)
        return
    filing_url = filing_index_url(filer.cik, latest['accession']) if latest else company_url

    # Incorporation, as the filings state it.
    if form_d and (form_d.jurisdiction or form_d.year_of_incorporation or form_d.over_five_years):
        where = f' in {form_d.jurisdiction.title()}' if form_d.jurisdiction else ''
        if form_d.year_of_incorporation:
            when = f', {form_d.year_of_incorporation}'
        elif form_d.over_five_years:
            when = ', more than five years before the filing'
        else:
            when = ''
        add('sec_incorporation', incorporation_claim, 'SEC Form D',
            f"{form_d.entity_type or 'The company'} formed{where}{when} (Form D filed {latest['filing_date']}).",
            R.PUBLIC_RECORD, filing_url)
    elif record.get('stateOfIncorporation'):
        add('sec_incorporation', incorporation_claim, 'SEC company record',
            f"Incorporated in {record['stateOfIncorporation']}, according to the SEC company record.",
            R.PUBLIC_RECORD, company_url)

    # The founder or owner, against the people the Form D names.
    person = _normalize(person_name)
    if not form_d:
        add('sec_person', person_claim, 'SEC Form D',
            "No Form D was found in this company's recent SEC filings, so there is no list of its people to compare.",
            R.NOT_APPLICABLE, company_url)
    elif len(person.split()) < 2:
        add('sec_person', person_claim, 'SEC Form D',
            'A full name is needed to compare with the people on the Form D.', R.NOT_APPLICABLE, filing_url)
    else:
        listed = next((roles for name, roles in form_d.people if _normalize(name) == person), None)
        if listed is not None:
            add('sec_person', person_claim, 'SEC Form D',
                f"Listed on the Form D as {', '.join(listed) or 'a related person'}.", R.MATCHES, filing_url)
        elif form_d.people:
            named = '; '.join(f"{name} ({', '.join(roles)})" if roles else name for name, roles in form_d.people)
            add('sec_person', person_claim, 'SEC Form D',
                f'Not among the people the Form D lists: {named}.', R.NOT_FOUND, filing_url)
        else:
            add('sec_person', person_claim, 'SEC Form D',
                'The Form D lists no related persons.', R.NOT_FOUND, filing_url)

    # The claimed founding year, against the year the Form D says the company was formed.
    if form_d and form_d.year_of_incorporation and claimed_year:
        year = form_d.year_of_incorporation
        gap = year - claimed_year
        if abs(gap) <= 1:
            add('sec_founding_year', founding_claim, 'SEC Form D',
                f'The Form D gives {year} as the year the company was formed, in line with the claimed founding year.',
                R.MATCHES, filing_url)
        elif gap > 0:
            add('sec_founding_year', founding_claim, 'SEC Form D',
                f'The Form D gives {year} as the year the company was formed, {gap} years after the claimed founding year. '
                'A business can operate before it incorporates, so this is worth asking about.',
                R.DOESNT_MATCH, filing_url)
        else:
            add('sec_founding_year', founding_claim, 'SEC Form D',
                f'The Form D gives {year} as the year the company was formed, {-gap} years before the claimed founding year.',
                R.DOESNT_MATCH, filing_url)
