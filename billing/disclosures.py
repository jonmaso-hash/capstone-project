"""
The one place the recurring-charge disclosure is written.

It is stated once here so the sentence on the plan card, the sentence beside the
consent checkbox, and the sentence stored on the consent record are the same
sentence. A customer must be able to point at what they agreed to, and the
stored copy has to match what was on screen.

Every customer sees this, regardless of where they are. Federal law is ROSCA
since the FTC's click-to-cancel rule was vacated in July 2025, and the strictest
state rules — California's amended ARL — are the practical floor. Branching on
jurisdiction is not possible at the moment it matters anyway: the disclosure has
to appear *before* payment details are collected, and the authoritative billing
address is only collected during checkout, at Stripe. The jurisdiction is
recorded afterwards, on the consent row, from that billing address.
"""
from .pricing import (
    BUYER_PRICE_USD,
    FIRM_PRICE_USD,
    FOUNDER_PRICE_USD,
    INVESTOR_PRICE_USD,
    SELLER_PRICE_USD,
)

CANCEL_INSTRUCTIONS = "You can cancel any time from Billing in your account settings."

PLAN_PRICES = {
    'FOUNDER_PREMIUM': FOUNDER_PRICE_USD,
    'SELLER_PREMIUM': SELLER_PRICE_USD,
    'INVESTOR_PREMIUM': INVESTOR_PRICE_USD,
    'BUYER_PREMIUM': BUYER_PRICE_USD,
    'INVESTOR_FIRM': FIRM_PRICE_USD,
}


def plan_price_usd(plan):
    return PLAN_PRICES.get(plan, 0)


def renewal_terms(plan):
    """The exact sentence shown before payment, and stored with the consent."""
    price = plan_price_usd(plan)
    interval = 'year' if plan == 'INVESTOR_FIRM' else 'month'
    return (
        f"Renews automatically at ${price} per {interval} until you cancel. "
        f"{CANCEL_INSTRUCTIONS} Cancelling stops the next renewal; you keep access "
        f"until the period you have paid for ends."
    )
