"""
What a founder discloses, to whom, field by field.

Before this, a founder's raise amount, revenue, prior funding and use of funds
were visible to **any signed-in account** -- creating an account was the only
gate -- and `raising_amount` plus `current_revenue` also went out as JSON to
Enterprise API key holders and as bulk CSV to any premium investor, for every
founder matching a filter, with no connection to any of them.

Three levels replace that. PUBLIC is anyone; CONNECTED is a party the founder
has actually accepted; PRIVATE is the founder alone. Deliberately not a role
test: holding an investor account is not authorization, because the founder
authorized a *person*, not a category.

The tests here are organised around the two ways a value escapes:

    disclosure   the value appears in a response
    inference    the value does not appear, but product behaviour reveals it

The second is the one a display-only fix misses. If `raising_amount` is hidden
but `?capital=` still filters on it, an unconnected viewer can bisect the
filter -- 500k no, 1M yes, 750k no -- and recover the number exactly. So every
level is proven through real requests against real surfaces, never against the
authority function alone: a correct predicate that a serialiser ignores is
still a leak.
"""
from unittest import mock

from django.contrib.auth.models import AnonymousUser, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Application,
    Connection,
    FIELD_CONNECTED,
    FIELD_PRIVATE,
    FIELD_PUBLIC,
    InvestorApplication,
    NEW_PROFILE_FIELD_VISIBILITY,
    can_view_profile_field,
    profile_field_level,
    validate_profile_field_visibility,
)
from .tests import _mock_embedding_generation

