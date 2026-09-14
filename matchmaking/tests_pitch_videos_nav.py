"""
One "Pitch Videos" destination for two established video experiences.

The navigation used to carry two items -- Explore (<=30s elevator pitches) and
Pitch Videos (1-3 min pitch videos). It now carries one, pointing at
pitch_videos_entry, which only redirects: signed-out visitors start on 30 sec
(Explore), signed-in users on Full Pitch, and ?tab=30sec / ?tab=full choose
explicitly. Each page links to the other.

Both underlying pages keep their routes, data, ranking, visibility, moderation
and tracking; the existing suites (tests_explore, PitchVideosSectionTests) pin
those. These tests pin only the navigation layer.
"""
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Application, InvestorApplication
from .tests import _mock_embedding_generation

User = get_user_model()

EXPLORE = '/explore/'
FULL = '/matchmaking/pitch-videos/'
ENTRY = '/matchmaking/videos/'


class PitchVideosEntryTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)

    def _lands_on(self, expected, query=''):
        response = self.client.get(ENTRY + query)
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_the_entry_route_is_where_the_url_name_points(self):
        self.assertEqual(reverse('matchmaking:pitch_videos_entry'), ENTRY)

    def test_signed_out_visitors_start_on_30_sec(self):
        self._lands_on(EXPLORE)

    def test_signed_in_investors_start_on_full_pitch(self):
        user = User.objects.create_user('pvn_investor', password='x')
        InvestorApplication.objects.create(user=user, full_name='I', company_name='Fund', email='i@t.test',
                                           investment_focus='SaaS', investment_stage='Seed')
        self.client.force_login(user)
        self._lands_on(FULL)

    def test_signed_in_founders_start_on_full_pitch(self):
        user = User.objects.create_user('pvn_founder', password='x')
        Application.objects.create(user=user, company_name='Co', founder_name='F', email='f@t.test',
                                   description='d', sector='SaaS', stage='Seed')
        self.client.force_login(user)
        self._lands_on(FULL)

    def test_signed_in_users_without_a_role_start_on_full_pitch(self):
        self.client.force_login(User.objects.create_user('pvn_roleless', password='x'))
        self._lands_on(FULL)

    def test_a_tab_parameter_opens_either_experience_on_purpose(self):
        self._lands_on(FULL, '?tab=full')
        self.client.force_login(User.objects.create_user('pvn_member', password='x'))
        self._lands_on(EXPLORE, '?tab=30sec')

    def test_an_unknown_tab_falls_back_to_the_default(self):
        self._lands_on(EXPLORE, '?tab=nonsense')


def _main_nav(html):
    match = re.search(r'<nav[^>]*aria-label="Main Navigation"[^>]*>(.*?)</nav>', html, re.S)
    assert match, 'main navigation not found'
    return match.group(1)


class SingleNavigationItemTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)

    def _assert_one_video_destination(self, html):
        nav = _main_nav(html)
        video_links = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>\s*(Pitch Videos|Explore)\s*</a>', nav)
        self.assertEqual(video_links, [(ENTRY, 'Pitch Videos')])

    def test_signed_out_navigation_has_one_pitch_videos_item(self):
        self._assert_one_video_destination(self.client.get(reverse('pages:home')).content.decode())

    def test_signed_in_navigation_has_one_pitch_videos_item(self):
        self.client.force_login(User.objects.create_user('pvn_nav', password='x'))
        self._assert_one_video_destination(self.client.get(reverse('billing:billing_page')).content.decode())


class PitchLengthSwitchTests(TestCase):

    def test_the_full_pitch_page_switches_to_30_sec(self):
        html = self.client.get(reverse('matchmaking:pitch_videos')).content.decode()
        switch = re.search(r'<nav class="pv-length-switch[^"]*"[^>]*>(.*?)</nav>', html, re.S).group(1)
        self.assertRegex(switch, rf'<a class="pv-length-btn" href="{EXPLORE}">30 sec</a>')
        self.assertRegex(switch, rf'<a class="pv-length-btn active" href="{FULL}" aria-current="page">Full Pitch</a>')

    def test_explore_switches_to_full_pitch(self):
        html = self.client.get(reverse('explore')).content.decode()
        topbar = re.search(r'<div class="ep-topbar">(.*?)\n</div>', html, re.S).group(1)
        self.assertRegex(topbar, rf'href="{FULL}"[^>]*>\s*Full Pitch')

    def test_the_underlying_routes_are_unchanged(self):
        self.assertEqual(reverse('explore'), EXPLORE)
        self.assertEqual(reverse('matchmaking:pitch_videos'), FULL)
        self.assertEqual(reverse('matchmaking:manage_elevator_pitch'), '/matchmaking/explore/manage/')
