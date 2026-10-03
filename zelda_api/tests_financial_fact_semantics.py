"""
A financial fact carries its metric and its period, or it is not stored.

From the JoyToys audit run (2026-09-30). The deck says "$300K / month" and
"$3.6M annualized run-rate" -- consistent figures, and the word "ARR" appears
nowhere in it. The generated memo nevertheless reported a 12x contradiction
between "$300K ARR" and "$300K per month", called the financial picture
"unreadable without clarification", carried that into five sections and made it
question #1 for management -- then cited finding the contradiction as Zelda's
own advantage.

THE MODEL DID NOT HALLUCINATE. `_build_structured_context` put the monthly
figure into `facts['arr']`, the reconciliation step copied it to
`facts['revenue']`, and `facts_display` JSON-dumped both keys. The model was
handed

    {"revenue": "$300K", "arr": "$300K"}

next to the insight "$300K per month" and correctly observed that a $300K ARR
cannot also be $300K monthly. It reasoned properly about corrupted input.

That is why this file tests the DATA CONTRACT and not the prose. A test at the
memo layer would go green after any prompt tweak while the corrupt contract
sat untouched -- the same mistake as asserting a value reached the page when
it only reached a <script> tag.

The invariant:

    A source statement may be transformed, normalized or derived downstream,
    but its metric, period and unit can never be silently replaced.

`arr` means annual recurring revenue. `mrr` means monthly recurring revenue.
`revenue` means an amount of revenue whose period is whatever the source said.
A figure may only occupy a field whose name its source supports.

Note: `facts['arr']` here and `ClaimedDatapoint(category='arr')` in Truth Delta
are INTENTIONALLY different contracts. The claim category legitimately means
ARR. Do not unify them.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

from .intelligence_pipeline import ZeldaIntelligencePipelineV2
from .vector_models import DocumentSource, IntelligenceInsight

User = get_user_model()


class FactSemanticsHarness(TestCase):

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('facts_owner', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pptx', source_entity='JoyToys', uploaded_by=self.user,
            document_type='pitch_deck', status='analyzed')

    def facts_from(self, *insights):
        """
        Run the real extractor over insights shaped like the analyzer's.
        Each argument is (category, insight_text).
        """
        objs = [
            IntelligenceInsight.objects.create(
                document=self.document, category=category, insight_text=text,
                confidence_score=0.95)
            for category, text in insights
        ]
        return ZeldaIntelligencePipelineV2()._build_structured_context(self.document, objs)


class MonthlyRevenueIsNotARRTests(FactSemanticsHarness):
    """The JoyToys defect, reduced to its smallest reproduction."""

    def test_the_harness_extracts_something(self):
        """Positive control: assertions below are about a populated dict."""
        facts = self.facts_from(('Revenue', '$300K / month'))
        self.assertEqual(facts['company'], 'JoyToys')
        self.assertTrue(
            any(facts.get(k) for k in ('revenue', 'arr', 'mrr')),
            'no revenue-ish fact was extracted at all, so nothing is being tested')

    def test_a_monthly_figure_never_lands_in_arr(self):
        """
        "$300K / month" is not annual recurring revenue. Storing it under a
        key named `arr` asserts a period the source never gave.
        """
        facts = self.facts_from(('Revenue', '$300K / month'))
        self.assertIsNone(
            facts['arr'],
            'a monthly figure was stored as ARR, which is what manufactured the '
            'JoyToys 12x contradiction')

    def test_a_monthly_figure_is_kept_as_revenue(self):
        """It must still be captured -- the fix is not to drop the number."""
        facts = self.facts_from(('Revenue', '$300K / month'))
        self.assertIsNotNone(facts['revenue'], 'the revenue figure was lost entirely')
        self.assertIn('300', str(facts['revenue']))

    def test_the_same_amount_is_never_presented_under_two_metrics(self):
        """
        The contradiction the model reported was between two keys holding the
        SAME string. Whatever the schema, one amount may occupy one metric.
        """
        facts = self.facts_from(('Revenue', '$300K / month'))
        populated = {k: v for k, v in facts.items()
                     if k in ('revenue', 'arr', 'mrr') and v}
        values = [str(v) for v in populated.values()]
        self.assertEqual(
            len(values), len(set(values)),
            f'the same figure appears under more than one metric: {populated} -- '
            f'this is exactly what Claude was handed and correctly called a '
            f'contradiction')


class AnExplicitMetricIsHonouredTests(FactSemanticsHarness):
    """
    Paired positives. Without these, "never populate arr" would pass by
    populating it never -- destroying the field rather than fixing it.
    """

    def test_an_explicit_arr_statement_populates_arr(self):
        facts = self.facts_from(('Revenue', 'The company reports $2.3M in ARR as of this quarter.'))
        self.assertIsNotNone(facts['arr'], 'a genuine ARR statement was not captured as ARR')
        self.assertIn('2.3', str(facts['arr']))

    def test_an_explicit_mrr_statement_does_not_become_arr(self):
        facts = self.facts_from(('Revenue', 'MRR of $50K as of this month.'))
        self.assertIsNone(facts['arr'], 'monthly recurring revenue was stored as ANNUAL')

    def test_an_unqualified_revenue_figure_is_not_promoted_to_arr(self):
        """
        "$4.5M revenue" states no period. Recording it as ARR invents one.
        """
        facts = self.facts_from(('Revenue', 'Current Revenue: $4.5M'))
        self.assertIsNone(facts['arr'],
                          'a revenue figure with no stated period was recorded as ARR')
        self.assertIsNotNone(facts['revenue'])


class BurnIsNotRevenueTests(FactSemanticsHarness):
    """
    Track B, at the boundary this file can reach. The analyzer classified
    "$240K annualized stated burn" as a Revenue insight; the extractor then
    used `bare_amount_pattern` -- which matches any dollar amount with no
    keyword at all -- and took it. Even granting the bad classification, a
    sentence that says "burn" must not yield a revenue fact.
    """

    def test_a_burn_sentence_does_not_produce_a_revenue_fact(self):
        facts = self.facts_from(('Revenue', '$240K annualized stated burn'))
        for field in ('revenue', 'arr', 'mrr'):
            with self.subTest(field=field):
                self.assertIsNone(
                    facts[field],
                    f'burn was recorded as {field}; the deck states this is burn, '
                    f'and the same deck warns that revenue minus burn is not profit')

    def test_a_real_revenue_sentence_still_works_alongside(self):
        """
        Paired positive: rejecting burn must not reject revenue stated in the
        same run.
        """
        facts = self.facts_from(
            ('Revenue', '$240K annualized stated burn'),
            ('Revenue', '$300K / month'),
        )
        self.assertIsNotNone(facts['revenue'], 'the real revenue figure was lost')
        self.assertIn('300', str(facts['revenue']))


class RaiseIsNotRevenueTests(FactSemanticsHarness):
    """
    The regression the existing comment at intelligence_pipeline.py:1373
    describes ("Seeking $20M Series-C" became $20M ARR). Re-asserted here
    because the bare-amount path for Revenue-categorised insights reopened it:
    a raise sentence misclassified as Revenue matches with no keyword needed.
    """

    def test_a_raise_sentence_classified_as_revenue_is_not_taken_as_revenue(self):
        facts = self.facts_from(('Revenue', '$250K sought, Series A, primary purpose: growth'))
        for field in ('revenue', 'arr', 'mrr'):
            with self.subTest(field=field):
                self.assertIsNone(facts[field],
                                  f'a capital raise was recorded as {field}')


class ClaimExtractionRespectsTheSameSemanticsTests(TestCase):
    """
    Track B: the SECOND producer. `truth_delta_tasks.extract_claims_from_insights`
    maps an insight category to a claim category and then takes whatever number
    `_extract_numeric_value` finds in the text. Nothing checks that the number
    is admissible evidence for that category, so on the JoyToys deck:

        Traction "$250K sought..."      -> customers = 250,000
        Funding  "...75% utilized"      -> funding_raised = 75
        Funding  "$250K Series A"       -> funding_raised = 250,000  (sought!)
        Revenue  "$240K annualized burn"-> revenue = 240,000

    Four of six claims materially wrong. Truth Delta then reported them
    honestly as unverified, which is correct -- but had JoyToys been an SEC
    filer, it would have compared burn against real revenue and reported a
    CONTRADICTION about a company that did nothing wrong. The grounding layer
    is faithful; it was being fed nonsense.

    A dollar amount is not a headcount. A percentage is not a sum of money.
    Money sought is not money raised. Burn is not revenue.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('claims_owner', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pptx', source_entity='JoyToys', uploaded_by=self.user,
            document_type='pitch_deck', status='analyzed')

    def claims_from(self, *insights):
        from unittest import mock
        from . import sec_identity
        from .truth_delta_models import ClaimedDatapoint
        from .truth_delta_tasks import extract_claims_from_insights
        for category, text in insights:
            IntelligenceInsight.objects.create(
                document=self.document, category=category, insight_text=text,
                confidence_score=0.95)
        # Claim extraction resolves the company identity, which reaches EDGAR.
        # These tests are about what counts as a money claim, not about SEC
        # availability, so the lookup is stubbed at `_get` -- the lowest seam
        # that removes the network -- and made to fail the way a real outage
        # fails, so sec_identity's own degradation path still runs.
        #
        # It was reaching the network until the test ban stopped being
        # swallowable: the ban had been firing here and something upstream was
        # catching it, so the suite looked clean while calling sec.gov.
        # NewsAPI is reached too, and is stubbed by making it INACTIVE rather
        # than by faking a response: that reproduces CI, where NEWS_API_KEY is
        # absent so the integration never activates. The local .env has a key,
        # which is the whole reason this diverged from CI unnoticed -- and why
        # `apiKey=...` turned up in a gate log.
        with mock.patch.object(
                sec_identity, '_get',
                side_effect=sec_identity.SecUnavailable(sec_identity.UNREACHABLE)), \
             mock.patch.object(settings, 'NEWS_API_KEY', ''):
            extract_claims_from_insights(self.document.id)
        return {c.category: c.claimed_value_numeric
                for c in ClaimedDatapoint.objects.filter(document=self.document)}

    def test_the_harness_creates_claims_at_all(self):
        """Positive control: the assertions below read this dict."""
        claims = self.claims_from(('Team', '17 employees'))
        self.assertEqual(claims.get('employees'), 17.0)

    def test_a_dollar_amount_is_not_a_customer_count(self):
        claims = self.claims_from(
            ('Traction', '$250K sought, Series A, primary purpose: growth'))
        self.assertIsNone(claims.get('customers'),
                          'a capital raise was recorded as a count of customers')

    def test_a_real_customer_count_still_becomes_a_claim(self):
        """Paired positive: the fix must not delete the customers category."""
        claims = self.claims_from(('Traction', '1,200 paying customers across three retailers'))
        self.assertEqual(claims.get('customers'), 1200.0)

    def test_a_percentage_is_not_an_amount_of_money(self):
        claims = self.claims_from(
            ('Funding', 'Prior capital raised: $20K. Bank line: 75% utilized.'))
        self.assertNotEqual(claims.get('funding_raised'), 75.0,
                            'a utilization percentage was recorded as dollars raised')

    def test_money_sought_is_not_money_raised(self):
        claims = self.claims_from(
            ('Funding', '$250K sought, Series A, primary use: new entertainment licenses'))
        self.assertIsNone(claims.get('funding_raised'),
                          'the amount being SOUGHT was recorded as capital already raised')

    def test_money_actually_raised_still_becomes_a_claim(self):
        """Paired positive."""
        claims = self.claims_from(('Funding', 'Prior capital raised: $20K to date.'))
        self.assertEqual(claims.get('funding_raised'), 20000.0)

    def test_burn_is_not_revenue(self):
        claims = self.claims_from(('Revenue', '$240K annualized stated burn'))
        self.assertIsNone(claims.get('revenue'),
                          'burn was recorded as revenue; had this company been an SEC '
                          'filer, Truth Delta would have reported a contradiction '
                          'against its real revenue')

    def test_real_revenue_still_becomes_a_claim(self):
        """Paired positive."""
        claims = self.claims_from(('Revenue', '$300K / month'))
        self.assertEqual(claims.get('revenue'), 300000.0)
