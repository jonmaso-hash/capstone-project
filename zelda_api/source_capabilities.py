"""
What each external source is allowed to establish.

Capability used to live in comments -- `SECFilingsIntegration.extract_customers`
returning None with "Not a standard XBRL concept" is a capability declaration
enforced by nothing. That is how 15 claim categories became 2 populated ones:
each narrowing happened silently because no layer stated what a source could
answer for.

Four roles, and the distinction between the middle two is the point:

    can_establish       authoritative for this claim -- its value may become
                        an ObservedDatapoint
    can_corroborate     may support a claim established elsewhere, but may
                        not be the origin of one
    informational_only  provides context to the analysis and never a claim
    unavailable         cannot speak to this claim at all

Declaration is EXHAUSTIVE. `capability_for` raises on anything undeclared
rather than returning a default, because a default is precisely the silent
narrowing this module exists to stop: the registry would read as complete
while saying nothing about the categories nobody remembered.

Scope note: this covers the categories the pipeline can actually STORE as
observations. `market_size` is deliberately absent -- it is extractable as a
claim and has no observed slot anywhere in `create_observed_datapoints`, so
declaring a source able to establish it would promise evidence the pipeline
has nowhere to put.
"""

CAN_ESTABLISH = 'can_establish'
CAN_CORROBORATE = 'can_corroborate'
INFORMATIONAL_ONLY = 'informational_only'
UNAVAILABLE = 'unavailable'

ROLES = frozenset({CAN_ESTABLISH, CAN_CORROBORATE, INFORMATIONAL_ONLY, UNAVAILABLE})

# The categories create_observed_datapoints can store. Keep in step with it:
# adding a category here without a slot there promises evidence that has
# nowhere to go.
OBSERVABLE_CATEGORIES = ('revenue', 'customers', 'employees', 'funding_raised')

CAPABILITIES = {
    # SEC EDGAR. Revenue comes from XBRL revenue tags and employees from
    # dei:EntityNumberOfEmployees. Customers is not a standard XBRL concept
    # and filings rarely disclose it in structured form; funding-raised is a
    # pitch-deck framing that SEC filers are typically past. Both extractors
    # return None by construction, and the tests hold them to it.
    'sec': {
        'revenue': CAN_ESTABLISH,
        'employees': CAN_ESTABLISH,
        'customers': UNAVAILABLE,
        'funding_raised': UNAVAILABLE,
    },
    # Crunchbase. Not configured -- it charges, and paid sources come last --
    # so nothing here is exercised today. Declared as corroboration rather
    # than establishment on purpose: its figures are aggregated and
    # self-reported upstream, which is a different kind of evidence from a
    # filed financial statement, and the distinction should survive the day
    # the key is added.
    'crunchbase': {
        'revenue': CAN_CORROBORATE,
        'employees': CAN_CORROBORATE,
        'customers': CAN_CORROBORATE,
        'funding_raised': CAN_CORROBORATE,
    },
    # NewsAPI. Live when configured, and every extract_* returns None; its own
    # docstring says headlines are "not a claim source itself". It supplies
    # context to the analysis and never a comparable value.
    'news': {
        'revenue': INFORMATIONAL_ONLY,
        'employees': INFORMATIONAL_ONLY,
        'customers': INFORMATIONAL_ONLY,
        'funding_raised': INFORMATIONAL_ONLY,
    },
}


def capability_for(source_type, category):
    """
    The declared role of `source_type` for `category`.

    Raises KeyError for anything undeclared. That is deliberate: a default
    would let an unknown source, or a category nobody thought about, pass as
    though it had been considered.
    """
    try:
        return CAPABILITIES[source_type][category]
    except KeyError:
        raise KeyError(
            f"No capability declared for source {source_type!r} and category "
            f"{category!r}. Declare it in zelda_api/source_capabilities.py -- "
            f"an undeclared pair is not a default, it is an omission."
        )


def may_establish(source_type, category):
    """Whether this source's value for this category may become evidence."""
    return capability_for(source_type, category) == CAN_ESTABLISH
