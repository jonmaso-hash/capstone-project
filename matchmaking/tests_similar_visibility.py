"""
"Similar startups" only opens for a company its viewer could discover.

find_similar_startups filters its results to discoverable, non-denied
companies, but looked the source company up by raw id with no check. Ids are
sequential, so any signed-in user could walk them and read the name and
username of private, archived or review-denied companies from the page title
and profile link. The source now meets the same bar as the results, except
for its owner and staff.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Application
from .tests import _mock_embedding_generation

User = get_user_model()


class SimilarStartupsVisibilityTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        patcher = mock.patch('matchmaking.views.generate_profile_embedding', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.owner = User.objects.create_user('sim_owner', password='x')
        self.source = Application.objects.create(
            user=self.owner, company_name='StealthCo', founder_name='F', email='s@t.test',
            description='d', sector='SaaS', stage='Seed',
        )
        self.viewer = User.objects.create_user('sim_viewer', password='x')
        self.staff = User.objects.create_user('sim_staff', password='x', is_staff=True)
        self.url = reverse('matchmaking:find_similar_startups', args=[self.source.id])

    def _get(self, user):
        self.client.force_login(user)
        return self.client.get(self.url)

    def _set(self, **fields):
        Application.objects.filter(id=self.source.id).update(**fields)

    def test_a_discoverable_company_is_open_to_any_signed_in_user(self):
        self.assertContains(self._get(self.viewer), 'StealthCo')

    def test_a_private_company_is_not_revealed(self):
        self._set(is_private=True)
        self.assertNotContains(self._get(self.viewer), 'StealthCo', status_code=404)

    def test_an_archived_company_is_not_revealed(self):
        self._set(archived_at=timezone.now())
        self.assertNotContains(self._get(self.viewer), 'StealthCo', status_code=404)

    def test_a_review_denied_company_is_not_revealed(self):
        self._set(review_status='DENIED')
        self.assertNotContains(self._get(self.viewer), 'StealthCo', status_code=404)

    def test_the_owner_still_sees_their_private_company(self):
        self._set(is_private=True)
        self.assertContains(self._get(self.owner), 'StealthCo')

    def test_staff_still_see_a_private_company(self):
        self._set(is_private=True)
        self.assertContains(self._get(self.staff), 'StealthCo')
