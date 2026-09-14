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

LIST_LIMIT = 20

RECENT_ACTIVITY = {
    'analyze': 'You analyzed this company with Zelda',
    'memo_view': 'You opened its Zelda brief',
    'truth_delta_view': 'You checked its evidence',
}
PAID_ANALYSIS = 'You ran a Zelda analysis'

STATUS_LABELS = {'analyzed': 'Ready', 'error': "Couldn't finish"}


def _status(document):
    return STATUS_LABELS.get(document.status, 'Processing')


def _own_documents(user):
    from .vector_models import DocumentSource
    documents = (
        DocumentSource.objects.filter(uploaded_by=user)
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


def _own_valuations(user):
    from .vector_models import DocumentSource
    documents = (
        DocumentSource.objects.filter(uploaded_by=user, document_type='business_valuation')
        .exclude(status='error')
        .order_by('-created_at')[:LIST_LIMIT]
    )
    return [{
        'name': document.source_entity or document.filename,
        'status': _status(document),
        'url': reverse('zelda_api:valuation_report', args=[document.id]),
        'created_at': document.created_at.isoformat(),
    } for document in documents]


def _recent_companies(user):
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
        .filter(id__in=latest).select_related('user')
    )
    ordered = sorted(applications, key=lambda application: latest[application.id][0], reverse=True)

    items = []
    for application in ordered[:LIST_LIMIT]:
        when, label = latest[application.id]
        document, memo = latest_analyzed_pitch_deck_and_memo(application.user)
        can_open_brief = bool(document and memo is not None and not document.is_hidden_by_staff)
        items.append({
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

    sections = []

    company_profile = (getattr(user, 'match_founder_profile', None)
                       or getattr(user, 'match_seller_profile', None))
    documents = _own_documents(user)
    if company_profile or documents:
        sections.append({
            'key': 'your_company',
            'title': 'Your company',
            'company': getattr(company_profile, 'company_name', '') or '',
            'reports': build_report_nav(user, user, None) if company_profile else [],
            'documents': documents,
        })

    valuations = _own_valuations(user)
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
            'items': _recent_companies(user),
        })

    has_role = any(getattr(user, name, None) is not None for name in (
        'match_founder_profile', 'match_investor_profile', 'match_seller_profile', 'match_buyer_profile'))
    return {
        'sections': sections,
        'profile_analytics_url': (
            reverse('accounts:profile_analysis', kwargs={'username': user.username}) if has_role else None),
    }
