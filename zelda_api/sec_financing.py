# zelda_api/sec_financing.py
"""
Capital and revenue evidence from SEC filings, for Entity Integrity.

sec_identity.py fetches and parses the filings; this module turns them into
financing events and rows, with no network access of its own:

    EDGAR data -> normalized financing events -> Entity Integrity rows

Financing events. A Form D amendment names the filing just before it
(previousAccessionNumber), not the original, and restates the whole offering,
so the amount sold is a running total. A chain of filings is one financing
event described by its newest filing; amounts are never added across
amendments.

The fundraising total adds separate events only, and leaves out offerings a
structured field marks as something other than a company raising capital:
pooled-fund offerings, business combinations, and securities described as
profits interests (service grants, not cash sales -- one real filing reports a
distribution threshold for them as "amount sold"). A filer's note on the sales
amounts is always shown but never, on its own, keeps an offering out. The
total is always Public record: Form D is not a complete record of a company's
capital.

Revenue. A Form D revenue bracket covers the issuer's most recently completed
fiscal year, and issuers need not amend when only revenue changes. Only an
explicitly annual figure is compared with it, and only when the filing is at
most REVENUE_FRESHNESS old; otherwise the bracket is shown as Public record.
A fund's net asset value range is never read as revenue.
"""
import re
from dataclasses import dataclass
from datetime import date, timedelta

REVENUE_FRESHNESS = timedelta(days=365)

# Exactly as Form D Item 5 prints them.
REVENUE_BRACKETS = {
    'No Revenues': (0, 0),
    '$1 - $1,000,000': (1, 1_000_000),
    '$1,000,001 - $5,000,000': (1_000_001, 5_000_000),
    '$5,000,001 - $25,000,000': (5_000_001, 25_000_000),
    '$25,000,001 - $100,000,000': (25_000_001, 100_000_000),
    'Over $100,000,000': (100_000_001, None),
}

POOLED_FUND_INDUSTRY = 'Pooled Investment Fund'
POOLED_FUND_SECURITY = 'Pooled investment fund interests'
_PROFITS_INTERESTS = re.compile(r'\bprofits?[\s-]+interests?\b', re.IGNORECASE)
MAX_CLARIFICATION_CHARS = 300

CAPITAL_CAVEAT = (
    "Form D is not a complete record of a company's capital: SAFEs, loans, grants and other financing may not "
    "appear. Only the recent filings on the SEC company record were reviewed. Older filings may not be included."
)


def money(value):
    return f'${value:,.0f}'


def revenue_bounds(bracket):
    """(low, high) for a Form D revenue bracket, high None for the open top bracket; None when it isn't a bracket."""
    return REVENUE_BRACKETS.get(bracket)


@dataclass
class FinancingEvent:
    accession: str       # the newest filing in the chain
    filing_date: str
    form_d: object       # sec_identity.FormD of the newest filing
    first_filed: str
    filing_count: int
    earlier_filings_missing: bool

    @property
    def last_amended(self):
        return self.filing_date if self.filing_count > 1 or self.form_d.is_amendment else None

    @property
    def amount_sold(self):
        return self.form_d.total_amount_sold

    @property
    def excluded_reason(self):
        form_d = self.form_d
        if form_d.is_business_combination:
            return 'business_combination'
        if form_d.industry_group == POOLED_FUND_INDUSTRY or POOLED_FUND_SECURITY in form_d.security_types:
            return 'pooled_fund'
        if any(_PROFITS_INTERESTS.search(security) for security in form_d.security_types):
            return 'profits_interests'
        return None

    @property
    def counts_toward_total(self):
        return self.excluded_reason is None and self.amount_sold is not None


