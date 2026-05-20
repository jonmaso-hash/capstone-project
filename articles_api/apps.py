# articles_api/apps.py
from django.apps import AppConfig

class ArticlesApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'articles_api'
    verbose_name = 'Zelda Content & Article Engine'