"""
Measurement-basis fidelity in a generated memo (RA-109; memo 98, graded partial pass, UB-604).

The grounded context carries a neutral note when two admitted usage claims count the same noun with the
same number on different bases ("500M messages" with no stated interval; "500M messages/month"). Memo 98
detected the question itself, then wrote in its risk section:

    "If the cumulative figure is being presented as a monthly figure, the key traction claim is
     materially overstated."

Nothing admitted makes the page-10 figure cumulative, and two bounded facts cannot show an overstatement:
they may measure different windows or definitions. After generation, sentence by sentence, and only when
the context carries a measurement-basis note:

    referent     "the cumulative figure/total/count/..." -> "the figure stated without an explicit
                 interval", unless an admitted fact of the noted pair is itself cumulative
    judgment     a statement about the pair's bases (it names cumulative/monthly/interval/run rate or
                 cites a noted ref) that calls a figure overstated, inflated, misleading or wrong is
                 replaced by the neutral clarification, worded from the pair's admitted bases; its
                 citations are kept

Questions ("Is the 500M messages figure a cumulative total or a monthly run rate?"), qualified scenarios
with an indefinite basis ("If ... is a cumulative total rather than monthly, ...") and sentences about
other metrics are left as written. The word "cumulative" is never replaced on its own, no citation is
dropped, and nothing here reads source text: only the note's refs and the admitted items' statements.
"""
import re
from dataclasses import dataclass
from typing import FrozenSet, Tuple

from .claim_context import _REF, _asks, _sentences
from .financial_metrics import CUMULATIVE_BASIS, usage_basis

MEASUREMENT_BASIS = 'measurement_basis'
UNSPECIFIED = 'the figure stated without an explicit interval'
_RATE_ADJECTIVE = {'month': 'monthly', 'week': 'weekly', 'day': 'daily', 'year': 'yearly'}

_CUMULATIVE_REFERENT = re.compile(
    r'\b(?P<the>[Tt])he\s+cumulative\s+(?:(?:messages?|bots?|usage)\s+)?(?:figure|total|count|number|metric|value)\b')
_BASIS_WORDS = re.compile(r'\b(?:cumulative(?:ly)?|monthly|per\s+month|interval|run[- ]rate|measurement\s+bas[ie]s)\b'
                          r'|/\s?month\b', re.I)
_JUDGMENT = re.compile(r'\b(?:overstat\w*|inflat\w*|exaggerat\w*|mislead\w*|misrepresent\w*|incorrect\w*|'
                       r'erroneous\w*|wrong)\b', re.I)
_LEAD = re.compile(r'^(?P<lead>\s*(?:[-•*·–]\s*)?)')


@dataclass(frozen=True)
class BasisFacts:
    pairs: Tuple[Tuple[str, ...], ...] = ()      # refs of each measurement-basis note, in the note's order
    refs: FrozenSet[str] = frozenset()
    cumulative_admitted: bool = False            # an admitted fact of a noted pair is itself cumulative
    clarification: str = ''                      # the neutral sentence, worded from the first pair's bases

    @property
    def active(self):
        return bool(self.pairs)


def _side(item):
    basis = usage_basis(item.statement) if item is not None else None
    if basis is None or not basis.rate:
        return UNSPECIFIED, False
    if basis.rate == CUMULATIVE_BASIS:
        return 'the cumulative figure', True
    return f'the {_RATE_ADJECTIVE.get(basis.rate, basis.rate)} figure', False


def basis_facts(items, notes):
    """The measurement-basis notes of a context, with what each noted ref's admitted statement says."""
    pairs = tuple(tuple(refs) for kind, refs, _ in (notes or ()) if kind == MEASUREMENT_BASIS and len(refs) == 2)
    if not pairs:
        return BasisFacts()
    by_ref = {item.ref: item for item in items}
    cumulative = False
    for pair in pairs:
        for ref in pair:
            cumulative = _side(by_ref.get(ref))[1] or cumulative
    first, second = (_side(by_ref.get(ref))[0] for ref in pairs[0])
    clarification = f'How {first} relates to {second} needs clarification before either is relied on'
    clarification = clarification[0].upper() + clarification[1:]
    return BasisFacts(pairs=pairs, refs=frozenset(r for pair in pairs for r in pair), cumulative_admitted=cumulative,
                      clarification=clarification)


def _cites_pair(sentence, facts):
    return any(ref.strip() in facts.refs for group in _REF.findall(sentence) for ref in re.split(r'[,;]', group))


def _judgment(sentence, facts, changes):
    """An error judgment about the noted bases becomes the neutral clarification; its citations stay."""
    if _asks(sentence) or not _JUDGMENT.search(sentence):
        return sentence
    if not (_BASIS_WORDS.search(sentence) or _cites_pair(sentence, facts)):
        return sentence
    lead = _LEAD.match(sentence).group('lead')
    groups = ' '.join(f'[{group}]' for group in _REF.findall(sentence))
    changes.append('basis_overstatement')
    return f"{lead}{facts.clarification}{' ' + groups if groups else ''}."


def _referent(sentence, facts, changes):
    """"the cumulative figure" when nothing admitted is cumulative: the figure has no stated interval."""
    if facts.cumulative_admitted or not _CUMULATIVE_REFERENT.search(sentence):
        return sentence
    changes.append('basis_cumulative_referent')
    return _CUMULATIVE_REFERENT.sub(lambda m: ('T' if m.group('the') == 'T' else 't') + UNSPECIFIED[1:], sentence)


def guard_basis_wording(text, facts):
    """Apply the rules to one memo section. Returns (text, changes). Inactive without a basis note."""
    if not isinstance(text, str) or not text or not facts.active:
        return text, []
    changes, out = [], []
    for sentence, separator in _sentences(text):
        sentence = _judgment(sentence, facts, changes)
        sentence = _referent(sentence, facts, changes)
        out.append(sentence + separator)
    return (''.join(out) if changes else text), changes
