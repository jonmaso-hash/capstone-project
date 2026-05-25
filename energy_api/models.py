# energy_api/models.py
from django.db import models

class PowerGridAsset(models.Model):
    ASSET_TYPES = [
        ('solar_farm', 'Solar Generation Facility'),
        ('wind_turbine', 'Wind Array Facility'),
        ('natural_gas', 'Natural Gas Peaker Plant'),
        ('battery_storage', 'BESS Battery Storage Bank'),
    ]
    STATUS_CHOICES = [
        ('operational', 'Operational / Nominal Grid Tie'),
        ('maintenance', 'Offline for Maintenance'),
        ('curtailed', 'Curtailed by Grid Operator'),
    ]

    asset_name = models.CharField(max_length=255)
    asset_type = models.CharField(max_length=30, choices=ASSET_TYPES, default='solar_farm')
    grid_region = models.CharField(max_length=50, help_text="e.g., CAISO, ERCOT, PJM")
    nameplate_capacity_mw = models.FloatField(help_text="Maximum design output capacity in Megawatts.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='operational')
    last_reported_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Power Grid Asset"
        verbose_name_plural = "Power Grid Assets"

    def __str__(self):
        return f"{self.asset_name} [{self.grid_region} - {self.get_asset_type_display()}]"


class GenerationLog(models.Model):
    """
    Logs instantaneous generation telemetry data.
    """
    # NO IMPORT NEEDED: PowerGridAsset is defined above in this same file.
    asset = models.ForeignKey(
        PowerGridAsset, 
        on_delete=models.CASCADE, 
        related_name='telemetry_logs'
    )
    current_output_mw = models.FloatField(help_text="Instantaneous output in Megawatts.")
    grid_frequency_hz = models.FloatField(default=60.00)
    carbon_offset_intensity = models.FloatField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    idempotency_key = models.UUIDField(
        unique=True, 
        null=True, 
        blank=True
    )

    class Meta:
        verbose_name = "Generation Log"
        verbose_name_plural = "Generation Logs"
        indexes = [
            models.Index(fields=['asset', 'recorded_at']),
            models.Index(fields=['idempotency_key']),
        ]

    def __str__(self):
        return f"Log {self.id} | {self.asset.asset_name} | {self.recorded_at}"