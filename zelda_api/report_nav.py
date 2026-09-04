"""
The shared "Explore the analysis" strip.

Interlink's four intelligence reports each answer one question:

    Company overview   (Zelda Intelligence Report) — what is this company?
    Check the evidence (Truth Delta)               — which claims hold up?
    Investment analysis(IC Memo)                   — what does it mean?
    Valuation range    (Business Valuation)        — what is it worth?

That architecture used to be legible only if you happened to enter through
the Zelda Report — it was the one page that linked anywhere. This builds
the same four-item strip for every report so the set is discoverable from
whichever one you land on first.

Navigation only. It resolves URLs and asks the existing permission rules
whether this viewer may open each destination; it never computes, scores,
or exposes report content.
"""
from django.urls import reverse

OVERVIEW = 'overview'
EVIDENCE = 'evidence'
ANALYSIS = 'analysis'
VALUATION = 'valuation'

# Plain-language destination labels — what the reader gets, not what we
# call the feature internally.
LABELS = [
    (OVERVIEW, 'Company overview'),
    (EVIDENCE, 'Check the evidence'),
    (ANALYSIS, 'Investment analysis'),
    (VALUATION, 'Valuation range'),
]

_LOCKED = 'Available once you and this company are connected'
_OWNER_ONLY = "Only this company can open its own valuation"
_INVESTOR_ONLY = 'Investor accounts only'


def build_report_nav(viewer, founder_user, current):
    """
    The four-item strip for one company, from the point of view of
    `viewer`. `current` is one of the module constants and marks the
    report the reader is already on (rendered as current, never linked).

    A destination is only included when that report actually exists for
    this company — we never imply an analysis that was never run. An
    existing-but-gated destination is included WITHOUT a url and with a
    short `note`, so the reader learns the report exists without being
    handed a link that 403s.
    """
    from matchmaking.models import Application
    from .vector_models import DocumentSource
    from .ic_memo import latest_analyzed_pitch_deck_and_memo, can_view_ic_memo

    application = Application.objects.filter(user=founder_user).first()
    pitch_deck_doc, memo = latest_analyzed_pitch_deck_and_memo(founder_user)
    valuation_doc = (
        DocumentSource.objects
        .filter(uploaded_by=founder_user, document_type='business_valuation', status='analyzed')
        .order_by('-created_at')
        .first()
    )

    is_staff = bool(getattr(viewer, 'is_staff', False))
    is_owner = viewer == founder_user
    viewer_is_investor = getattr(viewer, 'match_investor_profile', None) is not None

    urls, notes = {}, {}

    # Company overview — standalone_memo_view: investor profile or staff.
    if application:
        if viewer_is_investor or is_staff:
            urls[OVERVIEW] = reverse('matchmaking:standalone_memo',
                                     args=[application.company_name.lower().replace(' ', '-')])
        else:
            notes[OVERVIEW] = _INVESTOR_ONLY

    # Check the evidence — truth_delta_ui_view: any signed-in viewer,
    # except a document staff has hidden for review.
    if pitch_deck_doc:
        hidden = pitch_deck_doc.is_hidden_by_staff and not (is_owner or is_staff)
        if not hidden:
            urls[EVIDENCE] = reverse('zelda_api:truth_delta_ui', args=[pitch_deck_doc.id])

    # Investment analysis — ic_memo_view: owner, staff, or an investor
    # with an accepted connection.
    if pitch_deck_doc and memo is not None and application:
        if can_view_ic_memo(viewer, application):
            urls[ANALYSIS] = reverse('zelda_api:ic_memo', args=[pitch_deck_doc.id])
        else:
            notes[ANALYSIS] = _LOCKED

    # Valuation range — valuation_report_view: owner or staff only.
    if valuation_doc and hasattr(valuation_doc, 'valuation_report'):
        if is_owner or is_staff:
            urls[VALUATION] = reverse('zelda_api:valuation_report', args=[valuation_doc.id])
        else:
            notes[VALUATION] = _OWNER_ONLY

    items = []
    for key, label in LABELS:
        if key != current and key not in urls and key not in notes:
            continue  # that report doesn't exist for this company
        items.append({
            'key': key,
            'label': label,
            'url': None if key == current else urls.get(key),
            'note': '' if key == current else notes.get(key, ''),
            'is_current': key == current,
        })
    return items