def financing_events(filings):
    """
    Groups [(accession, filing date, FormD)] into financing events, newest
    first. Each filing is followed back through previousAccessionNumber; a
    link to a filing that isn't in the list ends the chain there, and filings
    pointing at the same missing filing stay together.
    """
    by_accession = {accession: (accession, filing_date, form_d) for accession, filing_date, form_d in filings}

    def chain_key(accession):
        seen = []
        current = accession
        while True:
            seen.append(current)
            previous = by_accession[current][2].previous_accession
            if not previous:
                return current, False
            if previous not in by_accession:
                return previous, True
            if previous in seen:
                return min(seen[seen.index(previous):]), False
            current = previous

    groups = {}
    for accession in by_accession:
        key, missing = chain_key(accession)
        group = groups.setdefault(key, {'filings': [], 'missing': False})
        group['filings'].append(by_accession[accession])
        group['missing'] = group['missing'] or missing

    events = []
    for group in groups.values():
        newest = max(group['filings'], key=lambda filing: (filing[1], filing[0]))
        events.append(FinancingEvent(
            accession=newest[0], filing_date=newest[1], form_d=newest[2],
            first_filed=min(filing[1] for filing in group['filings']),
            filing_count=len(group['filings']), earlier_filings_missing=group['missing'],
        ))
    events.sort(key=lambda event: (event.filing_date, event.accession), reverse=True)
    return events


def capital_total(events):
    """(total amount sold, counted events, events not counted)."""
    counted = [event for event in events if event.counts_toward_total]
    excluded = [event for event in events if not event.counts_toward_total]
    return sum(event.amount_sold for event in counted), counted, excluded


# --------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------

def _plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def describe_offering(event):
    form_d = event.form_d
    sold = money(form_d.total_amount_sold) if form_d.total_amount_sold is not None else 'An unstated amount'
    if form_d.offering_amount_indefinite:
        offered = ' (offering amount indefinite)'
    elif form_d.total_offering_amount is not None:
        offered = f' of {money(form_d.total_offering_amount)} offered'
    else:
        offered = ''
    investors = (f', to {_plural(form_d.investor_count, "investor")} in this offering'
                 if form_d.investor_count is not None else '')
    first_sale = f', first sale {form_d.date_of_first_sale}' if form_d.date_of_first_sale else ''
    parts = [f'Form D offering{first_sale}: {sold} sold{offered}{investors}.']

    if form_d.security_types:
        parts.append(f"Securities: {', '.join(form_d.security_types)}.")
    if event.last_amended:
        parts.append(f'First filed {event.first_filed}, last amended {event.last_amended}.')
    else:
        parts.append(f'Filed {event.first_filed}.')
    if event.earlier_filings_missing:
        parts.append("Earlier filings for this offering aren't among the recent SEC filings reviewed.")
    if form_d.sales_clarification:
        note = form_d.sales_clarification
        if len(note) > MAX_CLARIFICATION_CHARS:
            note = note[:MAX_CLARIFICATION_CHARS].rstrip() + '…'
        parts.append(f'The filer adds: "{note}"')

    reason = event.excluded_reason
    if reason == 'pooled_fund':
        kind = f' ({form_d.fund_type})' if form_d.fund_type else ''
        parts.append(f"A pooled investment fund{kind}, so it is not counted toward the company's fundraising total.")
    elif reason == 'business_combination':
        parts.append("Part of a business combination, so it is not counted toward the company's fundraising total.")
    elif reason == 'profits_interests':
        parts.append("The securities include profits interests, which are granted rather than sold for cash, so it is "
                     "not counted toward the company's fundraising total.")
    return ' '.join(parts)


def add_capital_rows(add, events, *, capital_claim, filing_url, company_url, reviewed_limit=None):
    """One Public record row per financing event, then the fundraising total beside the profile's claim."""
    from .entity_verification_models import EntityVerificationReport as R

    for event in events:
        add('sec_offering', 'Offering: not on the profile', 'SEC Form D', describe_offering(event),
            R.PUBLIC_RECORD, filing_url(event.accession))

    total, counted, excluded = capital_total(events)
    if counted:
        summary = (f"{money(total)} sold across {_plural(len(counted), 'Form D offering')} "
                   "in this company's recent SEC filings.")
    else:
        summary = "No Form D offering in this company's recent SEC filings counts toward its fundraising total."
    if excluded:
        summary += f" {_plural(len(excluded), 'other offering')} shown above {'is' if len(excluded) == 1 else 'are'} not counted."
    if reviewed_limit:
        summary += (f' Only the newest {reviewed_limit} Form D filings, and earlier filings in their amendment chains, '
                    'were reviewed.')
    add('sec_capital_raised', capital_claim, 'SEC Form D', f'{summary} {CAPITAL_CAVEAT}', R.PUBLIC_RECORD, company_url)


