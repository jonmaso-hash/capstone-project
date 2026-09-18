"""
Staff sessions end when they go idle.

Staff can impersonate users (ops/impersonation.py) and override deal states
(ops/views.py), so an unattended staff session is worth more to someone who
finds it than an ordinary one. Django's default session lasts two weeks with
no idle rule at all.

This applies to staff only. Members keep the ordinary session lifetime: they
have no such powers, and signing them out mid-task would cost real work.

The stamp lives in the session rather than on the user, so it costs no query
and dies with the session.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.utils import timezone

LAST_SEEN_KEY = 'staff_last_seen'
DEFAULT_IDLE_TIMEOUT = 3600  # an hour


class StaffSessionTimeoutMiddleware:
    """Sign a staff session out once it has been idle past the timeout."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and user.is_staff:
            timeout = timedelta(
                seconds=getattr(settings, 'STAFF_SESSION_IDLE_TIMEOUT', DEFAULT_IDLE_TIMEOUT)
            )
            now = timezone.now()
            last_seen = self._last_seen(request.session)
            if last_seen is not None and now - last_seen > timeout:
                logout(request)
                messages.info(request, "You were signed out after a period of inactivity.")
                return self.get_response(request)
            request.session[LAST_SEEN_KEY] = now.isoformat()
        return self.get_response(request)

    @staticmethod
    def _last_seen(session):
        stamp = session.get(LAST_SEEN_KEY)
        if not stamp:
            return None
        try:
            parsed = timezone.datetime.fromisoformat(stamp)
        except (TypeError, ValueError):
            # An unreadable stamp shouldn't lock anyone out; treat it as fresh
            # and let the line below rewrite it.
            return None
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
