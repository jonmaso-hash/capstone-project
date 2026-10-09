"""Optional, server-side product analytics. Never send company evidence or PII."""
import hashlib
import logging

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone
import requests

logger = logging.getLogger(__name__)
EVENT_PROPERTIES = {
    'signup_completed': {'role', 'method'},
    'zelda_reports_ready': {'product', 'reports'},
    'purchase_completed': {'product', 'amount_minor', 'currency', 'payment_kind'},
}


def track(event, user_id, key, *, occurred_at=None, **properties):
    """Queue only after commit; a queue outage never rolls back a user action.

    Keys name real business occurrences, not requests. Original timestamps and
    insert IDs survive worker retries so Mixpanel can deduplicate delivery.
    """
    if not settings.MIXPANEL_TOKEN or not user_id:
        return
    from ops.impersonation import is_impersonating
    if is_impersonating():
        return
    if event not in EVENT_PROPERTIES or set(properties) - EVENT_PROPERTIES[event]:
        raise ValueError('Unsupported analytics event or properties')
    namespace = settings.MIXPANEL_ID_NAMESPACE
    payload = {'event': event, 'properties': {
        **properties,
        'distinct_id': f'{namespace}:user:{user_id}',
        '$insert_id': hashlib.sha256(f'{namespace}:{event}:{key}'.encode()).hexdigest(),
        'time': int((occurred_at or timezone.now()).timestamp()),
        'environment': namespace,
        'source': 'server',
    }}

    def enqueue():
        try:
            # Broker publish retries are disabled: analytics must fail quickly.
            deliver_mixpanel_event.apply_async(args=[payload], retry=False)
        except Exception:
            logger.warning('Could not queue Mixpanel event %s', event)

    transaction.on_commit(enqueue)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def deliver_mixpanel_event(self, payload):
    if not settings.MIXPANEL_TOKEN:
        return
    # Drop queued development events if a worker has changed environments.
    if payload['properties']['environment'] != settings.MIXPANEL_ID_NAMESPACE:
        return
    properties = {**payload['properties'], 'token': settings.MIXPANEL_TOKEN}
    try:
        response = requests.post(
            settings.MIXPANEL_TRACK_URL, params={'verbose': 1, 'ip': 0},
            json=[{'event': payload['event'], 'properties': properties}], timeout=(2, 5),
        )
        response.raise_for_status()
        if response.json().get('status') != 1:
            raise ValueError('Mixpanel rejected analytics event')
    except (requests.RequestException, ValueError):
        # Never log the response, token, payload, or exception URL.
        raise self.retry()
