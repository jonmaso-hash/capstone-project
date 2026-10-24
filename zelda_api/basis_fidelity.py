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

and, first, in any sentence, one rule about which source a figure's citation names (memo 102, OF-1004):

    identity    a citation group written straight after ONE figure of a pair cites that figure's side: "states
                '500M messages/month' [C3, S3]" names page 12's figure, so page 10's claim C3 becomes page 12's
                C2 ("[C2, S3]"). A figure names a side only by its value, "+" and stated interval together (the
                same number alone names none), or, with no interval written, as a quotation of one side's whole
                statement ("'500M messages'"). One operand of "[C3, S2] vs [C3, S3]" whose other operand cites one
                side alone names the other side. The wrong ref becomes the named side's ref of the same kind (its
                claim, or its one repeating statement); with none, it is dropped when the group still cites the
                named side, and otherwise kept and logged as unresolved. Comparisons are kept: a group citing both
                sides' claims ("[C2, C3]") or both sides' statements, a group after a list holding the pair's
                other figure ("page 10 states '500M messages' ... while page 12 states '500M messages/month' [C2,
                C3]"), a group following no figure ("conflicting bases [C3, C2]"), a figure with another interval
                ("500M messages/day"), an unquoted figure with no interval ("500M messages [C2]"), and every ref
                outside the pair

and one rule about where figures are stated (memo 99, OF-705; review of d30a022):

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
                as of the 'X' slide context") is kept.
                A condition that only ACCEPTS the cited figures is not a hypothesis about their context (memo 102,
                OF-1003): "If the traction figures [S1, S2, S3] are taken at face value under the 'X' framing, ...
                at that point in time" carries page 10's heading onto page 12's S3. When the condition ("if",
                "assuming", "supposing") holds nothing but the figures' own subject (placing words, the pair's
                topics, the cited statements' words), their citations, an acceptance frame ("are taken at face
                value", "are accepted as stated") and the context phrase ending the antecedent, the other side's
                refs leave the condition's citations and follow the sentence as the deck's own fact ("...; the deck
                separately states 500M messages/month [S3] on page 12 (clarification)"). Any other predicate
                ("reflects a monthly run-rate", "all fall under"), "whether", a question, a denial, a hedge, a
                narrator, another speaker or another metric keeps the sentence
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
_JUDGMENT_WORD = r'(?:overstat\w*|inflat\w*|exaggerat\w*|mislead\w*|misrepresent\w*|incorrect\w*|erroneous\w*|wrong)\b'
_JUDGMENT = re.compile(r'\b' + _JUDGMENT_WORD, re.I)
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
# "in the 'X' slide context", "within a 'X' slide heading"; and memo 102's "under the 'X' framing" (OF-1003).
_CONTEXT_PHRASE = re.compile(r"\b(?:in|on|within|under)\s+(?:an?\s+|the\s+)?(?:(?:slide|page)(?:\s+context)?\s*"
                             r"(?:headed|titled|:)\s*'(?P<ctx>[^']+)'|'(?P<ctx2>[^']+)'\s+(?:slide\s+)?"
                             r"(?:context|heading|framing))", re.I)
# The same heading named as a time (memo 103, OF-1102/1103): "at the time of the 'X' slide", "as of the 'X' slide
# context", "by the time of the 'X' page".
_TIME_CONTEXT = re.compile(r"\b(?:at\s+the\s+time\s+of|as\s+of|by\s+the\s+time\s+of)\s+(?:the\s+)?'(?P<ctx>[^']+)'\s+"
                           r"(?:slide|page)(?:\s+(?:context|heading))?\b", re.I)
# Where a context phrase may be followed by a separately placed fact: the end of its clause.
_CLAUSE_END = re.compile(r'\s*(?:[.!]?["”’)]*\s*$|;|,\s*(?:while|whereas|and|but)\s)', re.I)
# A closing "with ..." clause after the context phrase (memo 103, OF-1102: ", with Pitch Deck Hunt listing $23.1M in
# prior funding [C1, S4]"): the moved fact follows it, so it keeps its own subject. _trailing_clause decides.
_TRAILING_WITH = re.compile(r',\s+(?:with|alongside)\s+(?P<body>[^;:()—–]*?)(?P<end>[.!]?["”’)]*\s*)$', re.I)
# A qualification of the figures' VERIFICATION, not of their date, place or truth (memo 103, OF-1102): "without
# independent verification", "not independently verified", "unverified". An allowlist: any other "without" or "not"
# still denies, and a hedge before it ("possibly without ...") still hedges.
_VERIFICATION_QUALIFIER = re.compile(
    r"\b(?:without\s+(?:any\s+)?(?:independent|external|third[-\s]party)\s+(?:verification|confirmation|corroboration)"
    r"|not\s+(?:yet\s+)?(?:been\s+)?independently\s+(?:verified|confirmed)|(?:as\s+yet\s+)?unverified)\b", re.I)
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
# A fragment continuing the clause before a dash rather than starting one with its own subject. The WHOLE fragment
# must parse as a continuation of the figures' clause (review of 377a142: a judgment-like first word, "misleading
# advertising is wrong", "inflation is affecting costs", owned the rest of the clause):
#   - a listed participle whose object is a judgment NOUN ("raising the possibility of metric inflation", "suggesting
#     possible inflation"); or
#   - optional "or/and/nor/which" and hedges, then a judgment PREDICATE about the figures ("or possibly inflated",
#     "misleading", "which may be overstated");
#   then only coordinated judgments ("or imprecise reporting"), the fragment's citations and closing punctuation.
# A bare noun ("— inflation."), a noun phrase after a predicate ("— overstated expectations are common"), any other tail
# ("— possibly inflated by bots") or an unlisted start ("— or Bob is wrong") is not classified: a new chain, kept
# (reviews of 750de3f, 7fb484b and 377a142).
_JUDGMENT_PREDICATE = r'(?:overstated|inflated|exaggerated|misleading|misrepresented|misrepresentative|incorrect|erroneous|wrong)\b'
_JUDGMENT_NOUN = r'(?:overstatements?|inflation|exaggerations?|misrepresentations?|errors?|inaccurac(?:y|ies))\b'
_CONTINUATION_MODIFIER = r'(?:possible|potential|metric|usage|imprecise|inaccurate)'
_CONTINUATION = re.compile(
    r"\s*(?:(?:raising|suggesting|indicating|implying)\s+(?:the\s+(?:possibility|prospect|risk)\s+of\s+|"
    r"(?:concerns?|questions?)\s+(?:of|about)\s+)?(?:" + _CONTINUATION_MODIFIER + r"\s+)*" + _JUDGMENT_NOUN + r"|"
    r"(?:(?:or|and|nor|which)\s+)?(?:(?:may|might|could|be|is|are|were|was|possibly|potentially|perhaps|probably|"
    r"likely|even|also)\s+)*" + _JUDGMENT_PREDICATE + r")"
    r"(?:\s+(?:or|and)\s+(?:(?:" + _CONTINUATION_MODIFIER + r"|possibly|potentially)\s+)*(?:" + _JUDGMENT_PREDICATE + r"|"
    + _JUDGMENT_NOUN + r"|reporting|measurement\b))*"
    r"(?:\s*\[[A-Z]\d+(?:\s*[,;]\s*[A-Z]\d+)*\])*[.!]?[\"”’)]*\s*", re.I)
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
    topics: frozenset = frozenset()    # words of its evidence's categories ("usage", "traction")
    figures: frozenset = frozenset()   # the figures its statements state ("500m")
    pages: frozenset = frozenset()     # the pages its members are on (10, 12)
    intervals: frozenset = frozenset()  # its sides' bases ("month"; "cumulative" for a cumulative or unstated side)
    statements: Tuple[str, ...] = ()   # each side's claim statement, in refs order ("500M messages", "500M messages/month")


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


def _interval(item):
    """A side's basis as _pair_basis reads it: its rate's interval ("month"), or "cumulative" for a cumulative side
    and for a side with no stated interval: "the cumulative figure" is the name the memos give the unstated figure,
    which _referent rewrites (memo 98, UB-604)."""
    basis = usage_basis(item.statement) if item is not None else None
    if basis is None or not basis.rate or basis.rate == CUMULATIVE_BASIS:
        return 'cumulative'
    return basis.rate


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
                                                                  if side[0] == UNSPECIFIED)),
                          topics=frozenset(word for item in items if item.ref in members
                                           for word in re.findall(r'[a-z]{3,}', (item.category or '').lower())),
                          figures=frozenset(hit.group(0).strip().lower() for item in items if item.ref in members
                                            for hit in _FIGURE.finditer(item.statement)),
                          pages=frozenset(_page(item) for item in items
                                          if item.ref in members and _page(item) is not None),
                          intervals=frozenset(_interval(by_ref.get(ref)) for ref in refs),
                          statements=tuple(by_ref[ref].statement if ref in by_ref else '' for ref in refs)))
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


