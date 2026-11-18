"""
The single source of truth for subscription prices.

The per-analysis prices already worked this way -- they live as constants in
zelda_api/quotas.py and reach the page through template variables, so the copy
cannot drift from what the code believes. The five subscription prices did not:
they were plain text in two templates, nine literals in total, with nothing
connecting "$250/mo" on the page to STRIPE_INVESTOR_PRICE_ID in Stripe.

That is a billing-integrity hazard rather than untidiness. A price change
touches two files that do not know about each other, and the failure mode is a
customer reading one number and being charged another. It nearly happened while
configuring Stripe test prices: a proposed $99 Buyer and $499 Firm would have
been created against a page still advertising $250 and $5,000.

Changing a price here changes every page that quotes it. It does NOT change what
Stripe charges -- these amounts must be kept in step with the Stripe prices the
STRIPE_*_PRICE_ID settings point at, which is the one link no amount of Python
can enforce from inside this codebase.
"""

# Individual subscriptions, monthly, in whole US dollars.
FOUNDER_PRICE_USD = 99
SELLER_PRICE_USD = 99

# Investor and Buyer carry the same premium entitlement set -- uncapped intro
# requests, CRM export, priority match alerts, and included monthly business
# valuations -- and are priced together.
INVESTOR_PRICE_USD = 250
BUYER_PRICE_USD = 250

# One flat subscription covering up to Firm.MAX_SEATS verified teammates, each
# with Investor Premium access. At 100 seats that is 100 x $250 = $25,000 of
# individual access, so the firm price is a volume discount rather than an
# independent number: moving it far below this makes a firm cheaper per seat
# than it is worth offering, and cannibalises the individual investor tier.
FIRM_PRICE_USD = 5000

# Investor Firm is closed to new subscriptions until its live Stripe price is
# confirmed. The deployed STRIPE_FIRM_PRICE_ID has not been checked against the
# live catalog, and the code disagreed with itself about the interval: pages
# said "$5,000/mo" while disclosures.renewal_terms said "per year". While this
# is False no page advertises a Firm price and firm checkout refuses to start.
# Existing firms are untouched: their seats, joining a firm, renewals and the
# webhook handling all work as before. Set it to True only after the Stripe
# price behind STRIPE_FIRM_PRICE_ID is confirmed to match FIRM_PRICE_USD and
# its interval, and the copy says that interval.
FIRM_OPEN_FOR_NEW_SUBSCRIPTIONS = False


def firm_open_for_new_subscriptions():
    """Read at call time, so tests and a later change flip it in one place."""
    return FIRM_OPEN_FOR_NEW_SUBSCRIPTIONS


def advertised_plan_price(plan):
    """
    The amount a customer may be told for `plan`, or None when it must not be
    quoted. Firm is not quoted while it is closed (see above), including to an
    existing firm owner, since the interval is the unconfirmed part.
    """
    from .disclosures import plan_price_usd
    if plan == 'INVESTOR_FIRM' and not firm_open_for_new_subscriptions():
        return None
    return plan_price_usd(plan) or None


def subscription_prices():
    """
    Template context for every page that quotes a subscription price.

    One call site per view, so a new pricing surface inherits the values instead
    of restating them. `firm_price` is None while Firm is closed, so a template
    that forgets the `firm_open` check still cannot print the amount.
    """
    firm_open = firm_open_for_new_subscriptions()
    return {
        'founder_price': FOUNDER_PRICE_USD,
        'investor_price': INVESTOR_PRICE_USD,
        'seller_price': SELLER_PRICE_USD,
        'buyer_price': BUYER_PRICE_USD,
        'firm_open': firm_open,
        'firm_price': FIRM_PRICE_USD if firm_open else None,
    }
