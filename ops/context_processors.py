from django.db.models import Q
from django.utils import timezone

from .models import Announcement


def active_announcements(request):
    """Feeds the dismissible banner in base.html — active + within its
    optional start/end window, on every page."""
    now = timezone.now()
    announcements = Announcement.objects.filter(is_active=True).filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=now)
    ).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gte=now)
    )
    return {'active_announcements': announcements}
