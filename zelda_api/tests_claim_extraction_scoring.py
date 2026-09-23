"""
A sentence carrying the figure must beat a longer sentence carrying none.

The 2026-09-22 pipeline experiment found the bottleneck upstream of Truth
Delta's grounding: SEC EDGAR returned Apple's real revenue and it verified
nothing, because no revenue claim was ever extracted to compare it against.
A deck for a real private company produced zero claims at all.

_calculate_confidence scores a sentence by, in order: a per-category "number
pattern" (95), an exact phrase (85), then ANY sentence of ten or more words
(70). Three consequences, all measured on real decks:

    "Total revenue for fiscal 2025 was approximately $416 billion" scores 50,
    because Revenue's number pattern is r'\\$[\\d,\\.]+[MBK]' and requires an
    abbreviated suffix -- a spelled-out "billion" does not match. The risk
    sentence "Concentration in iPhone revenue, exposure to manufacturing in
    Asia, and..." scores 70 for being longer, and wins. The winning rule is
    sentence length, not numeric content.

    The patterns are tuned to one healthcare deck: Market scores 95 only when
    a sentence also mentions hospitals/clinics/providers/healthcare, Traction
    looks for "momentum" or "series.c". Every other sector is scored by length.

    Team's keywords are 'team founder ceo experience background skill
    leadership'. "The company employs approximately 30 people" contains none
    of them, so headcount never reaches a claim.

And one downstream of them: "returned capital to shareholders continuously
since 2012" became funding_raised = 2012.0 -- a calendar year read as a
dollar amount, which Truth Delta then scored.

These tests use the real sentences from the experiment's decks. Each is paired
with a control that must keep working: a narrative category with no figure
anywhere must still produce its qualitative insight, or raising recall here
would simply be trading one silence for another.
"""
from django.test import SimpleTestCase

from .intelligence_pipeline import ZeldaIntelligencePipelineV2
from .truth_delta_tasks import _extract_numeric_value

APPLE_REVENUE = (
    'Total revenue for fiscal 2025 was approximately $416 billion. '
    'Services revenue was approximately $109 billion for the year.'
)
APPLE_RISK = (
    'Concentration in iPhone revenue, exposure to manufacturing in Asia, and '
    'regulatory attention to App Store distribution terms in several markets.'
)
BASECAMP_TEAM = 'The company employs approximately 30 people.'
NORTHPINE_MARKET = (
    'There are approximately 8,000 independent building-materials distributors in '
    'the United States, an addressable market of roughly $1.9 billion.'
)


class ConfidenceRewardsFiguresNotLengthTests(SimpleTestCase):

    def setUp(self):
        self.pipeline = ZeldaIntelligencePipelineV2()

    def confidence(self, category, sentence):
        return self.pipeline._calculate_confidence(category, sentence, sentence)

    def extract(self, category, text):
        keywords = self.pipeline.ANALYSIS_CATEGORIES[category]
        value, confidence, _ = self.pipeline._smart_extract(category, text, keywords)
        return value, confidence

    def test_a_spelled_out_amount_is_an_explicit_number(self):
        """'$416 billion' is a figure; only the abbreviation was recognised."""
        self.assertEqual(self.confidence('Revenue', 'Total revenue for fiscal 2025 was approximately $416 billion'), 95.0)

    def test_the_abbreviated_form_still_scores(self):
        """Control: the form that already worked must keep working."""
        self.assertEqual(self.confidence('Revenue', 'Current revenue of $4.2M across 41 accounts'), 95.0)

    def test_a_figure_outranks_a_longer_sentence_without_one(self):
        """The Apple case, on the real text of both sentences."""
        value, confidence = self.extract('Revenue', APPLE_REVENUE + ' ' + APPLE_RISK)
        self.assertIn('416', value)
        self.assertGreaterEqual(confidence, 95.0)

    def test_market_size_scores_outside_healthcare(self):
        """Market's 95 required hospitals/clinics/providers/healthcare."""
        self.assertEqual(self.confidence('Market', 'an addressable market of roughly $1.9 billion'), 95.0)

    def test_a_market_figure_is_extracted_from_a_real_deck_line(self):
        value, confidence = self.extract('Market', NORTHPINE_MARKET)
        self.assertIn('1.9', value)
        self.assertGreaterEqual(confidence, 95.0)

    def test_headcount_vocabulary_reaches_the_team_category(self):
        """'employs ... people' is how decks state headcount."""
        value, confidence = self.extract('Team', BASECAMP_TEAM)
        self.assertIsNotNone(value, 'no Team insight extracted from a headcount sentence')
        self.assertEqual(_extract_numeric_value(value), 30.0)

    def test_a_headcount_beats_a_longer_sentence_about_the_team(self):
        """
        Being extracted is not enough: the figure has to win. A team sentence
        with no number is exactly what used to take this category.
        """
        value, confidence = self.extract('Team', (
            'The leadership team brings deep experience across distribution, operations '
            'and finance from prior roles at larger competitors. ' + BASECAMP_TEAM
        ))
        self.assertEqual(_extract_numeric_value(value), 30.0, f'a non-numeric sentence won: {value!r}')
        self.assertEqual(confidence, 95.0)

    def test_a_named_founder_still_reaches_the_team_category(self):
        """Control: the existing Team behaviour is not traded away for headcount."""
        value, _ = self.extract('Team', 'Founder & CEO: Dana Whitfield, previously at a transmission operator.')
        self.assertIsNotNone(value)
        self.assertIn('Whitfield', value)

    def test_a_narrative_category_still_produces_its_insight(self):
        """Control: categories with no figures anywhere must not fall silent."""
        value, confidence = self.extract('Risk', APPLE_RISK)
        self.assertIsNotNone(value, 'narrative category produced nothing')
        self.assertGreater(confidence, 0)


