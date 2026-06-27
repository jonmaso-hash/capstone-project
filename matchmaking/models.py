from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.contrib.auth.models import User


class Application(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='match_founder_profile'
    )
    
    pitch_video = models.FileField(
        upload_to='pitch_videos/%Y/%m/', 
        blank=True, 
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'mov', 'webm'])],
        help_text="Upload a short 1-3 minute video pitch (MP4, MOV, WEBM)."
    )
    
    allow_direct_messages = models.BooleanField(
        default=False, 
        help_text="If True, verified users can bypass the matchmaking radar to initiate a Deal Room chat."
    )
    
    geography = models.CharField(
    max_length=255,
    blank=True,
    null=True
    )

    description_embedding = models.JSONField(
    blank=True,
    null=True
    )
    
    zelda_summary = models.TextField(
    blank=True,
    null=True
)

    zelda_risk_assessment = models.TextField(
    blank=True,
    null=True
)

    zelda_last_analysis = models.DateTimeField(
    blank=True,
    null=True
)
    
    description_vector = models.JSONField(blank=True, null=True)
    
    # Basic Info
    company_name = models.CharField(max_length=255)
    company_website = models.URLField(max_length=500, blank=True, null=True)
    founder_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=254)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    linkedin_url = models.URLField(max_length=500, blank=True, null=True)
    
    
    # Fields causing FieldError
    description = models.TextField(verbose_name="Executive Summary")
    reason_for_capital = models.TextField(blank=True, null=True)
    extra_info = models.TextField(blank=True, null=True)
    pitch_deck = models.FileField(upload_to='decks/', validators=[FileExtensionValidator(['pdf', 'pptx'])], blank=True, null=True)
    prior_amount_raised = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    company_size = models.PositiveIntegerField(null=True, blank=True) # Alias to fix FieldError
    
    # Zelda AI Engine Fields
    sector = models.CharField(max_length=100, default='Other')
    stage = models.CharField(max_length=100, default='Seed')
    raising_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    current_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    monthly_burn_rate = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    team_size = models.PositiveIntegerField(null=True, blank=True)
    years_in_business = models.PositiveIntegerField(default=0)
    
    # Metadata
    is_private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True) # Fixes Admin E035
    updated_at = models.DateTimeField(auto_now=True)
    
    zelda_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    runway_months = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)

    def save(self, *args, **kwargs):
        # Optional: Auto-run calculation on save if you want it to be instant
        super().save(*args, **kwargs)
    

    @property
    def completion_percentage(self):
        """Dynamically computes the data density score for the Zelda AI matrix."""
        tracked_fields = [
            self.company_name, self.company_website, self.founder_name,
            self.email, self.phone_number, self.description, self.sector,
            self.stage, self.raising_amount, self.current_revenue, self.pitch_deck
        ]
        filled_fields = sum(1 for field in tracked_fields if field)
        return int((filled_fields / len(tracked_fields)) * 100)

    @property
    def funding_stage(self):
        """Alias property to ensure seamless template compatibility across app contexts."""
        return self.stage
    
    @property
    def location(self):
        return self.geography
    
    def to_foundry_envelope(self):
        return {
        "origin": "application",
        "timestamp": self.updated_at.isoformat(),
        "payload": {
            "company_name": self.company_name,
            "sector": self.sector,
            "stage": self.stage,
            "raising_amount": float(self.raising_amount),
            "completion_percentage": self.completion_percentage,
        }
    }


