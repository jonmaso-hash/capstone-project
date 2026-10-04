"""
Phase 1 Task 5: GroundedContext. Bypass and contract tests that ship with it.

The five non-negotiables, each tested here:
1. No raw-document input to memo generation.
2. Claims keep provenance.
3. Verification state reaches generation (a contradiction arrives AS one).
4. Authorization happens before context construction.
5. ClaimedDatapoint.text_excerpt is not document text.
Plus the profile audience rule and the verify-then-write orchestration.
"""
import ast
import importlib
import inspect
import json
from unittest import mock

from django.apps import apps as django_apps
from django.utils import timezone

from matchmaking.models import FIELD_PUBLIC
from zelda_api import grounded_context as gc_module
from zelda_api import intelligence_pipeline as pipeline_module
from zelda_api.chunk_boundary import find_chunk_access
from zelda_api.grounded_context import (
    CONTRADICTED, INSUFFICIENT, SELF_REPORTED, VERIFIED, GroundedContext, GroundedItem, SourceRef,
)
from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
from zelda_api.principal import ORIGIN_TASK, Principal, PrincipalRequired
from zelda_api.retrieval import RetrievalRefused
from zelda_api.tests_authorization import CANARY, AuthorizationFixture
from zelda_api.truth_delta_models import ClaimedDatapoint, TruthDeltaReport
from zelda_api.vector_models import DocumentChunk, DocumentSource, IntelligenceInsight, IntelligenceMemo

SECRET = 'UNEXTRACTED-CHUNK-SENTENCE-4410'


def _row(category, claimed, observed, *, claim_period='FY2026', source='SEC EDGAR'):
    return {
        'category': category, 'claimed_value': str(claimed), 'claimed_value_numeric': claimed,
        'observed_value': None if observed is None else str(observed), 'observed_value_numeric': observed,
        'observed_source': source if observed is not None else None, 'observed_registrant': '0000320187',
        'observed_time_period': 'FY2026 10-K (period ending 2026-05-31)' if observed is not None else None,
        'discrepancy_pct': None, 'claim_raw_text': f'{category} claim', 'claim_period': claim_period,
    }


class _Grounded(AuthorizationFixture):

    def setUp(self):
        super().setUp()
        self.doc = self.docs['a']
        chunk = DocumentChunk.objects.get(document=self.doc)
        chunk.raw_text = f'Revenue was $52.8B. {SECRET}. Employees: 81,500.'
        chunk.page_number, chunk.chunk_index = 4, 0
        chunk.save()
        self.revenue_insight = IntelligenceInsight.objects.create(
            document=self.doc, insight_type='statement', category='Revenue',
            insight_text='Revenue was $52.8B.', confidence_score=95.0)
        self.revenue_insight.source_chunks.set([chunk])
        self.team_insight = IntelligenceInsight.objects.create(
            document=self.doc, insight_type='statement', category='Team',
            insight_text='Employees: 81,500.', confidence_score=90.0)
        self.team_insight.source_chunks.set([chunk])
        self.claims = {
            category: ClaimedDatapoint.objects.create(
                document=self.doc, category=category, claimed_value=text, claimed_value_numeric=value,
                page_number=4, chunk_hash='abc123', confidence_in_extraction=90.0, text_excerpt=text)
            for category, text, value in (('revenue', 'Revenue was $52.8B.', 52.8e9),
                                          ('employees', 'Employees: 81,500.', 81500.0),
                                          ('funding_raised', 'Raised $10M.', 1e7),
                                          ('customers', '400 customers.', 400.0))
        }
        TruthDeltaReport.objects.filter(document=self.doc).delete()
        self.report = TruthDeltaReport.objects.create(
            document=self.doc, overall_truth_score=40.0, credibility_risk='high', summary='prose',
            details={
                'claims': [], 'per_claim': [],
                'observed': [{'category': 'revenue'}, {'category': 'employees'}],
                'comparison': [
                    _row('revenue', 52.8e9, 46.398e9),            # diverges, period comparable -> contradicted
                    _row('employees', 81500.0, 80000.0),          # within 20% -> verified
                    _row('funding_raised', 1e7, None),            # nothing fetched -> no_data
                ],
            })
        self.owner = self.principals['owner_a']

    def build(self, principal=None):
        return GroundedContext.build(principal or self.owner, self.doc)

    def item(self, context, kind, category):
        return next(i for i in context.items if i.kind == kind and i.category == category)


