import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import ZeldaOrder

logger = logging.getLogger(__name__)


@shared_task(soft_time_limit=90, time_limit=120)
def fulfill_zelda_order(order_id):
    from .fulfillment import clone_source, notify, reconcile_order
    from zelda_api.principal import Principal, ORIGIN_TASK
    from zelda_api.authorization import authorize
    from zelda_api.tasks import process_document_pipeline, process_valuation_document_task
    from zelda_api.entity_verification import build_document_identity_report
    order = None
    try:
        with transaction.atomic():
            order = ZeldaOrder.objects.select_for_update().select_related('user', 'source_document').get(pk=order_id)
            if order.status != 'paid' or not order.paid_at:
                return
            auth = authorize(Principal.for_user(order.user, ORIGIN_TASK, 'paid Zelda product'))
            if not auth.text_permitted(order.source_document):
                raise ValueError('Evidence access refused')
            if any(key in order.reports for key in ('ic_memo', 'truth_delta')) and not order.analysis_document_id:
                order.analysis_document = clone_source(order, 'pitch_deck')
            if 'valuation' in order.reports and not order.valuation_document_id:
                order.valuation_document = clone_source(order, 'business_valuation')
            order.status, order.finished_at = 'processing', None
            order.save()
        if 'entity' in order.reports:
            order.entity_report = build_document_identity_report(order.source_document)
            order.save(update_fields=['entity_report'])
        for doc, task in ((order.analysis_document, process_document_pipeline),
                          (order.valuation_document, process_valuation_document_task)):
            if doc and doc.status != 'analyzed':
                task.delay(doc.id, doc.raw_text_full)
        reconcile_order(order)
        if order.status == 'processing':
            monitor_zelda_order.delay(str(order.id))
    except Exception:
        logger.exception('Could not fulfill Zelda order %s', order_id)
        if order and order.paid_at:
            ZeldaOrder.objects.filter(pk=order.pk, status__in=['paid', 'processing']).update(status='failed', finished_at=timezone.now())
            order.refresh_from_db()
            notify(order)


@shared_task(bind=True, max_retries=60)
def monitor_zelda_order(self, order_id):
    from .fulfillment import reconcile_order, notify
    order = ZeldaOrder.objects.filter(pk=order_id).first()
    if not order:
        return
    reconcile_order(order)
    if order.status == 'processing':
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30)
        ZeldaOrder.objects.filter(pk=order.pk, status='processing').update(status='failed', finished_at=timezone.now())
        order.refresh_from_db()
        notify(order)
