"""
Work Done layer — a small, shared way to show the concrete analysis work
a report is built on (pages read, sections searched, claims checked, …)
without ever claiming work that wasn't done.

The rule, enforced in one place here so no surface can drift from it:
a metric is shown ONLY when its underlying value is a genuinely computed,
meaningful positive integer. Everything else is omitted, never rendered
as a zero:

  * None                         -> omit
  * 0                            -> omit
  * hardcoded/template constants -> caller must not pass them
  * inferred/estimated values    -> caller must not pass them
  * stub/mock data               -> caller must not pass them

No time estimates ("hours saved") exist here by construction — the helper
has no parameter for them.

This is the presentation mechanism for *new* Work Done surfaces. The
Business Valuation report already exposes an equivalent `trust_stats`
shape through its tested API contract; that is left as-is rather than
re-plumbed through this helper.
"""

# Ordered so the rendered grid always reads the same way across reports:
# what was read, then what was searched, then what was checked against it.
_METRIC_ORDER = (
    ('pages', 'Pages analyzed'),
    ('sections', 'Sections searched'),
    ('sections_written', 'Sections written'),
    ('categories', 'Categories analyzed'),
    ('claims', 'Claims checked'),
    ('sources', 'Sources checked'),
    ('datapoints', 'External datapoints found'),
    ('citations', 'Citations'),
    ('slides', 'Slides timed'),
)


def _clean(value):
    """A value counts only if it is a real positive integer."""
    if isinstance(value, bool):
        return None
    if not isinstance(value, int):
        return None
    return value if value > 0 else None


def work_done_summary(**counts):
    """
    Build the ordered list of work-done stats for a report.

    Accepts any of the keys in `_METRIC_ORDER` (pages, sections,
    sections_written, categories, claims, sources, datapoints, citations,
    slides). Returns a list of ``{'value': int, 'label': str}`` in a fixed
    order, containing only the metrics whose count is a positive integer.

    Returns ``[]`` when nothing qualifies — callers should render nothing
    in that case, not an empty container.
    """
    unknown = set(counts) - {key for key, _ in _METRIC_ORDER}
    if unknown:
        raise TypeError(f"work_done_summary() got unexpected metric(s): {sorted(unknown)}")

    summary = []
    for key, label in _METRIC_ORDER:
        cleaned = _clean(counts.get(key))
        if cleaned is not None:
            summary.append({'value': cleaned, 'label': label})
    return summary
