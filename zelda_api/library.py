"""
The Zelda Library: the analyses and reports that already exist for the signed-in
user, in one place.

Before this, reopening an analysis in the Zelda panel meant typing its document ID
into the Memos tab. Nothing here generates, scores or unlocks anything -- it lists
what exists and links to it:

- your own documents and their analysis status, and your company's reports;
- your valuations, and the valuation history page;
- for investors, the companies you analyzed or whose reports you opened, most
  recent first -- from InvestorInterestEvent and AnalysisCreditCharge, which
  already record exactly that.

Every report link comes from build_report_nav, so the Library applies the same
access rules the reports enforce and names a locked report instead of linking to
a page that would refuse the viewer. A company that has since gone private or
been archived drops out of an investor's list (discoverable()), as it does from
every other discovery surface.
"""
from django.urls import reverse
from django.db import DatabaseError, transaction
import logging
import uuid

logger = logging.getLogger(__name__)

LIST_LIMIT = 20

RECENT_ACTIVITY = {
    'analyze': 'You analyzed this company with Zelda',
    'memo_view': 'You opened its Zelda brief',
    'truth_delta_view': 'You checked its evidence',
}
PAID_ANALYSIS = 'You ran a Zelda analysis'

STATUS_LABELS = {
    'ingested': 'Uploaded — not analyzed',
    'analyzed': 'Ready',
    'error': "Couldn't finish",
}


def _status(document):
    return STATUS_LABELS.get(document.status, 'Processing')


def _own_documents(user, product_storage=True, hidden_ids=()):
    from .vector_models import DocumentSource
    documents = DocumentSource.objects.filter(uploaded_by=user).exclude(pk__in=hidden_ids)
    if product_storage:
        documents = documents.filter(is_product_input=False, analysis_orders__isnull=True, valuation_orders__isnull=True)
    else:
        documents = documents.defer('is_product_input', 'is_external_subject', 'external_cik')
    documents = (documents
        .exclude(document_type='business_valuation')
        .select_related('memo')
        .order_by('-created_at')[:LIST_LIMIT]
    )
    return [{
        'document_id': document.id,
        'name': document.source_entity or document.filename,
        'kind': document.get_document_type_display(),
        'status': _status(document),
        'can_open_brief': document.status == 'analyzed' and hasattr(document, 'memo'),
        'created_at': document.created_at.isoformat(),
    } for document in documents]


def _own_valuations(user, product_storage=True, hidden_ids=()):
    from .vector_models import DocumentSource
    documents = DocumentSource.objects.filter(uploaded_by=user, document_type='business_valuation').exclude(pk__in=hidden_ids)
    if product_storage:
        documents = documents.filter(valuation_orders__isnull=True)
    else:
        documents = documents.defer('is_product_input', 'is_external_subject', 'external_cik')
    documents = (documents
        .exclude(status='error')
        .order_by('-created_at')[:LIST_LIMIT]
    )
    return [{
        'document_id': document.id,
        'name': document.source_entity or document.filename,
        'status': _status(document),
        'url': reverse('zelda_api:valuation_report', args=[document.id]),
        'created_at': document.created_at.isoformat(),
    } for document in documents]


def _recent_companies(user, hidden_ids=()):
    """Companies this investor analyzed or opened reports for, newest activity first."""
    from matchmaking.models import Application, InvestorInterestEvent
    from .ic_memo import latest_analyzed_pitch_deck_and_memo
    from .models import AnalysisCreditCharge
    from .report_nav import build_report_nav

    latest = {}  # Application id -> (when, what the investor did)

    def record(application_id, when, label):
        if application_id not in latest or when > latest[application_id][0]:
            latest[application_id] = (when, label)

    events = (
        InvestorInterestEvent.objects.filter(investor=user, event_type__in=RECENT_ACTIVITY)
        .values_list('founder_id', 'event_type', 'created_at')
    )
    for application_id, event_type, when in events:
        record(application_id, when, RECENT_ACTIVITY[event_type])

    charges = list(AnalysisCreditCharge.objects.filter(user=user).select_related('document'))
    application_by_owner = dict(
        Application.objects.filter(user_id__in={c.document.uploaded_by_id for c in charges})
        .values_list('user_id', 'id')
    )
    for charge in charges:
        application_id = application_by_owner.get(charge.document.uploaded_by_id)
        if application_id:
            record(application_id, charge.created_at, PAID_ANALYSIS)

    applications = (
        Application.objects.discoverable().exclude(review_status='DENIED')
        .filter(id__in=latest).exclude(id__in=hidden_ids).select_related('user')
    )
    ordered = sorted(applications, key=lambda application: latest[application.id][0], reverse=True)

    items = []
    for application in ordered[:LIST_LIMIT]:
        when, label = latest[application.id]
        document, memo = latest_analyzed_pitch_deck_and_memo(application.user)
        can_open_brief = bool(document and memo is not None and not document.is_hidden_by_staff)
        items.append({
            'company_id': application.id,
            'company': application.company_name or application.user.username,
            'activity': label,
            'last_activity': when.isoformat(),
            'profile_url': reverse('accounts:profile', kwargs={'username': application.user.username}),
            'brief_document_id': document.id if can_open_brief else None,
            'reports': build_report_nav(user, application.user, None),
        })
    return items


