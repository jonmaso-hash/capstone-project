import requests

def calculate_match_score(investor, founder):
    """
    Calculates a match percentage between an investor and a founder.
    Patched to use correct model fields: investment_focus and sector.
    """
    score = 0
    
    # Safely parse the comma-separated focus industries
    investor_sectors = [
        s.strip().lower() 
        for s in getattr(investor, 'investment_focus', '').split(',') 
        if s.strip()
    ]
    founder_sector = getattr(founder, 'sector', '').lower() if founder.sector else ""
    
    if founder_sector in investor_sectors:
        score += 50
    
    if investor.investment_stage and founder.stage:
        if investor.investment_stage.lower() == founder.stage.lower():
            score += 30
    
    inv_stage_str = investor.investment_stage.lower() if investor.investment_stage else ""
    keywords = investor_sectors + [inv_stage_str]
    
    if founder.description:
        description_hits = sum(1 for word in keywords if word and word in founder.description.lower())
        if description_hits > 0:
            score += min(20, description_hits * 5)
            
    return score

def calculate_rule_based_score(application, investor):
    """
    Calculates a compatibility score (0-100) based on hard constraints 
    like Sector and Investment Stage.
    """
    score = 0
    
    # 1. Sector Matching (40% of rule-based score)
    app_sector = application.sector.lower() if application.sector else ""
    investor_sectors = [s.strip().lower() for s in getattr(investor, 'investment_focus', '').split(',') if s.strip()]

    if app_sector in investor_sectors:
        score += 40
    elif any(s in app_sector for s in investor_sectors if s):
        score += 25

    # 2. Stage Matching (60% of rule-based score)
    app_stage = application.stage.lower() if application.stage else ""
    inv_stage = investor.investment_stage.lower() if investor.investment_stage else ""

    if app_stage == inv_stage:
        score += 60
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

def get_blended_match(ai_score, rule_score, application, investor):
    """
    Enhanced blended match that incorporates historical thumbs up/down feedback.
    """
    base_score = (rule_score * 0.7) + (ai_score * 0.3)
    
    from matchmaking.models import MatchFeedback
    feedback = MatchFeedback.objects.filter(application=application, investor=investor).first()
    
    if feedback:
        if feedback.vote == 1:
            return min(base_score + 15, 100)
        if feedback.vote == -1:
            return base_score * 0.5
            
    return round(base_score, 2)