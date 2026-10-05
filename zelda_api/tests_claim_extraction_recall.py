"""
Claim-extraction recall, PR 1: more claims from a deck, with no claim changing meaning.

The three-deck audit (docs/baselines/manychat/LEDGER.md, "Diagnosis") found that
a deck's claims could only come from one keyword-matched sentence per chunk per
category, with a vocabulary that missed a slide literally titled "Traction".
ManyChat's own ten slides produced zero claims; Ben & Jerry's produced zero.

The expected output for both decks was frozen in zelda_api/data/claim_recall/
BEFORE the code changed, from the stored chunk text of the audit runs. Every
recovered figure is asserted with its category, unit, slide and source sentence,
not just its number: a right number in the wrong category is the JoyToys failure
(a $250K raise filed as 250,000 customers), and it is worse than a missing claim.

Out of scope here, and reserved for PR 2 (fidelity): currency other than $,
period interpretation, attribution, and Truth Delta comparison.
"""
import hashlib
import json
import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from .intelligence_pipeline import ZeldaIntelligencePipelineV2
from .truth_delta_tasks import _extract_numeric_value

FIXTURES = Path(__file__).resolve().parent / 'data' / 'claim_recall'


def load_fixture(name):
    with open(FIXTURES / f'{name}.json', encoding='utf-8') as handle:
        return json.load(handle)


def sentences(text):
    """The sentence units the analyzer reads: the same split as _smart_extract."""
    return [s.strip() for s in re.split(r'(?<!\d)[.!?](?!\d)|\n', text) if s.strip()]


class FixtureIntegrityTests(SimpleTestCase):
    """The frozen fixtures are the audit's stored chunks, verbatim."""

    def test_fixture_chunks_are_the_stored_audit_chunks(self):
        for name in ('manychat', 'ben_jerrys'):
            fixture = load_fixture(name)
            path = Path(settings.BASE_DIR) / fixture['source']['path']
            # Git stores these files with LF; a Windows checkout writes CRLF. Hash the
            # LF form so the check means the same thing on every machine and in CI.
            raw = path.read_bytes().replace(b'\r\n', b'\n')
            self.assertEqual(hashlib.sha256(raw).hexdigest(), fixture['source']['sha256'], name)
            stored = [(r['page_number'], r['raw_text']) for r in json.loads(raw.decode('utf-8'))]
            self.assertEqual([(c['page_number'], c['raw_text']) for c in fixture['chunks']], stored, name)


