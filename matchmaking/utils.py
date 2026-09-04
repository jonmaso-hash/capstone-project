import hashlib
import requests
import re
from django.core.cache import cache

HARD_FILTER_CACHE_TTL = 60 * 60 * 24 * 7  # 7 days — these fields change rarely

def calculate_match_score(investor, founder):
    """
    Calculates a match percentage between an investor and a founder.
    Patched to use correct model fields: investment_focus and sector.
    """
    score = 0
    
    # Safely parse the comma-separated focus industries
    investor_sectors = [
        s.strip().lower() 
        for s in getattr(investor, 'investment_focus', '').split(',') 
        if s.strip()
    ]
    founder_sector = getattr(founder, 'sector', '').lower() if founder.sector else ""
    
    if founder_sector in investor_sectors:
        score += 50
    
    if investor.investment_stage and founder.stage:
        if investor.investment_stage.lower() == founder.stage.lower():
            score += 30
    
    inv_stage_str = investor.investment_stage.lower() if investor.investment_stage else ""
    keywords = investor_sectors + [inv_stage_str]
    
    if founder.description:
        description_hits = sum(1 for word in keywords if word and word in founder.description.lower())
        if description_hits > 0:
            score += min(20, description_hits * 5)
            
    return score

def calculate_rule_based_score(application, investor):
    """
    Calculates a compatibility score (0-100) based on hard constraints
    like Sector and Investment Stage, plus two soft founder-side signals
    (prior funding, capital efficiency) that no investor field states an
    explicit preference for — they're rewarded generically as risk-reducers
    rather than "matched" against anything investor-specified. Clamped to
    100 since sector+stage alone can already reach that ceiling.
    """
    score = 0

    # 1. Sector Matching (40% of rule-based score)
    app_sector = application.sector.lower() if application.sector else ""
    investor_sectors = [s.strip().lower() for s in getattr(investor, 'investment_focus', '').split(',') if s.strip()]

    if app_sector in investor_sectors:
        score += 40
    elif any(s in app_sector for s in investor_sectors if s):
        score += 25

    # 2. Stage Matching (60% of rule-based score)
    app_stage = application.stage.lower() if application.stage else ""
    inv_stage = investor.investment_stage.lower() if investor.investment_stage else ""

    if app_stage == inv_stage:
        score += 60
    elif _is_adjacent_stage(app_stage, inv_stage):
        score += 30

    # 3. Prior funding raised — having already convinced an outside investor
    # once is a mild, generic credibility signal regardless of sector/stage fit.
    if application.prior_amount_raised:
        score += 5

    # 4. Capital efficiency — rewards an ask that buys at least a year of
    # runway against disclosed burn. Silent (no bonus, no penalty) when burn
    # isn't disclosed, since most early founders won't have this yet and
    # "unknown" shouldn't read as a strike against them.
    burn = application.monthly_burn_rate
    if burn and application.raising_amount:
        implied_runway_months = float(application.raising_amount) / float(burn)
        if implied_runway_months >= 12:
            score += 5

    return min(score, 100)

def _is_adjacent_stage(stage1, stage2):
    """Helper to determine if two stages are close enough to be relevant."""
    adjacents = {
        'pre-seed': ['seed'],
        'seed': ['pre-seed', 'series a'],
        'series a': ['seed', 'series b'],
        'series b': ['series a', 'series c']
    }
    return stage2 in adjacents.get(stage1, [])


# 'Series A' / 'series-A' / 'Series_A' are the same stage typed three ways,
# and both sides of the comparison are free text, so the raw .lower() the
# hard filter used to do excluded pairs that plainly agree. Folded to the
# spelling _is_adjacent_stage's table already uses.
_STAGE_ALIASES = {'pre seed': 'pre-seed', 'preseed': 'pre-seed'}


def _normalize_stage(value):
    """
    Canonical form of a free-text stage label, for comparison only. Never
    persisted — this exists so a hyphen can't cost a founder an entire
    investor's deal flow.
    """
    if not value:
        return ''
    collapsed = re.sub(r'[\s_\-]+', ' ', value.strip().lower())
    return _STAGE_ALIASES.get(collapsed, collapsed)

