"""
What a Principal may use, decided before anything is retrieved.

Phase 1 Task 2. The line every intelligence operation follows:

    request / task / command -> Principal -> authorize() -> answer or refusal
                                                         -> retrieval / action

This module is a resolver, not an authority. Every answer is a call to a
rule that already exists and still governs its own surface:

    document_visible   document_is_visible_to + the staff-hide rule
    text_documents     raw document text: the owner, or staff
    finding_tier       truth_delta_unlocked, behind document_visible
    ic_memo_visible    can_view_ic_memo
    entity_report_visible  can_view_entity_report
    field_visible      can_view_profile_field

Parity tests hold each answer equal to the rule it wraps, so the two cannot
drift. Two compositions are deliberate and documented where they happen:

- The staff-hide rule (`is_hidden_by_staff`: "hides this document from
  everyone except the owner and staff") is folded into document_visible.
  Until now three views re-checked it by hand; document_is_visible_to alone
  would call a staff-hidden document visible.
- Raw text is owner-and-staff only, the boundary DocumentSearchView and
  DocumentRAGView enforce today (the Nike baseline showed it holding).
  Reaching a document's *reports* is wider (document_visible); reaching its
  *text* is not, and widening it is a product decision, not a side effect.

Authorization is computed live from principal.user on every call; nothing
is cached or snapshotted, so a change to a profile, a connection or a
Premium flag is seen by the next question.
"""
from .principal import require_principal

FULL = 'full'
LITE = 'lite'


def authorize(principal):
    """The resolver for this principal. No principal refuses (PrincipalRequired)."""
    return Authorization(require_principal(principal))


class Authorization:
    """Answers for one principal. Short-lived: build one per operation."""

    __slots__ = ('principal',)

    def __init__(self, principal):
        self.principal = require_principal(principal)

    @property
    def _user(self):
        return self.principal.user

    def _owns_or_staff(self, document):
        user = self._user
        return user.is_staff or document.uploaded_by_id == user.pk

    # -- documents ------------------------------------------------------------

    def text_documents(self):
        """
        The documents whose raw text (chunks) this principal may retrieve, as
        a queryset, so retrieval can filter candidates BEFORE it fetches them.
        Owner or staff. During staff "view as" the principal's user is the
        viewed user, so the staff member's own breadth does not apply.
        """
        from .vector_models import DocumentSource

        if self._user.is_staff:
            return DocumentSource.objects.all()
        return DocumentSource.objects.filter(uploaded_by=self._user)

    def text_permitted(self, document):
        """Per-document form of text_documents()."""
        return self._owns_or_staff(document)

    def document_visible(self, document):
        """
        Whether this principal may reach the document's reports at all.
        document_is_visible_to, plus the staff-hide rule.
        """
        from .document_access import document_is_visible_to

        if not document_is_visible_to(self._user, document):
            return False
        if document.is_hidden_by_staff and not self._owns_or_staff(document):
            return False
        return True

    # -- findings and reports ---------------------------------------------------

    def finding_tier(self, document):
        """
        How much of the document's verification findings this principal gets:
        FULL, LITE, or None when the document is not visible to them at all.
        The tier is truth_delta_unlocked: the document owner's Premium, or staff.
        """
        from .truth_delta_models import truth_delta_unlocked

        if not self.document_visible(document):
            return None
        return FULL if truth_delta_unlocked(self._user, document) else LITE

    def ic_memo_visible(self, founder_application):
        from .ic_memo import can_view_ic_memo

        return can_view_ic_memo(self._user, founder_application)

    def entity_report_visible(self, report):
        from .entity_verification import can_view_entity_report

        return can_view_entity_report(self._user, report)

    # -- profile fields -----------------------------------------------------------

    def field_visible(self, profile, field_name):
        from matchmaking.models import can_view_profile_field

        return can_view_profile_field(self._user, profile, field_name)
