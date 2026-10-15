"""
RA-109 / I1: a usage figure keeps what it counts AND its measurement basis.

The frozen ManyChat deck states "500M messages" on slide 10 (no interval) and
"500M" / "messages/month" on two lines of slide 12. Before this change:

    1. slide 12's number and its rate sat on separate lines, so no sentence
       carried both and the rate was never a candidate;
    2. _select_insights deduplicated Traction figures by number alone, so even
       a repaired "500M messages/month" collapsed into slide 10's "500M
       messages" (and "500M bots" into "500M messages");
    3. the claim unit kept only the counted noun, so a rate lost its "/month".

The fix keeps the two figures distinct, stores the rate as the unit
("messages/month"), and states the measurement-basis difference as an internal
clarification note: never as external verification, never as a contradiction.

Ownership controls are part of the contract. Joining a figure line to its noun
line must never turn a platform's own count (slide 4: "Telegram / 100M /
people") into a ManyChat claim.
"""
import json
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .intelligence_pipeline import ZeldaIntelligencePipelineV2

FIXTURES = Path(__file__).resolve().parent / 'data' / 'claim_recall'


def ra109_expectation():
    with open(FIXTURES / 'manychat_ra109.json', encoding='utf-8') as handle:
        return json.load(handle)


def traction_candidates(text, names=()):
    """Every qualifying Traction value the analyzer collects from one chunk. `names` are the
    document's known subject names, as _analyze_document passes them."""
    pipeline = ZeldaIntelligencePipelineV2()
    collected = []
    pipeline._smart_extract('Traction', text, pipeline.ANALYSIS_CATEGORIES['Traction'], collect=collected,
                            subject_names=names)
    return [value for value, _, _ in collected]


# --- 1. the actual stored ManyChat chunks ------------------------------------------

class FrozenManyChatUsageTests(TestCase):
    """Stored chunks -> analyzer -> claim task: three distinct, correctly sourced usage claims."""

    def setUp(self):
        from .tests_claim_extraction_recall import FrozenDeckExtractionTests
        self.harness = FrozenDeckExtractionTests()
        self.harness.setUp()

    def test_the_slide_12_rate_is_a_third_usage_claim(self):
        _, claims = self.harness.extract('manychat')
        usage = sorted((c.page_number, c.unit, c.claimed_value_numeric, c.claimed_value)
                       for c in claims if c.category == 'usage')
        self.assertEqual(usage, [
            (10, 'bots', 140_000.0, '140 000+ bots'),
            (10, 'messages', 500_000_000.0, '500M messages'),
            (12, 'messages/month', 500_000_000.0, '500M messages/month'),
        ])

    def test_the_rate_claim_is_sourced_to_its_own_bounded_lines(self):
        _, claims = self.harness.extract('manychat')
        rate = next(c for c in claims if c.unit == 'messages/month')
        self.assertEqual(rate.page_number, 12)
        self.assertEqual(rate.source_sentence, '500M messages/month')
        self.assertEqual(rate.text_excerpt, '500M messages/month')
        self.assertEqual(rate.ownership, 'implied')
        self.assertEqual(rate.narrator, '')
        self.assertTrue(rate.chunk_hash)

    def test_the_traction_insights_keep_all_three_figures(self):
        from .vector_models import IntelligenceInsight
        _, claims = self.harness.extract('manychat')
        insights = IntelligenceInsight.objects.filter(document=claims[0].document, category='Traction')
        found = sorted((i.insight_text, i.source_chunks.first().page_number) for i in insights)
        self.assertEqual(found, [('140 000+ bots', 10), ('500M messages', 10), ('500M messages/month', 12)])

    def test_matches_the_frozen_claims_plus_the_additive_ra109_expectation(self):
        from .tests_claim_extraction_recall import load_fixture
        _, claims = self.harness.extract('manychat')
        expected = load_fixture('manychat')['expected_claims'] + ra109_expectation()['added_claims']
        self.assertEqual(
            sorted((c.category, c.claimed_value_numeric, c.unit, c.page_number, c.claimed_value) for c in claims),
            sorted((e['category'], e['value'], e['unit'], e['page'], e['claimed_value']) for e in expected))

    def test_platform_counts_on_slide_4_stay_out(self):
        _, claims = self.harness.extract('manychat')
        self.assertFalse([c for c in claims if c.page_number == 4])
        self.assertFalse({9e8, 2.75e8, 1e8} & {c.claimed_value_numeric for c in claims})


# --- 2. joining a figure line to its noun/rate line ------------------------------------

