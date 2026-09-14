"""
Impersonation is read-only (PR #57).

While staff are viewing as a user (session['impersonator_id']), nothing may be
changed or recorded as that user:

- every POST/PUT/PATCH/DELETE is refused except stop-impersonation and logout;
  a form post goes back where it came from with a message, JSON and API
  requests get 403
- GETs that grant access or write -- the Stream chat token, opening a direct
  chat -- are refused too
- ordinary pages still load, but they record no interest events, profile
  views, dashboard or search analytics, and don't mark notifications read
- starting impersonation leaves the user's last_login alone

Each refused action is shown to have had no effect, and a control proves the
same action works, or is recorded, when the user does it themselves.
"""
import json
from datetime import timedelta
from unittest import mock

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from blog.models import Article
from matchmaking.models import (
    Application, Connection, Follow, InvestorApplication, InvestorInterestEvent,
    PageEvent, ProfileView, SearchEvent,
)
from matchmaking.tests import _mock_embedding_generation
from notifications.models import Notification
from ops.models import UserReport
from zelda_api.models import AnalysisCreditCharge

User = get_user_model()
SETTINGS_PAGE = 'http://testserver/settings/'


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class _Impersonating(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.staff = User.objects.create_user('ro_staff', password='x', is_staff=True)
        self.target = User.objects.create_user('ro_target', password='old-password')
        self.target_founder = Application.objects.create(
            user=self.target, company_name='Target Co', founder_name='T', email='t@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.target_investor = InvestorApplication.objects.create(
            user=self.target, full_name='T', email='t@t.com', company_name='Target Capital',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.other_founder_user = User.objects.create_user('ro_other_founder', password='x')
        self.other_founder = Application.objects.create(
            user=self.other_founder_user, company_name='Northwind Grid', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.other_investor_user = User.objects.create_user('ro_other_investor', password='x')
        self.other_investor = InvestorApplication.objects.create(
            user=self.other_investor_user, full_name='I', email='i@t.com', company_name='Harbor Capital',
            investment_focus='SaaS', investment_stage='Seed',
        )

    def _impersonate(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('ops:start_impersonation', args=[self.target.id]))
        # Positive control: the session really is viewing as the target.
        self.assertEqual(self.client.session['_auth_user_id'], str(self.target.id))
        self.assertEqual(self.client.session['impersonator_id'], self.staff.id)

    def _refused_form_post(self, url, data=None):
        response = self.client.post(url, data or {}, HTTP_REFERER=SETTINGS_PAGE)
        self.assertEqual(response.status_code, 302, url)
        self.assertEqual(response['Location'], SETTINGS_PAGE, url)
        return response

    def _refused_json_post(self, url, payload=None):
        response = self.client.post(url, data=json.dumps(payload or {}), content_type='application/json')
        self.assertEqual(response.status_code, 403, url)
        return response


class WritesAreRefusedTests(_Impersonating):

    def test_a_refused_form_post_goes_back_with_a_read_only_message(self):
        self._impersonate()
        response = self.client.post(
            reverse('usersettings:update_username'), {'username': 'renamed'}, HTTP_REFERER=SETTINGS_PAGE, follow=True)
        shown = ' '.join(str(m) for m in response.context['messages'])
        self.assertIn('read-only', shown.lower())
        self.assertIn(self.target.username, shown)

    def test_an_api_write_gets_403_json_and_never_reaches_the_view(self):
        self._impersonate()
        deck = SimpleUploadedFile('deck.pdf', b'%PDF-1.4 deck', content_type='application/pdf')
        with mock.patch('zelda_api.views.scan_pitch_deck', return_value={'error': 'unreadable'}) as scan:
            response = self.client.post(reverse('zelda_api:pitch_analysis'), {'pitch_deck': deck})
        self.assertEqual(response.status_code, 403)
        self.assertIn('read-only', response.json()['error'].lower())
        scan.assert_not_called()

    def test_identity_and_credentials(self):
        self._impersonate()
        self._refused_form_post(reverse('usersettings:update_username'), {'username': 'renamed'})
        self._refused_form_post(
            reverse('usersettings:delete_account'), {'confirm_username': 'ro_target', 'password': 'old-password'})
        self._refused_form_post(reverse('password_change'), {
            'old_password': 'old-password', 'new_password1': 'N3w-pass-word!', 'new_password2': 'N3w-pass-word!'})
        self._refused_form_post(reverse('account_email'), {'action_add': '', 'email': 'someone-else@example.com'})

        self.target.refresh_from_db()
        self.assertEqual(self.target.username, 'ro_target')
        self.assertTrue(self.target.check_password('old-password'))
        self.assertFalse(EmailAddress.objects.filter(email='someone-else@example.com').exists())

    def test_money_and_credits(self):
        self._impersonate()
        with mock.patch('stripe.checkout.Session.create') as checkout:
            self._refused_form_post(reverse('billing:create_checkout_session'))
        self._refused_form_post(reverse('matchmaking:activate_founder_highlight'))
        self._refused_json_post(reverse('zelda_api:analyze_founder_confirm', args=[self.other_founder_user.username]))

        checkout.assert_not_called()
        self.target_founder.refresh_from_db()
        self.assertIsNone(self.target_founder.last_highlight_at)
        self.assertFalse(AnalysisCreditCharge.objects.exists())

    def test_acting_toward_other_people(self):
        pending = Connection.objects.create(
            founder=self.target_founder, investor=self.other_investor, status='PENDING', initiated_by='INVESTOR')
        self._impersonate()
        self._refused_form_post(reverse('matchmaking:request_intro_from_founder', args=[self.other_investor.id]))
        self._refused_json_post(reverse('matchmaking:connection_action'), {'id': pending.id, 'action': 'ACCEPTED'})
        self._refused_form_post(reverse('matchmaking:toggle_follow', args=[self.other_founder_user.username]))
        self._refused_form_post(
            reverse('ops:submit_user_report', args=[self.other_founder_user.username]), {'reason': 'spam'})
        self._refused_form_post(reverse('blog:blog_view'), {'company_name': 'Co', 'title': 'Posted as you', 'body': 'x'})

        pending.refresh_from_db()
        self.assertEqual(pending.status, 'PENDING')
        self.assertEqual(Connection.objects.count(), 1)
        self.assertFalse(Follow.objects.exists())
        self.assertFalse(UserReport.objects.exists())
        self.assertFalse(Article.objects.exists())

    def test_privacy_visibility_and_profile_data(self):
        notification = Notification.objects.create(recipient=self.target, message='keep me')
        self._impersonate()
        self._refused_json_post(reverse('accounts:toggle_privacy'), {'is_private': True})
        self._refused_form_post(reverse('usersettings:archive_profile'))
        self._refused_form_post(reverse('usersettings:edit_founder_profile'), {'company_name': 'Renamed Co'})
        self._refused_json_post(reverse('api-delete', args=[notification.id]))

        self.target_founder.refresh_from_db()
        self.target_investor.refresh_from_db()
        self.assertFalse(self.target_founder.is_private)
        self.assertIsNone(self.target_founder.archived_at)
        self.assertIsNone(self.target_investor.archived_at)
        self.assertEqual(self.target_founder.company_name, 'Target Co')
        self.assertTrue(Notification.objects.filter(pk=notification.pk).exists())

    def test_control_the_user_themselves_can_make_the_same_changes(self):
        self.client.force_login(self.target)
        self.client.post(
            reverse('accounts:toggle_privacy'), data=json.dumps({'is_private': True}), content_type='application/json')
        self.client.post(reverse('usersettings:archive_profile'))

        self.target_founder.refresh_from_db()
        self.target_investor.refresh_from_db()
        self.assertTrue(self.target_founder.is_private)
        self.assertTrue(self.target_founder.archived_at or self.target_investor.archived_at)


class StillAllowedTests(_Impersonating):

    def test_pages_still_load(self):
        self._impersonate()
        self.assertEqual(self.client.get(reverse('usersettings:home')).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('accounts:profile', args=[self.other_founder_user.username])).status_code, 200)

    def test_stop_impersonation_still_works(self):
        self._impersonate()
        self.client.post(reverse('ops:stop_impersonation'))
        self.assertEqual(self.client.session['_auth_user_id'], str(self.staff.id))
        self.assertNotIn('impersonator_id', self.client.session)

    def test_logout_still_works(self):
        self._impersonate()
        self.client.post(reverse('accounts:logout'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_starting_impersonation_leaves_the_users_last_login_alone(self):
        a_month_ago = timezone.now() - timedelta(days=30)
        User.objects.filter(pk=self.target.pk).update(last_login=a_month_ago)
        self._impersonate()
        self.target.refresh_from_db()
        self.assertEqual(self.target.last_login, a_month_ago)


@override_settings(STREAM_API_KEY='stream-key', STREAM_API_SECRET='stream-secret')
class GetsRecordAndGrantNothingTests(_Impersonating):

    def test_no_chat_token_and_no_direct_chat(self):
        self._impersonate()
        with mock.patch('accounts.views.StreamChat') as accounts_stream, \
                mock.patch('matchmaking.views.StreamChat') as matchmaking_stream:
            responses = [
                self.client.get(reverse('accounts:stream_token')),
                self.client.get(reverse('matchmaking:stream_token')),
                self.client.get(reverse('matchmaking:initiate_direct_chat', args=[self.other_founder_user.id])),
            ]
        for response in responses:
            self.assertIn(response.status_code, (302, 403))
            self.assertNotIn(b'token', response.content)
        accounts_stream.assert_not_called()
        matchmaking_stream.assert_not_called()

    def test_control_the_user_gets_a_chat_token(self):
        self.client.force_login(self.target)
        with mock.patch('matchmaking.views.StreamChat') as stream:
            stream.return_value.create_token.return_value = 'user-token'
            response = self.client.get(reverse('matchmaking:stream_token'))
        self.assertEqual(response.json()['token'], 'user-token')

    def test_viewing_a_profile_records_nothing_as_the_user(self):
        self._impersonate()
        self.client.get(reverse('accounts:profile', args=[self.other_founder_user.username]))
        self.assertFalse(InvestorInterestEvent.objects.filter(investor=self.target).exists())
        self.assertFalse(ProfileView.objects.filter(viewer=self.target).exists())

    def test_control_the_user_viewing_a_profile_is_recorded(self):
        self.client.force_login(self.target)
        self.client.get(reverse('accounts:profile', args=[self.other_founder_user.username]))
        self.assertTrue(InvestorInterestEvent.objects.filter(investor=self.target, event_type='view').exists())
        self.assertTrue(ProfileView.objects.filter(viewer=self.target).exists())

    def _dashboard_search_and_analyze(self):
        self.client.get(reverse('matchmaking:founder_dashboard'))
        self.client.get(reverse('matchmaking:global_search'), {'industry': 'SaaS'})
        self.client.get(reverse('zelda_api:analyze_founder', args=[self.other_founder_user.username]))

    def test_dashboard_search_and_analyze_record_nothing_as_the_user(self):
        self._impersonate()
        self._dashboard_search_and_analyze()
        self.assertFalse(PageEvent.objects.filter(user=self.target).exists())
        self.assertFalse(SearchEvent.objects.filter(user=self.target).exists())
        self.assertFalse(InvestorInterestEvent.objects.filter(investor=self.target).exists())

    def test_control_the_user_doing_the_same_is_recorded(self):
        self.client.force_login(self.target)
        self._dashboard_search_and_analyze()
        self.assertTrue(PageEvent.objects.filter(user=self.target, event_type='dashboard_view').exists())
        self.assertTrue(SearchEvent.objects.filter(user=self.target).exists())
        self.assertTrue(InvestorInterestEvent.objects.filter(investor=self.target, event_type='analyze').exists())

    def test_opening_notifications_does_not_mark_them_read(self):
        unread = Notification.objects.create(recipient=self.target, message='for the user')
        self._impersonate()
        response = self.client.get(reverse('api-list'))
        self.assertEqual([n['id'] for n in response.json()], [unread.id])
        unread.refresh_from_db()
        self.assertFalse(unread.is_read)

    def test_control_the_user_opening_notifications_marks_them_read(self):
        unread = Notification.objects.create(recipient=self.target, message='for the user')
        self.client.force_login(self.target)
        self.client.get(reverse('api-list'))
        unread.refresh_from_db()
        self.assertTrue(unread.is_read)
