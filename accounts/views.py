import logging
import os
import re
import urllib.parse

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_GET
from stream_chat import StreamChat
from blog.models import Article

# Gemini Automated Deal Screening Orchestration Service
from matchmaking.services.deal_screener import index_founder_pitch_deck

# Syncing with the models defined for the matching engine
from matchmaking.models import Application, InvestorApplication
from .forms import ApplicationForm, InvestorForm

# 🔑 Dynamic lookups prevent NameError failures if external apps aren't active
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

logger = logging.getLogger(__name__)


# =====================================================================
# AUTHENTICATION ENGINE VIEWS
# =====================================================================

def signup_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile", username=request.user.username)
        
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, f"Welcome to Interlink Foundry, {user.username}!")
            return redirect("accounts:profile", username=user.username)
    else:
        form = UserCreationForm()
    return render(request, "accounts/signup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile", username=request.user.username)
        
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect("accounts:profile", username=user.username)
    else:
        form = AuthenticationForm()
    return render(request, "accounts/login.html", {"form": form})


# =====================================================================
# WORKSPACE MATCHMAKING ONBOARDING FLOWS
# =====================================================================

@login_required
def seeking_investment(request):
    """
    Founder Onboarding & Management: Collects/edits startup data and processes 
    pitch decks via Gemini Multimodal File Search.
    """
    if hasattr(request.user, "match_investor_profile"):
        messages.warning(request, "Investors cannot submit founder applications.")
        return redirect("accounts:profile", username=request.user.username)

    application = getattr(request.user, "match_founder_profile", None)

    if request.method == "POST":
        form = ApplicationForm(request.POST, request.FILES, instance=application)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            
            if app.pitch_deck:
                try:
                    index_founder_pitch_deck(app.id)
                    messages.success(request, "Founder profile updated! Gemini has successfully indexed your pitch deck.")
                except Exception as e:
                    logger.warning(f"Pitch deck background indexing failed for App ID {app.id}: {str(e)}")
                    messages.warning(request, "Profile saved, but automated deck vectorization is processing in the background.")
            else:
                messages.success(request, "Founder profile updated successfully!")
                
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = ApplicationForm(instance=application)

    return render(request, "accounts/seeking_investment.html", {"form": form})


@login_required
def investor_form(request):
    """
    Investor Onboarding & Management: Collects/edits investment mandates for the matching engine.
    """
    if hasattr(request.user, "match_founder_profile"):
        messages.warning(request, "Founders cannot submit investor profiles.")
        return redirect("accounts:profile", username=request.user.username)

    investor_profile = getattr(request.user, "match_investor_profile", None)

    if request.method == "POST":
        form = InvestorForm(request.POST, instance=investor_profile)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            messages.success(request, "Investment mandate updated successfully.")
            return redirect("matchmaking:bulletin_board")
    else:
        form = InvestorForm(instance=investor_profile)

    return render(request, "accounts/investor_form.html", {"form": form})


# =====================================================================
# USER PROFILE DISPATCH LAYER
# =====================================================================

@login_required
def profile(request, username):
    User = get_user_model()
    viewed_user = get_object_or_404(User, username=username)
    
    application = getattr(viewed_user, "match_founder_profile", None)
    investor_application = getattr(viewed_user, "match_investor_profile", None)
    show_welcome_prompt = not application and not investor_application

    # Blog integration: Fetch articles authored by this specific user
    user_articles = Article.objects.filter(author=viewed_user)

    return render(request, "accounts/profile.html", {
        "profile_user": viewed_user,
        "application": application,
        "investor_application": investor_application,
        "show_welcome_prompt": show_welcome_prompt,
        "user_articles": user_articles,
    })


@login_required
def redirect_to_own_profile(request):
    return redirect("accounts:profile", username=request.user.username)


@login_required
def profile_view(request, pk):
    User = get_user_model()
    profile_user = get_object_or_404(User, pk=pk)
    user_articles = Article.objects.filter(author=profile_user)
    
    return render(request, 'accounts/profile.html', {
        'profile_user': profile_user,
        'user_articles': user_articles
    })


# =====================================================================
# EXTERNAL INTEGRATIONS & REALTIME CHAT COMMUNICATIONS (APIs)
# =====================================================================

