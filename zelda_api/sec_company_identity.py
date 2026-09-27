"""
One company, one SEC registrant.

Two subsystems used to resolve a company name to a CIK independently, and on
2026-09-26 they disagreed: Entity Integrity chose 0000887557 while Truth Delta
chose 0000829224, both named "STARBUCKS CORP". Findings about two different
registrants were shown as facts about one company.

Neither implementation was careless. The shell matched because its FORMER
name is exactly "STARBUCKS CORPORATION" -- the string searched -- while the
operating company's current conformed name is "STARBUCKS CORP". Name equality
endorses the wrong answer, and cannot separate the two in any case, because
both carry the same current name.

What separates them is what they FILE:

    0000829224   10-K x10, 10-Q x33, newest 2026-07-29
    0000887557   no periodic filings at all, dormant since 2014

So identity is computed from filing history, and the result carries what the
registrant can support rather than only which one it is. That is the
source-capability question one level down: `sec: revenue = can_establish` is
a statement about a company that files annual reports, not about a name.

Deliberately NOT a form-number filter. Truth Delta's search passes
`type=10-K`, which excluded the shell by luck; it would also drop a foreign
private issuer filing 20-F or 40-F, a newly public company with 10-Qs and no
10-K yet, and it would happily accept a deregistered company whose last 10-K
is seven years old.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

FOUND = 'found'
AMBIGUOUS = 'ambiguous'
NOT_FOUND = 'not_found'

# Identity resolution and evidence capability are separate questions. A
# registrant can be FOUND and still be unable to establish revenue -- a
# private company that has filed only a Form D is exactly that, and is the
# normal case for this marketplace. Making periodic filings a condition of
# being found resurrects the annual-report heuristic that
# pages/tests_entity_sec_form_d.py exists to prevent.

# Forms that make a registrant a periodic reporter. Annual reporting is the
# capability that matters, so the foreign equivalents count: a 20-F filer
# reports annually exactly as a 10-K filer does.
ANNUAL_FORMS = frozenset({'10-K', '10-K/A', '10-KSB', '20-F', '20-F/A', '40-F', '40-F/A'})
QUARTERLY_FORMS = frozenset({'10-Q', '10-Q/A'})
PERIODIC_FORMS = ANNUAL_FORMS | QUARTERLY_FORMS

# Deregistration. A registrant that has filed one still has its old periodic
# reports on file, and they are history, not current evidence.
DEREGISTRATION_FORMS = frozenset({'15', '15-12B', '15-12G', '15F-12B', '15F-12G'})

# Beyond this, the newest periodic filing describes a company that may no
# longer resemble itself. Two years covers an annual reporter that is merely
# late, and excludes one that has stopped.
STALE_AFTER = timedelta(days=730)


@dataclass
class CompanyIdentity:
    """
    What Zelda believes one company's SEC registrant is, and what it supports.

    `cik` is None for every non-FOUND status -- an ambiguous or absent result
    has no registrant to attribute a finding to, and callers must be unable
    to quietly use one.
    """
    status: str
    cik: str = None
    name: str = None
    matched_on: str = None        # 'current_name' | 'former_name'
    has_ticker: bool = False
    is_stale: bool = False
    annual_filing_date: str = None
    candidate_ciks: tuple = field(default_factory=tuple)

    files_periodically: bool = False

    @property
    def can_establish_revenue(self):
        """
        Whether a revenue figure from this registrant may enter the evidence
        path -- reported INDEPENDENTLY of whether the registrant was found.

        A Form D-only private company is found and cannot establish revenue.
        Most Interlink companies are in that position, and it is an honest
        answer rather than a failure to resolve.
        """
        return self.status == FOUND and self.files_periodically

    @property
    def describes(self):
        """For attribution on a finding: which registrant this is about."""
        return f'{self.name} (CIK {self.cik})' if self.cik else None


def _forms(record):
    recent = ((record or {}).get('filings') or {}).get('recent') or {}
    return list(zip(recent.get('form') or [], recent.get('filingDate') or []))


def _newest(record, wanted):
    dates = [d for form, d in _forms(record) if form in wanted and d]
    return max(dates) if dates else None


def _core(text):
    from .entity_verification import _company_core
    return _company_core(text or '')


def _matched_on(record, wanted_core):
    if _core(record.get('name')) == wanted_core:
        return 'current_name'
    for former in record.get('formerNames') or []:
        if _core(former.get('name')) == wanted_core:
            return 'former_name'
    return None


def _rank(record, matched_on, today):
    """
    How strongly this registrant answers to the name, strongest first.

    Ordered deliberately: a current-name match outranks a former-name one,
    because a dormant registrant whose FORMER name is the search string beat
    the live company on 2026-09-26. Reporting evidence and recent activity
    separate a working company from a shell. A ticker corroborates and its
    absence never counts against a registrant -- private companies with
    registered debt file 10-Ks and have no ticker, and they are closer to
    this marketplace than SBUX is.
    """
    forms = _forms(record)
    newest = max((d for _, d in forms if d), default=None)
    active = False
    if newest:
        try:
            active = (today - date.fromisoformat(newest)) <= STALE_AFTER
        except ValueError:
            active = False
    return (
        1 if matched_on == 'current_name' else 0,
        1 if active else 0,
        1 if any(f in PERIODIC_FORMS for f, _ in forms) else 0,
        1 if record.get('tickers') else 0,
    )


def resolve_from_candidates(company_name, records, today=None):
    """
    Choose the one registrant that is this company, from submissions payloads.

    Separated from fetching so the decision is testable against recorded
    payloads and never depends on a live EDGAR call.

    Resolution ranks candidates; it does not require them to file anything.
    A weaker historical or dormant registrant must never be selected over a
    stronger current one merely because the search string matches its former
    name -- but a legitimate registrant that files nothing periodic is still
    the company's registrant.
    """
    today = today or date.today()
    wanted = _core(company_name)

    named = []
    for record in records or []:
        matched_on = _matched_on(record, wanted)
        if matched_on:
            named.append((record, matched_on))

    if not named:
        return CompanyIdentity(status=NOT_FOUND)

    ranked = sorted(named, key=lambda pair: _rank(pair[0], pair[1], today), reverse=True)
    best, matched_on = ranked[0]

    if len(ranked) > 1:
        runner_up, runner_matched = ranked[1]
        if _rank(best, matched_on, today) == _rank(runner_up, runner_matched, today):
            # Nothing separates them -- holding companies and debt-issuing
            # subsidiaries really do share a name. Refuse rather than pick.
            return CompanyIdentity(
                status=AMBIGUOUS,
                candidate_ciks=tuple(str(r.get('cik', '')).zfill(10) for r, _ in ranked),
            )

    annual = _newest(best, ANNUAL_FORMS)
    newest_periodic = _newest(best, PERIODIC_FORMS)
    deregistered = _newest(best, DEREGISTRATION_FORMS) is not None

    stale = deregistered
    if not stale:
        reference = newest_periodic or max((d for _, d in _forms(best) if d), default=None)
        if reference:
            try:
                stale = (today - date.fromisoformat(reference)) > STALE_AFTER
            except ValueError:
                stale = False

    return CompanyIdentity(
        status=FOUND,
        cik=str(best.get('cik', '')).zfill(10),
        name=best.get('name'),
        matched_on=matched_on,
        has_ticker=bool(best.get('tickers')),
        files_periodically=bool(newest_periodic),
        is_stale=stale,
        annual_filing_date=annual,
        candidate_ciks=tuple(str(r.get('cik', '')).zfill(10) for r, _ in ranked),
    )


# --------------------------------------------------------------------------
# Fetching the candidates
# --------------------------------------------------------------------------

# One resolution may fetch a submissions payload per candidate, so the search
# result is capped. EDGAR's company search is a prefix match and a short name
# can return dozens; beyond this the answer is ambiguous anyway.
MAX_CANDIDATES = 10


def candidate_ciks(company_name):
    """
    Every CIK EDGAR's company search offers for this name, not the first.

    The multi-match feed garbles company names into ARRAY(0x...) references,
    which defeated name-checking before -- but that no longer matters here.
    Only the CIKs are taken from the search; each registrant's authoritative
    name comes from its own submissions payload.
    """
    from . import sec_identity
    import re as _re

    seen = []
    for name in dict.fromkeys(filter(None, [
        (company_name or '').strip(), sec_identity._search_phrase(company_name),
    ])):
        try:
            response = sec_identity._get(sec_identity.COMPANY_SEARCH_URL, params={
                'action': 'getcompany', 'company': name, 'owner': 'include',
                'count': MAX_CANDIDATES, 'output': 'atom',
            })
        except sec_identity.SecUnavailable:
            raise
        for cik in _re.findall(r'<cik>(\d+)</cik>', response.text or '', _re.IGNORECASE):
            padded = cik.zfill(10)
            if padded not in seen:
                seen.append(padded)
        # Deliberately no early exit. Searching the name as given finds a
        # registrant whose FORMER name matches it exactly; the operating
        # company may only appear under the suffix-stripped phrase, because
        # EDGAR's conformed name abbreviates ("STARBUCKS CORP"). Stopping at
        # the first query that returned anything found the shell and never
        # looked for the company -- which is how the live check failed.
    return seen[:MAX_CANDIDATES]


def resolve_company_identity(company_name):
    """
    The one place a company name becomes an SEC registrant.

    Both Truth Delta and Entity Integrity call this, so they cannot disagree
    about which company they are describing -- which they did, live, on
    2026-09-26.

    Raises sec_identity.SecUnavailable when SEC cannot be reached: an
    unreachable source is a statement about the attempt, never an absence of
    a registrant, and callers must be unable to confuse the two.
    """
    from . import sec_identity

    records = []
    for cik in candidate_ciks(company_name):
        try:
            records.append(sec_identity.company_record(cik))
        except sec_identity.SecUnavailable:
            # Propagated, never swallowed: an unreachable source is a
            # statement about the attempt, not an absence of a registrant.
            raise
        except Exception:
            continue

    # Deliberately uncached. The caller this replaces did no caching either,
    # and adding it here would change how often SEC is called and how results
    # leak between requests -- a separate concern from making the two
    # subsystems agree on one registrant.
    return resolve_from_candidates(company_name, records)
