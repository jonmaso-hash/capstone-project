# hotel_api/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class HotelProperty(models.Model):
    name = models.CharField(max_length=255)
    location_city = models.CharField(max_length=100)
    star_rating = models.FloatField(default=0.0)
    # Stores parsed AI features like "near transit", "infinity pool", "ocean view"
    extracted_amenity_matrix = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'hotel_api'
        verbose_name = "Hotel Property"
        verbose_name_plural = "Hotel Properties"

    def __str__(self):
        return f"{self.name} ({self.location_city})"


class RoomInventory(models.Model):
    ROOM_TYPES = [
        ('standard', 'Standard King/Queen'),
        ('deluxe', 'Deluxe Suite'),
        ('penthouse', 'Executive Penthouse'),
    ]
    
    hotel = models.ForeignKey(HotelProperty, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=10)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='standard')
    base_price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    is_currently_vacant = models.BooleanField(default=True)

    class Meta:
        app_label = 'hotel_api'
        verbose_name = "Room Inventory Node"
        verbose_name_plural = "Room Inventory Nodes"

    def __str__(self):
        return f"{self.hotel.name} - Room {self.room_number} ({self.room_type})"


class HotelReservation(models.Model):
    STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('checked_in', 'Checked In'),
        ('cancelled', 'Cancelled'),
    ]

    guest = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hotel_bookings')
    room_node = models.ForeignKey(RoomInventory, on_delete=models.CASCADE, related_name='booking_history')
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    total_stay_cost = models.DecimalField(max_digits=12, decimal_places=2)
    booking_status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='confirmed')
    confirmation_hash = models.CharField(max_length=64, unique=True)

    class Meta:
        app_label = 'hotel_api'
        verbose_name = "Guest Reservation"
        verbose_name_plural = "Guest Reservations"

    def __str__(self):
        return f"Booking {self.confirmation_hash[:8]} - Guest: {self.guest.username}"