"""
Profile vs deck reconciliation (B-2 v1): see zelda_api/profile_reconciliation.py.

What is held here:

    EACH PAIR, EACH OUTCOME. consistent / differs / every not-comparable
    reason, with the values kept on not-comparable rows.

    THE TRAPS ARE NOT COMPARED. prior_amount_raised == 0 is the model default;
    profile revenue has no period; the deck disagreeing with itself picks no
    winner; a "funding raised" equal to the raise target may be the ask.

    ONE ASSOCIATION. A deck about another company gets no reconciliation, by
    the same helper the memo context uses.

    OWNER ONLY. The comparison discloses the profile figure. A viewer who CAN
    open the page (staff) is shown nothing, against a positive control proving
    the owner is shown the panel and the figure.

    NOT TRUTH DELTA. Rendering it writes no evidence and moves no state.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application

from .profile_reconciliation import (
    CONSISTENT, DIFFERS, NOT_COMPARABLE, reconcile_profile_with_deck,
)
from .truth_delta_models import ClaimedDatapoint, ObservedDatapoint, TruthDeltaReport
from .vector_models import DocumentSource

User = get_user_model()

PANEL_TITLE = 'Profile and deck figures to review'
# A figure that appears nowhere on the page except through the panel.
DISTINCT_TEAM = 37


class ReconciliationFixture(TestCase):

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('pr_owner', password='x')
        self.app = Application.objects.create(
            user=self.owner, company_name='Northwind Grid', founder_name='F', email='f@t.test',
            description='d', sector='SaaS', stage='Seed')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Northwind Grid', uploaded_by=self.owner,
            document_type='pitch_deck', status='analyzed')

    def profile(self, **fields):
        Application.objects.filter(pk=self.app.pk).update(**fields)
        self.app.refresh_from_db()

    def claim(self, category, value, excerpt=''):
        return ClaimedDatapoint.objects.create(
            document=self.document, category=category, claimed_value=str(value),
            claimed_value_numeric=value, text_excerpt=excerpt or f'{category}: {value}')

    def rows(self, viewer=None):
        return {r.profile_field: r for r in reconcile_profile_with_deck(self.document, viewer or self.owner)}

    def row(self, field):
        return self.rows()[field]


class EachPairEachOutcomeTests(ReconciliationFixture):

    def test_team_size_consistent(self):
        self.profile(team_size=12)
        self.claim('employees', 12.0)
        self.assertEqual(self.row('team_size').status, CONSISTENT)

    def test_team_size_within_tolerance_is_consistent(self):
        self.profile(team_size=100)
        self.claim('team_size', 95.0)
        self.assertEqual(self.row('team_size').status, CONSISTENT)

    def test_team_size_differs_keeps_both_values_and_dates(self):
        self.profile(team_size=12)
        self.claim('employees', 40.0)
        row = self.row('team_size')
        self.assertEqual(row.status, DIFFERS)
        self.assertEqual((row.profile_value, row.deck_values), (12.0, (40.0,)))
        self.assertEqual(row.profile_saved_at, self.app.updated_at)
        self.assertEqual(row.deck_uploaded_at, self.document.created_at)

    def test_prior_raised_different_numbers_have_unknown_profile_currency(self):
        self.profile(prior_amount_raised=500_000, raising_amount=3_000_000)
        self.claim('funding_raised', 2_000_000.0)
        self.assertEqual((self.row('prior_amount_raised').status, self.row('prior_amount_raised').reason),
                         (NOT_COMPARABLE, 'profile_currency_unknown'))

    def test_prior_raised_equal_numbers_do_not_establish_currency(self):
        self.profile(prior_amount_raised=2_000_000, raising_amount=3_000_000)
        self.claim('funding_raised', 2_000_000.0)
        self.assertEqual((self.row('prior_amount_raised').status, self.row('prior_amount_raised').reason),
                         (NOT_COMPARABLE, 'profile_currency_unknown'))

    def test_a_pair_with_no_deck_claim_is_omitted(self):
        self.profile(team_size=12)
        self.assertEqual(self.rows(), {})


class TheTrapsAreNotComparedTests(ReconciliationFixture):

    def assertNotComparable(self, field, reason):
        row = self.row(field)
        self.assertEqual((row.status, row.reason), (NOT_COMPARABLE, reason))
        return row

    def test_blank_profile_field(self):
        self.claim('employees', 12.0)
        row = self.assertNotComparable('team_size', 'profile_blank')
        self.assertEqual(row.deck_values, (12.0,), 'the deck value was dropped')

    def test_zero_prior_raised_may_be_the_default(self):
        """0 is what an unfilled profile holds; nothing records that it was entered."""
        self.assertEqual(self.app.prior_amount_raised, 0, 'the fixture is not on the model default')
        self.claim('funding_raised', 1_000_000.0)
        row = self.assertNotComparable('prior_amount_raised', 'profile_zero_may_be_default')
        self.assertEqual((row.profile_value, row.deck_values), (0.0, (1_000_000.0,)))

    def test_revenue_period_is_unknown_even_when_the_figures_agree(self):
        """The profile never says annual or monthly, so agreement proves nothing either."""
        self.profile(current_revenue=1_200_000)
        self.claim('revenue', 1_200_000.0)
        row = self.assertNotComparable('current_revenue', 'profile_period_unknown')
        self.assertEqual((row.profile_value, row.deck_values), (1_200_000.0, (1_200_000.0,)))

    def test_revenue_period_is_unknown_when_they_differ(self):
        self.profile(current_revenue=100_000)
        self.claim('arr', 1_200_000.0)
        self.assertNotComparable('current_revenue', 'profile_period_unknown')

    def test_conflicting_deck_claims_pick_no_winner(self):
        self.profile(team_size=12)
        self.claim('employees', 12.0)
        self.claim('team_size', 40.0)
        row = self.assertNotComparable('team_size', 'conflicting_deck_claims')
        self.assertEqual(sorted(row.deck_values), [12.0, 40.0], 'a deck value was silently dropped')

    def test_agreeing_deck_claims_are_not_a_conflict(self):
        """Paired control: two figures that agree are one figure."""
        self.profile(team_size=12)
        self.claim('employees', 12.0)
        self.claim('team_size', 12.0)
        self.assertEqual(self.row('team_size').status, CONSISTENT)

    def test_unparsed_deck_value(self):
        self.profile(team_size=12)
        ClaimedDatapoint.objects.create(document=self.document, category='employees',
                                        claimed_value='a growing team', claimed_value_numeric=None)
        self.assertNotComparable('team_size', 'deck_value_unparsed')

    def test_funding_raised_equal_to_the_raise_target_may_be_the_ask(self):
        """The JoyToys misfiling: a $250K raise filed as funding already raised."""
        self.profile(prior_amount_raised=50_000, raising_amount=250_000)
        self.claim('funding_raised', 250_000.0)
        self.assertNotComparable('prior_amount_raised', 'profile_currency_unknown')


class OneAssociationTests(ReconciliationFixture):

    def test_a_deck_about_another_company_is_not_reconciled(self):
        DocumentSource.objects.filter(pk=self.document.pk).update(source_entity='Acme Rockets')
        self.document.refresh_from_db()
        self.profile(team_size=12)
        self.claim('employees', 40.0)
        self.assertEqual(self.rows(), {})

    def test_the_memo_context_reads_the_same_association(self):
        from . import grounded_context
        self.assertEqual(grounded_context.profile_for_document(self.document), self.app)
        DocumentSource.objects.filter(pk=self.document.pk).update(source_entity='Acme Rockets')
        self.document.refresh_from_db()
        self.assertIsNone(grounded_context.profile_for_document(self.document))


class OwnerOnlyTests(ReconciliationFixture):

    def setUp(self):
        super().setUp()
        self.profile(team_size=DISTINCT_TEAM)
        self.claim('employees', 90.0)
        self.staff = User.objects.create_user('pr_staff', password='x', is_staff=True)

    def page(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.document.id]))
        self.assertEqual(response.status_code, 200, 'the viewer cannot open the page, so the negative proves nothing')
        return response

    def test_the_owner_sees_the_panel_and_the_figures(self):
        """Positive control for every negative below."""
        html = self.page(self.owner).content.decode()
        self.assertIn(PANEL_TITLE, html)
        self.assertIn(f'your profile says {DISTINCT_TEAM}', html)

    def test_staff_who_can_open_the_page_see_neither(self):
        response = self.page(self.staff)
        html = response.content.decode()
        self.assertEqual(response.context['profile_reconciliation'], [])
        self.assertNotIn(PANEL_TITLE, html)
        self.assertNotIn(f'your profile says {DISTINCT_TEAM}', html)

    def test_the_function_returns_nothing_to_anyone_else(self):
        from django.contrib.auth.models import AnonymousUser
        other = User.objects.create_user('pr_other', password='x')
        for viewer in (other, self.staff, AnonymousUser(), None):
            with self.subTest(viewer=viewer):
                self.assertEqual(reconcile_profile_with_deck(self.document, viewer), [])


class NotTruthDeltaTests(ReconciliationFixture):

    def test_rendering_it_writes_no_evidence_and_moves_no_state(self):
        self.profile(team_size=12)
        self.claim('employees', 40.0)
        state = self.document.verification_state
        self.client.force_login(self.owner)
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.document.id]))
        self.assertIn(PANEL_TITLE, response.content.decode(), 'the panel did not render, so this proves nothing')
        self.assertFalse(ObservedDatapoint.objects.filter(document=self.document).exists())
        self.assertFalse(TruthDeltaReport.objects.filter(document=self.document).exists())
        self.document.refresh_from_db()
        self.assertEqual(self.document.verification_state, state)

    def test_the_panel_uses_neutral_words(self):
        self.profile(team_size=12)
        self.claim('employees', 40.0)
        self.client.force_login(self.owner)
        html = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.document.id])).content.decode()
        start = html.index('data-section="profile-reconciliation"')
        panel = html[start:html.index('</ul>', start)].lower()
        self.assertIn('your profile says 12', panel, 'the panel slice is wrong')
        for word in ('contradict', 'error', 'mismatch', 'verified', 'false', 'inaccura'):
            with self.subTest(word=word):
                self.assertNotIn(word, panel)


class RevenueBasisTests(ReconciliationFixture):
    """
    Revenue is compared only when profile and deck share a basis: the profile
    says ARR and the deck has an `arr` claim. Nothing is annualized.
    """

    def test_profile_arr_vs_deck_arr_equal_amounts_need_currency_too(self):
        self.profile(current_revenue=1_200_000, revenue_period='arr')
        self.claim('arr', 1_200_000.0)
        self.assertEqual((self.row('current_revenue').status, self.row('current_revenue').reason),
                         (NOT_COMPARABLE, 'profile_currency_unknown'))

    def test_profile_arr_vs_deck_arr_different_amounts_need_currency_too(self):
        self.profile(current_revenue=1_200_000, revenue_period='arr')
        self.claim('arr', 3_000_000.0)
        row = self.row('current_revenue')
        self.assertEqual((row.status, row.reason), (NOT_COMPARABLE, 'profile_currency_unknown'))
        self.assertEqual((row.profile_value, row.deck_values), (1_200_000.0, (3_000_000.0,)))

    def test_profile_arr_vs_deck_revenue_only(self):
        self.profile(current_revenue=1_200_000, revenue_period='arr')
        self.claim('revenue', 3_000_000.0)
        row = self.row('current_revenue')
        self.assertEqual((row.status, row.reason), (NOT_COMPARABLE, 'deck_period_unknown'))
        self.assertEqual(row.deck_values, (3_000_000.0,))

    def test_profile_arr_sets_a_revenue_claim_aside_rather_than_calling_it_a_conflict(self):
        self.profile(current_revenue=1_200_000, revenue_period='arr')
        self.claim('arr', 1_200_000.0)
        self.claim('revenue', 9_000_000.0)
        row = self.row('current_revenue')
        self.assertEqual((row.status, row.reason), (NOT_COMPARABLE, 'profile_currency_unknown'))
        self.assertEqual(row.deck_values, (1_200_000.0,))

    def test_a_period_against_deck_arr_is_a_different_basis(self):
        for period in ('monthly', 'annual', 'ttm'):
            with self.subTest(period=period):
                self.profile(current_revenue=100_000, revenue_period=period)
                ClaimedDatapoint.objects.filter(document=self.document).delete()
                self.claim('arr', 1_200_000.0)
                row = self.row('current_revenue')
                self.assertEqual((row.status, row.reason), (NOT_COMPARABLE, 'different_revenue_basis'))

    def test_monthly_is_never_annualized(self):
        """$100K a month is $1.2M a year, and is still not compared with $1.2M ARR."""
        self.profile(current_revenue=100_000, revenue_period='monthly')
        self.claim('arr', 1_200_000.0)
        self.assertEqual(self.row('current_revenue').status, NOT_COMPARABLE)

    def test_a_period_against_deck_revenue_is_deck_period_unknown(self):
        self.profile(current_revenue=1_200_000, revenue_period='annual')
        self.claim('revenue', 1_200_000.0)
        row = self.row('current_revenue')
        self.assertEqual((row.status, row.reason), (NOT_COMPARABLE, 'deck_period_unknown'))
        self.assertEqual((row.profile_value, row.deck_values), (1_200_000.0, (1_200_000.0,)))

    def test_every_reason_has_owner_text(self):
        from .profile_reconciliation import REASON_TEXT
        for reason in ('profile_period_unknown', 'deck_period_unknown', 'different_revenue_basis', 'profile_currency_unknown'):
            with self.subTest(reason=reason):
                self.assertTrue(REASON_TEXT.get(reason))