def build_library(user):
    from .report_nav import build_report_nav
    from .models import LibraryHiddenItem

    sections = []
    warnings = []
    from billing.models import ZeldaOrder
    from .vector_models import DocumentSource
    try:
        with transaction.atomic():
            ZeldaOrder.objects.filter(user=user).only('id').first()
            list(DocumentSource.objects.filter(uploaded_by=user).values('is_product_input', 'is_external_subject', 'external_cik')[:1])
        product_storage = True
    except DatabaseError:
        logger.exception('Zelda purchased report storage unavailable for Library user %s', user.pk)
        product_storage = False
        warnings.append('Purchased reports are temporarily unavailable. Existing documents are shown below. Please try again shortly.')

    def available(call, label):
        try:
            with transaction.atomic():
                return call()
        except DatabaseError:
            logger.exception('Could not load Zelda Library section %s for user %s', label, user.pk)
            warnings.append(f'{label} could not be loaded. Please try again shortly.')
            return []

    hidden = {key: set() for key in ('document', 'valuation', 'order', 'company')}
    for item_type, item_id in available(
        lambda: list(LibraryHiddenItem.objects.filter(user=user).values_list('item_type', 'item_id')),
        'Hidden Library items',
    ):
        if item_type in hidden:
            hidden[item_type].add(item_id)

    def visible_document_ids(kind):
        return {int(value) for value in hidden[kind] if value.isdecimal()}

    company_profile = (getattr(user, 'match_founder_profile', None)
                       or getattr(user, 'match_seller_profile', None))
    documents = available(lambda: _own_documents(user, product_storage, visible_document_ids('document')), 'Your documents')
    if company_profile or documents:
        sections.append({
            'key': 'your_company',
            'title': 'Your company',
            'company': getattr(company_profile, 'company_name', '') or '',
            'reports': available(lambda: build_report_nav(user, user, None,
                visible_document_ids('document') | visible_document_ids('valuation')), 'Your company reports') if company_profile else [],
            'documents': documents,
        })

    valuations = available(lambda: _own_valuations(user, product_storage, visible_document_ids('valuation')), 'Your valuations')
    if valuations:
        sections.append({
            'key': 'valuations',
            'title': 'Your valuations',
            'items': valuations,
            'history_url': reverse('zelda_api:valuation_history'),
        })

    if getattr(user, 'match_investor_profile', None) is not None:
        sections.append({
            'key': 'recent_companies',
            'title': "Companies you've looked into",
            'items': available(lambda: _recent_companies(user, visible_document_ids('company')), 'Recent company reports'),
        })

    has_role = any(getattr(user, name, None) is not None for name in (
        'match_founder_profile', 'match_investor_profile', 'match_seller_profile', 'match_buyer_profile'))
    from billing.zelda_catalog import ALL_STRIPE_PRODUCTS, REPORTS
    from billing.fulfillment import reconcile_order
    purchases = []
    orders = available(lambda: list(ZeldaOrder.objects.filter(user=user).exclude(status='canceled').exclude(id__in=hidden['order']).select_related(
            'source_document', 'analysis_document', 'valuation_document', 'entity_report')[:LIST_LIMIT]), 'Purchased reports') if product_storage else []
    for order in orders:
        if not available(lambda: reconcile_order(order), 'Purchased report status'):
            continue
        purchases.append({'order_id': str(order.id), 'company': order.source_document.source_entity, 'product': ALL_STRIPE_PRODUCTS[order.product][0],
                          'status': order.get_status_display(), 'url': reverse('billing:zelda_order', args=[order.id]),
                          'reports': [{'name': REPORTS[key][0], 'url': reverse('billing:zelda_report', args=[order.id, key])}
                                      for key in order.reports] if order.status == 'ready' else []})
    return {
        'warnings': warnings,
        'purchases': purchases,
        'sections': sections,
        'profile_analytics_url': (
            reverse('accounts:profile_analysis', kwargs={'username': user.username}) if has_role else None),
    }


def dismiss_library_item(user, item_type, item_id):
    """Hide only a currently owned/listed item. Never erase source or billing data."""
    from billing.models import ZeldaOrder
    from .models import LibraryHiddenItem
    from .vector_models import DocumentSource

    if item_type == 'order':
        try:
            item_id = str(uuid.UUID(item_id))
        except (ValueError, AttributeError):
            return False
        exists = ZeldaOrder.objects.filter(user=user, pk=item_id).exclude(status='canceled').exists()
    elif item_type in ('document', 'valuation', 'company') and len(item_id) <= 18 and item_id.isdecimal():
        item_id = str(int(item_id))
        if item_type == 'company':
            exists = any(str(item['company_id']) == item_id for item in _recent_companies(user))
        else:
            documents = DocumentSource.objects.filter(uploaded_by=user, pk=item_id)
            if item_type == 'valuation':
                exists = documents.filter(document_type='business_valuation', valuation_orders__isnull=True).exists()
            else:
                exists = documents.exclude(document_type='business_valuation').filter(
                    is_product_input=False, analysis_orders__isnull=True, valuation_orders__isnull=True,
                ).exists()
    else:
        return False
    if not exists:
        return False
    LibraryHiddenItem.objects.get_or_create(user=user, item_type=item_type, item_id=item_id)
    return True
