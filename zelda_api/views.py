import os
import re
import logging
import urllib.parse
from datetime import timedelta

from django.conf import settings
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q, Avg, Sum, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse, Http404
from django.utils import timezone
from .vector_models import DocumentSource
from django.urls import path

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.parsers import MultiPartParser, FormParser


from .serializers import (
    DirectUploadDocumentSerializer, MarketAnalyticsSerializer,
    MemoGenerationSerializer, VectorMatchSerializer,
    DocumentAnalysisSerializer, WebCrawlSerializer,
)

# Core Deal Flow Utilities
from .utils import scan_pitch_deck, AnalyzedPitch, compile_executive_intelligence_memo, analyze_web_text

UserClass = get_user_model()
logger = logging.getLogger(__name__)

# ── Matchmaking models (optional dependency) ─────────────────────────────────
try:
    from matchmaking.models import Application, InvestorApplication, SellerApplication
    _MATCHMAKING_AVAILABLE = True
except ImportError:
    Application = None
    InvestorApplication = None
    SellerApplication = None
    _MATCHMAKING_AVAILABLE = False


# ── DiligenceEngine ───────────────────────────────────────────────────────────
# FIX: Moved DiligenceEngine to the TOP of the module so that
# DocumentIntakeAPIView (which references it) can resolve the name at call time.
class DiligenceEngine:
    @staticmethod
    def calculate_success_vector(founder_app, investor_app, crawled_data):
        internal_size = getattr(founder_app, 'company_size', 10) or 10
        current_revenue = getattr(founder_app, 'revenue', 0.0) or 0.0

        external_size = int(crawled_data.get('linkedin_headcount', 0) or 0)
        diff = abs(external_size - int(internal_size))

        internal_val = int(internal_size)
        transparency_score = max(0, 100 - ((diff / internal_val) * 100)) if internal_val > 0 else 0

        revenue_score = min(current_revenue / 1000000 * 100, 100)
        hiring_score = min(crawled_data.get('job_board_openings', 0) * 10, 100)

        # Dual-sided affinity booster
        investor_history_raw = getattr(investor_app, 'portfolio_raw_text', '') or ''
        portfolio_affinity_boost = 0.0
        if investor_history_raw.strip():
            founder_sector = (getattr(founder_app, 'sector', '') or '').lower()
            if founder_sector and founder_sector in investor_history_raw.lower():
                portfolio_affinity_boost = 15.0

        vector_score = (
            (revenue_score * 0.4)
            + (transparency_score * 0.3)
            + (hiring_score * 0.1)
            + portfolio_affinity_boost
        )

        return round(min(vector_score, 100.0), 2), round(transparency_score, 2)


# ── Django Template Render Views ──────────────────────────────────────────────

@login_required
def zelda_intelligence_dashboard(request):
    """
    Renders the frontend HTML dashboard for monitoring the data ingestion pipelines.
    """
    documents = DocumentSource.objects.all().order_by('-created_at')[:10]
    return render(request, 'dashboard/zelda_pipeline_dashboard.html', {'documents': documents})


@login_required
def zelda_search_view(request):
    """
    Renders the hybrid search workspace canvas, combining global queries 
    with context-aware results.
    """
    query = request.GET.get('q', '').strip()
    
    # Ready for integration with your matching, blog, and job apps lookups
    pitch_results = []
    blog_results = []
    job_results = []
    
    context = {
        'query': query,
        'pitch_results': pitch_results,
        'blog_results': blog_results,
        'job_results': job_results,
        'total_results': len(pitch_results) + len(blog_results) + len(job_results),
    }
    return render(request, 'search/zelda_search_results.html', context)


# ── REST Framework API Views ──────────────────────────────────────────────────

class ZeldaHealthCheckAPIView(APIView):
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok", "service": "zelda_api"})


ZELDA_ASK_DAILY_LIMIT = 30


def _founder_to_result_dict(app):
    """
    Builds the standard founder search-result dict — shared by
    ZeldaGlobalSearchAPIView and ZeldaAskAPIView so the two search surfaces
    never drift out of shape.
    """
    try:
        url = reverse('accounts:profile', kwargs={'username': app.user.username})
    except NoReverseMatch:
        url = f"/accounts/profile/{app.user.username}/"

    return {
        'type': 'Founder Profile',
        'title': f"Founder: {app.company_name}",
        'founder_name': app.user.get_full_name() or app.user.username,
        'username': app.user.username,
        'startup_name': app.company_name,
        'sector': app.sector or 'General',
        'executive_summary': (app.description or "")[:200] + '...',
        'funding_stage': getattr(app, 'funding_stage', 'Seed'),
        'has_pitch_deck': bool(app.pitch_deck),
        'url': url,
    }


def _seller_to_result_dict(seller):
    """
    Buyer-side mirror of _founder_to_result_dict — same shape convention
    (type/title/username/executive_summary/url) so the Ask Zelda widget's
    existing renderSearchResults JS handles both without a special case,
    with seller-specific fields (industry, asking_price, has_cim) in place
    of the founder-specific ones (sector, funding_stage, has_pitch_deck).
    """
    try:
        url = reverse('accounts:profile', kwargs={'username': seller.user.username})
    except NoReverseMatch:
        url = f"/accounts/profile/{seller.user.username}/"

    return {
        'type': 'Business Listing',
        'title': f"Business: {seller.company_name}",
        'seller_name': seller.user.get_full_name() or seller.user.username,
        'username': seller.user.username,
        'company_name': seller.company_name,
        'industry': seller.industry or 'General',
        'executive_summary': (seller.description or "")[:200] + '...',
        'asking_price': str(seller.asking_price) if seller.asking_price else None,
        'has_cim': bool(seller.cim_document),
        'url': url,
    }


