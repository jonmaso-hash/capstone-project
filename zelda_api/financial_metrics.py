"""
Which financial field a source statement is entitled to populate, and which
claim categories it is admissible evidence for.

A figure may only occupy a field whose name its SOURCE supports.

    arr      annual recurring revenue -- the source must say so
    mrr      monthly recurring revenue -- the source must say so
    revenue  an amount of revenue whose period is whatever the source gave,
             including "not stated"

Putting "$300K / month" into `arr` asserts an annual period the source never
gave. In the JoyToys audit run that is exactly what happened: the monthly
figure went into `arr`, reconciliation copied it to `revenue`, and the memo
prompt JSON-dumped both keys. Claude received

    {"revenue": "$300K", "arr": "$300K"}

beside the insight "$300K per month", correctly observed that a $300K ARR
cannot also be $300K monthly, reported the 12x contradiction across five memo
sections, made it question #1 for management, and cited catching it as Zelda's
own advantage. The model reasoned correctly; the data it was given was wrong.

NOTE: `facts['arr']` here and `ClaimedDatapoint(category='arr')` in Truth Delta
are INTENTIONALLY different contracts. The claim category genuinely means ARR.
Do not unify them.
"""
import re
import math

_IS_ARR = re.compile(r"\bARR\b|annual\s+recurring", re.IGNORECASE)
_IS_MRR = re.compile(r"\bMRR\b|monthly\s+recurring", re.IGNORECASE)

# Sentences plainly about a DIFFERENT metric, even when the analyzer filed them
# under Revenue. The Revenue branch of the extractor matches a bare dollar
# amount with NO keyword at all, so without this any number in a misclassified
# sentence becomes revenue. JoyToys turned "$240K annualized stated burn" into
# revenue and "$250K sought" into revenue and a customer count.
STATES_OTHER_METRIC = re.compile(
    r"\bburn\b|\bburning\b|\brunway\b|"
    r"\bsought\b|\bseeking\b|\bseeks\b|\braise\b|\braising\b|\braised\b|"
    r"\bSeries\s+[A-Z]\b|\bpre-seed\b|\bseed\s+round\b|"
    r"\bvaluation\b|\bpre-money\b|\bpost-money\b|"
    r"\butilized\b|\butilization\b|\bline\s+of\s+credit\b|\bbank\s+line\b|"
    r"\bmarket\s+size\b|\bTAM\b|\bSAM\b|\bSOM\b",
    re.IGNORECASE,
)


def states_other_metric(text):
    """True when the sentence is plainly about something other than revenue."""
    return bool(STATES_OTHER_METRIC.search(text or ""))


def revenue_field_for(text):
    """
    The revenue field this statement may populate.

    Recurring metrics require the source to name them. A figure that merely
    carries a period ("$300K / month") is revenue with that period, not MRR --
    recurring is a claim about the nature of the revenue, not its frequency.
    """
    text = text or ""
    if _IS_MRR.search(text):
        return "mrr"
    if _IS_ARR.search(text):
        return "arr"
    return "revenue"


# --- which claim categories a sentence may support -------------------------
#
# The claim extractor maps an insight category to a claim category and then
# takes whatever number the text contains. Nothing checked that the number was
# admissible evidence for that category, so on the JoyToys deck a $250K raise
# became 250,000 customers, a 75% bank-line utilization became $75 raised, an
# amount SOUGHT became capital raised, and annualized burn became revenue.
#
# Truth Delta then reported those honestly as unverified, which is correct --
# but for an SEC filer it would have compared burn against real revenue and
# announced a contradiction about a company that did nothing wrong. The
# grounding layer is faithful; it was being fed nonsense.

MONEY_CATEGORIES = frozenset({"revenue", "funding_raised", "market_size"})

_SEEKING = re.compile(
    r"\bsought\b|\bseeking\b|\bseeks\b|\bseek\b|\braising\b|\bto\s+raise\b|"
    r"\btarget(?:ing)?\b|\bask\b|\bcapital\s+request\b|\bnew\s+capital\b",
    re.IGNORECASE,
)
# Capital raised must be STATED as raised. A positive requirement, not merely
# the absence of "sought": the first version of this rule admitted anything
# without a disqualifier, and the real JoyToys insight defeated it. The deck
# slide reads "Seeking $250K", but the analyzer dropped the word when building
# the insight, leaving "$250K Series A Primary use: new entertainment
# licenses" -- no disqualifier to find, so the ask was recorded as capital
# raised. Absence of a disqualifier is not evidence of the positive.
_RAISED = re.compile(
    r"\braised\b|\bprior\s+capital\b|\bcapital\s+raised\b|\bto\s+date\b|"
    r"\bclosed\b|\bsecured\b|\bhas\s+raised\b|\bhave\s+raised\b|"
    r"\bpreviously\s+raised\b|\bfunding\s+received\b",
    re.IGNORECASE,
)
_COUNT_NOUN = re.compile(
    r"\bcustomers?\b|\bclients?\b|\busers?\b|\baccounts?\b|\bsubscribers?\b|"
    r"\bretailers?\b|\bstores?\b|\bclinics?\b|\bpractices?\b|\bhospitals?\b",
    re.IGNORECASE,
)
# What a usage figure counts. A bot or a message is not a customer, a user or
# a person: filing "140,000 bots" as customers is the JoyToys failure again,
# a real number in a claim that changes its meaning. These nouns are the ones
# the frozen audit decks actually use (docs/baselines/manychat); the list is
# widened by evidence, not by guessing what else a deck might count.
_USAGE_NOUN = re.compile(r"\b(bots?|messages?)\b", re.IGNORECASE)
# The first figure in the text, and the first counted noun of either kind after
# it. The insight text starts AT its figure (the analyzer cuts it there), so
# that noun is the one the figure counts.
_ANY_COUNTED_NOUN = re.compile(f"{_USAGE_NOUN.pattern}|(?:{_COUNT_NOUN.pattern})", re.IGNORECASE)
_PEOPLE_NOUN = re.compile(
    r"\bemployees?\b|\bstaff\b|\bheadcount\b|\bFTEs?\b|\bteam\s+(?:of|size)\b|"
    r"\bpeople\b|\bperson\s+team\b",
    re.IGNORECASE,
)
# Currency is separate from the amount and from a count's unit. A bare dollar
# symbol is deliberately unknown, including in a US company's deck.
CURRENCY_CODES = frozenset({'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'NZD', 'JPY',
                            'CNY', 'INR', 'CHF', 'SGD', 'HKD', 'MXN', 'BRL', 'ZAR'})
