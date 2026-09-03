import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import Application

logger = logging.getLogger(__name__)


@shared_task
def refresh_matches_for_founder_task(application_id, change_reason):
    """Async wrapper so a profile-save request never blocks on match recompute."""
    from .match_cache import refresh_matches_for_founder
    try:
        application = Application.objects.get(id=application_id)
    except Application.DoesNotExist:
        return
    refresh_matches_for_founder(application, change_reason)


@shared_task
def refresh_matches_for_investor_task(investor_id, change_reason):
    from .models import InvestorApplication
    from .match_cache import refresh_matches_for_investor
    try:
        investor_profile = InvestorApplication.objects.get(id=investor_id)
    except InvestorApplication.DoesNotExist:
        return
    refresh_matches_for_investor(investor_profile, change_reason)


@shared_task
def mark_milestone_change_task(application_id, milestone_title):
    from .match_cache import mark_milestone_change
    try:
        application = Application.objects.get(id=application_id)
    except Application.DoesNotExist:
        return
    mark_milestone_change(application, milestone_title)


@shared_task(bind=True, max_retries=3)
def send_weekly_digests(self):
    """
    Weekly summary for investors: new founders in their focus area, and new
    milestones from founders they follow. Fires an in-app Notification
    (always works) and best-effort emails it too (dev SMTP may not be
    configured, so email failures must never break the in-app notification).

    Per-investor notification/email failures are already isolated below
    (logged, not fatal) — the retry here is for something catastrophic
    failing the whole batch (e.g. a transient DB error), not per-investor
    noise.
    """
    try:
        return _send_weekly_digests_body()
    except Exception as exc:
        logger.error(f"send_weekly_digests failed: {str(exc)}")
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            self.retry(exc=exc, countdown=2 ** retry_count)
        else:
            logger.error(f"send_weekly_digests exhausted {self.max_retries} retries: {str(exc)}")
            from ops.models import log_failed_task
            log_failed_task('matchmaking.tasks.send_weekly_digests', [], str(exc))
            return {'status': 'error', 'error': str(exc), 'retries_exhausted': True}


def _send_tracked_digest_email(recipient_user, subject, message, destination):
    """
    Wraps the digest email with funnel tracking: records the 'sent'
    DigestEngagementEvent, then builds an HTML alternative carrying an
    invisible open-tracking pixel and a click-tracked link to the
    recipient's dashboard. The plain-text body stays exactly the message
    text, so clients that can't render HTML still get real content — see
    DigestEngagementEvent's docstring for how the token later gets picked
    up by digest_open_pixel/digest_click_redirect. Before this, the digest
    email had no link and no way to know if anyone ever opened it at all.
    """
    from django.core.mail import EmailMultiAlternatives
    from django.urls import reverse
    from .models import DigestEngagementEvent

    sent_event = DigestEngagementEvent.objects.create(recipient=recipient_user, event_type='sent')
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    pixel_url = f"{site_url}{reverse('matchmaking:digest_open_pixel', args=[sent_event.token])}"
    click_url = f"{site_url}{reverse('matchmaking:digest_click_redirect', args=[sent_event.token, destination])}"

    html_body = (
        f"<p>{message}</p>"
        f'<p><a href="{click_url}">View your best match &rarr;</a></p>'
        f'<img src="{pixel_url}" width="1" height="1" alt="" style="display:none;">'
    )

    email = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@interlinkfoundry.com'),
        to=[recipient_user.email],
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=True)


