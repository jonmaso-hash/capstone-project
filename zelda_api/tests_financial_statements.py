"""Consolidated financials survive from a filing's pages into the saved valuation report.

Regression for sandbox order d76ea12f: an Apple FY2026 10-K produced a valuation
built on "$14.8 billion" of revenue, which was the filing's deferred revenue
balance, while the consolidated statement of operations on PDF page 35 never
reached the report. The fixture is that filing's extracted text for pages 1,
35, 42 and 44. Production code holds no Apple values.
"""
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from .financial_statements import names_deferred_revenue, read_income_statement
from .intelligence_pipeline import ZeldaIntelligencePipelineV2
from .utils import page_marker, split_pages
from .valuation_gate import govern_net_margin
from .vector_models import BusinessValuationReport, DocumentChunk, DocumentSource, IntelligenceInsight

FIXTURE = (Path(__file__).parent / 'fixtures' / 'sec_10k_income_statement_pages.txt').read_text(encoding='utf-8')
PAGES = dict(split_pages(FIXTURE))


def pages(*numbers, edit=None):
    text = ''.join(page_marker('page', n) + '\n' + PAGES[n] + '\n' for n in numbers)
    return edit(text) if edit else text


def statement_page(header='Years Ended', dates='December 31, 2026 December 31, 2025', scale='(In thousands)',
                   rows='Total revenues $ 12,500 $ 10,000\nGross profit 5,000 4,000\nNet income $ 1,250 $ 900'):
    return (page_marker('page', 7) + '\nExample Holdings, Inc.\nCONSOLIDATED STATEMENTS OF INCOME\n'
            f'{scale}\n{header}\n{dates}\n{rows}\n')


class IncomeStatementParsingTests(SimpleTestCase):
    def test_apple_10k_statement_keeps_figures_and_provenance(self):
        statement = read_income_statement(FIXTURE)
        sales, prior = statement.latest('net_sales'), statement.prior('net_sales')
        income, margin = statement.latest('net_income'), statement.latest('gross_margin')

        self.assertEqual(sales.value, Decimal('478834000000'))
        self.assertEqual(prior.value, Decimal('416161000000'))
        self.assertEqual(income.value, Decimal('132175000000'))
        self.assertEqual(sales.amount(), '$478.834 billion')
        self.assertEqual(prior.amount(), '$416.161 billion')
        self.assertEqual(income.amount(), '$132.175 billion')
        self.assertEqual(round(statement.net_sales_growth().value), 15)
        self.assertEqual(round(statement.gross_margin_percentage().value, 1), Decimal('48.8'))
        for figure in (sales, prior, income, margin):
            with self.subTest(figure=figure.metric):
                self.assertEqual((figure.entity, figure.scope, figure.currency, figure.scale, figure.source_page,
                                  figure.period_type), ('Apple Inc.', 'consolidated', 'USD', 'millions', 35, 'annual'))
                self.assertEqual(figure.statement, 'Consolidated Statements of Operations')
        self.assertEqual((sales.line_item, sales.period_end, prior.period_end),
                         ('Total net sales', date(2026, 9, 26), date(2025, 9, 27)))
        self.assertEqual(sales.period_label, 'FY2026 (fiscal year ended September 26, 2026)')

    def test_deferred_revenue_page_never_yields_net_sales(self):
        self.assertIn('deferred revenue of $14.8 billion', PAGES[42])
        self.assertIsNone(read_income_statement(pages(42)))
        self.assertTrue(names_deferred_revenue('the Company had total deferred revenue of $14.8 billion'))
        self.assertFalse(names_deferred_revenue('Total net sales $ 478,834'))

    def test_deferred_revenue_row_never_qualifies_as_net_sales(self):
        self.assertIsNone(read_income_statement(statement_page(rows='Deferred revenue $ 14,800 $ 13,700')))
        self.assertIsNotNone(read_income_statement(statement_page()))  # positive control

    def test_prose_naming_the_statement_is_not_the_statement(self):
        self.assertIn('Consolidated Statements of Operations.', PAGES[44])
        self.assertIsNone(read_income_statement(pages(1, 42, 44)))

    def test_unknown_or_interim_period_never_qualifies_as_annual_revenue(self):
        cases = {
            'no period dates': lambda t: re.sub(r'September \d+,\s*\d{4}', '', t),
            'no annual header': lambda t: t.replace('Years Ended', ''),
            'quarterly header': lambda t: t.replace('Years Ended', 'Three Months Ended'),
        }
        self.assertIsNotNone(read_income_statement(pages(35)))  # positive control
        for name, edit in cases.items():
            with self.subTest(name):
                self.assertIsNone(read_income_statement(pages(35, edit=edit)))

    def test_unknown_scale_or_currency_is_rejected(self):
        self.assertIsNone(read_income_statement(pages(35, edit=lambda t: re.sub(r'\(In millions[^)]*\)', '', t))))
        self.assertIsNone(read_income_statement(pages(35, edit=lambda t: t.replace('$', ''))))
        self.assertIsNone(read_income_statement(statement_page(scale='(In thousands of euros)')))

    def test_scale_and_split_digit_groups(self):
        statement = read_income_statement(statement_page(rows='Total revenues $ 12,5 00 $ 10,000\nNet income $ 1,250 $ 900'))
        self.assertEqual(statement.latest('net_sales').value, Decimal('12500000'))
        self.assertEqual(statement.latest('net_sales').amount(), '$12.5 million')
        self.assertEqual(statement.latest('net_sales').entity, 'Example Holdings, Inc.')

    def test_row_with_wrong_column_count_is_dropped(self):
        statement = read_income_statement(statement_page(rows='Total revenues $ 12,500 $ 10,000\nNet income $ 1,250'))
        self.assertIsNotNone(statement.latest('net_sales'))
        self.assertIsNone(statement.latest('net_income'))


