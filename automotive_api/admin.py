# automotive_api/admin.py
from django.contrib import admin
from .models import DealershipShowroom, VehicleAsset, TestDriveBooking

@admin.register(DealershipShowroom)
class DealershipShowroomAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_city', 'franchise_affiliations', 'created_at')
    search_fields = ('name', 'location_city')


@admin.register(VehicleAsset)
class VehicleAssetAdmin(admin.ModelAdmin):
    list_display = ('vin', 'make', 'model', 'year', 'fuel_type', 'base_msrp', 'status')
    list_filter = ('fuel_type', 'status', 'make', 'year')
    search_fields = ('vin', 'make', 'model')
    ordering = ('-year',)


@admin.register(TestDriveBooking)
class TestDriveBookingAdmin(admin.ModelAdmin):
    # Added reservation_expires_at to the list_display for monitoring inventory lifecycle
    list_display = (
        'confirmation_token', 
        'customer', 
        'vehicle', 
        'scheduled_timestamp', 
        'status', 
        'reservation_expires_at'
    )
    
    # Enabled filtering by expiration date
    list_filter = ('status', 'scheduled_timestamp', 'reservation_expires_at')
    
    # Added idempotency_key to search_fields for debugging specific requests
    search_fields = ('confirmation_token', 'customer__username', 'vehicle__vin', 'idempotency_key')
    
    # Idempotency key should never be edited manually once the booking is generated
    readonly_fields = ('idempotency_key', 'created_at')