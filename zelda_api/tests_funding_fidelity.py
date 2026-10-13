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

from .claim_context import guard_time_wording
from .funding_fidelity import NO_PREMISE, PROFILE_UNDATED, funding_facts, guard_funding_fidelity, same_period
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


def guard(text, items=None, company='ManyChat'):
    """Memo 94's context: company "ManyChat" (GroundedContext.company), its items unless given."""
    return guard_funding_fidelity(text, funding_facts(items or memo94_items(), company))[0]


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
            'Pitch Deck Hunt lists the company as having raised $23.1M [S3].'),
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

    def test_attribution_stays_within_its_clause_and_the_company_keeps_the_money(self):
        # Review blocker 1. The bots are the company's; the $23.1M is Pitch Deck Hunt's listing of money the
        # company raised. The narrator takes only the funding clause; the company keeps its own predicate.
        cases = {
            'bots uncited (the review case)': (
                'The company states it has raised $23.1M [S3] and reports 140,000+ bots.',
                'Pitch Deck Hunt lists the company as having raised $23.1M [S3] and the company reports 140,000+ bots.'),
            'bots cited': (
                'The company states it has raised $23.1M [S3] and reports 140,000+ bots [S1].',
                'Pitch Deck Hunt lists the company as having raised $23.1M [S3] and the company reports 140,000+ bots '
                '[S1].'),
            'company named, comma before "and"': (
                'ManyChat says it raised $23.1M [S3], and processed 500M messages.',
                'Pitch Deck Hunt lists ManyChat as having raised $23.1M [S3], and ManyChat processed 500M messages.'),
            '"self-reported" in another clause stays the company\'s': (
                'The reported $23.1M [S3] is unconfirmed, and the evidence reduces to two self-reported usage figures.',
                'The reported $23.1M (per Pitch Deck Hunt) [S3] is unconfirmed, and the evidence reduces to two '
                'self-reported usage figures.'),
        }
        for name, (before, after) in cases.items():
            with self.subTest(case=name):
                result = guard(before)
                self.assertEqual(result, after)
                self.assertNotIn('Pitch Deck Hunt reports', result)
                self.assertNotIn('deck states', result)

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

    def test_only_affirmative_company_specific_current_raises_count(self):
        # Review blocker 2: a statement that mentions raising is not evidence of a raise now.
        text = '- What is the intended use of proceeds from this raise, broken down by category?'
        rewritten = text.replace('this raise', NO_PREMISE)
        cases = {
            'negated (the review case)': ('The company is not raising capital', rewritten),
            'missing section (the review case)': ('Use of proceeds: Not found', rewritten),
            'dated and past (the review case)': ('In 2015 the company was seeking $5M', rewritten),
            'negated with an amount': ('The company is not raising a $5M round', rewritten),
            'past without a year': ('The company was raising a $5M round', rewritten),
            'another company': ('Telegram is seeking $5M', rewritten),
            'third party reporting it': ('Seeking $5M seed round', rewritten),          # narrated: not the company
            # Second review: tentative, interrogative and conditional statements are not a raise.
            'tentative (the review case)': ('The company is considering raising $5M.', rewritten),
            'question (the review case)': ('Is the company raising $5M?', rewritten),
            'condition (the review case)': ('If the company is raising $5M, the founders should clarify its terms.',
                                            rewritten),
            'tentative, "may be"': ('The company may be raising a $5M round.', rewritten),
            'tentative, "plans"': ('We plan on raising a $5M seed round.', rewritten),
            'question, trailing': ('ManyChat is raising $5M?', rewritten),
            'condition, "whether"': ('It is unclear whether the company is raising $5M.', rewritten),
            'affirmative, opening verb': ('Seeking $5M seed round', text),
            'affirmative, "we"': ('We are raising a $5M Series A', text),
            'affirmative, company named': ('ManyChat is raising $5M', text),
        }
        for name, (statement, expected) in cases.items():
            with self.subTest(case=name):
                item = GroundedItem(ref='S4', kind='statement', category='Funding', statement=statement,
                                    status=SELF_REPORTED, sources=(SourceRef(document_id=1, page_number=11),),
                                    narrator='Crunchbase' if name == 'third party reporting it' else '')
                self.assertEqual(guard(text, memo94_items(more=[item])), expected)


