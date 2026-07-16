"""
Investment Committee (IC) Memo Generator — synthesizes existing AI-generated
content (IntelligenceMemo, TruthDeltaReport, BusinessValuationReport) plus
pitch-deck engagement analytics and financials into one shareable document.

Deliberately NOT a new generation pipeline: no new Celery task, no new
persisted model. The memo is assembled fresh from whatever already exists
for the founder every time it's requested, so it can never go stale the
way a cached/persisted snapshot would.
"""
from .vector_models import DocumentSource, IntelligenceMemo, BusinessValuationReport
from .truth_delta_models import TruthDeltaReport

# Same ordered section list as loadMemo() in
# templates/includes/zelda_ai_assistant_enhanced.html (~line 1199) — kept in
# sync deliberately so the IC memo and the in-app sidebar preview never
# show different section labels for the same underlying data.
MEMO_SECTIONS = [
    ('executive_summary', 'Executive Summary'),
    ('problem_solution', 'Problem & Solution'),
    ('market_analysis', 'Market Analysis'),
    ('team_assessment', 'Team Assessment'),
    ('financial_analysis', 'Financial Analysis'),
    ('risk_assessment', 'Risk Assessment'),
    ('investment_thesis', 'Investment Thesis'),
    ('investment_readiness', 'Investment Readiness'),
    ('questions_for_management', 'Questions for Management'),
]


def can_view_ic_memo(request_user, founder_application):
    """
    Owner + staff always. Otherwise only an investor with an ACCEPTED
    Connection to this founder — deliberately tighter than the existing
    DocumentMemoView, which lets any authenticated investor view any
    founder's memo with no connection check. A generated, forwardable IC
    memo is a bigger surface than an in-app preview, so it's scoped to
    investors who've actually been introduced.
    """
    if not request_user or not request_user.is_authenticated:
        return False
    if request_user == founder_application.user or request_user.is_staff:
        return True

    investor_profile = getattr(request_user, 'match_investor_profile', None)
    if not investor_profile:
        return False

    from matchmaking.models import Connection
    return Connection.objects.filter(
        investor=investor_profile, founder=founder_application, status='ACCEPTED'
    ).exists()


def build_ic_memo_context(founder_application):
    """
    Assembles everything an IC memo needs for one founder. Every piece is
    optional and independently None-able — a founder with no valuation
    request, no Truth Delta run yet, or no deck views at all still gets a
    memo, just with those sections omitted rather than faked.
    """
    from matchmaking.growth_metrics import get_deck_engagement_stats

    founder_user = founder_application.user

    pitch_deck_doc = (
        DocumentSource.objects.filter(
            uploaded_by=founder_user, document_type='pitch_deck', status='analyzed'
        )
        .order_by('-created_at')
        .first()
    )
    valuation_doc = (
        DocumentSource.objects.filter(
            uploaded_by=founder_user, document_type='business_valuation', status='analyzed'
        )
        .order_by('-created_at')
        .first()
    )

    memo_sections = None
    memo_meta = None
    truth_delta = None
    if pitch_deck_doc and hasattr(pitch_deck_doc, 'memo'):
        memo = pitch_deck_doc.memo
        memo_sections = [
            {'label': label, 'text': getattr(memo, key, '')}
            for key, label in MEMO_SECTIONS
            if getattr(memo, key, '')
        ]
        memo_meta = {
            'recommendation': memo.get_recommendation_display(),
            'completeness_score': round(memo.completeness_score * 100, 1),  # 0-1 -> 0-100 for display
            'citations_count': memo.citations_count,
            'generated_at': memo.created_at,
        }

        report = pitch_deck_doc.truthdeltareport_set.first()
        if report:
            truth_delta = {
                'overall_truth_score': report.overall_truth_score,
                'summary': report.summary,
            }

    valuation = None
    if valuation_doc and hasattr(valuation_doc, 'valuation_report'):
        vr = valuation_doc.valuation_report
        valuation = {
            'valuation_low': vr.valuation_low,
            'valuation_high': vr.valuation_high,
            'valuation_summary': vr.valuation_summary,
            'confidence_score': vr.confidence_score,  # already 0-100 scale, unlike memo's completeness_score
        }

    deck_engagement = get_deck_engagement_stats(founder_application)

    financials = {
        'raising_amount': founder_application.raising_amount,
        'current_revenue': founder_application.current_revenue,
        'monthly_burn_rate': founder_application.monthly_burn_rate,
        'team_size': founder_application.team_size,
        'years_in_business': founder_application.years_in_business,
        'runway_months': founder_application.runway_months,
        'zelda_score': founder_application.zelda_score,
    }

    return {
        'application': founder_application,
        'company_name': founder_application.company_name,
        'pitch_deck_doc': pitch_deck_doc,
        'memo_sections': memo_sections,
        'memo_meta': memo_meta,
        'truth_delta': truth_delta,
        'valuation': valuation,
        'deck_engagement': deck_engagement,
        'financials': financials,
    }


