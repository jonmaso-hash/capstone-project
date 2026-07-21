# zelda_api/valuation_preview.py
"""
Free-preview redaction for business_valuation reports (see
DocumentSource.valuation_tier). Design principle (through two revisions:
the first showed locked section cards for every field; the second added
a per-category "findings" checklist that was still, on reflection, too
much of the report's shape): the user came to Zelda with exactly one
question — "what's my company worth" — so the preview should sell the
ANSWER, not summarize the report's table of contents. Prove Zelda
understood the business (business overview, in full) and that the
analysis finished (trust stats + a plain risk COUNT, never category
names or any sample finding), tease the valuation itself (masked, not
omitted), then sell the unlock as one complete deliverable. Redaction
happens server-side here, not client-side in the template's JS — a
locked field is simply never present in the JSON, so it can't be read
out of the network tab.
"""

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


def build_valuation_response(doc, report, insights, confidence_breakdown, overall_confidence, financial_completeness, tier):
    """
    Assembles the full DocumentValuationView JSON body for the given
    tier. 'full' includes everything. 'preview' omits the valuation
    range, methodology, risk report, financial summary, and the entire
    per-category confidence breakdown — replaced by a plain risk COUNT
    (never category names, never a sample finding) plus a static list of
    what unlocking includes.
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
    response['unlock_includes'] = UNLOCK_INCLUDES
    return response
