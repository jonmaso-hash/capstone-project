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
    antecedent  no citations and no noun, but a definite figure referent ("the cumulative figure"), and the
                discussion before it in the same paragraph or list item is still about one pair: the last
                sentence resolved to it, with only bridge sentences between. A bridge is a complete, known
                measurement-basis sentence, matched whole: "These use different measurement bases.", with
                memo 98's "... and cannot be compared or reconciled without clarification from management."
                or the note's "... and need clarification before comparison." (review of c297ec3: an
                anaphoric opener alone let "This revenue figure is unaudited." carry the pair). Memo 98's
                uncited sentence follows "[C3, S2] ... [C2, S3]. These use ...".

There is no sole-pair fallback (review of 3e0fa33): one note does not make every monthly or cumulative
sentence about it. Any other sentence ends the antecedent, so a different metric in between ("Revenue is
reported as $10M.") leaves the next referent unresolved. A sentence naming a listed other metric
(revenue, customers, users, ...) is never resolved either; that list is a backstop, not the gate. Then:

    judgment    a resolved sentence about the pair's bases (it names cumulative/monthly/interval/run rate
                or cites the pair) that calls a figure overstated, inflated, misleading or wrong becomes
                that pair's neutral clarification; its citations, all the pair's, are kept
    referent    in a resolved sentence, "the cumulative figure/total/count/..." becomes "the figure stated
                without an explicit interval", unless that pair itself admits a cumulative fact

    label       in a resolved sentence, "contradiction(s)" / "contradictory" becomes "ambiguity" /
                "ambiguous" (memo 99, OF-704: "Measurement-basis contradiction ... [C2, C3]"): two bounded
                figures on different bases are a question to clarify. Kept when negated ("no contradiction"),
                asked, or when Truth Delta found a pair item CONTRADICTED. "Inconsistency" is not changed
    total       in a resolved sentence, the pair's unspecified-interval figure followed by "total" ("500M
                total") becomes "500M with no stated interval" (memo 99, OF-705), unless that pair admits a
                cumulative fact

and, in any sentence, one rule about where a figure is stated (memo 99, OF-705):

    location    "on the same (traction) slide [S2, S3]" or "on a slide headed 'X' [S1, S2, S3]", when the
                citation group mixes pages or contexts and cites a basis pair's member, becomes "on page 10
                (slide headed 'X') [S1, S2] and page 12 [S3]": every ref keeps its own page and context, from
                the admitted items' sources, in citation order. No ref is dropped and nothing is invented; a
                ref without a page leaves the sentence as written