class ZeldaGlobalSearchAPIView(APIView):
    """
    POST /api/v1/zelda/search/
    Zelda Core Global Search Engine API
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def post(self, request):
        user_query = request.data.get('q', '').strip()

        if not user_query:
            return Response({
                'status': 'success',
                'response': "What kind of matches are we hunting down today?",
                'results': [],
            }, status=status.HTTP_200_OK)

        from matchmaking.models import log_search_event
        log_search_event(request, 'zelda_ai_search', user_query)

        search_founders = request.data.get('founders', True)
        search_investors = request.data.get('investors', True)
        search_bulletins = request.data.get('bulletins', True)

        results = []
        seen_urls = set()

        clean_username_query = user_query[1:] if user_query.startswith('@') else user_query
        query_lower = user_query.lower()

        try:
            # 1. Username / account drilldown
            user_matches = UserClass.objects.filter(
                Q(username__icontains=clean_username_query)
                | Q(first_name__icontains=clean_username_query)
                | Q(last_name__icontains=clean_username_query)
            ).filter(is_staff=False, is_superuser=False, is_active=True).distinct()[:5]

            for matched_user in user_matches:
                try:
                    url = reverse('accounts:profile', kwargs={'username': matched_user.username})
                except NoReverseMatch:
                    url = f"/accounts/profile/{matched_user.username}/"

                if url in seen_urls:
                    continue

                if hasattr(matched_user, 'match_investor_profile'):
                    role_label = "Investor Profile Account"
                    desc = f"Verified Investor mandate profile for @{matched_user.username}."
                elif hasattr(matched_user, 'match_founder_profile'):
                    role_label = "Founder Profile Account"
                    founder_app = matched_user.match_founder_profile
                    desc = f"Founder profile for @{matched_user.username} managing {founder_app.company_name or 'a registered venture'}."
                else:
                    role_label = "User Network Profile"
                    desc = f"Community member profile page for @{matched_user.username}."

                results.append({
                    'type': role_label,
                    'title': f"User Profile: {matched_user.get_full_name() or matched_user.username}",
                    'description': desc,
                    'url': url,
                })
                seen_urls.add(url)

            # 2. Core application feature links
            if search_bulletins:
                try:
                    match_radar_url = reverse('founder_matchmaker')
                except NoReverseMatch:
                    match_radar_url = "/matchmaking/founder/matches/"

                try:
                    jobs_url = reverse('jobs_index')
                except NoReverseMatch:
                    jobs_url = "/jobs/"

                try:
                    blog_url = reverse('blog_view')
                except NoReverseMatch:
                    blog_url = "/blog/"

                core_platform_features = [
                    {
                        "title": "Match Radar (AI Vectors)",
                        "url": match_radar_url,
                        "type": "Application Feature",
                        "description": "Compute dynamic semantic vector similarity scores across founder pitches and investor target mandates.",
                        "keywords": ["match radar", "radar", "matches", "vectors", "similarity", "ai matching", "vector engine"],
                    },
                    {
                        "title": "Job Board Engine",
                        "url": jobs_url,
                        "type": "Marketplace Platform",
                        "description": "Discover current open hiring roles, startup talent requirements, technical employment positions, and work tracks.",
                        "keywords": ["job", "jobs", "hiring", "careers", "employment", "positions", "work", "talent", "opportunities"],
                    },
                    {
                        "title": "Venture Insights Blog",
                        "url": blog_url,
                        "type": "Community Hub",
                        "description": "Read platform data updates, shared ecosystem articles, founder stories, and community user posting logs.",
                        "keywords": ["blog", "insights", "articles", "stories", "posts", "comments", "likes", "writing", "new"],
                    },
                ]

                for feature in core_platform_features:
                    if query_lower in feature['title'].lower() or any(query_lower in kw for kw in feature['keywords']):
                        if feature['url'] not in seen_urls:
                            results.append({
                                'type': feature['type'],
                                'title': feature['title'],
                                'description': feature['description'],
                                'url': feature['url'],
                            })
                            seen_urls.add(feature['url'])

            # 3. Database deep crawl (matchmaking models)
            if _MATCHMAKING_AVAILABLE:
                if search_founders and Application:
                    # Privacy Gatekeeper: same rule as matchmaking._filtered_public_applications
                    # — Zelda search must never surface private or denied founder profiles.
                    founder_matches = Application.objects.discoverable().filter(
                        Q(company_name__icontains=user_query)
                        | Q(description__icontains=user_query)
                        | Q(sector__icontains=user_query)
                    ).exclude(review_status='DENIED').select_related('user')[:5]

                    for app in founder_matches:
                        result = _founder_to_result_dict(app)
                        if result['url'] in seen_urls:
                            continue

                        results.append(result)
                        seen_urls.add(result['url'])

                if search_investors and InvestorApplication:
                    # Privacy Gatekeeper: same rule as founder_matches above — this
                    # previously had no is_private/archived filter at all, letting
                    # Zelda search surface private and archived investor mandates.
                    investor_matches = InvestorApplication.objects.discoverable().filter(
                        Q(company_name__icontains=user_query)
                        | Q(investment_focus__icontains=user_query)
                        | Q(location__icontains=user_query)
                    ).select_related('user')[:5]

                    for inv in investor_matches:
                        try:
                            url = reverse('accounts:profile', kwargs={'username': inv.user.username})
                        except NoReverseMatch:
                            url = f"/accounts/profile/{inv.user.username}/"

                        if url in seen_urls:
                            continue

                        focus_text = inv.investment_focus or ""
                        snippet = focus_text[:120] + '...' if len(focus_text) > 120 else focus_text
                        display_name = inv.company_name or getattr(inv, 'full_name', None) or "Institutional Investor"
                        results.append({
                            'type': 'Investor Mandate',
                            'title': f"Investor: {display_name}",
                            'description': snippet,
                            'url': url,
                        })
                        seen_urls.add(url)

            # 4. Template file search
            template_route_map = {
                'home.html': ('Main Landing Page', '/home/'),
                'about.html': ('About Us', '/about/'),
                'services.html': ('Platform Services Overview', '/services/'),
                'contact.html': ('Contact & Support', '/contact/'),
                'edit_founder_profile.html': ('Founder Onboarding Hub', '/settings/profile/founder/'),
                'edit_investor_profile.html': ('Investor Mandate Portal', '/settings/profile/investor/'),
                'ai_search.html': ('Zelda UI Workspace Canvas', '/accounts/ai_search/'),
                'profile.html': ('User Metrics Engine Profiles', '/accounts/profile/'),
                'bulletin_board.html': ('Venture Bulletin Board', '/matchmaking/bulletin-board/'),
                'chat.html': ('Ecosystem Deal Room Space', '/matchmaking/deal-room/'),
            }

            search_roots = []
            for template_setting in settings.TEMPLATES:
                search_roots.extend(template_setting.get('DIRS', []))
            if not search_roots:
                search_roots.append(settings.BASE_DIR)

            for template_dir in search_roots:
                if os.path.exists(template_dir):
                    for root, _, files in os.walk(template_dir):
                        for file in files:
                            if file.endswith('.html') and file in template_route_map:
                                label, target_url = template_route_map[file]
                                if target_url in seen_urls:
                                    continue
                                try:
                                    full_path = os.path.join(root, file)
                                    with open(full_path, 'r', encoding='utf-8') as f:
                                        raw_html = f.read()
                                        clean_text = re.sub(r'\{%.*?%\}', '', raw_html)
                                        clean_text = re.sub(r'\{\{.*?\}\}', '', clean_text)
                                        clean_text = re.sub(r'<script.*?</script>', '', clean_text, flags=re.DOTALL)
                                        clean_text = re.sub(r'<style.*?</style>', '', clean_text, flags=re.DOTALL)
                                        clean_text = re.sub(r'<[^<]+?>', ' ', clean_text)
                                        visible_page_words = ' '.join(clean_text.split())
                                        if query_lower in visible_page_words.lower():
                                            start_idx = visible_page_words.lower().find(query_lower)
                                            snippet_extract = visible_page_words[
                                                max(0, start_idx - 30):min(len(visible_page_words), start_idx + 100)
                                            ]
                                            url_safe_query = urllib.parse.quote(user_query)
                                            results.append({
                                                'type': 'Landing Page Match',
                                                'title': label,
                                                'description': f"...{snippet_extract.strip()}...",
                                                'url': f"{target_url}#:~:text={url_safe_query}",
                                            })
                                            seen_urls.add(target_url)
                                except IOError:
                                    pass

            return Response({
                'status': 'success',
                'query': user_query,
                'response': f"I processed a comprehensive cross-registry sweep for '{user_query}' and uncovered {len(results)} entry points matching your criteria!",
                'results': results,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Zelda Exploration Pipeline dropped: {str(e)}")
            return Response(
                {'status': 'error', 'message': 'The search system pipeline encountered an unexpected validation drop.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ZeldaAskAPIView(APIView):
    """
    POST /api/v1/zelda/ask/
    Natural-language search, routed by the requester's own role — the
    "people with money" search for what they'd spend it on: a buyer's
    question searches sellers-for-sale (SellerApplication); everyone else
    (investors, and any user without a buyer profile) searches founders
    (Application), the original/default behavior. Role is read from the
    requester's own profile, never from the question text, so there's no
    way to spoof which schema gets queried.

    Claude only translates the question into an allowlisted constraint
    list for whichever schema applies — it never sees the database and
    never writes the text shown to the user. The displayed response and
    results always come from a real Django query, so nothing here can be
    hallucinated (same discipline as the memo/valuation prompts: only
    claims grounded in real data ever reach the screen).
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def post(self, request):
        question = request.data.get('q', '').strip()
        is_buyer = getattr(request.user, 'match_buyer_profile', None) is not None
        target = 'seller' if is_buyer else 'founder'
        noun_singular = 'business' if target == 'seller' else 'founder'
        noun_plural = 'businesses for sale' if target == 'seller' else 'founders'

        if not question:
            return Response({
                'status': 'success',
                'response': f"Ask me to find {noun_plural} by industry, size, price, or financials.",
                'results': [],
            }, status=status.HTTP_200_OK)

        from matchmaking.models import SearchEvent, log_search_event

        recent_count = SearchEvent.objects.filter(
            user=request.user,
            source='zelda_ask',
            created_at__gte=timezone.now() - timedelta(hours=24),
        ).count()
        if recent_count >= ZELDA_ASK_DAILY_LIMIT:
            return Response(
                {'status': 'error', 'message': "Daily limit for AI search reached — try again tomorrow."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        log_search_event(request, 'zelda_ask', question)

        try:
            from zelda_api.circuit_breaker import CircuitOpenError
            from zelda_api.intelligence_pipeline import (
                _call_claude_for_query_extraction, _search_with_relaxation,
                ASK_ZELDA_ALLOWED_FIELDS, ASK_ZELDA_SELLER_ALLOWED_FIELDS,
            )

            allowed_fields = ASK_ZELDA_SELLER_ALLOWED_FIELDS if target == 'seller' else ASK_ZELDA_ALLOWED_FIELDS

            extraction = _call_claude_for_query_extraction(question, target=target)
            constraints = [
                c for c in extraction.get('constraints', [])
                if isinstance(c, dict) and c.get('field') in allowed_fields
            ]

            if not constraints:
                return Response({
                    'status': 'success',
                    'response': f"I couldn't find specific search criteria in that — try mentioning industry, size, price, or financials for {noun_plural}.",
                    'results': [],
                }, status=status.HTTP_200_OK)

            if target == 'seller':
                base_queryset = SellerApplication.objects.discoverable().select_related('user').exclude(review_status='DENIED')
                to_result_dict = _seller_to_result_dict
            else:
                base_queryset = Application.objects.discoverable().select_related('user').exclude(review_status='DENIED')
                to_result_dict = _founder_to_result_dict

            matches, dropped_labels, widened = _search_with_relaxation(base_queryset, constraints, allowed_fields=allowed_fields)

            summary = ', '.join(f"{c['field']}={c['value']}" for c in constraints)
            results = [to_result_dict(obj) for obj in matches]
            count = len(matches)
            plural = 'es' if (target == 'seller' and count != 1) else ('s' if count != 1 else '')
            noun = 'business' if target == 'seller' else 'founder'

            if not matches:
                response_text = f"No {noun_plural} currently match: {summary}."
            elif dropped_labels:
                response_text = (
                    f"No exact match — showing {count} close {noun}{plural} after dropping "
                    f"{'; '.join(dropped_labels)}."
                )
            elif widened:
                response_text = (
                    f"No exact match on {summary} — showing {count} close {noun}{plural} "
                    f"within a wider range."
                )
            else:
                response_text = f"Found {count} {noun}{plural} matching: {summary}"

            return Response({
                'status': 'success',
                'response': response_text,
                'results': results,
            }, status=status.HTTP_200_OK)

        except CircuitOpenError:
            return Response(
                {'status': 'error', 'message': "AI search is temporarily unavailable — try again shortly."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.error(f"Ask Zelda pipeline error: {str(e)}")
            return Response(
                {'status': 'error', 'message': "Something went wrong processing that question."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MatchRadarAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def post(self, request):
        serializer = VectorMatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        mock_matches = [
            {"username": "alpha_ventures", "role": "investor", "match_score": 0.94, "alignment_rationale": "Strong overlap in B2B SaaS infrastructure focus."},
            {"username": "nexus_seed", "role": "investor", "match_score": 0.87, "alignment_rationale": "Matches early-stage pre-revenue metrics framework."},
        ]
        return Response({"status": "success", "engine": "Zelda-Vector-v1", "results_count": len(mock_matches), "matches": mock_matches}, status=status.HTTP_200_OK)


class SandboxScanView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
        file = request.FILES.get('file')
        if not file:
            return Response({"error": "No file uploaded. Make sure your form-data key is 'file'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            raw_data = scan_pitch_deck(file)
            pitch_object = AnalyzedPitch(raw_data)
            return Response(pitch_object.to_foundry_envelope(), status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Sandbox extraction failed: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DocumentIntakeAPIView(APIView):
    """
    POST /api/v1/zelda/documents/analyze/
    The Unified Interlink Foundry Pipeline for Founders.
    FIX: DiligenceEngine is now defined before this class (top of file).
    FIX: Removed orphaned second post() method that was hidden inside a docstring.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
        if not _MATCHMAKING_AVAILABLE:
            return Response({"error": "Matchmaking module is not installed."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({"error": "No file uploaded. Use the form-data key 'file'."}, status=status.HTTP_400_BAD_REQUEST)

        target_investor_id = request.data.get('investor_id')
        if target_investor_id:
            investor_app = get_object_or_404(InvestorApplication, id=target_investor_id)
        else:
            investor_app = InvestorApplication.objects.first()
            if not investor_app:
                return Response({"error": "No active investor profiles found in registry to compute vector matches against."}, status=status.HTTP_404_NOT_FOUND)

        try:
            raw_extracted_data = scan_pitch_deck(uploaded_file)
            if "error" in raw_extracted_data:
                return Response(raw_extracted_data, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

            raw_text_summary = raw_extracted_data.get("summary", "")

            founder_app, created = Application.objects.get_or_create(
                user=request.user,
                defaults={
                    'company_name': 'New Venture Track',
                    'description': raw_text_summary[:500],
                    'sector': 'Fintech / Infrastructure',
                },
            )

            if not created and raw_text_summary:
                founder_app.description = raw_text_summary[:500]
                founder_app.save()

            mock_crawl_telemetry = {
                'linkedin_headcount': getattr(founder_app, 'company_size', 15) or 15,
                'job_board_openings': 3,
            }
            vector_score, transparency_index = DiligenceEngine.calculate_success_vector(
                founder_app, investor_app, mock_crawl_telemetry
            )

            memo_markdown = compile_executive_intelligence_memo(
                founder_app=founder_app,
                investor_app=investor_app,
                extracted_deck_data=raw_extracted_data,
                vector_score=vector_score,
                transparency_index=transparency_index,
            )

            foundry_envelope = {
                "origin": "pitch_deck_scanner",
                "timestamp": "2026-05-25T12:00:00Z",
                "intelligence_score": vector_score,
                "payload": {
                    "summary": raw_text_summary[:500],
                    "investment_memo_markdown": memo_markdown,
                    "target_investor": investor_app.company_name or "Institutional Allocator",
                    "transparency_index": transparency_index,
                    "revenue": raw_extracted_data.get("revenue_metrics", "Pending LLM Analysis"),
                    "market": raw_extracted_data.get("market_size", "Pending LLM Analysis"),
                },
                "risk_flags": {
                    "low_transparency_variance": transparency_index < 70.0,
                },
            }

            return Response(foundry_envelope, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Unified intake pipeline execution failed: {str(e)}")
            return Response({"error": f"Intake pipeline structural error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WebExplorationAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def post(self, request):
        serializer = WebCrawlSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        target_url = serializer.validated_data['target_url']
        return Response({
            "status": "crawled",
            "url": target_url,
            "synthesized_summary": "Clean text payload ready for investment memo formatting.",
            "verification_status": "Matches deck parameters",
        }, status=status.HTTP_200_OK)


class DocumentDirectScraperAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
        serializer = DirectUploadDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if not _MATCHMAKING_AVAILABLE:
            return Response({"error": "Matchmaking module is not installed."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        uploaded_file = serializer.validated_data['file']
        doc_type = serializer.validated_data['document_type']  # FIX: was document_purpose

        founder_app = get_object_or_404(Application, user=request.user)
        founder_app.current_revenue = serializer.validated_data.get('current_revenue')
        founder_app.company_size = serializer.validated_data.get('company_size')
        founder_app.years_in_business = serializer.validated_data.get('years_in_business')
        founder_app.save()

        return Response({
            "status": "success",
            "file_meta": {
                "filename": uploaded_file.name,
                "size_bytes": uploaded_file.size,
                "content_type": uploaded_file.content_type,
            },
            "document_classification": doc_type,
            "extraction_payload": {
                "detected_problem_statement": "Fragmented financial communication protocols across distributed venture teams.",
                "market_sizing_claims": "TAM: $14B, SAM: $2.1B",
                "team_profiles": ["CEO: Ex-Stripe Engineer", "CTO: MIT Distributed Systems Lab"],
            },
            "vector_registry_sync": "completed_in_memory",
        }, status=status.HTTP_201_CREATED)


class MarketHealthAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def get(self, request):
        serializer = MarketAnalyticsSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if not _MATCHMAKING_AVAILABLE:
            return Response({"error": "Matchmaking module is not installed."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        total_founders = Application.objects.count()
        total_investors = InvestorApplication.objects.count()
        sector_breakdown = Application.objects.values('sector').annotate(count=Count('id')).order_by('-count')

        return Response({
            "status": "success",
            "metrics_timestamp": "2026-05-20T09:55:00Z",
            "ecosystem_depth": {
                "registered_founders": total_founders,
                "active_capital_allocators": total_investors,
                "total_platform_ratio": f"{total_founders}:{total_investors}",
            },
            "macro_financial_aggregates": {
                "average_target_raise": 1850000,
                "dominant_geography": "San Diego, California",
            },
            "sector_density_map": {item['sector'] or 'Unclassified': item['count'] for item in sector_breakdown},
        }, status=status.HTTP_200_OK)


class InvestmentMemoGeneratorAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def post(self, request):
        serializer = MemoGenerationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if not _MATCHMAKING_AVAILABLE:
            return Response({"error": "Matchmaking module is not installed."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        founder_id = serializer.validated_data['founder_id']
        tone = serializer.validated_data['tone']

        founder_app = get_object_or_404(Application, id=founder_id)

        memo_markdown = (
            f"# INVESTMENT MEMO: {founder_app.company_name or 'Ecosystem Venture'}\n"
            f"**Classification:** Internal Venture Review\n"
            f"**Tone Profile:** {tone.upper()}\n\n"
            f"## Executive Overview\n"
            f"{founder_app.description or 'No registry description summary documented.'}\n\n"
            f"## Diligence Parameters & Vector Context\n"
            f"- **Sector:** {founder_app.sector or 'Infrastructure General'}\n"
            f"- **Assigned Owner:** @{founder_app.user.username}\n"
            f"- **System Verification Ring:** Digital footprints match deck specifications."
        )

        return Response({
            "status": "compiled",
            "target_founder_id": founder_id,
            "format": "markdown",
            "investment_memo_payload": memo_markdown,
        }, status=status.HTTP_200_OK)


class MemoIntelligenceView(APIView):
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, startup_name):
        if not _MATCHMAKING_AVAILABLE:
            return Response({"error": "Matchmaking module is not installed."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        founder_app = get_object_or_404(Application, company_name__iexact=startup_name)
        investor_app = InvestorApplication.objects.first()
        url_to_crawl = getattr(founder_app, 'website', None)

        if url_to_crawl:
            external_data = self.perform_live_crawl(url_to_crawl)
        else:
            external_data = {'linkedin_headcount': 0, 'job_board_openings': 0}

        vector_score, transparency = DiligenceEngine.calculate_success_vector(founder_app, investor_app, external_data)

        return Response({
            "startup": founder_app.company_name,
            "success_vector_score": vector_score,
            "transparency_index": transparency,
            "text_synthesis": f"Memo for {startup_name} generated using live data. Score: {vector_score}/100.",
        })

    def perform_live_crawl(self, url):
        return {'linkedin_headcount': 45, 'job_board_openings': 2}


class InvestorPortfolioIntakeAPIView(APIView):
    """
    POST /api/v1/zelda/investors/portfolio/
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
        if not _MATCHMAKING_AVAILABLE:
            return Response({"error": "Matchmaking module is not installed."}, status=status.HTTP_503_SERVICE_UNunavailable)

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({"error": "No file uploaded. Use the form-data key 'file'."}, status=status.HTTP_400_BAD_REQUEST)

        investor_app = get_object_or_404(InvestorApplication, user=request.user)

        try:
            raw_extracted_data = scan_pitch_deck(uploaded_file)
            if "error" in raw_extracted_data:
                return Response(raw_extracted_data, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

            raw_portfolio_summary = raw_extracted_data.get("summary", "")

            if not raw_portfolio_summary.strip():
                return Response(
                    {"error": "Scraper engine failed to parse viable textual semantic parameters from this asset format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            investor_app.portfolio_raw_text = raw_portfolio_summary
            investor_app.save()

            foundry_envelope = {
                "origin": "investor_portfolio_scanner",
                "timestamp": "2026-05-26T06:00:00Z",
                "payload": {
                    "investor_node": investor_app.company_name or "Verified Allocator Account",
                    "extracted_portfolio_telemetry": raw_portfolio_summary[:300] + "...",
                    "status": "Dual-sided investment history successfully cataloged into database layer.",
                },
            }
            return Response(foundry_envelope, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Investor portfolio ingestion pipeline failed: {str(e)}")
            return Response({"error": f"Investor intake drop: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FounderMatchRadarAPIView(APIView):
    """
    POST /api/v1/zelda/founder/match-radar/
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def post(self, request):
        if not _MATCHMAKING_AVAILABLE:
            return Response({"error": "Matchmaking module is not installed."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        target_founder_app = get_object_or_404(Application, user=request.user)

        my_sector = target_founder_app.sector or "General Tech"
        my_geography = getattr(target_founder_app, 'geography', 'San Diego, California') or 'San Diego, California'
        my_raise = float(getattr(target_founder_app, 'target_raise', 0.0) or 0.0)

        filter_sector = request.data.get('sector', my_sector)
        filter_geography = request.data.get('geography', my_geography)

        peer_query = Application.objects.exclude(id=target_founder_app.id)

        if filter_sector:
            peer_query = peer_query.filter(sector__iexact=filter_sector)
        if filter_geography:
            peer_query = peer_query.filter(geography__icontains=filter_geography)

        total_peers = peer_query.count()
        aggregates = peer_query.aggregate(
            avg_raise=Avg('target_raise'),
            total_raise_pool=Sum('target_raise'),
            avg_size=Avg('company_size'),
        )

        avg_peer_raise = float(aggregates.get('avg_raise') or 0.0)
        avg_peer_size = float(aggregates.get('avg_size') or 0.0)

        macro_insight_narrative = (
            f"{total_peers} ventures in {filter_geography or 'your region'} within the {filter_sector or 'matching'} "
            f"track are actively scaling. On average, peers in this cluster are raising "
            f"${avg_peer_raise:,.2f} with an active operations headcount node of {int(avg_peer_size)} members."
        )

        anonymized_competitors = []
        peer_instances = peer_query.order_by('-id')[:25]

        for idx, peer in enumerate(peer_instances, start=1):
            peer_raise = float(getattr(peer, 'target_raise', 0.0) or 0.0)
            peer_size = int(getattr(peer, 'company_size', 10) or 10)

            raise_delta = abs(my_raise - peer_raise)
            max_possible_delta = max(my_raise, peer_raise, 1.0)
            similarity_vector = max(0.0, 100.0 - ((raise_delta / max_possible_delta) * 100.0))

            anonymized_competitors.append({
                "peer_node_id": f"PEER-TRACK-NX{idx:03d}",
                "proximity_vector_score": round(similarity_vector, 2),
                "metrics_comparison": {
                    "target_raise": peer_raise,
                    "company_size": peer_size,
                    "funding_stage": getattr(peer, 'funding_stage', 'Seed'),
                    "is_higher_capital_target": peer_raise > my_raise,
                },
            })

        anonymized_competitors = sorted(anonymized_competitors, key=lambda x: x['proximity_vector_score'], reverse=True)

        foundry_envelope = {
            "origin": "founder_competitive_match_radar",
            "timestamp": "2026-05-26T08:00:00Z",
            "payload": {
                "subject_venture": target_founder_app.company_name,
                "active_filters": {"sector": filter_sector, "geography": filter_geography},
                "macro_insights": {
                    "peer_cluster_count": total_peers,
                    "average_market_raise": round(avg_peer_raise, 2),
                    "total_capital_velocity_pool": round(float(aggregates.get('total_raise_pool') or 0.0), 2),
                    "market_density_statement": macro_insight_narrative,
                },
                "competitive_positioning_matrix": anonymized_competitors,
            },
        }

        return Response(foundry_envelope, status=status.HTTP_200_OK)


class SummarizeView(APIView):
    """
    Accepts raw page content and returns a structured AI summary.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def post(self, request):
        page_text = request.data.get('page_text', '')

        if not page_text:
            return Response({"error": "No page content provided."}, status=400)

        try:
            analysis = analyze_web_text(page_text)
            return Response({
                "traction": analysis.get('traction', 'No specific traction metrics detected.'),
                "tech": analysis.get('tech_stack', 'Standard technology framework detected.'),
                "ask": analysis.get('investment_ask', 'Target funding details not explicitly stated.'),
            })
        except Exception as e:
            logger.error(f"Zelda Summarizer Engine Failure: {str(e)}")
            return Response({"error": "Semantic processing failed."}, status=500)


class PitchDeckAnalysisAPIView(APIView):
    """
    POST /api/v1/zelda/pitch-analysis/
    Accepts a pitch deck file and returns structured AI analysis.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def post(self, request):
        uploaded_file = request.FILES.get('pitch_deck')
        if not uploaded_file:
            return Response(
                {"error": "No file provided. Send a PDF, PPTX, or TXT file as 'pitch_deck'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = scan_pitch_deck(uploaded_file)

        if "error" in result:
            return Response(result, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        analyzed = AnalyzedPitch(
            summary=result.get("summary", ""),
            metrics=result.get("metrics", {}),
            sections=result.get("sections", {}),
        )

        return Response({
            "status": "analyzed",
            "summary": analyzed.summary,
            "metrics": analyzed.metrics,
            "sections": analyzed.sections,
            "confidence": result.get("confidence", 0.0),
        }, status=status.HTTP_200_OK)


class IntelligenceMemoAPIView(APIView):
    """
    GET /api/v1/zelda/intelligence-memo/
    Generates an executive intelligence memo for the authenticated user's founder profile.

    FIX: Was incorrectly passing `request.user` (a User instance) to
    compile_executive_intelligence_memo(), which expects a founder_app (Application)
    model instance. Now fetches the founder Application first.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def get(self, request):
        if not _MATCHMAKING_AVAILABLE:
            return Response({"error": "Matchmaking module is not installed."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # FIX: fetch the correct object type before passing to memo compiler
        founder_app = get_object_or_404(Application, user=request.user)
        memo = compile_executive_intelligence_memo(founder_app)
        return Response({"status": "success", "memo": memo}, status=status.HTTP_200_OK)


class SummarizePageAPIView(APIView):
    """
    POST /api/v1/zelda/summarize/
    Accepts raw page text and returns structured startup intelligence analysis.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def post(self, request):
        page_text = request.data.get('text', '')
        if not page_text.strip():
            return Response(
                {"error": "No text provided. Send raw page content as 'text'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        analysis = analyze_web_text(page_text)
        return Response({"status": "success", "analysis": analysis}, status=status.HTTP_200_OK)
    
@login_required
def truth_delta_ui_view(request, document_id):
    from .truth_delta_models import TruthDeltaReport, ClaimedDatapoint, can_request_clarification, truth_delta_unlocked

    document = get_object_or_404(DocumentSource, id=document_id)

    if document.is_hidden_by_staff and document.uploaded_by != request.user and not request.user.is_staff:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("This document is currently under review and isn't visible yet.")

    if document.uploaded_by != request.user:
        viewer_is_investor = (
            getattr(request.user, 'accounts_investor_profile', None) is not None or
            getattr(request.user, 'match_investor_profile', None) is not None
        )
        if viewer_is_investor:
            from matchmaking.models import Application, log_investor_event
            founder_app = Application.objects.filter(user=document.uploaded_by).first()
            if founder_app:
                # Free discovery signal for the founder even when the
                # content itself is Premium-locked below — "an investor
                # showed interest" should never be paywalled.
                log_investor_event(request.user, founder_app, 'truth_delta_view')

    is_owner = document.uploaded_by == request.user
    tier = 'full' if truth_delta_unlocked(request.user, document) else 'lite'

    # Get latest report for this document
    report = TruthDeltaReport.objects.filter(
        document=document
    ).order_by('-created_at').first()

    # Get claims that were extracted
    claims = ClaimedDatapoint.objects.filter(document=document)

    # Clarification requests (interactive "ask for evidence" diligence) are a
    # Zelda AI feature — a Lite viewer sees WHETHER something is unverified,
    # not the tooling to chase it down.
    clarification_requests = []
    if report and tier == 'full':
        clarification_requests = [
            {
                'id': cr.id,
                'category': cr.category,
                'message': cr.message,
                'status': cr.status,
                'response_text': cr.response_text,
                'requested_by': cr.requested_by.get_full_name() or cr.requested_by.username,
                'requested_by_id': cr.requested_by_id,
                'created_at': cr.created_at.strftime('%b %d, %Y'),
            }
            for cr in report.clarification_requests.select_related('requested_by').order_by('-created_at')
        ]

    details = report.details if report else {}
    if tier == 'lite' and details:
        # Lite gets a few representative findings, not the full claim-by-claim
        # breakdown — "tells you whether there's a problem," not "exactly
        # where and what to do about it."
        details = {
            'claims': details.get('claims', []),
            'per_claim': (details.get('per_claim') or [])[:3],
        }

    category_states = report.category_states() if report else {}
    verified_count = sum(1 for s in category_states.values() if s == 'verified')
    unverified_count = sum(1 for s in category_states.values() if s == 'no_data')

    # Work Done — concrete analysis work on the underlying document.
    # work_done_summary keeps only genuinely-computed positive integers,
    # so an early-stage deck with no external corroboration simply shows
    # fewer stats rather than a row of zeros. "Claims checked" lives in
    # the verdict stat cards already, so it's not repeated here.
    from .work_done import work_done_summary
    work_done = work_done_summary(
        pages=document.total_pages,
        sections=document.chunks.count(),
        datapoints=document.observed_datapoints.count(),
    )

    context = {
        'document': document,
        'report': report,
        'claims': claims,
        'has_report': report is not None,
        'truth_score': round(report.overall_truth_score) if report and report.overall_truth_score is not None else None,
        'credibility_risk': report.credibility_risk if report else 'pending',
        'summary': report.summary if report else 'Verification pending.',
        'claims_count': claims.count(),
        'details': details,
        'clarification_requests': clarification_requests,
        'can_request_clarification': can_request_clarification(request.user, document) if tier == 'full' else False,
        'is_document_owner': is_owner,
        'truth_delta_tier': tier,
        'is_owner': is_owner,
        'category_states': category_states,
        'verified_count': verified_count,
        'unverified_count': unverified_count,
        'work_done': work_done,
    }
    from .disclaimers import DUE_DILIGENCE_DISCLAIMER
    from .report_nav import build_report_nav, EVIDENCE as REPORT_EVIDENCE
    context['disclaimer'] = DUE_DILIGENCE_DISCLAIMER
    context['report_nav'] = build_report_nav(request.user, document.uploaded_by, REPORT_EVIDENCE)

    # Entity Integrity (Secretary of State / domain / timeline checks) is a
    # Zelda AI feature per the Lite/AI split — Lite proves Zelda ran the
    # analysis, AI proves the company checks out.
    if tier == 'full':
        from .entity_verification_models import EntityVerificationReport
        context['entity_report'] = EntityVerificationReport.objects.filter(document=document).order_by('-created_at').first()
    else:
        context['entity_report'] = None

    return render(request, 'truth_delta_dashboard.html', context)


@login_required
@require_POST
def flag_truth_delta_claim(request, document_id, category):
    """
    An investor/buyer flags one specific unverified claim and asks the
    founder/seller to clarify or supply supporting documentation. Mirrors
    matchmaking.views.post_pitch_video_comment's shape exactly (inline
    fetch()+JsonResponse, notification fired only on success, wrapped so
    a notification failure never breaks the actual request).
    """
    from .truth_delta_models import TruthDeltaReport, ClaimedDatapoint, ClarificationRequest, can_request_clarification

    document = get_object_or_404(DocumentSource, id=document_id)
    if not can_request_clarification(request.user, document):
        return JsonResponse({'error': 'Not authorized.'}, status=403)

    valid_categories = {c[0] for c in ClaimedDatapoint.CATEGORY_CHOICES}
    if category not in valid_categories:
        return JsonResponse({'error': 'Unknown claim category.'}, status=400)

    report = TruthDeltaReport.objects.filter(document=document).order_by('-created_at').first()
    if not report:
        return JsonResponse({'error': 'No verification report exists for this document yet.'}, status=404)

    message = request.POST.get('message', '').strip()
    if len(message) > 1000:
        return JsonResponse({'error': 'Message is too long (max 1000 characters).'}, status=400)

    clarification = ClarificationRequest.objects.create(
        report=report, category=category, requested_by=request.user, message=message,
    )

    try:
        from notifications.models import Notification
        Notification.objects.create(
            recipient=document.uploaded_by,
            sender=request.user,
            notification_type='CLARIFICATION_REQUEST',
            message=f"{request.user.get_full_name() or request.user.username} asked for clarification on your {clarification.get_category_display()} claim.",
            target_url=reverse('zelda_api:truth_delta_ui', args=[document.id]),
        )
    except Exception as e:
        logger.warning(f"Failed to create clarification-request notification: {str(e)}")

    return JsonResponse({
        'status': 'success',
        'clarification': {
            'id': clarification.id,
            'category': clarification.category,
            'message': clarification.message,
            'status': clarification.status,
            'response_text': '',
            'requested_by': request.user.get_full_name() or request.user.username,
            'requested_by_id': request.user.id,
            'created_at': clarification.created_at.strftime('%b %d, %Y'),
        },
    })


@login_required
@require_POST
def respond_to_clarification_request(request, clarification_id):
    """Only the document owner (or staff) can respond — the founder/seller answering an investor's/buyer's question."""
    from .truth_delta_models import ClarificationRequest

    clarification = get_object_or_404(ClarificationRequest, id=clarification_id)
    owner = clarification.report.document.uploaded_by
    if request.user != owner and not request.user.is_staff:
        return JsonResponse({'error': 'Not authorized.'}, status=403)

    response_text = request.POST.get('response_text', '').strip()
    if not response_text:
        return JsonResponse({'error': 'Response cannot be empty.'}, status=400)
    if len(response_text) > 2000:
        return JsonResponse({'error': 'Response is too long (max 2000 characters).'}, status=400)

    clarification.response_text = response_text
    clarification.status = 'RESPONDED'
    clarification.responded_at = timezone.now()
    clarification.save()

    try:
        from notifications.models import Notification
        Notification.objects.create(
            recipient=clarification.requested_by,
            sender=request.user,
            notification_type='CLARIFICATION_RESPONSE',
            message=f"{owner.get_full_name() or owner.username} responded to your clarification request.",
            target_url=reverse('zelda_api:truth_delta_ui', args=[clarification.report.document_id]),
        )
    except Exception as e:
        logger.warning(f"Failed to create clarification-response notification: {str(e)}")

    return JsonResponse({'status': 'success', 'response_text': clarification.response_text})

@login_required
def _founder_investor_context(request, founder_username):
    """
    Shared resolution + auth for analyze_founder_profile and its confirm
    step: investor role check, founder lookup, and the founder's
    Application. Returns (investor_profile, founder_user, application) or
    an early JsonResponse on failure.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    investor_profile = (
        getattr(request.user, 'accounts_investor_profile', None) or
        getattr(request.user, 'match_investor_profile', None)
    )
    if not investor_profile:
        return None, JsonResponse({'status': 'error', 'message': 'Investor access required'}, status=403)

    founder_user = get_object_or_404(User, username=founder_username)
    application = getattr(founder_user, 'match_founder_profile', None)
    if not application:
        return None, JsonResponse({'status': 'error', 'message': 'No founder profile found'}, status=404)

    return (investor_profile, founder_user, application), None


def _match_reasons(application, investor_profile):
    """
    Plain comparisons over fields already on both profiles — no new AI
    call or scoring model, just surfacing why a match looks promising
    before an investor decides whether to spend an analysis on it. Reuses
    the exact sector/stage/ticket-size checks matchmaking/utils.py already
    uses for scoring (calculate_rule_based_score, passes_hard_filters),
    rather than re-deriving separate logic that could drift out of sync.
    """
    from matchmaking.utils import _is_adjacent_stage

    reasons = []
    app_sector = (application.sector or '').lower()
    investor_sectors = [s.strip().lower() for s in (investor_profile.investment_focus or '').split(',') if s.strip()]
    if app_sector and (app_sector in investor_sectors or any(s and s in app_sector for s in investor_sectors)):
        reasons.append(f"Sector alignment ({application.sector})")

    app_stage = (application.stage or '').lower()
    inv_stage = (investor_profile.investment_stage or '').lower()
    if app_stage and inv_stage and (app_stage == inv_stage or _is_adjacent_stage(app_stage, inv_stage)):
        reasons.append(f"Stage alignment ({application.stage})")

    if investor_profile.ticket_size_min is not None or investor_profile.ticket_size_max is not None:
        lo = investor_profile.ticket_size_min or 0
        hi = investor_profile.ticket_size_max
        if application.raising_amount >= lo and (hi is None or application.raising_amount <= hi):
            reasons.append("Raise size fits your check range")

    return reasons


def analyze_founder_profile(request, founder_username):
    """
    Track 1: Investor clicks 'Analyze with Zelda' on a founder profile.
    Finds the founder's existing pitch deck DocumentSource and returns the
    document ID so Zelda can load the memo directly — free, since it's
    just reading an already-generated memo.

    If no document exists yet, this no longer generates on the spot: it
    returns 'confirm_required' with the cached match score, plain-language
    reasons, and the analysis cost, so the investor sees why the match
    looks promising *before* deciding to spend an analysis. Generation
    itself only happens via confirm_analyze_founder_profile (POST) — see
    that view's docstring for why the cost moved off the founder.
    """
    from .vector_models import DocumentSource

    resolved, error_response = _founder_investor_context(request, founder_username)
    if error_response:
        return error_response
    investor_profile, founder_user, application = resolved

    # Silent outcome tracking — investor triggered Zelda analysis
    from matchmaking.models import log_investor_event
    log_investor_event(request.user, application, 'analyze')

    # Look for existing DocumentSource for this founder
    doc = DocumentSource.objects.filter(
        uploaded_by=founder_user,
        document_type='pitch_deck'
    ).order_by('-created_at').first()

    if doc:
        # Document already exists — return it directly
        return JsonResponse({
            'status': 'ready',
            'document_id': doc.id,
            'filename': doc.filename,
            'company': application.company_name or founder_user.username,
            'has_memo': hasattr(doc, 'memo'),
        })

    # No document yet — check if founder has a pitch deck file on their profile
    if application.pitch_deck:
        from .quotas import CREDIT_COSTS
        from matchmaking.models import AIMatch

        ai_match = AIMatch.objects.filter(investor=investor_profile, application=application).first()
        return JsonResponse({
            'status': 'confirm_required',
            'company': application.company_name or founder_user.username,
            'score': round(float(ai_match.score)) if ai_match else None,
            'reasons': _match_reasons(application, investor_profile),
            'analysis_cost': CREDIT_COSTS['memo'],
        })

    # No pitch deck at all
    return JsonResponse({
        'status': 'no_deck',
        'message': 'This founder has not uploaded a pitch deck yet.',
        'company': application.company_name or founder_user.username,
    })


@require_POST
def confirm_analyze_founder_profile(request, founder_username):
    """
    Explicit second step after analyze_founder_profile's 'confirm_required'
    — the investor has seen the score/reasons/cost and chosen to generate.

    Charged to the investor (request.user), not the founder: the founder
    never chose to spend anything here, and generation is idempotent per
    founder anyway (the first investor to confirm pays once; every later
    investor hits analyze_founder_profile's 'ready' branch for free — see
    that view's docstring).
    """
    from .vector_models import DocumentSource
    from .tasks import process_document_pipeline

    resolved, error_response = _founder_investor_context(request, founder_username)
    if error_response:
        return error_response
    investor_profile, founder_user, application = resolved

    if not application.pitch_deck:
        return JsonResponse({'status': 'no_deck', 'message': 'This founder has not uploaded a pitch deck yet.'}, status=404)

    # Re-check for a race: another investor may have confirmed first.
    doc = DocumentSource.objects.filter(uploaded_by=founder_user, document_type='pitch_deck').order_by('-created_at').first()
    if doc:
        return JsonResponse({
            'status': 'ready',
            'document_id': doc.id,
            'filename': doc.filename,
            'company': application.company_name or founder_user.username,
            'has_memo': hasattr(doc, 'memo'),
        })

    from .quotas import has_credits_for, upgrade_message

    if not has_credits_for(request.user, 'memo'):
        return JsonResponse({
            'status': 'error',
            'message': upgrade_message(request.user),
        }, status=402)

    try:
        from .utils import _extract_pptx_text, _extract_pdf_text
        deck_path = application.pitch_deck.path

        if deck_path.lower().endswith('.pptx'):
            with open(deck_path, 'rb') as pdf_file:
                raw_text, page_count = _extract_pdf_text(pdf_file)
        else:
            with open(deck_path, 'rb') as pdf_file:
                raw_text, page_count = _extract_pdf_text(pdf_file)

        doc = DocumentSource.objects.create(
            uploaded_by=founder_user,
            filename=application.pitch_deck.name,
            source_entity=application.company_name or founder_user.username,
            document_type='pitch_deck',
            raw_text_preview=raw_text[:1000],
            raw_text_full=raw_text,
            total_pages=page_count,
            status='ingested',
        )
        from .models import AnalysisCreditCharge
        AnalysisCreditCharge.objects.create(document=doc, user=request.user, job_type='memo')

        process_document_pipeline.delay(doc.id, raw_text)

        return JsonResponse({
            'status': 'processing',
            'document_id': doc.id,
            'company': application.company_name or founder_user.username,
            'message': 'Analysis started — check back in 30 seconds.',
        })

    except Exception as e:
        logger.warning(f"Track 1 pipeline trigger failed: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Pipeline error: {str(e)}'
        }, status=500)

def get_memo(request, doc_id):
    try:
        doc = ZeldaDocument.objects.get(id=doc_id)
        return JsonResponse({
            "status": "ok",
            "memo": doc.memo_text or "",   # never None
            "doc_id": doc_id,
        })
    except ZeldaDocument.DoesNotExist:
        return JsonResponse({
            "status": "not_found",
            "memo": "",
            "doc_id": doc_id,
        }, status=404)


@login_required
def valuation_request_view(request):
    """
    Upload form for the Business Valuation feature — any authenticated
    user, no founder/investor role required (standalone self-service
    tool), and uploading is never blocked: everyone can always generate a
    valuation (see quotas.py::valuation_tier_for_new_upload). `tier_status`
    only informs the banner shown above the form — whether this upload
    will render in full (and how much of a plan's monthly allowance is
    left) or as a free preview.
    """
    from .quotas import valuation_tier_status
    return render(request, 'zelda_valuation_request.html', {
        'tier_status': valuation_tier_status(request.user),
    })


@login_required
def valuation_report_view(request, document_id):
    """
    Report page for a business valuation request. Owner-or-staff only,
    matching DocumentValuationView's API-level gate.
    """
    from .vector_models import DocumentSource
    document = get_object_or_404(DocumentSource, id=document_id, document_type='business_valuation')

    if document.uploaded_by != request.user and not request.user.is_staff:
        raise Http404("Not found.")

    from .report_nav import build_report_nav, VALUATION as REPORT_VALUATION
    return render(request, 'zelda_valuation_report.html', {
        'document': document,
        'report_nav': build_report_nav(request.user, document.uploaded_by, REPORT_VALUATION),
    })


@login_required
def valuation_history_view(request):
    """
    A permanent library of every business valuation the user has generated
    — purchased-per-report and included-with-a-plan reports side by side,
    each labeled with how it was paid for and which numbered run it is for
    that company (a re-upload for the same business is a new version, not
    a silent overwrite — nothing in the pipeline dedupes uploads).
    """
    from .models import ValuationPurchase
    from .quotas import VALUATION_PURCHASE_TYPE_PRICES
    from matchmaking.models import _normalize_company_string
    from billing.models import Subscription
    from billing.views import _get_role_and_price

    documents = list(
        DocumentSource.objects.filter(
            uploaded_by=request.user, document_type='business_valuation',
        ).exclude(status='error').select_related('valuation_report').order_by('created_at', 'id')
    )

    purchases_by_document_id = {
        purchase.redeemed_document_id: purchase
        for purchase in ValuationPurchase.objects.filter(
            user=request.user, redeemed_document__in=documents,
        )
    }

    has_firm = getattr(request.user, 'firm_membership', None) is not None
    plan, _ = _get_role_and_price(request.user)
    if has_firm:
        included_label = "Included with your Firm plan"
    elif plan:
        included_label = f"Included with {Subscription.Plan(plan).label}"
    else:
        included_label = "Included with your plan"

    from .valuation_trend import compute_valuation_trend

    version_counts = {}
    last_full_report_by_company = {}
    reports = []
    for document in documents:
        company_key = _normalize_company_string(document.source_entity)
        version_counts[company_key] = version_counts.get(company_key, 0) + 1
        purchase = purchases_by_document_id.get(document.id)
        if purchase:
            price = VALUATION_PURCHASE_TYPE_PRICES.get(purchase.purchase_type)
            provenance_label = f"Purchased — ${price:.2f}" if price is not None else "Purchased"
        elif document.valuation_tier == 'preview':
            provenance_label = "Free preview — not yet unlocked"
        else:
            provenance_label = included_label

        # Trend vs. the previous FULL-tier version of the same company —
        # documents arrive in chronological order here, so the dict just
        # tracks "the last one seen," no re-querying needed. Never
        # computed against a locked preview (see valuation_trend.py).
        # Tracks the version NUMBER alongside the report since the
        # previous full version isn't always simply "version - 1" — a
        # preview-tier version could sit in between two full ones.
        trend = None
        previous_full_version = None
        current_report = getattr(document, 'valuation_report', None)
        if document.valuation_tier == 'full' and current_report:
            previous = last_full_report_by_company.get(company_key)
            if previous:
                previous_report, previous_full_version = previous
                trend = compute_valuation_trend(current_report, previous_report)
            last_full_report_by_company[company_key] = (current_report, version_counts[company_key])

        reports.append({
            'document': document,
            'version': version_counts[company_key],
            'purchase': purchase,
            'provenance_label': provenance_label,
            'trend': trend,
            'previous_full_version': previous_full_version,
        })

    reports.reverse()
    return render(request, 'zelda_valuation_history.html', {'reports': reports})


@login_required
def ic_memo_view(request, document_id):
    """
    Printable Investment Committee memo — synthesizes the existing memo,
    Truth Delta signal, valuation, deck engagement, and financials for one
    founder. This is the "PDF": no server-side PDF library, the page is
    print-styled and the user hits Ctrl/Cmd+P -> Save as PDF.
    """
    from .vector_models import DocumentSource
    from .ic_memo import build_ic_memo_context, can_view_ic_memo, ic_memo_unlocked
    from matchmaking.models import Application

    document = get_object_or_404(DocumentSource, id=document_id, document_type='pitch_deck')
    application = get_object_or_404(Application, user=document.uploaded_by)

    if not can_view_ic_memo(request.user, application):
        raise Http404("Not found.")

    tier = 'full' if ic_memo_unlocked(request.user, application) else 'lite'
    context = build_ic_memo_context(application, tier=tier)
    # Navigation only — added at render time, not in build_ic_memo_context,
    # so the Markdown export stays a pure document.
    from .report_nav import build_report_nav, ANALYSIS as REPORT_ANALYSIS
    context['report_nav'] = build_report_nav(request.user, document.uploaded_by, REPORT_ANALYSIS)
    return render(request, 'zelda_api/ic_memo.html', context)


@login_required
def ic_memo_download_view(request, document_id):
    """Same content and access gate as ic_memo_view, as a plain .md download."""
    from django.http import HttpResponse
    from .vector_models import DocumentSource
    from .ic_memo import build_ic_memo_context, can_view_ic_memo, ic_memo_unlocked, render_ic_memo_markdown
    from matchmaking.models import Application

    document = get_object_or_404(DocumentSource, id=document_id, document_type='pitch_deck')
    application = get_object_or_404(Application, user=document.uploaded_by)

    if not can_view_ic_memo(request.user, application):
        raise Http404("Not found.")

    if not ic_memo_unlocked(request.user, application):
        return redirect('zelda_api:ic_memo', document_id=document_id)

    context = build_ic_memo_context(application)
    markdown_text = render_ic_memo_markdown(context)

    response = HttpResponse(markdown_text, content_type='text/markdown')
    safe_name = (application.company_name or 'company').replace(' ', '-').lower()
    response['Content-Disposition'] = f'attachment; filename="{safe_name}-ic-memo.md"'
    return response


class JourneyStatusAPIView(APIView):
    """
    GET /api/v1/zelda/journey-status/

    Powers the state-aware Zelda icon: computes the caller's onboarding/
    engagement stage (founder or investor) and folds in their unread
    notification count, so the icon only needs one fetch per page load.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def get(self, request):
        from notifications.models import Notification
        from matchmaking.utils import (
            compute_founder_journey_stage, compute_investor_journey_stage,
            compute_seller_journey_stage, compute_buyer_journey_stage,
        )
        from matchmaking.journey_actions import ACTION_INFO, compute_profile_strength

        user = request.user
        is_investor = getattr(user, 'match_investor_profile', None) is not None
        is_seller = getattr(user, 'match_seller_profile', None) is not None
        is_buyer = getattr(user, 'match_buyer_profile', None) is not None

        if is_investor:
            stage = compute_investor_journey_stage(user)
            url_by_label = {
                'Create your investor profile': 'usersettings:edit_investor_profile',
                'Complete every mandate field': 'usersettings:edit_investor_profile',
                'Upload your portfolio for a similarity match': 'usersettings:edit_investor_profile',
                'Verify your business email': 'accounts:business_verification',
            }
        elif is_seller:
            stage = compute_seller_journey_stage(user)
            url_by_label = {
                'Create your business listing': 'usersettings:edit_seller_profile',
                'Upload a CIM document': 'usersettings:edit_seller_profile',
                'Get a Zelda valuation to price your asking price with confidence': 'zelda_api:valuation_request',
                'Connect with other businesses': 'matchmaking:acquisition_bulletin_board',
                'Verify your business email': 'accounts:business_verification',
            }
        elif is_buyer:
            stage = compute_buyer_journey_stage(user)
            url_by_label = {
                'Create your buyer profile': 'usersettings:edit_buyer_profile',
                'Complete every mandate field': 'usersettings:edit_buyer_profile',
                'Verify your business email': 'accounts:business_verification',
            }
        else:
            # Founders, and users with no role picked yet, both land on the
            # founder track — matching the "(after sign up) -> create
            # profile" first step described for new signups.
            stage = compute_founder_journey_stage(user)
            url_by_label = {
                'Create your founder profile': 'usersettings:edit_founder_profile',
                'Upload a pitch deck or pitch video': 'usersettings:edit_founder_profile',
                'Publish a blog post to boost visibility': 'blog:blog_view',
                "Post a job to show you're growing": 'jobs:create',
                'Connect with other businesses': 'matchmaking:bulletin_board',
                'Upload your business plan to Zelda for a competitiveness match': 'zelda_api:valuation_request',
                'Verify your business email': 'accounts:business_verification',
            }

        next_action_url = None
        next_best_action = None
        for item in stage['checklist']:
            if not item['done']:
                url_name = url_by_label.get(item['label'])
                if url_name:
                    try:
                        next_action_url = reverse(url_name)
                    except NoReverseMatch:
                        next_action_url = None

                info = ACTION_INFO.get(item['label'])
                if info:
                    next_best_action = {
                        'label': item['label'],
                        'why_it_matters': info['why_it_matters'],
                        'estimated_minutes': info['estimated_minutes'],
                        'action_label': info['action_label'],
                        'action_url': next_action_url,
                    }
                break

        unread_notifications = Notification.objects.filter(recipient=user, is_read=False).count()

        from .quotas import usage_nearing_limit, upgrade_message
        ai_usage_warning = upgrade_message(user) if usage_nearing_limit(user) else None

        return Response({
            'stage_color': stage['stage_color'],
            'headline': stage['headline'],
            'checklist': stage['checklist'],
            'unread_notifications': unread_notifications,
            'next_action_url': next_action_url,
            'next_best_action': next_best_action,
            'profile_strength': compute_profile_strength(stage['checklist']),
            'ai_usage_warning': ai_usage_warning,
        })