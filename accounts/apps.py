from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from . import analytics_signals  # noqa: F401
        from . import last_signin  # noqa: F401  (allauth login receiver)

