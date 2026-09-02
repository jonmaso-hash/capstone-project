# sharing/views.py
"""
Internal + external content sharing — Video/Blog/Job "Share" flow.
Deliberately owns no model: an internal share is a structured Stream
Chat message (content_type/content_id/shared_by custom fields sent
client-side, same as any other chat message — see matchmaking/static/
js/matchmaking.js's ContentShare component and templates/matchmaking/
chat.html's renderMessages), and an external share is just the real
page URL for that content, which already self-enforces its own access
rules on every request.

resolve_share is the one new piece of server logic: given a
content_type + content_id, answer "can the CURRENTLY authenticated user
view this right now" and return a small preview or an "unavailable"
flag. Called both when an internal share card renders in chat (so a
recipient never sees more than they're currently allowed to, regardless
of what was true when the message was sent) and could equally back an
external link's landing behavior later — the check is always about the
requesting viewer, never the original sharer.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse

User = get_user_model()

CONTENT_TYPES = {'PROFILE', 'VIDEO_FOUNDER', 'VIDEO_SELLER', 'BLOG', 'JOB'}


def _resolve_profile(request, content_id):
    """
    content_id is the User's id (a user holds at most one role profile —
    Founder/Investor/Seller/Buyer — so this alone identifies "whose
    profile", unlike video which needs a role-specific id). Available iff
    that role profile currently exists, isn't private, and isn't
    archived — a stricter bar than the profile PAGE's own gate (which
    doesn't block is_private for Investor/Buyer at all, and doesn't
    consider archived_at), by design: a share promises "this is a live,
    good-standing profile," not merely "this URL doesn't 404 for you
    specifically." Deliberately NOT viewer-dependent (unlike video's
    ROLE_ONLY) — a profile is either currently public or it isn't.
    """
    try:
        user = User.objects.get(id=content_id, is_active=True)
    except User.DoesNotExist:
        return None

    for attr, role_label in (
        ('match_founder_profile', 'Founder'), ('match_investor_profile', 'Investor'),
        ('match_seller_profile', 'Seller'), ('match_buyer_profile', 'Buyer'),
    ):
        role_profile = getattr(user, attr, None)
        if not role_profile:
            continue
        if getattr(role_profile, 'is_private', False) or getattr(role_profile, 'archived_at', None):
            return None
        person_name = (
            getattr(role_profile, 'founder_name', None) or getattr(role_profile, 'seller_name', None)
            or getattr(role_profile, 'full_name', None) or user.username
        )
        return {
            'title': person_name,
            'subtitle': f"{role_label} · {role_profile.company_name}" if role_profile.company_name else role_label,
            'view_url': reverse('accounts:profile', kwargs={'username': user.username}),
            'icon': 'profile',
        }
    return None


def _resolve_video_founder(request, content_id):
    from matchmaking.models import Application, can_view_pitch_video
    try:
        application = Application.objects.get(id=content_id)
    except Application.DoesNotExist:
        return None
    if not application.pitch_video or not can_view_pitch_video(request.user, application):
        return None
    return {
        'title': f'{application.company_name or "Untitled Company"} — Pitch Video',
        'subtitle': application.company_name or '',
        'view_url': reverse('accounts:profile', kwargs={'username': application.user.username}),
        'icon': 'video',
    }


def _resolve_video_seller(request, content_id):
    from matchmaking.models import SellerApplication, can_view_pitch_video
    try:
        seller = SellerApplication.objects.get(id=content_id)
    except SellerApplication.DoesNotExist:
        return None
    if not seller.pitch_video or not can_view_pitch_video(request.user, seller):
        return None
    return {
        'title': f'{seller.company_name or "Untitled Business"} — Pitch Video',
        'subtitle': seller.company_name or '',
        'view_url': reverse('accounts:profile', kwargs={'username': seller.user.username}),
        'icon': 'video',
    }


def _resolve_blog(request, content_id):
    from blog.models import Article
    try:
        article = Article.objects.get(id=content_id)
    except Article.DoesNotExist:
        return None
    return {
        'title': article.title,
        'subtitle': article.company_name or (article.author.username if article.author else ''),
        'view_url': article.get_absolute_url(),
        'icon': 'article',
    }


def _resolve_job(request, content_id):
    from jobs.models import JobListing
    try:
        job = JobListing.objects.get(id=content_id)
    except JobListing.DoesNotExist:
        return None
    if not job.is_active or job.is_expired:
        return None
    return {
        'title': job.title,
        'subtitle': job.company_name,
        'view_url': reverse('jobs:detail', kwargs={'pk': job.id}),
        'icon': 'job',
    }


_RESOLVERS = {
    'PROFILE': _resolve_profile,
    'VIDEO_FOUNDER': _resolve_video_founder,
    'VIDEO_SELLER': _resolve_video_seller,
    'BLOG': _resolve_blog,
    'JOB': _resolve_job,
}


@login_required
def resolve_share(request):
    """
    GET /sharing/resolve/?content_type=&content_id=

    Always evaluated against request.user — the person currently looking
    at the share card, never the original sharer. A missing/deleted
    object and a permission failure return the identical {available:
    false} shape on purpose, so a probing client can't distinguish
    "doesn't exist" from "exists but you can't see it."
    """
    content_type = request.GET.get('content_type', '')
    content_id = request.GET.get('content_id', '')

    resolver = _RESOLVERS.get(content_type)
    if not resolver or not content_id.isdigit():
        return JsonResponse({'available': False})

    result = resolver(request, int(content_id))
    if not result:
        return JsonResponse({'available': False})

    return JsonResponse({'available': True, **result})


@login_required
def user_search(request):
    """
    GET /sharing/user-search/?q=

    Mechanical username/company-name lookup for the share picker — no
    Zelda/AI involvement (see ZeldaGlobalSearchAPIView for that, a
    separate concern: "ask a question" vs. "pick a DM recipient"). Only
    the minimum needed to identify who you're sharing with; no email,
    no financial fields, no role-specific data beyond a display label.
    """
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    matches = User.objects.filter(
        Q(username__icontains=query)
        | Q(match_founder_profile__company_name__icontains=query)
        | Q(match_investor_profile__company_name__icontains=query)
        | Q(match_seller_profile__company_name__icontains=query)
        | Q(match_buyer_profile__company_name__icontains=query)
    ).filter(
        is_staff=False, is_superuser=False, is_active=True,
    ).exclude(id=request.user.id).distinct()[:8]

    results = []
    for user in matches:
        if hasattr(user, 'match_founder_profile'):
            display_name = user.match_founder_profile.company_name or user.username
            role_label = 'Founder'
        elif hasattr(user, 'match_investor_profile'):
            display_name = user.match_investor_profile.company_name or user.username
            role_label = 'Investor'
        elif hasattr(user, 'match_seller_profile'):
            display_name = user.match_seller_profile.company_name or user.username
            role_label = 'Seller'
        elif hasattr(user, 'match_buyer_profile'):
            display_name = user.match_buyer_profile.company_name or user.username
            role_label = 'Buyer'
        else:
            display_name = user.username
            role_label = 'Member'

        results.append({
            'id': user.id,
            'username': user.username,
            'display_name': display_name,
            'role_label': role_label,
        })

    return JsonResponse({'results': results})
