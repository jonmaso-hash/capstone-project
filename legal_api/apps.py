# legal_api/apps.py
from django.apps import AppConfig

class LegalApiConfig(AppConfig):
    # Sets the standard primary key field type implicitly for all legal models
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'legal_api'
    
    # Human-readable title displayed inside the Django Admin sidebar
    verbose_name = 'Zelda Legal Engine'