# -- 4. authorization before construction ----------------------------------------

class AuthorizationTests(_Grounded):

    def test_no_principal_refuses(self):
        for value in (None, self.users['a'], {'user_id': self.users['a'].pk}):
            with self.subTest(value=value), self.assertRaises(PrincipalRequired):
                GroundedContext.build(value, self.doc)

    def test_principal_without_text_access_refuses(self):
        for name in ('investor', 'connected', 'roleless', 'staff_as_investor', 'owner_x'):
            with self.subTest(principal=name), self.assertRaises(RetrievalRefused):
                self.build(self.principals[name])

    def test_owner_and_staff_build(self):
        self.assertEqual(self.build().document_id, self.doc.id)
        self.assertEqual(self.build(self.principals['staff']).document_id, self.doc.id)


# -- 3. verification state reaches generation -------------------------------------

class VerificationStateTests(_Grounded):

    def test_contradiction_arrives_as_a_contradiction(self):
        revenue = self.item(self.build(), 'claim', 'revenue')
        self.assertEqual(revenue.status, CONTRADICTED)
        self.assertEqual(len(revenue.external), 1)
        self.assertEqual(revenue.external[0].value, 46.398e9)
        self.assertEqual(revenue.external[0].source, 'SEC EDGAR')
        self.assertIn('FY2026', revenue.external[0].period)

    def test_states_are_truth_deltas_not_recomputed(self):
        context = self.build()
        canonical = self.report.category_states()
        mapping = {'verified': VERIFIED, 'contradicted': CONTRADICTED, 'no_data': INSUFFICIENT}
        for category in ('revenue', 'employees', 'funding_raised'):
            with self.subTest(category=category):
                self.assertEqual(self.item(context, 'claim', category).status, mapping[canonical[category]])

    def test_insufficient_carries_its_reason(self):
        funding = self.item(self.build(), 'claim', 'funding_raised')
        self.assertEqual(funding.status, INSUFFICIENT)
        self.assertEqual(funding.reason, self.report.grounding_reasons()['funding_raised'])

    def test_unchecked_category_is_self_reported(self):
        customers = self.item(self.build(), 'claim', 'customers')
        self.assertEqual((customers.status, customers.reason), (SELF_REPORTED, 'not_checked'))

    def test_nike_shape_period_unknown_keeps_the_external_value(self):
        details = dict(self.report.details)
        details['comparison'] = [_row('revenue', 52.8e9, 46.398e9, claim_period=None)]
        self.report.details = details
        self.report.save()
        revenue = self.item(self.build(), 'claim', 'revenue')
        self.assertEqual((revenue.status, revenue.reason), (INSUFFICIENT, 'period_unknown'))
        self.assertEqual(revenue.external[0].value, 46.398e9)

    def test_no_report_means_insufficient_not_supported(self):
        self.report.delete()
        context = self.build()
        self.assertEqual(context.verification, 'not_run')
        self.assertEqual(self.item(context, 'claim', 'revenue').reason, 'verification_not_run')
        DocumentSource.objects.filter(pk=self.doc.pk).update(verification_failed_at=timezone.now())
        self.doc.refresh_from_db()
        context = self.build()
        self.assertEqual(context.verification, 'failed')
        revenue = self.item(context, 'claim', 'revenue')
        self.assertEqual((revenue.status, revenue.reason), (INSUFFICIENT, 'verification_failed'))

    def test_the_prompt_receives_the_contradiction(self):
        payload = self.build().to_prompt_payload()
        revenue = next(i for i in payload['items'] if i['kind'] == 'claim' and i['category'] == 'revenue')
        self.assertEqual(revenue['status'], CONTRADICTED)
        self.assertEqual(revenue['external'][0]['source'], 'SEC EDGAR')
        self.assertEqual(revenue['external'][0]['value'], 46.398e9)


# -- 2. provenance ------------------------------------------------------------------

