# matchmaking/match_cache.py
"""
Keeps AIMatch fresh on change events (profile edits, milestones) rather
than recomputing on read — the weekly digest and any other consumer just
reads the cached row. Mirrors the event-driven shape send_priority_match_alerts
already uses (compute on new/changed profiles, not on a schedule), just
persisted instead of transient.

Only two kinds of events move the needle right now: a vector changing
(investor thesis or founder description edited) and a founder milestone
(no score change, but worth surfacing as a reason to look again). Deck
uploads / Zelda re-analysis could feed this later if it proves valuable —
not built yet since there's no evidence it's needed.
"""
from django.utils import timezone

from .services.ai_engine import calculate_similarity

# Below this, a recomputed score isn't meaningfully different — avoids
# bumping last_changed_at on floating-point noise between runs.
SCORE_CHANGE_EPSILON = 1.0


def upsert_match(investor_profile, application, change_reason):
    """Recompute and cache one investor<->founder pair's score."""
    from .models import AIMatch

    if not investor_profile.focus_vector or not application.description_vector:
        return None

    score = round(max(0.0, min(100.0, calculate_similarity(
        investor_profile.focus_vector, application.description_vector,
    ) * 100)), 3)
    now = timezone.now()

    existing = AIMatch.objects.filter(investor=investor_profile, application=application).first()
    if existing is None:
        return AIMatch.objects.create(
            investor=investor_profile, application=application,
            score=score, confidence_score=score,
            score_generated_at=now, last_changed_at=now, change_reason=change_reason,
        )

    score_moved = abs(float(existing.score) - score) >= SCORE_CHANGE_EPSILON
    existing.score = score
    existing.confidence_score = score
    existing.score_generated_at = now  # every recompute, regardless of whether the score moved
    if score_moved:
        existing.last_changed_at = now
        existing.change_reason = change_reason
    existing.save(update_fields=['score', 'confidence_score', 'score_generated_at', 'last_changed_at', 'change_reason'])
    return existing


def refresh_matches_for_founder(application, change_reason):
    """Recompute this founder's score against every eligible investor."""
    from .models import InvestorApplication

    if not application.description_vector:
        return
    investors = InvestorApplication.objects.discoverable().exclude(review_status='DENIED')
    for investor_profile in investors:
        upsert_match(investor_profile, application, change_reason)


def refresh_matches_for_investor(investor_profile, change_reason):
    """Recompute this investor's score against every eligible founder."""
    from .models import Application

    if not investor_profile.focus_vector:
        return
    applications = Application.objects.discoverable().exclude(review_status='DENIED')
    for application in applications:
        upsert_match(investor_profile, application, change_reason)


def mark_milestone_change(application, milestone_title):
    """
    A milestone doesn't move the score, but it's exactly the kind of "look
    again" signal the digest should surface — only touches pairs that
    already exist (a milestone alone doesn't establish a new match).
    """
    from .models import AIMatch

    AIMatch.objects.filter(application=application).update(
        last_changed_at=timezone.now(),
        change_reason=f"Founder completed a milestone: {milestone_title}",
    )
