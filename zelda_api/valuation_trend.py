# zelda_api/valuation_trend.py
"""
"Up/down X% since your last valuation" — the smallest lift on top of the
existing versioning foundation (zelda_api/views.py::valuation_history_view
already numbers repeat uploads of the same company as Version 1, Version
2, ...). Comparison only ever happens between two 'full' tier reports —
a preview-tier report has no real valuation_low/valuation_high to compare
against, and showing a delta computed from a locked report would leak
the very number the paywall protects.
"""
from decimal import Decimal


def get_previous_full_valuation(document):
    """
    (document, report) for the most recent OTHER full-tier valuation of
    the same company (normalized name match) uploaded by the same user
    before `document` — or (None, None) if this is the first full
    valuation for this company. Company matching reuses
    matchmaking._normalize_company_string, the same function
    valuation_history_view's own version-numbering already relies on, so
    the two can never disagree on what counts as "the same company."
    """
    from matchmaking.models import _normalize_company_string
    from .vector_models import DocumentSource

    normalized = _normalize_company_string(document.source_entity)
    candidates = (
        DocumentSource.objects.filter(
            uploaded_by=document.uploaded_by, document_type='business_valuation',
            valuation_tier='full', created_at__lt=document.created_at,
        )
        .exclude(id=document.id)
        .exclude(status='error')
        .select_related('valuation_report')
        .order_by('-created_at')
    )

    for candidate in candidates:
        if _normalize_company_string(candidate.source_entity) != normalized:
            continue
        report = getattr(candidate, 'valuation_report', None)
        if report and report.valuation_low is not None and report.valuation_high is not None:
            return candidate, report
    return None, None


def compute_valuation_trend(current_report, previous_report):
    """
    {'pct_change': int, 'direction': 'up'|'down'|'flat',
     'previous_low': Decimal, 'previous_high': Decimal,
     'midpoint_delta': Decimal, 'previous_date': datetime} comparing the
    midpoint of each report's valuation range — None if either report is
    missing a range (shouldn't happen for two 'full' tier reports, but
    stay defensive rather than divide by an absent number) or the
    previous midpoint is zero (a percentage off a zero baseline is
    meaningless, same convention as the funnel/trending code in
    matchmaking/insights_engine.py). midpoint_delta is the plain dollar
    change between the two midpoints — shown alongside the percentage
    since people read a dollar figure faster than a percentage.
    """
    if current_report.valuation_low is None or current_report.valuation_high is None:
        return None
    if previous_report.valuation_low is None or previous_report.valuation_high is None:
        return None

    current_mid = (Decimal(current_report.valuation_low) + Decimal(current_report.valuation_high)) / 2
    previous_mid = (Decimal(previous_report.valuation_low) + Decimal(previous_report.valuation_high)) / 2
    if previous_mid == 0:
        return None

    pct_change = round(float((current_mid - previous_mid) / previous_mid * 100))
    direction = 'up' if pct_change > 0 else 'down' if pct_change < 0 else 'flat'
    return {
        'pct_change': pct_change,
        'direction': direction,
        'previous_low': previous_report.valuation_low,
        'previous_high': previous_report.valuation_high,
        'midpoint_delta': current_mid - previous_mid,
        'previous_date': previous_report.created_at,
    }


# Which structured facts (see intelligence_pipeline.py::_build_structured_context)
# can drive a "primary drivers" explanation, and the plain-English verb
# pair for an increase/decrease in each.
DRIVER_FIELDS = [
    ('team_size', 'Team size', 'grew', 'shrank'),
    ('raise_amount', 'Funding raised', 'increased', 'decreased'),
]


def _driver_for_pair(current_value, previous_value, label, up_word, down_word):
    from .truth_delta_tasks import _extract_numeric_value

    if not current_value or not previous_value:
        return None
    current_num = _extract_numeric_value(current_value)
    previous_num = _extract_numeric_value(previous_value)
    if current_num is None or previous_num is None or current_num == previous_num:
        return None
    return f"{label} {up_word if current_num > previous_num else down_word}"


def compute_valuation_drivers(current_facts, previous_facts):
    """
    A short list of plain-English "primary drivers" comparing the
    structured facts each document's own pipeline pass already extracted
    (revenue/ARR, team size, funds raised) — reuses
    intelligence_pipeline.py's existing extraction and truth_delta_tasks'
    existing numeric parser, so this costs no new Claude call. A field
    that's missing from either document, or didn't actually change, is
    silently skipped rather than guessed at — this only ever reports
    what the two documents' own extracted facts actually show.
    """
    drivers = []

    revenue_current = current_facts.get('arr') or current_facts.get('revenue')
    revenue_previous = previous_facts.get('arr') or previous_facts.get('revenue')
    revenue_driver = _driver_for_pair(revenue_current, revenue_previous, 'Revenue', 'increased', 'decreased')
    if revenue_driver:
        drivers.append(revenue_driver)

    for field, label, up_word, down_word in DRIVER_FIELDS:
        driver = _driver_for_pair(current_facts.get(field), previous_facts.get(field), label, up_word, down_word)
        if driver:
            drivers.append(driver)

    return drivers
