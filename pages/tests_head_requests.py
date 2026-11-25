"""
A response to HEAD must carry no body.

Django renders HEAD like GET and leaves dropping the body to the server, and
gunicorn 26 does not drop it. In production that left HTML on a reused
keep-alive connection behind Caddy, and the next request over it failed as a
502 ('malformed HTTP status code "html>"', HEAD /terms/, 2026-11-24).

These tests call the real WSGI handler, as gunicorn does. Django's test Client
removes HEAD bodies itself (conditional_content_removal), so a Client-based
test would pass with or without the fix.
"""
import io

from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler
from django.http import FileResponse, HttpResponse, StreamingHttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from shared_utils.middleware import HeadResponseBodyMiddleware

MIDDLEWARE_PATH = 'shared_utils.middleware.HeadResponseBodyMiddleware'


def call_wsgi(method, path):
    """Run one request through Django's WSGI application the way a server does."""
    environ = {
        'REQUEST_METHOD': method, 'PATH_INFO': path, 'QUERY_STRING': '', 'SCRIPT_NAME': '',
        'SERVER_NAME': 'testserver', 'SERVER_PORT': '443', 'SERVER_PROTOCOL': 'HTTP/1.1',
        'HTTP_HOST': 'testserver', 'HTTP_X_FORWARDED_PROTO': 'https', 'HTTPS': 'on',
        'wsgi.url_scheme': 'https', 'wsgi.input': io.BytesIO(b''), 'wsgi.errors': io.StringIO(),
        'wsgi.version': (1, 0), 'wsgi.multithread': True, 'wsgi.multiprocess': True, 'wsgi.run_once': False,
    }
    captured = {}

    def start_response(status, headers, exc_info=None):
        captured['status'], captured['headers'] = status, dict(headers)

    result = WSGIHandler()(environ, start_response)
    try:
        body = b''.join(result)
    finally:
        if hasattr(result, 'close'):
            result.close()
    return captured['status'], captured['headers'], body


# Rendering a page needs static URLs; the manifest only exists after collectstatic.
@override_settings(STORAGES={**settings.STORAGES, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class HeadThroughWsgiTests(TestCase):
    def test_head_sends_no_body_but_keeps_the_get_length(self):
        get_status, get_headers, get_body = call_wsgi('GET', '/terms/')
        self.assertTrue(get_status.startswith('200'), get_status)
        self.assertGreater(len(get_body), 0, 'positive control: GET has a body')

        head_status, head_headers, head_body = call_wsgi('HEAD', '/terms/')
        self.assertEqual(head_status, get_status)
        self.assertEqual(head_body, b'', 'HEAD must not put body bytes on the connection')
        self.assertEqual(head_headers.get('Content-Length'), str(len(get_body)))

    def test_get_is_unchanged(self):
        _, headers, body = call_wsgi('GET', '/terms/')
        self.assertEqual(headers.get('Content-Length'), str(len(body)))


class HeadMiddlewareUnitTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def run_mw(self, method, response):
        return HeadResponseBodyMiddleware(lambda request: response)(getattr(self.factory, method.lower())('/x/'))

    def test_is_first_so_it_sees_the_finished_response(self):
        self.assertEqual(settings.MIDDLEWARE[0], MIDDLEWARE_PATH)

    def test_plain_response(self):
        response = self.run_mw('HEAD', HttpResponse(b'<!DOCTYPE html><html></html>'))
        self.assertEqual(response.content, b'')
        self.assertEqual(response['Content-Length'], '28')

    def test_existing_content_length_is_kept(self):
        original = HttpResponse(b'abc'); original['Content-Length'] = '3'
        self.assertEqual(self.run_mw('HEAD', original)['Content-Length'], '3')

    def test_streaming_response(self):
        response = self.run_mw('HEAD', StreamingHttpResponse(iter([b'chunk-1', b'chunk-2'])))
        self.assertEqual(b''.join(response.streaming_content), b'')

    def test_file_response_is_emptied_and_still_closed(self):
        handle = io.BytesIO(b'file body')
        response = self.run_mw('HEAD', FileResponse(handle))
        self.assertEqual(b''.join(response.streaming_content), b'')
        response.close()
        self.assertTrue(handle.closed)

    def test_other_methods_untouched(self):
        for method in ('GET', 'POST'):
            self.assertEqual(self.run_mw(method, HttpResponse(b'body')).content, b'body')
