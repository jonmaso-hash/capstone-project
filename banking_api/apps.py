# banking_api/apps.py
from django.apps import AppConfig

class BankingApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'banking_api'
    verbose_name = 'Zelda Banking Engine (Pinnacle)' # Updated for clarity