MISSING_MULTIPLE = 'An enterprise-value-to-revenue multiple stated in the submitted documents'


def claude_reply(**fields):
    body = {'business_overview': 'Overview.', 'financial_summary': 'Model summary.', 'risk_report': '1. Risk.',
            'valuation_summary': 'Model valuation text.', 'valuation_low': 88800000000,
            'valuation_high': 148000000000, 'multiple_basis': None, 'confidence': 60, **fields}
    response = mock.Mock()
    response.content = [mock.Mock(text=json.dumps(body))]
    return response


class ValuationReportGateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('valuation_gate_owner', password='x')
        self.pipeline = ZeldaIntelligencePipelineV2()

    def generate(self, raw_text, reply):
        doc = DocumentSource.objects.create(filename='filing.pdf', source_entity='Subject Co', uploaded_by=self.user,
                                            document_type='business_valuation', raw_text_full=raw_text)
        with mock.patch('anthropic.Anthropic') as anthropic:
            anthropic.return_value.messages.create.return_value = reply
            result = self.pipeline._generate_valuation_report(doc, {'confidence': 0.5})
            prompt = anthropic.return_value.messages.create.call_args.kwargs['messages'][0]['content']
        self.assertNotIn('error', result)
        return BusinessValuationReport.objects.get(document=doc), prompt

    def test_filing_without_multiple_basis_shows_verified_summary_and_no_range(self):
        report, prompt = self.generate(FIXTURE, claude_reply())

        self.assertIsNone(report.valuation_low)
        self.assertIsNone(report.valuation_high)
        for text in ('$478.834 billion', 'FY2026 (fiscal year ended September 26, 2026)', '$416.161 billion',
                     'FY2025 (fiscal year ended September 27, 2025)', ': 15% (', '48.8%', '$132.175 billion',
                     'reported as $478,834 million', 'Consolidated Statements of Operations of Apple Inc.',
                     'consolidated; USD; amounts reported in millions; PDF page 35'):
            with self.subTest(text=text):
                self.assertIn(text, report.financial_summary)
        self.assertNotIn('14.8', report.financial_summary)
        for text in ('No numeric valuation is given', 'Method:', 'Assumptions: none applied', 'Missing inputs:',
                     MISSING_MULTIPLE, '$478.834 billion'):
            with self.subTest(text=text):
                self.assertIn(text, report.valuation_summary)
        self.assertIn('$478.834 billion', prompt)
        self.assertNotIn('"revenue": "$14.8', prompt)

    def test_fabricated_multiple_basis_is_not_a_basis(self):
        reply = claude_reply(multiple_basis={
            'quote': 'Large technology companies trade at 6x to 10x enterprise value to revenue.'})
        report, _ = self.generate(FIXTURE, reply)
        self.assertIsNone(report.valuation_low)
        self.assertIn(MISSING_MULTIPLE, report.valuation_summary)

    def evidence(self, *sentences):
        return FIXTURE + page_marker('page', 90) + '\n' + '\n'.join(sentences) + '\n'

    def assert_withheld(self, report):
        self.assertIsNone(report.valuation_low)
        self.assertIsNone(report.valuation_high)
        self.assertIn('No numeric valuation is given', report.valuation_summary)
        self.assertIn(MISSING_MULTIPLE, report.valuation_summary)
        self.assertNotIn('Estimated enterprise value', report.valuation_summary)
        self.assertEqual(report.range_basis_label, '')
        self.assertIn('$478.834 billion', report.financial_summary)

    def test_supported_ev_revenue_multiple_gives_a_computed_enterprise_value_range(self):
        quote = 'Comparable hardware companies trade at EV/Revenue multiples of 6.0x to 7.5x trailing revenue.'
        report, _ = self.generate(self.evidence(quote), claude_reply(multiple_basis={'quote': quote}))
        self.assertEqual(report.valuation_low, Decimal('2873004000000'))   # 478,834 million x 6.0
        self.assertEqual(report.valuation_high, Decimal('3591255000000'))  # 478,834 million x 7.5
        summary = report.valuation_summary
        for text in ('Estimated enterprise value (EV/Revenue) for Subject Co: $2.873004 trillion to $3.591255 trillion.',
                     'This is enterprise value, not equity value',
                     'Formula: enterprise value = Total net sales, FY2026 (fiscal year ended September 26, 2026) '
                     '× EV/Revenue multiple.',
                     '• Low: $478,834 million × 6.0x = $2,873,004 million',
                     '• High: $478,834 million × 7.5x = $3,591,255 million',
                     '• Total net sales: Consolidated Statements of Operations of Apple Inc. (USD; reported in millions; '
                     'PDF page 35).',
                     f'• EV/Revenue multiple of 6.0x to 7.5x, quoted from the submitted documents (PDF page 90): "{quote}"'):
            with self.subTest(text=text):
                self.assertIn(text, summary)
        self.assertEqual(report.range_basis_label, 'Estimated enterprise value (EV/Revenue)')

    def test_supported_multiple_is_found_in_the_evidence_without_a_model_quote(self):
        report, _ = self.generate(self.evidence('Precedent transactions closed at 7x EV/Sales on annual net sales.'),
                                  claude_reply(multiple_basis=None))
        self.assertEqual(report.valuation_low, Decimal('3351838000000'))
        self.assertEqual(report.valuation_low, report.valuation_high)
        self.assertIn('(PDF page 90): "Precedent transactions closed at 7x EV/Sales', report.valuation_summary)

    def test_irrelevant_8x_quote_is_not_a_basis(self):
        quote = 'Unit shipments of the new product line grew 8x over five years.'
        report, _ = self.generate(self.evidence(quote), claude_reply(multiple_basis={'quote': quote}))
        self.assert_withheld(report)

    def test_ebitda_multiple_paired_with_revenue_is_not_a_revenue_basis(self):
        for quote in ('Comparable companies trade at 12x EV/EBITDA and grew revenue 15% last year.',
                      'Peers trade at an enterprise value of 12x EBITDA on trailing revenue of similar scale.'):
            with self.subTest(quote=quote):
                report, _ = self.generate(self.evidence(quote), claude_reply(multiple_basis={'quote': quote}))
                self.assert_withheld(report)

    def test_ambiguous_bases_are_withheld(self):
        cases = {
            'no enterprise value': 'Comparable hardware companies trade at 7.5x trailing revenue.',
            'forward multiple': 'Comparable companies trade at 6x to 7x forward EV/Revenue.',
            'equity basis': 'Peers trade at 5x price-to-sales, or 6x EV/Revenue.',
            'two separate multiples': 'Peers trade at 6x EV/Revenue while leaders trade at 9x EV/Revenue.',
            'range plus another multiple': 'Peers trade at 6x to 7x EV/Revenue and the sector leader at 11x.',
        }
        for name, quote in cases.items():
            with self.subTest(case=name):
                report, _ = self.generate(self.evidence(quote), claude_reply(multiple_basis={'quote': quote}))
                self.assert_withheld(report)

    def test_conflicting_evidence_is_withheld(self):
        raw = self.evidence('Comparable companies trade at 6x EV/Revenue on trailing net sales.',
                            'Precedent transactions closed at 9x EV/Revenue on trailing net sales.')
        report, _ = self.generate(raw, claude_reply(multiple_basis=None))
        self.assert_withheld(report)

    def test_model_bounds_that_disagree_with_the_inputs_are_never_used(self):
        quote = 'Comparable hardware companies trade at EV/Revenue multiples of 6.0x to 7.5x trailing revenue.'
        reply = claude_reply(valuation_low=88_800_000_000, valuation_high=148_000_000_000,
                             valuation_summary='Applying 6-10x to revenue of $14.8 billion gives $88.8B to $148B.',
                             multiple_basis={'quote': quote})
        report, _ = self.generate(self.evidence(quote), reply)
        self.assertEqual((report.valuation_low, report.valuation_high),
                         (Decimal('2873004000000'), Decimal('3591255000000')))
        for model_text in ('88.8', '148', '14.8', '6-10x'):
            with self.subTest(model_text=model_text):
                self.assertNotIn(model_text, report.valuation_summary)

    def test_model_bounds_without_a_basis_are_dropped(self):
        report, _ = self.generate(FIXTURE, claude_reply(valuation_low=2_873_004_000_000,
                                                        valuation_high=3_591_255_000_000))
        self.assert_withheld(report)

    def test_value_too_large_to_store_is_withheld(self):
        quote = 'Comparable companies trade at 25x EV/Revenue on trailing net sales.'
        report, _ = self.generate(self.evidence(quote), claude_reply(multiple_basis={'quote': quote}))
        self.assertIsNone(report.valuation_low)
        self.assertIn('below $10 trillion', report.valuation_summary)

    def test_no_verified_annual_revenue_means_no_range_even_with_a_quoted_multiple(self):
        quote = 'Comparable companies trade at 4x EV/Revenue on trailing revenue.'
        raw = page_marker('page', 1) + '\nCurrent Revenue: $4.5M\n' + quote + '\n'
        report, _ = self.generate(raw, claude_reply(valuation_low=1, valuation_high=2, multiple_basis={'quote': quote}))
        self.assertIsNone(report.valuation_high)
        self.assertIn('Annual revenue from a financial statement', report.valuation_summary)
        self.assertEqual(report.financial_summary, 'Model summary.')


