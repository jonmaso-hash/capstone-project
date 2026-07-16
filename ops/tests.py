import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from matchmaking.tests import _mock_embedding_generation
from .models import ImpersonationLog, BulkEmailLog

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ImpersonationTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user('ops_staff', password='x', is_staff=True)
        self.target_user = User.objects.create_user('ops_target', password='x')
        self.other_staff = User.objects.create_user('ops_other_staff', password='x', is_staff=True)

    def test_staff_can_start_and_stop_impersonation(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(reverse('ops:start_impersonation', args=[self.target_user.id]))

        self.assertRedirects(response, reverse('accounts:profile', args=[self.target_user.username]))
        self.assertEqual(self.client.session['_auth_user_id'], str(self.target_user.id))
        self.assertEqual(self.client.session['impersonator_id'], self.staff_user.id)
        log = ImpersonationLog.objects.get(impersonator=self.staff_user, target=self.target_user)
        self.assertIsNone(log.ended_at)

        response = self.client.post(reverse('ops:stop_impersonation'))

        self.assertEqual(self.client.session['_auth_user_id'], str(self.staff_user.id))
        self.assertNotIn('impersonator_id', self.client.session)
        log.refresh_from_db()
        self.assertIsNotNone(log.ended_at)

    def test_staff_cannot_impersonate_another_staff_member(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(reverse('ops:start_impersonation', args=[self.other_staff.id]), follow=True)

        self.assertContains(response, "be impersonated")
        self.assertEqual(self.client.session['_auth_user_id'], str(self.staff_user.id))
        self.assertFalse(ImpersonationLog.objects.filter(target=self.other_staff).exists())

    def test_non_staff_cannot_start_impersonation(self):
        self.client.force_login(self.target_user)

        response = self.client.post(reverse('ops:start_impersonation', args=[self.other_staff.id]), follow=True)

        self.assertContains(response, "restricted to staff")
        self.assertFalse(ImpersonationLog.objects.exists())


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DocumentVisibilityTests(TestCase):
    def setUp(self):
        from zelda_api.vector_models import DocumentSource

        self.staff_user = User.objects.create_user('doc_staff', password='x', is_staff=True)
        self.owner = User.objects.create_user('doc_owner', password='x')
        self.investor_user = User.objects.create_user('doc_investor', password='x')

        _mock_embedding_generation(self)
        from matchmaking.models import InvestorApplication
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com',
            company_name='ICo', investment_focus='SaaS', investment_stage='Seed',
        )

        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='TestCo', uploaded_by=self.owner,
            status='analyzed', is_hidden_by_staff=True,
        )

    def test_hidden_document_blocks_non_owner_non_staff(self):
        self.client.force_login(self.investor_user)
        response = self.client.get(f'/api/v1/zelda/documents/{self.document.id}/memo/')
        self.assertEqual(response.status_code, 403)

    def test_hidden_document_still_visible_to_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(f'/api/v1/zelda/documents/{self.document.id}/memo/')
        self.assertNotEqual(response.status_code, 403)

    def test_hidden_document_still_visible_to_staff(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(f'/api/v1/zelda/documents/{self.document.id}/memo/')
        self.assertNotEqual(response.status_code, 403)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ManualIntroCreationTests(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)
        from matchmaking.models import Application, InvestorApplication

        self.staff_user = User.objects.create_user('intro_staff', password='x', is_staff=True)
        founder_user = User.objects.create_user('intro_founder', password='x')
        investor_user = User.objects.create_user('intro_investor', password='x')

        self.founder = Application.objects.create(
            user=founder_user, founder_name='F', email='f@t.com', company_name='FCo',
            sector='SaaS', stage='Seed', description='test',
        )
        self.investor = InvestorApplication.objects.create(
            user=investor_user, full_name='I', email='i@t.com',
            company_name='ICo', investment_focus='SaaS', investment_stage='Seed',
        )

    def test_manual_intro_is_attributed_to_staff(self):
        from matchmaking.models import Connection

        self.client.force_login(self.staff_user)
        response = self.client.post(reverse('ops:manual_intro_create'), {
            'intro_type': 'founder_investor',
            'founder_id': self.founder.id,
            'investor_id': self.investor.id,
        })

        self.assertRedirects(response, reverse('ops:manual_intro_create'))
        conn = Connection.objects.get(founder=self.founder, investor=self.investor)
        self.assertEqual(conn.initiated_by, 'STAFF')
        self.assertEqual(conn.status, 'pending')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BulkEmailIsolationTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user('bulk_staff', password='x', is_staff=True, email='staff@t.com')
        self.good_user = User.objects.create_user('bulk_good', password='x', email='good@t.com')
        self.bad_user = User.objects.create_user('bulk_bad', password='x', email='bad@t.com')

    def test_one_failed_send_does_not_drop_the_rest(self):
        from .tasks import send_bulk_announcement

        log = BulkEmailLog.objects.create(
            subject='Test', body='Body', audience='ALL', sent_by=self.staff_user,
        )

        def fake_send_mail(*args, **kwargs):
            if kwargs['recipient_list'] == ['bad@t.com']:
                raise Exception('SMTP exploded')
            return 1

        with mock.patch('ops.tasks.send_mail', side_effect=fake_send_mail):
            result = send_bulk_announcement.run(log.id)

        self.assertEqual(result['status'], 'success')
        log.refresh_from_db()
        # 3 total recipients (staff, good, bad) minus the 1 that raised = 2
        self.assertEqual(log.recipient_count, 2)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TrainingDataPipelineTests(TestCase):
    """log_training_example wiring in override_connection_status/manual_intro_create + the Training Data page/export."""

    def setUp(self):
        _mock_embedding_generation(self)
        from matchmaking.models import Application, InvestorApplication, Connection

        self.staff_user = User.objects.create_user('td_staff', password='x', is_staff=True)
        founder_user = User.objects.create_user('td_founder', password='x')
        investor_user = User.objects.create_user('td_investor', password='x')

        self.founder = Application.objects.create(
            user=founder_user, founder_name='F', email='f@t.com', company_name='FCo',
            sector='SaaS', stage='Seed', description='test',
        )
        self.investor = InvestorApplication.objects.create(
            user=investor_user, full_name='I', email='i@t.com',
            company_name='ICo', investment_focus='SaaS', investment_stage='Seed',
        )
        self.conn = Connection.objects.create(
            founder=self.founder, investor=self.investor, status='ACCEPTED', initiated_by='FOUNDER',
        )

    def test_override_to_funded_logs_positive_ops_override_example(self):
        from matchmaking.models import MatchTrainingExample

        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('ops:override_connection_status', args=['connection', self.conn.id]),
            {'status': 'FUNDED'},
        )
        example = MatchTrainingExample.objects.get()
        self.assertEqual(example.anchor_type, 'INVESTOR')
        self.assertEqual(example.anchor_id, self.investor.id)
        self.assertEqual(example.candidate_type, 'FOUNDER')
        self.assertEqual(example.candidate_id, self.founder.id)
        self.assertEqual(example.label, 'POSITIVE')
        self.assertEqual(example.source, 'ops_override')

    def test_override_to_declined_logs_negative_ops_override_example(self):
        from matchmaking.models import MatchTrainingExample

        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('ops:override_connection_status', args=['connection', self.conn.id]),
            {'status': 'DECLINED'},
        )
        example = MatchTrainingExample.objects.get()
        self.assertEqual(example.label, 'NEGATIVE')
        self.assertEqual(example.source, 'ops_override')

    def test_override_to_pending_does_not_log_an_example(self):
        from matchmaking.models import MatchTrainingExample

        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('ops:override_connection_status', args=['connection', self.conn.id]),
            {'status': 'pending'},
        )
        self.assertFalse(MatchTrainingExample.objects.exists())

    def test_manual_intro_logs_positive_ops_manual_intro_example(self):
        from matchmaking.models import Application, InvestorApplication, MatchTrainingExample

        other_founder_user = User.objects.create_user('td_founder2', password='x')
        other_founder = Application.objects.create(
            user=other_founder_user, founder_name='F2', email='f2@t.com', company_name='FCo2',
            sector='SaaS', stage='Seed', description='test',
        )

        self.client.force_login(self.staff_user)
        self.client.post(reverse('ops:manual_intro_create'), {
            'intro_type': 'founder_investor',
            'founder_id': other_founder.id,
            'investor_id': self.investor.id,
        })

        example = MatchTrainingExample.objects.get()
        self.assertEqual(example.anchor_type, 'INVESTOR')
        self.assertEqual(example.anchor_id, self.investor.id)
        self.assertEqual(example.candidate_type, 'FOUNDER')
        self.assertEqual(example.candidate_id, other_founder.id)
        self.assertEqual(example.label, 'POSITIVE')
        self.assertEqual(example.source, 'ops_manual_intro')

    def test_manual_intro_on_existing_connection_does_not_double_log(self):
        from matchmaking.models import MatchTrainingExample

        self.client.force_login(self.staff_user)
        self.client.post(reverse('ops:manual_intro_create'), {
            'intro_type': 'founder_investor',
            'founder_id': self.founder.id,
            'investor_id': self.investor.id,
        })
        self.assertFalse(MatchTrainingExample.objects.exists())

    def test_training_data_page_shows_counts_by_source_and_label(self):
        from matchmaking.models import log_training_example

        log_training_example('INVESTOR', self.investor.id, 'FOUNDER', self.founder.id, 'POSITIVE', 'thumbs_up')
        log_training_example('INVESTOR', self.investor.id, 'FOUNDER', self.founder.id, 'NEGATIVE', 'ops_override')

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('ops:training_data'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'thumbs_up')
        self.assertContains(response, 'ops_override')
        self.assertEqual(response.context['total_count'], 2)

    def test_training_data_page_blocked_for_non_staff(self):
        self.client.force_login(self.founder.user)
        response = self.client.get(reverse('ops:training_data'), follow=True)
        self.assertContains(response, 'restricted to staff')

    def test_export_jsonl_contains_anchor_and_candidate_text(self):
        from matchmaking.models import log_training_example

        log_training_example('INVESTOR', self.investor.id, 'FOUNDER', self.founder.id, 'POSITIVE', 'thumbs_up')

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('ops:export_training_data'))

        self.assertEqual(response.status_code, 200)
        lines = response.content.decode().strip().split('\n')
        self.assertEqual(len(lines), 1)
        row = json.loads(lines[0])
        self.assertEqual(row['anchor'], self.investor.investment_focus)
        self.assertEqual(row['candidate'], self.founder.description)
        self.assertEqual(row['label'], 'POSITIVE')
        self.assertEqual(row['source'], 'thumbs_up')

    def test_export_jsonl_strips_known_pii_from_free_text(self):
        from matchmaking.models import log_training_example

        # Embed the founder's own known PII directly into the free-text
        # description — exactly the "name mentioned in prose" case regex
        # alone can't reliably catch, but the known-field substitution can.
        # (founder_name is overridden here to something realistic — the
        # setUp default of 'F' is too short/generic to exercise this.)
        self.founder.founder_name = 'Jordan Smith'
        self.founder.description = (
            "Founded by Jordan Smith, reach us at f@t.com or 555-123-4567. "
            "See https://foundershow.example.com for our demo."
        )
        self.founder.save(update_fields=['founder_name', 'description'])

        log_training_example('INVESTOR', self.investor.id, 'FOUNDER', self.founder.id, 'POSITIVE', 'thumbs_up')

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('ops:export_training_data'))

        row = json.loads(response.content.decode().strip())
        self.assertNotIn('f@t.com', row['candidate'])
        self.assertNotIn('555-123-4567', row['candidate'])
        self.assertNotIn('foundershow.example.com', row['candidate'])
        self.assertIn('[EMAIL]', row['candidate'])
        self.assertIn('[PHONE]', row['candidate'])
        self.assertIn('[URL]', row['candidate'])