def _send_weekly_digests_body():
    """
    One hero match per side, read from the AIMatch cache — never
    recomputed here. Deliberately not a "Marketplace This Week" dump: a
    single best-match highlight per user, anonymized for free viewers
    (sector/stage/amount bucket, no identity) and full detail for
    Premium, with a freshness line when the cached match changed recently
    (see matchmaking/digest.py and matchmaking/match_cache.py).
    """
    from .models import InvestorApplication
    from .digest import build_investor_digest_card, build_founder_digest_card, investor_digest_message, founder_digest_message
    from notifications.models import Notification

    sent_count = 0

    for investor_profile in InvestorApplication.objects.discoverable().exclude(review_status='DENIED').select_related('user'):
        investor_user = investor_profile.user
        card = build_investor_digest_card(investor_profile)
        if card is None:
            continue  # nothing worth leading with this week
        message = investor_digest_message(card)

        try:
            Notification.objects.create(
                recipient=investor_user,
                notification_type='WEEKLY_DIGEST',
                message=message,
                target_url='/matchmaking/dashboard/investor/'
            )
            sent_count += 1
        except Exception as e:
            logger.warning(f"Failed to create weekly digest notification for {investor_user.username}: {str(e)}")

        try:
            if investor_user.email:
                _send_tracked_digest_email(
                    investor_user, "Your best match this week — Interlink Foundry", message, destination='investor',
                )
        except Exception as e:
            logger.warning(f"Failed to email weekly digest to {investor_user.username}: {str(e)}")

    for application in Application.objects.discoverable().exclude(review_status='DENIED').select_related('user'):
        founder_user = application.user
        card = build_founder_digest_card(application)
        if card is None:
            continue  # nothing worth leading with this week

        message = founder_digest_message(card)

        try:
            Notification.objects.create(
                recipient=founder_user,
                notification_type='WEEKLY_DIGEST',
                message=message,
                target_url='/matchmaking/dashboard/founder/'
            )
            sent_count += 1
        except Exception as e:
            logger.warning(f"Failed to create weekly digest notification for {founder_user.username}: {str(e)}")

        try:
            if founder_user.email:
                _send_tracked_digest_email(
                    founder_user, "An investor matched with you this week — Interlink Foundry", message, destination='founder',
                )
        except Exception as e:
            logger.warning(f"Failed to email weekly digest to {founder_user.username}: {str(e)}")

    return {'status': 'success', 'digests_sent': sent_count}


@shared_task(bind=True, max_retries=3)
def snapshot_investor_predictions(self):
    """
    Invisible shadow-prediction system (Feature F4). For each investor,
    reruns the exact scoring already used by investor_dashboard (AI similarity
    + rule-based score, blended) to guess their next investment, and stashes
    the top-5 ranked founders as an InvestorPredictionSnapshot. Never shown to
    users — graded later, once that investor actually funds someone, by
    grade_investor_prediction_snapshots (triggered from connection_action_view).

    Skips investors with an unresolved snapshot newer than 7 days so this
    doesn't spam duplicate rows between funding events.
    """
    try:
        return _snapshot_investor_predictions_body()
    except Exception as exc:
        logger.error(f"snapshot_investor_predictions failed: {str(exc)}")
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            self.retry(exc=exc, countdown=2 ** retry_count)
        else:
            logger.error(f"snapshot_investor_predictions exhausted {self.max_retries} retries: {str(exc)}")
            from ops.models import log_failed_task
            log_failed_task('matchmaking.tasks.snapshot_investor_predictions', [], str(exc))
            return {'status': 'error', 'error': str(exc), 'retries_exhausted': True}


def _snapshot_investor_predictions_body():
    from .models import InvestorApplication, Connection, InvestorPredictionSnapshot, InvestorInterestEvent
    from .utils import calculate_rule_based_score, get_blended_match
    from .services.ai_engine import calculate_similarity

    week_ago = timezone.now() - timedelta(days=7)
    snapshots_created = 0

    for investor_profile in InvestorApplication.objects.discoverable().exclude(review_status='DENIED'):
        recent_unresolved = InvestorPredictionSnapshot.objects.filter(
            investor=investor_profile, is_resolved=False, created_at__gte=week_ago
        ).exists()
        if recent_unresolved:
            continue

        requested_ids = set(
            Connection.objects.filter(investor=investor_profile).values_list('founder_id', flat=True)
        )
        founders = Application.objects.discoverable().exclude(review_status='DENIED').exclude(id__in=requested_ids)

        ranked = []
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
            ranked.append((founder, final_score))

        if not ranked:
            continue

        ranked.sort(key=lambda pair: pair[1], reverse=True)
        top5 = ranked[:5]
        predicted_founder, predicted_score = top5[0]

        from django.db.models import Count
        event_counts = {
            row['event_type']: row['count']
            for row in InvestorInterestEvent.objects.filter(investor=investor_profile.user)
                .values('event_type').annotate(count=Count('id'))
        }

        InvestorPredictionSnapshot.objects.create(
            investor=investor_profile,
            predicted_founder=predicted_founder,
            predicted_score=predicted_score,
            runner_up_founders=[
                {'founder_id': f.id, 'score': score} for f, score in top5[1:]
            ],
            snapshot_telemetry={
                'event_counts': event_counts,
                'has_portfolio': bool(investor_profile.portfolio_raw_text),
                'has_focus_vector': bool(investor_profile.focus_vector),
            },
        )
        snapshots_created += 1

    return {'status': 'success', 'snapshots_created': snapshots_created}