class SplitLineJoinTests(SimpleTestCase):

    def join(self, text, names=()):
        from .usage_basis import join_split_usage_lines
        return join_split_usage_lines(text, names)

    def test_same_slide_figure_and_rate_lines_are_admitted(self):
        # The block's label is the document's own subject ("ManyChat"), so the subject's
        # names are required; without them the label is an unknown owner (review of a5494ae).
        text = 'ManyChat\n140 000+ bots\n500M\nmessages/month\nLaunching on Facebook'
        self.assertIn('500M messages/month', self.join(text, ['ManyChat']).split('\n'))
        self.assertIn('500M messages/month', traction_candidates(text, ['ManyChat']))
        self.assertEqual(self.join(text), text)

    def test_a_figure_at_the_start_of_a_block_is_admitted(self):
        self.assertEqual(self.join('500M\nmessages'), '500M messages')
        self.assertEqual(self.join('Traction by Apr-16\n2M\nbots'), 'Traction by Apr-16\n2M bots')

    def test_only_the_two_lines_are_joined(self):
        text = 'Traction\n\n140 000+ bots\n500M\nmessages/month\nLaunching on Facebook\nMessenger this month'
        self.assertEqual(self.join(text).count('\n'), text.count('\n') - 1)

    def test_a_chunk_boundary_is_never_crossed(self):
        # Two chunks, each analyzed on its own: neither has both halves.
        self.assertNotIn('500M messages/month', traction_candidates('ManyChat\n140 000+ bots\n500M'))
        self.assertNotIn('500M messages/month', traction_candidates('messages/month\nLaunching on Facebook'))

    def test_intervening_prose_or_a_blank_line_refuses(self):
        for text in ('500M\nWe grew quickly across many new markets\nmessages/month',
                     '500M\n\nmessages/month'):
            with self.subTest(text=text):
                self.assertEqual(self.join(text), text)

    def test_competing_figures_refuse(self):
        for text in ('500M 20K\nmessages/month',                  # two figures on the number line
                     '120,000\n500M\nmessages/month',             # a bare figure above: an axis or a list
                     '500M\nmessages/month 20K'):                 # a figure on the noun line
            with self.subTest(text=text):
                self.assertEqual(self.join(text), text)

    def test_a_platform_label_above_refuses(self):
        for text in ('Telegram\n100M\nmessages/month', 'FB Messenger\n900M\nbots', 'Kik\n275M\nmessages'):
            with self.subTest(text=text):
                self.assertEqual(self.join(text), text)
                # A bare noun line was already a figureless candidate before RA-109;
                # no candidate may carry the platform's figure.
                self.assertFalse([c for c in traction_candidates(text) if any(ch.isdigit() for ch in c)])

    def test_a_continuation_or_owner_label_below_refuses(self):
        for text in ('500M\nmessages/month\nvia Telegram', '500M\nmessages/month\non partner platforms',
                     '500M\nmessages/month\nTelegram'):
            with self.subTest(text=text):
                self.assertEqual(self.join(text), text)

    def test_the_old_people_control_still_matches_nothing(self):
        self.assertEqual(traction_candidates('FB Messenger\n900M\npeople'), [])
        self.assertEqual(self.join('FB Messenger\n900M\npeople'), 'FB Messenger\n900M\npeople')

    def test_the_join_reads_figures_exactly_as_the_analyzer_does(self):
        from .usage_basis import TRACTION_NUMBER
        self.assertEqual(TRACTION_NUMBER, ZeldaIntelligencePipelineV2._TRACTION_NUMBER)

    def test_the_slide_4_chunk_is_unchanged(self):
        from .tests_claim_extraction_recall import load_fixture
        slide4 = next(c['raw_text'] for c in load_fixture('manychat')['chunks'] if c['page_number'] == 4)
        self.assertEqual(self.join(slide4), slide4)


# --- 3. ownership through the claim layer ------------------------------------------