class DeferredRevenueFactTests(TestCase):
    """The sentence extractor trims context; the fact builder must still see it."""

    def facts_for(self, sentence):
        user = get_user_model().objects.create_user(f'deferred_{abs(hash(sentence))}', password='x')
        doc = DocumentSource.objects.create(filename='f.pdf', source_entity='Subject Co', uploaded_by=user,
                                            document_type='business_valuation', raw_text_full=sentence)
        chunk = DocumentChunk.objects.create(document=doc, chunk_index=0, page_number=42, raw_text=sentence,
                                             token_count=40)
        insight = IntelligenceInsight.objects.create(document=doc, category='Revenue', confidence_score=95,
                                                     insight_text='$14.8 billion and $13.7 billion, respectively')
        insight.source_chunks.set([chunk])
        return ZeldaIntelligencePipelineV2()._build_structured_context(
            doc, doc.insights.all(), ZeldaIntelligencePipelineV2.owner_task_principal(doc))

    def test_trimmed_deferred_revenue_sentence_is_not_revenue(self):
        facts = self.facts_for('As of September 26, 2026 and September 27, 2025, the Company had total deferred '
                               'revenue of $14.8 billion and $13.7 billion, respectively. Other text.')
        self.assertIsNone(facts['revenue'])
        self.assertIn('Revenue / ARR / MRR', facts['missing_fields'])

    def test_same_figure_from_a_revenue_sentence_still_counts(self):
        facts = self.facts_for('Total revenue was $14.8 billion and $13.7 billion, respectively. Other text.')
        self.assertEqual(facts['revenue'], '$14.8')

    def prompt_for(self, sentence):
        user = get_user_model().objects.create_user(f'prompt_{abs(hash(sentence))}', password='x')
        doc = DocumentSource.objects.create(filename='f.pdf', source_entity='Apple Inc.', uploaded_by=user,
                                            document_type='business_valuation', raw_text_full=FIXTURE)
        chunk = DocumentChunk.objects.create(document=doc, chunk_index=0, page_number=42, raw_text=sentence,
                                             token_count=40)
        insight = IntelligenceInsight.objects.create(document=doc, category='Revenue', confidence_score=95,
                                                     insight_text='$14.8 billion and $13.7 billion, respectively')
        insight.source_chunks.set([chunk])
        with mock.patch('anthropic.Anthropic') as anthropic:
            anthropic.return_value.messages.create.return_value = claude_reply()
            ZeldaIntelligencePipelineV2()._generate_valuation_report(doc, {'confidence': 0.5})
            prompt = anthropic.return_value.messages.create.call_args.kwargs['messages'][0]['content']
        report = BusinessValuationReport.objects.get(document=doc)
        return prompt, report

    def test_deferred_revenue_insight_never_reaches_the_valuation_prompt(self):
        prompt, report = self.prompt_for('the Company had total deferred revenue of $14.8 billion and '
                                         '$13.7 billion, respectively. Other text.')
        self.assertNotIn('$14.8 billion', prompt)
        self.assertIn('$478.834 billion', prompt)
        self.assertIn('No numeric valuation is given for Apple Inc.\n', report.valuation_summary)

    def test_revenue_insight_still_reaches_the_valuation_prompt(self):
        prompt, _ = self.prompt_for('Total revenue was $14.8 billion and $13.7 billion, respectively. Other text.')
        self.assertIn('$14.8 billion', prompt)