@shared_task
def grade_investor_prediction_snapshots(investor_id, actual_funded_founder_id):
    """
    Grades every unresolved shadow-prediction snapshot for this investor
    against the founder they actually just funded — comparable to a credit
    score's post-hoc grading against real repayment behavior. Triggered from
    connection_action_view when a deal is marked FUNDED.

    Weighted 0-100: sector (25), stage (20), geography (15), vector
    similarity (25), identity bonus (15, only if the exact founder predicted
    was the one funded). An exact match is floored at 90 (A band) even if a
    secondary field like geography is blank on the founder's profile —
    "predicted the right founder" should never be graded down by missing data.
    """
    from .models import InvestorApplication, InvestorPredictionSnapshot
    from .utils import _is_adjacent_stage
    from .services.ai_engine import calculate_similarity

    try:
        investor_profile = InvestorApplication.objects.get(id=investor_id)
        actual_founder = Application.objects.get(id=actual_funded_founder_id)
    except (InvestorApplication.DoesNotExist, Application.DoesNotExist):
        return {'status': 'error', 'message': 'Investor or founder not found'}

    snapshots = InvestorPredictionSnapshot.objects.filter(investor=investor_profile, is_resolved=False)
    graded_count = 0

    for snapshot in snapshots:
        predicted = snapshot.predicted_founder
        reasons = []

        is_exact_match = predicted.id == actual_founder.id
        identity_bonus = 15 if is_exact_match else 0
        if is_exact_match:
            reasons.append("predicted the exact founder funded")

        pred_sector = (predicted.sector or '').lower()
        actual_sector = (actual_founder.sector or '').lower()
        if pred_sector and pred_sector == actual_sector:
            sector_score = 25
            reasons.append(f"sector matched ({actual_founder.sector})")
        else:
            sector_score = 0

        pred_stage = (predicted.stage or '').lower()
        actual_stage = (actual_founder.stage or '').lower()
        if pred_stage and pred_stage == actual_stage:
            stage_score = 20
            reasons.append(f"stage matched ({actual_founder.stage})")
        elif _is_adjacent_stage(pred_stage, actual_stage):
            stage_score = 10
            reasons.append(f"stage was adjacent (predicted {predicted.stage}, funded {actual_founder.stage})")
        else:
            stage_score = 0

        pred_geo = (predicted.geography or '').lower().strip()
        actual_geo = (actual_founder.geography or '').lower().strip()
        if pred_geo and actual_geo and (pred_geo == actual_geo or pred_geo in actual_geo or actual_geo in pred_geo):
            geo_score = 15
            reasons.append(f"geography matched ({actual_founder.geography})")
        else:
            geo_score = 0

        if predicted.description_vector and actual_founder.description_vector:
            try:
                similarity = calculate_similarity(predicted.description_vector, actual_founder.description_vector)
                vector_score = round(max(0.0, min(1.0, similarity)) * 25, 1)
            except Exception:
                vector_score = 12.5
        else:
            vector_score = 12.5  # no vectors to compare — neutral midpoint, not a penalty

        total_score = identity_bonus + sector_score + stage_score + geo_score + vector_score
        if is_exact_match:
            # Guarantee the A band regardless of incidental gaps (e.g. blank
            # geography) — correctly predicting the founder is what matters.
            total_score = max(total_score, 90)

        if total_score >= 90:
            grade = 'A'
        elif total_score >= 80:
            grade = 'B'
        elif total_score >= 65:
            grade = 'C'
        elif total_score >= 50:
            grade = 'D'
        else:
            grade = 'F'

        if not reasons:
            reasons.append(f"predicted {predicted.company_name}, but actual funded founder shared no tracked signals")

        explanation = (
            f"Predicted {predicted.company_name} ({round(snapshot.predicted_score, 1)}% blended score); "
            f"investor actually funded {actual_founder.company_name}. "
            + "; ".join(reasons) + "."
        )

        snapshot.is_resolved = True
        snapshot.resolved_at = timezone.now()
        snapshot.actual_funded_founder = actual_founder
        snapshot.grade = grade
        snapshot.grade_score = round(total_score, 1)
        snapshot.grade_explanation = explanation
        snapshot.save(update_fields=[
            'is_resolved', 'resolved_at', 'actual_funded_founder', 'grade', 'grade_score', 'grade_explanation'
        ])
        graded_count += 1

    return {'status': 'success', 'graded_count': graded_count}


