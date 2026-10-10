"""
Company ownership of a claim: a figure another organisation owns is never stored
as this company's claim.

The frozen audit keys name the failure: Messenger's, Kik's and Telegram's user
counts presented as ManyChat's (docs/baselines/manychat key M2-M4), and the
parent's EUR 7.9B presented as Ben & Jerry's revenue (docs/baselines/ben-jerrys
key C5, a P0). Each negative below is paired with a control that must still be
stored, so the rule cannot pass by refusing everything.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from .claim_attribution import IMPLIED, NAMED, claim_ownership, company_names, source_sentence


class ClaimOwnershipTests(SimpleTestCase):

    def test_a_parent_units_figure_is_not_the_brands(self):
        # Ben & Jerry's page 10, with $ so the figure would parse today.
        sentence = "Unilever's ice cream unit generated $7.9B in 2024 sales"
        self.assertEqual(claim_ownership(sentence, ["Ben & Jerry's"]), (None, 'Unilever'))

    def test_the_company_names_own_apostrophe_is_not_another_owner(self):
        self.assertEqual(claim_ownership("Ben & Jerry's generated $7.9B in 2024 sales", ["Ben & Jerry's"]),
                         (NAMED, ''))
        self.assertEqual(claim_ownership("Ben & Jerry’s revenue was $900M", ["Ben & Jerry's"]),
                         (NAMED, ''))

    def test_a_platforms_users_are_not_the_companys(self):
        self.assertEqual(claim_ownership('Telegram has 100M users', ['ManyChat']), (None, 'Telegram'))
        self.assertEqual(claim_ownership("FB Messenger's 900M people", ['ManyChat']), (None, 'FB Messenger'))
        self.assertEqual(claim_ownership('ManyChat has 140,000 bots', ['ManyChat']), (NAMED, ''))  # control

    def test_another_subject_owns_the_figure_even_when_the_company_is_mentioned_later(self):
        sentence = 'Telegram has 100M users and integrates with ManyChat'
        self.assertEqual(claim_ownership(sentence, ['ManyChat']), (None, 'Telegram'))
        control = 'ManyChat has 2,000 customers and integrates with Telegram'
        self.assertEqual(claim_ownership(control, ['ManyChat']), (NAMED, ''))

    def test_a_third_party_source_about_the_company_keeps_the_company_as_owner(self):
        sentence = 'Source: Pitch Deck Hunt lists ManyChat as a 2015 Series A deck with $23.1M raised'
        self.assertEqual(claim_ownership(sentence, ['ManyChat']), (NAMED, ''))

    def test_unnamed_figures_in_the_companys_document_are_implied(self):
        for sentence in ('500M messages', 'Revenue reached $5M in FY2024', 'We have 500 customers',
                         "FY2024's revenue was $5M", "The Company's ARR is $2M", 'Our team of 12 people',
                         'Total funding raised: $3M', 'Customers grew to 1,200 in March'):
            with self.subTest(sentence=sentence):
                self.assertEqual(claim_ownership(sentence, ['Acme']), (IMPLIED, ''))

    def test_legal_suffixes_do_not_stop_the_company_being_named(self):
        self.assertEqual(claim_ownership('ManyChat reached 140,000 bots', ['ManyChat, Inc.']), (NAMED, ''))

    def test_another_owners_possessive_wins_even_when_the_company_is_named(self):
        sentence = "Unlike Salesforce's 150,000 customers, Acme serves 500 customers"
        self.assertEqual(claim_ownership(sentence, ['Acme']), (None, 'Salesforce'))

    def test_without_a_known_company_name_a_possessive_owner_is_third_party(self):
        # Conservative: with no name to recognise, "Acme's" cannot be shown to be the company.
        self.assertEqual(claim_ownership("Acme's revenue was $5M", []), (None, 'Acme'))

    def test_the_whole_source_sentence_is_recovered_from_a_span(self):
        chunk = "Market context\nUnilever's ice cream unit generated $7.9B in 2024 sales\nNext slide"
        self.assertEqual(source_sentence('generated $7.9B in 2024 sales', chunk),
                         "Unilever's ice cream unit generated $7.9B in 2024 sales")
        self.assertEqual(source_sentence('absent span', chunk), 'absent span')


class CompanyNamesTests(TestCase):

    def test_names_come_from_the_subject_and_the_owners_profile_but_not_unknown(self):
        from matchmaking.models import Application
        from .vector_models import DocumentSource
        user = get_user_model().objects.create_user('attribution_owner', password='x')
        Application.objects.create(user=user, company_name='Acme Robotics', founder_name='F',
                                   email='f@example.com', description='d', sector='SaaS', stage='Seed')
        own = DocumentSource.objects.create(uploaded_by=user, filename='d.pptx', source_entity='Unknown',
                                            document_type='pitch_deck')
        self.assertEqual(company_names(own), ['Acme Robotics'])
        external = DocumentSource.objects.create(uploaded_by=user, filename='e.txt', source_entity='Beta Corp',
                                                 document_type='research_report', is_external_subject=True)
        self.assertEqual(company_names(external), ['Beta Corp'])


class ClaimExtractionOwnershipTests(TestCase):
    """Insight -> claim gate, end to end, with the owner decided from the source sentence."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('ownership_owner', password='x')

    def claims_for(self, company, chunk_text, insight_text, category='Revenue'):
        from . import truth_delta_tasks
        from .truth_delta_models import ClaimedDatapoint
        from .vector_models import DocumentChunk, DocumentSource, IntelligenceInsight
        doc = DocumentSource.objects.create(uploaded_by=self.user, filename='d.pptx', source_entity=company,
                                            document_type='pitch_deck')
        chunk = DocumentChunk.objects.create(document=doc, chunk_index=0, page_number=10, section_title='',
                                             raw_text=chunk_text, token_count=20)
        insight = IntelligenceInsight.objects.create(document=doc, insight_type='statement', category=category,
                                                     insight_text=insight_text, confidence_score=80)
        insight.source_chunks.set([chunk])
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay'):
            truth_delta_tasks.extract_claims_from_insights(doc.id)
        return list(ClaimedDatapoint.objects.filter(document=doc))

    def test_a_parent_figure_whose_span_dropped_the_owner_is_not_stored(self):
        chunk = "Unilever's ice cream unit generated $7.9B in 2024 sales"
        self.assertEqual(self.claims_for("Ben & Jerry's", chunk, 'generated $7.9B in 2024 sales'), [])

    def test_currency_parsing_does_not_admit_the_parents_euro_revenue(self):
        chunk = "Unilever's ice cream unit generated €7.9bn in 2024 sales"
        self.assertEqual(self.claims_for("Ben & Jerry's", chunk, 'generated €7.9bn in 2024 sales'), [])
        control = self.claims_for("Ben & Jerry's", "Ben & Jerry's generated €790M in 2024 sales",
                                  'generated €790M in 2024 sales')
        self.assertEqual([(c.claimed_value_numeric, c.currency, c.ownership) for c in control],
                         [(790_000_000, 'EUR', NAMED)])

    def test_named_and_implied_company_figures_are_stored_with_their_ownership(self):
        named = self.claims_for("Ben & Jerry's", "Ben & Jerry's generated $790M in 2024 sales",
                                'generated $790M in 2024 sales')
        self.assertEqual([(c.claimed_value_numeric, c.ownership) for c in named], [(790_000_000, NAMED)])
        implied = self.claims_for('Acme', 'Revenue: $4.5M', 'Revenue: $4.5M')
        self.assertEqual([(c.claimed_value_numeric, c.ownership) for c in implied], [(4_500_000, IMPLIED)])

    def test_a_platform_count_mentioning_the_company_later_is_not_stored(self):
        sentence = 'Telegram has 100M users and integrates with ManyChat'
        self.assertEqual(self.claims_for('ManyChat', sentence, sentence, 'Traction'), [])
        control = 'ManyChat has 2,000 customers and integrates with Telegram'
        stored = self.claims_for('ManyChat', control, control, 'Traction')
        self.assertEqual([(c.category, c.claimed_value_numeric, c.ownership) for c in stored],
                         [('customers', 2000, NAMED)])

    def test_a_platform_user_count_is_not_stored_as_customers(self):
        self.assertEqual(self.claims_for('ManyChat', 'Telegram has 100M users', '100M users', 'Traction'), [])
        control = self.claims_for('ManyChat', 'ManyChat has 2,000 customers', '2,000 customers', 'Traction')
        self.assertEqual([(c.category, c.ownership) for c in control], [('customers', NAMED)])