class FrozenDeckExtractionTests(TestCase):
    """Stored chunk text -> analyzer -> claim gate, compared with the frozen expectation."""

    def setUp(self):
        from zelda_api.vector_models import DocumentSource
        self.user = get_user_model().objects.create_user('recall_owner', password='x')
        self.DocumentSource = DocumentSource

    def extract(self, name):
        from zelda_api import truth_delta_tasks
        from zelda_api.truth_delta_models import ClaimedDatapoint
        from zelda_api.vector_models import DocumentChunk

        fixture = load_fixture(name)
        doc = self.DocumentSource.objects.create(
            filename=f'{name}.pptx', source_entity=name, uploaded_by=self.user,
            document_type='pitch_deck', status='analyzing')
        for chunk in fixture['chunks']:
            DocumentChunk.objects.create(
                document=doc, chunk_index=chunk['chunk_index'], page_number=chunk['page_number'],
                section_title=chunk['section_title'], raw_text=chunk['raw_text'],
                token_count=chunk['token_count'])
        pipeline = ZeldaIntelligencePipelineV2()
        pipeline.used_chunks = set()
        pipeline._analyze_document(doc, '')
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay'):
            truth_delta_tasks.extract_claims_from_insights(doc.id)
        return fixture, list(ClaimedDatapoint.objects.filter(document=doc).order_by('id'))

    @staticmethod
    def row(claim):
        return (claim.category, claim.claimed_value_numeric, claim.unit, claim.page_number, claim.claimed_value)

    def assert_exactly_the_frozen_claims(self, name):
        fixture, claims = self.extract(name)
        expected = sorted(
            (e['category'], e['value'], e['unit'], e['page'], e['claimed_value'])
            for e in fixture['expected_claims'])
        self.assertEqual(sorted(self.row(c) for c in claims), expected)
        return fixture, claims

    def assert_sources(self, fixture, claims):
        """Each claim's text is a span of its declared source sentence, on its own slide."""
        by_page = {c['page_number']: c['raw_text'] for c in fixture['chunks']}
        for spec in fixture['expected_claims']:
            claim = next(c for c in claims if c.claimed_value == spec['claimed_value'])
            self.assertIn(spec['source_sentence'], sentences(by_page[spec['page']]), spec)
            self.assertIn(claim.claimed_value, spec['source_sentence'], spec)
            self.assertIn(claim.text_excerpt, spec['source_sentence'], spec)
            self.assertEqual(claim.category, spec['category'], spec)

    def assert_negatives(self, fixture, claims):
        values = {c.claimed_value_numeric for c in claims}
        for negative in fixture['negative_controls']:
            self.assertNotIn(negative['value'], values, negative)
        if any(n['page'] == 4 for n in fixture['negative_controls']):
            self.assertFalse([c for c in claims if c.page_number == 4])
        categories = {c.category for c in claims}
        for never in fixture['category_controls']['never']:
            self.assertNotIn(never, categories, fixture['category_controls']['why'])

    # --- ManyChat --------------------------------------------------------
    def test_manychat_yields_exactly_the_frozen_claims(self):
        self.assert_exactly_the_frozen_claims('manychat')

    def test_manychat_claims_carry_their_source_sentence_and_category(self):
        fixture, claims = self.assert_exactly_the_frozen_claims('manychat')
        self.assert_sources(fixture, claims)

    def test_manychat_platform_user_counts_are_not_company_claims(self):
        fixture, claims = self.extract('manychat')
        self.assert_negatives(fixture, claims)

    def test_bots_and_messages_are_never_customers(self):
        _, claims = self.extract('manychat')
        usage = [c for c in claims if c.category == 'usage']
        self.assertEqual(sorted(c.unit for c in usage), ['bots', 'messages'])
        self.assertFalse([c for c in claims if c.category == 'customers'])

    # --- Ben & Jerry's ---------------------------------------------------
    def test_ben_jerrys_yields_no_claims(self):
        fixture, claims = self.assert_exactly_the_frozen_claims('ben_jerrys')
        self.assertEqual(claims, [], fixture['why_no_positives'])

    def test_ben_jerrys_parent_euro_figure_share_and_years_stay_out(self):
        fixture, claims = self.extract('ben_jerrys')
        self.assert_negatives(fixture, claims)


class SpacedThousandsTests(SimpleTestCase):
    """Seed S-7: "140 000+ bots" parsed as 140."""

    def test_spaced_thousands_with_a_trailing_plus(self):
        self.assertEqual(_extract_numeric_value('140 000+ bots'), 140_000.0)

    def test_spaced_thousands_without_a_plus(self):
        self.assertEqual(_extract_numeric_value('140 000 bots'), 140_000.0)

    def test_several_spaced_groups(self):
        self.assertEqual(_extract_numeric_value('1 250 000 messages'), 1_250_000.0)

    def test_no_break_and_narrow_no_break_spaces(self):
        self.assertEqual(_extract_numeric_value('140 000 bots'), 140_000.0)
        self.assertEqual(_extract_numeric_value('140 000 bots'), 140_000.0)

    def test_comma_thousands_with_a_plus_still_parse(self):
        """Control: the separator that already worked."""
        self.assertEqual(_extract_numeric_value('140,000+ bots'), 140_000.0)

    def test_a_multiplier_with_a_plus(self):
        self.assertEqual(_extract_numeric_value('500M+ messages'), 500_000_000.0)

    def test_a_year_followed_by_a_count_is_not_joined(self):
        """2016 cannot open a spaced group: it is four digits, not one to three."""
        self.assertEqual(_extract_numeric_value('In 2016 500 customers signed up'), 500.0)

    def test_a_spaced_group_needs_exactly_three_digits(self):
        self.assertEqual(_extract_numeric_value('12 50 customers'), 12.0)

    def test_a_bare_year_is_still_skipped(self):
        self.assertIsNone(_extract_numeric_value('Founded in 2015'))


