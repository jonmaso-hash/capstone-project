"""
A memo that cannot be saved is a pipeline that cannot finish.

Migration 0024 renamed five memo fields (key_strengths -> supported_points,
key_concerns -> open_concerns, bull_case -> upside_scenario, base_case ->
base_scenario, bear_case -> downside_scenario) and the prompt was updated to
ask Claude for the new names. The writer in intelligence_pipeline._generate_memo
was not: it read the old keys out of Claude's response and wrote them to the
old field names.

Both halves were wrong, and either alone would have been a defect. The field
names no longer existed, so `update_or_create` raised "Invalid field name(s)",
_generate_memo returned {'error': ...}, process_document marked the document
`status='error'`, and the pipeline stopped before claim extraction -- so no
Truth Delta report could be produced either. Uploading any document produced
an errored document and no memo. And even had the field names been right, the
writer read keys Claude never returns, so those five sections would have been
saved blank.

Found by running a real deck through the real upload path, not by a test: the
suite covering this lives in zelda_api.tests, which CI runs only in its
non-blocking job. These tests are in the blocking job.

The structural test is the one that matters for next time. It reads the
writer's own field list and compares it against the model, so a future rename
that misses this call site fails immediately and offline, without Claude,
without a network, and without anyone thinking to upload a deck.
"""
import ast
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase

from .intelligence_pipeline import MEMO_JSON_KEYS, ZeldaIntelligencePipelineV2
from .vector_models import DocumentSource, IntelligenceMemo

PIPELINE_SOURCE = Path(settings.BASE_DIR) / 'zelda_api' / 'intelligence_pipeline.py'

# evidence_level is assigned after update_or_create, not inside its defaults.
SECTIONS_IN_DEFAULTS = tuple(k for k in MEMO_JSON_KEYS if k != 'evidence_level')

# What a response looked like before migration 0024 renamed the sections.
LEGACY_KEYS = {
    'investment_thesis': 'business_model_analysis',
    'key_strengths': 'supported_points',
    'key_concerns': 'open_concerns',
    'what_would_change_decision': 'what_would_change_the_picture',
    'bull_case': 'upside_scenario',
    'base_case': 'base_scenario',
    'bear_case': 'downside_scenario',
    'investment_readiness': 'information_readiness',
}


