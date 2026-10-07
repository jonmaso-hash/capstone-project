from datetime import timedelta

from django.db.models import Q
from django.db.models.functions import Upper
from django.utils import timezone

from usersettings.models import UserSettings
from .models import Notification


def expired_notifications(user):
    # Looking at history must not create settings or acknowledge notifications.
    days = UserSettings.objects.filter(user=user).values_list(
        'notification_retention_days', flat=True,
    ).first() or 0
    ordinary = Notification.objects.filter(
        recipient=user, dismissed_at__isnull=True, is_read=True,
    ).annotate(kind=Upper('notification_type')).exclude(
        Q(kind__startswith='SECURITY') | Q(kind__startswith='AUDIT') |
        Q(kind__in=Notification.RETAINED_TYPES))
    if days == -1:
        return ordinary
    if days > 0:
        return ordinary.filter(created_at__lt=timezone.now() - timedelta(days=days))
    return ordinary.none()


def visible_notifications(user):
    return Notification.objects.filter(recipient=user, dismissed_at__isnull=True).exclude(
        id__in=expired_notifications(user).values('id'),
    )


def apply_retention(user):
    # Preserve records for audit/deduplication while removing them from history.
    return expired_notifications(user).update(dismissed_at=timezone.now())
