"""
The one place a post-authentication destination is ever trusted.

Django's `@login_required` generates `?next=<path>` on 103 views across this
project, and until PR #27 every one of those destinations was discarded at the
auth boundary: `login_view` hardcoded a redirect to the user's own profile and
`signup_view` redirected to the role form, so a logged-out visitor following any
deep link — a notification, a shared page, an Explore card — landed somewhere
they never asked for.

Two rules hold everywhere in this module:

1. A destination is validated **when it is accepted**, never when it is used.
   Nothing reaches `request.session` or a redirect without having passed
   `url_has_allowed_host_and_scheme` first, so a smuggled `//evil.com` is
   discarded at the door rather than travelling through the signup lifecycle
   and being trusted two hops later.
2. An invalid destination is dropped silently and the caller falls back to its
   normal routing. A visitor who followed a tampered link still gets a working
   product; they simply do not get the tampered destination.
"""
from django.utils.http import url_has_allowed_host_and_scheme

# Session key holding a pending post-onboarding destination. Deliberately
# shaped like growth's `pending_referral_code`: stashed at signup GET, popped
# at first role-profile submission, because signup does not end at signup — it
# hands off to a role form that redirects again, so the destination has to
# survive two hops.
PENDING_NEXT_SESSION_KEY = 'pending_next_url'


def safe_destination(url, request):
    """
    Return `url` if it is a safe internal destination for this request, else None.

    Same-host, non-scheme-relative paths only. `//evil.com` and
    `https://evil.com` both fail, as does anything pointing at another host.
    """
    if not url:
        return None
    if not url_has_allowed_host_and_scheme(
        url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return None
    return url


def requested_destination(request):
    """
    The validated `next` this request is asking for, or None.

    POST wins over GET so a form's hidden field carries the destination across
    the submit; both are validated identically.
    """
    return safe_destination(
        request.POST.get('next') or request.GET.get('next'), request
    )


def remember_destination(request, url):
    """Stash an already-validated destination for after role onboarding."""
    destination = safe_destination(url, request)
    if destination:
        request.session[PENDING_NEXT_SESSION_KEY] = destination


def pop_destination(request):
    """
    Consume the pending destination exactly once.

    Popped rather than read, so an abandoned signup cannot leak its destination
    into an unrelated onboarding later in the same session. Re-validated on the
    way out because a session outlives the request that wrote it.
    """
    return safe_destination(
        request.session.pop(PENDING_NEXT_SESSION_KEY, None), request
    )