CURRENCY_SYMBOLS = {'US$': 'USD', 'C$': 'CAD', 'A$': 'AUD', 'NZ$': 'NZD',
                    'HK$': 'HKD', 'S$': 'SGD', '€': 'EUR', '£': 'GBP', '$': ''}
MONETARY_CATEGORIES = MONEY_CATEGORIES | {'arr'}
_CURRENCY_TOKEN = '(?:' + '|'.join(re.escape(t) for t in sorted(
    CURRENCY_CODES | set(CURRENCY_SYMBOLS), key=lambda t: (-len(t), t))) + ')'
_AMOUNT = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
_SCALE = r'(?:thousand\b|million\b|billion\b|trillion\b|bn\b|mn\b|[kmbt](?![A-Za-z]))'
MONEY_FIGURE = re.compile(
    rf'(?<![\w.,])(?:(?P<prefix>{_CURRENCY_TOKEN})\s*(?P<amount>{_AMOUNT})'
    rf'\s*(?P<scale>{_SCALE})?(?:\s*(?P<suffix>{_CURRENCY_TOKEN})(?!\w))?'
    rf'|(?P<suffix_amount>{_AMOUNT})\s*(?P<suffix_scale>{_SCALE})?\s*'
    rf'(?P<suffix_only>{_CURRENCY_TOKEN})(?!\w))'
    r'(?![\w]|[.,]\d)', re.IGNORECASE)
_MULTIPLIER = {
    "k": 1_000, "thousand": 1_000,
    "m": 1_000_000, "million": 1_000_000,
    "b": 1_000_000_000, "billion": 1_000_000_000,
    "bn": 1_000_000_000, "mn": 1_000_000,
    "t": 1_000_000_000_000, "trillion": 1_000_000_000_000,
}


def currency_code(value):
    """An explicit supported ISO code or qualified symbol; never infer USD."""
    if not isinstance(value, str):
        return ''
    value = value.strip().upper()
    return value if value in CURRENCY_CODES else CURRENCY_SYMBOLS.get(value, '')


def currency_amount(text):
    """First monetary amount and its explicit currency, or (None, '')."""
    match = MONEY_FIGURE.search(text or '')
    if not match:
        return None, ''
    digits = match['amount'] or match['suffix_amount']
    scale = (match['scale'] or match['suffix_scale'] or '').lower()
    value = float(digits.replace(',', '')) * _MULTIPLIER.get(scale, 1)
    if not math.isfinite(value):
        return None, ''
    codes = {currency_code(token) for token in (match['prefix'], match['suffix'], match['suffix_only'])
             if token and currency_code(token)}
    return value, next(iter(codes)) if len(codes) == 1 else ''


def currency_comparison_reason(category, claim_currency, observed_currency):
    if category not in MONETARY_CATEGORIES:
        return None
    a, b = currency_code(claim_currency), currency_code(observed_currency)
    if not a or not b:
        return 'currency_unknown'
    return 'currency_mismatch' if a != b else None


def claim_is_admissible(category, text):
    """
    Whether this sentence is admissible evidence for this claim category.

    Positive requirements wherever possible: a headcount needs a word for
    people, a customer count needs a word for customers, capital raised must
    say it was raised. A negative-only rule passes any sentence that merely
    omits the disqualifier -- which is how an ask whose "Seeking" had been
    dropped upstream was recorded as money already in the bank.
    """
    text = text or ""
    if category == "revenue":
        return not states_other_metric(text)
    if category == "funding_raised":
        return bool(_RAISED.search(text)) and not _SEEKING.search(text)
    if category == "customers":
        return bool(_COUNT_NOUN.search(text))
    if category == "employees":
        return bool(_PEOPLE_NOUN.search(text))
    if category == "usage":
        return usage_unit(text) is not None
    return True


def usage_unit(text):
    """
    The noun a usage figure counts ("bots", "messages"), or None.

    None unless the text has a figure and the first counted noun after it is a
    usage noun. "500M messages from 2,000 customers" counts messages; "2,000
    customers sent 500M messages" counts customers and stays a customer claim.
    """
    text = text or ""
    figure = re.search(r"\d", text)
    if not figure:
        return None
    noun = _ANY_COUNTED_NOUN.search(text, figure.start())
    if noun is None or noun.group(1) is None:
        return None
    return noun.group(1).lower()


def currency_value(text):
    """
    The first explicitly monetary amount, or None. Currency is returned by
    currency_amount; this compatibility helper returns just the number.

    Used for money categories so a percentage cannot win: the general numeric
    extractor matches percentages FIRST, which is how "Bank line: 75% utilized"
    became $75 of capital raised while the $20K actually raised sat unread in
    the same sentence.
    """
    return currency_amount(text)[0]
