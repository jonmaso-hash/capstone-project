# matchmaking/deal_activity.py
"""
Per-deal activity timeline for the Deal Workspace (matchmaking/views.py::
deal_workspace_view). Deliberately narrow: every event here is built from
a query that names BOTH sides of the relationship explicitly on the
underlying row (founder AND investor, or a viewer field that IS the
specific investor's user), never inferred from founder alone.

That distinction matters concretely: DataRoomDocument.founder == founder
is true for every document in the room, visible to every investor
connected to that founder — including a different investor than the one
this timeline is for. So a document *upload* is fair to show (it's a
founder-side broadcast event, not a claim about this specific investor),
but a document *view* is only fair to show when the viewer on that
specific DataRoomDocumentView row is this exact investor's user — that's
the "Investor A" vs "Investor B" leak the feature spec called out.

Two events (Connection accepted, Verified Funded) need Connection.
accepted_at/funded_at rather than updated_at — see those fields'
docstring on the Connection model for why updated_at can't be trusted
for this.
"""
from .models import DataRoomDocument, DataRoomAccessRequest, DataRoomInformationRequest, DataRoomDocumentView, PitchDeckViewSession, AcquisitionInterestEvent


def get_deal_activity_timeline(connection, limit=25):
    """
    Chronological (newest first) activity for ONE specific founder-investor
    relationship (a single Connection row) — not the founder's activity in
    general, not the investor's activity in general.
    """
    founder = connection.founder
    investor = connection.investor
    events = []

    # 'category' lets a caller filter by kind without re-deriving it from
    # the label text. In particular: 'document' events must be dropped by
    # the view whenever the viewer's CURRENT can_view_data_room check
    # fails (e.g. an investor whose Connection has moved past 'ACCEPTED'
    # to FUNDED_PENDING/FUNDED loses Data Room access — see
    # deal_workspace_view) — this function has no notion of "who is
    # asking right now," only "what genuinely happened in this
    # relationship," so that access check can't live here.
    if connection.accepted_at:
        events.append({
            'icon': 'bi-check-circle-fill', 'label': 'Connection accepted', 'timestamp': connection.accepted_at,
            'category': 'relationship',
        })

    if connection.status == 'FUNDED' and connection.funded_at:
        events.append({
            'icon': 'bi-patch-check-fill', 'label': 'Verified Funded', 'timestamp': connection.funded_at,
            'category': 'verified_outcome',
        })

    # Founder-side broadcast — visible to every connected investor, not a
    # claim about this investor specifically, so founder alone is the
    # correct (and only available) filter here.
    for doc in DataRoomDocument.objects.filter(founder=founder):
        events.append({
            'icon': 'bi-upload', 'label': f'Founder uploaded "{doc.label}"', 'timestamp': doc.uploaded_at,
            'category': 'document',
        })

    # Investor-specific — viewer is this exact investor's user, not just
    # "someone viewed a document in this founder's room."
    for view in DataRoomDocumentView.objects.filter(document__founder=founder, viewer=investor.user).select_related('document'):
        events.append({
            'icon': 'bi-eye', 'label': f'Investor viewed "{view.document.label}"', 'timestamp': view.created_at,
            'category': 'document',
        })

    for access_req in DataRoomAccessRequest.objects.filter(document__founder=founder, investor=investor).select_related('document'):
        events.append({
            'icon': 'bi-hand-index-thumb', 'label': f'Investor requested "{access_req.document.label}"',
            'timestamp': access_req.requested_at, 'category': 'document',
        })
        if access_req.decided_at:
            verb = 'approved' if access_req.status == 'APPROVED' else 'denied'
            events.append({
                'icon': 'bi-check2' if access_req.status == 'APPROVED' else 'bi-x-lg',
                'label': f'Founder {verb} access to "{access_req.document.label}"',
                'timestamp': access_req.decided_at, 'category': 'document',
            })

    for info_req in DataRoomInformationRequest.objects.filter(founder=founder, investor=investor):
        events.append({
            'icon': 'bi-send', 'label': f'Investor requested {info_req.get_category_display()}',
            'timestamp': info_req.requested_at, 'category': 'document',
        })
        if info_req.decided_at:
            verb = 'fulfilled' if info_req.status == 'FULFILLED' else 'declined'
            events.append({
                'icon': 'bi-check2' if info_req.status == 'FULFILLED' else 'bi-x-lg',
                'label': f'Founder {verb} the {info_req.get_category_display()} request',
                'timestamp': info_req.decided_at, 'category': 'document',
            })

    # Pitch-deck views carry real viewer attribution (unlike, say,
    # InvestorInterestEvent, which doesn't identify who) — safe to include.
    # Categorized 'engagement', not 'document': the pitch deck has its own,
    # looser viewing gate (_can_view_pitch_deck) entirely independent of
    # can_view_data_room, so it must never be filtered alongside Data Room
    # events.
    for session in PitchDeckViewSession.objects.filter(founder=founder, viewer=investor.user):
        events.append({
            'icon': 'bi-file-earmark-text', 'label': 'Investor viewed the pitch deck', 'timestamp': session.started_at,
            'category': 'engagement',
        })

    events.sort(key=lambda e: e['timestamp'], reverse=True)
    return events[:limit]