# Where one clause ends and the next begins: ";", a spaced dash, or a comma before a clause-linking conjunction
# ("…, but management has not clarified …"; review of 8d7f8dc). A coordinated judgment after the comma ("…, and
# possibly inflated") is a continuation fragment and stays in its clause's chain.
_CLAUSE_SPLIT = re.compile(r'(;\s*|\s+[—–]\s+|,\s+(?:and|but|while|whereas|yet|although|though|so|because|which)\s+)',
                           re.I)
# A verb in a list item: "The cumulative, monthly, and daily figures" is a list, not two clauses.
_ITEM_VERB = re.compile(r"\b(?:is|are|was|were|be|been|has|have|had|do|does|did|can|could|may|might|must|should|will|"
                        r"would|not|\w+ed)\b|" + _JUDGMENT_WORD, re.I)
# The judged subject (review of 8d7f8dc): the noun phrase before the judgment's verb group. Its head must be a figure
# or claim noun, one of the pair's own topics (the categories of its evidence: "traction", "usage"), or the pair's
# counted noun with one of the pair's figures ("the 500M messages"). Every other word in it must place or qualify the
# pair's figure: a basis word, the pair's noun, topic or figure, a page or slide, an own source, or a placing word.
# Any other word ("monthly costs", "misleading messages", "the hiring claim") makes the subject someone else's.
_FIGURE_HEAD = re.compile(r'(?:figure|total|count|number|metric|value|statistic|claim|rate)s?', re.I)
# A measure the pair's figures stand for; after a condition about the pair it is the pair's only with the pair's basis
# or vocabulary ("the implied monthly activity", memo 100), never with another noun ("monthly costs").
_MEASURE_HEAD = re.compile(r'(?:activity|activities|volumes?|scale|engagement|growth)', re.I)
_VERB_GROUP = frozenset({'is', 'are', 'was', 'were', 'be', 'been', 'being', 'may', 'might', 'could', 'can', 'would',
                         'will', 'should', 'must', 'appear', 'appears', 'seem', 'seems', 'look', 'looks', 'likely',
                         'possibly', 'potentially', 'probably', 'perhaps', 'materially', 'significantly',
                         'substantially', 'also', 'even', 'to'})
_DETERMINERS = frozenset({'the', 'a', 'an', 'this', 'that', 'these', 'those', 'its', 'their', 'each', 'either', 'both'})
_SUBJECT_QUALIFIERS = frozenset({'key', 'main', 'headline', 'reported', 'stated', 'claimed', 'larger', 'smaller',
                                 'higher', 'lower', 'former', 'latter', 'first', 'second', 'same', 'two', "company's",
                                 "deck's", "presentation's", "management's", "founders'", 'and', 'or',
                                 'implied', 'resulting', 'apparent', 'effective', 'underlying', 'overall', 'combined'})
# What may follow the pair's judgment in its own clause (_replaceable): coordinated judgments and their hedges, an
# object or comparison naming only the pair's measure or figures ("misrepresent the scale of actual activity", memo
# 100; "overstates the page-10 count", "overstated compared with the bare bot count"), citations and closing
# punctuation. The clarification replaces all of it; anything else ("(in management's view)", "according to
# management", "…, as noted earlier") is text it would delete, so the clause is kept (review of 72418e2).
_JUDGMENT_TAIL = re.compile(
    r'\s*' + _JUDGMENT_WORD + r'(?:\s+(?:and|or)\s+(?:(?:may|might|could|be|is|are|possibly|potentially|perhaps|'
    r'probably|likely|even|also|materially|significantly|substantially)\s+)*' + _JUDGMENT_WORD + r')*', re.I)
_TAIL_OBJECT_WORDS = frozenset({'of', 'actual', 'real', 'true', 'bare', 'as', 'than', 'compared', 'with', 'to',
                                'relative', 'against', 'versus', 'vs', 'vs.'})


def _replaceable(text, pair):
    """The text from a judgment to its clause's end is what the pair's clarification may replace (_JUDGMENT_TAIL)."""
    text = _REF.sub('', text)
    judgments = _JUDGMENT_TAIL.match(text)
    if not judgments:
        return False
    rest = text[judgments.end():]
    rest = re.sub(r'\b(page|slide)\s+(\d+)\b', r'\1-\2', re.sub(r'\bper\s+(month|week|day|year)\b', r'/\1', rest, flags=re.I),
                  flags=re.I)
    words = rest[:re.search(r'\s*[.!]?["”’)]*\s*$', rest).start()].split()
    return all(word.lower() in _DETERMINERS or word.lower() in _TAIL_OBJECT_WORDS or
               word.lower() in _SUBJECT_QUALIFIERS or _MEASURE_HEAD.fullmatch(word) or _FIGURE_HEAD.fullmatch(word) or
               _pair_basis(word, pair) or _pair_word(word, pair) or _pair_page(word, pair)
               for word in words)


_TAIL_INTERVAL = re.compile(r'(?:(?P<adjective>monthly|weekly|daily|yearly)|/\s?(?P<rate>month|week|day|year)|'
                            r'(?P<cumulative>cumulative(?:ly)?)|(?P<interval>interval))', re.I)


def _pair_basis(word, pair):
    """A basis word after the judgment names one of the pair's own bases (Pair.intervals): "the monthly figure",
    "the cumulative figure" for this pair, never "the yearly count" (review of 71ece83). "interval" names no other
    figure; any other basis wording ("run-rate") is not read as the pair's."""
    hit = _TAIL_INTERVAL.fullmatch(word)
    if not hit:
        return False
    if hit['interval']:
        return True
    if hit['cumulative']:
        return 'cumulative' in pair.intervals
    rate = hit['rate'] or {'monthly': 'month', 'weekly': 'week', 'daily': 'day', 'yearly': 'year'}[hit['adjective'].lower()]
    return rate.lower() in pair.intervals


def _pair_page(word, pair):
    """A page or slide after the judgment is one the pair's members are on (Pair.pages): "the page-10 count", never
    "the page-99 count" (review of 71ece83)."""
    hit = re.fullmatch(r'(?:page|slide)-?(\d+)', word, re.I)
    return bool(hit) and int(hit.group(1)) in pair.pages


def _pair_placing(word, pair):
    """A subject word that places the pair's own figure (review of 8f11844): one of its bases (_pair_basis), alone
    or on its noun or figure ("messages/month", "500M/month"), one of its pages (_pair_page), or its own vocabulary
    (_pair_word). "The page-99 figure", "the yearly figure" and "the cumulative, monthly, and daily figures" name a
    figure the pair does not establish, so the judgment is not the pair's."""
    hits = list(_BASIS_WORDS.finditer(word))
    if hits:
        rest = _BASIS_WORDS.sub('', word).strip('/-')
        return (all(_pair_basis(hit.group(0).replace(' ', ''), pair) for hit in hits) and
                (not rest or _pair_word(rest, pair)))
    return _pair_word(word, pair) or _pair_page(word, pair)


