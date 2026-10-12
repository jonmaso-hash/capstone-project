"""
Funding-source fidelity, from the live ManyChat run's memo 94 (document 3136;
owner grade: partial pass). The sentences below are memo 94's own, verbatim
from docs/baselines/manychat/postfix-a975af3/pass-a/09_memo.json, with that
run's refs: S1/C3 bots, S2/C2 messages, S3/C1 "$23.1M raised" (narrator Pitch
Deck Hunt), P1 stage, P2 sector.
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .funding_fidelity import NO_PREMISE, PROFILE_UNDATED, funding_facts, guard_funding_fidelity
from .grounded_context import INSUFFICIENT, SELF_REPORTED, GroundedItem, SourceRef

User = get_user_model()
PDH = 'Pitch Deck Hunt'


def memo94_items(**extra):
    page = lambda n: (SourceRef(document_id=3136, page_number=n),)
    return [
        GroundedItem(ref='C1', kind='claim', category='funding_raised', statement='$23.1M raised', status=INSUFFICIENT,
                     sources=page(2), dated=True, narrator=PDH, as_of='not stated', dates_not_as_of=('2015',)),
        GroundedItem(ref='C2', kind='claim', category='usage', statement='500M messages', status=INSUFFICIENT,
                     sources=page(10), dated=True, as_of='not stated', source_context='Traction by Apr-16'),
        GroundedItem(ref='C3', kind='claim', category='usage', statement='140 000+ bots', status=INSUFFICIENT,
                     sources=page(10), dated=True, as_of='not stated', source_context='Traction by Apr-16'),
        GroundedItem(ref='S1', kind='statement', category='Traction', statement='140 000+ bots', status=SELF_REPORTED,
                     sources=page(10), dated=True, as_of='not stated', source_context='Traction by Apr-16'),
        GroundedItem(ref='S2', kind='statement', category='Traction', statement='500M messages', status=SELF_REPORTED,
                     sources=page(10), dated=True, as_of='not stated', source_context='Traction by Apr-16'),
        GroundedItem(ref='S3', kind='statement', category='Funding', statement='$23.1M raised', status=SELF_REPORTED,
                     sources=page(2), dated=True, narrator=PDH, as_of='not stated', dates_not_as_of=('2015',)),
        GroundedItem(ref='P1', kind='profile', category='Stage (profile)', statement='Stage (profile): Series A',
                     status=SELF_REPORTED, sources=(SourceRef(document_id=None, profile_field='stage'),)),
        GroundedItem(ref='P2', kind='profile', category='Sector (profile)', statement='Sector (profile): Software',
                     status=SELF_REPORTED, sources=(SourceRef(document_id=None, profile_field='sector'),)),
        *extra.get('more', ()),
    ]


def guard(text, items=None):
    return guard_funding_fidelity(text, funding_facts(items or memo94_items()))[0]


class AttributionTests(SimpleTestCase):
    """Each section, bullet and question stands alone in a Lite view: it names the narrator itself."""

    CASES = {
        'information_readiness (Lite)': (
            '• Funding raised figure (self-reported, unverified): $23.1M [S3]',
            '• Funding raised figure (reported by Pitch Deck Hunt, unverified): $23.1M [S3]'),
        'base_scenario': (
            'and stated funding of $23.1M [S3].',
            'and stated funding of $23.1M (per Pitch Deck Hunt) [S3].'),
        'risk_assessment': (
            '1. Unverified funding figure: The $23.1M raised figure [S3] was checked but no external evidence could '
            'confirm or contradict it [C1], leaving the capital structure unresolvable from available materials.',
            '1. Unverified funding figure: The $23.1M raised figure (per Pitch Deck Hunt) [S3] was checked but no '
            'external evidence could confirm or contradict it [C1], leaving the capital structure unresolvable from '
            'available materials.'),
        'open_concerns (Lite)': (
            '• The $23.1M raised figure [S3] was checked and no external evidence could establish or contradict it [C1]; '
            'the capital structure and investor base remain unknown, which is critical for evaluating dilution and runway.',
            '• The $23.1M raised figure (per Pitch Deck Hunt) [S3] was checked and no external evidence could establish or '
            'contradict it [C1]; the capital structure and investor base remain unknown, which is critical for '
            'evaluating dilution and runway.'),
        'what_would_change_the_picture (Lite), uncited': (
            'alongside an independent confirmation of the $23.1M funding raised would most materially change what is known',
            'alongside an independent confirmation of the $23.1M funding raised (per Pitch Deck Hunt) would most '
            'materially change what is known'),
        'zelda_advantage': (
            'and the $23.1M funding figure [C1] were checked against external sources',
            'and the $23.1M funding figure (per Pitch Deck Hunt) [C1] were checked against external sources'),
        'question, uncited': (
            '- Who are the investors behind the $23.1M raised, and can you provide a current cap table and '
            'round-by-round breakdown?',
            '- Who are the investors behind the $23.1M raised (per Pitch Deck Hunt), and can you provide a current cap '
            'table and round-by-round breakdown?'),
        'memo 91 wording': (
            'The company states it has raised $23.1M [S3].',
            'Pitch Deck Hunt reports it has raised $23.1M [S3].'),
        'other spelling of the figure': (
            'Funding of $23.1 million [C1] is unconfirmed.',
            'Funding of $23.1 million (per Pitch Deck Hunt) [C1] is unconfirmed.'),
    }

    def test_memo_94_sentences_name_the_narrator(self):
        for name, (before, after) in self.CASES.items():
            with self.subTest(case=name):
                self.assertEqual(guard(before), after)

    def test_sentences_that_already_name_it_or_do_not_state_it_are_unchanged(self):
        for text in (
            # memo 94's executive summary and financial analysis
            'Pitch Deck Hunt lists $23.1M raised [S3], though this figure has not been independently verified.',
            '• Funding raised: Pitch Deck Hunt lists $23.1M raised [S3]; this could not be confirmed against external '
            'sources [C1] and should be treated as unverified.',
            # cites the claim but states no amount
            '• Funding raised figure requires external confirmation [C1]',
            # the company's own traction stays self-reported
            '• Bot count traction metric (self-reported, contextually dated Apr-16): 140,000+ bots [S1]',
            'All traction figures—140,000+ bots and 500M messages—are self-reported [S1, S2] from a contextually dated slide',
            # a different amount
            'A $2.31M seed and $23.15M are other figures.',
        ):
            with self.subTest(text=text[:60]):
                self.assertEqual(guard(text), text)

    def test_a_sentence_mixing_sources_names_the_deck_not_the_company_or_the_narrator(self):
        # The bots are the company's; the $23.1M is Pitch Deck Hunt's listing. Neither may take the other's source.
        self.assertEqual(
            guard('The company states it has raised $23.1M [S3] and reports 140,000+ bots [S1].'),
            'The deck states it has raised $23.1M (per Pitch Deck Hunt) [S3] and reports 140,000+ bots [S1].')

    def test_the_figure_phrase_is_not_split(self):
        self.assertEqual(guard('- What is the total raised beyond the $23.1M listed [S3]?'),
                         '- What is the total raised beyond the $23.1M listed (per Pitch Deck Hunt) [S3]?')

    def test_self_reported_covering_other_figures_is_not_reassigned(self):
        text = 'The self-reported figures [S1, S3] include $23.1M.'
        self.assertEqual(guard(text), 'The self-reported figures [S1, S3] include $23.1M (per Pitch Deck Hunt).')

    def test_a_figure_without_a_narrator_is_left_alone(self):
        items = [i for i in memo94_items() if i.ref not in ('C1', 'S3')] + [
            GroundedItem(ref='S3', kind='statement', category='Funding', statement='$23.1M raised',
                         status=SELF_REPORTED, sources=(SourceRef(document_id=1, page_number=2),))]
        text = '• Funding raised figure (self-reported, unverified): $23.1M [S3]'
        self.assertEqual(guard(text, items), text)


class FundingIsNotARaiseTests(SimpleTestCase):

    def test_reported_funding_is_not_a_financing_event(self):
        before = ('If the traction metrics [S1, S2] were not independently validated and the $23.1M raise [S3] cannot be '
                  'confirmed, the available evidence reduces to two self-reported usage figures')
        self.assertEqual(guard(before), (
            'If the traction metrics [S1, S2] were not independently validated and the reported $23.1M (per Pitch Deck '
            'Hunt) [S3] cannot be confirmed, the available evidence reduces to two self-reported usage figures'))

    def test_unsupported_raise_premises_are_removed_and_the_questions_kept(self):
        cases = {
            '- What is the current monthly burn rate, and what runway does the stated raise provide at current burn?':
                f'- What is the current monthly burn rate, and what runway does {NO_PREMISE} provide at current burn?',
            '- What is the intended use of proceeds from this raise, broken down by category?':
                f'- What is the intended use of proceeds from {NO_PREMISE}, broken down by category?',
            '• No revenue, burn, or financial operating data was extracted, meaning it is not possible to determine '
            'whether the platform\'s usage translates into commercial activity or how long the company can operate on '
            'its stated raise.':
                '• No revenue, burn, or financial operating data was extracted, meaning it is not possible to determine '
                'whether the platform\'s usage translates into commercial activity or how long the company can operate '
                f'on {NO_PREMISE}.',
        }
        for before, after in cases.items():
            with self.subTest(text=before[:50]):
                self.assertEqual(guard(before), after)

    def test_legitimate_questions_without_a_premise_are_unchanged(self):
        for text in ('- What is the current monthly burn rate?',
                     '- Is the company planning to raise, and how much?',
                     '- Who led the 2019 Series A round?',
                     '- Can you provide a round-by-round breakdown?',
                     '• Use of proceeds: Not found in the extracted evidence.'):
            with self.subTest(text=text):
                self.assertEqual(guard(text), text)

    def test_a_raise_in_the_evidence_keeps_its_wording(self):
        text = '- What is the intended use of proceeds from this raise, broken down by category?'
        public_raise = GroundedItem(ref='P3', kind='profile', category='Raising (profile)',
                                    statement='Raising (profile): 5000000.00 USD', status=SELF_REPORTED,
                                    sources=(SourceRef(document_id=None, profile_field='raising_amount'),))
        seeking = GroundedItem(ref='S4', kind='statement', category='Funding', statement='Seeking $5M seed round',
                               status=SELF_REPORTED, sources=(SourceRef(document_id=1, page_number=11),))
        zero_raise = GroundedItem(ref='P3', kind='profile', category='Raising (profile)',
                                  statement='Raising (profile): 0.00 USD', status=SELF_REPORTED,
                                  sources=(SourceRef(document_id=None, profile_field='raising_amount'),))
        for name, item, expected in (('profile raising 5M', public_raise, text), ('deck says seeking', seeking, text),
                                     ('profile raising 0', zero_raise, text.replace('this raise', NO_PREMISE))):
            with self.subTest(case=name):
                self.assertEqual(guard(text, memo94_items(more=[item])), expected)


class ProfileIsUndatedTests(SimpleTestCase):

    def test_profile_stage_is_kept_apart_from_the_slide_date(self):
        before = ('Taking the extracted evidence at face value: ManyChat was a Series A software company [P1, P2] with '
                  'meaningful early platform traction as of April 2016 [S1, S2] and stated funding of $23.1M [S3].')
        self.assertEqual(guard(before), (
            f'Taking the extracted evidence at face value: ManyChat was a Series A software company [P1, P2] '
            f'{PROFILE_UNDATED} with meaningful early platform traction as of April 2016 [S1, S2] and stated funding of '
            f'$23.1M (per Pitch Deck Hunt) [S3].'))

    def test_undated_profile_sentences_and_dated_slide_sentences_are_unchanged(self):
        for text in (
            'ManyChat is a software company (the company states sector is Software [P2]) operating at Series A stage '
            '(the company states [P1]).',
            '• Stage classification: Series A [P1]',
            "As of the slide context dated 'Traction by Apr-16,' the company states it had deployed 140,000+ bots and "
            'processed 500M messages [S1, S2].',
        ):
            with self.subTest(text=text[:50]):
                self.assertEqual(guard(text), text)

    def test_guard_is_idempotent_and_keeps_layout(self):
        text = ('• Funding raised figure (self-reported, unverified): $23.1M [S3]\n'
                '• Stage classification: Series A [P1]\n\n'
                '- What is the intended use of proceeds from this raise?')
        once = guard(text)
        self.assertEqual(guard(once), once)
        self.assertEqual(once.count('\n'), text.count('\n'))


class MemoWriterTests(TestCase):
    """Real ManyChat extraction -> GroundedContext -> _generate_memo (mocked model reply with memo 94's
    sentences) -> stored memo -> every consumer: full and Lite IC memo, Lite memo API, Markdown, overview."""

    def setUp(self):
        from matchmaking.models import Application
        from matchmaking.tests import _mock_embedding_generation
        from .tests_claim_context_dates import SLIDE2, SLIDE10
        from .vector_models import DocumentChunk, DocumentSource
        from . import truth_delta_tasks
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('ff_owner', password='x')
        self.app = Application.objects.create(
            user=self.owner, company_name='ManyChat', founder_name='F', email='ff@t.test',
            description='d', sector='Software', stage='Series A', is_premium=False,
            prior_amount_raised=163000000, raising_amount=0)
        self.doc = DocumentSource.objects.create(filename='manychat.pdf', source_entity='ManyChat',
                                                 uploaded_by=self.owner, document_type='pitch_deck', status='analyzed')
        for index, (page, text) in enumerate(((2, SLIDE2), (10, SLIDE10))):
            DocumentChunk.objects.create(document=self.doc, chunk_index=index, page_number=page, raw_text=text, token_count=60)
        ZeldaIntelligencePipelineV2()._analyze_document(self.doc, '')
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay'):
            truth_delta_tasks.extract_claims_from_insights(self.doc.id)

    def generate(self):
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .tests import grounded_context_for
        context = grounded_context_for(self.doc)
        ref = {(i.kind, i.statement): i.ref for i in context.items}
        s3, c1 = ref[('statement', '$23.1M raised')], ref[('claim', '$23.1M raised')]
        s1, s2 = ref[('statement', '140 000+ bots')], ref[('statement', '500M messages')]
        profile = ', '.join(i.ref for i in context.items if i.kind == 'profile')
        sections = {   # memo 94's sentences, refs mapped to this context
            'executive_summary': f'Pitch Deck Hunt lists $23.1M raised [{s3}], though this figure has not been '
                                 f'independently verified.',
            'information_readiness': f'Score: 10/100\nPresent:\n• Funding raised figure (self-reported, unverified): '
                                     f'$23.1M [{s3}]',
            'open_concerns': [f'The $23.1M raised figure [{s3}] was checked and no external evidence could establish or '
                              f'contradict it [{c1}].',
                              'No revenue, burn, or financial operating data was extracted, meaning it is not possible to '
                              'determine how long the company can operate on its stated raise.'],
            'what_would_change_the_picture': 'An independent confirmation of the $23.1M funding raised would most '
                                             'materially change what is known.',
            'base_scenario': f'ManyChat was a Series A software company [{profile}] with meaningful early platform '
                             f'traction as of April 2016 [{s1}, {s2}] and stated funding of $23.1M [{s3}].',
            'downside_scenario': f'If the $23.1M raise [{s3}] cannot be confirmed, little remains.',
            'questions_for_management': [
                'Who are the investors behind the $23.1M raised, and can you provide a current cap table?',
                'What is the current monthly burn rate, and what runway does the stated raise provide at current burn?',
                'What is the intended use of proceeds from this raise, broken down by category?'],
            'evidence_level': 'LITTLE_EVIDENCE',
        }
        response = mock.Mock()
        response.content = [mock.Mock(text=json.dumps(sections))]
        response.usage = mock.Mock(input_tokens=1, output_tokens=1)
        with mock.patch('anthropic.Anthropic') as client_cls:
            client_cls.return_value.messages.create.return_value = response
            result = ZeldaIntelligencePipelineV2()._generate_memo(context)
            call = client_cls.return_value.messages.create.call_args.kwargs
        self.assertNotIn('error', result, result.get('error'))
        from .vector_models import IntelligenceMemo
        return IntelligenceMemo.objects.get(pk=result['memo_id']), call, profile

    def assert_faithful(self, text, where):
        with self.subTest(surface=where):
            self.assertNotIn('self-reported, unverified): $23.1M', text)
            self.assertNotIn('stated raise', text)
            self.assertNotIn('this raise', text)
            self.assertNotIn('$23.1M raise ', text)
            self.assertIn('Pitch Deck Hunt', text)

    def test_stored_memo_is_faithful_and_structure_is_unchanged(self):
        memo, call, profile = self.generate()
        self.assertIn('(reported by Pitch Deck Hunt, unverified): $23.1M', memo.information_readiness)
        self.assertIn('$23.1M raised figure (per Pitch Deck Hunt) [S', memo.open_concerns)
        self.assertIn(f'operate on {NO_PREMISE}.', memo.open_concerns)
        self.assertIn('$23.1M funding raised (per Pitch Deck Hunt) would', memo.what_would_change_the_picture)
        self.assertIn(f'[{profile}] {PROFILE_UNDATED} with meaningful early platform traction as of April 2016',
                      memo.base_scenario)
        self.assertIn('the reported $23.1M (per Pitch Deck Hunt) [S', memo.downside_scenario)
        self.assertEqual(memo.questions_for_management.splitlines(), [
            '- Who are the investors behind the $23.1M raised (per Pitch Deck Hunt), and can you provide a current cap '
            'table?',
            f'- What is the current monthly burn rate, and what runway does {NO_PREMISE} provide at current burn?',
            f'- What is the intended use of proceeds from {NO_PREMISE}, broken down by category?'])
        self.assertTrue(memo.executive_summary.startswith('Pitch Deck Hunt lists $23.1M raised [S'))   # already named:
        self.assertNotIn('(per Pitch Deck Hunt)', memo.executive_summary)                              # unchanged
        # Prompt rule 10, and the raw-source boundary is unchanged.
        self.assertIn('10. Funding and the profile.', call['system'])
        self.assertNotIn('Series A deck with', call['messages'][0]['content'])
        # Structured periods untouched.
        from .truth_delta_models import ClaimedDatapoint
        for claim in ClaimedDatapoint.objects.filter(document=self.doc):
            self.assertEqual((claim.time_period, claim.period_kind, claim.period_fiscal_year, claim.period_end),
                             ('', '', None, None))

    def test_every_consumer_shows_the_faithful_text_within_its_tier(self):
        from matchmaking.models import InvestorApplication
        memo, _, _ = self.generate()
        staff = User.objects.create_user('ff_staff', password='x', is_staff=True)
        investor = User.objects.create_user('ff_investor', password='x')
        InvestorApplication.objects.create(user=investor, full_name='I', company_name='Fund', email='i@t.test',
                                           investment_focus='SaaS', investment_stage='Seed')
        surfaces = {}
        self.client.force_login(staff)
        surfaces['staff IC memo (full)'] = self.client.get(reverse('zelda_api:ic_memo', args=[self.doc.id]))
        surfaces['staff Markdown'] = self.client.get(reverse('zelda_api:ic_memo_download', args=[self.doc.id]))
        self.client.force_login(self.owner)
        surfaces['owner IC memo (Lite)'] = self.client.get(reverse('zelda_api:ic_memo', args=[self.doc.id]))
        self.client.force_login(investor)
        surfaces['investor memo API (Lite)'] = self.client.get(f'/api/v1/zelda/documents/{self.doc.id}/memo/')
        surfaces['investor company overview (Lite)'] = self.client.get(
            reverse('matchmaking:company_overview', args=[self.app.pk]))
        for name, response in surfaces.items():
            with self.subTest(surface=name):
                self.assertEqual(response.status_code, 200)
        api = surfaces['investor memo API (Lite)'].json()
        self.assertEqual((api['tier'], api['locked']), ('lite', True))     # tier permission unchanged
        self.assertNotIn('questions_for_management', api['lite_sections'])
        self.assert_faithful(api['lite_sections']['information_readiness'], 'Lite API information_readiness')
        self.assert_faithful(api['lite_sections']['open_concerns'], 'Lite API open_concerns')
        self.assert_faithful(api['lite_sections']['what_would_change_the_picture'], 'Lite API what_would_change')
        for name in ('staff IC memo (full)', 'staff Markdown', 'owner IC memo (Lite)'):
            self.assert_faithful(surfaces[name].content.decode(), name)
        markdown = surfaces['staff Markdown'].content.decode()
        self.assertIn(f'{NO_PREMISE}, broken down by category?', markdown)
        self.assertIn(PROFILE_UNDATED, markdown)
        self.assertIn('Pitch Deck Hunt lists $23.1M raised', surfaces['investor company overview (Lite)'].content.decode())
