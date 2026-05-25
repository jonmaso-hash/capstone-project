# zelda_api/registry.py
from django.apps import apps
from .protocol import FoundryStandardMixin

class PinnacleRegistry:
    """
    Dynamically discovers all models across the 13+ APIs that 
    inherit from FoundryStandardMixin and speak the Zelda Protocol.
    """
    _registry_cache = None

    @classmethod
    def get_adapters(cls):
        if cls._registry_cache is None:
            cls._registry_cache = {}
            # Scan all installed models in the Django project
            for model in apps.get_models():
                if issubclass(model, FoundryStandardMixin) and hasattr(model, 'source_name'):
                    cls._registry_cache[model.source_name] = model
        return cls._registry_cache

    @classmethod
    def get_model_for_source(cls, source_name):
        adapters = cls.get_adapters()
        return adapters.get(source_name)