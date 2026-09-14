"""
Account deletion -- accounts/deletion.py.

Before this, Settings could only delete a role profile, Django admin deleted
users without touching Stripe or Stream Chat, deleting a premium profile left
its Stripe subscription charging, deleting a firm owner silently removed every
member's seat, and abuse reports and impersonation logs vanished along with
the user they were about.

The contract these tests pin (agreed 2026-09-14) is a two-phase boundary:

  before the database commit   every check and the Stripe cancellation run
                               first; any failure aborts, and the account is
                               left exactly as it was
  after the database commit    stored files and the Stream Chat identity are
                               removed; a failure there is logged as retryable
                               work and never restores any part of the account
"""
import tempfile
from unittest import mock

import stripe
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, models
from django.db.models.signals import post_delete
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from billing.models import Subscription
from matchmaking.models import (
    Application, Connection, DataRoomDocument, Firm, FirmMembership, InvestorApplication, ProfileVideo,
)
from matchmaking.tests import _mock_embedding_generation
from notifications.models import Notification
from ops.models import FailedTaskLog, ImpersonationLog, UserReport
from usersettings.models import UserSettings

User = get_user_model()

PASSWORD = 'CorrectHorse!2026'


def _deletion():
    from accounts import deletion
    return deletion


def _stored(*field_files):
    return [(f.storage, f.name) for f in field_files]


