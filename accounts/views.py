from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login as auth_login
from django.contrib.auth.models import User
from django.contrib import messages 

from .models import Application, InvestorApplication
from .forms import ApplicationForm, InvestorForm

# --- Authentication Views ---

def signup_view(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            # Fix: Pass username to redirect
            return redirect("accounts:profile", username=user.username)
    else:
        form = UserCreationForm()
    return render(request, "accounts/signup.html", {"form": form})

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            # Fix: Pass username to redirect
            return redirect("accounts:profile", username=user.username)
    else:
        form = AuthenticationForm()
    return render(request, "accounts/login.html", {"form": form})

# --- Application Flow Views ---

@login_required
def seeking_investment(request):
    # 1. Prevent Investors from applying as Founders
    if hasattr(request.user, "investor_application"):
        messages.warning(request, "Investors cannot submit founder applications.")
        return redirect("accounts:profile", username=request.user.username)

    # 2. Prevent duplicate Founder applications
    application = getattr(request.user, "application", None)
    if application:
        return redirect("accounts:profile", username=request.user.username)

    if request.method == "POST":
        form = ApplicationForm(request.POST)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            messages.success(request, "Application submitted successfully!")
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = ApplicationForm()

    return render(request, "accounts/seeking_investment.html", {"form": form})

@login_required
def investor_form(request):
    # 1. Prevent Founders from applying as Investors
    if hasattr(request.user, "application"):
        messages.warning(request, "Founders cannot submit investor profiles.")
        return redirect("accounts:profile", username=request.user.username)

    # 2. Prevent duplicate Investor profiles
    investor_app = getattr(request.user, "investor_application", None)
    if investor_app:
        return redirect("accounts:profile", username=request.user.username)

    if request.method == "POST":
        form = InvestorForm(request.POST)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            messages.success(request, "Investor profile created successfully!")
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = InvestorForm()

    return render(request, "accounts/investor_form.html", {"form": form})

# --- Profile View ---

@login_required
def profile(request, username):
    # Fetch the user for the profile being viewed
    viewed_user = get_object_or_404(User, username=username)
    
    # Get associated data
    application = getattr(viewed_user, "application", None)
    investor_application = getattr(viewed_user, "investor_application", None)

    # UI logic
    show_welcome_prompt = not application and not investor_application

    return render(request, "accounts/profile.html", {
        "profile_user": viewed_user,
        "application": application,
        "investor_application": investor_application,
        "show_welcome_prompt": show_welcome_prompt, 
    })