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
    return render(request, "accounts/edit_professional_profile.html", {"form": form})
