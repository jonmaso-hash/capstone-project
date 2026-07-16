from django import template

register = template.Library()


def _lookup_score(user):
    from zelda_api.vector_models import DocumentSource

    if getattr(user, 'match_founder_profile', None):
        doc = DocumentSource.objects.filter(uploaded_by=user, document_type='pitch_deck').order_by('-id').first()
        if doc and hasattr(doc, 'memo'):
            return 'founder', doc.memo.readiness_score
        return 'founder', None

    if getattr(user, 'match_seller_profile', None):
        doc = DocumentSource.objects.filter(uploaded_by=user, document_type='business_valuation').order_by('-id').first()
        if doc and hasattr(doc, 'valuation_report'):
            return 'seller', int(round(doc.valuation_report.confidence_score))
        return 'seller', None

    return None, None


@register.inclusion_tag('growth/_badge_embed_snippet.html', takes_context=True)
def badge_embed_snippet(context):
    """
    Renders the copy-paste embed box on founder_dashboard.html/
    seller_dashboard.html — only shows anything once that user has a memo/
    valuation report with a parseable score (see readiness_badge view).
    """
    request = context['request']
    user = request.user
    if not user.is_authenticated:
        return {'score': None}

    role, score = _lookup_score(user)
    return {
        'score': score,
        'role': role,
        'username': user.username,
        'request': request,
    }
