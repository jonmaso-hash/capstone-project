"""
What surrounds a claim's figure, kept as CONTEXT and never as its period
(ManyChat RA-102 / RA-106).

The claim layer keeps a figure's own-sentence period (claim_periods) for
comparison. That rule stays: a heading on another line never becomes the
claim's period, and a bare year never does either. But dropping everything
else lost things a reader needs:

    slide 2   "Source: Pitch Deck Hunt lists ManyChat as a 2015 Series A deck
              with $23.1M raised."   -> a third party's listing, and "2015"
              describes the DECK, not when $23.1M was counted
    slide 10  "Traction by Apr-16" over "140 000+ bots" / "500M messages"
              -> the slide dates its figures, in a heading

and the memo, given only "$23.1M raised", wrote "The company states it has
raised $23.1M to date" -- a 2016-era listing presented as a current total.

This module recovers that context, bounded, for display and for the memo:

    dated_heading()      a dated heading directly above the figure's block
    claim_narrator()     who the sentence says reports the figure
    unbound_dates()      dates in the sentence that are NOT the figure's period
    guard_time_wording() removes "to date" / "currently" / ... that a memo
                         attaches to a figure whose own source says no such thing

None of it changes a claim's structured period, Truth Delta's comparison or
its score.
"""
import logging
import re

logger = logging.getLogger(__name__)

_MONTH = r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?'
_DATE = rf"(?:{_MONTH}[\s\-'.]*(?:\d{{4}}|\d{{2}})\b|(?:Q[1-4]\s*)?(?:19|20)\d{{2}}\b)"
# "by Apr-16", "as of Dec 2024", "through Q3 2023": a heading that dates a block.
_DATED_HEADING = re.compile(rf'\b(?:by|as\s+of|through|thru|until|ending|ended)\s+{_DATE}', re.I)
_HEADING_MAX = 80
_FIGURE_LINE_MAX = 40


def _norm(text):
    return ' '.join((text or '').split())


def dated_heading(span, chunk_text):
    """
    The dated heading over the block that holds `span`, or ''.

    Walk up from the figure's line across sibling figure lines (short lines
    with a number, e.g. the other metrics in the same list). The first line
    that is not a figure line ends the block: it is returned only if it is a
    short heading that dates the block with a preposition ("Traction by
    Apr-16") and carries words of its own. A bare axis label ("Apr-16"), an
    undated heading ("Total Bots Created") or a prose line stops the walk
    with nothing.
    """
    span = _norm(span)
    if not span:
        return ''
    lines = (chunk_text or '').splitlines()
    index = next((i for i, line in enumerate(lines) if span in _norm(line)), None)
    if index is None:
        return ''
    for line in reversed(lines[:index]):
        line = _norm(line)
        if not line:
            continue
        match = _DATED_HEADING.search(line)
        if match and len(line) <= _HEADING_MAX and re.search(r'[A-Za-z]{3,}', line[:match.start()]):
            return line
        if len(line) <= _FIGURE_LINE_MAX and re.search(r'\d', line) and not match:
            continue                     # a sibling figure in the same list
        return ''
    return ''


# "Source: Pitch Deck Hunt lists ManyChat as ...", "Crunchbase reports ...".
_NAME = r"[A-Z][\w&.'’-]*(?:\s+[A-Z][\w&.'’-]*){0,5}"
_NARRATED_LEAD = re.compile(
    rf"^(?i:source:\s*)?(?i:the\s+)?(?P<name>{_NAME})\s+"
    r"(?:lists|listed|reports|reported|says|said|states|stated|estimates|estimated|"
    r"ranks|ranked|describes|described|notes|noted|shows|showed|records|recorded)\b")
_NARRATED_INLINE = re.compile(
    rf"\b(?i:according\s+to|as\s+reported\s+by|reported\s+by|per)\s+(?i:the\s+)?(?P<name>{_NAME})")
_NOT_A_NARRATOR = {'we', 'our', 'us', 'it', 'they', 'this', 'the company', 'company', 'management', 'i'}


def claim_narrator(sentence, names=()):
    """Who the sentence says reports the figure, when that is not the company itself; else ''."""
    sentence = _norm(sentence)
    company = {_norm(n).lower() for n in names if n}
    for pattern in (_NARRATED_LEAD, _NARRATED_INLINE):
        match = pattern.search(sentence)
        if not match:
            continue
        name = match.group('name').strip(" .,:;'’")
        if name.lower() in _NOT_A_NARRATOR or name.lower() in company:
            continue
        if any(name.lower() in c or c in name.lower() for c in company):
            continue
        return name
    return ''


_ANY_DATE = re.compile(rf'(?i:{_MONTH})[\s\-\'.]*(?:\d{{4}}|\d{{2}})\b|\b(?:FY\s?)?(?:19|20)\d{{2}}\b')


def unbound_dates(sentence, period_phrase=''):
    """Dates written in the sentence that are not the figure's own period phrase, in order."""
    bound = _norm(period_phrase).lower()
    seen = []
    for match in _ANY_DATE.finditer(_norm(sentence)):
        token = match.group(0).strip()
        if bound and token.lower() in bound:
            continue
        if token not in seen:
            seen.append(token)
    return seen


# Wording that makes a figure current or a running total. A memo may use it
# only when the figure's own source sentence does.
TIME_WORDING = ('to date', 'so far', 'currently', 'at present', 'as of today', 'as of now',
                'as it stands', 'up to now', 'until now')
_TIME_WORDING = re.compile(r'\s*,?\s*\b(' + '|'.join(re.escape(p) for p in TIME_WORDING) + r')\b,?', re.I)
_REF = re.compile(r'\[([A-Z]\d+(?:\s*,\s*[A-Z]\d+)*)\]')
# Captured, so splitting keeps each separator (spaces, newlines, bullets) as written.
_SENTENCE = re.compile(r'((?<=[.!?])\s+|\n+)')


def time_wording_in(sentence):
    """The TIME_WORDING phrases a source sentence itself uses (lower case)."""
    text = _norm(sentence).lower()
    return tuple(p for p in TIME_WORDING if re.search(rf'\b{re.escape(p)}\b', text))


def guard_time_wording(text, allowed_by_ref):
    """
    Remove current/running-total wording from memo sentences that cite a
    claim-backed item whose source does not use that wording.

    `allowed_by_ref` maps a cited ref ("C1", "S3") to the phrases its source
    sentence uses. Only refs present in the map are guarded; a sentence that
    cites none of them is left as written.
    """
    if not isinstance(text, str) or not text:
        return text, []
    removed = []
    out = []
    for sentence in _SENTENCE.split(text):
        if _SENTENCE.fullmatch(sentence):
            out.append(sentence)         # a separator, kept exactly
            continue
        refs = [r.strip() for group in _REF.findall(sentence) for r in group.split(',')]
        guarded = [r for r in refs if r in allowed_by_ref]
        if guarded:
            def drop(match):
                phrase = match.group(1).lower()
                if all(phrase in allowed_by_ref[r] for r in guarded):
                    return match.group(0)
                removed.append(phrase)
                return ''
            rewritten = _TIME_WORDING.sub(drop, sentence)
            if rewritten != sentence:
                rewritten = re.sub(r' {2,}', ' ', rewritten)
                rewritten = re.sub(r' +([,.;:])', r'\1', rewritten)
                rewritten = re.sub(r'(\S)\[', r'\1 [', rewritten)
                sentence = rewritten
        out.append(sentence)
    return (''.join(out) if removed else text), removed
