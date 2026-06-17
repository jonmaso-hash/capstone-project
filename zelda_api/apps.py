from django.apps import AppConfig


class ZeldaApiConfig(AppConfig):
    # Specifies the default primary key field type for automatically generated auto-incrementing IDs
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'zelda_api'
    verbose_name = 'Zelda AI Engine'  # 🧠 This gives it a clean name on your Django Admin sidebar
    
    def ready(self):
        """
        Called when the app is ready.
        Registers Django signals for automatic pipeline triggering.
        """
        import zelda_api.signals  # noqa: F401