import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.forms import ApplicationForm, InvestorForm, SellerForm, BuyerForm
from growth.services import consume_referral_if_pending
from matchmaking.models import Application, SellerApplication, ProfileVideo
from .models import UserSettings


def _get_role_profile(user):
    """
    Returns (profile, role_label) for whichever of the four marketplace
    roles this user has — Archive/Delete is generic across all of them
    since Application/InvestorApplication/SellerApplication/BuyerApplication
    all share the same is_archived/archive()/unarchive() shape.
    """
    for attr, label in (
        ('match_founder_profile', 'founder profile'),
        ('match_investor_profile', 'investor mandate'),
        ('match_seller_profile', 'business listing'),
        ('match_buyer_profile', 'acquisition mandate'),
    ):
        profile = getattr(user, attr, None)
        if profile:
            return profile, label
    return None, None


@login_required
@require_POST
def archive_profile(request):
    profile, label = _get_role_profile(request.user)
    if not profile:
        messages.error(request, "No profile found to archive.")
        return redirect('usersettings:home')
    profile.archive()
    messages.success(request, f"Your {label} is archived — hidden from discovery, but every document and report stays intact. Reactivate anytime.")
    return redirect('usersettings:home')


@login_required
@require_POST
def unarchive_profile(request):
    profile, label = _get_role_profile(request.user)
    if not profile:
        messages.error(request, "No profile found to reactivate.")
        return redirect('usersettings:home')
    profile.unarchive()
    messages.success(request, f"Your {label} is active again and visible in discovery.")
    return redirect('usersettings:home')


@login_required
def delete_profile_confirm(request):
    profile, label = _get_role_profile(request.user)
    if not profile:
        messages.error(request, "No profile found to delete.")
        return redirect('usersettings:home')

    if request.method == "POST":
        profile.delete()
        messages.success(request, "Your profile has been permanently deleted.")
        return redirect('accounts:choose_role')

    return render(request, 'usersettings/delete_profile_confirm.html', {
        'role_label': label,
        'company_name': getattr(profile, 'company_name', None),
    })


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

    elevator_pitch = None
    if pitch_video_profile:
        elevator_pitch = ProfileVideo.objects.filter(
            kind=ProfileVideo.KIND_ELEVATOR_PITCH,
            **{pitch_video_role: pitch_video_profile},
        ).first()

    role_profile, role_label = _get_role_profile(request.user)

    return render(request, "usersettings/settings.html", {
        "user_settings": user_settings,
        "dm_enabled": dm_enabled,
        "is_private": is_private,
        "pitch_video_profile": pitch_video_profile,
        "pitch_video_role": pitch_video_role,
        "elevator_pitch": elevator_pitch,
        "role_profile": role_profile,
        "role_label": role_label,
    })


@login_required
@require_POST
def update_username(request):
    new_username = (request.POST.get('username') or '').strip()
    User = get_user_model()

    if not new_username:
        messages.error(request, "Username can't be blank.")
        return redirect('usersettings:home')

    if new_username == request.user.username:
        return redirect('usersettings:home')

    try:
        UnicodeUsernameValidator()(new_username)
    except ValidationError:
        messages.error(request, "Usernames can only contain letters, numbers, and @/./+/-/_ characters.")
        return redirect('usersettings:home')

    if User.objects.filter(username__iexact=new_username).exclude(pk=request.user.pk).exists():
        messages.error(request, f'"{new_username}" is already taken. Please choose another.')
        return redirect('usersettings:home')

    old_username = request.user.username
    request.user.username = new_username
    request.user.save(update_fields=['username'])
    messages.success(request, f'Your username is now "{new_username}" — your profile link has changed accordingly.')
    return redirect('usersettings:home')


@login_required
@require_POST
def update_profile_picture(request):
    picture = request.FILES.get('profile_picture')
    if not picture:
        messages.error(request, "Please choose an image to upload.")
        return redirect('usersettings:home')

    user_settings = UserSettings.for_user(request.user)
    user_settings.profile_picture = picture
    user_settings.save(update_fields=['profile_picture', 'updated_at'])
    messages.success(request, "Profile picture updated.")
    return redirect('usersettings:home')


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

            if 'pitch_deck' in form.changed_data:
                app.pitch_deck_uploaded_at = timezone.now()

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
