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
                  needed
    not cash      (memo 95) reported funding "against remaining runway": runway
                  needs the company's own affirmative cash balance and burn rate,
                  both with a structured as-of date and within six months of each
                  other, so otherwise the premise is qualified, worded from what
                  the evidence does hold; questions and "if" scenarios are kept
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
_CASH_PREMISE = re.compile(r'\b(?:remaining|existing|available)\s+(?P<a>runway|cash)\b|'
                           r'\b(?P<b>runway|cash)\s+(?:remaining|left)\b', re.I)
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
    # DATED. Runway is supported only by a DATED balance and a DATED burn rate near it.
    cash: str = NONE
    burn: str = NONE
    runway_supported: bool = False


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


def _month(as_of):
    match = _AS_OF.match(as_of or '')
    if not match:
        return None                                   # 'not stated', '' or unparseable: undated
    if match.group('fy'):
        return int(match.group('fy')) * 12 + 12
    return int(match.group('y')) * 12 + int(match.group('m'))


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
    month = _month(getattr(item, 'as_of', ''))
    qualified = (month is not None and not _HISTORICAL.search(text) and not _TENTATIVE.search(text)
                 and not _CONDITIONAL.search(text) and (kind == 'cash' or _RATE.search(text)))
    return kind, (DATED if qualified else PRESENT), (month if qualified else None)


def funding_facts(items, company=''):
    """What the guard needs from GroundedContext items: narrators, funding figures, profile refs, a live raise."""
    groups, funding, profile, supported, funding_items = {}, [], set(), False, set()
    funding_refs, states, months = set(), {'cash': NONE, 'burn': NONE}, {'cash': [], 'burn': []}
    for item in items:
        kind, state, month = cash_basis(item)
        if kind and state:
            states[kind] = max(states[kind], state, key=(NONE, PRESENT, DATED).index)
            if month is not None:
                months[kind].append(month)
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
    runway = any(abs(c - b) <= COMPATIBLE_MONTHS for c in months['cash'] for b in months['burn'])
    return FundingFacts(narrated, tuple(unique.values()), frozenset(profile), supported, company,
                        frozenset(funding_items), frozenset(funding_refs), states['cash'], states['burn'], runway)


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
    for span in _SELF_REPORTED.finditer(sentence):
        start, stop = _clause_start(sentence, span.start()), _clause_end(sentence, span.end())
        clause = sentence[start:stop].lower()
        # Left alone: a narrated amount stated in this clause (_attribute's), or a narrator already named here.
        stated = {r for entry in facts.narrated
                  if (entry.figure and entry.figure.search(sentence, start, stop)) or entry.narrator.lower() in clause
                  for r in entry.refs}
        for group in _REF.finditer(sentence, start, stop):
            refs = [r.strip() for r in re.split(r'[,;]', group.group(1))]
            moved = [r for r in refs if r in by_ref and r not in stated]
            if moved:
                break
        else:
            continue
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
    return sentence


def _attach_to_funding_clause(sentence, after, note, fallback, fallback_at):
    """
    Put the narrated note at the end of the first stretch about funding after the citation
    -- the rest of its own clause, then each later clause -- else beside the citation.
    """
    starts = [after] + [e for _, e in _boundaries(sentence) if e > after]
    for begin in starts:
        stop = _clause_end(sentence, begin)
        clause = sentence[begin:stop]
        if _FUNDING_WORDS.search(clause):
            at = begin + len(clause.rstrip(' .!?;:,"\''))
            return f'{sentence[:at]} {note}{sentence[at:]}'
    return f'{sentence[:fallback_at]} {fallback}{sentence[fallback_at:]}'


_MISSING = {
    'cash': {NONE: 'no cash balance is in the evidence', PRESENT: "the evidence's cash figure is not a dated balance"},
    'burn': {NONE: 'no burn rate is in the evidence', PRESENT: "the evidence's burn figure is not a dated rate"},
}


def cash_basis_note(word, facts):
    """
    The missing basis, worded from what the evidence actually holds, or None when the premise
    is supported: runway by a DATED cash balance with a DATED burn rate within
    COMPATIBLE_MONTHS of it; cash by a DATED balance.
    """
    if word == 'cash':
        if facts.cash == DATED:
            return None
        why = 'none is in the evidence' if facts.cash == NONE else _MISSING['cash'][PRESENT]
        return f'cash on hand (which needs a dated cash balance; {why})'
    if facts.runway_supported:
        return None
    if facts.cash == NONE and facts.burn == NONE:
        why = 'neither is in the evidence'
    elif facts.cash == DATED and facts.burn == DATED:
        why = "the evidence's cash balance and burn rate are not from the same period"
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

    def basis(match):
        note = cash_basis_note((match.group('a') or match.group('b')).lower(), facts)
        return match.group(0) if note is None else note

    rewritten = _CASH_PREMISE.sub(basis, sentence)
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


def guard_funding_fidelity(text, facts):
    """Apply the four rules to one memo section. Returns (text, changes)."""
    if not isinstance(text, str) or not text:
        return text, []
    changes, out = [], []
    for sentence, separator in _sentences(text):
        for rule in (_no_event, _no_premise, _cited_self_reported, _attribute, _no_cash_premise, _profile_undated):
            sentence = rule(sentence, facts, changes)
        out.append(sentence + separator)
    return (''.join(out) if changes else text), changes
