# automotive_api/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class DealershipShowroom(models.Model):
    name = models.CharField(max_length=255)
    location_city = models.CharField(max_length=150)
    franchise_affiliations = models.JSONField(default=list, help_text="Array of brands sold, e.g., Tesla, BMW, Ford.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'automotive_api'
        verbose_name = "Dealership Showroom"
        verbose_name_plural = "Dealership Showrooms"

    def __str__(self):
        return f"{self.name} — {self.location_city}"


class VehicleAsset(models.Model):
    FUEL_TYPES = [
        ('ice', 'Internal Combustion Engine'),
        ('bev', 'Battery Electric Vehicle'),
        ('phev', 'Plug-in Hybrid Electric Vehicle'),
    ]
    AVAILABILITY_STATUS = [
        ('available', 'In Showroom Lot'),
        ('reserved', 'Deposit Placed'),
        ('sold', 'Delivered to Customer'),
    ]

    showroom = models.ForeignKey(DealershipShowroom, on_delete=models.CASCADE, related_name='vehicles')
    vin = models.CharField(max_length=17, unique=True, verbose_name="VIN Number")
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.IntegerField()
    fuel_type = models.CharField(max_length=10, choices=FUEL_TYPES, default='ice')
    base_msrp = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="MSRP Price")
    status = models.CharField(max_length=15, choices=AVAILABILITY_STATUS, default='available')
    
    # Zelda AI extracts vehicle packages (e.g., Autopilot, Premium Leather, Sport Trim)
    extracted_spec_matrix = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'automotive_api'
        verbose_name = "Vehicle Asset"
        verbose_name_plural = "Vehicle Assets"

    def __str__(self):
        return f"{self.year} {self.make} {self.model} ({self.vin[:8]})"


class TestDriveBooking(models.Model):
    BOOKING_STATUS = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('no_show', 'No Show / Cancelled'),
    ]

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='automotive_bookings')
    vehicle = models.ForeignKey(VehicleAsset, on_delete=models.CASCADE, related_name='test_drives')
    scheduled_timestamp = models.DateTimeField()
    status = models.CharField(max_length=15, choices=BOOKING_STATUS, default='scheduled')
    confirmation_token = models.CharField(max_length=32, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'automotive_api'
        verbose_name = "Test Drive Booking"
        verbose_name_plural = "Test Drive Bookings"
        ordering = ['-scheduled_timestamp']

    def __str__(self):
        return f"Drive {self.confirmation_token[:8]} — {self.customer.username}"