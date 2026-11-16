"""What a valuation report may state, given the evidence actually verified.

A numeric range needs two things the evidence itself supports: annual revenue
read from a financial statement with a stated period, currency and scale, and
an enterprise-value-to-revenue multiple quoted from the submitted documents.
The range is then computed here, from those two inputs; the model's own bounds
are never used. A model's sense of what is "typical" for a company is not a
basis, and neither is a multiple of another metric (EBITDA, earnings, ARR), a
forward or quarterly multiple, a price or equity multiple, or a quote whose
numbers cannot be read as one multiple or one range. Without a basis that
explicitly applies to the verified metric, the report keeps the verified
financial summary, gives no range, and says which inputs are missing.
"""
import re
from dataclasses import dataclass
from decimal import Decimal

from .financial_statements import _money, _percent
from .utils import split_pages

MIN_QUOTE_CHARS = 15
# BusinessValuationReport.valuation_low/high: DecimalField(max_digits=15,
# decimal_places=2). A larger value fails on Postgres (SQLite would accept it).
MAX_STORABLE_VALUE = Decimal(10) ** 13

METHOD = ('Method: Zelda applies a valuation multiple only to annual financial inputs verified from the submitted '
          'financial statements, and only when the submitted documents themselves state an enterprise-value-to-revenue '
          'multiple (for example a comparable-company or precedent-transaction multiple). It does not substitute an '
          'assumed or "typical" multiple, and it does not apply a multiple of another metric to revenue.')
# The first line of a summary the gate wrote for a computed range. Pages read
# the range's label from it (see range_basis_label), so no schema change is needed.
EV_SUMMARY_PREFIX = 'Estimated enterprise value (EV/Revenue)'
EV_RANGE_LABEL = 'Estimated enterprise value (EV/Revenue)'

_NUMBER = r'(\d+(?:\.\d+)?)'
_TIMES = r'(?:x|×|times)(?![a-z])'
_RANGE = re.compile(_NUMBER + r'\s*(?:x|×)?\s*(?:-|–|—|to|and)\s*' + _NUMBER + r'\s*' + _TIMES, re.IGNORECASE)
_SINGLE = re.compile(_NUMBER + r'\s*' + _TIMES, re.IGNORECASE)
_EV = re.compile(r'\b(?:ev|tev|enterprise[\s-]+values?)\b', re.IGNORECASE)
_REVENUE = re.compile(r'\b(?:revenues?|net\s+sales|sales)\b', re.IGNORECASE)
# Any of these makes the quote about a different metric or basis than verified
# annual net sales, or leaves it open which one the multiple applies to.
_OTHER_METRIC = re.compile(
    r'\b(?:ebitda\w*|ebit|ebita|earnings|eps|p\s*/\s*e|pe\s+ratio|net\s+income|profits?|cash\s+flows?|fcf|'
    r'book\s+value|arr|mrr|recurring|gross\s+(?:profit|margin)|gmv|bookings|subscribers?|users?|'
    r'equity\s+values?|market\s+cap\w*|price[\s-]+to|p\s*/\s*s)\b', re.IGNORECASE)
_OTHER_PERIOD = re.compile(
    r'\b(?:forward|ntm|next\s+twelve|next\s+12|projected|forecast\w*|estimated|expected|budget\w*|'
    r'quarterly|monthly|annuali[sz]ed|run[\s-]?rate|20\d\d\s*e)\b', re.IGNORECASE)


@dataclass(frozen=True)
class MultipleBasis:
    low: Decimal
    high: Decimal
    quote: str
    source_page: int

    def text(self):
        return f'{self.low}x' if self.low == self.high else f'{self.low}x to {self.high}x'


def _normal(text):
    return re.sub(r'\s+', ' ', text or '').strip().lower()


def _quote(sections):
    basis = sections.get('multiple_basis')
    quote = basis.get('quote') if isinstance(basis, dict) else basis if isinstance(basis, str) else None
    return quote.strip() if isinstance(quote, str) and len(quote.strip()) >= MIN_QUOTE_CHARS else None


def _source_page(quote, raw_text):
    """The one PDF page whose text contains the quote verbatim, else None."""
    needle = _normal(quote)
    pages = [number for number, text in split_pages(raw_text or '') if needle in _normal(text)]
    return pages[0] if len(pages) == 1 else None


def _bounds(quote):
    """One multiple, or one low-high range of multiples; anything else is ambiguous (None)."""
    # "6.0x to 7.5x", "6.0-7.5x", "between 6 and 8 times"
    ranges = list(_RANGE.finditer(quote))
    singles = list(_SINGLE.finditer(quote))
    if len(ranges) == 1:
        span = ranges[0].span()
        if any(not (span[0] <= m.start() < span[1]) for m in singles):
            return None  # another multiple outside the range
        low, high = (Decimal(ranges[0].group(1)), Decimal(ranges[0].group(2)))
    elif not ranges and len(singles) == 1:
        low = high = Decimal(singles[0].group(1))
    else:
        return None
    return (low, high) if Decimal(0) < low <= high else None


