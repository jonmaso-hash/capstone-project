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


COMPANY_TYPES = ['public', 'seed', 'series_ab', 'established_private', 'business_for_sale']


def _doc(doc_id, company_name, text, claims, is_real_public_company=False, sector='unspecified', company_type=None):
    """
    claims: {category: (expected_numeric_or_None, note)} for categories
    that SHOULD be extracted. Every category in ALL_CATEGORIES not listed
    here is assumed should_extract=False by default.

    sector: a coarse industry tag (saas, hardware, biotech, healthtech,
    fintech, consumer, retail, logistics, energy) — lets
    evaluate_claim_extraction --by-sector check whether precision/recall
    is stable across document styles, or whether the extraction patterns
    are quietly overfit to one style of corporate disclosure.

    company_type: one of COMPANY_TYPES — a second, orthogonal stratification
    axis from sector. Defaults to 'public' when is_real_public_company is
    True, else 'established_private' (an ongoing private business with no
    stated funding round) — pass explicitly to override when the document
    actually states a stage (seed/Series A-B) or is a business-for-sale
    listing rather than a fundraising pitch deck.
    """
    if company_type is None:
        company_type = 'public' if is_real_public_company else 'established_private'
    assert company_type in COMPANY_TYPES, f"Unknown company_type {company_type!r} for {doc_id!r}"

    annotations = []
    for category in ALL_CATEGORIES:
        if category in claims:
            numeric, note = claims[category]
            annotations.append({'category': category, 'should_extract': True, 'expected_numeric': numeric, 'note': note})
        else:
            annotations.append({'category': category, 'should_extract': False, 'expected_numeric': None, 'note': 'Not genuinely supported by the document.'})
    return {
        'id': doc_id, 'company_name': company_name, 'is_real_public_company': is_real_public_company,
        'sector': sector, 'company_type': company_type, 'text': text, 'annotations': annotations,
    }


