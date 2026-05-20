from django.apps import AppConfig

class MarketingApiConfig(AppConfig):
    # Sets the standard primary key field type for your models implicitly
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'marketing_api'
    
    # Human-readable name that will appear in the Django Admin sidebar
    verbose_name = 'Zelda Marketing Engine'