RAISE = 1_000_000
REVENUE = 250_000


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class _Cast(TestCase):
    """Founder, staff, a connected investor, an unconnected investor, anonymous."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('fv_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='FV Co', founder_name='Dana Founder',
            email='fv@t.com', description='We build things.', sector='SaaS', stage='Seed',
            geography='San Diego CA', raising_amount=RAISE, current_revenue=REVENUE,
            reason_for_capital='Hiring two engineers.', review_status='APPROVED',
        )
        self.staff_user = User.objects.create_user('fv_staff', password='x', is_staff=True)

        self.connected_user = User.objects.create_user('fv_connected', password='x')
        self.connected_investor = InvestorApplication.objects.create(
            user=self.connected_user, full_name='C', company_name='ConnectedFund',
            email='fvc@t.com', investment_focus='SaaS', investment_stage='Seed',
        )
        Connection.objects.create(
            investor=self.connected_investor, founder=self.founder,
            status='ACCEPTED', initiated_by='INVESTOR',
        )

        self.stranger_user = User.objects.create_user('fv_stranger', password='x')
        self.stranger_investor = InvestorApplication.objects.create(
            user=self.stranger_user, full_name='S', company_name='StrangerFund',
            email='fvs@t.com', investment_focus='SaaS', investment_stage='Seed',
        )

    def set_level(self, field, level):
        self.founder.field_visibility = dict(self.founder.field_visibility or {})
        self.founder.field_visibility[field] = level
        self.founder.save()


class AuthorityMatrixTests(_Cast):
    """The matrix, at the authority. Surfaces are proven separately below."""

    def _who_can_see(self, field):
        return {
            'anonymous': can_view_profile_field(AnonymousUser(), self.founder, field),
            'stranger': can_view_profile_field(self.stranger_user, self.founder, field),
            'connected': can_view_profile_field(self.connected_user, self.founder, field),
            'owner': can_view_profile_field(self.founder_user, self.founder, field),
            'staff': can_view_profile_field(self.staff_user, self.founder, field),
        }

    def test_public_is_visible_to_everyone(self):
        self.set_level('raising_amount', FIELD_PUBLIC)
        self.assertEqual(self._who_can_see('raising_amount'), {
            'anonymous': True, 'stranger': True, 'connected': True, 'owner': True, 'staff': True,
        })

    def test_connected_excludes_anonymous_and_strangers(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.assertEqual(self._who_can_see('raising_amount'), {
            'anonymous': False, 'stranger': False, 'connected': True, 'owner': True, 'staff': True,
        })

    def test_private_excludes_even_a_connected_investor(self):
        self.set_level('raising_amount', FIELD_PRIVATE)
        self.assertEqual(self._who_can_see('raising_amount'), {
            'anonymous': False, 'stranger': False, 'connected': False, 'owner': True, 'staff': True,
        })

    def test_company_name_is_not_controllable(self):
        self.assertTrue(can_view_profile_field(AnonymousUser(), self.founder, 'company_name'))

    def test_holding_an_investor_account_is_not_authorization(self):
        """The distinction the feature exists for: role is not permission."""
        self.set_level('current_revenue', FIELD_CONNECTED)
        self.assertIsNotNone(getattr(self.stranger_user, 'match_investor_profile', None))
        self.assertFalse(can_view_profile_field(self.stranger_user, self.founder, 'current_revenue'))


class StoredValueTests(_Cast):
    """Absent or malformed must never read as PUBLIC."""

    def test_an_empty_dict_already_closes_financial_fields(self):
        self.founder.field_visibility = {}
        self.founder.save()
        self.assertEqual(profile_field_level(self.founder, 'raising_amount'), FIELD_CONNECTED)
        self.assertFalse(can_view_profile_field(self.stranger_user, self.founder, 'raising_amount'))

    def test_a_malformed_stored_value_falls_back_to_the_default_not_public(self):
        # Written straight to the column, bypassing save() validation, as a
        # corrupt row or a bad data migration would.
        Application.objects.filter(pk=self.founder.pk).update(field_visibility={'raising_amount': 'sure'})
        self.founder.refresh_from_db()
        self.assertEqual(profile_field_level(self.founder, 'raising_amount'), FIELD_CONNECTED)
        self.assertFalse(can_view_profile_field(self.stranger_user, self.founder, 'raising_amount'))

    def test_a_non_dict_stored_value_does_not_crash_or_open(self):
        Application.objects.filter(pk=self.founder.pk).update(field_visibility=['nonsense'])
        self.founder.refresh_from_db()
        self.assertFalse(can_view_profile_field(self.stranger_user, self.founder, 'raising_amount'))

    def test_every_financial_field_defaults_to_connected(self):
        for field in ('raising_amount', 'current_revenue', 'prior_amount_raised',
                      'monthly_burn_rate', 'reason_for_capital', 'founder_name'):
            self.assertEqual(NEW_PROFILE_FIELD_VISIBILITY[field], FIELD_CONNECTED, field)

    def test_pitch_deck_defaults_to_public_so_nothing_changes_for_it(self):
        self.assertEqual(NEW_PROFILE_FIELD_VISIBILITY['pitch_deck'], FIELD_PUBLIC)


class ValidationTests(_Cast):
    """A typo must fail loudly, not store a setting that does nothing."""

    def test_an_unknown_field_name_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_profile_field_visibility({'raising_amont': FIELD_PRIVATE})

    def test_an_unknown_level_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_profile_field_visibility({'raising_amount': 'SECRET'})

    def test_saving_a_bad_value_raises(self):
        self.founder.field_visibility = {'not_a_field': FIELD_PRIVATE}
        with self.assertRaises(ValidationError):
            self.founder.save()

    def test_an_empty_value_is_allowed(self):
        validate_profile_field_visibility({})
        validate_profile_field_visibility(None)


class ProfilePageTests(_Cast):
    """Read paths 1, 3 and 4 -- the rendered page, per viewer."""

    def profile_url(self):
        return reverse('accounts:profile', args=[self.founder_user.username])

    def test_connected_investor_sees_a_connected_field(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.client.force_login(self.connected_user)
        response = self.client.get(self.profile_url(), follow=True)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode(errors='ignore')
        self.assertIn('FV Co', body)  # positive control: the page really rendered
        self.assertIn('1,000,000', body)

    def test_signed_in_stranger_does_not(self):
        """This is the behaviour change: today any signed-in account sees it."""
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.client.force_login(self.stranger_user)
        response = self.client.get(self.profile_url(), follow=True)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode(errors='ignore')
        self.assertIn('FV Co', body)
        self.assertNotIn('1,000,000', body)

    def test_private_is_hidden_from_a_connected_investor(self):
        self.set_level('raising_amount', FIELD_PRIVATE)
        self.client.force_login(self.connected_user)
        response = self.client.get(self.profile_url(), follow=True)
        self.assertNotIn('1,000,000', response.content.decode(errors='ignore'))

    def test_the_founder_always_sees_their_own(self):
        self.set_level('raising_amount', FIELD_PRIVATE)
        self.client.force_login(self.founder_user)
        response = self.client.get(self.profile_url(), follow=True)
        self.assertIn('1,000,000', response.content.decode(errors='ignore'))

    def test_hiding_the_founder_name_hides_it(self):
        self.set_level('founder_name', FIELD_PRIVATE)
        self.client.force_login(self.stranger_user)
        response = self.client.get(self.profile_url(), follow=True)
        body = response.content.decode(errors='ignore')
        self.assertIn('FV Co', body)
        self.assertNotIn('Dana Founder', body)


class FilterInferenceTests(_Cast):
    """
    Read path 6. The attack, not the fix.

    A hidden value must not be recoverable by watching whether the founder
    appears as a threshold moves across it. Asserted by sweeping thresholds
    either side of the true amount: the answer must be constant.
    """

    def setUp(self):
        super().setUp()
        # A control founder with the SAME raise amount, disclosed publicly.
        # Without it, "the hidden founder never appears" passes just as well
        # when search is broken and returns nothing at all -- the test would
        # then be asserting that a dead page leaks no data, which is true and
        # worthless. The control proves filtering genuinely works on this data.
        self.control_user = User.objects.create_user('fv_control', password='x')
        self.control = Application.objects.create(
            user=self.control_user, company_name='Control Co', founder_name='Kim Control',
            email='fvk@t.com', description='We build things.', sector='SaaS', stage='Seed',
            geography='San Diego CA', raising_amount=RAISE, current_revenue=REVENUE,
            review_status='APPROVED',
            field_visibility={'raising_amount': FIELD_PUBLIC, 'current_revenue': FIELD_PUBLIC},
        )

    def search(self, **params):
        return self.client.get(reverse('matchmaking:global_search'), params)

    def appears(self, response, name='FV Co'):
        return name in response.content.decode(errors='ignore')

    def test_a_stranger_cannot_bisect_a_hidden_raise_amount(self):
        """
        The attack itself.

        Two founders, same raise amount. One discloses it publicly, one only to
        accepted connections. For an unconnected viewer, sweeping the threshold
        across the true value must move the control in and out of the results
        while never moving the hidden one -- proving the filter is live and
        that the hidden founder is nonetheless unreadable through it.
        """
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.client.force_login(self.stranger_user)

        hidden_seen, control_seen = set(), set()
        for threshold in (500_000, 900_000, 1_000_000, 1_100_000, 5_000_000):
            response = self.search(capital=str(threshold))
            hidden_seen.add(self.appears(response))
            control_seen.add(self.appears(response, 'Control Co'))

        self.assertEqual(len(control_seen), 2,
                         'the filter never changed anything, so this proves nothing')
        self.assertEqual(len(hidden_seen), 1,
                         'presence varied with the threshold, leaking the hidden value')

    def test_a_connected_investor_still_gets_real_filtering(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.client.force_login(self.connected_user)
        self.assertTrue(self.appears(self.search(capital='5000000')))
        self.assertFalse(self.appears(self.search(capital='500000')))

    def test_a_public_amount_filters_for_everyone(self):
        self.set_level('raising_amount', FIELD_PUBLIC)
        self.client.force_login(self.stranger_user)
        self.assertTrue(self.appears(self.search(capital='5000000')))
        self.assertFalse(self.appears(self.search(capital='500000')))

    def test_a_stranger_cannot_bisect_hidden_revenue(self):
        self.set_level('current_revenue', FIELD_CONNECTED)
        self.client.force_login(self.stranger_user)
        seen = {self.appears(self.search(revenue=str(t)))
                for t in (1_000, 250_000, 500_000)}
        self.assertEqual(len(seen), 1)

    def test_the_founder_still_appears_in_an_unfiltered_search(self):
        """Exclusion applies to the filter, not to existence."""
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.client.force_login(self.stranger_user)
        self.assertTrue(self.appears(self.search(industry='SaaS')))

    def test_nothing_announces_that_results_were_withheld(self):
        """A count of hidden results would disclose who chose privacy."""
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.client.force_login(self.stranger_user)
        body = self.search(capital='500000').content.decode(errors='ignore').lower()
        for leak in ('hidden because', 'results withheld', 'private raise', 'excluded because'):
            self.assertNotIn(leak, body)


class StaffForwardEmailTests(_Cast):
    """
    The one surface that PUSHES a founder's figures to someone who did not ask.

    Staff pick a founder and an investor; the investor is emailed immediately,
    and the connection created is `pending` -- so the recipient is, by
    definition, not someone the founder has accepted. Anything limited to
    accepted connections must therefore not be in that email. Staff choosing
    the recipient does not widen what the founder agreed to share.

    Asserted against the rendered message body, not the authority: a correct
    predicate that the template ignores still sends the email.
    """

    def forward_to(self, investor):
        from django.test import RequestFactory
        from .admin import forward_to_investor

        request = RequestFactory().post('/', {'apply': '1', 'investor': str(investor.id)})
        request.user = self.staff_user
        forward_to_investor(
            mock.Mock(), request, Application.objects.filter(pk=self.founder.pk)
        )
        return mail.outbox[-1].body

    def test_a_connected_field_does_not_go_out_to_an_unaccepted_investor(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        body = self.forward_to(self.stranger_investor)
        self.assertIn('FV Co', body)  # positive control: the email really rendered
        self.assertNotIn('1000000', body.replace(',', ''))

    def test_a_public_field_does_go_out(self):
        """Control: proves the email path is live and renders these figures."""
        self.set_level('raising_amount', FIELD_PUBLIC)
        body = self.forward_to(self.stranger_investor)
        self.assertIn('1000000', body.replace(',', ''))

    def test_use_of_funds_is_withheld_when_private(self):
        self.set_level('reason_for_capital', FIELD_PRIVATE)
        body = self.forward_to(self.stranger_investor)
        self.assertIn('FV Co', body)
        self.assertNotIn('Hiring two engineers', body)

    def test_an_accepted_investor_still_receives_connected_fields(self):
        """Forwarding to someone already accepted discloses what they may see."""
        self.set_level('raising_amount', FIELD_CONNECTED)
        body = self.forward_to(self.connected_investor)
        self.assertIn('1000000', body.replace(',', ''))

    def test_the_founder_name_is_withheld_when_private(self):
        self.set_level('founder_name', FIELD_PRIVATE)
        body = self.forward_to(self.stranger_investor)
        self.assertNotIn('Dana Founder', body)


class PublicDirectoryTests(_Cast):
    """
    The directory URL states sector, stage and location, so being listed there
    discloses all three regardless of what the template prints. A founder who
    keeps any of them below PUBLIC is left out entirely.
    """

    def directory_url(self):
        return reverse('growth:founder_directory', args=['saas', 'seed', 'san-diego-ca'])

    def test_a_founder_with_all_three_public_is_listed(self):
        """Positive control: the page works and this founder matches it."""
        response = self.client.get(self.directory_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn('FV Co', response.content.decode(errors='ignore'))

    def test_hiding_the_sector_removes_the_founder_from_the_directory(self):
        self.set_level('sector', FIELD_CONNECTED)
        response = self.client.get(self.directory_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('FV Co', response.content.decode(errors='ignore'))

    def test_hiding_the_location_removes_the_founder(self):
        self.set_level('geography', FIELD_PRIVATE)
        self.assertNotIn('FV Co', self.client.get(self.directory_url()).content.decode(errors='ignore'))

    def test_hiding_the_stage_removes_the_founder(self):
        self.set_level('stage', FIELD_PRIVATE)
        self.assertNotIn('FV Co', self.client.get(self.directory_url()).content.decode(errors='ignore'))

    def test_the_sitemap_stops_advertising_the_combination(self):
        """A URL for a page they are absent from would advertise it for them."""
        before = self.client.get(reverse('sitemap')).content.decode(errors='ignore')
        self.assertIn('saas', before.lower())
        self.set_level('sector', FIELD_PRIVATE)
        after = self.client.get(reverse('sitemap')).content.decode(errors='ignore')
        self.assertNotIn('/startups/saas/seed/san-diego-ca/', after)


class ICMemoTests(_Cast):
    """
    The memo's audience is already owner, staff, or an ACCEPTED connection, so
    a CONNECTED field belongs in it. A PRIVATE one does not.
    """

    def context_for(self, viewer):
        from zelda_api.ic_memo import build_ic_memo_context
        return build_ic_memo_context(self.founder, viewer=viewer)['financials']

    def test_a_connected_field_reaches_the_connected_audience(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.assertEqual(self.context_for(self.connected_user)['raising_amount'], RAISE)

    def test_a_private_field_does_not(self):
        self.set_level('raising_amount', FIELD_PRIVATE)
        self.assertIsNone(self.context_for(self.connected_user)['raising_amount'])

    def test_the_owner_still_sees_their_own_private_field(self):
        self.set_level('raising_amount', FIELD_PRIVATE)
        self.assertEqual(self.context_for(self.founder_user)['raising_amount'], RAISE)

    def test_without_a_viewer_private_is_still_stripped(self):
        """A caller that forgets the viewer must not get the permissive answer."""
        from zelda_api.ic_memo import build_ic_memo_context
        self.set_level('raising_amount', FIELD_PRIVATE)
        self.assertIsNone(build_ic_memo_context(self.founder)['financials']['raising_amount'])

    def test_the_rendered_memo_says_not_disclosed(self):
        """Proven at the output, not the context dict."""
        from zelda_api.ic_memo import build_ic_memo_context, render_ic_memo_markdown
        self.set_level('raising_amount', FIELD_PRIVATE)
        md = render_ic_memo_markdown(build_ic_memo_context(self.founder, viewer=self.connected_user))
        self.assertIn('Raising: not disclosed', md)
        self.assertNotIn('1,000,000', md)


class ExploreFeedTests(_Cast):
    """
    Explore serves anonymous visitors, so it is a PUBLIC disclosure surface.
    founder_name defaults to CONNECTED, which means the anonymous card shows a
    company without the person behind it unless the founder opens it.
    """

    def setUp(self):
        super().setUp()
        from .models import ProfileVideo
        # role is derived from which owner FK is set, not assignable.
        self.video = ProfileVideo.objects.create(
            founder=self.founder, kind=ProfileVideo.KIND_ELEVATOR_PITCH,
            caption='Our pitch',
            video=SimpleUploadedFile('p.mp4', b'x', content_type='video/mp4'),
        )

    def body(self):
        response = self.client.get(reverse('explore'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode(errors='ignore')

    def test_the_card_appears_at_all(self):
        """Positive control: without this the absence assertions prove nothing."""
        self.assertIn('FV Co', self.body())

    def test_founder_name_is_withheld_from_anonymous_by_default(self):
        body = self.body()
        self.assertIn('FV Co', body)
        self.assertNotIn('Dana Founder', body)

    def test_a_founder_can_make_their_name_public(self):
        self.set_level('founder_name', FIELD_PUBLIC)
        self.assertIn('Dana Founder', self.body())

    def test_a_hidden_sector_is_not_in_the_card_context(self):
        self.set_level('sector', FIELD_PRIVATE)
        body = self.body()
        self.assertIn('FV Co', body)
        self.assertNotIn('SaaS', body)


class SimilarStartupsTests(_Cast):
    """
    "Seeking $X" is the raise amount in a different costume.

    Similarity needs both profiles to carry a description_vector, and the
    suite mocks embedding generation to [] -- so without setting the vectors
    explicitly the page renders an empty list and every absence assertion here
    passes against nothing at all. A mutation of the authority proved exactly
    that about an earlier version of this class.
    """

    VECTOR = [1.0, 0.0, 0.0]

    def setUp(self):
        super().setUp()
        Application.objects.filter(pk=self.founder.pk).update(description_vector=self.VECTOR)
        self.founder.refresh_from_db()
        self.similar_user = User.objects.create_user('fv_similar', password='x')
        self.similar = Application.objects.create(
            user=self.similar_user, company_name='Similar Co', founder_name='S Founder',
            email='sim@t.com', description='We build things.', sector='SaaS', stage='Seed',
            geography='San Diego CA', raising_amount=RAISE, review_status='APPROVED',
        )
        Application.objects.filter(pk=self.similar.pk).update(description_vector=self.VECTOR)

    def body(self):
        self.client.force_login(self.stranger_user)
        response = self.client.get(
            reverse('matchmaking:find_similar_startups', args=[self.founder.id]), follow=True
        )
        self.assertEqual(response.status_code, 200)
        return response.content.decode(errors='ignore')

    def set_similar_level(self, level):
        # .update(), not .save(): the post_save signal regenerates
        # description_vector, and the suite mocks that generator to [], so
        # saving here would wipe the vector this page needs and silently empty
        # the result list -- which is exactly how the earlier version of these
        # tests came to assert nothing at all.
        Application.objects.filter(pk=self.similar.pk).update(
            field_visibility={'raising_amount': level}, description_vector=self.VECTOR
        )

    def test_the_similar_company_is_listed_at_all(self):
        """Positive control. Without it the assertions below prove nothing."""
        self.set_similar_level(FIELD_PUBLIC)
        self.assertIn('Similar Co', self.body())

    def test_a_public_amount_produces_the_seeking_line(self):
        """Control for the derived display: it renders when permitted."""
        self.set_similar_level(FIELD_PUBLIC)
        self.assertIn('1,000,000', self.body())

    def test_a_stranger_gets_no_derived_seeking_line(self):
        self.set_similar_level(FIELD_CONNECTED)
        body = self.body()
        self.assertIn('Similar Co', body)
        self.assertNotIn('1,000,000', body)

    def test_a_private_amount_is_withheld_too(self):
        self.set_similar_level(FIELD_PRIVATE)
        body = self.body()
        self.assertIn('Similar Co', body)
        self.assertNotIn('1,000,000', body)


class DigestBucketTests(_Cast):
    """A derived representation inherits the visibility of its source field."""

    def bucket_for(self, investor_profile):
        from .digest import build_investor_digest_card
        from .match_score import evaluate_venture_match
        card = build_investor_digest_card(investor_profile)
        return card['raising_bucket'] if card else None

    def test_a_bucket_is_not_built_from_a_hidden_amount(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        from .models import visible_profile_fields
        shown = visible_profile_fields(self.stranger_user, self.founder, ('raising_amount',))
        self.assertNotIn('raising_amount', shown)

    def test_a_connected_investor_may_receive_the_bucket(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        from .models import visible_profile_fields
        shown = visible_profile_fields(self.connected_user, self.founder, ('raising_amount',))
        self.assertIn('raising_amount', shown)

    def test_a_private_amount_is_withheld_from_everyone_but_the_owner(self):
        self.set_level('raising_amount', FIELD_PRIVATE)
        from .models import visible_profile_fields
        self.assertNotIn('raising_amount', visible_profile_fields(self.connected_user, self.founder, ('raising_amount',)))
        self.assertIn('raising_amount', visible_profile_fields(self.founder_user, self.founder, ('raising_amount',)))


class FounderControlsTests(_Cast):
    """The page where a founder actually sets these."""

    URL_NAME = 'usersettings:edit_founder_profile'

    def form_payload(self, **overrides):
        """The profile form's required fields, plus visibility selections."""
        payload = {
            'company_name': self.founder.company_name,
            'founder_name': self.founder.founder_name,
            'email': self.founder.email,
            'description': self.founder.description,
            'sector': self.founder.sector,
            'stage': self.founder.stage,
            'raising_amount': self.founder.raising_amount,
            'prior_amount_raised': self.founder.prior_amount_raised or 0,
            'years_in_business': self.founder.years_in_business or 0,
            'geography': self.founder.geography,
        }
        payload.update(overrides)
        return payload

    def test_the_page_offers_a_control_for_every_governed_field(self):
        self.client.force_login(self.founder_user)
        body = self.client.get(reverse(self.URL_NAME), follow=True).content.decode(errors='ignore')
        for name in NEW_PROFILE_FIELD_VISIBILITY:
            self.assertIn(f'visibility__{name}', body, name)

    def test_the_page_shows_the_level_currently_in_force(self):
        """Including the declared default, where the founder has chosen nothing."""
        self.client.force_login(self.founder_user)
        body = self.client.get(reverse(self.URL_NAME), follow=True).content.decode(errors='ignore')
        self.assertIn('value="CONNECTED" selected', body)

    def test_a_founder_can_open_a_field(self):
        self.client.force_login(self.founder_user)
        self.client.post(
            reverse(self.URL_NAME),
            self.form_payload(**{'visibility__raising_amount': FIELD_PUBLIC}),
            follow=True,
        )
        self.founder.refresh_from_db()
        self.assertEqual(profile_field_level(self.founder, 'raising_amount'), FIELD_PUBLIC)
        self.assertTrue(can_view_profile_field(self.stranger_user, self.founder, 'raising_amount'))

    def test_a_founder_can_close_a_field_completely(self):
        self.client.force_login(self.founder_user)
        self.client.post(
            reverse(self.URL_NAME),
            self.form_payload(**{'visibility__reason_for_capital': FIELD_PRIVATE}),
            follow=True,
        )
        self.founder.refresh_from_db()
        self.assertFalse(can_view_profile_field(self.connected_user, self.founder, 'reason_for_capital'))

    def test_a_crafted_level_is_dropped_rather_than_stored(self):
        """A hand-made POST must not reach the model validator and 500 the page."""
        self.client.force_login(self.founder_user)
        response = self.client.post(
            reverse(self.URL_NAME),
            self.form_payload(**{'visibility__raising_amount': 'EVERYONE'}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.founder.refresh_from_db()
        self.assertEqual(profile_field_level(self.founder, 'raising_amount'), FIELD_CONNECTED)

    def test_a_crafted_field_name_is_ignored(self):
        self.client.force_login(self.founder_user)
        self.client.post(
            reverse(self.URL_NAME),
            self.form_payload(**{'visibility__is_staff': FIELD_PUBLIC}),
            follow=True,
        )
        self.founder.refresh_from_db()
        self.assertNotIn('is_staff', self.founder.field_visibility or {})

    def test_another_founder_cannot_set_visibility_on_this_profile(self):
        """The editor works on request.user's own profile, never one named in a POST."""
        other = User.objects.create_user('fv_other_founder', password='x')
        Application.objects.create(
            user=other, company_name='Other Co', founder_name='O', email='o2@t.com',
            description='d', sector='SaaS', stage='Seed', review_status='APPROVED',
        )
        self.client.force_login(other)
        self.client.post(
            reverse(self.URL_NAME),
            self.form_payload(**{'visibility__raising_amount': FIELD_PUBLIC}),
            follow=True,
        )
        self.founder.refresh_from_db()
        self.assertEqual(profile_field_level(self.founder, 'raising_amount'), FIELD_CONNECTED)