def _has_verb(text):
    """The text has a verb (_ITEM_VERB). A participle or judgment word after its determiner, with only placing words
    between, modifies the figure and is not a verb: "The reported monthly figure [S2], and the larger figure [S3] are
    overstated" is one compound subject, "Management reported the monthly figure [S2], and …" two clauses (review of
    72418e2)."""
    for hit in _ITEM_VERB.finditer(text):
        before = re.findall(r"[\w'’]+", _REF.sub('', text[:hit.start()]))
        while before and (before[-1].lower() in _SUBJECT_QUALIFIERS or _BASIS_WORDS.fullmatch(before[-1])):
            before.pop()
        if not (before and before[-1].lower() in _DETERMINERS):
            return True
    return False


def _names_pair(text, pair):
    """The text names the pair's figures or their bases: a basis word, a figure referent ("the larger figure"), or
    the pair's counted noun. Read for the condition a judgment depends on ("If the cumulative figure is presented as
    monthly, the claim is overstated"); citations never match."""
    return bool(_BASIS_WORDS.search(text) or _FIGURE_REFERENT.search(text) or
                (pair.noun and re.search(rf'\b{re.escape(pair.noun[:-1])}s?\b', text, re.I)))


def _pair_word(word, pair):
    """A word of the pair's own vocabulary: its counted noun, a topic of its evidence, or one of its figures."""
    return bool((pair.noun and re.fullmatch(rf'{re.escape(pair.noun[:-1])}s?', word, re.I)) or
                word.lower() in pair.topics or word.rstrip('+').lower() in pair.figures)


def _owns_subject(segment, position, pair):
    """The judgment at `position` in its clause is about the pair. Its subject is the pair's (see _FIGURE_HEAD): a
    pair head and qualifiers that all place or qualify the pair's figure. After a condition naming the pair the head
    may instead be a measure carrying the pair's basis ("the implied monthly activity", memo 100); the qualifiers are
    read either way ("If the figures are monthly, the hiring claim is overstated" is not the pair's; review of
    a6dcddf). Anything else in the clause leaves whose judgment it is open, so the clause is not the pair's: words
    before the subject that are not a condition ("Management says", "In management's view,"). Text after the judgment
    ("…, in management's view", "(in management's view)") is read in _judged_segments, for both rules (_replaceable;
    review of 72418e2)."""
    tokens = re.findall(r"[\w'’/.+-]+|,", _REF.sub('', segment[:position]))
    while tokens and tokens[-1].lower() in _VERB_GROUP:
        tokens.pop()
    subject = []
    while tokens and tokens[-1] != ',' and tokens[-1].lower() not in _DETERMINERS:
        subject.insert(0, tokens.pop().strip('.'))
    while {'and', 'or'} & {word.lower() for word in subject} and tokens and tokens[-1] == ',':
        tokens.pop()                         # a serial list's earlier items: "The cumulative, monthly, and daily …"
        while tokens and tokens[-1] != ',' and tokens[-1].lower() not in _DETERMINERS:
            subject.insert(0, tokens.pop().strip('.'))
    if tokens and tokens[-1] != ',':
        tokens.pop()                         # the subject's determiner
    if tokens and re.fullmatch(r'\d+[.)]?|[-+]', tokens[0]):
        tokens.pop(0)                        # a list number or marker
    if not subject:
        return False
    before = ' '.join(tokens)
    condition = bool(tokens) and _CONDITION.fullmatch(tokens[0]) and tokens.count(',') == 1 and tokens[-1] == ','
    if tokens and not condition:
        return False
    head, qualifiers = subject[-1], subject[:-1]
    if not all(_pair_placing(word, pair) or word.lower() in _SUBJECT_QUALIFIERS for word in qualifiers):
        return False
    if (_FIGURE_HEAD.fullmatch(head) or head.lower() in pair.topics or
            (_pair_word(head, pair) and any(word.rstrip('+').lower() in pair.figures for word in qualifiers))):
        return True
    # The consequence of a condition about the pair: a measure the pair's figures stand for, with the pair's basis.
    return bool(condition and _names_pair(before, pair) and _MEASURE_HEAD.fullmatch(head) and
                any(_BASIS_WORDS.search(word) or _pair_word(word, pair) for word in qualifiers))


def _clauses(sentence):
    """The sentence split at _CLAUSE_SPLIT, except at the comma closing a serial list: when the clause before it has
    a bare comma and no verb at all ("The cumulative, monthly, and daily figures are overstated"). A clause with a verb
    is a clause, whatever its commas ("The monthly figure is inflated, in management's view, but …"; review of
    a6dcddf)."""
    parts = _CLAUSE_SPLIT.split(sentence)
    out = parts[:1]
    for separator, segment in zip(parts[1::2], parts[2::2]):
        left = out[-1]
        if separator.startswith(',') and ',' in left and not _has_verb(left):
            out[-1] += separator + segment
        else:
            out += [separator, segment]
    return out


def _judged_segments(sentence, pair):
    """The sentence split into clauses (_CLAUSE_SPLIT); the chain of every segment; and for each segment holding a
    judgment: whether a pair referent governs it, whether it is denied, its chain, and whether the judgment is the
    pair's. A referent governs its own segment and the continuation fragments that follow it after a dash or a
    linking comma ("These figures ... — raising the possibility of inflation", memo 101, OF-905). A ";" clause, or
    any other segment that is not a continuation fragment (a new subject: "— an analyst is wrong"), starts a new
    chain. A denial before the referent, or of an earlier judgment in the chain, covers the judgments that continue
    it ("Nothing suggests these figures are wrong — or inflated"; review of 750de3f). A judgment is the pair's when a
    referent governs it or one of its chain's judgments has the pair as its subject (_owns_subject); any other
    judgment is about something else ("— misleading advertising is wrong [S2, S3]", "— monthly costs are inflated";
    reviews of 9b28e14 and 8d7f8dc). Neither makes it the pair's when its chain's first clause goes on past the
    judgment with text the clarification would delete (_replaceable: "(in management's view)", "according to
    management"; review of 72418e2); continuation fragments are a fixed grammar and need no such reading."""
    parts = _clauses(sentence)
    judged, chains, governed, denied, chain, opened = [], [], False, False, 0, set()
    for i in range(0, len(parts), 2):
        segment = parts[i]
        if i and (parts[i - 1].strip() == ';' or not _CONTINUATION.fullmatch(segment)):
            governed, denied, chain = False, False, chain + 1     # a new clause or a new subject
        chains.append(chain)
        referent = _PAIR_REFERENT.search(segment)
        if referent:
            governed = True
            denied = denied or _denied(segment, referent.start())
        judgment = _JUDGMENT.search(segment)
        if judgment:
            denied = denied or _denied(segment, judgment.start())
            judged.append((i, governed, denied, chain))
            if (not i or chains[-2] != chain) and not _replaceable(segment[judgment.start():], pair):
                opened.add(chain)            # text after the judgment the clarification would delete
    owned = {c for k, c in enumerate(chains)
             if any(_owns_subject(parts[2 * k], hit.start(), pair) for hit in _JUDGMENT.finditer(parts[2 * k]))}
    judged = [(i, governed, denied, c, (governed or c in owned) and c not in opened) for i, governed, denied, c in judged]
    return parts, judged, chains


def _referent_judged(sentence, pair):
    """Every judgment of the pair is governed by "one or both figures" / "these figures": _referent_judgment decides
    it, with its protections (a denial, a contradicted pair, the sentence's other clauses; reviews of 1801ec5 and
    memo 101). Judgments that are not the pair's are left to neither rule."""
    _, judged, _ = _judged_segments(sentence, pair)
    return all(governed for _, governed, _, _, owned in judged if owned)