BUYBACK_LINE = next(line for line in PAGES[31].splitlines() if 'share repurchase program of up to' in line)
SERIES_B_LINE = ('In March 2026, the Company raised $25 million in a Series B financing led by Example Ventures '
                 'to expand its manufacturing capacity.')


class CapitalReturnIsNotFundraisingTests(TestCase):
    """Apple's buyback authorization was reported as "a $100 billion capital raise" (order d76ea12f)."""

    # The Funding insight the extractor saved for that order, before this fix.
    SAVED_BUYBACK_INSIGHT = '$100 billion and raised its quarterly dividend from $0.26 to $0.27 per s'

    def setUp(self):
        self.pipeline = ZeldaIntelligencePipelineV2()
        self.keywords = self.pipeline.ANALYSIS_CATEGORIES['Funding']

    def test_share_repurchase_authorization_yields_no_funding_figure(self):
        self.assertIn('repurchase program of up to $100 billion and raised its quarterly dividend', BUYBACK_LINE)
        self.assertIsNone(self.pipeline._extract_clean_value('Funding', BUYBACK_LINE))
        value, _, _ = self.pipeline._smart_extract('Funding', PAGES[31], self.keywords)
        self.assertNotIn('$100 billion', value or '')

    def test_genuine_fundraising_disclosure_yields_its_figure(self):
        self.assertIn('$25 million', self.pipeline._extract_clean_value('Funding', SERIES_B_LINE))
        value, confidence, _ = self.pipeline._smart_extract('Funding', SERIES_B_LINE, self.keywords)
        self.assertIn('$25 million', value)
        self.assertGreater(confidence, 0)

    def document(self, insight_text, source):
        user = get_user_model().objects.create_user(f'capital_{abs(hash(insight_text + source))}', password='x')
        doc = DocumentSource.objects.create(filename='f.pdf', source_entity='Subject Co', uploaded_by=user,
                                            document_type='business_valuation', raw_text_full=FIXTURE)
        chunk = DocumentChunk.objects.create(document=doc, chunk_index=0, page_number=31, raw_text=source,
                                             token_count=60)
        insight = IntelligenceInsight.objects.create(document=doc, category='Funding', confidence_score=95,
                                                     insight_text=insight_text)
        insight.source_chunks.set([chunk])
        return doc

    def prompt_for(self, doc):
        with mock.patch('anthropic.Anthropic') as anthropic:
            anthropic.return_value.messages.create.return_value = claude_reply()
            self.pipeline._generate_valuation_report(doc, {'confidence': 0.5})
            return anthropic.return_value.messages.create.call_args.kwargs['messages'][0]['content']

    def test_saved_buyback_insight_is_not_a_raise_amount_or_prompt_funding(self):
        doc = self.document(self.SAVED_BUYBACK_INSIGHT, PAGES[31])
        facts = self.pipeline._build_structured_context(doc, doc.insights.all(), self.pipeline.owner_task_principal(doc))
        self.assertIsNone(facts['raise_amount'])
        prompt = self.prompt_for(doc)
        self.assertNotIn('$100 billion', prompt)
        self.assertNotIn('raise_amount', prompt)

    def test_genuine_raise_insight_keeps_raise_amount_and_reaches_the_prompt(self):
        doc = self.document('$25 million in a Series B financing led by Example Ventures', SERIES_B_LINE)
        facts = self.pipeline._build_structured_context(doc, doc.insights.all(), self.pipeline.owner_task_principal(doc))
        self.assertIn('$25 million', facts['raise_amount'])
        prompt = self.prompt_for(doc)
        self.assertIn('$25 million in a Series B financing', prompt)
        self.assertIn('raise_amount', prompt)


