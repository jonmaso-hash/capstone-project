"""
Every page route in the pages app renders.

/services was routed to a template that never existed, so every visit was a
TemplateDoesNotExist 500 -- unnoticed because nothing linked to it. This walks
each argument-free route in pages/urls.py, signed out and signed in, and fails on
a server error, so a route left pointing at a missing template can't hide again.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import URLPattern, reverse

from pages import urls as pages_urls

User = get_user_model()


class PageRoutesRenderTests(TestCase):

    def _routes(self):
        for pattern in pages_urls.urlpatterns:
            if isinstance(pattern, URLPattern) and pattern.name and not pattern.pattern.converters:
                yield pattern.name

    def test_the_services_route_is_gone(self):
        self.assertNotIn('services', list(self._routes()))

    def test_no_page_route_returns_a_server_error(self):
        signed_in = User.objects.create_user('page_routes_user', password='x')
        for label, login in (('signed out', None), ('signed in', signed_in)):
            self.client.logout()
            if login:
                self.client.force_login(login)
            for name in self._routes():
                url = reverse(f'pages:{name}')
                with self.subTest(route=name, visitor=label):
                    response = self.client.get(url)
                    self.assertLess(response.status_code, 500, f'{url} returned {response.status_code}')
