"""
Deleting an account, and the Stripe cancellation deleting a role profile shares.

Two phases, with the database commit as the boundary (agreed 2026-09-14).

Before the commit, everything that can refuse runs first -- the firm-owner
check, then cancelling open Stripe subscriptions -- and then the delete itself
runs in one transaction. Any failure in this phase raises DeletionBlocked and
leaves the account exactly as it was. Stripe goes first because a deleted
account must never keep being charged; if the database step then fails, the
subscription stays cancelled and the user is told.

After the commit, stored files (shared_utils/file_cleanup.py), the Stream Chat
identity and the confirmation email run as on_commit callbacks. None of them
can undo the deletion: a failure is logged to ops.FailedTaskLog with only what
a retry needs -- a user id or a storage path -- and staff requeue it from the
ops dashboard.

Django admin cannot delete users (accounts/admin.py), so this module is the
only way an account is deleted: self-serve from Settings, or by staff from the
ops dashboard.
"""
import logging

import stripe
from django.conf import settings
from django.core.mail import send_mail
from django.db import DatabaseError, transaction

from billing.models import Subscription

logger = logging.getLogger(__name__)

STREAM_RETRY_TASK = 'accounts.tasks.delete_stream_user'

# Subscriptions that may still charge: cancelled before anything is deleted.
OPEN_STATUSES = [Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE, Subscription.Status.INCOMPLETE]

SUBSCRIPTION_FAILED = (
    "We couldn't cancel your subscription with our payment provider, so nothing was deleted. "
    "Please try again in a few minutes, or contact us."
)
FIRM_OWNER_WITH_MEMBERS = (
    "This account owns a firm that other members still use, so it can't be deleted yet. "
    "Contact us to transfer or close the firm first."
)
DELETE_FAILED = "Something went wrong and nothing was deleted. Please try again in a few minutes, or contact us."


class DeletionBlocked(Exception):
    """Deletion refused before anything was deleted. `message` is safe to show the user."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def delete_account(user, *, performed_by=None):
    """
    Permanently deletes `user` and everything that cascades from the account.
    Raises DeletionBlocked, with nothing deleted, if a check or the Stripe
    cancellation fails or the database rolls back.
    """
    _refuse_if_firm_owner_with_members(user)
    cancel_subscriptions(user)

    user_id, email, username = user.pk, user.email, user.username
    try:
        with transaction.atomic():
            user.delete()
            # Registered inside the transaction, so a rollback discards them.
            transaction.on_commit(lambda: _remove_stream_identity_or_log(str(user_id)))
            if email:
                transaction.on_commit(lambda: _send_deletion_email(email, username))
    except DatabaseError as exc:
        logger.exception("Account deletion rolled back for user %s", user_id)
        raise DeletionBlocked(DELETE_FAILED) from exc

    if performed_by is not None:
        logger.info("Account %s deleted by staff user %s", user_id, performed_by.pk)
    else:
        logger.info("Account %s deleted by its owner", user_id)


def delete_role_profile(user, profile):
    """
    Deletes one role profile, keeping the account. Its subscription is cancelled
    first through the same path as delete_account, and a firm owner with other
    members can't delete their investor profile, since that ends the firm's plan.
    """
    from matchmaking.models import InvestorApplication

    if isinstance(profile, InvestorApplication):
        _refuse_if_firm_owner_with_members(user)
    cancel_subscriptions(user, plans=_plans_for(profile))
    try:
        with transaction.atomic():
            profile.delete()
    except DatabaseError as exc:
        logger.exception("Profile deletion rolled back for user %s", user.pk)
        raise DeletionBlocked(DELETE_FAILED) from exc


def cancel_subscriptions(user, plans=None):
    """
    Cancels the user's open Stripe subscriptions (only `plans`, if given)
    immediately. Nothing is written locally: Stripe's
    customer.subscription.deleted webhook records the cancellation, as it does
    for a cancellation made in the billing portal. A subscription Stripe no
    longer has counts as cancelled; any other Stripe error raises DeletionBlocked.
    """
    subscriptions = Subscription.objects.filter(user=user, status__in=OPEN_STATUSES).exclude(stripe_subscription_id='')
    if plans is not None:
        subscriptions = subscriptions.filter(plan__in=plans)
    for subscription in subscriptions:
        try:
            stripe.Subscription.cancel(subscription.stripe_subscription_id, api_key=settings.STRIPE_SECRET_KEY)
        except stripe.error.InvalidRequestError as exc:
            if getattr(exc, 'code', None) == 'resource_missing':
                continue
            logger.error("Stripe refused to cancel subscription %s: %s", subscription.stripe_subscription_id, exc)
            raise DeletionBlocked(SUBSCRIPTION_FAILED) from exc
        except stripe.error.StripeError as exc:
            logger.error("Stripe cancellation failed for subscription %s: %s", subscription.stripe_subscription_id, exc)
            raise DeletionBlocked(SUBSCRIPTION_FAILED) from exc


def open_subscriptions(user):
    return Subscription.objects.filter(user=user, status__in=OPEN_STATUSES)


def remove_stream_identity(stream_user_id):
    """
    Hard-deletes one Stream Chat user and the messages they sent. Conversations
    and channels are never deleted: the counterparty's messages and the shared
    deal-room history stay. Raises on failure, so callers can retry.
    """
    if not (settings.STREAM_API_KEY and settings.STREAM_API_SECRET):
        logger.warning("Stream is not configured; no chat identity to remove for user %s", stream_user_id)
        return
    from stream_chat import StreamChat

    client = StreamChat(api_key=settings.STREAM_API_KEY, api_secret=settings.STREAM_API_SECRET)
    client.delete_users([stream_user_id], 'hard', messages='hard')


def _remove_stream_identity_or_log(stream_user_id):
    try:
        remove_stream_identity(stream_user_id)
    except Exception as exc:
        logger.exception("Stream identity removal failed after account deletion; logged for retry")
        from ops.models import log_failed_task
        log_failed_task(STREAM_RETRY_TASK, [stream_user_id], exc.__class__.__name__)


def _send_deletion_email(email, username):
    """Informational only: whether it is delivered never affects the deletion."""
    try:
        send_mail(
            subject="Your Interlink Foundry account has been deleted",
            message=(
                f"Hi {username},\n\n"
                "Your Interlink Foundry account has been deleted, along with its profile, documents and "
                "reports, and any subscription was cancelled.\n\n"
                f"If you didn't ask for this, contact us right away at {settings.SITE_URL}/contact/.\n\n"
                "Interlink Foundry"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Account deletion email could not be sent")


def _refuse_if_firm_owner_with_members(user):
    from matchmaking.models import Firm

    for firm in Firm.objects.filter(owner=user):
        if firm.memberships.exclude(user=user).exists():
            raise DeletionBlocked(FIRM_OWNER_WITH_MEMBERS)


def _plans_for(profile):
    from matchmaking.models import Application, BuyerApplication, InvestorApplication, SellerApplication

    return {
        Application: [Subscription.Plan.FOUNDER_PREMIUM],
        InvestorApplication: [Subscription.Plan.INVESTOR_PREMIUM, Subscription.Plan.INVESTOR_FIRM],
        SellerApplication: [Subscription.Plan.SELLER_PREMIUM],
        BuyerApplication: [Subscription.Plan.BUYER_PREMIUM],
    }[type(profile)]
