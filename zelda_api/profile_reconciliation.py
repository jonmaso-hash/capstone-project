"""
Profile vs deck: where a company's own figures disagree (B-2 v1).

A finding class of its own, before any public record is consulted:

    company profile  ->  company deck  ->  external evidence

Truth Delta answers the last arrow. This answers the first: does what the
company typed into its Interlink profile agree with what its own deck says?
It is NOT a Truth Delta state. A difference here is not "contradicted", an
agreement is not "verified", and nothing here touches the truth score. Neither
figure is assumed to be the right one -- that is for the company to resolve.

v1 boundaries, on purpose:

    OWNER ONLY. "Profile says X, deck says Y" discloses X, and a profile figure
    can be hidden from other viewers. reconcile_profile_with_deck() returns
    nothing for anyone but the document's owner, so a caller cannot leak a
    hidden figure by forgetting a check. Investor visibility is a later PR.

    CALCULATED ON READ. Nothing is stored, so there is no stale finding and no
    semantics version to carry yet.

    THREE NUMERIC PAIRS. The only profile fields with a deck claim category:
        current_revenue      <-> revenue / arr
        team_size            <-> employees / team_size
        prior_amount_raised  <-> funding_raised

Not-comparable is a result, not a failure, and keeps the values it could
identify so later memo or investor work does not have to recompute them:

    profile_blank              the profile field is empty
    profile_zero_may_be_default
                               prior_amount_raised is 0, which is also the
                               model default; nothing records that a founder
                               entered it, so 0 is not evidence of "none"
    profile_period_unknown     the profile's revenue field never says annual or
                               monthly, so no deck revenue figure is comparable
                               to it. Today this is every revenue pair.
    deck_value_unparsed        the deck claim had no numeric value
    conflicting_deck_claims    the deck's own figures disagree; none is chosen
    deck_claim_may_be_the_raise
                               the deck's "funding raised" equals the profile's
                               raise target, the JoyToys misfiling, so it may be
                               the ask rather than money already raised

Dates are what the schema actually has: the profile's last save (the whole
record, not the field) and the deck's upload time. Neither is when a figure was
true, and the owner panel says so.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

CONSISTENT, DIFFERS, NOT_COMPARABLE = 'consistent', 'differs', 'not_comparable'

# Two figures within this relative distance are the same figure. Shared by the
# profile-vs-deck comparison and the deck's agreement with itself.
REL_TOLERANCE = 0.10

# (profile field, label, deck claim categories, kind)
PAIRS = (
    ('current_revenue', 'Revenue', ('revenue', 'arr'), 'money'),
    ('team_size', 'Team size', ('employees', 'team_size'), 'count'),
    ('prior_amount_raised', 'Previously raised', ('funding_raised',), 'money'),
)


@dataclass(frozen=True)
class Reconciliation:
    profile_field: str
    label: str
    kind: str                                  # 'money' | 'count'
    status: str                                # CONSISTENT | DIFFERS | NOT_COMPARABLE
    reason: str = ''                           # set only when NOT_COMPARABLE
    profile_value: Optional[float] = None
    deck_values: Tuple[float, ...] = ()
    deck_claim_ids: Tuple[int, ...] = ()
    profile_saved_at: object = None            # Application.updated_at: the record, not the field
    deck_uploaded_at: object = None            # DocumentSource.created_at

    def display(self, value):
        if value is None:
            return ''
        return f'${value:,.0f}' if self.kind == 'money' else f'{value:,.0f}'

    @property
    def profile_display(self):
        return self.display(self.profile_value)

    @property
    def deck_display(self):
        return ', '.join(self.display(v) for v in self.deck_values)

    @property
    def reason_text(self):
        return REASON_TEXT.get(self.reason, '')


def _agree(a, b):
    if a == b:
        return True
    return abs(a - b) <= REL_TOLERANCE * max(abs(a), abs(b))


def reconcile_profile_with_deck(document, viewer):
    """
    One Reconciliation per pair the deck has a claim for, for the document's
    owner only. Anyone else -- other users, staff, anonymous -- gets [].
    Pairs with no deck claim are omitted: there is nothing to reconcile.
    """
    from .grounded_context import profile_for_document
    from .truth_delta_models import ClaimedDatapoint

    if viewer is None or not getattr(viewer, 'is_authenticated', False) \
            or document.uploaded_by_id != viewer.pk:
        return []
    app = profile_for_document(document)
    if app is None:
        return []

    claims = list(ClaimedDatapoint.objects.filter(document=document).order_by('id'))
    results = []
    for profile_field, label, categories, kind in PAIRS:
        pair_claims = [c for c in claims if c.category in categories]
        if not pair_claims:
            continue
        raw = getattr(app, profile_field, None)
        profile_value = float(raw) if raw is not None else None
        numeric = [c for c in pair_claims if c.claimed_value_numeric is not None]
        deck_values = tuple(c.claimed_value_numeric for c in numeric)
        base = dict(
            profile_field=profile_field, label=label, kind=kind,
            profile_value=profile_value, deck_values=deck_values,
            deck_claim_ids=tuple(c.id for c in numeric),
            profile_saved_at=app.updated_at, deck_uploaded_at=document.created_at,
        )

        def not_comparable(reason):
            return Reconciliation(status=NOT_COMPARABLE, reason=reason, **base)

        if profile_value is None:
            results.append(not_comparable('profile_blank'))
        elif profile_field == 'prior_amount_raised' and profile_value == 0:
            results.append(not_comparable('profile_zero_may_be_default'))
        elif not deck_values:
            results.append(not_comparable('deck_value_unparsed'))
        elif any(not _agree(v, deck_values[0]) for v in deck_values[1:]):
            results.append(not_comparable('conflicting_deck_claims'))
        elif profile_field == 'current_revenue':
            results.append(not_comparable('profile_period_unknown'))
        elif (profile_field == 'prior_amount_raised' and app.raising_amount
              and _agree(deck_values[0], float(app.raising_amount))
              and not _agree(deck_values[0], profile_value)):
            results.append(not_comparable('deck_claim_may_be_the_raise'))
        elif _agree(profile_value, deck_values[0]):
            results.append(Reconciliation(status=CONSISTENT, **base))
        else:
            results.append(Reconciliation(status=DIFFERS, **base))
    return results


# What the owner is told for each not-comparable reason. Neutral: none of these
# is an error, and none says which figure is right.
REASON_TEXT = {
    'profile_blank': 'Your profile leaves this blank, so there is nothing to compare the deck figure with.',
    'profile_zero_may_be_default': (
        'Your profile shows 0, which is also what an unfilled profile shows, so it was not compared.'),
    'profile_period_unknown': (
        "Your profile's revenue doesn't say whether it is annual or monthly, so it was not compared."),
    'deck_value_unparsed': 'Zelda could not read a figure from the deck for this.',
    'conflicting_deck_claims': 'The deck gives more than one figure for this, and they differ.',
    'deck_claim_may_be_the_raise': (
        "The deck's figure matches your raise target, so it may be the amount you are raising "
        'rather than money already raised. It was not compared.'),
}