@login_required
def get_stream_token(request):
    """
    Websocket Handshake API: Generates user authentication payload tokens for GetStream.io
    """
    try:
        api_key = getattr(settings, 'STREAM_API_KEY', None)
        api_secret = getattr(settings, 'STREAM_API_SECRET', None)
        
        if not api_key or not api_secret:
            return JsonResponse({
                'error': 'Configuration Error',
                'details': 'STREAM_API_KEY or STREAM_API_SECRET missing from settings.py or .env configuration.'
            }, status=500)
            
        server_client = StreamChat(api_key=api_key, api_secret=api_secret)
        
        user_id = str(request.user.username).lower().strip()
        token = server_client.create_token(user_id)
        
        return JsonResponse({
            'api_key': api_key,
            'token': token,
            'user_id': user_id,
            'username': request.user.get_full_name() or request.user.username
        })
        
    except Exception as e:
        logger.exception("Stream Token Generation Failed")
        return JsonResponse({
            'error': 'Internal Server Error',
            'details': str(e)
        }, status=500)


# =====================================================================
# AI ASSISTANCE SEARCH ENGINE LAYER (ZELDA)
# =====================================================================

@login_required
def ai_search_page(request):
    """
    Renders the standalone workspace canvas workspace for Zelda query tracking.
    """
    return render(request, "accounts/ai_search.html")


@login_required
@require_GET
def search_api(request):
    """
    Zelda Core True Global Search Engine: Sweeps all database entities across apps,
    cross-references raw static template file structures for exact phrase copies,
    and returns an automated matching index dictionary payload with text navigation anchoring.
    """
    user_query = request.GET.get('q', '').strip()

    if not user_query:
        return JsonResponse({
            'status': 'success', 
            'response': "What kind of matches are we hunting down today?", 
            'results': []
        })

    # Read front-end boundary toggle options
    search_founders = request.GET.get('founders', 'true').lower() == 'true'
    search_investors = request.GET.get('investors', 'true').lower() == 'true'
    search_bulletins = request.GET.get('bulletins', 'true').lower() == 'true'

    results = []
    seen_urls = set()  # Deduplication layer to prevent structural layout pollution
    
    # 🔍 Clean up query string if users search explicitly for an '@handle' string
    clean_username_query = user_query[1:] if user_query.startswith('@') else user_query
    query_lower = user_query.lower()

    try:
        # -----------------------------------------------------------------
        # USERNAME ACCOUNT DRILLDOWN REGISTRY CHECK
        # -----------------------------------------------------------------
        UserClass = get_user_model()
        user_matches = UserClass.objects.filter(
            Q(username__icontains=clean_username_query) |
            Q(first_name__icontains=clean_username_query) |
            Q(last_name__icontains=clean_username_query)
        ).distinct()[:5]

        for matched_user in user_matches:
            try:
                url = reverse('accounts:profile', kwargs={'username': matched_user.username})
            except NoReverseMatch:
                url = f"/accounts/profile/{matched_user.username}/"

            if url in seen_urls:
                continue

            # Figure out what kind of profile they maintain on Interlink Foundry
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

        # -----------------------------------------------------------------
        # 0. INJECT ENGINE CORE APPLICATION FEATURES (Match Radar, Jobs, Blog)
        # -----------------------------------------------------------------
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

        # -----------------------------------------------------------------
        # 1. DATABASE REGISTRY DEEP CRAWL
        # -----------------------------------------------------------------
        
        # Scan Founder Applications
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
                bio_text = app.description or ""
                snippet = bio_text[:120] + '...' if len(bio_text) > 120 else bio_text
                results.append({
                    'type': 'Founder Profile',
                    'title': f"Founder: {app.company_name}",
                    'description': snippet,
                    'url': url
                })
                seen_urls.add(url)

        # Scan Investor Mandates
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

        # Scan Bulletins, Career Openings, and Blogs
        if search_bulletins:
            if Job:
                job_matches = Job.objects.filter(
                    Q(title__icontains=user_query) | 
                    Q(description__icontains=user_query)
                )[:5]
                for job in job_matches:
                    url = f"/jobs/{job.id}/"
                    if url in seen_urls:
                        continue
                    desc_text = job.description or ""
                    results.append({
                        'type': 'Career Opening',
                        'title': f"Job: {job.title}",
                        'description': desc_text[:120] + '...',
                        'url': url
                    })
                    seen_urls.add(url)

            if BlogPost:
                blog_matches = BlogPost.objects.filter(
                    Q(title__icontains=user_query) |
                    Q(content__icontains=user_query)
                )[:5]
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

        # -----------------------------------------------------------------
        # 2. RAW TEMPLATE ARCHITECTURE ENGINE FILE SEARCH (LANDING PAGES)
        # -----------------------------------------------------------------
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
                                    visible_page_words_lower = visible_page_words.lower()
                                    
                                    if query_lower in visible_page_words_lower:
                                        start_idx = visible_page_words_lower.find(query_lower)
                                        snippet_extract = visible_page_words[max(0, start_idx - 30):min(len(visible_page_words), start_idx + 100)]
                                        
                                        url_safe_query = urllib.parse.quote(user_query)
                                        deep_link_url = f"{target_url}#:~:text={url_safe_query}"
                                        
                                        results.append({
                                            'type': 'Landing Page Match',
                                            'title': label,
                                            'description': f"...{snippet_extract.strip()}...",
                                            'url': deep_link_url
                                        })
                                        seen_urls.add(target_url)
                            except IOError:
                                pass

        # -----------------------------------------------------------------
        # 3. CONSTRUCT INTERLINK FOUNDRY NARRATION CONTEXT
        # -----------------------------------------------------------------
        if results:
            ai_narration = (
                f"I processed a comprehensive cross-registry sweep for **'{user_query}'** and uncovered "
                f"**{len(results)} distinct entry points** matching your query criteria across database matrix indexes and UI templates!"
            )
        else:
            ai_narration = f"I evaluated every data directory and template workspace across the foundry for '{user_query}' but couldn't locate a hit."

        return JsonResponse({
            'status': 'success',
            'query': user_query,
            'response': ai_narration,
            'results': results
        })

    except Exception as e:
        logger.error(f"Zelda Full-System Exploration Pipeline dropped: {str(e)}")
        return JsonResponse({
            'status': 'error', 
            'message': 'The search system pipeline encountered an unexpected validation drop.'
        }, status=500)