def _judgment(sentence, pair, changes):
    """An error judgment about the pair's bases becomes its neutral clarification; its citations stay. Only the
    chains holding the pair's judgments are replaced, adjacent ones by one clarification; every other clause stays
    as written, whether it judges something else or states a fact ("; management has not clarified the
    definitions"; reviews of 9b28e14 and 8d7f8dc)."""
    if _asks(sentence) or not _JUDGMENT.search(sentence) or _referent_judged(sentence, pair):
        return sentence
    if not (_BASIS_WORDS.search(sentence) or _cited(sentence)):
        return sentence
    parts, judged, chains = _judged_segments(sentence, pair)
    mine = {chain for _, _, _, chain, owned in judged if owned}          # not empty: see _referent_judged
    runs = []                                # (the pair's?, first part index, last part index)
    for k, chain in enumerate(chains):
        if runs and (chain in mine) == runs[-1][0]:
            runs[-1][2] = 2 * k
        else:
            runs.append([chain in mine, 2 * k, 2 * k])
    for is_mine, first, _ in runs:
        if is_mine and first and parts[first - 1].startswith(',') and not _has_verb(parts[first - 2]):
            return sentence                  # a compound subject, not two clauses (review of a6dcddf)
    changes.append('basis_overstatement')
    out = []
    for is_mine, first, last in runs:
        text = ''.join(parts[first:last + 1])
        if is_mine:                          # the pair's clauses: one clarification, their citations, their end
            end = re.search(r'[.!]?["”’)]*\s*$', text).group(0)
            groups = ' '.join(f'[{group}]' for group in _REF.findall(text))
            lead = _LEAD.match(text).group('lead') if first == 0 else text[:len(text) - len(text.lstrip())]
            words = pair.clarification if first == 0 else pair.clarification[0].lower() + pair.clarification[1:]
            text = f"{lead}{words}{' ' + groups if groups else ''}{end}"
        out.append((parts[first - 1] if first else '') + text)
    return ''.join(out)


def _referent_judgment(sentence, pair, changes):
    """An error judgment on "one or both figures" of this pair: that clause becomes the pair's clarification; the
    sentence's other clauses stay (OF-806)."""
    if pair.contradicted or _asks(sentence) or not _PAIR_REFERENT.search(sentence):
        return sentence
    parts, judged, _ = _judged_segments(sentence, pair)
    hit, replaced = False, set()
    for i, governed, denied, chain, owned in judged:
        if not (governed and owned) or denied:
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
    """"the cumulative figure" when this pair admits nothing cumulative and has a side with no stated interval: that
    figure has no stated interval. A pair of two stated rates has no such figure, so nothing is relabelled (review of
    8f11844)."""
    if pair.cumulative_admitted or not pair.unspecified_members or not _CUMULATIVE_REFERENT.search(sentence):
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


# The words that may lead the company's own figures into a clause with no reporting verb, besides the placing words
# and the cited statements' own words: its own source named ("the deck's", "the self-reported") and the "taking ...
# at face value" frame (memo 101's base scenario).
_OWN_HEAD_WORDS = frozenset({'selfreported', 'company', "company's", 'deck', "deck's", 'pitch', 'presentation',
                             "presentation's", 'founders', "founders'", 'founder', "founder's", 'management',
                             "management's", 'taking', 'at', 'face', 'value'})


def _own_head(head, cited, facts, topics=frozenset()):
    """Every word before the moved citations is the company's own source, a placing word, or a word or figure of the
    cited statements: no other speaker ("An analyst describes the deck's ...", "An analyst's reading of ...") and no
    aside (a parenthesis is not a plain gap). An allowlist, so an unlisted third party or verb keeps the sentence
    (review of 7fb484b). `topics`: the pair's own evidence categories ("the usage figures"), for a condition's
    subject (OF-1003)."""
    statements = [_DIGIT_GROUP.sub('', fact.lower()) for ref, *_, fact in facts.places if ref in cited]
    vocabulary = (_PLACING_WORDS | _OWN_HEAD_WORDS | {word for fact in statements for word in re.findall(r'[a-z]+', fact)}
                  | {form for fact in statements for form in _stated_forms(fact)} | topics)
    text = re.sub(r'\bself-reported\b', 'selfreported', head[_LEAD.match(head).end():], flags=re.I)
    return _plain_words(text, vocabulary)


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
    found += [(m.start(), m.end(), m.group('ctx'), False) for m in _TIME_CONTEXT.finditer(sentence)
              if sentence[:m.start()].count('(') == sentence[:m.start()].count(')')]
    for at, end, claimed, aside in sorted(found):
        if _conditional(sentence, at):
            continue
        clause_end = bool(_CLAUSE_END.match(sentence, end))
        if not clause_end and not _TRAILING_WITH.match(sentence, end):
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
        tail = None if clause_end else _trailing_clause(sentence, end, pair, facts)
        if not clause_end and tail is None:
            continue                           # a closing clause the rule does not know: no place for the fact
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
        head = _VERIFICATION_QUALIFIER.sub(' ', sentence[start:first])   # a verification qualifier is no denial
        clause_words = _VERIFICATION_QUALIFIER.sub(' ', sentence[start:at])
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
        if not verbs and not _own_head(head, cited, facts):
            continue                           # someone else's words before the figures (review of 7fb484b)
        words = re.findall(r"[\w']+", _REF.sub(' ', clause_words).lower())
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
        if (aside or verbs) and tail is None:  # the company's verb carries on: "..., and separately X on page 12"
            body = ''.join(', and separately ' + text for text in facts_text)
        else:                                  # no verb to carry on, or after another clause: a clause of its own
            body = '; the deck separately states ' + ', and separately '.join(facts_text)
        clarification = pair.clarification[0].lower() + pair.clarification[1:]
        if clarification not in sentence:
            body += f' ({clarification})'
        changes.append('basis_source_context')
        if tail is not None:                   # after the closing "with ..." clause, which keeps its own subject
            return out + sentence[end:tail] + body + sentence[tail:]
        return out + body + sentence[end:]
    return sentence


def _trailing_clause(sentence, end, pair, facts):
    """Where the moved fact goes when the context phrase is followed by a closing "with ..." clause: before the
    sentence's final punctuation (memo 103, OF-1102). Only a clause about something else: no ref of any pair, no
    condition, no page, slide or other heading, and none of this pair's figures, noun or bases (", with 500M
    messages/month stated separately" is about the figures). None otherwise: the sentence is kept."""
    match = _TRAILING_WITH.match(sentence, end)
    if match is None:
        return None
    body = match.group('body')
    members = set().union(*(p.members for p in facts.pairs))
    words = _REF.sub(' ', body)
    if (set(_cited(body)) & members or _CONDITION.search(words) or _CONTEXT_PHRASE.search(words)
            or _TIME_CONTEXT.search(words) or re.search(r"\b(?:pages?|slides?|headings?)\b|'[^']+'", words, re.I)
            or _names_pair(words, pair) or any(hit.group(0).strip().lower() in pair.figures for hit in _FIGURE.finditer(words))):
        return None
    return match.start('end')


# A condition that accepts the cited figures rather than supposing anything about their date or basis (memo 102,
# OF-1003): "If the traction figures [refs] are taken at face value under the 'X' framing, ...". An allowlist: any
# other predicate ("reflects a monthly run-rate", "also falls under", "dates from") is a hypothesis and is kept.
_ACCEPTANCE_CONDITION = re.compile(r'\b(?:if|assuming|supposing|suppose)\b', re.I)
_ACCEPTANCE = re.compile(r"\s*(?:are|is|were|was|be)\s+(?:all\s+)?(?:taken|accepted|read|treated)\s+"
                         r"(?:at\s+(?:their\s+|its\s+)?face\s+value|as\s+(?:stated|reported|presented|given))\s*", re.I)
# What may end a condition's context phrase: the comma before its consequence, a ";" or the end of the sentence.
_ANTECEDENT_END = re.compile(r'\s*(?:,|;|[.!]?["”’)]*\s*$)')