class FigureIdentityTests(SimpleTestCase):
    """Review blocker 3: the same amount is not the same item. Identity comes from the citation, then the wording."""

    def items(self):
        return memo94_items(more=[
            GroundedItem(ref='S4', kind='statement', category='Revenue', statement='$23.1M revenue',
                         status=SELF_REPORTED, sources=(SourceRef(document_id=3136, page_number=5),)),
            GroundedItem(ref='S5', kind='statement', category='Funding', statement='$23.1M raised',
                         status=SELF_REPORTED, sources=(SourceRef(document_id=3136, page_number=6),),
                         narrator='Crunchbase'),
        ])

    def test_another_item_with_the_same_amount_keeps_its_own_source(self):
        for text in ('The company reports $23.1M revenue [S4].',      # the review case
                     'Crunchbase reports $23.1M raised [S5].',        # the review case, its own narrator
                     'Crunchbase reports $23.1M raised [S4].',        # cited to a non-narrated item
                     'The company reports $23.1M revenue.',           # uncited, another metric
                     'Investors cite $23.1M revenue.',                # uncited, another metric beside a funding word
                     'Crunchbase reports $23.1M raised.',             # uncited, another named source
                     'Annual revenue reached $23.1M, per the deck.'):  # uncited, no funding wording
            with self.subTest(text=text):
                self.assertEqual(guard(text, self.items()), text)

    def test_a_metric_named_before_the_amount_keeps_its_own_identity(self):
        # Second review: Pitch Deck Hunt's funding item and a separate same-amount revenue item only.
        items = memo94_items(more=[
            GroundedItem(ref='S4', kind='statement', category='Revenue', statement='$23.1M revenue',
                         status=SELF_REPORTED, sources=(SourceRef(document_id=3136, page_number=5),))])
        for text in ('Investors cite annual revenue of $23.1M.',          # the review case
                     'Investors note revenue reached $23.1M.',
                     'Investors expect ARR of $23.1M.'):
            with self.subTest(text=text):
                self.assertEqual(guard(text, items), text)
        # Funding wording, no metric before or after: still attributed.
        self.assertEqual(guard('Investors are behind the $23.1M raised.', items),
                         'Investors are behind the $23.1M raised (per Pitch Deck Hunt).')

    def test_each_identity_check_holds_on_its_own(self):
        # No same-amount rival item and no metric word before the amount, so each check is the only guard.
        revenue = memo94_items(more=[
            GroundedItem(ref='S4', kind='statement', category='Revenue', statement='$23.1M revenue',
                         status=SELF_REPORTED, sources=(SourceRef(document_id=3136, page_number=5),))])
        cases = {
            'metric after the amount': ('Investors cite $23.1M revenue.', revenue),
            'another named source, not an item': ('Crunchbase reports $23.1M raised.', memo94_items()),
            'no funding wording': ('A figure of $23.1M appears on slide 2.', memo94_items()),
        }
        for name, (text, items) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(guard(text, items), text)

    def test_an_uncited_amount_two_sources_could_be_is_attributed_to_neither_in_any_order(self):
        crunchbase = GroundedItem(ref='S5', kind='statement', category='Funding', statement='$23.1M raised',
                                  status=SELF_REPORTED, sources=(SourceRef(document_id=3136, page_number=6),),
                                  narrator='Crunchbase')
        own = GroundedItem(ref='S6', kind='statement', category='Funding', statement='$23.1M raised',
                           status=SELF_REPORTED, sources=(SourceRef(document_id=3136, page_number=7),))
        for rival_name, rival in (('another narrator', crunchbase), ("the company's own figure", own)):
            forward = memo94_items(more=[rival])
            orders = {'forward': forward, 'reversed': list(reversed(forward))}
            for order, items in orders.items():
                with self.subTest(rival=rival_name, order=order):
                    uncited = '- Who are the investors behind the $23.1M raised?'
                    self.assertEqual(guard(uncited, items), uncited)
                    # A citation still decides, the same in either order.
                    self.assertEqual(guard('The $23.1M raised figure [S3] was checked.', items),
                                     'The $23.1M raised figure (per Pitch Deck Hunt) [S3] was checked.')
                    expected = ('The $23.1M raised figure (per Crunchbase) [S5] was checked.'
                                if rival is crunchbase else 'The $23.1M raised figure [S6] was checked.')
                    self.assertEqual(guard(f'The $23.1M raised figure [{rival.ref}] was checked.', items), expected)

    def test_the_narrated_item_is_still_attributed_beside_them(self):
        self.assertEqual(guard('Revenue was $23.1M [S4] and $23.1M was raised [S3].', self.items()),
                         'Revenue was $23.1M [S4] and $23.1M (per Pitch Deck Hunt) was raised [S3].')
        self.assertEqual(guard('The $23.1M raised figure [S3] was checked.', self.items()),
                         'The $23.1M raised figure (per Pitch Deck Hunt) [S3] was checked.')


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

    def generate(self, build=None):
        """`build(s1=, s2=, s3=, c1=, profile=)` replaces the default (memo 94) reply with another memo's sentences."""
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
        if build is not None:
            sections = {**build(s1=s1, s2=s2, s3=s3, c1=c1, profile=profile), 'evidence_level': 'LITTLE_EVIDENCE'}
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

    def test_memo_95_sentences_through_the_writer_and_its_lite_and_full_readers(self):
        # Memo 95 (document 3137; owner grade: partial pass), verbatim, refs mapped to this context.
        def memo95(s1, s2, s3, c1, profile):
            return {
                'information_readiness': f'Score: 10/100\nPresent:\n• Self-reported funding raised: $23.1M [{s3}]',
                'what_would_change_the_picture': (
                    'The single most important missing piece is a revenue and cost schedule — ideally '
                    'accountant-reviewed — covering at minimum the twelve months to the deck date, showing monthly '
                    'recurring revenue, gross margin, and burn rate. This alone would allow the traction figures '
                    f'[{s1}, {s2}] to be interpreted in the context of actual monetisation and would anchor assessment '
                    f'of the $23.1M funding figure [{s3}] against remaining runway.'),
                'base_scenario': (
                    f'Taking the self-reported figures at face value [{s1}, {s2}, {s3}], ManyChat had meaningful '
                    'bot-platform traction by April 2016 and had raised a material amount of capital.'),
                'questions_for_management': [
                    f'Who are the investors behind the $23.1M raised, when were the rounds closed, and how much capital '
                    f'remains available [{s3}, {c1}]?',
                    'What is the current monthly cash burn, and what is the implied runway from existing funds?'],
            }
        memo, call, _ = self.generate(memo95)
        self.assertIn('• Funding raised (reported by Pitch Deck Hunt): $23.1M [S', memo.information_readiness)
        self.assertNotIn('reported by Pitch Deck Hunt funding raised', memo.information_readiness)
        self.assertIn('This would allow the traction figures', memo.what_would_change_the_picture)
        self.assertIn('against runway (which needs a dated cash balance and burn rate; neither is in the evidence).',
                      memo.what_would_change_the_picture)
        self.assertNotIn('remaining runway', memo.what_would_change_the_picture)
        self.assertRegex(memo.base_scenario, r'^Taking the self-reported figures at face value \[S\d, S\d\], ManyChat '
                                             r'had meaningful bot-platform traction by April 2016 and had raised a '
                                             r'material amount of capital \(per Pitch Deck Hunt, undated\) \[S\d\]\.$')
        questions = memo.questions_for_management.splitlines()
        self.assertIn('how much capital remains available [S', questions[0])          # a question: kept
        self.assertEqual(questions[1], '- What is the current monthly cash burn, and what is the implied runway '
                                       'from existing funds?')
        self.assertIn('Runway or\n       remaining cash needs a dated cash balance', call['system'])
        self.assertIn('Dated cash and burn give runway as of their date, never current runway.', call['system'])
        self.assertNotIn('Series A deck with', call['messages'][0]['content'])     # raw-source boundary
        staff = User.objects.create_user('ff95_staff', password='x', is_staff=True)
        investor = User.objects.create_user('ff95_investor', password='x')
        from matchmaking.models import InvestorApplication
        InvestorApplication.objects.create(user=investor, full_name='I', company_name='Fund', email='i95@t.test',
                                           investment_focus='SaaS', investment_stage='Seed')
        self.client.force_login(staff)
        full = self.client.get(reverse('zelda_api:ic_memo', args=[self.doc.id])).content.decode()
        markdown = self.client.get(reverse('zelda_api:ic_memo_download', args=[self.doc.id])).content.decode()
        self.client.force_login(investor)
        lite = self.client.get(f'/api/v1/zelda/documents/{self.doc.id}/memo/').json()
        self.assertEqual((lite['tier'], lite['locked']), ('lite', True))
        for name, text in (('staff IC memo', full), ('staff Markdown', markdown),
                           ('Lite API information_readiness', lite['lite_sections']['information_readiness']),
                           ('Lite API what_would_change', lite['lite_sections']['what_would_change_the_picture'])):
            with self.subTest(surface=name):
                self.assertNotIn('reported by Pitch Deck Hunt funding raised', text)
                self.assertNotIn('remaining runway', text)
        self.assertIn('Funding raised (reported by Pitch Deck Hunt): $23.1M', lite['lite_sections']['information_readiness'])


