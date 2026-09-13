"""
A durable signal when a Zelda analysis reaches a terminal state.

The failure story was more precise than "Zelda failures are invisible". While
the user is *on* the report page, the valuation view polls DocumentStatusView
every three seconds and does show an error state. The gap is what happens after
they leave: nothing durable was ever written, so a user who closed the tab never
learned whether their analysis finished or failed. For a paid report that is the
part that matters.

`DocumentSource` already carries the terminal state (`analyzed` / `error`) and
its owner (`uploaded_by`), so this only has to turn state the system already
knows into a notification the user can come back to.

Deliberately narrow. No email, no webhooks, no staff alerting, and no retry
logic -- the pipeline tasks already retry with exponential backoff before they
mark a document `error`.
"""
import logging

from django.urls import NoReverseMatch, reverse

logger = logging.getLogger(__name__)

ANALYSIS_READY = 'ZELDA_ANALYSIS_READY'
ANALYSIS_FAILED = 'ZELDA_ANALYSIS_FAILED'

# What the user is told. Stable and human -- never str(exc), which is a raw
# exception string that means nothing to them and can expose internals. The
# exception is already logged and stored on DocumentSource.error_message for
# staff.
READY_MESSAGE = 'Your %s analysis is ready.'
FAILED_MESSAGE = (
    "We couldn't complete your %s analysis. Nothing was charged for a failed "
    "run — please try uploading it again."
)

# An investor who spent an analysis on a founder's deck (analyze_founder_profile's
# confirm step) is who asked for it, but the document stays owned by the founder,
# so uploaded_by is the wrong recipient -- the AnalysisCreditCharge names the
# person who paid. Their copy names the company, links to the founder's profile
# (the IC memo page needs an accepted connection), and says nothing about
# charging: an investor-triggered analysis is charged even when it fails.
PAYER_READY_MESSAGE = "Zelda's analysis of %s is ready."
PAYER_FAILED_MESSAGE = "Zelda couldn't complete the analysis of %s. Please try again later."

# Where the notification takes them, per document type.
REPORT_ROUTES = {
    'business_valuation': 'zelda_api:valuation_report',
}
DEFAULT_ROUTE = 'zelda_api:ic_memo'


def _owner_profile_url(document):
    try:
        return reverse('accounts:profile', kwargs={'username': document.uploaded_by.username})
    except NoReverseMatch:
        return None


def _report_url(document):
    """The page for this document, or None if it has no report route."""
    route = REPORT_ROUTES.get(document.document_type, DEFAULT_ROUTE)
    try:
        return reverse(route, args=[document.id])
    except NoReverseMatch:
        return None


def _document_label(document):
    """
    What to call the analysis in a sentence. Prefers the human document type
    over the filename, which is often an opaque upload name.
    """
    return (document.get_document_type_display() or 'document').lower()


def notify_terminal_state(document, succeeded):
    """
    Write one notification for this document's terminal state.

    Idempotent: post_save fires on every save of a DocumentSource, and a
    document can be saved again while still in a terminal state, so this keys
    on (recipient, type, target_url) and will not stack duplicates.

    Best effort. A notification failure must never take down the pipeline task
    or the signal that called it -- the analysis itself already succeeded or
    failed on its own terms.
    """
    try:
        from notifications.models import Notification

        charge = getattr(document, 'credit_charge', None)
        if charge is not None:
            recipient = charge.user
            company = (document.source_entity or document.uploaded_by.username)[:180]
            message = (PAYER_READY_MESSAGE if succeeded else PAYER_FAILED_MESSAGE) % company
            target_url = _owner_profile_url(document)
        else:
            recipient = document.uploaded_by
            if recipient is None:
                return None
            message = (READY_MESSAGE if succeeded else FAILED_MESSAGE) % _document_label(document)
            target_url = _report_url(document)

        Notification.objects.get_or_create(
            recipient=recipient,
            notification_type=ANALYSIS_READY if succeeded else ANALYSIS_FAILED,
            target_url=target_url,
            defaults={'message': message},
        )
    except Exception:
        logger.exception(
            'Could not write terminal notification for document %s', getattr(document, 'id', None))
        return None