class ProvenanceTests(_Grounded):

    def test_every_item_has_a_source(self):
        for item in self.build().items:
            with self.subTest(ref=item.ref):
                self.assertTrue(item.sources)

    def test_statements_point_at_page_and_chunk(self):
        statement = self.item(self.build(), 'statement', 'Revenue')
        self.assertEqual(statement.insight_id, self.revenue_insight.id)
        self.assertEqual([(s.document_id, s.page_number, s.chunk_index) for s in statement.sources],
                         [(self.doc.id, 4, 0)])

    def test_claims_point_at_page_and_hash(self):
        revenue = self.item(self.build(), 'claim', 'revenue')
        self.assertEqual(revenue.claim_id, self.claims['revenue'].id)
        self.assertEqual((revenue.sources[0].page_number, revenue.sources[0].chunk_hash), (4, 'abc123'))

    def test_an_item_without_provenance_cannot_exist(self):
        with self.assertRaises(ValueError):
            GroundedItem(ref='X', kind='statement', category='c', statement='s', status=SELF_REPORTED, sources=())
        with self.assertRaises(ValueError):
            SourceRef(document_id=None)

    def test_unknown_status_cannot_exist(self):
        with self.assertRaises(ValueError):
            GroundedItem(ref='X', kind='claim', category='c', statement='s', status='SUPPORTED',
                         sources=(SourceRef(document_id=1),))


# -- profile audience ------------------------------------------------------------------

class ProfileAudienceTests(_Grounded):

    def profile_fields(self, context):
        return {s.profile_field for i in context.items if i.kind == 'profile' for s in i.sources}

    def test_only_public_fields_enter(self):
        context = self.build()
        fields = self.profile_fields(context)
        self.assertIn('stage', fields)
        self.assertNotIn('current_revenue', fields)          # CONNECTED by default
        self.assertNotIn(CANARY, json.dumps(context.to_prompt_payload()))

    def test_a_field_made_public_enters(self):
        app = self.apps['a']
        app.field_visibility = {**app.field_visibility, 'current_revenue': FIELD_PUBLIC}
        app.save()
        self.assertIn('current_revenue', self.profile_fields(self.build()))


# -- 1. no raw-document input ----------------------------------------------------------------

def _fake_response(sections=None):
    response = mock.Mock()
    response.content = [mock.Mock(text=json.dumps(sections or {'executive_summary': 'Grounded.'}))]
    response.usage = mock.Mock(input_tokens=1, output_tokens=1)
    return response


class NoRawInputTests(_Grounded):

    def generate(self):
        with mock.patch('anthropic.Anthropic') as client_cls:
            client_cls.return_value.messages.create.return_value = _fake_response()
            result = ZeldaIntelligencePipelineV2()._generate_memo(self.build())
            prompt = client_cls.return_value.messages.create.call_args.kwargs['messages'][0]['content']
        return result, prompt

    def test_generate_memo_takes_only_a_grounded_context(self):
        for value in (self.doc, {'confidence': 0.5}, None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                ZeldaIntelligencePipelineV2()._generate_memo(value)

    def test_chunk_text_outside_extracted_statements_never_reaches_the_prompt(self):
        DocumentSource.objects.filter(pk=self.doc.pk).update(raw_text_full=f'full text {SECRET}')
        result, prompt = self.generate()
        self.assertNotIn('error', result)
        self.assertNotIn(SECRET, prompt)
        self.assertNotIn(CANARY, prompt)
        self.assertIn('CONTRADICTED', prompt)

    def test_memo_records_context_citations(self):
        result, _ = self.generate()
        memo = IntelligenceMemo.objects.get(pk=result['memo_id'])
        self.assertEqual(set(memo.insights_used.values_list('id', flat=True)),
                         {self.revenue_insight.id, self.team_insight.id})


RAW_NAMES = {'raw_text', 'raw_text_full', 'raw_text_preview', 'text_excerpt'}


def raw_reads(source):
    """Attribute reads of document text, plus any chunk access the boundary scanner sees."""
    found = [node.attr for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.Attribute) and node.attr in RAW_NAMES]
    found += [what for _, _, what in find_chunk_access(source)]
    return found


def _strip(source):
    lines = source.splitlines()
    indent = len(lines[0]) - len(lines[0].lstrip())
    return '\n'.join(line[indent:] for line in lines)


