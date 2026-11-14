"""What a valuation report may state, given the evidence actually verified.

A numeric range needs two things the evidence itself supports: annual revenue
read from a financial statement with a stated period, currency and scale, and
a basis for the multiple quoted from the submitted documents. A model's sense
of what is "typical" for a company is not a basis. Without both, the report
keeps the verified financial summary and says which inputs are missing.
"""
import re
from decimal import Decimal, InvalidOperation

from .financial_statements import _percent
from .utils import strip_page_markers

_MULTIPLE = re.compile(r'\d+(?:\.\d+)?\s*(?:x|×|times)(?![a-z])', re.IGNORECASE)
MIN_QUOTE_CHARS = 15

METHOD = ('Method: Zelda applies a valuation multiple only to annual financial inputs verified from the submitted '
          'financial statements, and only when the submitted documents themselves state the basis for that multiple '
          '(for example a comparable-company or precedent-transaction multiple). It does not substitute an assumed or '
          '"typical" multiple.')


def _normal(text):
    return re.sub(r'\s+', ' ', text or '').strip().lower()


def quoted_multiple_basis(sections, raw_text):
    """The model's quoted basis for its multiple, only if it is verbatim evidence naming a multiple."""
    basis = sections.get('multiple_basis')
    quote = basis.get('quote') if isinstance(basis, dict) else basis if isinstance(basis, str) else None
    if not isinstance(quote, str) or len(quote.strip()) < MIN_QUOTE_CHARS or not _MULTIPLE.search(quote):
        return None
    return quote.strip() if _normal(quote) in _normal(strip_page_markers(raw_text)) else None


def _number(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


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


def gate_valuation(sections, facts, statement, raw_text):
    """Keep a numeric range only when its revenue and its multiple both rest on evidence."""
    sections = dict(sections)
    if statement:
        sections['financial_summary'] = '\n'.join([
            statement.heading(), *statement.summary_lines(),
            'Figures not listed here were not verified from the financial statements.'])
    missing = []
    if not (statement and statement.latest('net_sales')):
        missing.append('Annual revenue from a financial statement that states its period, currency and scale. '
                       'Deferred revenue, segment figures and amounts with no stated period do not qualify.')
    quote = quoted_multiple_basis(sections, raw_text)
    if not quote:
        missing.append('A basis for the valuation multiple stated in the submitted documents, such as '
                       'comparable-company or precedent-transaction multiples.')
    low, high = _number(sections.get('valuation_low')), _number(sections.get('valuation_high'))
    if not missing and (low is None or high is None or low <= 0 or high < low):
        missing.append('A valid valuation range computed from those inputs.')
    if not missing:
        sections['valuation_summary'] = (f"{sections.get('valuation_summary') or ''}\n\n"
                                         f'Basis for the multiple, quoted from the submitted documents: "{quote}"').strip()
        return sections
    sections['valuation_low'] = sections['valuation_high'] = None
    verified = (facts.get('verified_financials') or [])[1:] or ['• None verified.']
    sections['valuation_summary'] = '\n'.join([
        f"No numeric valuation is given for {(facts.get('company') or 'this company').rstrip('.')}.", '', METHOD,
        'Assumptions: none applied. No multiple, discount or growth rate was assumed.', '',
        'Verified financial inputs:', *verified, '',
        'Missing inputs:', *[f'• {item}' for item in missing],
    ])
    return sections
