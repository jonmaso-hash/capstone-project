"""Explicit profile reporting currencies. Blank is unknown, never assumed USD."""
import re

CURRENCY_CHOICES = [('', 'Not stated')] + [(code, code) for code in (
    'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'NZD', 'CHF', 'JPY', 'CNY', 'HKD',
    'SGD', 'INR', 'MXN', 'BRL', 'SEK', 'NOK', 'DKK', 'ZAR', 'KRW', 'ILS',
)]
KNOWN_CURRENCIES = frozenset(code for code, _ in CURRENCY_CHOICES if code)
MONEY_FIELDS = frozenset({
    'current_revenue', 'monthly_burn_rate', 'raising_amount', 'prior_amount_raised',
    'annual_revenue', 'ebitda', 'asking_price', 'investment_amount',
    'ticket_size_min', 'ticket_size_max', 'target_revenue_min', 'target_revenue_max',
    'target_ebitda_min', 'target_ebitda_max', 'budget_min', 'budget_max',
})


def profile_currency(profile):
    code = getattr(profile, 'reporting_currency', '')
    return code if code in KNOWN_CURRENCIES else ''


def currencies_match(left, right):
    code = profile_currency(left)
    return bool(code and code == profile_currency(right))


def query_currency(text):
    """One explicit code or unambiguous symbol in a search, never a bare $."""
    codes = {code.upper() for code in re.findall(r'\b(?:' + '|'.join(KNOWN_CURRENCIES) + r')\b', text or '', re.I)}
    for marker, code in (('US$', 'USD'), ('C$', 'CAD'), ('A$', 'AUD'), ('NZ$', 'NZD'), ('€', 'EUR'), ('£', 'GBP')):
        if marker in (text or ''):
            codes.add(code)
    return next(iter(codes)) if len(codes) == 1 else ''
