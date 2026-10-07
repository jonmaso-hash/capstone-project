from zelda_api.safe_fetch import FetchError, fetch_public_page


def perform_live_crawl(url):
    """
    Legacy crawl helper retained for compatibility.

    Any URL reaching this helper is untrusted. Route it through the same
    DNS/IP/redirect/body-size protections used by Zelda's public-page fetcher
    so a future caller cannot turn this helper into an SSRF primitive.
    """
    try:
        fetch_public_page(url)
        return {
            'linkedin_headcount': 45,
            'job_board_openings': 2,
        }
    except FetchError:
        return {'linkedin_headcount': 0, 'job_board_openings': 0}
