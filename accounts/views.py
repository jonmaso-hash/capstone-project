from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Application
from .forms import ApplicationForm


def signup_view(request):
    return render(request, "accounts/signup.html")


def login_view(request):
    return render(request, "accounts/login.html")


@login_required
def seeking_investment(request):
    try:
        application = request.user.application
    except Application.DoesNotExist:
        application = None

    if request.method == "POST":
        form = ApplicationForm(request.POST, instance=application)

        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()

            # ✅ FIX: no username passed
            return redirect("accounts:profile")
    else:
        form = ApplicationForm(instance=application)

    return render(request, "accounts/seeking_investment.html", {
        "form": form
    })


@login_required
def profile(request):
    try:
        application = request.user.application
    except Application.DoesNotExist:
        application = None

    form = ApplicationForm(instance=application)

    return render(request, "accounts/profile.html", {
        "user": request.user,
        "application": application,
        "form": form
    })