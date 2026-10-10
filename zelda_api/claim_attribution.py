"""
Whose figure is this? Company ownership of a claim, decided before it is stored.

A correctly parsed number still produces a wrong result when it belongs to
someone else. The frozen audit decks name the two shapes: ManyChat's slide 4
lists Messenger's, Kik's and Telegram's user counts (key M2-M4), and Ben &
Jerry's page 10 says "Unilever's ice cream unit generated EUR 7.9B" (key C5).
Either presented as the company's own is an ATTRIBUTION ERROR.

The rule is deliberately narrow, so it can be audited:

    named      the source sentence names the company itself
    implied    the company's own document, and no other owner is named
    third party  another organisation owns the figure: a possessive
               ("Unilever's ice cream unit ...") or another organisation as
               the sentence's subject ("Telegram has 100M users")

Named and implied are both company-provided claims; neither is evidence that
the figure is true. A third-party figure is not a company claim at all and is
never stored as one. A stored claim with no ownership was recorded before
this rule and its ownership is unknown -- it is never backfilled.

Known limitation: a figure next to another organisation's name with no
possessive and no verb ("FB Messenger 900M people", when a deck sets the
three on separate lines) is not recognised here. Those lines do not reach
the claim layer today; any change that joins lines must add that case.
"""
import re

NAMED = 'named'
IMPLIED = 'implied'

# Sentence units, split the way the analyzer reads them (_smart_extract).
_SENTENCE = re.compile(r'(?<!\d)[.!?](?!\d)|\n')

_COMPANY = '\x00COMPANY\x00'
_LEGAL_SUFFIXES = {'inc', 'incorporated', 'corp', 'corporation', 'llc', 'ltd', 'limited', 'co', 'plc', 'gmbh', 'bv', 'sa'}
_PROPER = r"[A-Z][A-Za-z0-9&\-]*"
_POSSESSIVE = re.compile(r"(" + _PROPER + r"(?:\s+" + _PROPER + r")*)\s*['’]s\b")
_OWNING_VERBS = (r'has|had|have|generated|generates|reported|reports|raised|raises|reached|reaches|'
                 r'serves|served|counts|counted|announced|claims|claimed|posted|recorded|surpassed|hit')
_SUBJECT = re.compile(
    r"^\W*(?:[A-Za-z]+:\s*)?((?:" + _PROPER + r"\s+){0,3}" + _PROPER + r")\s+(?:" + _OWNING_VERBS + r")\b")

# Capitalised words that start or fill a sentence without naming an owner:
# pronouns, determiners, time words and the metric nouns decks lead with.
# A phrase made only of these is not another organisation.
_NOT_AN_OWNER = {
    'we', 'our', 'it', 'its', 'they', 'their', 'this', 'that', 'these', 'those', 'the', 'a', 'an',
    'company', 'business', 'team', 'management', 'founder', 'founders', 'ceo', 'platform', 'product',
    'year', 'last', 'next', 'today', 'month', 'quarter', 'fy', 'q1', 'q2', 'q3', 'q4', 'ytd', 'h1', 'h2',
    'revenue', 'revenues', 'sales', 'arr', 'mrr', 'gmv', 'ebitda', 'income', 'profit', 'bookings',
    'funding', 'capital', 'traction', 'growth', 'customers', 'customer', 'users', 'user', 'clients',
    'subscribers', 'members', 'downloads', 'employees', 'headcount', 'staff', 'total', 'annual',
    'monthly', 'weekly', 'daily', 'current', 'cumulative', 'net', 'gross', 'average', 'market', 'tam',
    'sam', 'som', 'series', 'seed', 'round', 'valuation', 'burn', 'runway', 'retention', 'churn',
    'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september',
    'october', 'november', 'december', 'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep',
    'sept', 'oct', 'nov', 'dec', 'source', 'note', 'over', 'more', 'nearly', 'almost', 'about',
}


def company_names(document):
    """The names this document's company goes by: its stated subject and, for
    the uploader's own document, the uploader's business profile name."""
    names = []
    entity = (getattr(document, 'source_entity', '') or '').strip()
    if entity and entity.lower() != 'unknown':
        names.append(entity)
    if not getattr(document, 'is_external_subject', False):
        user = getattr(document, 'uploaded_by', None)
        for attr in ('match_founder_profile', 'match_seller_profile'):
            profile = getattr(user, attr, None) if user is not None else None
            name = (getattr(profile, 'company_name', '') or '').strip() if profile is not None else ''
            if name and name not in names:
                names.append(name)
    return names


def _name_pattern(name):
    words = [w for w in re.split(r'[^A-Za-z0-9]+', name.lower()) if w]
    while len(words) > 1 and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    if not words or (len(words) == 1 and len(words[0]) < 3):
        return None
    return re.compile(r'(?<![A-Za-z0-9])' + r'\W+'.join(map(re.escape, words)) + r'(?![A-Za-z0-9])', re.I)


def _mask_company(sentence, names):
    for name in names:
        pattern = _name_pattern(name)
        if pattern:
            sentence = pattern.sub(_COMPANY, sentence)
    return sentence


def _is_owner(phrase):
    """True when a capitalised phrase names an organisation rather than a
    pronoun, a time word or a metric noun."""
    words = [w.lower() for w in re.split(r'\s+', phrase.strip()) if w]
    return bool(words) and not all(
        w in _NOT_AN_OWNER or re.fullmatch(r'(?:fy|cy|q[1-4]|h[12])?-?\d{2,4}', w) for w in words)


# Connectives that open a sentence in front of an owner's name ("Unlike
# Salesforce's ..."). Trimmed from the reported owner only; they never decide.
_LEADING_CONNECTIVES = {'unlike', 'like', 'per', 'according', 'compared', 'versus', 'vs', 'while',
                        'whereas', 'including', 'both', 'and', 'but', 'with', 'than', 'beyond'}


def _owner_name(phrase):
    words = phrase.split()
    while len(words) > 1 and (words[0].lower() in _LEADING_CONNECTIVES or words[0].lower() in _NOT_AN_OWNER):
        words.pop(0)
    return ' '.join(words)


def source_sentence(text, chunk_text):
    """The whole source sentence an extracted span came from, or the span itself."""
    span = ' '.join((text or '').split())
    for sentence in _SENTENCE.split(chunk_text or ''):
        if span and span in ' '.join(sentence.split()):
            return ' '.join(sentence.split())
    return span


def claim_ownership(sentence, names):
    """
    (ownership, owner): ownership is NAMED, IMPLIED or None for a third-party
    figure, in which case owner names who the sentence says it belongs to.
    """
    masked = _mask_company(sentence or '', names)
    for match in _POSSESSIVE.finditer(masked):
        if _is_owner(match.group(1)):
            return None, _owner_name(match.group(1))
    if _COMPANY in masked:
        return NAMED, ''
    subject = _SUBJECT.match(masked)
    if subject and _is_owner(subject.group(1)):
        return None, _owner_name(subject.group(1))
    return IMPLIED, ''
