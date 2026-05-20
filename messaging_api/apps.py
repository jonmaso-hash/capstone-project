# messaging_api/apps.py
from django.apps import AppConfig

class MessagingApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'messaging_api'
    verbose_name = 'Zelda Communication & Messaging Engine'