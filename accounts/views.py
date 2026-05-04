from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login as auth_login
from .models import Application
from .forms import ApplicationForm

def signup_view(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect("accounts:profile") # Add 'accounts:' prefix
    else:
        form = UserCreationForm()
    return render(request, "accounts/signup.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect("accounts:profile") # Add 'accounts:' prefix
    else:
        form = AuthenticationForm()
    return render(request, "accounts/login.html", {"form": form})

@login_required
def seeking_investment(request):
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
def profile(request):
    application = getattr(request.user, "application", None)

    return render(request, "accounts/profile.html", {
        "user": request.user,
        "application": application
    })