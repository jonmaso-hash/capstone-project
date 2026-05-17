from django.db import models
from django.conf import settings

# =================================================
# APPLICATION (FOUNDERS)
# =================================================
class Application(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_founder_profile"
    )

    # Founder & Company info
    founder_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=30, blank=True, null=True)
    company_name = models.CharField(max_length=255)
    company_website = models.URLField(blank=True, null=True)
    
    # AI INPUT FIELDS
    description = models.TextField() 
    sector = models.CharField(max_length=255, blank=True, null=True) # Maps to investor.investment_focus / sector lookups
    stage = models.CharField(max_length=50, blank=True, null=True)   # Maps to investor.investment_stage

    # MULTIMODAL DEAL SCREENING DATA
    pitch_deck = models.FileField(
        upload_to='pitch_decks/', 
        null=True, 
        blank=True,
        help_text="Founder pitch deck file (PDF) used for multimodal Gemini analysis."
    )
    file_search_store_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        help_text="The native Gemini managed vector store identifier used for grounding checks."
    )

    # ADVANCED KEYWORD MATCHING
    # This stores explicit comma-separated fallback keywords (e.g., "saas, b2b, ai, fintech")
    # used alongside vector logic to maximize query accuracy across complex mandates.
    keywords = models.CharField(
        max_length=500, 
        blank=True, 
        null=True, 
        help_text="Comma-separated fallback tags for strict keyword matching."
    )

    # Financials
    current_revenue = models.CharField(max_length=50, blank=True, null=True)
    years_in_business = models.PositiveIntegerField(blank=True, null=True)
    company_size = models.CharField(max_length=50, blank=True, null=True)
    raising_amount = models.CharField(max_length=50, blank=True, null=True)
    prior_amount_raised = models.CharField(max_length=50, blank=True, null=True)

    # Qualitative
    reason_for_capital = models.TextField(blank=True, null=True)
    extra_info = models.TextField(blank=True, null=True)

    # THE AI BRAIN
    description_vector = models.JSONField(null=True, blank=True)
    
    # BROKERAGE OVERSIGHT
    is_verified = models.BooleanField(
        default=False, 
        help_text="Designates whether this startup has been vetted by the brokerage team to appear in investor matching."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name or self.founder_name


# =================================================
# INVESTOR APPLICATION (Matchmaking Profile)
# =================================================
class InvestorApplication(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_investor_profile"
    )

    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True, null=True)
    company_name = models.CharField(max_length=255)
    website = models.URLField(max_length=500, blank=True, null=True)

    # AI INPUT FIELDS
    investment_focus = models.TextField() # e.g., "Looking for automated workflow management and cross-border fintech b2b SaaS."
    investment_stage = models.CharField(max_length=255) # e.g., "Seed, Series A"
    investment_amount = models.CharField(max_length=50, blank=True, null=True)

    # THE AI BRAIN
    focus_vector = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_name} ({self.full_name})"


# =================================================
# INTRODUCTIONS & CONNECTIONS (The Handshake)
# =================================================
class Connection(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Intro Sent'),
        ('DECLINED', 'Declined'),
        ('ARCHIVED', 'Archived'),
    ]

    investor = models.ForeignKey(InvestorApplication, on_delete=models.CASCADE, related_name='sent_intros')
    founder = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='received_intros')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    investor_note = models.TextField(blank=True, help_text="Optional note provided by the investor to facilitate the intro request.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('investor', 'founder') # Double safety constraint to prevent duplicate introduction requests

    def __str__(self):
        return f"{self.investor.company_name} -> {self.founder.company_name} [{self.status}]"


# =================================================
# AI SCORING & FEEDBACK
# =================================================
class AIMatch(models.Model):
    investor = models.ForeignKey(InvestorApplication, on_delete=models.CASCADE, related_name="ai_matches")
    founder = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="ai_matches")
    
    score = models.FloatField() 
    reasons = models.JSONField(default=list) 
    hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-score']
        unique_together = ('investor', 'founder')


class MatchFeedback(models.Model):
    VOTE_CHOICES = [
        (1, 'Upvote'),
        (-1, 'Downvote'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    investor = models.ForeignKey(InvestorApplication, on_delete=models.CASCADE)
    vote = models.SmallIntegerField(choices=VOTE_CHOICES)
    feedback_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'application', 'investor')