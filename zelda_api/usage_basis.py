"""
A usage figure split across two lines, and two usage figures stated on different bases (RA-109 / I1).

The frozen ManyChat deck sets slide 12's figure and its rate on adjacent lines:

    140 000+ bots
    500M
    messages/month
    Launching on Facebook

The analyzer reads one line at a time, so "500M" had no noun and
"messages/month" had no number, and the rate never became a claim. Slide 4
uses the same layout for other organisations' counts ("Telegram / 100M /
people"), which is why joining is narrow and refuses whenever the block could
belong to someone else:

  * one chunk only (this works on one chunk's text);
  * the figure line holds exactly one figure and nothing else;
  * the very next line is a usage noun with an optional supported rate, and
    nothing else -- no blank line, prose or second figure between them;
  * the BLOCK's owner is resolved, not just the neighbouring line's. Walking
    up across layout blank lines and sibling metric lines ("140 000+ bots"),
    the first other line must be a generic heading made of metric/time words
    ("Traction by Apr-16") or the document's own subject ("ManyChat", from
    the names the caller knows), or the chunk must start. Any other line --
    "Telegram", "FB Messenger", a prose sentence, a bare figure -- leaves the
    pair unjoined. Walking down the same way, a line that continues the
    figure ("via Telegram") or an organisation label ("Telegram Messaging
    Service") refuses; an ordinary statement ("Launching on Facebook") ends
    the block.

The claim task admits a usage span that only exists by joining lines when,
and only when, this same rule (with the document's subject names) joined it.
The owner is never inferred from the joined span alone.

The second half: once both figures survive, "500M messages" (no stated
interval) and "500M messages/month" are an internal measurement-basis
question for the reader, stated as such. Not external verification, not a
contradiction, and not a claim that both cannot be true.
"""
import re
from dataclasses import dataclass
from typing import Tuple

from .claim_attribution import _COMPANY, _LEGAL_SUFFIXES, _NOT_AN_OWNER, _SENTENCE, _mask_company
from .financial_metrics import CUMULATIVE_BASIS, basis_from_unit

# The same figure shape the analyzer uses for Traction counts
# (ZeldaIntelligencePipelineV2._TRACTION_NUMBER); tests assert they are equal.
TRACTION_NUMBER = (r'(?<![\w.,])(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?![\d.,])|[\d,]*\.?\d+)'
                   r'(?:[KkMmBb](?![A-Za-z])|\s*(?:thousand|million|billion)\b|(?!\w))\+?')

_FIGURE_LINE = re.compile(r'\s*' + TRACTION_NUMBER + r'\s*')
_UNIT_LINE = re.compile(
    r'\s*(?:(?:monthly|weekly|daily|yearly|annual)\s+)?(?:bots?|messages?)'
    r'(?:\s*(?:/|\bper\b)\s*(?:month|mo|week|wk|day|year|yr)\b)?\s*', re.IGNORECASE)
# A sibling metric in the same block: a figure, then up to four words naming it,
# none of them a capitalised name ("140 000+ bots", "2M messages/month").
_SIBLING_FIGURE_LINE = re.compile(r'\s*' + TRACTION_NUMBER + r'\s*(?P<words>[^\d]+?)\s*', re.IGNORECASE)
# A line that carries the figure on: a lower-case start, or a connective in any case.
_CONTINUATION = re.compile(r'^\s*(?:[a-z]|(?i:on|via|across|from|in|at|through|by|for|of|with|to)\b)')
_HEADING_WORDS = _NOT_AN_OWNER | {'by', 'in', 'as', 'of', 'at', 'since', 'through', 'until', 'and'}

# Why a split pair was not joined; read back by the claim layer.
OWNER_LABEL = 'owner_label'
UNBOUNDED = 'unbounded'


@dataclass(frozen=True)
class Refusal:
    figure: str          # the figure line, stripped
    unit: str            # the unit line, stripped
    reason: str          # OWNER_LABEL or UNBOUNDED
    label: str = ''      # the line that may name an owner, when there is one

    @property
    def span(self):
        return f'{self.figure} {self.unit}'


