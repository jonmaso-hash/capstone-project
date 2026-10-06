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


def selected_reports(product, selected=()):
    if product in REPORTS:
        return [product]
    if product == 'complete_bundle':
        return list(REPORTS)
    if product == 'three_pack' and isinstance(selected, list):
        if len(selected) == 3 and len(set(selected)) == 3 and all(key in REPORTS for key in selected):
            return sorted(selected)
    raise ValueError('Choose three different reports for the 3-Report Pack.')


def catalog():
    return [
        dict(
            key=key,
            name=value[0],
            amount=value[1],
            price=f'{value[1] / 100:.2f}',
            description=value[2],
        )
        for key, value in PRODUCTS.items()
    ]
