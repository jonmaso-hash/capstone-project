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
    Logs instantaneous generation telemetry data parsed and recorded 
    by Zelda's edge monitoring layers.
    """
    asset = models.ForeignKey(PowerGridAsset, on_delete=models.CASCADE, related_name='telemetry_logs')
    current_output_mw = models.FloatField(help_text="Instantaneous output in Megawatts.")
    grid_frequency_hz = models.FloatField(default=60.00, help_text="Monitored local grid line variance frequency.")
    carbon_offset_intensity = models.FloatField(help_text="Estimated metric tons of CO2 avoided per MWh generated.")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Generation Log"
        verbose_name_plural = "Generation Logs"
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.asset.asset_name} Telemetry: {self.current_output_mw} MW at {self.recorded_at.strftime('%H:%M:%S')}"