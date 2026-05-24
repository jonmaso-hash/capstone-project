import logging
import os
import re
import urllib.parse
import logging

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
from django.views.decorators.http import require_GET, require_POST
from stream_chat import StreamChat
from blog.models import Article
import json 
from django.http import JsonResponse 
from django.core.cache import cache

# Gemini Automated Deal Screening Orchestration Service
from matchmaking.services.deal_screener import index_founder_pitch_deck

# Syncing with the models defined for the matching engine
from matchmaking.models import Application, InvestorApplication
from .forms import ApplicationForm, InvestorForm

logger = logging.getLogger(__name__) 

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
    application = getattr(request.user, "match_founder_profile", None)
    form = None 

    if request.method == "POST":
        form = ApplicationForm(request.POST, request.FILES, instance=application)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            
            # --- CACHE INVALIDATION ---
            # If an application exists/was saved, clear its cached crawl data
            cache_key = f"startup_data_{app.id}"
            cache.delete(cache_key)
            
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
# AI ASSISTANCE CANVAS VIEW
# =====================================================================

@login_required
def ai_search_page(request):
    """
    Renders the standalone workspace canvas workspace for Zelda query tracking.
    """
    return render(request, "accounts/ai_search.html")

@require_POST
def account_search_api(request):
    try:
        data = json.loads(request.body)
        query_param = data.get('q', '').strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not query_param:
        return JsonResponse({"results": []})

    # 1. Define the search query using Q objects
    # This searches across the company_name, description, and sector fields
    search_query = (
        Q(company_name__icontains=query_param) | 
        Q(description__icontains=query_param) |
        Q(sector__icontains=query_param)
    )

    # 2. Filter the model and execute the query
    # We limit to the top 10 results for performance
    results_queryset = Application.objects.filter(search_query)[:10]

    # 3. Serialize the data into a list of dictionaries
    serialized_results = [
        {
            "title": app.company_name or "Untitled Application",
            "snippet": app.description[:100] + "..." if app.description else "No description available.",
            "url": reverse("accounts:profile", kwargs={"username": app.user.username})
        }
        for app in results_queryset
    ]

    return JsonResponse({
        "status": "success",
        "results": serialized_results
    })