class ACategoryMayCarryMoreThanOneFigureTests(SimpleTestCase):
    """
    A deck states revenue in one section and headcount in another. Keeping one
    sentence per category capped a whole document at five possible claims and
    discarded the rest before Truth Delta saw them.

    The evaluation corpus cannot exercise this: its documents are one or two
    sentences, so no category there ever holds two distinct figures. These
    tests stand in for that gap.
    """

    def setUp(self):
        self.pipeline = ZeldaIntelligencePipelineV2()

    def select(self, category, sentences):
        """Candidates as _analyze_document builds them, one per chunk."""
        keywords = self.pipeline.ANALYSIS_CATEGORIES[category]
        candidates, best = [], None
        for sentence in sentences:
            value, confidence, provenance = self.pipeline._smart_extract(category, sentence, keywords)
            if not value:
                continue
            candidate = (value, confidence, None, provenance)
            candidates.append(candidate)
            if best is None or confidence > best[1]:
                best = candidate
        return [text for text, _c, _chunk, _p in self.pipeline._select_insights(category, candidates, best)]

    def test_two_distinct_figures_both_survive(self):
        selected = self.select('Revenue', [
            'Annual recurring revenue of $11.4 million.',
            'Bootstrapped to $4 million in revenue before raising growth capital.',
        ])
        self.assertEqual(len(selected), 2, selected)

    def test_the_same_figure_restated_is_not_two_claims(self):
        selected = self.select('Revenue', [
            'Annual recurring revenue of $11.4 million.',
            'The company reports $11.4 million of recurring revenue.',
        ])
        self.assertEqual(len(selected), 1, selected)

    def test_a_percentage_does_not_become_a_second_figure(self):
        """'Net revenue retention of 131%' became a $131 revenue claim."""
        selected = self.select('Revenue', [
            'Annual recurring revenue of $4.2 million.',
            'Net revenue retention of 131%.',
        ])
        self.assertEqual(len(selected), 1, selected)
        self.assertIn('4.2', selected[0])

    def test_a_percentage_does_not_become_a_customer_count(self):
        selected = self.select('Traction', [
            '41 utility customers under contract.',
            'Net revenue retention of 131%.',
        ])
        self.assertEqual(len(selected), 1, selected)
        self.assertIn('41', selected[0])

    def test_a_narrative_category_still_keeps_exactly_one(self):
        """Control: memo sections and the scorecard expect one row per category."""
        selected = self.select('Risk', [
            'Competition from well-capitalised suites is intensifying.',
            'Regulatory attention to distribution terms continues in several markets.',
        ])
        self.assertEqual(len(selected), 1, selected)

    def test_a_category_is_capped(self):
        selected = self.select('Revenue', [
            'Revenue of $1 million in 2021.', 'Revenue of $2 million in 2022.',
            'Revenue of $3 million in 2023.', 'Revenue of $4 million in 2024.',
        ])
        self.assertLessEqual(len(selected), self.pipeline.MAX_INSIGHTS_PER_NUMERIC_CATEGORY)


class AYearIsNotAnAmountTests(SimpleTestCase):
    """'since 2012' became funding_raised = $2012."""

    def test_a_bare_year_is_not_read_as_money(self):
        self.assertIsNone(_extract_numeric_value(
            'Apple has returned capital to shareholders continuously since 2012.'))

    def test_a_founding_year_is_not_read_as_money(self):
        self.assertIsNone(_extract_numeric_value('Northpine Works has operated continuously since 2015.'))

    def test_a_real_amount_that_looks_like_a_year_is_kept(self):
        """Control: $2,015 is money -- the marker is the currency, not the digits."""
        self.assertEqual(_extract_numeric_value('Raised $2,015 in a friends and family round'), 2015.0)

    def test_the_currency_mark_alone_rescues_a_year_shaped_amount(self):
        """
        No separator to fall back on: $2015 is four bare digits in the year
        range, and only the currency mark distinguishes it from a date. A
        guard that ignored the mark would silently drop this claim.
        """
        self.assertEqual(_extract_numeric_value('Raised $2015 in a pre-seed round'), 2015.0)

    def test_a_count_that_happens_to_be_year_shaped_is_kept(self):
        """Control: 2,015 customers is a real count, not a date."""
        self.assertEqual(_extract_numeric_value('2,015 customers under contract'), 2015.0)

    def test_an_ordinary_amount_is_unaffected(self):
        self.assertEqual(_extract_numeric_value('$6.5 million in seed capital'), 6500000.0)