@shared_task(bind=True, max_retries=3)
def snapshot_buyer_predictions(self):
    """
    Business Marketplace equivalent of snapshot_investor_predictions (Feature
    F4 extension). For each buyer, reruns the exact scoring already used by
    buyer_dashboard (AI similarity + deal-economics rule score, blended) to
    guess their next acquisition, and stashes the top-5 ranked sellers as a
    BuyerPredictionSnapshot. Never shown to users — graded later, once that
    buyer actually closes a deal, by grade_buyer_prediction_snapshots
    (triggered from acquisition_connection_action_view).

    Skips buyers with an unresolved snapshot newer than 7 days so this
    doesn't spam duplicate rows between closed deals.
    """
    try:
        return _snapshot_buyer_predictions_body()
    except Exception as exc:
        logger.error(f"snapshot_buyer_predictions failed: {str(exc)}")
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            self.retry(exc=exc, countdown=2 ** retry_count)
        else:
            logger.error(f"snapshot_buyer_predictions exhausted {self.max_retries} retries: {str(exc)}")
            from ops.models import log_failed_task
            log_failed_task('matchmaking.tasks.snapshot_buyer_predictions', [], str(exc))
            return {'status': 'error', 'error': str(exc), 'retries_exhausted': True}


def _snapshot_buyer_predictions_body():
    from .models import SellerApplication, BuyerApplication, AcquisitionConnection, BuyerPredictionSnapshot, AcquisitionInterestEvent
    from .utils import calculate_deal_rule_based_score, get_deal_blended_match
    from .services.ai_engine import calculate_similarity

    week_ago = timezone.now() - timedelta(days=7)
    snapshots_created = 0

    for buyer_profile in BuyerApplication.objects.discoverable().exclude(review_status='DENIED'):
        recent_unresolved = BuyerPredictionSnapshot.objects.filter(
            buyer=buyer_profile, is_resolved=False, created_at__gte=week_ago
        ).exists()
        if recent_unresolved:
            continue

        requested_ids = set(
            AcquisitionConnection.objects.filter(buyer=buyer_profile).values_list('seller_id', flat=True)
        )
        sellers = SellerApplication.objects.discoverable().exclude(review_status='DENIED').exclude(id__in=requested_ids)

        ranked = []
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
            ranked.append((seller, final_score))

        if not ranked:
            continue

        ranked.sort(key=lambda pair: pair[1], reverse=True)
        top5 = ranked[:5]
        predicted_seller, predicted_score = top5[0]

        from django.db.models import Count
        event_counts = {
            row['event_type']: row['count']
            for row in AcquisitionInterestEvent.objects.filter(buyer=buyer_profile.user)
                .values('event_type').annotate(count=Count('id'))
        }

        BuyerPredictionSnapshot.objects.create(
            buyer=buyer_profile,
            predicted_seller=predicted_seller,
            predicted_score=predicted_score,
            runner_up_sellers=[
                {'seller_id': s.id, 'score': score} for s, score in top5[1:]
            ],
            snapshot_telemetry={
                'event_counts': event_counts,
                'has_focus_vector': bool(buyer_profile.focus_vector),
            },
        )
        snapshots_created += 1

    return {'status': 'success', 'snapshots_created': snapshots_created}


