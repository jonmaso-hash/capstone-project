# zelda_api/truth_delta_models.py
"""
Truth Delta Verification Engine Models
Compares claimed data vs observed data to detect discrepancies.
This is the highest-value diligence feature.
"""
from django.db import models
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

    def category_states(self):
        """
        {category: 'verified' | 'no_data'} derived from `details` — a
        claim counts as 'verified' only when its per-claim `observed`
        field actually names real external evidence, not merely that a
        Claude assessment exists. Deliberately two-state, not three:
        "contradicted" isn't something the stored assessment text
        reliably distinguishes from "verified but concerning" without
        over-reading free text as a structured signal.
        """
        per_claim = self.details.get('per_claim', [])
        if per_claim:
            return {
                row['category']: (
                    'verified' if row.get('observed') and 'no external data' not in row['observed'].lower()
                    else 'no_data'
                )
                for row in per_claim if row.get('category')
            }
        # No qualitative per_claim breakdown at all (e.g. the "no external
        # data found for this company" branch) — every claim is unchecked.
        return {c['category']: 'no_data' for c in self.details.get('claims', []) if c.get('category')}

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