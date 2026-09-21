"""
The one-time notice that per-field visibility defaults were applied.

Per-field visibility shipped with defaults rather than a blank slate, so a
founder's raise amount, revenue, prior funding, use of funds and name moved
from "any signed-in account" to "investors you have accepted". Nobody is newly
exposed by a tightening -- the reason to send anything is that a founder who
never opens the settings page will simply find their profile quieter across
Explore, search, the directory and the weekly digest, with no way to connect
that to a change we made.

A management command rather than a migration or a signal: migrations run in
tests and on every developer's machine, so sending from one would mean a test
suite that notifies real people.
"""
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from notifications.models import Notification

from .management.commands.notify_profile_visibility import MESSAGE, NOTIFICATION_TYPE
from .models import Application
from .tests import _mock_embedding_generation


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class NotifyProfileVisibilityTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.migrated_user = User.objects.create_user('npv_migrated', password='x')
        self.migrated = Application.objects.create(
            user=self.migrated_user, company_name='Migrated Co', founder_name='M',
            email='m@t.com', description='d', sector='SaaS', stage='Seed',
        )
        # Stamped as the backfill would have.
        Application.objects.filter(pk=self.migrated.pk).update(
            field_visibility_defaults_applied_at=timezone.now()
        )

        # Created after the feature shipped: chose its own settings, never
        # surprised by them, so telling it "your defaults changed" would be
        # false rather than merely redundant.
        self.new_user = User.objects.create_user('npv_new', password='x')
        self.new = Application.objects.create(
            user=self.new_user, company_name='New Co', founder_name='N',
            email='n@t.com', description='d', sector='SaaS', stage='Seed',
        )

    def run_command(self, *args):
        out = StringIO()
        call_command('notify_profile_visibility', *args, stdout=out)
        return out.getvalue()

    def notices(self, user=None):
        qs = Notification.objects.filter(notification_type=NOTIFICATION_TYPE)
        return qs.filter(recipient=user) if user else qs

    def test_the_message_fits_the_column(self):
        """
        Notification.message is CharField(max_length=255).

        SQLite does not enforce max_length and Postgres does, so an overlong
        message would pass every local run and every CI run -- both SQLite --
        and then raise on production. This project has never run its suite
        against Postgres, so the assertion has to live here.
        """
        self.assertLessEqual(len(MESSAGE), 255)

    def test_it_notifies_a_founder_the_backfill_touched(self):
        self.run_command()
        self.assertEqual(self.notices(self.migrated_user).count(), 1)

    def test_it_skips_a_profile_created_after_the_change(self):
        self.run_command()
        self.assertEqual(self.notices(self.new_user).count(), 0)

    def test_running_it_twice_does_not_notify_twice(self):
        self.run_command()
        self.run_command()
        self.assertEqual(self.notices(self.migrated_user).count(), 1)

    def test_idempotency_survives_a_wording_change(self):
        """
        Keyed on the type constant, never on the message text.

        A founder notified under earlier wording must not be notified again
        when the text is revised -- otherwise editing a sentence would re-send
        to everyone who already read it.
        """
        Notification.objects.create(
            recipient=self.migrated_user, notification_type=NOTIFICATION_TYPE,
            message='wording from an earlier release',
        )
        self.run_command()
        self.assertEqual(self.notices(self.migrated_user).count(), 1)
        self.assertEqual(
            self.notices(self.migrated_user).get().message,
            'wording from an earlier release',
            'the existing notice was replaced rather than left alone',
        )

    def test_dry_run_creates_nothing(self):
        output = self.run_command('--dry-run')
        self.assertIn('npv_migrated', output)
        self.assertEqual(self.notices().count(), 0)

    def test_the_notice_links_to_the_page_that_fixes_it(self):
        self.run_command()
        notice = self.notices(self.migrated_user).get()
        self.assertEqual(notice.target_url, reverse('usersettings:edit_founder_profile'))

    def test_it_comes_from_the_platform_not_a_person(self):
        self.run_command()
        self.assertIsNone(self.notices(self.migrated_user).get().sender)

    def test_the_message_says_what_changed_and_where_to_act(self):
        self.run_command()
        message = self.notices(self.migrated_user).get().message
        self.assertIn('raise amount', message)
        self.assertIn('accepted', message)
        self.assertIn('profile settings', message)
