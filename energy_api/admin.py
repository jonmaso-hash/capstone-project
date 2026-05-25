# energy_api/admin.py
from django.contrib import admin
from .models import PowerGridAsset, GenerationLog

@admin.register(PowerGridAsset)
class PowerGridAssetAdmin(admin.ModelAdmin):
    list_display = ('asset_name', 'asset_type', 'grid_region', 'nameplate_capacity_mw', 'status', 'last_reported_at')
    list_filter = ('asset_type', 'grid_region', 'status')
    search_fields = ('asset_name', 'grid_region')
    ordering = ('asset_name',)


@admin.register(GenerationLog)
class GenerationLogAdmin(admin.ModelAdmin):
    # Added idempotency_key to list_display for audit verification
    list_display = (
        'asset', 
        'current_output_mw', 
        'grid_frequency_hz', 
        'carbon_offset_intensity', 
        'recorded_at', 
        'idempotency_key'
    )
    list_filter = ('recorded_at', 'asset__asset_type')
    
    # Added idempotency_key to search_fields for rapid debugging of duplicate ingestion alerts
    search_fields = ('asset__asset_name', 'idempotency_key')
    
    # Protect the key from manual modification
    readonly_fields = ('idempotency_key', 'recorded_at')
    ordering = ('-recorded_at',)