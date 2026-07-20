# zelda_api/models.py
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from datetime import datetime
from .protocol import FoundryStandardMixin 
from .truth_delta_models import ClaimedDatapoint, TruthDeltaReport


# ==========================================
# CONTENT & KNOWLEDGE ENGINE MODELS
# ==========================================
class ArticleCategory(FoundryStandardMixin, models.Model):
    source_name = "articles_category"
    
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        app_label = 'zelda_api'
        verbose_name = "Article Category"
        verbose_name_plural = "Article Categories"

    def get_serialized_data(self):
        return {"name": self.name, "slug": self.slug}

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ArticlePost(FoundryStandardMixin, models.Model):
    source_name = "articles"
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('review', 'Under AI Review'),
        ('published', 'Published'),
    ]
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='zelda_articles')
    category = models.ForeignKey(ArticleCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='zelda_articles')
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    content_body = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    zelda_seo_analytics = models.JSONField(default=dict, blank=True)
    
    # ADDED TIMESTAMPS TO FIX THE (models.E015) ORDERING ERROR
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'zelda_api'
        ordering = ['-created_at']

    def get_serialized_data(self):
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author.username,
            "category": self.category.name if self.category else None,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "seo_analytics": self.zelda_seo_analytics
        }

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class AnalysisCreditCharge(models.Model):
    """
    Explicit override of who a generation's AI-credit cost is charged to —
    needed for the one case where the actor differs from the resource
    owner: an investor confirming analyze_founder_profile's generation
    creates a DocumentSource owned by the founder (uploaded_by has to stay
    the founder — everything else about ownership/visibility depends on
    it), but the cost belongs to the investor who chose to spend it, not
    the founder whose profile happened to be analyzed.

    zelda_api/quotas.py::credits_used() adds this document's cost to the
    charged user's usage and excludes the document from the owner's own
    count — without this, the founder's own monthly allowance would get
    silently spent by someone else's click, which is exactly the trust
    problem the confirm-before-spend flow exists to prevent.
    """
    document = models.OneToOneField('zelda_api.DocumentSource', on_delete=models.CASCADE, related_name='credit_charge')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='analysis_credit_charges')
    job_type = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'zelda_api'

    def __str__(self):
        return f"{self.user.username} charged {self.job_type} for document {self.document_id}"


class ValuationPurchase(models.Model):
    """
    A paid, one-time unlock of ONE specific preview-tier business
    valuation report into 'full' — the free-preview paywall's purchase
    path for roles that don't get valuations bundled into a subscription
    (Founder/Seller at a flat $9.99/report) or that have exceeded their
    monthly included allowance (Investor/Buyer overage at $5/report; Firm
    overage at $1.99/report — cheaper per-report since a firm seat's
    monthly allowance is already 8x an individual's, and the $5,000/mo
    base already prices in a bulk relationship). See zelda_api/quotas.py::
    valuation_unlock_price() for the full role-based pricing rules this
    backs.

    Unlike the old pay-before-upload flow, redeemed_document and
    redeemed_at are set immediately by quotas.py::unlock_valuation_document
    when the webhook fires — there's no "next generation" to wait for,
    since the document being unlocked already exists and was named in the
    Stripe Checkout metadata at purchase time.
    """
    PURCHASE_TYPES = [
        ('report', 'Founder/Seller $9.99 report'),
        ('overage', 'Investor/Buyer $5 overage report'),
        ('firm_overage', 'Firm $1.99 overage report'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='valuation_purchases')
    purchase_type = models.CharField(max_length=20, choices=PURCHASE_TYPES)
    stripe_checkout_session_id = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(auto_now_add=True)
    redeemed_at = models.DateTimeField(null=True, blank=True)
    redeemed_document = models.ForeignKey(
        'zelda_api.DocumentSource', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='valuation_purchase_redemption',
    )

    class Meta:
        app_label = 'zelda_api'
        indexes = [
            models.Index(fields=['user', 'redeemed_at']),
        ]

    def __str__(self):
        state = 'redeemed' if self.redeemed_at else 'unredeemed'
        return f"{self.user.username} — {self.get_purchase_type_display()} ({state})"