# zelda_api/confidence_breakdown.py
"""
Per-category confidence breakdown surfaced on valuation/memo reports —
built entirely from data already computed during analysis
(IntelligenceInsight.category/.confidence_score), so this costs zero
additional Claude calls and works retroactively on every already-analyzed
document, not just new ones.

The overall confidence shown alongside a report is derived from these same
per-category numbers (see compute_overall_confidence) rather than being a
separate, coarser "how many categories got any insight at all" count — that
coverage-only version couldn't distinguish a document with thin, low-
confidence coverage from one with strong evidence in every category, and
gave no indication of *why* confidence was low.
"""
from .intelligence_pipeline import ZeldaIntelligencePipelineV2

ANALYSIS_CATEGORY_NAMES = list(ZeldaIntelligencePipelineV2.ANALYSIS_CATEGORIES)
CATEGORY_COUNT = len(ANALYSIS_CATEGORY_NAMES)

# A flat "specific figure" explanation reads fine for Revenue but is wrong
# for Problem or Product — there's no "figure" to find in a qualitative
# category. Two axes vary per category instead: the noun for what's being
# looked for (a number vs. a claim), and the verb for how it'd appear
# (reported vs. described). Categories not listed fall back to 'detail'/
# 'described' via .get()'s default below.
_CATEGORY_STYLE = {
    'Revenue': {'noun': 'figure', 'verb': 'reported'},
    'Funding': {'noun': 'figure', 'verb': 'reported'},
    'Traction': {'noun': 'signal', 'verb': 'reported'},
    'Team': {'noun': 'detail', 'verb': 'described'},
    'Product': {'noun': 'detail', 'verb': 'described'},
    'Problem': {'noun': 'claim', 'verb': 'described'},
    'Market': {'noun': 'claim', 'verb': 'described'},
    'Risk': {'noun': 'claim', 'verb': 'described'},
}
_DEFAULT_STYLE = {'noun': 'detail', 'verb': 'described'}


def _section_name(source_attribution):
    """'Extracted from: Traction' -> 'Traction' — falls back to 'the document' if unset."""
    prefix = 'Extracted from: '
    if source_attribution and source_attribution.startswith(prefix):
        return source_attribution[len(prefix):]
    return 'the document'


def _why_for_insight(category, insight):
    """
    Tier thresholds mirror _calculate_confidence's own documented tiers
    (explicit number match: 95, exact phrase match: 85, keyword-with-
    context: 70, generic/fallback: 35-50) — what changes per category is
    only the noun/verb, not the tier logic itself, and the section name is
    real provenance (insight.source_attribution), not invented framing.
    """
    style = _CATEGORY_STYLE.get(category, _DEFAULT_STYLE)
    section = _section_name(insight.source_attribution)
    score = insight.confidence_score

    if score >= 90:
        return f'Explicitly {style["verb"]} as "{insight.insight_text}" in the {section} section.'
    if score >= 80:
        return f'{style["verb"].capitalize()} using standard terminology in the {section} section, but without an explicit {style["noun"]}.'
    if score >= 60:
        return f'Mentioned in the {section} section, but the {style["noun"]} isn\'t explicitly quantified.'
    return f'No clear {style["noun"]} found for this category — inferred indirectly from the {section} section.'


def compute_confidence_breakdown(insights):
    """
    [{category, confidence (0-10, one decimal), why, insight_text}, ...] —
    one row per category that has an insight, ordered to match
    ANALYSIS_CATEGORIES (a stable, meaningful order) rather than whatever
    order the insights happen to come in.

    `insights` is any iterable of objects with .category/.confidence_score/
    .insight_text — either the in-memory list _analyze_document just built,
    or document.insights.all() for an already-analyzed document.
    """
    insights_by_category = {insight.category: insight for insight in insights}

    rows = []
    for category in ZeldaIntelligencePipelineV2.ANALYSIS_CATEGORIES:
        insight = insights_by_category.get(category)
        if not insight:
            continue
        rows.append({
            'category': category,
            'confidence': round(insight.confidence_score / 10, 1),
            'why': _why_for_insight(category, insight),
            'insight_text': insight.insight_text,
            'source_attribution': insight.source_attribution,
        })
    return rows


# Deterministic confidence -> letter-grade mapping for the free-preview
# "Zelda Analysis Scorecard" (zelda_api/valuation_preview.py). This grades
# CONFIDENCE — how much evidence Zelda found for a category — not the
# underlying business's quality; a low grade means thin evidence, not a
# weak team/market/etc. Callers must always present grades under that
# framing (see build_valuation_scorecard's docstring), never as a
# standalone verdict.
CONFIDENCE_GRADE_BANDS = [
    (9.0, 'A+'), (8.0, 'A'), (7.0, 'B+'), (6.0, 'B'),
    (5.0, 'C+'), (4.0, 'C'), (3.0, 'D'),
]


def grade_for_confidence(confidence_0_to_10):
    for threshold, grade in CONFIDENCE_GRADE_BANDS:
        if confidence_0_to_10 >= threshold:
            return grade
    return 'F'


def compute_overall_confidence(insights):
    """
    Average confidence across ALL canonical categories, treating a category
    with no insight as a 0 contribution — this is why a document missing
    several categories scores lower even if the categories it does have are
    all high-confidence, and why two thinly-inferred categories score lower
    than two directly-stated ones. Returns 0.0-1.0, same scale the old
    coverage-only formula used (min(len(insights) / 8.0, 1.0)), so nothing
    downstream that just displays this number needs to change.
    """
    insights_by_category = {insight.category: insight for insight in insights}
    total = sum(
        insights_by_category[c].confidence_score
        for c in ZeldaIntelligencePipelineV2.ANALYSIS_CATEGORIES
        if c in insights_by_category
    )
    return min(total / (CATEGORY_COUNT * 100.0), 1.0)


# The financial fields _build_structured_context looks for — same dict as
# its own `checks` mapping, duplicated rather than imported to keep this
# module import-cheap and because the two are allowed to diverge (this one
# describes a user-facing completeness score, that one describes what to
# tell Claude is missing).
FINANCIAL_COMPLETENESS_FIELDS = {
    'arr': 'Revenue / ARR / MRR',
    'raise_amount': 'Raise amount',
    'market_size': 'Total addressable market size',
    'use_of_proceeds': 'Use of proceeds',
    'burn_rate': 'Monthly burn rate',
    'retention': 'Customer retention / churn rate',
    'growth_rate': 'Growth rate',
}


def compute_financial_completeness(facts):
    """
    Platform-derived, NOT a model confidence score — how many of the key
    financial fields actually got disclosed, out of the ones
    _build_structured_context checks for. Must be labeled as
    platform-derived wherever it's shown, so it doesn't read as if Claude
    assessed its own confidence in financial completeness — it didn't;
    this is a plain missing-fields count.
    """
    total = len(FINANCIAL_COMPLETENESS_FIELDS)
    disclosed = sum(1 for field in FINANCIAL_COMPLETENESS_FIELDS if facts.get(field))
    return {
        'ratio': disclosed / total if total else 0.0,
        'disclosed': disclosed,
        'total': total,
    }