def both_guards(text, items, company='ManyChat'):
    """The pipeline's order (_generate_memo): the time guard, then the funding guard, on one section."""
    allowed = {item.ref: item.time_wording_allowed for item in items if item.dated}
    timed, _ = guard_time_wording(text, allowed)
    return guard_funding_fidelity(timed, funding_facts(items, company))[0]


def memo95_items(**extra):
    """Memo 95's memo-input items (09b of the 2948998 run): same refs and narrator as memo 94's."""
    return memo94_items(**extra)


class SelfReportedWordingTests(SimpleTestCase):
    """FF-302 and FF-305 (P2): natural wording, and a narrated listing never counted as the company's own."""

    def test_memo_95_label_reads_naturally(self):
        self.assertEqual(guard('• Self-reported funding raised: $23.1M [S3]'),
                         '• Funding raised (reported by Pitch Deck Hunt): $23.1M [S3]')

    def test_other_self_reported_forms(self):
        cases = {
            'parenthetical (memo 94)': ('• Funding raised figure (self-reported, unverified): $23.1M [S3]',
                                        '• Funding raised figure (reported by Pitch Deck Hunt, unverified): $23.1M [S3]'),
            'predicate': ('The $23.1M raised [S3] is self-reported.',
                          'The $23.1M raised [S3] is reported by Pitch Deck Hunt.'),
            'adjective': ('The self-reported $23.1M [S3] is unverified.',
                          'The $23.1M (per Pitch Deck Hunt) [S3] is unverified.'),
            'adjective opening the sentence': ('Self-reported $23.1M raised [S3] is unverified.',
                                               '$23.1M raised (per Pitch Deck Hunt) [S3] is unverified.'),
        }
        for name, (before, after) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(guard(before), after)

    def test_memo_95_mixed_references_split_traction_from_funding(self):
        before = ('Taking the self-reported figures at face value [S1, S2, S3], ManyChat had meaningful bot-platform '
                  'traction by April 2016 and had raised a material amount of capital.')
        self.assertEqual(guard(before, memo95_items()), (
            'Taking the self-reported figures at face value [S1, S2], ManyChat had meaningful bot-platform traction by '
            'April 2016 and had raised a material amount of capital (per Pitch Deck Hunt, undated) [S3].'))

    def test_cited_paraphrases_need_no_amount(self):
        cases = {
            'sole paraphrase': ('Self-reported funding [S3] remains unverified.',
                                'Funding (per Pitch Deck Hunt) [S3] remains unverified.'),
            'claim ref in the group': ('The self-reported figures [S1, C1] support the funding history.',
                                       'The self-reported figures [S1] support the funding history (per Pitch Deck '
                                       'Hunt, undated) [C1].'),
            'no separate funding clause': ('The self-reported figures [S1, S3] are unverified.',
                                           'The self-reported figures [S1] (funding: per Pitch Deck Hunt, undated '
                                           '[S3]) are unverified.'),
        }
        for name, (before, after) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(guard(before), after)

    def crunchbase(self, as_of='not stated'):
        return GroundedItem(ref='S4', kind='statement', category='Funding', statement='$22M raised',
                            status=SELF_REPORTED, sources=(SourceRef(document_id=3137, page_number=3),), dated=True,
                            narrator='Crunchbase', as_of=as_of)

    def test_every_narrated_reference_in_a_mixed_group_leaves_in_one_pass(self):
        before = ('Taking the self-reported figures at face value [S1, S3, S4], ManyChat had meaningful bot-platform '
                  'traction by April 2016 and had raised a material amount of capital.')
        after = ('Taking the self-reported figures at face value [S1], ManyChat had meaningful bot-platform traction by '
                 'April 2016 and had raised a material amount of capital (per Pitch Deck Hunt, undated) [S3] and '
                 '(per Crunchbase, undated) [S4].')
        items = memo95_items(more=[self.crunchbase()])
        once = guard(before, items)
        self.assertEqual(once, after)
        self.assertEqual(guard(before, list(reversed(items))), after)     # item order does not matter
        self.assertEqual(guard(once, items), once)                        # idempotent
        self.assertEqual(guard(once, list(reversed(items))), once)

    def test_mixed_group_variants_with_two_narrators(self):
        items = memo95_items(more=[self.crunchbase()])
        cases = {
            'citation order decides the note order': (
                'Taking the self-reported figures at face value [S4, S1, S3], ManyChat had raised capital.',
                'Taking the self-reported figures at face value [S1], ManyChat had raised capital (per Crunchbase, '
                'undated) [S4] and (per Pitch Deck Hunt, undated) [S3].'),
            'no funding clause': (
                'The self-reported figures [S1, S3, S4] are unverified.',
                'The self-reported figures [S1] (funding: per Pitch Deck Hunt, undated [S3]; per Crunchbase, undated '
                '[S4]) are unverified.'),
            'both narrators in a sole group': (
                'Self-reported funding [S3, S4] remains unverified.',
                'Funding (per Pitch Deck Hunt and Crunchbase) [S3, S4] remains unverified.'),
            'the same narrator twice': (
                'Taking the self-reported figures at face value [S1, C1, S3], ManyChat had raised capital.',
                'Taking the self-reported figures at face value [S1], ManyChat had raised capital (per Pitch Deck Hunt, '
                'undated) [C1, S3].'),
            'an all-narrated group beside company refs': (
                'The self-reported traction [S1] with funding [S3, S4] is unverified.',
                'The self-reported traction [S1] with funding (per Pitch Deck Hunt, undated) [S3] and (per Crunchbase, '
                'undated) [S4] is unverified.'),
            'a narrator named in another clause': (
                'Pitch Deck Hunt lists $23.1M raised [S3]; taking the self-reported figures at face value [S1, S4], '
                'ManyChat had raised capital.',
                'Pitch Deck Hunt lists $23.1M raised [S3]; taking the self-reported figures at face value [S1], '
                'ManyChat had raised capital (per Crunchbase, undated) [S4].'),
        }
        for name, (before, after) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(guard(before, items), after)
                self.assertEqual(guard(before, list(reversed(items))), after)
                self.assertEqual(guard(after, items), after)

    def test_every_self_reported_clause_is_corrected_in_one_invocation(self):
        items = memo95_items(more=[self.crunchbase()])
        cases = {
            # The review repro: S3's note stays beside its own group, never in S4's clause.
            'The self-reported figures [S1, S3] are noted, and self-reported funding [S4] is unverified.':
                'The self-reported figures [S1] (funding: per Pitch Deck Hunt, undated [S3]) are noted, and funding '
                '(per Crunchbase) [S4] is unverified.',
            'Taking the self-reported figures at face value [S1, S3], ManyChat had raised capital, and self-reported '
            'funding [S4] is unverified.':
                'Taking the self-reported figures at face value [S1], ManyChat had raised capital (per Pitch Deck Hunt, '
                'undated) [S3], and funding (per Crunchbase) [S4] is unverified.',
            # An uncited "self-reported" clause is still another source's: S3's note does not move into it.
            'The self-reported figures [S1, S3] are noted, and self-reported funding is unverified.':
                'The self-reported figures [S1] (funding: per Pitch Deck Hunt, undated [S3]) are noted, and '
                'self-reported funding is unverified.',
            'Self-reported funding [S4] is unverified; the self-reported figures [S1, S3] are noted.':
                'Funding (per Crunchbase) [S4] is unverified; the self-reported figures [S1] (funding: per Pitch Deck '
                'Hunt, undated [S3]) are noted.',
        }
        for before, after in cases.items():
            with self.subTest(text=before[:50]):
                self.assertEqual(guard(before, items), after)                      # one call fixes every clause
                self.assertEqual(guard(before, list(reversed(items))), after)
                self.assertEqual(guard(after, items), after)
                self.assertEqual(guard(after, list(reversed(items))), after)

    def dealroom(self):
        return GroundedItem(ref='S5', kind='statement', category='Funding', statement='$20M raised',
                            status=SELF_REPORTED, sources=(SourceRef(document_id=3137, page_number=4),), dated=True,
                            narrator='Dealroom', as_of='not stated')

    def test_every_group_governed_by_one_span_in_one_call(self):
        items = memo95_items(more=[self.crunchbase(), self.dealroom()])
        cases = {
            'The self-reported figures [S1, S3] with [S4] plus [S5] are unverified.':
                'The self-reported figures [S1] (funding: per Pitch Deck Hunt, undated [S3]; per Crunchbase, undated '
                '[S4]; per Dealroom, undated [S5]) are unverified.',
            'The self-reported funding [S3] plus [S4] is unverified.':          # Crunchbase was never named
                'The funding (per Pitch Deck Hunt and Crunchbase) [S3, S4] is unverified.',
            # Locality: a joined run in another clause, with no "self-reported" of its own, is not this span's.
            'The self-reported figures [S1, S3] are noted, and [S4] plus [S5] is listed.':
                'The self-reported figures [S1] (funding: per Pitch Deck Hunt, undated [S3]) are noted, and [S4] plus '
                '[S5] is listed.',
            # "self-reported" after the run it governs.
            '[S3] plus [S4] are self-reported.':
                '[S3, S4] are reported by Pitch Deck Hunt and Crunchbase.',
            '[S1, S3] plus [S4] are self-reported.':
                '[S1] (funding: per Pitch Deck Hunt, undated [S3]; per Crunchbase, undated [S4]) are self-reported.',
            # A company-only run before the narrated run in the same clause stays as written.
            'The self-reported figures [S1] with [S2] exceed funding [S3] plus [S4].':
                'The self-reported figures [S1] with [S2] exceed funding (per Pitch Deck Hunt, undated) [S3] and (per '
                'Crunchbase, undated) [S4].',
            # Company-only runs are left as written.
            'The self-reported figures [S1] with [S2] are unverified.':
                'The self-reported figures [S1] with [S2] are unverified.',
        }
        for before, after in cases.items():
            with self.subTest(text=before[:50]):
                for order in (items, list(reversed(items))):
                    self.assertEqual(guard(before, order), after)
                    self.assertEqual(guard(after, order), after)          # idempotent

    def test_a_dated_second_narrator_is_not_called_undated(self):
        items = memo95_items(more=[self.crunchbase(as_of='2024-05-01')])
        self.assertEqual(
            guard('Taking the self-reported figures at face value [S1, S3, S4], ManyChat had raised capital.', items),
            'Taking the self-reported figures at face value [S1], ManyChat had raised capital (per Pitch Deck Hunt, '
            'undated) [S3] and (per Crunchbase) [S4].')

    def test_a_dated_narrated_item_is_not_called_undated(self):
        dated = [i if i.ref not in ('C1', 'S3') else GroundedItem(
            ref=i.ref, kind=i.kind, category=i.category, statement=i.statement, status=i.status, sources=i.sources,
            dated=True, narrator=PDH, as_of='2016-04-30') for i in memo94_items()]
        self.assertEqual(
            guard('Taking the self-reported figures at face value [S1, S2, S3], ManyChat had raised capital.', dated),
            'Taking the self-reported figures at face value [S1, S2], ManyChat had raised capital (per Pitch Deck '
            'Hunt) [S3].')

    def test_company_traction_stays_self_reported(self):
        for text in (   # memo 95, verbatim
                '• Self-reported traction metrics as of an Apr-16 slide context: 140,000+ bots, 500M messages [S1, S2]',
                'Unverified traction figures: The two headline traction metrics — 140,000+ bots and 500M messages '
                '[S1, S2] — are self-reported on a slide dated by context to April 2016 and could not be externally '
                'checked [C2, C3].',
                '• The two core traction claims — 140,000+ bots and 500M messages [S1, S2] — are self-reported and '
                'unverified [C2, C3]; without independent confirmation it is unknown whether these figures reflect '
                'unique active bots, cumulative totals, or another definition, which is material to understanding '
                'platform health.'):
            with self.subTest(text=text[:50]):
                self.assertEqual(guard(text, memo95_items()), text)


