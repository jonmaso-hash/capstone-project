"""
ManyChat RA-102 / RA-106: dates and narrators survive as context, and an
undated or historical figure never becomes a current running total.

The deck text below is the stored text of document 3133's slides 2 and 10
(frozen in docs/baselines/manychat/rerun/pass-a/04_claims.json):

    slide 2   "Source: Pitch Deck Hunt lists ManyChat as a 2015 Series A deck with
              $23.1M raised."  -- a third party's listing; "2015" is the deck's year
    slide 10  "Traction by Apr-16" above "140 000+ bots" and "500M messages"

Before: every claim kept only the bare figure ("$23.1M raised"), and memo 91
wrote "The company states it has raised $23.1M to date". After: the claim
keeps the sentence, the narrator and the slide heading as CONTEXT; its
structured period (the 2026-10-10 owner rule) and Truth Delta are unchanged;
the memo is given an explicit "as_of: not stated" and cannot add "to date".
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .claim_context import (
    claim_narrator, dated_heading, guard_time_wording, time_wording_in, unbound_dates,
)
from .claim_periods import claim_period
from .intelligence_pipeline import ZeldaIntelligencePipelineV2
from .truth_delta_models import ClaimedDatapoint
from .vector_models import DocumentChunk, DocumentSource, IntelligenceMemo

User = get_user_model()

SLIDE2 = (
    "Why this deck fits the audit leg\n"
    "Source: Pitch Deck Hunt lists ManyChat as a 2015 Series A deck with $23.1M raised. The embedded "
    "SlideShare deck has 10 slides. ManyChat’s current site is active under Manychat, Inc. and describes "
    "current products across Instagram, WhatsApp, TikTok, and Messenger.\nStage\nSeries A\n"
    "Company status\nActive private company"
)
FUNDING_SENTENCE = "Source: Pitch Deck Hunt lists ManyChat as a 2015 Series A deck with $23.1M raised."
SLIDE10 = (
    "angel.co/manychat\nmike@manychat.com\nTotal Bots Created\nJul-15\nAug-15\nSep-15\nOct-15\nNov-15\n"
    "Dec-15\nJan-16\nFeb-16\nMar-16\nApr-16\n0\n20,000\n40,000\n60,000\n80,000\n100,000\n120,000\n140,000\n"
    "Traction by Apr-16\n140 000+ bots\n500M messages\n"
    "Recreated from public Pitch Deck Hunt / SlideShare source • slide 8"
)
# Memo 91's executive summary, as stored (09_memo.json).
MEMO91_SUMMARY = ("The company states it has raised $23.1M to date [S3] and reports a platform scale of "
                  "140,000+ bots deployed and 500M messages processed [S1, S2].")


class SlideHeadingContextTests(SimpleTestCase):

    def test_the_traction_heading_dates_both_figures_under_it(self):
        self.assertEqual(dated_heading('140 000+ bots', SLIDE10), 'Traction by Apr-16')
        self.assertEqual(dated_heading('500M messages', SLIDE10), 'Traction by Apr-16')

    def test_the_heading_never_becomes_the_structured_period(self):
        for figure in ('140 000+ bots', '500M messages'):
            with self.subTest(figure=figure):
                period = claim_period(figure)
                self.assertEqual((period.kind, period.fiscal_year, period.period_end), ('', None, None))

    def test_unrelated_dates_are_not_attached(self):
        cases = {
            'chart axis value under axis month labels': ('140,000', SLIDE10),
            'undated heading': ('$2M raised', 'Funding\n$2M raised'),
            'bare-year heading': ('$5M raised', '2015 Highlights\n$5M raised'),
            'prose line between heading and figure': (
                '$5M raised', 'Traction by Apr-16\nWe expanded into new markets.\n$5M raised'),
            'dated heading below the figure': ('$5M raised', '$5M raised\nTraction by Apr-16'),
            'forward-looking line, no date': ('500M messages/month', 'Launching on Facebook Messenger this month\n500M messages/month'),
            'figure not on this slide': ('$23.1M raised', SLIDE10),
        }
        for name, (figure, chunk) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(dated_heading(figure, chunk), '')

    def test_prose_with_numbers_between_heading_and_figure_ends_the_block(self):
        # Short lines that hold numbers but are not a figure and its name are
        # prose: the heading may describe something else, so nothing attaches.
        for between in ('Up 3x in 6 months', 'Grew 40% since 2015', '3 markets launched in 2016',
                        '12 employees hired.', 'Over 2 years of growth', 'Raised in 2015'):
            with self.subTest(between=between):
                chunk = f'Traction by Apr-16\n140 000+ bots\n{between}\n500M messages'
                self.assertEqual(dated_heading('500M messages', chunk), '')
                self.assertEqual(dated_heading('140 000+ bots', chunk), 'Traction by Apr-16')

    def test_a_figure_inside_prose_gets_no_heading(self):
        for line in ('We passed 500M messages in March', '500M messages were sent by 40,000 bots'):
            with self.subTest(line=line):
                self.assertEqual(dated_heading('500M messages', f'Traction by Apr-16\n{line}'), '')

    def test_the_real_block_keeps_its_heading_with_more_siblings(self):
        chunk = SLIDE10.replace('500M messages\n', '500M messages\n$1.2M ARR\n35% MoM\n')
        for figure in ('140 000+ bots', '500M messages', '$1.2M ARR', '35% MoM'):
            with self.subTest(figure=figure):
                self.assertEqual(dated_heading(figure, chunk), 'Traction by Apr-16')


class FundingSentenceContextTests(SimpleTestCase):

    def test_pitch_deck_hunt_is_the_narrator_and_2015_is_not_the_as_of_date(self):
        self.assertEqual(claim_narrator(FUNDING_SENTENCE, ['ManyChat']), 'Pitch Deck Hunt')
        period = claim_period(FUNDING_SENTENCE)
        self.assertEqual((period.kind, period.fiscal_year, period.period_end), ('', None, None))
        self.assertEqual(unbound_dates(FUNDING_SENTENCE, period.phrase), ['2015'])
        self.assertEqual(time_wording_in(FUNDING_SENTENCE), ())

    def test_the_company_or_no_one_is_not_a_narrator(self):
        for sentence in ('ManyChat has raised $23.1M.', 'We raised $2M per our last filing.',
                         'The company reports $4M in revenue.', 'Revenue per month is $40K.',
                         'Telegram has 100M users.',
                         # The company in the narrator slot is still the company speaking.
                         'ManyChat reports 140,000+ bots created.',
                         'According to ManyChat, 500M messages were sent.'):
            with self.subTest(sentence=sentence):
                self.assertEqual(claim_narrator(sentence, ['ManyChat']), '')
        self.assertEqual(claim_narrator('According to Crunchbase, ManyChat raised $18M in 2019.', ['ManyChat']),
                         'Crunchbase')

    def test_a_figures_own_period_is_not_reported_as_an_unbound_date(self):
        sentence = 'FY2024 revenue was $5M, up from 2022.'
        period = claim_period(sentence)
        self.assertEqual(period.fiscal_year, 2024)
        self.assertEqual(unbound_dates(sentence, period.phrase), ['2022'])


class TimeWordingGuardTests(SimpleTestCase):

    def test_memo_91s_to_date_is_removed_and_nothing_else_changes(self):
        guarded, removed = guard_time_wording(MEMO91_SUMMARY, {'S3': (), 'S1': (), 'S2': ()})
        self.assertEqual(removed, ['to date'])
        self.assertEqual(guarded, MEMO91_SUMMARY.replace(' to date', ''))

    def test_wording_the_source_itself_uses_is_kept(self):
        allowed = time_wording_in('We have raised $5M to date from angels.')
        text = 'The company states it has raised $5M to date [C1].'
        self.assertEqual(guard_time_wording(text, {'C1': allowed}), (text, []))

    def test_other_current_wording_and_layout(self):
        text = ('• Funding: currently $23.1M raised [S3]\n'
                '• No revenue has been disclosed to date.\n'
                '• Bots: 140,000+ so far [S1]')
        guarded, removed = guard_time_wording(text, {'S3': (), 'S1': ()})
        self.assertEqual(sorted(removed), ['currently', 'so far'])
        self.assertEqual(guarded, ('• Funding: $23.1M raised [S3]\n'
                                   '• No revenue has been disclosed to date.\n'   # cites nothing: kept
                                   '• Bots: 140,000+ [S1]'))

    def test_refs_that_are_not_claim_backed_are_left_alone(self):
        text = 'The team is currently hiring [S9].'
        self.assertEqual(guard_time_wording(text, {'S3': ()}), (text, []))

    def test_citation_before_or_after_the_sentence_stop(self):
        cases = {
            'before': ('ManyChat has raised $23.1M to date [S3].', 'ManyChat has raised $23.1M [S3].'),
            'after': ('ManyChat has raised $23.1M to date. [S3]', 'ManyChat has raised $23.1M. [S3]'),
            'after, no space': ('ManyChat has raised $23.1M to date.[S3]', 'ManyChat has raised $23.1M.[S3]'),
            'after, end of line': ('Raised $23.1M to date. [S3]\nNext line.', 'Raised $23.1M. [S3]\nNext line.'),
            'touching the phrase': ('Raised $23.1M to date[S3].', 'Raised $23.1M [S3].'),
        }
        for name, (text, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(guard_time_wording(text, {'S3': ()}), (expected, ['to date']))

    def test_grouped_references(self):
        allowed = {'S1': (), 'S3': (), 'C2': ('so far',)}
        cases = {
            'comma group': ('Bots: 140,000+ so far [S1, S3].', 'Bots: 140,000+ [S1, S3].'),
            'semicolon group, after the stop': ('Bots: 140,000+ so far. [S1; S3]', 'Bots: 140,000+. [S1; S3]'),
            'adjacent groups': ('Bots: 140,000+ so far.[S1][S3]', 'Bots: 140,000+.[S1][S3]'),
            # One cited source does not say "so far": the shared sentence may not either.
            'one source allows, one does not': ('140,000+ bots so far [C2, S1].', '140,000+ bots [C2, S1].'),
        }
        for name, (text, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(guard_time_wording(text, allowed), (expected, ['so far']))
        kept = '140,000+ bots so far [C2].'
        self.assertEqual(guard_time_wording(kept, allowed), (kept, []))

    def test_a_citation_after_the_stop_never_moves_to_the_next_sentence(self):
        text = 'ManyChat lists $23.1M raised. [S3] No revenue has been disclosed to date.'
        self.assertEqual(guard_time_wording(text, {'S3': ()}), (text, []))
        text = ('The company has raised $23.1M to date. [S3] Revenue has not been disclosed so far. '
                'Bots total 140,000+ currently [S1].')
        self.assertEqual(guard_time_wording(text, {'S3': (), 'S1': ()}), (
            'The company has raised $23.1M. [S3] Revenue has not been disclosed so far. Bots total 140,000+ [S1].',
            ['to date', 'currently']))

    def test_questions_and_requests_for_current_figures_are_kept(self):
        allowed = {'S1': (), 'S3': ()}
        for text in ('What has ManyChat raised to date [S3]?',
                     'How many bots are live currently? [S1]',
                     '- Is the $23.1M [S3] the total raised to date?',
                     '3. How many messages has the platform sent so far [S1]?',
                     'Confirm the total raised to date [S3].',
                     '• Ask management how many bots are active currently [S1].',
                     'Q2: Verify whether 500M messages is the count to date [S1].'):
            with self.subTest(text=text):
                self.assertEqual(guard_time_wording(text, allowed), (text, []))

    def test_a_statement_next_to_a_question_is_still_guarded(self):
        text = ('How much has ManyChat raised to date [S3]?\n'
                'ManyChat has raised $23.1M to date [S3].\n'
                'What has the company raised so far? The deck lists $23.1M so far. [S3]')
        self.assertEqual(guard_time_wording(text, {'S3': ()}), (
            'How much has ManyChat raised to date [S3]?\n'
            'ManyChat has raised $23.1M [S3].\n'
            'What has the company raised so far? The deck lists $23.1M. [S3]',
            ['to date', 'so far']))


class ManyChatExtractionTests(TestCase):
    """The real insight and claim extraction over slides 2 and 10, into the memo boundary and out."""

    def setUp(self):
        from matchmaking.models import Application
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('mc_dates_owner', password='x')
        self.app = Application.objects.create(
            user=self.owner, company_name='ManyChat', founder_name='F', email='mcd@t.test',
            description='d', sector='Software', stage='Series A', is_premium=True)
        self.doc = DocumentSource.objects.create(
            filename='manychat.pdf', source_entity='ManyChat', uploaded_by=self.owner,
            document_type='pitch_deck', status='analyzed')
        for index, (page, text) in enumerate(((2, SLIDE2), (10, SLIDE10))):
            DocumentChunk.objects.create(document=self.doc, chunk_index=index, page_number=page,
                                         raw_text=text, token_count=60)
        from . import truth_delta_tasks
        ZeldaIntelligencePipelineV2()._analyze_document(self.doc, '')
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay'):
            truth_delta_tasks.extract_claims_from_insights(self.doc.id)
        self.claims = {c.category if c.category != 'usage' else c.unit: c
                       for c in ClaimedDatapoint.objects.filter(document=self.doc)}

    def test_claims_keep_sentence_narrator_and_heading_but_no_period(self):
        funding = self.claims['funding_raised']
        self.assertEqual(funding.claimed_value_numeric, 23.1e6)
        self.assertEqual(funding.narrator, 'Pitch Deck Hunt')
        # Verbatim; claim_attribution.source_sentence's splitter drops the final full stop.
        self.assertEqual(funding.source_sentence, FUNDING_SENTENCE.rstrip('.'))
        self.assertEqual(funding.source_context, '')
        for unit in ('bots', 'messages'):
            with self.subTest(unit=unit):
                self.assertEqual(self.claims[unit].source_context, 'Traction by Apr-16')
                self.assertEqual(self.claims[unit].narrator, '')
        for claim in self.claims.values():
            with self.subTest(claim=claim.claimed_value):
                self.assertEqual((claim.time_period, claim.period_kind, claim.period_fiscal_year,
                                  claim.period_end), ('', '', None, None))

    def test_truth_delta_comparison_and_score_are_unchanged(self):
        from .truth_delta_engine import TruthDeltaEngine
        with mock.patch('zelda_api.truth_delta_engine.data_source_manager.create_observed_datapoints'), \
             mock.patch('zelda_api.truth_delta_engine.data_source_manager.fetch_news_headlines', return_value=[]), \
             mock.patch('zelda_api.dataforb2b_adapter.observe', return_value='unconfigured'), \
             mock.patch.object(TruthDeltaEngine, '_call_claude_for_verification', return_value={'per_claim': []}):
            report = TruthDeltaEngine().verify_document(self.doc.id)
        self.assertEqual((report.overall_truth_score, report.credibility_risk), (None, 'unknown'))
        self.assertTrue(all(state == 'no_data' for state in report.category_states().values()))
        for row in report.details['comparison']:
            self.assertFalse(row.get('claim_period_kind'))
            self.assertIsNone(row.get('claim_fiscal_year'))

    def context(self):
        from .tests import grounded_context_for
        return grounded_context_for(self.doc)

    def test_the_memo_is_told_as_of_narrator_and_context_but_not_the_sentence(self):
        payload = self.context().to_prompt_payload()
        funding_items = [i for i in payload['items'] if i['statement'] == '$23.1M raised']
        self.assertEqual({i['kind'] for i in funding_items}, {'claim', 'statement'})
        for item in funding_items:
            with self.subTest(kind=item['kind']):
                self.assertEqual(item['as_of'], 'not stated')
                self.assertEqual(item['narrator'], 'Pitch Deck Hunt')
                self.assertEqual(item['dates_not_as_of'], ['2015'])
        for item in (i for i in payload['items'] if i['statement'] in ('140 000+ bots', '500M messages')):
            with self.subTest(statement=item['statement'], kind=item['kind']):
                self.assertEqual(item['source_context'], 'Traction by Apr-16')
                self.assertEqual(item['as_of'], 'not stated')
        text = json.dumps(payload)
        self.assertNotIn('Series A deck with', text)          # the sentence itself stays out
        self.assertNotIn('SlideShare deck has 10 slides', text)

    @staticmethod
    def refs(context):
        return ({i.statement: i.ref for i in context.items if i.kind == 'statement'},
                {i.statement: i.ref for i in context.items if i.kind == 'claim'})

    def memo_reply(self, context, sections=None):
        refs, claim_refs = self.refs(context)
        summary = (f"The company states it has raised $23.1M to date [{refs['$23.1M raised']}] and reports "
                   f"140,000+ bots so far [{refs['140 000+ bots']}].")
        concerns = (f"- Funding of $23.1M is currently unconfirmed [{claim_refs['$23.1M raised']}]\n"
                    f"- No revenue has been disclosed to date.")
        sections = sections or {'executive_summary': summary, 'open_concerns': concerns}
        response = mock.Mock()
        response.content = [mock.Mock(text=json.dumps({**sections, 'evidence_level': 'LITTLE_EVIDENCE'}))]
        response.usage = mock.Mock(input_tokens=1, output_tokens=1)
        return response

    def generate(self, sections=None):
        context = self.context()
        if callable(sections):
            sections = sections(*self.refs(context))
        with mock.patch('anthropic.Anthropic') as client_cls:
            client_cls.return_value.messages.create.return_value = self.memo_reply(context, sections)
            result = ZeldaIntelligencePipelineV2()._generate_memo(context)
            call = client_cls.return_value.messages.create.call_args.kwargs
        self.assertNotIn('error', result, result.get('error'))
        return IntelligenceMemo.objects.get(pk=result['memo_id']), call

    def test_generated_memo_cannot_present_the_listing_as_a_current_total(self):
        memo, call = self.generate()
        self.assertNotIn('to date', memo.executive_summary)
        self.assertNotIn('so far', memo.executive_summary)
        # Funding-source fidelity (tests_funding_fidelity): Pitch Deck Hunt takes only the funding clause;
        # the company keeps the money and its own bot count.
        self.assertIn('Pitch Deck Hunt lists the company as having raised $23.1M [S', memo.executive_summary)
        self.assertIn('and the company reports 140,000+ bots [S', memo.executive_summary)
        self.assertNotIn('currently', memo.open_concerns)
        self.assertIn('No revenue has been disclosed to date.', memo.open_concerns)   # cites nothing: kept
        self.assertIn('9. Dates and who is speaking', call['system'])
        self.assertIn('Pitch Deck Hunt', call['messages'][0]['content'])
        self.assertIn('"as_of": "not stated"', call['messages'][0]['content'])

    def test_writer_guards_citations_placed_after_the_stop_and_grouped(self):
        def sections(refs, claim_refs):
            funding, bots, messages = refs['$23.1M raised'], refs['140 000+ bots'], refs['500M messages']
            return {
                'executive_summary': (f"The company has raised $23.1M to date. [{funding}] No revenue has been "
                                      f"disclosed to date. The platform reports 140,000+ bots and 500M messages "
                                      f"so far [{bots}, {messages}]."),
                'supported_points': (f"- Scale: 500M messages currently.[{messages}][{bots}]\n"
                                     f"- Pitch Deck Hunt lists $23.1M raised [{claim_refs['$23.1M raised']}]."),
            }
        memo, _ = self.generate(sections)
        self.assertEqual(memo.executive_summary, (
            'The company has raised $23.1M (per Pitch Deck Hunt). [{0}] No revenue has been disclosed to date. '
            'The platform reports '
            '140,000+ bots and 500M messages [{1}, {2}].').format(*self.cited(memo.executive_summary)))
        self.assertTrue(memo.supported_points.startswith('- Scale: 500M messages.[S'), memo.supported_points)
        self.assertNotIn('currently', memo.supported_points)
        self.assertIn('Pitch Deck Hunt lists $23.1M raised [C', memo.supported_points)

    @staticmethod
    def cited(text):
        import re
        return [r for group in re.findall(r'\[([^\]]+)\]', text) for r in group.split(', ')]

    def test_writer_keeps_research_questions_for_current_figures(self):
        def sections(refs, claim_refs):
            funding, bots = refs['$23.1M raised'], refs['140 000+ bots']
            return {
                'executive_summary': f"Pitch Deck Hunt lists $23.1M raised [{funding}].",
                'questions_for_management': [
                    f"What is the total ManyChat has raised to date, beyond the $23.1M listed [{funding}]?",
                    f"How many bots are active currently, against 140,000+ created by Apr-16 [{bots}]?",
                    f"Confirm the number of messages sent so far [{refs['500M messages']}].",
                    f"The deck's 140,000+ bots are the count so far [{bots}].",
                ],
            }
        memo, _ = self.generate(sections)
        questions = memo.questions_for_management.splitlines()
        self.assertEqual(len(questions), 4, questions)
        self.assertIn('raised to date, beyond the $23.1M listed', questions[0])
        self.assertIn('active currently, against 140,000+', questions[1])
        self.assertIn('messages sent so far [S', questions[2])
        # A statement in the same section is still guarded.
        self.assertNotIn('so far', questions[3])
        self.assertIn("140,000+ bots are the count [S", questions[3])

    def test_ic_memo_and_company_overview_show_the_guarded_text(self):
        from matchmaking.models import InvestorApplication
        memo, _ = self.generate()
        staff = User.objects.create_user('mc_dates_staff', password='x', is_staff=True)
        self.client.force_login(staff)
        ic_memo = self.client.get(reverse('zelda_api:ic_memo', args=[self.doc.id])).content.decode()
        investor = User.objects.create_user('mc_dates_investor', password='x')
        InvestorApplication.objects.create(user=investor, full_name='I', company_name='Fund', email='i@t.test',
                                           investment_focus='SaaS', investment_stage='Seed')
        self.client.force_login(investor)
        overview = self.client.get(reverse('matchmaking:company_overview', args=[self.app.pk]))
        self.assertEqual(overview.status_code, 200)
        for name, html in (('ic_memo', ic_memo), ('overview', overview.content.decode())):
            with self.subTest(surface=name):
                self.assertIn('Pitch Deck Hunt lists the company as having raised $23.1M [S', html)
                self.assertNotIn('$23.1M to date', html)
