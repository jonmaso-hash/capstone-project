import re
import uuid
from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from pgvector.django import VectorField
from .validators import MaxFileSizeValidator

REVIEW_STATUS_CHOICES = [
    ('APPROVED', 'Approved'),
    ('PENDING', 'Pending Review'),
    ('DENIED', 'Denied'),
]

# Founder/Seller Premium's monthly highlight perk — a 24-hour visibility
# boost the owner can trigger once every 30 days, replacing the old "full
# counterpart identity in digest" benefit (which let founders/sellers
# identify and solicit investors/buyers directly, off-platform).
HIGHLIGHT_DURATION = timedelta(hours=24)
HIGHLIGHT_COOLDOWN = timedelta(days=30)

# A founder/seller gets a free 24-hour window to fix typos/refine their
# vector-field answers right after saving — editing again inside that window
# just pushes the window out another 24 hours rather than starting the
# 30-day lock early. The 30-day lock only actually begins once 24 hours
# pass with no further edits.
VECTOR_FIELD_EDIT_GRACE_PERIOD = timedelta(hours=24)
VECTOR_FIELD_LOCK_DURATION = timedelta(days=30)

# "Profile complete" is measured everywhere (analytics.py's funnel,
# growth_metrics.py's platform insights) as description_vector__isnull=False.
# Without a floor, a one-word description ("test", "TBD") used to count as
# complete the instant the post_save signal saw any non-empty text at all.
# 10 words is deliberately low — just enough to exclude placeholder text
# without rejecting a real, if brief, one-sentence description.
MIN_FOUNDER_DESCRIPTION_WORDS = 10


def founder_description_meets_word_count(description):
    """Gates AI match-vector generation for Application.description (and
    therefore the 'profile complete' signal derived from description_vector
    everywhere it's read) on a minimum word count."""
    return bool(description) and len(description.split()) >= MIN_FOUNDER_DESCRIPTION_WORDS


class ApplicationQuerySet(models.QuerySet):
    def discoverable(self):
        """
        The one place every bulletin board/matchmaking/search surface should
        filter through — private (incognito) profiles were already excluded
        everywhere via is_private=False; archived profiles (a founder
        between ventures, pausing fundraising) now get the same treatment
        without needing every call site updated by hand.
        """
        return self.filter(is_private=False, archived_at__isnull=True)


class Application(models.Model):
    # Fields that feed the AI match vector — editing any of these re-locks
    # the group for 30 days (see vector_fields_locked below).
    VECTOR_FIELDS = ['description', 'sector', 'stage', 'extra_info', 'reason_for_capital', 'geography']

    objects = ApplicationQuerySet.as_manager()

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

    # Multi-vector chunking — additive, additional to description_vector
    # above (which stays exactly as-is and keeps serving every existing
    # call site unchanged). Each chunk is embedded from a specific,
    # already-existing free-text/structured field rather than an invented
    # category with no source text. Populated lazily by matchmaking/signals.py,
    # same pattern as description_vector.
    problem_solution_vector = models.JSONField(blank=True, null=True, help_text="Embedding of 'description' (Executive Summary).")
    capital_plan_vector = models.JSONField(blank=True, null=True, help_text="Embedding of 'reason_for_capital'.")
    market_context_vector = models.JSONField(blank=True, null=True, help_text="Embedding of sector/stage/geography combined.")

    # Postgres-only ANN fast path — a real pgvector column (fixed 768-dim,
    # separate from the full-size description_vector above) with an HNSW
    # index, used by find_similar_startups to avoid an O(n) Python cosine
    # scan at scale. On SQLite this field exists in Django's model state but
    # has no underlying column (see migration 0049) — nothing outside the
    # postgres-guarded code path in find_similar_startups/signals.py may
    # touch it.
    description_vector_pg = VectorField(dimensions=384, blank=True, null=True)

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
    archived_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Set when the founder archives this profile — hidden from discovery like is_private, "
                   "but distinct so the owner can tell 'paused' apart from 'incognito' and reactivate it.",
    )
    is_verified = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False, help_text="Founder Premium: Featured Placement on the bulletin board.")
    is_staff_featured = models.BooleanField(default=False, help_text="Staff-curated Featured Placement — independent of paid premium status.")
    is_hidden_by_staff = models.BooleanField(default=False, help_text="Hides this pitch deck/video from everyone except the owner and staff.")
    last_highlight_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Founder Premium: last time the monthly 24-hour highlight boost was activated.",
    )
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='APPROVED')
    denial_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True) # Fixes Admin E035
    updated_at = models.DateTimeField(auto_now=True)
    vector_fields_updated_at = models.DateTimeField(null=True, blank=True)
    # Separate from updated_at (which bumps on any field edit) — investors
    # care specifically about deck freshness, not "did they touch the form."
    pitch_deck_uploaded_at = models.DateTimeField(null=True, blank=True)

    # Pitch Videos section — social actions on pitch_video (above), each
    # independently disable-able by the owner via pitch_video_*_enabled so
    # a founder can keep the engagement mechanics social-media users expect
    # without being forced into all of them.
    pitch_video_likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='liked_founder_pitch_videos', blank=True
    )
    pitch_video_saves = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='saved_founder_pitch_videos', blank=True
    )
    pitch_video_comments_enabled = models.BooleanField(default=True)
    pitch_video_shares_enabled = models.BooleanField(default=True)
    pitch_video_show_like_count = models.BooleanField(default=True)
    pitch_video_notify_on_comments = models.BooleanField(default=True)
    PITCH_VIDEO_VISIBILITY_CHOICES = [
        ('SITE_WIDE', 'Everyone (Pitch Videos section)'),
        ('ROLE_ONLY', 'Investors only'),
        ('PROFILE_ONLY', 'Off — profile page only'),
    ]
    pitch_video_visibility = models.CharField(
        max_length=20, choices=PITCH_VIDEO_VISIBILITY_CHOICES, default='SITE_WIDE'
    )

    zelda_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    runway_months = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, default=None)

    def save(self, *args, **kwargs):
        # Optional: Auto-run calculation on save if you want it to be instant
        super().save(*args, **kwargs)

    @property
    def vector_fields_complete(self):
        """
        True only when every VECTOR_FIELDS entry has a real value. The lock
        is meant to keep the matching algorithm stable once an investor can
        actually see a real, fully-formed profile — locking a half-filled
        profile just penalizes someone still onboarding and serves no
        anti-gaming purpose, since there's nothing stable to protect yet.
        """
        return all(getattr(self, field) for field in self.VECTOR_FIELDS)

    @property
    def vector_fields_locked(self):
        if not self.vector_fields_complete:
            return False
        if not self.vector_fields_updated_at:
            return False
        grace_ends_at = self.vector_fields_updated_at + VECTOR_FIELD_EDIT_GRACE_PERIOD
        now = timezone.now()
        if now < grace_ends_at:
            return False
        return now < grace_ends_at + VECTOR_FIELD_LOCK_DURATION

    @property
    def vector_fields_unlock_at(self):
        if not self.vector_fields_complete:
            return None
        if not self.vector_fields_updated_at:
            return None
        return self.vector_fields_updated_at + VECTOR_FIELD_EDIT_GRACE_PERIOD + VECTOR_FIELD_LOCK_DURATION

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
    def approximate_founding_year(self):
        """
        years_in_business ("Years Since Founding") stays a plain duration
        count — no schema change — but the profile display wants an actual
        year, so this derives one. Approximate because a duration entered at
        any point during the year rounds to the same value; good enough for
        display, not used anywhere in scoring.
        """
        if not self.years_in_business:
            return None
        return timezone.now().year - self.years_in_business

    @property
    def funding_stage(self):
        """Alias property to ensure seamless template compatibility across app contexts."""
        return self.stage

    @property
    def location(self):
        return self.geography

    @property
    def is_highlighted(self):
        return bool(self.last_highlight_at) and timezone.now() - self.last_highlight_at < HIGHLIGHT_DURATION

    @property
    def can_activate_highlight(self):
        if not self.is_premium:
            return False
        if not self.last_highlight_at:
            return True
        return timezone.now() - self.last_highlight_at >= HIGHLIGHT_COOLDOWN

    def activate_highlight(self):
        self.last_highlight_at = timezone.now()
        self.save(update_fields=['last_highlight_at'])

    @property
    def is_archived(self):
        return self.archived_at is not None

    def archive(self):
        """Hides from discovery (see ApplicationQuerySet.discoverable) while keeping every
        document, Zelda report, and Truth Delta history intact — reversible via unarchive()."""
        self.archived_at = timezone.now()
        self.save(update_fields=['archived_at'])

    def unarchive(self):
        self.archived_at = None
        self.save(update_fields=['archived_at'])

    # Canonical Verified Funded helpers — the ONLY thing allowed to produce
    # these is a Connection that reached the mutually-confirmed 'FUNDED'
    # state (see connection_action_view's FUNDED/CONFIRM_FUNDED/DENY_FUNDED
    # handling). Never derive this from a profile field, user-entered text,
    # uploaded document, or AI inference — Zelda can analyze a transaction,
    # but only the counterparty-confirmed status can verify one. Read
    # straight off the querysets rather than a cached counter so there is
    # no duplicated state to drift out of sync.
    @property
    def verified_funding_count(self):
        return self.connections.filter(status='FUNDED').count()

    @property
    def has_verified_funding(self):
        return self.connections.filter(status='FUNDED').exists()

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


