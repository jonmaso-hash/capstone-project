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
# A line that is only a figure and a few words naming it: "140 000+ bots",
# "500M messages", "$5M raised", or a bare chart value "20,000". A line with a
# second number, a sentence stop or more words is prose ("Up 3x in 6 months",
# "12 employees hired."), and prose ends the block even when it holds numbers.
_FIGURE_LINE = re.compile(
    r"^(?:~|≈|>\s*|<\s*)?[$€£]?\d{1,3}(?:[ ,.]?\d{3})*(?:\.\d+)?\s?"
    r"(?:%|x|bn|mm|[kmb]|million|billion|thousand)?\+?"
    r"(?:\s+[A-Za-z][A-Za-z/&’'-]*){0,3}$", re.I)


def _norm(text):
    return ' '.join((text or '').split())


def _figure_line(line):
    return bool(_FIGURE_LINE.match(line))


def dated_heading(span, chunk_text):
    """
    The dated heading over the block that holds `span`, or ''.

    The figure's own line must be a figure line (a number and up to three
    words naming it). Walk up across sibling figure lines, e.g. the other
    metrics in the same list. The first line that is not a figure line ends
    the block: it is returned only if it is a short heading that dates the
    block with a preposition ("Traction by Apr-16") and carries words of its
    own. A bare axis label ("Apr-16"), an undated heading ("Total Bots
    Created") or a prose line -- with or without numbers in it -- stops the
    walk with nothing. When in doubt, nothing is associated.
    """
    span = _norm(span)
    if not span:
        return ''
    lines = (chunk_text or '').splitlines()
    index = next((i for i, line in enumerate(lines) if span in _norm(line)), None)
    if index is None or not _figure_line(_norm(lines[index])):
        return ''
    for line in reversed(lines[:index]):
        line = _norm(line)
        if not line:
            continue
        if _figure_line(line):
            continue                     # a sibling figure in the same list
        match = _DATED_HEADING.search(line)
        if match and len(line) <= _HEADING_MAX and re.search(r'[A-Za-z]{3,}', line[:match.start()]):
            return line
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
_REF_GROUP = r'\[[A-Z]\d+(?:\s*[,;]\s*[A-Z]\d+)*\]'
_REF = re.compile(r'\[([A-Z]\d+(?:\s*[,;]\s*[A-Z]\d+)*)\]')
# A sentence ends at . ! or ? together with any closing quote and any citations
# written straight after it ("...raised $23.1M to date. [S3]"), then whitespace;
# or at a line break. The citations belong to the sentence they follow, never
# to the next one.
_BOUNDARY = re.compile(rf'[.!?]["”’)]*(?:[ \t]*{_REF_GROUP})*(?P<sep>\s+|\Z)|(?P<nl>\n+)')
# A sentence that asks for a figure rather than stating one: a research
# question ("What has ManyChat raised to date [S3]?") or a request to
# management ("Confirm the total raised to date [S3].").
_LIST_MARKER = re.compile(r'^(?:[-•*·–]|\d+[.)]|Q\d+[:.)])\s*')
_REQUEST_LEAD = re.compile(
    r'^(?:ask|confirm|verify|clarify|request|obtain|provide|explain|disclose|validate|'
    r'check|determine|quantify|reconcile|break\s+down)\b', re.I)


def time_wording_in(sentence):
    """The TIME_WORDING phrases a source sentence itself uses (lower case)."""
    text = _norm(sentence).lower()
    return tuple(p for p in TIME_WORDING if re.search(rf'\b{re.escape(p)}\b', text))


def _sentences(text):
    """(sentence, separator) pairs that join back into `text` exactly."""
    pos = 0
    for match in _BOUNDARY.finditer(text):
        group = 'sep' if match.group('sep') is not None else 'nl'
        yield text[pos:match.start(group)], match.group(group)
        pos = match.end()
    if pos < len(text):
        yield text[pos:], ''


def _asks(sentence):
    """True for a question or a request for a figure, which asserts nothing."""
    body = _LIST_MARKER.sub('', _REF.sub('', sentence).strip())
    return body.rstrip('"”’) ').endswith('?') or bool(_REQUEST_LEAD.match(body))


def _restore_opening(original, rewritten):
    """
    "As of today, the $23.1M ..." loses its opening phrase: the rest starts the sentence (or the
    bullet) again, without a leading space and with the capital the original opening had.
    """
    marker = _LIST_MARKER.match(original.lstrip())
    lead = original[:len(original) - len(original.lstrip())] + (marker.group(0) if marker else '')
    if not rewritten.startswith(lead):
        return rewritten
    body = rewritten[len(lead):].lstrip()
    opening = original[len(lead):].lstrip()[:1]
    if body and opening.isupper() and body[:1].islower():
        body = body[:1].upper() + body[1:]
    return lead + body


def guard_time_wording(text, allowed_by_ref):
    """
    Remove current/running-total wording from memo sentences that STATE a
    figure while citing a claim-backed item whose source does not use that
    wording.

    `allowed_by_ref` maps a cited ref ("C1", "S3") to the phrases its source
    sentence uses. Only refs present in the map are guarded; a sentence that
    cites none of them is left as written, and so is a question or request
    asking management for a current figure.
    """
    if not isinstance(text, str) or not text:
        return text, []
    removed = []
    out = []
    for sentence, separator in _sentences(text):
        refs = [r.strip() for group in _REF.findall(sentence) for r in re.split(r'[,;]', group)]
        guarded = [r for r in refs if r in allowed_by_ref]
        if guarded and not _asks(sentence):
            def drop(match):
                phrase = match.group(1).lower()
                if all(phrase in allowed_by_ref[r] for r in guarded):
                    return match.group(0)
                removed.append(phrase)
                # "$23.1M to date[S3]" keeps one space before its citation.
                follows = match.string[match.end():match.end() + 1]
                return ' ' if follows == '[' and match.group(0)[:1].isspace() else ''
            rewritten = _TIME_WORDING.sub(drop, sentence)
            if rewritten != sentence:
                rewritten = re.sub(r' {2,}', ' ', rewritten)
                rewritten = re.sub(r' +([,.;:])', r'\1', rewritten)
                rewritten = _restore_opening(sentence, rewritten)
                sentence = rewritten
        out.append(sentence + separator)
    return (''.join(out) if removed else text), removed
