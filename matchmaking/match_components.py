"""
The components that produce Signals for the Match Score contract.

Every function here returns a Signal whose value is a number or None.
None is never replaced by a stand-in, never redistributed, and never
treated as either good or bad news - it simply lowers the basis, which
gates the band (see matchmaking/match_score.py).

Two families deserve their provenance spelled out, because they are what
made "independence" impossible to enforce before:

  * The semantic signal is computed over the founder's description. That
    description usually asserts the sector and the stage in so many
    words, so a high similarity is often the sector/stage claim restated
    rather than corroboration of it. `_semantic_derived_from` detects
    that literally, and the contract then refuses to count the pair
    twice.

  * Deal structure used to award 25 points when the buyer selected
    NO_PREFERENCE - points for the absence of a preference. That is the
    contract's central prohibition stated as code, so it now returns
    None.
"""
import re

from .match_score import COVERAGE, DECLARED, INFERRED, Signal

SECTOR = 'sector'
STAGE = 'stage'
SEMANTIC = 'semantic'
SPARSE = 'sparse'
INDUSTRY = 'industry'
DEAL_SIZE = 'deal_size'
DEAL_STRUCTURE = 'deal_structure'


def _terms(text):
    return [t.strip().lower() for t in (text or '').replace('\n', ',').split(',') if t.strip()]


def _mentions(haystack, needle):
    """Whole-phrase containment, so 'AI' does not match 'chain'."""
    if not haystack or not needle:
        return False
    return re.search(r'\b' + re.escape(needle.strip().lower()) + r'\b', haystack.lower()) is not None


def _semantic_derived_from(description, sector, stage):
    """
    Which declared families the description text already asserts. Those
    are the families the semantic signal cannot independently corroborate.
    """
    families = set()
    if sector and _mentions(description, sector):
        families.add(SECTOR)
    if stage and _mentions(description, stage):
        families.add(STAGE)
    return frozenset(families)


def sector_signal(application, investor):
    """Founder sector against the investor's declared focus list."""
    app_sector = (application.sector or '').strip().lower()
    focus = _terms(getattr(investor, 'investment_focus', ''))
    if not app_sector or not focus:
        return Signal(SECTOR, None, SECTOR, DECLARED, detail='sector or focus not stated')
    if app_sector in focus:
        return Signal(SECTOR, 100.0, SECTOR, DECLARED, detail=f'{application.sector} is a stated focus')
    if any(term in app_sector or app_sector in term for term in focus):
        return Signal(SECTOR, 60.0, SECTOR, DECLARED, detail=f'{application.sector} is adjacent to the stated focus')
    return Signal(SECTOR, 0.0, SECTOR, DECLARED, detail=f'{application.sector} is outside the stated focus')


def stage_signal(application, investor):
    """Founder stage against the investor's declared stage."""
    from .utils import _is_adjacent_stage, _normalize_stage

    app_stage = _normalize_stage(application.stage)
    inv_stage = _normalize_stage(getattr(investor, 'investment_stage', ''))
    if not app_stage or not inv_stage:
        return Signal(STAGE, None, STAGE, DECLARED, detail='stage not stated on one side')
    if app_stage == inv_stage:
        return Signal(STAGE, 100.0, STAGE, DECLARED, detail=f'raising at {application.stage}, which matches the mandate')
    if _is_adjacent_stage(app_stage, inv_stage) or _is_adjacent_stage(inv_stage, app_stage):
        return Signal(STAGE, 50.0, STAGE, DECLARED, detail=f'{application.stage} is one stage from the mandate')
    return Signal(STAGE, 0.0, STAGE, DECLARED, detail=f'{application.stage} is outside the mandate')


def semantic_signal(application, investor):
    """
    Embedding similarity between the founder's description and the
    investor's focus text. Inferred, not declared - and carries the
    families its source text already asserts, so it cannot corroborate a
    claim it merely restates.
    """
    from .services.ai_engine import calculate_similarity

    derived = _semantic_derived_from(application.description, application.sector, application.stage)
    focus_vector = getattr(investor, 'focus_vector', None)
    description_vector = getattr(application, 'description_vector', None)
    if not focus_vector or not description_vector:
        return Signal(SEMANTIC, None, SEMANTIC, INFERRED, derived, 'no embedding on one side')
    try:
        raw = calculate_similarity(focus_vector, description_vector)
    except Exception:
        # Could not compute is still not-known. R1: never a stand-in.
        return Signal(SEMANTIC, None, SEMANTIC, INFERRED, derived, 'similarity could not be computed')
    return Signal(SEMANTIC, max(0.0, min(100.0, raw * 100)), SEMANTIC, INFERRED, derived,
                  'description and mandate are semantically related')