def viewer_principal(user):
    from django.test import RequestFactory
    from .principal import Principal
    request = RequestFactory().get('/')
    request.user, request.session = user, {}
    return Principal.from_request(request, label='test viewer')


class InsightSourceSentenceScopeTests(TestCase):
    """
    The guards read an insight's source text only through document_chunks(),
    for the principal actually asking: the owner in a background job, the
    viewer in a web request. A viewer without text access gets the figure
    marked unavailable -- not counted, not confirmed, and no refusal.
    """

    def setUp(self):
        self.owner = get_user_model().objects.create_user('source_scope_owner', password='x')
        self.viewer = get_user_model().objects.create_user('source_scope_viewer', password='x')

    def doc(self, owner=None):
        return DocumentSource.objects.create(filename='f.pdf', source_entity='Subject Co',
                                             uploaded_by=owner or self.owner,
                                             document_type='business_valuation', raw_text_full='')

    def saved(self, doc, source, category='Funding', text='$25 million in a Series B'):
        chunk = DocumentChunk.objects.create(document=doc, chunk_index=doc.insights.count(), page_number=31,
                                             raw_text=source, token_count=60)
        insight = IntelligenceInsight.objects.create(document=doc, category=category, confidence_score=95,
                                                     insight_text=text)
        insight.source_chunks.set([chunk])
        return insight

    def facts(self, doc, principal):
        return ZeldaIntelligencePipelineV2()._build_structured_context(doc, doc.insights.all(), principal)

    # -- authorized worker ----------------------------------------------------

    def test_worker_reads_through_document_chunks_as_the_owner_of_this_document(self):
        from . import retrieval
        doc = self.doc()
        self.saved(doc, SERIES_B_LINE)
        with mock.patch.object(retrieval, 'document_chunks', wraps=retrieval.document_chunks) as scoped:
            facts = self.facts(doc, ZeldaIntelligencePipelineV2.owner_task_principal(doc))
        self.assertIn('$25 million', facts['raise_amount'])
        self.assertEqual(facts['_unavailable_evidence'], [])
        principal, scoped_doc = scoped.call_args.args
        self.assertEqual((principal.user, principal.origin, scoped_doc), (self.owner, 'task', doc))

    def test_valuation_job_acts_as_the_owner_and_keeps_its_guards(self):
        from . import retrieval
        doc = self.doc()
        self.saved(doc, SERIES_B_LINE)
        self.saved(doc, PAGES[31], text=CapitalReturnIsNotFundraisingTests.SAVED_BUYBACK_INSIGHT)
        with mock.patch.object(retrieval, 'document_chunks', wraps=retrieval.document_chunks) as scoped, \
                mock.patch('anthropic.Anthropic') as anthropic:
            anthropic.return_value.messages.create.return_value = claude_reply()
            result = ZeldaIntelligencePipelineV2()._generate_valuation_report(doc, {'confidence': 0.5})
            prompt = anthropic.return_value.messages.create.call_args.kwargs['messages'][0]['content']
        self.assertNotIn('error', result)
        self.assertIn('$25 million in a Series B', prompt)
        self.assertNotIn('$100 billion', prompt)
        self.assertTrue(scoped.call_args_list)
        for call in scoped.call_args_list:
            self.assertEqual((call.args[0].user, call.args[0].origin), (self.owner, 'task'))

    def test_valuation_job_whose_owner_cannot_be_a_principal_writes_no_report(self):
        gone = get_user_model().objects.create_user('source_scope_gone', password='x', is_active=False)
        doc = self.doc(gone)
        self.saved(doc, SERIES_B_LINE)
        with mock.patch('anthropic.Anthropic') as anthropic:
            result = ZeldaIntelligencePipelineV2()._generate_valuation_report(doc, {'confidence': 0.5})
        self.assertIn('error', result)
        anthropic.return_value.messages.create.assert_not_called()
        self.assertFalse(BusinessValuationReport.objects.filter(document=doc).exists())

    # -- web viewer -----------------------------------------------------------

    def test_non_owner_viewer_without_text_access_gets_figures_marked_unavailable(self):
        from . import retrieval
        doc = self.doc()
        self.saved(doc, 'Total revenue was $14.8 billion and $13.7 billion, respectively. Other text.',
                   category='Revenue', text='$14.8 billion and $13.7 billion, respectively')
        self.saved(doc, SERIES_B_LINE)
        with mock.patch.object(retrieval, 'document_chunks', wraps=retrieval.document_chunks) as scoped:
            facts = self.facts(doc, viewer_principal(self.viewer))
        scoped.assert_not_called()
        self.assertIsNone(facts['revenue'])
        self.assertIsNone(facts['raise_amount'])
        self.assertEqual([e['field'] for e in facts['_unavailable_evidence']], ['revenue', 'raise_amount'])
        # positive control: the owner, viewing, has the same figures confirmed
        owner_facts = self.facts(doc, viewer_principal(self.owner))
        self.assertEqual(owner_facts['revenue'], '$14.8')
        self.assertIn('$25 million', owner_facts['raise_amount'])
        self.assertEqual(owner_facts['_unavailable_evidence'], [])

    def test_prompt_leaves_out_an_insight_whose_source_the_principal_may_not_read(self):
        doc = self.doc()
        self.saved(doc, SERIES_B_LINE)
        facts = self.facts(doc, ZeldaIntelligencePipelineV2.owner_task_principal(doc))
        prompts = {}
        for who, principal in (('owner', ZeldaIntelligencePipelineV2.owner_task_principal(doc)),
                               ('viewer', viewer_principal(self.viewer))):
            with mock.patch('anthropic.Anthropic') as anthropic:
                anthropic.return_value.messages.create.return_value = claude_reply()
                ZeldaIntelligencePipelineV2()._call_claude_for_valuation(doc, facts, doc.insights.all(), principal)
                prompts[who] = anthropic.return_value.messages.create.call_args.kwargs['messages'][0]['content']
        self.assertIn('1. [Funding | 95% confidence] $25 million in a Series B', prompts['owner'])  # control
        self.assertNotIn('[Funding | 95% confidence]', prompts['viewer'])

    def test_no_principal_reads_nothing_and_confirms_nothing(self):
        doc = self.doc()
        self.saved(doc, SERIES_B_LINE)
        facts = self.facts(doc, None)
        self.assertIsNone(facts['raise_amount'])
        self.assertEqual(facts['_unavailable_evidence'][0]['label'], 'Raise amount')

    def test_unlinked_insight_needs_no_source_text(self):
        doc = self.doc()
        IntelligenceInsight.objects.create(document=doc, category='Funding', confidence_score=95,
                                           insight_text='Raised $25 million in a Series B')
        facts = self.facts(doc, viewer_principal(self.viewer))
        self.assertIn('$25 million', facts['raise_amount'])
        self.assertEqual(facts['_unavailable_evidence'], [])

    def test_a_chunk_of_another_document_is_not_read(self):
        doc, other = self.doc(), self.doc()
        insight = self.saved(other, SERIES_B_LINE)
        owner = ZeldaIntelligencePipelineV2.owner_task_principal(doc)
        self.assertEqual(ZeldaIntelligencePipelineV2._insight_source_sentence(owner, doc, insight), '')
        self.assertIn('Series B financing',  # positive control
                      ZeldaIntelligencePipelineV2._insight_source_sentence(owner, other, insight))


