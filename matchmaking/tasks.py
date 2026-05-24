from celery import shared_task
from django.core.cache import cache
from .models import Application
from matchmaking.services.web_crawling import get_live_startup_data


@shared_task
def crawl_startup_data_task(application_id):
    """
    Background task to fetch data and update the cache.
    """
    try:
        app = Application.objects.get(id=application_id)
        # Assuming your service function exists as imported
        data = get_live_startup_data(app.linkedin_url)
        
        # Cache the result for 1 hour (3600 seconds)
        cache_key = f"startup_data_{app.id}"
        cache.set(cache_key, data, 3600)
        return f"Successfully cached data for {app.company_name}"
        
    except Application.DoesNotExist:
        return f"Application with id {application_id} not found."
    except Exception as e:
        return f"Error crawling data: {str(e)}"