def _condition_context(sentence, facts, changes):
    """A condition that only accepts the cited figures, followed by a context phrase that only one side's refs
    belong to: the context is not supposed, it is carried onto the other side's refs (OF-1003). Those refs leave the
    condition's citations and follow the sentence as their own fact, with their own page and context."""
    if _asks(sentence) or not facts.pairs:
        return sentence
    places = {ref: (page, context, fact) for ref, page, context, fact in facts.places}
    for match in _CONTEXT_PHRASE.finditer(sentence):
        at, end, claimed = match.start(), match.end(), match.group('ctx') or match.group('ctx2')
        if sentence[:at].count('(') != sentence[:at].count(')') or not _ANTECEDENT_END.match(sentence, end):
            continue
        start = _place_clause_start(sentence, at)
        conditions = list(_ACCEPTANCE_CONDITION.finditer(sentence, start, at))
        if not conditions:
            continue                           # not a condition: the affirmative rule above decides
        condition = conditions[-1]
        groups = list(_REF.finditer(sentence, condition.end(), at))
        if not groups or not _ACCEPTANCE.fullmatch(sentence, groups[-1].end(), at):
            continue                           # another predicate: a hypothesis about the figures, kept
        if any(not re.fullmatch(r'[\s,]*(?:and\s+)?', sentence[a.end():b.start()]) for a, b in zip(groups, groups[1:])):
            continue
        cited = [ref for group in groups for ref in _split_refs(group.group(1))]
        if any(ref not in places for ref in cited) or set(cited) & facts.narrated:
            continue
        outside = [ref for ref in cited if places[ref][1] != claimed]
        inside = [ref for ref in cited if places[ref][1] == claimed]
        pair = next((p for p in facts.pairs if len(p.sides) == 2 and set(outside) <= p.members), None)
        if not outside or not inside or pair is None:
            continue                           # nothing stays under the heading, or the moved refs are no pair's side
        if any(set(_split_refs(group.group(1))) <= set(outside) for group in groups):
            continue                           # a group of moved refs alone ("[S1, S2] and [S3]") would be left empty
                                               # and its connector dangling: no faithful rewrite, kept (review of 75ca81f)
        head = sentence[condition.end():groups[0].start()]
        clause = sentence[start:at]
        # A denial or hedge cannot pass: _ACCEPTANCE is matched whole and the subject is an allowlist.
        if (any(name.lower() in clause.lower() for name in facts.narrators) or _ATTRIBUTION.search(sentence[:at])
                or not _own_head(head, cited, facts, pair.topics)):
            continue                           # someone else's figures, or words the rule does not know
        out, pos = sentence[:groups[0].start()], groups[0].start()
        for group in groups:
            keep = [ref for ref in _split_refs(group.group(1)) if ref not in outside]
            out += sentence[pos:group.start()] + '[' + ', '.join(keep) + ']'
            pos = group.end()
        out += sentence[pos:]
        runs = []                              # adjacent refs on one page and context share a run
        for ref in outside:
            if runs and runs[-1][0] == places[ref][:2]:
                runs[-1][1].append(ref)
            else:
                runs.append((places[ref][:2], [ref]))
        body = '; the deck separately states ' + ', and separately '.join(
            ' and '.join(f'{places[ref][2]} [{ref}]' for ref in refs) + f' on page {page}'
            + (f", under '{context}'" if context else '') for (page, context), refs in runs)
        clarification = pair.clarification[0].lower() + pair.clarification[1:]
        if clarification not in sentence:
            body += f' ({clarification})'
        final = re.search(r'[.!]?["”’)]*\s*$', out)
        changes.append('basis_condition_context')
        return out[:final.start()] + body + out[final.start():]
    return sentence


# A condition opening the sentence (memo 103, OF-1103). One elsewhere ("X would be large if ...", "According to an
# analyst, if ...") is not read.
_LEADING_CONDITION = re.compile(r'^\s*(?:[-•*·–]\s*)?(?:if|assuming|supposing|suppose)\b', re.I)
# A comma that continues the antecedent with a further condition (", and if they date from ...") rather than ending it.
_FURTHER_CONDITION = re.compile(r'\s*(?:(?:and|or)\s+)?(?:if|assuming|supposing|suppose|whether|unless)\b', re.I)
# What a condition may suppose about the cited figures without supposing their date: that they are accurate,
# correct, reliable or valid, taken or accepted as stated, or that one basis is the correct one ("the per-month figure
# is the correct basis"). An allowlist: any other word ("dates", "reflects", "as of", "April", a heading) is a
# hypothesis the condition makes itself, and the sentence is kept.
_ACCEPTING_WORDS = frozenset({'is', 'are', 'were', 'was', 'be', 'accurate', 'correct', 'reliable', 'valid', 'true',
                              'right', 'taken', 'accepted', 'read', 'treated', 'at', 'face', 'value', 'as', 'stated',
                              'reported', 'presented', 'given', 'basis', 'per'})


def _accepting_antecedent(text, cited, facts, pair):
    """Every word of the condition is the company's own source, a placing or accepting word, a word or figure of the
    cited statements, the pair's category or one of its bases: it supposes nothing about the figures' date."""
    statements = [_DIGIT_GROUP.sub('', fact.lower()) for ref, *_, fact in facts.places if ref in cited]
    vocabulary = (_PLACING_WORDS | _OWN_HEAD_WORDS | _ACCEPTING_WORDS | pair.topics | set(pair.intervals)
                  | {_RATE_ADJECTIVE.get(interval, interval) for interval in pair.intervals}
                  | {word for fact in statements for word in re.findall(r'[a-z]+', fact)}
                  | {form for fact in statements for form in _stated_forms(fact)})
    text = re.sub(r'\bself-reported\b', 'selfreported', _VERIFICATION_QUALIFIER.sub(' ', text), flags=re.I)
    text = re.sub(r'(?<=[a-z])[-/](?=[a-z])', ' ', text, flags=re.I)    # "per-month", "messages/month"
    return _plain_words(text, vocabulary)


# The consequence's subject: the company named ("ManyChat"), "the company", "the platform" or "it". Its own words
# are not read; the predicate after it must describe the cited figures (review of c8a0336).
_CONSEQUENCE_SUBJECT = re.compile(r"\s*(?:the\s+(?:company|platform|business)|it|[A-Z][\w&'.-]*(?:\s+[A-Z][\w&'.-]*){0,2})"
                                  r"(?=\s)")
# What a consequence may say about the cited figures besides their own words, figures and the pair's categories: the
# scale they describe ("would represent a platform with significant throughput", "had a large platform"). An
# allowlist: another metric ("revenue would be $10M"), a denial, a speaker or an unknown word keeps the sentence.
_CONSEQUENCE_WORDS = frozenset({'would', 'could', 'might', 'may', 'will', 'have', 'has', 'had', 'been', 'be', 'is',
                                'was', 'represent', 'represents', 'represented', 'built', 'reached', 'achieved',
                                'operated', 'run', 'with', 'its', 'by', 'period', 'referenced', 'already',
                                'significant', 'sizeable', 'sizable', 'large', 'meaningful', 'substantial',
                                'considerable', 'high', 'volume', 'bot', 'messaging', 'user', 'base'})
