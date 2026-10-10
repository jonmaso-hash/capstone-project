"""
What period a figure describes, and when two periods may be compared.

This is the admission gate for `contradicted`. Until claims carried a period,
every disagreement ended as period_unknown; a period on the claim is what lets
a gap become a contradiction, so the comparison rule lives here, in one place,
with its edges frozen in zelda_api/data/claim_periods/expectations.json.

A claim's period is read from the claim's OWN sentence only. A slide heading
on another line ("Traction by Apr-16") never attaches: joining lines is what
exposes a platform's user counts to the claim layer (see claim_attribution).

Kinds:

    annual      a reported year: "FY2024", "fiscal 2025", "year ended May 31, 2026"
    quarterly   "Q3 2024", "quarterly"
    monthly     "per month", "/month", "MRR"
    ttm         trailing twelve months
    run_rate    "ARR", "annualized", "run-rate": derived, never reported annual
    cumulative  "to date", "cumulative", "by Apr-16"

Boundaries (owner decisions, 2026-10-10):

  * A fiscal-year label never implies an end date. "FY2024" is matched only
    against the filer's own fiscal-year label for the observed period, and a
    claimed end date only against the observed end date.
  * A bare year ("a 2015 Series A deck", "founded in 1978") is not a period.
  * Two conflicting bases in one sentence leave the period unknown.
  * Two distinct fiscal years or end dates in one sentence leave the period
    unresolved: the amount is not bound to either.
"""
import re
from dataclasses import dataclass
from datetime import date

ANNUAL = 'annual'
QUARTERLY = 'quarterly'
MONTHLY = 'monthly'
TTM = 'ttm'
RUN_RATE = 'run_rate'
CUMULATIVE = 'cumulative'
KINDS = (ANNUAL, QUARTERLY, MONTHLY, TTM, RUN_RATE, CUMULATIVE)

# Comparison outcomes.
COMPARABLE = 'comparable'     # same basis and the same period, established on both sides
MISMATCH = 'mismatch'         # both sides state a period and they differ
UNRESOLVED = 'unresolved'     # same basis, but which period cannot be established
UNKNOWN = 'unknown'           # the claim (or the evidence) carries no usable period

_MONTHS = ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
_MONTH_WORD = r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?'

# Basis markers. Acronyms are case-sensitive so "arr" inside a word or a
# lowercase token cannot set a basis.
_KIND_MARKERS = {
    MONTHLY: re.compile(r'(?i:\bper\s+month\b|/\s?mo(?:nth)?\b|\bmonthly\b|\bthis\s+month\b)|\bMRR\b'),
    RUN_RATE: re.compile(r'(?i:\brun[- ]?rate\b|\bannuali[sz]ed\b|\bannual\s+recurring\s+revenue\b)|\bARR\b'),
    TTM: re.compile(r'(?i:\btrailing\s+(?:twelve|12)[- ]months?\b|\blast\s+(?:twelve|12)\s+months\b)|\bTTM\b|\bLTM\b'),
    QUARTERLY: re.compile(r'\bQ[1-4]\b|(?i:\bquarterly\b|\b(?:this|last|per|each)\s+quarter\b|\bquarter\s+ended\b)'),
    CUMULATIVE: re.compile(r'(?i:\bto\s+date\b|\bcumulative(?:ly)?\b|\bsince\s+(?:inception|launch|founding)\b|'
                           r'\bby\s+' + _MONTH_WORD + r"[- ']?\d{2,4}\b)"),
    ANNUAL: re.compile(r'(?i:\bannual(?:ly)?\b|\bper\s+(?:year|annum)\b|\byearly\b|/\s?yr\b)'),
}
_FISCAL_YEAR = re.compile(r"\bFY\s?'?(\d{4}|\d{2})\b|(?i:\bfiscal\s+(?:year\s+)?(\d{4})\b)")
_YEAR_ENDED = re.compile(r'(?i:\b(?:fiscal\s+)?year\s+ended\s+(' + _MONTH_WORD + r')\s+(\d{1,2}),?\s+(\d{4}))')


@dataclass(frozen=True)
class ClaimPeriod:
    kind: str = ''
    fiscal_year: int = None
    period_end: date = None
    phrase: str = ''


def _fiscal_year(match):
    digits = match.group(1) or match.group(2)
    year = int(digits)
    return 2000 + year if len(digits) == 2 else year


def _end_date(match):
    month = _MONTHS.index(match.group(1)[:3].lower()) + 1
    try:
        return date(int(match.group(3)), month, int(match.group(2)))
    except ValueError:
        return None


def claim_period(sentence):
    """The period a claim's own sentence states, or an empty ClaimPeriod."""
    text = sentence or ''
    found = {kind: pattern.search(text) for kind, pattern in _KIND_MARKERS.items()}
    found = {kind: match for kind, match in found.items() if match}
    if RUN_RATE in found:
        # "annual run-rate" and "annual recurring revenue" are run-rates.
        found.pop(ANNUAL, None)
    # Every fiscal-year and end-date marker, not just the first: "Our FY2026
    # results improved on FY2025 revenue of USD 52.8 billion" names two years
    # and the amount is FY2025's. Which marker an amount belongs to is not
    # decided here -- guessing by proximity is the same misattribution in a
    # new place -- so two or more DISTINCT periods leave the period unresolved.
    fiscal = [(_fiscal_year(m), m.group(0)) for m in _FISCAL_YEAR.finditer(text)]
    ended = [(_end_date(m), m.group(0)) for m in _YEAR_ENDED.finditer(text)]
    ended = [(day, phrase) for day, phrase in ended if day]
    markers = {('fy', year) for year, _ in fiscal} | {('end', day) for day, _ in ended}
    if len(found) > 1:
        return ClaimPeriod()
    if not found and not markers:
        return ClaimPeriod()
    kind = next(iter(found)) if found else ANNUAL
    phrases = [m.group(0) for m in found.values()] + [phrase for _, phrase in fiscal + ended]
    fiscal_year = period_end = None
    if kind == ANNUAL and len(markers) == 1:
        # Dates only qualify an annual figure; a fiscal year does not name a month.
        (which, value), = markers
        if which == 'end':
            period_end = value
        else:
            fiscal_year = value
    elif kind != ANNUAL:
        phrases = [m.group(0) for m in found.values()]
    return ClaimPeriod(kind, fiscal_year, period_end, '; '.join(dict.fromkeys(p.strip() for p in phrases))[:100])


def compare_periods(claim_kind, claim_fiscal_year, claim_end, observed_kind, observed_fiscal_year, observed_end):
    """
    COMPARABLE, MISMATCH, UNRESOLVED or UNKNOWN.

    An exact end-date match or an equal fiscal-year label is COMPARABLE. A
    claimed date a few days from the observed end (a 52/53-week year written
    as "September 30") is UNRESOLVED rather than either: it neither proves the
    same period nor proves a different one. A fiscal year is never compared
    with an end date.
    """
    if not claim_kind or not observed_kind:
        return UNKNOWN
    if claim_kind != observed_kind:
        return MISMATCH
    if claim_kind != ANNUAL:
        return UNRESOLVED
    if claim_end and observed_end:
        if claim_end == observed_end:
            return COMPARABLE
        return UNRESOLVED if abs((claim_end - observed_end).days) <= 7 else MISMATCH
    if claim_fiscal_year and observed_fiscal_year:
        return COMPARABLE if claim_fiscal_year == observed_fiscal_year else MISMATCH
    return UNRESOLVED
