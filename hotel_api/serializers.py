# hotel_api/serializers.py
from rest_framework import serializers
from .models import HotelProperty, HotelReservation

class HotelPropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelProperty
        fields = ['id', 'name', 'location_city', 'star_rating', 'extracted_amenity_matrix']


class RoomBookingPayloadSerializer(serializers.Serializer):
    room_id = serializers.IntegerField(required=True)
    check_in = serializers.DateField(required=True)
    check_out = serializers.DateField(required=True)
    promo_code = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate(self, data):
        if data['check_in'] >= data['check_out']:
            raise serializers.ValidationError("Check-out target timeline must occur after your check-in date.")
        return data