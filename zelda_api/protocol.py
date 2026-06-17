# zelda_api/protocol.py
"""
Foundry Standard Protocol Mixin
Ensures all models follow the Interlink Foundry envelope standard for AI responses.
"""
from datetime import datetime
from django.db import models


class FoundryStandardMixin:
    """
    Mixin that adds Foundry Protocol compliance to any model.
    Standardizes data serialization into the Foundry Envelope format.
    """
    source_name = "unknown"  # Override in child classes
    
    def to_foundry_envelope(self, include_risk_flags=False):
        """
        Wraps model data into the standard Foundry Protocol Envelope.
        
        Returns:
            dict: Standardized envelope format for all Zelda API responses
        """
        return {
            "origin": self.source_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": self.get_serialized_data(),
            "risk_flags": self.get_risk_flags() if include_risk_flags else {}
        }
    
    def get_serialized_data(self):
        """
        Override in child classes to return model-specific payload.
        Should return a dictionary of key data points.
        """
        return {"id": self.id}
    
    def get_risk_flags(self):
        """
        Override in child classes to return validation/risk data.
        Used for data quality scoring.
        """
        return {}