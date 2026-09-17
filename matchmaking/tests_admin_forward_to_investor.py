"""
Django admin's "Forward selected Founder(s) to an Investor" makes a staff
introduction, and never touches an existing relationship.

The action used to create connections as `requested` with the default
initiator (INVESTOR). No dashboard queue lists `requested` (they match
`pending`), so nobody could answer those introductions. Worse, for a founder
and investor who were already connected it overwrote the status with
`requested` -- an ACCEPTED, DECLINED or FUNDED relationship reset by one staff
click, which the answer-once rule (D11) would then treat as unanswered.

It now matches the ops "manual intro" tool:

- a new connection is initiated_by='STAFF' with the default `pending` status,
  so it appears in the founder's inbound queue and the founder answers it
- an existing connection is left exactly as it is -- status, initiator and
  timestamps -- and is reported as already existing

The investor is still emailed the founder's profile either way.

Invariant: staff initiating an introduction must never mutate an existing
relationship.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from matchmaking.models import Application, Connection, InvestorApplication
from matchmaking.tests import _mock_embedding_generation

User = get_user_model()


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class _Forwarding(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.admin_user = User.objects.create_superuser('fwd_admin', 'admin@t.com', 'x')
        self.founder_user = User.objects.create_user('fwd_founder', password='x')
        self.founder = self._founder(self.founder_user, 'Northwind Grid')
        self.investor_user = User.objects.create_user('fwd_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='Ivy Investor', email='ivy@t.com', company_name='Harbor Capital',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.old = timezone.now() - timedelta(days=30)

    def _founder(self, user, company):
        return Application.objects.create(
            user=user, company_name=company, founder_name='F', email=f'{user.username}@t.com',
            description='test', sector='SaaS', stage='Seed',
        )

    def _forward(self, *founders, apply=True):
        self.client.force_login(self.admin_user)
        data = {
            'action': 'forward_to_investor',
            '_selected_action': [f.id for f in founders],
            'investor': self.investor.id,
        }
        if apply:
            data['apply'] = '1'
        return self.client.post(reverse('admin:matchmaking_application_changelist'), data, follow=apply)

    def _messages(self, response):
        return ' '.join(str(m) for m in response.context['messages'])


class NewStaffIntroductionTests(_Forwarding):

    def test_a_forwarded_founder_becomes_a_pending_staff_introduction(self):
        self._forward(self.founder)
        connection = Connection.objects.get(founder=self.founder, investor=self.investor)
        self.assertEqual(connection.status, 'pending')
        self.assertEqual(connection.initiated_by, 'STAFF')
        self.assertIsNone(connection.accepted_at)

    def test_it_appears_in_the_founders_inbound_queue(self):
        self._forward(self.founder)
        self.client.force_login(self.founder_user)
        response = self.client.get('/matchmaking/dashboard/founder/')
        self.assertEqual(response.status_code, 200)
        ids = [c.id for c in response.context['pending_requests']]
        self.assertIn(Connection.objects.get(founder=self.founder).id, ids)

    @mock.patch('matchmaking.views.ensure_deal_channel', return_value=None)
    def test_the_founder_answers_it_and_the_investor_cannot(self, _channel):
        self._forward(self.founder)
        connection = Connection.objects.get(founder=self.founder)
        url = reverse('matchmaking:connection_action')
        body = {'id': connection.id, 'action': 'ACCEPTED'}

        self.client.force_login(self.investor_user)
        self.assertEqual(self.client.post(url, data=body, content_type='application/json').status_code, 403)

        self.client.force_login(self.founder_user)
        self.assertEqual(self.client.post(url, data=body, content_type='application/json').status_code, 200)
        connection.refresh_from_db()
        self.assertEqual(connection.status, 'ACCEPTED')

    def test_the_investor_is_emailed_the_founders_profile(self):
        self._forward(self.founder)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ivy@t.com'])
        self.assertIn('Northwind Grid', mail.outbox[0].subject)

    def test_the_admin_is_told_how_many_were_new(self):
        response = self._forward(self.founder)
        self.assertIn('1 new', self._messages(response))

    def test_the_selection_page_still_renders_before_applying(self):
        response = self._forward(self.founder, apply=False)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Connection.objects.exists())


class ExistingRelationshipTests(_Forwarding):

    def _existing(self, status, initiated_by='INVESTOR'):
        answered = status not in ('pending',) and status != 'DECLINED'
        return Connection.objects.create(
            founder=self.founder, investor=self.investor, status=status, initiated_by=initiated_by,
            accepted_at=self.old if answered else None,
            funded_at=self.old if status == 'FUNDED' else None,
            notes='Their own notes.',
        )

    def test_an_existing_connection_is_never_changed(self):
        for status in ('pending', 'ACCEPTED', 'DECLINED', 'FUNDED_PENDING', 'FUNDED'):
            for initiated_by in ('INVESTOR', 'FOUNDER'):
                with self.subTest(status=status, initiated_by=initiated_by):
                    Connection.objects.all().delete()
                    original = self._existing(status, initiated_by)
                    before = Connection.objects.filter(pk=original.pk).values().get()

                    self._forward(self.founder)

                    self.assertEqual(Connection.objects.filter(founder=self.founder).count(), 1)
                    after = Connection.objects.filter(pk=original.pk).values().get()
                    self.assertEqual(after, before)

    def test_the_admin_is_told_it_already_existed(self):
        self._existing('ACCEPTED')
        response = self._forward(self.founder)
        text = self._messages(response)
        self.assertIn('already', text)
        self.assertNotIn('Updated', text)

    def test_the_investor_is_still_emailed_for_an_existing_connection(self):
        self._existing('ACCEPTED')
        self._forward(self.founder)
        self.assertEqual(len(mail.outbox), 1)

    def test_a_mixed_selection_creates_only_the_missing_introductions(self):
        self._existing('FUNDED')
        other_user = User.objects.create_user('fwd_founder_2', password='x')
        other = self._founder(other_user, 'Gridworks')

        response = self._forward(self.founder, other)

        self.assertEqual(Connection.objects.get(founder=self.founder).status, 'FUNDED')
        created = Connection.objects.get(founder=other)
        self.assertEqual((created.status, created.initiated_by), ('pending', 'STAFF'))
        text = self._messages(response)
        self.assertIn('1 new', text)
        self.assertIn('1 already', text)
