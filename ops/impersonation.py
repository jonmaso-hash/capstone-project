"""
Impersonation is read-only.

A staff member viewing as a user (ops.views.start_impersonation) sees what the
user sees and changes nothing as them:

- every POST/PUT/PATCH/DELETE is refused, except leaving impersonation and
  signing out. A refusal, not a denylist, so a view added later is covered
  without anyone remembering to list it.
- GETs that grant access as the user are refused too: the Stream chat token
  (reading and sending their messages) and opening a direct chat.
- pages still load, but is_impersonating() is True for the request, and the
  analytics loggers, profile-view log and notification list check it, so staff
  browsing is never recorded as the user's own activity.

Editing on a user's behalf would be its own feature with its own authorization,
not an exemption here.
"""
import contextvars

from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import Resolver404, resolve
from django.utils.http import url_has_allowed_host_and_scheme

SESSION_KEY = 'impersonator_id'
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}

# The only writes allowed while impersonating: leaving it, and signing out.
ALLOWED_WRITES = {'ops:stop_impersonation', 'accounts:logout', 'logout', 'account_logout'}

# Reads that hand out access as the user. The token endpoints are fetched by
# JavaScript, so they are refused as JSON.
REFUSED_READS = {'accounts:stream_token', 'matchmaking:stream_token', 'matchmaking:initiate_direct_chat'}
JSON_READS = {'accounts:stream_token', 'matchmaking:stream_token'}

_impersonating = contextvars.ContextVar('impersonating', default=False)


def is_impersonating():
    """True while the current request is a staff member viewing as a user."""
    return _impersonating.get()


class ReadOnlyImpersonationMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.session.get(SESSION_KEY):
            return self.get_response(request)

        view_name = _view_name(request.path_info)
        if request.method in SAFE_METHODS:
            refused = view_name in REFUSED_READS
        else:
            refused = view_name not in ALLOWED_WRITES
        if refused:
            return _refuse(request, as_json=view_name in JSON_READS)

        token = _impersonating.set(True)
        try:
            return self.get_response(request)
        finally:
            _impersonating.reset(token)


def _view_name(path):
    try:
        return resolve(path).view_name
    except Resolver404:
        return None


def _refuse(request, as_json=False):
    message = f"Read-only while viewing as {request.user.username}. Return to your staff account to make changes."
    if as_json or _wants_json(request):
        return JsonResponse({'error': message}, status=403)

    # A form post: back to the page it came from, with the reason shown there.
    messages.error(request, message)
    page = request.META.get('HTTP_REFERER', '')
    if not url_has_allowed_host_and_scheme(page, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        page = '/'
    return HttpResponseRedirect(page)


def _wants_json(request):
    return (
        request.path_info.startswith('/api/')
        or request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or request.content_type == 'application/json'
        or 'application/json' in request.headers.get('accept', '')
    )
