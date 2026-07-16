from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from django.conf import settings
from django.core.mail import send_mail

from .models import UserReport, Invite, WaitlistEntry, Announcement, BulkEmailLog

User = get_user_model()

# Maps the short role key used in ops URLs to its model — one place to
# extend if a 5th role type is ever added.
ROLE_MODELS = {}


def _role_models():
    """Lazy import to avoid a circular import at module load time."""
    global ROLE_MODELS
    if not ROLE_MODELS:
        from matchmaking.models import Application, InvestorApplication, SellerApplication, BuyerApplication
        ROLE_MODELS = {
            'founder': Application,
            'investor': InvestorApplication,
            'seller': SellerApplication,
            'buyer': BuyerApplication,
        }
    return ROLE_MODELS


def _staff_required(request):
    """Shared staff-only gate — mirrors platform_metrics' inline check
    (matchmaking/views.py) rather than inventing a new decorator."""
    if not request.user.is_staff:
        messages.error(request, "Access to the operations dashboard is restricted to staff.")
        return redirect('pages:home')
    return None


@login_required
def dashboard(request):
    guard = _staff_required(request)
    if guard:
        return guard

    from matchmaking.models import Application, InvestorApplication, SellerApplication, BuyerApplication

    pending_review_count = (
        Application.objects.filter(review_status='PENDING').count()
        + InvestorApplication.objects.filter(review_status='PENDING').count()
        + SellerApplication.objects.filter(review_status='PENDING').count()
        + BuyerApplication.objects.filter(review_status='PENDING').count()
    )
    open_reports_count = UserReport.objects.filter(status='OPEN').count()
    pending_invites_count = Invite.objects.filter(status='PENDING').count()
    waitlist_count = WaitlistEntry.objects.filter(invited=False).count()
    active_announcements_count = Announcement.objects.filter(is_active=True).count()

    return render(request, 'ops/dashboard.html', {
        'pending_review_count': pending_review_count,
        'open_reports_count': open_reports_count,
        'pending_invites_count': pending_invites_count,
        'waitlist_count': waitlist_count,
        'active_announcements_count': active_announcements_count,
        'ops_section': 'dashboard',
    })


# =====================================================================
# 1. USER APPROVAL / VERIFICATION QUEUE
# =====================================================================

@login_required
def verification_queue(request):
    guard = _staff_required(request)
    if guard:
        return guard

    pending_by_role = {
        role: list(model.objects.filter(review_status='PENDING'))
        for role, model in _role_models().items()
    }

    return render(request, 'ops/verification_queue.html', {'pending_by_role': pending_by_role, 'ops_section': 'verification'})


@login_required
@require_POST
def review_action(request, role, profile_id):
    """Approve or deny a profile — mirrors matchmaking/admin.py's
    approve_profiles/deny_profiles actions exactly (same status transitions,
    same denial_reason clearing on approve)."""
    guard = _staff_required(request)
    if guard:
        return guard

    model = _role_models().get(role)
    if not model:
        messages.error(request, "Unknown profile type.")
        return redirect('ops:verification_queue')

    profile = get_object_or_404(model, id=profile_id)
    action = request.POST.get('action')

    if action == 'approve':
        profile.review_status = 'APPROVED'
        profile.denial_reason = ''
        profile.save(update_fields=['review_status', 'denial_reason'])
        messages.success(request, f"Approved {profile}.")
    elif action == 'deny':
        profile.review_status = 'DENIED'
        profile.denial_reason = request.POST.get('denial_reason', '').strip()
        profile.save(update_fields=['review_status', 'denial_reason'])
        messages.success(request, f"Denied {profile}.")
    else:
        messages.error(request, "Unknown action.")

    return redirect('ops:verification_queue')


@login_required
@require_POST
def flag_for_review(request, role, profile_id):
    """Puts a live profile back into the verification queue for a
    staff spot-check — the only path that ever sets review_status='PENDING'
    (nothing does this automatically, so nothing changes for anyone unless
    a staff member acts)."""
    guard = _staff_required(request)
    if guard:
        return guard

    model = _role_models().get(role)
    if not model:
        messages.error(request, "Unknown profile type.")
        return redirect('ops:user_management')

    profile = get_object_or_404(model, id=profile_id)
    profile.review_status = 'PENDING'
    profile.save(update_fields=['review_status'])
    messages.success(request, f"Flagged {profile} for re-review.")
    return redirect('ops:user_management')


