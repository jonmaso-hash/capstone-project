from django.shortcuts import render, redirect  # Added redirect here
from django.core.mail import send_mail
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import contactForm  # Added your form import back

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
            WaitlistEntry.objects.get_or_create(email=email, defaults={'name': name})
            messages.success(request, "You're on the list — we'll be in touch.")
        return redirect('pages:waitlist')
    return render(request, 'pages/waitlist.html')


def services(request):
    return render(request, 'pages/services.html')

def about(request):
    return render(request, 'pages/about.html')

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

    return render(request, 'pages/thank_you.html', {
        'applicant_name': applicant_name,
        'application': application,
        'dashboard_url': dashboard_url,
        'show_celebration': show_celebration,
        'next_step_text': next_step_text,
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

            try:
                send_mail(
                    subject=f"Email From KCV Capital: {name}",
                    message=message_body,
                    from_email=None,      # Uses EMAIL_HOST_USER from settings.py
                    recipient_list=['jonmaso@gmail.com'],
                    fail_silently=False,
                )
                messages.success(request, "Message sent successfully!")
                return redirect('contact') # This clears the form and shows the success message

            except Exception as e:
                messages.error(request, f"Error sending email: {e}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = contactForm()

    return render(request, 'pages/contact.html', {'form': form})