class UsageRoutingTests(SimpleTestCase):
    """Which claim category a Traction figure may be filed under, from its own words."""

    def setUp(self):
        self.pipeline = ZeldaIntelligencePipelineV2()

    def traction(self, sentence):
        keywords = self.pipeline.ANALYSIS_CATEGORIES['Traction']
        value, confidence, _ = self.pipeline._smart_extract('Traction', sentence, keywords)
        return value, confidence

    def test_a_bot_count_is_a_traction_figure(self):
        self.assertEqual(self.traction('140 000+ bots')[0], '140 000+ bots')

    def test_a_message_count_with_a_multiplier_is_a_traction_figure(self):
        value, confidence = self.traction('500M messages')
        self.assertEqual(value, '500M messages')
        self.assertEqual(confidence, 95.0)

    def test_a_customer_figure_wins_over_a_usage_figure_in_one_sentence(self):
        """Pre-PR behaviour is kept: the customer count is the claim, not the message count."""
        self.assertEqual(self.traction('We have 500M messages and 2,000 customers')[0][:15], '2,000 customers')
        self.assertTrue(self.traction('Serving 2,000 customers who sent 500M messages')[0].startswith('2,000 customers'))

    def test_a_platform_user_count_on_its_own_lines_matches_nothing(self):
        self.assertEqual(self.traction('FB Messenger\n900M\npeople'), (None, 0.0))

    def test_claim_category_follows_the_counted_noun(self):
        from .financial_metrics import usage_unit
        self.assertEqual(usage_unit('140 000+ bots'), 'bots')
        self.assertEqual(usage_unit('500M messages'), 'messages')
        self.assertEqual(usage_unit('500M messages from 2,000 customers'), 'messages')
        self.assertIsNone(usage_unit('2,000 customers sent 500M messages'))
        self.assertIsNone(usage_unit('5,000 customers'))
        self.assertIsNone(usage_unit('Total Bots Created'))


class UsageClaimTests(TestCase):
    """A usage insight becomes a `usage` claim with its noun as the unit -- never `customers`."""

    def setUp(self):
        from zelda_api.vector_models import DocumentChunk, DocumentSource
        self.user = get_user_model().objects.create_user('usage_owner', password='x')
        self.doc = DocumentSource.objects.create(
            filename='u.pptx', source_entity='U', uploaded_by=self.user,
            document_type='pitch_deck', status='analyzing')
        self.chunk = DocumentChunk.objects.create(
            document=self.doc, chunk_index=0, page_number=3, section_title='Traction',
            raw_text='x', token_count=1)

    def claims_for(self, *texts):
        from zelda_api import truth_delta_tasks
        from zelda_api.truth_delta_models import ClaimedDatapoint
        from zelda_api.vector_models import IntelligenceInsight
        for text in texts:
            insight = IntelligenceInsight.objects.create(
                document=self.doc, insight_type='statement', category='Traction',
                insight_text=text, confidence_score=95.0)
            insight.source_chunks.set([self.chunk])
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay'):
            truth_delta_tasks.extract_claims_from_insights(self.doc.id)
        return [(c.category, c.claimed_value_numeric, c.unit)
                for c in ClaimedDatapoint.objects.filter(document=self.doc).order_by('id')]

    def test_bots(self):
        self.assertEqual(self.claims_for('140 000+ bots'), [('usage', 140_000.0, 'bots')])

    def test_messages(self):
        self.assertEqual(self.claims_for('500M messages'), [('usage', 500_000_000.0, 'messages')])

    def test_customers_are_unchanged(self):
        self.assertEqual(self.claims_for('2,000 customers'), [('customers', 2_000.0, '')])

    def test_a_traction_sentence_counting_neither_is_still_refused(self):
        self.assertEqual(self.claims_for('Traction by Apr-16'), [])