# =====================================================================
# 2. REPORTED USERS QUEUE
# =====================================================================

@login_required
def reported_users(request):
    guard = _staff_required(request)
    if guard:
        return guard

    open_reports = UserReport.objects.filter(status='OPEN').select_related('reporter', 'reported_user')
    resolved_reports = UserReport.objects.exclude(status='OPEN').select_related('reporter', 'reported_user')[:50]

    return render(request, 'ops/reported_users.html', {
        'open_reports': open_reports,
        'resolved_reports': resolved_reports,
        'ops_section': 'reports',
    })


@login_required
@require_POST
def resolve_report(request, report_id):
    guard = _staff_required(request)
    if guard:
        return guard

    from django.utils import timezone
    report = get_object_or_404(UserReport, id=report_id)
    action = request.POST.get('action')

    if action in ('resolve', 'dismiss'):
        report.status = 'RESOLVED' if action == 'resolve' else 'DISMISSED'
        report.resolution_notes = request.POST.get('resolution_notes', '').strip()
        report.resolved_by = request.user
        report.resolved_at = timezone.now()
        report.save(update_fields=['status', 'resolution_notes', 'resolved_by', 'resolved_at'])
        messages.success(request, "Report updated.")
    else:
        messages.error(request, "Unknown action.")

    return redirect('ops:reported_users')


@login_required
@require_POST
def submit_user_report(request, username):
    """Public-facing (any logged-in user) — the only path that populates
    the Reported Users queue. Linked from profile.html."""
    reported_user = get_object_or_404(User, username=username)
    reason = request.POST.get('reason', '').strip()

    if reported_user == request.user:
        messages.error(request, "You can't report yourself.")
    elif not reason:
        messages.error(request, "Please describe the issue before submitting a report.")
    else:
        UserReport.objects.create(reporter=request.user, reported_user=reported_user, reason=reason)
        messages.success(request, "Thanks — our team will review this report.")

    return redirect('accounts:profile', username=username)


# =====================================================================
# 3. FEATURED PROFILE MANAGEMENT
# =====================================================================

@login_required
def featured_profiles(request):
    guard = _staff_required(request)
    if guard:
        return guard

    from matchmaking.models import Application, SellerApplication

    search_query = request.GET.get('q', '').strip()

    founders = Application.objects.filter(is_private=False).exclude(review_status='DENIED')
    sellers = SellerApplication.objects.filter(is_private=False).exclude(review_status='DENIED')
    if search_query:
        founders = founders.filter(company_name__icontains=search_query)
        sellers = sellers.filter(company_name__icontains=search_query)

    return render(request, 'ops/featured_profiles.html', {
        'founders': founders.order_by('-is_staff_featured', 'company_name')[:100],
        'sellers': sellers.order_by('-is_staff_featured', 'company_name')[:100],
        'search_query': search_query,
        'ops_section': 'featured',
    })


@login_required
@require_POST
def toggle_featured(request, role, profile_id):
    guard = _staff_required(request)
    if guard:
        return guard

    from matchmaking.models import Application, SellerApplication
    model = {'founder': Application, 'seller': SellerApplication}.get(role)
    if not model:
        messages.error(request, "Featured placement only applies to founders and sellers.")
        return redirect('ops:featured_profiles')

    profile = get_object_or_404(model, id=profile_id)
    profile.is_staff_featured = not profile.is_staff_featured
    profile.save(update_fields=['is_staff_featured'])
    messages.success(request, f"{'Featured' if profile.is_staff_featured else 'Unfeatured'} {profile.company_name}.")
    return redirect('ops:featured_profiles')


# =====================================================================
# 5. MANUAL INTRO CREATION
# =====================================================================

