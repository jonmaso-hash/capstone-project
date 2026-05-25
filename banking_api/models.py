# banking_api/models.py
import uuid
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from zelda_api.protocol import FoundryStandardMixin

class Transaction(FoundryStandardMixin, models.Model):
    # ADD MISSING FIELDS TO RESOLVE ADMIN ERRORS:
    reference_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    account = models.CharField(max_length=100, default="default_account")
    amount = models.DecimalField(max_length=20, max_digits=12, decimal_places=2, default=0.00)
    transaction_type = models.CharField(
        max_length=20, 
        choices=[('deposit', 'Deposit'), ('withdrawal', 'Withdrawal'), ('transfer', 'Transfer')],
        default='transfer'
    )
    status = models.CharField(max_length=20, default='pending')
    idempotency_key = models.CharField(max_length=255, unique=True, blank=True, null=True)
    execution_timestamp = models.DateTimeField(default=timezone.now)

    # Pre-existing fields from your file snippet:
    compliance_status = models.CharField(max_length=20, default='pending')
    aml_screening_results = models.JSONField(default=dict, blank=True)

    def save(self, *args, **kwargs):
        """1. PROACTIVE ENFORCEMENT (Blocking Layer)"""
        with transaction.atomic():
            # Block or Flag immediately based on rules
            if float(self.amount) >= 10000.00:
                self.compliance_status = 'flagged'
            else:
                self.compliance_status = 'cleared'
            super().save(*args, **kwargs)

# 2. REACTIVE CHECKING (Audit Layer)
@receiver(post_save, sender=Transaction)
def reactive_fraud_analysis(sender, instance, created, **kwargs):
    if created:
        pass