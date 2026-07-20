# zelda_api/quotas.py
"""
AI credits — the guard on Zelda's memo/Truth-Delta Claude-cost surface.

Every other zelda_api endpoint (viewing a memo, viewing a valuation, IC
memo, chunk/insight browsing, vector search, RAG retrieval) reads rows that
were already generated — no fresh Claude spend, so those stay free and
uncapped. Confirmed at each read site: DocumentMemoView/DocumentValuationView/
TruthDeltaScoreView are GET-only reads of already-persisted rows, and
analyze_founder_profile explicitly returns an existing DocumentSource
instead of creating a new one when one already exists — ten investors
viewing the same founder share one memo, one Claude call. Pay-to-generate,
free-to-read.

Business valuation is deliberately NOT part of this shared pool — see
valuation_tier_for_new_upload() below. Everyone can always generate one
(no upload-time paywall); the paywall instead redacts the *rendering* of
a preview-tier report until it's unlocked, either per-document
(valuation_unlock_price()) or by staying under a plan's monthly full-tier
allowance (VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT for Investor/Buyer
Premium, VALUATION_FIRM_MONTHLY_LIMIT per Firm seat) — real, different
business terms from the memo/Truth-Delta pool, not just "a heavier
version of a memo."

Two call sites trigger a fresh Claude call and are gated by the shared
pool here:
  - DocumentIngestView.post, for document_type != 'business_valuation'
    (memo generation)
  - analyze_founder_profile (memo generation, investor-triggered, but
    only the first time — see reuse note above)
  - TruthDeltaVerifyView.post (verification — explicitly re-runnable per
    its own docstring, with no existing cap before this)

Credits, not a flat action count: a flat "1 free action total" gives a
free user zero room to experience more than one feature before hitting a
wall. Credits fix that while keeping the same underlying mechanism —
count real rows created in the window, no separate ledger table — just
weighted by job cost instead of counted flatly, mirroring
FREE_CRM_LEAD_LIMIT/DAILY_INTRO_REQUEST_LIMIT's "count existing rows"
convention in matchmaking/views.py.

Weekly soft cap, layered on top of the monthly one: every real Claude call
here is a single-shot, small-context Sonnet call (see intelligence_pipeline
.py's _call_claude_for_memo and truth_delta_engine.py's
_call_claude_for_verification — max_tokens 1536-4000, insight-summary
input, not full documents), so PREMIUM_CREDITS=100/month costs on the
order of $7-20/month even at the worst-case per-credit price (a memo,
with Celery's 3x task retry) — comfortably under even the cheapest
subscription ($99/mo Founder/Seller), so the monthly number itself didn't
need to shrink. WEEKLY_CREDIT_FRACTION exists for a different reason:
spreading usage across the month rather than letting it burst entirely
into one week, the same spirit as the weekly caps LLM providers put on
their own consumer plans.
"""
import math
from datetime import timedelta

from django.utils import timezone

FREE_CREDITS = 3
PREMIUM_CREDITS = 100
CREDIT_WINDOW_DAYS = 30

WEEKLY_WINDOW_DAYS = 7
# 40% of the monthly allowance per week — enough for a genuinely busy week
# (more than the perfectly-even ~23%) without ever letting a single week
# burn the whole month's credits in one sitting.
WEEKLY_CREDIT_FRACTION = 0.4
# Firm seats (matchmaking.models.Firm/FirmMembership) get a looser weekly
# fraction than an individual Premium seat — team diligence work is
# burstier (several analysts working the same live deal in the same week)
# and the firm's flat $5,000/mo already prices in higher usage per seat.
FIRM_WEEKLY_CREDIT_FRACTION = 0.7

CREDIT_COSTS = {
    'memo': 1,
    'truth_delta_verify': 1,
}

