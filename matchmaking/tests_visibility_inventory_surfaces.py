"""
Request-level proof for the surfaces the source guard found.

Per-field visibility (#83) certified eleven surfaces and missed five more that
rendered a founder's raise amount or revenue with no visibility check -- two of
them reachable anonymously. tests_visibility_source_guard now makes a missed
read fail at the source; this module proves each fixed surface actually
behaves, through a real request, for the three viewers that matter:

    anonymous            must not see a CONNECTED figure
    signed-in stranger   must not see it either -- an account is not consent
    accepted connection  must see it: the positive control on every surface

Every negative assertion is paired with that control on the SAME page for the
SAME founder, so an empty page cannot make an absence pass.
"""
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse

from .models import FIELD_CONNECTED, FIELD_PRIVATE, FIELD_PUBLIC, MatchFeedback
from .tests_field_visibility import RAISE, _Cast

AMOUNT = ('1,000,000', '1000000')


def _has_amount(text):
    return any(a in text for a in AMOUNT)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FounderBulletinBoardTests(_Cast):
    """Anonymous-reachable. Printed the raise amount regardless of the setting."""

    def body(self):
        response = self.client.get(reverse('matchmaking:bulletin_board'))
        self.assertEqual(response.status_code, 200)
        text = response.content.decode(errors='ignore')
        self.assertIn('FV Co', text)  # the founder is on the page at all
        return text

    def test_anonymous_does_not_see_a_connected_amount(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.assertFalse(_has_amount(self.body()))

    def test_signed_in_stranger_does_not_either(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.client.force_login(self.stranger_user)
        self.assertFalse(_has_amount(self.body()))

    def test_a_public_amount_is_shown_to_anonymous(self):
        """Positive control: the board renders this figure when permitted."""
        self.set_level('raising_amount', FIELD_PUBLIC)
        self.assertTrue(_has_amount(self.body()))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GlobalSearchResultsDisplayTests(_Cast):
    """
    #83 closed search's FILTER inference channel and missed that its results
    page PRINTS the figures. These search without a financial filter, so the
    founder is present, and assert on what the page shows about them.
    """

    def body(self):
        response = self.client.get(reverse('matchmaking:global_search'), {'industry': 'SaaS'})
        self.assertEqual(response.status_code, 200)
        text = response.content.decode(errors='ignore')
        self.assertIn('FV Co', text)
        return text

    def test_anonymous_search_hides_a_connected_amount(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.assertFalse(_has_amount(self.body()))

    def test_anonymous_search_hides_connected_revenue(self):
        self.set_level('current_revenue', FIELD_CONNECTED)
        self.assertNotIn('250000', self.body().replace(',', ''))

    def test_connected_investor_sees_it(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.client.force_login(self.connected_user)
        self.assertTrue(_has_amount(self.body()))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class InvestorShortlistTests(_Cast):
    """Liking a founder is not the founder accepting you."""

    def shortlist_for(self, investor_user, investor_profile):
        MatchFeedback.objects.create(
            user=investor_user, application=self.founder, investor=investor_profile, vote=1,
        )
        self.client.force_login(investor_user)
        response = self.client.get(reverse('matchmaking:investor_shortlist'))
        self.assertEqual(response.status_code, 200)
        text = response.content.decode(errors='ignore')
        self.assertIn('FV Co', text)
        return text

    def test_a_liking_stranger_does_not_see_a_connected_amount(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.assertFalse(_has_amount(self.shortlist_for(self.stranger_user, self.stranger_investor)))

    def test_an_accepted_investor_does(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.assertTrue(_has_amount(self.shortlist_for(self.connected_user, self.connected_investor)))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class StandaloneMemoTests(_Cast):
    """Whether the memo is shown is one question; which figures, another."""

    def body(self, user):
        self.client.force_login(user)
        response = self.client.get(
            reverse('matchmaking:standalone_memo', args=['fv-co']), follow=True
        )
        self.assertEqual(response.status_code, 200)
        text = response.content.decode(errors='ignore')
        self.assertIn('FV Co', text)
        return text

    def test_stranger_does_not_see_a_connected_amount(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.assertFalse(_has_amount(self.body(self.stranger_user)))

    def test_accepted_investor_does(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.assertTrue(_has_amount(self.body(self.connected_user)))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ZeldaAdvantagePayloadTests(_Cast):
    """
    founder_data_json was gated on an ACCEPTED connection but ignored PRIVATE,
    so a connected investor still received figures hidden from everyone.
    """

    def payload(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]), follow=True)
        return response.context.get('founder_data_json') if response.context else None

    def test_connected_investor_gets_the_payload_when_all_figures_are_shared(self):
        """Positive control: the widget is live for an authorised viewer."""
        self.assertIsNotNone(self.payload(self.connected_user))

    def test_a_private_figure_withholds_the_whole_payload(self):
        self.set_level('current_revenue', FIELD_PRIVATE)
        self.assertIsNone(self.payload(self.connected_user))

    def test_the_owner_still_gets_it(self):
        self.set_level('current_revenue', FIELD_PRIVATE)
        self.assertIsNotNone(self.payload(self.founder_user))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MatchReasonsTests(_Cast):
    """
    "Raise size fits your check range" fired only when the amount sat inside a
    range the investor controls -- so re-running with a moved range bisected it.
    """

    def reasons(self, investor_profile):
        from zelda_api.views import _match_reasons
        investor_profile.ticket_size_min = 500_000
        investor_profile.ticket_size_max = 2_000_000
        investor_profile.save()
        return _match_reasons(self.founder, investor_profile)

    def test_the_raise_reason_is_withheld_from_a_stranger(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.assertNotIn('Raise size fits your check range', self.reasons(self.stranger_investor))

    def test_a_public_amount_still_produces_the_reason(self):
        """Positive control: the reason is live when the amount is disclosed."""
        self.set_level('raising_amount', FIELD_PUBLIC)
        self.assertIn('Raise size fits your check range', self.reasons(self.stranger_investor))

    def test_an_accepted_investor_gets_it(self):
        self.set_level('raising_amount', FIELD_CONNECTED)
        self.assertIn('Raise size fits your check range', self.reasons(self.connected_investor))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class HiddenRaiseDoesNotDecideDiscoveryTests(_Cast):
    """
    The invariant, stated as the attack:

        Two founders identical in everything an investor can see, whose private
        raise amounts differ. An investor who can see neither amount must get
        identical discoverability for both -- otherwise the amount is being
        read back through whether the founder appears.

    The investor's smallest cheque sits BETWEEN the two amounts. Before the fix
    the hard filter excluded the founder whose whole round was smaller than
    that cheque and kept the other, so moving ticket_size_min and watching who
    appeared bisected both amounts.
    """

    SMALL, LARGE, CHEQUE = 200_000, 5_000_000, 1_000_000

    def setUp(self):
        super().setUp()
        self.small = self._twin('fv_twin_small', 'Small Co', self.SMALL)
        self.large = self._twin('fv_twin_large', 'Large Co', self.LARGE)
        self.stranger_investor.ticket_size_min = self.CHEQUE
        self.stranger_investor.investment_stage = 'Seed'
        self.stranger_investor.save()

    def _twin(self, username, company, amount):
        from .models import Application
        user = User.objects.create_user(username, password='x')
        return Application.objects.create(
            user=user, company_name=company, founder_name='T', email=f'{username}@t.com',
            description='We build things.', sector='SaaS', stage='Seed',
            geography='San Diego CA', raising_amount=amount, review_status='APPROVED',
        )

    def _passes(self, founder):
        from .utils import passes_hard_filters
        return passes_hard_filters(founder, self.stranger_investor)

    def test_hidden_amounts_do_not_change_eligibility(self):
        self.assertEqual(self._passes(self.small), self._passes(self.large),
                         'eligibility differs between twins whose only difference is a hidden amount')
        self.assertTrue(self._passes(self.small), 'a hidden raise must be skipped, not held against the founder')

    def test_visible_amounts_still_filter(self):
        """
        Positive control. Without it, "both pass" is also what a filter that
        never runs looks like. With the amounts public, the cheque that cannot
        fit the small round must still exclude it.
        """
        for founder in (self.small, self.large):
            founder.field_visibility = {'raising_amount': FIELD_PUBLIC}
            founder.save()
        self.assertFalse(self._passes(self.small))
        self.assertTrue(self._passes(self.large))

    def test_the_bulletin_board_lists_both_twins(self):
        """
        The same invariant at the request boundary, asserted on the listing
        itself -- the `pitches` the hard filter produced -- rather than on the
        page text. The board has other sections that name companies without
        applying hard filters, so a founder excluded from the listing can still
        appear elsewhere on the page; an earlier version of this test searched
        the whole page and passed with the leak restored.
        """
        self.client.force_login(self.stranger_user)
        response = self.client.get(reverse('matchmaking:bulletin_board'))
        listed = {p.pk for p in response.context['pitches']}
        self.assertIn(self.large.pk, listed)  # the listing is live for this investor
        self.assertIn(self.small.pk, listed, 'a hidden raise amount excluded a founder from the listing')

    def test_a_cached_verdict_does_not_survive_the_founder_hiding_it(self):
        """
        The cache key carries the visibility decision. A result computed while
        the amount was public must not be served once the founder hides it.
        """
        self.small.field_visibility = {'raising_amount': FIELD_PUBLIC}
        self.small.save()
        self.assertFalse(self._passes(self.small))   # cached: excluded
        self.small.field_visibility = {'raising_amount': FIELD_CONNECTED}
        self.small.save()
        self.assertTrue(self._passes(self.small), 'a stale cached exclusion outlived the founder hiding the amount')
