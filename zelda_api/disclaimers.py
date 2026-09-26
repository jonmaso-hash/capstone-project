"""
Shared legal disclaimer text for every AI-generated intelligence surface
(Intelligence Memo, Truth Delta, IC Memo, Valuation) — one string so the
wording can't drift between report types as they're edited independently.

Also home to the evidence-source description, for the same reason and after
the same failure: five surfaces named Truth Delta's sources in their own
words, and three of them ended up asserting Crunchbase, which does not run
without an API key it deliberately doesn't have.
"""
from django.conf import settings

# Addressed to "you", not "investors": the same constant renders on reports read
# by founders, sellers and buyers, and the old wording told three of those four
# audiences that somebody else was responsible for their diligence.
DUE_DILIGENCE_DISCLAIMER = (
    "This report is provided for informational and due-diligence purposes only. It is not "
    "financial, investment, legal, tax, or accounting advice. Do not rely solely on this "
    "report when making an investment or transaction decision. You are responsible for "
    "conducting your own independent due diligence and, where appropriate, consulting "
    "qualified professional advisers. It is not a binding representation by Interlink Foundry."
)


def verifying_source_names():
    """
    The sources that can actually yield a datapoint to compare a claim
    against, right now, under this deployment's configuration.

    Derived from the same settings the fetch layer reads, because
    `DataSourceManager.get_all_active()` skips any integration whose
    `authenticate()` returns False — and Crunchbase's returns False without
    CRUNCHBASE_API_KEY. A surface that names it anyway is describing a lookup
    that never happens.

    News is deliberately absent even when configured: every
    `NewsIntegration.extract_*` returns None, and its docstring says
    headlines are "not a claim source itself". It gives Claude context; it
    does not verify a claim.
    """
    names = ['SEC EDGAR']
    if getattr(settings, 'CRUNCHBASE_API_KEY', ''):
        names.append('Crunchbase')
    return names


def _join(names):
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"


def evidence_sources_sentence():
    """
    One sentence describing what a claim is actually checked against, for
    every surface that needs to say so.

    Two things it deliberately does NOT say. It does not promise coverage:
    only revenue and employees are populated by any live source today, and
    only for companies that file with the SEC, so the sources are named
    "where they report the metric". And it does not list news among them.
    """
    sentence = (
        f"Claims are compared against {_join(verifying_source_names())}, "
        f"where those sources report the metric."
    )
    if getattr(settings, 'NEWS_API_KEY', ''):
        sentence += " Recent news is read for context and is not used to verify a claim."
    return sentence
