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
    list_display = ('asset', 'current_output_mw', 'grid_frequency_hz', 'carbon_offset_intensity', 'recorded_at')
    list_filter = ('recorded_at', 'asset__asset_type')
    search_fields = ('asset__asset_name',)
    ordering = ('-recorded_at',)