"""
A seller controls what their listing discloses, and to whom.

Sellers had no visibility model at all. Asking price was shown to anonymous
visitors on the acquisition board and the Pitch Videos page; revenue, EBITDA
and reason for sale to any signed-in account on the profile; all three
financial figures in bulk through the acquisition CSV; the price as JSON through
Ask Zelda, together with a has_cim flag that disclosed whether a CIM existed --
which the CIM endpoint itself is carefully built not to reveal.

Policy (SELLER_FIELD_VISIBILITY): asking price PUBLIC by default, because on a
business-for-sale listing it is the listing, but tightenable; revenue, EBITDA
and reason for sale CONNECTED -- an AcquisitionConnection that is ACCEPTED,
CLOSED_PENDING or CLOSED.

Organised, as on the founder side, around the two ways a value escapes:

    disclosure   the value appears in a response
    inference    it does not appear, but behaviour reveals it

The inference tests vary a HIDDEN value and require the unauthorized result to
stay identical, each with a public-value control proving the channel is live
when disclosure is allowed -- otherwise "identical" is also what a dead page
looks like.
"""
import csv
import io
import json
from unittest import mock

from django.contrib.auth.models import AnonymousUser, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    AcquisitionConnection, Application, BuyerApplication, FIELD_CONNECTED, FIELD_PRIVATE,
    FIELD_PUBLIC, SellerApplication, can_view_profile_field,
)
from .tests import _mock_embedding_generation

PRICE = 1_200_000
REVENUE = 3_400_000
EBITDA = 560_000


