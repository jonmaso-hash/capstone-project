"""
One accepted document is shared by every Zelda intelligence tab.

Reproduced at b4ba2f1 (local walk, seller, 7 product tabs): after "Use this
document" on one tab, checkout from any other tab already sent the same
document_id, so nothing was lost. But no tab showed the accepted file's name,
and every other tab's upload form looked empty, which read as "upload again".

The behavioural test drives the real panel markup and the real
static/js/zelda_products.js in headless Chrome: upload once, accept it, switch
tabs, and check that every tab shows the same filename and document_id and that
checkout from another tab posts that id. Intake and checkout are answered by a
loopback-only test server, so no Stripe session, order or payment can exist,
and Chrome cannot resolve any host other than 127.0.0.1.

A missing browser is a failure, not a skip: the blocking CI job's runner has
Chrome, and tools/browser_policy_smoke.py already depends on it.
"""
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

User = get_user_model()
ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_JS = ROOT / 'static' / 'js' / 'zelda_products.js'
STATIC_STORAGE = {**settings.STORAGES, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}

# Markup characters in the name: textContent must show them, never parse them.
FIRST_FILE = 'Board pack Q3 <b>bold</b> & notes.txt'
REPLACEMENT_FILE = 'Second deck.txt'
REJECTED_FILE = 'not-a-document.exe'