def add_form_d_revenue_row(add, *, form_d, filing_date, revenue_claim, revenue_amount, revenue_is_annual,
                           source_url, today=None):
    from .entity_verification_models import EntityVerificationReport as R

    if not form_d.revenue_range and form_d.net_asset_value_range:
        add('sec_revenue', revenue_claim, 'SEC Form D',
            f'The Form D filed {filing_date} gives a net asset value range ({form_d.net_asset_value_range}) '
            'instead of revenue; net asset value is not revenue.', R.NOT_APPLICABLE, source_url)
        return

    bracket = form_d.revenue_range
    bounds = revenue_bounds(bracket)
    if bounds is None:
        reason = {
            'Decline to Disclose': 'declines to disclose revenue',
            'Not Applicable': 'marks revenue as not applicable',
        }.get(bracket, 'gives no revenue range')
        add('sec_revenue', revenue_claim, 'SEC Form D', f'The Form D filed {filing_date} {reason}.',
            R.NOT_APPLICABLE, source_url)
        return

    range_text = 'no revenues' if bounds == (0, 0) else f'revenue in the {bracket} range'
    reported = (f"The Form D filed {filing_date} reports {range_text} for the issuer's most recently completed "
                "fiscal year.")

    if revenue_amount is None:
        add('sec_revenue', revenue_claim, 'SEC Form D', reported, R.PUBLIC_RECORD, source_url)
        return
    if not revenue_is_annual:
        add('sec_revenue', revenue_claim, 'SEC Form D',
            f"{reported} The profile's figure has no stated period, so it isn't compared with this annual range.",
            R.PUBLIC_RECORD, source_url)
        return
    if (today or date.today()) - date.fromisoformat(filing_date) > REVENUE_FRESHNESS:
        add('sec_revenue', revenue_claim, 'SEC Form D',
            f"{reported} That filing is more than 12 months old, so it isn't compared with current revenue.",
            R.PUBLIC_RECORD, source_url)
        return

    low, high = bounds
    if revenue_amount >= low and (high is None or revenue_amount <= high):
        add('sec_revenue', revenue_claim, 'SEC Form D',
            f"{reported} The profile's annual revenue is within that range.", R.PUBLIC_RECORD, source_url)
    else:
        add('sec_revenue', revenue_claim, 'SEC Form D',
            f"{reported} The profile's annual revenue is outside that range. Revenue can change after a fiscal "
            "year ends, so this is worth asking about.", R.DOESNT_MATCH, source_url)


def annual_report_revenue(facts):
    """(revenue, period) from a 10-K filer's company facts, through the existing Truth Delta extractor, or None."""
    from .truth_delta_sources import SECFilingsIntegration

    integration = SECFilingsIntegration()
    revenue = integration.extract_revenue(facts)
    if not revenue:
        return None
    return revenue[0], integration.extract_time_period(facts) or '10-K'


def add_annual_report_revenue_row(add, annual_revenue, *, revenue_claim, source_url):
    """A 10-K filer's latest annual revenue, as Public record."""
    from .entity_verification_models import EntityVerificationReport as R

    value, period = annual_revenue
    add('sec_revenue', revenue_claim, 'SEC 10-K',
        f"Revenue of {money(value)} in its {period}, from SEC annual report data. It is shown for reference "
        "and not compared with the profile.", R.PUBLIC_RECORD, source_url)
