from datetime import timedelta

from django.urls import NoReverseMatch, reverse
from django.utils import timezone


def _safe_reverse(name, *args, **kwargs):
    try:
        return reverse(name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return None


def _action(label, why, action_label, action_url, estimated_minutes=2, source='workflow'):
    return {
        'label': label,
        'why_it_matters': why,
        'estimated_minutes': estimated_minutes,
        'action_label': action_label,
        'action_url': action_url,
        'source': source,
    }


def momentum_next_action(user):
    """Return one factual, workflow-oriented next action after setup is complete.

    This intentionally avoids counterparty ranking, investment recommendations,
    transaction predictions, or any inference about who is most likely to fund
    or acquire whom. It only reacts to observable user state and platform events.
    """
    from notifications.models import Notification
    from matchmaking.models import (
        FundraisingLead,
        FounderMilestone,
        InvestorShortlist,
    )

    # 1. Human activity that needs a response always wins.
    message = Notification.objects.filter(
        recipient=user,
        is_read=False,
        dismissed_at__isnull=True,
        notification_type='MESSAGE',
    ).order_by('-created_at').first()
    if message:
        return _action(
            'Reply to your new message',
            'A person in your Interlink network sent you a message. Keeping an active conversation moving is the most useful next step.',
            'Open message',
            message.target_url or _safe_reverse('notification-history'),
            2,
            'message',
        )

    relationship_notice = Notification.objects.filter(
        recipient=user,
        is_read=False,
        dismissed_at__isnull=True,
        notification_type__in=('INTRO_REQUEST', 'INTRO_ACCEPTED'),
    ).order_by('-created_at').first()
    if relationship_notice:
        return _action(
            'Review your relationship update',
            relationship_notice.message,
            'Review update',
            relationship_notice.target_url or _safe_reverse('notification-history'),
            2,
            'relationship',
        )

    report_notice = Notification.objects.filter(
        recipient=user,
        is_read=False,
        dismissed_at__isnull=True,
        notification_type__in=('ZELDA_ANALYSIS_READY', 'ANALYSIS_READY'),
    ).order_by('-created_at').first()
    if report_notice:
        return _action(
            'Review your completed Zelda report',
            'A Zelda report you requested is ready. Review the evidence, open questions, and limitations while the underlying materials are still fresh.',
            'Open report',
            report_notice.target_url,
            5,
            'report',
        )

    founder = getattr(user, 'match_founder_profile', None)
    seller = getattr(user, 'match_seller_profile', None)
    investor = getattr(user, 'match_investor_profile', None)
    buyer = getattr(user, 'match_buyer_profile', None)
    now = timezone.now()

    # 2. Keep relationship workflow organized.
    if founder is not None:
        visible_leads = FundraisingLead.objects.filter(founder=founder)
        if not visible_leads.exists():
            return _action(
                'Start your fundraising CRM',
                'Your setup is complete, but your relationship board is still empty. Add the investors you are actively tracking so follow-up does not live in your inbox or memory.',
                'Open Fundraising CRM',
                _safe_reverse('matchmaking:fundraising_crm'),
                5,
                'crm',
            )

        latest_milestone = FounderMilestone.objects.filter(founder=founder).order_by('-created_at').first()
        if latest_milestone is None or latest_milestone.created_at < now - timedelta(days=45):
            return _action(
                'Post a fresh company milestone',
                'Your network has not seen a recent company update. A factual milestone keeps your profile current without changing how Zelda ranks or recommends anything.',
                'Review milestones',
                _safe_reverse('matchmaking:founder_dashboard'),
                5,
                'milestone',
            )

        if getattr(founder, 'updated_at', None) and founder.updated_at < now - timedelta(days=30):
            return _action(
                'Review your pitch profile',
                'Your founder profile has not been updated in 30 days. Check whether your company, raise, traction, or materials have changed.',
                'Review profile',
                _safe_reverse('usersettings:edit_founder_profile'),
                5,
                'profile_freshness',
            )

        # Low-priority recurring allowance nudge. The centralized constant lets
        # pricing policy change without duplicating the number here.
        try:
            from matchmaking.views import FREE_CRM_LEAD_LIMIT
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            additions = FundraisingLead.objects.filter(founder=founder, created_at__gte=month_start).count()
            if not founder.is_premium and additions < FREE_CRM_LEAD_LIMIT:
                remaining = FREE_CRM_LEAD_LIMIT - additions
                return _action(
                    'Use your refreshed CRM allowance',
                    f'You can add {remaining} more new CRM lead{"s" if remaining != 1 else ""} this month. Existing leads stay in your board.',
                    'Add a CRM lead',
                    _safe_reverse('matchmaking:fundraising_crm'),
                    3,
                    'entitlement',
                )
        except Exception:
            pass

    if investor is not None and not InvestorShortlist.objects.filter(investor=investor).exists():
        return _action(
            'Build your shortlist',
            'You have completed setup but have not saved any companies for later review. A shortlist gives you a working set without treating any company as a recommendation.',
            'Open Investor Discovery',
            _safe_reverse('matchmaking:investor_dashboard'),
            5,
            'shortlist',
        )

    if seller is not None and getattr(seller, 'updated_at', None) and seller.updated_at < now - timedelta(days=30):
        return _action(
            'Review your seller profile',
            'Your business-for-sale profile has not been updated in 30 days. Check whether the operating details, materials, or transaction preferences have changed.',
            'Review profile',
            _safe_reverse('usersettings:edit_seller_profile'),
            5,
            'profile_freshness',
        )

    if buyer is not None:
        return _action(
            'Review your acquisition workspace',
            'Your core setup is complete. Review active conversations, saved businesses, and outstanding diligence tasks before starting something new.',
            'Open Buyer Dashboard',
            _safe_reverse('matchmaking:buyer_dashboard'),
            5,
            'workspace',
        )

    # 3. Neutral fallback: maintain the user's own information, not a prediction.
    return _action(
        'Keep your Interlink workspace current',
        'Your core setup is complete and there is nothing urgent waiting. Review your recent activity and update anything that has changed.',
        'Open my workspace',
        _safe_reverse('accounts:post_login_router'),
        5,
        'maintenance',
    )
