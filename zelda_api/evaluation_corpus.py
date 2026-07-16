# zelda_api/evaluation_corpus.py
"""
Manually annotated evaluation corpus for claim-extraction quality —
measures ZeldaIntelligencePipelineV2's claim extraction (_analyze_document
-> extract_claims_from_insights), not Truth Delta's verification judgment.
Run via: python manage.py evaluate_claim_extraction

Sourcing note: genuinely private, confidential startup pitch decks aren't
something this tool has access to (that's the whole point of a pitch
deck being private) or a right to redistribute if it did. 6 of these 25
documents instead use REAL, publicly-traded companies with real,
approximately-accurate figures (in the same spirit as the live Apple
Truth Delta demo) — legitimate to reference since these are public
companies whose investor materials are meant for public consumption, and
SEC EDGAR can genuinely verify them. The remaining 19 are realistic
synthetic documents authored specifically to probe known failure
patterns: the exact fabrication bug just fixed, cross-category number
contamination, ambiguous units, spelled-out numbers, ranges, and
narrative-only documents with zero numeric claims.

Every document is annotated for all 8 extraction categories
(Problem/Market/Revenue/Team/Product/Traction/Funding/Risk), not just the
numeric ones Truth Delta consumes, for a complete precision/recall
picture of the whole pipeline — not just its numeric subset.
"""

ALL_CATEGORIES = ['Problem', 'Market', 'Revenue', 'Team', 'Product', 'Traction', 'Funding', 'Risk']


def _doc(doc_id, company_name, text, claims, is_real_public_company=False):
    """
    claims: {category: (expected_numeric_or_None, note)} for categories
    that SHOULD be extracted. Every category in ALL_CATEGORIES not listed
    here is assumed should_extract=False by default.
    """
    annotations = []
    for category in ALL_CATEGORIES:
        if category in claims:
            numeric, note = claims[category]
            annotations.append({'category': category, 'should_extract': True, 'expected_numeric': numeric, 'note': note})
        else:
            annotations.append({'category': category, 'should_extract': False, 'expected_numeric': None, 'note': 'Not genuinely supported by the document.'})
    return {'id': doc_id, 'company_name': company_name, 'is_real_public_company': is_real_public_company, 'text': text, 'annotations': annotations}


