from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login as auth_login
from django.contrib import messages 
from .models import Application, InvestorApplication
from .forms import ApplicationForm, InvestorForm

def signup_view(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect("accounts:profile")
    else:
        form = UserCreationForm()
    return render(request, "accounts/signup.html", {"form": form})

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect("accounts:profile")
    else:
        form = AuthenticationForm()
    return render(request, "accounts/login.html", {"form": form})

@login_required
def seeking_investment(request):
    # 1. Check if they are already an Investor
    if hasattr(request.user, "investor_application"):

        return redirect("accounts:profile")

    # 2. Check if they have already submitted a Founder application
    application = getattr(request.user, "application", None)
    if application:
        return redirect("accounts:profile")

    if request.method == "POST":
        form = ApplicationForm(request.POST)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            messages.success(request, "Application submitted successfully!")
            return redirect("accounts:profile")
    else:
        form = ApplicationForm()

    return render(request, "accounts/seeking_investment.html", {"form": form})

@login_required
def investor_form(request):
    # 1. Check if they are already a Founder
    if hasattr(request.user, "application"):
        return redirect("accounts:profile")

    # 2. Check if they have already submitted an Investor profile
    investor_app = getattr(request.user, "investor_application", None)
    if investor_app:
        return redirect("accounts:profile")

    if request.method == "POST":
        form = InvestorForm(request.POST)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            messages.success(request, "Investor profile created successfully!")
            return redirect("accounts:profile")
    else:
        form = InvestorForm()

    return render(request, "accounts/investor_form.html", {"form": form})

@login_required
def profile(request):
    application = getattr(request.user, "application", None)
    investor_application = getattr(request.user, "investor_application", None)

    show_welcome_prompt = not application and not investor_application

    return render(request, "accounts/profile.html", {
        "user": request.user,
        "application": application,
        "investor_application": investor_application,
        "show_welcome_prompt": show_welcome_prompt, 
    })