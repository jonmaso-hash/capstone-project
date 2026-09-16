# zelda_api/document_access.py
"""
Who may reach a document by its id.

Document ids are sequential integers, so every endpoint that takes one is a
surface someone can walk. PR #57 put the discoverable rule (not private, not
archived, not DENIED) on the routes that look a company up by name; these are
the same rule for the routes that look one up by document id:

- documents/<id>/memo/
- documents/<id>/verification/
- documents/<id>/truth-delta/
- documents/<id>/truth-delta/claims/<category>/flag/

The owner and staff always pass. Anyone else passes only while the business
the document belongs to is discoverable -- the startup for a founder's deck,
the business-for-sale for a seller's. A document whose uploader has no business
profile at all (an investor's own portfolio upload, a roleless user's file) is
owner-and-staff only: without that, the memo endpoint would hand any investor
any other investor's upload.

Callers answer 404, exactly as for a document that isn't there, so a response
never confirms a hidden company exists. Role checks that already answer 403
("you are not an investor") keep doing so -- that reveals nothing about the
company.

Not a relationship gate. An ACCEPTED connection is its own grant: the IC memo
(zelda_api/ic_memo.py::can_view_ic_memo) stays scoped by the introduction, so
an investor already introduced to a founder keeps that access when the founder
later goes private. Going private means "not discoverable to new parties", not
"erase established relationships". These id-walkable surfaces are discovery
surfaces, so they follow visibility even for a connected investor.
"""


def business_is_visible_to(user, subject):
    """Whether `user` may see this business (Application or SellerApplication) at all."""
    from matchmaking.models import Application, SellerApplication, founder_is_visible_to

    if subject is None:
        return False
    if isinstance(subject, Application):
        # The single source of truth for the founder rule, shared with the
        # by-name routes PR #57 fixed.
        return founder_is_visible_to(user, subject)
    if user.is_authenticated and (user == subject.user or user.is_staff):
        return True
    return (
        SellerApplication.objects.discoverable().exclude(review_status='DENIED')
        .filter(pk=subject.pk).exists()
    )


def document_is_visible_to(user, document):
    """
    The owner and staff always; anyone else only while the business this
    document belongs to is discoverable and not DENIED. An uploader with no
    business profile has no discoverable business, so nobody else passes.
    """
    from .entity_verification import subject_for_document

    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user == document.uploaded_by:
        return True
    # Same resolution Entity Integrity uses, so "which business is this
    # document about" has one answer for a user who is both founder and seller.
    return business_is_visible_to(user, subject_for_document(document))
