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
  * the line above is empty, a sibling figure line ("140 000+ bots"), or a
    generic heading made of metric/time words ("Traction by Apr-16"). Any
    other label above ("Telegram", "FB Messenger", even the company's own
    name) may name the owner, so the pair is left unjoined;
  * the line below does not continue the figure ("via Telegram", "on
    partner platforms") and is not a bare organisation label.

The second half: once both figures survive, "500M messages" (no stated
interval) and "500M messages/month" are an internal measurement-basis
question for the reader, stated as such. Not external verification, not a
contradiction, and not a claim that both cannot be true.
"""
import re
from dataclasses import dataclass
from typing import Tuple

from .claim_attribution import _NOT_AN_OWNER
from .financial_metrics import CUMULATIVE_BASIS, basis_from_unit

# The same figure shape the analyzer uses for Traction counts
# (ZeldaIntelligencePipelineV2._TRACTION_NUMBER); tests assert they are equal.
TRACTION_NUMBER = (r'(?<![\w.,])(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?![\d.,])|[\d,]*\.?\d+)'
                   r'(?:[KkMmBb](?![A-Za-z])|\s*(?:thousand|million|billion)\b|(?!\w))\+?')

_FIGURE_LINE = re.compile(r'\s*' + TRACTION_NUMBER + r'\s*')
_UNIT_LINE = re.compile(
    r'\s*(?:(?:monthly|weekly|daily|yearly|annual)\s+)?(?:bots?|messages?)'
    r'(?:\s*(?:/|\bper\b)\s*(?:month|mo|week|wk|day|year|yr)\b)?\s*', re.IGNORECASE)
_SIBLING_FIGURE_LINE = re.compile(TRACTION_NUMBER + r'\s*\S', re.IGNORECASE)
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


def _owner_label_below(line):
    """A short line with no figure that is not a generic word: another party's name, possibly."""
    words = line.split()
    return 0 < len(words) <= 2 and not re.search(r'\d', line) and not _generic_heading(line)


def scan_split_usage_lines(text):
    """
    (joined_text, refusals). joined_text is `text` with each admitted figure
    line and unit line joined by one space; every other line is unchanged.
    refusals lists the figure/unit pairs that were NOT joined, with the reason.
    """
    lines = (text or '').split('\n')
    out, refusals, i = [], [], 0
    while i < len(lines):
        line = lines[i]
        if (i + 1 < len(lines) and _FIGURE_LINE.fullmatch(line) and lines[i + 1].strip()
                and not re.search(r'\d', lines[i + 1])):
            figure, unit = line.strip(), lines[i + 1].strip()
            if _UNIT_LINE.fullmatch(unit):
                above = lines[i - 1].strip() if i > 0 else ''
                below = lines[i + 2].strip() if i + 2 < len(lines) else ''
                reason, label = None, ''
                if above and _FIGURE_LINE.fullmatch(above):
                    reason, label = UNBOUNDED, above          # a bare figure above: an axis or a list
                elif above and not ((_SIBLING_FIGURE_LINE.match(above) and re.search(r'[A-Za-z]', above))
                                    or _generic_heading(above)):
                    reason, label = OWNER_LABEL, above
                elif below and _CONTINUATION.match(below):
                    reason, label = OWNER_LABEL, below
                elif below and _owner_label_below(below):
                    reason, label = OWNER_LABEL, below
                if reason is None:
                    out.append(f'{figure} {unit}')
                    i += 2
                    continue
                refusals.append(Refusal(figure, unit, reason, label))
        out.append(line)
        i += 1
    _unbounded_pairs(lines, refusals)
    return '\n'.join(out), refusals


def _unbounded_pairs(lines, refusals):
    """A figure line and a unit line in the same chunk that are NOT adjacent (prose or a
    blank line between them): recorded so a claim spanning them can be refused."""
    for i, line in enumerate(lines):
        if not _FIGURE_LINE.fullmatch(line):
            continue
        for j in range(i + 2, len(lines)):
            if _UNIT_LINE.fullmatch(lines[j].strip()) and lines[j].strip():
                refusals.append(Refusal(line.strip(), lines[j].strip(), UNBOUNDED))
                break


def join_split_usage_lines(text):
    """`text` with every admissible figure/unit line pair joined (see the module docstring)."""
    return scan_split_usage_lines(text)[0]


def refused_split(span, chunk_text):
    """The Refusal whose joined form is `span`, or None. For the claim layer: a usage span
    that only exists by joining lines this module refused must not become a claim."""
    span = ' '.join((span or '').split())
    for refusal in scan_split_usage_lines(chunk_text)[1]:
        if span.startswith(refusal.span):
            return refusal
    return None


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