def _is_premium_user(user):
    for related_name in (
        'match_founder_profile',
        'match_investor_profile',
        'match_seller_profile',
        'match_buyer_profile',
    ):
        profile = getattr(user, related_name, None)
        if profile is not None and getattr(profile, 'is_premium', False):
            return True
    return False


def _credits_used_in_window(user, window_start):
    """Shared by credits_used (30-day) and credits_used_this_week (7-day) — same weighting, different lookback."""
    from .vector_models import DocumentSource
    from .truth_delta_models import TruthDeltaReport
    from .models import AnalysisCreditCharge

    docs = DocumentSource.objects.filter(
        uploaded_by=user, created_at__gte=window_start,
    ).exclude(status='error').exclude(credit_charge__isnull=False)
    # business_valuation documents are excluded entirely — they're priced
    # and gated by valuation_access() below, not this shared pool.
    memo_credits = docs.exclude(document_type='business_valuation').count() * CREDIT_COSTS['memo']
    verification_credits = TruthDeltaReport.objects.filter(
        document__uploaded_by=user, created_at__gte=window_start,
    ).count() * CREDIT_COSTS['truth_delta_verify']
    charged_credits = sum(
        CREDIT_COSTS[charge.job_type]
        for charge in AnalysisCreditCharge.objects.filter(user=user, created_at__gte=window_start)
    )
    return memo_credits + verification_credits + charged_credits


def credits_used(user):
    """
    Weighted AI-credit spend this user triggered in the current 30-day window.

    Documents with an AnalysisCreditCharge row are excluded from their
    owner's own count and added to the charged user's instead — that's
    the one case (analyze_founder_profile's confirm step) where whoever
    triggered the generation isn't the document's owner. See
    AnalysisCreditCharge's docstring for why uploaded_by can't just be
    the investor instead.
    """
    window_start = timezone.now() - timedelta(days=CREDIT_WINDOW_DAYS)
    return _credits_used_in_window(user, window_start)


def credits_used_this_week(user):
    """Same weighting as credits_used, but the trailing 7 days — the soft weekly cap's own counter."""
    window_start = timezone.now() - timedelta(days=WEEKLY_WINDOW_DAYS)
    return _credits_used_in_window(user, window_start)


def credit_limit(user):
    return PREMIUM_CREDITS if _is_premium_user(user) else FREE_CREDITS


def _has_firm_seat(user):
    return getattr(user, 'firm_membership', None) is not None


def weekly_credit_limit(user):
    """
    Floored at FREE_CREDITS: at FREE_CREDITS=3, spreading is meaningless —
    there's no realistic "burst" to prevent with an allowance that small,
    so the weekly fraction would just make the free tier feel more
    restrictive than its own monthly cap for no real benefit. The floor
    only matters for tiers whose fraction would otherwise dip below it;
    Premium/Firm are well above it and get the full spreading effect.
    """
    fraction = FIRM_WEEKLY_CREDIT_FRACTION if _has_firm_seat(user) else WEEKLY_CREDIT_FRACTION
    return max(math.ceil(credit_limit(user) * fraction), FREE_CREDITS)


def has_credits_for(user, job_type):
    """
    Staff are exempt. Everyone else needs enough remaining credits under
    BOTH the monthly allowance and the weekly soft cap to cover job_type's
    cost — hitting either one blocks the action.
    """
    if user.is_staff:
        return True
    cost = CREDIT_COSTS[job_type]
    if credits_used(user) + cost > credit_limit(user):
        return False
    return credits_used_this_week(user) + cost <= weekly_credit_limit(user)


def remaining_analyses(user):
    """For display only ("2 of 3 analyses remaining") — never "credits" to a user."""
    return max(0, credit_limit(user) - credits_used(user))


def remaining_weekly_analyses(user):
    """The weekly soft cap's own remaining count, for display alongside remaining_analyses."""
    return max(0, weekly_credit_limit(user) - credits_used_this_week(user))


