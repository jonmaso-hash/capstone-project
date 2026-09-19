"""
customer.subscription.updated keeps the local subscription state and renewal
date right (Tier 0 billing fix).

Two defects in one branch of the webhook:

- The renewal date was never stored. Since Stripe API 2025-03-31.basil a
  subscription carries no top-level current_period_end -- the period lives on
  each subscription item (items.data[].current_period_end) -- and this
  account's API version (2026-06-24.dahlia) is later than that. So the billing
  page's "Renews ..." line never appeared. A payload that did carry the
  legacy top-level field crashed the handler instead: it used timezone.utc,
  which Django 6 removed, so Stripe retried and the status never updated.
- Every status other than active/past_due was stored as INCOMPLETE, so a
  canceled or unpaid subscription looked like an unfinished checkout and a
  trial got no Premium.

Acceptance criteria this file pins:
  1. the renewal date is stored from the current payload shape (items)
  2. the legacy top-level field is still read
  3. time-zone handling can't crash the handler
  4. every Stripe status maps to its intended local state and Premium flag
  5. the same event twice leaves the same state, with no extra side effects
  6. an event for an unknown subscription changes nothing
The rest of the webhook is covered by billing's existing tests.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from matchmaking.models import Application
from matchmaking.tests import _mock_embedding_generation
from notifications.models import Notification
from .models import Subscription
from .tests import FAKE_STRIPE_SETTINGS
from .tests_webhook_signed import SIGNING_SECRET, _payload, _signature_header

User = get_user_model()

RENEWS = datetime.datetime(2026, 10, 17, 12, 0, tzinfo=datetime.timezone.utc)
LATER = datetime.datetime(2026, 11, 17, 12, 0, tzinfo=datetime.timezone.utc)


def stamp(moment):
    return int(moment.timestamp())


def items(*period_ends):
    """A subscription's `items` list as the current API sends it."""
    return {'object': 'list', 'data': [
        {'id': f'si_{index}', 'object': 'subscription_item', 'current_period_end': end}
        for index, end in enumerate(period_ends)
    ]}


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    **{**FAKE_STRIPE_SETTINGS, 'STRIPE_WEBHOOK_SECRET': SIGNING_SECRET},
)
class _Updated(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('sub_updated_founder', password='x')
        self.app = Application.objects.create(
            user=self.user, founder_name='F', email='f@t.com', company_name='FCo',
            sector='SaaS', stage='Seed', description='test', is_private=False,
        )
        self.sub = Subscription.objects.create(
            user=self.user, plan=Subscription.Plan.FOUNDER_PREMIUM,
            stripe_customer_id='cus_upd', stripe_subscription_id='sub_upd',
            status=Subscription.Status.ACTIVE,
        )
        self._set_premium(True)

    def _set_premium(self, value):
        Application.objects.filter(pk=self.app.pk).update(is_premium=value)

    def _updated(self, subscription_id='sub_upd', **fields):
        data = {'id': subscription_id, 'object': 'subscription', 'status': 'active'}
        data.update(fields)
        payload = _payload('customer.subscription.updated', data)
        return self.client.post(
            reverse('billing:stripe_webhook'), data=payload, content_type='application/json',
            HTTP_STRIPE_SIGNATURE=_signature_header(payload),
        )

    def _state(self):
        self.sub.refresh_from_db()
        self.app.refresh_from_db()
        return self.sub.status, self.app.is_premium


class RenewalDateTests(_Updated):

    def test_the_renewal_date_is_read_from_the_subscription_items(self):
        response = self._updated(items=items(stamp(RENEWS)))
        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.current_period_end, RENEWS)

    def test_the_earliest_item_period_end_is_the_renewal_date(self):
        self._updated(items=items(stamp(LATER), stamp(RENEWS)))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.current_period_end, RENEWS)

    def test_a_legacy_top_level_period_end_is_still_read_without_crashing(self):
        response = self._updated(current_period_end=stamp(RENEWS))
        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.current_period_end, RENEWS)

    def test_the_item_period_end_wins_over_the_legacy_field(self):
        self._updated(items=items(stamp(RENEWS)), current_period_end=stamp(LATER))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.current_period_end, RENEWS)

    def test_no_period_end_leaves_the_stored_date_alone(self):
        Subscription.objects.filter(pk=self.sub.pk).update(current_period_end=LATER)
        response = self._updated()
        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.current_period_end, LATER)

    def test_an_unreadable_period_end_is_ignored(self):
        for value in ('soon', None, -10 ** 20):
            with self.subTest(value=value):
                Subscription.objects.filter(pk=self.sub.pk).update(current_period_end=LATER)
                response = self._updated(items=items(value), status='past_due')
                self.assertEqual(response.status_code, 200)
                self.sub.refresh_from_db()
                self.assertEqual(self.sub.current_period_end, LATER)
                # The status still updates even though the date couldn't be read.
                self.assertEqual(self.sub.status, Subscription.Status.PAST_DUE)

    def test_the_billing_page_shows_the_renewal_date(self):
        self._updated(items=items(stamp(RENEWS)))
        self.client.force_login(self.user)
        response = self.client.get(reverse('billing:billing_page'))
        # The line now carries the recurring terms with the date.
        self.assertContains(response, 'October 17, 2026')
        self.assertContains(response, 'Renews automatically')


