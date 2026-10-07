"""The seven one-time Zelda products sold in the hub. Amounts are USD cents."""

REPORTS = {
    'intelligence_memo': (
        'Zelda Intelligence Memo',
        199,
        'A concise orientation memo from Zelda: what the evidence says, what Zelda noticed, and what is worth investigating next.',
    ),
    'ic_memo': (
        'Zelda IC Memo',
        499,
        'An investment-committee memo grounded in the evidence you provide: business, market, team, financials, risks and questions for management.',
    ),
    'truth_delta': (
        'Truth Delta Report',
        1999,
        'Checks document claims against available external evidence, keeping contradictions, missing evidence and unavailable sources distinct.',
    ),
    'entity': (
        'Entity Integrity Report',
        999,
        'Public company identity and registration evidence. Missing public records do not mean a business is false or illegitimate.',
    ),
    'valuation': (
        'Business valuation',
        99,
        'A model-based business valuation, with financial context, assumptions and limitations. Not an appraisal or transaction price.',
    ),
}

PRODUCTS = {
    'intelligence_memo': REPORTS['intelligence_memo'],
    'ic_memo': REPORTS['ic_memo'],
    'truth_delta': REPORTS['truth_delta'],
    'complete_bundle': (
        'Zelda Complete Intelligence Bundle',
        4999,
        'All five individual Zelda reports for one company and evidence set, saved together in your Library.',
    ),
    'three_pack': (
        'Zelda 3-Report Pack',
        2499,
        'Choose any three of the five individual Zelda reports for one company and evidence set.',
    ),
    'entity': REPORTS['entity'],
    'valuation': REPORTS['valuation'],
}

DILIGENCE_PRODUCTS = {
    'truth_delta_diligence': (
        'Truth Delta Report',
        1000,
        'One Truth Delta report for an investor or buyer evaluating a company.',
    ),
    'truth_delta_credit_pack': (
        'Truth Delta 3-Report Credit Pack',
        2500,
        'Three reusable Truth Delta credits. Redeem one credit for one new Truth Delta report on any company you evaluate.',
    ),
}

ALL_STRIPE_PRODUCTS = {**PRODUCTS, **DILIGENCE_PRODUCTS}


def diligence_catalog():
    return sorted(
        [
            dict(
                key=key,
                name=value[0],
                amount=value[1],
                price=f'{value[1] / 100:.2f}',
                description=value[2],
            )
            for key, value in DILIGENCE_PRODUCTS.items()
        ],
        key=lambda product: (product['amount'], product['name']),
    )


def role_catalog(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return catalog()
    investor_profile = getattr(user, 'match_investor_profile', None)
    buyer_profile = getattr(user, 'match_buyer_profile', None)
    if investor_profile is not None or buyer_profile is not None:
        return diligence_catalog()
    return catalog()



def selected_reports(product, selected=()):
    if product == 'truth_delta_diligence':
        return ['truth_delta']
    if product in REPORTS:
        return [product]
    if product == 'complete_bundle':
        return list(REPORTS)
    if product == 'three_pack' and isinstance(selected, list):
        if len(selected) == 3 and len(set(selected)) == 3 and all(key in REPORTS for key in selected):
            return sorted(selected)
    raise ValueError('Choose three different reports for the 3-Report Pack.')


def catalog():
    return sorted(
        [
            dict(
                key=key,
                name=value[0],
                amount=value[1],
                price=f'{value[1] / 100:.2f}',
                description=value[2],
            )
            for key, value in PRODUCTS.items()
        ],
        key=lambda product: (product['amount'], product['name']),
    )


def catalog_with_purchase_state(user):
    """Founder-workspace catalog annotated from the user's actual paid orders.

    Individual reports count as purchased whether bought alone or inside a
    pack/bundle. Package cards count only direct purchases of that package.
    paid_at is the purchase/update timestamp because Stripe payment is the
    authoritative point at which the user bought the new report run.
    """
    products = catalog()
    if not user or not getattr(user, 'is_authenticated', False):
        return products

    from .models import ZeldaOrder

    orders = list(
        ZeldaOrder.objects.filter(user=user, paid_at__isnull=False)
        .only('product', 'reports', 'paid_at')
        .order_by('-paid_at')
    )
    latest_report_purchase = {}
    latest_product_purchase = {}
    for order in orders:
        latest_product_purchase.setdefault(order.product, order.paid_at)
        for report_key in order.reports or []:
            latest_report_purchase.setdefault(report_key, order.paid_at)

    for product in products:
        key = product['key']
        if key in REPORTS:
            purchased_at = latest_report_purchase.get(key)
            product['purchase_kind'] = 'report'
        else:
            purchased_at = latest_product_purchase.get(key)
            product['purchase_kind'] = 'package'
        product['purchased'] = purchased_at is not None
        product['last_purchased_at'] = purchased_at
        if purchased_at:
            product['cta_label'] = 'Update reports' if product['purchase_kind'] == 'package' else 'Update report'
        else:
            product['cta_label'] = 'Buy package' if product['purchase_kind'] == 'package' else 'Create report'
    return products