class InvestorApplicationQuerySet(models.QuerySet):
    def discoverable(self):
        """See ApplicationQuerySet.discoverable — same is_private/archived_at pattern."""
        return self.filter(is_private=False, archived_at__isnull=True)


class InvestorApplication(models.Model):
    """
    Investor Profile Mandate Engine
    Manages search priority targets and ticket capacities for venture funds and angels.
    """
    objects = InvestorApplicationQuerySet.as_manager()

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
    # Structured, optional hard-filter counterpart to investment_amount's free
    # text above — mirrors BuyerApplication's budget_min/max, which made this
    # exact tradeoff for the same reason (deal-economics matching needs real
    # numbers). Null means "not declared", which fails the hard filter open
    # rather than excluding anyone.
    ticket_size_min = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Minimum Check Size")
    ticket_size_max = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Maximum Check Size")
    # Zelda AI Cache Layer Vectors
    focus_vector = models.JSONField(blank=True, null=True, help_text="Stores embeddings array")

    # Multi-vector chunking — additive, additional to focus_vector above
    # (which stays exactly as-is for every existing call site). Embedded
    # from investment_thesis_summary, falling back to investment_focus when
    # blank, since not every investor fills in the optional thesis summary.
    thesis_vector = models.JSONField(blank=True, null=True, help_text="Embedding of investment_thesis_summary (or investment_focus if blank).")
    # Asymmetric weights an investor sets themselves — "if my profile
    # emphasizes X, weigh X higher." Not normalized to sum to 1 in the DB;
    # get_weighted_chunk_score normalizes at scoring time so a partially
    # filled-in set of weights still behaves sanely.
    weight_problem_solution = models.FloatField(default=0.334, help_text="How much to weigh problem/solution fit (0-1).")
    weight_capital_plan = models.FloatField(default=0.333, help_text="How much to weigh capital-plan/use-of-funds fit (0-1).")
    weight_market_context = models.FloatField(default=0.333, help_text="How much to weigh sector/stage/geography fit (0-1).")

    # Postgres-only ANN twin of focus_vector — see Application.description_vector_pg
    # for the full rationale. No consumer wired yet (find_similar_startups is
    # founder-to-founder only); this exists so an investor-to-investor
    # lookalike search can reuse the same HNSW-indexed column later without
    # another migration.
    focus_vector_pg = VectorField(dimensions=384, blank=True, null=True)

    # Visibility and Log Infrastructure
    is_private = models.BooleanField(default=False)
    archived_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Set when the investor archives this mandate — hidden from discovery like is_private, "
                   "but distinct so the owner can tell 'paused' apart from 'incognito' and reactivate it.",
    )
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

    @property
    def is_archived(self):
        return self.archived_at is not None

    def archive(self):
        self.archived_at = timezone.now()
        self.save(update_fields=['archived_at'])

    def unarchive(self):
        self.archived_at = None
        self.save(update_fields=['archived_at'])

    # Canonical Verified Funded helpers — mirrors Application's (see that
    # model's docstring for the invariant: only a counterparty-confirmed
    # Connection.status == 'FUNDED' may produce these, never a profile
    # field, claim, or AI inference).
    @property
    def verified_funding_count(self):
        return self.connections.filter(status='FUNDED').count()

    @property
    def has_verified_funding(self):
        return self.connections.filter(status='FUNDED').exists()

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
        choices=[('INVESTOR', 'Investor'), ('FOUNDER', 'Founder'), ('STAFF', 'Staff (Manual Intro)')],
        default='INVESTOR',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Deliberately separate from updated_at, which is NOT a reliable proxy
    # for these — Deal Pulse's toggle_deal_attention/update_deal_notes both
    # explicitly touch updated_at on notes/attention edits that can happen
    # long after acceptance (or after FUNDED), so updated_at drifts. Only
    # connection_action_view sets these, exactly once each, at the real
    # transition — see get_deal_activity_timeline in deal_activity.py,
    # which needs a genuinely provable timestamp for these two events.
    accepted_at = models.DateTimeField(null=True, blank=True)
    funded_at = models.DateTimeField(null=True, blank=True)

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
    Cached investor<->founder match score — one row per pair, kept fresh by
    matchmaking/match_cache.py whenever either side's vector changes or the
    founder logs a milestone. This is what the weekly digest reads instead
    of recomputing cosine similarity at send time: match scores are cheap
    to cache and read, so digest/search/homepage should never pay the cost
    of a fresh computation, only the compute-triggering event should.

    last_changed_at/change_reason track *why* a score is fresh — separate
    from created_at, which only reflects when this pair was first scored —
    so the digest can say "confidence increased" or "founder completed a
    milestone" instead of just showing a static number.

    score_generated_at is separate again from last_changed_at: it updates
    on *every* recompute (matchmaking/match_cache.py::upsert_match), even
    when the score barely moves and last_changed_at deliberately doesn't
    bump (see SCORE_CHANGE_EPSILON) — so it answers "when was this number
    last verified against current data," while last_changed_at answers
    "when did something happen worth telling the user about." Conflating
    the two would make either question unanswerable.
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
    score_generated_at = models.DateTimeField(null=True, blank=True)
    last_changed_at = models.DateTimeField(null=True, blank=True)
    change_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "AI Match"
        verbose_name_plural = "AI Matches"
        ordering = ["-score"]
        constraints = [
            models.UniqueConstraint(fields=['investor', 'application'], name='unique_investor_application_match'),
        ]

