def calculate_match_score(investor, founder):
    """
    Calculates a match percentage between an investor and a founder.
    """
    score = 0
    total_weight = 100
    
    # 1. Sector Match (Weight: 50)
    # Assumes interested_sectors is a comma-separated string or list
    investor_sectors = [s.strip().lower() for s in investor.interested_sectors.split(',')]
    if founder.industry.lower() in investor_sectors:
        score += 50
    
    # 2. Stage Match (Weight: 30)
    if investor.investment_stage.lower() == founder.stage.lower():
        score += 30
    
    # 3. 'AI Vibe' / Keyword Match (Weight: 20)
    # This simulates NLP by looking for keywords in the description
    keywords = investor_sectors + [investor.investment_stage.lower()]
    description_hits = sum(1 for word in keywords if word in founder.description.lower())
    
    if description_hits > 0:
        score += min(20, description_hits * 5)

    return score