def find_browser():
    for name in ('google-chrome', 'chromium', 'chromium-browser'):
        path = shutil.which(name)
        if path:
            return path
    for path in (os.environ.get('CHROME_PATH', ''),
                 r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                 r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'):
        if path and Path(path).exists():
            return path
    return None


SCENARIO = r"""
<script>
const wait = ms => new Promise(r => setTimeout(r, ms));
const panels = () => [...document.querySelectorAll('.zelda-product-panel')].filter(p => p.querySelector('.zelda-product-upload'));
function switchTab(key) {   // what the Zelda panel's tab buttons do: show one section
    document.querySelectorAll('.tab-content').forEach(c => { c.style.display = 'none'; });
    document.getElementById('tab-product-' + key).style.display = 'flex';
}
async function until(test, ms = 5000) {
    for (let t = 0; t < ms; t += 50) { if (test()) return true; await wait(50); }
    return false;
}
function choose(panel, name, company) {
    const form = panel.querySelector('.zelda-product-upload');
    form.elements.company.value = company;
    form.elements.company.dispatchEvent(new Event('input', {bubbles: true}));
    const transfer = new DataTransfer();
    transfer.items.add(new File(['Synthetic evidence. Not a real company. Revenue 812,345 USD.'], name, {type: 'text/plain'}));
    form.elements.file.files = transfer.files;
    form.elements.file.dispatchEvent(new Event('change', {bubbles: true}));
    return form;
}
async function submitUpload(panel) {
    const status = panel.querySelector('.zelda-upload-status');
    status.className = 'zelda-upload-status';
    panel.querySelector('.zelda-product-upload button[type="submit"]').click();
    return until(() => /text-(success|danger)/.test(status.className));
}
function tabState(panel) {
    const box = panel.querySelector('.zelda-shared-document');
    const form = panel.querySelector('.zelda-product-upload');
    return {
        product: panel.dataset.product,
        visible: getComputedStyle(panel).display !== 'none',
        summaryShown: Boolean(box) && !box.hidden,
        summaryName: box ? box.querySelector('.zelda-shared-document-name').textContent : null,
        summaryCompany: box ? box.querySelector('.zelda-shared-document-company').textContent : null,
        summaryElements: box ? box.querySelectorAll('.zelda-shared-document-name *').length : null,
        documentId: box ? box.dataset.documentId : null,
        fileInputFiles: form.elements.file.files.length,
        companyInput: form.elements.company.value,
        fileLabel: form.querySelector('label[for^="product-file-"]').textContent.trim(),
        submitLabel: form.querySelector('button[type="submit"]').textContent.trim(),
        checkoutDisabled: panel.querySelector('.zelda-product-checkout').disabled,
    };
}
async function checkout(panel) {
    switchTab(panel.dataset.product);
    const button = panel.querySelector('.zelda-product-checkout');
    if (button.disabled) return 'disabled';
    button.click();
    return until(() => /intercepted/.test(panel.querySelector('.zelda-product-status').textContent));
}
window.addEventListener('load', async () => {
    const result = {};
    try {
        const all = panels();
        const [first, second, third] = all;
        result.products = all.map(p => p.dataset.product);
        result.before = tabState(first);

        switchTab(first.dataset.product);
        choose(first, FIRST_FILE, 'Larkspur Analytics (synthetic)');
        result.firstAccepted = await submitUpload(first);
        result.afterAccept = [];
        for (const panel of all) { switchTab(panel.dataset.product); result.afterAccept.push(tabState(panel)); }
        result.checkoutFromSecond = await checkout(second);
        result.checkoutFromFirst = await checkout(first);

        switchTab(third.dataset.product);
        choose(third, REJECTED_FILE, 'Larkspur Analytics (synthetic)');
        result.rejectedSettled = await submitUpload(third);
        result.afterRejected = all.map(tabState);
        third.querySelector('.zelda-product-upload').elements.file.value = '';
        third.querySelector('.zelda-product-upload').elements.file.dispatchEvent(new Event('change', {bubbles: true}));

        choose(third, REPLACEMENT_FILE, 'Larkspur Analytics (synthetic)');
        result.replacementAccepted = await submitUpload(third);
        result.afterReplacement = all.map(tabState);
        result.checkoutAfterReplacement = await checkout(first);
    } catch (error) {
        result.error = String(error && error.stack || error);
    }
    const out = document.createElement('output');
    out.id = 'scenario-result';
    out.textContent = JSON.stringify(result);
    document.body.appendChild(out);
});
</script>
"""


class _Harness(BaseHTTPRequestHandler):
    page = b''
    intake_path = checkout_path = ''
    intake_bodies = []
    checkout_bodies = []
    next_document_id = [4242]

    def _send(self, status, body, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/':
            return self._send(200, self.page, 'text/html; charset=utf-8')
        if self.path == settings.STATIC_URL.rstrip('/') + '/js/zelda_products.js' or self.path == '/static/js/zelda_products.js':
            return self._send(200, PRODUCTS_JS.read_bytes(), 'text/javascript')
        self._send(404, b'{}')

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        if self.path == self.intake_path:
            message = BytesParser(policy=policy.default).parsebytes(
                b'Content-Type: ' + self.headers['Content-Type'].encode() + b'\r\n\r\n' + body)
            fields = {part.get_param('name', header='content-disposition'): (part.get_filename(), part.get_payload(decode=True))
                      for part in message.iter_parts()}
            filename = fields.get('file', (None, b''))[0] or ''
            company = (fields.get('company', (None, b''))[1] or b'').decode()
            self.intake_bodies.append({'filename': filename, 'company': company})
            if not filename.lower().endswith(('.pdf', '.pptx', '.txt')):   # the real view's rule
                return self._send(400, json.dumps({'error': 'Use a PDF, PPTX or TXT document up to 25 MB.'}).encode())
            document_id = self.next_document_id[0]
            self.next_document_id[0] += 1
            return self._send(201, json.dumps({'document_id': document_id, 'company': company,
                                               'evidence': 'Your uploaded document', 'filename': filename,
                                               'valuation_block_reason': ''}).encode())
        if self.path == self.checkout_path:
            self.checkout_bodies.append(json.loads(body or b'null'))
            return self._send(400, json.dumps({'error': 'Checkout intercepted by the test; nothing was purchased.'}).encode())
        self._send(404, b'{}')

    def log_message(self, *args):
        pass


@override_settings(STORAGES=STATIC_STORAGE)
class SharedDocumentAcrossTabsBrowserTests(TestCase):
    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('shared_doc_tabs', password='x')

    def render_page(self):
        request = RequestFactory().get('/')
        request.user = self.user
        panels = render_to_string('includes/zelda_product_panels.html', {'csp_nonce': ''}, request=request)
        scenario = SCENARIO.replace('FIRST_FILE', json.dumps(FIRST_FILE)).replace(
            'REPLACEMENT_FILE', json.dumps(REPLACEMENT_FILE)).replace('REJECTED_FILE', json.dumps(REJECTED_FILE))
        return ('<!doctype html><html><head><meta charset="utf-8"></head><body>'
                '<p id="zelda-subject-name">No company selected</p><p id="zelda-subject-help">Select a company.</p>'
                + panels + scenario + '</body></html>').encode('utf-8')

    def run_scenario(self):
        browser = find_browser()
        if not browser:
            self.fail('Chrome/Chromium is required for this behavioural test (set CHROME_PATH).')

        class Handler(_Harness):
            page = self.render_page()
            intake_path = reverse('billing:zelda_intake')
            checkout_path = reverse('billing:zelda_checkout')
            intake_bodies, checkout_bodies, next_document_id = [], [], [4242]

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='zelda-shared-doc-') as profile:
                completed = subprocess.run([
                    browser, '--headless', '--no-sandbox', '--disable-gpu', '--no-first-run',
                    '--no-default-browser-check', '--disable-background-networking', '--disable-extensions',
                    '--disable-component-update', '--disable-sync',
                    '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1',
                    f'--user-data-dir={profile}', '--dump-dom', '--virtual-time-budget=20000',
                    f'http://127.0.0.1:{server.server_port}/',
                ], capture_output=True, text=True, encoding='utf-8', timeout=90)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        match = re.search(r'<output id="scenario-result">(.*?)</output>', completed.stdout, re.S)
        self.assertIsNotNone(match, 'scenario did not finish:\n' + completed.stdout[-3000:] + completed.stderr[-1500:])
        result = json.loads(html.unescape(match.group(1)))
        self.assertNotIn('error', result, result.get('error'))
        return result, Handler

    def test_one_upload_is_shown_and_used_by_every_tab(self):
        result, server = self.run_scenario()
        self.assertGreaterEqual(len(result['products']), 3, result['products'])
        self.assertFalse(result['before']['summaryShown'], 'positive control: no summary before any upload')
        self.assertTrue(result['firstAccepted'])
        self.assertEqual(server.intake_bodies[0], {'filename': FIRST_FILE, 'company': 'Larkspur Analytics (synthetic)'})

        expected = f'Selected document: {FIRST_FILE} — used across intelligence tabs.'
        for state in result['afterAccept']:
            with self.subTest(product=state['product']):
                self.assertTrue(state['visible'])
                self.assertTrue(state['summaryShown'])
                self.assertEqual(state['summaryName'], expected)
                self.assertEqual(state['summaryCompany'], 'Company: Larkspur Analytics (synthetic)')
                self.assertEqual(state['summaryElements'], 0, 'the filename is text, never markup')
                self.assertEqual(state['documentId'], '4242')
                # Other inputs are never filled to simulate another upload.
                self.assertEqual(state['fileInputFiles'], 0)
                self.assertEqual(state['submitLabel'], 'Replace selected document')
                self.assertEqual(state['fileLabel'], 'Replace the selected document with another file')

        # Checkout from another tab, then from the uploading tab, sends the accepted id.
        self.assertTrue(result['checkoutFromSecond'])
        self.assertTrue(result['checkoutFromFirst'])
        self.assertEqual([body['document_id'] for body in server.checkout_bodies[:2]], [4242, 4242])

    def test_a_rejected_replacement_keeps_the_accepted_document(self):
        result, server = self.run_scenario()
        self.assertTrue(result['rejectedSettled'])
        self.assertEqual(server.intake_bodies[1]['filename'], REJECTED_FILE)
        for state in result['afterRejected']:
            with self.subTest(product=state['product']):
                self.assertEqual(state['documentId'], '4242')
                self.assertIn(FIRST_FILE, state['summaryName'])
        third = result['afterRejected'][2]
        self.assertTrue(third['checkoutDisabled'], 'the tab holding the rejected file stays gated (existing rule)')

    def test_a_successful_replacement_updates_every_tab(self):
        result, server = self.run_scenario()
        self.assertTrue(result['replacementAccepted'])
        for state in result['afterReplacement']:
            with self.subTest(product=state['product']):
                self.assertEqual(state['documentId'], '4243')
                self.assertEqual(state['summaryName'], f'Selected document: {REPLACEMENT_FILE} — used across intelligence tabs.')
                self.assertEqual(state['fileInputFiles'], 0)
        self.assertTrue(result['checkoutAfterReplacement'])
        self.assertEqual(server.checkout_bodies[-1]['document_id'], 4243)


@override_settings(STRIPE_SECRET_KEY='sk_test_zelda_ci_only')
class IntakeReturnsAcceptedFilenameTests(TestCase):
    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user('intake_filename', password='x')
        self.client.force_login(self.user)

    @mock.patch('zelda_api.utils.extract_text_from_file', return_value=('Readable company evidence and product information. ' * 30, 1))
    def test_upload_response_names_the_stored_file(self, _extract):
        from zelda_api.vector_models import DocumentSource
        response = self.client.post(reverse('billing:zelda_intake'), {
            'company': 'External Co', 'file': SimpleUploadedFile('Board pack Q3.txt', b'readable')})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['filename'], 'Board pack Q3.txt')
        self.assertEqual(DocumentSource.objects.get(pk=data['document_id']).filename, data['filename'])

    def test_registration_snapshot_has_no_filename(self):
        from django.core import signing
        token = signing.dumps({'name': 'Apple Inc.', 'cik': '0000320193'}, salt='zelda-company-selection')
        with mock.patch('zelda_api.sec_identity.company_record', return_value={'name': 'Apple Inc.'}):
            response = self.client.post(reverse('billing:zelda_intake'), {'subject_token': token})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['filename'], '')
