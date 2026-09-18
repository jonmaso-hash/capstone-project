"""
Written confirmation of what a subscription costs and how it ends.

`billing/` sent no email at all before this. Stripe sends a card receipt, which
is not the same thing: it does not say what the plan includes, when it renews,
or how to stop it — and Stripe sends nothing at all when a subscription is
cancelled, which is the message customers most often say they never received.

Sending is best-effort: a mail failure must never make a cancellation look like
it failed, because the cancellation has already happened at Stripe by then.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

from .disclosures import CANCEL_INSTRUCTIONS, plan_price_usd

logger = logging.getLogger(__name__)


def _date(value):
    """'March 04, 2026' — %-d is not portable to Windows, so no day-stripping."""
    return f"{value:%B %d, %Y}" if value else None


def _send(subscription, subject, lines):
    recipient = (subscription.user.email or '').strip()
    if not recipient:
        logger.info("No email on record for user %s; skipping %r", subscription.user_id, subject)
        return False
    try:
        send_mail(subject, "\n".join(lines), settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
        return True
    except Exception:
        # The subscription change already happened at Stripe. Losing the email
        # is bad; pretending the change failed would be worse.
        logger.exception("Subscription email %r could not be sent to user %s", subject, subscription.user_id)
        return False


def send_subscription_started_email(subscription):
    """What they bought, what it costs each month, when it renews, how to stop."""
    renews = _date(subscription.current_period_end)
    lines = [
        f"Hi {subscription.user.username},",
        "",
        f"Your {subscription.get_plan_display()} subscription is active.",
        "",
        f"Amount: ${plan_price_usd(subscription.plan)} per month.",
        "This subscription renews automatically each month until you cancel.",
    ]
    if renews:
        lines.append(f"Next renewal: {renews}.")
    lines += [
        "",
        CANCEL_INSTRUCTIONS,
        "Cancelling stops the next renewal; you keep access until the period you have paid for ends.",
        "",
        "— Interlink Foundry",
    ]
    return _send(subscription, "Your Interlink Foundry subscription is active", lines)


def send_subscription_cancelled_email(subscription):
    """What ends, and exactly when it stops."""
    ends = _date(subscription.current_period_end)
    lines = [
        f"Hi {subscription.user.username},",
        "",
        f"Your {subscription.get_plan_display()} subscription has been cancelled and will not renew.",
        (f"You keep access until {ends}, the end of the period you have already paid for."
         if ends else "You keep access until the end of the period you have already paid for."),
        "You will not be charged again.",
        "",
        "If you cancelled by mistake, you can subscribe again from Billing in your account settings.",
        "",
        "— Interlink Foundry",
    ]
    return _send(subscription, "Your Interlink Foundry subscription has been cancelled", lines)
