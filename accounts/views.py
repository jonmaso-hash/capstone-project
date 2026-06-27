import json
import logging
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.cache import cache
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

# Core Matchmaking Engine Models
from matchmaking.services.ai_engine import calculate_zelda_advantage
from matchmaking.utils import clean_financial_input
from matchmaking.models import Application, InvestorApplication, Connection, Follow
from .forms import ApplicationForm, InvestorForm

# External/Third-Party Apps
from stream_chat import StreamChat

logger = logging.getLogger(__name__)

# Dynamic lookups prevent NameError failures if optional external apps aren't active
JobListing = None
if apps.is_installed('jobs'):
    try:
        from jobs.models import JobListing
    except ImportError:
        pass

Article = None
if apps.is_installed('blog'):
    try:
        from blog.models import Article
    except ImportError:
        pass


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
            
            # Route to appropriate onboarding based on selected role
            role = request.POST.get('role', '')
            if role == 'founder':
                return redirect('accounts:seeking_investment')
            elif role == 'investor':
                return redirect('accounts:investor_form')
            else:
                # buyer/seller — go to profile with welcome prompt
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
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = AuthenticationForm()
    return render(request, "accounts/login.html", {"form": form})


# =====================================================================
# WORKSPACE MATCHMAKING ONBOARDING FLOWS
# =====================================================================

@login_required
def seeking_investment(request):
    # Pull profile using the correct engine relation attribute
    application = getattr(request.user, "match_founder_profile", None)

    if request.method == "POST":
        form = ApplicationForm(request.POST, request.FILES, instance=application)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            
            # --- CACHE INVALIDATION ---
            cache_key = f"startup_data_{app.id}"
            cache.delete(cache_key)
            
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = ApplicationForm(instance=application)

    return render(request, "accounts/seeking_investment.html", {"form": form})


@login_required
def investor_form(request):
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
def profile(request, username=None, pk=None):
    """
    Renders user profile, calculates follow status, and fetches connections.
    """
    User = get_user_model()
    
    # 1. Resolve User
    if pk:
        viewed_user = get_object_or_404(User, pk=pk)
        return redirect("accounts:profile", username=viewed_user.username)
    viewed_user = get_object_or_404(User, username=username)

    # 2. Data Retrieval
    application = getattr(viewed_user, "match_founder_profile", None)
    investor_application = getattr(viewed_user, "match_investor_profile", None)
    
    dm_enabled = False
    if application and application.allow_direct_messages:
        dm_enabled = True
    elif investor_application and investor_application.allow_direct_messages:
        dm_enabled = True

    # Fetch optional modules safely
    user_jobs = []
    if JobListing:
        user_jobs = JobListing.objects.filter(poster=viewed_user).order_by('-created_at')

    user_articles = []
    if Article:
        user_articles = Article.objects.filter(author=viewed_user).order_by('-created_on')

    # 3. Follow System
    is_following = False
    if request.user.is_authenticated:
        is_following = Follow.objects.filter(follower=request.user, following=viewed_user).exists()
    
    following_list = Follow.objects.filter(follower=viewed_user).select_related("following")

    # 4. Privacy Gatekeeper
    if viewed_user != request.user and application and getattr(application, "is_private", False):
        if not application.allowed_viewers.filter(id=request.user.id).exists():
            return render(request, "accounts/profile_private.html", {"profile_user": viewed_user})

    # 5. Zelda Advantage Engine
    zelda_score, founder_data_json = None, None
    if application:
        has_advantage_access = (viewed_user == request.user)
        if not has_advantage_access:
            viewer_investor = getattr(request.user, "match_investor_profile", None)
            if viewer_investor and Connection.objects.filter(investor=viewer_investor, founder=application, status="ACCEPTED").exists():
                has_advantage_access = True
        
        if has_advantage_access:
            zelda_score = calculate_zelda_advantage(application)
            founder_data_json = json.dumps({
                "revenue": float(clean_financial_input(application.current_revenue) or 0),
                "ask": float(clean_financial_input(application.raising_amount) or 0),
                "burn": float(clean_financial_input(application.monthly_burn_rate) or 1),
                "team_size": int(clean_financial_input(application.team_size) or 1),
                "years": int(clean_financial_input(application.years_in_business) or 0),
            })

    context = {
        "profile_user": viewed_user,
        "application": application,
        "investor_application": investor_application,
        "zelda_score": zelda_score,
        "founder_data_json": founder_data_json,
        "is_following": is_following,
        "following_list": following_list,
        "user_articles": user_articles,
        "user_jobs": user_jobs,
        "dm_enabled": dm_enabled,
    }

    return render(request, "accounts/profile.html", context)

@login_required
def redirect_to_own_profile(request):
    return redirect("accounts:profile", username=request.user.username)


# =====================================================================
# EXTERNAL INTEGRATIONS & REALTIME CHAT COMMUNICATIONS (APIs)
# =====================================================================