def _memo_defaults_keys():
    """The field names _generate_memo actually writes, read from the source."""
    tree = ast.parse(PIPELINE_SOURCE.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == 'update_or_create'):
            continue
        for keyword in node.keywords:
            if keyword.arg == 'defaults' and isinstance(keyword.value, ast.Dict):
                return [k.value for k in keyword.value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    return []


class MemoWriterMatchesTheModelTests(TestCase):
    """Offline, no Claude: the call site and the model cannot drift apart."""

    def test_every_field_the_writer_sets_exists_on_the_model(self):
        model_fields = {f.name for f in IntelligenceMemo._meta.get_fields()}
        unknown = sorted(set(_memo_defaults_keys()) - model_fields)
        self.assertEqual(
            unknown, [],
            'intelligence_pipeline._generate_memo writes field names that '
            'IntelligenceMemo does not have, so every memo save raises: ' + ', '.join(unknown),
        )

    def test_every_declared_section_reaches_a_field(self):
        """MEMO_JSON_KEYS is the contract; a section Claude returns must be stored."""
        written = set(_memo_defaults_keys())
        missing = sorted(set(SECTIONS_IN_DEFAULTS) - written)
        self.assertEqual(missing, [], 'declared memo sections never persisted: ' + ', '.join(missing))

    def test_the_scanner_found_the_call_site(self):
        """Positive control: an empty list would pass both tests above."""
        self.assertGreater(len(_memo_defaults_keys()), 10)


class MemoPersistsThroughTheRealWriterTests(TestCase):
    """_generate_memo with Claude stubbed: no network, no API spend."""

    def setUp(self):
        self.user = User.objects.create_user('memo_owner', password='x')
        self.doc = DocumentSource.objects.create(
            filename='deck.txt', source_entity='Northwind Grid Systems, Inc.',
            uploaded_by=self.user, document_type='pitch_deck',
            raw_text_full='Revenue of $4.2 million. 41 customers.',
        )

    def generate(self, sections):
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=sections), \
             mock.patch.object(pipeline, '_build_structured_context', return_value=''):
            from zelda_api.tests import grounded_context_for
            return pipeline._generate_memo(grounded_context_for(self.doc))

    def test_a_memo_is_saved_from_the_sections_claude_is_asked_for(self):
        sections = {key: f'{key} text' for key in MEMO_JSON_KEYS}
        sections['evidence_level'] = 'PARTLY_EVIDENCED'

        result = self.generate(sections)

        self.assertNotIn('error', result, result.get('error'))
        memo = IntelligenceMemo.objects.get(document=self.doc)
        for key in SECTIONS_IN_DEFAULTS:
            self.assertEqual(getattr(memo, key), f'{key} text', key)
        self.assertEqual(memo.evidence_level, 'PARTLY_EVIDENCED')

    def test_an_older_response_shape_still_reaches_the_renamed_fields(self):
        """A response using the pre-0024 key names must not save blank sections."""
        sections = {key: f'{key} text' for key in MEMO_JSON_KEYS if key not in LEGACY_KEYS.values()}
        for legacy in LEGACY_KEYS:
            sections[legacy] = f'{legacy} text'

        result = self.generate(sections)

        self.assertNotIn('error', result, result.get('error'))
        memo = IntelligenceMemo.objects.get(document=self.doc)
        for legacy, field in LEGACY_KEYS.items():
            self.assertEqual(getattr(memo, field), f'{legacy} text', f'{legacy} -> {field}')

    def test_a_claude_error_is_still_reported_rather_than_saved(self):
        """Control: the failure path must not be papered over by the fix."""
        result = self.generate({'error': 'Claude unavailable'})
        self.assertIn('error', result)
        self.assertFalse(IntelligenceMemo.objects.filter(document=self.doc).exists())

    def test_list_sections_survive_the_writer_and_automatic_archive(self):
        """R-001: a billed response must survive the post_save archive signal."""
        from django.db import models
        from matchmaking.models import Application, DataRoomReportLink
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        founder = Application.objects.create(
            user=self.user, company_name=self.doc.source_entity, founder_name='F',
            email='memo@test.invalid', description='test', sector='SaaS', stage='Seed',
        )
        sections = {key: f'{key} text' for key in MEMO_JSON_KEYS}
        sections['evidence_level'] = 'PARTLY_EVIDENCED'
        sections['questions_for_management'] = ['What is retention? [1]', 'Who owns café IP? [2]']
        sections['supported_points'] = ['A cited point [1]']
        sections['open_concerns'] = {'gap': 'Revenue period not disclosed [2]'}

        result = self.generate(sections)

        self.assertNotIn('error', result, result.get('error'))
        memo = IntelligenceMemo.objects.get(document=self.doc)
        self.assertEqual(memo.questions_for_management, str(sections['questions_for_management']))
        self.assertEqual(memo.supported_points, str(sections['supported_points']))
        self.assertEqual(memo.open_concerns, str(sections['open_concerns']))
        link = DataRoomReportLink.objects.get(founder=founder, report_key='memo')
        expected = sum(len(getattr(memo, field.name).encode('utf-8'))
                       for field in memo._meta.fields if isinstance(field, models.TextField))
        self.assertEqual(link.size_bytes, expected)
        self.assertNotIn('error', self.generate(sections))
        self.assertEqual(DataRoomReportLink.objects.filter(founder=founder, report_key='memo').count(), 1)

    def test_list_section_memo_task_reaches_analyzed(self):
        from .tasks import generate_intelligence_memo, intelligence_pipeline
        with mock.patch.object(intelligence_pipeline, '_call_claude_for_memo', return_value={
            'executive_summary': 'A supported summary [1]',
            'questions_for_management': ['What remains unknown? [1]'],
        }), mock.patch('zelda_api.tasks.notify_document_processed.delay') as notify:
            result = generate_intelligence_memo(self.doc.pk)
        self.assertEqual(result['status'], 'success', result)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, 'analyzed')
        self.assertTrue(IntelligenceMemo.objects.filter(document=self.doc).exists())
        notify.assert_called_once_with(self.doc.pk)

    def test_archive_failure_does_not_roll_back_generated_memo(self):
        with mock.patch('matchmaking.data_room_quota.try_save_report', side_effect=RuntimeError('archive unavailable')), \
             self.assertLogs('zelda_api.signals', level='ERROR'):
            result = self.generate({'executive_summary': 'Supported summary [1]'})
        self.assertNotIn('error', result)
        self.assertEqual(IntelligenceMemo.objects.get(document=self.doc).executive_summary, 'Supported summary [1]')

    def test_failed_status_keeps_internal_exception_out_of_the_response(self):
        self.doc.status = 'error'
        self.doc.error_message = "Memo error: 'list' object has no attribute 'encode'"
        self.doc.save(update_fields=['status', 'error_message'])
        self.client.force_login(self.user)
        response = self.client.get(f'/api/v1/zelda/documents/{self.doc.pk}/status/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'error')
        self.assertIn("couldn't complete", response.json()['error'])
        self.assertNotIn('encode', response.content.decode())
        self.doc.refresh_from_db()
        self.assertIn('encode', self.doc.error_message)
