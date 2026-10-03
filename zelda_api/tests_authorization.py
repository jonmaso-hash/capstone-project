"""
Phase 1 Task 2: the authorization resolver. Bypass tests that ship with it.

AuthorizationFixture is the SHARED fixture the locked contract requires
(point 2): it always contains a private company's document, a hidden PRIVATE
field and a Lite-gated finding, because filter-before-retrieval and
retrieve-then-filter are indistinguishable when nothing sensitive exists.
Task 3's retrieval tests reuse it.

Two kinds of test, on purpose:
- Expected outcomes, written out by hand. Parity alone could be vacuous: if
  the resolver and the authority were wrong together, parity would pass.
- Parity with the authority each answer wraps, over every principal and
  object, so the resolver cannot drift into being a second authority.
"""
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.test import TestCase

from matchmaking.models import (
    FIELD_PRIVATE, NEW_PROFILE_FIELD_VISIBILITY, Application, Connection,
    InvestorApplication, can_view_profile_field,
)
from matchmaking.tests import _mock_embedding_generation
from zelda_api.authorization import FULL, LITE, Authorization, authorize
from zelda_api.document_access import document_is_visible_to
from zelda_api.entity_verification import can_view_entity_report
from zelda_api.entity_verification_models import EntityReportAccessGrant, EntityVerificationReport
from zelda_api.ic_memo import can_view_ic_memo
from zelda_api.principal import ORIGIN_HTTP, ORIGIN_TASK, Principal, PrincipalRequired
from zelda_api.truth_delta_models import TruthDeltaReport, truth_delta_unlocked
from zelda_api.vector_models import DocumentChunk, DocumentSource

User = get_user_model()
CANARY = 'CANARY-AUTHZ-HIDDEN'


