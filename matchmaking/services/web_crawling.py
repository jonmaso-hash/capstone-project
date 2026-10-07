import logging

from bs4 import BeautifulSoup

from zelda_api.safe_fetch import FetchError, fetch_public_page

logger = logging.getLogger(__name__)


def get_live_startup_data(url):
    if not url:
        return {'linkedin_headcount': 0, 'job_board_openings': 0}

    try:
        result = fetch_public_page(url)
        soup = BeautifulSoup(result.text, 'html.parser')
        job_cards = soup.find_all('div', class_='cardOutline')
        return {
            'linkedin_headcount': 0,
            'job_board_openings': len(job_cards),
        }
    except FetchError:
        logger.warning("Crawling refused or failed for an untrusted public URL.")
        return {'linkedin_headcount': 0, 'job_board_openings': 0}