Questions, indefinite conditional scenarios and other metrics are left as written. The word "cumulative"
is never replaced on its own, no citation is moved onto another pair's wording, and nothing here reads
source text: only the notes' refs and the admitted items' statements, statuses, pages and contexts.
"""
import re
from dataclasses import dataclass
from typing import Optional, Tuple

from .claim_context import _REF, _asks, _sentences
from .financial_metrics import CUMULATIVE_BASIS, usage_basis
from .grounded_context import CONTRADICTED

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
# A definite referent an antecedent can supply ("the cumulative figure", "the monthly total", "the figures").
_FIGURE_REFERENT = re.compile(r'\bthe\s+(?:(?:cumulative|monthly|weekly|daily|yearly|annual|headline|larger|smaller|'
                              r'former|latter|first|second|same|other)\s+)?(?:figure|total|count|number|metric|value)s?\b',
                              re.I)
# A bridge continues the discussion it follows. Deliberately an allowlist of whole known basis sentences: any
# other wording (another metric, a citation, a figure, a paraphrase or an added tail) ends the antecedent.
_BRIDGE = re.compile(
    r'\s*(?:these|this|they|both|each|the\s+two)\s+uses?\s+different\s+measurement\s+bases'
    r'(?:\s+and\s+(?:cannot\s+be\s+compared\s+or\s+reconciled\s+without\s+clarification\s+from\s+management|'
    r'need\s+clarification\s+before\s+comparison))?[.!]?\s*', re.I)
_CONTRADICTION = re.compile(r'\b(?:(?P<art>[Aa])\s+)?(?P<word>contradictions?|contradictory)\b', re.I)
_NEGATED = re.compile(r'\b(?:no|not|never|neither|nor|without|rather\s+than|instead\s+of)\b(?:\W+\w+){0,3}?\W+contradict',
                      re.I)
_LABEL = {'contradiction': 'ambiguity', 'contradictions': 'ambiguities', 'contradictory': 'ambiguous'}
_FIGURE = re.compile(r'\d[\d.,]*\s?[KMBkmb]?\b')
# "on the same (traction) slide [refs]" / "on a slide headed 'X' [refs]": one place claimed for a citation group.
_SHARED_PLACE = re.compile(r"\b(?:on|in)\s+(?:a|the)\s+(?:same(?:\s+\w+)?\s+(?:slide|page)|slide\s+headed\s+'(?P<ctx>[^']+)')"
                           r"\s*\[(?P<group>[A-Z]\d+(?:\s*,\s*[A-Z]\d+)*)\]")
_LEAD = re.compile(r'^(?P<lead>\s*(?:[-•*·–]\s*)?)')


@dataclass(frozen=True)
class Pair:
    refs: Tuple[str, ...]              # the note's refs, in the note's order
    members: frozenset                 # those refs plus the statements repeating them
    noun: str                          # the counted noun both sides share ("messages")
    cumulative_admitted: bool          # this pair itself admits a cumulative fact
    clarification: str                 # the neutral sentence, worded from this pair's bases
    contradicted: bool = False         # Truth Delta found a member CONTRADICTED: "contradiction" may be real
    unspecified: Tuple[str, ...] = ()  # the figure on a side with no stated interval ("500M")


@dataclass(frozen=True)
class BasisFacts:
    pairs: Tuple[Pair, ...] = ()      # empty: no note, so no sentence can resolve and nothing changes
    places: Tuple[Tuple[str, int, str], ...] = ()   # (ref, page, source context) for every admitted item with a page


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
        unspecified = []
        for ref, side in zip(refs, sides):
            figure = _FIGURE.search(by_ref[ref].statement) if side[0] == UNSPECIFIED and ref in by_ref else None
            if figure:
                unspecified.append(figure.group(0).strip())
        pairs.append(Pair(refs=tuple(refs), members=frozenset(members), noun=sides[0][2] or sides[1][2],
                          cumulative_admitted=any(side[1] for side in sides),
                          clarification=clarification[0].upper() + clarification[1:],
                          contradicted=any(item.status == CONTRADICTED for item in items if item.ref in members),
                          unspecified=tuple(unspecified)))
    places = tuple((item.ref, _page(item), item.source_context or '') for item in items if _page(item) is not None)
    return BasisFacts(pairs=tuple(pairs), places=places)


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
    if previous is not None and _FIGURE_REFERENT.search(sentence):
        return previous
    return None


def _bridges(sentence):
    """A whole known basis sentence ("These use different measurement bases.") keeps the pair before it."""
    return bool(_BRIDGE.fullmatch(sentence))


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


def _label(sentence, pair, changes):
    """"contradiction" for this pair's two bases: an ambiguity to clarify, unless negated, asked or external."""
    if pair.contradicted or _asks(sentence) or _NEGATED.search(sentence) or not _CONTRADICTION.search(sentence):
        return sentence

    def neutral(match):
        word = _LABEL[match.group('word').lower()]
        word = word[0].upper() + word[1:] if match.group('word')[0].isupper() else word
        art = match.group('art')
        return (art + 'n ' if art else '') + word

    changes.append('basis_contradiction_label')
    return _CONTRADICTION.sub(neutral, sentence)


def _total(sentence, pair, changes):
    """"500M total" for the pair's figure with no stated interval: it has no stated interval."""
    if pair.cumulative_admitted or _asks(sentence):
        return sentence
    for figure in pair.unspecified:
        pattern = re.compile(rf'(?<![\w.$]){re.escape(figure)}\s+total\b')
        if pattern.search(sentence):
            changes.append('basis_unspecified_total')
            sentence = pattern.sub(f'{figure} with no stated interval', sentence)
    return sentence


def _location(sentence, facts, changes):
    """One place claimed for refs from different pages or contexts: each ref under its own page and context."""
    if _asks(sentence):
        return sentence
    places = {ref: (page, context) for ref, page, context in facts.places}
    members = set().union(*(pair.members for pair in facts.pairs)) if facts.pairs else set()

    def place(match):
        cited = [ref.strip() for ref in match.group('group').split(',')]
        if not set(cited) & members or any(ref not in places for ref in cited):
            return match.group(0)
        claimed = match.group('ctx')
        where = {places[ref] for ref in cited}
        if len(where) == 1 and (claimed is None or next(iter(where))[1] == claimed):
            return match.group(0)              # one page and context, and the phrase names it
        groups = {}
        for ref in cited:
            groups.setdefault(places[ref], []).append(ref)
        changes.append('basis_source_location')
        return 'on ' + ' and '.join(
            f"page {page}{f' (slide headed {chr(39)}{context}{chr(39)})' if context else ''} [{', '.join(refs)}]"
            for (page, context), refs in groups.items())

    return _SHARED_PLACE.sub(place, sentence)


def guard_basis_wording(text, facts):
    """Apply the rules to one memo section. Returns (text, changes). Without a basis note no sentence resolves."""
    if not isinstance(text, str) or not text:
        return text, []
    changes, out = [], []
    previous: Optional[Pair] = None          # the pair this paragraph / list item is still discussing
    for sentence, separator in _sentences(text):
        pair = _resolve(sentence, facts, previous)
        if pair is not None:
            sentence = _judgment(sentence, pair, changes)
            sentence = _referent(sentence, pair, changes)
            sentence = _label(sentence, pair, changes)
            sentence = _total(sentence, pair, changes)
            previous = pair
        elif not _bridges(sentence):
            previous = None                  # another metric, another citation or an unresolved figure
        sentence = _location(sentence, facts, changes)
        out.append(sentence + separator)
        if '\n' in separator:
            previous = None                  # a new paragraph or list item
    return (''.join(out) if changes else text), changes