class AuthorizationFixture(TestCase):
    """
    Companies
      A  discoverable, not Premium   deck_a: Lite-gated finding; reason_for_capital PRIVATE (canary)
      P  discoverable, Premium       deck_p: full finding for anyone who can see it
      X  private (is_private)        deck_x: the private document
      H  discoverable                deck_h: hidden by staff
    People
      unrelated investor, investor with an ACCEPTED connection to A,
      staff, roleless user, and staff viewing-as the unrelated investor.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.users = {}
        self.apps = {}
        self.docs = {}
        for key, extra in (('a', {}), ('p', {'is_premium': True}), ('x', {'is_private': True}), ('h', {})):
            user = User.objects.create_user(f'authz_owner_{key}', password='x')
            visibility = dict(NEW_PROFILE_FIELD_VISIBILITY)
            visibility['reason_for_capital'] = FIELD_PRIVATE
            app = Application.objects.create(
                user=user, company_name=f'AuthzCo {key.upper()}', founder_name='F', email=f'{key}@t.test',
                description='d', sector='SaaS', stage='Seed', current_revenue=1000,
                reason_for_capital=f'{CANARY} {key}', field_visibility=visibility, **extra,
            )
            doc = DocumentSource.objects.create(
                uploaded_by=user, filename=f'{key}.pdf', source_entity=app.company_name,
                document_type='pitch_deck', status='analyzed', is_hidden_by_staff=(key == 'h'),
            )
            TruthDeltaReport.objects.create(document=doc, overall_truth_score=50.0, credibility_risk='medium',
                                            summary='s', details={'claims': [], 'per_claim': []})
            DocumentChunk.objects.create(document=doc, chunk_index=0, page_number=1, token_count=3, raw_text=f'text of {key}')
            self.users[key], self.apps[key], self.docs[key] = user, app, doc

        self.investor = User.objects.create_user('authz_investor', password='x')
        InvestorApplication.objects.create(user=self.investor, full_name='I', email='i@t.test',
                                           company_name='Ic', investment_focus='SaaS', investment_stage='Seed')
        self.connected = User.objects.create_user('authz_connected', password='x')
        connected_profile = InvestorApplication.objects.create(
            user=self.connected, full_name='C', email='c@t.test', company_name='Cc',
            investment_focus='SaaS', investment_stage='Seed')
        Connection.objects.create(investor=connected_profile, founder=self.apps['a'], status='ACCEPTED')
        self.staff = User.objects.create_user('authz_staff', password='x', is_staff=True)
        self.roleless = User.objects.create_user('authz_roleless', password='x')

        self.entity_report = EntityVerificationReport.objects.create(
            founder_profile=self.apps['a'], document=self.docs['a'], findings=[])
        EntityReportAccessGrant.objects.create(report=self.entity_report, user=self.connected)

        task = lambda u: Principal.for_user(u, ORIGIN_TASK)
        self.principals = {
            'owner_a': task(self.users['a']),
            'owner_x': task(self.users['x']),
            'investor': task(self.investor),
            'connected': task(self.connected),
            'staff': task(self.staff),
            'roleless': task(self.roleless),
            'staff_as_investor': Principal(user=self.investor, origin=ORIGIN_HTTP, actor=self.staff, read_only=True),
        }

    def auth(self, name):
        return authorize(self.principals[name])


class RefusalTests(AuthorizationFixture):

    def test_no_principal_refuses(self):
        for value in (None, self.investor, {'user_id': self.investor.pk}):
            with self.subTest(value=value), self.assertRaises(PrincipalRequired):
                authorize(value)
            with self.subTest(value=value), self.assertRaises(PrincipalRequired):
                Authorization(value)


class PrivateDocumentTests(AuthorizationFixture):
    """deck_x belongs to a private company."""

    def test_strangers_cannot_reach_it(self):
        for name in ('investor', 'connected', 'roleless', 'owner_a', 'staff_as_investor'):
            with self.subTest(name=name):
                auth = self.auth(name)
                self.assertFalse(auth.document_visible(self.docs['x']))
                self.assertFalse(auth.text_permitted(self.docs['x']))
                self.assertIsNone(auth.finding_tier(self.docs['x']))

    def test_owner_and_staff_can(self):
        for name in ('owner_x', 'staff'):
            with self.subTest(name=name):
                auth = self.auth(name)
                self.assertTrue(auth.document_visible(self.docs['x']))
                self.assertTrue(auth.text_permitted(self.docs['x']))


class RawTextTests(AuthorizationFixture):
    """Raw text is owner-and-staff only, decided before retrieval."""

    def test_text_documents_is_a_queryset_for_filtering_before_retrieval(self):
        self.assertIsInstance(self.auth('investor').text_documents(), QuerySet)

    def test_chunks_filtered_by_the_resolver(self):
        def chunks(name):
            permitted = self.auth(name).text_documents()
            return set(DocumentChunk.objects.filter(document__in=permitted).values_list('document_id', flat=True))

        everything = set(d.pk for d in self.docs.values())
        self.assertEqual(chunks('investor'), set())
        self.assertEqual(chunks('connected'), set())
        self.assertEqual(chunks('roleless'), set())
        self.assertEqual(chunks('owner_a'), {self.docs['a'].pk})
        self.assertEqual(chunks('owner_x'), {self.docs['x'].pk})
        self.assertTrue(everything <= chunks('staff'))

    def test_visible_report_does_not_mean_readable_text(self):
        # An unrelated investor may reach deck_a's reports but not its text.
        auth = self.auth('investor')
        self.assertTrue(auth.document_visible(self.docs['a']))
        self.assertFalse(auth.text_permitted(self.docs['a']))

    def test_staff_viewing_as_a_user_gets_the_users_scope_not_staffs(self):
        auth = self.auth('staff_as_investor')
        self.assertEqual(list(auth.text_documents()), [])
        self.assertEqual(auth.finding_tier(self.docs['a']), LITE)


class HiddenFieldTests(AuthorizationFixture):
    """reason_for_capital is PRIVATE; current_revenue is CONNECTED."""

    def test_private_field(self):
        app = self.apps['a']
        self.assertTrue(self.auth('owner_a').field_visible(app, 'reason_for_capital'))
        self.assertTrue(self.auth('staff').field_visible(app, 'reason_for_capital'))
        for name in ('investor', 'connected', 'roleless', 'staff_as_investor'):
            with self.subTest(name=name):
                self.assertFalse(self.auth(name).field_visible(app, 'reason_for_capital'))

    def test_connected_field(self):
        app = self.apps['a']
        self.assertTrue(self.auth('connected').field_visible(app, 'current_revenue'))
        self.assertFalse(self.auth('investor').field_visible(app, 'current_revenue'))


class LiteGatedFindingTests(AuthorizationFixture):
    """The finding tier follows the document owner's Premium, never the viewer's."""

    def test_non_premium_owner_means_lite_for_everyone_but_staff(self):
        for name in ('investor', 'connected', 'roleless', 'owner_a'):
            with self.subTest(name=name):
                self.assertEqual(self.auth(name).finding_tier(self.docs['a']), LITE)
        self.assertEqual(self.auth('staff').finding_tier(self.docs['a']), FULL)

    def test_premium_owner_means_full(self):
        self.assertEqual(self.auth('investor').finding_tier(self.docs['p']), FULL)

    def test_premium_viewer_does_not_unlock(self):
        profile = self.investor.match_investor_profile
        profile.is_premium = True
        profile.save()
        self.assertEqual(self.auth('investor').finding_tier(self.docs['a']), LITE)


class StaffHiddenDocumentTests(AuthorizationFixture):
    """deck_h: is_hidden_by_staff, composed into document_visible."""

    def test_hidden_from_everyone_but_owner_and_staff(self):
        # The composition matters: the underlying rule alone says visible.
        self.assertTrue(document_is_visible_to(self.investor, self.docs['h']))
        self.assertFalse(self.auth('investor').document_visible(self.docs['h']))
        self.assertIsNone(self.auth('investor').finding_tier(self.docs['h']))
        self.assertTrue(self.auth('staff').document_visible(self.docs['h']))
        owner = authorize(Principal.for_user(self.users['h'], ORIGIN_TASK))
        self.assertTrue(owner.document_visible(self.docs['h']))


class GrantTests(AuthorizationFixture):

    def test_ic_memo_follows_the_accepted_connection(self):
        self.assertTrue(self.auth('connected').ic_memo_visible(self.apps['a']))
        self.assertFalse(self.auth('investor').ic_memo_visible(self.apps['a']))

    def test_entity_report_follows_the_grant(self):
        self.assertTrue(self.auth('connected').entity_report_visible(self.entity_report))
        self.assertFalse(self.auth('investor').entity_report_visible(self.entity_report))
        self.assertTrue(self.auth('owner_a').entity_report_visible(self.entity_report))

    def test_answers_are_live_not_snapshotted(self):
        auth = self.auth('investor')
        self.assertFalse(auth.ic_memo_visible(self.apps['a']))
        Connection.objects.create(investor=self.investor.match_investor_profile,
                                  founder=self.apps['a'], status='ACCEPTED')
        self.assertTrue(auth.ic_memo_visible(self.apps['a']))


class ParityTests(AuthorizationFixture):
    """Every answer equals the existing authority it wraps, for every pair."""

    def test_parity(self):
        fields = sorted(NEW_PROFILE_FIELD_VISIBILITY)
        for name, principal in self.principals.items():
            auth, user = authorize(principal), principal.user
            for key, doc in self.docs.items():
                with self.subTest(principal=name, doc=key):
                    staff_hidden = doc.is_hidden_by_staff and not (user.is_staff or doc.uploaded_by_id == user.pk)
                    visible = document_is_visible_to(user, doc) and not staff_hidden
                    self.assertEqual(auth.document_visible(doc), visible)
                    self.assertEqual(auth.text_permitted(doc), user.is_staff or doc.uploaded_by_id == user.pk)
                    self.assertEqual(auth.text_permitted(doc), auth.text_documents().filter(pk=doc.pk).exists())
                    expected_tier = (FULL if truth_delta_unlocked(user, doc) else LITE) if visible else None
                    self.assertEqual(auth.finding_tier(doc), expected_tier)
            for key, app in self.apps.items():
                with self.subTest(principal=name, app=key):
                    self.assertEqual(auth.ic_memo_visible(app), can_view_ic_memo(user, app))
                    for field in fields:
                        self.assertEqual(auth.field_visible(app, field), can_view_profile_field(user, app, field))
            with self.subTest(principal=name, report='entity'):
                self.assertEqual(auth.entity_report_visible(self.entity_report),
                                 can_view_entity_report(user, self.entity_report))
