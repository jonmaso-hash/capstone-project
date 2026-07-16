from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from matchmaking.models import Application, InvestorApplication
from .models import PlatformInsightReport, ReferralInvite

# Hardcoded rather than trusting a POST-supplied redirect target (open-redirect
# risk) — each source has exactly one legitimate place to send the user back to.
REFERRAL_SOURCE_REDIRECTS = {
    'fundraising_lead': 'matchmaking:fundraising_crm',
    'deal_pulse_portfolio': 'matchmaking:deal_pulse',
}

DIRECTORY_PAGE_SIZE = 12
BADGE_CACHE_TTL = 60 * 60 * 24  # 1 day — keyed by score, so a new memo naturally busts it

BADGE_COLORS = [
    (80, '#2ea44f'),   # green
    (50, '#dfb317'),   # yellow/orange
    (0, '#e05d44'),    # red
]


def _public_queryset(model):
    """
    Same privacy filter already used by every bulletin board in the app
    (founder_bulletin_board, investor_dashboard, etc.) — a pSEO page must
    never surface a profile that toggle wouldn't otherwise show.
    """
    return model.objects.filter(is_private=False).exclude(review_status='DENIED')


def _slug_to_search_text(slug):
    # Matches the existing icontains-filter convention used throughout
    # global_search/founder_bulletin_board/investor_dashboard — not an
    # exact slug registry, just a de-hyphenated substring to search for.
    return slug.replace('-', ' ')


def investor_directory(request, sector_slug, stage_slug, location_slug):
    sector_text = _slug_to_search_text(sector_slug)
    stage_text = _slug_to_search_text(stage_slug)
    location_text = _slug_to_search_text(location_slug)

    investors = _public_queryset(InvestorApplication).filter(
        investment_focus__icontains=sector_text,
        investment_stage__icontains=stage_text,
        location__icontains=location_text,
    ).select_related('user').order_by('-created_at')

    count = investors.count()

    return render(request, 'growth/investor_directory.html', {
        'sector_display': sector_text.title(),
        'stage_display': stage_text.title(),
        'location_display': location_text.title(),
        'count': count,
        'profiles': investors[:DIRECTORY_PAGE_SIZE],
    })


def founder_directory(request, sector_slug, stage_slug, location_slug):
    sector_text = _slug_to_search_text(sector_slug)
    stage_text = _slug_to_search_text(stage_slug)
    location_text = _slug_to_search_text(location_slug)

    founders = _public_queryset(Application).filter(
        sector__icontains=sector_text,
        stage__icontains=stage_text,
        geography__icontains=location_text,
    ).select_related('user').order_by('-created_at')

    count = founders.count()

    return render(request, 'growth/founder_directory.html', {
        'sector_display': sector_text.title(),
        'stage_display': stage_text.title(),
        'location_display': location_text.title(),
        'count': count,
        'profiles': founders[:DIRECTORY_PAGE_SIZE],
    })


def robots_txt(request):
    lines = [
        "User-Agent: *",
        "Allow: /",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def _badge_color(score):
    for threshold, color in BADGE_COLORS:
        if score >= threshold:
            return color
    return BADGE_COLORS[-1][1]


def _render_badge_svg(score):
    color = _badge_color(score)
    label = "Zelda Readiness"
    value = f"{score}/100"
    label_width = 100
    value_width = 55
    total_width = label_width + value_width

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label}: {value}">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,sans-serif" font-size="11">
    <text x="{label_width / 2}" y="14">{label}</text>
    <text x="{label_width + value_width / 2}" y="14">{value}</text>
  </g>
</svg>'''


def readiness_badge(request, role, username):
    """
    Public, unauthenticated SVG badge — no login required, meant to be
    embedded on a founder/seller's own external site or pitch deck via a
    plain <a href="profile"><img src="this"></a> snippet. 404s (rather than
    rendering a broken/misleading badge) for a private profile or for a
    profile with no parseable score yet.
    """
    from zelda_api.vector_models import DocumentSource

    User = get_user_model()
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        raise Http404

    if role == 'founder':
        profile = getattr(user, 'match_founder_profile', None)
    elif role == 'seller':
        profile = getattr(user, 'match_seller_profile', None)
    else:
        raise Http404

    if not profile or profile.is_private or profile.review_status == 'DENIED':
        raise Http404

    score = None
    if role == 'founder':
        doc = DocumentSource.objects.filter(uploaded_by=user, document_type='pitch_deck').order_by('-id').first()
        if doc and hasattr(doc, 'memo'):
            score = doc.memo.readiness_score
    else:
        doc = DocumentSource.objects.filter(uploaded_by=user, document_type='business_valuation').order_by('-id').first()
        if doc and hasattr(doc, 'valuation_report'):
            score = int(round(doc.valuation_report.confidence_score))

    if score is None:
        raise Http404

    cache_key = f"readiness_badge_svg:{role}:{username}:{score}"
    svg = cache.get(cache_key)
    if svg is None:
        svg = _render_badge_svg(score)
        cache.set(cache_key, svg, BADGE_CACHE_TTL)

    return HttpResponse(svg, content_type='image/svg+xml')


@login_required
@require_POST
def create_referral_invite(request):
    """
    Shared by both referral directions — Fundraising CRM (founder invites a
    lead) and Deal Pulse (investor invites a portfolio company) — the only
    difference between them is which source/role_hint gets posted and
    which page to redirect back to.
    """
    invitee_email = request.POST.get('invitee_email', '').strip()
    role_hint = request.POST.get('role_hint', '')
    source = request.POST.get('source', '')

    redirect_target = REFERRAL_SOURCE_REDIRECTS.get(source)
    if not redirect_target:
        raise Http404("Unknown referral source.")

    if not invitee_email or role_hint not in dict(ReferralInvite.ROLE_HINT_CHOICES):
        messages.error(request, "An email address is required to send an invite.")
        return redirect(redirect_target)

    invite = ReferralInvite.objects.create(
        inviter=request.user, invitee_email=invitee_email, role_hint=role_hint, source=source,
    )

    signup_url = request.build_absolute_uri(reverse('accounts:signup')) + f'?ref={invite.code}'
    try:
        send_mail(
            subject=f"{request.user.username} invited you to Interlink Foundry",
            message=(
                f"{request.user.username} thinks you'd be a great fit for Interlink Foundry, "
                f"a private marketplace for founders and investors.\n\nJoin here: {signup_url}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitee_email],
            fail_silently=True,
        )
        messages.success(request, f"Invite sent to {invitee_email}.")
    except Exception:
        messages.warning(request, "Invite created, but the email failed to send.")

    return redirect(redirect_target)


def insights_list(request):
    reports = PlatformInsightReport.objects.filter(is_published=True)
    return render(request, 'growth/insights_list.html', {'reports': reports})


def insights_detail(request, period_slug):
    report = PlatformInsightReport.objects.filter(period_slug=period_slug, is_published=True).first()
    if not report:
        raise Http404
    return render(request, 'growth/insights_detail.html', {'report': report})
