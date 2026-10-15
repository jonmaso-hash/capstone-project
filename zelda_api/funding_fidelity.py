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
    cited mix     (memo 95) "the self-reported figures [S1, S2, S3]" where S3 is
                  narrated: the company's refs stay self-reported, and every
                  narrated ref moves, in one pass, to the clause about funding,
                  "(per <narrator>, undated) [S3]" -- found by citation, no amount
                  needed; every "self-reported" in the sentence is handled in one
                  call, each note kept out of clauses that cite other sources
    not cash      (memo 95) reported funding "against remaining runway": runway
                  needs the company's own affirmative cash balance and burn rate,
                  both with a structured as-of date and within six months of each
                  other (a bare fiscal year matches only the same fiscal year), so
                  otherwise the premise is qualified, worded from what the evidence
                  does hold; even a supported pair is only as of its date, so
                  "current" wording takes that date; questions and "if" scenarios
                  are kept
    provenance    (memo 96) a narrator is credited only with its own refs, checked
                  against each cited ref's metadata, no amount needed: "as reported
                  by Pitch Deck Hunt [C1, C2, C3]" -> "Pitch Deck Hunt [C1] ([C2, C3]
                  are the company's own traction statements)", and "the narrator of
                  the funding and traction claims" -> "the funding claims"; "[S1, S2]
                  and the same figures as reported by Pitch Deck Hunt [C1]" -> "the
                  funding figure reported by" unless its own refs state those figures;
                  narrators named together are checked against their combined refs;
                  questions are kept
Self-reported labels read naturally: "• Self-reported funding raised: $23.1M"
-> "• Funding raised (reported by Pitch Deck Hunt): $23.1M".

Only wording changes. No item, period, score or permission is touched, and
nothing here reads source text.
"""
import re
from dataclasses import dataclass
from typing import FrozenSet, Optional, Tuple

from .claim_context import _ANY_DATE, _REF, _asks, _sentences, claim_narrator

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
# Not yet a raise: "is considering raising", "may be raising", "plans to".
_TENTATIVE = re.compile(r'\b(?:consider\w*|explor\w*|plan\w*|intend\w*|hop\w*|aim\w*|expect\w*|may|might|could|'
                        r'would|potential\w*|possib\w*|likely|looking\s+to|thinking\s+about|evaluat\w*)\b', re.I)
# Not a statement: "Is the company raising $5M?", "If the company is raising $5M, ...".
_QUESTION_LEAD = re.compile(r'^(?:is|are|was|were|does|do|did|will|would|can|could|has|have|should|how|what|why|when)\b',
                            re.I)
_CONDITIONAL = re.compile(r'\b(?:if|unless|whether|assuming|provided|suppose|supposing|should|in\s+case)\b', re.I)
_YEAR = re.compile(r'\b(?:19|20)\d{2}\b|\b[A-Z][a-z]{2}-\d{2}\b')
_MONEY = re.compile(r'\$\s?(\d[\d,]*(?:\.\d+)?)\s?(thousand|million|billion|mn|bn|k|m|b)?\b', re.I)
_UNITS = {'k': r'(?:k|thousand)', 'thousand': r'(?:k|thousand)', 'm': r'(?:m|mn|million)', 'mn': r'(?:m|mn|million)',
          'million': r'(?:m|mn|million)', 'b': r'(?:b|bn|billion)', 'bn': r'(?:b|bn|billion)', 'billion': r'(?:b|bn|billion)'}
# Words that belong to the figure's phrase: "$23.1M raised", "$23.1M funding figure".
_FIGURE_TAIL = re.compile(r'(?:\s+(?:in\s+)?(?:funding|raised|figure|total|listed|reported))*')
# What makes an uncited figure read as funding, near it in the same clause.
_FUNDING_WORDS = re.compile(r'\b(?:rais\w*|fund\w*|investors?|invest\w*|capital|financ\w*|rounds?)\b', re.I)
_METRICS = r'(?:revenue|revenues|arr|mrr|sales|valuation|market|tam|sam|gmv|profit|ebitda|income|loss|burn|bookings)'
_OTHER_METRIC = re.compile(r'\s*(?:in\s+)?' + _METRICS + r'\b', re.I)       # after: "$23.1M revenue"
_METRIC_WORD = re.compile(r'\b' + _METRICS + r'\b', re.I)                   # before: "annual revenue of $23.1M"
_METRIC_WINDOW = 4                                                           # words before the amount
_CLAUSE_END = re.compile(r'[;,]|\s+(?:and|but|while|whereas)\s+')
_SELF_REPORTED = re.compile(r'\bself[-\s]reported\b', re.I)
# Reported funding treated as money still in hand (memo 95: "...the $23.1M funding figure [S3]
# against remaining runway"). Runway needs a dated cash balance and a burn basis.
_CASH_PREMISE = re.compile(r"\b(?P<now>current|present|today's)\s+(?:(?:remaining|existing|available)\s+)?"
                           r"(?P<c>runway|cash)\b(?!(?:\s+on\s+hand)?\s*\(which\s+needs)|"
                           r'\b(?:remaining|existing|available)\s+(?P<a>runway|cash)\b|'
                           r'\b(?P<b>runway|cash)\s+(?:remaining|left)\b', re.I)
# Current wording elsewhere in the premise's clause: "... against remaining runway today".
_NOW = re.compile(r'\b(?:today|now|currently|presently|at\s+present)\b', re.I)
# An introductory time qualifier governs the whole sentence, across its comma: "Today, the $23.1M ... supports
# remaining runway." ("Now" only with its comma: "Now that ..." is not a time qualifier.)
_LEAD_NOW = re.compile(r"^(?P<lead>\s*(?:[-•*·–]|\d+[.)])?\s*)(?P<now>(?:as\s+of\s+)?(?:today(?:['’]s)?|currently|presently|"
                       r'at\s+present|at\s+this\s+point)\b\s*,?\s*|now\s*,\s*)', re.I)
_SUFFICIENT_ALONE = re.compile(r'\b(\w+)\s+alone\s+(would|will|could|can)\b')
# The company's own cash and burn evidence. A balance is a cash figure that is not a flow or a burn;
# a burn basis is a burn figure with a rate ("$150K per month"). Each is only a basis when it is
# affirmative and has a structured as-of date (GroundedItem.as_of, never a date in its wording).
_CASH_WORD = re.compile(r'\bcash\b(?!\s+(?:flow|burn|outflow))|\bbank\s+balance\b|\bin\s+the\s+bank\b', re.I)
_BURN_WORD = re.compile(r'\bburn(?:s|ing|ed)?\b', re.I)
_RATE = re.compile(r'\b(?:per|a|each|every)\s+(?:month|quarter|year)\b|/\s?(?:mo|month|qtr|quarter|yr|year)\b|'
                   r'\b(?:monthly|quarterly|annual|annually|yearly)\b', re.I)
_UNKNOWN = re.compile(r'\b(?:unknown|undisclosed|not\s+(?:disclosed|stated|provided|available)|n/a)\b', re.I)
_HISTORICAL = re.compile(r'\b(?:previously|formerly|historically|once|used\s+to|in\s+the\s+past|had\s+been|'
                         r'prior\s+to|at\s+(?:its|the|one)\s+(?:peak|time))\b', re.I)
_AS_OF = re.compile(r'^(?:(?P<y>\d{4})-(?P<m>\d{2})-\d{2}|FY(?P<fy>\d{4}))$')
COMPATIBLE_MONTHS = 6          # a burn rate dated within this many months of the cash balance
# A dated pair supports runway AS OF its date, never "current" runway: current wording takes the evidence's date.
NO_CURRENT = 'the evidence gives no current figure'
# Evidence states for a cash balance or a burn basis.
NONE, PRESENT, DATED = '', 'present', 'dated'
# A qualified scenario ("If ... with meaningful runway remaining, then ...") states nothing as fact.
_HYPOTHESIS = re.compile(r'\b(?:if|unless|assuming|suppose|supposing|provided|whether)\b', re.I)
_COORDINATED_VERB = re.compile(r'(\s*,?\s+and\s+)(?=(?:reports|states|says|claims|lists|has|had|is|was|'
                               r'describes|shows|notes|processed|deployed|created|sent|grew|serves)\b)', re.I)


@dataclass(frozen=True)
class Narrated:
    narrator: str
    refs: FrozenSet[str]
    figure: Optional[re.Pattern]
    funding: bool
    undated: bool = True           # its as_of is "not stated": attribution says "undated"


@dataclass(frozen=True)
class FundingFacts:
    narrated: Tuple[Narrated, ...] = ()
    funding_figures: Tuple[re.Pattern, ...] = ()
    profile_refs: FrozenSet[str] = frozenset()
    raise_supported: bool = False
    company: str = ''
    # Every funding item's amount with its narrator ('' when the company's own), in no
    # particular order: an uncited amount two of them could be is attributed to neither.
    funding_items: FrozenSet[Tuple[str, str]] = frozenset()
    # Refs of every funding item (a citation alone can name the funding figure).
    funding_refs: FrozenSet[str] = frozenset()
    # The company's own cash balance and burn basis: NONE, PRESENT (a figure that is not a
    # dated, affirmative basis: undated, historical, tentative, or a burn without a rate) or
    # DATED. Runway is supported only by a DATED balance and a DATED burn rate of the same
    # period; runway_as_of / cash_as_of hold that evidence's own as-of date ('' when none).
    cash: str = NONE
    burn: str = NONE
    runway_as_of: str = ''
    cash_as_of: str = ''
    # Every item's (ref, narrator, kind of figure): narrator '' for the company's own and
    # the profile's; kind 'funding', 'traction', 'revenue', 'profile' or the category. A
    # citation may be credited to a narrator only for that narrator's own refs (memo 96).
    ref_sources: FrozenSet[Tuple[str, str, str]] = frozenset()
    # Every item's (ref, statement): "the same figures as reported by <narrator>" holds only
    # when the narrator's own refs state the figures it is equated with (memo 96).
    ref_figures: FrozenSet[Tuple[str, str]] = frozenset()

    @property
    def runway_supported(self):
        return bool(self.runway_as_of)


def figure_pattern(statement):
    """A pattern for the statement's money figure in any usual spelling ("$23.1M", "$23.1 million")."""
    match = _MONEY.search(statement or '')
    if not match:
        return None
    unit = _UNITS.get((match.group(2) or '').lower(), '')
    number = re.escape(match.group(1).replace(',', ''))
    return re.compile(r'\$\s?' + number + (r'\s?' + unit if unit else '') + r'(?!\w|\.\d)', re.I)


# The kinds of figure a sentence can name a narrator's claims by ("the funding and traction claims").
_KIND_WORDS = {
    'funding': r'funding|fundraising|capital|raises?|raised|financing|investment',
    'traction': r'traction|usage|bots?|messages?|users?|customers?|engagement|growth|adoption',
    'revenue': r'revenues?|sales|arr|mrr|bookings',
}
_KIND_CATEGORIES = {
    'funding': ('funding_raised', 'funding'),
    'traction': ('usage', 'traction', 'users', 'customers', 'growth', 'engagement'),
    'revenue': ('revenue', 'arr', 'mrr', 'sales'),
}


def figure_kind(category):
    """'funding', 'traction' or 'revenue' for an item's category; else the category itself."""
    category = (category or '').strip().lower()
    return next((kind for kind, names in _KIND_CATEGORIES.items() if category in names), category)


def current_raise(statement, company=''):
    """
    True only for an affirmative, company-specific, current raise: "Seeking $5M
    seed round", "We are raising a $5M Series A", "ManyChat is raising $5M".
    Never a negation ("is not raising"), a past or dated raise ("In 2015 the
    company was seeking $5M"), another company, a missing section ("Use of
    proceeds: Not found"), a tentative one ("is considering raising $5M"), a
    question ("Is the company raising $5M?") or a condition ("If the company is
    raising $5M, ...").
    """
    text = ' '.join((statement or '').split())
    if text.rstrip(' .)"\'').endswith('?') or _QUESTION_LEAD.match(text) or _CONDITIONAL.search(text):
        return False
    if _TENTATIVE.search(text):
        return False
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


def _period(as_of):
    """
    ('month', n) for a period end, ('fy', year) for a bare fiscal year, None when undated. A
    fiscal year without an established period end has no month: FY2026 is not December 2026.
    """
    match = _AS_OF.match(as_of or '')
    if not match:
        return None                                   # 'not stated', '' or unparseable: undated
    if match.group('fy'):
        return ('fy', int(match.group('fy')))
    return ('month', int(match.group('y')) * 12 + int(match.group('m')))


def same_period(cash, burn):
    """Two period ends within COMPATIBLE_MONTHS, or the same fiscal year label; never a month against a bare FY."""
    if cash[0] != burn[0]:
        return False
    return cash[1] == burn[1] if cash[0] == 'fy' else abs(cash[1] - burn[1]) <= COMPATIBLE_MONTHS


def _latest(dated):
    """
    The as-of string of the latest (as_of, period): by year, then the full ISO date (its day too, so
    2016-04-30 beats 2016-04-01 in any item order). A bare fiscal year sorts before its year's
    period ends; that only chooses which date is shown, nothing is inferred.
    """
    def key(entry):
        as_of, (kind, n) = entry
        return ((n - 1) // 12, 1, as_of) if kind == 'month' else (n, 0, as_of)
    return max(dated, key=key)[0]


def cash_basis(item):
    """
    (kind, state, month) for one item as runway evidence: kind 'cash' or 'burn', state NONE /
    PRESENT / DATED. Only the company's own affirmative figure counts at all: a narrator's,
    a profile field, a negation ("no cash in the bank"), an unknown ("Burn rate: not
    disclosed") or a question is NONE. An undated, historical ("previously had $2M in
    cash"), tentative or conditional figure, or a burn without a rate, is PRESENT.
    """
    text = ' '.join((getattr(item, 'statement', '') or '').split())
    burn, cash = bool(_BURN_WORD.search(text)), bool(_CASH_WORD.search(text))
    kind = 'burn' if burn else 'cash' if cash else ''
    if (not kind or getattr(item, 'narrator', '') or item.kind == 'profile' or not _MONEY.search(text)
            or _NEGATED.search(text) or _UNKNOWN.search(text) or _asks(text)):
        return kind, NONE, None
    period = _period(getattr(item, 'as_of', ''))
    qualified = (period is not None and not _HISTORICAL.search(text) and not _TENTATIVE.search(text)
                 and not _CONDITIONAL.search(text) and (kind == 'cash' or _RATE.search(text)))
    return kind, (DATED if qualified else PRESENT), (period if qualified else None)


def funding_facts(items, company=''):
    """What the guard needs from GroundedContext items: narrators, funding figures, profile refs, a live raise."""
    groups, funding, profile, supported, funding_items = {}, [], set(), False, set()
    funding_refs, states, dated = set(), {'cash': NONE, 'burn': NONE}, {'cash': [], 'burn': []}
    sources, figures = set(), set()
    for item in items:
        figures.add((item.ref, ' '.join((item.statement or '').lower().split())))
        sources.add((item.ref, '' if item.kind == 'profile' else (getattr(item, 'narrator', '') or ''),
                     'profile' if item.kind == 'profile' else figure_kind(item.category)))
        kind, state, period = cash_basis(item)
        if kind and state:
            states[kind] = max(states[kind], state, key=(NONE, PRESENT, DATED).index)
            if period is not None:
                dated[kind].append((item.as_of, period))
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
        if is_funding:
            funding_refs.add(item.ref)
        if is_funding and pattern:
            funding.append(pattern)
            funding_items.add((pattern.pattern, (getattr(item, 'narrator', '') or '').lower()))
        if getattr(item, 'narrator', ''):
            key = (item.narrator, pattern.pattern if pattern else item.statement)
            undated = (getattr(item, 'as_of', '') or 'not stated') == 'not stated'
            narrator, refs, _, was_funding, was_undated = groups.get(key, (item.narrator, set(), pattern, False, True))
            refs.add(item.ref)
            groups[key] = (narrator, refs, pattern, was_funding or is_funding, was_undated and undated)
    narrated = tuple(Narrated(n, frozenset(r), p, f, u) for n, r, p, f, u in groups.values())
    unique = {p.pattern: p for p in funding}
    pairs = [c for c in dated['cash'] if any(same_period(c[1], b[1]) for b in dated['burn'])]
    return FundingFacts(narrated, tuple(unique.values()), frozenset(profile), supported, company,
                        frozenset(funding_items), frozenset(funding_refs), states['cash'], states['burn'],
                        _latest(pairs) if pairs else '', _latest(dated['cash']) if dated['cash'] else '',
                        frozenset(sources), frozenset(figures))


def _refs_in(group):
    return {r.strip() for r in re.split(r'[,;]', group)}


def _cited(sentence):
    return {r for group in _REF.findall(sentence) for r in _refs_in(group)}


def _boundaries(sentence, separators=_CLAUSE_END):
    """Clause separators outside parentheses and citations: "(self-reported, unverified): $23.1M" and
    "[S1, S3]" are not split."""
    depth, spans = 0, []
    for match in re.finditer(r'[()\[\]]|' + separators.pattern, sentence):
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


def _same_figure(sentence, found, end, entry, facts):
    """Is this occurrence of the amount the narrated item, not another item with the same amount?"""
    clause_start, clause_end = _clause_start(sentence, found.start()), _clause_end(sentence, end)
    cite = _REF.search(sentence, end, clause_end) or next(
        iter(_REF.finditer(sentence, clause_start, found.start())), None)
    if cite:                                         # cited (after, else before, in its clause): the citation decides
        return bool(_refs_in(cite.group(1)) & entry.refs)
    if _OTHER_METRIC.match(sentence, found.end()):   # "$23.1M revenue"
        return False
    before = ' '.join(sentence[clause_start:found.start()].split()[-_METRIC_WINDOW:])
    if _METRIC_WORD.search(before):                  # "annual revenue of $23.1M"
        return False
    rivals = {narrator for pattern, narrator in facts.funding_items
              if narrator != entry.narrator.lower() and re.compile(pattern, re.I).match(sentence, found.start())}
    if rivals:                                       # uncited and another item's amount too: attribute to none
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
            if _same_figure(sentence, found, end, entry, facts):
                break
            found = entry.figure.search(sentence, found.end())
        if not found:
            continue
        subject = _states_raised(sentence, found, facts)
        if subject:
            sentence = _reattribute_clause(sentence, subject, entry, facts)
        elif _sole_figure(sentence, found) and _self_reported_in_clause(sentence, found, end, entry, facts):
            span = _self_reported_in_clause(sentence, found, end, entry, facts)
            reworded = _reword_self_reported(sentence, span, entry.narrator)
            if reworded is None:             # attributive: "the self-reported $23.1M" -> "the $23.1M (per ...)"
                sentence = _drop_word(sentence, span)
                found = entry.figure.search(sentence)
                end = _FIGURE_TAIL.match(sentence, found.end()).end()
                reworded = f'{sentence[:end]} (per {entry.narrator}){sentence[end:]}'
            sentence = reworded
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


# "• Self-reported funding raised: $23.1M [S3]" -- "self-reported" opening a label.
_LABEL = re.compile(r'(?P<lead>[\s•\-*·–\d.)]*)self[-\s]reported\s+(?P<np>[^:()\[\]]{1,60}?):\s*', re.I)
_PREDICATE = re.compile(r'\b(?:is|are|was|were|be|been|being)\s+$', re.I)


def _reword_self_reported(sentence, span, narrator):
    """
    Natural wording for "self-reported" that describes a narrated figure (FF-302), or None
    when it is an attributive adjective, which the caller drops in favour of "(per ...)":
      label          "• Self-reported funding raised: $23.1M [S3]"
                     -> "• Funding raised (reported by Pitch Deck Hunt): $23.1M [S3]"
      parenthetical  "Funding raised figure (self-reported, unverified): $23.1M"
                     -> "(reported by Pitch Deck Hunt, unverified)"
      predicate      "The $23.1M is self-reported" -> "The $23.1M is reported by Pitch Deck Hunt"
    """
    before, after = sentence[:span.start()], sentence[span.end():]
    if before.count('(') > before.count(')'):
        return f'{before}reported by {narrator}{after}'
    label = _LABEL.match(sentence)
    if label and label.end('lead') == span.start():
        noun = label.group('np')
        return f"{label.group('lead')}{noun[:1].upper()}{noun[1:]} (reported by {narrator}): {sentence[label.end():]}"
    if _PREDICATE.search(before):
        return f'{before}reported by {narrator}{after}'
    return None


def _drop_word(sentence, span):
    """Remove "self-reported " and restore a capital if it opened the sentence or a bullet."""
    before, after = sentence[:span.start()], sentence[span.end():].lstrip()
    if not before.strip(' •-*·–0123456789.)'):
        after = after[:1].upper() + after[1:]
    return before + after


def _cited_self_reported(sentence, facts, changes):
    """
    "self-reported" whose citations include a narrated item, found by citation alone (no
    amount needed). The company's own figures stay self-reported; the narrated figure is
    attributed separately and, when it has no as-of date, marked undated (FF-305):
      mixed  "Taking the self-reported figures at face value [S1, S2, S3], ManyChat had ...
              traction by April 2016 and had raised a material amount of capital."
          -> "Taking the self-reported figures at face value [S1, S2], ManyChat had ...
              traction by April 2016 and had raised a material amount of capital
              (per Pitch Deck Hunt, undated) [S3]."
      sole   "Self-reported funding [S3] remains unverified."
          -> "Funding (per Pitch Deck Hunt) [S3] remains unverified."
    Every narrated ref in the group is handled in one pass, in citation order, so the result
    does not depend on item order: "[S1, S3, S4]" with S3 from Pitch Deck Hunt and S4 from
    Crunchbase keeps "[S1]" and adds "(per Pitch Deck Hunt, undated) [S3] and (per
    Crunchbase, undated) [S4]". A clause that states a narrated amount itself is left to
    _attribute.
    """
    by_ref = {ref: entry for entry in facts.narrated for ref in entry.refs}
    # Every "self-reported" in the sentence, each in its own clause: a handled one is a no-op the
    # next time round, so this ends once nothing changes (bounded by the number of spans).
    for _ in range(len(_SELF_REPORTED.findall(sentence)) + 1):
        for span in _SELF_REPORTED.finditer(sentence):
            rewritten = _one_self_reported(sentence, span, facts, changes, by_ref)
            if rewritten is not None:
                sentence = rewritten
                break
        else:
            break
    return sentence


# What may sit between two citation groups of one run: nothing, "with", "plus", "&", "as well as".
_JOINER = re.compile(r'\s*(?:with|plus|&|as\s+well\s+as)?\s*', re.I)


def _merge_joined_groups(sentence, start, stop, movable):
    """
    The first run of citation groups joined only by _JOINER, within [start, stop), that holds a
    movable ref, merged into one group: (sentence, new stop, run start, characters removed). None
    when there is no such run.
    """
    groups = list(_REF.finditer(sentence, start, stop))
    i = 0
    while i < len(groups):
        j = i
        while j + 1 < len(groups) and _JOINER.fullmatch(sentence, groups[j].end(), groups[j + 1].start()):
            j += 1
        run = groups[i:j + 1]
        refs = [r.strip() for g in run for r in re.split(r'[,;]', g.group(1))]
        if len(run) > 1 and any(movable(r) for r in refs):
            joined = f'[{", ".join(refs)}]'
            new = sentence[:run[0].start()] + joined + sentence[run[-1].end():]
            removed = len(sentence) - len(new)
            return new, stop - removed, run[0].start(), removed
        i = j + 1
    return None


def _one_self_reported(sentence, span, facts, changes, by_ref):
    """One "self-reported" span, handled within its clause; None when it has no narrated ref to move."""
    start, stop = _clause_start(sentence, span.start()), _clause_end(sentence, span.end())
    clause = sentence[start:stop].lower()
    # Left alone: a narrated amount stated in this clause (_attribute's), or a narrator already named here.
    stated = {r for entry in facts.narrated
              if (entry.figure and entry.figure.search(sentence, start, stop)) or entry.narrator.lower() in clause
              for r in entry.refs}
    merged = _merge_joined_groups(sentence, start, stop, lambda r: r in by_ref and r not in stated)
    if merged:
        # "[S1, S3] with [S4] plus [S5]" is one citation run governed by the same "self-reported":
        # it becomes "[S1, S3, S4, S5]" so every narrated ref in it is handled in this one step.
        sentence, stop, run_start, removed = merged
        span = _SELF_REPORTED.match(sentence, span.start() if span.start() < run_start else span.start() - removed)
    for group in _REF.finditer(sentence, start, stop):
        refs = [r.strip() for r in re.split(r'[,;]', group.group(1))]
        moved = [r for r in refs if r in by_ref and r not in stated]
        if moved:
            break
    else:
        return None
    narrators = {}                                   # narrator -> (its refs, all undated), first-cited first
    for ref in moved:
        entry = by_ref[ref]
        own, undated = narrators.get(entry.narrator, ([], True))
        narrators[entry.narrator] = (own + [ref], undated and entry.undated)
    names = ' and '.join(narrators)
    cited = {r for m in _REF.finditer(sentence, start, stop) for r in _refs_in(m.group(1))}
    if not (cited - set(by_ref) - facts.profile_refs):
        # Sole: everything the clause cites is narrated, so "self-reported" is the narrators' word.
        reworded = _reword_self_reported(sentence, span, names)
        if reworded is None:
            shorter = _drop_word(sentence, span)
            cite = _REF.search(shorter, max(0, group.start() - (len(sentence) - len(shorter))))
            reworded = f'{shorter[:cite.start()].rstrip()} (per {names}) {shorter[cite.start():]}'
        changes.extend(f'attribution:{n}' for n in narrators)
        return reworded
    changes.extend(f'mixed_self_reported:{n}' for n in narrators)
    undated = lambda u: ', undated' if u else ''
    note = ' and '.join(f'(per {n}{undated(u)}) [{", ".join(own)}]' for n, (own, u) in narrators.items())
    kept = [r for r in refs if r not in moved]
    if not kept:            # "traction [S1] with funding [S3, S4]": the group was all narrated, the note replaces it
        return f'{sentence[:group.start()].rstrip()} {note}{sentence[group.end():]}'
    replacement = f'[{", ".join(kept)}]'
    sentence = f'{sentence[:group.start()]}{replacement}{sentence[group.end():]}'
    fallback = '(funding: ' + '; '.join(f'per {n}{undated(u)} [{", ".join(own)}]'
                                        for n, (own, u) in narrators.items()) + ')'
    after_group = group.start() + len(replacement)
    return _attach_to_funding_clause(sentence, after_group, note, fallback, after_group)


def _attach_to_funding_clause(sentence, after, note, fallback, fallback_at):
    """
    Put the narrated note at the end of the first stretch about funding after the citation
    -- the rest of its own clause, then each later clause -- else beside the citation. A later
    clause with citations or "self-reported" of its own belongs to other sources: the search
    stops there ("[S1, S3] are noted, and self-reported funding [S4] is unverified" keeps S3's
    note beside its own group, not in S4's clause).
    """
    starts = [after] + [e for _, e in _boundaries(sentence) if e > after]
    for begin in starts:
        stop = _clause_end(sentence, begin)
        clause = sentence[begin:stop]
        if begin != after and (_REF.search(clause) or _SELF_REPORTED.search(clause)):
            break
        if _FUNDING_WORDS.search(clause):
            at = begin + len(clause.rstrip(' .!?;:,"\''))
            return f'{sentence[:at]} {note}{sentence[at:]}'
    return f'{sentence[:fallback_at]} {fallback}{sentence[fallback_at:]}'


_MISSING = {
    'cash': {NONE: 'no cash balance is in the evidence', PRESENT: "the evidence's cash figure is not a dated balance"},
    'burn': {NONE: 'no burn rate is in the evidence', PRESENT: "the evidence's burn figure is not a dated rate"},
}


def cash_basis_note(word, facts, current=False):
    """
    The missing basis, worded from what the evidence actually holds, or None when the premise
    is supported: runway by a DATED cash balance with a DATED burn rate of the same period
    (same_period); cash by a DATED balance. Support is only as of the evidence's date, so a
    premise worded as current keeps that date instead: "runway as of 2016-04-30 (...)".
    """
    if word == 'cash':
        if facts.cash == DATED:
            return f'cash as of {facts.cash_as_of} (the latest dated cash balance; {NO_CURRENT})' if current else None
        why = 'none is in the evidence' if facts.cash == NONE else _MISSING['cash'][PRESENT]
        return f'cash on hand (which needs a dated cash balance; {why})'
    if facts.runway_supported:
        if current:
            return f'runway as of {facts.runway_as_of} (from the dated cash balance and burn rate; {NO_CURRENT})'
        return None
    if facts.cash == NONE and facts.burn == NONE:
        why = 'neither is in the evidence'
    elif facts.cash == DATED and facts.burn == DATED:
        why = "the evidence's cash balance and burn rate are not shown to be from the same period"
    else:
        why = ' and '.join(_MISSING[k][getattr(facts, k)] for k in ('cash', 'burn') if getattr(facts, k) != DATED)
    return f'runway (which needs a dated cash balance and burn rate; {why})'


def _no_cash_premise(sentence, facts, changes):
    """
    Reported funding is not money in hand (FF-303): in a statement about the funding figure,
    "remaining runway" / "available cash" gains its missing basis. Questions and qualified
    scenarios ("if ... with meaningful runway remaining") are left alone, and so is a premise
    the evidence supports (cash_basis_note).
    """
    if _asks(sentence) or _HYPOTHESIS.search(sentence):
        return sentence
    if not (_cited(sentence) & facts.funding_refs or any(p.search(sentence) for p in facts.funding_figures)):
        return sentence

    lead = _LEAD_NOW.match(sentence)

    def basis(match):
        clause = sentence[_clause_start(sentence, match.start()):_clause_end(sentence, match.end())]
        word = (match.group('a') or match.group('b') or match.group('c')).lower()
        note = cash_basis_note(word, facts, current=bool(match.group('now') or _NOW.search(clause) or lead))
        if note is None:
            return match.group(0)
        supported = facts.cash == DATED if word == 'cash' else facts.runway_supported
        if match.group('now') and not supported:          # "current runway (which needs ...)"
            return f"{match.group('now')} {note}"
        return note                                        # supported: the evidence's date replaces "current"

    rewritten = _CASH_PREMISE.sub(basis, sentence)
    # The evidence's date replaces current wording: an introductory "Today, ..." first (the rest is
    # recapitalised), then "today" / "now" in the dated note's own clause.
    if lead and NO_CURRENT in rewritten and NO_CURRENT not in sentence:
        remaining_lead = _LEAD_NOW.match(rewritten)
        prefix = lead.group('lead')
        rest = rewritten[remaining_lead.end():] if remaining_lead else rewritten[len(prefix):]
        rewritten = prefix + rest[:1].upper() + rest[1:]
    for dated in reversed(list(re.finditer(re.escape(f'; {NO_CURRENT})'), rewritten))):
        start, stop = _clause_start(rewritten, dated.start()), _clause_end(rewritten, dated.end())
        for now in reversed(list(_NOW.finditer(rewritten, start, stop))):
            gap = len(rewritten[:now.start()]) - len(rewritten[:now.start()].rstrip())
            rewritten = rewritten[:now.start() - gap] + rewritten[now.end():]
    if rewritten != sentence:
        # "This alone would allow ... against remaining runway": a revenue/cost schedule alone is not enough.
        rewritten = _SUFFICIENT_ALONE.sub(r'\1 \2', rewritten)
        changes.append('cash_premise')
    return rewritten


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


# Between a citation and its narrator: "[C2, C3] reported by Pitch Deck Hunt", "[C2] (per Pitch Deck Hunt".
_CREDITED_BEFORE = r'\s*,?\s*(?:\(\s*)?(?:as\s+)?(?:(?:reported|narrated|listed|cited|stated|published)\s+by|per)\s+' \
                   r'(?:the\s+)?(?:[\w-]+\s+){0,3}?'
# Another subject between a narrator and a citation: the citation is that subject's, not the narrator's.
_OTHER_SUBJECT = r"the\s+company|company's|its\s+own|the\s+deck|the\s+profile|self[-\s]reported"
_CREDIT_GAP = 120                  # characters from a narrator's name to the citation credited to it
_CREDIT_END = re.compile(r'[;,]|\s+(?:but|while|whereas)\s+')


def _owner_of(ref, sources):
    narrator, kind = sources[ref]
    if narrator:
        return f'per {narrator}'
    return 'the profile' if kind == 'profile' else 'the company'


def _provenance_note(wrong, sources, label, keep):
    """
    "[C2, C3] are the company's own traction statements"; "[S4] is per Crunchbase": every
    mis-credited ref, in citation order, under its own source. With nothing left for the
    narrators, the note says so first: "not Pitch Deck Hunt's: ...".
    """
    owners = {}
    for ref in wrong:
        owners.setdefault(_owner_of(ref, sources), []).append(ref)
    parts = []
    for owner, refs in owners.items():
        verb = 'is' if len(refs) == 1 else 'are'
        if owner == 'the company':
            kinds = {sources[r][1] for r in refs}
            kind = f'{kinds.pop()} ' if len(kinds) == 1 and '' not in kinds else ''
            what = f"the company's own {kind}statement{'s' if len(refs) > 1 else ''}"
        else:
            what = owner
        parts.append(f'[{", ".join(refs)}] {verb} {what}')
    return ('' if keep else f'not {label}: ') + '; '.join(parts)


_NAME_JOIN = r'\s*(?:,\s*(?:and\s+)?|and\s+|&\s*|or\s+)'


def _names_pattern(names):
    return '|'.join(re.escape(n) for n in sorted(names, key=lambda n: (-len(n), n)))


def _name_run(sentence, mention, names):
    """
    The narrators named together from `mention` on ("Pitch Deck Hunt and Crunchbase", "A, B and
    C"), in the order named, and where the run ends. A joint credit is checked against their
    combined refs.
    """
    canonical = {n.lower(): n for n in names}
    run, end = [canonical[mention.group(0).lower()]], mention.end()
    following = re.compile(_NAME_JOIN + r'(' + _names_pattern(names) + r')\b', re.I)
    while True:
        more = following.match(sentence, end)
        if not more or canonical[more.group(1).lower()] in run:
            return run, end
        run.append(canonical[more.group(1).lower()])
        end = more.end()


def _joined_before(names, company):
    """Another subject joined just before a name ("Crunchbase and Pitch Deck Hunt", "the company and
    Pitch Deck Hunt"): the credit is shared, and is checked from the first name of the run, or not at all."""
    subjects = [_OTHER_SUBJECT] + ([_names_pattern(names)] if names else []) + ([re.escape(company)] if company else [])
    return re.compile(r'\b(?:' + '|'.join(subjects) + r')\s*(?:,|\band\b|&|\bor\b)\s*$', re.I)


def _credited_group(sentence, start, end, others, joined):
    """
    The citation group the narrators named at sentence[start:end] are credited with, or None: the next
    group in the same clause ("and" joins nouns here: "the bot and message counts [S1, S2]") with no
    other subject in between, or the group just before "reported by <narrator>".
    """
    clause_start = _clause_start(sentence, start)
    if joined.search(sentence, max(0, start - 80), start):
        return None
    ends = [s for s, _ in _boundaries(sentence, _CREDIT_END) if s >= end]
    clause_end = ends[0] if ends else len(sentence)
    after = _REF.search(sentence, end)
    if after and after.start() <= clause_end and after.start() - end <= _CREDIT_GAP:
        if not others.search(sentence, end, after.start()):
            return after
    for before in reversed(list(_REF.finditer(sentence, clause_start, start))):
        if re.fullmatch(_CREDITED_BEFORE, sentence[before.end():start], re.I):
            return before
        break
    return None


def _label(run):
    """ "Pitch Deck Hunt's"; "Pitch Deck Hunt's or Crunchbase's" for names credited together."""
    return ' or '.join(f"{n}'s" for n in run)


def _credit_citations(sentence, name, sources, company, changes):
    """
    Each citation group credited to `name`, alone or named together with other narrators, keeps
    only refs that one of them narrates; the rest are named under their own source.
    """
    narrators = {s[0] for s in sources.values() if s[0]}
    joined = _joined_before(narrators - {name}, company)
    pos = 0
    while True:
        mention = re.compile(re.escape(name), re.I).search(sentence, pos)
        if not mention:
            return sentence
        pos = mention.end()
        if re.match(r"['’]s\b", sentence[mention.end():]) or re.search(r'\b(?:is|are)\s+per\s+$', sentence[:mention.start()]):
            continue                     # "Pitch Deck Hunt's ..." and "[S4] is per Crunchbase": this rule's own notes
        run, run_end = _name_run(sentence, mention, narrators)
        others = re.compile(r'\b(?:' + '|'.join([_OTHER_SUBJECT] + [re.escape(n) for n in sorted(narrators - set(run))] +
                                                ([re.escape(company)] if company else [])) + r')\b', re.I)
        group = _credited_group(sentence, mention.start(), run_end, others, joined)
        if not group:
            continue
        label = _label(run)
        refs = [r for r in re.split(r'\s*[,;]\s*', group.group(1))]
        wrong = [r for r in refs if r in sources and sources[r][0] not in run]
        if not wrong or sentence[group.end():].startswith(f' (not {label}:'):
            continue
        keep = [r for r in refs if r not in wrong]
        note = _provenance_note(wrong, sources, label, keep)
        cited = f'[{", ".join(keep)}]' if keep else group.group(0)
        sentence = f'{sentence[:group.start()]}{cited} ({note}){sentence[group.end():]}'
        pos = group.start() + len(cited) + len(note) + 3
        changes.append(f'provenance:{" and ".join(run)}')


def _role_phrase(names):
    """ "<name> is the narrator of the funding and traction claims" / "<name> and <name> list the funding
    figures"; `who` holds the names."""
    alternatives = _names_pattern(names)
    return re.compile(
        rf'\b(?P<who>(?:{alternatives})(?:{_NAME_JOIN}(?:{alternatives}))*)\s+'
        rf'(?:(?:is|are|was|were|as|acts?\s+as|being)\s+(?:the\s+|a\s+)?(?:narrators?|sources?|reporters?)\s+of|'
        rf'(?:narrates?|narrated|reports?|reported|lists?|listed))\s+(?:the\s+)?'
        rf'(?P<list>[a-z][a-z\s,-]*?)\s+(?P<noun>claims?|figures?|statements?|metrics?|data|numbers)\b', re.I)


def _kind_of(word):
    return next((k for k, p in _KIND_WORDS.items() if re.search(rf'\b(?:{p})\b', word, re.I)), None)


def _credit_kinds(sentence, sources, company, changes):
    """
    The kinds of figure credited to narrators, alone or together, keep only the kinds one of them
    narrates; the company's own are removed.
    """
    narrators = {s[0] for s in sources.values() if s[0]}
    role = _role_phrase(narrators).search(sentence)
    if not role or _joined_before(set(), company).search(sentence, max(0, role.start() - 80), role.start()):
        return sentence
    canonical = {n.lower(): n for n in narrators}
    run = [canonical[m.lower()] for m in re.findall(_names_pattern(narrators), role.group('who'), re.I)]
    label = _label(run)
    narrated = {kind for narrator, kind in sources.values() if narrator in run}
    own = {kind for narrator, kind in sources.values() if not narrator and kind != 'profile'}
    words = [w for w in re.split(r'\s*(?:,\s*(?:and\s+)?|\s+and\s+|\s+or\s+)\s*', role.group('list')) if w]
    wrong = [w for w in words if _kind_of(w) not in narrated and _kind_of(w) in own]
    if not wrong:
        return sentence
    kept = [w for w in words if w not in wrong]
    if kept:
        joined = kept[0] if len(kept) == 1 else ', '.join(kept[:-1]) + ' and ' + kept[-1]
        sentence = sentence[:role.start('list')] + joined + sentence[role.end('list'):]
    elif not sentence[role.end():].startswith(f' (not {label}:'):
        kinds = sorted({_kind_of(w) for w in wrong})
        sentence = (f"{sentence[:role.end()]} (not {label}: the company's own {' and '.join(kinds)} "
                    f"{role.group('noun')}){sentence[role.end():]}")
    else:
        return sentence
    changes.append(f'provenance:{" and ".join(run)}')
    return sentence


def _same_phrase(names):
    """ "the same figures as reported by <name> [refs]", "the same numbers as <name> [refs]"."""
    alternatives = _names_pattern(names)
    return re.compile(
        rf'\b(?:the|those)\s+(?P<same>(?:same|identical)\s+(?P<noun>figures?|numbers?|amounts?|metrics?|claims?|'
        rf'statements?|data)\s+(?P<as>as\s+)?)(?P<verb>(?:(?:reported|narrated|listed|cited|stated|published)\s+by|per)\s+)?'
        rf'(?:the\s+)?(?:[\w-]+\s+){{0,3}}?(?P<who>(?:{alternatives})(?:{_NAME_JOIN}(?:{alternatives}))*)\b', re.I)


def _is_note(sentence, group):
    """A ref group inside a note this guard wrote: "([C2, C3] are the company's ...", "...: [S4] is per Crunchbase"."""
    return (re.search(r'(?:\(|;\s|:\s)$', sentence[:group.start()]) is not None
            and re.match(r'\s+(?:is|are)\b', sentence[group.end():]) is not None)


def _same_figures(sentence, sources, figures, company, changes):
    """
    "[S1, S2] and the same figures as reported by Pitch Deck Hunt [C1]" holds only when the
    narrators' own cited refs state every figure of the group it is equated with. Otherwise
    the equation is dropped and the narrators' figures are named by their kind: "the funding
    figure reported by Pitch Deck Hunt [C1]" (memo 96: the company's traction [S1, S2] is
    not Pitch Deck Hunt's $23.1M raised [C1]). With none of the narrators' own refs cited,
    nothing is the same: "the figures reported by". A ref outside the context is left as is.

    Every equation in the sentence is checked, each against the nearest group cited before
    it and after the previous equation; this guard's own notes are never that group. The
    company named together with the narrators ("reported by the company and Pitch Deck
    Hunt") shares the credit: its own refs count as stated too.
    """
    narrators = {s[0] for s in sources.values() if s[0]}
    phrase = _same_phrase(narrators)
    canonical = {n.lower(): n for n in narrators}
    subject = r'(?:the\s+company|the\s+deck' + (f'|{re.escape(company)}' if company else '') + r')'
    shared_before = re.compile(subject + r'\s*(?:,|\band\b|&|\bor\b)\s*$', re.I)
    shared_after = re.compile(_NAME_JOIN + subject + r'\b', re.I)
    others = re.compile(r'\b(?:' + '|'.join([_OTHER_SUBJECT] + ([re.escape(company)] if company else [])) + r')\b', re.I)
    pos = floor = 0
    while True:
        same = phrase.search(sentence, pos)
        if not same:
            return sentence
        pos = same.end()
        if not same.group('as') and not same.group('verb'):
            continue
        run = [canonical[m.lower()] for m in re.findall(_names_pattern(narrators), same.group('who'), re.I)]
        after = shared_after.match(sentence, same.end())
        shared = bool(after or shared_before.search(sentence, same.end('same'), same.start('who')))
        start = after.end() if after else same.end()
        compared = [g for g in _REF.finditer(sentence, floor, same.start()) if not _is_note(sentence, g)]
        credited = _REF.search(sentence, start)
        if (not credited or credited.start() - start > _CREDIT_GAP
                or others.search(sentence, start, credited.start())):
            continue
        floor = credited.end()
        if not compared:
            continue
        owners = set(run) | ({''} if shared else set())
        cited = re.split(r'\s*[,;]\s*', credited.group(1))
        own = [r for r in cited if r in sources and sources[r][0] in owners]
        equated = {figures[r] for r in re.split(r'\s*[,;]\s*', compared[-1].group(1)) if r in figures}
        stated = {figures[r] for r in own}
        if not equated or any(r not in sources for r in cited) or equated <= stated:
            continue
        kinds = list(dict.fromkeys(sources[r][1] for r in own))
        noun = same.group('noun')
        if noun.lower() != 'data':
            noun = noun.rstrip('sS') + ('' if len(stated) == 1 else 's')
        kind = ' and '.join(kinds) + ' ' if kinds and all(k in _KIND_WORDS for k in kinds) else ''
        words = f'{kind}{noun} {"" if same.group("verb") else "from "}'
        delta = len(words) - (same.end('same') - same.start('same'))
        sentence = f'{sentence[:same.start("same")]}{words}{sentence[same.end("same"):]}'
        pos, floor = pos + delta, floor + delta
        changes.append(f'provenance:{" and ".join(run)}')


def _narrator_provenance(sentence, facts, changes):
    """
    A narrator is credited only with its own refs, kinds and figures (memo 96): "the
    company's own deck statements [S1, S2] and the same figures as reported by Pitch Deck
    Hunt [C1, C2, C3], ... Pitch Deck Hunt is the narrator of the funding and traction
    claims" credits the company's traction [C2, C3] to Pitch Deck Hunt and equates it with
    Pitch Deck Hunt's funding [C1]. Narrators named together are checked against their
    combined refs. Checked against each cited ref's own metadata, so no amount is needed.
    Questions and requests are kept as asked.
    """
    if not facts.ref_sources or _asks(sentence):
        return sentence
    sources = {ref: (narrator, kind) for ref, narrator, kind in facts.ref_sources}
    present = [n for n in sorted({narrator for narrator, _ in sources.values() if narrator})
               if n.lower() in sentence.lower()]
    if not present:
        return sentence
    for name in present:
        sentence = _credit_citations(sentence, name, sources, facts.company, changes)
    sentence = _credit_kinds(sentence, sources, facts.company, changes)
    return _same_figures(sentence, sources, dict(facts.ref_figures), facts.company, changes)


# --- memo 98 (NP-603 / NP-604) ---------------------------------------------------------------------
# A narrated funding fact's narrative belongs to its narrator: "it establishes the fundraising narrative the
# company has put forward [C1]" credits the company with what only Pitch Deck Hunt narrates.
_COMPANY_NARRATES = re.compile(
    r'\b(?P<subject>[Tt]he company)(?=(?:\s+(?:has|had))?\s+(?:put\s+forward|present(?:s|ed)?|state(?:s|d)?|'
    r'report(?:s|ed)?|claim(?:s|ed)?|assert(?:s|ed)?|advance(?:s|d)?|offer(?:s|ed)?)\b)')
_NARRATIVE_WORDS = re.compile(r'\b(?:fundrais\w*|funding|raised|capital|financing)\b', re.I)
_TRACTION_WORDS = re.compile(r'\b(?:bots?|messages?|users?|customers?|traction|usage|engagement)\b', re.I)
# "the total amount raised": an aggregation the admitted funding item does not state.
_TOTAL = re.compile(r'\btotal\s+(?=(?:amount\s+)?(?:raised|funding|capital)\b)', re.I)
_STATED_TOTAL = re.compile(r'\b(?:total|to\s+date|cumulative\w*|in\s+aggregate|so\s+far)\b', re.I)
# Historical funding as the runway / operating-cash denominator, in a statement or a question:
# "how long the company can operate on the capital narrated as raised [S4]",
# "runway against the $23.1M (per Pitch Deck Hunt) narrated as raised [S4]?".
_SPAN = r'(?:[^.;?\[\]]|\.(?=\d))'
_FUNDING_DENOMINATOR = re.compile(
    rf'\b(?P<verb>runway|operate|operating|survive|sustain)\b(?P<mid>{_SPAN}{{0,40}}?)\s+'
    rf'(?P<link>against|on|from|with|out\s+of)\s+(?P<phrase>{_SPAN}+?)(?=\s*\[|\s*[.;?](?!\d)|\s*$)', re.I)
_DENOMINATOR_WORDS = re.compile(r'\b(?:capital|funding|raised|raise|proceeds)\b', re.I)
NOT_CASH = 'is historical funding, not cash on hand'


def _narrated_funding_refs(facts):
    return {ref for ref, narrator, kind in facts.ref_sources if narrator and kind == 'funding'}


def _narrative_owner(sentence, facts, changes):
    """A narrative citing only one narrator's funding refs is that narrator's, not the company's."""
    cited = _cited(sentence)
    if not cited or not _NARRATIVE_WORDS.search(sentence):
        return sentence
    sources = {ref: (narrator, kind) for ref, narrator, kind in facts.ref_sources}
    if not all(sources.get(ref, ('', ''))[0] and sources[ref][1] == 'funding' for ref in cited):
        return sentence
    narrators = {sources[ref][0] for ref in cited}
    if len(narrators) != 1:
        return sentence
    narrator = next(iter(narrators))

    def owner(match):
        # Only in the clause that names the funding narrative: "... and the company reports 140,000+
        # bots" is the company's own statement and stays the company's.
        clause = sentence[_clause_start(sentence, match.start()):_clause_end(sentence, match.end())]
        if not _NARRATIVE_WORDS.search(clause) or _TRACTION_WORDS.search(clause):
            return match.group(0)
        changes.append('narrator_narrative')
        return narrator

    return _COMPANY_NARRATES.sub(owner, sentence)


def _unsupported_total(sentence, facts, changes):
    """ "the total amount raised" for a narrated funding fact whose own statement states no total."""
    narrated = _narrated_funding_refs(facts)
    if _asks(sentence) or not _TOTAL.search(sentence):
        return sentence                   # "What is the total raised beyond the $23.1M ...?" asks; it is kept
    statements = dict(facts.ref_figures)
    if any(_STATED_TOTAL.search(statements.get(ref, '')) for ref in narrated):
        return sentence

    def drop(match):
        # Only where the clause states the narrated figure itself (its amount or its citation).
        start, stop = _clause_start(sentence, match.start()), _clause_end(sentence, match.end())
        clause = sentence[start:stop] + _trailing_refs(sentence, stop)
        if not (_cited(clause) & narrated or any(p.search(clause) for p in facts.funding_figures)):
            return match.group(0)
        changes.append('unsupported_total')
        return ''

    return _TOTAL.sub(drop, sentence)


def _trailing_refs(sentence, stop):
    """Citations straight after a clause belong to it ("... the total amount raised [S4].")."""
    match = re.match(r'\s*(?:\[[^\]]*\]\s*)+', sentence[stop:])
    return match.group(0) if match else ''


def _funding_not_runway(sentence, facts, changes):
    """
    Historical funding is never the cash or runway denominator, also in a question: the denominator
    is kept and named for what it is. Dated cash and burn questions, and questions about whether the
    funding occurred, are untouched: the denominator must itself name funding (its amount, capital,
    funding, raised, proceeds), so "on its $2M cash balance" is never rewritten.
    """
    if NOT_CASH in sentence:
        return sentence
    if not (_cited(sentence) & facts.funding_refs or any(p.search(sentence) for p in facts.funding_figures)):
        return sentence

    def rewrite(match):
        phrase = match.group('phrase').strip()
        if not (any(p.search(phrase) for p in facts.funding_figures) or _DENOMINATOR_WORDS.search(phrase)):
            return match.group(0)
        changes.append('funding_not_runway')
        return (f"{match.group('verb')}{match.group('mid')} — from the dated cash and burn alone, since "
                f"{phrase} {NOT_CASH}")

    return _FUNDING_DENOMINATOR.sub(rewrite, sentence)


def guard_funding_fidelity(text, facts):
    """Apply the rules to one memo section. Returns (text, changes)."""
    if not isinstance(text, str) or not text:
        return text, []
    changes, out = [], []
    for sentence, separator in _sentences(text):
        for rule in (_no_event, _no_premise, _cited_self_reported, _attribute, _narrator_provenance,
                     _no_cash_premise, _profile_undated, _narrative_owner, _unsupported_total, _funding_not_runway):
            sentence = rule(sentence, facts, changes)
        out.append(sentence + separator)
    return (''.join(out) if changes else text), changes