def _snapshot(user):
    """Everything the account owns or is referenced by, for before/after comparison."""
    state = {'user': User.objects.filter(id=user.id, is_active=True).count()}
    for rel in User._meta.related_objects:
        if getattr(rel, 'on_delete', None) is not None:
            label = f'{rel.related_model._meta.label}.{rel.field.name}'
            state[label] = rel.related_model._base_manager.filter(**{rel.field.name: user.id}).count()
    state['data_room_documents'] = DataRoomDocument.objects.filter(founder__user=user).count()
    state['profile_videos'] = ProfileVideo.objects.filter(founder__user=user).count()
    state['connections'] = Connection.objects.filter(founder__user=user).count()
    state['subscriptions'] = sorted(Subscription.objects.filter(user=user).values_list('stripe_subscription_id', 'status'))
    return state


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(),
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    STREAM_API_KEY='test-key', STREAM_API_SECRET='test-secret',
    DEFAULT_FROM_EMAIL='hello@interlinkfoundry.com',
)
class DeletionTestCase(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.stripe_cancel = self._patch('stripe.Subscription.cancel')
        # Patched at the SDK so these run before and after accounts/deletion.py exists.
        self.stream = self._patch('stream_chat.StreamChat')

    def _patch(self, target, **kwargs):
        patcher = mock.patch(target, **kwargs)
        started = patcher.start()
        self.addCleanup(patcher.stop)
        return started

    def _founder(self, username='del_founder', email='founder@example.test'):
        user = User.objects.create_user(username, email=email, password=PASSWORD)
        app = Application.objects.create(
            user=user, company_name=f'{username} Co', founder_name='F', email=email or 'none@example.test',
            description='d', sector='SaaS', stage='Seed',
            pitch_deck=SimpleUploadedFile('deck.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        return user, app

    def _investor(self, username='del_investor'):
        user = User.objects.create_user(username, email=f'{username}@example.test', password=PASSWORD)
        investor = InvestorApplication.objects.create(
            user=user, full_name='I', company_name=f'{username} Fund', email=f'{username}@example.test',
            investment_focus='SaaS', investment_stage='Seed',
        )
        return user, investor

    def _populated_founder(self):
        user, app = self._founder()
        DataRoomDocument.objects.create(
            founder=app, label='Cap table', category='CAP_TABLE',
            file=SimpleUploadedFile('cap.csv', b'a,b', content_type='text/csv'),
        )
        ProfileVideo.objects.create(founder=app, video=SimpleUploadedFile('pitch.mp4', b'mp4', content_type='video/mp4'))
        user_settings = UserSettings.for_user(user)
        user_settings.profile_picture = SimpleUploadedFile('me.png', b'png', content_type='image/png')
        user_settings.save()
        Notification.objects.create(recipient=user, notification_type='SYSTEM', message='Welcome.')
        return user, app

    def _files_of(self, user, app):
        return _stored(
            app.pitch_deck,
            DataRoomDocument.objects.get(founder=app).file,
            ProfileVideo.objects.get(founder=app).video,
            UserSettings.objects.get(user=user).profile_picture,
        )

    def _subscription(self, user, sub_id='sub_active', status=Subscription.Status.ACTIVE,
                      plan=Subscription.Plan.FOUNDER_PREMIUM):
        return Subscription.objects.create(
            user=user, plan=plan, stripe_customer_id='cus_test', stripe_subscription_id=sub_id, status=status,
        )

    def _firm(self, owner, *members):
        firm = Firm.objects.create(name='Fund', verified_domain=f'{owner.username}.test', owner=owner)
        FirmMembership.objects.create(firm=firm, user=owner)
        for member in members:
            FirmMembership.objects.create(firm=firm, user=member)
        return firm


class DeletingAnAccountTests(DeletionTestCase):

    def test_the_user_and_everything_that_cascades_from_them_is_gone(self):
        user, app = self._populated_founder()
        investor_user, investor = self._investor()
        Connection.objects.create(investor=investor, founder=app, status='ACCEPTED')
        user_id = user.id

        with self.captureOnCommitCallbacks(execute=True):
            _deletion().delete_account(user)

        self.assertFalse(User.objects.filter(id=user_id).exists())
        for rel in User._meta.related_objects:
            if getattr(rel, 'on_delete', None) is models.CASCADE:
                with self.subTest(relation=f'{rel.related_model._meta.label}.{rel.field.name}'):
                    self.assertFalse(rel.related_model._base_manager.filter(**{rel.field.name: user_id}).exists())
        self.assertFalse(Connection.objects.filter(founder_id=app.id).exists())
        # The counterparty is untouched.
        self.assertTrue(User.objects.filter(id=investor_user.id).exists())
        self.assertTrue(InvestorApplication.objects.filter(id=investor.id).exists())

    def test_stored_files_are_removed_only_after_the_commit(self):
        user, app = self._populated_founder()
        files = self._files_of(user, app)

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            _deletion().delete_account(user)
        for storage, name in files:
            self.assertTrue(storage.exists(name), f'{name} was removed before the commit')

        for callback in callbacks:
            callback()
        for storage, name in files:
            self.assertFalse(storage.exists(name), f'{name} is still stored')

    def test_the_deleted_user_is_told_by_email(self):
        user, _ = self._founder()
        with self.captureOnCommitCallbacks(execute=True):
            _deletion().delete_account(user)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['founder@example.test'])
        self.assertIn('deleted', mail.outbox[0].subject.lower())

    def test_an_email_failure_does_not_affect_the_deletion(self):
        user, _ = self._founder()
        with mock.patch('django.core.mail.message.EmailMessage.send', side_effect=RuntimeError('mail down')):
            with self.captureOnCommitCallbacks(execute=True):
                _deletion().delete_account(user)
        self.assertFalse(User.objects.filter(id=user.id).exists())

    def test_an_account_without_an_email_is_still_deleted(self):
        user, _ = self._founder(username='del_no_email', email='')
        with self.captureOnCommitCallbacks(execute=True):
            _deletion().delete_account(user)
        self.assertFalse(User.objects.filter(id=user.id).exists())
        self.assertEqual(len(mail.outbox), 0)


class StripeBeforeTheCommitTests(DeletionTestCase):

    def test_open_subscriptions_are_cancelled_in_stripe_while_the_account_still_exists(self):
        user, _ = self._founder()
        self._subscription(user, 'sub_active', Subscription.Status.ACTIVE)
        self._subscription(user, 'sub_past_due', Subscription.Status.PAST_DUE)
        self._subscription(user, 'sub_incomplete', Subscription.Status.INCOMPLETE)
        self._subscription(user, 'sub_old', Subscription.Status.CANCELED)
        seen = []
        self.stripe_cancel.side_effect = lambda sub_id, *a, **kw: seen.append((sub_id, User.objects.filter(id=user.id).exists()))

        with self.captureOnCommitCallbacks(execute=True):
            _deletion().delete_account(user)

        self.assertCountEqual(seen, [('sub_active', True), ('sub_past_due', True), ('sub_incomplete', True)])
        self.assertFalse(User.objects.filter(id=user.id).exists())

    def test_a_stripe_failure_aborts_and_leaves_the_account_exactly_as_it_was(self):
        user, app = self._populated_founder()
        self._subscription(user)
        files = self._files_of(user, app)
        before = _snapshot(user)
        self.stripe_cancel.side_effect = stripe.error.APIConnectionError('Stripe is unreachable')

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(_deletion().DeletionBlocked):
                _deletion().delete_account(user)

        self.assertEqual(_snapshot(user), before)
        for storage, name in files:
            self.assertTrue(storage.exists(name))
        self.stream.assert_not_called()
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(FailedTaskLog.objects.exists())

    def test_a_subscription_stripe_no_longer_has_does_not_block_deletion(self):
        user, _ = self._founder()
        self._subscription(user)
        self.stripe_cancel.side_effect = stripe.error.InvalidRequestError(
            'No such subscription', param='id', code='resource_missing')
        with self.captureOnCommitCallbacks(execute=True):
            _deletion().delete_account(user)
        self.assertFalse(User.objects.filter(id=user.id).exists())


class FailureBeforeTheCommitTests(DeletionTestCase):

    def test_a_database_failure_midway_through_the_cascade_rolls_everything_back(self):
        user, app = self._populated_founder()
        files = self._files_of(user, app)
        before = _snapshot(user)

        def fail(**kwargs):
            raise DatabaseError('disk full')
        post_delete.connect(fail, sender=DataRoomDocument, weak=False, dispatch_uid='deletion-test-failure')
        self.addCleanup(post_delete.disconnect, sender=DataRoomDocument, dispatch_uid='deletion-test-failure')

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(_deletion().DeletionBlocked):
                _deletion().delete_account(user)

        self.assertEqual(_snapshot(user), before)
        for storage, name in files:
            self.assertTrue(storage.exists(name), f'{name} was removed though nothing was deleted')
        self.stream.assert_not_called()
        self.assertEqual(len(mail.outbox), 0)

    def test_a_firm_owner_with_other_members_is_blocked_before_anything_else_runs(self):
        owner, _ = self._investor('firm_owner')
        member, _ = self._investor('firm_member')
        self._firm(owner, member)
        self._subscription(owner, plan=Subscription.Plan.INVESTOR_FIRM)
        before = _snapshot(owner)

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(_deletion().DeletionBlocked):
                _deletion().delete_account(owner)

        self.assertEqual(_snapshot(owner), before)
        self.stripe_cancel.assert_not_called()
        self.assertTrue(FirmMembership.objects.filter(user=member).exists())


class FirmTests(DeletionTestCase):

    def test_a_sole_firm_owner_can_delete_and_the_firm_plan_is_cancelled(self):
        owner, _ = self._investor('solo_owner')
        self._firm(owner)
        self._subscription(owner, 'sub_firm', plan=Subscription.Plan.INVESTOR_FIRM)
        with self.captureOnCommitCallbacks(execute=True):
            _deletion().delete_account(owner)
        self.stripe_cancel.assert_called_once()
        self.assertEqual(self.stripe_cancel.call_args[0][0], 'sub_firm')
        self.assertFalse(Firm.objects.exists())

    def test_a_firm_member_can_delete_without_affecting_the_firm(self):
        owner, _ = self._investor('firm_owner')
        member, _ = self._investor('firm_member')
        firm = self._firm(owner, member)
        with self.captureOnCommitCallbacks(execute=True):
            _deletion().delete_account(member)
        self.assertTrue(Firm.objects.filter(id=firm.id).exists())
        self.assertTrue(FirmMembership.objects.filter(user=owner).exists())


class AfterTheCommitTests(DeletionTestCase):

    def test_the_stream_identity_and_messages_are_removed_but_not_conversations(self):
        user, _ = self._founder()
        user_id = str(user.id)

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            _deletion().delete_account(user)
        self.stream.assert_not_called()

        for callback in callbacks:
            callback()
        client = self.stream.return_value
        client.delete_users.assert_called_once()
        args, kwargs = client.delete_users.call_args
        self.assertEqual(list(kwargs.get('user_ids', args[0] if args else [])), [user_id])
        self.assertEqual(kwargs.get('delete_type', args[1] if len(args) > 1 else None), 'hard')
        self.assertEqual(kwargs.get('messages'), 'hard')
        self.assertNotIn('conversations', kwargs)
        client.delete_channels.assert_not_called()

    def test_a_stream_failure_is_logged_for_retry_and_the_account_stays_deleted(self):
        self.stream.return_value.delete_users.side_effect = RuntimeError('Stream unavailable')
        user, _ = self._founder()
        user_id = user.id

        with self.captureOnCommitCallbacks(execute=True):
            _deletion().delete_account(user)

        self.assertFalse(User.objects.filter(id=user_id).exists())
        log = FailedTaskLog.objects.get(task_name='accounts.tasks.delete_stream_user')
        self.assertEqual(log.args_json, [str(user_id)])
        for personal in ('del_founder', 'founder@example.test'):
            self.assertNotIn(personal, log.exception_message)

    def test_a_storage_failure_is_logged_for_retry_and_the_account_stays_deleted(self):
        user, app = self._founder()
        deck = app.pitch_deck.name
        with mock.patch('django.core.files.storage.FileSystemStorage.delete', side_effect=OSError('storage unavailable')):
            with self.captureOnCommitCallbacks(execute=True):
                _deletion().delete_account(user)
        self.assertFalse(User.objects.filter(id=user.id).exists())
        log = FailedTaskLog.objects.get(task_name='accounts.tasks.delete_stored_file')
        self.assertEqual(log.args_json, [deck])

    def test_the_stream_retry_task_removes_the_identity(self):
        from accounts.tasks import delete_stream_user
        delete_stream_user('42')
        args, kwargs = self.stream.return_value.delete_users.call_args
        self.assertEqual(list(kwargs.get('user_ids', args[0] if args else [])), ['42'])

    def test_the_file_retry_task_removes_the_file_and_can_run_twice(self):
        from accounts.tasks import delete_stored_file
        name = default_storage.save('data_room/leftover.csv', ContentFile(b'x'))
        delete_stored_file(name)
        delete_stored_file(name)
        self.assertFalse(default_storage.exists(name))


class SafetyRecordTests(DeletionTestCase):

    def test_a_report_against_a_deleted_user_survives_without_the_account(self):
        user, _ = self._founder()
        reporter, _ = self._investor()
        report = UserReport.objects.create(reporter=reporter, reported_user=user, reason='Spam messages.')
        with self.captureOnCommitCallbacks(execute=True):
            _deletion().delete_account(user)
        report.refresh_from_db()
        self.assertIsNone(report.reported_user)
        self.assertEqual(report.reported_username, 'del_founder')
        self.assertEqual(report.reason, 'Spam messages.')

    def test_a_report_filed_by_a_deleted_user_survives(self):
        user, _ = self._founder()
        reporter, _ = self._investor()
        report = UserReport.objects.create(reporter=reporter, reported_user=user, reason='Spam messages.')
        with self.captureOnCommitCallbacks(execute=True):
            _deletion().delete_account(reporter)
        report.refresh_from_db()
        self.assertIsNone(report.reporter)
        self.assertEqual(report.reported_user, user)

    def test_the_impersonation_log_survives_deletion_of_the_target(self):
        user, _ = self._founder()
        staff = User.objects.create_user('del_staff', password=PASSWORD, is_staff=True)
        log = ImpersonationLog.objects.create(impersonator=staff, target=user)
        with self.captureOnCommitCallbacks(execute=True):
            _deletion().delete_account(user)
        log.refresh_from_db()
        self.assertIsNone(log.target)
        self.assertEqual((log.impersonator_username, log.target_username), ('del_staff', 'del_founder'))


class RoleProfileDeletionTests(DeletionTestCase):

    def test_deleting_a_premium_profile_cancels_its_subscription_first(self):
        user, app = self._founder()
        self._subscription(user)
        seen = []
        self.stripe_cancel.side_effect = lambda sub_id, *a, **kw: seen.append((sub_id, Application.objects.filter(id=app.id).exists()))
        self.client.force_login(user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('usersettings:delete_profile_confirm'))
        self.assertEqual(seen, [('sub_active', True)])
        self.assertFalse(Application.objects.filter(id=app.id).exists())
        self.assertTrue(User.objects.filter(id=user.id).exists())

    def test_a_stripe_failure_keeps_the_profile(self):
        user, app = self._founder()
        self._subscription(user)
        self.stripe_cancel.side_effect = stripe.error.APIConnectionError('Stripe is unreachable')
        self.client.force_login(user)
        self.client.post(reverse('usersettings:delete_profile_confirm'))
        self.assertTrue(Application.objects.filter(id=app.id).exists())

    def test_a_firm_owner_with_members_cannot_delete_their_investor_profile(self):
        owner, investor = self._investor('firm_owner')
        member, _ = self._investor('firm_member')
        self._firm(owner, member)
        self.client.force_login(owner)
        self.client.post(reverse('usersettings:delete_profile_confirm'))
        self.assertTrue(InvestorApplication.objects.filter(id=investor.id).exists())
        self.stripe_cancel.assert_not_called()


class SelfServeDeletionViewTests(DeletionTestCase):

    def setUp(self):
        super().setUp()
        self.user, self.app = self._founder()
        self.url = reverse('usersettings:delete_account')

    def test_settings_offers_account_deletion(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('usersettings:home')), self.url)

    def test_the_confirmation_page_separates_the_four_outcomes(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        for heading in ('Permanently deleted', 'Kept without your identity', 'Your subscription', 'Finished shortly after'):
            self.assertContains(response, heading)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_the_wrong_username_is_refused(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {'confirm_username': 'someone_else', 'password': PASSWORD})
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_the_wrong_password_is_refused(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {'confirm_username': self.user.username, 'password': 'not-my-password'})
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_a_confirmed_deletion_signs_out_and_goes_home(self):
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, {'confirm_username': self.user.username, 'password': PASSWORD})
        self.assertRedirects(response, reverse('pages:home'), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(id=self.user.id).exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_a_social_login_account_confirms_with_the_username_alone(self):
        self.user.set_unusable_password()
        self.user.save()
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, {'confirm_username': self.user.username})
        self.assertFalse(User.objects.filter(id=self.user.id).exists())

    def test_a_blocked_deletion_explains_and_keeps_the_account_signed_in(self):
        self._subscription(self.user)
        self.stripe_cancel.side_effect = stripe.error.APIConnectionError('Stripe is unreachable')
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'confirm_username': self.user.username, 'password': PASSWORD}, follow=True)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())
        self.assertIn('subscription', ' '.join(str(m) for m in response.context['messages']).lower())
        self.assertEqual(self.client.session['_auth_user_id'], str(self.user.id))

    def test_get_never_deletes_and_signed_out_visitors_are_sent_to_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.user)
        self.client.get(self.url, {'confirm_username': self.user.username, 'password': PASSWORD})
        self.assertTrue(User.objects.filter(id=self.user.id).exists())