class NetMarginTests(TestCase):
    """A net margin is reported only as verified same-period net income / net sales, with its source."""

    def setUp(self):
        self.statement = read_income_statement(FIXTURE)

    def test_net_margin_is_computed_from_same_period_statement_figures(self):
        latest = self.statement.net_margins()[0]
        self.assertEqual(latest.name, 'Net margin, FY2026')
        self.assertEqual(round(latest.value, 1), Decimal('27.6'))
        self.assertEqual(latest.value, Decimal(132175) / Decimal(478834) * 100)
        self.assertIn('Net margin, FY2026: 27.6% (computed as Net income $132,175 million / Total net sales '
                      '$478,834 million, both for the fiscal year ended September 26, 2026; PDF page 35)',
                      '\n'.join(self.statement.summary_lines()))

    def test_statement_without_net_income_reports_no_net_margin(self):
        statement = read_income_statement(statement_page(rows='Total revenues $ 12,500 $ 10,000'))
        self.assertEqual(statement.net_margins(), [])
        self.assertNotIn('Net margin', '\n'.join(statement.summary_lines()))

    def test_model_net_margin_is_kept_only_when_verified_and_then_cited(self):
        text = ('1. COMPETITION: Pressure could compress margins at 48.8% gross and 27.6% net. Other risk stays.\n'
                '2. A net margin of 31% leads peers. Second point stays.\n'
                '3. 15% net sales growth stays.')
        governed = govern_net_margin(text, self.statement)
        self.assertIn('27.6% net (verified: Net margin, FY2026 27.6%, computed as Net income $132,175 million / '
                      'Total net sales $478,834 million', governed)
        self.assertIn('PDF page 35).', governed)
        self.assertNotIn('31%', governed)
        for kept in ('Other risk stays.', 'Second point stays.', '15% net sales growth stays.'):
            with self.subTest(kept=kept):
                self.assertIn(kept, governed)

    def test_no_verified_statement_means_no_net_margin(self):
        governed = govern_net_margin('Revenue grew. Net profit margin was 27.6%. Gross margin of 48.8% held.', None)
        self.assertEqual(governed, 'Revenue grew. Gross margin of 48.8% held.')

    def test_saved_report_cites_the_net_margin_and_drops_an_unverified_one(self):
        user = get_user_model().objects.create_user('net_margin_owner', password='x')
        doc = DocumentSource.objects.create(filename='filing.pdf', source_entity='Apple Inc.', uploaded_by=user,
                                            document_type='business_valuation', raw_text_full=FIXTURE)
        reply = claude_reply(risk_report='1. Margins sit at 48.8% gross and 27.6% net. 2. Net margin was 25.0% before.',
                             business_overview='A large company with a 30% net margin. It sells devices.')
        with mock.patch('anthropic.Anthropic') as anthropic:
            anthropic.return_value.messages.create.return_value = reply
            ZeldaIntelligencePipelineV2()._generate_valuation_report(doc, {'confidence': 0.5})
        report = BusinessValuationReport.objects.get(document=doc)
        self.assertIn('27.6% net (verified: Net margin, FY2026 27.6%', report.risk_report)
        self.assertNotIn('25.0%', report.risk_report)
        self.assertEqual(report.business_overview, 'It sells devices.')
        self.assertIn('Net margin, FY2026: 27.6%', report.financial_summary)
        self.assertIsNone(report.valuation_low)
