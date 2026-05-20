from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class InsurancePolicy(models.Model):
    POLICY_TYPES = [
        ('commercial_liability', 'Commercial General Liability'),
        ('key_person', 'Key Person Indemnity'),
        ('cyber_security', 'Cyber Risk & Data Breach'),
        ('property_asset', 'Commercial Property Coverage'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active / In Force'),
        ('underwriting', 'Pending Underwriting Review'),
        ('lapsed', 'Lapsed / Non-Payment'),
    ]

    holder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='insurance_policies')
    policy_number = models.CharField(max_length=32, unique=True)
    policy_type = models.CharField(max_length=30, choices=POLICY_TYPES, default='commercial_liability')
    coverage_limit = models.DecimalField(max_digits=15, decimal_places=2, help_text="Maximum aggregate payout limit.")
    deductible = models.DecimalField(max_digits=12, decimal_places=2)
    premium_annual = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='underwriting')
    issued_at = models.DateField(blank=True, null=True)

    class Meta:
        app_label = 'insurance_api'
        verbose_name = "Insurance Policy"
        verbose_name_plural = "Insurance Policies"

    def __str__(self):
        return f"{self.policy_number} ({self.get_policy_type_display()})"


class InsuranceClaim(models.Model):
    CLAIM_STATUS = [
        ('submitted', 'Claim Lodged / Pending Review'),
        ('investigating', 'Under Adjuster Investigation'),
        ('approved', 'Approved for Settlement payout'),
        ('denied', 'Claim Repudiated / Denied'),
    ]

    policy = models.ForeignKey(InsurancePolicy, on_delete=models.CASCADE, related_name='claims')
    claim_reference = models.CharField(max_length=32, unique=True)
    incident_description = models.TextField(help_text="Detailed summary of the loss or liability event.")
    claimed_amount = models.DecimalField(max_digits=15, decimal_places=2)
    approved_payout_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=CLAIM_STATUS, default='submitted')
    # Zelda AI extracts structured damage parsing parameters here
    ai_risk_assessment_flags = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'insurance_api'
        verbose_name = "Insurance Claim"
        verbose_name_plural = "Insurance Claims"
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Claim {self.claim_reference} - {self.status.upper()}"