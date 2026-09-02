# zelda_api/valuation_preview.py
"""
Free-preview redaction for business_valuation reports (see
DocumentSource.valuation_tier). Design principle (through three
revisions: the first showed locked section cards for every field; the
second added a per-category "findings" checklist that was still, on
reflection, too much of the report's shape; the third added a bare
letter-grade Scorecard — see build_valuation_scorecard's docstring for
why that's a materially different disclosure than the rejected second
revision, not a reversion to it): the user came to Zelda with exactly
one question — "what's my company worth" — so the preview should sell
the ANSWER, not summarize the report's table of contents. Prove Zelda
understood the business (business overview, in full) and that the
analysis finished (trust stats, a plain risk COUNT, and now a bare
per-category grade — never category findings, explanations, or any
sample finding text), tease the valuation itself (masked, not omitted),
then sell the unlock as one complete deliverable. Redaction happens
server-side here, not client-side in the template's JS — a locked field
is simply never present in the JSON, so it can't be read out of the
network tab.
"""
from .confidence_breakdown import grade_for_confidence

# What a full unlock includes — deliberately doesn't promise a PDF
# export, since that isn't a real capability today (see
# zelda_api/views.py::valuation_report_view and templates/
# zelda_valuation_report.html — there is no export feature to unlock).
UNLOCK_INCLUDES = [
    'Estimated valuation range',
    'Complete risk report',
    'Valuation methodology',
    'Full confidence breakdown',
    'Evidence citations',
    'Historical valuation tracking',
]


def _split_risk_lines(risk_report_text):
    """
    risk_report is free text Claude writes as a numbered/bulleted list per
    the "3-5 specific risks" prompt instruction, not a structured field.
    Splits on newlines and strips bullet/number decoration; falls back to
    the whole text as one "risk" if there's no line structure at all —
    used only to COUNT findings for the preview teaser, never to display
    any of their actual text.
    """
    lines = [line.strip(' -•*\t') for line in (risk_report_text or '').splitlines() if line.strip()]
    lines = [line.lstrip('0123456789.) ') for line in lines]
    return lines or ([risk_report_text] if risk_report_text else [])


def build_valuation_scorecard(confidence_breakdown):
    """
    Free-preview "Zelda Analysis Scorecard" — a bare letter grade per
    category (Problem/Market/Revenue/Team/Product/Traction/Funding/Risk,
    whichever the document has insights for), stripped of everything else
    compute_confidence_breakdown carries: no `why`, no `insight_text`, no
    `source_attribution`. Those stay full-tier-only (see UNLOCK_INCLUDES's
    "Full confidence breakdown") — this only ever emits {category, grade}.

    This grades CONFIDENCE — how much evidence Zelda found for that
    category — not the underlying business's quality. A 'Team: B' means
    Zelda found moderate evidence about the team, not that the team is
    mediocre; callers must present this under an explicit label ("Zelda
    Analysis Scorecard") with a confidence-not-quality subtitle, never as
    a standalone grade that could be misread as a verdict on the business.

    Materially different disclosure than the second (rejected) preview
    revision's per-category findings checklist: that showed what Zelda
    found per category; this shows only that Zelda analyzed each
    category, at what confidence — proof of completed work, like the
    trust-stats numbers, not a finding about any one dimension.
    """
    return [
        {'category': row['category'], 'grade': grade_for_confidence(row['confidence'])}
        for row in confidence_breakdown
    ]


def build_valuation_response(doc, report, insights, confidence_breakdown, overall_confidence, financial_completeness, tier):
    """
    Assembles the full DocumentValuationView JSON body for the given
    tier. 'full' includes everything. 'preview' omits the valuation
    range, methodology, risk report, financial summary, and the detailed
    per-category confidence breakdown (why/insight_text/source_attribution)
    — replaced by a plain risk COUNT (never a sample finding), a bare
    per-category letter-grade Scorecard (see build_valuation_scorecard —
    grades only, no explanations), plus a static list of what unlocking
    includes.
    """
    from .disclaimers import DUE_DILIGENCE_DISCLAIMER

    response = {
        'report_id': report.id,
        'document_id': doc.id,
        'document_name': doc.source_entity,
        'valuation_tier': tier,
        'confidence_score': overall_confidence,
        'financial_completeness': financial_completeness,
        'trust_stats': {
            'pages_analyzed': doc.total_pages,
            'chunks_analyzed': doc.chunks.count(),
            'categories_analyzed': len(insights),
        },
        'generated_at': report.created_at.isoformat(),
        'sections': {
            'business_overview': report.business_overview,
        },
        'disclaimer': DUE_DILIGENCE_DISCLAIMER,
    }

    if tier == 'full':
        response['valuation_low'] = str(report.valuation_low) if report.valuation_low is not None else None
        response['valuation_high'] = str(report.valuation_high) if report.valuation_high is not None else None
        response['confidence_breakdown'] = confidence_breakdown
        response['sections']['financial_summary'] = report.financial_summary
        response['sections']['risk_report'] = report.risk_report
        response['sections']['valuation_summary'] = report.valuation_summary
        return response

    risk_lines = _split_risk_lines(report.risk_report)
    response['risk_count'] = len(risk_lines)
    response['scorecard'] = build_valuation_scorecard(confidence_breakdown)
    response['unlock_includes'] = UNLOCK_INCLUDES
    return response