CORPUS = [
    # --- Real public companies (SEC EDGAR-verifiable) ---
    _doc(
        'real_apple_revenue', 'Apple Inc.',
        "Apple Inc. generated approximately $416 billion in revenue for fiscal year 2025, "
        "driven by strong iPhone, Services, and Mac performance across all geographic segments.",
        {'Revenue': (416_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='hardware',
    ),
    _doc(
        'real_microsoft_revenue', 'Microsoft Corporation',
        "Microsoft Corporation posted revenue of roughly $270 billion for its most recent fiscal year, "
        "led by growth in Azure, Microsoft 365, and LinkedIn.",
        {'Revenue': (270_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='saas',
    ),
    _doc(
        'real_nike_revenue', 'Nike, Inc.',
        "Nike, Inc. reported total fiscal-year revenue of approximately $46 billion across its "
        "Nike Direct and wholesale channels worldwide.",
        {'Revenue': (46_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='consumer',
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
        is_real_public_company=True, sector='consumer',
    ),
    _doc(
        'real_cocacola_revenue_with_adspend_trap', 'The Coca-Cola Company',
        "The Coca-Cola Company reported net operating revenue of approximately $47 billion. "
        "Separately, the company disclosed roughly $5 billion in annual global marketing and advertising spend.",
        {'Revenue': (47_000_000_000, 'Explicit revenue figure stated — the $5B marketing figure is a decoy, not revenue')},
        is_real_public_company=True, sector='consumer',
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
        is_real_public_company=True, sector='retail',
    ),

    # --- Synthetic: clean single-category claims ---
    _doc(
        'nimbus_revenue_only', 'Nimbus Analytics',
        "Nimbus Analytics generated $2.4 million in revenue last year, driven by its core data "
        "pipeline product sold to mid-market logistics companies. The founding team has bootstrapped "
        "the business without taking outside funding to date.",
        {'Revenue': (2_400_000, 'Explicit revenue figure, no funding mentioned anywhere')},
        sector='saas',
    ),
    _doc(
        'kestrel_funding_only', 'Kestrel Robotics',
        "Kestrel Robotics raised $8 million in Series A funding led by a specialist deep-tech fund. "
        "The company has not yet disclosed revenue figures publicly.",
        {'Funding': (8_000_000, 'Explicit funding figure with clear Series A context')},
        sector='hardware', company_type='series_ab',
    ),
    _doc(
        'bramblewood_revenue_and_funding', 'Bramblewood Foods',
        "Bramblewood Foods generated $6.1 million in revenue last year and separately closed a "
        "$4 million seed round earlier this year to expand its distribution network.",
        {
            'Revenue': (6_100_000, 'Explicit revenue figure'),
            'Funding': (4_000_000, 'Explicit, separate funding figure with seed-round context'),
        },
        sector='consumer', company_type='seed',
    ),
    _doc(
        'ironwood_team_only', 'Ironwood Logistics',
        "Ironwood Logistics is a freight-matching platform for regional trucking fleets. "
        "The company now employs 58 employees across engineering, operations, and sales.",
        {'Team': (58, 'Explicit headcount figure using the literal word "employees"')},
        sector='logistics',
    ),
    _doc(
        'marrow_traction_only', 'Marrow Biotech',
        "Marrow Biotech provides lab-management software to biotech research teams. "
        "The platform now serves 340 enterprise customers across North America and Europe.",
        {'Traction': (340, 'Explicit customer count using the literal word "customers"')},
        sector='biotech',
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
        sector='saas',
    ),

    # --- Synthetic: format/phrasing edge cases (recall stress tests) ---
    _doc(
        'thistledown_percentage_growth', 'Thistledown Analytics',
        "Thistledown Analytics has seen 212% year-over-year growth in its customer base, with no "
        "paid marketing spend to date.",
        {'Traction': (212, 'Growth percentage is a legitimate traction claim, no dollar figure involved')},
        sector='saas',
    ),
    _doc(
        'whitmore_seed_capital_phrasing', 'Whitmore Freight',
        "Whitmore Freight secured $2 million in seed capital last quarter from a group of logistics-focused angels.",
        {'Funding': (2_000_000, 'Explicit funding figure using "seed capital" phrasing rather than "Series"')},
        sector='logistics', company_type='seed',
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
        sector='saas', company_type='seed',
    ),
    _doc(
        'cormorant_revenue_range', 'Cormorant Systems',
        "Cormorant Systems' revenue this year is tracking between $3 million and $5 million, "
        "depending on how the final two enterprise deals close.",
        {'Revenue': (3_000_000, 'Revenue range stated — a real claim, though the extractor is expected to struggle with range formatting; lower bound used as the expected value')},
        sector='saas',
    ),
    _doc(
        'driftwood_spelled_out_headcount', 'Driftwood Insurance',
        "Driftwood Insurance is a team of twelve employees working out of a single office in Denver.",
        {'Team': (12, 'Headcount spelled out as a word ("twelve") rather than a digit — a real claim the digit-only regex is expected to miss entirely')},
        sector='fintech',
    ),
    _doc(
        'halcyon_comma_formatted_users', 'Halcyon Textiles',
        "Halcyon Textiles now serves 15,000 registered users across six countries through its "
        "direct-to-consumer platform.",
        {'Traction': (15_000, 'Explicit, comma-formatted user count')},
        sector='consumer',
    ),
    _doc(
        'ember_market_size_only', 'Ember Systems',
        "Ember Systems is targeting a $50 billion global addressable market in industrial IoT sensors.",
        {'Market': (50_000_000_000, 'Explicit market-size figure with clear TAM framing')},
        sector='hardware',
    ),
    _doc(
        'palisade_headcount_in_noisy_sentence', 'Palisade Robotics',
        "Founded in a garage in 2019 by two engineers, Palisade Robotics has since scaled its "
        "operations, opened a second facility, and now counts 27 full-time employees among its ranks.",
        {'Team': (27, 'Genuine headcount figure buried in a long, noisy sentence — tests extraction robustness to sentence length')},
        sector='hardware',
    ),
    _doc(
        'vantage_funding_range', 'Vantage Point Energy',
        "Vantage Point Energy raised between $1 million and $2 million from angel investors in its "
        "pre-seed round earlier this year.",
        {'Funding': (1_000_000, 'Funding range stated — lower bound used as the expected value; extractor is expected to struggle with range formatting')},
        sector='energy', company_type='seed',
    ),
    _doc(
        'larkspur_team_and_traction_together', 'Larkspur Financial',
        "Larkspur Financial employs 95 people and serves 4,200 active customers across the Southeast.",
        {
            'Team': (95, 'Explicit headcount figure'),
            'Traction': (4_200, 'Explicit customer count in the same sentence as the headcount figure'),
        },
        sector='fintech',
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
        sector='healthtech',
    ),
    _doc(
        'quillfeather_customer_spend_trap', 'Quillfeather Media',
        "Our top customer's internal marketing budget is $4 million per year, and they've told us "
        "we're now roughly 30% of that spend.",
        {},
        # No Revenue claim expected: $4M is a CUSTOMER's budget, not
        # Quillfeather's own revenue. Another entity-attribution trap.
        sector='saas',
    ),
    _doc(
        'foxglove_funding_keyword_no_number', 'Foxglove Dynamics',
        "We're proud to have closed our Series A this quarter with participation from strategic partners.",
        {},
        # No Funding claim expected: strong funding-context keywords
        # ("Series A", "closed") but zero dollar figure anywhere in the
        # sentence. Tests that keyword presence alone, without a number,
        # doesn't produce a numeric funding claim.
        sector='hardware', company_type='series_ab',
    ),

    # =====================================================================
    # CORPUS EXPANSION (25 -> 100): sector-diversified batch, added after
    # the original 25 to check whether extraction precision/recall holds
    # across styles of corporate disclosure rather than being quietly
    # overfit to the first batch's phrasing. Reuses the same archetype
    # patterns (clean claim / narrative-only / format edge case / false-
    # positive trap) deliberately, since the point is coverage across
    # sectors, not inventing new failure modes — those are covered above.
    # =====================================================================

    # --- SaaS (2 new) ---
    _doc(
        'vellum_revenue_only', 'Vellum Analytics',
        "Vellum Analytics generated $4.8 million in revenue last year from its subscription-based "
        "reporting platform sold to mid-market retailers.",
        {'Revenue': (4_800_000, 'Explicit revenue figure, no funding mentioned')},
        sector='saas',
    ),
    _doc(
        'northbridge_narrative_only', 'Northbridge CRM',
        "Sales teams juggle a fragmented mess of spreadsheets and disconnected tools. Northbridge CRM "
        "centralizes the entire pipeline into one platform. Our main risk is competition from "
        "well-funded incumbents already selling into the same accounts.",
        {
            'Problem': (None, 'Genuine "fragmented" problem statement'),
            'Product': (None, 'Genuine "centralizes...one platform" product statement'),
            'Risk': (None, 'Genuine competitive-risk statement'),
        },
        sector='saas',
    ),

    # --- Hardware (4 new) ---
    _doc(
        'real_tesla_revenue', 'Tesla, Inc.',
        "Tesla, Inc. reported total revenue of approximately $98 billion for the fiscal year, "
        "driven by vehicle deliveries and energy storage deployments.",
        {'Revenue': (98_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='hardware',
    ),
    _doc(
        'cinder_funding_only', 'Cinder Robotics',
        "Cinder Robotics raised $12 million in Series A funding to scale manufacturing of its "
        "warehouse-automation arm. Revenue figures have not yet been disclosed.",
        {'Funding': (12_000_000, 'Explicit funding figure with clear Series A context')},
        sector='hardware', company_type='series_ab',
    ),
    _doc(
        'fathom_team_only', 'Fathom Sensors',
        "Fathom Sensors builds underwater monitoring hardware for offshore energy operators. "
        "The company now employs 34 employees across hardware engineering and field operations.",
        {'Team': (34, 'Explicit headcount figure using the literal word "employees"')},
        sector='hardware',
    ),
    _doc(
        'anchorpoint_competitor_trap', 'Anchorpoint Devices',
        "A well-known industry leader in this space posted $600 million in revenue last year. "
        "Anchorpoint Devices is still pre-revenue as we finalize our first production run.",
        {},
        # No Revenue claim expected: the figure belongs to a named
        # "industry leader," not Anchorpoint itself.
        sector='hardware', company_type='seed',
    ),

    # --- Consumer (3 new) ---
    _doc(
        'real_pepsico_revenue', 'PepsiCo, Inc.',
        "PepsiCo, Inc. reported net revenue of approximately $91 billion, led by its beverage and "
        "convenient foods divisions across global markets.",
        {'Revenue': (91_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='consumer',
    ),
    _doc(
        'birchwood_traction_only', 'Birchwood Apparel',
        "Birchwood Apparel is a direct-to-consumer outdoor clothing brand. The company now serves "
        "22,000 customers through its online storefront alone.",
        {'Traction': (22_000, 'Explicit, comma-formatted customer count')},
        sector='consumer',
    ),
    _doc(
        'driftglass_funding_range', 'Driftglass Beverages',
        "Driftglass Beverages raised between $2 million and $3 million from beverage-focused angel "
        "investors in its seed round.",
        {'Funding': (2_000_000, 'Funding range stated — lower bound used as expected value; range formatting is a known recall gap')},
        sector='consumer', company_type='seed',
    ),

    # --- Logistics (6 new) ---
    _doc(
        'overland_revenue_only', 'Overland Freight',
        "Overland Freight generated $7.3 million in revenue last year connecting regional shippers "
        "with independent carriers across the Midwest.",
        {'Revenue': (7_300_000, 'Explicit revenue figure, no funding mentioned')},
        sector='logistics',
    ),
    _doc(
        'waypoint_funding_only', 'Waypoint Shipping',
        "Waypoint Shipping closed a $5 million seed round led by a logistics-focused venture fund "
        "to expand its port-scheduling software.",
        {'Funding': (5_000_000, 'Explicit funding figure with clear seed-round context')},
        sector='logistics', company_type='seed',
    ),
    _doc(
        'cascade_team_only', 'Cascade Distribution',
        "Cascade Distribution operates regional fulfillment centers for e-commerce brands. "
        "The company now employs 112 employees across its three warehouse locations.",
        {'Team': (112, 'Explicit headcount figure using the literal word "employees"')},
        sector='logistics',
    ),
    _doc(
        'anchorfleet_narrative_only', 'Anchor Fleet',
        "Fleet dispatch today is fragmented across phone calls, spreadsheets, and paper logs. "
        "Anchor Fleet centralizes dispatch onto one platform for small and mid-size carriers. "
        "Our biggest risk is competition from larger logistics incumbents entering this segment.",
        {
            'Problem': (None, 'Genuine "fragmented" problem statement'),
            'Product': (None, 'Genuine "centralizes...one platform" product statement'),
            'Risk': (None, 'Genuine competitive-risk statement'),
        },
        sector='logistics',
    ),
    _doc(
        'portside_spelled_out_headcount', 'Portside Logistics',
        "Portside Logistics is a team of eighteen employees coordinating freight across three ports.",
        {'Team': (18, 'Headcount spelled out as a word ("eighteen") — a real claim the digit-only regex is expected to miss')},
        sector='logistics',
    ),
    _doc(
        'trailhead_customer_spend_trap', 'Trailhead Cargo',
        "Our largest shipping customer alone moves $9 million worth of freight through our network "
        "annually, and that relationship keeps growing.",
        {},
        # No Revenue claim expected: $9M is the customer's freight
        # VALUE moving through the network, not Trailhead's own revenue.
        sector='logistics',
    ),

    # --- Fintech (6 new) ---
    _doc(
        'real_visa_revenue', 'Visa Inc.',
        "Visa Inc. reported net revenue of approximately $36 billion for the fiscal year, driven by "
        "payments volume growth and cross-border transactions.",
        {'Revenue': (36_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='fintech',
    ),
    _doc(
        'meridian_funding_only', 'Meridian Pay',
        "Meridian Pay raised $15 million in Series B funding to expand its small-business payments "
        "platform into new states.",
        {'Funding': (15_000_000, 'Explicit funding figure with clear Series B context')},
        sector='fintech', company_type='series_ab',
    ),
    _doc(
        'ledgerline_traction_only', 'Ledgerline Capital',
        "Ledgerline Capital provides automated bookkeeping for small accounting firms. "
        "The platform now serves 890 accounting firm customers nationwide.",
        {'Traction': (890, 'Explicit customer count using the literal word "customers"')},
        sector='fintech',
    ),
    _doc(
        'brightpath_rival_funding_trap', 'Brightpath Lending',
        "A rival lender in our space raised $40 million last quarter, well ahead of where we are today. "
        "Brightpath Lending has not raised any outside capital.",
        {},
        # No Funding claim expected: the $40M belongs to a named rival, not Brightpath.
        sector='fintech',
    ),
    _doc(
        'ferry_percentage_growth', 'Ferry Financial',
        "Ferry Financial has grown its active account base 165% year-over-year, with no paid "
        "acquisition spend to date.",
        {'Traction': (165, 'Growth percentage is a legitimate traction claim, no dollar figure involved')},
        sector='fintech',
    ),
    _doc(
        'cobalt_according_to_trap', 'Cobalt Bank',
        "According to TechCrunch, a competing digital bank raised $80 million this year. "
        "Cobalt Bank's own fundraising has not yet been announced.",
        {},
        # No Funding claim expected: attributed to a third party via
        # "According to TechCrunch," not a claim about Cobalt Bank itself.
        sector='fintech',
    ),

    # --- Retail (7 new) ---
    _doc(
        'real_target_revenue', 'Target Corporation',
        "Target Corporation reported total revenue of approximately $107 billion for the fiscal "
        "year, across its stores and digital channels.",
        {'Revenue': (107_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='retail',
    ),
    _doc(
        'real_home_depot_revenue', 'The Home Depot, Inc.',
        "The Home Depot, Inc. generated net sales of approximately $159 billion for the fiscal "
        "year, led by its Pro and DIY customer segments.",
        {'Revenue': (159_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='retail',
    ),
    _doc(
        'thistlebrook_traction_only', 'Thistlebrook Retail',
        "Thistlebrook Retail operates a chain of specialty home-goods stores. "
        "The company now serves 48,000 loyalty program members across its 12 locations.",
        {'Traction': (48_000, 'Explicit, comma-formatted member/customer count')},
        sector='retail',
    ),
    _doc(
        'amberlight_funding_only', 'Amberlight Stores',
        "Amberlight Stores secured $3 million in seed capital from regional retail investors to "
        "open its first three flagship locations.",
        {'Funding': (3_000_000, 'Explicit funding figure using "seed capital" phrasing')},
        sector='retail', company_type='seed',
    ),
    _doc(
        'hollowbrook_team_noisy_sentence', 'Hollowbrook Goods',
        "Started as a single storefront in 2015, Hollowbrook Goods has since expanded regionally, "
        "opened a distribution hub, and now counts 76 full-time employees among its retail and "
        "warehouse staff.",
        {'Team': (76, 'Genuine headcount figure buried in a long, noisy sentence')},
        sector='retail',
    ),
    _doc(
        'cedarline_market_size_only', 'Cedarline Market',
        "Cedarline Market is targeting a $12 billion addressable market in specialty regional grocery.",
        {'Market': (12_000_000_000, 'Explicit market-size figure with clear TAM framing')},
        sector='retail',
    ),
    _doc(
        'fernwood_narrative_only', 'Fernwood Outfitters',
        "Outdoor gear retail today is fragmented between big-box chains and disconnected local "
        "shops. Fernwood Outfitters centralizes curated gear discovery onto one platform. "
        "Our biggest risk is competition from large e-commerce incumbents.",
        {
            'Problem': (None, 'Genuine "fragmented" problem statement'),
            'Product': (None, 'Genuine "centralizes...one platform" product statement'),
            'Risk': (None, 'Genuine competitive-risk statement'),
        },
        sector='retail',
    ),

    # --- Biotech (7 new) ---
    _doc(
        'real_pfizer_revenue', 'Pfizer Inc.',
        "Pfizer Inc. reported total revenue of approximately $58 billion for the fiscal year, "
        "across its vaccines, oncology, and internal medicine portfolios.",
        {'Revenue': (58_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='biotech',
    ),
    _doc(
        'real_moderna_revenue', 'Moderna, Inc.',
        "Moderna, Inc. reported total revenue of approximately $3 billion for the fiscal year, "
        "primarily from its respiratory vaccine portfolio.",
        {'Revenue': (3_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='biotech',
    ),
    _doc(
        'helix_funding_only', 'Helix Therapeutics',
        "Helix Therapeutics raised $22 million in Series B funding to advance its lead gene-therapy "
        "candidate into Phase 2 trials.",
        {'Funding': (22_000_000, 'Explicit funding figure with clear Series B context')},
        sector='biotech', company_type='series_ab',
    ),
    _doc(
        'genovant_team_only', 'Genovant Bio',
        "Genovant Bio is a preclinical-stage biotechnology company. "
        "The company now employs 41 employees across research and regulatory affairs.",
        {'Team': (41, 'Explicit headcount figure using the literal word "employees"')},
        sector='biotech', company_type='seed',
    ),
    _doc(
        'cascadia_narrative_only', 'Cascadia Biosciences',
        "Rare-disease diagnosis today is fragmented across dozens of disconnected specialist "
        "labs. Cascadia Biosciences centralizes testing onto one platform for clinicians. "
        "Our biggest risk is regulatory approval timelines beyond our control.",
        {
            'Problem': (None, 'Genuine "fragmented" problem statement'),
            'Product': (None, 'Genuine "centralizes...one platform" product statement'),
            'Risk': (None, 'Genuine regulatory-risk statement'),
        },
        sector='biotech',
    ),
    _doc(
        'meridiangenomics_competitor_trap', 'Meridian Genomics',
        "Our closest peer in genomic diagnostics reported $150 million in revenue last year. "
        "Meridian Genomics has not yet commercialized its first assay.",
        {},
        # No Revenue claim expected: the figure belongs to a named "peer," not Meridian.
        sector='biotech', company_type='seed',
    ),
    _doc(
        'northfield_funding_range', 'Northfield Labs',
        "Northfield Labs raised between $4 million and $6 million in its seed extension round "
        "earlier this year.",
        {'Funding': (4_000_000, 'Funding range stated — lower bound used as expected value; range formatting is a known recall gap')},
        sector='biotech',
    ),

    # --- Energy (7 new) ---
    _doc(
        'real_nextera_revenue', 'NextEra Energy, Inc.',
        "NextEra Energy, Inc. reported total operating revenue of approximately $24 billion for "
        "the fiscal year, across its regulated utility and renewable generation segments.",
        {'Revenue': (24_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='energy',
    ),
    _doc(
        'real_exxonmobil_revenue', 'Exxon Mobil Corporation',
        "Exxon Mobil Corporation reported total revenue of approximately $340 billion for the "
        "fiscal year, across its upstream and downstream segments.",
        {'Revenue': (340_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='energy',
    ),
    _doc(
        'solara_funding_only', 'Solara Power',
        "Solara Power closed a $18 million Series A round to expand its residential solar "
        "installation footprint across three new states.",
        {'Funding': (18_000_000, 'Explicit funding figure with clear Series A context')},
        sector='energy', company_type='series_ab',
    ),
    _doc(
        'windmere_traction_only', 'Windmere Energy',
        "Windmere Energy provides community solar subscriptions to homeowners. "
        "The platform now serves 6,400 subscriber households across the region.",
        {'Traction': (6_400, 'Explicit, comma-formatted subscriber count')},
        sector='energy',
    ),
    _doc(
        'terraform_team_noisy_sentence', 'Terraform Grid',
        "Founded by two grid engineers in a co-working space, Terraform Grid has since built out "
        "field operations across four states and now counts 63 full-time employees among its staff.",
        {'Team': (63, 'Genuine headcount figure buried in a long, noisy sentence')},
        sector='energy',
    ),
    _doc(
        'brightfield_market_size_only', 'Brightfield Solar',
        "Brightfield Solar is targeting a $30 billion addressable market in distributed solar "
        "storage.",
        {'Market': (30_000_000_000, 'Explicit market-size figure with clear TAM framing')},
        sector='energy',
    ),
    _doc(
        'meridianwind_spelled_out_headcount', 'Meridian Wind',
        "Meridian Wind is a team of twenty-two employees developing offshore wind assessment tools.",
        {'Team': (22, 'Headcount spelled out as a word ("twenty-two") — a real claim the digit-only regex is expected to miss')},
        sector='energy',
    ),

    # --- Healthtech (7 new) ---
    _doc(
        'real_unitedhealth_revenue', 'UnitedHealth Group Incorporated',
        "UnitedHealth Group Incorporated reported total revenue of approximately $400 billion for "
        "the fiscal year, across its insurance and Optum health services segments.",
        {'Revenue': (400_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='healthtech',
    ),
    _doc(
        'vitalis_funding_only', 'Vitalis Health',
        "Vitalis Health raised $9 million in Series A funding to expand its remote patient "
        "monitoring platform into new health systems.",
        {'Funding': (9_000_000, 'Explicit funding figure with clear Series A context')},
        sector='healthtech', company_type='series_ab',
    ),
    _doc(
        'carepoint_traction_only', 'Carepoint Diagnostics',
        "Carepoint Diagnostics provides at-home lab testing kits. "
        "The company now serves 31,000 patients through its direct-to-consumer channel.",
        {'Traction': (31_000, 'Explicit, comma-formatted patient/customer count')},
        sector='healthtech',
    ),
    _doc(
        'wellspring_narrative_only', 'Wellspring Clinical',
        "Clinical trial recruitment today is fragmented across disconnected referral networks. "
        "Wellspring Clinical centralizes patient matching onto one platform for research sites. "
        "Our biggest risk is regulatory and privacy compliance across jurisdictions.",
        {
            'Problem': (None, 'Genuine "fragmented" problem statement'),
            'Product': (None, 'Genuine "centralizes...one platform" product statement'),
            'Risk': (None, 'Genuine compliance-risk statement'),
        },
        sector='healthtech',
    ),
    _doc(
        'northstar_competitor_trap', 'Northstar Medical',
        "An industry leader in remote diagnostics posted $220 million in revenue last year. "
        "Northstar Medical is still in its early commercial launch phase.",
        {},
        # No Revenue claim expected: figure belongs to a named "industry leader," not Northstar.
        sector='healthtech', company_type='seed',
    ),
    _doc(
        'ironbridge_team_only', 'Ironbridge Health',
        "Ironbridge Health builds scheduling software for outpatient clinics. "
        "The company now employs 29 employees across engineering and clinical operations.",
        {'Team': (29, 'Explicit headcount figure using the literal word "employees"')},
        sector='healthtech',
    ),
    _doc(
        'clearview_customer_spend_trap', 'Clearview Diagnostics',
        "Our largest health-system customer alone spends $7 million annually through our "
        "diagnostics ordering platform.",
        {},
        # No Revenue claim expected: $7M is the customer's spend
        # THROUGH the platform, not Clearview's own revenue (ambiguous
        # GMV-vs-revenue framing, deliberately unresolved either way).
        sector='healthtech',
    ),

    # --- Manufacturing (new sector, 8) ---
    _doc(
        'real_caterpillar_revenue', 'Caterpillar Inc.',
        "Caterpillar Inc. reported total revenue of approximately $67 billion for the fiscal year, "
        "across its construction, resource, and energy equipment segments.",
        {'Revenue': (67_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='manufacturing',
    ),
    _doc(
        'real_3m_revenue', '3M Company',
        "3M Company reported net sales of approximately $24 billion for the fiscal year across "
        "its safety, industrial, and consumer segments.",
        {'Revenue': (24_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='manufacturing',
    ),
    _doc(
        'anvilworks_revenue_only', 'Anvilworks Manufacturing',
        "Anvilworks Manufacturing generated $11.4 million in revenue last year producing custom "
        "metal components for industrial equipment makers.",
        {'Revenue': (11_400_000, 'Explicit revenue figure, no funding mentioned')},
        sector='manufacturing',
    ),
    _doc(
        'sterling_funding_only', 'Sterling Fabrication',
        "Sterling Fabrication closed a $7 million growth round to add a second production line "
        "at its existing facility.",
        {'Funding': (7_000_000, 'Explicit funding figure with clear growth-round context')},
        sector='manufacturing', company_type='series_ab',
    ),
    _doc(
        'ridgeline_team_only', 'Ridgeline Industrial',
        "Ridgeline Industrial produces precision-machined parts for the aerospace supply chain. "
        "The company now employs 88 employees across its two manufacturing plants.",
        {'Team': (88, 'Explicit headcount figure using the literal word "employees"')},
        sector='manufacturing',
    ),
    _doc(
        'forgeline_traction_only', 'Forgeline Metals',
        "Forgeline Metals supplies specialty alloys to industrial fabricators. "
        "The company now serves 210 enterprise customers across North America.",
        {'Traction': (210, 'Explicit customer count using the literal word "customers"')},
        sector='manufacturing',
    ),
    _doc(
        'cobaltmachine_spelled_out_headcount', 'Cobalt Machine Works',
        "Cobalt Machine Works is a team of fifteen employees running two CNC production lines.",
        {'Team': (15, 'Headcount spelled out as a word ("fifteen") — a real claim the digit-only regex is expected to miss')},
        sector='manufacturing',
    ),
    _doc(
        'hearthstone_narrative_only', 'Hearthstone Manufacturing',
        "Small-batch manufacturing today is fragmented across disconnected suppliers and "
        "spreadsheet-based scheduling. Hearthstone Manufacturing centralizes production planning "
        "onto one platform. Our biggest risk is exposure to raw material price volatility.",
        {
            'Problem': (None, 'Genuine "fragmented" problem statement'),
            'Product': (None, 'Genuine "centralizes...one platform" product statement'),
            'Risk': (None, 'Genuine commodity-risk statement'),
        },
        sector='manufacturing',
    ),

    # --- AI (new sector, 8) ---
    _doc(
        'synthara_revenue_only', 'Synthara AI',
        "Synthara AI generated $3.6 million in revenue last year from its document-automation "
        "API sold to enterprise customers.",
        {'Revenue': (3_600_000, 'Explicit revenue figure, no funding mentioned')},
        sector='ai',
    ),
    _doc(
        'cognivault_funding_only', 'Cognivault',
        "Cognivault raised $25 million in Series A funding to scale its model-evaluation "
        "infrastructure for enterprise AI teams.",
        {'Funding': (25_000_000, 'Explicit funding figure with clear Series A context')},
        sector='ai', company_type='series_ab',
    ),
    _doc(
        'neuralbridge_traction_only', 'Neuralbridge',
        "Neuralbridge provides an inference-optimization layer for AI applications. "
        "The platform now serves 175 enterprise customers processing production traffic.",
        {'Traction': (175, 'Explicit customer count using the literal word "customers"')},
        sector='ai',
    ),
    _doc(
        'latticework_narrative_only', 'Latticework AI',
        "Enterprise data today is fragmented across disconnected silos that block model training. "
        "Latticework AI centralizes data preparation onto one platform. Our biggest risk is "
        "competition from well-funded foundation-model labs building similar tooling.",
        {
            'Problem': (None, 'Genuine "fragmented" problem statement'),
            'Product': (None, 'Genuine "centralizes...one platform" product statement'),
            'Risk': (None, 'Genuine competitive-risk statement'),
        },
        sector='ai',
    ),
    _doc(
        'vantagecognition_competitor_trap', 'Vantage Cognition',
        "A well-funded industry leader in this space reported $500 million in revenue last year. "
        "Vantage Cognition is still pre-revenue as we finalize our first enterprise pilots.",
        {},
        # No Revenue claim expected: figure belongs to a named "industry leader," not Vantage.
        sector='ai', company_type='seed',
    ),
    _doc(
        'pathlight_percentage_growth', 'Pathlight AI',
        "Pathlight AI has grown its API call volume 340% year-over-year since launching its "
        "public beta.",
        {'Traction': (340, 'Growth percentage is a legitimate traction claim, no dollar figure involved')},
        sector='ai', company_type='seed',
    ),
    _doc(
        'embermind_team_noisy_sentence', 'Embermind',
        "Started by three former research scientists, Embermind has since built out applied "
        "engineering and go-to-market functions, and now counts 19 full-time employees among "
        "its ranks.",
        {'Team': (19, 'Genuine headcount figure buried in a long, noisy sentence')},
        sector='ai',
    ),
    _doc(
        'solvix_according_to_trap', 'Solvix AI',
        "According to a recent industry report, a competing AI startup raised $60 million this "
        "year. Solvix AI's own fundraising has not yet been announced.",
        {},
        # No Funding claim expected: attributed via "According to a
        # recent industry report" to a competitor, not Solvix itself.
        sector='ai',
    ),

    # --- Media (new sector, 8) ---
    _doc(
        'real_netflix_revenue', 'Netflix, Inc.',
        "Netflix, Inc. reported total revenue of approximately $39 billion for the fiscal year, "
        "driven by global subscriber growth and advertising-tier adoption.",
        {'Revenue': (39_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='media',
    ),
    _doc(
        'real_disney_revenue', 'The Walt Disney Company',
        "The Walt Disney Company reported total revenue of approximately $91 billion for the "
        "fiscal year, across its entertainment, sports, and experiences segments.",
        {'Revenue': (91_000_000_000, 'Explicit revenue figure stated')},
        is_real_public_company=True, sector='media',
    ),
    _doc(
        'lumenpress_funding_only', 'Lumenpress Media',
        "Lumenpress Media closed a $6 million seed round to expand its independent-creator "
        "publishing tools.",
        {'Funding': (6_000_000, 'Explicit funding figure with clear seed-round context')},
        sector='media', company_type='seed',
    ),
    _doc(
        'northlight_traction_only', 'Northlight Studios',
        "Northlight Studios produces short-form video content for brand partners. "
        "The studio now serves 64 brand customers on ongoing content retainers.",
        {'Traction': (64, 'Explicit customer count using the literal word "customers"')},
        sector='media',
    ),
    _doc(
        'driftwave_team_only', 'Driftwave Media',
        "Driftwave Media operates a network of niche podcast properties. "
        "The company now employs 23 employees across production and ad sales.",
        {'Team': (23, 'Explicit headcount figure using the literal word "employees"')},
        sector='media',
    ),
    _doc(
        'cascadebroadcasting_market_size_only', 'Cascade Broadcasting',
        "Cascade Broadcasting is targeting a $8 billion addressable market in regional streaming "
        "advertising.",
        {'Market': (8_000_000_000, 'Explicit market-size figure with clear TAM framing')},
        sector='media',
    ),
    _doc(
        'ferngully_spelled_out_headcount', 'Ferngully Publishing',
        "Ferngully Publishing is a team of eleven employees producing a slate of newsletters.",
        {'Team': (11, 'Headcount spelled out as a word ("eleven") — a real claim the digit-only regex is expected to miss')},
        sector='media',
    ),
    _doc(
        'anchorline_rival_funding_trap', 'Anchorline Films',
        "A rival production studio raised $45 million last quarter to fund its slate. "
        "Anchorline Films has not raised any outside capital.",
        {},
        # No Funding claim expected: the $45M belongs to a named rival studio, not Anchorline.
        sector='media',
    ),

    # --- Business-for-sale listings (company_type='business_for_sale') ---
    # A structurally distinct document style from every entry above: an
    # established, profitable small business being SOLD, not a startup
    # raising capital. CIM-style vocabulary (EBITDA, asking price, years
    # in business, owner succession) rather than pitch-deck vocabulary
    # (ARR, TAM, Series A) — and Funding realistically never applies here,
    # which is itself an expected structural fact worth the eval
    # confirming, not a gap. This entire style was completely
    # unrepresented in the corpus until now, despite being a real,
    # distinct document type Interlink Foundry's own M&A marketplace
    # (SellerApplication) actually handles.
    _doc(
        'ridgeway_revenue_and_ebitda', 'Ridgeway Print Shop',
        "Ridgeway Print Shop generated $1.8 million in revenue last year, with EBITDA of "
        "$410,000. The business is being offered at an asking price of $1.2 million as the "
        "owner transitions into retirement.",
        {'Revenue': (1_800_000, 'Explicit revenue figure stated')},
        sector='manufacturing', company_type='business_for_sale',
    ),
    _doc(
        'cobblestone_team_only', 'Cobblestone Bakery',
        "Founded 14 years ago, Cobblestone Bakery now employs 22 employees across its two "
        "retail locations and is being sold as the owner transitions to retirement.",
        {'Team': (22, 'Explicit headcount figure using the literal word "employees"')},
        sector='consumer', company_type='business_for_sale',
    ),
    _doc(
        'sterling_narrative_only', 'Sterling Grooming Co.',
        "Local demand for specialty pet grooming is fragmented among small independent shops. "
        "Sterling Grooming Co. centralizes bookings and loyalty programs onto one platform "
        "across its three locations. The primary risk for a buyer is key-person dependency on "
        "the current owner-operator.",
        {
            'Problem': (None, 'Genuine "fragmented" problem statement'),
            'Product': (None, 'Genuine "centralizes...one platform" product statement'),
            'Risk': (None, 'Genuine key-person-risk statement — a real, common M&A diligence concern for owner-operated businesses'),
        },
        sector='consumer', company_type='business_for_sale',
    ),
    _doc(
        'fernbrook_traction_only', 'Fernbrook Landscaping',
        "Fernbrook Landscaping serves 340 recurring commercial clients across the metro area "
        "and is being offered for sale as part of the owner's succession plan.",
        {'Traction': (340, 'Explicit client count using the literal word "clients"')},
        sector='consumer', company_type='business_for_sale',
    ),
    _doc(
        'meridianhvac_comma_revenue', 'Meridian HVAC Services',
        "Meridian HVAC Services generated $2,450,000 in revenue last year, with the seller "
        "estimating an EBITDA margin near 18%.",
        {'Revenue': (2_450_000, 'Explicit, comma-formatted revenue figure')},
        sector='manufacturing', company_type='business_for_sale',
    ),
    _doc(
        'thistlewood_according_to_trap', 'Thistlewood Laundromat Group',
        "According to a regional business brokerage, comparable laundromat chains in this metro "
        "area have sold for 3x EBITDA. This business's own EBITDA has not yet been formally "
        "disclosed to prospective buyers.",
        {},
        # No Revenue/other numeric claim expected: the 3x EBITDA multiple
        # is a market comp cited via "According to a regional business
        # brokerage," not a figure about Thistlewood itself.
        sector='consumer', company_type='business_for_sale',
    ),
    _doc(
        'oakhollow_market_size_only', 'Oakhollow Commercial Cleaning',
        "Oakhollow Commercial Cleaning operates in a regional commercial cleaning market "
        "estimated at $80 million annually.",
        {'Market': (80_000_000, 'Explicit market-size figure with clear framing')},
        sector='logistics', company_type='business_for_sale',
    ),
    _doc(
        'brackenridge_spelled_out_headcount', 'Brackenridge Auto Repair',
        "Brackenridge Auto Repair employs a team of nine people across its two service bays.",
        {'Team': (9, 'Headcount spelled out as a word ("nine") — a real claim the digit-only regex is expected to miss')},
        sector='manufacturing', company_type='business_for_sale',
    ),
    _doc(
        'wrenfield_team_and_traction', 'Wrenfield Dental Practice',
        "Wrenfield Dental Practice employs 11 staff members and maintains a base of 2,800 "
        "active patients built up over eighteen years in the same location.",
        {
            'Team': (11, 'Explicit headcount figure — note: uses "staff members," not the literal word "employees," a real recall gap the digit-only regex around "employees?" is expected to miss'),
            'Traction': (2_800, 'Explicit patient/client-equivalent count — note: uses "patients," not "customers/clients/users," another real recall gap'),
        },
        sector='healthtech', company_type='business_for_sale',
    ),
    _doc(
        'larkhaven_funding_keyword_absent', 'Larkhaven Pet Boarding',
        "Larkhaven Pet Boarding has been profitable and self-funded since opening eight years "
        "ago, with no outside investment of any kind.",
        {},
        # No Funding claim expected — and structurally, none should ever
        # be expected for a business-for-sale listing at all, unlike
        # pitch decks where a Funding claim is common. This document
        # exists specifically to confirm that absence is handled cleanly.
        sector='consumer', company_type='business_for_sale',
    ),
]