def passes_hard_filters(application, investor):
    """
    Hard-constraint gate — the actual fix for the "high semantic score on a
    legally/logistically nonviable deal" false-positive problem. Unlike
    calculate_rule_based_score (a SOFT bonus that still lets a mismatch
    through with partial credit), a failure here excludes the founder from
    that investor's results entirely — they're never scored, never shown.

    Every check fails OPEN when the investor hasn't declared that
    constraint, so this can only ever narrow an investor's own existing
    results — it never retroactively hides matches for investors who never
    set these fields.

    Result is cached: the key is built directly from every field this
    function reads, so a changed profile automatically produces a
    different (uncached) key — there's no separate invalidation logic to
    write or get wrong. ticket_size_max is deliberately absent below
    because the computation no longer reads it; see _compute_hard_filters.
    """
    key_material = (
        f"v2:{investor.id}:{investor.ticket_size_min}:"
        f"{investor.investment_stage}:{application.id}:{application.raising_amount}:{application.stage}"
    )
    cache_key = f"hard_filter:{hashlib.sha256(key_material.encode('utf-8')).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = _compute_hard_filters(application, investor)
    cache.set(cache_key, result, HARD_FILTER_CACHE_TTL)
    return result


def _compute_hard_filters(application, investor):
    """
    Only genuinely nonviable pairings are excluded here. Anything that is
    merely a poor fit belongs in ranking, where the investor can still see
    it and judge for themselves.

    On cheque size: ticket_size_min/max describe the cheque this investor
    writes into a round; raising_amount is the size of the whole round.
    They are different quantities, and comparing them directly excluded
    every well-capitalised founder from every realistically-sized cheque
    writer — a $250k–$1.5M investor is an ordinary participant in a $4M
    seed round, not a mismatch for it. The one combination that cannot
    work is an investor whose SMALLEST cheque exceeds the entire round,
    since there is no way to deploy it; that is all we exclude on. A
    cheque smaller than the round is just syndication.

    On an undeclared raise: raising_amount is a non-null DecimalField
    defaulting to 0, so 0 overwhelmingly means "hasn't said yet" rather
    than "raising nothing" — and the founders who haven't said yet are
    exactly the new ones a cold marketplace can least afford to hide.
    Skipped rather than failed, on the same principle that keeps
    calculate_rule_based_score silent about an undisclosed burn rate:
    absent data must not read as a strike against the founder.
    """
    raising_amount = application.raising_amount
    if investor.ticket_size_min is not None and raising_amount:
        if investor.ticket_size_min > raising_amount:
            return False

    # Adjacency is checked in both directions: the table is one-way (it
    # lists 'series c' as a neighbour of 'series b' but has no 'series c'
    # key of its own), and a one-way read of it silently excluded the
    # later-stage half of every such pair.
    if investor.investment_stage:
        app_stage = _normalize_stage(application.stage)
        inv_stage = _normalize_stage(investor.investment_stage)
        if app_stage != inv_stage \
                and not _is_adjacent_stage(app_stage, inv_stage) \
                and not _is_adjacent_stage(inv_stage, app_stage):
            return False

    return True

def get_weighted_chunk_score(application, investor):
    """
    Multi-vector chunked, asymmetrically-weighted alternative to comparing
    description_vector/focus_vector as monolithic blocks. Compares each
    founder chunk against the investor chunk it's conceptually paired with,
    weights each pair by the investor's own declared emphasis, and
    normalizes by the weight actually used (so a founder/investor pair
    missing one chunk isn't penalized — it's just excluded from the average,
    not treated as a zero).

    Returns None (not 0.0) when neither side has any chunk vectors yet, so
    callers can fall back to the whole-profile ai_score instead of scoring
    a match on data that doesn't exist.
    """
    from matchmaking.services.ai_engine import calculate_similarity

    pairs = [
        (application.problem_solution_vector, investor.thesis_vector, investor.weight_problem_solution),
        (application.market_context_vector, investor.focus_vector, investor.weight_market_context),
        (application.capital_plan_vector, investor.thesis_vector, investor.weight_capital_plan),
    ]

    weighted_total = 0.0
    weight_used = 0.0
    for founder_vector, investor_vector, weight in pairs:
        if not founder_vector or not investor_vector:
            continue
        similarity = calculate_similarity(founder_vector, investor_vector)
        weighted_total += similarity * weight
        weight_used += weight

    if weight_used == 0:
        return None

    return max(0.0, min(100.0, (weighted_total / weight_used) * 100))

