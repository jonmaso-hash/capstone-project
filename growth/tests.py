from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.text import slugify

from matchmaking.tests import _mock_embedding_generation
from matchmaking.models import Application, InvestorApplication
from .models import ReferralInvite
from .services import consume_referral_if_pending
from .sitemaps import InvestorDirectorySitemap, FounderDirectorySitemap

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PseoDirectoryTests(TestCase):
    """investor_directory/founder_directory: correct aggregate count, excludes private/denied profiles."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.public_user = User.objects.create_user('pseo_public_investor', password='x')
        self.private_user = User.objects.create_user('pseo_private_investor', password='x')
        self.denied_user = User.objects.create_user('pseo_denied_investor', password='x')

        InvestorApplication.objects.create(
            user=self.public_user, full_name='Public I', email='pub@t.com', company_name='PubVC',
            investment_focus='B2B SaaS', investment_stage='Seed', location='California',
        )
        InvestorApplication.objects.create(
            user=self.private_user, full_name='Private I', email='priv@t.com', company_name='PrivVC',
            investment_focus='B2B SaaS', investment_stage='Seed', location='California', is_private=True,
        )
        InvestorApplication.objects.create(
            user=self.denied_user, full_name='Denied I', email='den@t.com', company_name='DenVC',
            investment_focus='B2B SaaS', investment_stage='Seed', location='California', review_status='DENIED',
        )

    def test_count_excludes_private_and_denied(self):
        response = self.client.get(reverse('growth:investor_directory', args=['b2b-saas', 'seed', 'california']))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['count'], 1)
        self.assertEqual(list(response.context['profiles']), [InvestorApplication.objects.get(user=self.public_user)])

    def test_no_match_renders_empty_state(self):
        response = self.client.get(reverse('growth:investor_directory', args=['fintech', 'series-a', 'new-york']))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['count'], 0)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ReadinessBadgeTests(TestCase):
    """readiness_badge: 404s for private profiles / unparseable scores, 200s with correct SVG otherwise."""

    def setUp(self):
        _mock_embedding_generation(self)

    def _founder_with_memo(self, username, investment_readiness, is_private=False):
        from zelda_api.vector_models import DocumentSource, IntelligenceMemo

        user = User.objects.create_user(username, password='x')
        Application.objects.create(
            user=user, founder_name='F', email=f'{username}@t.com', company_name='FCo',
            sector='SaaS', stage='Seed', description='test', is_private=is_private,
        )
        doc = DocumentSource.objects.create(filename='deck.pdf', source_entity='FCo', uploaded_by=user, document_type='pitch_deck')
        IntelligenceMemo.objects.create(
            document=doc, executive_summary='Summary.', investment_thesis='Thesis.',
            investment_readiness=investment_readiness,
        )
        return user

    def test_public_founder_with_parseable_score_returns_svg(self):
        self._founder_with_memo('badge_public_founder', 'Score: 87/100\nStrengths: ...')
        response = self.client.get(reverse('growth:readiness_badge', kwargs={'role': 'founder', 'username': 'badge_public_founder'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/svg+xml')
        self.assertIn(b'87/100', response.content)

    def test_private_founder_404s(self):
        self._founder_with_memo('badge_private_founder', 'Score: 90/100', is_private=True)
        response = self.client.get(reverse('growth:readiness_badge', kwargs={'role': 'founder', 'username': 'badge_private_founder'}))
        self.assertEqual(response.status_code, 404)

    def test_unparseable_score_404s(self):
        self._founder_with_memo('badge_no_score_founder', 'No score format here at all.')
        response = self.client.get(reverse('growth:readiness_badge', kwargs={'role': 'founder', 'username': 'badge_no_score_founder'}))
        self.assertEqual(response.status_code, 404)

    def test_unknown_username_404s(self):
        response = self.client.get(reverse('growth:readiness_badge', kwargs={'role': 'founder', 'username': 'does_not_exist_at_all'}))
        self.assertEqual(response.status_code, 404)


class ReadinessScoreParsingTests(TestCase):
    """IntelligenceMemo.readiness_score parses the standard 'Score: XX/100' format, returns None otherwise."""

    def _memo(self, investment_readiness):
        from zelda_api.vector_models import DocumentSource, IntelligenceMemo
        user = User.objects.create_user(f'score_parse_{DocumentSource.objects.count()}', password='x')
        doc = DocumentSource.objects.create(filename='deck.pdf', source_entity='FCo', uploaded_by=user, document_type='pitch_deck')
        return IntelligenceMemo.objects.create(
            document=doc, executive_summary='S', investment_thesis='T', investment_readiness=investment_readiness,
        )

    def test_parses_standard_format(self):
        memo = self._memo('Score: 73/100\nStrengths: Good traction.')
        self.assertEqual(memo.readiness_score, 73)

    def test_returns_none_for_malformed_text(self):
        memo = self._memo('This memo has no score at all.')
        self.assertIsNone(memo.readiness_score)

    def test_returns_none_for_blank_text(self):
        memo = self._memo('')
        self.assertIsNone(memo.readiness_score)

    def test_caps_at_100(self):
        memo = self._memo('Score: 150/100')
        self.assertEqual(memo.readiness_score, 100)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ReferralInviteTests(TestCase):
    """create_referral_invite + consume_referral_if_pending: reward granted exactly once."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('referral_founder', password='x')
        self.founder_app = Application.objects.create(
            user=self.founder_user, founder_name='F', email='rf@t.com', company_name='FCo',
            sector='SaaS', stage='Seed', description='test',
        )

    def test_create_referral_invite_sends_and_persists(self):
        self.client.force_login(self.founder_user)
        response = self.client.post(reverse('growth:create_referral_invite'), {
            'invitee_email': 'lead@t.com', 'role_hint': 'INVESTOR', 'source': 'fundraising_lead',
        })
        self.assertRedirects(response, reverse('matchmaking:fundraising_crm'))
        invite = ReferralInvite.objects.get()
        self.assertEqual(invite.inviter, self.founder_user)
        self.assertEqual(invite.invitee_email, 'lead@t.com')
        self.assertEqual(invite.status, 'PENDING')
        self.assertTrue(invite.code)

    def test_unknown_source_404s(self):
        self.client.force_login(self.founder_user)
        response = self.client.post(reverse('growth:create_referral_invite'), {
            'invitee_email': 'lead@t.com', 'role_hint': 'INVESTOR', 'source': 'not_a_real_source',
        })
        self.assertEqual(response.status_code, 404)

    def test_consume_referral_grants_premium_reward_exactly_once(self):
        invite = ReferralInvite.objects.create(
            inviter=self.founder_user, invitee_email='newinvestor@t.com', role_hint='INVESTOR', source='fundraising_lead',
        )
        new_investor_user = User.objects.create_user('referral_new_investor', password='x')
        new_investor_app = InvestorApplication.objects.create(
            user=new_investor_user, full_name='New I', email='newinvestor@t.com', company_name='NewVC',
            investment_focus='SaaS', investment_stage='Seed',
        )

        request = mock.Mock()
        request.session = {'pending_referral_code': invite.code}

        consume_referral_if_pending(request, new_investor_app)

        self.founder_app.refresh_from_db()
        invite.refresh_from_db()
        self.assertTrue(self.founder_app.is_premium)
        self.assertEqual(invite.status, 'ACCEPTED')
        self.assertTrue(invite.reward_granted)
        self.assertIsNotNone(invite.accepted_at)

    def test_reused_code_does_not_double_grant(self):
        invite = ReferralInvite.objects.create(
            inviter=self.founder_user, invitee_email='newinvestor2@t.com', role_hint='INVESTOR', source='fundraising_lead',
        )
        new_investor_user = User.objects.create_user('referral_new_investor2', password='x')
        new_investor_app = InvestorApplication.objects.create(
            user=new_investor_user, full_name='New I2', email='newinvestor2@t.com', company_name='NewVC2',
            investment_focus='SaaS', investment_stage='Seed',
        )

        request = mock.Mock()
        request.session = {'pending_referral_code': invite.code}
        consume_referral_if_pending(request, new_investor_app)

        # Manually flip the reward off to simulate a staff/billing correction,
        # then try consuming the same (already-ACCEPTED, not PENDING) code
        # again — it must not match the PENDING-only lookup and grant twice.
        self.founder_app.is_premium = False
        self.founder_app.save(update_fields=['is_premium'])

        request2 = mock.Mock()
        request2.session = {'pending_referral_code': invite.code}
        consume_referral_if_pending(request2, new_investor_app)

        self.founder_app.refresh_from_db()
        self.assertFalse(self.founder_app.is_premium)  # still false — no second grant happened

    def test_no_pending_code_is_a_no_op(self):
        request = mock.Mock()
        request.session = {}
        # Should not raise even with nothing to consume.
        consume_referral_if_pending(request, self.founder_app)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SitemapTests(TestCase):
    """Sitemap enumeration only includes combos with >=1 public profile."""

    def setUp(self):
        _mock_embedding_generation(self)
        public_user = User.objects.create_user('sitemap_public_investor', password='x')
        private_user = User.objects.create_user('sitemap_private_investor', password='x')

        InvestorApplication.objects.create(
            user=public_user, full_name='Pub', email='sp@t.com', company_name='PubVC',
            investment_focus='FinTech', investment_stage='Series A', location='Texas',
        )
        InvestorApplication.objects.create(
            user=private_user, full_name='Priv', email='spr@t.com', company_name='PrivVC',
            investment_focus='OnlyPrivate', investment_stage='Series A', location='Texas', is_private=True,
        )

    def test_only_public_combo_included(self):
        items = InvestorDirectorySitemap().items()
        slugs = [combo[0] for combo in items]
        self.assertIn(slugify('FinTech'), slugs)
        self.assertNotIn(slugify('OnlyPrivate'), slugs)