@shared_task
def grade_buyer_prediction_snapshots(buyer_id, actual_closed_seller_id):
    """
    Grades every unresolved shadow-prediction snapshot for this buyer
    against the seller listing they actually just closed on — mirrors
    grade_investor_prediction_snapshots. Triggered from
    acquisition_connection_action_view when a deal is marked CLOSED.

    Weighted 0-100: industry (25), deal-size fit (20), deal-structure match
    (15), vector similarity (25), identity bonus (15, only if the exact
    seller predicted was the one closed). An exact match is floored at 90
    (A band) even if a secondary field is blank — "predicted the right
    seller" should never be graded down by missing data.
    """
    from .models import BuyerApplication, SellerApplication, BuyerPredictionSnapshot
    from .services.ai_engine import calculate_similarity

    try:
        buyer_profile = BuyerApplication.objects.get(id=buyer_id)
        actual_seller = SellerApplication.objects.get(id=actual_closed_seller_id)
    except (BuyerApplication.DoesNotExist, SellerApplication.DoesNotExist):
        return {'status': 'error', 'message': 'Buyer or seller not found'}

    snapshots = BuyerPredictionSnapshot.objects.filter(buyer=buyer_profile, is_resolved=False)
    graded_count = 0

    for snapshot in snapshots:
        predicted = snapshot.predicted_seller
        reasons = []

        is_exact_match = predicted.id == actual_seller.id
        identity_bonus = 15 if is_exact_match else 0
        if is_exact_match:
            reasons.append("predicted the exact seller closed")

        pred_industry = (predicted.industry or '').lower()
        actual_industry = (actual_seller.industry or '').lower()
        if pred_industry and pred_industry == actual_industry:
            industry_score = 25
            reasons.append(f"industry matched ({actual_seller.industry})")
        else:
            industry_score = 0

        pred_price = predicted.asking_price
        actual_price = actual_seller.asking_price
        if pred_price is not None and actual_price is not None and actual_price > 0:
            price_diff_pct = abs(pred_price - actual_price) / actual_price
            if price_diff_pct <= 0.15:
                size_score = 20
                reasons.append("deal size closely matched")
            elif price_diff_pct <= 0.35:
                size_score = 10
                reasons.append("deal size was in the same range")
            else:
                size_score = 0
        else:
            size_score = 0

        pred_structure = predicted.deal_structure
        actual_structure = actual_seller.deal_structure
        if pred_structure and pred_structure == actual_structure:
            structure_score = 15
            reasons.append(f"deal structure matched ({actual_seller.get_deal_structure_display()})")
        else:
            structure_score = 0

        if predicted.description_vector and actual_seller.description_vector:
            try:
                similarity = calculate_similarity(predicted.description_vector, actual_seller.description_vector)
                vector_score = round(max(0.0, min(1.0, similarity)) * 25, 1)
            except Exception:
                vector_score = 12.5
        else:
            vector_score = 12.5  # no vectors to compare — neutral midpoint, not a penalty

        total_score = identity_bonus + industry_score + size_score + structure_score + vector_score
        if is_exact_match:
            # Guarantee the A band regardless of incidental gaps — correctly
            # predicting the seller is what matters.
            total_score = max(total_score, 90)

        if total_score >= 90:
            grade = 'A'
        elif total_score >= 80:
            grade = 'B'
        elif total_score >= 65:
            grade = 'C'
        elif total_score >= 50:
            grade = 'D'
        else:
            grade = 'F'

        if not reasons:
            reasons.append(f"predicted {predicted.company_name}, but the actual closed seller shared no tracked signals")

        explanation = (
            f"Predicted {predicted.company_name} ({round(snapshot.predicted_score, 1)}% blended score); "
            f"buyer actually closed on {actual_seller.company_name}. "
            + "; ".join(reasons) + "."
        )

        snapshot.is_resolved = True
        snapshot.resolved_at = timezone.now()
        snapshot.actual_closed_seller = actual_seller
        snapshot.grade = grade
        snapshot.grade_score = round(total_score, 1)
        snapshot.grade_explanation = explanation
        snapshot.save(update_fields=[
            'is_resolved', 'resolved_at', 'actual_closed_seller', 'grade', 'grade_score', 'grade_explanation'
        ])
        graded_count += 1

    return {'status': 'success', 'graded_count': graded_count}


MATCH_ALERT_THRESHOLD = 80.0


@shared_task(bind=True, max_retries=3)
def send_priority_match_alerts(self):
    """
    Priority Match Alerts — Founder/Investor/Seller/Buyer Premium perk.
    Scans counterpart profiles created in the last 24h and notifies premium
    users whose vector similarity against one clears MATCH_ALERT_THRESHOLD.
    Bounded to "new since yesterday" so a daily run never re-scans the whole
    network — mirrors send_weekly_digests' retry wrapper.
    """
    try:
        return _send_priority_match_alerts_body()
    except Exception as exc:
        logger.error(f"send_priority_match_alerts failed: {str(exc)}")
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            self.retry(exc=exc, countdown=2 ** retry_count)
        else:
            logger.error(f"send_priority_match_alerts exhausted {self.max_retries} retries: {str(exc)}")
            from ops.models import log_failed_task
            log_failed_task('matchmaking.tasks.send_priority_match_alerts', [], str(exc))
            return {'status': 'error', 'error': str(exc), 'retries_exhausted': True}