# Interest event types that represent a genuine buyer-side interaction
# worth surfacing on a deal timeline. Deliberately excludes 'closed' (the
# AcquisitionConnection.closed_at event above already covers that from
# the authoritative source, so including both would double-count the same
# fact) and 'thumbs_up'/'thumbs_down' (bulletin-board feedback, not really
# a "deal" event once a relationship is already accepted).
ACQUISITION_TIMELINE_EVENT_TYPES = {
    'view': 'Buyer viewed the listing',
    'video_play': 'Buyer played the pitch video',
    'memo_view': 'Buyer viewed the Intelligence Memo',
    'truth_delta_view': 'Buyer viewed Truth Delta verification',
    'message_sent': 'Buyer sent a message',
}


def get_acquisition_deal_activity_timeline(acquisition_connection, limit=25):
    """
    M&A mirror of get_deal_activity_timeline, for one specific
    buyer-seller relationship (a single AcquisitionConnection row).

    Deliberately narrower than the Connection-side timeline: there is no
    seller-side Data Room (DataRoomDocument.founder is hard-FK'd to
    Application, not SellerApplication — confirmed absent, not merely
    unused), so there are no document upload/view/request events to draw
    from at all. Rather than infer document activity that was never
    actually recorded against this relationship, this only surfaces:
    the two AcquisitionConnection lifecycle/outcome timestamps (both
    already relationship-provable — they live directly on this exact
    row), and AcquisitionInterestEvent rows, which DO carry real
    buyer+seller attribution on every row (see log_buyer_event) unlike
    the Data Room gap above.
    """
    seller = acquisition_connection.seller
    buyer = acquisition_connection.buyer
    events = []

    if acquisition_connection.accepted_at:
        events.append({
            'icon': 'bi-check-circle-fill', 'label': 'Connection accepted', 'timestamp': acquisition_connection.accepted_at,
            'category': 'relationship',
        })

    if acquisition_connection.status == 'CLOSED' and acquisition_connection.closed_at:
        events.append({
            'icon': 'bi-patch-check-fill', 'label': 'Verified Sold', 'timestamp': acquisition_connection.closed_at,
            'category': 'verified_outcome',
        })

    interest_events = AcquisitionInterestEvent.objects.filter(
        seller=seller, buyer=buyer.user, event_type__in=ACQUISITION_TIMELINE_EVENT_TYPES.keys(),
    )
    for event in interest_events:
        events.append({
            'icon': 'bi-eye', 'label': ACQUISITION_TIMELINE_EVENT_TYPES[event.event_type], 'timestamp': event.created_at,
            'category': 'engagement',
        })

    events.sort(key=lambda e: e['timestamp'], reverse=True)
    return events[:limit]
