"""
The stranger discovery funnel.

Three paths the cold-contact audit found broken, each traced entry to
destination. These tests assert the destination, not merely that a page
renders 200 -- every one of these surfaces already returned 200 while
leading nowhere.
"""
import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Application, ProfileVideo, SellerApplication
from .tests import _mock_embedding_generation

User = get_user_model()


def _founder(username, **kw):
    user = User.objects.create_user(username, password='x')
    defaults = dict(
        company_name=f'{username}Co', founder_name='F', email=f'{username}@t.com',
        description='Forecasting software for community solar operators.',
        sector='Climate Tech', stage='Seed', raising_amount=4_000_000,
    )
    defaults.update(kw)
    return Application.objects.create(user=user, **defaults)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PublicProfileLinkTests(TestCase):
    """
    Paths 2 and 3: a browsing stranger clicking the one thing that
    interested them.

    The profile page is @login_required, and both the bulletin board and
    search results linked straight at it, so an anonymous click landed on
    a bare login form with no indication of what was behind it. Explore
    already did the right thing; the rule now lives in one place.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.app = _founder('sf_founder')

    def test_anonymous_link_goes_to_signup_carrying_the_profile(self):
        from .views import public_profile_link

        request = self.client.request().wsgi_request
        link = public_profile_link(request, 'sf_founder')
        self.assertIn(reverse('accounts:signup'), link)
        self.assertIn('sf_founder', link)

    def test_authenticated_link_goes_straight_to_the_profile(self):
        from .views import public_profile_link

        viewer = User.objects.create_user('sf_viewer', password='x')
        self.client.force_login(viewer)
        request = self.client.get('/').wsgi_request
        self.assertEqual(
            public_profile_link(request, 'sf_founder'),
            reverse('accounts:profile', kwargs={'username': 'sf_founder'}))

    def test_bulletin_card_does_not_send_a_stranger_to_a_bare_login(self):
        html = self.client.get(reverse('matchmaking:bulletin_board')).content.decode()
        profile_path = reverse('accounts:profile', kwargs={'username': 'sf_founder'})
        # Not assertNotIn(profile_path): the signup URL legitimately carries
        # it as ?next=. What must not appear is an href pointing straight at
        # the login-required page.
        self.assertNotIn(
            f'href="{profile_path}"', html,
            'an anonymous bulletin card must not link straight at a login-required page')
        self.assertIn(f'{reverse("accounts:signup")}?next={profile_path}', html)

    def test_search_result_leads_to_the_company(self):
        investor = User.objects.create_user('sf_inv', password='x')
        self.client.force_login(investor)
        html = self.client.get(reverse('matchmaking:global_search'),
                               {'industry': 'Climate Tech'}).content.decode()
        self.assertIn(reverse('accounts:profile', kwargs={'username': 'sf_founder'}), html)

    def test_no_dead_anchor_remains_on_a_search_result(self):
        investor = User.objects.create_user('sf_inv2', password='x')
        self.client.force_login(investor)
        html = self.client.get(reverse('matchmaking:global_search'),
                               {'industry': 'Climate Tech'}).content.decode()
        self.assertNotIn('Analyze Pipeline Entry', html)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ExploreSupplyChainTests(TestCase):
    """
    Path 1, as a supply-pipeline regression rather than an empty-state one.

    The audit found /explore/ empty and the first reading was "needs
    seeding". The trace said otherwise: ProfileVideo had zero rows of any
    kind, the queryset was correct, and the reason nothing existed is that
    the onboarding checklist asked for `Application.pitch_video` -- a
    different field Explore never reads.

    So this walks the whole chain: a founder posts an elevator pitch ->
    the row exists -> the visibility queryset sees it -> an anonymous
    visitor gets a card -> that card's link converts rather than bounces.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.app = _founder('sf_ep')

    def _publish_elevator_pitch(self):
        return ProfileVideo.objects.create(
            founder=self.app,
            kind=ProfileVideo.KIND_ELEVATOR_PITCH,
            status=ProfileVideo.STATUS_PUBLISHED,
            caption='Thirty seconds on community solar.',
            video=SimpleUploadedFile('pitch.mp4', b'\x00\x00\x00\x18ftypmp42', content_type='video/mp4'),
        )

    def test_explore_is_empty_before_anyone_posts(self):
        self.assertEqual(ProfileVideo.objects.visible_elevator_pitches().count(), 0)
        response = self.client.get(reverse('explore'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['cards']), [])

    def test_a_published_pitch_reaches_an_anonymous_visitor(self):
        self._publish_elevator_pitch()

        self.assertEqual(ProfileVideo.objects.visible_elevator_pitches().count(), 1)
        response = self.client.get(reverse('explore'))
        self.assertEqual(response.status_code, 200)
        cards = response.context['cards']
        self.assertEqual(len(cards), 1, 'the whole point of Explore is that this needs no account')
        self.assertEqual(cards[0]['company_name'], 'sf_epCo')

    def test_that_card_converts_rather_than_bounces(self):
        self._publish_elevator_pitch()
        card = self.client.get(reverse('explore')).context['cards'][0]
        self.assertIn(reverse('accounts:signup'), card['profile_url'])
        self.assertIn('sf_ep', card['profile_url'])

    def test_quarantined_pitches_do_not_reach_explore(self):
        video = self._publish_elevator_pitch()
        video.status = ProfileVideo.STATUS_QUARANTINED
        video.save(update_fields=['status'])
        self.assertEqual(len(self.client.get(reverse('explore')).context['cards']), 0)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ChecklistNamesTheRightVideoTests(TestCase):
    """
    Fix 3 and 4: the checklist has to mean the thing it says.

    "Upload a pitch deck or pitch video" was satisfied by
    Application.pitch_video, so a founder could tick it and remain absent
    from Explore. The two concepts are separate in the model docstring
    already; the checklist now separates them too.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.app = _founder('sf_cl', pitch_deck=SimpleUploadedFile(
            'deck.pdf', b'%PDF-1.4', content_type='application/pdf'))

    def _labels(self):
        from .utils import compute_founder_journey_stage
        return {item['label']: item['done']
                for item in compute_founder_journey_stage(self.app.user)['checklist']}

    def test_the_explore_step_exists_and_is_separate(self):
        labels = self._labels()
        self.assertIn('Post a 30-second elevator pitch to Explore', labels)
        self.assertIn('Upload a pitch deck or a 1–3 min pitch video', labels)

    def test_a_pitch_video_does_not_tick_the_explore_step(self):
        # The exact false promise the audit found: a founder uploads a
        # profile pitch video, the old single item goes green, and Explore
        # stays empty.
        self.app.pitch_video = SimpleUploadedFile(
            'clip.mp4', b'\x00\x00\x00\x18ftypmp42', content_type='video/mp4')
        self.app.save(update_fields=['pitch_video'])
        self.assertFalse(self._labels()['Post a 30-second elevator pitch to Explore'])

    def test_a_published_elevator_pitch_ticks_it(self):
        ProfileVideo.objects.create(
            founder=self.app, kind=ProfileVideo.KIND_ELEVATOR_PITCH,
            status=ProfileVideo.STATUS_PUBLISHED,
            video=SimpleUploadedFile('p.mp4', b'\x00\x00\x00\x18ftypmp42', content_type='video/mp4'),
        )
        self.assertTrue(self._labels()['Post a 30-second elevator pitch to Explore'])

    def test_an_unpublished_pitch_does_not_tick_it(self):
        ProfileVideo.objects.create(
            founder=self.app, kind=ProfileVideo.KIND_ELEVATOR_PITCH,
            status=ProfileVideo.STATUS_QUARANTINED,
            video=SimpleUploadedFile('p.mp4', b'\x00\x00\x00\x18ftypmp42', content_type='video/mp4'),
        )
        self.assertFalse(self._labels()['Post a 30-second elevator pitch to Explore'])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ElevatorPitchIsAYellowStageAskTests(TestCase):
    """
    The supply loop, from the point a founder is first asked.

    Explore was empty because nothing invited anyone to post. The elevator
    pitch existed only in the GREEN checklist, which requires a deck or a
    1-3 min video first -- so a founder had to produce the heavy
    fundraising asset before being asked for the light public one. Every
    seeded founder sat in yellow and was never asked at all.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.app = _founder('yp_founder')
        self.client.force_login(self.app.user)

    def _status(self):
        return self.client.get('/api/v1/zelda/journey-status/').json()

    def _publish(self):
        return ProfileVideo.objects.create(
            founder=self.app, kind=ProfileVideo.KIND_ELEVATOR_PITCH,
            status=ProfileVideo.STATUS_PUBLISHED,
            video=SimpleUploadedFile('p.mp4', b'0' * 32, content_type='video/mp4'),
        )

    def test_a_yellow_founder_is_asked_before_having_any_pitch_asset(self):
        data = self._status()
        self.assertEqual(data['stage_color'], 'yellow')
        self.assertEqual(data['next_best_action']['label'],
                         'Post a 30-second elevator pitch to Explore')
        self.assertEqual(data['next_best_action']['action_url'],
                         reverse('matchmaking:manage_elevator_pitch'))

    def test_the_ask_does_not_change_when_the_stage_flips(self):
        # has_pitch_asset still owns the stage. Publishing an elevator
        # pitch must not promote anyone to green.
        self._publish()
        self.assertEqual(self._status()['stage_color'], 'yellow')

    def test_a_deck_still_promotes_to_green(self):
        self.app.pitch_deck = SimpleUploadedFile('d.pdf', b'%PDF-1.4', content_type='application/pdf')
        self.app.save(update_fields=['pitch_deck'])
        self.assertEqual(self._status()['stage_color'], 'green')

    def test_strength_is_the_journey_ratio_and_the_new_step_can_raise_it(self):
        # The denominator grew, so a profile-only founder reads 1/3 rather
        # than 1/2. The label does not regress, and the new step is the
        # cheapest way to move the bar -- which yellow previously had no
        # way to do at all.
        before = self._status()['profile_strength']
        self.assertAlmostEqual(before['ratio'], 1 / 3)
        self.assertEqual(before['label'], 'Building')

        self._publish()
        after = self._status()['profile_strength']
        self.assertAlmostEqual(after['ratio'], 2 / 3)
        self.assertEqual(after['label'], 'Good')
        self.assertGreater(after['ratio'], before['ratio'])

    def test_publishing_makes_the_founder_visible_to_a_stranger(self):
        # The whole point: the ask exists so Explore has supply.
        self.assertEqual(len(self.client.get(reverse('explore')).context['cards']), 0)
        self._publish()

        anon = self.client_class()
        cards = anon.get(reverse('explore')).context['cards']
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['company_name'], 'yp_founderCo')
        self.assertIn(reverse('accounts:signup'), cards[0]['profile_url'])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SellerElevatorPitchAskTests(TestCase):
    """Same ask on the seller side, where the CIM is even heavier."""

    def setUp(self):
        _mock_embedding_generation(self)
        user = User.objects.create_user('yp_seller', password='x')
        self.seller = SellerApplication.objects.create(
            user=user, company_name='YPSell', seller_name='S', email='s@t.com',
            description='A regional services business.', industry='Facilities Services')
        self.client.force_login(user)

    def test_a_yellow_seller_is_asked_before_the_cim(self):
        from .utils import compute_seller_journey_stage
        stage = compute_seller_journey_stage(self.seller.user)
        self.assertEqual(stage['stage_color'], 'yellow')
        self.assertEqual([i['label'] for i in stage['checklist']], [
            'Create your business listing',
            'Post a 30-second elevator pitch to Explore',
            'Upload a CIM document',
        ])

    def test_a_seller_pitch_reaches_explore(self):
        ProfileVideo.objects.create(
            seller=self.seller, kind=ProfileVideo.KIND_ELEVATOR_PITCH,
            status=ProfileVideo.STATUS_PUBLISHED,
            video=SimpleUploadedFile('s.mp4', b'0' * 32, content_type='video/mp4'),
        )
        cards = self.client_class().get(reverse('explore')).context['cards']
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['role_label'], 'Business for sale')

    def test_the_cim_still_owns_the_stage(self):
        from .utils import compute_seller_journey_stage
        ProfileVideo.objects.create(
            seller=self.seller, kind=ProfileVideo.KIND_ELEVATOR_PITCH,
            status=ProfileVideo.STATUS_PUBLISHED,
            video=SimpleUploadedFile('s2.mp4', b'0' * 32, content_type='video/mp4'),
        )
        self.assertEqual(compute_seller_journey_stage(self.seller.user)['stage_color'], 'yellow')
