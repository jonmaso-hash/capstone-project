"""
Staff sign-in goes through the rate-limited login, and staff sessions expire.

The 5-per-username / 30-per-IP lockout lives in accounts.views.login_view.
Django's admin ships its own login form at <admin path>login/, which that
lockout never touched -- so the one staff account (the superuser) could be
guessed at without limit by anyone who found the admin path. The old
db.sqlite3 in this repo's public git history carries that account's password
hash, which makes an offline crack plus unlimited online attempts a real path
in, not a theoretical one.

Now the admin login form is not served at all: the URL redirects to the
rate-limited login, carrying `next` so the visitor still lands in the admin.
Staff sessions also expire after an idle period, since staff can impersonate
users and override deal states.

Staff 2FA stays a post-launch item: with the guessing path closed and the
superuser password rotated, it is defence in depth rather than the control
holding the boundary.
"""
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import RateLimitEvent

User = get_user_model()

PASSWORD = 'StaffLockout!2026xyz'
FAST_HASHER = ['django.contrib.auth.hashers.MD5PasswordHasher']
ADMIN = '/' + settings.ADMIN_URL_PATH


@override_settings(PASSWORD_HASHERS=FAST_HASHER)
class AdminLoginGoesThroughTheLockoutTests(TestCase):

    def setUp(self):
        self.staff = User.objects.create_user(
            'al_staff', email='al_staff@example.com', password=PASSWORD,
            is_staff=True, is_superuser=True,
        )

    def test_the_admin_login_form_is_not_served(self):
        response = self.client.get(ADMIN + 'login/')
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_it_keeps_where_the_visitor_was_going(self):
        response = self.client.get(ADMIN + 'login/?next=' + ADMIN)
        query = parse_qs(urlparse(response.url).query)
        self.assertEqual(query.get('next'), [ADMIN])

    def test_reaching_the_admin_anonymously_ends_at_the_rate_limited_login(self):
        response = self.client.get(ADMIN, follow=True)
        self.assertEqual(response.status_code, 200)
        # The site's own login page, which is the one that counts attempts.
        self.assertTemplateUsed(response, 'accounts/login.html')

    def test_guessing_a_staff_password_is_limited_like_any_other(self):
        for _ in range(5):
            self.client.post(reverse('accounts:login'), {'username': 'al_staff', 'password': 'wrong'})
        refused = self.client.post(
            reverse('accounts:login'), {'username': 'al_staff', 'password': PASSWORD},
        )
        self.assertEqual(refused.status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(RateLimitEvent.objects.filter(scope='login_username').exists())

    def test_staff_can_still_sign_in_and_reach_the_admin(self):
        response = self.client.post(
            reverse('accounts:login'),
            {'username': 'al_staff', 'password': PASSWORD, 'next': ADMIN},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, ADMIN)
        self.assertEqual(self.client.get(ADMIN).status_code, 200)


    def test_a_member_cannot_reach_the_admin_through_it(self):
        member = User.objects.create_user('al_member', password=PASSWORD)
        self.client.force_login(member)
        # A signed-in non-staff visitor is turned away, not bounced to a login
        # they have already passed -- that would redirect in a circle.
        response = self.client.get(ADMIN, follow=True)
        self.assertNotContains(response, 'Site administration')
        self.assertContains(response, 'restricted to staff')
        # And the redirect route itself grants nothing.
        self.assertRedirects(self.client.get(ADMIN + 'login/'), reverse('pages:home'))

    def test_the_admin_still_works_once_signed_in(self):
        self.client.post(
            reverse('accounts:login'),
            {'username': 'al_staff', 'password': PASSWORD, 'next': ADMIN},
        )
        index = self.client.get(ADMIN)
        self.assertContains(index, 'Site administration')
        # A real changelist, not just the index page.
        changelist = self.client.get(reverse('admin:matchmaking_application_changelist'))
        self.assertEqual(changelist.status_code, 200)


@override_settings(PASSWORD_HASHERS=FAST_HASHER, STAFF_SESSION_IDLE_TIMEOUT=3600)
class StaffSessionIdleTimeoutTests(TestCase):

    def setUp(self):
        self.staff = User.objects.create_user('st_staff', password=PASSWORD, is_staff=True)
        self.member = User.objects.create_user('st_member', password=PASSWORD)

    def _idle(self, minutes):
        """Move this session's last-seen stamp into the past."""
        session = self.client.session
        session['staff_last_seen'] = (timezone.now() - timedelta(minutes=minutes)).isoformat()
        session.save()

    def test_an_idle_staff_session_is_signed_out(self):
        self.client.force_login(self.staff)
        self._idle(61)
        response = self.client.get(reverse('ops:dashboard'), follow=True)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTemplateUsed(response, 'accounts/login.html')

    def test_an_active_staff_session_continues(self):
        self.client.force_login(self.staff)
        self._idle(5)
        self.client.get(reverse('pages:home'))
        self.assertEqual(str(self.staff.id), self.client.session.get('_auth_user_id'))

    def test_a_members_session_is_left_alone(self):
        self.client.force_login(self.member)
        self._idle(600)
        self.client.get(reverse('pages:home'))
        self.assertEqual(str(self.member.id), self.client.session.get('_auth_user_id'))

    def test_staff_activity_resets_the_timer(self):
        self.client.force_login(self.staff)
        self._idle(59)
        # A request just inside the hour refreshes the stamp...
        self.client.get(reverse('pages:home'))
        refreshed = self.client.session['staff_last_seen']
        self.assertGreater(
            timezone.datetime.fromisoformat(refreshed),
            timezone.now() - timedelta(minutes=1),
        )
        # ...so another 59 idle minutes still doesn't reach the timeout.
        self._idle(59)
        self.client.get(reverse('pages:home'))
        self.assertEqual(str(self.staff.id), self.client.session.get('_auth_user_id'))

    @override_settings(STAFF_SESSION_IDLE_TIMEOUT=60)
    def test_the_timeout_is_configurable_and_still_spares_members(self):
        self.client.force_login(self.staff)
        self._idle(2)  # two minutes, past a 60-second timeout
        self.client.get(reverse('pages:home'))
        self.assertNotIn('_auth_user_id', self.client.session)

        member_client = self.client_class()
        member_client.force_login(self.member)
        session = member_client.session
        session['staff_last_seen'] = (timezone.now() - timedelta(days=3)).isoformat()
        session.save()
        member_client.get(reverse('pages:home'))
        self.assertEqual(str(self.member.id), member_client.session.get('_auth_user_id'))