class SplitLineOwnershipTests(TestCase):
    """A split platform-owned rate cannot become an implied company claim, by any route."""

    def setUp(self):
        from .vector_models import DocumentSource
        self.owner = get_user_model().objects.create_user('ra109_owner', password='x')
        self.doc = DocumentSource.objects.create(filename='d.pptx', source_entity='ManyChat',
                                                 uploaded_by=self.owner, document_type='pitch_deck')

    def claims_for(self, chunk_text, insight_text):
        from . import truth_delta_tasks
        from .truth_delta_models import ClaimedDatapoint
        from .vector_models import DocumentChunk, IntelligenceInsight
        chunk = DocumentChunk.objects.create(document=self.doc, chunk_index=0, page_number=4,
                                             section_title='', raw_text=chunk_text, token_count=5)
        insight = IntelligenceInsight.objects.create(document=self.doc, insight_type='statement',
                                                     category='Traction', insight_text=insight_text,
                                                     confidence_score=95.0)
        insight.source_chunks.set([chunk])
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay'):
            truth_delta_tasks.extract_claims_from_insights(self.doc.id)
        return list(ClaimedDatapoint.objects.filter(document=self.doc))

    def test_a_platform_rate_split_across_lines_is_refused_even_if_offered_as_an_insight(self):
        self.assertEqual(self.claims_for('Telegram\n100M\nmessages/month', '100M messages/month'), [])

    def test_an_unbounded_split_is_refused_at_the_claim_layer(self):
        self.assertEqual(self.claims_for('500M\nWe grew across markets\nmessages/month', '500M messages/month'), [])

    def test_the_company_rate_on_its_own_lines_is_kept_and_implied(self):
        claims = self.claims_for('140 000+ bots\n500M\nmessages/month', '500M messages/month')
        self.assertEqual([(c.unit, c.ownership, c.source_sentence) for c in claims],
                         [('messages/month', 'implied', '500M messages/month')])

    def test_a_dated_heading_over_a_joined_figure_stays_context(self):
        claims = self.claims_for('Traction by Apr-16\n2M\nbots', '2M bots')
        self.assertEqual([(c.unit, c.source_context, c.period_kind, c.period_end) for c in claims],
                         [('bots', 'Traction by Apr-16', '', None)])

    def test_end_to_end_the_analyzer_offers_no_figure_or_claim_from_a_platform_block(self):
        # The bare noun line ("messages/month") was already a figureless Traction insight
        # before RA-109 and still is; what must never appear is a figure or a claim.
        from . import truth_delta_tasks
        from .truth_delta_models import ClaimedDatapoint
        from .vector_models import DocumentChunk, IntelligenceInsight
        DocumentChunk.objects.create(document=self.doc, chunk_index=0, page_number=4, section_title='',
                                     raw_text='Telegram\n100M\nmessages/month\nKik\n275M\nbots', token_count=5)
        pipeline = ZeldaIntelligencePipelineV2()
        pipeline.used_chunks = set()
        pipeline._analyze_document(self.doc, '')
        texts = list(IntelligenceInsight.objects.filter(document=self.doc, category='Traction')
                     .values_list('insight_text', flat=True))
        self.assertFalse([t for t in texts if any(ch.isdigit() for ch in t)], texts)
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay'):
            truth_delta_tasks.extract_claims_from_insights(self.doc.id)
        self.assertFalse(ClaimedDatapoint.objects.filter(document=self.doc).exists())


# --- 4. deduplication by metric meaning ------------------------------------------

class UsageDedupTests(SimpleTestCase):

    def select(self, category, *texts):
        pipeline = ZeldaIntelligencePipelineV2()
        candidates = [(text, 95.0, None, None) for text in texts]
        return [c[0] for c in pipeline._select_insights(category, candidates, candidates[0])]

    def test_alternate_spellings_of_the_same_metric_and_basis_dedupe(self):
        self.assertEqual(self.select('Traction', '500M messages', '500 million messages'), ['500M messages'])
        self.assertEqual(self.select('Traction', '500M messages/month', '500M messages per month'),
                         ['500M messages/month'])

    def test_a_different_basis_survives(self):
        self.assertEqual(self.select('Traction', '500M messages', '500M messages/month'),
                         ['500M messages', '500M messages/month'])

    def test_a_different_noun_survives(self):
        self.assertEqual(self.select('Traction', '500M bots', '500M messages'), ['500M bots', '500M messages'])

    def test_a_different_number_survives(self):
        self.assertEqual(self.select('Traction', '500M messages', '600M messages/month'),
                         ['500M messages', '600M messages/month'])

    def test_customer_and_money_behaviour_is_unchanged(self):
        self.assertEqual(self.select('Traction', '2,000 customers', '2,000 customers in Europe'), ['2,000 customers'])
        self.assertEqual(self.select('Funding', '$5M raised', 'USD 5M raised'), ['$5M raised', 'USD 5M raised'])
        self.assertEqual(self.select('Funding', '$5M raised', '$5 million raised'), ['$5M raised'])

    def test_the_cap_is_unchanged(self):
        kept = self.select('Traction', '1M bots', '2M messages', '2M messages/month', '3M messages/day')
        self.assertEqual(len(kept), ZeldaIntelligencePipelineV2.MAX_INSIGHTS_PER_NUMERIC_CATEGORY)
        self.assertEqual(ZeldaIntelligencePipelineV2.MAX_INSIGHTS_PER_NUMERIC_CATEGORY, 3)


