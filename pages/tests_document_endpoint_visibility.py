"""
Document-ID endpoints answer for a hidden company exactly as for a missing one.

PR #57 put the discoverable() rule (not private, not archived, not DENIED) on
the routes that look a founder up by name. The document-ID routes were deferred
and still let anyone walk sequential ids:

- documents/<id>/memo/                      any investor
- documents/<id>/verification/              any signed-in user
- documents/<id>/truth-delta/               any signed-in user
- documents/<id>/truth-delta/claims/<c>/flag/  any investor or buyer, and it
                                            notified the hidden founder

All four now go through document_is_visible_to(user, document): the owner and
staff always; anyone else only while the uploader's business profile (startup
or business-for-sale) is discoverable and not DENIED. A document whose uploader
has no business profile at all is owner-and-staff only, so the memo endpoint
can't serve any investor's upload to any other investor.

Hidden answers 404, never 403, so no response confirms a hidden company exists.
Role checks that already answered 403 keep answering 403.

Deliberately unchanged (relationship, not discovery): the IC memo stays scoped
by an ACCEPTED connection. An investor already introduced to a founder keeps
that access when the founder later goes private -- going private means "not
discoverable to new parties", not "erase established relationships". The
sequential-id surfaces above are not relationship surfaces, so the same
investor gets 404 there.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from matchmaking.models import (
    Application, BuyerApplication, Connection, InvestorApplication, SellerApplication,
)
from matchmaking.tests import _mock_embedding_generation
from zelda_api.truth_delta_models import ClaimedDatapoint, ClarificationRequest, TruthDeltaReport
from zelda_api.vector_models import DocumentSource, IntelligenceMemo

User = get_user_model()
HIDDEN = ('private', 'archived', 'denied')


def _memo_for(document):
    return IntelligenceMemo.objects.create(
        document=document, executive_summary='Summary.', investment_thesis='Thesis.',
        recommendation='NEEDS_REVIEW', completeness_score=0.6, citations_count=1,
    )


def _report_for(document):
    return TruthDeltaReport.objects.create(
        document=document, overall_truth_score=70.0, credibility_risk='low', summary='ok',
        details={'claims': [{'category': 'revenue'}], 'per_claim': []},
    )


class _Documents(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('doc_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='Northwind Grid', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.deck = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='Northwind Grid',
            document_type='pitch_deck', status='analyzed',
        )
        _memo_for(self.deck)
        _report_for(self.deck)

        self.investor_user = User.objects.create_user('doc_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com', company_name='Harbor Capital',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.staff = User.objects.create_user('doc_staff', password='x', is_staff=True)
        self.roleless = User.objects.create_user('doc_roleless', password='x')

    def _set_visibility(self, how, profile=None):
        profile = profile or self.founder
        profile.is_private = how == 'private'
        profile.archived_at = timezone.now() if how == 'archived' else None
        if hasattr(profile, 'review_status'):
            profile.review_status = 'DENIED' if how == 'denied' else 'APPROVED'
        profile.save()

    def _get(self, user, name, document=None):
        self.client.force_login(user)
        return self.client.get(reverse(name, args=[(document or self.deck).id]))

    def _flag(self, user, document=None):
        self.client.force_login(user)
        category = ClaimedDatapoint.CATEGORY_CHOICES[0][0]
        return self.client.post(
            reverse('zelda_api:truth_delta_claim_flag', args=[(document or self.deck).id, category]),
            {'message': 'Could you share evidence?'},
        )


class VisibleCompanyControlTests(_Documents):
    """Controls: nothing about a discoverable company changes."""

    def test_an_investor_reads_the_memo(self):
        self.assertEqual(self._get(self.investor_user, 'zelda_api:document_memo').status_code, 200)

    def test_any_signed_in_user_opens_the_truth_delta_page_and_json(self):
        for user in (self.investor_user, self.roleless):
            with self.subTest(user=user.username):
                self.assertEqual(self._get(user, 'zelda_api:truth_delta_ui').status_code, 200)
                self.assertEqual(self._get(user, 'zelda_api:truth_delta_score').status_code, 200)

    def test_an_investor_flags_a_claim(self):
        self.assertEqual(self._flag(self.investor_user).status_code, 200)
        self.assertTrue(ClarificationRequest.objects.exists())

    def test_the_owner_and_staff_reach_everything(self):
        for user in (self.founder_user, self.staff):
            for name in ('zelda_api:document_memo', 'zelda_api:truth_delta_ui', 'zelda_api:truth_delta_score'):
                with self.subTest(user=user.username, name=name):
                    self.assertEqual(self._get(user, name).status_code, 200)


class HiddenCompanyTests(_Documents):

    def test_the_memo_endpoint_answers_404_for_a_hidden_company(self):
        for how in HIDDEN:
            with self.subTest(how=how):
                self._set_visibility(how)
                response = self._get(self.investor_user, 'zelda_api:document_memo')
                self.assertEqual(response.status_code, 404)
                self.assertNotIn('Northwind', response.content.decode())

    def test_the_truth_delta_page_and_json_answer_404_for_a_hidden_company(self):
        for how in HIDDEN:
            for name in ('zelda_api:truth_delta_ui', 'zelda_api:truth_delta_score'):
                with self.subTest(how=how, name=name):
                    self._set_visibility(how)
                    response = self._get(self.investor_user, name)
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn('Northwind', response.content.decode())

    def test_a_roleless_viewer_also_gets_404_rather_than_a_report(self):
        self._set_visibility('private')
        self.assertEqual(self._get(self.roleless, 'zelda_api:truth_delta_ui').status_code, 404)
        self.assertEqual(self._get(self.roleless, 'zelda_api:truth_delta_score').status_code, 404)

    def test_flagging_a_hidden_companys_claim_is_404_and_never_notifies_the_founder(self):
        from notifications.models import Notification
        for how in HIDDEN:
            with self.subTest(how=how):
                self._set_visibility(how)
                self.assertEqual(self._flag(self.investor_user).status_code, 404)
        self.assertFalse(ClarificationRequest.objects.exists())
        self.assertFalse(Notification.objects.filter(recipient=self.founder_user).exists())

    def test_a_buyer_cannot_flag_a_hidden_companys_claim_either(self):
        buyer_user = User.objects.create_user('doc_buyer', password='x')
        BuyerApplication.objects.create(
            user=buyer_user, full_name='B', email='b@t.com', company_name='Acquire Co',
            acquisition_thesis='SaaS', budget_min=1, budget_max=2,
        )
        self.assertEqual(self._flag(buyer_user).status_code, 200)  # control: visible company
        ClarificationRequest.objects.all().delete()
        self._set_visibility('archived')
        self.assertEqual(self._flag(buyer_user).status_code, 404)
        self.assertFalse(ClarificationRequest.objects.exists())

    def test_the_owner_and_staff_still_reach_a_hidden_companys_own_documents(self):
        for how in HIDDEN:
            for user in (self.founder_user, self.staff):
                for name in ('zelda_api:document_memo', 'zelda_api:truth_delta_ui', 'zelda_api:truth_delta_score'):
                    with self.subTest(how=how, user=user.username, name=name):
                        self._set_visibility(how)
                        self.assertEqual(self._get(user, name).status_code, 200)

    def test_a_viewer_without_an_investor_role_still_gets_403_from_the_memo_endpoint(self):
        # The existing role gate is unchanged: not-an-investor is 403, not 404.
        self.assertEqual(self._get(self.roleless, 'zelda_api:document_memo').status_code, 403)


class RelationshipAccessTests(_Documents):
    """An ACCEPTED connection is its own grant; discovery visibility doesn't revoke it."""

    def _ic_memo(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('zelda_api:ic_memo', args=[self.deck.id]))

    def test_an_introduced_investor_keeps_the_ic_memo_when_the_founder_goes_private(self):
        Connection.objects.create(investor=self.investor, founder=self.founder, status='ACCEPTED')
        self.assertEqual(self._ic_memo(self.investor_user).status_code, 200)
        for how in HIDDEN:
            with self.subTest(how=how):
                self._set_visibility(how)
                self.assertEqual(self._ic_memo(self.investor_user).status_code, 200)

    def test_an_investor_with_no_relationship_gets_404_for_a_hidden_founders_documents(self):
        self._set_visibility('private')
        self.assertEqual(self._ic_memo(self.investor_user).status_code, 404)
        self.assertEqual(self._get(self.investor_user, 'zelda_api:document_memo').status_code, 404)

    def test_the_sequential_id_surfaces_are_not_relationship_surfaces(self):
        # The IC memo is scoped by the introduction; the panel/preview endpoints
        # are discovery surfaces and follow visibility even for a connected investor.
        Connection.objects.create(investor=self.investor, founder=self.founder, status='ACCEPTED')
        self._set_visibility('private')
        self.assertEqual(self._ic_memo(self.investor_user).status_code, 200)
        for name in ('zelda_api:document_memo', 'zelda_api:truth_delta_ui', 'zelda_api:truth_delta_score'):
            with self.subTest(name=name):
                self.assertEqual(self._get(self.investor_user, name).status_code, 404)


