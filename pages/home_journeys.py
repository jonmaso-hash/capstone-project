"""Public role journeys and the signed-in homepage path."""

HOME_JOURNEYS = [{'key': 'founder',
  'label': 'Founder',
  'card_goal': 'Raise capital',
  'description': 'Publish your pitch and connect with investors.',
  'title': 'Your path from signup to funding.',
  'goal': 'Your goal: raise capital',
  'steps': [{'title': 'Create your account',
             'description': 'Sign up as a Founder and introduce your company.'},
            {'title': 'Build your pitch',
             'description': 'Complete your profile, add your deck, and share your story.'},
            {'title': 'Get discovered',
             'description': 'Publish your pitch to the Founders Bulletin so investors can discover '
                            'your company.'},
            {'title': 'Connect with investors',
             'description': 'Discover relevant investors and request introductions.'},
            {'title': 'Move toward funding',
             'description': 'Share approved materials, answer questions, and discuss terms.'},
            {'title': 'Add Zelda · optional',
             'description': 'Use Zelda to review your materials, spot gaps, and support your '
                            'preparation at any stage.'}]},
 {'key': 'investor',
  'label': 'Investor',
  'card_goal': 'Find opportunities',
  'description': 'Discover companies and manage your pipeline.',
  'title': 'From signup to informed investment decisions.',
  'goal': 'Your goal: find the right opportunity',
  'steps': [{'title': 'Create your account',
             'description': 'Sign up as an Investor and set your industries, stages, and '
                            'investment range.'},
            {'title': 'Discover companies',
             'description': 'Browse the Founders Bulletin to discover companies and shortlist '
                            'relevant opportunities.'},
            {'title': 'Start the conversation',
             'description': 'Request introductions and connect privately with founders.'},
            {'title': 'Use your CRM',
             'description': 'Organize your opportunities, track conversations, and manage '
                            'follow-ups.'},
            {'title': 'Add Zelda · optional',
             'description': 'Use intelligence reports to support your research and diligence when '
                            'you need them.'}]},
 {'key': 'seller',
  'label': 'Seller',
  'card_goal': 'Sell your business',
  'description': 'Present your business and connect with buyers.',
  'title': 'From signup to buyer conversations.',
  'goal': 'Your goal: sell your business',
  'steps': [{'title': 'Create your account',
             'description': 'Sign up as a Seller and introduce your business.'},
            {'title': 'Prepare your listing',
             'description': 'Add your business details, financial context, and sale goals.'},
            {'title': 'Build buyer confidence',
             'description': 'Organize materials and use Zelda to identify information gaps.'},
            {'title': 'Connect with buyers',
             'description': 'Help interested buyers understand your business and request '
                            'introductions.'},
            {'title': 'Move toward a sale',
             'description': 'Share approved documents, conduct diligence, and negotiate terms.'}]},
 {'key': 'buyer',
  'label': 'Buyer',
  'card_goal': 'Acquire a business',
  'description': 'Explore businesses and connect with sellers.',
  'title': 'From signup to acquisition conversations.',
  'goal': 'Your goal: acquire a business',
  'steps': [{'title': 'Create your account',
             'description': 'Sign up as a Buyer and describe what you are looking for.'},
            {'title': 'Set your criteria',
             'description': 'Add your target industry, location, and acquisition budget.'},
            {'title': 'Explore businesses',
             'description': 'Browse seller profiles and shortlist businesses that fit.'},
            {'title': 'Review the opportunity',
             'description': 'Use Zelda reports and approved documents to support your diligence.'},
            {'title': 'Move toward acquisition',
             'description': 'Connect with sellers, ask questions, and negotiate directly.'}]}]


def home_journey_context(request):
    """Use the same profile precedence as the post-login dashboard router."""
    if not request.user.is_authenticated:
        return {"home_journeys": HOME_JOURNEYS, "home_journey_signed_in": False}
    for journey in HOME_JOURNEYS:
        if getattr(request.user, "match_" + journey["key"] + "_profile", None) is not None:
            return {"home_journeys": [journey], "home_journey_signed_in": True}
    pending_role = request.session.get("pending_profile_role")
    for journey in HOME_JOURNEYS:
        if journey["key"] == pending_role:
            return {"home_journeys": [journey], "home_journey_signed_in": True}
    return {"home_journeys": [], "home_journey_signed_in": True}
