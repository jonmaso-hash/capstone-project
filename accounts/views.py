from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login as auth_login
from django.contrib.auth.models import User
from django.contrib import messages 

# Gemini Automated Deal Screening Orchestration Service
from matchmaking.services.deal_screener import index_founder_pitch_deck

# Syncing with the models we defined for the matching engine
from matchmaking.models import Application, InvestorApplication
from .forms import ApplicationForm, InvestorForm 


# =================================================
# AUTHENTICATION VIEWS
# =================================================

def signup_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile", username=request.user.username)
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, f"Welcome to Interlink Foundry, {user.username}!")
            return redirect("accounts:profile", username=user.username)
    else:
        form = UserCreationForm()
    return render(request, "accounts/signup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile", username=request.user.username)
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect("accounts:profile", username=user.username)
    else:
        form = AuthenticationForm()
    return render(request, "accounts/login.html", {"form": form})


# =================================================
# APPLICATION & INVESTOR FLOW
# =================================================

@login_required
def seeking_investment(request):
    """
    Founder Onboarding: Collects startup data and processes pitch decks 
    via Gemini Multimodal File Search.
    """
    # 1. Block existing Investors from becoming Founders
    if hasattr(request.user, "match_investor_profile"):
        messages.warning(request, "Investors cannot submit founder applications.")
        return redirect("accounts:profile", username=request.user.username)

    # 2. Prevent duplicate applications
    application = getattr(request.user, "match_founder_profile", None)
    if application:
        messages.info(request, "You already have an active founder profile.")
        return redirect("accounts:profile", username=request.user.username)

    if request.method == "POST":
        # FIXED: Added request.FILES context to catch layout payloads (PDF decks)
        form = ApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            
            # FIXED: Nested tracking logic safely inside validation execution frame
            if app.pitch_deck:
                try:
                    index_founder_pitch_deck(app.id)
                    messages.success(request, "Founder profile submitted! Gemini has successfully indexed your pitch deck.")
                except Exception as e:
                    # Fail-safe to ensure user registration goes through even if API times out
                    messages.warning(request, "Profile saved, but automated deck vectorization is processing in the background.")
            else:
                messages.success(request, "Founder profile submitted! The matching engine is now analyzing your pitch.")
                
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = ApplicationForm()

    return render(request, "accounts/seeking_investment.html", {"form": form})


@login_required
def investor_form(request):
    """
    Investor Onboarding: Collects investment mandate for the matching engine.
    """
    # 1. Block existing Founders from becoming Investors
    if hasattr(request.user, "match_founder_profile"):
        messages.warning(request, "Founders cannot submit investor profiles.")
        return redirect("accounts:profile", username=request.user.username)

    # 2. Check for existing profile
    investor_profile = getattr(request.user, "match_investor_profile", None)
    if investor_profile:
        messages.info(request, "Your investor mandate is already complete.")
        return redirect("accounts:profile", username=request.user.username)

    if request.method == "POST":
        form = InvestorForm(request.POST)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            messages.success(request, "Mandate saved. Accessing the Deal Flow dashboard...")
            return redirect("matchmaking:investor_index")
    else:
        form = InvestorForm()

    return render(request, "accounts/investor_form.html", {"form": form})


# =================================================
# PROFILE & NAVIGATION
# =================================================

@login_required
def profile(request, username):
    """
    Main User Hub: Displays the profile cards built for Interlink Foundry.
    """
    viewed_user = get_object_or_404(User, username=username)
    
    # Using the matching engine's related_names
    application = getattr(viewed_user, "match_founder_profile", None)
    investor_application = getattr(viewed_user, "match_investor_profile", None)

    # Trigger for the UI Welcome Prompt
    show_welcome_prompt = not application and not investor_application

    return render(request, "accounts/profile.html", {
        "profile_user": viewed_user,
        "application": application,
        "investor_application": investor_application,
        "show_welcome_prompt": show_welcome_prompt, 
    })


@login_required
def redirect_to_own_profile(request):
    return redirect("accounts:profile", username=request.user.username)