class StructuralTests(_Grounded):

    def test_generator_and_context_read_no_document_text(self):
        for name, source in (
            ('_generate_memo', _strip(inspect.getsource(ZeldaIntelligencePipelineV2._generate_memo))),
            ('_call_claude_for_memo', _strip(inspect.getsource(ZeldaIntelligencePipelineV2._call_claude_for_memo))),
            ('grounded_context', inspect.getsource(gc_module)),
        ):
            with self.subTest(source=name):
                self.assertEqual(raw_reads(source), [])

    def test_the_scan_can_fail(self):
        source = _strip(inspect.getsource(ZeldaIntelligencePipelineV2._generate_memo))
        needle = '            memo_sections = self._call_claude_for_memo(context)\n'
        self.assertIn(needle.strip(), source)
        for injected in ('doc = DocumentSource.objects.get(id=context.document_id); text = doc.raw_text_full',
                         'chunks = list(DocumentChunk.objects.filter(document_id=context.document_id))',
                         'excerpts = [c.text_excerpt for c in claims]'):
            with self.subTest(injected=injected):
                mutated = source.replace(needle.strip(), injected + '\n        ' + needle.strip(), 1)
                self.assertTrue(raw_reads(mutated))

    def test_state_mapping_is_exact(self):
        self.assertEqual(gc_module._CANONICAL_TO_STATE,
                         {'verified': VERIFIED, 'contradicted': CONTRADICTED, 'no_data': INSUFFICIENT})


# -- 5. text_excerpt is not document text -----------------------------------------------------

class ExcerptTests(_Grounded):

    def test_new_claims_store_the_sentence_not_the_chunk(self):
        ClaimedDatapoint.objects.filter(document=self.doc).delete()
        from zelda_api import truth_delta_tasks
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay'):
            truth_delta_tasks.extract_claims_from_insights(self.doc.id)
        excerpts = list(ClaimedDatapoint.objects.filter(document=self.doc).values_list('text_excerpt', flat=True))
        self.assertTrue(excerpts)
        for excerpt in excerpts:
            self.assertNotIn(SECRET, excerpt)
            self.assertLessEqual(len(excerpt), 300)

    def test_migration_bounds_existing_rows(self):
        claim = self.claims['revenue']
        ClaimedDatapoint.objects.filter(pk=claim.pk).update(text_excerpt=f'whole chunk {SECRET} ' * 50)
        migration = importlib.import_module('zelda_api.migrations.0030_bound_claimed_text_excerpt')
        migration.bound_existing_excerpts(django_apps, None)
        claim.refresh_from_db()
        self.assertEqual(claim.text_excerpt, 'Revenue was $52.8B.')

    def test_nothing_reads_text_excerpt(self):
        from django.conf import settings
        from zelda_api.chunk_boundary import first_party_files
        readers = []
        for path in first_party_files(str(settings.BASE_DIR)):
            with open(path, encoding='utf8') as handle:
                tree = ast.parse(handle.read())
            readers += [f'{path}:{n.lineno}' for n in ast.walk(tree)
                        if isinstance(n, ast.Attribute) and n.attr == 'text_excerpt'
                        and isinstance(n.ctx, ast.Load)]
        self.assertEqual(readers, [], 'text_excerpt is read somewhere; gate it as document text first.')


# -- orchestration: verify, then write ----------------------------------------------------------