class NoBusinessProfileTests(_Documents):
    """An uploader with no business profile: owner and staff only."""

    def setUp(self):
        super().setUp()
        self.other_investor = User.objects.create_user('doc_investor_2', password='x')
        InvestorApplication.objects.create(
            user=self.other_investor, full_name='I2', email='i2@t.com', company_name='Second Capital',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.portfolio = DocumentSource.objects.create(
            uploaded_by=self.investor_user, filename='portfolio.pdf', source_entity='Harbor Capital',
            document_type='portfolio', status='analyzed',
        )
        _memo_for(self.portfolio)
        _report_for(self.portfolio)

    def test_another_investor_cannot_read_an_investors_own_upload(self):
        for name in ('zelda_api:document_memo', 'zelda_api:truth_delta_ui', 'zelda_api:truth_delta_score'):
            with self.subTest(name=name):
                self.assertEqual(self._get(self.other_investor, name, document=self.portfolio).status_code, 404)

    def test_the_uploader_and_staff_still_read_it(self):
        for user in (self.investor_user, self.staff):
            for name in ('zelda_api:document_memo', 'zelda_api:truth_delta_ui', 'zelda_api:truth_delta_score'):
                with self.subTest(user=user.username, name=name):
                    self.assertEqual(self._get(user, name, document=self.portfolio).status_code, 200)


class SellerDocumentTests(_Documents):
    """A business-for-sale is a business too: the same rule, its own profile."""

    def setUp(self):
        super().setUp()
        self.seller_user = User.objects.create_user('doc_seller', password='x')
        self.seller = SellerApplication.objects.create(
            user=self.seller_user, company_name='Harbor Bakery', seller_name='S', email='s@t.com',
            description='test', industry='Food', years_in_business=3,
        )
        self.seller_deck = DocumentSource.objects.create(
            uploaded_by=self.seller_user, filename='cim.pdf', source_entity='Harbor Bakery',
            document_type='pitch_deck', status='analyzed',
        )
        _report_for(self.seller_deck)

    def test_a_visible_sellers_report_stays_readable(self):
        self.assertEqual(
            self._get(self.investor_user, 'zelda_api:truth_delta_ui', document=self.seller_deck).status_code, 200)

    def test_a_hidden_sellers_report_answers_404(self):
        for how in ('private', 'archived'):
            with self.subTest(how=how):
                self._set_visibility(how, profile=self.seller)
                response = self._get(self.investor_user, 'zelda_api:truth_delta_ui', document=self.seller_deck)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn('Harbor Bakery', response.content.decode())

    def test_the_seller_and_staff_still_reach_it(self):
        self._set_visibility('private', profile=self.seller)
        for user in (self.seller_user, self.staff):
            with self.subTest(user=user.username):
                self.assertEqual(
                    self._get(user, 'zelda_api:truth_delta_ui', document=self.seller_deck).status_code, 200)


class StaffHiddenDocumentTests(_Documents):
    """
    The existing is_hidden_by_staff rule is untouched for a company that is
    still discoverable -- but visibility is decided first, so a hidden
    company's document never answers 403 (which would confirm it exists).
    """

    def setUp(self):
        super().setUp()
        self.deck.is_hidden_by_staff = True
        self.deck.save()

    def test_a_visible_companys_staff_hidden_document_still_answers_403(self):
        for name in ('zelda_api:document_memo', 'zelda_api:truth_delta_ui', 'zelda_api:truth_delta_score'):
            with self.subTest(name=name):
                self.assertEqual(self._get(self.investor_user, name).status_code, 403)

    def test_a_hidden_companys_staff_hidden_document_answers_404_not_403(self):
        for how in HIDDEN:
            for name in ('zelda_api:document_memo', 'zelda_api:truth_delta_ui', 'zelda_api:truth_delta_score'):
                with self.subTest(how=how, name=name):
                    self._set_visibility(how)
                    response = self._get(self.investor_user, name)
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn('Northwind', response.content.decode())

    def test_the_owner_still_reaches_their_own_staff_hidden_document(self):
        self.assertEqual(self._get(self.founder_user, 'zelda_api:truth_delta_ui').status_code, 200)
        self._set_visibility('private')
        self.assertEqual(self._get(self.founder_user, 'zelda_api:truth_delta_ui').status_code, 200)
        self.assertEqual(self._get(self.staff, 'zelda_api:truth_delta_ui').status_code, 200)


class HelperTests(_Documents):

    def test_document_is_visible_to_is_the_one_rule(self):
        from zelda_api.document_access import document_is_visible_to

        self.assertTrue(document_is_visible_to(self.founder_user, self.deck))
        self.assertTrue(document_is_visible_to(self.staff, self.deck))
        self.assertTrue(document_is_visible_to(self.investor_user, self.deck))
        for how in HIDDEN:
            with self.subTest(how=how):
                self._set_visibility(how)
                self.deck.refresh_from_db()
                self.assertFalse(document_is_visible_to(self.investor_user, self.deck))
                self.assertTrue(document_is_visible_to(self.founder_user, self.deck))
                self.assertTrue(document_is_visible_to(self.staff, self.deck))

    def test_an_anonymous_user_never_passes(self):
        from django.contrib.auth.models import AnonymousUser
        from zelda_api.document_access import document_is_visible_to

        self.assertFalse(document_is_visible_to(AnonymousUser(), self.deck))
