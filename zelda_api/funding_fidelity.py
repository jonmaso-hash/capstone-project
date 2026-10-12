"""
Funding-source fidelity in a generated memo (ManyChat live run, memo 94;
owner grade: partial pass).

Memo 94 kept "Pitch Deck Hunt lists $23.1M raised" in its executive summary,
but the same figure lost its narrator, or became a financing event, elsewhere:

    information_readiness  "Funding raised figure (self-reported, unverified): $23.1M [S3]"
    base_scenario          "ManyChat was a Series A software company [P1, P2] with meaningful
                            early platform traction as of April 2016 [S1, S2] and stated
                            funding of $23.1M [S3]."
    downside_scenario      "...the $23.1M raise [S3] cannot be confirmed..."
    questions              "...what runway does the stated raise provide at current burn?"
                           "What is the intended use of proceeds from this raise...?"

Lite views show these sections on their own, so each sentence has to carry
its own attribution. After generation, sentence by sentence:

    attribution   a sentence that states a narrated figure names its narrator:
                  "self-reported" -> "reported by <narrator>", "the company
                  states" -> "<narrator> reports", else "(per <narrator>)"
                  right after the figure
    no event      "the $23.1M raise" -> "the reported $23.1M": reported
                  funding is not a raise, a round or cash
    no premise    with no current raise in the evidence, "this raise" / "the
                  stated raise" / "its current round" -> "any current or
                  planned raise"; the question itself is kept
    profile date  a sentence that cites a profile item (P...) and also names a
                  date marks the profile value "(current profile, undated)"

Only wording changes. No item, period, score or permission is touched, and
nothing here reads source text.
"""
import re
from dataclasses import dataclass
from typing import FrozenSet, Optional, Tuple

from .claim_context import _ANY_DATE, _REF, _sentences

# The evidence shows a raise happening now: a public "Raising (profile)" amount
# above zero, or a statement that the company is seeking or raising money.
_CURRENT_RAISE = re.compile(r'\b(?:seeking|raising|use\s+of\s+(?:proceeds|funds)|(?:the|our)\s+ask)\b', re.I)
# A raise taken as given: "this raise", "the stated raise", "its current round".
_PREMISE = re.compile(
    r'\b(?:this|(?:the|its|their)\s+(?:stated|current|proposed|planned|upcoming|new))\s+'
    r'(?:raise|round|fundraise|financing)\b', re.I)
NO_PREMISE = 'any current or planned raise'
PROFILE_UNDATED = '(current profile, undated)'
_MONEY = re.compile(r'\$\s?(\d[\d,]*(?:\.\d+)?)\s?(thousand|million|billion|mn|bn|k|m|b)?\b', re.I)
_UNITS = {'k': r'(?:k|thousand)', 'thousand': r'(?:k|thousand)', 'm': r'(?:m|mn|million)', 'mn': r'(?:m|mn|million)',
          'million': r'(?:m|mn|million)', 'b': r'(?:b|bn|billion)', 'bn': r'(?:b|bn|billion)', 'billion': r'(?:b|bn|billion)'}
# Words that belong to the figure's phrase: "$23.1M raised", "$23.1M funding figure".
_FIGURE_TAIL = re.compile(r'(?:\s+(?:in\s+)?(?:funding|raised|figure|total|listed|reported))*')
_SELF_REPORTED = re.compile(r'\bself[-\s]reported\b', re.I)
_COMPANY_STATES = re.compile(r'\b[Tt]he company (?:states|reports|says|claims)\b')


@dataclass(frozen=True)
class Narrated:
    narrator: str
    refs: FrozenSet[str]
    figure: Optional[re.Pattern]


@dataclass(frozen=True)
class FundingFacts:
    narrated: Tuple[Narrated, ...] = ()
    funding_figures: Tuple[re.Pattern, ...] = ()
    profile_refs: FrozenSet[str] = frozenset()
    raise_supported: bool = False


def figure_pattern(statement):
    """A pattern for the statement's money figure in any usual spelling ("$23.1M", "$23.1 million")."""
    match = _MONEY.search(statement or '')
    if not match:
        return None
    unit = _UNITS.get((match.group(2) or '').lower(), '')
    number = re.escape(match.group(1).replace(',', ''))
    return re.compile(r'\$\s?' + number + (r'\s?' + unit if unit else '') + r'(?!\w|\.\d)', re.I)


