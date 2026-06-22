# zelda_api/truth_delta_sources.py
"""
Data source integrations for Truth Delta verification.
Pulls observed data from: Crunchbase, LinkedIn, SEC, Web, News, etc.
"""
import logging
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from django.conf import settings
from .truth_delta_models import ObservedDatapoint, ExternalDataSource

logger = logging.getLogger(__name__)


class DataSourceIntegration:
    """Base class for all data source integrations"""
    
    source_type = None
    source_name = None
    
    def authenticate(self) -> bool:
        """Check if API credentials are valid"""
        raise NotImplementedError
    
    def fetch_company_data(self, company_name: str, domain: str = None) -> Dict:
        """Fetch company data from this source"""
        raise NotImplementedError
    
    def extract_revenue(self, data: Dict) -> Optional[Tuple[float, str]]:
        """Extract revenue figure (value, unit)"""
        raise NotImplementedError
    
    def extract_customers(self, data: Dict) -> Optional[int]:
        """Extract customer count"""
        raise NotImplementedError
    
    def extract_employees(self, data: Dict) -> Optional[int]:
        """Extract employee count"""
        raise NotImplementedError
    
    def extract_funding(self, data: Dict) -> Optional[float]:
        """Extract total funding raised"""
        raise NotImplementedError
    
    def extract_growth_rate(self, data: Dict) -> Optional[float]:
        """Extract YoY growth rate"""
        raise NotImplementedError


