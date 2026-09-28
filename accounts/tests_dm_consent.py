"""
Direct messaging is an opt-in consent control, and it must work for every role.

DM is the documented bypass around the four role-paired introduction views:
a user who opts in can be contacted without going through matching. That
makes the toggle a consent control, not a preference -- and a consent control
that reports success without persisting anything is worse than one that is
missing, because the user believes they changed something they did not.

What was wrong:

    `allow_direct_messages` lived on Application (founder) and
    InvestorApplication only. The Messaging card renders for EVERY role with
    no gate, and toggle_dm_view wrote only to those two models. A seller-only
    or buyer-only user flipped the switch, both lookups returned None,
    nothing was written, and the view still answered
    {"status": "success", "dm_enabled": true}. The page said "Direct
    messaging is now open", and on reload it silently reverted.

The invariants:

    PERSISTENCE IS WHAT SUCCESS MEANS. A successful response means an
    applicable role profile was actually written. No persistence, no success.

    EVERY ROLE THE USER HOLDS. All four role profiles are OneToOne, so a user
    can hold up to four at once. The toggle is one account-level preference
    stored on role-specific models, so it is written to EVERY profile the
    user holds -- never "the first matching one wins", which would leave the
    account's roles disagreeing with each other and with the read paths.

    BOTH READ SITES. dm_enabled is computed independently in accounts/views.py
    (the Message button on a profile) and usersettings/views.py (the toggle's
    own checked state). Fixing one leaves the toggle and the profile page
    contradicting each other, so each is asserted separately -- a shared
    concept is not a shared code path.

    OFF BY DEFAULT. A new field on a consent control must not opt anyone in.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import (
    Application, BuyerApplication, InvestorApplication, SellerApplication,
)

User = get_user_model()


def make_founder(user):
    return Application.objects.create(
        user=user, company_name='Founder Co', founder_name='F Founder',
        email=user.email or 'f@example.invalid', description='A founder business.',
    )


def make_investor(user):
    return InvestorApplication.objects.create(
        user=user, company_name='Investor Partners',
        email=user.email or 'i@example.invalid',
        investment_focus='Seed software.',
    )


def make_seller(user):
    return SellerApplication.objects.create(
        user=user, company_name='Seller Co', seller_name='S Seller',
        email=user.email or 's@example.invalid', description='A business for sale.',
    )


def make_buyer(user):
    return BuyerApplication.objects.create(
        user=user, full_name='B Buyer', company_name='Buyer Holdings',
        email=user.email or 'b@example.invalid',
        acquisition_thesis='Profitable service businesses.',
    )


ROLES = {
    'founder': make_founder,
    'investor': make_investor,
    'seller': make_seller,
    'buyer': make_buyer,
}


class DMConsentHarness(TestCase):

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def user_with(self, *roles, username='dm_user'):
        user = User.objects.create_user(username, email=f'{username}@example.invalid',
                                        password='x')
        profiles = {role: ROLES[role](user) for role in roles}
        self.client.force_login(user)
        return user, profiles

    def toggle(self, enabled):
        return self.client.post(
            reverse('accounts:toggle_dm'), data=json.dumps({'dm_enabled': enabled}),
            content_type='application/json')

    @staticmethod
    def stored(profile):
        profile.refresh_from_db()
        return profile.allow_direct_messages


class EveryRoleCanOptInTests(DMConsentHarness):

    def test_the_harness_reaches_the_endpoint_at_all(self):
        """
        Positive control. Every assertion below reads a stored flag after a
        POST; a harness whose POST never arrives would make them all vacuous.
        """
        _, profiles = self.user_with('founder', username='dm_control')
        response = self.toggle(True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.stored(profiles['founder']),
                        'the founder path already worked, so the harness is wrong')

    def test_a_seller_can_open_direct_messages(self):
        _, profiles = self.user_with('seller', username='dm_seller')
        self.toggle(True)
        self.assertTrue(self.stored(profiles['seller']),
                        'a seller flipped the switch and nothing was persisted')

    def test_a_buyer_can_open_direct_messages(self):
        _, profiles = self.user_with('buyer', username='dm_buyer')
        self.toggle(True)
        self.assertTrue(self.stored(profiles['buyer']),
                        'a buyer flipped the switch and nothing was persisted')

    def test_every_role_can_close_them_again(self):
        """
        A consent control has to be revocable, not just grantable. Asserted
        per role, because a write path that only handles the enable direction
        would leave a user unable to withdraw consent.
        """
        for role in ROLES:
            with self.subTest(role=role):
                _, profiles = self.user_with(role, username=f'dm_off_{role}')
                self.toggle(True)
                self.assertTrue(self.stored(profiles[role]), 'setup did not enable')
                self.toggle(False)
                self.assertFalse(self.stored(profiles[role]),
                                 'consent could be granted but not withdrawn')


class SuccessMeansSomethingWasPersistedTests(DMConsentHarness):
    """
    The original defect, stated as a contract rather than a value check. The
    endpoint answered "success" while writing nothing, which is the shape that
    let this survive: the response was correct-looking, so nothing downstream
    had reason to disagree.
    """

    def test_a_user_with_no_role_profile_is_not_told_it_worked(self):
        User.objects.create_user('dm_roleless', password='x')
        self.client.login(username='dm_roleless', password='x')
        response = self.toggle(True)
        payload = response.json()
        self.assertNotEqual(
            payload.get('status'), 'success',
            'the endpoint claimed success with no profile to persist to')

    def test_the_refusal_says_something_a_user_can_act_on(self):
        User.objects.create_user('dm_roleless2', password='x')
        self.client.login(username='dm_roleless2', password='x')
        response = self.toggle(True)
        self.assertTrue((response.json().get('message') or '').strip(),
                        'the refusal carried no explanation')


class EveryRoleTheUserHoldsTests(DMConsentHarness):
    """
    All four role profiles are OneToOne, so one account can hold all four.
    The toggle is a single account-level preference stored on role-specific
    models, so a partial write leaves the account's own roles disagreeing --
    and the read paths answer "enabled if ANY role says so", which would then
    report consent the user never gave on the other role.
    """

    def test_a_multi_role_user_has_every_profile_written(self):
        _, profiles = self.user_with('founder', 'seller', username='dm_multi')
        self.toggle(True)
        for role, profile in profiles.items():
            with self.subTest(role=role):
                self.assertTrue(self.stored(profile),
                                f'{role} was skipped -- first-match-wins leaves roles disagreeing')

    def test_all_four_roles_at_once_are_all_written(self):
        _, profiles = self.user_with(*ROLES, username='dm_all_four')
        self.toggle(True)
        self.assertEqual(
            {role: self.stored(p) for role, p in profiles.items()},
            {role: True for role in profiles},
        )

    def test_withdrawing_consent_reaches_every_role(self):
        """
        The dangerous direction. A partial disable leaves a role still open to
        direct messages after the user switched it off, and the read paths
        would keep reporting enabled.
        """
        _, profiles = self.user_with(*ROLES, username='dm_all_off')
        self.toggle(True)
        self.toggle(False)
        self.assertEqual(
            {role: self.stored(p) for role, p in profiles.items()},
            {role: False for role in profiles},
        )


class BothReadSitesAgreeTests(DMConsentHarness):
    """
    dm_enabled is computed twice, independently: accounts/views.py decides
    whether a profile shows a Message button, usersettings/views.py decides
    whether the toggle renders checked. A shared concept is not a shared code
    path, so each is asserted on its own -- fixing one alone makes the
    settings page and the profile page contradict each other.
    """

    def test_the_toggle_is_actually_on_the_settings_page_for_a_seller(self):
        """
        Positive control for the two assertions below, which both slice the
        page at id="dmToggle". If the control were absent, those slices would
        raise or match nothing and the reason would be unclear.
        """
        self.user_with('seller', username='dm_set_present')
        html = self.client.get(reverse('usersettings:home')).content.decode()
        self.assertIn('id="dmToggle"', html, 'the toggle is not on the page at all')

    def test_the_settings_toggle_starts_unchecked_for_a_seller(self):
        self.user_with('seller', username='dm_set_seller_off')
        html = self.client.get(reverse('usersettings:home')).content.decode()
        switch = html.split('id="dmToggle"')[1].split('>')[0]
        self.assertNotIn('checked', switch,
                         'a new seller was shown as already consenting')

    def test_the_settings_toggle_is_checked_after_a_seller_opts_in(self):
        self.user_with('seller', username='dm_set_seller_on')
        self.toggle(True)
        html = self.client.get(reverse('usersettings:home')).content.decode()
        switch = html.split('id="dmToggle"')[1].split('>')[0]
        self.assertIn('checked', switch,
                      'the seller opted in and the settings page still shows it off')

    def test_a_visitor_sees_the_message_control_on_a_consenting_seller(self):
        seller_user = User.objects.create_user('dm_pub_seller', email='ps@example.invalid',
                                               password='x')
        seller = make_seller(seller_user)
        seller.allow_direct_messages = True
        seller.save(update_fields=['allow_direct_messages'])

        visitor = User.objects.create_user('dm_visitor', password='x')
        self.client.force_login(visitor)
        response = self.client.get(
            reverse('accounts:profile', kwargs={'username': seller_user.username}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['dm_enabled'],
                        'a consenting seller was still treated as unreachable')

    def test_a_visitor_sees_no_message_control_on_a_non_consenting_seller(self):
        """
        Paired negative. Without it, a read path hardcoded to True would pass
        the test above while destroying the consent control entirely.
        """
        seller_user = User.objects.create_user('dm_pub_seller2', email='ps2@example.invalid',
                                               password='x')
        make_seller(seller_user)
        visitor = User.objects.create_user('dm_visitor2', password='x')
        self.client.force_login(visitor)
        response = self.client.get(
            reverse('accounts:profile', kwargs={'username': seller_user.username}))
        self.assertFalse(response.context['dm_enabled'],
                         'a seller who never opted in was shown as reachable')


class ConsentIsOffByDefaultTests(DMConsentHarness):

    def test_a_new_role_profile_does_not_consent(self):
        for role, build in ROLES.items():
            with self.subTest(role=role):
                user = User.objects.create_user(f'dm_def_{role}', email=f'{role}@example.invalid',
                                                password='x')
                profile = build(user)
                self.assertFalse(
                    profile.allow_direct_messages,
                    'a migration or default opted this role into direct messages')
