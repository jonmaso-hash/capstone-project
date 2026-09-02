import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from matchmaking.tests import _mock_embedding_generation
from matchmaking.models import Application, InvestorApplication, SellerApplication, BuyerApplication

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ResolveShareProfileTests(TestCase):
    """
    sharing.views._resolve_profile — the fourth shareable content type.
    content_id is the User's id (one role profile per user). Deliberately
    a STRICTER bar than the profile page's own gate: not private AND not
    archived, for every role (the page itself never blocks Investor/Buyer
    on is_private, and doesn't consider archived_at at all) — a share
    promises "this is a live, good-standing profile," not merely "this
    URL happens not to 404 for you."
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('rsp_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='RSPCo', founder_name='Jane Founder', email='rspf@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.investor_user = User.objects.create_user('rsp_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='Ivan Investor', company_name='RSPFund', email='rspi@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.viewer = User.objects.create_user('rsp_viewer', password='x')
        self.client.force_login(self.viewer)

    def _resolve(self, content_id):
        return self.client.get(reverse('sharing:resolve_share'), {'content_type': 'PROFILE', 'content_id': content_id})

    def test_public_founder_profile_is_available_with_person_name_and_role_subtitle(self):
        data = self._resolve(self.founder_user.id).json()
        self.assertTrue(data['available'])
        self.assertEqual(data['title'], 'Jane Founder')
        self.assertEqual(data['subtitle'], 'Founder · RSPCo')
        self.assertEqual(data['view_url'], reverse('accounts:profile', kwargs={'username': self.founder_user.username}))

    def test_public_investor_profile_is_available(self):
        data = self._resolve(self.investor_user.id).json()
        self.assertTrue(data['available'])
        self.assertEqual(data['title'], 'Ivan Investor')
        self.assertEqual(data['subtitle'], 'Investor · RSPFund')

    def test_private_founder_profile_is_unavailable(self):
        self.founder.is_private = True
        self.founder.save(update_fields=['is_private'])
        self.assertFalse(self._resolve(self.founder_user.id).json()['available'])

    def test_archived_founder_profile_is_unavailable(self):
        self.founder.archive()
        self.assertFalse(self._resolve(self.founder_user.id).json()['available'])

    def test_private_investor_profile_is_unavailable_even_though_the_page_itself_would_still_render(self):
        """The share resolver is deliberately stricter than accounts.views.
        profile's own gate — that view never blocks Investor/Buyer on
        is_private at all."""
        self.investor.is_private = True
        self.investor.save(update_fields=['is_private'])
        self.assertFalse(self._resolve(self.investor_user.id).json()['available'])

    def test_permission_change_after_share_is_respected_immediately(self):
        response_before = self._resolve(self.founder_user.id)
        self.assertTrue(response_before.json()['available'])

        self.founder.is_private = True
        self.founder.save(update_fields=['is_private'])

        response_after = self._resolve(self.founder_user.id)
        self.assertFalse(response_after.json()['available'])

    def test_deleted_user_is_unavailable(self):
        user_id = self.founder_user.id
        self.founder_user.delete()
        self.assertFalse(self._resolve(user_id).json()['available'])

    def test_inactive_user_is_unavailable(self):
        self.founder_user.is_active = False
        self.founder_user.save(update_fields=['is_active'])
        self.assertFalse(self._resolve(self.founder_user.id).json()['available'])

    def test_user_with_no_role_profile_is_unavailable(self):
        bare_user = User.objects.create_user('rsp_bare', password='x')
        self.assertFalse(self._resolve(bare_user.id).json()['available'])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], MEDIA_ROOT=tempfile.mkdtemp())
class ResolveShareVideoFounderTests(TestCase):
    """
    sharing.views.resolve_share for VIDEO_FOUNDER — matchmaking.models.
    can_view_pitch_video is the single authority here; these tests prove
    the resolver actually defers to it correctly, and — the core security
    property requested — that access is evaluated for the CURRENT
    requesting viewer, never baked in from whenever a share was sent.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('rsv_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='RSVCo', founder_name='F', email='rsvf@t.com',
            description='test', sector='SaaS', stage='Seed',
            pitch_video=SimpleUploadedFile('pitch.mp4', b'x', content_type='video/mp4'),
        )
        self.investor_user = User.objects.create_user('rsv_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='RSVFund', email='rsvi@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.stranger_user = User.objects.create_user('rsv_stranger', password='x')

    def _resolve(self, user, content_id=None):
        self.client.force_login(user)
        return self.client.get(reverse('sharing:resolve_share'), {
            'content_type': 'VIDEO_FOUNDER', 'content_id': content_id or self.founder.id,
        })

    def test_owner_can_always_view_own_video(self):
        response = self._resolve(self.founder_user)
        data = response.json()
        self.assertTrue(data['available'])
        self.assertIn('RSVCo', data['title'])

    def test_site_wide_video_visible_to_any_authenticated_user(self):
        response = self._resolve(self.stranger_user)
        self.assertTrue(response.json()['available'])

    def test_role_only_video_visible_to_investor_not_to_stranger(self):
        """The exact Alice/Bob/Charlie property: whether the card is
        available depends on WHO is asking right now, not on who shared it."""
        self.founder.pitch_video_visibility = 'ROLE_ONLY'
        self.founder.save(update_fields=['pitch_video_visibility'])

        investor_response = self._resolve(self.investor_user)
        self.assertTrue(investor_response.json()['available'])

        stranger_response = self._resolve(self.stranger_user)
        self.assertFalse(stranger_response.json()['available'])

    def test_private_profile_blocks_non_owner_even_when_site_wide(self):
        self.founder.is_private = True
        self.founder.save(update_fields=['is_private'])
        response = self._resolve(self.stranger_user)
        self.assertFalse(response.json()['available'])

    def test_staff_hidden_blocks_non_owner(self):
        self.founder.is_hidden_by_staff = True
        self.founder.save(update_fields=['is_hidden_by_staff'])
        response = self._resolve(self.stranger_user)
        self.assertFalse(response.json()['available'])

    def test_staff_can_always_view(self):
        staff_user = User.objects.create_user('rsv_staff', password='x', is_staff=True)
        self.founder.is_private = True
        self.founder.save(update_fields=['is_private'])
        response = self._resolve(staff_user)
        self.assertTrue(response.json()['available'])

    def test_permission_change_after_share_is_respected_immediately(self):
        """The key requirement: a video shared while SITE_WIDE must become
        unavailable to a non-investor the moment the owner tightens
        visibility — the resolver must never trust a stale snapshot."""
        response_before = self._resolve(self.stranger_user)
        self.assertTrue(response_before.json()['available'])

        self.founder.pitch_video_visibility = 'ROLE_ONLY'
        self.founder.save(update_fields=['pitch_video_visibility'])

        response_after = self._resolve(self.stranger_user)
        self.assertFalse(response_after.json()['available'])

    def test_no_video_uploaded_is_unavailable(self):
        no_video_founder_user = User.objects.create_user('rsv_no_video', password='x')
        no_video_founder = Application.objects.create(
            user=no_video_founder_user, company_name='NoVideoCo', founder_name='F', email='novideo@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        response = self._resolve(self.stranger_user, content_id=no_video_founder.id)
        self.assertFalse(response.json()['available'])

    def test_nonexistent_application_is_unavailable_not_an_error(self):
        response = self._resolve(self.stranger_user, content_id=999999)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['available'])

    def test_unauthenticated_request_redirects_to_login(self):
        response = self.client.get(reverse('sharing:resolve_share'), {
            'content_type': 'VIDEO_FOUNDER', 'content_id': self.founder.id,
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], MEDIA_ROOT=tempfile.mkdtemp())
class ResolveShareVideoSellerTests(TestCase):
    """M&A mirror — ROLE_ONLY means buyers-only for a seller's video."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.seller_user = User.objects.create_user('rsvs_seller', password='x')
        self.seller = SellerApplication.objects.create(
            user=self.seller_user, company_name='RSVSCo', seller_name='S', email='rsvss@t.com',
            description='test', industry='SaaS',
            pitch_video=SimpleUploadedFile('pitch.mp4', b'x', content_type='video/mp4'),
        )
        self.buyer_user = User.objects.create_user('rsvs_buyer', password='x')
        BuyerApplication.objects.create(
            user=self.buyer_user, full_name='B', company_name='RSVSAcquirer', email='rsvsb@t.com',
        )
        self.stranger_user = User.objects.create_user('rsvs_stranger', password='x')

    def _resolve(self, user, content_id=None):
        self.client.force_login(user)
        return self.client.get(reverse('sharing:resolve_share'), {
            'content_type': 'VIDEO_SELLER', 'content_id': content_id or self.seller.id,
        })

    def test_role_only_video_visible_to_buyer_not_to_stranger(self):
        self.seller.pitch_video_visibility = 'ROLE_ONLY'
        self.seller.save(update_fields=['pitch_video_visibility'])

        self.assertTrue(self._resolve(self.buyer_user).json()['available'])
        self.assertFalse(self._resolve(self.stranger_user).json()['available'])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ResolveShareBlogTests(TestCase):
    """Blog articles have no privacy field at all — existence is the only question."""

    def setUp(self):
        self.author = User.objects.create_user('rsb_author', password='x')
        self.viewer = User.objects.create_user('rsb_viewer', password='x')
        from blog.models import Article
        self.article = Article.objects.create(title='A Real Post', body='body', author=self.author)

    def test_existing_article_is_available_to_any_authenticated_user(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('sharing:resolve_share'), {
            'content_type': 'BLOG', 'content_id': self.article.id,
        })
        data = response.json()
        self.assertTrue(data['available'])
        self.assertEqual(data['title'], 'A Real Post')

    def test_deleted_article_is_unavailable(self):
        article_id = self.article.id
        self.article.delete()
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('sharing:resolve_share'), {
            'content_type': 'BLOG', 'content_id': article_id,
        })
        self.assertFalse(response.json()['available'])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ResolveShareJobTests(TestCase):
    """JobListing has no privacy field — only is_active/is_expired govern availability."""

    def setUp(self):
        self.poster = User.objects.create_user('rsj_poster', password='x')
        self.viewer = User.objects.create_user('rsj_viewer', password='x')
        from jobs.models import JobListing
        self.JobListing = JobListing
        self.job = JobListing.objects.create(
            poster=self.poster, company_name='JobCo', title='Engineer', description='Build things.',
        )

    def _resolve(self, content_id=None):
        self.client.force_login(self.viewer)
        return self.client.get(reverse('sharing:resolve_share'), {
            'content_type': 'JOB', 'content_id': content_id or self.job.id,
        })

    def test_active_job_is_available(self):
        data = self._resolve().json()
        self.assertTrue(data['available'])
        self.assertEqual(data['title'], 'Engineer')
        self.assertEqual(data['subtitle'], 'JobCo')

    def test_inactive_job_is_unavailable(self):
        self.job.is_active = False
        self.job.save(update_fields=['is_active'])
        self.assertFalse(self._resolve().json()['available'])

    def test_expired_job_is_unavailable(self):
        from django.utils import timezone
        from datetime import timedelta
        self.job.expires_at = timezone.now() - timedelta(days=1)
        self.job.save(update_fields=['expires_at'])
        self.assertFalse(self._resolve().json()['available'])

    def test_deleted_job_is_unavailable(self):
        job_id = self.job.id
        self.job.delete()
        self.assertFalse(self._resolve(content_id=job_id).json()['available'])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ResolveShareMalformedInputTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('rsm_user', password='x')
        self.client.force_login(self.user)

    def test_unknown_content_type_is_unavailable_not_an_error(self):
        response = self.client.get(reverse('sharing:resolve_share'), {
            'content_type': 'SOMETHING_MADE_UP', 'content_id': '1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['available'])

    def test_non_numeric_content_id_is_unavailable_not_an_error(self):
        response = self.client.get(reverse('sharing:resolve_share'), {
            'content_type': 'BLOG', 'content_id': 'not-a-number',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['available'])

    def test_missing_params_is_unavailable_not_an_error(self):
        response = self.client.get(reverse('sharing:resolve_share'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['available'])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UserSearchTests(TestCase):
    """
    sharing.views.user_search — the share-picker's mechanical lookup.
    No AI, minimal fields only (no email, no financial data).
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.searcher = User.objects.create_user('us_searcher', password='x')
        self.client.force_login(self.searcher)

        self.founder_user = User.objects.create_user('us_findable_founder', password='x')
        Application.objects.create(
            user=self.founder_user, company_name='Findable Widgets Co', founder_name='F', email='usf@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.investor_user = User.objects.create_user('us_findable_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Findable Capital', email='usi@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.staff_user = User.objects.create_user('us_staff_findable', password='x', is_staff=True)
        self.inactive_user = User.objects.create_user('us_inactive_findable', password='x', is_active=False)

    def _search(self, q):
        return self.client.get(reverse('sharing:user_search'), {'q': q}).json()

    def test_query_too_short_returns_empty(self):
        self.assertEqual(self._search('a')['results'], [])

    def test_matches_by_username(self):
        results = self._search('findable_founder')
        self.assertTrue(any(r['username'] == 'us_findable_founder' for r in results['results']))

    def test_matches_by_founder_company_name(self):
        results = self._search('Findable Widgets')
        self.assertTrue(any(r['display_name'] == 'Findable Widgets Co' for r in results['results']))
        matched = next(r for r in results['results'] if r['username'] == 'us_findable_founder')
        self.assertEqual(matched['role_label'], 'Founder')

    def test_matches_by_investor_company_name(self):
        results = self._search('Findable Capital')
        matched = next(r for r in results['results'] if r['username'] == 'us_findable_investor')
        self.assertEqual(matched['role_label'], 'Investor')

    def test_excludes_staff(self):
        results = self._search('us_staff_findable')
        self.assertEqual(results['results'], [])

    def test_excludes_inactive_users(self):
        results = self._search('us_inactive_findable')
        self.assertEqual(results['results'], [])

    def test_excludes_self(self):
        results = self._search('us_searcher')
        self.assertEqual(results['results'], [])

    def test_result_fields_are_minimal_no_sensitive_data(self):
        results = self._search('findable_founder')
        for r in results['results']:
            self.assertEqual(set(r.keys()), {'id', 'username', 'display_name', 'role_label'})

    def test_unauthenticated_request_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(reverse('sharing:user_search'), {'q': 'findable'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)