class OrchestrationTests(_Grounded):

    def test_every_terminal_verification_path_queues_the_memo(self):
        from zelda_api import truth_delta_tasks
        cases = {
            'success': mock.Mock(return_value=self.report),
            'no_claims': mock.Mock(return_value=None),
            'failure': mock.Mock(side_effect=RuntimeError('EDGAR down')),
        }
        for name, verify in cases.items():
            with self.subTest(path=name), \
                    mock.patch('zelda_api.tasks.generate_intelligence_memo.delay') as queue, \
                    mock.patch.object(truth_delta_tasks.TruthDeltaEngine, 'verify_document', verify):
                try:
                    truth_delta_tasks.verify_document_truth_delta(self.doc.id)
                except RuntimeError:
                    pass
                queue.assert_called_once_with(self.doc.id)

    def test_claim_extraction_failure_queues_the_memo(self):
        from zelda_api import truth_delta_tasks
        with mock.patch('zelda_api.tasks.generate_intelligence_memo.delay') as queue, \
                mock.patch.object(IntelligenceInsight.objects, 'filter', side_effect=RuntimeError('boom')):
            truth_delta_tasks.extract_claims_from_insights(self.doc.id)
        queue.assert_called_once_with(self.doc.id)

    def test_valuation_documents_get_no_memo(self):
        from zelda_api import truth_delta_tasks
        DocumentSource.objects.filter(pk=self.doc.pk).update(document_type='business_valuation')
        with mock.patch('zelda_api.tasks.generate_intelligence_memo.delay') as queue:
            truth_delta_tasks.verification_finished(self.doc.id)
        queue.assert_not_called()

    def test_unqueueable_verification_still_ends_in_a_memo(self):
        with mock.patch('zelda_api.truth_delta_tasks.extract_claims_from_insights.delay', side_effect=RuntimeError('no broker')), \
                mock.patch('zelda_api.entity_verification_tasks.verify_entity_integrity.delay'), \
                mock.patch('zelda_api.tasks.generate_intelligence_memo.delay') as queue:
            ZeldaIntelligencePipelineV2()._trigger_verification(self.doc)
        queue.assert_called_once_with(self.doc.id)
        self.doc.refresh_from_db()
        self.assertIsNotNone(self.doc.verification_failed_at)

    def test_process_document_writes_no_memo_and_waits_for_verification(self):
        IntelligenceMemo.objects.filter(document=self.doc).delete()
        with mock.patch.object(ZeldaIntelligencePipelineV2, '_trigger_verification') as trigger, \
                mock.patch('anthropic.Anthropic') as client_cls:
            result = ZeldaIntelligencePipelineV2().process_document(
                self.doc, 'Acme revenue was $4M in 2025. The team has 12 engineers. ' * 20)
        self.assertEqual(result['status'], 'success', result)
        trigger.assert_called_once()
        client_cls.return_value.messages.create.assert_not_called()
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, 'verifying')
        self.assertFalse(IntelligenceMemo.objects.filter(document=self.doc).exists())

    def test_memo_stage_writes_from_the_context_and_notifies(self):
        from zelda_api.tasks import generate_intelligence_memo
        with mock.patch('anthropic.Anthropic') as client_cls, \
                mock.patch('zelda_api.tasks.notify_document_processed.delay') as notify:
            client_cls.return_value.messages.create.return_value = _fake_response()
            result = generate_intelligence_memo(self.doc.id)
            prompt = client_cls.return_value.messages.create.call_args.kwargs['messages'][0]['content']
        self.assertEqual(result['status'], 'success', result)
        self.assertIn('CONTRADICTED', prompt)
        notify.assert_called_once_with(self.doc.id)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, 'analyzed')

    def test_failed_regeneration_keeps_the_previous_memo(self):
        from zelda_api.tasks import generate_intelligence_memo
        IntelligenceMemo.objects.filter(document=self.doc).delete()
        IntelligenceMemo.objects.create(document=self.doc, executive_summary='Earlier memo.')
        DocumentSource.objects.filter(pk=self.doc.pk).update(status='analyzed')
        with mock.patch('anthropic.Anthropic') as client_cls:
            client_cls.return_value.messages.create.side_effect = Exception('API down')
            result = generate_intelligence_memo(self.doc.id)
        self.assertTrue(result.get('kept_previous_memo'))
        self.assertEqual(IntelligenceMemo.objects.get(document=self.doc).executive_summary, 'Earlier memo.')
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, 'analyzed')

    def test_deactivated_owner_refuses_rather_than_writing(self):
        from zelda_api.tasks import generate_intelligence_memo
        IntelligenceMemo.objects.filter(document=self.doc).delete()
        self.users['a'].is_active = False
        self.users['a'].save()
        with mock.patch('anthropic.Anthropic') as client_cls:
            result = generate_intelligence_memo(self.doc.id)
        self.assertEqual(result['status'], 'error')
        client_cls.return_value.messages.create.assert_not_called()
