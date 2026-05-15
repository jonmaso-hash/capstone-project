from django.apps import AppConfig


class MatchmakingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'matchmaking'

    def ready(self):
        # If you ever need to import models here (for signals, etc.), 
        # you MUST do it inside this ready() method, not at the top of the file.
        import matchmaking.signals