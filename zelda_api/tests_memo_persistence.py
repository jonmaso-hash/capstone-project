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
            return pipeline._generate_memo(self.doc, {'confidence': 0.8})

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
