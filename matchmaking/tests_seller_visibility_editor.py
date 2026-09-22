"""
The page where a seller sets who sees each of their four controlled fields.

The rule this editor lives under:

    Sellers control disclosure of their own four fields across
    PUBLIC / CONNECTED / PRIVATE. Independent authorities remain independent
    and cannot be widened by field visibility.

So two things are tested, and the second matters more than the first.

    The editor changes real authority -- a choice made on the page is the
    answer can_view_profile_field gives afterwards.

    The editor changes nothing else. The CIM, the deal workspace, the pitch
    video and a private listing's absence from discovery each have their own
    gate. Setting every field PUBLIC must not open any of them, and setting
    every field PRIVATE must not close any of them for a buyer who has
    earned them. Each independence test also proves the field itself moved,
    so an editor that silently did nothing cannot pass it.
"""
import json
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import AnonymousUser, User
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse

from .models import (
    AcquisitionConnection, FIELD_CONNECTED, FIELD_PRIVATE, FIELD_PUBLIC,
    SELLER_FIELD_VISIBILITY, SellerApplication, can_view_pitch_video,
    can_view_profile_field, profile_field_level,
)
from .tests_seller_field_visibility import _SellerCast

URL_NAME = 'usersettings:edit_seller_profile'


class _EditorCast(_SellerCast):

    def form_payload(self, seller=None, **overrides):
        """Every field the listing form requires, taken from the listing itself."""
        seller = seller or self.seller
        payload = {
            'company_name': seller.company_name,
            'seller_name': seller.seller_name,
            'email': seller.email,
            'description': seller.description,
            'industry': seller.industry,
            'geography': seller.geography or '',
            'annual_revenue': seller.annual_revenue or '',
            'ebitda': seller.ebitda or '',
            'asking_price': seller.asking_price,
            'deal_structure': seller.deal_structure,
            'years_in_business': seller.years_in_business or 0,
            'reason_for_sale': seller.reason_for_sale or '',
        }
        payload.update(overrides)
        return payload

    def save_as(self, user, seller=None, **visibility):
        """
        Submit the editor as `user`, with visibility__<field> selections.

        Asserts the form was accepted. Without that, every "was not stored"
        assertion below would also pass for a form that failed validation and
        saved nothing at all.
        """
        self.client.force_login(user)
        response = self.client.post(
            reverse(URL_NAME),
            self.form_payload(seller, **{f'visibility__{k}': v for k, v in visibility.items()}),
        )
        errors = response.context['form'].errors if response.status_code == 200 else ''
        self.assertEqual(response.status_code, 302, errors)
        self.seller.refresh_from_db()
        return response