# At least one of these, the pair's categories or the cited statements' words must be in the predicate: it is the
# figures' scale the heading dates, not something else ("revenue would be significant" names none).
_SCALE_NOUNS = frozenset({'platform', 'scale', 'throughput', 'adoption', 'footprint', 'reach', 'volume'})
# The heading phrase must close the consequence's clause: the sentence ends, or a dash, ";" or ":" follows. Anything
# else after it (", according to an analyst", ", only if ...", "[S1, S3]") is part of the consequence, and kept.
_CONSEQUENCE_CLOSE = re.compile(r'\s*(?:[.!]?["”’)]*\s*$|[—–;:]|-(?=\s))')
# What may not follow the clause either: a condition, supposition or contingency, a citation, a speaker, a denial or
# the date itself ("— if the monthly figure dates from that period", "— subject to the monthly figure referring to
# that period", "— according to an analyst").
_LATER_HYPOTHESIS = re.compile(r"\b(?:if|whether|unless|assuming|supposing|suppose|provided|providing|so\s+long\s+as|"
                               r"as\s+long\s+as|on\s+(?:the\s+)?(?:condition|assumption|basis|understanding)|presum\w*|"
                               r"dat(?:e|es|ed|ing)|subject\s+to|contingent|conditional\w*|conditioned|dependent|"
                               r"depend(?:s|ing)?|only\s+when|insofar|in\s+(?:the\s+)?event|in\s+case|should|given\s+that|"
                               r"refer\w*|relat(?:e|es|ed|ing)|appl(?:y|ies|ied)|cover(?:s|ed|ing)?)\b", re.I)
# Nor may it name the figures, their basis, a place or any time: a clause about them after the heading may suppose
# their date in words no list holds ("— with the monthly figure from that period"). Besides these, the pair's
# categories, bases and the cited statements' words; any figure or quoted span keeps the sentence too.
_REST_FIGURE_WORDS = frozenset({'figure', 'figures', 'number', 'numbers', 'metric', 'metrics', 'statement',
                                'statements', 'period', 'periods', 'time', 'times', 'timing', 'when', 'whenever', 'then',
                                'until', 'before', 'after', 'since', 'during', 'interval', 'intervals', 'basis', 'bases',
                                'page', 'pages', 'slide', 'slides', 'heading', 'headings', 'month', 'monthly', 'week',
                                'weekly', 'day', 'daily', 'year', 'yearly', 'annual', 'annually', 'quarter', 'quarterly',
                                'cumulative', 'total', 'run', 'rate', 'april', 'apr'})
# Words that deny or all but deny a consequence wherever they stand, its subject included ("No platform would ...",
# "Neither platform ...", "Few platforms ..."); any "-n't" word too (review of c49cb4d).
_CONSEQUENCE_DENIAL = _DENIAL | frozenset({'few', 'hardly', 'barely', 'scarcely', 'nobody', 'nowhere'})


def _rest_free(rest, cited, facts, pair):
    """What follows the consequence's clause (after a dash, ";" or ":") adds nothing that qualifies it: no condition
    or contingency, no citation, speaker or denial, and no mention of the figures, their basis, a place or a time."""
    text = rest.lower().translate(_APOSTROPHES)
    words = set(re.findall(r"[a-z']+", re.sub(r'(?<=[a-z])[-/](?=[a-z])', ' ', text)))
    statements = [_DIGIT_GROUP.sub('', fact.lower()) for ref, *_, fact in facts.places if ref in cited]
    figure_words = ((_REST_FIGURE_WORDS | pair.topics | set(pair.intervals)
                     | {_RATE_ADJECTIVE.get(interval, interval) for interval in pair.intervals}
                     | {word for fact in statements for word in re.findall(r'[a-z]+', fact)}) - _PLACING_WORDS
                    | {'figure', 'figures', 'total', 'rate'})
    return not (_REF.search(rest) or _LATER_HYPOTHESIS.search(rest) or _ATTRIBUTION.search(rest)
                or words & _DENIAL or any(word.endswith("n't") for word in words)
                or words & figure_words or re.search(r"\d|'[^']+'|‘[^’]+’", rest))


def _figures_consequence(consequence, cited, facts, pair):
    """The consequence before the heading phrase is a subject and a predicate about the cited figures' scale, in
    allowlisted words, naming that scale (a scale noun, the pair's category or a word of the cited statements)."""
    subject = _CONSEQUENCE_SUBJECT.match(consequence)
    if subject is None:
        return False
    every = set(re.findall(r"[a-z']+", consequence.lower().translate(_APOSTROPHES)))
    if every & _CONSEQUENCE_DENIAL or any(word.endswith("n't") for word in every):
        return False                           # a denial, the subject's too ("No platform", "Neither platform")
    statements = [_DIGIT_GROUP.sub('', fact.lower()) for ref, *_, fact in facts.places if ref in cited]
    nouns = {form[3] for form in map(_statement_form, statements) if form and form[3]} | pair.topics   # "bots"
    vocabulary = ((_PLACING_WORDS | _CONSEQUENCE_WORDS | _SCALE_NOUNS | nouns
                   | {word for fact in statements for word in re.findall(r'[a-z]+', fact)}) - _DENIAL
                  | {form for fact in statements for form in _stated_forms(fact)})
    predicate = re.sub(r'(?<=[a-z])[-/](?=[a-z])', ' ', consequence[subject.end():], flags=re.I)  # "high-volume"
    words = set(re.findall(r"[a-z']+", re.sub(r'(?<=[a-z])[-/](?=[a-z])', ' ', consequence.lower())))
    return _plain_words(predicate, vocabulary) and bool(words & (_SCALE_NOUNS | nouns))   # "the platform would be large"


def _consequence_context(sentence, facts, changes):
    """A condition that only accepts the cited figures (or their basis), whose CONSEQUENCE places them at page 10's
    heading ("..., ManyChat would represent a platform ... at the time of the 'Traction by Apr-16' slide"): the
    heading is carried onto page 12's figure, which the condition never supposed (OF-1103). The condition and its
    consequence are kept whole; right after the phrase, a parenthesis places the heading on its own page and page
    12's figure on its page, with no date context. Conditions that suppose the date themselves are kept, and so is
    a consequence about anything but the cited figures' scale, one the heading does not close (", according to an
    analyst", ", only if ...", a citation), and one followed by a condition, speaker, citation or denial (review of
    c8a0336)."""
    if _asks(sentence) or not facts.pairs:
        return sentence
    condition = _LEADING_CONDITION.match(sentence)
    if condition is None:
        return sentence
    depth, split = 0, None                     # the antecedent ends at the first comma that does not add a condition
    for i in range(condition.end(), len(sentence)):      # (never one inside a parenthesis or a citation group)
        if sentence[i] in '([':
            depth += 1
        elif sentence[i] in ')]':
            depth = max(0, depth - 1)
        elif (sentence[i] == ',' and depth == 0 and not _FURTHER_CONDITION.match(sentence, i + 1)
              and not (sentence[i - 1:i].isdigit() and sentence[i + 1:i + 2].isdigit())):   # not "140,000+"
            split = i
            break
    if split is None:
        return sentence
    found = sorted([(m.start(), m.end(), m.group('ctx') or m.group('ctx2')) for m in _CONTEXT_PHRASE.finditer(sentence, split)]
                   + [(m.start(), m.end(), m.group('ctx')) for m in _TIME_CONTEXT.finditer(sentence, split)])
    found = [hit for hit in found if sentence[:hit[0]].count('(') == sentence[:hit[0]].count(')')]
    if not found:
        return sentence
    at, end, claimed = found[0]
    if sentence.startswith(f" ('{claimed}' heads page", end):
        return sentence                        # already placed
    places = {ref: (page, context, fact) for ref, page, context, fact in facts.places}
    antecedent = sentence[condition.end():split]
    cited = [ref for group in _REF.finditer(antecedent) for ref in _split_refs(group.group(1))]
    if not cited or any(ref not in places for ref in cited) or set(cited) & facts.narrated:
        return sentence
    inside = list(dict.fromkeys(ref for ref in cited if places[ref][1] == claimed))
    outside = list(dict.fromkeys(ref for ref in cited if places[ref][1] != claimed))
    pair = next((p for p in facts.pairs if len(p.sides) == 2 and outside and set(outside) <= p.members), None)
    if pair is None or any(places[ref][1] for ref in outside):
        return sentence                        # no pair side carried, or it has a heading of its own
    pages = {page for _, page, context, _ in facts.places if context == claimed}
    if len(pages) != 1:
        return sentence                        # the heading is no single page's
    consequence = sentence[split + 1:at]
    close = _CONSEQUENCE_CLOSE.match(sentence, end)
    if close is None:
        return sentence                        # the consequence goes on past the heading: its words are not read
    rest = sentence[close.end():]              # after a dash, ";" or ":"; empty at the sentence's end
    if (_REF.search(consequence) or not _rest_free(rest, cited, facts, pair)
            or any(name.lower() in sentence.lower() for name in facts.narrators)
            or not _figures_consequence(consequence, cited, facts, pair)
            or not _accepting_antecedent(antecedent, cited, facts, pair)):
        return sentence                        # a cited consequence or one about something else, a later condition,
                                               # speaker, citation or denial, or a hypothesis of the condition's own
    runs = []                                  # adjacent refs on one page share a run
    for ref in outside:
        if runs and runs[-1][0] == places[ref][0]:
            runs[-1][1].append(ref)
        else:
            runs.append((places[ref][0], [ref]))
    moved = ', and '.join(' and '.join(f'{places[ref][2]} [{ref}]' for ref in refs) + f' on page {page}'
                          for page, refs in runs)
    held = ' and '.join(f'{places[ref][2]} [{ref}]' for ref in inside)
    note = (f" ('{claimed}' heads page {next(iter(pages))}" + (f', which states {held}' if held else '')
            + f'; the deck states {moved}, with no date context)')
    changes.append('basis_consequence_context')
    return sentence[:end] + note + sentence[end:]


