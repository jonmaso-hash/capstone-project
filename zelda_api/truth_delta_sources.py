# zelda_api/truth_delta_sources.py
"""
Data source integrations for Truth Delta verification.
Pulls observed data from: Crunchbase, SEC EDGAR, News.

Deliberately does NOT integrate LinkedIn (or scrape it directly) — the
official LinkedIn API requires partner approval most projects can't get,
and scraping linkedin.com directly violates its Terms of Service. SEC
EDGAR and Crunchbase/NewsAPI (with a legitimate key) are the sources kept
here on purpose.
"""
import logging
import re
import requests
from typing import Dict, List, Optional, Tuple
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

    def extract_time_period(self, data: Dict) -> Optional[str]:
        """
        Best-effort label for when the observed data is from (e.g. 'FY2025
        10-K'), so a stale figure doesn't get compared against a fresh
        pitch-deck claim without context. Optional — sources that don't
        know return None.
        """
        return None


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
            logger.info("No Crunchbase API key configured — skipping this source.")
            return False

        try:
            response = self.session.get(f"{self.base_url}/entities/companies", params={'limit': 1}, timeout=10)
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
                    params={'domain_name': domain, 'sort_order': 'desc', 'sort_by': 'founded_on'},
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get('entities'):
                        return data['entities'][0]

            # Fallback to name search
            response = self.session.get(
                f"{self.base_url}/entities/companies",
                params={'name': company_name, 'limit': 1},
                timeout=10,
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
        if not data:
            return None
        annual_revenue = data.get('annual_revenue')
        if annual_revenue and isinstance(annual_revenue, (int, float)):
            return float(annual_revenue), '$'
        return None

    def extract_customers(self, data: Dict) -> Optional[int]:
        if not data:
            return None
        customers = data.get('num_customers')
        if customers:
            return int(customers)
        return None

    def extract_employees(self, data: Dict) -> Optional[int]:
        if not data:
            return None
        employees = data.get('num_employees_max') or data.get('num_employees_min')
        if employees:
            return int(employees)
        return None

    def extract_funding(self, data: Dict) -> Optional[float]:
        if not data:
            return None
        funding = data.get('total_funding_usd')
        if funding:
            return float(funding)
        return None

    def extract_growth_rate(self, data: Dict) -> Optional[float]:
        return None


class SECFilingsIntegration(DataSourceIntegration):
    """
    Integration with SEC EDGAR's public XBRL "company facts" API. Needs no
    API key — only applies to companies that file with the SEC (public
    companies, or private ones with registered securities), so it will
    correctly find nothing for most venture-stage founders. When it does
    find a filer, the numbers are the company's own audited/reported
    figures, not an estimate.
    """

    source_type = 'sec'
    source_name = 'SEC EDGAR'

    # SEC's fair-access policy requires a descriptive User-Agent with a
    # real contact — a generic/missing one gets rate-limited or blocked.
    # Deployers should replace the email with their own if this integration
    # gets meaningful production traffic.
    USER_AGENT = 'Interlink Foundry Truth Delta (contact: admin@interlinkfoundry.com)'

    REVENUE_TAGS = [
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'RevenueFromContractWithCustomerIncludingAssessedTax',
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.USER_AGENT})

    def authenticate(self) -> bool:
        """SEC EDGAR is public, always available."""
        return True

    def _find_cik(self, company_name: str) -> Optional[str]:
        """
        Resolves a company name to a 10-digit zero-padded CIK via SEC's
        public company-search Atom feed. Returns the first match — SEC's
        own relevance ranking, not ours.
        """
        try:
            response = self.session.get(
                'https://www.sec.gov/cgi-bin/browse-edgar',
                params={'action': 'getcompany', 'company': company_name, 'type': '10-K', 'owner': 'include', 'count': 10, 'output': 'atom'},
                timeout=10,
            )
            if response.status_code != 200:
                return None

            match = re.search(r'CIK=(\d{10})', response.text) or re.search(r'CIK=(\d+)', response.text)
            if not match:
                return None
            return match.group(1).zfill(10)
        except Exception as e:
            logger.error(f"SEC CIK lookup failed for {company_name}: {e}")
            return None

    def fetch_company_data(self, company_name: str, domain: str = None) -> Dict:
        """
        Resolves the company to a CIK, then pulls its full XBRL company
        facts payload (all tagged financial figures it has ever filed).
        """
        cik = self._find_cik(company_name)
        if not cik:
            return {}

        try:
            response = self.session.get(
                f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json',
                timeout=15,
            )
            if response.status_code != 200:
                return {}
            payload = response.json()
            payload['_cik'] = cik
            return payload
        except Exception as e:
            logger.error(f"SEC companyfacts fetch failed for {company_name} (CIK {cik}): {e}")
            return {}

    def _latest_annual_fact(self, data: Dict, tags: List[str]) -> Optional[Dict]:
        """
        Given a companyfacts payload and a list of candidate XBRL concept
        names, returns the single most recent 10-K-form USD fact across
        ALL of them — not just whichever tag is listed first. Filers
        change which concept they tag over time (e.g. most switched from
        the old 'Revenues' to 'RevenueFromContractWithCustomerExcluding...'
        around ASC 606 adoption in 2018), so a tag that merely has *some*
        data isn't necessarily the one with the *current* data; picking
        the first non-empty tag returned several-year-stale figures for
        real companies during live testing.
        """
        facts = (data or {}).get('facts', {}).get('us-gaap', {})
        all_annual = []
        for tag in tags:
            concept = facts.get(tag)
            if not concept:
                continue
            usd_facts = concept.get('units', {}).get('USD', [])
            all_annual.extend(f for f in usd_facts if f.get('form') == '10-K' and f.get('val') is not None)

        if not all_annual:
            return None
        all_annual.sort(key=lambda f: f.get('end', ''), reverse=True)
        return all_annual[0]

    def extract_revenue(self, data: Dict) -> Optional[Tuple[float, str]]:
        fact = self._latest_annual_fact(data, self.REVENUE_TAGS)
        if not fact:
            return None
        return float(fact['val']), '$'

    def extract_employees(self, data: Dict) -> Optional[int]:
        dei = (data or {}).get('facts', {}).get('dei', {})
        concept = dei.get('EntityNumberOfEmployees')
        if not concept:
            return None
        pure_facts = concept.get('units', {}).get('pure', [])
        if not pure_facts:
            return None
        pure_facts.sort(key=lambda f: f.get('end', ''), reverse=True)
        val = pure_facts[0].get('val')
        return int(val) if val is not None else None

    def extract_customers(self, data: Dict) -> Optional[int]:
        return None  # Not a standard XBRL concept — SEC filings rarely disclose this in structured form.

    def extract_funding(self, data: Dict) -> Optional[float]:
        return None  # SEC filers are typically past the "funding raised" framing pitch decks use.

    def extract_growth_rate(self, data: Dict) -> Optional[float]:
        return None

    def extract_time_period(self, data: Dict) -> Optional[str]:
        fact = self._latest_annual_fact(data, self.REVENUE_TAGS)
        if not fact:
            return None
        fy = fact.get('fy')
        end = fact.get('end', '')
        return f"FY{fy} 10-K (period ending {end})" if fy else f"10-K (period ending {end})"