class ConnectionRequest(models.Model):
    founder = models.ForeignKey('Application', on_delete=models.CASCADE, related_name='inbound_requests')
    investor = models.ForeignKey('InvestorApplication', on_delete=models.CASCADE, related_name='outbound_requests')
    status = models.CharField(
        max_length=20, 
        choices=[('PENDING', 'Pending'), ('ACCEPTED', 'Accepted'), ('DECLINED', 'Declined')],
        default='PENDING'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    

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


class PitchVideoView(models.Model):
    """
    One row per browser session that played a founder's pitch video —
    unlike PitchDeckSlideTime (append-only per-slide deltas), video has a
    single linear timeline, so this tracks the furthest playback position
    reached per session directly, updated in place as the viewer watches.
    """
    founder = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='video_view_sessions')
    viewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client_session_id = models.CharField(max_length=64)
    video_duration_seconds = models.FloatField()
    max_watched_seconds = models.FloatField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('founder', 'viewer', 'client_session_id')


class ProfileView(models.Model):
    """
    Unified profile-view log covering all four account types. Founder/seller
    profile-view counts still primarily come from InvestorInterestEvent /
    AcquisitionInterestEvent (which predate this model and already have
    timestamps), so this exists to close two real gaps: investor/buyer had
    no view tracking at all, and nothing anywhere tracked time-on-page.
    """
    viewed_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile_views_received')
    viewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='profile_views_made')
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['viewed_user', '-created_at']),
            models.Index(fields=['session_key']),
        ]


class MessageThread(models.Model):
    """
    Actual messages live in Stream Chat (external), so this is the local
    proxy for "have these two users ever messaged" — one row per unique
    pair, get-or-created wherever a chat channel is created. user_a/user_b
    are always stored in id order so the same pair can't create two rows
    regardless of who initiated.
    """
    user_a = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='message_threads_as_a')
    user_b = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='message_threads_as_b')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_a', 'user_b')

    @classmethod
    def log_thread(cls, user_1, user_2):
        if not user_1 or not user_2 or user_1.id == user_2.id:
            return
        lo, hi = sorted([user_1, user_2], key=lambda u: u.id)
        cls.objects.get_or_create(user_a=lo, user_b=hi)


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
        ('video_play',        'Pitch Video Played'),
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


COMPANY_SUFFIXES_RE = re.compile(r'(inc|llc|corp|ltd|co|group|holdings)$')


def _normalize_company_string(s):
    """Lowercase, strip non-alphanumerics, then strip one trailing
    corporate suffix (Inc/LLC/Corp/etc.) if present. Never returns an
    empty string when the input had real content — falls back to the
    un-suffix-stripped form rather than over-stripping to ''."""
    normalized = re.sub(r'[^a-z0-9]', '', (s or '').lower())
    stripped = COMPANY_SUFFIXES_RE.sub('', normalized)
    return stripped if stripped else normalized


def company_matches_email_domain(company_name, email):
    """Lenient business-email check: normalized company name and the
    email's domain label (before the TLD) must overlap, either direction.
    "Interlink Foundry" matches interlinkfoundry.com, interlink.com, and
    foundryinc.com. Never raises on malformed input — just returns False."""
    if not company_name or not email or '@' not in email:
        return False
    domain = email.rsplit('@', 1)[-1]
    if '.' not in domain:
        return False
    domain_label = domain.split('.')[0]
    normalized_company = _normalize_company_string(company_name)
    normalized_domain = _normalize_company_string(domain_label)
    if not normalized_company or not normalized_domain:
        return False
    return normalized_domain in normalized_company or normalized_company in normalized_domain


def _resolve_company_name(user):
    """Which profile's company name governs the business-email check, for
    users who may have more than one role — same founder > investor >
    seller > buyer priority accounts/views.py::profile() already uses."""
    for attr in ('match_founder_profile', 'match_investor_profile', 'match_seller_profile', 'match_buyer_profile'):
        profile = getattr(user, attr, None)
        if profile:
            return profile.company_name
    return None


class BusinessEmailVerification(models.Model):
    """
    Self-serve verification for the existing per-role 'Verified' badge
    (Application/InvestorApplication/SellerApplication/BuyerApplication.is_verified,
    all already BooleanField(default=False)). A user submits a business email
    whose domain must match their company name, gets a 6-digit code by real
    email, and typing it back here flips is_verified=True on every role
    profile they have — 'verified' describes the person/business, not one
    role view. FK (not OneToOne) so past attempts stay visible to staff for
    support; the "current" one is the latest PENDING row for a user.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('EXPIRED', 'Expired'),
        ('LOCKED', 'Locked'),
    ]

    MAX_ATTEMPTS = 5
    CODE_EXPIRY = timedelta(minutes=30)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='business_email_verifications')
    business_email = models.EmailField(max_length=254)
    code = models.CharField(max_length=6, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'status'])]

    def save(self, *args, **kwargs):
        if not self.pk:
            if not self.code:
                import secrets
                self.code = f"{secrets.randbelow(1000000):06d}"
            if not self.expires_at:
                self.expires_at = timezone.now() + self.CODE_EXPIRY
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} — {self.business_email} [{self.status}]"


class Firm(models.Model):
    """
    An investor-side team plan: one $5,000/mo subscription (billing/models
    .py's Subscription.Plan.INVESTOR_FIRM) covers up to MAX_SEATS investor
    seats. verified_domain is extracted from the founding member's own
    verified BusinessEmailVerification — the same self-serve verification
    pipeline individual users already go through, not a separate one — so
    a firm is just "everyone who's verified an email on this domain," and
    joining (see billing/views.py::join_firm) needs no separate approval.
    Each seat gets Investor Premium's monthly AI-analysis allowance but a
    higher weekly sub-cap (see zelda_api/quotas.py's FIRM_WEEKLY_CREDIT_
    FRACTION) since team diligence work is burstier than one person's.
    """
    MAX_SEATS = 100

    name = models.CharField(max_length=255)
    verified_domain = models.CharField(max_length=255, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_firm')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.verified_domain})"


class FirmMembership(models.Model):
    """OneToOne on user — one firm per person. See Firm's docstring for the join rules."""
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='memberships')
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='firm_membership')
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} @ {self.firm.name}"


