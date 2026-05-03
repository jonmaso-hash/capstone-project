from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Application


def signup_view(request):
    return render(request, "accounts/signup.html")


def login_view(request):
    return render(request, "accounts/login.html")


def seeking_investment(request):
    if request.method == "POST":
        company_name = request.POST.get("company_name")
        description = request.POST.get("description")
        amount_requested = request.POST.get("amount_requested")

        if company_name and description and amount_requested:
            Application.objects.create(
                user=request.user,
                company_name=company_name,
                description=description,
                amount_requested=amount_requested,
            )
            messages.success(request, "Application submitted successfully.")
            return redirect("accounts:thank_you")

        messages.error(request, "All fields are required.")

    return render(request, "accounts/seeking_investment.html")


def profile_view(request, username):
    user = get_object_or_404(User, username=username)
    application = Application.objects.filter(user=user).first()

    return render(request, "accounts/profile.html", {
        "profile_user": user,
        "application": application
    })


def thank_you(request):
    return render(request, "accounts/thank_you.html")


def applications_list(request):
    applications = Application.objects.all()
    return render(request, "accounts/applications_list.html", {
        "applications": applications
    })


def application_detail(request, pk):
    application = get_object_or_404(Application, pk=pk)
    return render(request, "accounts/application_detail.html", {
        "application": application
    })