# A citation group written straight after one figure ("states '500M messages/month' [C3, S3]"): the figure, any
# opening quote before it and closing quote after it. The figure may carry its noun and its interval.
_MENTION_END = re.compile(r"(?P<open>['‘\"“])?(?<![\w.,$])(?P<value>\$?\d[\d,]*(?:\.\d+)?[kmb]?)(?P<plus>\+?)"
                          r"(?:/(?P<rate>[a-z]+))?(?:\s+(?P<noun>[a-z]+)(?:/(?P<nrate>[a-z]+))?)?"
                          r"(?P<close>['’\"”])?\s*$", re.I)
# Two citation groups contrasted as two figures: "[C3, S2] vs [C2, S3]".
_VERSUS = re.compile(r"\[(?P<a>[A-Z]\d+(?:\s*[,;]\s*[A-Z]\d+)*)\]\s*(?:vs\.?|versus)\s*"
                     r"\[(?P<b>[A-Z]\d+(?:\s*[,;]\s*[A-Z]\d+)*)\]", re.I)


def _statement_form(statement):
    """A statement's first figure as (value, plus, interval, noun): "500M messages/month" -> ("500m", "", "month",
    "messages"). Lowercased, digit groups joined."""
    found = re.search(r'(?<![\w.$])(\$?\d[\d,]*(?:\.\d+)?[kmb]?)(\+?)(?:/([a-z]+))?(?:\s+([a-z]+)(?:/([a-z]+))?)?',
                      _DIGIT_GROUP.sub('', statement.lower()))
    if found is None:
        return None
    return found.group(1).replace(',', ''), found.group(2), found.group(3) or found.group(5) or '', found.group(4) or ''


def _mention_side(pair, mention):
    """The one side of `pair` a figure mention names, or None. The figure's value, "+" and stated interval must be
    exactly one side's ("500M messages/month" is the monthly side); with no interval written, only a quotation of
    one side's whole statement names it ("'500M messages'"). The same number alone names no side."""
    value = mention.group('value').lower().replace(',', '')
    rate = (mention.group('rate') or mention.group('nrate') or '').lower()
    noun = (mention.group('noun') or '').lower()
    quoted = bool(mention.group('open')) and bool(mention.group('close'))
    forms = [_statement_form(statement) for statement in pair.statements]
    if any(form is None for form in forms) or len(forms) != len(pair.sides):
        return None
    if rate:
        sides = [i for i, (v, plus, interval, n) in enumerate(forms)
                 if v == value and interval == rate and plus == mention.group('plus') and (not noun or noun == n)]
    elif quoted:
        text = _DIGIT_GROUP.sub('', mention.group(0).strip().strip('\'‘’"“” ').lower())
        sides = [i for i, statement in enumerate(pair.statements)
                 if ' '.join(_DIGIT_GROUP.sub('', statement.lower()).split()) == ' '.join(text.split())]
    else:
        return None
    return sides[0] if len(sides) == 1 else None


def _compares(refs, pair):
    """The group cites both sides' claims ("[C3, C2]") or both sides' statements ("[S2, S3]"): a comparison of the
    two figures, whatever figure it follows."""
    claims = {i for i, members in enumerate(pair.sides) for ref in refs if ref in members and ref in pair.refs}
    statements = {i for i, members in enumerate(pair.sides) for ref in refs if ref in members and ref not in pair.refs}
    return len(claims) > 1 or len(statements) > 1


# Words that make a clause deny what a source states ("Page 10 does not state ...", "the slide omits ..."): its
# citations are the evidence of that source, not of the figure it lacks (review of 75ca81f).
_IDENTITY_DENIAL = _DENIAL | frozenset({'omit', 'omits', 'omitted', 'absent', 'missing', 'nowhere'})
_NAMED_PAGES = re.compile(r'\bpages?[\s-]+(\d+(?:\s*(?:,|and|or|&)\s*\d+)*)', re.I)
# Typographic apostrophes read as "'": "doesn’t" is "doesn't" (review of f2a6ac1). Any "-n't" word denies.
_APOSTROPHES = str.maketrans({'’': "'", '‘': "'", 'ʼ': "'"})


def _clause_bounds(sentence, at, soft=True):
    """(start, end) of the clause holding `at`: it stops at ";", ":", a dash, a clause-linking comma (", while") or
    an unmatched parenthesis on either side, and at the sentence's end. With soft=False only ";" and a clause-linking
    comma end it: a colon, a dash or a parenthesis does not."""
    start, depth = 0, 0
    for i in range(at - 1, -1, -1):
        ch = sentence[i]
        if soft and ch == ')':
            depth += 1
        elif soft and ch == '(':
            if depth == 0:
                start = i + 1
                break
            depth -= 1
        elif depth == 0 and (ch == ';' or (soft and ch in ':—')):
            start = i + 1
            break
        elif depth == 0 and ch == ',' and _CLAUSE_LINK.match(sentence, i):
            start = _CLAUSE_LINK.match(sentence, i).end()
            break
    end, depth = len(sentence), 0
    for i in range(at, len(sentence)):
        ch = sentence[i]
        if soft and ch == '(':
            depth += 1
        elif soft and ch == ')':
            if depth == 0:
                end = i
                break
            depth -= 1
        elif depth == 0 and (ch == ';' or (soft and ch in ':—') or (ch == ',' and _CLAUSE_LINK.match(sentence, i))):
            end = i
            break
    return start, end


# A segment that reports for itself: it opens (after an optional "and", "but", "while", "whereas") with a source as
# subject and that subject's finite reporting verb: "page 12 states", "the deck stated", "while page 12 lists". An
# allowlist (review of b718566): a reporting word alone is often an adjective or participle ("the reported '500M
# messages/month'", "reported as", "as reported", "the figure reported elsewhere"), a subordinate "as the deck states"
# reports nothing of its own, and a page alone ("on page 12, ...") is no clause. A verb followed by "as" is read as
# a participle.
_OWN_REPORT = re.compile(
    r"\s*(?:(?:and|but|while|whereas)\s+)?"
    r"(?:pages?[\s-]+\d+|slides?[\s-]+\d+|the\s+(?:deck|pitch\s+deck|company|slide|presentation|founders?|management|team)"
    r"|it|they)\s+(?:(?:also|separately|instead|itself)\s+)?"
    r"(?:states|stated|reports|reported|presents|presented|lists|listed|shows|showed|gives|gave|cites|cited)\b"
    r"(?!\s+as\b)", re.I)