@login_required
def get_stream_token(request):
    try:
        api_key = getattr(settings, 'STREAM_API_KEY', None)
        api_secret = getattr(settings, 'STREAM_API_SECRET', None)
        
        if not api_key or not api_secret:
            return JsonResponse({
                'error': 'Configuration Error',
                'details': 'STREAM_API_KEY or STREAM_API_SECRET missing from settings.py or environment configuration.'
            }, status=500)
            
        client = StreamChat(api_key=api_key, api_secret=api_secret)
        
        # IMPORTANT: Use the user's integer ID as a string, because JS passes integer targetIDs
        user_id = str(request.user.id)
        username = request.user.username
        
        # 1. Create the token
        token = client.create_token(user_id)
        
        # 2. CRITICAL FIX: Upsert the user into Stream's database immediately
        client.upsert_user({"id": user_id, "name": username})
        
        return JsonResponse({
            'api_key': api_key,
            'token': token,
            'user_id': user_id,
            'username': username
        })
        
    except Exception as e:
        logger.exception("Stream Token Generation & Upsert Failed")
        return JsonResponse({'error': 'Internal Server Error', 'details': str(e)}, status=500)


# =====================================================================
# AI ASSISTANCE CANVAS VIEW
# =====================================================================

@login_required
def ai_search_page(request):
    return render(request, "accounts/ai_search.html")


@require_POST
@login_required
def account_search_api(request):
    try:
        data = json.loads(request.body)
        query_param = data.get('q', '').strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not query_param:
        return JsonResponse({"results": []})

    search_query = (
        Q(company_name__icontains=query_param) | 
        Q(sector__icontains=query_param) |
        Q(description__icontains=query_param)
    )

    # 🔒 FILTER BOUNDARIES: Enforces public alignment unless the request belongs to the owner
    results_queryset = Application.objects.filter(search_query).filter(
        Q(is_private=False) | Q(user=request.user)
    )[:10]

    serialized_results = [
        {
            "title": app.company_name or "Untitled Application",
            "snippet": f"Sector: {app.sector} | Stage: {getattr(app, 'stage', '')}",
            "url": reverse("accounts:profile", kwargs={"username": app.user.username})
        }
        for app in results_queryset
    ]

    return JsonResponse({"status": "success", "results": serialized_results})


# =====================================================================
# PRIVACY MANAGEMENT LAYER (AJAX ENDPOINT)
# =====================================================================

@login_required
@require_POST
def toggle_privacy_view(request):
    try:
        data = json.loads(request.body)
        is_private_state = bool(data.get('is_private', False))
        
        founder_profile = Application.objects.filter(user=request.user).first()
        if founder_profile:
            founder_profile.is_private = is_private_state
            founder_profile.save(update_fields=['is_private'])

        investor_profile = InvestorApplication.objects.filter(user=request.user).first()
        if investor_profile:
            investor_profile.is_private = is_private_state
            investor_profile.save(update_fields=['is_private'])

        return JsonResponse({"status": "success", "is_private": is_private_state})
    except Exception as e:
        logger.exception("AJAX privacy toggle update failed.")
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
    
@login_required
def zelda_dashboard_view(request):
    # 1. Use the exact same lookup method as your profile view
    application = getattr(request.user, "match_founder_profile", None)
    
    # 2. If it is STILL None, the database record genuinely doesn't exist for this user.
    if not application:
        messages.warning(request, "Please initialize your founder profile to access the Zelda Dashboard.")
        return redirect('accounts:seeking_investment')
    
    # 3. Safely pass the data to the template
    context = {
        'application': application,
        'founder_data_json': json.dumps({
            'revenue': float(application.current_revenue or 0),
            'ask': float(application.raising_amount or 0),
            'burn': float(application.monthly_burn_rate or 1),
            'team': int(application.team_size or 1)
        })
    }
    return render(request, "accounts/zelda_dashboard.html", context)

@login_required
def update_criteria(request):
    if request.method == "POST":
        app = Application.objects.get(user=request.user)
        
        # Update inputs
        app.current_revenue = request.POST.get('revenue')
        app.monthly_burn_rate = request.POST.get('burn')
        app.team_size = request.POST.get('team')
        app.save()
        
        # Run the engine
        calculate_zelda_advantage(app)
        
        # Return JSON instead of redirecting
        return JsonResponse({
            'status': 'success',
            'zelda_score': app.zelda_score,
            'runway_months': float(app.runway_months)
        })
        
@login_required
@require_POST
def toggle_dm_view(request):
    try:
        data = json.loads(request.body)
        is_enabled = bool(data.get('dm_enabled', False))
        
        founder_profile = Application.objects.filter(user=request.user).first()
        if founder_profile:
            founder_profile.allow_direct_messages = is_enabled
            founder_profile.save(update_fields=['allow_direct_messages'])

        investor_profile = InvestorApplication.objects.filter(user=request.user).first()
        if investor_profile:
            investor_profile.allow_direct_messages = is_enabled
            investor_profile.save(update_fields=['allow_direct_messages'])

        return JsonResponse({"status": "success", "dm_enabled": is_enabled})
    except Exception as e:
        logger.exception("AJAX DM toggle update failed.")
        return JsonResponse({"status": "error", "message": str(e)}, status=400)