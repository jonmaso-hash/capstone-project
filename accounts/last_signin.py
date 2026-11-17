"""The "Last used" hint on the login page.

A sign-in names its method here (password, or the social provider's id). The
method waits in the session until authentication has fully succeeded -- for
staff, that means after the MFA step (accounts/staff_mfa.py) -- and only then
is it written to a cookie. A failed, cancelled or half-finished sign-in never
gets that far, and logging out flushes the session, so an abandoned method is
dropped. The cookie itself outlives logout: it is a hint about this browser,
holds nothing but the method name, and grants nothing.
"""
from django.dispatch import receiver

from allauth.account.signals import user_logged_in as allauth_user_logged_in

COOKIE = 'last_signin_method'
MAX_AGE = 180 * 24 * 60 * 60
PENDING = 'last_signin_method_pending'
PASSWORD = 'password'
# Every option the login page offers. Anything else in the cookie is ignored.
METHODS = (PASSWORD, 'google', 'facebook', 'linkedin')


def remember(request, method):
    """Note ``method`` for this sign-in; the cookie is written once it fully succeeds."""
    if method in METHODS:
        request.session[PENDING] = method


@receiver(allauth_user_logged_in)
def _social_signin(sender, request, user, sociallogin=None, **kwargs):
    # allauth sends this only after the provider callback has authenticated
    # and logged the member in -- never for a cancelled or failed attempt.
    if sociallogin is not None:
        remember(request, sociallogin.account.provider)


def fully_authenticated(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return False
    if not user.is_staff:
        return True
    from . import staff_mfa
    from .models import StaffMFA
    return staff_mfa.is_verified(request, StaffMFA.objects.filter(user=user).first())


class LastSigninMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        session = getattr(request, 'session', None)
        method = session.get(PENDING) if session is not None else None
        if method and fully_authenticated(request):
            del session[PENDING]
            response.set_cookie(COOKIE, method, max_age=MAX_AGE, secure=True,
                                httponly=True, samesite='Lax')
        return response


def provider_available(request, provider_id):
    """True when ``provider_id`` has an app with a client id configured."""
    from allauth.socialaccount.adapter import get_adapter
    try:
        apps = get_adapter().list_apps(request, provider=provider_id)
    except Exception:
        return False
    return any(app.client_id for app in apps)


def last_used(request):
    """The method to badge on the login page, or None."""
    method = request.COOKIES.get(COOKIE)
    if method not in METHODS:
        return None
    if method != PASSWORD and not provider_available(request, method):
        return None
    return method
