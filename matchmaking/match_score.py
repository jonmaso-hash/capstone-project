"""
The Interlink Match Score - canonical contract v1.

One definition of "match", enforced in one place. Before this, the
codebase had three unrelated scales (raw cosine, a 0.7/0.3 blend, a
0.5/0.25/0.25 blend), thresholds set against the wrong one, and at least
four ways for absent information to become positive evidence. Re-tuning
weights could not fix that, because the weights were never the
disagreement - the meaning was.

    Match Score - the strength of demonstrated fit between two parties.

Four concepts stay separate and must never be folded back together:

    eligibility      can this pairing exist at all?      hard filters
    match strength   how much evidence of fit is there?  band (+ score)
    evidence basis   how much information was available? basis count
    user preference  what did a human say about it?      never here

The BAND is the entire user-facing surface. The numeric score exists only
to order candidates within a band and must never be rendered to a user:
the evidence is a handful of coarse signals, and a continuous 0-100
number implies a resolution that evidence does not have.

Rules, each of which retires a specific defect found in the audit:

    R1  A component returns a value or None. Never a stand-in.
        (retires ai_score = 50.0, which outranked all 126 real pairs)
    R2  Absence never redistributes weight onto the survivors. It lowers
        the basis count, which gates the band - never the arithmetic.
        (measured: naive renormalisation raised an empty profile 57->60)
    R3  No single signal can reach Strong.
        (retires stage-alone = 60, industry + NO_PREFERENCE = 65)
    R4  The absence of a stated preference is not evidence.
        (retires NO_PREFERENCE scoring +25)
    R5  Attributes that do not differentiate never enter match strength.
        (prior funding and capital efficiency raise a founder equally
        against every investor, so they cannot be evidence of fit)
    R6  Sparse keyword overlap is coverage, not fit: basis only.
    R7  Correlated evidence cannot count twice - see independent_count.
"""
from dataclasses import dataclass, field
from enum import IntEnum
from itertools import combinations

CONTRACT_VERSION = 'v1'

# How a signal relates to fit. Only DECLARED and INFERRED can move match
# strength; COVERAGE says how much was knowable, never how good it is.
DECLARED = 'declared'   # both sides stated something, and the statements agree
INFERRED = 'inferred'   # derived from content neither side asserted as a claim
COVERAGE = 'coverage'   # information availability (R6)


class Band(IntEnum):
    """
    The user-facing answer. IntEnum so a consumer can write
    `band >= Band.NOTABLE` instead of carrying a magic number - which is
    the whole point of retiring DIGEST_MIN_SCORE = 50.0, a threshold no
    pair in the database could reach.
    """
    UNRANKED = 0
    POSSIBLE = 1
    NOTABLE = 2
    STRONG = 3

    @property
    def label(self):
        return self.name.capitalize()


@dataclass(frozen=True)
class Signal:
    """
    One component's finding.

    source_family is the provenance that makes independence mechanically
    checkable rather than a judgement call: two signals drawn from the
    same family are one piece of evidence wearing two hats.

    derived_from names families whose evidence this signal may merely be
    restating. A semantic similarity computed over a description that
    itself asserts the sector is not independent corroboration of the
    sector match - it is that same assertion, embedded.
    """
    key: str
    value: float | None
    source_family: str
    party: str
    derived_from: frozenset = field(default_factory=frozenset)
    detail: str = ''

    @property
    def present(self):
        return self.value is not None

    @property
    def moves_strength(self):
        return self.present and self.party in (DECLARED, INFERRED)

    @property
    def corroborates(self):
        """
        Evidence *for* fit. A component that fired with 0 did not abstain -
        it looked and found disagreement, which is the opposite of
        corroboration and must never help carry a pairing to Strong.
        """
        return self.moves_strength and self.value > 0

    @property
    def contradicts(self):
        """Evidence *against* fit: the component looked and disagreed."""
        return self.moves_strength and self.value == 0

    @property
    def in_basis(self):
        return self.present