@login_required
def manual_intro_create(request):
    guard = _staff_required(request)
    if guard:
        return guard

    from matchmaking.models import Application, InvestorApplication, SellerApplication, BuyerApplication, Connection, AcquisitionConnection

    if request.method == 'POST':
        intro_type = request.POST.get('intro_type')

        if intro_type == 'founder_investor':
            founder = get_object_or_404(Application, id=request.POST.get('founder_id'))
            investor = get_object_or_404(InvestorApplication, id=request.POST.get('investor_id'))
            conn, created = Connection.objects.get_or_create(
                founder=founder, investor=investor,
                defaults={'initiated_by': 'STAFF', 'notes': 'Created manually by staff.'},
            )
            if created:
                messages.success(request, f"Created intro: {founder.company_name} ↔ {investor.company_name}.")
                from matchmaking.models import log_training_example
                log_training_example('INVESTOR', investor.id, 'FOUNDER', founder.id, 'POSITIVE', 'ops_manual_intro')
            else:
                messages.info(request, f"{founder.company_name} and {investor.company_name} already have a connection.")

        elif intro_type == 'seller_buyer':
            seller = get_object_or_404(SellerApplication, id=request.POST.get('seller_id'))
            buyer = get_object_or_404(BuyerApplication, id=request.POST.get('buyer_id'))
            conn, created = AcquisitionConnection.objects.get_or_create(
                seller=seller, buyer=buyer,
                defaults={'initiated_by': 'STAFF', 'notes': 'Created manually by staff.'},
            )
            if created:
                messages.success(request, f"Created intro: {seller.company_name} ↔ {buyer.company_name}.")
                from matchmaking.models import log_training_example
                log_training_example('BUYER', buyer.id, 'SELLER', seller.id, 'POSITIVE', 'ops_manual_intro')
            else:
                messages.info(request, f"{seller.company_name} and {buyer.company_name} already have a connection.")
        else:
            messages.error(request, "Unknown intro type.")

        return redirect('ops:manual_intro_create')

    return render(request, 'ops/manual_intro_create.html', {
        'founders': Application.objects.exclude(review_status='DENIED').order_by('company_name'),
        'investors': InvestorApplication.objects.exclude(review_status='DENIED').order_by('company_name'),
        'sellers': SellerApplication.objects.exclude(review_status='DENIED').order_by('company_name'),
        'buyers': BuyerApplication.objects.exclude(review_status='DENIED').order_by('company_name'),
        'ops_section': 'manual_intro',
    })


# =====================================================================
# 6. MATCH OVERRIDE TOOLS
# =====================================================================

@login_required
def match_override(request):
    guard = _staff_required(request)
    if guard:
        return guard

    from matchmaking.models import Connection, AcquisitionConnection

    status_filter = request.GET.get('status', '').strip()

    connections = Connection.objects.select_related('founder', 'investor').order_by('-created_at')
    acquisitions = AcquisitionConnection.objects.select_related('seller', 'buyer').order_by('-created_at')
    if status_filter:
        connections = connections.filter(status__iexact=status_filter)
        acquisitions = acquisitions.filter(status__iexact=status_filter)

    return render(request, 'ops/match_override.html', {
        'connections': connections[:100],
        'acquisitions': acquisitions[:100],
        'status_filter': status_filter,
        'ops_section': 'match_override',
    })


@login_required
@require_POST
def override_connection_status(request, conn_type, conn_id):
    guard = _staff_required(request)
    if guard:
        return guard

    from matchmaking.models import Connection, AcquisitionConnection

    model = {'connection': Connection, 'acquisition': AcquisitionConnection}.get(conn_type)
    if not model:
        messages.error(request, "Unknown connection type.")
        return redirect('ops:match_override')

    conn = get_object_or_404(model, id=conn_id)
    new_status = request.POST.get('status', '').strip()
    valid_statuses = {'pending', 'ACCEPTED', 'DECLINED', 'FUNDED', 'CLOSED'}
    if new_status not in valid_statuses:
        messages.error(request, "Invalid status value.")
    else:
        conn.status = new_status
        conn.save(update_fields=['status', 'updated_at'])
        messages.success(request, f"Status overridden to {new_status}.")

        from matchmaking.models import log_training_example
        label = 'POSITIVE' if new_status in ('ACCEPTED', 'FUNDED', 'CLOSED') else ('NEGATIVE' if new_status == 'DECLINED' else None)
        if label:
            if conn_type == 'connection':
                log_training_example('INVESTOR', conn.investor_id, 'FOUNDER', conn.founder_id, label, 'ops_override')
            else:
                log_training_example('BUYER', conn.buyer_id, 'SELLER', conn.seller_id, label, 'ops_override')

    return redirect('ops:match_override')


