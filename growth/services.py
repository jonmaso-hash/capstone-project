from django.utils import timezone

from .models import ReferralInvite


def consume_referral_if_pending(request, new_profile):
    """
    Called from the is_new_submission branch of each usersettings
    edit_{founder,investor,seller,buyer}_profile view — the one place all
    4 profile types actually get created. Marks the pending referral (if
    any, stashed in session by accounts.views.signup_view) ACCEPTED and
    grants the referrer's premium reward exactly once (reward_granted
    guards against a double-grant if this is ever called twice for the
    same invite).
    """
    code = request.session.pop('pending_referral_code', None)
    if not code:
        return

    try:
        invite = ReferralInvite.objects.get(code=code, status='PENDING')
    except ReferralInvite.DoesNotExist:
        return

    invite.status = 'ACCEPTED'
    invite.accepted_at = timezone.now()

    if not invite.reward_granted:
        # Reusing the exact premium-grant lever already used by the
        # Stripe-driven "Featured Placement" flow — no new premium
        # mechanism, just another caller of the same helper.
        from billing.views import _apply_premium_flag
        _apply_premium_flag(invite.inviter, True)
        invite.reward_granted = True

    invite.save(update_fields=['status', 'accepted_at', 'reward_granted'])