class DataRoomDocument(models.Model):
    """
    Founder-uploaded due-diligence document (cap table, financials, legal/IP).
    Deliberately not routed through zelda_api.DocumentSource — that model's
    status field is a chunking/embedding/analysis pipeline state machine,
    a poor fit for a document that is never meant to be AI-analyzed. Titles
    are visible to any connected investor (see can_view_data_room); whether
    the file itself needs a separate, founder-approved DataRoomAccessRequest
    depends on `visibility` (see can_download_data_room_document).
    """
    CATEGORY_CHOICES = [
        ('CAP_TABLE', 'Cap Table'),
        ('FINANCIALS', 'Financials'),
        ('CUSTOMER_METRICS', 'Customer Metrics'),
        ('REVENUE_BREAKDOWN', 'Revenue Breakdown'),
        ('CONTRACTS', 'Contracts'),
        ('LEGAL_IP', 'Legal / IP'),
        ('PRODUCT_ROADMAP', 'Product Roadmap'),
        ('TEAM_INFO', 'Team Information'),
        ('OTHER', 'Other'),
    ]
    # Per-document trust tier a founder can opt into, independent of
    # category. Defaults to today's exact behavior (INVESTOR_APPROVED) so
    # every pre-existing document and every founder who never touches this
    # field is completely unaffected. There's no separate "Public" tier —
    # can_view_data_room already gates the whole room to accepted-connection
    # investors (or owner/staff), so a document visible to anyone who can
    # see the room at all *is* MATCH_ONLY; a true public tier would mean
    # loosening that room-level gate, a separate decision.
    VISIBILITY_CHOICES = [
        ('MATCH_ONLY', 'Any Connected Investor — no approval needed'),
        ('INVESTOR_APPROVED', 'Requires Founder Approval'),
        ('NDA_REQUIRED', 'Requires Approval + NDA Acknowledgment'),
    ]
    founder = models.ForeignKey('matchmaking.Application', on_delete=models.CASCADE, related_name='data_room_documents')
    file = models.FileField(
        upload_to='data_room/',
        validators=[FileExtensionValidator(['pdf', 'docx', 'xlsx', 'csv', 'pptx']), MaxFileSizeValidator(max_mb=25)],
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER')
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='INVESTOR_APPROVED')
    label = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', '-uploaded_at']

    def __str__(self):
        return f"{self.label} ({self.get_category_display()}) — {self.founder.company_name}"


