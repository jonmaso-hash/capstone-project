"""
A figure belongs to the metric whose label is nearest it, not to whichever
label sits within N characters.

`_extract_clean_value` has a branch per category, and three of the four bind a
figure to a label by proximity:

    Traction  ([\\d,]+)\\s*(customers?|users?|clients?...)   adjacent -- CORRECT
    Team      figure [^.]{0,30} label                       30-char window
    Funding   figure .{0,40} (series|round|raised|funding)   40-char window
    Revenue   (amount)\\s*(?:arr|mrr|revenue|recurring)?     label OPTIONAL

So in one sentence carrying two metrics, the wrong figure wins:

    "Bootstrapped to $4 million in revenue, then raised $9 million in growth
     capital"                       -> funding_raised = 4,000,000
    "The addressable market is $1.9 billion and our revenue is $11.4 million"
                                    -> revenue = 1,900,000,000  (167x wrong)
    "Serving 218 customers with 87 full-time employees"
                                    -> employees = 218

The number is parsed correctly every time; it is attached to the wrong claim.
That is worse than a missing claim, because the result looks coherent all the
way downstream. Claims carry no period today, so such a pairing declines as
`period_unknown` -- luck, not design. Once claim periods exist, a market-size
figure sitting in `revenue` produces a FALSE CONTRADICTION against a claim the
company never made, with the grounding layer faithfully reporting a lie it was
handed.

Traction is the branch that works and the model for the rest: bind the figure
to its own label.

The evaluation corpus cannot catch this on its own. It HAS multi-metric
sentences, but every one states the target metric first -- the order the greedy
rule happens to handle. Reversing the clauses of a real corpus sentence flips
the result:

    Bramblewood as written (revenue first) -> 6,100,000  correct
    Bramblewood reversed   (funding first) -> 4,000,000  wrong

Order-inverted entries are therefore added to the corpus alongside this fix.
"""
from django.test import SimpleTestCase

from .intelligence_pipeline import ZeldaIntelligencePipelineV2
from .truth_delta_tasks import _extract_numeric_value


