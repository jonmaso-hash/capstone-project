from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login as auth_login
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
    # Retrieve existing founder application if it exists
    application = getattr(request.user, "application", None)

    if request.method == "POST":
        form = ApplicationForm(request.POST, instance=application)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            return redirect("accounts:profile")
    else:
        form = ApplicationForm(instance=application)

    return render(request, "accounts/seeking_investment.html", {
        "form": form
    })

@login_required
def investor_form(request):
    # Retrieve existing investor application if it exists
    investor_app = getattr(request.user, "investor_application", None)

    if request.method == "POST":
        form = InvestorForm(request.POST, instance=investor_app)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            return redirect("accounts:profile")
    else:
        form = InvestorForm(instance=investor_app)

    return render(request, "accounts/investor_form.html", {
        "form": form
    })

@login_required
def profile(request):
    # Fetch both potential application types for the profile page
    application = getattr(request.user, "application", None)
    investor_application = getattr(request.user, "investor_application", None)

    return render(request, "accounts/profile.html", {
        "user": request.user,
        "application": application,
        "investor_application": investor_application
    })