class DataRoomAccessRequest(models.Model):
    """
    Per-(document, investor) approval gate — applies to INVESTOR_APPROVED
    and NDA_REQUIRED documents (MATCH_ONLY skips this entirely; see
    can_download_data_room_document). An investor sees document titles for
    any founder they're connected to, but downloading a specific file needs
    the founder's explicit approval for that one document — titles are not
    an automatic-access grant. Re-requesting after a DENIED resets the same
    row to PENDING rather than creating a duplicate (see unique_together).
    nda_accepted is only meaningful (and only enforced) for NDA_REQUIRED
    documents — see data_room_request_access, which requires it be set at
    request time for that tier.
    """
    STATUS_CHOICES = [('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('DENIED', 'Denied')]

    document = models.ForeignKey(DataRoomDocument, on_delete=models.CASCADE, related_name='access_requests')
    investor = models.ForeignKey('matchmaking.InvestorApplication', on_delete=models.CASCADE, related_name='data_room_requests')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    nda_accepted = models.BooleanField(default=False)
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('document', 'investor')

    def __str__(self):
        return f"{self.investor.company_name} → {self.document.label} [{self.status}]"


class DataRoomInformationRequest(models.Model):
    """
    Structured "please provide X" request — the mirror image of
    DataRoomAccessRequest, which asks for access to a document that
    already exists. An investor instead picks a category the founder
    hasn't uploaded anything for yet; the founder gets notified and
    either uploads a matching document (data_room_upload auto-fulfills
    any PENDING request in that category) or explicitly declines.
    Fulfilling a request only means the category now has *something* in
    the room — the investor still goes through the normal
    DataRoomAccessRequest flow to actually download that specific file.
    Re-requesting after FULFILLED/DECLINED resets the same row to PENDING
    rather than creating a duplicate (see unique_together) — covers the
    "we need updated financials six months later" case without a second
    row per ask.
    """
    STATUS_CHOICES = [('PENDING', 'Pending'), ('FULFILLED', 'Fulfilled'), ('DECLINED', 'Declined')]

    founder = models.ForeignKey('matchmaking.Application', on_delete=models.CASCADE, related_name='data_room_information_requests')
    investor = models.ForeignKey('matchmaking.InvestorApplication', on_delete=models.CASCADE, related_name='data_room_information_requests')
    category = models.CharField(max_length=20, choices=DataRoomDocument.CATEGORY_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    fulfilled_document = models.ForeignKey(
        DataRoomDocument, on_delete=models.SET_NULL, null=True, blank=True, related_name='fulfilled_information_requests'
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('founder', 'investor', 'category')

    def __str__(self):
        return f"{self.investor.company_name} → {self.get_category_display()} [{self.status}]"


class DataRoomDocumentView(models.Model):
    """Append-only access log — every actual file download is a real
    due-diligence event worth recording distinctly, unlike
    PitchDeckViewSession's per-session dedup."""
    document = models.ForeignKey(DataRoomDocument, on_delete=models.CASCADE, related_name='view_log')
    viewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='data_room_views_made')
    created_at = models.DateTimeField(auto_now_add=True)


def can_view_data_room(request_user, founder_application):
    """Gate for reaching the data room page at all (document titles list) —
    identical logic/order to zelda_api/ic_memo.py::can_view_ic_memo, the
    strict gate, not the looser _can_view_pitch_deck rule (any non-private
    viewer), since cap tables/financials are far more sensitive than a
    pitch deck."""
    if not request_user or not request_user.is_authenticated:
        return False
    if request_user == founder_application.user or request_user.is_staff:
        return True
    investor_profile = getattr(request_user, 'match_investor_profile', None)
    if not investor_profile:
        return False
    return Connection.objects.filter(
        investor=investor_profile, founder=founder_application, status='ACCEPTED'
    ).exists()


def can_download_data_room_document(request_user, document):
    """Separate, stricter gate for the actual file bytes — owner/staff
    always. For an investor it depends on document.visibility:
    MATCH_ONLY skips DataRoomAccessRequest entirely (being allowed into the
    room — can_view_data_room — is itself the only gate); INVESTOR_APPROVED
    needs an APPROVED request same as before this tiering existed;
    NDA_REQUIRED needs an APPROVED request that also has nda_accepted set."""
    if request_user == document.founder.user or request_user.is_staff:
        return True
    investor_profile = getattr(request_user, 'match_investor_profile', None)
    if not investor_profile:
        return False
    if document.visibility == 'MATCH_ONLY':
        return can_view_data_room(request_user, document.founder)
    access_request = DataRoomAccessRequest.objects.filter(
        document=document, investor=investor_profile, status='APPROVED'
    ).first()
    if not access_request:
        return False
    if document.visibility == 'NDA_REQUIRED' and not access_request.nda_accepted:
        return False
    return True


def can_view_deal_workspace(request_user, connection):
    """
    Deal Workspace gate: the two parties to this specific Connection, or
    staff — nobody else, regardless of their role elsewhere on the
    platform. Only meaningful once the relationship is at least ACCEPTED;
    a bare 'pending' request or a DECLINED one has no workspace (there's
    nothing to compose — no chat, no data room access, no point).
    """
    if not request_user or not request_user.is_authenticated:
        return False
    if request_user.is_staff:
        return True
    if request_user not in (connection.founder.user, connection.investor.user):
        return False
    return connection.status in ('ACCEPTED', 'FUNDED_PENDING', 'FUNDED')


def can_view_acquisition_deal_workspace(request_user, acquisition_connection):
    """M&A mirror of can_view_deal_workspace — the two parties to this
    specific AcquisitionConnection (seller/buyer), or staff; CLOSED
    replaces FUNDED as the terminal state, same as everywhere else this
    marketplace's status vocabulary is mirrored."""
    if not request_user or not request_user.is_authenticated:
        return False
    if request_user.is_staff:
        return True
    if request_user not in (acquisition_connection.seller.user, acquisition_connection.buyer.user):
        return False
    return acquisition_connection.status in ('ACCEPTED', 'CLOSED_PENDING', 'CLOSED')


def can_view_pitch_video(viewer_user, owner_profile):
    """
    Single authority for pitch-video visibility — used by BOTH the
    internal-share resolver and the external-share resolver (sharing/
    views.py), so a permission change (owner flips visibility, or a
    profile goes private) takes effect identically everywhere a video
    might be viewed, not just on the profile page itself. Deliberately
    evaluates the VIEWER's current standing, never the sharer's — sharing
    something you can see must never grant someone else access they
    wouldn't otherwise have (see sharing/views.py's resolve_share).

    Works for either owner type (Application/founder or SellerApplication/
    seller) — both share the same is_private/is_hidden_by_staff/
    pitch_video_visibility shape. ROLE_ONLY means "investors only" for a
    founder's video, "buyers only" for a seller's video.
    """
    if not viewer_user or not viewer_user.is_authenticated:
        return False
    if viewer_user == owner_profile.user or viewer_user.is_staff:
        return True
    if owner_profile.is_hidden_by_staff or owner_profile.is_private:
        return False
    if owner_profile.pitch_video_visibility != 'ROLE_ONLY':
        return True
    if isinstance(owner_profile, Application):
        return getattr(viewer_user, 'match_investor_profile', None) is not None
    return getattr(viewer_user, 'match_buyer_profile', None) is not None


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


class SellerApplicationQuerySet(models.QuerySet):
    def discoverable(self):
        """See ApplicationQuerySet.discoverable — same is_private/archived_at pattern."""
        return self.filter(is_private=False, archived_at__isnull=True)


class SellerApplication(models.Model):
    """
    Business-for-Sale Profile — the M&A marketplace's mirror of Application
    (Founder). Same shape (vector-embedded matching fields with a 30-day
    edit lock, always-editable deal economics, metadata) but for businesses
    being sold rather than startups raising capital.
    """
    VECTOR_FIELDS = ['description', 'industry', 'geography', 'reason_for_sale', 'extra_info']

    objects = SellerApplicationQuerySet.as_manager()

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
    pitch_video = models.FileField(
        upload_to='pitch_videos/%Y/%m/',
        blank=True, null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=['mp4', 'mov', 'webm']),
            MaxFileSizeValidator(max_mb=200),
        ],
        help_text="Upload a short 1-3 minute video walking through why you're selling, growth opportunities, and the ideal buyer (MP4, MOV, WEBM). Max 200MB."
    )

    is_private = models.BooleanField(default=False)
    archived_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Set when the seller archives this listing — hidden from discovery like is_private, "
                   "but distinct so the owner can tell 'paused' apart from 'incognito' and reactivate it.",
    )
    is_verified = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False, help_text="Seller Premium: Featured Listing in the business marketplace.")
    is_staff_featured = models.BooleanField(default=False, help_text="Staff-curated Featured Listing — independent of paid premium status.")
    is_hidden_by_staff = models.BooleanField(default=False, help_text="Hides this listing's CIM document from everyone except the owner and staff.")
    last_highlight_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Seller Premium: last time the monthly 24-hour highlight boost was activated.",
    )
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='APPROVED')
    denial_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    vector_fields_updated_at = models.DateTimeField(null=True, blank=True)

    # Pitch Videos section — seller-side mirror of Application's fields above.
    pitch_video_likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='liked_seller_pitch_videos', blank=True
    )
    pitch_video_saves = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='saved_seller_pitch_videos', blank=True
    )
    pitch_video_comments_enabled = models.BooleanField(default=True)
    pitch_video_shares_enabled = models.BooleanField(default=True)
    pitch_video_show_like_count = models.BooleanField(default=True)
    pitch_video_notify_on_comments = models.BooleanField(default=True)
    PITCH_VIDEO_VISIBILITY_CHOICES = [
        ('SITE_WIDE', 'Everyone (Pitch Videos section)'),
        ('ROLE_ONLY', 'Buyers only'),
        ('PROFILE_ONLY', 'Off — profile page only'),
    ]
    pitch_video_visibility = models.CharField(
        max_length=20, choices=PITCH_VIDEO_VISIBILITY_CHOICES, default='SITE_WIDE'
    )

    @property
    def vector_fields_complete(self):
        """See Application.vector_fields_complete — same rationale, seller's own VECTOR_FIELDS list."""
        return all(getattr(self, field) for field in self.VECTOR_FIELDS)

    @property
    def vector_fields_locked(self):
        if not self.vector_fields_complete:
            return False
        if not self.vector_fields_updated_at:
            return False
        grace_ends_at = self.vector_fields_updated_at + VECTOR_FIELD_EDIT_GRACE_PERIOD
        now = timezone.now()
        if now < grace_ends_at:
            return False
        return now < grace_ends_at + VECTOR_FIELD_LOCK_DURATION

    @property
    def vector_fields_unlock_at(self):
        if not self.vector_fields_complete:
            return None
        if not self.vector_fields_updated_at:
            return None
        return self.vector_fields_updated_at + VECTOR_FIELD_EDIT_GRACE_PERIOD + VECTOR_FIELD_LOCK_DURATION

    @property
    def is_highlighted(self):
        return bool(self.last_highlight_at) and timezone.now() - self.last_highlight_at < HIGHLIGHT_DURATION

    @property
    def can_activate_highlight(self):
        if not self.is_premium:
            return False
        if not self.last_highlight_at:
            return True
        return timezone.now() - self.last_highlight_at >= HIGHLIGHT_COOLDOWN

    def activate_highlight(self):
        self.last_highlight_at = timezone.now()
        self.save(update_fields=['last_highlight_at'])

    @property
    def is_archived(self):
        return self.archived_at is not None

    def archive(self):
        self.archived_at = timezone.now()
        self.save(update_fields=['archived_at'])

    def unarchive(self):
        self.archived_at = None
        self.save(update_fields=['archived_at'])

    # Canonical Verified Sold helpers — mirrors Application.has_verified_funding
    # (see that model's docstring for the invariant). Only a counterparty-
    # confirmed AcquisitionConnection.status == 'CLOSED' may produce these.
    @property
    def verified_sale_count(self):
        return self.acquisition_connections.filter(status='CLOSED').count()

    @property
    def has_verified_sale(self):
        return self.acquisition_connections.filter(status='CLOSED').exists()

    def __str__(self):
        return f"{self.company_name} (For Sale)"

    class Meta:
        indexes = [
            models.Index(fields=['is_private', 'review_status']),
        ]