class AFigureBelongsToItsNearestLabelTests(SimpleTestCase):

    def setUp(self):
        self.pipeline = ZeldaIntelligencePipelineV2()

    def extract(self, category, sentence):
        keywords = self.pipeline.ANALYSIS_CATEGORIES[category]
        value, _confidence, _provenance = self.pipeline._smart_extract(category, sentence, keywords)
        return _extract_numeric_value(value) if value else None

    # --- Funding: the originally observed defect -------------------------
    def test_a_revenue_figure_before_raised_is_not_the_funding(self):
        self.assertEqual(self.extract(
            'Funding',
            'Bootstrapped to $4 million in revenue, then raised $9 million in growth capital in 2021.',
        ), 9_000_000.0)

    def test_funding_stated_alone(self):
        self.assertEqual(self.extract('Funding', 'Raised $9 million in growth capital in 2021.'), 9_000_000.0)

    def test_funding_stated_before_revenue(self):
        """Control: the order that already worked must keep working."""
        self.assertEqual(self.extract(
            'Funding', 'Raised $9 million in growth capital after reaching $4 million in revenue.',
        ), 9_000_000.0)

    def test_seeking_phrasing(self):
        self.assertEqual(self.extract(
            'Funding', 'Seeking $18 million Series A at a $90 million pre-money valuation.',
        ), 18_000_000.0)

    def test_seed_capital_phrasing(self):
        self.assertEqual(self.extract('Funding', '$6.5 million in seed capital across two rounds.'), 6_500_000.0)

    # --- Revenue: the worst case ----------------------------------------
    def test_a_market_size_figure_is_not_revenue(self):
        """A 167x error: $1.9B of addressable market read as company revenue."""
        self.assertEqual(self.extract(
            'Revenue', 'The addressable market is $1.9 billion and our revenue is $11.4 million.',
        ), 11_400_000.0)

    def test_a_funding_figure_is_not_revenue(self):
        self.assertEqual(self.extract(
            'Revenue', 'Seeking $18 million Series A; annual recurring revenue is $11.4 million.',
        ), 11_400_000.0)

    def test_an_ebitda_figure_is_not_revenue(self):
        """From the corpus's own ridgeway sentence, clauses reversed."""
        self.assertEqual(self.extract(
            'Revenue', 'Ridgeway Print Shop posted EBITDA of $410,000 last year, on revenue of $1.8 million.',
        ), 1_800_000.0)

    def test_revenue_stated_first_still_works(self):
        """Control: the corpus's own ordering."""
        self.assertEqual(self.extract(
            'Revenue',
            'Bramblewood Foods generated $6.1 million in revenue last year and separately closed a $4 million seed round.',
        ), 6_100_000.0)

    def test_revenue_stated_alone(self):
        self.assertEqual(self.extract('Revenue', 'Annual recurring revenue is $11.4 million.'), 11_400_000.0)

    def test_the_abbreviated_arr_form(self):
        self.assertEqual(self.extract('Revenue', 'Current revenue of $4.2M across 41 accounts.'), 4_200_000.0)

    def test_the_spelled_out_form_from_a_real_deck(self):
        self.assertEqual(self.extract(
            'Revenue', 'Total revenue for fiscal 2025 was approximately $416 billion.',
        ), 416_000_000_000.0)

    # --- Team ------------------------------------------------------------
    def test_a_customer_count_is_not_a_headcount(self):
        self.assertEqual(self.extract('Team', 'Serving 218 customers with 87 full-time employees.'), 87.0)

    def test_headcount_stated_alone(self):
        self.assertEqual(self.extract('Team', 'The company employs approximately 87 full-time employees.'), 87.0)

    def test_the_employs_phrasing_from_a_real_deck(self):
        self.assertEqual(self.extract('Team', 'The company employs approximately 30 people.'), 30.0)

    # --- Traction: already correct, must not regress ---------------------
    def test_an_employee_count_is_not_a_customer_count(self):
        self.assertEqual(self.extract(
            'Traction', 'Our 87 full-time employees serve 218 customers across 31 states.',
        ), 218.0)

    def test_customers_stated_alone(self):
        self.assertEqual(self.extract('Traction', '218 distributor customers across 31 states.'), 218.0)

    def test_a_customer_count_is_not_revenue(self):
        """
        "serves 340 recurring commercial clients" carries a revenue LABEL
        ("recurring") and no money at all. Falling through to the qualitative
        path let the numeric parser downstream claim the customer count as
        revenue -- a money field taking a number that is not money.
        """
        self.assertIsNone(self.extract(
            'Revenue', 'Fernbrook Landscaping serves 340 recurring commercial clients.'))

    # --- the CLOSEST binding wins, not merely "a" binding ----------------
    def test_the_tightest_binding_wins_over_a_distant_one(self):
        """
        From the corpus's auric entry: the company's own seed round sits one
        character from its label, while the investors' assets under management
        sit sixty characters from the nearest funding word. Declining both, or
        taking the far one, loses a real claim -- this is what cost seven
        points of recall before closest-binding replaced "decline if two look
        owned".
        """
        self.assertEqual(self.extract(
            'Funding',
            'The company closed a $6 million seed round in March, backed by two firms that '
            'together manage over $500 million in assets.',
        ), 6_000_000.0)

    def test_a_founding_year_does_not_outrank_the_headcount(self):
        """From the corpus's palisade entry: 2019 is 115 characters from the label; 27 is one."""
        self.assertEqual(self.extract(
            'Team',
            'Founded in a garage in 2019 by two engineers, Palisade Robotics has since scaled '
            'its operations and now counts 27 full-time staff.',
        ), 27.0)

    def test_a_metric_named_before_its_figure_still_binds(self):
        """
        "Our employees numbered 87" names the metric first. An earlier rule
        required the label to follow a count and silently dropped this.
        """
        self.assertEqual(self.extract('Team', 'Our employees numbered 87 at year end.'), 87.0)

    def test_a_figure_beside_another_metrics_label_is_not_claimed(self):
        """
        EBITDA owns its own figure even though `revenue` appears in the
        sentence: without EBITDA, margin, valuation and the rest as labels,
        $410,000 would be bound to the only label present and become revenue.
        """
        self.assertIsNone(self.extract(
            'Revenue', 'Revenue grew steadily last year; EBITDA of $410,000 was reported.'))

    # --- ambiguity yields no claim, never a confident guess --------------
    def test_two_figures_equally_close_to_the_label_yield_no_claim(self):
        """
        Nearest-label is the rule for these narrow patterns, not a universal
        semantic truth. Where the pattern cannot establish which figure the
        label owns, the extractor must decline rather than pick one: a missing
        claim is visible downstream, a plausible wrong one survives every layer.
        """
        self.assertIsNone(self.extract(
            'Revenue', 'Revenue of $4 million and revenue of $7 million were reported by the two units.',
        ))

    def test_a_bare_figure_with_no_label_is_not_a_revenue_claim(self):
        self.assertIsNone(self.extract('Revenue', 'The company reported $11.4 million last year.'))

    def test_a_bare_count_with_no_label_is_not_a_headcount(self):
        self.assertIsNone(self.extract('Team', 'The leadership team grew to 87 during the period.'))

    # --- a narrative category must still produce its insight -------------
    def test_a_category_with_no_figure_still_extracts(self):
        keywords = self.pipeline.ANALYSIS_CATEGORIES['Revenue']
        value, _c, _p = self.pipeline._smart_extract(
            'Revenue', 'The company sells software to small businesses on a subscription basis.', keywords)
        self.assertIsNotNone(value, 'a qualitative revenue sentence produced nothing')
