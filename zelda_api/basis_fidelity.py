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

    label       in a resolved sentence, an affirmative "contradiction(s)" / "contradictory" becomes
                "ambiguity" / "ambiguous" (memo 99, OF-704: "Measurement-basis contradiction ... [C2, C3]"):
                two bounded figures on different bases are a question to clarify. Kept when the word is denied
                or qualified in the words before it ("no", "cannot establish", "insufficient evidence to
                establish", "unable to show", ...), inside a condition ("If the figures are contradictory, ..."),
                asked, or when Truth Delta found a pair item CONTRADICTED. "Inconsistency" is not changed
    total       in a resolved sentence, the pair's unspecified-interval figure followed by "total" ("500M
                total") becomes "500M with no stated interval" (memo 99, OF-705), unless that pair admits a
                cumulative fact, the sentence asks, or the words sit inside a condition ("If 500M total is ...")

and, first, in any sentence, one rule about where figures are stated (memo 99, OF-705; review of d30a022):

    location    a clause placing a citation group "on the same (traction) slide" or "on a slide headed 'X'",
                when the group mixes pages or contexts and cites a basis pair's member, is restated fact by
                fact from the admitted items: "<subject> states 140 000+ bots [S1] and 500M messages with no
                explicit interval [S2] on page 10, under 'X', and separately 500M messages/month [S3] on page
                12 (how ... needs clarification before either is relied on)". Each fact is its item's own
                statement (a pair's no-interval side says so), under its own page and context; adjacent refs
                on one page share a run, so the citation order is kept; the pair's clarification follows when
                both sides are cited. Only the phrase's own clause is restated: it starts after ";", ":", a
                dash or a clause-linking comma (", while" / ", and" / ", but" / ", whereas"), so an earlier
                clause, its narrator and its citations are kept (review of b54d82b). The clause must be known:
                no other citation in it, no narrated cited figure, a company subject with a reporting verb
                ("the company states" is kept) or no subject with a linking verb ("the figures appear"
                becomes "The deck states"), and no word but the cited figures' own words, their own figures
                and a few placing words, inside parentheses too (an aside such as "revenue is $10M" or
                "unaudited" keeps the sentence; a measurement-basis remark is dropped only when the pair's
                clarification is restated; review of 191e627). A figure the cited statements do not hold
                ("250M messages/month"), or one of theirs with another interval or currency ("500M/day",
                "$500M"), keeps the sentence too, as do a sum, comparison or sign ("500M + 500M", "~500M")
                and a nested or unbalanced parenthesis (reviews of ed29f3b). A figure is matched whole: its
                value, any "+" and any "/interval" must be one form a cited statement states ("500M messages/
                month" states "500M" and "500M/month"), so a qualification or denominator no statement gives
                ("500M+", "500M+/month", "500M/messages") keeps the sentence (review of 2465791). A denial ("does not state", "do not appear", "never"), another fact
                ("revenue"), a narrator's subject or an unknown predicate keeps the sentence as written, as do
                a condition, a question or a ref with no page; nothing is invented and no ref is dropped
    context     a figure citing both sides of one pair before a trailing context aside ("500M messages [S2, S3]
                ... (in a slide context headed 'Traction by Apr-16')", memo 100, OF-805) keeps, before the aside,
                only the refs that context belongs to; the other side's fact follows the aside with its own ref,
                page and context ("..., and separately 500M messages/month [S3] on page 12 (clarification)").
                Only when every ref in the clause is a known place, the moved refs are one side of one pair, not
                narrated, and each shares its citation group with the other side's ref under that context; and
                only the company's own affirmative statement: its subject ("the company", "the deck") right
                before the reporting verb the moved refs follow, and no denial or hedge ("does not state",
                "may", "appears to") in the clause. A narrator's listing, a denial, a hedge, a question and a
                condition keep their citations (review of 1801ec5).
                The same context named outside parentheses ("... [S2, S3]) in a slide context headed 'X'",
                "[S1, S2, S3], ... by the period referenced in the 'X' slide context", memo 101, OF-903/904) is
                treated alike, citations inside an earlier parenthesis included. The other side's fact is placed
                only where the context phrase ends its clause (end of sentence, ";" or a clause-linking comma):
                mid-clause ("... in the 'X' slide context is the headline figure") there is nowhere to put it,
                so the sentence is kept. A reporting verb before the moved refs must have the company as its
                subject ("self-reported" is an adjective, not a verb); a narrator named in the clause keeps it.
                Without a reporting verb the fact is its own clause ("; the deck separately states 500M
                messages/month [S3] on page 12 (clarification)"), and only when the clause names the company's
                own source ("self-reported", "the deck", "the company"); a statement attributed to anyone else
                ("According to an analyst, ...", "per ...", "as reported by ...", "... says") keeps its citations
                (review of 750de3f). A hypothesis inside a condition ("If ... [S3] reflects a monthly run-rate
                as of the 'X' slide context") is kept
    cumulative  "the cumulative and monthly presentations" (memo 101, OF-906) presupposes that one side is
    presupposed cumulative. For the pair its own following citation group belongs to (or else the pair the
                sentence resolved to), when that pair admits no cumulative fact, "cumulative" becomes
                "unspecified-interval", inside a condition too: the phrase presupposes rather than supposes.
                The phrase's own noun must be a figure noun ("presentations", "figures") or the pair's noun,
                never another metric ("the cumulative and monthly revenue"), and a later citation owns it only
                when no clause connector ("while", "but", ...) stands between them (review of 750de3f).
                "If the figure is cumulative", "a cumulative total or a monthly rate", a question, another
                pair's or another metric's figures, and a pair with an admitted cumulative side are kept

and two rules that continue an item's discussion (memo 100):

    referent    "one or both figures", "both figures", "either figure" continues the pair the item's last
    judgment    sentence resolved to, like "the figures" (OF-806), and so does "these figures" (memo 101,
                OF-905). An error judgment in that clause ("one or both figures may misrepresent the scale of
                actual activity"), or in a part of it after a dash that continues "these figures" ("These
                figures ... — raising the possibility of metric inflation"), becomes the pair's clarification;
                the sentence's other parts stay. An independent clause after ";", or a part after a dash that
                has its own subject ("— an analyst is wrong"), needs its own referent; a denial before the
                referent or of an earlier judgment covers the judgments coordinated with it after a dash
                ("Nothing suggests these figures are wrong — or inflated"), and coordinated judgments of the
                same figures become one clarification (review of 750de3f). Not
                when the pair has a CONTRADICTED member, the words are denied, the sentence asks, or it cites
                anything outside the pair. The judgment rule above leaves such a sentence to this one, cited or
                not, so these protections hold (review of 1801ec5); a judgment not governed by such a referent
                is still the judgment rule's
    conditions  "These conditions are stated by the company [refs]" after a sentence setting conditions ("if
                the bots reflect active, paying customers ...", OF-807): the cited statements state the
                figures, not the conditions. The subject becomes "The figures", a "rests on the company's own
                assertions" consequence is dropped, and the conditions the cited statements do not state are
                named as hypotheses that need evidence. Kept when there is no condition before it in the same
                item, no citation to check, or every condition is in the cited statements' own words

A condition covers the words after "if" / "whether" / "unless" / "assuming" in the same sentence, for the
label, total and location rules only; the judgment rule above is unchanged (memo 98's conditional
overstatement is still corrected).

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
# Words in the six before "contradiction" that deny or qualify it: "no contradiction", "cannot establish a
# contradiction", "insufficient evidence to establish a contradiction", "unable to show a contradiction".
_DENIAL = frozenset({'no', 'not', 'never', 'neither', 'nor', 'without', 'cannot', "can't", "couldn't", 'unable',
                     'insufficient', 'inadequate', 'lack', 'lacks', 'lacking', 'rather', 'instead', 'fail', 'fails',
                     'failed', 'nothing', 'none'})
_TO_ESTABLISH = re.compile(r'\bto\s+(?:establish|show|prove|demonstrate|confirm|determine)\b', re.I)
_CONDITION = re.compile(r'\b(?:if|whether|unless|assuming|supposing|suppose)\b', re.I)
_REPORTING = re.compile(r'\b(?:states?|stated|reports?|reported|presents?|presented|lists?|listed|shows?|shown|'
                        r'gives?|cites?)\b', re.I)
_LABEL = {'contradiction': 'ambiguity', 'contradictions': 'ambiguities', 'contradictory': 'ambiguous'}
_FIGURE = re.compile(r'\d[\d.,]*\s?[KMBkmb]?\b')
# "on the same (traction) slide [refs]" / "on a slide headed 'X' [refs]": one place claimed for a citation group.
_SHARED_PLACE = re.compile(r"\b(?:on|in)\s+(?:a|the)\s+(?:same(?:\s+\w+)?\s+(?:slide|page)|slide\s+headed\s+'(?P<ctx>[^']+)')"
                           r"\s*\[(?P<group>[A-Z]\d+(?:\s*,\s*[A-Z]\d+)*)\]")
_LEAD = re.compile(r'^(?P<lead>\s*(?:[-•*·–]\s*)?)')
# The only comma that ends a placing clause: one that links a new clause (", while the figures appear ...").
_CLAUSE_LINK = re.compile(r',\s*(?:while|whereas|and|but)\s+', re.I)
# Subjects that report the company's own figures; any other subject (a narrator, "it") is not borrowed.
_OWN_SUBJECT = re.compile(r'(?:the\s+)?(?:company|deck|pitch\s+deck|presentation|founders?|management)', re.I)
_LINKING = frozenset({'appear', 'appears', 'are', 'is', 'were', 'was', 'sit', 'sits'})
# The words a clause placing the cited figures may use besides their own statements' words and figures:
# anything else ("revenue", "not", "never", "places") is another fact, a denial or an unknown predicate.
_PLACING_WORDS = frozenset({'a', 'an', 'the', 'both', 'these', 'those', 'two', 'all', 'either', 'or', 'and', 'of',
                            'that', 'figure', 'figures', 'metric', 'metrics', 'number', 'numbers', 'count', 'counts',
                            'total', 'totals', 'rate', 'rates', 'usage', 'traction', 'message', 'headline'}) | _LINKING
_TOKEN = re.compile(r"[$\d][\w.,+$/]*|[a-z']+")
# A space grouping a statement's digits ("140 000+"): the memo writes the same figure as "140,000+".
_DIGIT_GROUP = re.compile(r'(?<=\d)[ \u00a0\u202f](?=\d{3}\b)')
# A whole figure token: a value, an optional "+", one "/interval" and closing punctuation ("140,000+", "500m/month,").
# Anything else ("500m+500m", "1.5x", a lone "$") is not classified.
_FIGURE_TOKEN = re.compile(r'\$?\d[\d,]*(?:\.\d+)?[kmb]?\+?(?:/[a-z]+)?[.,]?')
# What may separate the words of a placing clause: no sign or operator ("+", "-", "=", "~", "%").
_PLAIN_GAP = re.compile(r'[\s,.]*')
# A referent for the two figures a basis item is discussing (memo 100, OF-806): "one or both figures"; and the
# plural demonstrative continuing it (memo 101, OF-905): "these figures".
_PAIR_REFERENT = re.compile(r'\b(?:(?:one\s+or\s+both|both|either|neither)\s+(?:of\s+the\s+(?:two\s+)?)?'
                            r'(?:figures?|numbers?|metrics?)|(?:these|those)\s+(?:two\s+)?(?:figures|numbers|metrics))\b',
                            re.I)
# A context aside after a figure's citations (memo 100, OF-805): "(in a slide context headed 'X')",
# "(slide context: 'X')", "(slide headed 'X')".
_CONTEXT_ASIDE = re.compile(r"\(\s*(?:in\s+|on\s+)?(?:an?\s+|the\s+)?(?:slide|page)(?:\s+context)?\s*"
                            r"(?:headed\s+|titled\s+|:\s*)?'(?P<ctx>[^']+)'\s*\)", re.I)
# The same context named outside parentheses (memo 101, OF-903/904): "in a slide context headed 'X'",
# "in the 'X' slide context", "within a 'X' slide heading".
_CONTEXT_PHRASE = re.compile(r"\b(?:in|on|within|under)\s+(?:an?\s+|the\s+)?(?:(?:slide|page)(?:\s+context)?\s*"
                             r"(?:headed|titled|:)\s*'(?P<ctx>[^']+)'|'(?P<ctx2>[^']+)'\s+(?:slide\s+)?(?:context|heading))",
                             re.I)
# Where a context phrase may be followed by a separately placed fact: the end of its clause.
_CLAUSE_END = re.compile(r'\s*(?:[.!]?["”’)]*\s*$|;|,\s*(?:while|whereas|and|but)\s)', re.I)
# The company's own subject ending right before its reporting verb: "the company states", "... only that the deck
# lists". A narrator ("Pitch Deck Hunt lists") or anything between ("the company does not state", "may state")
# does not match (review of 1801ec5).
_OWN_SUBJECT_END = re.compile(r"(?:^\s*(?:[-•*·–]\s*)?|\bthat\s+|\bwhile\s+|\bwhereas\s+|\band\s+|,\s*)(?:the\s+)?(?:company|deck|"
                              r"pitch\s+deck|presentation|founders?|management)\s*$", re.I)
# "the cumulative and monthly presentations" (memo 101, OF-906): a definite description presupposing that one side
# is cumulative. "is cumulative", "a cumulative total or a monthly rate" and questions are hypotheses, not this.
_CUMULATIVE_PAIR = re.compile(r"\b(?:[Tt])he\s+(?:(?P<cum1>cumulative)\s+(?:and|or|vs\.?|versus)\s+"
                              r"(?:monthly|weekly|daily|yearly|annual)|(?:monthly|weekly|daily|yearly|annual)\s+"
                              r"(?:and|or|vs\.?|versus)\s+(?P<cum2>cumulative))\b")
UNSPECIFIED_ADJECTIVE = 'unspecified-interval'
# A fragment continuing the clause before a dash rather than starting one with its own subject: a participle
# ("raising ..."), "or/and/nor" + a predicate ("or inflated"), "possibly ...", "which ..." (review of 750de3f).
_CONTINUATION = re.compile(r"\s*(?:\w+ing\b|(?:or|and|nor)\s+(?!(?:a|an|the|this|that|these|those|it|its|they|their|he|"
                           r"she|we|i|you|management|investors?|analysts?)\b)|possibly\b|potentially\b|perhaps\b|which\b)",
                           re.I)
# Words attributing a statement to someone ("According to an analyst, ...", "per an industry report", "X says ..."):
# not the company's own statement (review of 750de3f).
_ATTRIBUTION = re.compile(r"\b(?:according\s+to|per|as\s+(?:reported|stated|listed|cited|noted|described)\s+by|"
                          r"(?:reported|listed|cited|noted|described|estimated)\s+by|says?|said|claims?|claimed|notes?|"
                          r"noted|writes?|wrote|estimates?|believes?|argues?|argued|told)\b", re.I)
# The company's own source named in a clause with no reporting verb ("the self-reported traction metrics", "the
# deck's figures"): required before such a clause's citations are moved (review of 750de3f).
_OWN_SOURCE = re.compile(r"\bself-reported\b|\b(?:the\s+)?(?:company|deck|pitch\s+deck|presentation|founders?|"
                         r"management)(?:'s)?\b", re.I)
# The noun a "the cumulative and monthly ..." phrase is about must be a figure noun, never another metric
# ("the cumulative and monthly revenue"; review of 750de3f).
_FIGURE_NOUN = re.compile(r"\s+(?:presentations?|figures?|numbers?|counts?|totals?|rates?|bases|basis|readings?|"
                          r"versions?|metrics?|values?|statements?|measures?)\b", re.I)
# A connector starting another clause between a phrase and a later citation ("... differ while the message counts
# ... [C2, C3]"): the citation is that clause's.
_CLAUSE_CONNECTOR = re.compile(r"\b(?:while|whereas|but|although|though|because|since|unless|whereby)\b", re.I)
# Hedged wording: a statement the clause does not make outright.
_UNCERTAIN = re.compile(r"\b(?:may|might|could|possibly|perhaps|probably|likely|apparently|appears?|seems?|reportedly|"
                        r"allegedly|purportedly|unclear|uncertain|unconfirmed|whether|estimated?|approximately|"
                        r"roughly)\b", re.I)
# "These conditions are stated by the company" (memo 100, OF-807); a denial ("are not stated") does not match.
_CONDITION_CLAIM = re.compile(r"^(?P<lead>\s*(?:[-•*·–]\s*)?)(?P<subject>(?:these|those|the|both|all|such)\s+"
                              r"(?:conditions|assumptions|premises))(?=\s+(?:are|were|have\s+been)\s+(?:all\s+)?"
                              r"(?:stated|reported|claimed|asserted|presented|given)\s+by\s+(?:the\s+)?"
                              r"(?:company|deck|management|founders?)\b)", re.I)
# Conditions an analysis places on a usage figure that a deck's figure does not itself state.
_HYPOTHESIS = re.compile(r'\b(?:active|paying\s+customers|paying|paid|recurring\s+revenue|revenue|customers|'
                         r'retention|monetis\w*|monetiz\w*|profitab\w*)\b', re.I)
# "..., so the upside reading rests entirely on the company's own assertions": the conditions are not those.
_OWN_ASSERTIONS = re.compile(r",?\s*so\s+[^;.]*?\brests?\b[^;.]*?\bthe\s+company's\s+own\s+"
                             r"(?:assertions|claims|statements)\b", re.I)
# The model's own remark that the basis is open (memo 99): what the pair's restated clarification says.
_BASIS_ASIDE = re.compile(r'measurement\s+basis\s+(?:unresolved|questioned|unclear|ambiguous)'
                          r'(?:\s*;\s*see\s+open\s+concerns)?', re.I)


@dataclass(frozen=True)
class Pair:
    refs: Tuple[str, ...]              # the note's refs, in the note's order
    members: frozenset                 # those refs plus the statements repeating them
    noun: str                          # the counted noun both sides share ("messages")
    cumulative_admitted: bool          # this pair itself admits a cumulative fact
    clarification: str                 # the neutral sentence, worded from this pair's bases
    contradicted: bool = False         # Truth Delta found a member CONTRADICTED: "contradiction" may be real
    unspecified: Tuple[str, ...] = ()  # the figure on a side with no stated interval ("500M")
    sides: Tuple[frozenset, ...] = ()  # each side's members (its claim and the statements repeating it)
    unspecified_members: frozenset = frozenset()   # members of a side with no stated interval


@dataclass(frozen=True)
class BasisFacts:
    pairs: Tuple[Pair, ...] = ()      # empty: no note, so no sentence can resolve and nothing changes
    places: Tuple[Tuple[str, int, str, str], ...] = ()   # (ref, page, source context, fact) for items with a page
    narrated: frozenset = frozenset()  # refs a narrator (not the company) reports
    narrators: frozenset = frozenset()  # the narrators' names ("Pitch Deck Hunt")


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
        side_members = []
        for ref in refs:
            claim = by_ref.get(ref)
            mine = {ref}
            if claim is not None:
                mine |= {item.ref for item in items if item.kind == 'statement'
                         and ' '.join(item.statement.split()) == ' '.join(claim.statement.split())
                         and _page(item) == _page(claim)}
            side_members.append(frozenset(mine))
            members |= mine
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
                          unspecified=tuple(unspecified), sides=tuple(side_members),
                          unspecified_members=frozenset().union(*(mine for mine, side in zip(side_members, sides)
                                                                  if side[0] == UNSPECIFIED))))
    bare = frozenset().union(*(pair.unspecified_members for pair in pairs))
    places = tuple((item.ref, _page(item), item.source_context or '',
                    item.statement + (' with no explicit interval' if item.ref in bare else ''))
                   for item in items if _page(item) is not None)
    return BasisFacts(pairs=tuple(pairs), places=places,
                      narrated=frozenset(item.ref for item in items if getattr(item, 'narrator', '')),
                      narrators=frozenset(item.narrator for item in items if getattr(item, 'narrator', '')))


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
    if previous is not None and (_FIGURE_REFERENT.search(sentence) or _PAIR_REFERENT.search(sentence)):
        return previous
    return None


def _bridges(sentence):
    """A whole known basis sentence ("These use different measurement bases.") keeps the pair before it."""
    return bool(_BRIDGE.fullmatch(sentence))


def _judged_segments(sentence):
    """The sentence split at ";" and at dashes, and for each segment holding a judgment: whether a pair referent
    governs it, whether it is denied, and its chain. A referent governs its own segment and the continuation
    fragments that follow it after a dash ("These figures ... — raising the possibility of inflation", memo 101,
    OF-905). A ";" clause, or a dash followed by anything but a continuation fragment (a new subject: "— an analyst
    is wrong"), starts a new chain. A denial before the referent, or of an earlier judgment in the chain, covers the
    judgments that continue it ("Nothing suggests these figures are wrong — or inflated"; review of 750de3f)."""
    parts = re.split(r'(;\s*|\s+[—–]\s+)', sentence)
    judged, governed, denied, chain = [], False, False, 0
    for i in range(0, len(parts), 2):
        segment = parts[i]
        if i and (parts[i - 1].strip() == ';' or not _CONTINUATION.match(segment)):
            governed, denied, chain = False, False, chain + 1     # a new clause or a new subject
        referent = _PAIR_REFERENT.search(segment)
        if referent:
            governed = True
            denied = denied or _denied(segment, referent.start())
        judgment = _JUDGMENT.search(segment)
        if judgment:
            denied = denied or _denied(segment, judgment.start())
            judged.append((i, governed, denied, chain))
    return parts, judged


def _referent_judged(sentence):
    """Every segment judging the figures is governed by "one or both figures" / "these figures": _referent_judgment
    decides it, with its protections (a denial, a contradicted pair, the sentence's other clauses; reviews of
    1801ec5 and memo 101)."""
    _, judged = _judged_segments(sentence)
    return bool(judged) and all(governed for _, governed, _, _ in judged)


def _judgment(sentence, pair, changes):
    """An error judgment about the pair's bases becomes its neutral clarification; its citations stay."""
    if _asks(sentence) or not _JUDGMENT.search(sentence) or _referent_judged(sentence):
        return sentence
    if not (_BASIS_WORDS.search(sentence) or _cited(sentence)):
        return sentence
    lead = _LEAD.match(sentence).group('lead')
    groups = ' '.join(f'[{group}]' for group in _REF.findall(sentence))
    changes.append('basis_overstatement')
    return f"{lead}{pair.clarification}{' ' + groups if groups else ''}."


def _referent_judgment(sentence, pair, changes):
    """An error judgment on "one or both figures" of this pair: that clause becomes the pair's clarification; the
    sentence's other clauses stay (OF-806)."""
    if pair.contradicted or _asks(sentence) or not _PAIR_REFERENT.search(sentence):
        return sentence
    parts, judged = _judged_segments(sentence)
    hit, replaced = False, set()
    for i, governed, denied, chain in judged:
        if not governed or denied:
            continue
        clause = parts[i]
        end = re.search(r'[.!]?["”’)]*\s*$', clause).group(0)
        groups = ' '.join(f'[{group}]' for group in _REF.findall(clause))
        if chain in replaced:                # a coordinated judgment of the same figures: one clarification
            parts[i - 1], parts[i] = '', (' ' + groups if groups else '') + end
            continue
        lead = _LEAD.match(clause).group('lead') if i == 0 else clause[:len(clause) - len(clause.lstrip())]
        text = pair.clarification if i == 0 else pair.clarification[0].lower() + pair.clarification[1:]
        parts[i] = f"{lead}{text}{' ' + groups if groups else ''}{end}"
        replaced.add(chain)
        hit = True
    if not hit:
        return sentence
    changes.append('basis_referent_judgment')
    return ''.join(parts)


def _referent(sentence, pair, changes):
    """"the cumulative figure" when this pair admits nothing cumulative: the figure has no stated interval."""
    if pair.cumulative_admitted or not _CUMULATIVE_REFERENT.search(sentence):
        return sentence
    changes.append('basis_cumulative_referent')
    return _CUMULATIVE_REFERENT.sub(lambda m: ('T' if m.group('the') == 'T' else 't') + UNSPECIFIED[1:], sentence)


def _conditional(sentence, position):
    """The words at `position` sit inside a condition ("If the figures are contradictory ...")."""
    return bool(_CONDITION.search(sentence[:position]))


def _denied(sentence, position):
    """The six words before `position` deny or qualify what follows ("cannot establish a ...")."""
    before = sentence[:position]
    words = {w.lower() for w in re.findall(r"[\w']+", before)[-6:]}
    return bool(words & _DENIAL) or bool(_TO_ESTABLISH.search(' '.join(re.findall(r"[\w']+", before)[-6:])))


def _label(sentence, pair, changes):
    """An affirmative "contradiction" for this pair's two bases: an ambiguity to clarify (see the docstring)."""
    if pair.contradicted or _asks(sentence) or not _CONTRADICTION.search(sentence):
        return sentence
    hits = []

    def neutral(match):
        if _denied(sentence, match.start('word')) or _conditional(sentence, match.start()):
            return match.group(0)
        hits.append(match.group('word'))
        word = _LABEL[match.group('word').lower()]
        word = word[0].upper() + word[1:] if match.group('word')[0].isupper() else word
        art = match.group('art')
        return (art + 'n ' if art else '') + word

    out = _CONTRADICTION.sub(neutral, sentence)
    if hits:
        changes.append('basis_contradiction_label')
    return out


def _total(sentence, pair, changes):
    """"500M total" for the pair's figure with no stated interval: it has no stated interval."""
    if pair.cumulative_admitted or _asks(sentence):
        return sentence
    for figure in pair.unspecified:
        pattern = re.compile(rf'(?<![\w.$]){re.escape(figure)}\s+total\b')
        hits = [m for m in pattern.finditer(sentence) if not _conditional(sentence, m.start())]
        if hits:
            changes.append('basis_unspecified_total')
            sentence = pattern.sub(lambda m: m.group(0) if _conditional(sentence, m.start())
                                   else f'{figure} with no stated interval', sentence)
    return sentence


def _place_clause_start(sentence, end):
    """Where the clause holding `end` starts: after the last ";", ":", dash or clause-linking comma (", while")
    outside parentheses. Other commas (numbers, lists) do not end it."""
    depth = 0
    for i in range(end - 1, -1, -1):
        ch = sentence[i]
        if ch == ')':
            depth += 1
        elif ch == '(':
            depth = max(0, depth - 1)
        elif depth == 0 and ch in ';:—':
            return i + 1
        elif depth == 0 and ch == ',' and _CLAUSE_LINK.match(sentence, i):
            return _CLAUSE_LINK.match(sentence, i).end()
    return 0


def _figure_key(token):
    """A whole figure token's complete form: its value, any "+" and any "/interval", grouping commas and closing
    punctuation dropped: "500m+/month," -> "500m+/month"; "$23.1m" keeps its "$"; "140,000+" -> "140000+"."""
    match = re.match(r'(\$?)(\d[\d,]*(?:\.\d+)?)([kmb]?)(\+?)(/[a-z]+)?', token)
    return (match.group(1) + match.group(2).replace(',', '') + match.group(3) + match.group(4)
            + (match.group(5) or ''))


# A statement's figure with the interval it states: on the figure ("500m/month") or on its noun ("500m messages/
# month"). Statements are lowercased and their digit groups joined first.
_STATED_FIGURE = re.compile(r'(?<![\w.$])(\$?\d[\d,]*(?:\.\d+)?[kmb]?)(\+?)(?:/([a-z]+)|\s+[a-z]+/([a-z]+))?')


def _stated_forms(statement):
    """The complete figure forms a cited statement supports: each of its figures with or without the "+" and the
    interval it states, never one it does not ("500m messages/month" -> "500m", "500m/month"; "140000+ bots" ->
    "140000", "140000+"). A placed figure may leave out what its statement says, which the restatement gives back,
    but not add to it."""
    forms = set()
    for match in _STATED_FIGURE.finditer(statement):
        value, interval = match.group(1).replace(',', ''), match.group(3) or match.group(4)
        for qualifier in {'', match.group(2)}:
            forms.add(value + qualifier)
            if interval:
                forms.add(value + qualifier + '/' + interval)
    return forms


def _plain_words(text, vocabulary):
    """Every word of `text` is one of `vocabulary`, and every figure's complete form is one the cited statements
    state (in `vocabulary`): "500M/month", not "250M", "500M/day", "500M+" or "500M/messages".
    Nothing but spaces and commas or full stops may stand between them, so a sum, a comparison or a sign of held
    figures ("500M + 500M", "500M = 500M/month", "~500M") is not placing wording. Citations are not words: the
    citation check in _placing_head judges them."""
    text = _REF.sub(' ', text).lower()
    if not _PLAIN_GAP.fullmatch(_TOKEN.sub(' ', text)):
        return False
    for word in _TOKEN.findall(text):
        if word[0] in '$0123456789':
            if not _FIGURE_TOKEN.fullmatch(word):
                return False
            if _figure_key(word) not in vocabulary:
                return False
        elif word not in vocabulary:
            return False
    return True


def _placing_words(text, vocabulary, clarified):
    """Every word and figure of `text` is one of `vocabulary`'s, inside parentheses too: the restatement discards
    the clause's wording, so an aside holding another fact, figure or qualification ("revenue is $10M",
    "250M messages/month", "unaudited") keeps the sentence, and so does a nested or unbalanced parenthesis, which
    is not classified. The one other aside it may drop is a measurement-basis remark ("measurement basis
    unresolved; see open concerns"), and only when `clarified`: the pair's clarification, restated, says it."""
    asides = re.findall(r'\(([^()]*)\)', text)
    outside = re.sub(r'\([^()]*\)', ' ', text)     # a nested or unclosed aside leaves a parenthesis: not plain
    return _plain_words(outside, vocabulary) and all(
        _plain_words(aside, vocabulary) or (clarified and _BASIS_ASIDE.fullmatch(aside.strip()))
        for aside in asides)


def _placing_head(sentence, start, clause, cited, facts, clarified):
    """The clause's own subject and reporting verb, when the clause is known to place exactly the cited figures:
    no other citation, the company's own figures, a company subject (or none, with a linking verb) and nothing
    but those figures' words, asides included. None when any of that is unknown: the sentence is then kept as
    written."""
    if _REF.search(clause) or set(cited) & facts.narrated:
        return None
    statements = [_DIGIT_GROUP.sub('', fact.lower()) for ref, *_, fact in facts.places if ref in cited]
    vocabulary = (_PLACING_WORDS | {word for fact in statements for word in re.findall(r'[a-z]+', fact)}
                  | {form for fact in statements for form in _stated_forms(fact)})   # no other figure is placed
    lead = _LEAD.match(clause).end()
    verb = _reporting_verb(clause)
    if verb is not None:
        if not _OWN_SUBJECT.fullmatch(clause[lead:verb.start()].strip()):
            return None
        if not _placing_words(clause[verb.end():], vocabulary, clarified):
            return None
        return sentence[:start] + clause[:verb.end()] + ' '
    words = _TOKEN.findall(re.sub(r'\([^()]*\)', ' ', clause).lower())
    if not set(words) & _LINKING or not _placing_words(clause[lead:], vocabulary, clarified):
        return None
    if start == 0:
        return _LEAD.match(sentence).group('lead') + 'The deck states '
    return sentence[:start] + clause[:len(clause) - len(clause.lstrip())] + 'the deck states '


def _reporting_verb(clause):
    """The clause's first reporting verb outside parentheses ("the company states ...")."""
    for match in _REPORTING.finditer(clause):
        if clause[:match.start()].count('(') == clause[:match.start()].count(')'):
            return match
    return None


def _location(sentence, facts, changes):
    """One place claimed for refs from different pages or contexts: restated fact by fact (see the docstring)."""
    if _asks(sentence):
        return sentence
    places = {ref: (page, context, fact) for ref, page, context, fact in facts.places}
    members = set().union(*(pair.members for pair in facts.pairs)) if facts.pairs else set()
    for match in _SHARED_PLACE.finditer(sentence):
        cited = [ref.strip() for ref in match.group('group').split(',')]
        if not set(cited) & members or any(ref not in places for ref in cited) or _conditional(sentence, match.start()):
            continue
        claimed = match.group('ctx')
        where = {places[ref][:2] for ref in cited}
        if len(where) == 1 and (claimed is None or next(iter(where))[1] == claimed):
            continue                           # one page and context, and the phrase names it
        runs = []                              # adjacent refs on one page and context share a run
        for ref in cited:
            if runs and runs[-1][0] == places[ref][:2]:
                runs[-1][1].append(ref)
            else:
                runs.append((places[ref][:2], [ref]))
        body = ', and separately '.join(
            ' and '.join(f'{places[ref][2]} [{ref}]' for ref in refs) + f' on page {page}'
            + (f", under '{context}'" if context else '') for (page, context), refs in runs)
        both = next((pair for pair in facts.pairs if len(pair.sides) == 2
                     and all(set(cited) & side for side in pair.sides)), None)
        if both is not None:
            body += f' ({both.clarification[0].lower()}{both.clarification[1:]})'
        start = _place_clause_start(sentence, match.start())
        head = _placing_head(sentence, start, sentence[start:match.start()], cited, facts, both is not None)
        if head is None:
            continue                           # the clause, its subject or its predicate is not known
        changes.append('basis_source_location')
        return _location(head + body + sentence[match.end():], facts, [])
    return sentence


def _split_refs(group):
    return [ref.strip() for ref in re.split(r'[,;]', group)]


def _context_aside(sentence, facts, changes):
    """Both sides of a pair cited before a context aside that only one side's refs belong to: the other side's
    refs leave that citation group and follow the aside as their own fact (OF-805; see the docstring)."""
    if _asks(sentence) or not facts.pairs:
        return sentence
    places = {ref: (page, context, fact) for ref, page, context, fact in facts.places}
    found = [(m.start(), m.end(), m.group('ctx'), True) for m in _CONTEXT_ASIDE.finditer(sentence)]
    found += [(m.start(), m.end(), m.group('ctx') or m.group('ctx2'), False) for m in _CONTEXT_PHRASE.finditer(sentence)
              if sentence[:m.start()].count('(') == sentence[:m.start()].count(')')]   # an aside's own words: above
    for at, end, claimed, aside in sorted(found):
        if _conditional(sentence, at):
            continue
        if not _CLAUSE_END.match(sentence, end):
            continue                           # mid-clause ("... is the headline figure"): no place for the fact
        start = _place_clause_start(sentence, at)
        groups = list(_REF.finditer(sentence, start, at))
        cited = [ref for group in groups for ref in _split_refs(group.group(1))]
        if not cited or any(ref not in places for ref in cited):
            continue
        outside = [ref for ref in cited if places[ref][1] != claimed]
        inside = [ref for ref in cited if places[ref][1] == claimed]
        if not outside or not inside or set(outside) & facts.narrated:
            continue
        pair = next((p for p in facts.pairs if len(p.sides) == 2 and set(outside) <= p.members), None)
        if pair is None:
            continue
        # Each moved ref shares its citation group with a ref of the same pair under the claimed context: one
        # figure cited for both sides. (A side's refs share one page and context, so that ref is the other side.)
        merged = all(any(ref in inside and ref in pair.members for ref in _split_refs(group.group(1)))
                     for group in groups if set(_split_refs(group.group(1))) & set(outside))
        if not merged:
            continue                           # the page-12 figure is its own mention: not split here
        # Only an affirmative statement of the company's own figures: a reporting verb the moved citations follow
        # must have the company as its subject (review of 1801ec5); no narrator named in the clause, and no denial
        # or hedge in it.
        first = min(group.start() for group in groups if set(_split_refs(group.group(1))) & set(outside))
        head = sentence[start:first]
        verbs = [verb for verb in _REPORTING.finditer(head) if head[:verb.start()].count('(') == head[:verb.start()].count(')')
                 and head[verb.start() - 1:verb.start()] != '-']     # "self-reported" is an adjective, not a verb
        if verbs and not _OWN_SUBJECT_END.search(head[:verbs[-1].start()]):
            continue
        clause = sentence[start:at]
        if any(name.lower() in clause.lower() for name in facts.narrators):
            continue
        if _ATTRIBUTION.search(sentence[:at]):
            continue                           # attributed to someone else (review of 750de3f)
        if not verbs and not _OWN_SOURCE.search(clause):
            continue                           # no reporting verb and no own source named: whose statement is unknown
        words = re.findall(r"[\w']+", _REF.sub(' ', clause).lower())
        if set(words) & _DENIAL or _UNCERTAIN.search(' '.join(words)):
            continue
        out, pos = sentence[:start], start
        for group in groups:
            keep = [ref for ref in _split_refs(group.group(1)) if ref not in outside]
            out += sentence[pos:group.start()] + '[' + ', '.join(keep) + ']'
            pos = group.end()
        out += sentence[pos:end]
        runs = []                              # adjacent refs on one page and context share a run
        for ref in outside:
            if runs and runs[-1][0] == places[ref][:2]:
                runs[-1][1].append(ref)
            else:
                runs.append((places[ref][:2], [ref]))
        facts_text = [' and '.join(f'{places[ref][2]} [{ref}]' for ref in refs) + f' on page {page}'
                      + (f", under '{context}'" if context else '') for (page, context), refs in runs]
        if aside or verbs:                     # the company's verb carries on: "..., and separately X on page 12"
            body = ''.join(', and separately ' + text for text in facts_text)
        else:                                  # no reporting verb to carry on: a clause of its own
            body = '; the deck separately states ' + ', and separately '.join(facts_text)
        clarification = pair.clarification[0].lower() + pair.clarification[1:]
        if clarification not in sentence:
            body += f' ({clarification})'
        changes.append('basis_source_context')
        return out + body + sentence[end:]
    return sentence


def _cumulative_presupposed(sentence, pair, facts, changes):
    """"the cumulative and monthly ..." for a pair whose side without a stated interval is not admitted cumulative:
    that side's interval is unspecified (memo 101, OF-906). The pair is the one the phrase's own following citation
    group belongs to, or else the one the sentence resolved to; inside a condition too, since the phrase presupposes
    rather than supposes. Questions are kept."""
    if _asks(sentence) or not _CUMULATIVE_PAIR.search(sentence):
        return sentence
    hits = []

    def owner(match):
        group = _REF.search(sentence, match.end())
        if group is None:
            return pair
        between = sentence[match.end():group.start()]
        if re.search(r'[,;]', between) or _CLAUSE_CONNECTOR.search(between):
            return None                      # the later citation is another clause's: ownership unknown
        refs = set(_split_refs(group.group(1)))
        owners = [p for p in facts.pairs if refs <= p.members]
        return owners[0] if len(owners) == 1 else None

    def neutral(match):
        noun = _FIGURE_NOUN.match(sentence, match.end())
        pair_noun = next((p.noun for p in facts.pairs if p.noun), '')
        if noun is None and not (pair_noun and re.match(rf'\s+{re.escape(pair_noun[:-1])}s?\b', sentence[match.end():], re.I)):
            return match.group(0)            # another metric's phrase ("the cumulative and monthly revenue")
        mine = owner(match)
        if mine is None or mine.cumulative_admitted:
            return match.group(0)
        hits.append(match.group(0))
        word = 'cum1' if match.group('cum1') else 'cum2'
        s, e = match.start(word) - match.start(), match.end(word) - match.start()
        return match.group(0)[:s] + UNSPECIFIED_ADJECTIVE + match.group(0)[e:]

    out = _CUMULATIVE_PAIR.sub(neutral, sentence)
    if hits:
        changes.append('basis_cumulative_presupposed')
    return out


def _condition_attribution(sentence, before, facts, changes):
    """"These conditions are stated by the company [refs]" after conditions the cited statements do not state:
    the figures are the company's, the conditions are hypotheses (OF-807; see the docstring)."""
    match = _CONDITION_CLAIM.match(sentence)
    if match is None or not before or _asks(sentence):
        return sentence
    condition = _CONDITION.search(before)
    cited = _cited(sentence)
    places = {ref: fact for ref, _, _, fact in facts.places}
    if condition is None or not cited or any(ref not in places for ref in cited):
        return sentence
    conditions = []
    for hit in _HYPOTHESIS.finditer(before[condition.start():]):
        word = ' '.join(hit.group(0).lower().split())
        if word not in conditions:
            conditions.append(word)
    stated = ' '.join(places[ref].lower() for ref in cited)
    unstated = [word for word in conditions if word not in stated]
    if not unstated:
        return sentence
    subject = 'The figures' if match.group('subject')[0].isupper() else 'the figures'
    rest = _OWN_ASSERTIONS.sub('', sentence[match.end():])
    end = re.search(r'[.!]?["”’)]*\s*$', rest).group(0)
    rest = rest[:len(rest) - len(end)] if end else rest
    changes.append('basis_condition_attribution')
    return (f"{match.group('lead')}{subject}{rest}; the conditions placed on them ({', '.join(unstated)}) are "
            f"hypotheses the evidence does not state, and would need evidence{end or '.'}")


def guard_basis_wording(text, facts):
    """Apply the rules to one memo section. Returns (text, changes). Without a basis note no sentence resolves."""
    if not isinstance(text, str) or not text:
        return text, []
    changes, out = [], []
    previous: Optional[Pair] = None          # the pair this paragraph / list item is still discussing
    before = None                            # the sentence before, in the same paragraph / list item
    for sentence, separator in _sentences(text):
        sentence = _location(sentence, facts, changes)
        sentence = _context_aside(sentence, facts, changes)
        sentence = _condition_attribution(sentence, before, facts, changes)
        pair = _resolve(sentence, facts, previous)
        if pair is not None:
            sentence = _judgment(sentence, pair, changes)
            sentence = _referent(sentence, pair, changes)
            sentence = _label(sentence, pair, changes)
            sentence = _total(sentence, pair, changes)
            sentence = _referent_judgment(sentence, pair, changes)
            previous = pair
        elif not _bridges(sentence):
            previous = None                  # another metric, another citation or an unresolved figure
        sentence = _cumulative_presupposed(sentence, pair, facts, changes)
        out.append(sentence + separator)
        before = sentence
        if '\n' in separator:
            previous = None                  # a new paragraph or list item
            before = None
    return (''.join(out) if changes else text), changes
