"""
External Verification Adapters
Modular classes to fetch observed data from various APIs.
"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseVerifier(ABC):
    """Abstract base class for all external data sources."""
    @abstractmethod
    def fetch(self, entity_name, attribute):
        """Must return a dict: {'value': float, 'source_url': str, 'date': date} or None"""
        pass

class CrunchbaseVerifier(BaseVerifier):
    def fetch(self, entity_name, attribute):
        logger.info(f"Querying Crunchbase for {entity_name}...")
        # IMPLEMENTATION: Integrate with Crunchbase API
        # Example logic:
        # data = requests.get(f"https://api.crunchbase.com/v4/entities/{entity_name}...")
        # return {'value': 20000000.0, 'source_url': 'https://crunchbase.com/...', 'date': '2026-06-01'}
        return None 

class SECVerifier(BaseVerifier):
    def fetch(self, entity_name, attribute):
        logger.info(f"Querying SEC EDGAR for {entity_name}...")
        # IMPLEMENTATION: Integrate with SEC EDGAR API
        return None

class LinkedInVerifier(BaseVerifier):
    def fetch(self, entity_name, attribute):
        logger.info(f"Querying LinkedIn for {entity_name}...")
        return None

class VerifierFactory:
    """Factory to return the correct verifier based on source type."""
    _verifiers = {
        'crunchbase': CrunchbaseVerifier(),
        'sec': SECVerifier(),
        'linkedin': LinkedInVerifier(),
    }

    @staticmethod
    def get_verifier(source_type):
        return VerifierFactory._verifiers.get(source_type.lower())