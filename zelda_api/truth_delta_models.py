# zelda_api/truth_delta_models.py
"""
Truth Delta Verification Engine Models
Compares claimed data vs observed data to detect discrepancies.
This is the highest-value diligence feature.
"""
from django.db import models
from django.utils import timezone
from django.conf import settings
from .vector_models import DocumentSource


class ExternalDataSource(models.Model):
    """
    Represents an external data source (Crunchbase, LinkedIn, SEC, etc)
    Used for cross-referencing claims against verified external data.
    """
    
    SOURCE_TYPES = [
        ('crunchbase', 'Crunchbase'),
        ('linkedin', 'LinkedIn'),
        ('sec', 'SEC EDGAR'),
        ('web', 'Web Scraping'),
        ('news', 'News Articles'),
        ('domain', 'Domain WHOIS'),
        ('jobs', 'Job Boards'),
        ('news_api', 'News API'),
        ('corporate', 'Corporate Filings'),
        ('other', 'Other Source'),
    ]
    
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    source_name = models.CharField(max_length=255)
    url = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True, help_text="API key if needed")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    
    class Meta:
        app_label = 'zelda_api'
        verbose_name = "External Data Source"
        verbose_name_plural = "External Data Sources"
    
    def __str__(self):
        return f"{self.source_name} ({self.source_type})"


class ClaimedDatapoint(models.Model):
    """
    A single claim extracted from a founder's pitch deck.
    E.g., "500 customers", "$1M ARR", "200% YoY growth"
    """
    
    CATEGORY_CHOICES = [
        ('revenue', 'Revenue'),
        ('arr', 'Annual Recurring Revenue (ARR)'),
        ('customers', 'Customer Count'),
        ('growth_rate', 'Growth Rate (%)'),
        ('employees', 'Employee Count'),
        ('funding_raised', 'Funding Raised'),
        ('market_share', 'Market Share'),
        ('market_size', 'Total Addressable Market Size'),
        ('user_count', 'User Count'),
        ('engagement', 'Engagement Metric'),
        ('churn', 'Churn Rate'),
        ('team_size', 'Team Size'),
        ('office_locations', 'Office Locations'),
        ('countries', 'Countries Served'),
        ('other', 'Other Metric'),
    ]
    
    document = models.ForeignKey(DocumentSource, on_delete=models.CASCADE, related_name='claimed_datapoints')

    # The claim itself
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    claimed_value = models.CharField(max_length=255, help_text="E.g., '500', '$1M', '200%'")
    claimed_value_numeric = models.FloatField(null=True, blank=True, help_text="Numeric value for comparison")
    unit = models.CharField(max_length=50, blank=True, help_text="E.g., 'customers', '$', '%'")
    time_period = models.CharField(max_length=100, blank=True, help_text="E.g., 'YoY', 'Q3 2024'")
    source_chunk = models.CharField(max_length=255, blank=True, help_text="Which slide/section in deck")

    # Provenance — full traceability back to the source chunk this claim came from
    page_number = models.IntegerField(null=True, blank=True, help_text="Page this claim's source chunk came from")
    text_excerpt = models.TextField(blank=True, help_text="Full source chunk text this claim was extracted from")
    chunk_hash = models.CharField(max_length=128, blank=True, help_text="Hash of the source chunk, for change detection/dedup")

    # Extraction metadata
    confidence_in_extraction = models.FloatField(default=0.7, help_text="How confident are we we extracted this correctly")
    extraction_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'zelda_api'
        ordering = ['category', '-created_at']
    
    def __str__(self):
        return f"{self.category}: {self.claimed_value}"


