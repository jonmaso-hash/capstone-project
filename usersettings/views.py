import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.forms import ApplicationForm, InvestorForm, SellerForm, BuyerForm
from growth.services import consume_referral_if_pending
from matchmaking.models import Application, SellerApplication
from .models import UserSettings


@login_required
def settings_home(request):
    """
    Central settings page: relocated Privacy/DM toggles plus the new
    invitation/follow/blog/profile-visibility toggles.
    """
    user_settings = UserSettings.for_user(request.user)

    application = getattr(request.user, "match_founder_profile", None)
    investor_application = getattr(request.user, "match_investor_profile", None)

    dm_enabled = False
    if application and application.allow_direct_messages:
        dm_enabled = True
    elif investor_application and investor_application.allow_direct_messages:
        dm_enabled = True

    is_private = bool(
        (application and application.is_private) or
        (investor_application and investor_application.is_private)
    )

    # Pitch Videos section — settings live on whichever profile(s) the user
    # has (same "field lives on the role model" pattern as allow_direct_messages
    # above), not on UserSettings, since they're specific to a founder/seller
    # listing rather than an account-wide preference.
    seller_application = getattr(request.user, "match_seller_profile", None)
    pitch_video_profile = application or seller_application
    pitch_video_role = 'founder' if application else ('seller' if seller_application else None)

    return render(request, "usersettings/settings.html", {
        "user_settings": user_settings,
        "dm_enabled": dm_enabled,
        "is_private": is_private,
        "pitch_video_profile": pitch_video_profile,
        "pitch_video_role": pitch_video_role,
    })


@login_required
@require_POST
def toggle_setting(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"status": "error", "message": "Invalid request body."}, status=400)

    field = payload.get("field")
    value = payload.get("value")

    if field not in UserSettings.TOGGLE_FIELDS:
        return JsonResponse({"status": "error", "message": "Unknown setting."}, status=400)

    user_settings = UserSettings.for_user(request.user)
    setattr(user_settings, field, bool(value))
    user_settings.save(update_fields=[field, "updated_at"])

    return JsonResponse({"status": "success", "field": field, "value": bool(value)})


@login_required
def edit_founder_profile(request):
    """
    Canonical founder profile editor. Match-vector fields (description,
    sector, stage, extra_info, reason_for_capital, geography) lock for
    30 days after they're last changed — display fields stay editable.
    """
    application = getattr(request.user, "match_founder_profile", None)
    is_new_submission = application is None
    is_locked = bool(application and application.vector_fields_locked)

    if request.method == "POST":
        form = ApplicationForm(request.POST, request.FILES, instance=application, lock_vector_fields=is_locked)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user

            vector_changed = any(f in form.changed_data for f in Application.VECTOR_FIELDS)
            if vector_changed:
                app.vector_fields_updated_at = timezone.now()

            app.save()

            cache.delete(f"startup_data_{app.id}")

            if is_new_submission:
                consume_referral_if_pending(request, app)
                return redirect("pages:thank_you")

            messages.success(request, "Founder profile updated.")
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = ApplicationForm(instance=application, lock_vector_fields=is_locked)

    return render(request, "usersettings/edit_founder_profile.html", {
        "form": form,
        "application": application,
        "is_locked": is_locked,
        "unlock_at": application.vector_fields_unlock_at if application else None,
    })


@login_required
def edit_investor_profile(request):
    if hasattr(request.user, "match_founder_profile"):
        messages.warning(request, "Founders cannot submit investor profiles.")
        return redirect("accounts:profile", username=request.user.username)

    investor_profile = getattr(request.user, "match_investor_profile", None)
    is_new_submission = investor_profile is None

    if request.method == "POST":
        form = InvestorForm(request.POST, instance=investor_profile)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()

            if is_new_submission:
                consume_referral_if_pending(request, app)
                return redirect("pages:thank_you")

            messages.success(request, "Investment mandate updated successfully.")
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = InvestorForm(instance=investor_profile)

    return render(request, "usersettings/edit_investor_profile.html", {"form": form})


@login_required
def edit_seller_profile(request):
    """
    Canonical seller (business-for-sale) profile editor. Match-vector fields
    (description, industry, geography, reason_for_sale, extra_info) lock for
    30 days after they're last changed — deal economics stay editable, same
    pattern as edit_founder_profile.
    """
    seller_profile = getattr(request.user, "match_seller_profile", None)
    is_new_submission = seller_profile is None
    is_locked = bool(seller_profile and seller_profile.vector_fields_locked)

    if request.method == "POST":
        form = SellerForm(request.POST, request.FILES, instance=seller_profile, lock_vector_fields=is_locked)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user

            vector_changed = any(f in form.changed_data for f in SellerApplication.VECTOR_FIELDS)
            if vector_changed:
                app.vector_fields_updated_at = timezone.now()

            app.save()

            if is_new_submission:
                consume_referral_if_pending(request, app)
                return redirect("pages:thank_you")

            messages.success(request, "Business listing updated.")
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = SellerForm(instance=seller_profile, lock_vector_fields=is_locked)

    return render(request, "usersettings/edit_seller_profile.html", {
        "form": form,
        "seller_profile": seller_profile,
        "is_locked": is_locked,
        "unlock_at": seller_profile.vector_fields_unlock_at if seller_profile else None,
    })


@login_required
def edit_buyer_profile(request):
    buyer_profile = getattr(request.user, "match_buyer_profile", None)
    is_new_submission = buyer_profile is None

    if request.method == "POST":
        form = BuyerForm(request.POST, instance=buyer_profile)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()

            if is_new_submission:
                consume_referral_if_pending(request, app)
                return redirect("pages:thank_you")

            messages.success(request, "Acquisition mandate updated successfully.")
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = BuyerForm(instance=buyer_profile)

    return render(request, "usersettings/edit_buyer_profile.html", {"form": form})
