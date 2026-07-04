from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from .validators import MaxFileSizeValidator

REVIEW_STATUS_CHOICES = [
    ('APPROVED', 'Approved'),
    ('PENDING', 'Pending Review'),
    ('DENIED', 'Denied'),
]


class Application(models.Model):
    # Fields that feed the AI match vector — editing any of these re-locks
    # the group for 30 days (see vector_fields_locked below).
    VECTOR_FIELDS = ['description', 'sector', 'stage', 'extra_info', 'reason_for_capital', 'geography']

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='match_founder_profile'
    )
    
    pitch_video = models.FileField(
        upload_to='pitch_videos/%Y/%m/',
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=['mp4', 'mov', 'webm']),
            MaxFileSizeValidator(max_mb=200),
        ],
        help_text="Upload a short 1-3 minute video pitch (MP4, MOV, WEBM). Max 200MB."
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
    pitch_deck = models.FileField(
        upload_to='decks/',
        validators=[FileExtensionValidator(['pdf', 'pptx']), MaxFileSizeValidator(max_mb=25)],
        blank=True, null=True,
    )
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
    is_verified = models.BooleanField(default=False)
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='APPROVED')
    denial_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True) # Fixes Admin E035
    updated_at = models.DateTimeField(auto_now=True)
    vector_fields_updated_at = models.DateTimeField(null=True, blank=True)

    zelda_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    runway_months = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)

    def save(self, *args, **kwargs):
        # Optional: Auto-run calculation on save if you want it to be instant
        super().save(*args, **kwargs)

    @property
    def vector_fields_locked(self):
        if not self.vector_fields_updated_at:
            return False
        return timezone.now() < self.vector_fields_updated_at + timedelta(days=30)

    @property
    def vector_fields_unlock_at(self):
        if not self.vector_fields_updated_at:
            return None
        return self.vector_fields_updated_at + timedelta(days=30)

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

    class Meta:
        # is_private + review_status are filtered together on every single
        # matching/dashboard/bulletin-board query in the app (founder_dashboard,
        # investor_dashboard, founder_bulletin_board, global_search, etc.) —
        # this is the single most-repeated query shape in the whole codebase.
        indexes = [
            models.Index(fields=['is_private', 'review_status']),
        ]


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
    linkedin_url = models.URLField(max_length=500, blank=True, null=True)
    
    # Focus Metrics for Similarity Processing Layouts
    investment_focus = models.TextField()
    investment_stage = models.CharField(max_length=100)
    investment_amount = models.CharField(max_length=100, default='Unspecified', verbose_name="Target Ticket Size")    
    # Zelda AI Cache Layer Vectors
    focus_vector = models.JSONField(blank=True, null=True, help_text="Stores embeddings array")

    # Visibility and Log Infrastructure
    is_private = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False, help_text="Premium tier: bypasses the daily outreach cap.")
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='APPROVED')
    denial_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Investor Profile"
        verbose_name_plural = "Investor Profiles"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['is_private', 'review_status']),
        ]
        
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
    initiated_by = models.CharField(
        max_length=20,
        choices=[('INVESTOR', 'Investor'), ('FOUNDER', 'Founder')],
        default='INVESTOR',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Deal Pulse — investor's own manual triage on top of the connection's
    # actual status, plus private working notes.
    needs_attention = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

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


class PitchDeckViewSession(models.Model):
    """One row per browser session that opened a founder's pitch deck viewer."""
    founder = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='deck_view_sessions')
    viewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client_session_id = models.CharField(max_length=64)
    started_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('founder', 'viewer', 'client_session_id')


class PitchDeckSlideTime(models.Model):
    """
    Append-only per-slide duration deltas reported by the viewer via sendBeacon.
    The client resets its local accumulator after each successful send, so these
    rows are incremental, not cumulative — analytics just SUM them per slide.
    """
    session = models.ForeignKey(PitchDeckViewSession, on_delete=models.CASCADE, related_name='slide_times')
    slide_number = models.PositiveIntegerField()
    duration_seconds = models.FloatField()
    recorded_at = models.DateTimeField(auto_now_add=True)


class FundraisingLead(models.Model):
    """
    A founder's personal outreach tracker — most leads here won't be
    registered Interlink Foundry members, so this is deliberately decoupled
    from Connection (which represents a specific platform intro-request).
    """
    STAGE_CHOICES = [
        ('LEADS', 'Leads'),
        ('CONTACTED', 'Contacted'),
        ('MEETING_BOOKED', 'Meeting Booked'),
        ('DUE_DILIGENCE', 'Due Diligence'),
        ('TERM_SHEET', 'Term Sheet'),
    ]
    founder = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='fundraising_leads')
    investor_name = models.CharField(max_length=255)
    firm_name = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='LEADS')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.investor_name} ({self.get_stage_display()})"


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


