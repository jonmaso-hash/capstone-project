"""
Which financial field a source statement is entitled to populate.

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

SAYS_ANNUAL = re.compile(
    r"\bARR\b|annual\s+recurring|\bannualized\b|\bannual\b|\bper\s+year\b|/\s*(?:yr|year)\b",
    re.IGNORECASE,
)
SAYS_MONTHLY = re.compile(
    r"\bMRR\b|monthly\s+recurring|\bper\s+month\b|\bmonthly\b|/\s*(?:mo|month)\b",
    re.IGNORECASE,
)
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