# =====================================================================
# 7. BULK EMAIL ANNOUNCEMENTS
# =====================================================================

@login_required
def bulk_email(request):
    guard = _staff_required(request)
    if guard:
        return guard

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        audience = request.POST.get('audience', '')

        if not subject or not body or audience not in dict(BulkEmailLog.AUDIENCE_CHOICES):
            messages.error(request, "Subject, body, and a valid audience are all required.")
        else:
            from .tasks import send_bulk_announcement
            log = BulkEmailLog.objects.create(subject=subject, body=body, audience=audience, sent_by=request.user)
            send_bulk_announcement.delay(log.id)
            messages.success(request, f"Sending to {log.get_audience_display()} in the background — check history for the final count.")

        return redirect('ops:bulk_email')

    history = BulkEmailLog.objects.select_related('sent_by')[:50]
    return render(request, 'ops/bulk_email.html', {
        'history': history,
        'audience_choices': BulkEmailLog.AUDIENCE_CHOICES,
        'ops_section': 'bulk_email',
    })


# =====================================================================
# 8. BETA INVITE MANAGEMENT — tracking/outreach only, does not gate signup
# =====================================================================

@login_required
def invite_management(request):
    guard = _staff_required(request)
    if guard:
        return guard

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, "Email is required.")
        else:
            invite = Invite.objects.create(email=email, invited_by=request.user)
            try:
                send_mail(
                    subject="You're invited to Interlink Foundry",
                    message=(
                        f"You've been invited to join Interlink Foundry. "
                        f"Sign up any time at {request.build_absolute_uri('/accounts/signup/')} — "
                        f"reference code {invite.code} if asked."
                    ),
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@interlinkfoundry.com'),
                    recipient_list=[email],
                    fail_silently=True,
                )
            except Exception:
                pass
            messages.success(request, f"Invite sent to {email}.")
        return redirect('ops:invite_management')

    return render(request, 'ops/invite_management.html', {
        'invites': Invite.objects.select_related('invited_by')[:100],
        'ops_section': 'invites',
    })


@login_required
@require_POST
def revoke_invite(request, invite_id):
    guard = _staff_required(request)
    if guard:
        return guard

    invite = get_object_or_404(Invite, id=invite_id)
    invite.status = 'EXPIRED'
    invite.save(update_fields=['status'])
    messages.success(request, f"Revoked invite for {invite.email}.")
    return redirect('ops:invite_management')


# =====================================================================
# 9. WAITLIST MANAGEMENT — tracking/outreach only, does not gate signup
# =====================================================================

@login_required
def waitlist_management(request):
    guard = _staff_required(request)
    if guard:
        return guard

    return render(request, 'ops/waitlist_management.html', {
        'entries': WaitlistEntry.objects.filter(invited=False)[:200],
        'invited_entries': WaitlistEntry.objects.filter(invited=True)[:50],
        'ops_section': 'waitlist',
    })


