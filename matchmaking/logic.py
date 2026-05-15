from .models import Application, InvestorApplication

def calculate_rule_based_score(application, investor):
    """
    Calculates a compatibility score (0-100) based on hard constraints 
    like Sector and Investment Stage.
    """
    score = 0
    
    # 1. Sector Matching (40% of rule-based score)
    # We normalize both to lowercase to avoid "SaaS" vs "saas" mismatches
    app_sector = application.sector.lower() if application.sector else ""
    # Assuming investor preferred_sectors is a comma-separated string
    investor_sectors = [s.strip().lower() for s in investor.investment_focus.split(',')]

    if app_sector in investor_sectors:
        score += 40
    elif any(s in app_sector for s in investor_sectors):
        # Partial match (e.g., "Fintech" matches "Financial Technology")
        score += 25

    # 2. Stage Matching (60% of rule-based score)
    # Hard constraint: Investors usually have strict mandates for Stage
    app_stage = application.stage.lower() if application.stage else ""
    inv_stage = investor.investment_stage.lower() if investor.investment_stage else ""

    if app_stage == inv_stage:
        score += 60
    # Secondary check: If the stage is "adjacent" (e.g., Seed vs Pre-Seed)
    elif _is_adjacent_stage(app_stage, inv_stage):
        score += 30

    return score

def _is_adjacent_stage(stage1, stage2):
    """Helper to determine if two stages are close enough to be relevant."""
    adjacents = {
        'pre-seed': ['seed'],
        'seed': ['pre-seed', 'series a'],
        'series a': ['seed', 'series b'],
        'series b': ['series a', 'series c']
    }
    return stage2 in adjacents.get(stage1, [])

def get_blended_match(ai_score, rule_score):
    """
    Combines the AI Vector score and the Rule-based score.
    Higher weight is given to rules (Stage/Sector) to ensure mandate fit.
    """
    # 70% Weight on Rules, 30% on AI "Vibe"
    return (rule_score * 0.7) + (ai_score * 0.3)

def get_blended_match(ai_score, rule_score, application, investor):
    """
    Enhanced blended match that incorporates historical feedback.
    """
    base_score = (rule_score * 0.7) + (ai_score * 0.3)
    
    # Check for historical feedback
    from .models import MatchFeedback
    feedback = MatchFeedback.objects.filter(application=application, investor=investor).first()
    
    if feedback:
        # If they upvoted, boost the score to 100
        if feedback.vote == 1:
            return min(base_score + 15, 100)
        # If they downvoted, slash the score by 50%
        if feedback.vote == -1:
            return base_score * 0.5
            
    return base_score