class FounderMilestone(models.Model):
    """
    Founder-posted progress updates (revenue, customers, product launches,
    hiring). Investors following the founder are notified when one is posted.
    """
    MILESTONE_TYPES = [
        ('revenue', 'Revenue Milestone'),
        ('customers', 'Customer Milestone'),
        ('product_launch', 'Product Launch'),
        ('hiring', 'Hiring Update'),
        ('funding', 'Funding Update'),
        ('other', 'Other'),
    ]
    founder = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='milestones')
    milestone_type = models.CharField(max_length=20, choices=MILESTONE_TYPES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.founder.company_name}: {self.title}"

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"
    
class InvestorInterestEvent(models.Model):
    """
    Silent background tracking of investor-founder interactions.
    Costs nothing to log now, becomes the foundation for Success
    Vector Score and outcome-based predictions later.
    """
    EVENT_TYPES = [
        ('view',              'Profile View'),
        ('thumbs_up',         'Thumbs Up'),
        ('thumbs_down',       'Thumbs Down'),
        ('analyze',           'Analyzed with Zelda'),
        ('memo_view',         'Viewed Intelligence Memo'),
        ('truth_delta_view',  'Viewed Truth Delta'),
        ('intro_request',     'Requested Introduction'),
        ('message_sent',      'Sent Direct Message'),
        ('funded',            'Deal Funded'),
    ]

    investor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='investor_events'
    )
    founder = models.ForeignKey(
        'matchmaking.Application',
        on_delete=models.CASCADE,
        related_name='interest_events'
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['founder', '-created_at']),
            models.Index(fields=['investor', '-created_at']),
            models.Index(fields=['event_type']),
        ]

    def __str__(self):
        return f"{self.investor.username} → {self.founder.company_name} [{self.get_event_type_display()}]"


def log_investor_event(investor_user, founder_application, event_type, metadata=None):
    """
    Fire-and-forget event logger. Never breaks the calling view,
    even if logging itself fails.
    """
    if not investor_user or not getattr(investor_user, 'is_authenticated', False):
        return
    if not founder_application:
        return
    try:
        InvestorInterestEvent.objects.create(
            investor=investor_user,
            founder=founder_application,
            event_type=event_type,
            metadata=metadata or {}
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to log investor event: {str(e)}")


class APIKey(models.Model):
    """
    Enterprise API tier — lets external firms consume the public matchmaking
    data programmatically. Distinct from the internal SessionAuthentication/
    TokenAuthentication used by the site's own logged-in-user API calls.
    Keys are issued manually by staff via admin for now (no self-serve UI).
    """
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys')
    firm_name = models.CharField(max_length=255, help_text="External firm/organization this key belongs to")
    key = models.CharField(max_length=64, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.key:
            import secrets
            self.key = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.firm_name} ({self.key[:8]}...)"


class InvestorPredictionSnapshot(models.Model):
    """
    Invisible shadow-prediction system: guesses which founder an investor will
    fund next using the same scoring components already driving live
    matching (blended AI + rule score), then grades itself once that investor
    actually funds someone. Never shown to users — staff-only via admin.
    """
    GRADE_CHOICES = [
        ('A', 'A — Predicted Correctly'),
        ('B', 'B — Sector/Stage/Geo Sound, Investor Deviated'),
        ('C', 'C — Partial Signal Match'),
        ('D', 'D — Weak Signal Match'),
        ('F', 'F — Missed Entirely'),
    ]

    investor = models.ForeignKey(InvestorApplication, on_delete=models.CASCADE, related_name='prediction_snapshots')
    predicted_founder = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='predicted_by_snapshots')
    predicted_score = models.FloatField()
    runner_up_founders = models.JSONField(default=list, blank=True, help_text="Top 5 [{founder_id, score}] at snapshot time")
    snapshot_telemetry = models.JSONField(default=dict, blank=True, help_text="InvestorInterestEvent counts + portfolio/vector presence at snapshot time")
    created_at = models.DateTimeField(auto_now_add=True)

    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    actual_funded_founder = models.ForeignKey(
        Application, on_delete=models.CASCADE, null=True, blank=True, related_name='resolved_prediction_snapshots'
    )
    grade = models.CharField(max_length=1, choices=GRADE_CHOICES, null=True, blank=True)
    grade_score = models.FloatField(null=True, blank=True, help_text="0-100 raw score before A-F bucketing")
    grade_explanation = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['investor', '-created_at']),
            models.Index(fields=['is_resolved']),
        ]

    def __str__(self):
        status = f"resolved: {self.grade}" if self.is_resolved else "pending"
        return f"{self.investor.company_name} → predicted {self.predicted_founder.company_name} ({status})"