def usage_nearing_limit(user):
    """
    True once either window has crossed 80% used — a soft warning, not a
    block, so a user can see it coming instead of hitting a wall mid-task.
    """
    limit = credit_limit(user)
    if limit and credits_used(user) / limit >= 0.8:
        return True
    weekly_limit = weekly_credit_limit(user)
    if weekly_limit and credits_used_this_week(user) / weekly_limit >= 0.8:
        return True
    return False


def upgrade_message(user):
    """
    User-facing copy always says "AI analyses," never "credits" — credits
    are an internal weighting mechanism (a valuation costs more than a
    memo), not a concept users should have to learn. Shows what's actually
    left rather than assuming zero — a heavier job (e.g. a valuation) can
    get blocked while the user still has some remaining allowance. Points
    at whichever window is actually the blocker (monthly vs. the weekly
    soft cap) rather than always quoting the monthly one.
    """
    remaining, limit = remaining_analyses(user), credit_limit(user)
    weekly_remaining, weekly_limit = remaining_weekly_analyses(user), weekly_credit_limit(user)

    if weekly_remaining < remaining:
        return (
            f"You've used this week's AI analyses allowance ({weekly_remaining} of {weekly_limit} remaining this week). "
            f"It resets on a rolling 7-day basis — or upgrade to Premium for a higher weekly allowance."
        )
    return (
        f"You don't have enough AI analyses left for this ({remaining} of {limit} remaining this period). "
        f"Upgrade to Premium for a much higher monthly allowance."
    )


# ==========================================================================
# BUSINESS VALUATION — priced and gated separately from the shared AI-credit
# pool above. Real cost per valuation call is ~$0.02 (a single small-context
# Sonnet call — see intelligence_pipeline.py's _call_claude_for_valuation),
# so every number below carries enormous margin; the limits are about
# product positioning (stickiness, encouraging a subscription, making a
# one-off purchase feel low-risk), not cost recovery.
# ==========================================================================

# Investor/Buyer Premium: roughly one report a day, deliberately generous
# for stickiness — a founder/seller diligence habit forms faster at this
# cadence than at a stingier monthly number.
VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT = 30
# Firm seats: proportionally higher than an individual Premium seat (8x,
# vs. the AI-credit pool's parity), since a firm's $5,000/mo already prices
# in heavier, multi-analyst usage across up to 100 seats.
VALUATION_FIRM_MONTHLY_LIMIT = 250

# Founder/Seller: valuation is never bundled into their $99/mo subscription
# — pay-per-use only, priced low enough that a merely-curious founder buys
# one on impulse rather than deciding it's not worth the money.
VALUATION_REPORT_PRICE_USD = 9.99
# Investor/Buyer overage beyond their included 30/month.
VALUATION_OVERAGE_PRICE_USD = 5.00
# Firm overage beyond the included 250/month per seat — priced lower than
# the individual overage rate for the same bulk-relationship reason the
# base firm allowance is 8x an individual's.
VALUATION_FIRM_OVERAGE_PRICE_USD = 1.99

# Keyed by ValuationPurchase.purchase_type — lets call sites (e.g. the
# valuation history page) show what a purchased report cost without
# re-deriving the price from the purchase_type by hand.
VALUATION_PURCHASE_TYPE_PRICES = {
    'report': VALUATION_REPORT_PRICE_USD,
    'overage': VALUATION_OVERAGE_PRICE_USD,
    'firm_overage': VALUATION_FIRM_OVERAGE_PRICE_USD,
}


def _valuations_used_this_month(user):
    """
    Full-tier business_valuation documents this user has generated in the
    last 30 days — excludes failed generations, same convention as
    credits_used. Deliberately excludes tier='preview' documents: a free
    preview never draws down a plan's included allowance, only a full
    unlock does (whether paid for or covered by the plan).
    """
    from .vector_models import DocumentSource
    window_start = timezone.now() - timedelta(days=CREDIT_WINDOW_DAYS)
    return DocumentSource.objects.filter(
        uploaded_by=user, document_type='business_valuation', valuation_tier='full',
        created_at__gte=window_start,
    ).exclude(status='error').count()