def _independent(a, b):
    """
    Two signals are independent only when each conclusion could survive
    if the other's underlying evidence were removed. Deliberately
    conservative: under-classifying Strong is an acceptable error, a
    loophole that counts one fact twice is not.
    """
    if a.source_family == b.source_family:
        return False
    if b.source_family in a.derived_from or a.source_family in b.derived_from:
        return False
    return True


def independent_count(signals):
    """
    Size of the largest pairwise-independent set of strength-moving
    signals. Exhaustive rather than greedy - the component roster is
    tiny, and a greedy pass can undercount depending on iteration order.
    """
    movers = [s for s in signals if s.corroborates]
    for size in range(len(movers), 0, -1):
        for combo in combinations(movers, size):
            if all(_independent(x, y) for x, y in combinations(combo, 2)):
                return size
    return 0


def derive_band(signals):
    """
    Strong    >= 2 independent corroborating signals, >= 1 of them
              party-declared, and nothing contradicting  (R3, R7)
    Notable   >= 1 party-declared corroborating signal
    Possible  something fired, but nothing corroborates a declared fit
    Unranked  nothing fired at all

    The "nothing contradicting" clause matters more than it looks. Without
    it, a founder whose sector is plainly outside the mandate and whose
    stage is merely adjacent has two independent declared signals - one
    saying no and one saying nearly - and lands in Strong. Two components
    that looked and disagreed are not corroboration.
    """
    movers = [s for s in signals if s.moves_strength]
    if not movers:
        return Band.UNRANKED

    corroborating = [s for s in movers if s.corroborates]
    has_declared_support = any(s.party == DECLARED for s in corroborating)
    contradicted = any(s.contradicts for s in movers)

    if has_declared_support and not contradicted and independent_count(signals) >= 2:
        return Band.STRONG
    if has_declared_support:
        return Band.NOTABLE
    return Band.POSSIBLE


def internal_score(signals):
    """
    Ordering only - never rendered to a user.

    Unweighted mean over the FULL strength-component roster, not over the
    components that happen to be present. That denominator is R2 made
    arithmetic: a missing component lowers the score instead of handing
    its share to the survivors. No weights are introduced here - choosing
    them is a calibration question that follows labelled data, and is not
    a prerequisite for the contract.
    """
    roster = [s for s in signals if s.party in (DECLARED, INFERRED)]
    if not roster:
        return 0.0
    return round(sum(s.value for s in roster if s.present) / len(roster), 2)


@dataclass(frozen=True)
class MatchResult:
    """What every consumer reads. One shape, one meaning, one version."""
    band: Band
    score: float
    basis: int
    independent: int
    signals: tuple
    contract_version: str = CONTRACT_VERSION

    @property
    def full_basis(self):
        """
        Every strength component this pairing could have had, it has.
        Alerting requires this on top of a Strong band: an outbound push
        spends the recipient's attention and should carry the strictest
        evidence standard in the system.
        """
        roster = [s for s in self.signals if s.party in (DECLARED, INFERRED)]
        return bool(roster) and all(s.present for s in roster)

    @property
    def persistable(self):
        """
        A pairing with no evidence has no prediction to record. Writing
        one anyway corrupts the very dataset used to grade the engine
        later, which is why this gates the snapshot tasks.
        """
        return self.basis > 0 and self.band > Band.UNRANKED

    def as_dict(self):
        return {
            'band': self.band.name,
            'score': self.score,
            'basis': self.basis,
            'independent': self.independent,
            'match_contract_version': self.contract_version,
        }


def build_result(signals):
    signals = tuple(signals)
    return MatchResult(
        band=derive_band(signals),
        score=internal_score(signals),
        basis=sum(1 for s in signals if s.in_basis),
        independent=independent_count(signals),
        signals=signals,
    )
