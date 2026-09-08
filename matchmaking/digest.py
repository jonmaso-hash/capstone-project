# matchmaking/digest.py
"""
Turns the AIMatch cache into the weekly digest's hero card — one
best-match highlight per investor/founder. Deliberately one hero match,
not a list: both outside reviews of this plan warned against shipping a
"Marketplace This Week" dump on day one, and a single hero keeps the
free->paid gate legible instead of diffusing it across many rows.

Identity reveal is asymmetric by design: the investor-side card still
shows the founder's company name to Premium viewers (that's the core of
what an investor is paying to see, and founders are already discoverable
public profiles). The founder-side card never reveals investor identity,
Premium or not — a founder who knows exactly which investor matched can
solicit them directly, off-platform, which is the disintermediation
vector this asymmetry closes. Founder Premium's perk instead is the
monthly highlight boost (see Application.is_highlighted).
"""
from datetime import timedelta

from django.utils import timezone

from .match_components import evaluate_venture_match
from .match_score import Band

# The digest goes to every user, free included, so it takes the looser of
# the two bars: Notable (at least one thing both parties declared) rather
# than the Strong-plus-full-basis a priority alert demands.
#
# This used to be DIGEST_MIN_SCORE = 50.0 applied to AIMatch.score, which
# is raw cosine similarity. Across all 135 cached pairs that value ranges
# 0-41.6, so **zero** rows could ever clear it and the weekly digest sent
# nothing to anyone, every week, silently. A band cannot go stale that way:
# it is defined by evidence, not by a number someone guessed against a
# distribution nobody had measured.
DIGEST_MIN_BAND = Band.NOTABLE

# A change_reason older than this reads as stale news, not a fresh signal —
# omitted rather than shown once the pair's freshness has aged out.
FRESHNESS_WINDOW_DAYS = 7


def _amount_bucket(amount):
    if not amount:
        return None
    amount = float(amount)
    if amount < 250_000:
        return "Under $250K"
    if amount < 1_000_000:
        return "$250K–$1M"
    if amount < 5_000_000:
        return "$1M–$5M"
    return "$5M+"


def _ticket_range(investor_profile):
    lo, hi = investor_profile.ticket_size_min, investor_profile.ticket_size_max
    if lo and hi:
        return f"${float(lo):,.0f}–${float(hi):,.0f}"
    if lo:
        return f"${float(lo):,.0f}+"
    return investor_profile.investment_amount or None


def _freshness_reason(ai_match):
    """
    The one thing the AIMatch cache knows that the contract does not: when
    this pairing last changed, and why. None when there is no cached row.
    """
    if ai_match is None or not ai_match.last_changed_at or not ai_match.change_reason:
        return None
    if timezone.now() - ai_match.last_changed_at > timedelta(days=FRESHNESS_WINDOW_DAYS):
        return None
    return ai_match.change_reason


def _pick_hero(scored):
    """
    scored is an iterable of (counterpart, MatchResult). Ranks by band
    first, then by the canonical internal score - never by AIMatch.score,
    which is a raw semantic input and not a match score at all.
    """
    eligible = [(c, r) for c, r in scored if r.band >= DIGEST_MIN_BAND]
    if not eligible:
        return None, None
    return max(eligible, key=lambda pair: (pair[1].band, pair[1].score))


def get_investor_hero(investor_profile):
    """
    (application, result, ai_match_or_None) for this week's hero card, or
    (None, None, None) when nothing clears the band.

    Candidates are the discoverable founder population, NOT the AIMatch
    cache. The cache only ever holds pairs where BOTH sides already have
    an embedding (match_cache.upsert_match returns early otherwise), so
    reading candidates from it silently lost every pairing the contract
    can evaluate on declared signals alone. Measured on the audit fixture:
    an investor with no focus vector had 11 contract-eligible pairings, 0
    cached rows, and received nothing.

    Eligibility is the contract's to decide. Discovery must not pre-filter
    on a different rule, or the contract never gets to see the pairing.

    The cache is still consulted, but only for the freshness line.

    This evaluates the contract per candidate rather than reading a
    precomputed row, so it is O(founders) per investor. That is fine for a
    weekly batch job and is deliberately not optimised into a second cache
    -- a cache is what caused this defect.
    """
    from .models import AIMatch, Application

    candidates = Application.objects.discoverable().exclude(review_status='DENIED')
    application, result = _pick_hero(
        (app, evaluate_venture_match(app, investor_profile)) for app in candidates
    )
    if application is None:
        return None, None, None
    ai_match = AIMatch.objects.filter(investor=investor_profile, application=application).first()
    return application, result, ai_match


def get_founder_hero(application):
    """Reverse digest: same discovery rule, investors as candidates."""
    from .models import AIMatch, InvestorApplication

    candidates = InvestorApplication.objects.discoverable().exclude(review_status='DENIED')
    investor_profile, result = _pick_hero(
        (inv, evaluate_venture_match(application, inv)) for inv in candidates
    )
    if investor_profile is None:
        return None, None, None
    ai_match = AIMatch.objects.filter(investor=investor_profile, application=application).first()
    return investor_profile, result, ai_match


def build_investor_digest_card(investor_profile):
    """None if there's no eligible cached match to lead the digest with this week."""
    application, result, ai_match = get_investor_hero(investor_profile)
    if application is None:
        return None
    card = {
        # The band, not a percentage. A "43% fit" invites the reader to
        # treat it as a probability, and the evidence behind it - a sector
        # string, a stage string, one embedding - cannot carry that.
        'band': result.band.label,
        'sector': application.sector,
        'stage': application.stage,
        'raising_bucket': _amount_bucket(application.raising_amount),
        'freshness': _freshness_reason(ai_match),
        'is_premium_viewer': investor_profile.is_premium,
    }
    if investor_profile.is_premium:
        card['company_name'] = application.company_name
    return card


def build_founder_digest_card(application):
    """
    None if there's no eligible cached match to lead the reverse digest with
    this week. Unlike the investor-side card, this never reveals the
    investor's identity — not even to Founder Premium — since a founder who
    knows exactly which investor matched can solicit them directly, off-
    platform. Founder Premium's equivalent perk is the monthly highlight
    boost (see Application.is_highlighted) instead.
    """
    investor_profile, result, ai_match = get_founder_hero(application)
    if investor_profile is None:
        return None
    return {
        'band': result.band.label,
        'investment_focus_excerpt': (investor_profile.investment_focus or '')[:80],
        'ticket_range': _ticket_range(investor_profile),
        'freshness': _freshness_reason(ai_match),
    }


def investor_digest_message(card):
    if card['is_premium_viewer']:
        message = f"Your best match this week: a {card['band'].lower()} match — {card['company_name']} ({card['sector']}, {card['stage']})"
    else:
        message = f"Your best match this week: a {card['band'].lower()} match — {card['sector']}, {card['stage']}"
    if card['raising_bucket']:
        message += f", raising {card['raising_bucket']}"
    message += "."
    if card['freshness']:
        message += f" {card['freshness']}."
    if not card['is_premium_viewer']:
        message += " Upgrade to see who they are."
    return message


def founder_digest_message(card):
    message = f"An investor matched with you this week: a {card['band'].lower()} match"
    if card['investment_focus_excerpt']:
        message += f", focused on {card['investment_focus_excerpt']}"
    if card['ticket_range']:
        message += f", checks of {card['ticket_range']}"
    message += "."
    if card['freshness']:
        message += f" {card['freshness']}."
    return message
