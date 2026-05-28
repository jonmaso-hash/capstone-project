from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator

# =================================================
# APPLICATION (FOUNDERS)
# =================================================
class Application(models.Model):
    """
    Founder Venture Profile Matrix.
    Tracks personal details, physical HQ location bounds, financial targets,
    and Gemini AI multimodal context files.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_founder_profile"
    )
    
    # --- ADD THIS PRIVACY FIELD LAYER ---
    is_private = models.BooleanField(
        default=False, 
        help_text="Hides your startup profile from the global search directory and the public board."
    )

    # Founder Personal & Location Data
    founder_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    linkedin_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Founder LinkedIn Profile")
    location = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="HQ Operating Location (e.g., San Francisco, CA or London, UK)"
    )
    
    # Company Metrics
    company_name = models.CharField(max_length=255)
    company_website = models.URLField(max_length=500, blank=True, null=True)
    company_size = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., 1-10, 11-50 employees")
    years_in_business = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., Less than 1 year, 1–2 years, 3–5 years")
    
    # AI Processing Inputs
    description = models.TextField(help_text="One-sentence pitch or short technical summary.") 
    sector = models.CharField(max_length=255, blank=True, null=True, help_text="Primary vertical index (e.g., SaaS, FinTech, AI)") 
    stage = models.CharField(max_length=100, blank=True, null=True, help_text="Current fundraising round stage (e.g., Pre-Seed, Seed)")   

    # Multimodal Gemini File Processing Store Pipelines
    pitch_deck = models.FileField(
        upload_to='pitch_decks/%Y/%m/', 
        null=True, 
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        help_text="Founder pitch deck file (PDF) used for multimodal Gemini analysis."
    )
    file_search_store_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        help_text="The native Gemini managed vector file identifier used for grounding queries."
    )

    # Fallback Indexing System
    keywords = models.CharField(
        max_length=500, 
        blank=True, 
        null=True, 
        help_text="Comma-separated tokens for matching algorithms (e.g., saas, b2b, ai)."
    )

    # Financial Configurations (Tolerates structural conversion or direct numeric inputs)
    raising_amount = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="Target fundraising target metric (e.g., 200,000 or 1.5M)."
    )
    prior_amount_raised = models.CharField(
        max_length=100, 
        default="0", 
        blank=True, 
        null=True, 
        help_text="Aggregate capital raised previously."
    )
    current_revenue = models.CharField(
        max_length=100, 
        default="0", 
        blank=True, 
        null=True, 
        help_text="Annual or Monthly Recurring Revenue breakdown metric."
    )

    # Qualitative Breakdowns
    reason_for_capital = models.TextField(blank=True, null=True)
    extra_info = models.TextField(blank=True, null=True)

    # High-Dimensional Core Storage Block
    description_vector = models.JSONField(null=True, blank=True, help_text="System multi-modal float embedding matrix array.")
    
    # Platform Governance Control System
    is_verified = models.BooleanField(
        default=False, 
        help_text="Designates whether this startup has been vetted by the team to appear in general investor bulletin boards."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name if self.company_name else self.founder_name


# =================================================
# INVESTOR APPLICATION (Matchmaking Profile)
# =================================================
class InvestorApplication(models.Model):
    """
    Investor Deployment Mandate Profile.
    Maps check sizes, geographical criteria, and target investment strategies.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_investor_profile"
    )
    
    portfolio_raw_text = models.TextField(
        blank=True, 
        null=True, 
        help_text="Scraped textual layout telemetry from historical fund portfolio data uploads."
    )

    # Personal Profile & Location Section
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True, null=True)
    company_name = models.CharField(max_length=255, verbose_name="Firm / Fund Name")
    website = models.URLField(max_length=500, blank=True, null=True)
    linkedin_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Investor LinkedIn Profile")
    location = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Operating Hub Base (e.g., New York, NY or Toronto, ON)"
    )
    
    # Geolocation Radius Mandate Filtering Field
    target_distance_range = models.CharField(
        max_length=100,
        default="GLOBAL",
        help_text="Target radial allocation limit (e.g., Local, Regional, National, GLOBAL)"
    )

    # Deployment Parameters 
    # Deployment Parameters 
    investment_focus = models.TextField(help_text="Detailed summary of targeted industry criteria or fund investment thesis.")
    investment_stage = models.CharField(max_length=255, help_text="Target stages (e.g., Seed, Series A)") 
    
    # Text choice array configuration
    investment_amount = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Target ticket check size range metric deployment limit (e.g., 250,000-500,000)."
    )

    # Vector Storage Core
    focus_vector = models.JSONField(null=True, blank=True, help_text="System vector embedding cache array representing investment thesis strategy.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # --- INCOGNITO & PRIVACY LAYER ---
    is_private = models.BooleanField(
        default=False, 
        help_text="Incognito Mode: Hides your profile from public visibility boards, global metrics grids, and Zelda AI."
    )

    def __str__(self):
        return f"{self.company_name} ({self.full_name})"


# =================================================
# INTRODUCTIONS & CONNECTIONS (The Handshake)
# =================================================
class Connection(models.Model):
    """
    Platform Introduction Request Tracker.
    Logs direct handshake requests made by investors to founders.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Intro Sent'),
        ('DECLINED', 'Declined'),
        ('ARCHIVED', 'Archived'),
    ]

    investor = models.ForeignKey(InvestorApplication, on_delete=models.CASCADE, related_name='sent_intros')
    founder = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='received_intros')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    investor_note = models.TextField(blank=True, help_text="Optional note provided by the investor to facilitate the introduction.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('investor', 'founder')

    def __str__(self):
        return f"{self.investor.company_name} -> {self.founder.company_name} [{self.status}]"


# =================================================
# AI SCORING & FEEDBACK
# =================================================
class AIMatch(models.Model):
    """
    Automated Matching Score Index.
    Records system score calculations computed via vector logic or deal_screener.py metrics.
    """
    investor = models.ForeignKey(InvestorApplication, on_delete=models.CASCADE, related_name="ai_matches")
    founder = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="ai_matches")
    
    score = models.FloatField(help_text="Calculated match index score spanning 0.0 to 100.0") 
    reasons = models.JSONField(default=list, help_text="Array listing specific context justifications generated by Gemini.") 
    hidden = models.BooleanField(default=False, help_text="Allows users to archive this match configuration from active view feeds.")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-score']
        unique_together = ('investor', 'founder')

    def __str__(self):
        return f"AI Match: {self.investor.company_name} <-> {self.founder.company_name} ({self.score}%)"


class MatchFeedback(models.Model):
    """
    Reinforcement Data Feedback Engine.
    Captures explicit upvotes and downvotes to fine-tune vector routing behaviors over time.
    """
    VOTE_CHOICES = [
        (1, 'Upvote'),
        (-1, 'Downvote'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    investor = models.ForeignKey(InvestorApplication, on_delete=models.CASCADE)
    
    vote = models.SmallIntegerField(choices=VOTE_CHOICES)
    feedback_text = models.TextField(blank=True, null=True, help_text="User descriptive commentary explaining vote rationale.")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'application', 'investor')

    def __str__(self):
        return f"Feedback by {self.user.username} on Match ({self.get_vote_display()})"

from django import forms
from .models import Application, InvestorApplication

class AdvancedFounderForm(forms.ModelForm):
    YEARS_CHOICES = [
        ('<1', 'Less than 1 year'),
        ('1-2', '1–2 years'),
        ('3-5', '3–5 years'),
        ('5+', '5+ years'),
    ]
    SIZE_CHOICES = [
        ('1-10', '1–10 employees'),
        ('11-50', '11–50 employees'),
        ('51-200', '51–200 employees'),
        ('201+', '201+ employees'),
    ]
    
    years_in_business = forms.ChoiceField(choices=YEARS_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    company_size = forms.ChoiceField(choices=SIZE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = Application
        fields = ['years_in_business', 'company_size', 'prior_amount_raised', 'location', 'current_revenue']