import requests
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def get_live_startup_data(url):
    if not url:
        return {'linkedin_headcount': 0, 'job_board_openings': 0}

    try:
        # Use a user-agent to avoid being blocked
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Now we target the stable 'cardOutline' classes we identified
        job_cards = soup.find_all('div', class_='cardOutline')
        
        return {
            'linkedin_headcount': 0, 
            'job_board_openings': len(job_cards) # This will now be dynamic!
        }
    except Exception as e:
        logger.error(f"Crawling failed for {url}: {e}")
        return {'linkedin_headcount': 0, 'job_board_openings': 0}