# matchmaking/journey_actions.py
"""
Per-checklist-item copy for the "Next best improvement" card the Zelda
widget shows (see zelda_api/views.py::JourneyStatusAPIView). Every
statement here is true regardless of how matching or ranking changes
later — e.g. "uploading a deck lets Zelda generate a brief" is something
the app actually does (zelda_api/pipeline_views.py), not an invented
number like "improves match quality by 12%" that nothing computes.

Keyed by the exact checklist label text from matchmaking/utils.py's
compute_*_journey_stage functions — a handful of labels (e.g. "Verify
your business email") are shared verbatim across roles, so one entry
covers all of them; the founder- and seller-specific "generate a Zelda
brief from your deck/CIM" entries deliberately differ since the two
document types feed different Zelda reports.
"""

ACTION_INFO = {
    # Founder
    'Create your founder profile': {
        'why_it_matters': "I need your profile before I can start matching you with investors.",
        'estimated_minutes': 5,
        'action_label': 'Create Profile',
    },
    'Upload a pitch deck or pitch video': {
        'why_it_matters': "Upload a pitch deck and I can generate a full Zelda Intelligence Brief for investors — deeper diligence than a profile alone.",
        'estimated_minutes': 2,
        'action_label': 'Upload Pitch Deck',
    },
    'Publish a blog post to boost visibility': {
        'why_it_matters': "A blog post gives investors more context on your thinking and helps you show up in search.",
        'estimated_minutes': 10,
        'action_label': 'Write a Post',
    },
    "Post a job to show you're growing": {
        'why_it_matters': "An open job posting is a concrete signal to investors that you're scaling.",
        'estimated_minutes': 5,
        'action_label': 'Post a Job',
    },
    'Connect with other businesses': {
        'why_it_matters': "Following other founders and investors helps me learn who you want to be matched with.",
        'estimated_minutes': 1,
        'action_label': 'Browse the Bulletin',
    },
    'Upload your business plan to Zelda for a competitiveness match': {
        'why_it_matters': "I'll cross-check your plan against real filings and market data before founders and investors see it.",
        'estimated_minutes': 3,
        'action_label': 'Upload to Zelda',
    },
    'Verify your business email': {
        'why_it_matters': "Verified profiles build more trust with the people reviewing your opportunity.",
        'estimated_minutes': 2,
        'action_label': 'Verify Email',
    },

    # Investor
    'Create your investor profile': {
        'why_it_matters': "I need your mandate before I can start surfacing founders.",
        'estimated_minutes': 5,
        'action_label': 'Create Mandate',
    },
    'Complete every mandate field': {
        'why_it_matters': "A complete mandate gives me the detail I need to match you accurately.",
        'estimated_minutes': 3,
        'action_label': 'Complete Mandate',
    },
    'Upload your portfolio for a similarity match': {
        'why_it_matters': "I can surface founders whose profile resembles companies already in your portfolio.",
        'estimated_minutes': 3,
        'action_label': 'Upload Portfolio',
    },

    # Seller
    'Create your business listing': {
        'why_it_matters': "I need your listing before I can start matching you with buyers.",
        'estimated_minutes': 5,
        'action_label': 'Create Listing',
    },
    'Upload a CIM document': {
        'why_it_matters': "Upload a CIM and I can generate a full Zelda Intelligence Brief for buyers — deeper diligence than a listing alone.",
        'estimated_minutes': 3,
        'action_label': 'Upload CIM',
    },
    'Get a Zelda valuation to price your asking price with confidence': {
        'why_it_matters': "I can generate an AI-backed valuation estimate from your financials.",
        'estimated_minutes': 3,
        'action_label': 'Get a Valuation',
    },

    # Buyer
    'Create your buyer profile': {
        'why_it_matters': "I need your acquisition mandate before I can start surfacing listings.",
        'estimated_minutes': 5,
        'action_label': 'Create Mandate',
    },
}


# Thresholds on the checklist's done/total ratio — a word, not a number,
# is what the UI shows (see JourneyStatusAPIView and the "My Progress"
# tab); the ratio itself only ever drives the strength bar's width.
_STRENGTH_LABELS = (
    (1.0, 'Strong'),
    (0.6, 'Good'),
    (0.01, 'Building'),
)


def compute_profile_strength(checklist):
    """
    {'ratio': 0-1 float, 'label': str} from a journey-stage checklist —
    never shown to the user as a raw percentage, only as a labeled bar.
    """
    total = len(checklist)
    if total == 0:
        return {'ratio': 0.0, 'label': 'Just Started'}

    done = sum(1 for item in checklist if item['done'])
    ratio = done / total

    for threshold, label in _STRENGTH_LABELS:
        if ratio >= threshold:
            return {'ratio': ratio, 'label': label}
    return {'ratio': ratio, 'label': 'Just Started'}