def _basis(sentence, page):
    """A MultipleBasis when this one sentence states an EV/revenue multiple for annual revenue."""
    if not _SINGLE.search(sentence) or not (_EV.search(sentence) and _REVENUE.search(sentence)):
        return None
    if _OTHER_METRIC.search(sentence) or _OTHER_PERIOD.search(sentence):
        return None
    bounds = _bounds(sentence)
    return MultipleBasis(bounds[0], bounds[1], sentence, page) if bounds else None


def _evidence_sentences(raw_text):
    for page, text in split_pages(raw_text or ''):
        # Decimal points ("7.5x") are not followed by a space, so they never split.
        for sentence in re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', text).strip()):
            if len(sentence) >= MIN_QUOTE_CHARS and _SINGLE.search(sentence):
                yield page, sentence


def ev_revenue_basis(sections, raw_text):
    """The EV/revenue multiple the evidence states, if it states exactly one; else None.

    Candidates are sentences of the submitted documents, plus the model's quote
    when it appears verbatim on exactly one page. A candidate must name
    enterprise value and revenue/net sales, name no other metric, equity basis
    or non-annual period, and contain exactly one multiple or one range. If the
    candidates disagree on the bounds, the basis is ambiguous and none is used.
    """
    candidates = [basis for basis in (_basis(sentence, page) for page, sentence in _evidence_sentences(raw_text))
                  if basis]
    quote = _quote(sections)
    page = _source_page(quote, raw_text) if quote else None
    quoted = _basis(quote, page) if page is not None else None
    if quoted:
        candidates.insert(0, quoted)
    if len({(basis.low, basis.high) for basis in candidates}) != 1:
        return None
    return candidates[0]


def range_basis_label(valuation_summary):
    """The label for a stored range: enterprise value when the gate computed it, else ''."""
    return EV_RANGE_LABEL if (valuation_summary or '').startswith(EV_SUMMARY_PREFIX) else ''


def _reported(value):
    return f'{value.normalize():,f}'


def apply_statement_facts(facts, statement, document_id):
    """Statement figures replace sentence-derived revenue and growth, with their provenance."""
    sales = statement.latest('net_sales')
    facts['revenue'] = f'{sales.amount()} ({sales.line_item}, {sales.period_label}, PDF page {sales.source_page})'
    facts['arr'] = facts['mrr'] = None
    growth = statement.net_sales_growth()
    if growth:
        facts['growth_rate'] = f'{_percent(growth.value, 0)}% ({growth.name}, PDF page {growth.source_page})'
    facts['verified_financials'] = [statement.heading(), *statement.summary_lines()]
    facts['_provenance']['revenue'] = {
        'status': 'statement', 'source': 'document', 'document_value': facts['revenue'], 'profile_value': None,
        'document_id': document_id, 'confidence': None, 'line_item': sales.line_item, 'entity': sales.entity,
        'scope': sales.scope, 'period_end': sales.period_end.isoformat(), 'currency': sales.currency,
        'scale': sales.scale, 'source_page': sales.source_page,
    }
    facts['missing_fields'] = [field for field in facts['missing_fields']
                               if field not in ('Revenue / ARR / MRR', 'Growth rate')]
    return facts


_NET_MARGIN_MENTION = re.compile(
    r'(?<!gross )(?<!operating )\b(?:net(?:\s+(?:profit|income))?|profit)\s+margins?\b[^.;%\n]{0,60}?(\d+(?:\.\d+)?)\s*%'
    r'|(\d+(?:\.\d+)?)\s*%\s+net\b(?:\s+(?:profit\s+|income\s+)?margins?\b'
    r'|(?!\s+(?:sales|revenues?|income|earnings|cash|loss(?:es)?|assets|debt|proceeds|of|interest|new|retention|'
    r'dollar|change|growth|increase|decrease|additions?|adds?|promoter)\b))',
    re.IGNORECASE)
# A sentence ends at . ! or ? that is not a decimal point ("$478.834 billion").
_SENTENCE = re.compile(r'(?:[^.!?\n]|[.!?](?=\d))+(?:[.!?]+(?!\d)\s*|$)')
_SENTENCE_END = re.compile(r'^(.*?)([.!?]*)(\s*)$', re.DOTALL)
MODEL_SECTIONS = ('business_overview', 'financial_summary', 'risk_report', 'valuation_summary')


def _matching_net_margin(written, margins):
    """The verified net margin a written percentage states, at the precision it was written."""
    places = len(written.split('.')[1]) if '.' in written else 0
    stated = Decimal(written)
    return next((ratio for ratio in margins if _percent(ratio.value, places) == stated), None)


