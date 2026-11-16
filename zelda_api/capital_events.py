"""Telling money a company raises apart from money it returns.

A share repurchase authorization or a dividend is capital flowing OUT to
shareholders. Filings put those next to the verb "raised" ("announced a new
share repurchase program of up to $100 billion and raised its quarterly
dividend"), and a sentence-level extractor that binds a figure to the nearest
fundraising word then reports a $100 billion capital raise. That is not a
weaker reading of the sentence; it is the opposite of what it says.

The rule fails closed: a sentence that names a capital return is not a
fundraising disclosure unless it also uses an unambiguous fundraising term
(a priced round, a financing, a private placement, named investors).
"""
import re

_CAPITAL_RETURN = re.compile(
    r'\b(?:re-?purchas\w*|buy-?backs?|buys?\s+back|bought\s+back|buying\s+back|dividends?|'
    r'redemptions?|redeem(?:s|ed|ing)?|capital\s+return|'
    r'return(?:s|ed|ing)?\s+(?:of\s+)?(?:capital|cash)\s+to\s+(?:shareholders|stockholders))\b',
    re.IGNORECASE)

_FUNDRAISING = re.compile(
    r'\b(?:pre-seed|seed\s+(?:round|funding|financing|investment)|series\s+[a-h]\b|'
    r'(?:funding|financing|investment|venture|equity|priced)\s+rounds?|'
    r'(?:equity|venture|convertible(?:\s+note)?|debt|preferred\s+stock)\s+financings?|'
    r'venture\s+(?:capital|funding|debt)|private\s+placements?|crowdfunding|capital\s+raise|'
    r'(?:raised|raising|secured|closed)\b[^.\n]{0,60}\bfrom\s+(?:new\s+and\s+existing\s+|existing\s+|new\s+)?'
    r'(?:investors?|backers|angels?|venture)|led\s+by)\b',
    re.IGNORECASE)


def names_capital_return(text):
    """True when the text names a repurchase, buyback, dividend or redemption."""
    return bool(_CAPITAL_RETURN.search(text or ''))


def names_fundraising(text):
    """True when the text uses an unambiguous fundraising term."""
    return bool(_FUNDRAISING.search(text or ''))


def describes_capital_return(text):
    """True when the text is about returning capital and never says it raised any.

    Such text cannot supply a funding figure or a raise amount.
    """
    return names_capital_return(text) and not names_fundraising(text)