class ReportedFundingIsNotCashTests(SimpleTestCase):
    """FF-303: runway needs a dated cash balance and a burn basis; reported funding and a revenue/cost schedule are not."""

    def test_memo_95_runway_premise(self):
        before = ('This alone would allow the traction figures [S1, S2] to be interpreted in the context of actual '
                  'monetisation and would anchor assessment of the $23.1M funding figure (per Pitch Deck Hunt) [S3] '
                  'against remaining runway.')
        self.assertEqual(guard(before, memo95_items()), (
            'This would allow the traction figures [S1, S2] to be interpreted in the context of actual monetisation '
            'and would anchor assessment of the $23.1M funding figure (per Pitch Deck Hunt) [S3] against runway '
            '(which needs a dated cash balance and burn rate; neither is in the evidence).'))

    def test_cash_premise_found_by_citation_alone(self):
        self.assertEqual(guard('The funding [C1] leaves available cash for 2026.', memo95_items()),
                         'The funding [C1] leaves cash on hand (which needs a dated cash balance; none is in the '
                         'evidence) for 2026.')

    def test_questions_scenarios_unknowns_and_unrelated_runway_are_kept(self):
        for text in (   # memo 95, verbatim, except the last two controls
                'If the self-reported traction figures [S1, S2] — 140,000+ bots and 500M messages as of the Apr-16 '
                'slide context — reflect genuinely active, monetisable usage, and if the $23.1M raised (per Pitch Deck '
                'Hunt) [S3] was deployed efficiently with meaningful runway remaining, then ManyChat may have achieved '
                'substantial platform scale before seeking any current or planned raise.',
                'Undated and unverified funding: The $23.1M raised figure (per Pitch Deck Hunt) [S3] carries no stated '
                'date and no external corroboration [C1], making it impossible to determine when funds were raised, '
                'from whom, or how much remains available.',
                '- Who are the investors behind the $23.1M raised (per Pitch Deck Hunt), when were the rounds closed, '
                'and how much capital remains available [S3, C1]?',
                '- What is the current monthly cash burn, and what is the implied runway from existing funds?',
                # A research question may ask about remaining runway for the cited funding.
                '- How much remaining runway does the $23.1M raised (per Pitch Deck Hunt) [S3] represent today?',
                '• Runway: not calculated',
                'The company\'s remaining runway is unknown.'):                  # no funding figure or citation
            with self.subTest(text=text[:50]):
                self.assertEqual(guard(text, memo95_items()), text)

    RUNWAY = 'It would anchor the $23.1M funding figure (per Pitch Deck Hunt) [S3] against remaining runway.'
    CASH = 'The $23.1M funding figure (per Pitch Deck Hunt) [S3] is not the available cash.'

    def evidence(self, ref, statement, as_of='', **extra):
        return GroundedItem(ref=ref, kind='statement', category=extra.pop('category', 'Financials'),
                            statement=statement, status=SELF_REPORTED,
                            sources=(SourceRef(document_id=1, page_number=11),), as_of=as_of, **extra)

    def runway(self, *more):
        return guard(self.RUNWAY, memo95_items(more=list(more)))

    def test_undated_cash_alone_does_not_support_runway(self):
        # Revised from 49663be, where any company figure near the word "cash" left the premise alone.
        undated = self.evidence('S4', '$2.1M cash in the bank')
        self.assertEqual(self.runway(undated), (
            'It would anchor the $23.1M funding figure (per Pitch Deck Hunt) [S3] against runway (which needs a dated '
            "cash balance and burn rate; the evidence's cash figure is not a dated balance and no burn rate is in the "
            'evidence).'))
        third_party = self.evidence('S4', '$2.1M cash in the bank', as_of='2026-06-30', narrator='Crunchbase')
        self.assertIn('neither is in the evidence', self.runway(third_party))

    def test_dated_cash_and_a_compatible_burn_rate_support_runway(self):
        cash = self.evidence('S4', '$2.1M cash in the bank', as_of='2026-06-30')
        for burn in (self.evidence('S5', 'Net burn of $150K per month', as_of='2026-06-30'),
                     self.evidence('S5', 'Monthly cash burn: $150K', as_of='2026-03-31')):
            with self.subTest(burn=burn.statement):
                self.assertEqual(self.runway(cash, burn), self.RUNWAY)
                self.assertEqual(self.runway(burn, cash), self.RUNWAY)        # item order does not matter
        self.assertEqual(guard(self.CASH, memo95_items(more=[cash])), self.CASH)   # a dated balance is cash
        fy_cash = self.evidence('S4', '$2.1M cash in the bank', as_of='FY2026')
        fy_burn = self.evidence('S5', '$1.8M annual burn', as_of='FY2026')
        self.assertEqual(self.runway(fy_cash, fy_burn), self.RUNWAY)              # the same fiscal year label

    def test_each_insufficient_basis_keeps_the_guard_and_says_what_is_missing(self):
        cash = self.evidence('S4', '$2.1M cash in the bank', as_of='2026-06-30')
        burn = self.evidence('S5', 'Net burn of $150K per month', as_of='2026-06-30')
        no_cash, no_burn = 'no cash balance is in the evidence', 'no burn rate is in the evidence'
        bad_cash = "the evidence's cash figure is not a dated balance"
        bad_burn = "the evidence's burn figure is not a dated rate"
        cases = {
            'cash only': ([cash], no_burn),
            'burn only': ([burn], no_cash),
            'undated burn': ([cash, self.evidence('S5', 'Net burn of $150K per month', as_of='not stated')], bad_burn),
            'burn without a rate': ([cash, self.evidence('S5', 'Total burn of $1.8M', as_of='2026-06-30')], bad_burn),
            'historical cash': ([burn, self.evidence('S4', 'Previously had $2.1M cash in the bank', as_of='2026-06-30')],
                                bad_cash),
            'estimated cash': ([burn, self.evidence('S4', 'Expects $2.1M cash in the bank', as_of='2026-06-30')],
                               bad_cash),
            'conditional burn': ([cash, self.evidence('S5', 'If hiring closes, burn of $150K per month',
                                                      as_of='2026-06-30')], bad_burn),
            'negated cash': ([burn, self.evidence('S4', 'The company does not hold $2.1M in cash', as_of='2026-06-30')],
                             no_cash),
            'cash asked, not stated': ([burn, self.evidence('S4', 'Is the $2.1M cash in the bank?', as_of='2026-06-30')],
                                       no_cash),
            'unknown burn': ([cash, self.evidence('S5', 'Monthly burn: undisclosed (budget $150K per month)',
                                                  as_of='2026-06-30')], no_burn),
            'cash flow is not cash': ([burn, self.evidence('S4', '$2.1M operating cash flow', as_of='2026-06-30')],
                                      no_cash),
            'third-party burn': ([cash, self.evidence('S5', 'Net burn of $150K per month', as_of='2026-06-30',
                                                      narrator='Crunchbase')], no_burn),
            'profile runway': ([GroundedItem(ref='P3', kind='profile', category='Runway (profile)',
                                             statement='Runway (profile): 18 months, $2.1M cash', status=SELF_REPORTED,
                                             sources=(SourceRef(document_id=None, profile_field='runway_months'),))],
                               'neither is in the evidence'),
            'periods apart': ([cash, self.evidence('S5', 'Net burn of $150K per month', as_of='2024-12-31')],
                              "the evidence's cash balance and burn rate are not shown to be from the same period"),
            # No fiscal period end is established, so FY2026 is not read as December 2026 (six months from June).
            'fiscal year against a period end': ([cash, self.evidence('S5', '$1.8M annual burn', as_of='FY2026')],
                                                 "the evidence's cash balance and burn rate are not shown to be from "
                                                 'the same period'),
        }
        for name, (more, why) in cases.items():
            with self.subTest(case=name):
                out = self.runway(*more)
                self.assertIn(f'against runway (which needs a dated cash balance and burn rate; {why}', out)
                if any('burn' in i.statement and not i.narrator for i in more):
                    self.assertNotIn('neither', out)           # a burn figure is present: never "neither"
                self.assertEqual(self.runway(*reversed(more)), out)

    def pair(self, as_of):
        return [self.evidence('S4', '$2.1M cash in the bank', as_of=as_of),
                self.evidence('S5', 'Net burn of $150K per month', as_of=as_of)]

    def test_matching_dates_do_not_establish_current_runway_or_cash(self):
        for as_of in ('2016-04-30', '2030-06-30', 'FY2026'):
            dated = (f'runway as of {as_of} (from the dated cash balance and burn rate; the evidence gives no current '
                     'figure)')
            cases = {
                'It would anchor the $23.1M funding figure (per Pitch Deck Hunt) [S3] against current remaining runway.':
                    f'It would anchor the $23.1M funding figure (per Pitch Deck Hunt) [S3] against {dated}.',
                'The $23.1M raised (per Pitch Deck Hunt) [S3] leaves remaining runway today.':
                    f'The $23.1M raised (per Pitch Deck Hunt) [S3] leaves {dated}.',
                'The $23.1M funding figure (per Pitch Deck Hunt) [S3] is not the current available cash.':
                    f'The $23.1M funding figure (per Pitch Deck Hunt) [S3] is not the cash as of {as_of} (the latest '
                    'dated cash balance; the evidence gives no current figure).',
            }
            for before, after in cases.items():
                with self.subTest(as_of=as_of, text=before[-40:]):
                    items = memo95_items(more=self.pair(as_of))
                    self.assertEqual(guard(before, items), after)
                    self.assertEqual(guard(before, list(reversed(items))), after)
                    self.assertEqual(guard(after, items), after)                    # idempotent

    def test_supported_historical_analysis_and_dated_positive_controls_are_kept(self):
        items = memo95_items(more=self.pair('2016-04-30'))
        for text in (
                self.RUNWAY,                                                         # no current wording
                'Against the April 2016 cash balance and burn rate [S4, S5], the $23.1M funding figure (per Pitch '
                'Deck Hunt) [S3] implied remaining runway at that date.',
                '- How much current remaining runway does the $23.1M raised (per Pitch Deck Hunt) [S3] represent?',
                'If the $23.1M raised (per Pitch Deck Hunt) [S3] were still available, current runway would be '
                'longer.'):
            with self.subTest(text=text[:50]):
                self.assertEqual(guard(text, items), text)

    def test_unsupported_current_wording_is_qualified(self):
        cases = {
            'It would anchor the $23.1M funding figure (per Pitch Deck Hunt) [S3] against current runway.':
                'It would anchor the $23.1M funding figure (per Pitch Deck Hunt) [S3] against current runway (which '
                'needs a dated cash balance and burn rate; neither is in the evidence).',
            'The $23.1M funding figure (per Pitch Deck Hunt) [S3] is not current cash.':
                'The $23.1M funding figure (per Pitch Deck Hunt) [S3] is not current cash on hand (which needs a dated '
                'cash balance; none is in the evidence).',
        }
        for before, after in cases.items():
            with self.subTest(text=before[-30:]):
                self.assertEqual(guard(before, memo95_items()), after)
                self.assertEqual(guard(after, memo95_items()), after)

    def test_introductory_time_qualifier_through_both_guards(self):
        dated = ('supports runway as of 2016-04-30 (from the dated cash balance and burn rate; the evidence gives no '
                 'current figure).')
        cases = {
            'Today, the $23.1M funding figure (per Pitch Deck Hunt) [S3] supports remaining runway.':
                f'The $23.1M funding figure (per Pitch Deck Hunt) [S3] {dated}',
            # The time guard removes these phrases first (no source says them), restoring the capital; with no
            # current wording left, the dated pair supports the plain premise (the dated positive control).
            '- As of today, the $23.1M funding figure (per Pitch Deck Hunt) [S3] supports remaining runway.':
                '- The $23.1M funding figure (per Pitch Deck Hunt) [S3] supports remaining runway.',
            'At present, the $23.1M funding figure (per Pitch Deck Hunt) [S3] supports remaining runway.':
                'The $23.1M funding figure (per Pitch Deck Hunt) [S3] supports remaining runway.',
            'Currently the $23.1M funding figure (per Pitch Deck Hunt) [S3] supports remaining runway.':
                'The $23.1M funding figure (per Pitch Deck Hunt) [S3] supports remaining runway.',
            # Kept: not a time qualifier, a question, a qualified scenario.
            'Now that funds are raised, the $23.1M funding figure (per Pitch Deck Hunt) [S3] supports remaining runway.':
                'Now that funds are raised, the $23.1M funding figure (per Pitch Deck Hunt) [S3] supports remaining '
                'runway.',
            'Today, how much remaining runway does the $23.1M raised (per Pitch Deck Hunt) [S3] represent?':
                'Today, how much remaining runway does the $23.1M raised (per Pitch Deck Hunt) [S3] represent?',
            'Today, if the $23.1M raised (per Pitch Deck Hunt) [S3] were unspent, remaining runway would be longer.':
                'Today, if the $23.1M raised (per Pitch Deck Hunt) [S3] were unspent, remaining runway would be '
                'longer.',
        }
        items = memo95_items(more=self.pair('2016-04-30'))
        for before, after in cases.items():
            with self.subTest(text=before[:40]):
                for order in (items, list(reversed(items))):
                    self.assertEqual(both_guards(before, order), after)
                    self.assertEqual(both_guards(after, order), after)    # idempotent
        # Where the time guard keeps the phrase (its source says it, or it cites no claim-backed item), the
        # funding guard alone still dates an introductory qualifier.
        for lead in ('As of today, ', 'At present, ', 'Currently '):
            with self.subTest(lead=lead):
                self.assertEqual(guard(f'{lead}the $23.1M funding figure (per Pitch Deck Hunt) [S3] supports remaining '
                                       'runway.', items), f'The $23.1M funding figure (per Pitch Deck Hunt) [S3] {dated}')
        # Without support the premise is qualified as before and "Today," stays.
        self.assertEqual(both_guards('Today, the $23.1M funding figure (per Pitch Deck Hunt) [S3] supports remaining '
                                     'runway.', memo95_items()),
                         'Today, the $23.1M funding figure (per Pitch Deck Hunt) [S3] supports runway (which needs a '
                         'dated cash balance and burn rate; neither is in the evidence).')

    def test_possessive_opening_through_both_guards(self):
        # "Today's" / "Today’s" opening a sentence, a bullet or a numbered item (patch
        # funding-fidelity-possessive-opening-fix): the dated note keeps its noun and capital, and the marker stays.
        runway = ('runway as of 2016-04-30 (from the dated cash balance and burn rate; the evidence gives no current '
                  'figure)')
        cash = 'cash as of 2016-04-30 (the latest dated cash balance; the evidence gives no current figure)'
        funding = 'the $23.1M funding figure (per Pitch Deck Hunt) [S3]'
        dated = memo95_items(more=self.pair('2016-04-30'))
        for apostrophe in ("'", '\u2019'):
            for marker in ('', '- ', '\u2022 ', '1. ', '2) '):
                today = f'{marker}Today{apostrophe}s'
                cases = {
                    f'{today} $23.1M funding figure (per Pitch Deck Hunt) [S3] supports remaining runway.':
                        f'{marker}$23.1M funding figure (per Pitch Deck Hunt) [S3] supports {runway}.',
                    f'{today} remaining runway is anchored by {funding}.':
                        f'{marker}{runway[:1].upper()}{runway[1:]} is anchored by {funding}.',
                    f'{today} available cash is not {funding}.':
                        f'{marker}{cash[:1].upper()}{cash[1:]} is not {funding}.',
                }
                for before, after in cases.items():
                    with self.subTest(text=before[:30]):
                        for items in (dated, list(reversed(dated))):
                            self.assertEqual(both_guards(before, items), after)
                            self.assertEqual(both_guards(after, items), after)       # idempotent
                # Without a dated pair the premise is qualified and the possessive opening stays.
                unsupported = f'{today} remaining runway is anchored by {funding}.'
                expected = (f'{today} runway (which needs a dated cash balance and burn rate; neither is in the '
                            f'evidence) is anchored by {funding}.')
                with self.subTest(unsupported=unsupported[:30]):
                    self.assertEqual(both_guards(unsupported, memo95_items()), expected)
                    self.assertEqual(both_guards(expected, memo95_items()), expected)

    def test_the_latest_date_uses_its_day_in_any_item_order(self):
        early = self.evidence('S4', '$2.1M cash in the bank', as_of='2016-04-01')
        late = self.evidence('S6', '$1.9M cash in the bank', as_of='2016-04-30')
        burn = self.evidence('S5', 'Net burn of $150K per month', as_of='2016-04-30')
        runway = 'It would anchor the $23.1M funding figure (per Pitch Deck Hunt) [S3] against current remaining runway.'
        cash = 'The $23.1M funding figure (per Pitch Deck Hunt) [S3] is not the current available cash.'
        for more in ([early, late, burn], [late, early, burn], [burn, late, early]):
            with self.subTest(order=[i.as_of for i in more]):
                for items in (memo95_items(more=more), list(reversed(memo95_items(more=more)))):
                    self.assertIn('runway as of 2016-04-30 (', guard(runway, items))
                    self.assertIn('cash as of 2016-04-30 (', guard(cash, items))

    def test_a_month_end_never_matches_a_bare_fiscal_year(self):
        # same_period's own contract, independent of the size of either number (month index 2024 vs FY2024).
        self.assertFalse(same_period(('month', 2024), ('fy', 2024)))
        self.assertFalse(same_period(('fy', 2024), ('month', 2024)))
        self.assertTrue(same_period(('fy', 2024), ('fy', 2024)))

    def test_cash_premise_needs_a_dated_balance(self):
        undated = self.evidence('S4', '$2.1M cash in the bank')
        self.assertEqual(guard(self.CASH, memo95_items(more=[undated])), (
            'The $23.1M funding figure (per Pitch Deck Hunt) [S3] is not the cash on hand (which needs a dated cash '
            "balance; the evidence's cash figure is not a dated balance)."))

    def test_supported_runway_keeps_the_sentence_unchanged_and_the_alone_wording(self):
        cash = self.evidence('S4', '$2.1M cash in the bank', as_of='2026-06-30')
        burn = self.evidence('S5', 'Net burn of $150K per month', as_of='2026-06-30')
        text = 'This alone would anchor the $23.1M funding figure (per Pitch Deck Hunt) [S3] against remaining runway.'
        self.assertEqual(guard(text, memo95_items(more=[cash, burn])), text)

    def test_memo_95_guard_is_idempotent(self):
        text = ('• Self-reported funding raised: $23.1M [S3]\nTaking the self-reported figures at face value '
                '[S1, S2, S3], ManyChat had raised a material amount of capital.\nThis alone would anchor the $23.1M '
                'funding figure [S3] against remaining runway.')
        once = guard(text, memo95_items())
        self.assertEqual(guard(once, memo95_items()), once)
        self.assertEqual(once.count('\n'), text.count('\n'))