DEAL_STRUCTURE_CHOICES = [
    ('ASSET_SALE', 'Asset Sale'),
    ('STOCK_SALE', 'Stock Sale'),
    ('MERGER', 'Merger'),
    ('OPEN', 'Open to Either'),
]


class SellerApplication(models.Model):
    """
    Business-for-Sale Profile — the M&A marketplace's mirror of Application
    (Founder). Same shape (vector-embedded matching fields with a 30-day
    edit lock, always-editable deal economics, metadata) but for businesses
    being sold rather than startups raising capital.
    """
    VECTOR_FIELDS = ['description', 'industry', 'geography', 'reason_for_sale', 'extra_info']

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='match_seller_profile'
    )

    company_name = models.CharField(max_length=255)
    company_website = models.URLField(max_length=500, blank=True, null=True)
    seller_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=254)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    linkedin_url = models.URLField(max_length=500, blank=True, null=True)

    description = models.TextField(verbose_name="Business Overview")
    description_vector = models.JSONField(blank=True, null=True)

    industry = models.CharField(max_length=100, default='Other')
    geography = models.CharField(max_length=255, blank=True, null=True)

    annual_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    ebitda = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    asking_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    deal_structure = models.CharField(max_length=20, choices=DEAL_STRUCTURE_CHOICES, default='OPEN')
    team_size = models.PositiveIntegerField(null=True, blank=True)
    years_in_business = models.PositiveIntegerField(default=0)

    reason_for_sale = models.TextField(blank=True, null=True)
    extra_info = models.TextField(blank=True, null=True)
    cim_document = models.FileField(
        upload_to='cim_documents/',
        validators=[FileExtensionValidator(['pdf', 'pptx']), MaxFileSizeValidator(max_mb=25)],
        blank=True, null=True,
        help_text="Confidential Information Memorandum — the standard M&A teaser/info packet. Max 25MB."
    )

    is_private = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='APPROVED')
    denial_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    vector_fields_updated_at = models.DateTimeField(null=True, blank=True)

    @property
    def vector_fields_locked(self):
        if not self.vector_fields_updated_at:
            return False
        return timezone.now() < self.vector_fields_updated_at + timedelta(days=30)

    @property
    def vector_fields_unlock_at(self):
        if not self.vector_fields_updated_at:
            return None
        return self.vector_fields_updated_at + timedelta(days=30)

    def __str__(self):
        return f"{self.company_name} (For Sale)"

    class Meta:
        indexes = [
            models.Index(fields=['is_private', 'review_status']),
        ]


class BuyerApplication(models.Model):
    """
    Acquirer Profile — the M&A marketplace's mirror of InvestorApplication.
    Uses real numeric deal-size ranges (rather than InvestorApplication's
    free-text investment_amount) because deal-economics matching needs
    actual numbers to compare against a seller's asking_price.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='match_buyer_profile'
    )
    full_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=254)
    phone = models.CharField(max_length=50, blank=True, null=True)
    company_name = models.CharField(max_length=255)
    website = models.URLField(max_length=500, blank=True, null=True)
    linkedin_url = models.URLField(max_length=500, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)

    acquisition_thesis = models.TextField(help_text="What kind of businesses are you looking to acquire?")
    focus_vector = models.JSONField(blank=True, null=True)

    target_revenue_min = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    target_revenue_max = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    target_ebitda_min = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    target_ebitda_max = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    budget_min = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    preferred_deal_structure = models.CharField(
        max_length=20,
        choices=DEAL_STRUCTURE_CHOICES + [('NO_PREFERENCE', 'No Preference')],
        default='NO_PREFERENCE'
    )

    is_private = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False, help_text="Premium tier: bypasses the daily outreach cap.")
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='APPROVED')
    denial_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Buyer (Acquirer) Profile"
        verbose_name_plural = "Buyer (Acquirer) Profiles"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['is_private', 'review_status']),
        ]

    @property
    def completion_percentage(self):
        tracked_fields = [
            self.full_name, self.email, self.phone, self.company_name,
            self.website, self.acquisition_thesis, self.budget_min, self.budget_max,
        ]
        filled_fields = sum(1 for field in tracked_fields if field)
        return int((filled_fields / len(tracked_fields)) * 100)

    def __str__(self):
        return f"{self.company_name} Acquisition Mandate ({self.full_name})"


class AcquisitionConnection(models.Model):
    """
    Handshake Request Mapping for the M&A marketplace — mirrors Connection
    (Investor/Founder), but 'CLOSED' replaces 'FUNDED' as the terminal state
    (a completed acquisition rather than a completed funding round).
    """
    buyer = models.ForeignKey(BuyerApplication, on_delete=models.CASCADE, related_name="acquisition_connections")
    seller = models.ForeignKey(SellerApplication, on_delete=models.CASCADE, related_name="acquisition_connections")
    status = models.CharField(max_length=50, default="pending")
    initiated_by = models.CharField(
        max_length=20,
        choices=[('BUYER', 'Buyer'), ('SELLER', 'Seller')],
        default='BUYER',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    needs_attention = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("buyer", "seller")
        verbose_name = "Acquisition Connection"
        verbose_name_plural = "Acquisition Connections"


class DealFeedback(models.Model):
    """
    Buyer thumbs up/down on a seller listing — mirrors MatchFeedback, feeds
    the acquisition bulletin board's match-score tuning exactly like the
    founder bulletin board's MatchFeedback does today.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    seller = models.ForeignKey(SellerApplication, on_delete=models.CASCADE, related_name="deal_feedback")
    buyer = models.ForeignKey(BuyerApplication, on_delete=models.CASCADE, related_name="deal_feedback")
    vote = models.IntegerField(choices=[(1, "Upvote"), (-1, "Downvote")])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Deal Feedback"
        verbose_name_plural = "Deal Feedbacks"