class SellerEditorControlsTests(_EditorCast):
    """The editor changes real authority, and only for known field/level pairs."""

    def page(self):
        self.client.force_login(self.seller_user)
        response = self.client.get(reverse(URL_NAME))
        self.assertEqual(response.status_code, 200)
        return response.content.decode(errors='ignore')

    def test_the_page_offers_a_control_for_every_governed_field(self):
        body = self.page()
        for name in SELLER_FIELD_VISIBILITY:
            self.assertIn(f'name="visibility__{name}"', body, name)

    def test_the_page_offers_all_three_levels_for_every_field(self):
        self.page()
        response = self.client.get(reverse(URL_NAME))
        rows = response.context['visibility_rows']
        self.assertEqual([r['name'] for r in rows], list(SELLER_FIELD_VISIBILITY))
        levels = [value for value, _ in response.context['visibility_choices']]
        self.assertEqual(levels, [FIELD_PUBLIC, FIELD_CONNECTED, FIELD_PRIVATE])

    def test_the_page_speaks_of_buyers_not_investors(self):
        """The founder labels say 'investors'; on a listing that would be false."""
        self.page()
        response = self.client.get(reverse(URL_NAME))
        labels = ' '.join(label for _, label in response.context['visibility_choices'])
        self.assertIn('buyers', labels)
        self.assertNotIn('investor', labels.lower())

    def test_the_page_shows_the_level_currently_in_force(self):
        """The declared default where the seller has chosen nothing, their choice where they have."""
        self.tighten(self.seller, 'ebitda', FIELD_PRIVATE)
        self.page()
        rows = {r['name']: r['level'] for r in self.client.get(reverse(URL_NAME)).context['visibility_rows']}
        self.assertEqual(rows, {
            'asking_price': FIELD_PUBLIC,
            'annual_revenue': FIELD_CONNECTED,
            'ebitda': FIELD_PRIVATE,
            'reason_for_sale': FIELD_CONNECTED,
        })

    def test_a_seller_can_open_a_field_to_everyone(self):
        self.assertFalse(can_view_profile_field(self.stranger_user, self.seller, 'annual_revenue'))
        self.save_as(self.seller_user, annual_revenue=FIELD_PUBLIC)
        self.assertEqual(profile_field_level(self.seller, 'annual_revenue'), FIELD_PUBLIC)
        self.assertTrue(can_view_profile_field(self.stranger_user, self.seller, 'annual_revenue'))
        self.assertTrue(can_view_profile_field(AnonymousUser(), self.seller, 'annual_revenue'))

    def test_a_seller_can_close_the_asking_price_completely(self):
        self.save_as(self.seller_user, asking_price=FIELD_PRIVATE)
        self.assertFalse(can_view_profile_field(self.connected_user, self.seller, 'asking_price'))
        self.assertFalse(can_view_profile_field(self.stranger_user, self.seller, 'asking_price'))
        self.assertTrue(can_view_profile_field(self.seller_user, self.seller, 'asking_price'))

    def test_a_seller_can_restrict_a_field_to_accepted_buyers(self):
        self.save_as(self.seller_user, asking_price=FIELD_CONNECTED)
        self.assertTrue(can_view_profile_field(self.connected_user, self.seller, 'asking_price'))
        self.assertFalse(can_view_profile_field(self.stranger_user, self.seller, 'asking_price'))

    def test_a_field_left_out_of_the_post_keeps_its_setting(self):
        """Merged, not replaced: a partial submission must not reset other choices."""
        self.tighten(self.seller, 'ebitda', FIELD_PRIVATE)
        self.save_as(self.seller_user, annual_revenue=FIELD_PUBLIC)
        self.assertEqual(profile_field_level(self.seller, 'ebitda'), FIELD_PRIVATE)
        self.assertEqual(profile_field_level(self.seller, 'annual_revenue'), FIELD_PUBLIC)

    def test_a_crafted_level_is_dropped_rather_than_stored(self):
        """
        A hand-made POST must neither be stored nor reach the model validator
        and 500 the page. The valid selection in the same POST is the control:
        it proves the form was saved and only the crafted value was dropped.
        """
        self.save_as(self.seller_user, annual_revenue='EVERYONE', ebitda=FIELD_PUBLIC)
        self.assertEqual(profile_field_level(self.seller, 'annual_revenue'), FIELD_CONNECTED)
        self.assertNotIn('EVERYONE', json.dumps(self.seller.field_visibility))
        self.assertEqual(profile_field_level(self.seller, 'ebitda'), FIELD_PUBLIC)

    def test_a_crafted_field_name_is_ignored(self):
        """Including a founder field and an independently governed resource."""
        self.save_as(
            self.seller_user,
            raising_amount=FIELD_PUBLIC, cim_document=FIELD_PUBLIC, is_private=FIELD_PUBLIC,
            ebitda=FIELD_PUBLIC,
        )
        self.assertEqual(set(self.seller.field_visibility), {'ebitda'})

    def test_the_selects_still_work_while_vector_fields_are_locked(self):
        """
        reason_for_sale is a match-vector field and locks for 30 days after a
        change. The lock is about the matching text, not about who may read it:
        a seller must still be able to hide it.
        """
        from datetime import timedelta
        from django.utils import timezone
        # Locked = every vector field filled, and past the 24h grace period.
        SellerApplication.objects.filter(pk=self.seller.pk).update(
            extra_info='Family owned.', vector_fields_updated_at=timezone.now() - timedelta(days=2),
        )
        self.seller.refresh_from_db()
        self.assertTrue(self.seller.vector_fields_locked)
        self.save_as(self.seller_user, reason_for_sale=FIELD_PRIVATE)
        self.assertFalse(can_view_profile_field(self.connected_user, self.seller, 'reason_for_sale'))

    def test_a_new_listing_starts_with_the_sellers_choices(self):
        newcomer = User.objects.create_user('sfv_new_seller', password='x')
        self.client.force_login(newcomer)
        payload = self.form_payload(**{
            'company_name': 'Fresh Co', 'email': 'fresh@t.com',
            'visibility__ebitda': FIELD_PRIVATE,
        })
        response = self.client.post(reverse(URL_NAME), payload)
        self.assertEqual(response.status_code, 302)
        fresh = SellerApplication.objects.get(user=newcomer)
        self.assertEqual(profile_field_level(fresh, 'ebitda'), FIELD_PRIVATE)
        self.assertEqual(profile_field_level(fresh, 'annual_revenue'), FIELD_CONNECTED)

    def test_another_seller_cannot_set_visibility_on_this_listing(self):
        """The editor works on request.user's own listing, never one named in a POST."""
        other_user = User.objects.create_user('sfv_other_seller', password='x')
        other = self._seller(other_user, 'Other Co', PRICE_OTHER)
        self.client.force_login(other_user)
        response = self.client.post(
            reverse(URL_NAME),
            self.form_payload(other, **{'visibility__annual_revenue': FIELD_PUBLIC, 'id': self.seller.pk}),
        )
        self.assertEqual(response.status_code, 302)
        self.seller.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(profile_field_level(self.seller, 'annual_revenue'), FIELD_CONNECTED)
        self.assertEqual(profile_field_level(other, 'annual_revenue'), FIELD_PUBLIC)

    def test_an_anonymous_post_changes_nothing(self):
        response = self.client.post(
            reverse(URL_NAME), self.form_payload(**{'visibility__annual_revenue': FIELD_PUBLIC}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])
        self.seller.refresh_from_db()
        self.assertEqual(profile_field_level(self.seller, 'annual_revenue'), FIELD_CONNECTED)


