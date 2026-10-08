"""Grandfather existing Zelda reports into founders' private Data Rooms."""
from django.db import migrations


def backfill_reports(apps, schema_editor):
    alias = schema_editor.connection.alias
    Application = apps.get_model('matchmaking', 'Application')
    Link = apps.get_model('matchmaking', 'DataRoomReportLink')
    Document = apps.get_model('zelda_api', 'DocumentSource')
    Memo = apps.get_model('zelda_api', 'IntelligenceMemo')
    Evidence = apps.get_model('zelda_api', 'TruthDeltaReport')
    Valuation = apps.get_model('zelda_api', 'BusinessValuationReport')
    Order = apps.get_model('billing', 'ZeldaOrder')

    founders = dict(Application.objects.using(alias).values_list('user_id', 'id'))
    clones = set(Order.objects.using(alias).exclude(analysis_document_id__isnull=True)
                 .values_list('analysis_document_id', flat=True))
    clones.update(Order.objects.using(alias).exclude(valuation_document_id__isnull=True)
                  .values_list('valuation_document_id', flat=True))
    documents = {doc.id: doc for doc in Document.objects.using(alias).filter(uploaded_by_id__in=founders)}

    def add(founder_id, kind, source_id, key, size, when):
        link, created = Link.objects.using(alias).get_or_create(
            founder_id=founder_id, source_kind=kind, source_id=str(source_id), report_key=key,
            defaults={'size_bytes': max(1, size)},
        )
        if created and when:
            Link.objects.using(alias).filter(pk=link.pk).update(saved_at=when)

    memo_sizes = {}
    evidence_sizes = {}
    valuation_sizes = {}
    memo_fields = ('executive_summary', 'problem_solution', 'market_analysis', 'team_assessment',
                   'financial_analysis', 'risk_assessment', 'business_model_analysis',
                   'information_readiness', 'supported_points', 'open_concerns',
                   'what_would_change_the_picture', 'upside_scenario', 'base_scenario',
                   'downside_scenario', 'zelda_advantage', 'questions_for_management', 'retrieved_context')
    for memo in Memo.objects.using(alias).iterator():
        size = sum(len((getattr(memo, name) or '').encode('utf-8')) for name in memo_fields)
        memo_sizes[memo.document_id] = size
        doc = documents.get(memo.document_id)
        if doc and doc.id not in clones and not doc.is_product_input and not doc.is_external_subject and doc.document_type == 'pitch_deck':
            add(founders[doc.uploaded_by_id], 'document', doc.id, 'memo', size, memo.created_at)
    for report in Evidence.objects.using(alias).iterator():
        import json
        size = len((report.summary or '').encode('utf-8')) + len(json.dumps(report.details).encode('utf-8'))
        evidence_sizes[report.document_id] = size
        doc = documents.get(report.document_id)
        if doc and doc.id not in clones and not doc.is_product_input:
            add(founders[doc.uploaded_by_id], 'document', doc.id, 'truth_delta', size, report.created_at)
    for report in Valuation.objects.using(alias).iterator():
        size = sum(len((getattr(report, name) or '').encode('utf-8')) for name in
                   ('business_overview', 'financial_summary', 'risk_report', 'valuation_summary'))
        valuation_sizes[report.document_id] = size
        doc = documents.get(report.document_id)
        if doc and doc.id not in clones and not doc.is_product_input:
            add(founders[doc.uploaded_by_id], 'document', doc.id, 'valuation', size, doc.created_at)
    for order in Order.objects.using(alias).filter(status='ready', paid_at__isnull=False).iterator():
        founder_id = founders.get(order.user_id)
        if founder_id:
            for key in order.reports:
                if key in ('intelligence_memo', 'ic_memo', 'truth_delta', 'valuation', 'entity'):
                    size = (valuation_sizes.get(order.valuation_document_id, 0) if key == 'valuation' else
                            evidence_sizes.get(order.analysis_document_id, 0) if key == 'truth_delta' else
                            memo_sizes.get(order.analysis_document_id, 0) if key in ('intelligence_memo', 'ic_memo') else 0)
                    add(founder_id, 'order', order.pk, key, size,
                        order.finished_at or order.paid_at)


class Migration(migrations.Migration):
    dependencies = [
        ('matchmaking', '0093_dataroom_storage_quota'),
        ('zelda_api', '0039_libraryhiddenitem'),
        ('billing', '0007_truth_delta_credit_wallet'),
    ]
    operations = [migrations.RunPython(backfill_reports, migrations.RunPython.noop)]
