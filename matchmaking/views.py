import math
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import PermissionDenied

# Consolidated Structural Business Models
from .models import Application, InvestorApplication, Connection, MatchFeedback

# AI Vector Pipeline & Rule-Based Match Core Engine
from matchmaking.services.ai_engine import generate_profile_embedding, calculate_similarity
from .logic import calculate_rule_based_score, get_blended_match


# ==========================================
# CUSTOM SECURITY DECORATORS
# ==========================================

def founder_required(view_func):
    """
    Decorator for views that checks if the logged-in user contains
    a valid founder badge/profile application record.
    """
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')  # Hardened namespace route target
        
        if getattr(request.user, 'is_founder', False) or hasattr(request.user, 'match_founder_profile'):
            return view_func(request, *args, **kwargs)
        
        raise PermissionDenied("Access restricted. Only registered founders can access this matchmaking workspace.")
    return _wrapped_view


# ==========================================
# MATCHMAKING CORE VIEWS
# ==========================================

@login_required
def investor_dashboard(request):
    """
    Blended Matchmaking Dashboard: Ranks founders based on AI + Rules.
    Features an advanced keyword-matching fallback system.
    """
    investor_profile = getattr(request.user, 'match_investor_profile', None)
    
    if not investor_profile:
        messages.info(request, "Please complete your investor profile to view matches.")
        return redirect('accounts:investor_form')

    # Lazy-generation framework utilizing the unified Gemini SDK
    if not investor_profile.focus_vector and investor_profile.investment_focus:
        try:
            vector_array = generate_profile_embedding(investor_profile.investment_focus)
            if vector_array:
                investor_profile.focus_vector = vector_array
                investor_profile.save()
        except Exception:
            investor_profile.focus_vector = None

    match_results = []
    requested_ids = Connection.objects.filter(investor=investor_profile).values_list('founder_id', flat=True)

    # Keyword semantic fallback framework if vectors are missing
    if not investor_profile.focus_vector:
        search_terms = [term.strip() for term in investor_profile.investment_focus.replace(',', ' ').split() if len(term.strip()) > 2]
        query = Q()
        for term in search_terms:
            query |= Q(sector__icontains=term) | Q(keywords__icontains=term) | Q(company_name__icontains=term)
        
        founders = Application.objects.filter(query | Q(stage__icontains=investor_profile.investment_stage)).select_related('user')
    else:
        founders = Application.objects.all().select_related('user')
    
    for founder in founders:
        if not founder.description_vector:
            if founder.description:
                try:
                    vector_array = generate_profile_embedding(founder.description)
                    if vector_array:
                        founder.description_vector = vector_array
                        founder.save()
                    else:
                        continue
                except Exception:
                    continue
            else:
                continue

        if investor_profile.focus_vector and founder.description_vector:
            raw_ai_similarity = calculate_similarity(investor_profile.focus_vector, founder.description_vector)
            ai_score = raw_ai_similarity * 100
        else:
            ai_score = 50.0

        rule_score = calculate_rule_based_score(application=founder, investor=investor_profile)
        final_score = get_blended_match(ai_score, rule_score, application=founder, investor=investor_profile)
        
        if final_score > 10:
            match_results.append({
                'founder': founder,
                'ai_score': round(ai_score, 1),
                'rule_score': round(rule_score, 1),
                'final_score': round(final_score, 1),
                'already_requested': founder.id in requested_ids
            })
    
    match_results = sorted(match_results, key=lambda x: x['final_score'], reverse=True)

    return render(request, 'matchmaking/investor_dashboard.html', {
        'matches': match_results,
        'investor': investor_profile,
    })


@login_required
def founder_dashboard(request):
    """
    Founder-facing dashboard: View matching investors ranked by a blended 
    AI + Rule algorithm, and manage incoming handshake requests.
    """
    application = getattr(request.user, 'match_founder_profile', None)
    
    if not application:
        messages.info(request, "Complete your founder profile to see investor matches.")
        return redirect('accounts:seeking_investment')

    # Lazy-generation engine using unified Gemini vectorization pipeline
    if not application.description_vector and application.description:
        try:
            vector_array = generate_profile_embedding(application.description)
            if vector_array:
                application.description_vector = vector_array
                application.save()
        except Exception:
            pass

    # Extract pending inbound handshake records optimized via select_related
    pending_requests = Connection.objects.filter(
        founder=application, 
        status='PENDING'
    ).select_related('investor__user')

    # Query allocators (pulling related user records to eliminate N+1 data hits)
    investors = InvestorApplication.objects.all().select_related('user')
    match_results = []
    
    for investor in investors:
        if application.description_vector and investor.focus_vector:
            ai_score = calculate_similarity(application.description_vector, investor.focus_vector) * 100
        else:
            ai_score = 50.0

        rule_score = calculate_rule_based_score(application=application, investor=investor)
        final_score = get_blended_match(ai_score, rule_score, application=application, investor=investor)
        
        if final_score > 15:
            match_results.append({
                'investor': investor,
                'final_score': round(final_score, 1),
                'rule_match': rule_score >= 80,
            })
    
    match_results = sorted(match_results, key=lambda x: x['final_score'], reverse=True)

    return render(request, 'matchmaking/founder_dashboard.html', {
        'matches': match_results,
        'application': application,
        'pending_requests': pending_requests
    })