def funding_facts(items):
    """What the guard needs from GroundedContext items: narrators, funding figures, profile refs, a live raise."""
    groups, funding, profile, supported = {}, [], set(), False
    for item in items:
        if item.kind == 'profile':
            profile.add(item.ref)
            fields = {s.profile_field for s in item.sources}
            if 'raising_amount' in fields:
                amount = re.search(r':\s*([\d,]*\.?\d+)', item.statement or '')
                supported = supported or bool(amount and float(amount.group(1).replace(',', '') or 0) > 0)
            continue
        if _CURRENT_RAISE.search(item.statement or ''):
            supported = True
        pattern = figure_pattern(item.statement)
        if item.category in ('funding_raised', 'Funding') and pattern:
            funding.append(pattern)
        if getattr(item, 'narrator', ''):
            key = (item.narrator, pattern.pattern if pattern else item.statement)
            narrator, refs, _ = groups.get(key, (item.narrator, set(), pattern))
            refs.add(item.ref)
            groups[key] = (narrator, refs, pattern)
    narrated = tuple(Narrated(n, frozenset(r), p) for n, r, p in groups.values())
    unique = {p.pattern: p for p in funding}
    return FundingFacts(narrated, tuple(unique.values()), frozenset(profile), supported)


def _cited(sentence):
    return {r.strip() for group in _REF.findall(sentence) for r in re.split(r'[,;]', group)}


def _attribute(sentence, facts, changes):
    refs = _cited(sentence)
    for entry in facts.narrated:
        found = entry.figure.search(sentence) if entry.figure else None
        if not found or entry.narrator.lower() in sentence.lower():
            continue
        others = refs - entry.refs - facts.profile_refs
        if not others and _SELF_REPORTED.search(sentence):
            sentence = _SELF_REPORTED.sub(f'reported by {entry.narrator}', sentence, count=1)
        elif not others and _COMPANY_STATES.search(sentence) and not sentence.rstrip(' .]').endswith('?'):
            sentence = _COMPANY_STATES.sub(f'{entry.narrator} reports', sentence, count=1)
        else:
            # "The company states it has raised $23.1M [S3] and reports 140,000+ bots [S1]":
            # both figures are the deck's but only one is the company's, so the deck is the subject.
            states = _COMPANY_STATES.search(sentence)
            if states and states.start() < found.start():
                sentence = (sentence[:states.start()] + ('The' if states.group(0)[0] == 'T' else 'the')
                            + ' deck states' + sentence[states.end():])
                found = entry.figure.search(sentence)
            end = _FIGURE_TAIL.match(sentence, found.end()).end()
            sentence = f'{sentence[:end]} (per {entry.narrator}){sentence[end:]}'
        changes.append(f'attribution:{entry.narrator}')
    return sentence


def _no_event(sentence, facts, changes):
    for pattern in facts.funding_figures:
        rewritten = re.sub(r'\b(?:the|a|this|its)\s+(' + pattern.pattern + r')\s+raise\b',
                           r'the reported \1', sentence, flags=re.I)
        if rewritten != sentence:
            changes.append('funding_as_event')
            sentence = rewritten
    return sentence


def _no_premise(sentence, facts, changes):
    if facts.raise_supported:
        return sentence
    rewritten = _PREMISE.sub(NO_PREMISE, sentence)
    if rewritten != sentence:
        changes.append('raise_premise')
    return rewritten


def _profile_undated(sentence, facts, changes):
    if PROFILE_UNDATED in sentence or not (_cited(sentence) & facts.profile_refs):
        return sentence
    if not _ANY_DATE.search(_REF.sub('', sentence)):
        return sentence
    for match in _REF.finditer(sentence):
        if {r.strip() for r in re.split(r'[,;]', match.group(1))} & facts.profile_refs:
            changes.append('profile_undated')
            return f'{sentence[:match.end()]} {PROFILE_UNDATED}{sentence[match.end():]}'
    return sentence


def guard_funding_fidelity(text, facts):
    """Apply the four rules to one memo section. Returns (text, changes)."""
    if not isinstance(text, str) or not text:
        return text, []
    changes, out = [], []
    for sentence, separator in _sentences(text):
        for rule in (_no_event, _no_premise, _attribute, _profile_undated):
            sentence = rule(sentence, facts, changes)
        out.append(sentence + separator)
    return (''.join(out) if changes else text), changes