# --- 5. rate forms ---------------------------------------------------------------

class UsageBasisFormTests(SimpleTestCase):

    def basis(self, text):
        from .financial_metrics import usage_basis
        found = usage_basis(text)
        return None if found is None else (found.noun, found.rate, found.label)

    def test_monthly_forms(self):
        for text in ('500M messages/month', '500M messages / month', '500M messages per month',
                     '500M monthly messages', '500M messages/mo', '500M messages a month',
                     '500M messages sent per month'):
            with self.subTest(text=text):
                self.assertEqual(self.basis(text), ('messages', 'month', 'messages/month'))

    def test_other_supported_rates(self):
        self.assertEqual(self.basis('2M messages per day'), ('messages', 'day', 'messages/day'))
        self.assertEqual(self.basis('2M daily messages'), ('messages', 'day', 'messages/day'))
        self.assertEqual(self.basis('5,000 bots/week'), ('bots', 'week', 'bots/week'))
        self.assertEqual(self.basis('10M messages per year'), ('messages', 'year', 'messages/year'))

    def test_no_stated_interval(self):
        self.assertEqual(self.basis('500M messages'), ('messages', '', 'messages'))
        self.assertEqual(self.basis('140 000+ bots'), ('bots', '', 'bots'))
        self.assertEqual(self.basis('1 bot'), ('bots', '', 'bots'))

    def test_an_explicit_cumulative_total(self):
        self.assertEqual(self.basis('500M messages to date'), ('messages', 'cumulative', 'messages (cumulative)'))
        self.assertEqual(self.basis('500M cumulative messages'), ('messages', 'cumulative', 'messages (cumulative)'))

    def test_unsupported_denominators_are_refused_not_dropped(self):
        for text in ('500M messages per user', '500M messages/quarter', '500M messages per bot'):
            with self.subTest(text=text):
                self.assertIsNone(self.basis(text))

    def test_usage_unit_keeps_its_noun_only_contract(self):
        from .financial_metrics import usage_unit
        self.assertEqual(usage_unit('500M messages/month'), 'messages')
        self.assertEqual(usage_unit('500M messages'), 'messages')

    def test_not_a_usage_figure(self):
        self.assertIsNone(self.basis('2,000 customers'))
        self.assertIsNone(self.basis('Total Bots Created'))
        self.assertIsNone(self.basis('2,000 customers sent 500M messages'))


class UsageBasisClaimTests(TestCase):
    """The unit stored on the claim carries the rate; an unsupported denominator stores nothing."""

    def setUp(self):
        from .vector_models import DocumentChunk, DocumentSource
        self.user = get_user_model().objects.create_user('ra109_units', password='x')
        self.doc = DocumentSource.objects.create(filename='u.pptx', source_entity='U', uploaded_by=self.user,
                                                 document_type='pitch_deck')
        self.chunk = DocumentChunk.objects.create(document=self.doc, chunk_index=0, page_number=3,
                                                  section_title='', raw_text='x', token_count=1)

    def claims_for(self, *texts):
        from . import truth_delta_tasks
        from .truth_delta_models import ClaimedDatapoint
        from .vector_models import IntelligenceInsight
        for text in texts:
            insight = IntelligenceInsight.objects.create(document=self.doc, insight_type='statement',
                                                         category='Traction', insight_text=text,
                                                         confidence_score=95.0)
            insight.source_chunks.set([self.chunk])
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay'):
            truth_delta_tasks.extract_claims_from_insights(self.doc.id)
        return [(c.category, c.claimed_value_numeric, c.unit)
                for c in ClaimedDatapoint.objects.filter(document=self.doc).order_by('id')]

    def test_rate_units(self):
        self.assertEqual(sorted(self.claims_for('500M messages/month', '500M messages', '2M daily messages')), [
            ('usage', 2e6, 'messages/day'), ('usage', 5e8, 'messages'), ('usage', 5e8, 'messages/month')])

    def test_unsupported_denominator_is_not_stored(self):
        self.assertEqual(self.claims_for('500M messages per user'), [])


# --- 6. periods ------------------------------------------------------------------