def get_blended_match(ai_score, rule_score, application, investor, sparse_score=None):
    """
    Enhanced blended match that incorporates historical thumbs up/down feedback.

    sparse_score is optional and defaults to None so every existing caller
    keeps its exact prior behavior (70% rule / 30% ai) unchanged. Passing a
    sparse_score (0-100, from calculate_sparse_similarity) switches to the
    3-way hybrid blend: 50% rule / 25% dense ai / 25% sparse keyword-overlap.

    ai_score itself is transparently upgraded to the weighted multi-vector
    chunk score (get_weighted_chunk_score) whenever both sides have chunk
    vectors — no caller changes needed. Falls back to the passed-in
    whole-profile ai_score when chunks aren't available yet (e.g. a profile
    that hasn't been touched/re-saved since the chunking rollout).
    """
    chunk_score = get_weighted_chunk_score(application, investor)
    if chunk_score is not None:
        ai_score = chunk_score

    if sparse_score is not None:
        base_score = (rule_score * 0.5) + (ai_score * 0.25) + (sparse_score * 0.25)
    else:
        base_score = (rule_score * 0.7) + (ai_score * 0.3)

    from matchmaking.models import MatchFeedback
    feedback = MatchFeedback.objects.filter(application=application, investor=investor).first()

    if feedback:
        if feedback.vote == 1:
            return min(base_score + 15, 100)
        if feedback.vote == -1:
            return base_score * 0.5

    return round(base_score, 2)


def calculate_deal_rule_based_score(seller, buyer):
    """
    Calculates a compatibility score (0-100) for the M&A marketplace based
    on deal economics — industry, whether the seller's asking price fits
    the buyer's acquisition budget, and deal-structure preference. Mirrors
    calculate_rule_based_score's shape, but scored on deal terms rather than
    sector/stage since fundraising and M&A criteria aren't the same thing.
    """
    score = 0

    # 1. Industry Matching (40% of rule-based score)
    seller_industry = seller.industry.lower() if seller.industry else ""
    thesis_text = (buyer.acquisition_thesis or "").lower()

    if seller_industry and seller_industry in thesis_text:
        score += 40
    elif seller_industry and any(word in thesis_text for word in seller_industry.split() if len(word) > 2):
        score += 25

    # 2. Deal Size Fit (35% of rule-based score) — does asking_price fall
    # within the buyer's acquisition budget range?
    asking_price = seller.asking_price
    budget_min = buyer.budget_min
    budget_max = buyer.budget_max

    if asking_price is not None and budget_min is not None and budget_max is not None:
        if budget_min <= asking_price <= budget_max:
            score += 35
        else:
            # Partial credit if within 20% of the nearest bound
            nearest_bound = budget_min if asking_price < budget_min else budget_max
            if nearest_bound > 0 and abs(asking_price - nearest_bound) / nearest_bound <= 0.2:
                score += 15

    # 3. Deal Structure Match (25% of rule-based score)
    seller_structure = seller.deal_structure
    buyer_preference = buyer.preferred_deal_structure

    if buyer_preference == 'NO_PREFERENCE':
        score += 25
    elif seller_structure == buyer_preference:
        score += 25
    elif seller_structure == 'OPEN':
        score += 15

    return score


def get_deal_blended_match(ai_score, rule_score, seller, buyer):
    """
    Blended AI + rule score for the M&A marketplace, incorporating
    DealFeedback thumbs up/down. Identical shape to get_blended_match.
    """
    base_score = (rule_score * 0.7) + (ai_score * 0.3)

    from matchmaking.models import DealFeedback
    feedback = DealFeedback.objects.filter(seller=seller, buyer=buyer).first()

    if feedback:
        if feedback.vote == 1:
            return min(base_score + 15, 100)
        if feedback.vote == -1:
            return base_score * 0.5

    return round(base_score, 2)


def get_uncontacted_high_matches(investor_profile, threshold=80):
    """
    Counts founders scoring >= threshold on the exact blended-match formula
    investor_dashboard uses, excluding founders this investor already has a
    Connection with. Skips lazy vector generation (unlike investor_dashboard)
    since this runs on every journey-status poll — founders without a vector
    yet just fall back to the same ai_score=50 default the dashboard uses.
    """
    from matchmaking.models import Application, Connection
    from matchmaking.services.ai_engine import calculate_similarity

    requested_ids = set(
        Connection.objects.filter(investor=investor_profile).values_list('founder_id', flat=True)
    )

    founders = Application.objects.discoverable().exclude(review_status='DENIED').exclude(id__in=requested_ids)

    count = 0
    for founder in founders:
        if investor_profile.focus_vector and founder.description_vector:
            try:
                ai_score = max(0.0, min(100.0, calculate_similarity(investor_profile.focus_vector, founder.description_vector) * 100))
            except Exception:
                ai_score = 50.0
        else:
            ai_score = 50.0

        rule_score = calculate_rule_based_score(application=founder, investor=investor_profile)
        final_score = get_blended_match(ai_score, rule_score, application=founder, investor=investor_profile)

        if final_score >= threshold:
            count += 1

    return count


