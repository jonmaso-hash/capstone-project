import requests

def calculate_match_score(investor, founder):
    """
    Calculates a match percentage between an investor and a founder.
    """
    score = 0
    # Logic unchanged to preserve existing behavior
    investor_sectors = [s.strip().lower() for s in investor.interested_sectors.split(',')]
    if founder.industry.lower() in investor_sectors:
        score += 50
    
    if investor.investment_stage.lower() == founder.stage.lower():
        score += 30
    
    keywords = investor_sectors + [investor.investment_stage.lower()]
    description_hits = sum(1 for word in keywords if word in founder.description.lower())
    
    if description_hits > 0:
        score += min(20, description_hits * 5)
    return score

def get_blended_match(ai_score, rule_score, application, investor):
    """
    Calculates a blended match score based on AI similarity and rule compliance.
    """
    # Example blending logic:
    # Adjust weights (0.7 and 0.3) to suit your project's specific needs
    final_score = (ai_score * 0.7) + (rule_score * 0.3)
    return round(final_score, 2)
