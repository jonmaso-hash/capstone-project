"""
Measurement-basis fidelity in a generated memo (RA-109; memo 98, graded partial pass, UB-604).

The grounded context carries a neutral note when two admitted usage claims count the same noun with the
same number on different bases ("500M messages" with no stated interval; "500M messages/month"). Memo 98
detected the question itself, then wrote in its risk section:

    "If the cumulative figure is being presented as a monthly figure, the key traction claim is
     materially overstated."

Nothing admitted makes the page-10 figure cumulative, and two bounded facts cannot show an overstatement:
they may measure different windows or definitions.

Each note is its own PAIR, with its own refs, sides and cumulative support (review of 2fb8530). A sentence
is acted on only when it resolves to exactly one pair:

    citations   every ref it cites belongs to that pair (a statement that repeats a pair claim's figure on
                the same page counts as the pair's); a sentence citing anything else is left alone
    noun        no citations, and the pair's counted noun ("messages") names exactly one pair
    paragraph   no citations and no noun: the nearest earlier sentence in the same paragraph or list item
                that resolved to a pair (memo 98's uncited sentence follows "[C3, S2] ... [C2, S3]")
    sole pair   no citations, and the context has exactly one pair

A sentence that names another metric (revenue, customers, users, ...) is never resolved. Then:

    judgment    a resolved sentence about the pair's bases (it names cumulative/monthly/interval/run rate
                or cites the pair) that calls a figure overstated, inflated, misleading or wrong becomes
                that pair's neutral clarification; its citations, all the pair's, are kept
    referent    in a resolved sentence, "the cumulative figure/total/count/..." becomes "the figure stated
                without an explicit interval", unless that pair itself admits a cumulative fact

Questions, indefinite conditional scenarios and other metrics are left as written. The word "cumulative"
is never replaced on its own, no citation is moved onto another pair's wording, and nothing here reads
source text: only the notes' refs and the admitted items' statements and pages.
"""
import re
from dataclasses import dataclass
from typing import Optional, Tuple

from .claim_context import _REF, _asks, _sentences
from .financial_metrics import CUMULATIVE_BASIS, usage_basis

MEASUREMENT_BASIS = 'measurement_basis'
UNSPECIFIED = 'the figure stated without an explicit interval'
_RATE_ADJECTIVE = {'month': 'monthly', 'week': 'weekly', 'day': 'daily', 'year': 'yearly'}

_CUMULATIVE_REFERENT = re.compile(
    r'\b(?P<the>[Tt])he\s+cumulative\s+(?:(?:messages?|bots?|usage)\s+)?(?:figure|total|count|number|metric|value)\b')
_BASIS_WORDS = re.compile(r'\b(?:cumulative(?:ly)?|monthly|weekly|daily|yearly|per\s+(?:month|week|day|year)|'
                          r'interval|run[- ]rate|measurement\s+bas[ie]s)\b|/\s?(?:month|week|day|year)\b', re.I)
_JUDGMENT = re.compile(r'\b(?:overstat\w*|inflat\w*|exaggerat\w*|mislead\w*|misrepresent\w*|incorrect\w*|'
                       r'erroneous\w*|wrong)\b', re.I)
# Metrics a usage-basis note says nothing about.
_OTHER_METRIC = re.compile(r'\b(?:revenues?|sales|arr|mrr|gmv|bookings|profit|margin|ebitda|income|burn|cash|'
                           r'runway|funding|raised|valuation|customers?|users?|subscribers?|clients?|accounts?|'
                           r'downloads?|employees?|headcount|market|tam)\b', re.I)
_LEAD = re.compile(r'^(?P<lead>\s*(?:[-•*·–]\s*)?)')


@dataclass(frozen=True)
class Pair:
    refs: Tuple[str, ...]              # the note's refs, in the note's order
    members: frozenset                 # those refs plus the statements repeating them
    noun: str                          # the counted noun both sides share ("messages")
    cumulative_admitted: bool          # this pair itself admits a cumulative fact
    clarification: str                 # the neutral sentence, worded from this pair's bases


@dataclass(frozen=True)
class BasisFacts:
    pairs: Tuple[Pair, ...] = ()      # empty: no note, so no sentence can resolve and nothing changes


