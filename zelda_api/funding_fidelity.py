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

    attribution   where a sentence states THIS narrated figure, the clause
                  that states it names the narrator. Identity first: a figure
                  followed by a citation is the cited item's, so "$23.1M
                  revenue [S4]" is never Pitch Deck Hunt's; an uncited figure
                  must read as the same kind of figure ("$23.1M raised") and
                  the sentence may not name another source ("Crunchbase
                  reports"). Then, within that clause only:
                    "The company states it has raised $23.1M [S3] and reports
                     140,000+ bots" -> "Pitch Deck Hunt lists the company as
                     having raised $23.1M [S3] and the company reports 140,000+
                     bots" (the company keeps the money and its own figures);
                    "self-reported" -> "reported by <narrator>" when it sits
                     in the figure's own clause and the narrated figure is the
                     sentence's only figure ("two self-reported usage figures"
                     in another clause stays the company's);
                    else "(per <narrator>)" right after the figure's phrase
    no event      "the $23.1M raise" -> "the reported $23.1M": reported
                  funding is not a raise, a round or cash
    no premise    unless the evidence affirmatively shows THIS company raising
                  now, "this raise" / "the stated raise" / "its current round"
                  -> "any current or planned raise"; the question is kept
    profile date  a sentence that cites a profile item (P...) and also names a
                  date marks the profile value "(current profile, undated)"

Only wording changes. No item, period, score or permission is touched, and
nothing here reads source text.
"""
import re
from dataclasses import dataclass
from typing import FrozenSet, Optional, Tuple

from .claim_context import _ANY_DATE, _REF, _sentences, claim_narrator

# A raise taken as given: "this raise", "the stated raise", "its current round".
_PREMISE = re.compile(
    r'\b(?:this|(?:the|its|their)\s+(?:stated|current|proposed|planned|upcoming|new))\s+'
    r'(?:raise|round|fundraise|financing)\b', re.I)
NO_PREMISE = 'any current or planned raise'
PROFILE_UNDATED = '(current profile, undated)'
# Affirmative current-raise wording, company-specific: a statement that opens with
# "Seeking"/"Raising", or whose subject is "we" / "the company" / the company's name.
_RAISE_VERB = r'(?:raising|seeking)\b[^.;]{0,40}?(?:\$\s?\d|\bseed\b|\bseries\s+[a-e]\b|\bround\b)'
_NEGATED = re.compile(r"\b(?:not|no|never|n't|no\s+longer|without)\b", re.I)
_PAST = re.compile(r'\b(?:was|were|had|previously|formerly|earlier)\b', re.I)
_YEAR = re.compile(r'\b(?:19|20)\d{2}\b|\b[A-Z][a-z]{2}-\d{2}\b')
_MONEY = re.compile(r'\$\s?(\d[\d,]*(?:\.\d+)?)\s?(thousand|million|billion|mn|bn|k|m|b)?\b', re.I)
_UNITS = {'k': r'(?:k|thousand)', 'thousand': r'(?:k|thousand)', 'm': r'(?:m|mn|million)', 'mn': r'(?:m|mn|million)',
          'million': r'(?:m|mn|million)', 'b': r'(?:b|bn|billion)', 'bn': r'(?:b|bn|billion)', 'billion': r'(?:b|bn|billion)'}
# Words that belong to the figure's phrase: "$23.1M raised", "$23.1M funding figure".
_FIGURE_TAIL = re.compile(r'(?:\s+(?:in\s+)?(?:funding|raised|figure|total|listed|reported))*')
# What makes an uncited figure read as funding, near it in the same clause.
_FUNDING_WORDS = re.compile(r'\b(?:rais\w*|fund\w*|investors?|invest\w*|capital|financ\w*|rounds?)\b', re.I)
_OTHER_METRIC = re.compile(r'\s*(?:in\s+)?(?:revenue|arr|mrr|sales|valuation|market|tam|sam|gmv|profit|ebitda|'
                           r'income|loss|burn|bookings)\b', re.I)
_CLAUSE_END = re.compile(r'[;,]|\s+(?:and|but|while|whereas)\s+')
_SELF_REPORTED = re.compile(r'\bself[-\s]reported\b', re.I)
_COORDINATED_VERB = re.compile(r'(\s*,?\s+and\s+)(?=(?:reports|states|says|claims|lists|has|had|is|was|'
                               r'describes|shows|notes|processed|deployed|created|sent|grew|serves)\b)', re.I)


@dataclass(frozen=True)
class Narrated:
    narrator: str
    refs: FrozenSet[str]
    figure: Optional[re.Pattern]
    funding: bool


@dataclass(frozen=True)
class FundingFacts:
    narrated: Tuple[Narrated, ...] = ()
    funding_figures: Tuple[re.Pattern, ...] = ()
    profile_refs: FrozenSet[str] = frozenset()
    raise_supported: bool = False
    company: str = ''


def figure_pattern(statement):
    """A pattern for the statement's money figure in any usual spelling ("$23.1M", "$23.1 million")."""
    match = _MONEY.search(statement or '')
    if not match:
        return None
    unit = _UNITS.get((match.group(2) or '').lower(), '')
    number = re.escape(match.group(1).replace(',', ''))
    return re.compile(r'\$\s?' + number + (r'\s?' + unit if unit else '') + r'(?!\w|\.\d)', re.I)


def current_raise(statement, company=''):
    """
    True only for an affirmative, company-specific, current raise: "Seeking $5M
    seed round", "We are raising a $5M Series A", "ManyChat is raising $5M".
    Never a negation ("is not raising"), a past or dated raise ("In 2015 the
    company was seeking $5M"), another company, or a missing section ("Use of
    proceeds: Not found").
    """
    text = ' '.join((statement or '').split())
    subjects = [r'we', r"we're", r'the\s+company']
    if company:
        subjects.append(re.escape(company))
    pattern = re.compile(rf'^(?:{_RAISE_VERB})|\b(?:{"|".join(subjects)})\b((?:\s+\w+){{0,3}}?)\s+{_RAISE_VERB}', re.I)
    match = pattern.search(text)
    if not match:
        return False
    between = match.group(1) or ''
    if _NEGATED.search(between) or _NEGATED.search(text):
        return False
    if _PAST.search(between) or _YEAR.search(text):
        return False
    return True


def funding_facts(items, company=''):
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
        if not getattr(item, 'narrator', '') and current_raise(item.statement, company):
            supported = True
        pattern = figure_pattern(item.statement)
        is_funding = item.category in ('funding_raised', 'Funding')
        if is_funding and pattern:
            funding.append(pattern)
        if getattr(item, 'narrator', ''):
            key = (item.narrator, pattern.pattern if pattern else item.statement)
            narrator, refs, _, was_funding = groups.get(key, (item.narrator, set(), pattern, False))
            refs.add(item.ref)
            groups[key] = (narrator, refs, pattern, was_funding or is_funding)
    narrated = tuple(Narrated(n, frozenset(r), p, f) for n, r, p, f in groups.values())
    unique = {p.pattern: p for p in funding}
    return FundingFacts(narrated, tuple(unique.values()), frozenset(profile), supported, company)


def _refs_in(group):
    return {r.strip() for r in re.split(r'[,;]', group)}


def _cited(sentence):
    return {r for group in _REF.findall(sentence) for r in _refs_in(group)}


def _boundaries(sentence):
    """Clause separators outside parentheses and citations: "(self-reported, unverified): $23.1M" and
    "[S1, S3]" are not split."""
    depth, spans = 0, []
    for match in re.finditer(r'[()\[\]]|' + _CLAUSE_END.pattern, sentence):
        if match.group(0) in '([':
            depth += 1
        elif match.group(0) in ')]':
            depth = max(0, depth - 1)
        elif depth == 0:
            spans.append((match.start(), match.end()))
    return spans


def _clause_end(sentence, start):
    return next((s for s, _ in _boundaries(sentence) if s >= start), len(sentence))


def _clause_start(sentence, end):
    starts = [e for _, e in _boundaries(sentence) if e <= end]
    return starts[-1] if starts else 0


def _same_figure(sentence, found, end, entry):
    """Is this occurrence of the amount the narrated item, not another item with the same amount?"""
    clause_end = _clause_end(sentence, end)
    cite = _REF.search(sentence, end, clause_end) or next(
        iter(_REF.finditer(sentence, _clause_start(sentence, found.start()), found.start())), None)
    if cite:                                         # cited (after, else before, in its clause): the citation decides
        return bool(_refs_in(cite.group(1)) & entry.refs)
    if _OTHER_METRIC.match(sentence, found.end()):   # "$23.1M revenue"
        return False
    other = claim_narrator(sentence)
    if other and other.lower() != entry.narrator.lower():    # "Crunchbase reports $23.1M raised"
        return False
    if entry.funding:
        clause = sentence[_clause_start(sentence, found.start()):clause_end]
        return bool(_FUNDING_WORDS.search(clause))
    return True


def _attribute(sentence, facts, changes):
    for entry in facts.narrated:
        if not entry.figure or entry.narrator.lower() in sentence.lower():
            continue
        found = entry.figure.search(sentence)
        while found:
            end = _FIGURE_TAIL.match(sentence, found.end()).end()
            if _same_figure(sentence, found, end, entry):
                break
            found = entry.figure.search(sentence, found.end())
        if not found:
            continue
        subject = _states_raised(sentence, found, facts)
        if subject:
            sentence = _reattribute_clause(sentence, subject, entry, facts)
        elif _sole_figure(sentence, found) and _self_reported_in_clause(sentence, found, end, entry, facts):
            span = _self_reported_in_clause(sentence, found, end, entry, facts)
            sentence = f'{sentence[:span.start()]}reported by {entry.narrator}{sentence[span.end():]}'
        else:
            sentence = f'{sentence[:end]} (per {entry.narrator}){sentence[end:]}'
        changes.append(f'attribution:{entry.narrator}')
    return sentence


def _states_raised(sentence, found, facts):
    """The "<the company> states it has raised" lead-in directly governing the figure, if any."""
    names = [r'[Tt]he\s+company'] + ([re.escape(facts.company)] if facts.company else [])
    lead = re.compile(rf'\b(?P<subject>{"|".join(names)})\s+(?:states|reports|says|claims)(?:\s+that)?\s+'
                      rf'(?:it|they)\s+(?:has\s+|have\s+|had\s+)?raised\s+$')
    return lead.search(sentence, 0, found.start())


def _reattribute_clause(sentence, subject, entry, facts):
    """
    "The company states it has raised $23.1M [S3] and reports 140,000+ bots" ->
    "Pitch Deck Hunt lists the company as having raised $23.1M [S3] and the company
    reports 140,000+ bots": the narrator takes only the funding clause; the company
    stays the one that raised it and keeps its own predicate.
    """
    who = subject.group('subject')
    recipient = 'the company' if who.lower().startswith('the') else who
    head = f'{sentence[:subject.start()]}{entry.narrator} lists {recipient} as having raised '
    rest = sentence[subject.end():]
    figure = entry.figure.match(rest)
    tail_end = _FIGURE_TAIL.match(rest, figure.end()).end() if figure else 0
    cite = re.match(r'\s*\[[^\]]+\]', rest[tail_end:])
    cut = tail_end + (cite.end() if cite else 0)
    following = _COORDINATED_VERB.sub(rf'\1{recipient} ', rest[cut:], count=1) \
        if _COORDINATED_VERB.match(rest[cut:]) else rest[cut:]
    return head + rest[:cut] + following


def _self_reported_in_clause(sentence, found, end, entry, facts):
    """
    "self-reported" in the figure's own clause, when every citation in that clause is the
    narrated item's -- never one describing another clause's figures, or covering the
    company's own figures too ("The self-reported figures [S1, S3]").
    """
    start, stop = _clause_start(sentence, found.start()), _clause_end(sentence, end)
    cited = {r for m in _REF.finditer(sentence, start, stop) for r in _refs_in(m.group(1))}
    if cited - entry.refs - facts.profile_refs:
        return None
    return _SELF_REPORTED.search(sentence, start, stop)


def _sole_figure(sentence, found):
    """No other number in the sentence besides this figure and the citations."""
    rest = _REF.sub('', sentence[:found.start()] + sentence[found.end():])
    return not re.search(r'\d', rest)


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
        if _refs_in(match.group(1)) & facts.profile_refs:
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
