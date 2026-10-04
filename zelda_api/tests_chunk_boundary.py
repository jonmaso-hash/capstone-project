"""
Phase 1 Task 4: the repo-wide structural boundary around document text.

Acceptance criterion: any future code path that reaches chunk content outside
the approved boundary fails CI before merge. The allowlist below is the whole
approved boundary; each entry names WHY that function may touch chunks. It is
keyed by (file, function), not line, so moving a read into another function
fails too. A stale entry (nothing found there any more) also fails, so the
list can only describe code that exists.
"""
import inspect
import os

from django.conf import settings
from django.test import SimpleTestCase

from zelda_api import chunk_boundary, intelligence_pipeline, pipeline_views
from zelda_api.chunk_boundary import find_chunk_access, scan

ALLOWLIST = {
    # The boundary itself.
    ('zelda_api/retrieval.py', 'VectorRetriever._candidates'):
        'THE retrieval boundary: chunks filtered by authorize(principal).text_documents().',
    # Ingest: the pipeline processing the document it was asked to process.
    ('zelda_api/intelligence_pipeline.py', 'ZeldaIntelligencePipelineV2._chunk_document'):
        'Ingest: deletes and recreates this document\'s chunks.',
    ('zelda_api/intelligence_pipeline.py', 'ZeldaIntelligencePipelineV2._embed_chunks'):
        'Ingest: embeds this document\'s chunks.',
    ('zelda_api/intelligence_pipeline.py', 'ZeldaIntelligencePipelineV2._analyze_document'):
        'Ingest: extracts insights from this document\'s chunks and links them.',
    ('zelda_api/intelligence_pipeline.py', 'ZeldaIntelligencePipelineV2._extract_insight_with_confidence'):
        'Ingest: links an insight to its source chunks in this document.',
    ('zelda_api/truth_delta_tasks.py', 'extract_claims_from_insights'):
        'Ingest: copies the source chunk into ClaimedDatapoint.text_excerpt. That copy is '
        'document text at rest outside this boundary; nothing reads it today, and any '
        'surface that does must gate it like raw text (Task 5).',
    # Delete paths.
    ('zelda_api/tasks.py', 'process_document_pipeline'):
        'Delete: clears partial chunks when the pipeline fails.',
    ('zelda_api/tasks.py', 'process_valuation_document_task'):
        'Delete: clears partial chunks when valuation processing fails.',
    # Model definition and the staff-only Django admin.
    ('zelda_api/vector_models.py', 'IntelligenceInsight'):
        'Model definition: the source_chunks relation.',
    ('zelda_api/admin_intelligence.py', 'DocumentChunkAdmin'):
        'Staff-only Django admin registration.',
    ('zelda_api/admin_intelligence.py', 'IntelligenceInsightAdmin.source_chunks_display'):
        'Staff-only Django admin display.',
}


def project_root():
    return str(settings.BASE_DIR)


class BoundaryTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.found = scan(project_root())

    def test_every_chunk_access_is_allowlisted(self):
        outside = {key: hits for key, hits in self.found.items() if key not in ALLOWLIST}
        self.assertEqual(
            outside, {},
            'Code reaches document chunk content outside the approved boundary. Read chunks '
            'through zelda_api.retrieval (principal-scoped), or, for a genuine ingest/delete '
            'path, add an ALLOWLIST entry that says why.',
        )

    def test_no_stale_allowlist_entries(self):
        stale = sorted(key for key in ALLOWLIST if key not in self.found)
        self.assertEqual(stale, [], 'Allowlisted functions no longer touch chunks; remove them.')

    def test_every_entry_has_a_reason(self):
        for key, reason in ALLOWLIST.items():
            with self.subTest(key=key):
                self.assertGreater(len(reason.strip()), 20)

    def test_the_scan_sees_the_real_tree(self):
        # Positive control: an empty scan would pass the first test vacuously.
        self.assertIn(('zelda_api/retrieval.py', 'VectorRetriever._candidates'), self.found)
        self.assertGreater(len(self.found), 5)
        files = list(chunk_boundary.first_party_files(project_root()))
        self.assertTrue(any(f.replace('\\', '/').endswith('zelda_api/pipeline_views.py') for f in files))
        self.assertFalse(any(os.path.basename(f).startswith('tests') for f in files))


def _hits(source):
    return [what for _, _, what in find_chunk_access(source)]