class UsageBasisPeriodTests(TestCase):

    def setUp(self):
        from .tests_claim_extraction_recall import FrozenDeckExtractionTests
        self.harness = FrozenDeckExtractionTests()
        self.harness.setUp()

    def test_a_monthly_rate_invents_no_as_of_date(self):
        from .grounded_context import claim_dating
        _, claims = self.harness.extract('manychat')
        rate = next(c for c in claims if c.unit == 'messages/month')
        self.assertIsNone(rate.period_end)
        self.assertIsNone(rate.period_fiscal_year)
        self.assertEqual(claim_dating(rate)['as_of'], 'not stated')
        self.assertEqual(claim_dating(rate)['time_wording_allowed'], ())

    def test_slide_context_stays_context_and_a_bare_count_is_not_cumulative(self):
        _, claims = self.harness.extract('manychat')
        messages = next(c for c in claims if c.unit == 'messages' and c.page_number == 10)
        self.assertEqual(messages.source_context, 'Traction by Apr-16')
        self.assertEqual(messages.period_kind, '')
        self.assertNotIn('cumulative', messages.unit)


# --- 7-9. the basis note: grounded payload, reader, Truth Delta, and when it is silent --

def _claim(doc, value, unit, page, text, n):
    from .truth_delta_models import ClaimedDatapoint
    return ClaimedDatapoint.objects.create(
        document=doc, category='usage', claimed_value=text, claimed_value_numeric=value, unit=unit,
        page_number=page, ownership='implied', source_sentence=text, text_excerpt=text,
        chunk_hash=f'h{n}', confidence_in_extraction=95.0)


class BasisNoteTests(TestCase):

    def setUp(self):
        from .vector_models import DocumentSource
        self.owner = get_user_model().objects.create_user('ra109_note_owner', password='x')
        self.doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat',
                                                 uploaded_by=self.owner, document_type='pitch_deck')

    def notes(self):
        from .truth_delta_models import ClaimedDatapoint
        from .usage_basis import basis_notes
        return basis_notes(ClaimedDatapoint.objects.filter(document=self.doc).order_by('id'))

    def test_the_i1_pair_gets_one_neutral_note(self):
        a = _claim(self.doc, 5e8, 'messages', 10, '500M messages', 1)
        b = _claim(self.doc, 5e8, 'messages/month', 12, '500M messages/month', 2)
        notes = self.notes()
        self.assertEqual(len(notes), 1)
        note = notes[0]
        self.assertEqual(note.claim_ids, (a.id, b.id))
        self.assertEqual(note.pages, (10, 12))
        self.assertEqual(note.text, 'Page 10 states 500M messages without an explicit interval; page 12 states '
                                    '500M messages/month. These use different measurement bases and need '
                                    'clarification before comparison.')
        for word in ('contradict', 'verified', 'false', 'error', 'cannot both'):
            self.assertNotIn(word, note.text.lower())

    def test_no_note_for_same_basis_duplicates(self):
        _claim(self.doc, 5e8, 'messages', 10, '500M messages', 1)
        _claim(self.doc, 5e8, 'messages', 12, '500 million messages', 2)
        self.assertEqual(self.notes(), [])

    def test_no_note_for_different_metrics_or_different_numbers(self):
        _claim(self.doc, 5e8, 'bots', 10, '500M bots', 1)
        _claim(self.doc, 5e8, 'messages/month', 12, '500M messages/month', 2)
        _claim(self.doc, 2e7, 'messages', 11, '20M messages', 3)
        self.assertEqual(self.notes(), [])

    def test_an_explicit_cumulative_total_is_described_as_one(self):
        _claim(self.doc, 5e8, 'messages (cumulative)', 10, '500M messages to date', 1)
        _claim(self.doc, 5e8, 'messages/month', 12, '500M messages/month', 2)
        self.assertIn('Page 10 states 500M messages as a cumulative total;', self.notes()[0].text)


