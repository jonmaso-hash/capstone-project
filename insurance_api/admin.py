# insurance_api/admin.py
from django.contrib import admin
from .models import InsurancePolicy, InsuranceClaim

@admin.register(InsurancePolicy)
class InsurancePolicyAdmin(admin.ModelAdmin):
    list_display = ('policy_number', 'holder', 'policy_type', 'coverage_limit', 'status', 'issued_at')
    list_filter = ('policy_type', 'status', 'issued_at')
    search_fields = ('policy_number', 'holder__username')
    ordering = ('-issued_at',)


@admin.register(InsuranceClaim)
class InsuranceClaimAdmin(admin.ModelAdmin):
    list_display = ('claim_reference', 'policy', 'claimed_amount', 'status', 'submitted_at')
    list_filter = ('status', 'submitted_at')
    search_fields = ('claim_reference', 'policy__policy_number', 'incident_description')
    ordering = ('-submitted_at',)