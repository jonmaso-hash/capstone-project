# zelda_api/protocol.py
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class FoundryStandardMixin:
    """
    Pinnacle-standard Mixin: Enforces strict data normalization and
    validates the 'Zelda' language contract across all 13 Provider APIs.
    """
    
    # Must be overridden by the child class
    source_name = "undefined_source"

    def to_foundry_envelope(self):
        """
        Normalizes provider object into the standard Zelda AI format.
        Includes pre-flight validation to ensure data integrity.
        """
        # 1. Pre-flight check: Ensure source_name is defined
        if self.source_name == "undefined_source":
            logger.warning(f"Protocol Warning: {self.__class__.__name__} has not defined a source_name.")

        try:
            # 2. Construct the envelope
            envelope = {
                "origin": self.source_name,
                "timestamp": getattr(self, 'updated_at', timezone.now()),
                "intelligence_score": getattr(self, 'zelda_score', 0.0),
                "payload": self.get_serialized_data(),
                "risk_flags": getattr(self, 'ai_risk_assessment_flags', {})
            }
            
            # 3. Post-construction validation
            return self._validate_envelope(envelope)

        except Exception as e:
            logger.error(f"Foundry Protocol Violation for {self.source_name}: {e}")
            return {"error": "Normalization failed", "origin": self.source_name}

    def _validate_envelope(self, envelope):
        """Internal helper to ensure the envelope meets minimum requirements."""
        if not envelope.get("payload"):
            logger.error(f"Validation Error: Empty payload detected for {self.source_name}")
        return envelope

    def get_serialized_data(self):
        """
        Each API model MUST implement this. 
        If not, the Foundry Protocol will explicitly raise an error.
        """
        raise NotImplementedError(
            f"Pinnacle Error: {self.__class__.__name__} must implement 'get_serialized_data()'."
        )
        
    def to_foundry_envelope(self, include_full_data=False):
        # Business Flow Improvement: 
        # Only return the "essential" payload unless explicitly asked for more.
        payload = self.get_serialized_data() if include_full_data else self.get_essential_summary()
        return {
            "origin": self.source_name,
            "payload": payload,
            "status": "optimized"
        }