class BasisNoteInGroundedContextTests(TestCase):
    """The note reaches the memo payload from normalized facts and refs -- never raw text."""

    def setUp(self):
        from .tests_claim_extraction_recall import FrozenDeckExtractionTests
        self.harness = FrozenDeckExtractionTests()
        self.harness.setUp()
        _, self.claims = self.harness.extract('manychat')
        self.doc = self.claims[0].document

    def payload(self):
        from .grounded_context import GroundedContext
        from .principal import ORIGIN_TASK, Principal
        principal = Principal.for_user(self.doc.uploaded_by, ORIGIN_TASK, label='ra109 test')
        return GroundedContext.build(principal, self.doc).to_prompt_payload()

    def test_both_facts_and_their_sources_survive(self):
        payload = self.payload()
        rows = {(i['statement'], i['sources'][0].get('page')) for i in payload['items'] if i['kind'] == 'claim'}
        self.assertIn(('500M messages', 10), rows)
        self.assertIn(('500M messages/month', 12), rows)

    def test_the_note_names_both_refs_and_both_bounded_facts(self):
        payload = self.payload()
        refs = {i['statement']: i['ref'] for i in payload['items'] if i['kind'] == 'claim'}
        self.assertEqual(payload['consistency_notes'], [{
            'kind': 'measurement_basis',
            'refs': [refs['500M messages'], refs['500M messages/month']],
            'note': 'Page 10 states 500M messages without an explicit interval; page 12 states '
                    '500M messages/month. These use different measurement bases and need clarification '
                    'before comparison.',
        }])

    def test_no_raw_source_key_or_canary_text_crosses(self):
        blob = json.dumps(self.payload())
        for leak in ('angel.co', 'mike@manychat.com', 'Launching on Facebook', 'Messenger this month',
                     'CANARY', 'ANSWER_KEY', 'I1', 'cumulative by context', 'Recreated from public'):
            self.assertNotIn(leak, blob)

    def test_a_document_without_a_basis_pair_has_no_notes_key(self):
        from .truth_delta_models import ClaimedDatapoint
        ClaimedDatapoint.objects.filter(document=self.doc, unit='messages/month').delete()
        self.assertNotIn('consistency_notes', self.payload())

    def test_the_memo_prompt_says_a_note_is_not_a_contradiction(self):
        from .grounded_context import GroundedContext
        from .principal import ORIGIN_TASK, Principal
        context = GroundedContext.build(Principal.for_user(self.doc.uploaded_by, ORIGIN_TASK, label='t'), self.doc)
        captured = {}

        class Messages:
            def create(self, **kwargs):
                captured.update(kwargs)
                raise RuntimeError('stop after capture')

        client = mock.Mock(messages=Messages())
        with mock.patch('zelda_api.anthropic_client.background_anthropic_client', return_value=client):
            try:
                ZeldaIntelligencePipelineV2()._call_claude_for_memo(context)
            except Exception:
                pass
        self.assertIn('11. Consistency notes.', captured['system'])
        self.assertIn('not a contradiction', captured['system'])
        self.assertIn('"consistency_notes"', captured['messages'][0]['content'])


class BasisNoteOnTruthDeltaPageTests(TestCase):

    def setUp(self):
        from .vector_models import DocumentSource
        User = get_user_model()
        self.owner = User.objects.create_user('ra109_page_owner', password='x')
        self.doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat',
                                                 uploaded_by=self.owner, document_type='pitch_deck',
                                                 status='analyzed')
        _claim(self.doc, 5e8, 'messages', 10, '500M messages', 1)
        _claim(self.doc, 5e8, 'messages/month', 12, '500M messages/month', 2)

    def page(self):
        return self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id]))

    def test_the_owner_sees_the_note(self):
        self.client.force_login(self.owner)
        html = self.page().content.decode()
        self.assertIn('Measurement basis to clarify', html)
        self.assertIn('These use different measurement bases and need clarification before comparison.', html)

    def test_anonymous_sees_nothing(self):
        response = self.page()
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(b'measurement bases', response.content)

    def test_no_note_without_a_basis_pair(self):
        from .truth_delta_models import ClaimedDatapoint
        ClaimedDatapoint.objects.filter(document=self.doc, unit='messages/month').delete()
        self.client.force_login(self.owner)
        self.assertNotIn('Measurement basis to clarify', self.page().content.decode())


class BasisNoteIsNotVerificationTests(TestCase):
    """Truth Delta states and score are untouched: no observation means INSUFFICIENT."""

    def setUp(self):
        from .vector_models import DocumentSource
        self.owner = get_user_model().objects.create_user('ra109_td_owner', password='x')
        self.doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat',
                                                 uploaded_by=self.owner, document_type='pitch_deck')
        _claim(self.doc, 5e8, 'messages', 10, '500M messages', 1)

    def verify(self):
        from .truth_delta_engine import TruthDeltaEngine
        engine = TruthDeltaEngine()
        claude = {'overall_truth_score': None, 'credibility_risk': 'unknown', 'summary': 'x', 'per_claim': []}
        with mock.patch.object(engine, '_call_claude_for_verification', return_value=claude), \
             mock.patch('zelda_api.truth_delta_engine.data_source_manager') as sources:
            sources.create_observed_datapoints.return_value = None
            sources.fetch_news_headlines.return_value = []
            return engine.verify_document(self.doc.id)

    def test_the_rate_pair_stays_insufficient_with_no_contradiction_and_the_same_score(self):
        before = self.verify()
        _claim(self.doc, 5e8, 'messages/month', 12, '500M messages/month', 2)
        after = self.verify()
        self.assertEqual(after.category_states(), {'usage': 'no_data'})
        stats = after.claim_stats()
        self.assertEqual((stats.get('verified', 0), stats.get('contradicted', 0)), (0, 0))
        self.assertEqual(after.overall_truth_score, before.overall_truth_score)
        self.assertNotIn('measurement', json.dumps(after.details, default=str).lower())