@login_required
@founder_required
def founder_matchmaker(request):
    """
    Dedicated dashboard for founders to see which specific investors 
    have explicitly 'liked' or upvoted their startup profile card.
    """
    founder_app = get_object_or_404(Application, user=request.user)
    
    likes = MatchFeedback.objects.filter(
        application=founder_app,
        vote=1
    ).select_related('investor__user')
    
    interested_investors = [like.investor for like in likes]
    
    return render(request, 'matchmaking/founder_matchmaker.html', {
        'founder_app': founder_app,
        'interested_investors': interested_investors,
    })


def founder_bulletin_board(request):
    """
    Queries verified startup Application profiles to display on the Interlink Foundry bulletin board.
    Calculates dynamic AI match scores if an authenticated investor is browsing.
    """
    pitches_queryset = Application.objects.all().select_related('user')
    
    # Check if a logged-in investor is browsing to compute dynamic match scores
    investor_profile = None
    if request.user.is_authenticated:
        investor_profile = getattr(request.user, 'match_investor_profile', None)

    pitches = []
    for pitch in pitches_queryset:
        # If the viewer is a verified investor with an active vector, calculate similarity
        if investor_profile and investor_profile.focus_vector and pitch.description_vector:
            try:
                raw_similarity = calculate_similarity(investor_profile.focus_vector, pitch.description_vector)
                match_percentage = int(max(0, raw_similarity) * 100)
            except Exception:
                match_percentage = 75
        else:
            # Neutral baseline fallback score for founders browsing or non-logged-in users
            match_percentage = 75
            
        pitch.match_percentage = match_percentage
        pitches.append(pitch)
        
    # Sort the public feed dynamically so highest matching sectors sit at the top for investors
    if investor_profile and investor_profile.focus_vector:
        pitches = sorted(pitches, key=lambda x: x.match_percentage, reverse=True)

    return render(request, 'matchmaking/bulletin_board.html', {
        'pitches': pitches,
    })


# ==========================================
# INTERACTION & TRANSACTION HANDLERS
# ==========================================

@login_required
@require_POST
def request_intro(request, application_id, investor_id):
    """
    The Intro Workflow: Creates a Connection record and dispatches an alert to the broker.
    """
    founder_app = get_object_or_404(Application, id=application_id)
    investor_profile = getattr(request.user, 'match_investor_profile', None)

    if not investor_profile:
        messages.error(request, "Only registered investors can request introductions.")
        return redirect(request.META.get('HTTP_REFERER', 'matchmaking:investor_dashboard'))

    connection, created = Connection.objects.get_or_create(
        investor=investor_profile,
        founder=founder_app
    )

    if created:
        subject = f"[Handshake Alert] Intro Request: {investor_profile.company_name} -> {founder_app.company_name}"
        email_body = (
            f"Broker Lead Notification:\n\n"
            f"Investor: {investor_profile.full_name} ({investor_profile.company_name})\n"
            f"Founder Startup Target: {founder_app.company_name}\n\n"
            f"Mandate Target Stage: {investor_profile.investment_stage}\n"
            f"Action Required: Navigate to the admin workspace to process and approve this platform handshake."
        )
        
        send_mail(
            subject=subject,
            message=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)],
            fail_silently=True
        )
        messages.success(request, f"Intro request sent for {founder_app.company_name}! Our team will facilitate the connection.")
    else:
        messages.info(request, "You have already requested an introduction to this founder.")

    return redirect('matchmaking:investor_dashboard')


@login_required
@require_POST
def record_vote(request):
    """
    Captures platform interaction metadata (Thumbs Up / Down) to optimize data value metrics.
    """
    application_id = request.POST.get('application_id')
    vote_value = request.POST.get('vote')
    
    investor_profile = getattr(request.user, 'match_investor_profile', None)
    if not investor_profile or not application_id:
        return redirect('matchmaking:investor_dashboard')
        
    founder_app = get_object_or_404(Application, id=application_id)
    numerical_vote = 1 if vote_value == 'up' else -1

    MatchFeedback.objects.update_or_create(
        user=request.user,
        application=founder_app,
        investor=investor_profile,
        defaults={'vote': numerical_vote}
    )

    messages.success(request, "Feedback recorded. We're tuning your algorithm!")
    return redirect(request.META.get('HTTP_REFERER', 'matchmaking:investor_dashboard'))