def _generic_heading(line):
    words = [w for w in re.split(r'[^A-Za-z0-9]+', line.lower()) if w]
    return bool(words) and all(w in _HEADING_WORDS or re.fullmatch(r'\d{1,4}', w) for w in words)


def _subject_label(line, names):
    """The line is the document's own subject name (legal suffixes allowed), and nothing else."""
    if not names:
        return False
    masked = _mask_company(line, names)
    if _COMPANY not in masked:
        return False
    rest = [w for w in re.split(r'[^A-Za-z0-9]+', masked.replace(_COMPANY, ' ').lower()) if w]
    return all(w in _LEGAL_SUFFIXES for w in rest)


def _sibling(line):
    """A sibling metric line: a figure and a few lower-case/generic words, no name in it."""
    match = _SIBLING_FIGURE_LINE.fullmatch(line)
    if not match or not re.search(r'[A-Za-z]', match['words']):
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", match['words'])
    return len(words) <= 4 and all(w[0].islower() or w.lower() in _HEADING_WORDS for w in words)


def _name_label(line):
    """A short title-case line with no figure and no lower-case word: an organisation's name."""
    words = line.split()
    if not 0 < len(words) <= 6 or re.search(r'\d', line) or _generic_heading(line):
        return False
    return all(not re.match(r'[A-Za-z]', w) or w[0].isupper() for w in words)


def _block_label_above(lines, i, names):
    """(reason, label) for the block over the figure line at i: None when it is resolved."""
    for j in range(i - 1, -1, -1):
        line = lines[j].strip()
        if not line:
            continue                                  # layout whitespace: the same block
        if _FIGURE_LINE.fullmatch(line):
            return UNBOUNDED, line                    # a bare figure: an axis or a list
        if _sibling(line):
            continue                                  # another metric in the same block
        if _generic_heading(line) or _subject_label(line, names):
            return None, ''
        return OWNER_LABEL, line                      # a name or prose: the owner is not ours
    return None, ''


def _block_label_below(lines, j, names):
    """(reason, label) for the block under the unit line at j - 1: None when nothing claims it."""
    for k in range(j, len(lines)):
        line = lines[k].strip()
        if not line:
            continue
        if _CONTINUATION.match(line):
            return OWNER_LABEL, line                  # carries the figure on ("via Telegram")
        if _FIGURE_LINE.fullmatch(line):
            return None, ''                           # the next figure starts another pair
        if _sibling(line):
            continue
        if _generic_heading(line) or _subject_label(line, names):
            return None, ''
        if _name_label(line):
            return OWNER_LABEL, line                  # a caption naming an organisation
        return None, ''                               # an ordinary statement ends the block
    return None, ''


def scan_split_usage_lines(text, names=()):
    """
    (joined_text, refusals). joined_text is `text` with each admitted figure
    line and unit line joined by one space; every other line is unchanged.
    refusals lists the figure/unit pairs that were NOT joined, with the reason.
    `names` are the document's own subject names; without them a label naming
    the subject is an unknown owner and refuses.
    """
    lines = (text or '').split('\n')
    out, refusals, i = [], [], 0
    while i < len(lines):
        line = lines[i]
        if (i + 1 < len(lines) and _FIGURE_LINE.fullmatch(line) and lines[i + 1].strip()
                and not re.search(r'\d', lines[i + 1])):
            figure, unit = line.strip(), lines[i + 1].strip()
            if _UNIT_LINE.fullmatch(unit):
                reason, label = _block_label_above(lines, i, names)
                if reason is None:
                    reason, label = _block_label_below(lines, i + 2, names)
                if reason is None:
                    out.append(f'{figure} {unit}')
                    i += 2
                    continue
                refusals.append(Refusal(figure, unit, reason, label))
        out.append(line)
        i += 1
    return '\n'.join(out), refusals


def join_split_usage_lines(text, names=()):
    """`text` with every admissible figure/unit line pair joined (see the module docstring)."""
    return scan_split_usage_lines(text, names)[0]


def _norm(text):
    return ' '.join((text or '').split())