class AcquisitionInterestEvent(models.Model):
    """
    Silent background tracking of buyer-seller interactions — mirrors
    InvestorInterestEvent exactly, same event-type vocabulary swapped to
    the M&A vocabulary ('closed' replaces 'funded').
    """
    EVENT_TYPES = [
        ('view',              'Listing View'),
        ('thumbs_up',         'Thumbs Up'),
        ('thumbs_down',       'Thumbs Down'),
        ('analyze',           'Analyzed with Zelda'),
        ('memo_view',         'Viewed Intelligence Memo'),
        ('truth_delta_view',  'Viewed Truth Delta'),
        ('intro_request',     'Requested Introduction'),
        ('message_sent',      'Sent Direct Message'),
        ('closed',            'Deal Closed'),
    ]

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='buyer_events'
    )
    seller = models.ForeignKey(
        'matchmaking.SellerApplication',
        on_delete=models.CASCADE,
        related_name='interest_events'
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['seller', '-created_at']),
            models.Index(fields=['buyer', '-created_at']),
            models.Index(fields=['event_type']),
        ]

    def __str__(self):
        return f"{self.buyer.username} → {self.seller.company_name} [{self.get_event_type_display()}]"


def log_buyer_event(buyer_user, seller_application, event_type, metadata=None):
    """
    Fire-and-forget event logger for the M&A marketplace — mirrors
    log_investor_event exactly.
    """
    if not buyer_user or not getattr(buyer_user, 'is_authenticated', False):
        return
    if not seller_application:
        return
    try:
        AcquisitionInterestEvent.objects.create(
            buyer=buyer_user,
            seller=seller_application,
            event_type=event_type,
            metadata=metadata or {}
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to log buyer event: {str(e)}")


class BuyerPredictionSnapshot(models.Model):
    """
    Business Marketplace equivalent of InvestorPredictionSnapshot: invisible
    shadow-prediction system that guesses which seller listing a buyer will
    close on next, using the same deal-economics + AI scoring already
    driving buyer_dashboard, then grades itself once that buyer actually
    closes a deal. Never shown to users — staff-only via admin.
    """
    GRADE_CHOICES = [
        ('A', 'A — Predicted Correctly'),
        ('B', 'B — Industry/Size/Structure Sound, Buyer Deviated'),
        ('C', 'C — Partial Signal Match'),
        ('D', 'D — Weak Signal Match'),
        ('F', 'F — Missed Entirely'),
    ]

    buyer = models.ForeignKey(BuyerApplication, on_delete=models.CASCADE, related_name='prediction_snapshots')
    predicted_seller = models.ForeignKey(SellerApplication, on_delete=models.CASCADE, related_name='predicted_by_snapshots')
    predicted_score = models.FloatField()
    runner_up_sellers = models.JSONField(default=list, blank=True, help_text="Top 5 [{seller_id, score}] at snapshot time")
    snapshot_telemetry = models.JSONField(default=dict, blank=True, help_text="AcquisitionInterestEvent counts + vector presence at snapshot time")
    created_at = models.DateTimeField(auto_now_add=True)

    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    actual_closed_seller = models.ForeignKey(
        SellerApplication, on_delete=models.CASCADE, null=True, blank=True, related_name='resolved_prediction_snapshots'
    )
    grade = models.CharField(max_length=1, choices=GRADE_CHOICES, null=True, blank=True)
    grade_score = models.FloatField(null=True, blank=True, help_text="0-100 raw score before A-F bucketing")
    grade_explanation = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['buyer', '-created_at']),
            models.Index(fields=['is_resolved']),
        ]

    def __str__(self):
        status = f"resolved: {self.grade}" if self.is_resolved else "pending"
        return f"{self.buyer.company_name} → predicted {self.predicted_seller.company_name} ({status})"

