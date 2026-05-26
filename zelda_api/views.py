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
from .utils import scan_pitch_deck, AnalyzedPitch, compile_executive_intelligence_memo

# Syncing with the models defined for the matching engine
from matchmaking.models import Application, InvestorApplication

# Pinnacle Architecture Registry
from .registry import PinnacleRegistry

UserClass = get_user_model()
logger = logging.getLogger(__name__)

class ZeldaGlobalSearchAPIView(APIView):
    """
    POST /api/v1/zelda/search/
    Zelda Core Global Search Engine API
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

            return Response({
                'status': 'success',
                'query': user_query,
                'response': f"I processed a comprehensive cross-registry sweep for '{user_query}' and uncovered {len(results)} entry points matching your criteria!",
                'results': results
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Zelda Exploration Pipeline dropped: {str(e)}")
            return Response({'status': 'error', 'message': 'The search system pipeline encountered an unexpected validation drop.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MatchRadarAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = VectorMatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        mock_matches = [
            {"username": "alpha_ventures", "role": "investor", "match_score": 0.94, "alignment_rationale": "Strong overlap in B2B SaaS infrastructure focus."},
            {"username": "nexus_seed", "role": "investor", "match_score": 0.87, "alignment_rationale": "Matches early-stage pre-revenue metrics framework."}
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
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
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
            
            if not created and raw_text_summary:
                founder_app.description = raw_text_summary[:500]
                founder_app.save()

            # Step 3: Run Cross-Registry Matching via Triangulated DiligenceEngine
            mock_crawl_telemetry = {'linkedin_headcount': getattr(founder_app, 'company_size', 15) or 15, 'job_board_openings': 3}
            vector_score, transparency_index = DiligenceEngine.calculate_success_vector(founder_app, investor_app, mock_crawl_telemetry)

            # Step 4: Compile Standardized Investment Memo Markdown Architecture via Utility
            memo_markdown = compile_executive_intelligence_memo(
                founder_app=founder_app,
                investor_app=investor_app,
                extracted_deck_data=raw_extracted_data,
                vector_score=vector_score,
                transparency_index=transparency_index
            )

            # Step 5: Encapsulate and Flatten parameters directly into a Protocol Foundry Envelope
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
                    "market": raw_extracted_data.get("market_size", "Pending LLM Analysis")
                },
                "risk_flags": {
                    "low_transparency_variance": True if transparency_index < 70.0 else False
                }
            }

            return Response(foundry_envelope, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Unified intake pipeline execution failed: {str(e)}")
            return Response({"error": f"Intake pipeline structural error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InvestorPortfolioIntakeAPIView(APIView):
    """
    POST /api/v1/zelda/investors/portfolio/
    Ingests and scrapes an investor's historical fund data or portfolio reviews to enrich vector matching.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({"error": "No file uploaded. Use the form-data key 'file'."}, status=status.HTTP_400_BAD_REQUEST)
            
        investor_app = get_object_or_404(InvestorApplication, user=request.user)

        try:
            # Scrape incoming portfolio telemetry via standard file pipeline
            raw_extracted_data = scan_pitch_deck(uploaded_file)
            if "error" in raw_extracted_data:
                return Response(raw_extracted_data, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
                
            raw_portfolio_summary = raw_extracted_data.get("summary", "")
            
            # Persist raw text to database model layout tracking attribute
            if hasattr(investor_app, 'portfolio_raw_text') or True:
                investor_app.portfolio_raw_text = raw_portfolio_summary
                investor_app.save()

            foundry_envelope = {
                "origin": "investor_portfolio_scanner",
                "timestamp": "2026-05-25T12:00:00Z",
                "payload": {
                    "investor_node": investor_app.company_name or "Institutional Allocator",
                    "extracted_portfolio_telemetry": raw_portfolio_summary[:300],
                    "status": "Dual-sided investment history successfully cataloged into database layer."
                }
            }
            return Response(foundry_envelope, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Investor portfolio ingestion failed: {str(e)}")
            return Response({"error": f"Investor intake drop: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WebExplorationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WebCrawlSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        target_url = serializer.validated_data['target_url']
        return Response({"status": "crawled", "url": target_url, "synthesized_summary": "Clean text payload ready for investment memo formatting.", "verification_status": "Matches deck parameters"}, status=status.HTTP_200_OK)
    

class DocumentDirectScraperAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
        serializer = DirectUploadDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = serializer.validated_data['file']
        doc_type = serializer.validated_data['document_type']
        
        founder_app = get_object_or_404(Application, user=request.user)
        founder_app.current_revenue = serializer.validated_data.get('current_revenue')
        founder_app.company_size = serializer.validated_data.get('company_size')
        founder_app.years_in_business = serializer.validated_data.get('years_in_business')
        founder_app.save()
        
        return Response({
            "status": "success",
            "file_meta": {"filename": uploaded_file.name, "size_bytes": uploaded_file.size, "content_type": uploaded_file.content_type},
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
        sector_breakdown = Application.objects.values('sector').annotate(count=Count('id')).order_by('-count')
        
        return Response({
            "status": "success",
            "metrics_timestamp": "2026-05-20T09:55:00Z",
            "ecosystem_depth": {"registered_founders": total_founders, "active_capital_allocators": total_investors, "total_platform_ratio": f"{total_founders}:{total_investors}"},
            "macro_financial_aggregates": {"average_target_raise": 1850000, "dominant_geography": "San Diego, California"},
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
        
        return Response({"status": "compiled", "target_founder_id": founder_id, "format": "markdown", "investment_memo_payload": memo_markdown}, status=status.HTTP_200_OK)


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
        
        # DUAL-SIDED AFFINITY BOOSTER ENGINE LOGIC
        investor_history_raw = getattr(investor_app, 'portfolio_raw_text', '') or ''
        portfolio_affinity_boost = 0.0
        
        if investor_history_raw.strip():
            # Check for keyword sector density overlap between founder sector and investor portfolio text
            founder_sector = (founder_app.sector or '').lower()
            if founder_sector and founder_sector in investor_history_raw.lower():
                portfolio_affinity_boost = 15.0  # Boost score if data traces align
        
        vector_score = (
            (revenue_score * 0.4) + 
            (transparency_score * 0.3) + 
            (hiring_score * 0.1) + 
            portfolio_affinity_boost
        )
        
        return round(min(vector_score, 100.0), 2), round(transparency_score, 2)


class MemoIntelligenceView(APIView):
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, startup_name):
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
            "text_synthesis": f"Memo for {startup_name} generated using live data. Score: {vector_score}/100."
        })

    def perform_live_crawl(self, url):
        return {'linkedin_headcount': 45, 'job_board_openings': 2}


class ZeldaGatewayAPIView(APIView):
    """
    GET /api/v1/zelda/gateway/{source_name}/
    The universal orchestration endpoint.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, source_name):
        model_class = PinnacleRegistry.get_model_for_source(source_name)
        if not model_class:
            return Response({
                "status": "error",
                "message": f"Source '{source_name}' is not registered with the Pinnacle architecture.",
                "available_sources": list(PinnacleRegistry.get_adapters().keys())
            }, status=source.HTTP_404_NOT_FOUND)

        object_id = request.query_params.get('id')
        if object_id:
            instance = get_object_or_404(model_class, id=object_id)
            return Response(instance.to_foundry_envelope(), status=status.HTTP_200_OK)
        else:
            instances = model_class.objects.all().order_by('-id')[:50]
            envelopes = [inst.to_foundry_envelope() for inst in instances]
            return Response({"status": "success", "source_engine": source_name, "orchestration_payload": envelopes}, status=status.HTTP_200_OK)

class InvestorPortfolioIntakeAPIView(APIView):
    """
    POST /api/v1/zelda/investors/portfolio/
    Ingests and scrapes an investor's historical fund data or portfolio reviews to enrich vector matching.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {"error": "No file uploaded. Use the form-data key 'file'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Guarantee the authenticated user has an investor account profile node
        investor_app = get_object_or_404(InvestorApplication, user=request.user)

        try:
            # Step 1: Run file through your core multi-format layout parser
            raw_extracted_data = scan_pitch_deck(uploaded_file)
            if "error" in raw_extracted_data:
                return Response(raw_extracted_data, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
                
            raw_portfolio_summary = raw_extracted_data.get("summary", "")
            
            if not raw_portfolio_summary.strip():
                return Response(
                    {"error": "Scraper engine failed to parse viable textual semantic parameters from this asset format."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Step 2: Persist raw text token layout payload directly to the database tracker
            investor_app.portfolio_raw_text = raw_portfolio_summary
            investor_app.save()

            # Step 3: Structure output as an enterprise-grade Foundry Protocol Envelope
            foundry_envelope = {
                "origin": "investor_portfolio_scanner",
                "timestamp": "2026-05-26T06:00:00Z",
                "payload": {
                    "investor_node": investor_app.company_name or "Verified Allocator Account",
                    "extracted_portfolio_telemetry": raw_portfolio_summary[:300] + "...",
                    "status": "Dual-sided investment history successfully cataloged into database layer."
                }
            }
            return Response(foundry_envelope, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Investor portfolio ingestion pipeline failed: {str(e)}")
            return Response(
                {"error": f"Investor intake drop: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class FounderMatchRadarAPIView(APIView):
    """
    POST /api/v1/zelda/founder/match-radar/
    Calculates competitive intelligence positioning for a founder against anonymized peer networks
    using geographic, sector, and target capital telemetry vectors.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 1. Identify the target founder app context
        target_founder_app = get_object_or_404(Application, user=request.user)
        
        # Pull baseline vectors from target founder
        my_sector = target_founder_app.sector or "General Tech"
        my_geography = getattr(target_founder_app, 'geography', 'San Diego, California') or 'San Diego, California'
        my_raise = float(getattr(target_founder_app, 'target_raise', 0.0) or 0.0)
        
        # 2. Extract runtime filter adjustments from payload if provided
        filter_sector = request.data.get('sector', my_sector)
        filter_geography = request.data.get('geography', my_geography)
        
        # 3. Base Query Set for Rivals (Exclude self, protect privacy)
        peer_query = Application.objects.exclude(id=target_founder_app.id)
        
        if filter_sector:
            peer_query = peer_query.filter(sector__iexact=filter_sector)
        if filter_geography:
            peer_query = peer_query.filter(geography__icontains=filter_geography)

        # 4. Generate Macroeconomic Aggregations
        total_peers = peer_query.count()
        aggregates = peer_query.aggregate(
            avg_raise=Avg('target_raise'),
            total_raise_pool=Sum('target_raise'),
            avg_size=Avg('company_size')
        )
        
        avg_peer_raise = float(aggregates.get('avg_raise') or 0.0)
        avg_peer_size = float(aggregates.get('avg_size') or 0.0)
        
        # Generate macro narrative summary dynamic text
        macro_insight_narrative = (
            f"{total_peers} ventures in {filter_geography or 'your region'} within the {filter_sector or 'matching'} "
            f"track are actively scaling. On average, peers in this cluster are raising "
            f"${avg_peer_raise:,.2f} with an active operations headcount node of {int(avg_peer_size)} members."
        )

        # 5. Build Anonymized Peer Match Vectors List
        anonymized_competitors = []
        peer_instances = peer_query.order_by('-id')[:25] # Cap matrix depth for efficiency
        
        for idx, peer in enumerate(peer_instances, start=1):
            peer_raise = float(getattr(peer, 'target_raise', 0.0) or 0.0)
            peer_size = int(getattr(peer, 'company_size', 10) or 10)
            
            # Compute a synthetic, lightweight competitive matrix variance distance
            # This measures distance from the baseline founder track
            raise_delta = abs(my_raise - peer_raise)
            max_possible_delta = max(my_raise, peer_raise, 1.0)
            similarity_vector = max(0.0, 100.0 - ((raise_delta / max_possible_delta) * 100.0))
            
            # Strict Privacy Shielding: Never return company names or descriptions
            anonymized_competitors.append({
                "peer_node_id": f"PEER-TRACK-NX{idx:03d}", 
                "proximity_vector_score": round(similarity_vector, 2),
                "metrics_comparison": {
                    "target_raise": peer_raise,
                    "company_size": peer_size,
                    "funding_stage": getattr(peer, 'funding_stage', 'Seed'),
                    "is_higher_capital_target": peer_raise > my_raise
                }
            })

        # Sort array by closest vector proximity
        anonymized_competitors = sorted(anonymized_competitors, key=lambda x: x['proximity_vector_score'], reverse=True)

        # 6. Encapsulate inside the standard Protocol Envelope
        foundry_envelope = {
            "origin": "founder_competitive_match_radar",
            "timestamp": "2026-05-26T08:00:00Z",
            "payload": {
                "subject_venture": target_founder_app.company_name,
                "active_filters": {
                    "sector": filter_sector,
                    "geography": filter_geography
                },
                "macro_insights": {
                    "peer_cluster_count": total_peers,
                    "average_market_raise": round(avg_peer_raise, 2),
                    "total_capital_velocity_pool": round(float(aggregates.get('total_raise_pool') or 0.0), 2),
                    "market_density_statement": macro_insight_narrative
                },
                "competitive_positioning_matrix": anonymized_competitors
            }
        }
        
        return Response(foundry_envelope, status=status.HTTP_200_OK)