class StatusMappingTests(_Updated):

    MAPPING = (
        ('active', Subscription.Status.ACTIVE, True),
        ('trialing', Subscription.Status.ACTIVE, True),
        ('past_due', Subscription.Status.PAST_DUE, False),
        ('unpaid', Subscription.Status.PAST_DUE, False),
        ('canceled', Subscription.Status.CANCELED, False),
        ('incomplete_expired', Subscription.Status.CANCELED, False),
        ('incomplete', Subscription.Status.INCOMPLETE, False),
    )

    def _reset(self, status, premium):
        Subscription.objects.filter(pk=self.sub.pk).update(status=status)
        self._set_premium(premium)

    def test_every_stripe_status_maps_to_its_local_state_and_premium_flag(self):
        for stripe_status, local_status, premium in self.MAPPING:
            # Start from the opposite Premium state so a missed update shows.
            for starting_status, starting_premium in (
                    (Subscription.Status.ACTIVE, True), (Subscription.Status.PAST_DUE, False)):
                with self.subTest(stripe_status=stripe_status, starting=starting_status):
                    self._reset(starting_status, starting_premium)
                    response = self._updated(status=stripe_status)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(self._state(), (local_status, premium))

    def test_a_paused_subscription_has_no_premium(self):
        self._reset(Subscription.Status.ACTIVE, True)
        self._updated(status='paused')
        status, premium = self._state()
        self.assertFalse(premium)
        self.assertNotEqual(status, Subscription.Status.ACTIVE)

    def test_an_unrecognised_status_turns_premium_off(self):
        self._reset(Subscription.Status.ACTIVE, True)
        self._updated(status='something_stripe_adds_later')
        status, premium = self._state()
        self.assertFalse(premium)
        self.assertNotEqual(status, Subscription.Status.ACTIVE)


class IdempotencyTests(_Updated):

    def test_the_same_update_twice_leaves_the_same_state_and_nothing_extra(self):
        first = self._updated(status='past_due', items=items(stamp(RENEWS)))
        after_first = (self._state(), self.sub.current_period_end)
        second = self._updated(status='past_due', items=items(stamp(RENEWS)))
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual((self._state(), self.sub.current_period_end), after_first)
        self.assertEqual(after_first, ((Subscription.Status.PAST_DUE, False), RENEWS))
        self.assertFalse(Notification.objects.exists())

    def test_an_update_for_an_unknown_subscription_changes_nothing(self):
        response = self._updated(subscription_id='sub_someone_else', status='canceled', items=items(stamp(RENEWS)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._state(), (Subscription.Status.ACTIVE, True))
        self.assertIsNone(self.sub.current_period_end)
