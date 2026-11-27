"""
Uploaded PDFs are parsed by pypdf, not the unmaintained PyPDF2.

Pitch decks and diligence documents are read inside the web request
(zelda_api/pipeline_views.py calls zelda_api.utils.extract_text_from_file).
PyPDF2 3.0.1, its last release, loops forever on a page whose content stream
ends inside a comment (GHSA-4vvm-4w3v-6mr8 / CVE-2023-36464); the fix exists
only in pypdf 3.9.0 and later. Under gunicorn's gthread workers that loop
holds a request thread for good, and the worker keeps checking in, so the
timeout never reclaims it.

The PDF below is built here, byte by byte, so the test needs no sample file.
"""
import re
import threading
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from packaging.version import Version

from zelda_api.utils import ExtractionError, extract_text_from_file

FIXED = Version('3.9.0')
ROOT = Path(__file__).resolve().parents[1]


def _pdf(content):
    """A one-page PDF whose page content stream is exactly `content`."""
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Length %d >>\nstream\n' % len(content) + content + b'\nendstream',
    ]
    out = bytearray(b'%PDF-1.4\n')
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b'%d 0 obj\n' % number + body + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objects) + 1)
    for offset in offsets:
        out += b'%010d 00000 n \n' % offset
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objects) + 1, xref)
    return bytes(out)


def _upload(content):
    return SimpleUploadedFile('deck.pdf', _pdf(content), content_type='application/pdf')


class PdfParserFloorTests(SimpleTestCase):

    def test_requirements_pin_pypdf_at_or_above_the_fixed_release_and_drop_pypdf2(self):
        text = (ROOT / 'requirements.txt').read_text(encoding='utf-8')
        pins = re.findall(r'(?im)^pypdf==([0-9][^\s;#]*)\s*$', text)
        self.assertEqual(len(pins), 1, pins)
        self.assertGreaterEqual(Version(pins[0]), FIXED)
        self.assertIsNone(re.search(r'(?im)^pypdf2\b', text))

    def test_runtime_pypdf_is_at_or_above_the_fixed_release(self):
        import pypdf
        self.assertGreaterEqual(Version(pypdf.__version__), FIXED)

    def test_the_extractor_does_not_import_pypdf2(self):
        source = (ROOT / 'zelda_api' / 'utils.py').read_text(encoding='utf-8')
        self.assertNotRegex(source, r'(?m)^\s*(import PyPDF2|from PyPDF2\b)')


class PdfExtractionTests(SimpleTestCase):

    def test_a_readable_pdf_still_reads(self):
        text, pages = extract_text_from_file(_upload(b'BT /F1 24 Tf 72 700 Td (Revenue grew) Tj ET'))
        self.assertEqual(pages, 1)
        self.assertIn('Revenue grew', text)

    def test_a_content_stream_ending_in_a_comment_finishes(self):
        outcome = {}

        def run():
            try:
                outcome['result'] = extract_text_from_file(
                    _upload(b'BT /F1 24 Tf 72 700 Td (Revenue grew) Tj ET\n% trailing comment'))
            except ExtractionError as error:
                outcome['refused'] = error.reason

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(timeout=15)
        self.assertFalse(worker.is_alive(), 'PDF text extraction did not finish within 15 seconds')
        self.assertTrue(outcome, 'extraction neither returned nor raised ExtractionError')