PRICE_OTHER = 900_000

_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=_MEDIA)
class FieldVisibilityNeverBecomesAuthorityTests(_EditorCast):
    """
    Changing the seller's field visibility may widen or narrow visibility of
    that field, but it must never widen -- or narrow -- visibility of an
    independently governed resource.

    One snapshot of every such answer, for every viewer who is not the owner,
    is taken before the editor is used and compared after it. The snapshot is
    itself checked to contain both a granted and a refused answer per resource:
    otherwise "unchanged" is also what a dead endpoint looks like.
    """

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        super().setUp()
        # A real CIM on disk, so the endpoint's "allowed" answer is a 200 and
        # distinguishable from its "refused or absent" 404.
        storage = self.seller.cim_document.storage
        cim = storage.save('cim_documents/acme.pdf', ContentFile(b'%PDF-1.4 cim'))
        video = storage.save('pitch_videos/acme.mp4', ContentFile(b'mp4'))
        SellerApplication.objects.filter(pk=self.seller.pk).update(
            cim_document=cim, pitch_video=video, pitch_video_visibility='ROLE_ONLY',
        )
        self.seller.refresh_from_db()
        self.accepted = AcquisitionConnection.objects.get(buyer=self.connected_buyer, seller=self.seller)
        self.pending_user, self.pending_buyer = self._buyer('sfv_pending')
        self.pending = AcquisitionConnection.objects.create(
            buyer=self.pending_buyer, seller=self.seller, status='PENDING', initiated_by='BUYER',
        )
        self.plain_user = User.objects.create_user('sfv_plain', password='x')  # no buyer profile

    def viewers(self):
        return {
            'anonymous': None,
            'plain': self.plain_user,
            'stranger': self.stranger_user,
            'pending': self.pending_user,
            'connected': self.connected_user,
        }

    def status(self, user, url):
        self.client.logout()
        if user is not None:
            self.client.force_login(user)
        return self.client.get(url).status_code

    def has_cim(self, user):
        self.client.force_login(user)
        constraints = [{'field': 'industry', 'qualifier': 'exact', 'value': 'Manufacturing'}]
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction',
                        return_value={'constraints': constraints}):
            response = self.client.post(
                reverse('zelda_api:ask'), data=json.dumps({'q': 'businesses'}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        row = next(r for r in response.json()['results'] if r['company_name'] == 'Acme Widgets')
        return row['has_cim']

    def snapshot(self):
        cim_url = reverse('matchmaking:cim_document_serve', args=[self.seller.pk])
        accepted_url = reverse('matchmaking:acquisition_deal_workspace', args=[self.accepted.pk])
        pending_url = reverse('matchmaking:acquisition_deal_workspace', args=[self.pending.pk])
        snap = {}
        for label, user in self.viewers().items():
            snap[('cim_endpoint', label)] = self.status(user, cim_url)
            snap[('accepted_workspace', label)] = self.status(user, accepted_url)
            snap[('pending_workspace', label)] = self.status(user, pending_url)
            snap[('pitch_video', label)] = can_view_pitch_video(user or AnonymousUser(), self.seller)
            # Ask Zelda searches listings only for buyers; the others never
            # receive a seller row, so there is no flag to compare for them.
            if label in ('stranger', 'pending', 'connected'):
                snap[('ask_zelda_has_cim', label)] = self.has_cim(user)
        self.client.logout()
        return snap

    def assert_live(self, snap):
        """Each resource grants someone and refuses someone -- the comparison means something."""
        by_resource = {}
        for (resource, _), answer in snap.items():
            by_resource.setdefault(resource, set()).add(answer)
        # The pending workspace is refused to every non-owner viewer by design;
        # its "granted" control is the accepted workspace, same endpoint.
        by_resource.pop('pending_workspace')
        for resource, answers in by_resource.items():
            self.assertGreater(len(answers), 1, f'{resource} gave one answer to everyone: {answers}')
        self.assertEqual(snap[('cim_endpoint', 'connected')], 200)
        self.assertEqual(snap[('accepted_workspace', 'connected')], 200)

    def set_every_field(self, level):
        self.save_as(self.seller_user, **{name: level for name in SELLER_FIELD_VISIBILITY})
        for name in SELLER_FIELD_VISIBILITY:
            self.assertEqual(profile_field_level(self.seller, name), level, name)

    def test_opening_every_field_widens_nothing_else(self):
        before = self.snapshot()
        self.assert_live(before)
        self.assertFalse(can_view_profile_field(self.stranger_user, self.seller, 'ebitda'))

        self.set_every_field(FIELD_PUBLIC)

        # The field itself did widen -- the editor was not a no-op.
        self.assertTrue(can_view_profile_field(AnonymousUser(), self.seller, 'ebitda'))
        self.assertTrue(can_view_profile_field(self.stranger_user, self.seller, 'reason_for_sale'))
        self.assertEqual(self.snapshot(), before)

    def test_closing_every_field_narrows_nothing_else(self):
        before = self.snapshot()
        self.assert_live(before)

        self.set_every_field(FIELD_PRIVATE)

        self.assertFalse(can_view_profile_field(self.connected_user, self.seller, 'asking_price'))
        self.assertEqual(self.snapshot(), before)


class PrivateListingStaysPrivateTests(_EditorCast):
    """
    A private listing is absent from discovery. Making its figures PUBLIC is
    a statement about the figures, not about whether the listing may be found.
    """

    def board_lists_acme(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse('matchmaking:acquisition_bulletin_board'))
        self.assertEqual(response.status_code, 200)
        return 'Acme Widgets' in response.content.decode(errors='ignore')

    def zelda_lists_acme(self, user):
        self.client.force_login(user)
        constraints = [{'field': 'industry', 'qualifier': 'exact', 'value': 'Manufacturing'}]
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction',
                        return_value={'constraints': constraints}):
            response = self.client.post(
                reverse('zelda_api:ask'), data=json.dumps({'q': 'businesses'}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        return any(r.get('company_name') == 'Acme Widgets' for r in response.json()['results'])

    def profile_shows_acme(self, user):
        # A private listing's profile answers 200 with a "this profile is
        # private" page, so the status code cannot tell the two apart; whether
        # the listing itself is on the page can.
        self.client.force_login(user)
        response = self.client.get(reverse('accounts:profile', args=[self.seller_user.username]))
        self.assertEqual(response.status_code, 200)
        return 'Acme Widgets' in response.content.decode(errors='ignore')

    def test_a_listed_business_is_found_everywhere(self):
        """Control: each discovery surface is live for this listing when it is not private."""
        self.save_as(self.seller_user, **{name: FIELD_PUBLIC for name in SELLER_FIELD_VISIBILITY})
        self.assertTrue(self.board_lists_acme(self.stranger_user))
        self.assertTrue(self.zelda_lists_acme(self.stranger_user))
        self.assertTrue(self.profile_shows_acme(self.stranger_user))

    def test_public_figures_do_not_list_a_private_business(self):
        SellerApplication.objects.filter(pk=self.seller.pk).update(is_private=True)
        self.seller.refresh_from_db()
        before = (self.board_lists_acme(self.stranger_user), self.zelda_lists_acme(self.stranger_user),
                  self.profile_shows_acme(self.stranger_user))
        self.assertEqual(before, (False, False, False))

        self.save_as(self.seller_user, **{name: FIELD_PUBLIC for name in SELLER_FIELD_VISIBILITY})

        self.assertTrue(self.seller.is_private)  # the form did not touch the listing's own switch
        after = (self.board_lists_acme(self.stranger_user), self.zelda_lists_acme(self.stranger_user),
                 self.profile_shows_acme(self.stranger_user))
        self.assertEqual(after, before)
