# zelda_api/admin.py
"""
Django Admin Configuration for Zelda API
"""
from django.contrib import admin

# Import intelligent models admin (already registered via decorator)
from .admin_intelligence import (  # noqa: F401
    DocumentSourceAdmin,
    DocumentChunkAdmin,
    IntelligenceInsightAdmin,
    IntelligenceMemoAdmin,
)
from .truth_delta_models import (
    ExternalDataSource, ClaimedDatapoint, ObservedDatapoint, TruthDeltaReport,
)
from .entity_verification_models import EntityVerificationReport


@admin.register(ExternalDataSource)
class ExternalDataSourceAdmin(admin.ModelAdmin):
    list_display = ['source_name', 'source_type', 'is_active']
    list_filter = ['source_type', 'is_active']


@admin.register(ClaimedDatapoint)
class ClaimedDatapointAdmin(admin.ModelAdmin):
    list_display = ['document', 'category', 'claimed_value', 'claimed_value_numeric', 'confidence_in_extraction', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['document__source_entity', 'claimed_value']
    readonly_fields = ['created_at']


@admin.register(ObservedDatapoint)
class ObservedDatapointAdmin(admin.ModelAdmin):
    list_display = ['document', 'category', 'observed_value', 'source', 'source_credibility', 'time_period', 'created_at']
    list_filter = ['category', 'source', 'created_at']
    search_fields = ['document__source_entity', 'observed_value']
    readonly_fields = ['created_at']


@admin.register(TruthDeltaReport)
class TruthDeltaReportAdmin(admin.ModelAdmin):
    list_display = ['document', 'overall_truth_score', 'credibility_risk', 'created_at']
    list_filter = ['credibility_risk', 'created_at']
    search_fields = ['document__source_entity']
    readonly_fields = ['created_at']


@admin.register(EntityVerificationReport)
class EntityVerificationReportAdmin(admin.ModelAdmin):
    list_display = ['document', 'domain', 'domain_registered_date', 'claimed_founding_year', 'created_at']
    list_filter = ['created_at']
    search_fields = ['document__source_entity', 'domain']
    readonly_fields = ['created_at']