def perform_database_lookup(query):
    """
    Helper Function: Scans local Django database for matches across Jobs
    to feed targeted contextual data to Zelda.
    """
    context_data = {
        'jobs': [],
        'profiles': []
    }
    
    words = query.lower().split()
    if not words or not Job:
        return context_data

    try:
        job_matches = Job.objects.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query)
        )[:3]
        
        for job in job_matches:
            context_data['jobs'].append({
                'title': job.title,
                'company': job.company_name if hasattr(job, 'company_name') else "Platform Partner",
                'description': job.description[:200] + "...",
            })
    except Exception as e:
        logger.error(f"Safe Job contextual execution runtime dropped: {str(e)}")
        
    return context_data

def extract_and_enrich_usernames(user_input_text):
    """
    Scans Zelda input for usernames and returns systemic data 
    context snippets for any valid accounts discovered.
    """
    # Pattern to find words starting with '@' or isolated handle formats
    usernames_found = re.findall(r'@([\w-]+)', user_input_text)
    
    # Also grab fallback phrases like "find user X" or "search profile X"
    phrase_match = re.search(r'(?:find user|search profile|look up)\s+([\w-]+)', user_input_text, re.IGNORECASE)
    if phrase_match:
        usernames_found.append(phrase_match.group(1))
        
    context_injection = ""
    
    if usernames_found:
        # Deduplicate list
        usernames_found = list(set(usernames_found))
        
        matched_users = User.objects.filter(username__in=usernames_found)
        if matched_users.exists():
            context_injection += "\n[Zelda System Override: Found matching user database entities]\n"
            for u in matched_users:
                context_injection += f"- User Handle: @{u.username}\n"
                context_injection += f"  Profile URL Path: /accounts/profile/{u.username}/\n"
                # If they have specific roles on your platform, tell Zelda
                if hasattr(u, 'investor_profile'):
                    context_injection += "  Platform Status: Verified Investor\n"
                elif hasattr(u, 'founder_profile'):
                    context_injection += "  Platform Status: Startup Founder\n"
                    
    return context_injection

