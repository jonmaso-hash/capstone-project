"""Batch 34: enforce browser policies without breaking existing integrations."""
import re
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.middleware.csp import ContentSecurityPolicyMiddleware
from django.middleware.security import SecurityMiddleware
from django.template import Engine, RequestContext
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from whitenoise.middleware import WhiteNoiseMiddleware

from config.browser_policy import policies
from shared_utils.browser_policy import BrowserPolicyMiddleware
from shared_utils.middleware import IdempotencyMiddleware
from shared_utils.upload_limits import UploadSizeLimitMiddleware


def _stack(view):
    return ContentSecurityPolicyMiddleware(BrowserPolicyMiddleware(SecurityMiddleware(view)))


def _nonce(response):
    return re.search(r"'nonce-([^']+)'", response['Content-Security-Policy'])[1]


def _html(request):
    engine = Engine(context_processors=['django.template.context_processors.csp'])
    template = engine.from_string(
        '<script nonce="{{ csp_nonce }}">window.trusted = true;</script>'
        '<p>{{ user_text }}</p><script>window.untrusted = true;</script>')
    return HttpResponse(template.render(RequestContext(request, {
        'user_text': '<script>window.injected = true;</script>',
    })))


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.scripts.append(dict(attrs))


class BrowserPolicyTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def assertPolicies(self, response):
        self.assertIn('Content-Security-Policy', response)
        self.assertIn('Content-Security-Policy-Report-Only', response)
        self.assertEqual(response['Referrer-Policy'], 'strict-origin-when-cross-origin')
        self.assertEqual(response['Cross-Origin-Opener-Policy'], 'same-origin-allow-popups')
        self.assertEqual(response['Cross-Origin-Resource-Policy'], 'same-origin')
        self.assertIn('camera=()', response['Permissions-Policy'])
        self.assertIn('microphone=()', response['Permissions-Policy'])
        self.assertIn('clipboard-write=(self)', response['Permissions-Policy'])
        self.assertIn('fullscreen=(self)', response['Permissions-Policy'])
        self.assertNotIn('Cross-Origin-Embedder-Policy', response)

    def test_nonce_is_fresh_matches_both_headers_and_only_trusted_markup(self):
        view = _stack(_html)
        first = view(self.factory.get('/'))
        second = view(self.factory.get('/'))
        self.assertPolicies(first)
        self.assertNotEqual(_nonce(first), _nonce(second))
        for response in (first, second):
            nonce = _nonce(response)
            self.assertIn(f"'nonce-{nonce}'", response['Content-Security-Policy-Report-Only'])
            parser = _Scripts()
            parser.feed(response.content.decode())
            self.assertEqual(parser.scripts, [{'nonce': nonce}, {}])
            self.assertIn(b'&lt;script&gt;window.injected', response.content)
            self.assertIn('private', response['Cache-Control'])
            self.assertIn('no-store', response['Cache-Control'])

    def test_inline_handlers_are_staged_but_inline_scripts_are_enforced(self):
        response = _stack(_html)(self.factory.get('/'))
        enforced = response['Content-Security-Policy']
        candidate = response['Content-Security-Policy-Report-Only']
        self.assertIn("script-src-attr 'unsafe-inline'", enforced)
        self.assertIn("script-src-attr 'none'", candidate)
        scripts = next(d for d in enforced.split('; ') if d.startswith('script-src '))
        self.assertNotIn("'unsafe-inline'", scripts)
        self.assertNotIn("'unsafe-eval'", enforced)
        for directive in ('object-src', 'frame-src', 'frame-ancestors'):
            self.assertIn(f"{directive} 'none'", enforced)
        self.assertIn("form-action 'self'", enforced)
        self.assertNotIn('report-uri', candidate)
        self.assertNotIn('report-to', candidate)

    def test_json_errors_and_streaming_responses_receive_policies_without_nonce(self):
        for status in (200, 403, 404, 413, 500):
            with self.subTest(status=status):
                response = _stack(lambda request: JsonResponse({'ok': False}, status=status))(
                    self.factory.get('/'))
                self.assertPolicies(response)
                self.assertNotIn("'nonce-", response['Content-Security-Policy'])
                self.assertNotIn('Cache-Control', response)
        response = _stack(lambda request: StreamingHttpResponse(iter([b'private file'])))(
            self.factory.get('/download/'))
        self.assertPolicies(response)
        self.assertTrue(response.streaming)
        response.close()

    @override_settings(SECURE_SSL_REDIRECT=True, DEBUG=False)
    def test_https_redirect_is_covered_even_when_view_never_runs(self):
        view = mock.Mock(side_effect=AssertionError('view must not run'))
        response = _stack(view)(self.factory.get('/'))
        self.assertEqual(response.status_code, 301)
        self.assertPolicies(response)
        view.assert_not_called()

    def test_whitenoise_static_response_is_covered_without_disabling_static_caching(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'test.js').write_text('window.staticLoaded = true;', encoding='utf-8')
            with override_settings(STATIC_ROOT=root, WHITENOISE_AUTOREFRESH=True):
                view = mock.Mock(side_effect=AssertionError('view must not run'))
                response = _stack(WhiteNoiseMiddleware(view))(self.factory.get('/static/test.js'))
                self.assertEqual(response.status_code, 200)
                self.assertPolicies(response)
                self.assertNotIn('no-store', response.get('Cache-Control', ''))
                view.assert_not_called()
                response.close()

    def test_upload_refusal_is_covered_before_body_parsing(self):
        view = mock.Mock(side_effect=AssertionError('view must not run'))
        request = self.factory.post('/api/policy-test/', CONTENT_LENGTH=str(30 * 1024 * 1024))
        with mock.patch('shared_utils.upload_limits._limit_for', return_value=25):
            response = _stack(UploadSizeLimitMiddleware(view))(request)
        self.assertEqual(response.status_code, 413)
        self.assertPolicies(response)
        view.assert_not_called()

    def test_html_cannot_opt_into_shared_caching(self):
        def view(request):
            response = _html(request)
            response['Cache-Control'] = 'public, max-age=3600'
            return response
        response = _stack(view)(self.factory.get('/'))
        self.assertIn('private', response['Cache-Control'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertNotIn('public', response['Cache-Control'])

    def test_pdf_chat_and_configured_storage_have_required_sources(self):
        enforced, _ = policies('test-uploads', 'eu-west-2')
        self.assertIn('https://cdnjs.cloudflare.com', enforced['worker-src'])
        self.assertIn('blob:', enforced['worker-src'])
        self.assertIn('https://cdnjs.cloudflare.com', enforced['connect-src'])
        self.assertIn('https://*.stream-io-api.com', enforced['connect-src'])
        self.assertIn('wss://*.stream-io-api.com', enforced['connect-src'])
        self.assertIn('https://test-uploads.s3.amazonaws.com', enforced['connect-src'])
        self.assertIn('https://test-uploads.s3.eu-west-2.amazonaws.com', enforced['connect-src'])
        self.assertNotIn('https:', enforced['connect-src'])
        self.assertNotIn('*', enforced['script-src'])

    def test_all_trusted_template_script_tags_use_the_request_nonce(self):
        count = 0
        for path in Path(settings.BASE_DIR, 'templates').rglob('*.html'):
            for tag in re.findall(r'<script\b[^>]*>', path.read_text(encoding='utf-8')):
                count += 1
                with self.subTest(path=str(path), tag=tag):
                    self.assertIn('nonce="{{ csp_nonce }}"', tag)
        self.assertGreater(count, 40, 'positive control: the template inventory must be discovered')


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                                      'LOCATION': 'browser-policy-idempotency-tests'}})
class NonceReplayTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def _request(self):
        request = self.factory.post('/policy-test/', HTTP_IDEMPOTENCY_KEY='repeated-action')
        request.user = SimpleNamespace(is_authenticated=True, pk=42)
        return request

    def test_html_replay_rotates_nonce_without_executing_the_mutation_again(self):
        view = mock.Mock(side_effect=_html)
        middleware = _stack(IdempotencyMiddleware(view))
        first = middleware(self._request())
        second = middleware(self._request())
        self.assertEqual(view.call_count, 1)
        self.assertEqual(second['X-Cache-Lookup'], 'HIT - Idempotency Protected')
        self.assertNotEqual(_nonce(first), _nonce(second))
        self.assertEqual(second.content, first.content.replace(_nonce(first).encode(), _nonce(second).encode()))
        self.assertNotIn(_nonce(first).encode(), second.content)
        parser = _Scripts()
        parser.feed(second.content.decode())
        self.assertEqual(parser.scripts, [{'nonce': _nonce(second)}, {}])
        self.assertIn('no-store', second['Cache-Control'])

    def test_json_replay_does_not_create_a_nonce_or_change_the_result(self):
        view = mock.Mock(return_value=JsonResponse({'charged': 1}))
        middleware = _stack(IdempotencyMiddleware(view))
        first = middleware(self._request())
        second = middleware(self._request())
        self.assertEqual(view.call_count, 1)
        self.assertEqual(first.content, second.content)
        self.assertNotIn("'nonce-", second['Content-Security-Policy'])


class RenderedPagePolicyTests(TestCase):
    def test_real_home_and_login_scripts_match_the_header(self):
        for name in ('pages:home', 'accounts:login'):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                nonce = _nonce(response)
                parser = _Scripts()
                parser.feed(response.content.decode())
                self.assertGreater(len(parser.scripts), 2)
                for script in parser.scripts:
                    if script.get('type') not in ('application/json', 'application/ld+json'):
                        self.assertEqual(script.get('nonce'), nonce)
                self.assertEqual(response['Cross-Origin-Opener-Policy'], 'same-origin-allow-popups')

    @override_settings(DEBUG=False)
    def test_real_not_found_response_has_the_policy(self):
        response = self.client.get('/no-such-browser-policy-route/')
        self.assertEqual(response.status_code, 404)
        self.assertIn('Content-Security-Policy', response)
        self.assertIn('Permissions-Policy', response)