def render_ic_memo_markdown(context):
    """Formats the same context dict the HTML view renders, as plain Markdown — one formatter, so the two can't drift apart."""
    lines = [f"# Investment Committee Memo — {context['company_name']}", '']

    if context['memo_meta']:
        meta = context['memo_meta']
        lines.append(f"**Recommendation:** {meta['recommendation']}  ")
        lines.append(f"**Memo Completeness:** {meta['completeness_score']}%  ")
        lines.append(f"**Citations:** {meta['citations_count']}  ")
        lines.append(f"**Generated:** {meta['generated_at']:%Y-%m-%d}")
        lines.append('')

    if context['memo_sections']:
        for section in context['memo_sections']:
            lines.append(f"## {section['label']}")
            lines.append(section['text'])
            lines.append('')
    else:
        lines.append('_No intelligence memo has been generated for this founder yet._')
        lines.append('')

    if context['truth_delta']:
        td = context['truth_delta']
        lines.append('## Truth Delta Signal')
        lines.append(
            "_Automated cross-check against SEC EDGAR, Crunchbase, and recent news coverage where "
            "available — a real signal, not a substitute for full diligence, since public data is "
            "sparse or nonexistent for most early-stage private companies._"
        )
        if td['overall_truth_score'] is not None:
            lines.append(f"**Signal Score:** {td['overall_truth_score']}/100")
        if td['summary']:
            lines.append(td['summary'])
        lines.append('')

    if context['valuation']:
        v = context['valuation']
        lines.append('## Valuation')
        if v['valuation_low'] is not None and v['valuation_high'] is not None:
            lines.append(f"**Range:** ${v['valuation_low']:,.0f} – ${v['valuation_high']:,.0f}")
        lines.append(f"**Confidence:** {v['confidence_score']:.0f}/100")
        if v['valuation_summary']:
            lines.append(v['valuation_summary'])
        lines.append('')

    fin = context['financials']
    lines.append('## Financial Snapshot')
    lines.append(f"- Raising: ${fin['raising_amount']:,.0f}" if fin['raising_amount'] else "- Raising: not disclosed")
    lines.append(f"- Current revenue: ${fin['current_revenue']:,.0f}" if fin['current_revenue'] is not None else "- Current revenue: not disclosed")
    lines.append(f"- Monthly burn: ${fin['monthly_burn_rate']:,.0f}" if fin['monthly_burn_rate'] is not None else "- Monthly burn: not disclosed")
    lines.append(f"- Runway: {fin['runway_months']} months" if fin['runway_months'] else "- Runway: not calculated")
    lines.append(f"- Team size: {fin['team_size']}" if fin['team_size'] else "- Team size: not disclosed")
    lines.append(f"- Zelda Score: {fin['zelda_score']}/99")
    lines.append('')

    if context['deck_engagement']:
        de = context['deck_engagement']
        lines.append('## Pitch Deck Engagement')
        lines.append(f"- Total viewing sessions: {de['total_sessions']}")
        lines.append(f"- Unique viewers: {de['unique_viewers']}")
        lines.append(f"- Average session time: {de['avg_session_time']}s")
        if de['slides']:
            lines.append('')
            lines.append('| Slide | Avg. Time (s) | Views |')
            lines.append('|---|---|---|')
            for slide in de['slides']:
                lines.append(f"| {slide['slide_number']} | {slide['avg_duration']} | {slide['views']} |")
        lines.append('')

    return '\n'.join(lines)
