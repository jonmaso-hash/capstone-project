# hotel_api/admin.py
from django.contrib import admin
from .models import HotelProperty, RoomInventory, HotelReservation

@admin.register(HotelProperty)
class HotelPropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_city', 'star_rating', 'created_at')
    search_fields = ('name', 'location_city')
    ordering = ('name',)


@admin.register(RoomInventory)
class RoomInventoryAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'hotel', 'room_type', 'base_price_per_night', 'is_currently_vacant')
    list_filter = ('room_type', 'is_currently_vacant', 'hotel')
    search_fields = ('room_number', 'hotel__name')


@admin.register(HotelReservation)
class HotelReservationAdmin(admin.ModelAdmin):
    list_display = ('confirmation_hash', 'guest', 'room_node', 'check_in_date', 'booking_status')
    list_filter = ('booking_status', 'check_in_date')
    search_fields = ('confirmation_hash', 'guest__username', 'room_node__room_number')