class BuyerApplicationQuerySet(models.QuerySet):
    def discoverable(self):
        """See ApplicationQuerySet.discoverable — same is_private/archived_at pattern."""
        return self.filter(is_private=False, archived_at__isnull=True)


class BuyerApplication(models.Model):
    """
    Acquirer Profile — the M&A marketplace's mirror of InvestorApplication.
    Uses real numeric deal-size ranges (rather than InvestorApplication's
    free-text investment_amount) because deal-economics matching needs
    actual numbers to compare against a seller's asking_price.
    """
    objects = BuyerApplicationQuerySet.as_manager()

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
    archived_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Set when the buyer archives this mandate — hidden from discovery like is_private, "
                   "but distinct so the owner can tell 'paused' apart from 'incognito' and reactivate it.",
    )
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

    @property
    def is_archived(self):
        return self.archived_at is not None

    def archive(self):
        self.archived_at = timezone.now()
        self.save(update_fields=['archived_at'])

    def unarchive(self):
        self.archived_at = None
        self.save(update_fields=['archived_at'])

    # Canonical Verified Sold helpers — mirrors SellerApplication's (see
    # that model's docstring for the invariant).
    @property
    def verified_sale_count(self):
        return self.acquisition_connections.filter(status='CLOSED').count()

    @property
    def has_verified_sale(self):
        return self.acquisition_connections.filter(status='CLOSED').exists()

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
        choices=[('BUYER', 'Buyer'), ('SELLER', 'Seller'), ('STAFF', 'Staff (Manual Intro)')],
        default='BUYER',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Symmetric with Connection.accepted_at/funded_at — same reasoning:
    # updated_at is touched by notes/attention edits that can happen long
    # after either transition, so it can't be trusted for "when did this
    # actually get accepted/closed." Only acquisition_connection_action_view
    # sets these, exactly once each, at the real transition.
    accepted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

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
        ('video_play',        'Pitch Video Played'),
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


class PageEvent(models.Model):
    """
    Anonymous-friendly funnel event for the pre-signup stages (landing page,
    signup started) that InvestorInterestEvent/AcquisitionInterestEvent can't
    cover since there's no authenticated user yet. Session-keyed until a user
    exists, then optionally linked once known.
    """
    EVENT_TYPES = [
        ('landing_view', 'Landing Page View'),
        ('signup_started', 'Signup Page Viewed'),
        ('signup_completed', 'Signup Completed'),
        ('dashboard_view', 'Dashboard/Match List Viewed'),
    ]

    session_key = models.CharField(max_length=40, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='page_events'
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    role = models.CharField(max_length=20, blank=True)
    utm_source = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['event_type', '-created_at']),
            models.Index(fields=['session_key']),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} ({self.session_key[:8]})"


