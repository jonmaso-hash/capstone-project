# zelda_api/adapters.py
from automotive_api.models import VehicleAsset
from logistics_api.models import FreightShipment
from banking_api.models import Transaction
from hotel_api.models import HotelReservation
from insurance_api.models import InsuranceClaim
from real_estate_api.models import UnderwritingReport
from messaging_api.models import ChatMessage
from marketplace_api.models import LicensePurchase
from marketing_api.models import LeadICPScore
from legal_api.models import ConflictEvaluation
from energy_api.models import GenerationLog
from articles_api.models import ArticlePost
from jobs_api.models import JobApplication

class DataAdapter:
    """
    Pinnacle-standard Adapter: Decouples the orchestrator from 
    specific API implementation details using a registry pattern.
    """
    
    # 1. THE REGISTRY: Maps source types to their respective models
    # This centralizes configuration and makes the code Open/Closed.
    _MODEL_REGISTRY = {
        'automotive': VehicleAsset,
        'logistics': FreightShipment,
        'banking': Transaction,
        'hotel': HotelReservation,
        'insurance': InsuranceClaim,
        'real_estate': UnderwritingReport,
        'messaging': ChatMessage,
        'marketplace': LicensePurchase,
        'marketing': LeadICPScore,
        'legal': ConflictEvaluation,
        'energy_api': GenerationLog,
        'articles': ArticlePost,
        'jobs': JobApplication,
    }

    @staticmethod
    def get_unified_data(source_type, id):
        # 2. LOOKUP: Retrieve the model class dynamically
        model_class = DataAdapter._MODEL_REGISTRY.get(source_type)
        
        if not model_class:
            raise ValueError(f"Source type '{source_type}' is not registered in the Foundry protocol.")
            
        # 3. DELEGATION: Delegate data retrieval and normalization to the model
        # The model itself is now responsible for its own Zelda envelope format.
        try:
            obj = model_class.objects.get(id=id)
            return obj.to_foundry_envelope()
        except model_class.DoesNotExist:
            raise ValueError(f"{source_type} object with id {id} not found.")