def _governing_clause(sentence, at):
    """The words governing the group at `at`, citations removed: its own clause when that clause reports something
    itself (_OWN_REPORT: "(page 12 states '500M messages/month' [C3, S3])"); otherwise the figure is only set off by
    a colon, a dash or a parenthesis, and the clause around it names the source and any denial ("Page 10 does not
    state: the reported '500M messages/month' [C3, S2]", "... does not state (reported as '...' [C3, S2])")."""
    start, end = _clause_bounds(sentence, at)
    inner = _REF.sub(' ', sentence[start:end])
    if _OWN_REPORT.match(inner):
        return inner
    start, end = _clause_bounds(sentence, at, soft=False)
    return _REF.sub(' ', sentence[start:end])


def _states_as_cited(sentence, at, pair, sides, places):
    """The clause holding the group at `at` affirms the figure as the named side's: it is not a question, not a
    "whether", denies nothing, and every page or source context it names is one of `sides`' own (a "vs" names both). "Page 10 does not state
    '500M messages/month' [C3, S2]" and "Does page 10 state ...?" cite page 10 as what page 10 states: kept."""
    if _asks(sentence):
        return False
    clause = _governing_clause(sentence, at).translate(_APOSTROPHES)
    words = set(re.findall(r"[\w']+", clause.lower()))
    if words & _IDENTITY_DENIAL or any(word.endswith("n't") for word in words) or 'whether' in words:
        return False
    own = {places[ref][0] for i in sides for ref in pair.sides[i] if ref in places}
    named = {int(n) for found in _NAMED_PAGES.finditer(clause) for n in re.findall(r'\d+', found.group(1))}
    if named - own:
        return False                           # another page is named: the refs may be its evidence
    others = {places[ref][1] for i, members in enumerate(pair.sides) if i not in sides for ref in members if ref in places}
    others -= {places[ref][1] for i in sides for ref in pair.sides[i] if ref in places}
    return not any(context and context.translate(_APOSTROPHES).lower() in clause.lower() for context in others)


def _identity_fix(refs, pair, side, changes):
    """`refs` cite the figure on `side`: a ref of the pair's other side becomes this side's ref of the same kind
    (its claim for a claim, its one repeating statement for a statement). With no such ref, the wrong ref is dropped
    when the group still cites this side, and kept, as unresolved, when it does not. Other refs are untouched."""
    other = set().union(*(members for i, members in enumerate(pair.sides) if i != side))
    claim, statements = pair.refs[side], sorted(pair.sides[side] - set(pair.refs))
    out, unresolved = [], False
    for ref in refs:
        if ref not in other:
            out.append(ref)
            continue
        replacement = claim if ref in pair.refs else (statements[0] if len(statements) == 1 else None)
        if replacement is not None and replacement not in refs and replacement not in out:
            out.append(replacement)
        elif replacement is None and not set(refs) & pair.sides[side]:
            out.append(ref)                    # nothing the evidence can put in its place
            unresolved = True
    if unresolved:
        changes.append('basis_citation_identity_unresolved')
    return out


def _citation_identity(sentence, facts, changes):
    """A citation group attached to one figure of a pair cites that figure's own side (OF-1004): a ref of the other
    side ("'500M messages/month' [C3, S3]", C3 being page 10's claim) becomes the named side's ref. Only a group
    written straight after one figure that names a side, or one operand of "[...] vs [...]" whose other operand cites
    one side alone. A group after a list of the pair's figures ("500M messages and 500M messages/month [C3, C2]"), a
    group following no figure ("the two slides present conflicting bases [C3, C2]") and refs outside the pair are
    kept: comparisons cite both sides."""
    if not facts.pairs:
        return sentence
    places = {ref: (page, context) for ref, page, context, fact in facts.places}
    out, pos, previous_end = '', 0, 0
    for group in _REF.finditer(sentence):
        refs = _split_refs(group.group(1))
        before = sentence[:group.start()]
        mention = _MENTION_END.search(before)
        fixed = refs
        if mention is not None:
            for pair in facts.pairs:
                if len(pair.sides) != 2 or not set(refs) & pair.members or _compares(refs, pair):
                    continue
                side = _mention_side(pair, mention)
                if side is None:
                    continue
                value = mention.group('value').lower().replace(',', '')
                earlier = sentence[max(previous_end, _place_clause_start(sentence, mention.start())):mention.start()]
                if any(_figure_key(token).split('/')[0].rstrip('+') == value.rstrip('+')
                       for token in _FIGURE_TOKEN.findall(_DIGIT_GROUP.sub('', earlier).lower())):
                    continue                   # the group may cover an earlier figure of the pair: a list
                if not _states_as_cited(sentence, group.start(), pair, {side}, places):
                    continue                   # a denial, a question or another source named: kept
                fixed = _identity_fix(refs, pair, side, changes)
        out += sentence[pos:group.start()] + ('[' + ', '.join(fixed) + ']' if fixed != refs else group.group(0))
        if fixed != refs:
            changes.append('basis_citation_identity')
        pos = previous_end = group.end()
    sentence = out + sentence[pos:]

    def contrast(match):
        a, b = _split_refs(match.group('a')), _split_refs(match.group('b'))
        for pair in facts.pairs:
            if len(pair.sides) != 2:
                continue
            on = lambda refs: {i for i, members in enumerate(pair.sides) for ref in refs if ref in members}
            sa, sb = on(a), on(b)
            if _compares(a, pair) or _compares(b, pair) or not _states_as_cited(sentence, match.start(), pair, {0, 1}, places):
                continue
            if len(sa) == 1 and sb == {0, 1}:
                b = _identity_fix(b, pair, 1 - next(iter(sa)), changes)
            elif len(sb) == 1 and sa == {0, 1}:
                a = _identity_fix(a, pair, 1 - next(iter(sb)), changes)
            else:
                continue
            changes.append('basis_citation_identity')
            between = sentence[match.end('a') + 1:match.start('b') - 1]
            return '[' + ', '.join(a) + ']' + between + '[' + ', '.join(b) + ']'
        return match.group(0)

    return _VERSUS.sub(contrast, sentence)


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
        own_noun = rf'\b{re.escape(pair_noun[:-1])}s?\b' if pair_noun else None
        if noun is None and not (own_noun and re.match(r'\s+' + own_noun, sentence[match.end():], re.I)):
            return match.group(0)            # another metric's phrase ("the cumulative and monthly revenue")
        if noun is not None:
            # A generic figure noun names no metric of its own: a qualifier after it must name the pair's noun
            # ("figures for messages", "presentations of the 500M messages figure"), never anything else ("figures
            # for revenue", "figures for bots"; review of 7fb484b).
            after = sentence[noun.end():]
            if re.match(r'\s+(?:for|of|on|about|in|from|across)\b', after, re.I) and not (own_noun and re.match(
                    r'\s+\w+\s+(?:(?:the|a|an|these|those)\s+)?(?:[$\d][\w.,+/$]*\s+)?' + own_noun, after, re.I)):
                return match.group(0)
        mine = owner(match)
        if mine is None or mine.cumulative_admitted or not mine.unspecified_members:
            return match.group(0)            # admitted cumulative, or no side without a stated interval (two rates)
        group = _REF.search(sentence, match.end())
        if _OTHER_METRIC.search(sentence[_place_clause_start(sentence, match.start()):
                                         group.start() if group else len(sentence)]):
            return match.group(0)            # another metric named before the owning citation ("differ from revenue")
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
        sentence = _citation_identity(sentence, facts, changes)
        sentence = _location(sentence, facts, changes)
        sentence = _context_aside(sentence, facts, changes)
        sentence = _condition_context(sentence, facts, changes)
        sentence = _consequence_context(sentence, facts, changes)
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