# --- review of a5494ae: three source-fidelity failures ---------------------------------

class _ClaimTaskHarness(TestCase):
    """The real analyzer and the real claim task on one chunk of a ManyChat document."""

    def setUp(self):
        from .vector_models import DocumentSource
        self.owner = get_user_model().objects.create_user('ra109_review_owner', password='x')
        self.doc = DocumentSource.objects.create(filename='d.pptx', source_entity='ManyChat',
                                                 uploaded_by=self.owner, document_type='pitch_deck')

    def reset(self):
        from .truth_delta_models import ClaimedDatapoint
        from .vector_models import DocumentChunk, IntelligenceInsight
        ClaimedDatapoint.objects.filter(document=self.doc).delete()
        IntelligenceInsight.objects.filter(document=self.doc).delete()
        DocumentChunk.objects.filter(document=self.doc).delete()

    def analyze(self, chunk_text):
        """Chunk -> _analyze_document -> extract_claims_from_insights; returns the claims."""
        from . import truth_delta_tasks
        from .truth_delta_models import ClaimedDatapoint
        from .vector_models import DocumentChunk
        self.reset()
        DocumentChunk.objects.create(document=self.doc, chunk_index=0, page_number=5, section_title='',
                                     raw_text=chunk_text, token_count=5)
        pipeline = ZeldaIntelligencePipelineV2()
        pipeline.used_chunks = set()
        pipeline._analyze_document(self.doc, '')
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay'):
            truth_delta_tasks.extract_claims_from_insights(self.doc.id)
        return list(ClaimedDatapoint.objects.filter(document=self.doc).order_by('id'))

    def offer(self, chunk_text, *insight_texts):
        """Insights handed straight to the claim task (the claim-admission gate on its own)."""
        from . import truth_delta_tasks
        from .truth_delta_models import ClaimedDatapoint
        from .vector_models import DocumentChunk, IntelligenceInsight
        self.reset()
        chunk = DocumentChunk.objects.create(document=self.doc, chunk_index=1, page_number=6, section_title='',
                                             raw_text=chunk_text, token_count=5)
        for text in insight_texts:
            insight = IntelligenceInsight.objects.create(document=self.doc, insight_type='statement',
                                                         category='Traction', insight_text=text,
                                                         confidence_score=95.0)
            insight.source_chunks.set([chunk])
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay'):
            truth_delta_tasks.extract_claims_from_insights(self.doc.id)
        return list(ClaimedDatapoint.objects.filter(document=self.doc).order_by('id'))


PLATFORM_BLOCKS = (
    'Telegram\n\n500M\nmessages/month',                       # owner label above a layout blank
    'Telegram\n100M bots\n500M\nmessages/month',              # owner label above a sibling metric
    'Telegram\n\n100M bots\n\n500M\nmessages/month',          # both
    '500M\nmessages/month\nTelegram Messaging Service',       # a longer owner label below
    '500M\nmessages/month\n\nTelegram',                       # owner label below a layout blank
    '500M\nmessages/month\n100M bots\nTelegram',              # below a sibling metric
    'FB Messenger\n\n\n900M\nbots',
)