def _notify_priority_matches(premium_profiles, new_counterparts, vector_field_self, vector_field_other, target_url, label):
    """
    For each premium profile, checks its vector against every newly-created
    counterpart profile; fires one Notification per pair that clears
    MATCH_ALERT_THRESHOLD. `label` names the counterpart type in the message
    (e.g. "investor", "founder").
    """
    from notifications.models import Notification
    from .services.ai_engine import calculate_similarity

    alerts_sent = 0
    for profile in premium_profiles:
        self_vector = getattr(profile, vector_field_self, None)
        if not self_vector:
            continue
        for counterpart in new_counterparts:
            other_vector = getattr(counterpart, vector_field_other, None)
            if not other_vector:
                continue
            try:
                score = max(0.0, min(100.0, calculate_similarity(self_vector, other_vector) * 100))
            except Exception:
                continue
            if score < MATCH_ALERT_THRESHOLD:
                continue

            counterpart_name = getattr(counterpart, 'company_name', '') or getattr(counterpart, 'full_name', '') or 'a new match'
            Notification.objects.create(
                recipient=profile.user,
                notification_type='PRIORITY_MATCH',
                message=f"New high-fit {label} match: {counterpart_name} ({round(score)}% fit).",
                target_url=target_url,
            )
            alerts_sent += 1
    return alerts_sent


def _send_priority_match_alerts_body():
    from .models import Application, InvestorApplication, SellerApplication, BuyerApplication

    day_ago = timezone.now() - timedelta(hours=24)
    total_alerts = 0

    new_investors = list(InvestorApplication.objects.discoverable().filter(created_at__gte=day_ago).exclude(review_status='DENIED'))
    new_founders = list(Application.objects.discoverable().filter(created_at__gte=day_ago).exclude(review_status='DENIED'))
    new_buyers = list(BuyerApplication.objects.discoverable().filter(created_at__gte=day_ago).exclude(review_status='DENIED'))
    new_sellers = list(SellerApplication.objects.discoverable().filter(created_at__gte=day_ago).exclude(review_status='DENIED'))

    if new_investors:
        premium_founders = Application.objects.discoverable().filter(is_premium=True).exclude(review_status='DENIED')
        total_alerts += _notify_priority_matches(
            premium_founders, new_investors, 'description_vector', 'focus_vector',
            '/matchmaking/dashboard/founder/', 'investor',
        )

    if new_founders:
        premium_investors = InvestorApplication.objects.discoverable().filter(is_premium=True).exclude(review_status='DENIED')
        total_alerts += _notify_priority_matches(
            premium_investors, new_founders, 'focus_vector', 'description_vector',
            '/matchmaking/dashboard/investor/', 'founder',
        )

    if new_buyers:
        premium_sellers = SellerApplication.objects.discoverable().filter(is_premium=True).exclude(review_status='DENIED')
        total_alerts += _notify_priority_matches(
            premium_sellers, new_buyers, 'description_vector', 'focus_vector',
            '/matchmaking/dashboard/seller/', 'buyer',
        )

    if new_sellers:
        premium_buyers = BuyerApplication.objects.discoverable().filter(is_premium=True).exclude(review_status='DENIED')
        total_alerts += _notify_priority_matches(
            premium_buyers, new_sellers, 'focus_vector', 'description_vector',
            '/matchmaking/dashboard/buyer/', 'seller',
        )


@shared_task
def ensure_next_month_partition():
    """
    Creates next month's partition on PageEvent/MatchTrainingExample ahead
    of time (see migration 0050). Postgres-only — a no-op everywhere else.
    Safe to fail/skip: rows destined for a missing partition just land in
    the DEFAULT partition instead (see that migration's docstring), so this
    is a pure optimization, never a correctness dependency. No retry logic
    for that reason — unlike the other beat tasks here, a missed run has no
    user-visible failure mode to guard against.
    """
    from django.db import connection
    if connection.vendor != 'postgresql':
        return {'status': 'skipped', 'reason': 'not postgresql'}

    today = timezone.now().date()
    next_month_start = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    month_after_start = (next_month_start + timedelta(days=32)).replace(day=1)
    suffix = next_month_start.strftime('y%Ym%m')

    with connection.cursor() as cursor:
        for table in ('matchmaking_pageevent', 'matchmaking_matchtrainingexample'):
            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS {table}_{suffix} "
                f"PARTITION OF {table} FOR VALUES FROM (%s) TO (%s);",
                [next_month_start, month_after_start],
            )

    return {'status': 'success', 'partition_suffix': suffix}

    return {'status': 'success', 'alerts_sent': total_alerts}