# marketplace_api/admin.py
from django.contrib import admin
from .models import DigitalProduct, LicensePurchase

@admin.register(DigitalProduct)
class DigitalProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'category', 'price', 'is_published', 'created_at')
    list_filter = ('category', 'is_published')
    search_fields = ('title', 'seller__username')
    ordering = ('-created_at',)


@admin.register(LicensePurchase)
class LicensePurchaseAdmin(admin.ModelAdmin):
    list_display = ('license_key', 'buyer', 'product', 'gross_amount', 'purchased_at')
    list_filter = ('purchased_at',)
    search_fields = ('license_key', 'buyer__username', 'product__title')
    ordering = ('-purchased_at',)