def log_page_event(request, event_type, role='', user=None):
    """
    Fire-and-forget funnel logger for pre-signup traffic — mirrors
    log_investor_event/log_buyer_event's "never break the calling view"
    contract. Dedupes per session+event_type+day so a page refresh doesn't
    spam rows.

    utm_source is captured for first-touch attribution only: read from
    ?utm_source= or ?ref= and stored only if this session has no PageEvent
    at all yet, so a later visit (with or without the param) never
    overwrites how the visitor actually first arrived.
    """
    try:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key

        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        already_logged = PageEvent.objects.filter(
            session_key=session_key, event_type=event_type, created_at__gte=today_start
        ).exists()
        if not already_logged:
            utm_source = ''
            if not PageEvent.objects.filter(session_key=session_key).exists():
                utm_source = (request.GET.get('utm_source') or request.GET.get('ref') or '')[:100]
            PageEvent.objects.create(
                session_key=session_key, event_type=event_type, role=role, user=user, utm_source=utm_source,
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to log page event: {str(e)}")


class SearchEvent(models.Model):
    """
    One row per non-empty search — the filter-based global_search page and
    the Zelda AI sidebar search are two different entry points to "look for
    a company," so `source` distinguishes them for the Engagement tab's
    'searches per user' metric.
    """
    SOURCE_CHOICES = [
        ('filter_search', 'Filter Search'),
        ('zelda_ai_search', 'Zelda AI Search'),
        ('zelda_ask', 'Ask Zelda (NL Query)'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='search_events'
    )
    session_key = models.CharField(max_length=40, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    query_summary = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.get_source_display()}: {self.query_summary[:40]}"


class DigestEngagementEvent(models.Model):
    """
    Funnel instrumentation for the weekly digest email — before this,
    there was zero visibility past "we called send_mail": the email was
    plain text with no link at all, so nothing could tell whether anyone
    opened or clicked it, let alone whether that led anywhere.

    token ties the sent/opened/clicked rows for one digest instance
    together without a self-referencing FK: _send_weekly_digests_body
    generates a fresh token and records 'sent'; the pixel/redirect views
    (matchmaking/views.py::digest_open_pixel/digest_click_redirect) look
    up the 'sent' row by token to know who to attribute the opened/clicked
    event to, then record it with that same token.
    """
    EVENT_TYPES = [
        ('sent', 'Digest Sent'),
        ('opened', 'Digest Opened'),
        ('clicked', 'Hero Match Clicked'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='digest_engagement_events'
    )
    event_type = models.CharField(max_length=10, choices=EVENT_TYPES)
    token = models.UUIDField(default=uuid.uuid4, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['token', 'event_type']),
            models.Index(fields=['event_type', '-created_at']),
        ]

    def __str__(self):
        return f"{self.recipient.username}: {self.get_event_type_display()}"


def log_search_event(request, source, query_summary):
    """
    Fire-and-forget search logger — never breaks the calling view, same
    contract as log_page_event/log_investor_event. Skips silently when
    there's nothing to search on (empty filters/query).
    """
    if not query_summary:
        return
    try:
        session_key = request.session.session_key or ''
        SearchEvent.objects.create(
            user=request.user if request.user.is_authenticated else None,
            session_key=session_key,
            source=source,
            query_summary=query_summary[:255],
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to log search event: {str(e)}")


class MatchTrainingExample(models.Model):
    """
    Data-collection half of the match-feedback loop — logs every organic
    vote/accept/decline and every staff override/manual-intro as a labeled
    (anchor, candidate, label) triple. This is deliberately just the
    pipeline: no training code, no model artifact, no inference path lives
    here. Once there's enough volume, the ops Training Data page's JSONL
    export is what an offline training script would consume.
    """
    ANCHOR_TYPES = [
        ('INVESTOR', 'Investor'),
        ('BUYER', 'Buyer'),
    ]
    CANDIDATE_TYPES = [
        ('FOUNDER', 'Founder'),
        ('SELLER', 'Seller'),
    ]
    LABEL_CHOICES = [
        ('POSITIVE', 'Positive'),
        ('NEGATIVE', 'Negative'),
    ]
    SOURCE_CHOICES = [
        ('thumbs_up', 'Thumbs Up'),
        ('thumbs_down', 'Thumbs Down'),
        ('funded', 'Deal Funded'),
        ('closed', 'Deal Closed'),
        ('declined', 'Declined'),
        ('ops_override', 'Staff Override'),
        ('ops_manual_intro', 'Staff Manual Intro'),
    ]

    anchor_type = models.CharField(max_length=20, choices=ANCHOR_TYPES)
    anchor_id = models.PositiveIntegerField()
    candidate_type = models.CharField(max_length=20, choices=CANDIDATE_TYPES)
    candidate_id = models.PositiveIntegerField()
    label = models.CharField(max_length=20, choices=LABEL_CHOICES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['anchor_type', 'anchor_id']),
            models.Index(fields=['label', 'source']),
        ]

    def __str__(self):
        return f"{self.anchor_type}:{self.anchor_id} → {self.candidate_type}:{self.candidate_id} ({self.label}/{self.source})"


def log_training_example(anchor_type, anchor_id, candidate_type, candidate_id, label, source):
    """
    Fire-and-forget — mirrors log_investor_event's "never break the calling
    view" contract exactly.
    """
    try:
        MatchTrainingExample.objects.create(
            anchor_type=anchor_type, anchor_id=anchor_id,
            candidate_type=candidate_type, candidate_id=candidate_id,
            label=label, source=source,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to log training example: {str(e)}")


class PitchVideoComment(models.Model):
    """
    A comment on a founder's or seller's pitch video — exactly one of
    founder/seller is set (enforced in the posting view, not a DB
    constraint, since cross-backend boolean-XOR CheckConstraints are
    unreliable on SQLite). Kept as one model rather than two parallel
    FounderPitchVideoComment/SellerPitchVideoComment classes since a
    comment's shape (author, body, timestamp) has nothing role-specific
    about it — unlike Connection/AcquisitionConnection, which really do
    have different lifecycle fields per side.
    """
    founder = models.ForeignKey(
        'matchmaking.Application', on_delete=models.CASCADE, null=True, blank=True,
        related_name='pitch_video_comments',
    )
    seller = models.ForeignKey(
        'matchmaking.SellerApplication', on_delete=models.CASCADE, null=True, blank=True,
        related_name='pitch_video_comments',
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pitch_video_comments_made')
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['founder', '-created_at']),
            models.Index(fields=['seller', '-created_at']),
        ]

    def __str__(self):
        target = self.founder.company_name if self.founder_id else self.seller.company_name
        return f"{self.author.username} on {target}'s pitch video"


class ProfileVideoQuerySet(models.QuerySet):
    def visible_elevator_pitches(self):
        """
        The Explore / Elevator Pitches feed source — PUBLISHED elevator
        pitches whose owning founder/seller profile is itself discoverable
        (not private, not archived, not staff-hidden, not review-denied).
        QUARANTINED and REMOVED videos never appear here: a single valid
        report is enough to pull a video out of this queryset (see
        ProfileVideo.quarantine). Anonymous visitors get the exact same
        list — Explore has no role gate.
        """
        founder_ok = (
            models.Q(founder__isnull=False)
            & models.Q(founder__is_private=False)
            & models.Q(founder__archived_at__isnull=True)
            & models.Q(founder__is_hidden_by_staff=False)
            & ~models.Q(founder__review_status='DENIED')
        )
        seller_ok = (
            models.Q(seller__isnull=False)
            & models.Q(seller__is_private=False)
            & models.Q(seller__archived_at__isnull=True)
            & models.Q(seller__is_hidden_by_staff=False)
            & ~models.Q(seller__review_status='DENIED')
        )
        return self.filter(
            kind=ProfileVideo.KIND_ELEVATOR_PITCH,
            status=ProfileVideo.STATUS_PUBLISHED,
        ).filter(founder_ok | seller_ok).select_related(
            'founder__user', 'seller__user',
        )


class ProfileVideo(models.Model):
    """
    A single typed short-form video attached to a founder (Application) or
    seller (SellerApplication) profile — exactly one of founder/seller is
    set (same one-model-two-owners pattern as PitchVideoComment; enforced
    in the managing view, plus the partial-unique constraints below).

    Phase 1 exposes only ELEVATOR_PITCH: the =<30-second clip that powers
    the anonymous Explore feed. The `kind` enum exists now so PRODUCT_DEMO
    / FOUNDER_STORY / CUSTOMER_PROOF can be added later without reworking
    storage or moderation. This is deliberately SEPARATE from
    Application.pitch_video / SellerApplication.pitch_video (the existing
    1-3 min authenticated "Pitch Videos" section), which is left intact.

    Moderation is publish-first: a video is PUBLISHED and publicly
    discoverable the moment it is uploaded. The first valid report
    QUARANTINEs it (pulled from Explore, queued for staff) — a report is a
    temporary takedown, never an automatic guilty verdict. Staff then
    either restore it (-> PUBLISHED) or remove it (-> REMOVED).
    """
    KIND_ELEVATOR_PITCH = 'ELEVATOR_PITCH'
    KIND_CHOICES = [
        (KIND_ELEVATOR_PITCH, 'Elevator Pitch (=<30s)'),
        # Phase 2+: ('PRODUCT_DEMO', ...), ('FOUNDER_STORY', ...), ('CUSTOMER_PROOF', ...)
    ]

    STATUS_PUBLISHED = 'PUBLISHED'
    STATUS_QUARANTINED = 'QUARANTINED'
    STATUS_REMOVED = 'REMOVED'
    STATUS_CHOICES = [
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_QUARANTINED, 'Quarantined - under review'),
        (STATUS_REMOVED, 'Removed by staff'),
    ]

    ELEVATOR_MAX_MB = 30
    ELEVATOR_MAX_SECONDS = 30

    objects = ProfileVideoQuerySet.as_manager()

    founder = models.ForeignKey(
        'matchmaking.Application', on_delete=models.CASCADE, null=True, blank=True,
        related_name='profile_videos',
    )
    seller = models.ForeignKey(
        'matchmaking.SellerApplication', on_delete=models.CASCADE, null=True, blank=True,
        related_name='profile_videos',
    )
    kind = models.CharField(max_length=32, choices=KIND_CHOICES, default=KIND_ELEVATOR_PITCH)
    video = models.FileField(
        upload_to='elevator_pitches/%Y/%m/',
        validators=[
            FileExtensionValidator(allowed_extensions=['mp4', 'mov', 'webm']),
            MaxFileSizeValidator(max_mb=ELEVATOR_MAX_MB),
        ],
        help_text="=<30 seconds. MP4, MOV, or WEBM. Max 30MB.",
    )
    caption = models.CharField(
        max_length=140, blank=True,
        help_text="One line shown under your video in Explore - the one-sentence version of what you're building.",
    )
    duration_seconds = models.FloatField(
        null=True, blank=True, help_text="Reported by the browser at upload time.",
    )

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PUBLISHED)

    interested_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='interested_profile_videos', blank=True,
    )
    view_count = models.PositiveIntegerField(default=0)
    completed_view_count = models.PositiveIntegerField(
        default=0, help_text="Views that reached >=90% of the clip.",
    )

    # Denormalised moderation audit trail; per-report detail is on ProfileVideoReport.
    report_count = models.PositiveIntegerField(default=0)
    first_reported_at = models.DateTimeField(null=True, blank=True)
    quarantined_at = models.DateTimeField(null=True, blank=True)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    last_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='profile_videos_reviewed',
    )
    last_review_decision = models.CharField(max_length=16, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['kind', 'status', '-created_at']),
            models.Index(fields=['status', 'first_reported_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['founder', 'kind'], condition=models.Q(founder__isnull=False),
                name='uniq_founder_video_kind',
            ),
            models.UniqueConstraint(
                fields=['seller', 'kind'], condition=models.Q(seller__isnull=False),
                name='uniq_seller_video_kind',
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} - {self.owner_display} ({self.status})"

    @property
    def owner_profile(self):
        return self.founder or self.seller

    @property
    def role(self):
        return 'founder' if self.founder_id else 'seller'

    @property
    def owner_display(self):
        p = self.owner_profile
        return getattr(p, 'company_name', '') if p else ''

    @property
    def completion_rate(self):
        return (self.completed_view_count / self.view_count) if self.view_count else 0.0

    def quarantine(self, *, first_report_at=None):
        """First valid report pulls the video from Explore into the staff queue."""
        now = timezone.now()
        updates = ['status', 'updated_at']
        self.status = self.STATUS_QUARANTINED
        if self.quarantined_at is None:
            self.quarantined_at = now
            updates.append('quarantined_at')
        if self.first_reported_at is None:
            self.first_reported_at = first_report_at or now
            updates.append('first_reported_at')
        self.save(update_fields=updates)

    def _record_review(self, staff_user, status, decision):
        self.status = status
        self.last_reviewed_at = timezone.now()
        self.last_reviewed_by = staff_user
        self.last_review_decision = decision
        self.save(update_fields=[
            'status', 'last_reviewed_at', 'last_reviewed_by',
            'last_review_decision', 'updated_at',
        ])

    def restore(self, staff_user):
        """Staff decided the report was not upheld - back onto Explore."""
        self._record_review(staff_user, self.STATUS_PUBLISHED, 'RESTORED')
        self.reports.filter(decision=ProfileVideoReport.DECISION_PENDING).update(
            decision=ProfileVideoReport.DECISION_RESTORED,
            reviewed_at=timezone.now(), reviewed_by=staff_user,
        )

    def remove_by_staff(self, staff_user):
        """Staff upheld the report - permanently off Explore."""
        self._record_review(staff_user, self.STATUS_REMOVED, 'REMOVED')
        self.reports.filter(decision=ProfileVideoReport.DECISION_PENDING).update(
            decision=ProfileVideoReport.DECISION_UPHELD,
            reviewed_at=timezone.now(), reviewed_by=staff_user,
        )


class ProfileVideoReport(models.Model):
    """
    One viewer report against a ProfileVideo. Reporting requires a logged-in
    account (a deliberate abuse safeguard, since a single report is enough
    to hide a video). The report immediately quarantines the video but is
    explicitly a temporary takedown pending staff review, not a verdict -
    staff resolve each report as RESTORED or UPHELD.
    """
    REASON_CHOICES = [
        ('SCAM', 'Scam / fraudulent claim'),
        ('IMPERSONATION', 'Impersonation'),
        ('MISLEADING', 'Misleading information'),
        ('INAPPROPRIATE', 'Inappropriate content'),
        ('IP', 'Copyright / IP concern'),
        ('SPAM', 'Spam'),
        ('OTHER', 'Other'),
    ]
    DECISION_PENDING = 'PENDING'
    DECISION_RESTORED = 'RESTORED'
    DECISION_UPHELD = 'UPHELD'
    DECISION_CHOICES = [
        (DECISION_PENDING, 'Pending review'),
        (DECISION_RESTORED, 'Restored - report not upheld'),
        (DECISION_UPHELD, 'Upheld - video removed'),
    ]

    video = models.ForeignKey(ProfileVideo, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='profile_video_reports',
    )
    reason = models.CharField(max_length=16, choices=REASON_CHOICES)
    detail = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    decision = models.CharField(max_length=16, choices=DECISION_CHOICES, default=DECISION_PENDING)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='profile_video_reports_reviewed',
    )

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['video', 'reporter'], condition=models.Q(reporter__isnull=False),
                name='uniq_report_per_user_per_video',
            ),
        ]

    def __str__(self):
        return f"{self.get_reason_display()} report on video #{self.video_id}"