class AdminAndOpsDeletionTests(DeletionTestCase):

    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_superuser('del_admin', 'admin@example.test', PASSWORD)
        self.target, _ = self._founder()

    def test_django_admin_cannot_delete_users(self):
        request = RequestFactory().get('/')
        request.user = self.staff
        user_admin = admin.site._registry[User]
        self.assertFalse(user_admin.has_delete_permission(request))
        self.assertFalse(user_admin.has_delete_permission(request, self.target))
        self.assertNotIn('delete_selected', user_admin.get_actions(request))
        self.client.force_login(self.staff)
        self.client.post(reverse('admin:auth_user_delete', args=[self.target.id]), {'post': 'yes'})
        self.assertTrue(User.objects.filter(id=self.target.id).exists())

    def test_staff_delete_through_the_same_service(self):
        self._subscription(self.target)
        self.client.force_login(self.staff)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('ops:delete_user', args=[self.target.id]), {'confirm_username': self.target.username})
        self.assertFalse(User.objects.filter(id=self.target.id).exists())
        self.stripe_cancel.assert_called_once()

    def test_ops_deletion_needs_the_typed_username(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('ops:delete_user', args=[self.target.id]), {'confirm_username': 'wrong'})
        self.assertTrue(User.objects.filter(id=self.target.id).exists())

    def test_non_staff_cannot_use_ops_deletion(self):
        outsider, _ = self._investor('del_outsider')
        self.client.force_login(outsider)
        self.client.post(reverse('ops:delete_user', args=[self.target.id]), {'confirm_username': self.target.username})
        self.assertTrue(User.objects.filter(id=self.target.id).exists())

    def test_ops_cannot_delete_staff_or_yourself(self):
        other_staff = User.objects.create_user('del_other_staff', password=PASSWORD, is_staff=True)
        self.client.force_login(self.staff)
        for target in (other_staff, self.staff):
            with self.subTest(target=target.username):
                self.client.post(reverse('ops:delete_user', args=[target.id]), {'confirm_username': target.username})
                self.assertTrue(User.objects.filter(id=target.id).exists())