def _has(text, number):
    return f'{number:,}' in text or str(number) in text.replace(',', '')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class _SellerCast(TestCase):
    """A seller, staff, an accepted buyer, a stranger buyer, anonymous."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.seller_user = User.objects.create_user('sfv_seller', password='x')
        self.seller = self._seller(self.seller_user, 'Acme Widgets', PRICE)
        self.staff_user = User.objects.create_user('sfv_staff', password='x', is_staff=True)
        self.connected_user, self.connected_buyer = self._buyer('sfv_connected')
        AcquisitionConnection.objects.create(
            buyer=self.connected_buyer, seller=self.seller, status='ACCEPTED', initiated_by='BUYER',
        )
        self.stranger_user, self.stranger_buyer = self._buyer('sfv_stranger')

    def _seller(self, user, company, price, **extra):
        fields = dict(
            user=user, company_name=company, seller_name='S', email=f'{user.username}@t.com',
            description='A steady regional manufacturer.', industry='Manufacturing',
            geography='Ohio', asking_price=price, annual_revenue=REVENUE, ebitda=EBITDA,
            reason_for_sale='Owner retiring after 30 years.', review_status='APPROVED',
        )
        fields.update(extra)
        return SellerApplication.objects.create(**fields)

    def _buyer(self, username, **extra):
        user = User.objects.create_user(username, password='x')
        fields = dict(
            user=user, full_name='B', email=f'{username}@t.com', company_name=f'{username} LLC',
            acquisition_thesis='We acquire manufacturing businesses.',
            budget_min=500_000, budget_max=2_000_000,
        )
        fields.update(extra)
        return user, BuyerApplication.objects.create(**fields)

    def tighten(self, seller, field, level):
        # .update(): the post_save signal would otherwise regenerate vectors.
        stored = dict(seller.field_visibility or {})
        stored[field] = level
        SellerApplication.objects.filter(pk=seller.pk).update(field_visibility=stored)
        seller.refresh_from_db()


class SellerAuthorityTests(_SellerCast):

    def who(self, field):
        return {
            'anonymous': can_view_profile_field(AnonymousUser(), self.seller, field),
            'stranger': can_view_profile_field(self.stranger_user, self.seller, field),
            'connected': can_view_profile_field(self.connected_user, self.seller, field),
            'owner': can_view_profile_field(self.seller_user, self.seller, field),
            'staff': can_view_profile_field(self.staff_user, self.seller, field),
        }

    def test_asking_price_is_public_by_default(self):
        self.assertTrue(all(self.who('asking_price').values()))

    def test_a_tightened_asking_price_is_withheld_from_strangers(self):
        self.tighten(self.seller, 'asking_price', FIELD_CONNECTED)
        self.assertEqual(self.who('asking_price'), {
            'anonymous': False, 'stranger': False, 'connected': True, 'owner': True, 'staff': True,
        })

    def test_revenue_ebitda_and_reason_default_to_accepted_buyers(self):
        for field in ('annual_revenue', 'ebitda', 'reason_for_sale'):
            with self.subTest(field=field):
                self.assertEqual(self.who(field), {
                    'anonymous': False, 'stranger': False, 'connected': True, 'owner': True, 'staff': True,
                })

    def test_closing_a_deal_does_not_hide_the_figures(self):
        """The acquisition mirror of the funded-investor fix."""
        for status in ('CLOSED_PENDING', 'CLOSED'):
            with self.subTest(status=status):
                AcquisitionConnection.objects.filter(buyer=self.connected_buyer).update(status=status)
                self.assertTrue(can_view_profile_field(self.connected_user, self.seller, 'annual_revenue'))

    def test_a_pending_request_is_not_a_connection(self):
        AcquisitionConnection.objects.filter(buyer=self.connected_buyer).update(status='pending')
        self.assertFalse(can_view_profile_field(self.connected_user, self.seller, 'annual_revenue'))


class AnonymousSurfaceTests(_SellerCast):
    """The acquisition board and Pitch Videos both serve anonymous visitors."""

    def board(self):
        response = self.client.get(reverse('matchmaking:acquisition_bulletin_board'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode(errors='ignore')
        self.assertIn('Acme Widgets', body)  # the listing is on the page at all
        return body

    def test_board_shows_a_public_price(self):
        """Control: the default is unchanged -- buyers still browse by price."""
        self.assertTrue(_has(self.board(), PRICE))

    def test_board_hides_a_tightened_price(self):
        self.tighten(self.seller, 'asking_price', FIELD_CONNECTED)
        self.assertFalse(_has(self.board(), PRICE))

    def videos(self):
        SellerApplication.objects.filter(pk=self.seller.pk).update(
            pitch_video=SimpleUploadedFile('p.mp4', b'x', content_type='video/mp4').name
        )
        response = self.client.get(reverse('matchmaking:pitch_videos'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode(errors='ignore')

    def test_pitch_videos_show_a_public_price(self):
        """Control, and proof the seller card renders at all for this fixture."""
        body = self.videos()
        self.assertIn('Acme Widgets', body)
        self.assertTrue(_has(body, PRICE))

    def test_pitch_videos_hide_a_tightened_price(self):
        # Asserted, never skipped: a skip reports as "not failed" and would hide
        # a test that never reached its real assertion.
        self.tighten(self.seller, 'asking_price', FIELD_CONNECTED)
        body = self.videos()
        self.assertIn('Acme Widgets', body)
        self.assertFalse(_has(body, PRICE))


class SellerProfileTests(_SellerCast):

    def body(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse('accounts:profile', args=[self.seller_user.username]), follow=True)
        self.assertEqual(response.status_code, 200)
        text = response.content.decode(errors='ignore')
        self.assertIn('Acme Widgets', text)
        return text

    def test_a_stranger_does_not_see_revenue_ebitda_or_reason(self):
        body = self.body(self.stranger_user)
        self.assertFalse(_has(body, REVENUE))
        self.assertFalse(_has(body, EBITDA))
        self.assertNotIn('Owner retiring', body)

    def test_an_accepted_buyer_does(self):
        """Positive control on the same page."""
        body = self.body(self.connected_user)
        self.assertTrue(_has(body, REVENUE))
        self.assertTrue(_has(body, EBITDA))
        self.assertIn('Owner retiring', body)

    def test_anonymous_cannot_reach_the_profile_at_all(self):
        """profile() is login-required; this pins it for the seller half too."""
        response = self.client.get(reverse('accounts:profile', args=[self.seller_user.username]))
        self.assertEqual(response.status_code, 302)


class HiddenPriceDoesNotShapeMatchingTests(_SellerCast):
    """
    The invariant as the attack. Two sellers identical in everything a buyer
    can see, with different hidden asking prices; the buyer's budget sits so
    that one price is inside it and one outside. Nothing the buyer observes may
    differ between them.
    """

    INSIDE, OUTSIDE = 1_000_000, 9_000_000

    def setUp(self):
        super().setUp()
        self.twin_in = self._seller(User.objects.create_user('sfv_in', password='x'), 'Twin In', self.INSIDE)
        self.twin_out = self._seller(User.objects.create_user('sfv_out', password='x'), 'Twin Out', self.OUTSIDE)

    def signal(self, seller):
        from .match_components import deal_size_signal
        seller.refresh_from_db()
        result = deal_size_signal(seller, self.stranger_buyer)
        return (result.value, result.detail)

    def test_hidden_prices_produce_identical_signals(self):
        for twin in (self.twin_in, self.twin_out):
            self.tighten(twin, 'asking_price', FIELD_CONNECTED)
        self.assertEqual(self.signal(self.twin_in), self.signal(self.twin_out))

    def test_a_hidden_price_signals_exactly_like_an_unstated_one(self):
        """Anything distinguishable from 'not stated' would disclose a price exists."""
        self.tighten(self.twin_in, 'asking_price', FIELD_CONNECTED)
        unstated = self._seller(User.objects.create_user('sfv_unstated', password='x'), 'Unstated', 0)
        self.assertEqual(self.signal(self.twin_in), self.signal(unstated))

    def test_public_prices_do_differ(self):
        """Control: with prices public the signal genuinely depends on them."""
        self.assertNotEqual(self.signal(self.twin_in), self.signal(self.twin_out))

    def listed(self, **params):
        self.client.force_login(self.stranger_user)
        response = self.client.get(reverse('matchmaking:buyer_dashboard'), params)
        self.assertEqual(response.status_code, 200)
        return {m['seller'].pk for m in response.context['matches']}

    def test_the_max_price_filter_cannot_bisect_hidden_prices(self):
        for twin in (self.twin_in, self.twin_out):
            self.tighten(twin, 'asking_price', FIELD_CONNECTED)
        seen = set()
        for threshold in (500_000, 1_000_000, 5_000_000, 20_000_000):
            listed = self.listed(max_price=str(threshold))
            seen.add((self.twin_in.pk in listed, self.twin_out.pk in listed))
        self.assertEqual(len(seen), 1, 'a hidden price changed what the max-price filter returned')

    def test_the_max_price_filter_works_on_public_prices(self):
        """Control: the filter is live."""
        low = self.listed(max_price='2000000')
        high = self.listed(max_price='20000000')
        self.assertNotIn(self.twin_out.pk, low)
        self.assertEqual(self.twin_out.pk in high, self.twin_in.pk in high)


class AskZeldaSellerJSONTests(_SellerCast):
    """has_cim and asking_price in the Ask Zelda JSON."""

    def ask(self, user, constraints):
        self.client.force_login(user)
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction',
                        return_value={'constraints': constraints}):
            response = self.client.post(
                reverse('zelda_api:ask'), data=json.dumps({'q': 'businesses'}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        return response.json()['results']

    INDUSTRY = [{'field': 'industry', 'qualifier': 'exact', 'value': 'Manufacturing'}]

    def row(self, user, company='Acme Widgets'):
        return next(r for r in self.ask(user, self.INDUSTRY) if r['company_name'] == company)

    def test_has_cim_is_identical_whether_or_not_a_cim_exists(self):
        """
        The CIM endpoint answers 404 for 'none' and 'not allowed' alike; the
        JSON must not undo that for a buyer who may not download it.
        """
        without = self.row(self.stranger_user)['has_cim']
        SellerApplication.objects.filter(pk=self.seller.pk).update(cim_document='cim_documents/acme.pdf')
        with_cim = self.row(self.stranger_user)['has_cim']
        self.assertEqual(without, with_cim)

    def test_an_accepted_buyer_learns_a_cim_exists(self):
        """Control: the flag is live for someone who may download it."""
        SellerApplication.objects.filter(pk=self.seller.pk).update(cim_document='cim_documents/acme.pdf')
        self.assertTrue(self.row(self.connected_user)['has_cim'])

    def test_a_hidden_price_serialises_like_an_unstated_one(self):
        self.tighten(self.seller, 'asking_price', FIELD_CONNECTED)
        row = self.row(self.stranger_user)
        self.assertIn('asking_price', row)   # key present, as for an unstated price
        self.assertIsNone(row['asking_price'])

    def test_a_public_price_is_serialised(self):
        self.assertEqual(float(self.row(self.stranger_user)['asking_price']), float(PRICE))

    def appears(self, user, threshold):
        # A decoy priced below every threshold keeps the strict search
        # non-empty, so Ask Zelda never relaxes the constraint away. Without it
        # a single listing reappears through relaxation whatever its price, and
        # "present" stops meaning "matched the filter" -- which is how an
        # earlier version of the bisection test below passed while testing
        # nothing.
        if not SellerApplication.objects.filter(company_name='Decoy Co').exists():
            self._seller(User.objects.create_user('sfv_decoy', password='x'), 'Decoy Co', 100_000)
        results = self.ask(user, [{'field': 'asking_price', 'qualifier': 'at_most', 'value': threshold}])
        names = {r['company_name'] for r in results}
        self.assertIn('Decoy Co', names)  # the strict search really ran
        return 'Acme Widgets' in names

    def test_ask_zelda_cannot_bisect_a_hidden_price(self):
        self.tighten(self.seller, 'asking_price', FIELD_CONNECTED)
        seen = {self.appears(self.stranger_user, t) for t in (500_000, 1_000_000, 1_500_000, 5_000_000)}
        self.assertEqual(len(seen), 1, 'a hidden price was recoverable through Ask Zelda')

    def test_ask_zelda_filters_a_public_price(self):
        """Control."""
        self.assertFalse(self.appears(self.stranger_user, 500_000))
        self.assertTrue(self.appears(self.stranger_user, 5_000_000))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AskZeldaFounderBisectionTests(TestCase):
    """
    The founder half of the Ask Zelda hole, live on main since #86: filtering
    on raising_amount -- CONNECTED by default -- through natural language.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        founder_user = User.objects.create_user('azf_founder', password='x')
        self.founder = Application.objects.create(
            user=founder_user, company_name='Hidden Raise Co', founder_name='F', email='azf@t.com',
            description='test', sector='SaaS', stage='Seed', raising_amount=1_000_000,
            review_status='APPROVED',
        )
        self.searcher = User.objects.create_user('azf_searcher', password='x')

    def appears(self, threshold):
        if not Application.objects.filter(company_name='Decoy Raise Co').exists():
            decoy_user = User.objects.create_user('azf_decoy', password='x')
            Application.objects.create(
                user=decoy_user, company_name='Decoy Raise Co', founder_name='D', email='azfd@t.com',
                description='test', sector='SaaS', stage='Seed', raising_amount=100_000,
                review_status='APPROVED', field_visibility={'raising_amount': FIELD_PUBLIC},
            )
        self.client.force_login(self.searcher)
        constraints = [{'field': 'raising_amount', 'qualifier': 'at_most', 'value': threshold}]
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction',
                        return_value={'constraints': constraints}):
            response = self.client.post(
                reverse('zelda_api:ask'), data=json.dumps({'q': 'founders raising under'}),
                content_type='application/json',
            )
        # Founder results carry the company as `startup_name`, not
        # `company_name`; checking the wrong key made "absent" constant and the
        # bisection test pass vacuously -- its control is what caught it.
        names = {r.get('startup_name') for r in response.json()['results']}
        self.assertIn('Decoy Raise Co', names)  # the strict search really ran
        return 'Hidden Raise Co' in names

    def test_a_hidden_raise_cannot_be_bisected(self):
        seen = {self.appears(t) for t in (500_000, 900_000, 1_000_000, 1_100_000, 5_000_000)}
        self.assertEqual(len(seen), 1, 'a hidden raise amount was recoverable through Ask Zelda')

    def founder_name_served(self):
        self.founder.user.first_name, self.founder.user.last_name = 'Dana', 'Hidden'
        self.founder.user.save()
        self.client.force_login(self.searcher)
        constraints = [{'field': 'sector', 'qualifier': 'exact', 'value': 'SaaS'}]
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction',
                        return_value={'constraints': constraints}):
            response = self.client.post(
                reverse('zelda_api:ask'), data=json.dumps({'q': 'saas founders'}),
                content_type='application/json',
            )
        row = next(r for r in response.json()['results'] if r.get('startup_name') == 'Hidden Raise Co')
        return row['founder_name']

    def test_a_hidden_founder_name_is_not_served_from_the_account(self):
        """
        The name came from user.get_full_name(), not the founder_name field, so
        hiding the field did not hide the name. Default is CONNECTED.
        """
        self.assertNotIn('Hidden', self.founder_name_served())

    def test_a_public_founder_name_is_served(self):
        """Control."""
        Application.objects.filter(pk=self.founder.pk).update(field_visibility={'founder_name': FIELD_PUBLIC})
        self.assertIn('Hidden', self.founder_name_served())

    def test_a_public_raise_is_filterable(self):
        """Control."""
        Application.objects.filter(pk=self.founder.pk).update(field_visibility={'raising_amount': FIELD_PUBLIC})
        self.assertFalse(self.appears(500_000))
        self.assertTrue(self.appears(5_000_000))