def compute_founder_journey_stage(user):
    """
    Computes the founder's onboarding/engagement stage for the guided Zelda
    icon: red (no profile) -> yellow (profile, no pitch asset) -> green
    (has a pitch asset, then rotates ongoing engagement nudges).
    """
    application = getattr(user, 'match_founder_profile', None)

    if not application:
        return {
            'stage_color': 'red',
            'headline': "Let's build your founder profile — investors can't find you yet.",
            'checklist': [
                {'label': 'Create your founder profile', 'done': False},
            ],
        }

    has_pitch_asset = bool(application.pitch_deck) or bool(application.pitch_video)

    if not has_pitch_asset:
        return {
            'stage_color': 'yellow',
            'headline': 'Make your profile stand out — submit a pitch deck or pitch video.',
            'checklist': [
                {'label': 'Create your founder profile', 'done': True},
                {'label': 'Upload a pitch deck or pitch video', 'done': False},
            ],
        }

    from matchmaking.models import Follow

    has_blog = user.articles.exists()
    has_job = user.job_listings.exists()
    has_follow = Follow.objects.filter(follower=user).exists()
    has_zelda_doc = user.zelda_documents.exists()

    return {
        'stage_color': 'green',
        'headline': "Your profile is complete — an investor will reach out if your business matches their focus.",
        'checklist': [
            {'label': 'Create your founder profile', 'done': True},
            {'label': 'Upload a pitch deck or pitch video', 'done': True},
            {'label': 'Publish a blog post to boost visibility', 'done': has_blog},
            {'label': 'Post a job to show you\'re growing', 'done': has_job},
            {'label': 'Connect with other businesses', 'done': has_follow},
            {'label': 'Upload your business plan to Zelda for a competitiveness match', 'done': has_zelda_doc},
            {'label': 'Verify your business email', 'done': application.is_verified},
        ],
    }


def compute_investor_journey_stage(user):
    """
    Computes the investor's onboarding/engagement stage for the guided Zelda
    icon: red (no profile) -> yellow (incomplete mandate) -> green (complete,
    then surfaces uncontacted high-confidence matches as an ongoing nudge).
    """
    investor_profile = getattr(user, 'match_investor_profile', None)

    if not investor_profile:
        return {
            'stage_color': 'red',
            'headline': "Let's build your investor mandate — set your focus so Zelda can start matching founders.",
            'checklist': [
                {'label': 'Create your investor profile', 'done': False},
            ],
        }

    if investor_profile.completion_percentage < 100:
        return {
            'stage_color': 'yellow',
            'headline': 'Finish your investment mandate so Zelda can match you accurately.',
            'checklist': [
                {'label': 'Create your investor profile', 'done': True},
                {'label': 'Complete every mandate field', 'done': False},
            ],
        }

    has_portfolio = bool(investor_profile.portfolio_raw_text)
    uncontacted_count = get_uncontacted_high_matches(investor_profile)

    if uncontacted_count > 0:
        headline = f"You have {uncontacted_count} strong match{'es' if uncontacted_count != 1 else ''} you haven't reached out to yet."
    else:
        headline = "Your mandate is set — Zelda will notify you as new high-confidence matches appear."

    return {
        'stage_color': 'green',
        'headline': headline,
        'checklist': [
            {'label': 'Create your investor profile', 'done': True},
            {'label': 'Complete every mandate field', 'done': True},
            {'label': 'Upload your portfolio for a similarity match', 'done': has_portfolio},
            {'label': 'Verify your business email', 'done': investor_profile.is_verified},
        ],
        'uncontacted_high_matches': uncontacted_count,
    }