@login_required
@require_POST
def convert_waitlist_to_invite(request, entry_id):
    guard = _staff_required(request)
    if guard:
        return guard

    from django.utils import timezone
    entry = get_object_or_404(WaitlistEntry, id=entry_id)

    invite = Invite.objects.create(email=entry.email, invited_by=request.user)
    try:
        send_mail(
            subject="You're invited to Interlink Foundry",
            message=(
                f"Thanks for joining the waitlist — you're invited to sign up now at "
                f"{request.build_absolute_uri('/accounts/signup/')} (code {invite.code})."
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@interlinkfoundry.com'),
            recipient_list=[entry.email],
            fail_silently=True,
        )
    except Exception:
        pass

    entry.invited = True
    entry.invited_at = timezone.now()
    entry.save(update_fields=['invited', 'invited_at'])
    messages.success(request, f"Converted {entry.email} to an invite.")
    return redirect('ops:waitlist_management')


# =====================================================================
# 10. PLATFORM ANNOUNCEMENTS
# =====================================================================

@login_required
def announcements_view(request):
    guard = _staff_required(request)
    if guard:
        return guard

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        body = request.POST.get('body', '').strip()
        if not title or not body:
            messages.error(request, "Title and body are required.")
        else:
            Announcement.objects.create(title=title, body=body, created_by=request.user)
            messages.success(request, "Announcement posted.")
        return redirect('ops:announcements')

    return render(request, 'ops/announcements.html', {
        'announcements': Announcement.objects.select_related('created_by')[:100],
        'ops_section': 'announcements',
    })


@login_required
@require_POST
def toggle_announcement(request, announcement_id):
    guard = _staff_required(request)
    if guard:
        return guard

    announcement = get_object_or_404(Announcement, id=announcement_id)
    announcement.is_active = not announcement.is_active
    announcement.save(update_fields=['is_active'])
    messages.success(request, f"{'Activated' if announcement.is_active else 'Deactivated'} \"{announcement.title}\".")
    return redirect('ops:announcements')


# =====================================================================
# 11 & 12. USER MANAGEMENT — impersonation + suspend/disable
# =====================================================================

@login_required
def user_management(request):
    guard = _staff_required(request)
    if guard:
        return guard

    search_query = request.GET.get('q', '').strip()
    users = User.objects.all().order_by('-date_joined')
    if search_query:
        users = users.filter(username__icontains=search_query)

    users = list(users[:100])
    role_models = _role_models()
    for u in users:
        u.role_profiles = []
        for role, model in role_models.items():
            profile = model.objects.filter(user=u).first()
            if profile:
                u.role_profiles.append((role, profile))

    return render(request, 'ops/user_management.html', {
        'users': users,
        'search_query': search_query,
        'ops_section': 'users',
    })


@login_required
@require_POST
def toggle_user_active(request, user_id):
    guard = _staff_required(request)
    if guard:
        return guard

    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        messages.error(request, "You can't suspend your own account.")
    elif target.is_staff:
        messages.error(request, "Staff accounts can't be suspended from here.")
    else:
        target.is_active = not target.is_active
        target.save(update_fields=['is_active'])
        messages.success(request, f"{'Reactivated' if target.is_active else 'Suspended'} {target.username}.")

    return redirect('ops:user_management')


@login_required
@require_POST
def start_impersonation(request, user_id):
    guard = _staff_required(request)
    if guard:
        return guard

    from django.contrib.auth import login
    from .models import ImpersonationLog

    target = get_object_or_404(User, id=user_id)
    if target.is_staff:
        messages.error(request, "Staff accounts can't be impersonated.")
        return redirect('ops:user_management')
    if target == request.user:
        messages.error(request, "You can't impersonate yourself.")
        return redirect('ops:user_management')

    staff_id = request.user.id
    ImpersonationLog.objects.create(impersonator=request.user, target=target)
    # login() flushes the session when switching between two different
    # already-authenticated users (session-fixation protection), so
    # impersonator_id must be set AFTER login(), not before.
    login(request, target, backend='django.contrib.auth.backends.ModelBackend')
    request.session['impersonator_id'] = staff_id
    messages.info(request, f"Viewing as {target.username}.")
    return redirect('accounts:profile', username=target.username)


@login_required
@require_POST
def stop_impersonation(request):
    from django.contrib.auth import login
    from .models import ImpersonationLog
    from django.utils import timezone

    impersonator_id = request.session.get('impersonator_id')
    if not impersonator_id:
        messages.error(request, "You're not currently impersonating anyone.")
        return redirect('pages:home')

    staff_user = get_object_or_404(User, id=impersonator_id)

    log = ImpersonationLog.objects.filter(impersonator=staff_user, target=request.user, ended_at__isnull=True).order_by('-started_at').first()
    if log:
        log.ended_at = timezone.now()
        log.save(update_fields=['ended_at'])

    del request.session['impersonator_id']
    login(request, staff_user, backend='django.contrib.auth.backends.ModelBackend')
    messages.success(request, "Back to your staff account.")
    return redirect('ops:user_management')


# =====================================================================
# 13. REVIEW UPLOADED DOCUMENTS BEFORE THEY'RE VISIBLE
# =====================================================================

@login_required
def document_review(request):
    guard = _staff_required(request)
    if guard:
        return guard

    from zelda_api.vector_models import DocumentSource
    from matchmaking.models import Application, SellerApplication

    documents = DocumentSource.objects.select_related('uploaded_by').order_by('-created_at')[:100]
    decks = Application.objects.exclude(pitch_deck='').exclude(pitch_deck__isnull=True).order_by('-created_at')[:50]
    cims = SellerApplication.objects.exclude(cim_document='').exclude(cim_document__isnull=True).order_by('-created_at')[:50]

    return render(request, 'ops/document_review.html', {
        'documents': documents,
        'decks': decks,
        'cims': cims,
        'ops_section': 'documents',
    })


@login_required
@require_POST
def toggle_profile_document_hidden(request, role, profile_id):
    """Hides a founder's pitch deck/video or a seller's CIM — the other half
    of document review, since these live directly on the profile model
    rather than in zelda_api's DocumentSource pipeline."""
    guard = _staff_required(request)
    if guard:
        return guard

    from matchmaking.models import Application, SellerApplication
    model = {'founder': Application, 'seller': SellerApplication}.get(role)
    if not model:
        messages.error(request, "Unknown profile type.")
        return redirect('ops:document_review')

    profile = get_object_or_404(model, id=profile_id)
    profile.is_hidden_by_staff = not profile.is_hidden_by_staff
    profile.save(update_fields=['is_hidden_by_staff'])
    messages.success(request, f"{'Hid' if profile.is_hidden_by_staff else 'Unhid'} {profile.company_name}'s documents.")
    return redirect('ops:document_review')


@login_required
@require_POST
def toggle_document_hidden(request, document_id):
    guard = _staff_required(request)
    if guard:
        return guard

    from zelda_api.vector_models import DocumentSource

    document = get_object_or_404(DocumentSource, id=document_id)
    document.is_hidden_by_staff = not document.is_hidden_by_staff
    document.save(update_fields=['is_hidden_by_staff'])
    messages.success(request, f"{'Hid' if document.is_hidden_by_staff else 'Unhid'} {document.filename or document.source_entity}.")
    return redirect('ops:document_review')


# =====================================================================
# TRAINING DATA — the deliberately-scoped-down half of the match-feedback
# loop (see MatchTrainingExample's docstring). No training code lives here.
# =====================================================================

@login_required
def training_data(request):
    guard = _staff_required(request)
    if guard:
        return guard

    from django.db.models import Count
    from matchmaking.models import MatchTrainingExample

    by_source = MatchTrainingExample.objects.values('source', 'label').annotate(count=Count('id')).order_by('source', 'label')
    total_count = MatchTrainingExample.objects.count()

    return render(request, 'ops/training_data.html', {
        'by_source': by_source,
        'total_count': total_count,
        'ops_section': 'training_data',
    })


def _resolve_anchor_text(anchor_type, anchor_id):
    """Returns (text, profile) — the profile is needed by _sanitize_for_export
    to know exactly which name/company/email/phone values to redact."""
    from matchmaking.models import InvestorApplication, BuyerApplication
    try:
        if anchor_type == 'INVESTOR':
            profile = InvestorApplication.objects.get(id=anchor_id)
            return profile.investment_thesis_summary or profile.investment_focus, profile
        profile = BuyerApplication.objects.get(id=anchor_id)
        return profile.acquisition_thesis, profile
    except (InvestorApplication.DoesNotExist, BuyerApplication.DoesNotExist):
        return None, None


def _resolve_candidate_text(candidate_type, candidate_id):
    from matchmaking.models import Application, SellerApplication
    try:
        if candidate_type == 'FOUNDER':
            profile = Application.objects.get(id=candidate_id)
            return profile.description, profile
        profile = SellerApplication.objects.get(id=candidate_id)
        return profile.description, profile
    except (Application.DoesNotExist, SellerApplication.DoesNotExist):
        return None, None


def _sanitize_for_export(text, profile):
    """
    Strips PII before free-text pitch/thesis descriptions ever leave this
    view — this JSONL export is meant to eventually feed an offline training
    script, and must be structurally anonymous if it does.

    Two passes: (1) exact substitution of this specific record's own
    name/company/email/phone — precise, since we know exactly what to
    redact from the DB rather than guessing; (2) generic regex patterns as
    a fallback for PII the first pass can't know about (an email/phone/URL
    mentioned in prose that belongs to someone else, e.g. a customer quote).
    """
    import re

    if not text:
        return text

    sanitized = text
    name = getattr(profile, 'full_name', None) or getattr(profile, 'founder_name', None) or getattr(profile, 'seller_name', None)
    company = getattr(profile, 'company_name', None)
    email = getattr(profile, 'email', None)
    phone = getattr(profile, 'phone', None) or getattr(profile, 'phone_number', None)

    for value, token in [(name, '[NAME]'), (company, '[COMPANY]'), (email, '[EMAIL]'), (phone, '[PHONE]')]:
        if value:
            sanitized = re.sub(re.escape(str(value)), token, sanitized, flags=re.IGNORECASE)

    sanitized = re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', '[EMAIL]', sanitized)
    sanitized = re.sub(r'(\+?\d[\d\-\s().]{7,}\d)', '[PHONE]', sanitized)
    sanitized = re.sub(r'https?://\S+', '[URL]', sanitized)
    return sanitized


@login_required
def export_training_data(request):
    guard = _staff_required(request)
    if guard:
        return guard

    import json
    from django.http import HttpResponse
    from matchmaking.models import MatchTrainingExample

    response = HttpResponse(content_type='application/x-ndjson')
    response['Content-Disposition'] = 'attachment; filename="training_examples.jsonl"'

    for example in MatchTrainingExample.objects.all():
        anchor_text, anchor_profile = _resolve_anchor_text(example.anchor_type, example.anchor_id)
        candidate_text, candidate_profile = _resolve_candidate_text(example.candidate_type, example.candidate_id)
        if not anchor_text or not candidate_text:
            continue  # profile was deleted since the example was logged
        response.write(json.dumps({
            'anchor': _sanitize_for_export(anchor_text, anchor_profile),
            'candidate': _sanitize_for_export(candidate_text, candidate_profile),
            'label': example.label,
            'source': example.source,
            'created_at': example.created_at.isoformat(),
        }) + '\n')

    return response


# =====================================================================
# 15. FAILED TASKS — dead-letter view for Celery tasks whose retries were
# exhausted (see ops/models.py::FailedTaskLog / log_failed_task).
# =====================================================================

@login_required
def failed_tasks(request):
    guard = _staff_required(request)
    if guard:
        return guard

    from .models import FailedTaskLog

    return render(request, 'ops/failed_tasks.html', {
        'failures': FailedTaskLog.objects.all()[:200],
        'ops_section': 'failed_tasks',
    })


@login_required
@require_POST
def requeue_failed_task(request, failure_id):
    guard = _staff_required(request)
    if guard:
        return guard

    from celery import current_app
    from .models import FailedTaskLog

    failure = get_object_or_404(FailedTaskLog, id=failure_id)

    try:
        task = current_app.tasks[failure.task_name]
        task.delay(*failure.args_json)
        messages.success(request, f"Requeued {failure.task_name}.")
        failure.delete()
    except KeyError:
        messages.error(request, f"Task '{failure.task_name}' is no longer registered — can't requeue.")
    except Exception as e:
        messages.error(request, f"Requeue failed: {str(e)}")

    return redirect('ops:failed_tasks')


# =====================================================================
# 16. INSIGHT REPORTS — review/publish gate for the quarterly aggregated
# data-drop reports (see growth/tasks.py::generate_quarterly_insight_report).
# Drafts are unpublished until staff approve them here.
# =====================================================================

@login_required
def insight_reports(request):
    guard = _staff_required(request)
    if guard:
        return guard

    from growth.models import PlatformInsightReport

    return render(request, 'ops/insight_reports.html', {
        'reports': PlatformInsightReport.objects.all(),
        'ops_section': 'insight_reports',
    })


@login_required
@require_POST
def toggle_insight_report_published(request, report_id):
    guard = _staff_required(request)
    if guard:
        return guard

    from growth.models import PlatformInsightReport

    report = get_object_or_404(PlatformInsightReport, id=report_id)
    report.is_published = not report.is_published
    report.save(update_fields=['is_published'])
    messages.success(request, f"{'Published' if report.is_published else 'Unpublished'} \"{report.title}\".")
    return redirect('ops:insight_reports')
