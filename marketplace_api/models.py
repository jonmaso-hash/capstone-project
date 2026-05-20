# marketplace_api/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class DigitalProduct(models.Model):
    ASSET_CATEGORIES = [
        ('code_template', 'Code Architecture & Boilerplates'),
        ('dataset', 'Structured Data & Vector Vectors'),
        ('ai_prompt', 'Engineered AI Prompts & Agents'),
        ('saas_plugin', 'SaaS Extension Microservices'),
    ]

    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='marketplace_products')
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=30, choices=ASSET_CATEGORIES, default='code_template')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    download_url = models.URLField(max_length=500)
    is_published = models.BooleanField(default=True)
    # Metadata parsed by Zelda (e.g., framework versions, dependencies)
    compiled_spec_manifest = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'marketplace_api'
        verbose_name = "Digital Product"
        verbose_name_plural = "Digital Products"

    def __str__(self):
        return f"{self.title} (${self.price})"


class LicensePurchase(models.Model):
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='marketplace_purchases')
    product = models.ForeignKey(DigitalProduct, on_delete=models.RESTRICT, related_name='sales_history')
    license_key = models.CharField(max_length=64, unique=True)
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee_deducted = models.DecimalField(max_digits=10, decimal_places=2)
    seller_payout_share = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'marketplace_api'
        verbose_name = "License Purchase"
        verbose_name_plural = "License Purchases"

    def __str__(self):
        return f"License {self.license_key[:12]} - Product ID {self.product_id}"