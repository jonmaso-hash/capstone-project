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

# Deliberately looser than MATCH_ALERT_THRESHOLD (80.0, matchmaking/tasks.py's
# premium-only priority alert) — the digest goes to every user, free
# included, so it needs a floor that still finds *a* best match most weeks
# rather than reusing the premium bar and often finding nothing.
DIGEST_MIN_SCORE = 50.0

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
    if not ai_match.last_changed_at or not ai_match.change_reason:
        return None
    if timezone.now() - ai_match.last_changed_at > timedelta(days=FRESHNESS_WINDOW_DAYS):
        return None
    return ai_match.change_reason


def get_investor_hero_match(investor_profile):
    return investor_profile.ai_matches.filter(score__gte=DIGEST_MIN_SCORE).order_by('-score').first()


def get_founder_hero_match(application):
    return application.ai_matches.filter(score__gte=DIGEST_MIN_SCORE).order_by('-score').first()


def build_investor_digest_card(investor_profile):
    """None if there's no eligible cached match to lead the digest with this week."""
    ai_match = get_investor_hero_match(investor_profile)
    if ai_match is None:
        return None
    application = ai_match.application
    card = {
        'score': round(float(ai_match.score)),
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
    ai_match = get_founder_hero_match(application)
    if ai_match is None:
        return None
    investor_profile = ai_match.investor
    return {
        'score': round(float(ai_match.score)),
        'investment_focus_excerpt': (investor_profile.investment_focus or '')[:80],
        'ticket_range': _ticket_range(investor_profile),
        'freshness': _freshness_reason(ai_match),
    }


def investor_digest_message(card):
    if card['is_premium_viewer']:
        message = f"Your best match this week: {card['score']}% fit — {card['company_name']} ({card['sector']}, {card['stage']})"
    else:
        message = f"Your best match this week: {card['score']}% fit — {card['sector']}, {card['stage']}"
    if card['raising_bucket']:
        message += f", raising {card['raising_bucket']}"
    message += "."
    if card['freshness']:
        message += f" {card['freshness']}."
    if not card['is_premium_viewer']:
        message += " Upgrade to see who they are."
    return message


def founder_digest_message(card):
    message = f"An investor matched with you this week: {card['score']}% fit"
    if card['investment_focus_excerpt']:
        message += f", focused on {card['investment_focus_excerpt']}"
    if card['ticket_range']:
        message += f", checks of {card['ticket_range']}"
    message += "."
    if card['freshness']:
        message += f" {card['freshness']}."
    return message
