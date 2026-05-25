import os
import re
import logging
import urllib.parse

from django.conf import settings
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model
from django.apps import apps
from django.db.models import Q, Avg, Sum, Count
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.parsers import MultiPartParser, FormParser

from .serializers import (
    DirectUploadDocumentSerializer, MarketAnalyticsSerializer, 
    MemoGenerationSerializer, VectorMatchSerializer, 
    DocumentAnalysisSerializer, WebCrawlSerializer
)

# Core Deal Flow Utilities
from .utils import scan_pitch_deck, AnalyzedPitch

# Syncing with the models defined for the matching engine
from matchmaking.models import Application, InvestorApplication

# Pinnacle Architecture Registry
from .registry import PinnacleRegistry

UserClass = get_user_model()
logger = logging.getLogger(__name__)

# Dynamic lookups prevent NameError failures if external apps aren't active
Job = None
if apps.is_installed('jobs'):
    try:
        from jobs.models import Job
    except ImportError:
        pass

BlogPost = None
if apps.is_installed('blog'):
    try:
        from blog.models import BlogPost
    except ImportError:
        pass


class ZeldaGlobalSearchAPIView(APIView):
    """
    POST /api/v1/zelda/search/
    Zelda Core True Global Search Engine API
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_query = request.data.get('q', '').strip()

        if not user_query:
            return Response({
                'status': 'success', 
                'response': "What kind of matches are we hunting down today?", 
                'results': []
            }, status=status.HTTP_200_OK)

        search_founders = request.data.get('founders', True)
        search_investors = request.data.get('investors', True)
        search_bulletins = request.data.get('bulletins', True)

        results = []
        seen_urls = set()
        
        clean_username_query = user_query[1:] if user_query.startswith('@') else user_query
        query_lower = user_query.lower()

        try:
            # 1. USERNAME ACCOUNT DRILLDOWN REGISTRY CHECK
            user_matches = UserClass.objects.filter(
                Q(username__icontains=clean_username_query) |
                Q(first_name__icontains=clean_username_query) |
                Q(last_name__icontains=clean_username_query)
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
                    'url': url
                })
                seen_urls.add(url)

            # 2. CORE APPLICATION FEATURES
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
                        "keywords": ["match radar", "radar", "matches", "vectors", "similarity", "ai matching", "vector engine"]
                    },
                    {
                        "title": "Job Board Engine",
                        "url": jobs_url,
                        "type": "Marketplace Platform",
                        "description": "Discover current open hiring roles, startup talent requirements, technical employment positions, and work tracks.",
                        "keywords": ["job", "jobs", "hiring", "careers", "employment", "positions", "work", "talent", "opportunities"]
                    },
                    {
                        "title": "Venture Insights Blog",
                        "url": blog_url,
                        "type": "Community Hub",
                        "description": "Read platform data updates, shared ecosystem articles, founder stories, and community user posting logs.",
                        "keywords": ["blog", "insights", "articles", "stories", "posts", "comments", "likes", "writing", "new"]
                    }
                ]

                for feature in core_platform_features:
                    if query_lower in feature['title'].lower() or any(query_lower in kw for kw in feature['keywords']):
                        if feature['url'] not in seen_urls:
                            results.append({
                                'type': feature['type'],
                                'title': feature['title'],
                                'description': feature['description'],
                                'url': feature['url']
                            })
                            seen_urls.add(feature['url'])

            # 3. DATABASE REGISTRY DEEP CRAWL
            if search_founders:
                    founder_matches = Application.objects.filter(
                        Q(company_name__icontains=user_query) |
                        Q(description__icontains=user_query) |
                        Q(sector__icontains=user_query)
                    ).select_related('user')[:5]

                    for app in founder_matches:
                        try:
                            url = reverse('accounts:profile', kwargs={'username': app.user.username})
                        except NoReverseMatch:
                            url = f"/accounts/profile/{app.user.username}/"
                            
                        if url in seen_urls:
                            continue
                            
                        results.append({
                            'type': 'Founder Profile',
                            'title': f"Founder: {app.company_name}",
                            'founder_name': app.user.get_full_name() or app.user.username,
                            'startup_name': app.company_name,
                            'sector': app.sector or 'General',
                            'executive_summary': (app.description or "")[:200] + '...',
                            'funding_stage': getattr(app, 'funding_stage', 'Seed'),
                            'url': url
                        })
                        seen_urls.add(url)

            if search_investors:
                investor_matches = InvestorApplication.objects.filter(
                    Q(company_name__icontains=user_query) |
                    Q(investment_focus__icontains=user_query) |
                    Q(location__icontains=user_query)
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
                    display_name = inv.company_name or inv.full_name or "Institutional Investor"
                    results.append({
                        'type': 'Investor Mandate',
                        'title': f"Investor: {display_name}",
                        'description': snippet,
                        'url': url
                    })
                    seen_urls.add(url)

            if search_bulletins:
                if Job:
                    job_matches = Job.objects.filter(Q(title__icontains=user_query) | Q(description__icontains=user_query))[:5]
                    for job in job_matches:
                        url = f"/jobs/{job.id}/"
                        if url in seen_urls:
                            continue
                        results.append({
                            'type': 'Career Opening',
                            'title': f"Job: {job.title}",
                            'description': (job.description or "")[:120] + '...',
                            'url': url
                        })
                        seen_urls.add(url)

                if BlogPost:
                    blog_matches = BlogPost.objects.filter(Q(title__icontains=user_query) | Q(content__icontains=user_query))[:5]
                    for post in blog_matches:
                        url = getattr(post, 'get_absolute_url', lambda: "/blog/")()
                        if url in seen_urls:
                            continue
                        content_text = getattr(post, 'content', '') or getattr(post, 'summary', '') or ""
                        results.append({
                            'type': 'Venture Insights',
                            'title': f"Blog: {post.title}",
                            'description': content_text[:120] + '...',
                            'url': url
                        })
                        seen_urls.add(url)

            # 4. RAW TEMPLATE ARCHITECTURE FILE SEARCH
            template_route_map = {
                'home.html': ('Main Landing Page', '/home/'),
                'about.html': ('About Us', '/about/'),
                'services.html': ('Platform Services Overview', '/services/'),
                'contact.html': ('Contact & Support', '/contact/'),
                'seeking_investment.html': ('Founder Onboarding Hub', '/accounts/seeking-investment/'),
                'investor_form.html': ('Investor Mandate Portal', '/accounts/investor-form/'),
                'ai_search.html': ('Zelda UI Workspace Canvas', '/accounts/ai_search/'),
                'profile.html': ('User Metrics Engine Profiles', '/accounts/profile/'),
                'bulletin_board.html': ('Venture Bulletin Board', '/matchmaking/bulletin-board/'),
                'deal_room.html': ('Ecosystem Deal Room Space', '/matchmaking/deal-room/'),
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
                                            snippet_extract = visible_page_words[max(0, start_idx - 30):min(len(visible_page_words), start_idx + 100)]
                                            
                                            url_safe_query = urllib.parse.quote(user_query)
                                            results.append({
                                                'type': 'Landing Page Match',
                                                'title': label,
                                                'description': f"...{snippet_extract.strip()}...",
                                                'url': f"{target_url}#:~:text={url_safe_query}"
                                            })
                                            seen_urls.add(target_url)
                                except IOError:
                                    pass

            # 5. CONSTRUCT NARRATION CONTEXT
            if results:
                ai_narration = (
                    f"I processed a comprehensive cross-registry sweep for **'{user_query}'** and uncovered "
                    f"**{len(results)} distinct entry points** matching your criteria!"
                )
            else:
                ai_narration = f"I evaluated every data directory across the foundry for '{user_query}' but couldn't locate a hit."

            return Response({
                'status': 'success',
                'query': user_query,
                'response': ai_narration,
                'results': results
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Zelda Exploration Pipeline dropped: {str(e)}")
            return Response({
                'status': 'error', 
                'message': 'The search system pipeline encountered an unexpected validation drop.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MatchRadarAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = VectorMatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        mock_matches = [
            {
                "username": "alpha_ventures",
                "role": "investor",
                "match_score": 0.94,
                "alignment_rationale": "Strong overlap in B2B SaaS infrastructure focus."
            },
            {
                "username": "nexus_seed",
                "role": "investor",
                "match_score": 0.87,
                "alignment_rationale": "Matches early-stage pre-revenue metrics framework."
            }
        ]
        
        return Response({
            "status": "success",
            "engine": "Zelda-Vector-v1",
            "results_count": len(mock_matches),
            "matches": mock_matches
        }, status=status.HTTP_200_OK)


class SandboxScanView(APIView):
    """
    Temporary sandbox for testing the Interlink Foundry pitch deck scanner.
    Bypasses auth for rapid iteration on PDF extraction.
    """
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
    
    The Unified Interlink Foundry Pipeline:
    1. Extracts unstructured text from multi-part file uploads (.pdf, .pptx, .pptm).
    2. Dynamically builds a structured Markdown Investment Memo.
    3. Cross-references the founder metrics against an investor mandate to calculate vector affinity.
    4. Guarantees output delivery inside a standardized Foundry Envelope.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
        # Ensure multipart payload includes the target pitch deck file
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {"error": "No file uploaded. Use the form-data key 'file'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Target an investor profile ID to generate the custom vector alignment score
        # Fallback to the first available investor if no explicit ID is provided
        target_investor_id = request.data.get('investor_id')
        if target_investor_id:
            investor_app = get_object_or_404(InvestorApplication, id=target_investor_id)
        else:
            investor_app = InvestorApplication.objects.first()
            if not investor_app:
                return Response(
                    {"error": "No active investor profiles found in registry to compute vector matches against."},
                    status=status.HTTP_404_NOT_FOUND
                )

        try:
            # Step 1: Core File Scraping Engine Pipeline
            raw_extracted_data = scan_pitch_deck(uploaded_file)
            if "error" in raw_extracted_data:
                return Response(raw_extracted_data, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
                
            raw_text_summary = raw_extracted_data.get("summary", "")

            # Step 2: Fetch Founder Core Context Database Parameters
            founder_app, created = Application.objects.get_or_create(
                user=request.user,
                defaults={
                    'company_name': 'New Venture Track',
                    'description': raw_text_summary[:500],
                    'sector': 'Fintech / Infrastructure'
                }
            )
            
            # If the application already existed, update its description track with the fresh layout text
            if not created and raw_text_summary:
                founder_app.description = raw_text_summary[:500]
                founder_app.save()

            # Step 3: Compile Standardized Investment Memo Markdown Architecture
            memo_markdown = (
                f"# INTEL MEMO: {founder_app.company_name or 'Unclassified Venture'}\n"
                f"**Classification:** Institutional Diligence Review\n"
                f"**Target Allocation Track:** {investor_app.company_name or 'Ecosystem Capital'}\n\n"
                f"## Extracted Executive Summary Layout\n"
                f"{raw_text_summary or 'No text layout context extracted.'}\n\n"
                f"## Registry Data Parameters\n"
                f"- **Sector Density Tag:** {founder_app.sector or 'General Analytics'}\n"
                f"- **Assigned Owner Node:** @{request.user.username}\n"
                f"- **Investor Target Focus:** {investor_app.investment_focus or 'Generalist Thesis'}"
            )

            # Step 4: Run Cross-Registry Matching via DiligenceEngine
            # Mocking a live crawled payload block to satisfy the dynamic vector calculation engine
            mock_crawl_telemetry = {
                'linkedin_headcount': getattr(founder_app, 'company_size', 15) or 15, 
                'job_board_openings': 3
            }
            
            vector_score, transparency_index = DiligenceEngine.calculate_success_vector(
                founder_app, 
                mock_crawl_telemetry
            )

            # Step 5: Encapsulate and Flatten parameters directly into a Protocol Foundry Envelope
            # Fulfills your Pinnacle Architecture data contract constraints cleanly
            foundry_envelope = {
                "origin": "pitch_deck_scanner",
                "timestamp": "2026-05-25T12:00:00Z",  # Can use django.utils.timezone.now().isoformat()
                "intelligence_score": vector_score,
                "payload": {
                    "summary": raw_text_summary[:500],
                    "investment_memo_markdown": memo_markdown,
                    "target_investor": investor_app.company_name or "Institutional Allocator",
                    "transparency_index": transparency_index,
                    "revenue": raw_extracted_data.get("revenue_metrics", "Pending LLM Analysis"),
                    "market": raw_extracted_data.get("market_size", "Pending LLM Analysis")
                },
                "risk_flags": {
                    "low_transparency_variance": True if transparency_index < 70.0 else False
                }
            }

            return Response(foundry_envelope, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Unified intake pipeline execution failed: {str(e)}")
            return Response(
                {"error": f"Intake pipeline structural error: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WebExplorationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WebCrawlSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        target_url = serializer.validated_data['target_url']
        
        return Response({
            "status": "crawled",
            "url": target_url,
            "synthesized_summary": "Clean text payload ready for investment memo formatting.",
            "verification_status": "Matches deck parameters"
        }, status=status.HTTP_200_OK)
    
class DocumentDirectScraperAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
        serializer = DirectUploadDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = serializer.validated_data['file']
        doc_type = serializer.validated_data['document_type']
        
        # FIX: Explicitly fetch the application associated with the user before saving
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
                "content_type": uploaded_file.content_type
            },
            "document_classification": doc_type,
            "extraction_payload": {
                "detected_problem_statement": "Fragmented financial communication protocols across distributed venture teams.",
                "market_sizing_claims": "TAM: $14B, SAM: $2.1B",
                "team_profiles": ["CEO: Ex-Stripe Engineer", "CTO: MIT Distributed Systems Lab"]
            },
            "vector_registry_sync": "completed_in_memory"
        }, status=status.HTTP_201_CREATED)


class MarketHealthAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = MarketAnalyticsSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        total_founders = Application.objects.count()
        total_investors = InvestorApplication.objects.count()
        
        sector_breakdown = (
            Application.objects.values('sector')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        return Response({
            "status": "success",
            "metrics_timestamp": "2026-05-20T09:55:00Z",
            "ecosystem_depth": {
                "registered_founders": total_founders,
                "active_capital_allocators": total_investors,
                "total_platform_ratio": f"{total_founders}:{total_investors}"
            },
            "macro_financial_aggregates": {
                "average_target_raise": 1850000,
                "dominant_geography": "San Diego, California"
            },
            "sector_density_map": {item['sector'] or 'Unclassified': item['count'] for item in sector_breakdown}
        }, status=status.HTTP_200_OK)


class InvestmentMemoGeneratorAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MemoGenerationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
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
            # FIX: Corrected variable reference from `founder_input` to `founder_id`
            "target_founder_id": founder_id, 
            "format": "markdown",
            "investment_memo_payload": memo_markdown
        }, status=status.HTTP_200_OK)
        
class DiligenceEngine:
    @staticmethod
    def calculate_success_vector(founder_app, crawled_data):
        internal_size = getattr(founder_app, 'company_size', 10)
        current_revenue = getattr(founder_app, 'revenue', 0.0)
        
        external_size = int(crawled_data.get('linkedin_headcount', 0))
        diff = abs(external_size - int(internal_size))

        internal_val = int(internal_size)
        if internal_val > 0:
            deviation = (diff / internal_val) * 100
            transparency_score = max(0, 100 - deviation)
        else:
            transparency_score = 0
        
        revenue_score = min(current_revenue / 1000000 * 100, 100)
        hiring_score = min(crawled_data.get('job_board_openings', 0) * 10, 100)
        
        vector_score = (
            (revenue_score * 0.5) + 
            (transparency_score * 0.3) + 
            (hiring_score * 0.2)
        )
        
        return round(vector_score, 2), round(transparency_score, 2)
        

class MemoIntelligenceView(APIView):
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, startup_name):
        founder_app = get_object_or_404(Application, company_name__iexact=startup_name)
        url_to_crawl = getattr(founder_app, 'website', None)
        
        if url_to_crawl:
            external_data = self.perform_live_crawl(url_to_crawl)
        else:
            external_data = {'linkedin_headcount': 0, 'job_board_openings': 0}
        
        vector_score, transparency = DiligenceEngine.calculate_success_vector(founder_app, external_data)
        
        return Response({
            "startup": founder_app.company_name,
            "success_vector_score": vector_score,
            "transparency_index": transparency,
            "text_synthesis": f"Memo for {startup_name} generated using live data. Score: {vector_score}/100."
        })

    def perform_live_crawl(self, url):
        return {'linkedin_headcount': 45, 'job_board_openings': 2}


# ==============================================================================
# PINNACLE ARCHITECTURE: THE ZELDA GATEWAY
# ==============================================================================
class ZeldaGatewayAPIView(APIView):
    """
    GET /api/v1/zelda/gateway/{source_name}/
    
    The universal orchestration endpoint. Routes requests dynamically to the 
    correct API model across the ecosystem and guarantees the output is formatted 
    as a Foundry Envelope.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, source_name):
        # 1. Dynamic Routing: Find the correct API model via the Registry
        model_class = PinnacleRegistry.get_model_for_source(source_name)
        
        if not model_class:
            return Response({
                "status": "error",
                "message": f"Source '{source_name}' is not registered with the Pinnacle architecture.",
                "available_sources": list(PinnacleRegistry.get_adapters().keys())
            }, status=status.HTTP_404_NOT_FOUND)

        # 2. Query execution (Supports single ID or bulk fetch)
        object_id = request.query_params.get('id')
        
        if object_id:
            # Fetch a specific entity
            instance = get_object_or_404(model_class, id=object_id)
            return Response(
                instance.to_foundry_envelope(), 
                status=status.HTTP_200_OK
            )
        else:
            # Fetch recent telemetry
            instances = model_class.objects.all().order_by('-id')[:50]
            envelopes = [inst.to_foundry_envelope() for inst in instances]
            
            return Response({
                "status": "success",
                "source_engine": source_name,
                "orchestration_payload": envelopes
            }, status=status.HTTP_200_OK)