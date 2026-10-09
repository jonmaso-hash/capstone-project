from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .models import PersonProfile
from .professional_forms import PersonProfileForm


@login_required
@require_http_methods(["GET", "POST"])
def edit_professional_profile(request):
    """Separate owner-only editor; does not mutate marketplace applications."""
    profile = PersonProfile.objects.filter(user=request.user).first()
    if request.method == "POST":
        form = PersonProfileForm(request.POST, instance=profile)
        if form.is_valid():
            record = form.save(commit=False)
            record.user = request.user
            record.save()
            messages.success(request, "Professional profile saved.")
            return redirect("accounts:edit_professional_profile")
    else:
        form = PersonProfileForm(instance=profile)
    return render(request, "accounts/edit_professional_profile.html", {"form": form, "education": EducationRecord.objects.filter(person__user=request.user).order_by("-started_on", "-pk"), "relationships": OrganizationRelationship.objects.filter(person__user=request.user).select_related("organization").order_by("-started_on", "-pk")})


from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import EducationRecord, OrganizationRelationship, ProfessionalOrganization
from .professional_forms import EducationRecordForm, OrganizationRelationshipForm


@login_required
@require_http_methods(["GET", "POST"])
def edit_education(request, pk=None):
    profile = PersonProfile.objects.filter(user=request.user).first()
    record = get_object_or_404(EducationRecord, pk=pk, person__user=request.user) if pk else None
    form = EducationRecordForm(request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            person, _ = PersonProfile.objects.get_or_create(user=request.user)
            education = form.save(commit=False)
            education.person = person
            education.save()
        messages.success(request, "Education saved.")
        return redirect("accounts:edit_professional_profile")
    return render(request, "accounts/edit_professional_record.html", {
        "form": form, "section": "Education", "profile": profile,
    })


@login_required
@require_http_methods(["POST"])
def delete_education(request, pk):
    record = get_object_or_404(EducationRecord, pk=pk, person__user=request.user)
    record.delete()
    messages.success(request, "Education removed.")
    return redirect("accounts:edit_professional_profile")


@login_required
@require_http_methods(["GET", "POST"])
def edit_organization_relationship(request, pk=None):
    record = get_object_or_404(OrganizationRelationship, pk=pk, person__user=request.user) if pk else None
    form = OrganizationRelationshipForm(request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            person, _ = PersonProfile.objects.get_or_create(user=request.user)
            # A new private organization record avoids silently editing another user's shared record.
            organization = ProfessionalOrganization.objects.create(
                name=form.cleaned_data["organization_name"],
                website=form.cleaned_data["organization_website"],
            )
            if record:
                old_org = record.organization
            relationship = form.save(commit=False)
            relationship.person = person
            relationship.organization = organization
            relationship.save()
            if record and not old_org.people.exists():
                old_org.delete()
        messages.success(request, "Organization relationship saved.")
        return redirect("accounts:edit_professional_profile")
    return render(request, "accounts/edit_professional_record.html", {
        "form": form, "section": "Organization", "profile": None,
    })


@login_required
@require_http_methods(["POST"])
def delete_organization_relationship(request, pk):
    record = get_object_or_404(OrganizationRelationship, pk=pk, person__user=request.user)
    org = record.organization
    record.delete()
    if not org.people.exists():
        org.delete()
    messages.success(request, "Organization relationship removed.")
    return redirect("accounts:edit_professional_profile")


@require_http_methods(["GET"])
def public_professional_profile(request, username):
    """Opt-in public overview with independently opted-in child records only."""
    from django.contrib.auth import get_user_model
    user = get_object_or_404(get_user_model(), username=username, is_active=True)
    profile = get_object_or_404(PersonProfile, user=user, is_public=True)
    education = EducationRecord.objects.filter(person=profile, is_public=True).order_by("-started_on", "-pk")
    relationships = OrganizationRelationship.objects.filter(person=profile, is_public=True).select_related("organization").order_by("-started_on", "-pk")
    return render(request, "accounts/public_professional_profile.html", {
        "profile": profile, "education": education, "relationships": relationships,
    })
