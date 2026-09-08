"""
The checklist label is a join key across three files, and nothing enforced it.

`matchmaking/utils.py` produces checklist labels. `journey_actions.ACTION_INFO`
and `journey_actions.URL_BY_LABEL` are both keyed by that exact string. A
mismatch is silent: `ACTION_INFO.get(label)` returns None and
JourneyStatusAPIView simply skips building the card, so the "Next best
improvement" disappears with no error, no warning and no failing test.

That is exactly what PR #23 did — it renamed
"Upload a pitch deck or pitch video" to "Upload a pitch deck or a 1–3 min
pitch video" and left both maps behind, removing the card for every
yellow-stage founder. These tests make the contract executable so a rename
fails loudly instead.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from .journey_actions import ACTION_INFO, URL_BY_LABEL
from .models import Application, BuyerApplication, InvestorApplication, SellerApplication
from .tests import _mock_embedding_generation
from .utils import (
    compute_buyer_journey_stage, compute_founder_journey_stage,
    compute_investor_journey_stage, compute_seller_journey_stage,
)

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class JourneyLabelMappingTests(TestCase):
    """Every label every role can be shown must resolve in both maps."""

    def setUp(self):
        _mock_embedding_generation(self)

    def _all_labels_for(self, compute, user):
        """Every label this role can see, across all three stages."""
        return [item['label'] for item in compute(user)['checklist']]

    def _founder_labels(self):
        user = User.objects.create_user('jm_founder', password='x')
        labels = set(self._all_labels_for(compute_founder_journey_stage, user))  # red

        app = Application.objects.create(
            user=user, company_name='JMCo', founder_name='F', email='f@t.com',
            description='A company.', sector='SaaS', stage='Seed')
        user.refresh_from_db()
        labels |= set(self._all_labels_for(compute_founder_journey_stage, user))  # yellow

        app.pitch_deck = SimpleUploadedFile('d.pdf', b'%PDF-1.4', content_type='application/pdf')
        app.save(update_fields=['pitch_deck'])
        user.refresh_from_db()
        labels |= set(self._all_labels_for(compute_founder_journey_stage, user))  # green
        return labels

    def _seller_labels(self):
        user = User.objects.create_user('jm_seller', password='x')
        labels = set(self._all_labels_for(compute_seller_journey_stage, user))

        seller = SellerApplication.objects.create(
            user=user, company_name='JMSell', seller_name='S', email='s@t.com',
            description='A business.', industry='Facilities Services')
        user.refresh_from_db()
        labels |= set(self._all_labels_for(compute_seller_journey_stage, user))

        seller.cim_document = SimpleUploadedFile('c.pdf', b'%PDF-1.4', content_type='application/pdf')
        seller.save(update_fields=['cim_document'])
        user.refresh_from_db()
        labels |= set(self._all_labels_for(compute_seller_journey_stage, user))
        return labels

    def _investor_labels(self):
        user = User.objects.create_user('jm_investor', password='x')
        labels = set(self._all_labels_for(compute_investor_journey_stage, user))  # red

        InvestorApplication.objects.create(
            user=user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed')
        user.refresh_from_db()
        labels |= set(self._all_labels_for(compute_investor_journey_stage, user))  # yellow

        # Green is gated on completion_percentage == 100, a property counting
        # optional fields. Forced rather than filled in, so this test keeps
        # covering green-stage labels even if those optional fields change.
        with mock.patch.object(InvestorApplication, 'completion_percentage',
                               new_callable=mock.PropertyMock, return_value=100):
            user.refresh_from_db()
            labels |= set(self._all_labels_for(compute_investor_journey_stage, user))
        return labels

    def _buyer_labels(self):
        user = User.objects.create_user('jm_buyer', password='x')
        labels = set(self._all_labels_for(compute_buyer_journey_stage, user))  # red

        BuyerApplication.objects.create(
            user=user, full_name='B', company_name='Hale', email='b@t.com',
            acquisition_thesis='Buy things.')
        user.refresh_from_db()
        labels |= set(self._all_labels_for(compute_buyer_journey_stage, user))  # yellow

        with mock.patch.object(BuyerApplication, 'completion_percentage',
                               new_callable=mock.PropertyMock, return_value=100):
            user.refresh_from_db()
            labels |= set(self._all_labels_for(compute_buyer_journey_stage, user))
        return labels

    def test_every_label_has_action_copy(self):
        for role, getter in (('founder', self._founder_labels), ('seller', self._seller_labels),
                             ('investor', self._investor_labels), ('buyer', self._buyer_labels)):
            for label in sorted(getter()):
                with self.subTest(role=role, label=label):
                    self.assertIn(
                        label, ACTION_INFO,
                        f'{role} checklist label {label!r} has no ACTION_INFO entry, so the '
                        f'"Next best improvement" card silently disappears for that item')

    def test_every_label_has_a_destination(self):
        for role, getter in (('founder', self._founder_labels), ('seller', self._seller_labels),
                             ('investor', self._investor_labels), ('buyer', self._buyer_labels)):
            for label in sorted(getter()):
                with self.subTest(role=role, label=label):
                    self.assertIn(
                        label, URL_BY_LABEL[role],
                        f'{role} checklist label {label!r} has no URL_BY_LABEL entry, so the '
                        f'card has nowhere to send the user')

    def test_every_destination_actually_resolves(self):
        # A url name can rot independently of the label matching.
        for role, mapping in URL_BY_LABEL.items():
            for label, url_name in mapping.items():
                with self.subTest(role=role, label=label):
                    try:
                        reverse(url_name)
                    except NoReverseMatch:
                        self.fail(f'{role}/{label!r} points at {url_name!r}, which does not resolve')

    def test_no_stale_action_copy_for_labels_no_role_can_see(self):
        # The other direction: an ACTION_INFO key nothing produces is a
        # rename that was only half applied.
        live = (self._founder_labels() | self._seller_labels()
                | self._investor_labels() | self._buyer_labels())
        stale = sorted(set(ACTION_INFO) - live)
        self.assertEqual(
            stale, [],
            f'ACTION_INFO keys no checklist produces: {stale}. A label was renamed '
            f'and the copy left behind.')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class YellowFounderNextBestActionTests(TestCase):
    """
    The regression itself, through the real API rather than the maps.

    A yellow-stage founder is the exact case PR #23 broke: their first
    unfinished item is the renamed pitch-asset label, so the card vanished.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('jm_yellow', password='x')
        Application.objects.create(
            user=self.user, company_name='YellowCo', founder_name='F', email='y@t.com',
            description='A company.', sector='SaaS', stage='Seed')
        self.client.force_login(self.user)

    def test_a_yellow_founder_still_gets_a_next_best_action(self):
        response = self.client.get('/api/v1/zelda/journey-status/')
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['stage_color'], 'yellow')
        self.assertIsNotNone(
            data['next_best_action'],
            'the renamed pitch-asset label must still resolve to action copy')
        self.assertEqual(data['next_best_action']['label'],
                         'Upload a pitch deck or a 1–3 min pitch video')
        self.assertTrue(data['next_best_action']['action_url'])