class BlockOwnershipTests(_ClaimTaskHarness):
    """Finding 1: a blank line or a sibling metric must not hide the block's owner."""

    def test_the_helper_refuses_every_platform_block(self):
        from .usage_basis import join_split_usage_lines
        for text in PLATFORM_BLOCKS:
            with self.subTest(text=text):
                self.assertEqual(join_split_usage_lines(text, ['ManyChat']), text)

    def test_the_analyzer_offers_no_platform_figure(self):
        for text in PLATFORM_BLOCKS:
            with self.subTest(text=text):
                figures = [c for c in traction_candidates(text, ['ManyChat']) if '500M' in c or '900M' in c]
                self.assertEqual(figures, [])

    def test_no_claim_end_to_end(self):
        for text in PLATFORM_BLOCKS:
            with self.subTest(text=text):
                claims = self.analyze(text)
                self.assertFalse([c for c in claims if c.claimed_value_numeric in (5e8, 9e8)],
                                 [(c.claimed_value, c.unit, c.ownership) for c in claims])

    def test_claim_admission_refuses_a_joined_span_from_a_platform_block(self):
        for text in PLATFORM_BLOCKS[:6]:
            with self.subTest(text=text):
                self.assertEqual([(c.claimed_value, c.ownership) for c in self.offer(text, '500M messages/month')], [])

    def test_company_owned_blocks_are_kept(self):
        for text in ('ManyChat\n140 000+ bots\n500M\nmessages/month\nLaunching on Facebook',
                     'ManyChat\n\n500M\nmessages/month',
                     'Traction by Apr-16\n\n140 000+ bots\n500M\nmessages/month',
                     '140 000+ bots\n\n500M\nmessages/month\n\nLaunching on Facebook'):
            with self.subTest(text=text):
                rate = [(c.unit, c.ownership, c.source_sentence) for c in self.analyze(text)
                        if c.unit == 'messages/month']
                self.assertEqual(rate, [('messages/month', 'implied', '500M messages/month')])

    def test_an_unknown_label_is_refused_and_the_subject_label_admitted(self):
        from .usage_basis import join_split_usage_lines
        self.assertEqual(join_split_usage_lines('Acme\n500M\nmessages', ['Acme']), 'Acme\n500M messages')
        self.assertEqual(join_split_usage_lines('Acme\n500M\nmessages', []), 'Acme\n500M\nmessages')
        self.assertEqual(join_split_usage_lines('Acme\n500M\nmessages', ['ManyChat']), 'Acme\n500M\nmessages')


class DenominatorTests(_ClaimTaskHarness):
    """Finding 2: a numeric or compound denominator is refused, never simplified."""

    UNREPRESENTABLE = ('500M messages per 2 months', '500M messages/2 months', '500M messages every 2 months',
                       '500M messages/month per user', '500M messages per month per user',
                       '500M messages per month, per user', '500M messages/day/user', '500M bi-monthly messages')

    def test_the_helper_refuses_them(self):
        from .financial_metrics import usage_basis
        for text in self.UNREPRESENTABLE:
            with self.subTest(text=text):
                self.assertIsNone(usage_basis(text))

    def test_supported_controls_still_hold(self):
        from .financial_metrics import usage_basis
        for text, label in (('500M messages/month', 'messages/month'), ('500M messages per month', 'messages/month'),
                            ('500M messages every month', 'messages/month'), ('2M messages per day', 'messages/day'),
                            ('5,000 bots/week', 'bots/week'), ('10M messages per year', 'messages/year'),
                            ('500M messages a month', 'messages/month'), ('500M messages', 'messages'),
                            ('500M messages/month.', 'messages/month'),
                            ('500M messages per month across 40 countries', 'messages/month')):
            with self.subTest(text=text):
                self.assertEqual(usage_basis(text).label, label)

    def test_selection_does_not_keep_an_unrepresentable_rate(self):
        pipeline = ZeldaIntelligencePipelineV2()
        texts = ('500M messages', '500M messages per 2 months', '500M messages/month per user', '500M messages/month')
        candidates = [(t, 95.0, None, None) for t in texts]
        self.assertEqual([c[0] for c in pipeline._select_insights('Traction', candidates, candidates[0])],
                         ['500M messages', '500M messages/month'])

    def test_the_claim_task_stores_neither(self):
        claims = self.offer('x', '500M messages per 2 months', '500M messages/month per user')
        self.assertEqual([(c.claimed_value, c.unit) for c in claims], [])


class CumulativeBindingTests(_ClaimTaskHarness):
    """Finding 3: cumulative wording counts only inside the usage figure's own phrase."""

    def test_wording_that_belongs_elsewhere_leaves_the_basis_unspecified(self):
        from .financial_metrics import usage_basis
        for text in ('500M messages with lifetime customer support', '500M messages; bots tracked since launch',
                     '500M messages and a cumulative rise in signups', '500M messages, total revenue undisclosed'):
            with self.subTest(text=text):
                self.assertEqual(usage_basis(text).label, 'messages')

    def test_the_figures_own_cumulative_wording_still_counts(self):
        from .financial_metrics import usage_basis
        for text in ('500M messages to date', '500M messages sent to date', '500M cumulative messages',
                     '500M total messages', '500M messages since launch', '500M lifetime messages',
                     '500M messages cumulatively'):
            with self.subTest(text=text):
                self.assertEqual(usage_basis(text).label, 'messages (cumulative)')

    def test_the_claim_task_and_the_note_do_not_borrow_it(self):
        from .usage_basis import basis_notes
        claims = self.offer('x', '500M messages with lifetime customer support', '500M messages')
        self.assertEqual(sorted(c.unit for c in claims), ['messages', 'messages'])
        self.assertEqual(basis_notes(claims), [])