class DetectorMutationTests(SimpleTestCase):
    """Each way of reaching chunk text is seen; counting and metadata are not."""

    def assertFlagged(self, source):
        self.assertTrue(_hits(source), f'not flagged:\n{source}')

    def assertClean(self, source):
        self.assertEqual(_hits(source), [], f'wrongly flagged:\n{source}')

    def test_reads_are_flagged(self):
        for source in (
            'def f(d):\n    return DocumentChunk.objects.filter(document=d)',
            'def f():\n    return DocumentChunk._default_manager.all()',
            'def f(d):\n    return list(d.chunks.all())',
            'def f(d):\n    return d.chunks.values_list("raw_text", flat=True)',
            'def f(d):\n    return d.chunks.values_list("page_number", "raw_text")',
            'def f(d):\n    return d.chunks.first().raw_text',
            'def f(i):\n    return i.source_chunks.all()',
            'def f(d):\n    return d.chunks.values_list("page_number", flat=True).first()',
            'def f():\n    return DocumentSource.objects.filter(chunks__raw_text__icontains="x")',
            'def f():\n    return Insight.objects.values("source_chunks__raw_text")',
            'def f():\n    from django.apps import apps\n    return apps.get_model("zelda_api", "DocumentChunk")',
            'def f():\n    return apps.get_model("zelda_api.DocumentChunk")',
            'def f(c):\n    c.execute("SELECT raw_text FROM zelda_api_documentchunk")',
            'M = DocumentChunk\ndef f():\n    return M.objects.all()',
            'def f():\n    return getattr(DocumentChunk, "objects").all()',
            'from .vector_models import DocumentChunk as Chunk\ndef f():\n    return Chunk.objects.all()',
        ):
            with self.subTest(source=source):
                self.assertFlagged(source)

    def test_counts_and_metadata_are_clean(self):
        for source in (
            'def f(d):\n    return d.chunks.count()',
            'def f(d):\n    return d.chunks.filter(embedding_vector__isnull=False).count()',
            'def f(d):\n    return d.chunks.exists()',
            'def f(i):\n    return i.source_chunks.count()',
            'def f(i):\n    return list(i.source_chunks.values_list("page_number", flat=True))',
            'def f(i):\n    return list(i.source_chunks.values_list("chunk_index", flat=True))',
            'from .vector_models import DocumentChunk\n',
            'def f():\n    raise DocumentChunk.DoesNotExist',
        ):
            with self.subTest(source=source):
                self.assertClean(source)

    def test_findings_are_attributed_to_the_enclosing_function(self):
        source = 'class A:\n    def b(self):\n        return DocumentChunk.objects.all()\n'
        self.assertEqual([q for q, _, _ in find_chunk_access(source)], ['A.b'])


class RealModuleMutationTests(SimpleTestCase):
    """Injecting a direct read into real code puts it outside the allowlist."""

    def _outside(self, module, needle, injected):
        source = inspect.getsource(module)
        self.assertIn(needle, source, 'mutation did not apply')
        mutated = source.replace(needle, injected + needle, 1)
        rel = os.path.relpath(inspect.getsourcefile(module), project_root()).replace('\\', '/')
        return [(rel, q) for q, _, _ in find_chunk_access(mutated) if (rel, q) not in ALLOWLIST]

    def test_direct_read_in_a_view_fails(self):
        outside = self._outside(
            pipeline_views,
            "            query = _query_from(request)\n",
            "            leaked = list(DocumentChunk.objects.filter(document=doc))\n",
        )
        self.assertIn(('zelda_api/pipeline_views.py', 'DocumentSearchView.post'), outside)

    def test_related_manager_read_in_a_view_fails(self):
        outside = self._outside(
            pipeline_views,
            "            query = _query_from(request)\n",
            "            leaked = [c.raw_text for c in doc.chunks.all()]\n",
        )
        self.assertIn(('zelda_api/pipeline_views.py', 'DocumentSearchView.post'), outside)

    def test_new_pipeline_reader_fails_even_in_an_allowlisted_module(self):
        outside = self._outside(
            intelligence_pipeline,
            "    def _embed_chunks(",
            "    def _memo_context(self, document_source):\n"
            "        return [c.raw_text for c in DocumentChunk.objects.filter(document=document_source)]\n\n",
        )
        self.assertIn(('zelda_api/intelligence_pipeline.py', 'ZeldaIntelligencePipelineV2._memo_context'), outside)
