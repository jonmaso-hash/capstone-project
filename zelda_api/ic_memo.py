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
    ('key_strengths', 'Key Strengths'),
    ('key_concerns', 'Key Concerns'),
    ('what_would_change_decision', 'What Would Change the Decision'),
    ('bull_case', 'Bull Case'),
    ('base_case', 'Base Case'),
    ('bear_case', 'Bear Case'),
    ('zelda_advantage', 'Zelda Advantage'),
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


def ic_memo_unlocked(request_user, founder_application):
    """
    Separate from can_view_ic_memo's access gate: whether the FULL Zelda AI
    memo is unlocked, vs. Zelda Lite. Gated on the FOUNDER's own Premium,
    not the investor's — this is a founder-controlled asset (their
    diligence package to share), so gating it on the investor's premium
    instead would let a founder ask to be connected and have investors
    keep viewing it for free with no one ever paying. Staff bypass for
    support purposes.
    """
    if request_user.is_staff:
        return True
    return founder_application.is_premium


# Zelda Lite shows the sections that answer "would an investment committee
# want to look closer?" — thesis, readiness, and the evidence-cited
# strengths/concerns/decision-changer that came out of the same structured-
# fields pass. Everything else (financial/market/team/risk detail, bull/
# base/bear scenario analysis, the Zelda Advantage note, Truth Delta,
# valuation, deck engagement) is the "what would they actually say and why"
# depth reserved for Zelda AI.
LITE_MEMO_SECTION_KEYS = {
    'investment_thesis', 'investment_readiness',
    'key_strengths', 'key_concerns', 'what_would_change_decision',
}


def build_ic_memo_context(founder_application, tier='full'):
    """
    Assembles everything an IC memo needs for one founder. Every piece is
    optional and independently None-able — a founder with no valuation
    request, no Truth Delta run yet, or no deck views at all still gets a
    memo, just with those sections omitted rather than faked.

    tier='lite' restricts memo_sections to LITE_MEMO_SECTION_KEYS and omits
    truth_delta/valuation/deck_engagement/financials entirely (None) rather
    than partially redacting them — those are each already Premium-gated
    reports in their own right, so showing a partial version of them here
    would be a second, inconsistent paywall for the same content.
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
        section_keys = MEMO_SECTIONS if tier == 'full' else [
            (key, label) for key, label in MEMO_SECTIONS if key in LITE_MEMO_SECTION_KEYS
        ]
        memo_sections = [
            {'label': label, 'text': getattr(memo, key, '')}
            for key, label in section_keys
            if getattr(memo, key, '')
        ]
        memo_meta = {
            'recommendation': memo.get_recommendation_display(),
            # Despite the model field's name, IntelligenceMemo.completeness_score is
            # Claude's own self-reported confidence in its analysis (see
            # intelligence_pipeline.py's `analysis_result.get('confidence', 0)`) — NOT
            # how much of the memo got filled in. Labeling it "completeness" produced
            # exactly the investor confusion flagged in review ("0.0% complete" next to
            # a fully-written memo). Renamed here; section_coverage below is the actual
            # structural completeness metric.
            'analysis_confidence': round(memo.completeness_score * 100, 1),  # 0-1 -> 0-100 for display
            'section_coverage': round(len(memo_sections) / len(MEMO_SECTIONS) * 100, 1) if MEMO_SECTIONS else 0,
            'readiness_score': memo.readiness_score,  # parsed 0-100 from investment_readiness text, or None
            'citations_count': memo.citations_count,
            'generated_at': memo.created_at,
        }

        if tier == 'full':
            report = pitch_deck_doc.truthdeltareport_set.first()
            if report:
                truth_delta = {
                    'overall_truth_score': report.overall_truth_score,
                    'summary': report.summary,
                }

    valuation = None
    deck_engagement = None
    financials = None
    if tier == 'full':
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

    from .disclaimers import DUE_DILIGENCE_DISCLAIMER

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
        'disclaimer': DUE_DILIGENCE_DISCLAIMER,
        'ic_memo_tier': tier,
    }


def render_ic_memo_markdown(context):
    """Formats the same context dict the HTML view renders, as plain Markdown — one formatter, so the two can't drift apart."""
    lines = [f"# AI Investment Committee Memo — {context['company_name']}", '']

    if context['memo_meta']:
        meta = context['memo_meta']
        lines.append(f"**Recommendation:** {meta['recommendation']}  ")
        lines.append(f"**Section Coverage:** {meta['section_coverage']}% of memo sections generated  ")
        lines.append(f"**Analysis Confidence:** {meta['analysis_confidence']}% (Zelda's own confidence in its analysis, not a verification score)  ")
        if meta['readiness_score'] is not None:
            lines.append(f"**Investment Readiness:** {meta['readiness_score']}/100  ")
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
            lines.append(f"**Signal Score:** {td['overall_truth_score']}/100 — reflects only the claims that had external data to check against, not an overall company assessment")
        if td['summary']:
            lines.append(td['summary'])
        lines.append('')

    if context['valuation']:
        v = context['valuation']
        lines.append('## Valuation')
        if v['valuation_low'] is not None and v['valuation_high'] is not None:
            lines.append(f"**Range:** ${v['valuation_low']:,.0f} – ${v['valuation_high']:,.0f}")
        lines.append(f"**Analysis Confidence:** {v['confidence_score']:.0f}/100 — Zelda's confidence in the valuation analysis, not a bound on the range")
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
    lines.append(f"- Zelda Score: {fin['zelda_score']}/99 — internal stability/efficiency/runway composite, not a verification or readiness measure")
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

    if context.get('disclaimer'):
        lines.append('---')
        lines.append(f"_{context['disclaimer']}_")
        lines.append('')

    return '\n'.join(lines)
