from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.contrib.auth import get_user_model
from django.contrib.admin.views.decorators import staff_member_required
import re

from .models import FounderApplication

User = get_user_model()


# -------------------------
# Helpers
# -------------------------
def clean_money(value):
    """
    Converts strings like:
    '500,000', '$500,000', ' 500 000 ' → 500000.0
    """
    if not value:
        return None
    value = re.sub(r"[^\d.]", "", value)
    return float(value) if value else None


# -------------------------
# Auth Views
# -------------------------
def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()

    return render(request, 'accounts/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')

    return render(request, 'accounts/login.html', {'form': form})


# -------------------------
# Profile
# -------------------------
def profile_view(request, username):
    user = get_object_or_404(User, username=username)
    return render(request, 'accounts/profile.html', {'profile_user': user})


# -------------------------
# Application Form
# -------------------------
@login_required
def seeking_investment(request):
    if request.method == "POST":

        FounderApplication.objects.create(
            user=request.user,

            # Personal
            founder_name=request.POST.get("founder_name"),
            email=request.POST.get("email"),
            phone_number=request.POST.get("phone_number"),

            # Company
            company_name=request.POST.get("company_name"),
            company_website=request.POST.get("company_website"),

            # Description
            pitch_summary=request.POST.get("description"),
            business_description=request.POST.get("business_description"),

            # Funding
            sector=request.POST.get("sector"),
            stage=request.POST.get("stage"),

            raising_amount=clean_money(request.POST.get("raising_amount")),
            years_in_business=request.POST.get("years_in_business") or None,
            company_size=request.POST.get("company_size"),

            amount_raised=clean_money(request.POST.get("amount_raised")),

            # Intent
            reason_for_capital=request.POST.get("reason_for_capital"),

            # Extra
            extra_info=request.POST.get("extra_info"),
        )

        request.session["applicant_name"] = request.POST.get("founder_name")

        return redirect('accounts:thank_you')

    return render(request, 'seeking-investment.html')


# -------------------------
# Thank You Page
# -------------------------
@login_required
def thank_you(request):
    name = request.session.get("applicant_name", request.user.username)

    return render(request, 'thank_you.html', {
        "name": name
    })


# -------------------------
# Admin-style Applications View
# -------------------------
@staff_member_required
def applications_list(request):
    applications = FounderApplication.objects.all().order_by('-created_at')

    return render(request, 'accounts/applications.html', {
        'applications': applications
    })