import logging

from django.conf import settings
from django.shortcuts import render, redirect  # Added redirect here
from django.core.mail import EmailMessage
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.urls import reverse
from accounts.redirects import safe_destination
from billing.pricing import subscription_prices
from .forms import contactForm  # Added your form import back

logger = logging.getLogger(__name__)

# Create your views here.
def home_view(request):
    from matchmaking.models import log_page_event, Application, SellerApplication
    from matchmaking.views import DAILY_INTRO_REQUEST_LIMIT, FREE_CRM_LEAD_LIMIT
    from zelda_api.quotas import (
        FREE_CREDITS, PREMIUM_CREDITS,
        VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT, VALUATION_OVERAGE_PRICE_USD,
        VALUATION_FIRM_MONTHLY_LIMIT, VALUATION_FIRM_OVERAGE_PRICE_USD,
        VALUATION_REPORT_PRICE_USD,
    )
    log_page_event(request, 'landing_view')

    featured_founders = Application.objects.discoverable().filter(is_staff_featured=True).exclude(review_status='DENIED')[:6]
    featured_sellers = SellerApplication.objects.discoverable().filter(is_staff_featured=True).exclude(review_status='DENIED')[:6]

    return render(request, 'pages/home.html', {
        **subscription_prices(),
        'featured_founders': featured_founders,
        'featured_sellers': featured_sellers,
        'daily_intro_limit': DAILY_INTRO_REQUEST_LIMIT,
        'free_crm_lead_limit': FREE_CRM_LEAD_LIMIT,
        'free_ai_credits': FREE_CREDITS,
        'premium_ai_credits': PREMIUM_CREDITS,
        'valuation_investor_buyer_monthly_limit': VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT,
        'valuation_overage_price': VALUATION_OVERAGE_PRICE_USD,
        'valuation_firm_monthly_limit': VALUATION_FIRM_MONTHLY_LIMIT,
        'valuation_firm_overage_price': VALUATION_FIRM_OVERAGE_PRICE_USD,
        'valuation_report_price': VALUATION_REPORT_PRICE_USD,
    })

def waitlist_join(request):
    from ops.models import WaitlistEntry
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        name = request.POST.get('name', '').strip()
        if not email:
            messages.error(request, "Email is required.")
        else:
            # 10 joins an hour per address (accounts/rate_limits.py). Over that the
            # visitor sees the same confirmation and nothing is saved.
            from accounts import rate_limits
            if rate_limits.reserve('waitlist_ip', rate_limits.client_ip(request)) is not None:
                WaitlistEntry.objects.get_or_create(email=email, defaults={'name': name})
            messages.success(request, "You're on the list — we'll be in touch.")
        return redirect('pages:waitlist')
    return render(request, 'pages/waitlist.html')


# Both legal pages are deliberately unauthenticated: a visitor has to be able
# to read them before they sign up or pay, and they are linked from the footer
# on every page including the signup form. LEGAL_PAGES_ARE_DRAFT flags them as
# awaiting review; set it False once reviewed language is in place.
LEGAL_PAGES_ARE_DRAFT = True
LEGAL_LAST_UPDATED = 'September 2026'


def privacy(request):
    return render(request, 'pages/privacy.html', {
        'page_title': 'Privacy Policy',
        'last_updated': LEGAL_LAST_UPDATED,
        'draft_notice': LEGAL_PAGES_ARE_DRAFT,
    })


def terms(request):
    return render(request, 'pages/terms.html', {
        'page_title': 'Terms of Service',
        'last_updated': LEGAL_LAST_UPDATED,
        'draft_notice': LEGAL_PAGES_ARE_DRAFT,
    })

def bulletin_board(request):
    return render(request, 'pages/bulletin_board.html')

