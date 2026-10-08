"""Owner-only Data Room index of saved Zelda report links."""
from django.urls import reverse

REPORT_FOLDERS = ('Memos', 'Truth Delta', 'Valuations', 'Entity checks')


def report_archive_for_owner(user, search=''):
    from billing.models import ZeldaOrder
    from billing.zelda_catalog import REPORTS
    from matchmaking.models import Application, DataRoomReportLink
    from .vector_models import DocumentSource

    founder = Application.objects.filter(user=user).first()
    if not founder:
        return []
    links = list(DataRoomReportLink.objects.filter(founder=founder))
    documents = {str(doc.id): doc for doc in DocumentSource.objects.filter(
        uploaded_by=user, pk__in=[link.source_id for link in links if link.source_kind == 'document'])}
    orders = {str(order.id): order for order in ZeldaOrder.objects.filter(
        user=user, pk__in=[link.source_id for link in links if link.source_kind == 'order'])
        .select_related('source_document')}
    entries = []
    for link in links:
        if link.source_kind == 'document':
            document = documents.get(link.source_id)
            if not document:
                continue
            subject = document.source_entity or document.filename
            folder, title, route = {
                'memo': ('Memos', 'IC Memo', 'zelda_api:ic_memo'),
                'truth_delta': ('Truth Delta', 'Evidence report', 'zelda_api:truth_delta_ui'),
                'valuation': ('Valuations', 'Business valuation', 'zelda_api:valuation_report'),
            }.get(link.report_key, (None, None, None))
            if not route:
                continue
            url = reverse(route, args=[document.id])
            shareable = link.report_key in ('memo', 'truth_delta') and not document.is_external_subject
        else:
            order = orders.get(link.source_id)
            if not order or order.status != 'ready' or not order.paid_at or link.report_key not in order.reports:
                continue
            subject = order.source_document.source_entity
            title = REPORTS.get(link.report_key, ('Report',))[0]
            folder = ('Valuations' if link.report_key == 'valuation' else 'Truth Delta'
                      if link.report_key == 'truth_delta' else 'Entity checks'
                      if link.report_key == 'entity' else 'Memos')
            url = reverse('billing:zelda_report', args=[order.id, link.report_key])
            shareable = False
        entries.append({'folder': folder, 'subject': subject, 'title': title,
                        'url': url, 'date': link.saved_at, 'shareable': shareable})

    term = search.strip().casefold()[:100]
    if term:
        entries = [entry for entry in entries if term in ' '.join(
            (entry['folder'], entry['subject'], entry['title'])).casefold()]
    return [{'name': name, 'entries': [entry for entry in entries if entry['folder'] == name]}
            for name in REPORT_FOLDERS if any(entry['folder'] == name for entry in entries)]