class ObservedDatapoint(models.Model):
    """
    Verified data from external sources.
    This is the "ground truth" we compare against claims.
    """
    
    document = models.ForeignKey(DocumentSource, on_delete=models.CASCADE, related_name='observed_datapoints')
    
    # The observed value
    category = models.CharField(max_length=50, choices=ClaimedDatapoint.CATEGORY_CHOICES)
    observed_value = models.CharField(max_length=255)
    observed_value_numeric = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    time_period = models.CharField(max_length=100, blank=True)
    
    # Source information
    source = models.ForeignKey(ExternalDataSource, on_delete=models.SET_NULL, null=True)
    source_url = models.URLField(blank=True)
    source_date = models.DateField(null=True, blank=True, help_text="When this data was published")
    
    # Credibility
    source_credibility = models.FloatField(default=0.8, help_text="0.0-1.0 how much we trust this source")
    extraction_method = models.CharField(
        max_length=50,
        choices=[
            ('api', 'API Call'),
            ('web_scrape', 'Web Scraping'),
            ('manual', 'Manual Entry'),
            ('filing', 'Corporate Filing'),
        ],
        default='api'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'zelda_api'
        ordering = ['-source_date', '-created_at']
    
    def __str__(self):
        return f"{self.category}: {self.observed_value}"


class TruthDeltaReport(models.Model):
    document = models.ForeignKey('DocumentSource', on_delete=models.CASCADE)
    # Null (not 0.0) specifically means "no external data was found to
    # compare against" — distinct from an actual low score, since 0.0
    # would otherwise misleadingly read as "claims are false" rather than
    # "we couldn't check." See TruthDeltaEngine.verify_document.
    overall_truth_score = models.FloatField(null=True, blank=True)
    credibility_risk = models.CharField(max_length=20, default='unknown')
    summary = models.TextField(blank=True)
    # Structured per-claim comparison: {"claims": [...], "per_claim": [...]}
    # — lets the dashboard eventually render a claimed-vs-observed table
    # without a new model; empty dict when nothing was computed.
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'zelda_api'
        ordering = ['-created_at']

    def grounded_categories(self):
        """
        The categories this report actually holds external evidence for:
        `details['observed']`, written from the ObservedDatapoint rows the
        pipeline fetched. Nothing a model wrote can add to this set.

        A report stored before `observed` was recorded has no key here and
        so grounds nothing — the conservative answer, since a claim cannot
        be shown to be corroborated by evidence that was never saved.
        """
        return {
            row.get('category')
            for row in (self.details or {}).get('observed') or []
            if row.get('category')
        }

    def category_states(self):
        """
        {category: 'verified' | 'no_data'} — 'verified' means THIS pipeline
        fetched and stored an external datapoint in that category.

        It deliberately does not read the per-claim `observed` text. That
        field is written by a language model, so deriving verification from
        it let the model's prose stand in for evidence: with no external
        source configured or reachable, a row reading "Crunchbase reports
        $4.2M ARR" counted as corroboration of the very deck it came from.
        The model may describe evidence; only the fetch creates it.

        The consequence runs both ways, on purpose. A claim with a stored
        datapoint counts as verified even where the model's row says it
        found nothing, and news headlines never count — they are never
        stored as datapoints, and Truth Delta's own prompt says a headline
        corroborates a narrative but never confirms a figure.

        Deliberately two-state, not three: "contradicted" isn't something
        the stored assessment text reliably distinguishes from "verified
        but concerning" without over-reading free text as a structured
        signal. How far a verified claim diverges from its evidence is the
        score's job, not this function's.
        """
        grounded = self.grounded_categories()
        per_claim = self.details.get('per_claim', [])
        if per_claim:
            return {
                row['category']: ('verified' if row['category'] in grounded else 'no_data')
                for row in per_claim if row.get('category')
            }
        # No qualitative per_claim breakdown at all (e.g. the "no external
        # data found for this company" branch).
        return {
            c['category']: ('verified' if c['category'] in grounded else 'no_data')
            for c in self.details.get('claims', []) if c.get('category')
        }

    def per_claim_rows(self):
        """
        The per-claim table with the server's grounding answer attached, so
        a page renders what the evidence says instead of re-deciding from
        the prose it was handed — which is how the claim list and the stat
        cards came to compute "verified" two different ways.
        """
        grounded = self.grounded_categories()
        return [
            {**row, 'grounded': row.get('category') in grounded}
            for row in self.details.get('per_claim', []) or []
        ]

    def verifiability_stats(self):
        """
        {'total', 'verified', 'pct'} — how many of this report's claims
        actually got cross-referenced against real external data, computed
        from `details` (the single source of truth) rather than stored
        separately, so it can never drift out of sync with the per-claim
        table itself.
        """
        states = self.category_states()
        total = len(states)
        if not total:
            return {'total': 0, 'verified': 0, 'pct': None}
        verified = sum(1 for state in states.values() if state == 'verified')
        return {'total': total, 'verified': verified, 'pct': round(verified / total * 100, 1)}


class ClarificationRequest(models.Model):
    """
    An investor/buyer flags one specific unverified claim on a Truth
    Delta report and asks the founder/seller to clarify or supply
    supporting documentation. Scoped to a single report, not the document
    generally — which claims are even unverified can change between
    re-verifications, so a request is tied to the exact report it was
    raised against.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Response'),
        ('RESPONDED', 'Responded'),
        ('DISMISSED', 'Dismissed'),
    ]

    report = models.ForeignKey(TruthDeltaReport, on_delete=models.CASCADE, related_name='clarification_requests')
    category = models.CharField(max_length=50, choices=ClaimedDatapoint.CATEGORY_CHOICES)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='clarification_requests_sent')
    message = models.TextField(blank=True, help_text="What the investor/buyer wants clarified")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    response_text = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'zelda_api'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.requested_by.username} asked about {self.category} on document {self.report.document_id} [{self.status}]"


class FindingDispute(models.Model):
    """
    The subject of a report contesting a finding about itself.

    Distinct from ClarificationRequest, which runs the other way: an investor
    asking the company to explain a claim. This is the company's right of reply
    to what Interlink publishes about it, and it has to be auditable afterwards
    — a report that says a claim is unsupported, read by investors, is exactly
    the kind of statement someone later argues about.

    Append-only by design. `original_evidence_state` and `original_observed_text`
    are copied in at creation, so re-running verification changes the report but
    never changes what this record says the report said at the time. Resolution
    adds fields; it never edits the ones above it.

    An open dispute does **not** move the evidence state. "Disputed by the
    company — under review" means the company contests it, not that the company
    is right; only a staff resolution decides what the evidence supports.
    """

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Under review'
        UPHELD = 'UPHELD', 'Upheld — the finding stands on the evidence reviewed'
        CORRECTED = 'CORRECTED', 'Corrected — the evidence warranted a change'
        CLOSED_INSUFFICIENT = 'CLOSED_INSUFFICIENT', 'Closed — insufficient basis to change it'
        WITHDRAWN = 'WITHDRAWN', 'Withdrawn'

    report = models.ForeignKey(TruthDeltaReport, on_delete=models.CASCADE, related_name='disputes')
    category = models.CharField(max_length=50, choices=ClaimedDatapoint.CATEGORY_CHOICES)

    # What the report said when this was raised. Never updated.
    original_evidence_state = models.CharField(max_length=20)
    original_observed_text = models.TextField(blank=True)

    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='finding_disputes_raised',
    )
    reason = models.TextField(help_text="What the company says is wrong with the finding")
    evidence_text = models.TextField(blank=True, help_text="Supporting detail the company supplied")
    evidence_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    resolution_note = models.TextField(blank=True, help_text="Why staff decided what they decided")
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='finding_disputes_resolved',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'zelda_api'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['report', 'status'])]

    def __str__(self):
        return f"{self.get_status_display()} — {self.category} on report {self.report_id}"

    @property
    def is_open(self):
        return self.status == self.Status.OPEN

    def resolve(self, status, note, by):
        """
        Record a decision. The note is mandatory: a resolution without a stated
        reason is indistinguishable from the finding quietly changing, which is
        the thing this record exists to prevent.
        """
        if status == self.Status.OPEN:
            raise ValueError("Resolving a dispute needs a decision, not OPEN.")
        if not (note or '').strip():
            raise ValueError("A resolution needs a note saying why.")
        self.status = status
        self.resolution_note = note.strip()
        self.resolved_by = by
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolution_note', 'resolved_by', 'resolved_at'])


def open_dispute_categories(report):
    """Categories the subject is currently contesting, for the report page."""
    if not report:
        return set()
    return set(
        report.disputes.filter(status=FindingDispute.Status.OPEN).values_list('category', flat=True)
    )


def can_request_clarification(request_user, document):
    """
    Same viewer gate as the Truth Delta page itself (any investor/buyer,
    or staff) — deliberately not connection-gated like IC Memo, since
    asking about something already visible on a page they can already
    view isn't a bigger disclosure. The owner never "requests
    clarification" from themselves.
    """
    if not request_user or not request_user.is_authenticated:
        return False
    if request_user == document.uploaded_by:
        return False
    if request_user.is_staff:
        return True
    is_investor = (
        getattr(request_user, 'match_investor_profile', None) is not None or
        getattr(request_user, 'accounts_investor_profile', None) is not None
    )
    is_buyer = getattr(request_user, 'match_buyer_profile', None) is not None
    return is_investor or is_buyer


def _owner_is_premium(user):
    application = getattr(user, 'match_founder_profile', None)
    if application:
        return application.is_premium
    seller_application = getattr(user, 'match_seller_profile', None)
    if seller_application:
        return seller_application.is_premium
    return False


def truth_delta_unlocked(request_user, document):
    """
    Separate from can_request_clarification's access gate: whether the
    actual verification content (score, claims, evidence, trend) is
    unlocked, vs. just a locked preview. Same founder/seller-controlled-
    asset model as the IC Memo: gated on the document OWNER's own
    Premium, not the viewer's, so it's free for any investor/buyer who
    can already reach this page once the owner unlocks it. Staff bypass
    for support purposes.
    """
    if request_user.is_staff:
        return True
    return _owner_is_premium(document.uploaded_by)


def diff_verification_reports(newer, older):
    """
    Compares two TruthDeltaReports for the same founder/seller —
    consecutive in time, `newer` more recent than `older` — category by
    category, and returns what changed:
    {'newly_verified': [...], 'lost_verification': [...]}

    'newly_verified' includes categories absent or unverified in `older`
    that are verified in `newer`. 'lost_verification' is scoped to
    categories present in BOTH reports (i.e. genuinely re-checked) that
    were verified in `older` but aren't in `newer` — a category simply
    not claimed this round isn't "lost," it's just not part of this
    round's claims.
    """
    newer_states = newer.category_states()
    older_states = older.category_states()
    common_categories = set(newer_states) & set(older_states)

    newly_verified = sorted(
        cat for cat, state in newer_states.items()
        if state == 'verified' and older_states.get(cat) != 'verified'
    )
    lost_verification = sorted(
        cat for cat in common_categories
        if older_states[cat] == 'verified' and newer_states[cat] != 'verified'
    )
    return {'newly_verified': newly_verified, 'lost_verification': lost_verification}