def _side(item):
    basis = usage_basis(item.statement) if item is not None else None
    if basis is None or not basis.rate:
        return UNSPECIFIED, False, basis.noun if basis else ''
    if basis.rate == CUMULATIVE_BASIS:
        return 'the cumulative figure', True, basis.noun
    return f'the {_RATE_ADJECTIVE.get(basis.rate, basis.rate)} figure', False, basis.noun


def _page(item):
    return item.sources[0].page_number if item is not None and item.sources else None


def basis_facts(items, notes):
    """One Pair per measurement-basis note, each with only its own refs, bases and cumulative support."""
    by_ref = {item.ref: item for item in items}
    pairs = []
    for kind, refs, _ in notes or ():
        if kind != MEASUREMENT_BASIS or len(refs) != 2:
            continue
        sides = [_side(by_ref.get(ref)) for ref in refs]
        members = set(refs)
        for ref in refs:
            claim = by_ref.get(ref)
            if claim is None:
                continue
            members |= {item.ref for item in items if item.kind == 'statement'
                        and ' '.join(item.statement.split()) == ' '.join(claim.statement.split())
                        and _page(item) == _page(claim)}
        clarification = f'How {sides[0][0]} relates to {sides[1][0]} needs clarification before either is relied on'
        pairs.append(Pair(refs=tuple(refs), members=frozenset(members), noun=sides[0][2] or sides[1][2],
                          cumulative_admitted=any(side[1] for side in sides),
                          clarification=clarification[0].upper() + clarification[1:]))
    return BasisFacts(pairs=tuple(pairs))


def _cited(sentence):
    return [ref.strip() for group in _REF.findall(sentence) for ref in re.split(r'[,;]', group)]


def _resolve(sentence, facts, previous):
    """The one Pair this sentence is about, or None (see the module docstring)."""
    if _OTHER_METRIC.search(_REF.sub('', sentence)):
        return None
    cited = _cited(sentence)
    if cited:
        owners = {pair for pair in facts.pairs if set(cited) <= pair.members}
        return next(iter(owners)) if len(owners) == 1 else None
    named = [pair for pair in facts.pairs if pair.noun and re.search(rf'\b{re.escape(pair.noun[:-1])}s?\b', sentence, re.I)]
    if named:
        return named[0] if len(named) == 1 else None
    if previous is not None:
        return previous
    return facts.pairs[0] if len(facts.pairs) == 1 else None


def _judgment(sentence, pair, changes):
    """An error judgment about the pair's bases becomes its neutral clarification; its citations stay."""
    if _asks(sentence) or not _JUDGMENT.search(sentence):
        return sentence
    if not (_BASIS_WORDS.search(sentence) or _cited(sentence)):
        return sentence
    lead = _LEAD.match(sentence).group('lead')
    groups = ' '.join(f'[{group}]' for group in _REF.findall(sentence))
    changes.append('basis_overstatement')
    return f"{lead}{pair.clarification}{' ' + groups if groups else ''}."


def _referent(sentence, pair, changes):
    """"the cumulative figure" when this pair admits nothing cumulative: the figure has no stated interval."""
    if pair.cumulative_admitted or not _CUMULATIVE_REFERENT.search(sentence):
        return sentence
    changes.append('basis_cumulative_referent')
    return _CUMULATIVE_REFERENT.sub(lambda m: ('T' if m.group('the') == 'T' else 't') + UNSPECIFIED[1:], sentence)


def guard_basis_wording(text, facts):
    """Apply the rules to one memo section. Returns (text, changes). Without a basis note no sentence resolves."""
    if not isinstance(text, str) or not text:
        return text, []
    changes, out = [], []
    previous: Optional[Pair] = None          # the pair resolved earlier in this paragraph / list item
    for sentence, separator in _sentences(text):
        pair = _resolve(sentence, facts, previous)
        if pair is not None:
            sentence = _judgment(sentence, pair, changes)
            sentence = _referent(sentence, pair, changes)
            if _cited(sentence) or re.search(rf'\b{re.escape(pair.noun[:-1])}s?\b', sentence, re.I):
                previous = pair
        out.append(sentence + separator)
        if '\n' in separator:
            previous = None                  # a new paragraph or list item
    return (''.join(out) if changes else text), changes