@login_required
def thank_you_view(request):
    """
    Shared landing page after first-time profile submission for all four
    roles (edit_founder_profile/edit_investor_profile/edit_seller_profile/
    edit_buyer_profile all redirect here — see usersettings/views.py).

    dashboard_url and next_step_text used to be founder-only/absent: the
    "Back to Dashboard" button linked to '/' (home) for everyone, and the
    celebration was gated on completion_percentage == 100 — a metric that
    counts several optional fields (phone, website, current_revenue), so
    it essentially never fired for a founder who only filled the required
    ones. Reaching this page at all means required onboarding is done,
    so the celebration now fires unconditionally, with next_step_text
    naming a concrete, real signal (has_pitch_asset) to improve further —
    never an invented number like "your match quality improves by X%".
    """
    applicant_name = request.user.get_full_name() or request.user.username
    application = getattr(request.user, 'match_founder_profile', None)
    investor_profile = getattr(request.user, 'match_investor_profile', None)
    seller_profile = getattr(request.user, 'match_seller_profile', None)
    buyer_profile = getattr(request.user, 'match_buyer_profile', None)

    if application:
        if application.founder_name:
            applicant_name = application.founder_name
        dashboard_url = 'matchmaking:founder_dashboard'
        has_pitch_asset = bool(application.pitch_deck) or bool(application.pitch_video)
        next_step_text = (
            "Add recent milestones to keep investors updated." if has_pitch_asset
            else "Upload a pitch deck to give investors more to review."
        )
    elif investor_profile:
        dashboard_url = 'matchmaking:investor_dashboard'
        next_step_text = "Add your check-size range and thesis summary to sharpen your matches."
    elif seller_profile:
        dashboard_url = 'matchmaking:seller_dashboard'
        next_step_text = "Upload financials or a data room document to build buyer confidence."
    elif buyer_profile:
        dashboard_url = 'matchmaking:buyer_dashboard'
        next_step_text = "Add your acquisition criteria to sharpen your matches."
    else:
        dashboard_url = 'pages:home'
        next_step_text = ""

    # Gate the celebration on actually having a profile, not on any
    # completeness threshold — this page is only ever reached via a
    # just-created-profile redirect, but someone navigating here directly
    # with no profile at all shouldn't see a false "profile is live" toast.
    show_celebration = bool(application or investor_profile or seller_profile or buyer_profile)

    # A visitor who arrived from a deep link (an Explore card, a shared
    # profile, a notification) had their destination carried through signup and
    # role onboarding — see accounts/redirects.py. It rides in as ?next= rather
    # than skipping this page, so the onboarding milestone still happens and the
    # original intent becomes a visible CTA instead of a silent redirect.
    # Re-validated here: this is the point of use, and the query string is as
    # untrusted as any other.
    pending_destination = safe_destination(request.GET.get('next'), request)

    return render(request, 'pages/thank_you.html', {
        'applicant_name': applicant_name,
        'application': application,
        'dashboard_url': dashboard_url,
        'show_celebration': show_celebration,
        'next_step_text': next_step_text,
        'pending_destination': pending_destination,
    })

def contact_view(request):
    if request.method == 'POST':
        form = contactForm(request.POST)

        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            company_name = form.cleaned_data['company']
            phone_number = form.cleaned_data['phone']
            message = form.cleaned_data['message']

            # Formatted string for the email content
            message_body = (
                f'You have a new inquiry\n\n'
                f'Name: {name}\n'
                f'Email: {email}\n'
                f'Company Name: {company_name}\n'
                f'Phone Number: {phone_number}\n\n'
                f'Message:\n{message}'
            )

            # Sent from the site's verified sender (Postmark refuses anything
            # else) to the configured inbox, with Reply-To set to the visitor
            # so a reply goes to them. Only the send is inside the try: the
            # redirect used to be too, and because it named 'contact' instead
            # of 'pages:contact' it raised after a successful send, so visitors
            # were told their delivered message had failed.
            # 5 messages an hour per address (accounts/rate_limits.py); a message
            # that fails to send doesn't count.
            from accounts import rate_limits
            client_ip = rate_limits.client_ip(request)
            token = rate_limits.reserve('contact_ip', client_ip)
            if token is None:
                messages.error(request, f"Too many messages from this network. Try again {rate_limits.retry_phrase('contact_ip', client_ip)}.")
                return render(request, 'pages/contact.html', {'form': form}, status=429)

            try:
                EmailMessage(
                    subject=f"Interlink Foundry contact form: {name}",
                    body=message_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[settings.CONTACT_FORM_RECIPIENT],
                    reply_to=[email],
                ).send(fail_silently=False)
            except Exception:
                rate_limits.release(token)
                logger.exception('Contact form email could not be sent')
                messages.error(request, "We couldn't send your message right now. Please try again in a few minutes.")
            else:
                messages.success(request, "Message sent successfully!")
                return redirect('pages:contact')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = contactForm()

    return render(request, 'pages/contact.html', {'form': form})


@require_POST
def analytics_consent(request):
    """
    Record an analytics choice, or change one already made.

    A POST, not a link: it changes state, and it must be as easy to withdraw as
    to give. The destination is validated like every other post-action redirect
    here — a consent click is not a reason to trust a URL.
    """
    from accounts.redirects import safe_destination
    from .analytics import CONSENT_COOKIE, CONSENT_MAX_AGE, DENIED, GRANTED

    granted = request.POST.get('choice') == 'accept'
    destination = safe_destination(request.POST.get('next'), request) or reverse('pages:home')
    response = redirect(destination)
    response.set_cookie(
        CONSENT_COOKIE,
        GRANTED if granted else DENIED,
        max_age=CONSENT_MAX_AGE,
        samesite='Lax',
        secure=not settings.DEBUG,
        httponly=False,
    )
    if not granted:
        # Nothing of theirs should be left behind by a decline.
        response.delete_cookie('_ga')
    return response
