"""
Whether Google Analytics may load on this request, decided server-side.

The tag is rendered into the page only when every condition holds, so "GA does
not load before consent" is a property of the HTML rather than a promise made by
JavaScript. Loading gtag and then telling it not to track is weaker: the request
to Google has already happened.

Four conditions, each for its own reason:

- a measurement ID is configured — a fresh checkout and CI stay silent
- not DEBUG — local development never writes into the production property
- the visitor has accepted — no analytics storage before a choice
- the page is public — GA covers the acquisition surface; what members do
  afterwards is the database's business, not Google's

The one exception is a completed signup, which fires its conversion event on the
next page even though the visitor is now signed in. Without it the funnel stops
one step short of the only event that matters, and the event itself carries no
identity — just the fact that a signup completed.
"""
from django.conf import settings

CONSENT_COOKIE = 'analytics_consent'
GRANTED = 'granted'
DENIED = 'denied'
CONSENT_MAX_AGE = 60 * 60 * 24 * 365  # a year, then ask again
PENDING_EVENTS_SESSION_KEY = 'ga_pending_events'


def measurement_id():
    return (getattr(settings, 'GA_MEASUREMENT_ID', '') or '').strip()


def is_configured():
    return bool(measurement_id()) and not settings.DEBUG


def consent_state(request):
    value = request.COOKIES.get(CONSENT_COOKIE)
    return value if value in (GRANTED, DENIED) else None


def analytics_context(request):
    """
    Template context. Also drains any one-shot events queued server-side, so a
    conversion recorded during a redirect still reaches the next rendered page.
    """
    if not is_configured():
        return {'analytics_enabled': False, 'show_consent_banner': False, 'ga_events': []}

    state = consent_state(request)
    session = getattr(request, 'session', None)
    pending = []
    if session is not None:
        pending = session.get(PENDING_EVENTS_SESSION_KEY) or []

    # Signed-in pages are not tracked; a queued conversion is the exception.
    signed_in = getattr(request, 'user', None) is not None and request.user.is_authenticated
    enabled = state == GRANTED and (not signed_in or bool(pending))

    if enabled and pending and session is not None:
        del session[PENDING_EVENTS_SESSION_KEY]
        session.modified = True

    return {
        'analytics_enabled': enabled,
        'ga_measurement_id': measurement_id(),
        'show_consent_banner': state is None,
        'ga_events': pending if enabled else [],
    }


def queue_event(request, name):
    """
    Record a conversion that happens during a redirect (signup completing, for
    instance) so the next rendered page can report it. Event names only — never
    identities, company names, or anything from a document.
    """
    session = getattr(request, 'session', None)
    if session is None or not is_configured():
        return
    events = session.get(PENDING_EVENTS_SESSION_KEY) or []
    if name not in events:
        events.append(name)
    session[PENDING_EVENTS_SESSION_KEY] = events
    session.modified = True
