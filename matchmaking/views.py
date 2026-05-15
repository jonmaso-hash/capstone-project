from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from .models import Application

# Unified imports from your updated project structure
from .models import Application, InvestorApplication, Connection, MatchFeedback
from .services.ai_engine import generate_vector, calculate_similarity
from .logic import calculate_rule_based_score, get_blended_match

@login_required
def investor_dashboard(request):
    """
    Blended Matchmaking Dashboard: Ranks founders based on AI + Rules.
    Features an advanced keyword-matching fallback system.
    """
    # Aligned to match the 'match_investor_profile' related_name in models.py
    investor_profile = getattr(request.user, 'match_investor_profile', None)
    
    if not investor_profile:
        messages.info(request, "Please complete your investor profile to view matches.")
        return redirect('accounts:investor_form')

    # Ensure AI Vector exists for the Investor
    if not investor_profile.focus_vector and investor_profile.investment_focus:
        try:
            investor_profile.focus_vector = generate_vector(investor_profile.investment_focus)
            investor_profile.save()
        except Exception:
            # Fallback gracefully if AI engine service encounters a bump
            investor_profile.focus_vector = None

    match_results = []
    # Get IDs of startups this investor has already requested to avoid duplicates
    requested_ids = Connection.objects.filter(investor=investor_profile).values_list('founder_id', flat=True)

    # ADVANCED KEYWORD FALLBACK & FILTERING
    # If vector matching fails or isn't built yet, we pull relevant items via string lookup
    if not investor_profile.focus_vector:
        # Extract individual clean lookup terms from the investment focus description
        search_terms = [term.strip() for term in investor_profile.investment_focus.replace(',', ' ').split() if len(term.strip()) > 2]
        
        query = Q()
        for term in search_terms:
            query |= Q(sector__icontains=term) | Q(keywords__icontains=term) | Q(company_name__icontains=term)
        
        # Pull down founders matching either the keyword query or basic investment stage matching
        founders = Application.objects.filter(query | Q(stage__icontains=investor_profile.investment_stage))
    else:
        # Pull all items if vectors are healthy and operational
        founders = Application.objects.all()
    
    for founder in founders:
        # Handle lazy background generation of founder text vectors if missing
        if not founder.description_vector:
            if founder.description:
                try:
                    founder.description_vector = generate_vector(founder.description)
                    founder.save()
                except Exception:
                    continue
            else:
                continue

        # AI Scoring (Cosine Similarity)
        if investor_profile.focus_vector and founder.description_vector:
            raw_ai_similarity = calculate_similarity(investor_profile.focus_vector, founder.description_vector)
            ai_score = raw_ai_similarity * 100
        else:
            ai_score = 50.0  # Fair default baseline score if performing strict keyword fallback matching

        # Rule Scoring (Hard constraints like Stage, Industry, Ticket Size)
        rule_score = calculate_rule_based_score(application=founder, investor=investor_profile)
        
        # Blended Score (Weighted average of AI + Rules)
        final_score = get_blended_match(ai_score, rule_score, application=founder, investor=investor_profile)
        
        # Only show relevant matches (threshold of 10)
        if final_score > 10:
            match_results.append({
                'founder': founder,
                'ai_score': round(ai_score, 1),
                'rule_score': round(rule_score, 1),
                'final_score': round(final_score, 1),
                'already_requested': founder.id in requested_ids
            })
    
    # Rank by highest score first
    match_results = sorted(match_results, key=lambda x: x['final_score'], reverse=True)

    return render(request, 'matchmaking/investor_dashboard.html', {
        'matches': match_results,
        'investor': investor_profile,
    })

@login_required
@require_POST
def request_intro(request, application_id):
    """
    The Intro Workflow: Creates a Connection record and dispatches an alert to the broker.
    """
    founder_app = get_object_or_404(Application, id=application_id)
    investor_profile = getattr(request.user, 'match_investor_profile', None)

    if not investor_profile:
        messages.error(request, "Only registered investors can request introductions.")
        return redirect('matchmaking:investor_index')

    # Create the Connection record safely without duplication
    connection, created = Connection.objects.get_or_create(
        investor=investor_profile,
        founder=founder_app
    )

    if created:
        # Dispatch Brokerage Email Notification
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

    return redirect('matchmaking:investor_index')

@login_required
def founder_dashboard(request):
    """
    Founder-facing dashboard: View matching investors and manage incoming requests.
    """
    # Aligned to match the 'match_founder_profile' related_name in models.py
    application = getattr(request.user, 'match_founder_profile', None)
    
    if not application:
        messages.info(request, "Complete your founder profile to see investor matches.")
        return redirect('accounts:seeking_investment')

    # AI Vectorization check for founder
    if not application.description_vector and application.description:
        try:
            application.description_vector = generate_vector(application.description)
            application.save()
        except Exception:
            pass

    # Get incoming intro requests from investors
    pending_requests = Connection.objects.filter(founder=application, status='PENDING').select_related('investor')

    # Find investors who might like this startup
    investors = InvestorApplication.objects.exclude(focus_vector__isnull=True)
    match_results = []
    
    for investor in investors:
        if application.description_vector and investor.focus_vector:
            ai_score = calculate_similarity(application.description_vector, investor.focus_vector) * 100
        else:
            ai_score = 50.0

        rule_score = calculate_rule_based_score(application, investor)
        final_score = get_blended_match(ai_score, rule_score)
        
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
@require_POST
def record_vote(request):
    """
    Captures platform interaction metadata (Thumbs Up / Down) to optimize data value metrics.
    """
    application_id = request.POST.get('application_id')
    vote_value = request.POST.get('vote')
    
    investor_profile = getattr(request.user, 'match_investor_profile', None)
    if not investor_profile or not application_id:
        return redirect('matchmaking:investor_index')
        
    founder_app = get_object_or_404(Application, id=application_id)
    
    # Translate template post variables into explicit integer choice limits
    numerical_vote = 1 if vote_value == 'up' else -1

    # Save tracking data for future data premium buyers to see
    MatchFeedback.objects.update_or_create(
        user=request.user,
        application=founder_app,
        investor=investor_profile,
        defaults={'vote': numerical_vote}
    )

    messages.success(request, "Feedback recorded. We're tuning your algorithm!")
    return redirect('matchmaking:investor_index')

@login_required
def founder_bulletin_board(request):
    """
    Queries verified startup Application profiles to display 
    on the Interlink Foundry bulletin board.
    """
    # Swap out Pitch.objects for Application.objects
    pitches = Application.objects.filter(is_verified=True)
    
    # Note: If you want to see all entries regardless of their vetted status
    # while you test out the page look, swap the query above out for:
    # pitches = Application.objects.all()

    return render(request, 'matchmaking/bulletin_board.html', {
        'pitches': pitches,
    })