import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

User = get_user_model()

# Maps a BulkEmailLog.audience value to the profile-relation lookup used to
# filter User — 'ALL' needs no filter.
AUDIENCE_FILTERS = {
    'FOUNDER': 'match_founder_profile__isnull',
    'INVESTOR': 'match_investor_profile__isnull',
    'SELLER': 'match_seller_profile__isnull',
    'BUYER': 'match_buyer_profile__isnull',
}


@shared_task(bind=True, max_retries=3)
def send_bulk_announcement(self, log_id):
    """
    Sends a staff-composed announcement email to a user segment — mirrors
    matchmaking.tasks.send_weekly_digests' shape (bind=True/max_retries
    wrapper + a _body() function, per-recipient try/except so one bad
    address never drops the rest of the batch).
    """
    try:
        return _send_bulk_announcement_body(log_id)
    except Exception as exc:
        logger.error(f"send_bulk_announcement failed: {str(exc)}")
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            self.retry(exc=exc, countdown=2 ** retry_count)
        else:
            logger.error(f"send_bulk_announcement exhausted {self.max_retries} retries: {str(exc)}")
            return {'status': 'error', 'error': str(exc), 'retries_exhausted': True}


def _send_bulk_announcement_body(log_id):
    from .models import BulkEmailLog
    from notifications.models import Notification

    log = BulkEmailLog.objects.get(id=log_id)

    recipients = User.objects.filter(is_active=True).exclude(email='')
    filter_kwarg = AUDIENCE_FILTERS.get(log.audience)
    if filter_kwarg:
        recipients = recipients.filter(**{filter_kwarg: False})

    sent_count = 0
    for user in recipients:
        try:
            send_mail(
                subject=log.subject,
                message=log.body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@interlinkfoundry.com'),
                recipient_list=[user.email],
                fail_silently=True,
            )
            Notification.objects.create(
                recipient=user,
                notification_type='ANNOUNCEMENT',
                message=log.subject,
            )
            sent_count += 1
        except Exception as e:
            logger.warning(f"Failed to send bulk announcement to {user.username}: {str(e)}")

    log.recipient_count = sent_count
    log.save(update_fields=['recipient_count'])

    return {'status': 'success', 'sent_count': sent_count}
