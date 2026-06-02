from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator


class Application(models.Model):
    """
    Founder Application Profile Engine
    Stores institutional and deck credentials for startup ventures.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_founder_profile"  # Matches views.py getattr lookups
    )
    company_name = models.CharField(max_length=255)
    company_website = models.URLField(max_length=500, blank=True, null=True)
    founder_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=254)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Text Analysis Blocks (Fed directly into Zelda AI vector matching engine)
    description = models.TextField(verbose_name="Executive Summary")
    reason_for_capital = models.TextField(blank=True, null=True)
    extra_info = models.TextField(blank=True, null=True)
    
    # Traction Matrix Fields
    sector = models.CharField(max_length=100, default='Other')
    stage = models.CharField(max_length=100, default='Seed', verbose_name="Funding Stage")
    raising_amount = models.IntegerField(default=0, help_text="Numeric value for search filtering")
    current_revenue = models.IntegerField(default=0, help_text="Numeric value for search filtering")
    prior_amount_raised = models.CharField(max_length=100, blank=True, null=True)
    years_in_business = models.CharField(max_length=50, blank=True, null=True)
    company_size = models.CharField(max_length=50, blank=True, null=True)
    
    # Secure Asset Upload Engine supporting documents and slide decks
    pitch_deck = models.FileField(
        upload_to="pitch_decks/",
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "pptx", "ppt"])],
        blank=True,
        null=True
    )
    
    # Zelda AI Cache Layer Vectors
    description_vector = models.JSONField(blank=True, null=True, help_text="Stores embeddings array")
    
    # System Visibility Control State Switches
    is_private = models.BooleanField(
        default=False, 
        help_text="Enable incognito mode to omit your application from global filters and automated AI indexing."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Founder Application"
        verbose_name_plural = "Founder Applications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company_name} ({self.founder_name})"
    
    @property
    def funding_stage(self):
        return self.stage

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
    score = models.FloatField()
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