def govern_net_margin(text, statement):
    """Keep a net margin only when it is the verified same-period ratio, and cite it.

    A sentence stating any other net margin, or any net margin when no income
    statement was verified, is removed: the model is not a source.
    """
    if not text:
        return text
    margins = statement.net_margins() if statement else []
    kept = []
    for line in text.split('\n'):
        out = []
        for sentence in _SENTENCE.findall(line):
            mentions = list(_NET_MARGIN_MENTION.finditer(sentence))
            if not mentions:
                out.append(sentence)
                continue
            ratios = [_matching_net_margin(m.group(1) or m.group(2), margins) for m in mentions]
            if not all(ratios):
                continue
            citation = '; '.join(dict.fromkeys(
                f'{r.name} {_percent(r.value, 1)}%, computed as {r.formula}, PDF page {r.source_page}' for r in ratios))
            body, punctuation, space = _SENTENCE_END.match(sentence).groups()
            out.append(f'{body} (verified: {citation}){punctuation}{space}')
        if not line.strip():
            kept.append(line)
        elif ''.join(out).strip():
            # A line emptied by removal is dropped rather than left blank.
            kept.append(''.join(out).rstrip())
    return '\n'.join(kept)


def gate_valuation(sections, facts, statement, raw_text):
    """Keep a numeric range only when its revenue and its multiple both rest on evidence."""
    sections = dict(sections)
    # Model-written text first; the deterministic sections written below
    # carry their own citations.
    for field in MODEL_SECTIONS:
        if isinstance(sections.get(field), str):
            sections[field] = govern_net_margin(sections[field], statement)
    if statement:
        sections['financial_summary'] = '\n'.join([
            statement.heading(), *statement.summary_lines(),
            'Figures not listed here were not verified from the financial statements.'])
    company = (facts.get('company') or 'this company').rstrip('.')
    missing = []
    sales = statement.latest('net_sales') if statement else None
    if not sales:
        missing.append('Annual revenue from a financial statement that states its period, currency and scale. '
                       'Deferred revenue, segment figures and amounts with no stated period do not qualify.')
    basis = ev_revenue_basis(sections, raw_text)
    if not basis:
        missing.append('An enterprise-value-to-revenue multiple stated in the submitted documents (for example '
                       'comparable-company or precedent-transaction EV/Revenue multiples), quoted from one page, '
                       'giving one multiple or one range. Multiples of EBITDA, earnings or ARR, forward or quarterly '
                       'multiples, and equity or price multiples do not apply to annual net sales.')
    if not missing:
        # Computed here; the model's valuation_low/high are never used.
        low, high = (sales.value * basis.low).quantize(Decimal(1)), (sales.value * basis.high).quantize(Decimal(1))
        if high >= MAX_STORABLE_VALUE:
            missing.append('A computed enterprise value below $10 trillion, the largest value a report can store.')
    if not missing:
        sections['valuation_low'], sections['valuation_high'] = low, high
        unit = sales.scale[:-1]
        sections['valuation_summary'] = '\n'.join([
            f'{EV_SUMMARY_PREFIX} for {company}: {_money(low)}' + ('' if low == high else f' to {_money(high)}') + '.',
            'This is enterprise value, not equity value: no adjustment for cash, debt or other claims was made.',
            '', METHOD,
            f'Formula: enterprise value = {sales.line_item}, {sales.period_label} × EV/Revenue multiple.',
            f'• Low: ${_reported(sales.reported)} {unit} × {basis.low}x = ${_reported(sales.reported * basis.low)} {unit}',
            *([] if low == high else [
                f'• High: ${_reported(sales.reported)} {unit} × {basis.high}x = '
                f'${_reported(sales.reported * basis.high)} {unit}']),
            '', 'Sources:',
            f'• {sales.line_item}: {statement.statement} of {sales.entity} ({sales.currency}; reported in '
            f'{sales.scale}; PDF page {sales.source_page}).',
            f'• EV/Revenue multiple of {basis.text()}, quoted from the submitted documents (PDF page '
            f'{basis.source_page}): "{basis.quote}"',
            'Assumptions: the quoted multiple is applied as stated to verified annual net sales. No other multiple, '
            'discount or growth rate was assumed.',
        ])
        return sections
    sections['valuation_low'] = sections['valuation_high'] = None
    verified = (facts.get('verified_financials') or [])[1:] or ['• None verified.']
    sections['valuation_summary'] = '\n'.join([
        f"No numeric valuation is given for {company}.", '', METHOD,
        'Assumptions: none applied. No multiple, discount or growth rate was assumed.', '',
        'Verified financial inputs:', *verified, '',
        'Missing inputs:', *[f'• {item}' for item in missing],
    ])
    return sections
