# zelda_api/registry.py
"""
Pinnacle Registry
Centralized registry for all Zelda AI models, endpoints, and capabilities.
"""
from typing import Dict, List


class PinnacleRegistry:
    """
    Central registry for Zelda AI capabilities and models.
    Maintains a catalog of available AI engines, matching algorithms, and data sources.
    """
    
    # AI Engines available
    AI_ENGINES = {
        "vector_matching": {
            "name": "Vector Matching Engine",
            "version": "1.0",
            "description": "Semantic similarity matching using vector embeddings",
            "status": "active"
        },
        "pitch_analyzer": {
            "name": "Pitch Deck Analyzer",
            "version": "1.0",
            "description": "Document parsing and metric extraction engine",
            "status": "active"
        },
        "text_summarizer": {
            "name": "Web Text Summarizer",
            "version": "1.0",
            "description": "Extracts structured insights from unstructured text",
            "status": "active"
        },
        "intelligence_memo": {
            "name": "Intelligence Memo Generator",
            "version": "1.0",
            "description": "Compiles executive intelligence briefs with market analysis",
            "status": "active"
        }
    }
    
    # API Endpoints
    API_ENDPOINTS = {
        "global_search": "/api/v1/zelda/search/",
        "pitch_analysis": "/api/v1/zelda/pitch-analysis/",
        "investor_portfolio": "/api/v1/zelda/investor-portfolio/",
        "founder_match_radar": "/api/v1/zelda/founder/match-radar/",
        "summarizer": "/api/v1/zelda/summarize/",
        "intelligence_memo": "/api/v1/zelda/intelligence-memo/"
    }
    
    # Data Sources
    DATA_SOURCES = {
        "internal_db": {
            "source": "Internal PostgreSQL Database",
            "tables": ["Application", "InvestorApplication", "ArticlePost", "Follow"],
            "update_frequency": "Real-time"
        },
        "web_crawl": {
            "source": "Web Crawling Pipeline",
            "scope": "External startup data, Crunchbase, LinkedIn",
            "update_frequency": "Daily"
        },
        "user_generated": {
            "source": "User-submitted documents",
            "formats": ["PDF", "PPTX", "TXT"],
            "update_frequency": "On-demand"
        }
    }
    
    @classmethod
    def get_engine(cls, engine_name: str) -> Dict:
        """Get details about a specific AI engine."""
        return cls.AI_ENGINES.get(engine_name, {})
    
    @classmethod
    def list_engines(cls) -> List[str]:
        """List all available AI engines."""
        return list(cls.AI_ENGINES.keys())
    
    @classmethod
    def get_endpoint(cls, endpoint_name: str) -> str:
        """Get the URL path for an API endpoint."""
        return cls.API_ENDPOINTS.get(endpoint_name, "")
    
    @classmethod
    def list_endpoints(cls) -> Dict[str, str]:
        """List all available API endpoints."""
        return cls.API_ENDPOINTS.copy()
    
    @classmethod
    def get_status(cls) -> Dict:
        """Get overall Zelda AI system status."""
        active_engines = sum(1 for e in cls.AI_ENGINES.values() if e['status'] == 'active')
        
        return {
            "system": "Zelda AI - Interlink Foundry",
            "status": "operational",
            "active_engines": active_engines,
            "total_engines": len(cls.AI_ENGINES),
            "data_sources": len(cls.DATA_SOURCES),
            "api_endpoints": len(cls.API_ENDPOINTS),
            "engines": cls.list_engines(),
            "data_sources_list": list(cls.DATA_SOURCES.keys())
        }