class InvestorApplication(models.Model):
    """
    Investor Profile Mandate Engine
    Manages search priority targets and ticket capacities for venture funds and angels.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_investor_profile"  # Matches views.py getattr lookups
    )
    allow_direct_messages = models.BooleanField(
        default=False,
        help_text="If True, verified users can bypass the matchmaking radar to initiate a Deal Room chat."
    )
    portfolio_raw_text = models.TextField(
    blank=True,
    null=True
    )

    focus_embedding = models.JSONField(
    blank=True,
    null=True
    )
    
    investment_thesis_summary = models.TextField(
    blank=True,
    null=True
    )

    last_portfolio_analysis = models.DateTimeField(
    blank=True,
    null=True
    )
    
    location = models.CharField(
    max_length=255,
    blank=True,
    null=True
    )
    
    full_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=254)
    phone = models.CharField(max_length=50, blank=True, null=True)
    company_name = models.CharField(max_length=255)
    website = models.URLField(max_length=500, blank=True, null=True)
    
    # Focus Metrics for Similarity Processing Layouts
    investment_focus = models.TextField()
    investment_stage = models.CharField(max_length=100)
    investment_amount = models.CharField(max_length=100, default='Unspecified', verbose_name="Target Ticket Size")    
    # Zelda AI Cache Layer Vectors
    focus_vector = models.JSONField(blank=True, null=True, help_text="Stores embeddings array")

    # Visibility and Log Infrastructure
    is_private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Investor Profile"
        verbose_name_plural = "Investor Profiles"
        ordering = ["-created_at"]
        
    def to_foundry_envelope(self):
        return {
        "origin": "investor_application",
        "timestamp": self.updated_at.isoformat(),
        "payload": {
            "company_name": self.company_name,
            "investment_focus": self.investment_focus,
            "investment_stage": self.investment_stage,
            "investment_amount": self.investment_amount,
            "completion_percentage": self.completion_percentage,
        }
    }
        
    @property
    def completion_percentage(self):
        """Dynamically computes the mandate specification density for recommendations."""
        tracked_fields = [
            self.full_name, self.email, self.phone, self.company_name,
            self.website, self.investment_focus, self.investment_stage,
            self.investment_amount
        ]
        filled_fields = sum(1 for field in tracked_fields if field)
        return int((filled_fields / len(tracked_fields)) * 100)

    def __str__(self):
        return f"{self.company_name} Investment Mandate ({self.full_name})"


class Connection(models.Model):
    """
    Handshake Request Mapping Architecture
    Tracks platform introductions between investors and founders.
    """
    investor = models.ForeignKey(InvestorApplication, on_delete=models.CASCADE, related_name="connections")
    founder = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="connections")
    status = models.CharField(max_length=50, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("investor", "founder")
        verbose_name = "Platform Connection"
        verbose_name_plural = "Platform Connections"


class MatchFeedback(models.Model):
    """
    Engagement Logging Matrix
    Stores user interaction votes (upvotes/downvotes) to fine-tune recommendation systems.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="feedback")
    investor = models.ForeignKey(InvestorApplication, on_delete=models.CASCADE, related_name="feedback")
    vote = models.IntegerField(choices=[(1, "Upvote"), (-1, "Downvote")])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Match Feedback"
        verbose_name_plural = "Match Feedbacks"


class AIMatch(models.Model):
    """
    Pre-calculated AI Scoring Manifest
    Saves computed vector matrix weights for reporting, admin panels, or async processes.
    """
    investor = models.ForeignKey(InvestorApplication, on_delete=models.CASCADE, related_name="ai_matches")
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="ai_matches")
    score = models.DecimalField(
    max_digits=6,
    decimal_places=3
)
    match_reason = models.TextField(
    blank=True,
    null=True
)
    geography = models.CharField(

    max_length=255,

    blank=True,

    null=True

)

    confidence_score = models.DecimalField(
    max_digits=5,
    decimal_places=2,
    default=0
)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "AI Match Log"
        verbose_name_plural = "AI Match Logs"
        ordering = ["-score"]
        
class ConnectionRequest(models.Model):
    founder = models.ForeignKey('Application', on_delete=models.CASCADE, related_name='inbound_requests')
    investor = models.ForeignKey('InvestorApplication', on_delete=models.CASCADE, related_name='outbound_requests')
    status = models.CharField(
        max_length=20, 
        choices=[('PENDING', 'Pending'), ('ACCEPTED', 'Accepted'), ('DECLINED', 'Declined')],
        default='PENDING'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
class DealRoom(models.Model):
    # Linked to a specific Connection between Founder and Investor
    connection = models.OneToOneField('Connection', on_delete=models.CASCADE, related_name='deal_room')
    is_active = models.BooleanField(default=False) # Access is locked until founder approves
    created_at = models.DateTimeField(auto_now_add=True)

class Document(models.Model):
    deal_room = models.ForeignKey(DealRoom, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='deal_rooms/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
        
class Follow(models.Model):
    # The person clicking the follow button
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        related_name='following_relationships', 
        on_delete=models.CASCADE
    )
    # The person being followed
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        related_name='follower_relationships', 
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevents duplicate follow records in the database
        unique_together = ('follower', 'following')

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"
    

    