class AcquisitionCsvTests(_SellerCast):

    def rows(self, user):
        user.match_buyer_profile.is_premium = True
        user.match_buyer_profile.save()
        self.client.force_login(user)
        body = self.client.get(reverse('matchmaking:export_acquisition_csv')).content.decode(errors='ignore')
        rows = list(csv.reader(io.StringIO(body)))
        return {r[0]: r for r in rows[1:] if r}

    def test_revenue_and_ebitda_are_withheld_from_a_stranger(self):
        row = self.rows(self.stranger_user)['Acme Widgets']
        self.assertEqual(row[4], '')   # Annual Revenue
        self.assertEqual(row[5], '')   # EBITDA

    def test_an_accepted_buyer_receives_them(self):
        """Control."""
        row = self.rows(self.connected_user)['Acme Widgets']
        self.assertNotEqual(row[4], '')
        self.assertNotEqual(row[5], '')

    def test_a_hidden_price_exports_exactly_like_an_unstated_one(self):
        self.tighten(self.seller, 'asking_price', FIELD_CONNECTED)
        self._seller(User.objects.create_user('sfv_nop', password='x'), 'No Price Co', 0)
        rows = self.rows(self.stranger_user)
        self.assertEqual(rows['Acme Widgets'][3], rows['No Price Co'][3])
        self.assertEqual(rows['Acme Widgets'][3], '')

    def test_a_public_price_exports(self):
        self.assertNotEqual(self.rows(self.stranger_user)['Acme Widgets'][3], '')