def get_uncontacted_high_deal_matches(buyer_profile, threshold=80):
    """
    Business Marketplace equivalent of get_uncontacted_high_matches — counts
    seller listings scoring >= threshold on the exact blended deal-economics
    formula buyer_dashboard uses, excluding listings this buyer already has
    an AcquisitionConnection with.
    """
    from matchmaking.models import SellerApplication, AcquisitionConnection
    from matchmaking.services.ai_engine import calculate_similarity

    requested_ids = set(
        AcquisitionConnection.objects.filter(buyer=buyer_profile).values_list('seller_id', flat=True)
    )

    sellers = SellerApplication.objects.discoverable().exclude(review_status='DENIED').exclude(id__in=requested_ids)

    count = 0
    for seller in sellers:
        if buyer_profile.focus_vector and seller.description_vector:
            try:
                ai_score = max(0.0, min(100.0, calculate_similarity(buyer_profile.focus_vector, seller.description_vector) * 100))
            except Exception:
                ai_score = 50.0
        else:
            ai_score = 50.0

        rule_score = calculate_deal_rule_based_score(seller=seller, buyer=buyer_profile)
        final_score = get_deal_blended_match(ai_score, rule_score, seller=seller, buyer=buyer_profile)

        if final_score >= threshold:
            count += 1

    return count


def compute_seller_journey_stage(user):
    """
    Computes the seller's onboarding/engagement stage for the guided Zelda
    icon: red (no listing) -> yellow (listing, no CIM) -> green (has a CIM,
    then rotates ongoing engagement nudges). Mirrors compute_founder_journey_stage.
    """
    seller_profile = getattr(user, 'match_seller_profile', None)

    if not seller_profile:
        return {
            'stage_color': 'red',
            'headline': "Let's list your business — acquirers can't find it yet.",
            'checklist': [
                {'label': 'Create your business listing', 'done': False},
            ],
        }

    has_cim = bool(seller_profile.cim_document)

    if not has_cim:
        return {
            'stage_color': 'yellow',
            'headline': 'Make your listing stand out — upload a Confidential Information Memorandum (CIM).',
            'checklist': [
                {'label': 'Create your business listing', 'done': True},
                {'label': 'Upload a CIM document', 'done': False},
            ],
        }

    from matchmaking.models import Follow

    has_follow = Follow.objects.filter(follower=user).exists()
    has_zelda_doc = user.zelda_documents.exists()

    return {
        'stage_color': 'green',
        'headline': "Your listing is complete — an acquirer will reach out if your business matches their mandate.",
        'checklist': [
            {'label': 'Create your business listing', 'done': True},
            {'label': 'Upload a CIM document', 'done': True},
            {'label': 'Get a Zelda valuation to price your asking price with confidence', 'done': has_zelda_doc},
            {'label': 'Connect with other businesses', 'done': has_follow},
            {'label': 'Verify your business email', 'done': seller_profile.is_verified},
        ],
    }


def compute_buyer_journey_stage(user):
    """
    Computes the buyer's onboarding/engagement stage for the guided Zelda
    icon: red (no profile) -> yellow (incomplete mandate) -> green (complete,
    then surfaces uncontacted high-confidence matches). Mirrors
    compute_investor_journey_stage.
    """
    buyer_profile = getattr(user, 'match_buyer_profile', None)

    if not buyer_profile:
        return {
            'stage_color': 'red',
            'headline': "Let's build your acquisition mandate — set your thesis so Zelda can start matching businesses.",
            'checklist': [
                {'label': 'Create your buyer profile', 'done': False},
            ],
        }

    if buyer_profile.completion_percentage < 100:
        return {
            'stage_color': 'yellow',
            'headline': 'Finish your acquisition mandate so Zelda can match you accurately.',
            'checklist': [
                {'label': 'Create your buyer profile', 'done': True},
                {'label': 'Complete every mandate field', 'done': False},
            ],
        }

    uncontacted_count = get_uncontacted_high_deal_matches(buyer_profile)

    if uncontacted_count > 0:
        headline = f"You have {uncontacted_count} strong match{'es' if uncontacted_count != 1 else ''} you haven't reached out to yet."
    else:
        headline = "Your mandate is set — Zelda will notify you as new high-confidence matches appear."

    return {
        'stage_color': 'green',
        'headline': headline,
        'checklist': [
            {'label': 'Create your buyer profile', 'done': True},
            {'label': 'Complete every mandate field', 'done': True},
            {'label': 'Verify your business email', 'done': buyer_profile.is_verified},
        ],
        'uncontacted_high_matches': uncontacted_count,
    }


def clean_financial_input(raw_value):
    if not raw_value:
        return 0
    
    # Cast to string to handle potential Decimal objects or existing clean integers
    raw_str = str(raw_value)
    
    # Handle ranges
    if '-' in raw_str:
        raw_str = raw_str.split('-')[0]
        
    # Remove everything except digits
    clean_str = re.sub(r'[^\d]', '', raw_str)
    
    try:
        return int(clean_str)
    except ValueError:
        return 0