CORPUS = [
    # --- Real public companies (SEC EDGAR-verifiable) ---
    _doc(
        'real_apple_revenue', 'Apple Inc.',
        "Apple Inc. generated approximately $416 billion in revenue for fiscal year 2025, "
        "driven by strong iPhone, Services, and Mac performance across all geographic segments.",
        {'Revenue': (416_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True,
    ),
    _doc(
        'real_microsoft_revenue', 'Microsoft Corporation',
        "Microsoft Corporation posted revenue of roughly $270 billion for its most recent fiscal year, "
        "led by growth in Azure, Microsoft 365, and LinkedIn.",
        {'Revenue': (270_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True,
    ),
    _doc(
        'real_nike_revenue', 'Nike, Inc.',
        "Nike, Inc. reported total fiscal-year revenue of approximately $46 billion across its "
        "Nike Direct and wholesale channels worldwide.",
        {'Revenue': (46_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True,
    ),
    _doc(
        'real_starbucks_revenue_and_headcount_trap', 'Starbucks Corporation',
        "Starbucks Corporation generated approximately $36 billion in revenue last fiscal year. "
        "The company now employs over 380,000 partners worldwide across its company-operated and licensed stores.",
        {'Revenue': (36_000_000_000, 'Explicit revenue figure stated')},
        # Deliberately no Team claim expected: Starbucks calls its workforce
        # "partners," not "employees" — the Team fallback regex only
        # matches the literal word "employees," so a real, human-readable
        # headcount claim here is expected to be genuinely present but
        # likely MISSED by the extractor. Ground truth says it should be
        # extracted; the eval is expected to surface this as a recall gap.
        is_real_public_company=True,
    ),
    _doc(
        'real_cocacola_revenue_with_adspend_trap', 'The Coca-Cola Company',
        "The Coca-Cola Company reported net operating revenue of approximately $47 billion. "
        "Separately, the company disclosed roughly $5 billion in annual global marketing and advertising spend.",
        {'Revenue': (47_000_000_000, 'Explicit revenue figure stated — the $5B marketing figure is a decoy, not revenue')},
        is_real_public_company=True,
    ),
    _doc(
        'real_costco_revenue_and_cardholder_trap', 'Costco Wholesale Corporation',
        "Costco Wholesale Corporation generated approximately $255 billion in revenue in its latest fiscal year. "
        "Costco now counts over 130 million cardholders across its global membership base.",
        {'Revenue': (255_000_000_000, 'Explicit revenue figure stated')},
        # Deliberately no Traction claim expected to be caught cleanly:
        # "cardholders" isn't in the Traction regex's word list
        # (customers?|users?|companies?|clients?) — a real membership
        # count that a human would recognize as traction, but the
        # extractor's fixed vocabulary is expected to miss it.
        is_real_public_company=True,
    ),

    # --- Synthetic: clean single-category claims ---
    _doc(
        'nimbus_revenue_only', 'Nimbus Analytics',
        "Nimbus Analytics generated $2.4 million in revenue last year, driven by its core data "
        "pipeline product sold to mid-market logistics companies. The founding team has bootstrapped "
        "the business without taking outside funding to date.",
        {'Revenue': (2_400_000, 'Explicit revenue figure, no funding mentioned anywhere')},
    ),
    _doc(
        'kestrel_funding_only', 'Kestrel Robotics',
        "Kestrel Robotics raised $8 million in Series A funding led by a specialist deep-tech fund. "
        "The company has not yet disclosed revenue figures publicly.",
        {'Funding': (8_000_000, 'Explicit funding figure with clear Series A context')},
    ),
    _doc(
        'bramblewood_revenue_and_funding', 'Bramblewood Foods',
        "Bramblewood Foods generated $6.1 million in revenue last year and separately closed a "
        "$4 million seed round earlier this year to expand its distribution network.",
        {
            'Revenue': (6_100_000, 'Explicit revenue figure'),
            'Funding': (4_000_000, 'Explicit, separate funding figure with seed-round context'),
        },
    ),
    _doc(
        'ironwood_team_only', 'Ironwood Logistics',
        "Ironwood Logistics is a freight-matching platform for regional trucking fleets. "
        "The company now employs 58 employees across engineering, operations, and sales.",
        {'Team': (58, 'Explicit headcount figure using the literal word "employees"')},
    ),
    _doc(
        'marrow_traction_only', 'Marrow Biotech',
        "Marrow Biotech provides lab-management software to biotech research teams. "
        "The platform now serves 340 enterprise customers across North America and Europe.",
        {'Traction': (340, 'Explicit customer count using the literal word "customers"')},
    ),

    # --- Synthetic: narrative-only, zero numeric claims (precision stress test) ---
    _doc(
        'petrichor_narrative_only', 'Petrichor Media',
        "The video ad market is fragmented, forcing publishers to juggle a dozen disconnected tools "
        "just to run a single campaign. Petrichor Media centralizes ad operations onto one platform, "
        "giving publishers a single dashboard for the entire workflow. Our biggest risk is competition "
        "from larger ad-tech incumbents entering the same space.",
        {
            'Problem': (None, 'Genuine "fragmented" problem statement present'),
            'Product': (None, 'Genuine "centralizes...one platform" product statement present'),
            'Risk': (None, 'Genuine competitive-risk statement present'),
        },
        # No numeric figures anywhere in the document at all — every
        # numeric category (Revenue/Funding/Team/Traction/Market) must
        # come back empty. This is the cleanest possible test of the
        # fabrication fix: a document engineered to have nothing
        # extractable in those categories, on purpose.
    ),

    # --- Synthetic: format/phrasing edge cases (recall stress tests) ---
    _doc(
        'thistledown_percentage_growth', 'Thistledown Analytics',
        "Thistledown Analytics has seen 212% year-over-year growth in its customer base, with no "
        "paid marketing spend to date.",
        {'Traction': (212, 'Growth percentage is a legitimate traction claim, no dollar figure involved')},
    ),
    _doc(
        'whitmore_seed_capital_phrasing', 'Whitmore Freight',
        "Whitmore Freight secured $2 million in seed capital last quarter from a group of logistics-focused angels.",
        {'Funding': (2_000_000, 'Explicit funding figure using "seed capital" phrasing rather than "Series"')},
    ),
    _doc(
        'auric_cross_contamination_stress_test', 'Auric Data',
        "Auric Data's platform processes 40,000 transactions daily for its retail clients. The company "
        "closed a $6 million seed round in March, backed by two firms that together manage over $500 "
        "million in assets.",
        {
            'Traction': (40_000, 'Explicit daily transaction volume'),
            'Funding': (6_000_000, 'The genuine funding figure — must not be confused with the 40,000 transaction count or the $500M AUM figure, neither of which is Auric\'s own funding'),
        },
    ),
    _doc(
        'cormorant_revenue_range', 'Cormorant Systems',
        "Cormorant Systems' revenue this year is tracking between $3 million and $5 million, "
        "depending on how the final two enterprise deals close.",
        {'Revenue': (3_000_000, 'Revenue range stated — a real claim, though the extractor is expected to struggle with range formatting; lower bound used as the expected value')},
    ),
    _doc(
        'driftwood_spelled_out_headcount', 'Driftwood Insurance',
        "Driftwood Insurance is a team of twelve employees working out of a single office in Denver.",
        {'Team': (12, 'Headcount spelled out as a word ("twelve") rather than a digit — a real claim the digit-only regex is expected to miss entirely')},
    ),
    _doc(
        'halcyon_comma_formatted_users', 'Halcyon Textiles',
        "Halcyon Textiles now serves 15,000 registered users across six countries through its "
        "direct-to-consumer platform.",
        {'Traction': (15_000, 'Explicit, comma-formatted user count')},
    ),
    _doc(
        'ember_market_size_only', 'Ember Systems',
        "Ember Systems is targeting a $50 billion global addressable market in industrial IoT sensors.",
        {'Market': (50_000_000_000, 'Explicit market-size figure with clear TAM framing')},
    ),
    _doc(
        'palisade_headcount_in_noisy_sentence', 'Palisade Robotics',
        "Founded in a garage in 2019 by two engineers, Palisade Robotics has since scaled its "
        "operations, opened a second facility, and now counts 27 full-time employees among its ranks.",
        {'Team': (27, 'Genuine headcount figure buried in a long, noisy sentence — tests extraction robustness to sentence length')},
    ),
    _doc(
        'vantage_funding_range', 'Vantage Point Energy',
        "Vantage Point Energy raised between $1 million and $2 million from angel investors in its "
        "pre-seed round earlier this year.",
        {'Funding': (1_000_000, 'Funding range stated — lower bound used as the expected value; extractor is expected to struggle with range formatting')},
    ),
    _doc(
        'larkspur_team_and_traction_together', 'Larkspur Financial',
        "Larkspur Financial employs 95 people and serves 4,200 active customers across the Southeast.",
        {
            'Team': (95, 'Explicit headcount figure'),
            'Traction': (4_200, 'Explicit customer count in the same sentence as the headcount figure'),
        },
    ),

    # --- Synthetic: false-positive traps (precision stress tests) ---
    _doc(
        'solstice_competitor_revenue_trap', 'Solstice Health',
        "Our largest competitor reported $200 million in revenue last year, while we are just "
        "getting started in this market. Solstice Health has not yet publicly disclosed its own revenue figures.",
        {},
        # No Revenue claim expected: the only dollar figure in the
        # document belongs to a NAMED COMPETITOR, not Solstice Health
        # itself. This is a genuinely hard case (the sentence contains
        # the word "revenue" and a dollar figure, which is exactly what
        # the keyword+number matching logic looks for) — expected to
        # reveal a real, still-open precision gap: the extractor has no
        # entity attribution, so it likely misattributes the competitor's
        # revenue as the company's own claim.
    ),
    _doc(
        'quillfeather_customer_spend_trap', 'Quillfeather Media',
        "Our top customer's internal marketing budget is $4 million per year, and they've told us "
        "we're now roughly 30% of that spend.",
        {},
        # No Revenue claim expected: $4M is a CUSTOMER's budget, not
        # Quillfeather's own revenue. Another entity-attribution trap.
    ),
    _doc(
        'foxglove_funding_keyword_no_number', 'Foxglove Dynamics',
        "We're proud to have closed our Series A this quarter with participation from strategic partners.",
        {},
        # No Funding claim expected: strong funding-context keywords
        # ("Series A", "closed") but zero dollar figure anywhere in the
        # sentence. Tests that keyword presence alone, without a number,
        # doesn't produce a numeric funding claim.
    ),
]