def in_raw_sentence(span, chunk_text):
    """The span is part of one of the chunk's own sentences, with no line joined."""
    span = _norm(span)
    return bool(span) and any(span in _norm(s) for s in _SENTENCE.split((chunk_text or '').replace('\r\n', '\n')))


def admitted_join(span, chunk_text, names=()):
    """True when the join rule, with the document's subject names, produced the line `span` starts with."""
    span = _norm(span)
    original = {_norm(line) for line in (chunk_text or '').replace('\r\n', '\n').split('\n')}
    joined = scan_split_usage_lines((chunk_text or '').replace('\r\n', '\n'), names)[0].split('\n')
    return any(line and line not in original and span.startswith(line) for line in (_norm(x) for x in joined))


def unresolved_split(span, chunk_text, names=()):
    """
    For the claim task. The span is in none of its chunk's sentences, its figure
    stands alone on a line of that chunk -- so the span exists only by joining
    lines -- and the join rule, with the document's subject names, did not join
    that pair: the block's owner is unresolved (another organisation's label
    across a blank line or a sibling metric, prose between number and noun).
    Such a span is refused; its owner is never read from the bare joined span.
    """
    if in_raw_sentence(span, chunk_text):
        return False
    figure = re.match(r'\s*' + TRACTION_NUMBER, span or '')
    if figure is None:
        return False
    lines = {_norm(line) for line in (chunk_text or '').replace('\r\n', '\n').split('\n')}
    if _norm(figure.group(0)) not in lines:
        return False
    return not admitted_join(span, chunk_text, names)


# --- the measurement-basis note -------------------------------------------------

@dataclass(frozen=True)
class BasisNote:
    claim_ids: Tuple[int, ...]
    pages: Tuple[object, ...]
    text: str
    kind: str = 'measurement_basis'


def format_count(value):
    """500000000 -> '500M', 140000 -> '140,000', 1500000 -> '1.5M'."""
    for size, suffix in ((1e9, 'B'), (1e6, 'M')):
        if abs(value) >= size:
            scaled = value / size
            return (f'{scaled:.0f}' if scaled == int(scaled) else f'{scaled:.1f}'.rstrip('0').rstrip('.')) + suffix
    return f'{value:,.0f}' if value == int(value) else f'{value:,}'


def _describe(value, basis):
    figure = f'{format_count(value)} {basis.noun}'
    if basis.rate == CUMULATIVE_BASIS:
        return f'{figure} as a cumulative total'
    if basis.rate:
        return f'{format_count(value)} {basis.label}'
    return f'{figure} without an explicit interval'


def _where(page):
    return f'page {page}' if page is not None else 'an unnumbered page'


def basis_notes(claims):
    """
    One note per pair of usage claims that count the same noun with the same
    number on different bases. Built from the stored, admitted claims only
    (category, value, unit, page, id) -- never source text. Same-basis
    repetitions and different nouns or numbers get no note.
    """
    usage = []
    for claim in claims:
        if claim.category != 'usage' or claim.claimed_value_numeric is None:
            continue
        basis = basis_from_unit(claim.unit)
        if basis is not None:
            usage.append((claim, basis))
    # Page order, then id: the note reads the same however the claims are ordered.
    usage.sort(key=lambda pair: (pair[0].page_number is None, pair[0].page_number or 0, pair[0].id or 0))
    notes, seen = [], set()
    for n, (a, basis_a) in enumerate(usage):
        for b, basis_b in usage[n + 1:]:
            if basis_a.noun != basis_b.noun or basis_a.rate == basis_b.rate:
                continue
            if a.claimed_value_numeric != b.claimed_value_numeric:
                continue
            key = (basis_a.noun, a.claimed_value_numeric, basis_a.rate, basis_b.rate)
            if key in seen:
                continue
            seen.add(key)
            first = _where(a.page_number)
            text = (f'{first[0].upper()}{first[1:]} states {_describe(a.claimed_value_numeric, basis_a)}; '
                    f'{_where(b.page_number)} states {_describe(b.claimed_value_numeric, basis_b)}. '
                    'These use different measurement bases and need clarification before comparison.')
            notes.append(BasisNote(claim_ids=(a.id, b.id), pages=(a.page_number, b.page_number), text=text))
    return notes
