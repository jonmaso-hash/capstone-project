"""Compose existing Zelda engines and outputs for an owned, paid evidence set."""
import json
import logging
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from .models import ZeldaOrder

logger = logging.getLogger(__name__)


def archive_ready_order(order):
    """Save report references when space allows; a paid report always stays in Library."""
    from matchmaking.data_room_quota import try_save_report
    from zelda_api.principal import Principal, ORIGIN_TASK
    if order.status != 'ready' or not order.paid_at:
        return
    for key in order.reports:
        try:
            sections = report_sections(order, key, Principal.for_user(order.user, ORIGIN_TASK, 'report archive sizing'))
            size = len(json.dumps(sections, ensure_ascii=False).encode('utf-8'))
            try_save_report(order.user, 'order', order.id, key, size)
        except Exception:
            logger.exception('Could not save paid report %s for order %s in Data Room', key, order.pk)


def notify(order):
    from notifications.models import Notification
    Notification.objects.get_or_create(
        recipient=order.user, notification_type='ZELDA_ANALYSIS_READY' if order.status == 'ready' else 'ZELDA_ANALYSIS_FAILED',
        target_url=reverse('billing:zelda_order', args=[order.id]), defaults={
            'message': ('Your purchased Zelda reports are ready and saved in Library.' if order.status == 'ready'
                        else 'Your purchased Zelda reports could not finish. Retry from Library without another payment.'),
        },
    )


def reconcile_order(order):
    if order.status != 'processing':
        return order
    documents = [doc for doc in (order.analysis_document, order.valuation_document) if doc]
    failed = any(doc.status == 'error' or doc.verification_state == doc.FAILED for doc in documents)
    if order.entity_report and order.entity_report.status == 'failed':
        failed = True
    ready = bool(documents or order.entity_report) and all(doc.status == 'analyzed' for doc in documents)
    if order.analysis_document and not hasattr(order.analysis_document, 'memo'):
        ready = False
    if order.valuation_document and not hasattr(order.valuation_document, 'valuation_report'):
        ready = False
    if 'entity' in order.reports and (not order.entity_report or order.entity_report.status != 'complete'):
        ready = False
    if failed or ready:
        state = 'failed' if failed else 'ready'
        changed = ZeldaOrder.objects.filter(pk=order.pk, status='processing').update(status=state, finished_at=timezone.now())
        order.refresh_from_db()
        if changed:
            notify(order)
            if state == 'ready':
                archive_ready_order(order)
    return order


def clone_source(order, kind):
    from zelda_api.vector_models import DocumentSource
    source = order.source_document
    return DocumentSource.objects.create(
        uploaded_by=order.user, filename=source.filename, source_entity=source.source_entity,
        document_type=kind, raw_text_full=source.raw_text_full, raw_text_preview=source.raw_text_preview,
        total_pages=source.total_pages, is_external_subject=source.is_external_subject,
        external_cik=source.external_cik, valuation_tier='full' if kind == 'business_valuation' else 'preview',
    )


def report_sections(order, key, principal):
    """Stored engine outputs, never a new prompt or another evidence verdict."""
    if key == 'intelligence_memo':
        from zelda_api.ic_memo import zelda_report_observations
        memo = order.analysis_document.memo
        observations = zelda_report_observations(memo, order.analysis_document)
        noticed = '\n'.join(f'• {point}' for point in observations['noticed'])
        investigating = '\n'.join(
            f"• {item['topic']}" for item in observations['worth_investigating']
        )
        return [
            {
                'title': 'Executive Summary',
                'text': memo.executive_summary or 'Insufficient disclosed evidence.',
            },
            {
                'title': 'What Zelda Noticed',
                'text': noticed or 'The available evidence does not support an additional observation.',
            },
            {
                'title': 'Worth Investigating',
                'text': investigating or 'No additional investigation topic was established from the available evidence.',
            },
            {
                'title': 'Information Readiness',
                'text': memo.information_readiness or 'Insufficient disclosed evidence.',
            },
        ]
    if key == 'ic_memo':
        from zelda_api.ic_memo import MEMO_SECTIONS
        memo = order.analysis_document.memo
        return [{'title': label, 'text': getattr(memo, field) or 'Insufficient disclosed evidence.'} for field, label in MEMO_SECTIONS]
    if key == 'valuation':
        report = order.valuation_document.valuation_report
        return [{'title': title, 'text': getattr(report, field) or 'Insufficient disclosed evidence.'} for field, title in (
            ('business_overview', 'Business Overview'), ('financial_summary', 'Financial Summary'),
            ('risk_report', 'Risk Report'), ('valuation_summary', 'Valuation and Assumptions'))]
    if key == 'entity':
        from zelda_api.entity_verification import display_rows
        return [{'title': row['check'].replace('_', ' ').title(), 'text':
                 f"{row.get('claim', '')}\n{row.get('evidence', '')}\nResult: {row['result_label']}\nSource: {row.get('source_url') or row.get('evidence_source', '')}"}
                for row in display_rows(order.entity_report)]
    from zelda_api.truth_delta_models import TruthDeltaReport, ClaimedDatapoint
    document = order.analysis_document
    report = TruthDeltaReport.objects.filter(document=document).order_by('-created_at', '-id').first()
    sections = [{'title': 'Evidence Summary', 'text': report.summary if report else
                 'No checkable claims were extracted from this evidence. This is not a finding about the company.'}]
    from zelda_api.grounded_context import GroundedContext
    # Reuse the canonical evidence-state presentation. No VERIFIED -> supported
    # translations or exception/absence conflation in the commerce layer.
    context = GroundedContext.build(principal, document)
    for item in context.items:
        if item.kind == 'claim':
            sections.append({'title': f'{item.category.replace("_", " ").title()} — {item.status}',
                             'text': item.statement + ('\n' + item.reason if item.reason else '') + '\n' +
                             '\n'.join(f'{value.source}: {value.value} ({value.role})' for value in item.external)})
    return sections
