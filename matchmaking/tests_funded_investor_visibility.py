"""
An investor does not lose sight of a founder's figures by funding them.

The founder Connection runs ACCEPTED -> FUNDED_PENDING -> FUNDED. Field
visibility treated only ACCEPTED as connected -- it copied can_view_data_room's
rule rather than the deal workspace's -- so the moment an investor marked a deal
funded, every CONNECTED field that founder had shared with them disappeared,
while the deal workspace itself stayed open. The investor who funded the
company was left unable to see its raise amount.

All three visibility paths hardcoded ACCEPTED, so all three are exercised: a
fix to one alone would leave a funded investor seeing a figure on one page and
not another.

    per-object   can_view_profile_field       -> the founder profile page
    bulk         attach_visible_fields        -> the bulletin board
    filter       restrict_queryset_for_field_filter -> a ?capital= search

ACCEPTED is the control on every path. The negative cases -- a pending request
and a declined one -- prove the set grew by exactly the two post-acceptance
states rather than becoming "any connection at all".
"""
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse

from .models import (
    Connection, ESTABLISHED_FOUNDER_CONNECTION_STATES, FIELD_CONNECTED,
    InvestorApplication, can_view_deal_workspace, can_view_profile_field,
)
from .tests_field_visibility import _Cast

AMOUNT = ('1,000,000', '1000000')
RETAINING = ('ACCEPTED', 'FUNDED_PENDING', 'FUNDED')
NOT_RETAINING = ('pending', 'DECLINED')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FundedInvestorKeepsVisibilityTests(_Cast):

    def setUp(self):
        super().setUp()
        self.set_level('raising_amount', FIELD_CONNECTED)

    def investor_with(self, status):
        user = User.objects.create_user(f'fiv_{status.lower()}', password='x')
        investor = InvestorApplication.objects.create(
            user=user, full_name='I', company_name=f'{status} Fund', email=f'{status}@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        connection = Connection.objects.create(
            investor=investor, founder=self.founder, status=status, initiated_by='INVESTOR',
        )
        return user, connection

    # -- per-object path -----------------------------------------------------

    def profile_shows_amount(self, user):
        self.client.force_login(user)
        response = self.client.get(
            reverse('accounts:profile', args=[self.founder_user.username]), follow=True
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode(errors='ignore')
        self.assertIn('FV Co', body)  # the page really rendered for this viewer
        return any(a in body for a in AMOUNT)

    def test_profile_page_across_the_lifecycle(self):
        for status in RETAINING:
            with self.subTest(status=status):
                user, _ = self.investor_with(status)
                self.assertTrue(self.profile_shows_amount(user),
                                f'a {status} investor lost sight of the raise amount')

    def test_profile_page_still_hides_it_before_acceptance(self):
        for status in NOT_RETAINING:
            with self.subTest(status=status):
                user, _ = self.investor_with(status)
                self.assertFalse(self.profile_shows_amount(user))

    # -- bulk path -------------------------------------------------------------

    def board_shows_amount(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse('matchmaking:bulletin_board'))
        self.assertEqual(response.status_code, 200)
        founder = next(p for p in response.context['pitches'] if p.pk == self.founder.pk)
        return 'raising_amount' in founder.visible_fields

    def test_bulletin_board_across_the_lifecycle(self):
        for status in RETAINING:
            with self.subTest(status=status):
                user, _ = self.investor_with(status)
                self.assertTrue(self.board_shows_amount(user))

    def test_bulletin_board_still_hides_it_before_acceptance(self):
        for status in NOT_RETAINING:
            with self.subTest(status=status):
                user, _ = self.investor_with(status)
                self.assertFalse(self.board_shows_amount(user))

    # -- filter path -----------------------------------------------------------

    def survives_capital_filter(self, user):
        """A threshold above the amount: the founder matches if the filter may see it."""
        self.client.force_login(user)
        body = self.client.get(
            reverse('matchmaking:global_search'), {'capital': '5000000'}
        ).content.decode(errors='ignore')
        return 'FV Co' in body

    def test_capital_filter_across_the_lifecycle(self):
        for status in RETAINING:
            with self.subTest(status=status):
                user, _ = self.investor_with(status)
                self.assertTrue(self.survives_capital_filter(user),
                                f'a {status} investor was filtered away from a founder they are connected to')

    def test_capital_filter_still_excludes_before_acceptance(self):
        for status in NOT_RETAINING:
            with self.subTest(status=status):
                user, _ = self.investor_with(status)
                self.assertFalse(self.survives_capital_filter(user))

    # -- one definition --------------------------------------------------------

    def test_workspace_and_visibility_agree_for_every_state(self):
        """
        The bug existed because two definitions of "connected" disagreed. They
        now read one constant; this pins that they answer identically.
        """
        for status in RETAINING + NOT_RETAINING:
            with self.subTest(status=status):
                user, connection = self.investor_with(status)
                self.assertEqual(
                    can_view_deal_workspace(user, connection),
                    can_view_profile_field(user, self.founder, 'raising_amount'),
                    f'workspace and visibility disagree about {status}',
                )

    def test_the_constant_holds_the_lifecycle(self):
        self.assertEqual(tuple(ESTABLISHED_FOUNDER_CONNECTION_STATES), RETAINING)