def sparse_signal(application, investor):
    """
    Exact-term overlap. COVERAGE: it says the two texts discuss the same
    things, which is information availability, not evidence of fit (R6).
    """
    from .services.ai_engine import calculate_sparse_similarity

    focus = getattr(investor, 'investment_focus', '')
    if not focus or not application.description:
        return Signal(SPARSE, None, SPARSE, COVERAGE, detail='no text on one side')
    try:
        raw = calculate_sparse_similarity(focus, application.description)
    except Exception:
        return Signal(SPARSE, None, SPARSE, COVERAGE, detail='overlap could not be computed')
    return Signal(SPARSE, max(0.0, min(100.0, raw * 100)), SPARSE, COVERAGE, detail='shared vocabulary')


def venture_signals(application, investor):
    """The full component roster for an investor <-> founder pairing."""
    return [
        sector_signal(application, investor),
        stage_signal(application, investor),
        semantic_signal(application, investor),
        sparse_signal(application, investor),
    ]


# ---------------------------------------------------------------- M&A ----

def industry_signal(seller, buyer):
    industry = (seller.industry or '').strip().lower()
    thesis = (getattr(buyer, 'acquisition_thesis', '') or '').lower()
    if not industry or not thesis:
        return Signal(INDUSTRY, None, INDUSTRY, DECLARED, detail='industry or thesis not stated')
    if _mentions(thesis, industry):
        return Signal(INDUSTRY, 100.0, INDUSTRY, DECLARED, detail=f'{seller.industry} named in the thesis')
    words = [w for w in industry.split() if len(w) > 2]
    if words and any(_mentions(thesis, w) for w in words):
        return Signal(INDUSTRY, 60.0, INDUSTRY, DECLARED, detail=f'{seller.industry} overlaps the thesis')
    return Signal(INDUSTRY, 0.0, INDUSTRY, DECLARED, detail=f'{seller.industry} is outside the thesis')


def deal_size_signal(seller, buyer):
    """
    Asking price against the buyer's budget - like against like, which is
    why this one was always sound where the venture side's cheque-vs-round
    comparison was not.

    asking_price is a non-null DecimalField defaulting to 0, exactly like
    raising_amount on the founder side: 0 means "hasn't said yet" far more
    often than "free". Treated as unstated rather than as a stated
    mismatch, so a seller who has not priced the business is ranked lower
    for thin evidence rather than scored against a number they never gave.
    """
    asking = seller.asking_price
    lo, hi = buyer.budget_min, buyer.budget_max
    if not asking or lo is None or hi is None:
        return Signal(DEAL_SIZE, None, DEAL_SIZE, DECLARED, detail='asking price or budget not stated')
    if lo <= asking <= hi:
        return Signal(DEAL_SIZE, 100.0, DEAL_SIZE, DECLARED, detail='asking price sits inside the budget')
    bound = lo if asking < lo else hi
    if bound and abs(asking - bound) / bound <= 0.2:
        return Signal(DEAL_SIZE, 50.0, DEAL_SIZE, DECLARED, detail='asking price is near the budget')
    return Signal(DEAL_SIZE, 0.0, DEAL_SIZE, DECLARED, detail='asking price is outside the budget')


def deal_structure_signal(seller, buyer):
    """
    NO_PREFERENCE returns None, not a match.

    A buyer who has not expressed a structural preference has told us
    nothing about fit with this seller; scoring it as agreement was the
    clearest case in the codebase of absence becoming positive evidence
    (R4). It was worth 25 of 100, enough to carry industry + nothing else
    to 65.
    """
    seller_structure = getattr(seller, 'deal_structure', None)
    preference = getattr(buyer, 'preferred_deal_structure', None)
    if not seller_structure or not preference or preference == 'NO_PREFERENCE':
        return Signal(DEAL_STRUCTURE, None, DEAL_STRUCTURE, DECLARED, detail='no structure preference stated')
    if seller_structure == preference:
        return Signal(DEAL_STRUCTURE, 100.0, DEAL_STRUCTURE, DECLARED, detail='deal structures agree')
    if seller_structure == 'OPEN':
        return Signal(DEAL_STRUCTURE, 60.0, DEAL_STRUCTURE, DECLARED, detail='seller is open on structure')
    return Signal(DEAL_STRUCTURE, 0.0, DEAL_STRUCTURE, DECLARED, detail='deal structures differ')


def deal_signals(seller, buyer):
    """The full component roster for a buyer <-> seller pairing."""
    return [
        industry_signal(seller, buyer),
        deal_size_signal(seller, buyer),
        deal_structure_signal(seller, buyer),
    ]