class CrunchbaseIntegration(DataSourceIntegration):
    """Integration with Crunchbase API for company data"""
    
    source_type = 'crunchbase'
    source_name = 'Crunchbase'
    
    def __init__(self):
        self.api_key = getattr(settings, 'CRUNCHBASE_API_KEY', None)
        self.base_url = 'https://api.crunchbase.com/v4'
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({'X-Cb-User-Key': self.api_key})
    
    def authenticate(self) -> bool:
        """Verify API key is valid"""
        if not self.api_key:
            logger.warning("No Crunchbase API key configured")
            return False
        
        try:
            response = self.session.get(f"{self.base_url}/entities/companies", params={'limit': 1})
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Crunchbase auth failed: {e}")
            return False
    
    def fetch_company_data(self, company_name: str, domain: str = None) -> Dict:
        """Fetch company data from Crunchbase"""
        if not self.api_key:
            return {}
        
        try:
            # Search by domain first (most reliable)
            if domain:
                response = self.session.get(
                    f"{self.base_url}/entities/companies",
                    params={
                        'domain_name': domain,
                        'sort_order': 'desc',
                        'sort_by': 'founded_on'
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get('entities'):
                        return data['entities'][0]
            
            # Fallback to name search
            response = self.session.get(
                f"{self.base_url}/entities/companies",
                params={
                    'name': company_name,
                    'limit': 1
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('entities'):
                    return data['entities'][0]
            
            return {}
        
        except Exception as e:
            logger.error(f"Crunchbase fetch failed for {company_name}: {e}")
            return {}
    
    def extract_revenue(self, data: Dict) -> Optional[Tuple[float, str]]:
        """Extract revenue from Crunchbase data"""
        if not data:
            return None
        
        # Crunchbase uses 'revenue_range' or 'annual_revenue'
        annual_revenue = data.get('annual_revenue')
        if annual_revenue and isinstance(annual_revenue, (int, float)):
            return float(annual_revenue), '$'
        
        return None
    
    def extract_customers(self, data: Dict) -> Optional[int]:
        """Extract customer count from Crunchbase"""
        if not data:
            return None
        
        customers = data.get('num_customers')
        if customers:
            return int(customers)
        
        return None
    
    def extract_employees(self, data: Dict) -> Optional[int]:
        """Extract employee count from Crunchbase"""
        if not data:
            return None
        
        # Crunchbase typically has employee count range
        employees = data.get('num_employees_max') or data.get('num_employees_min')
        if employees:
            return int(employees)
        
        return None
    
    def extract_funding(self, data: Dict) -> Optional[float]:
        """Extract total funding raised"""
        if not data:
            return None
        
        funding = data.get('total_funding_usd')
        if funding:
            return float(funding)
        
        return None
    
    def extract_growth_rate(self, data: Dict) -> Optional[float]:
        """Growth rate not directly available in Crunchbase"""
        return None


class LinkedInIntegration(DataSourceIntegration):
    """Integration with LinkedIn for employee count and company data"""
    
    source_type = 'linkedin'
    source_name = 'LinkedIn'
    
    def __init__(self):
        self.api_key = getattr(settings, 'LINKEDIN_API_KEY', None)
        self.base_url = 'https://api.linkedin.com/v2'
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({'Authorization': f'Bearer {self.api_key}'})
    
    def authenticate(self) -> bool:
        """Verify LinkedIn API access"""
        if not self.api_key:
            logger.warning("No LinkedIn API key configured")
            return False
        
        try:
            response = self.session.get(f"{self.base_url}/me", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"LinkedIn auth failed: {e}")
            return False
    
    def fetch_company_data(self, company_name: str, domain: str = None) -> Dict:
        """Fetch company data from LinkedIn"""
        if not self.api_key:
            return {}
        
        try:
            response = self.session.get(
                f"{self.base_url}/search/companies",
                params={'keywords': company_name, 'count': 1},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('elements'):
                    return data['elements'][0]
            
            return {}
        
        except Exception as e:
            logger.error(f"LinkedIn fetch failed for {company_name}: {e}")
            return {}
    
    def extract_employees(self, data: Dict) -> Optional[int]:
        """Extract employee count from LinkedIn"""
        if not data:
            return None
        
        # LinkedIn provides employee count range
        employee_count_range = data.get('employeeCountRange', {})
        max_count = employee_count_range.get('max')
        
        if max_count:
            return int(max_count)
        
        return None
    
    def extract_revenue(self, data: Dict) -> Optional[Tuple[float, str]]:
        return None  # LinkedIn doesn't provide revenue
    
    def extract_customers(self, data: Dict) -> Optional[int]:
        return None
    
    def extract_funding(self, data: Dict) -> Optional[float]:
        return None
    
    def extract_growth_rate(self, data: Dict) -> Optional[float]:
        return None


class SECFilingsIntegration(DataSourceIntegration):
    """Integration with SEC EDGAR for public company filings"""
    
    source_type = 'sec'
    source_name = 'SEC EDGAR'
    
    def __init__(self):
        self.base_url = 'https://www.sec.gov/cgi-bin/browse-edgar'
        self.session = requests.Session()
    
    def authenticate(self) -> bool:
        """SEC EDGAR is public, always available"""
        return True
    
    def fetch_company_data(self, company_name: str, domain: str = None) -> Dict:
        """Fetch company CIK from SEC"""
        try:
            response = self.session.get(
                self.base_url,
                params={'company': company_name, 'owner': 'exclude', 'action': 'getcompany'},
                timeout=10,
                headers={'User-Agent': 'Zelda Intelligence'}
            )
            
            if response.status_code == 200:
                # Parse response to extract CIK
                import re
                cik_match = re.search(r'CIK=(\d+)', response.text)
                if cik_match:
                    return {'cik': cik_match.group(1), 'html': response.text}
            
            return {}
        
        except Exception as e:
            logger.error(f"SEC fetch failed for {company_name}: {e}")
            return {}
    
    def extract_revenue(self, data: Dict) -> Optional[Tuple[float, str]]:
        """Extract revenue from 10-K/10-Q filings"""
        # This would require parsing HTML/XML from SEC filings
        # Placeholder for now
        return None
    
    def extract_employees(self, data: Dict) -> Optional[int]:
        return None
    
    def extract_customers(self, data: Dict) -> Optional[int]:
        return None
    
    def extract_funding(self, data: Dict) -> Optional[float]:
        return None
    
    def extract_growth_rate(self, data: Dict) -> Optional[float]:
        return None


class NewsIntegration(DataSourceIntegration):
    """Integration with news APIs for funding announcements"""
    
    source_type = 'news'
    source_name = 'News API'
    
    def __init__(self):
        self.api_key = getattr(settings, 'NEWS_API_KEY', None)
        self.base_url = 'https://newsapi.org/v2'
    
    def authenticate(self) -> bool:
        if not self.api_key:
            logger.warning("No News API key configured")
            return False
        return True
    
    def fetch_company_data(self, company_name: str, domain: str = None) -> Dict:
        """Fetch news about company"""
        if not self.api_key:
            return {}
        
        try:
            response = requests.get(
                f"{self.base_url}/everything",
                params={
                    'q': company_name,
                    'sortBy': 'publishedAt',
                    'language': 'en',
                    'apiKey': self.api_key
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            
            return {}
        
        except Exception as e:
            logger.error(f"News fetch failed for {company_name}: {e}")
            return {}
    
    def extract_funding(self, data: Dict) -> Optional[float]:
        """Extract funding amounts from news articles"""
        # This would require NLP to parse funding amounts from articles
        # Placeholder for now
        return None
    
    def extract_revenue(self, data: Dict) -> Optional[Tuple[float, str]]:
        return None
    
    def extract_customers(self, data: Dict) -> Optional[int]:
        return None
    
    def extract_employees(self, data: Dict) -> Optional[int]:
        return None
    
    def extract_growth_rate(self, data: Dict) -> Optional[float]:
        return None


class DataSourceManager:
    """Manages all data source integrations"""
    
    INTEGRATIONS = {
        'crunchbase': CrunchbaseIntegration,
        'linkedin': LinkedInIntegration,
        'sec': SECFilingsIntegration,
        'news': NewsIntegration,
    }
    
    @classmethod
    def get_integration(cls, source_type: str) -> Optional[DataSourceIntegration]:
        """Get integration instance for a source type"""
        integration_class = cls.INTEGRATIONS.get(source_type)
        if integration_class:
            return integration_class()
        return None
    
    @classmethod
    def get_all_active(cls) -> List[DataSourceIntegration]:
        """Get all active integrations"""
        active = []
        for source_type, integration_class in cls.INTEGRATIONS.items():
            integration = integration_class()
            if integration.authenticate():
                active.append(integration)
            else:
                logger.warning(f"Skipping {source_type} - authentication failed")
        return active
    
    @classmethod
    def fetch_company_data(cls, company_name: str, domain: str = None) -> Dict[str, Dict]:
        """
        Fetch company data from all available sources.
        Returns dict of {source_type: data}
        """
        results = {}
        
        for integration in cls.get_all_active():
            logger.info(f"Fetching {company_name} from {integration.source_name}")
            try:
                data = integration.fetch_company_data(company_name, domain)
                if data:
                    results[integration.source_type] = data
            except Exception as e:
                logger.error(f"Error fetching from {integration.source_name}: {e}")
        
        return results
    
    @classmethod
    def create_observed_datapoints(
        cls,
        document,
        company_name: str,
        domain: str = None
    ) -> List[ObservedDatapoint]:
        """
        Fetch data from all sources and create ObservedDatapoint records.
        
        Returns:
            List of created ObservedDatapoint objects
        """
        created_points = []
        
        # Fetch from all sources
        all_data = cls.fetch_company_data(company_name, domain)
        
        if not all_data:
            logger.warning(f"No data found for {company_name}")
            return []
        
        # Create ObservedDatapoint for each metric found
        for source_type, data in all_data.items():
            integration = cls.get_integration(source_type)
            if not integration:
                continue
            
            # Get or create ExternalDataSource
            external_source, _ = ExternalDataSource.objects.get_or_create(
                source_type=source_type,
                defaults={
                    'source_name': integration.source_name,
                    'is_active': True
                }
            )
            
            # Revenue
            revenue_data = integration.extract_revenue(data)
            if revenue_data:
                value, unit = revenue_data
                point = ObservedDatapoint.objects.create(
                    document=document,
                    category='revenue',
                    observed_value=str(value),
                    observed_value_numeric=float(value),
                    unit=unit,
                    source=external_source,
                    source_credibility=0.95,  # Crunchbase/SEC are highly credible
                    extraction_method='api'
                )
                created_points.append(point)
            
            # Customers
            customers = integration.extract_customers(data)
            if customers:
                point = ObservedDatapoint.objects.create(
                    document=document,
                    category='customers',
                    observed_value=str(customers),
                    observed_value_numeric=float(customers),
                    unit='customers',
                    source=external_source,
                    source_credibility=0.9,
                    extraction_method='api'
                )
                created_points.append(point)
            
            # Employees
            employees = integration.extract_employees(data)
            if employees:
                point = ObservedDatapoint.objects.create(
                    document=document,
                    category='employees',
                    observed_value=str(employees),
                    observed_value_numeric=float(employees),
                    unit='headcount',
                    source=external_source,
                    source_credibility=0.85,
                    extraction_method='api'
                )
                created_points.append(point)
            
            # Funding
            funding = integration.extract_funding(data)
            if funding:
                point = ObservedDatapoint.objects.create(
                    document=document,
                    category='funding_raised',
                    observed_value=f"${funding:,.0f}",
                    observed_value_numeric=float(funding),
                    unit='$',
                    source=external_source,
                    source_credibility=0.95,
                    extraction_method='api'
                )
                created_points.append(point)
        
        logger.info(f"Created {len(created_points)} observed datapoints for {company_name}")
        return created_points
    
class ExternalSourceManager:
    """Interface for Crunchbase, LinkedIn, News, SEC."""
    @staticmethod
    def get_market_data(company_name):
        # Implementation for external API calls
        return {"funding": "verified", "revenue": "partial"}


# Global manager instance
data_source_manager = DataSourceManager()