def valuation_tier_for_new_upload(user):
    """
    'full' or 'preview' for a document `user` is uploading right now.

    Every user can always upload and generate a valuation — there's no
    more upload-time paywall (see DocumentIngestView). This only decides
    whether that generation renders the complete report or the free
    preview (see DocumentValuationView, which redacts a 'preview'-tier
    report's number/methodology/full risk list server-side).

      - Staff: always 'full'.
      - Firm seats: 'full' while under VALUATION_FIRM_MONTHLY_LIMIT/month,
        then 'preview' (unlockable per-document — see
        valuation_unlock_price).
      - Investor/Buyer Premium: 'full' while under
        VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT/month, then 'preview'.
      - Everyone else (Founder/Seller, role-less users, and
        non-Premium Investor/Buyer — valuation was never bundled into
        their plan): always 'preview'.
    """
    if user.is_staff:
        return 'full'

    if getattr(user, 'firm_membership', None) is not None:
        return 'full' if _valuations_used_this_month(user) < VALUATION_FIRM_MONTHLY_LIMIT else 'preview'

    role_profile = getattr(user, 'match_investor_profile', None) or getattr(user, 'match_buyer_profile', None)
    if role_profile and getattr(role_profile, 'is_premium', False):
        return 'full' if _valuations_used_this_month(user) < VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT else 'preview'

    return 'preview'


def valuation_tier_status(user):
    """
    Display-only context for the upload page: what tier the user's next
    upload will render at, plus their remaining monthly allowance if one
    applies. Purely informational — uploading is never blocked.
    """
    tier = valuation_tier_for_new_upload(user)
    has_firm = getattr(user, 'firm_membership', None) is not None
    role_profile = getattr(user, 'match_investor_profile', None) or getattr(user, 'match_buyer_profile', None)
    is_plan_premium = has_firm or (role_profile and getattr(role_profile, 'is_premium', False))

    if not is_plan_premium:
        return {'tier': tier, 'remaining': None, 'limit': None, 'is_plan_premium': False}

    limit = VALUATION_FIRM_MONTHLY_LIMIT if has_firm else VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT
    used = _valuations_used_this_month(user)
    return {'tier': tier, 'remaining': max(limit - used, 0), 'limit': limit, 'is_plan_premium': True}


def valuation_unlock_price(user):
    """
    (purchase_type, price) to unlock ONE preview-tier report into 'full'
    for `user` right now — same role-based discount ladder as the monthly
    allowances themselves: Firm cheapest, Investor/Buyer Premium next
    (both closer to being, or already being, a paying subscriber), flat
    rate for everyone else.
    """
    if getattr(user, 'firm_membership', None) is not None:
        return 'firm_overage', VALUATION_FIRM_OVERAGE_PRICE_USD
    if getattr(user, 'match_investor_profile', None) or getattr(user, 'match_buyer_profile', None):
        return 'overage', VALUATION_OVERAGE_PRICE_USD
    return 'report', VALUATION_REPORT_PRICE_USD


def unlock_valuation_document(document, purchase_type, stripe_checkout_session_id=''):
    """
    Flips a preview-tier document to 'full' and records the purchase that
    paid for it — called directly from the Stripe webhook the moment
    payment succeeds (unlike the old pay-before-upload flow, there's no
    "next generation" to wait for: the document already exists and the
    user is unlocking this specific one).
    """
    from .models import ValuationPurchase
    document.valuation_tier = 'full'
    document.save(update_fields=['valuation_tier'])
    return ValuationPurchase.objects.create(
        user=document.uploaded_by, purchase_type=purchase_type,
        stripe_checkout_session_id=stripe_checkout_session_id,
        redeemed_document=document, redeemed_at=timezone.now(),
    )
