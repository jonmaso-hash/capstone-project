"""
Context for outbound HTML emails.

Split out of the admin action so the context an email is actually rendered
with can be asserted directly. An email template referencing `{{ site_url }}`
that nobody puts in the context renders a RELATIVE image URL, which resolves
against nothing in a mail client and shows a broken image -- and no request
ever fails, so nothing reveals it. The template cannot check this for itself;
only a test of the context can.
"""
from django.conf import settings


def site_url():
    """Absolute origin for links and images in email, never a relative path."""
    return getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')


def founder_match_context(founder, investor, visible_fields):
    return {
        'founder': founder,
        'investor': investor,
        'visible_fields': visible_fields,
        # Images and links in email have no page to resolve against.
        'site_url': site_url(),
    }
