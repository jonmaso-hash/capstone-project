"""Data Room storage limits. Report purchases remain independent of this quota."""
import logging
from django.db import transaction
from django.db.models import Sum

from .models import Application, DataRoomDocument, DataRoomReportLink

logger = logging.getLogger(__name__)

MB = 1024 * 1024
FREE_LIMIT_BYTES = 500 * MB
PREMIUM_LIMIT_BYTES = 5 * 1024 * MB


def room_limit(founder):
    return PREMIUM_LIMIT_BYTES if founder.is_premium else FREE_LIMIT_BYTES


def room_usage(founder):
    """Count actual uploaded file sizes and serialized Zelda report sizes."""
    for document in DataRoomDocument.objects.filter(founder=founder, size_bytes__isnull=True):
        try:
            size = document.file.size
        except Exception:
            logger.warning('Could not measure Data Room file %s; blocking new saves until resolved', document.pk)
            return room_limit(founder)
        DataRoomDocument.objects.filter(pk=document.pk, size_bytes__isnull=True).update(size_bytes=size)
    file_bytes = DataRoomDocument.objects.filter(founder=founder).aggregate(total=Sum('size_bytes'))['total'] or 0
    report_bytes = DataRoomReportLink.objects.filter(founder=founder).aggregate(total=Sum('size_bytes'))['total'] or 0
    return file_bytes + report_bytes


def try_save_report(user, source_kind, source_id, report_key, size_bytes):
    """Idempotently archive a completed, owned report if the room has space."""
    from billing.models import ZeldaOrder
    from zelda_api.vector_models import DocumentSource

    with transaction.atomic():
        founder = Application.objects.select_for_update().filter(user=user).first()
        if not founder:
            return False
        source_id = str(source_id)
        if source_kind == 'order':
            order = ZeldaOrder.objects.filter(pk=source_id, user=user, status='ready', paid_at__isnull=False).first()
            valid = bool(order and report_key in order.reports)
        elif source_kind == 'document' and source_id.isdecimal():
            document = DocumentSource.objects.filter(pk=source_id, uploaded_by=user, is_product_input=False).first()
            valid = bool(document and not document.analysis_orders.exists() and not document.valuation_orders.exists()
                         and report_key in ('memo', 'truth_delta', 'valuation'))
        else:
            valid = False
        if not valid:
            return False
        if DataRoomReportLink.objects.filter(founder=founder, source_kind=source_kind,
                                             source_id=source_id, report_key=report_key).exists():
            return True
        size_bytes = max(1, int(size_bytes))
        if room_usage(founder) + size_bytes > room_limit(founder):
            return False
        DataRoomReportLink.objects.create(founder=founder, source_kind=source_kind,
                                          source_id=source_id, report_key=report_key, size_bytes=size_bytes)
        return True