class NewsIntegration(DataSourceIntegration):
    """
    Integration with NewsAPI for recent coverage of the company. Doesn't
    produce a structured numeric datapoint (extracting a reliable dollar
    figure out of free-text headlines needs real NLP, which is out of
    scope) — instead exposes recent headlines as qualitative corroborating
    context for the Claude judgment step in TruthDeltaEngine.
    """

    source_type = 'news'
    source_name = 'News API'

    def __init__(self):
        self.api_key = getattr(settings, 'NEWS_API_KEY', None)
        self.base_url = 'https://newsapi.org/v2'

    def authenticate(self) -> bool:
        if not self.api_key:
            logger.info("No News API key configured — skipping this source.")
            return False
        return True

    def fetch_company_data(self, company_name: str, domain: str = None) -> Dict:
        if not self.api_key:
            return {}

        try:
            response = requests.get(
                f"{self.base_url}/everything",
                params={'q': company_name, 'sortBy': 'publishedAt', 'language': 'en', 'pageSize': 5, 'apiKey': self.api_key},
                timeout=10,
            )
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            logger.error(f"News fetch failed for {company_name}: {e}")
            return {}

    def extract_headlines(self, data: Dict) -> List[str]:
        """Recent article titles, for Claude to read as qualitative context — not a claim source itself."""
        articles = (data or {}).get('articles', [])
        return [a['title'] for a in articles if a.get('title')][:5]

    def extract_funding(self, data: Dict) -> Optional[float]:
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
        'sec': SECFilingsIntegration,
        'news': NewsIntegration,
    }

    @classmethod
    def get_integration(cls, source_type: str) -> Optional[DataSourceIntegration]:
        integration_class = cls.INTEGRATIONS.get(source_type)
        if integration_class:
            return integration_class()
        return None

    @classmethod
    def get_all_active(cls) -> List[DataSourceIntegration]:
        active = []
        for source_type, integration_class in cls.INTEGRATIONS.items():
            integration = integration_class()
            if integration.authenticate():
                active.append(integration)
            else:
                logger.info(f"Skipping {source_type} — not configured or unreachable.")
        return active

    @classmethod
    def fetch_company_data(cls, company_name: str, domain: str = None) -> Dict[str, Dict]:
        """Fetch company data from all available sources. Returns dict of {source_type: data}"""
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
    def create_observed_datapoints(cls, document, company_name: str, domain: str = None) -> List[ObservedDatapoint]:
        """
        Fetch data from all sources and create ObservedDatapoint records.
        Returns the list of created ObservedDatapoint objects.
        """
        created_points = []
        all_data = cls.fetch_company_data(company_name, domain)

        if not all_data:
            logger.info(f"No external data found for {company_name}")
            return []

        for source_type, data in all_data.items():
            integration = cls.get_integration(source_type)
            if not integration:
                continue

            external_source, _ = ExternalDataSource.objects.get_or_create(
                source_type=source_type,
                defaults={'source_name': integration.source_name, 'is_active': True},
            )
            time_period = integration.extract_time_period(data) or ''

            revenue_data = integration.extract_revenue(data)
            if revenue_data:
                value, unit = revenue_data
                created_points.append(ObservedDatapoint.objects.create(
                    document=document, category='revenue', observed_value=str(value),
                    observed_value_numeric=float(value), unit=unit, time_period=time_period,
                    source=external_source, source_credibility=0.95, extraction_method='api',
                ))

            customers = integration.extract_customers(data)
            if customers:
                created_points.append(ObservedDatapoint.objects.create(
                    document=document, category='customers', observed_value=str(customers),
                    observed_value_numeric=float(customers), unit='customers', time_period=time_period,
                    source=external_source, source_credibility=0.9, extraction_method='api',
                ))

            employees = integration.extract_employees(data)
            if employees:
                created_points.append(ObservedDatapoint.objects.create(
                    document=document, category='employees', observed_value=str(employees),
                    observed_value_numeric=float(employees), unit='headcount', time_period=time_period,
                    source=external_source, source_credibility=0.85, extraction_method='api',
                ))

            funding = integration.extract_funding(data)
            if funding:
                created_points.append(ObservedDatapoint.objects.create(
                    document=document, category='funding_raised', observed_value=f"${funding:,.0f}",
                    observed_value_numeric=float(funding), unit='$', time_period=time_period,
                    source=external_source, source_credibility=0.95, extraction_method='api',
                ))

        logger.info(f"Created {len(created_points)} observed datapoints for {company_name}")
        return created_points

    @classmethod
    def fetch_news_headlines(cls, company_name: str) -> List[str]:
        """Best-effort recent headlines for qualitative context — [] if NewsAPI isn't configured."""
        news = NewsIntegration()
        if not news.authenticate():
            return []
        return news.extract_headlines(news.fetch_company_data(company_name))


# Global manager instance
data_source_manager = DataSourceManager()
