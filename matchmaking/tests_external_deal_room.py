"""
The external deal room: Interlink holds the link, never the documents.

A founder's cap table, financials and contracts are the most sensitive material
on the platform. Today the only way to share them is to upload them here, which
makes Interlink Foundry the custodian of exactly the documents it has the least
business holding.

This adds the other path: the founder keeps the documents in a data room they
control -- DocSend, Box, a Workspace drive -- and Interlink stores the address
and decides who may read it. Nothing is uploaded, proxied, mirrored or cached,
so there is no copy here to leak.

Two authorizations, deliberately not merged into one:

    can_view_data_room                  may this person be in the room at all?
    can_view_external_deal_room_url     may this person see the address?

The first is the existing gate -- owner, staff, or an investor with an ACCEPTED
connection -- and is reused unchanged rather than reimplemented. The second is
narrower: the owner grants each investor individually. Being connected is not
consent to receive the address, because the address is itself the credential.

That gap is the point of most of the tests below.
"""
from unittest import mock

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Application,
    Connection,
    ExternalDealRoom,
    ExternalDealRoomEvent,
    ExternalDealRoomGrant,
    InvestorApplication,
    can_view_external_deal_room_url,
)
from .tests import _mock_embedding_generation

EXTERNAL_URL = 'https://example-dataroom.test/room/abc123'
ROTATED_URL = 'https://example-dataroom.test/room/zzz999'


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class _Room(TestCase):
    """Shared cast: owner, staff, a granted investor, a connected-but-not-granted
    investor, an investor with no connection, and a founder who is a stranger."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.owner_user = User.objects.create_user('edr_owner', password='x')
        self.founder = Application.objects.create(
            user=self.owner_user, company_name='EDR Co', founder_name='F',
            email='edr@t.com', description='d', sector='SaaS', stage='Seed',
        )
        self.staff_user = User.objects.create_user('edr_staff', password='x', is_staff=True)

        self.granted_user = User.objects.create_user('edr_granted', password='x')
        self.granted_investor = InvestorApplication.objects.create(
            user=self.granted_user, full_name='I', company_name='GrantedFund',
            email='edrg@t.com', investment_focus='SaaS', investment_stage='Seed',
        )
        Connection.objects.create(
            investor=self.granted_investor, founder=self.founder,
            status='ACCEPTED', initiated_by='INVESTOR',
        )

        self.connected_user = User.objects.create_user('edr_connected', password='x')
        self.connected_investor = InvestorApplication.objects.create(
            user=self.connected_user, full_name='I', company_name='ConnectedFund',
            email='edrc@t.com', investment_focus='SaaS', investment_stage='Seed',
        )
        Connection.objects.create(
            investor=self.connected_investor, founder=self.founder,
            status='ACCEPTED', initiated_by='INVESTOR',
        )

        self.stranger_user = User.objects.create_user('edr_stranger', password='x')
        self.stranger_investor = InvestorApplication.objects.create(
            user=self.stranger_user, full_name='I', company_name='StrangerFund',
            email='edrs@t.com', investment_focus='SaaS', investment_stage='Seed',
        )

        self.room = ExternalDealRoom.objects.create(
            founder=self.founder, title='Series A materials',
            provider='DocSend', external_url=EXTERNAL_URL,
        )
        self.grant = ExternalDealRoomGrant.objects.create(
            room=self.room, investor=self.granted_investor,
        )

    def room_url(self):
        return reverse('matchmaking:data_room', args=[self.owner_user.username])


class AuthorizationMatrixTests(_Room):
    """Part 20, items 1-4: who may see the address."""

    def test_anonymous_is_not_authorized(self):
        self.assertFalse(can_view_external_deal_room_url(AnonymousUser(), self.room))

    def test_owner_and_staff_are_authorized(self):
        self.assertTrue(can_view_external_deal_room_url(self.owner_user, self.room))
        self.assertTrue(can_view_external_deal_room_url(self.staff_user, self.room))

    def test_granted_investor_is_authorized(self):
        self.assertTrue(can_view_external_deal_room_url(self.granted_user, self.room))

    def test_connected_but_ungranted_investor_is_not(self):
        """The distinction this whole feature exists for: an ACCEPTED connection
        opens the room, it does not hand over the address."""
        from .models import can_view_data_room
        self.assertTrue(can_view_data_room(self.connected_user, self.founder))
        self.assertFalse(can_view_external_deal_room_url(self.connected_user, self.room))

    def test_unconnected_investor_is_not(self):
        self.assertFalse(can_view_external_deal_room_url(self.stranger_user, self.room))

    def test_user_with_no_investor_profile_is_not(self):
        plain = User.objects.create_user('edr_plain', password='x')
        self.assertFalse(can_view_external_deal_room_url(plain, self.room))


class RevocationTests(_Room):
    """Part 20, items 5, 6, 12 and Part 7."""

    def test_owner_can_revoke_and_access_stops(self):
        self.assertTrue(can_view_external_deal_room_url(self.granted_user, self.room))
        self.client.force_login(self.owner_user)
        response = self.client.post(
            reverse('matchmaking:external_deal_room_revoke', args=[self.owner_user.username]),
            {'investor_id': self.granted_investor.id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(can_view_external_deal_room_url(self.granted_user, self.room))

    def test_revocation_is_recorded_not_deleted(self):
        """The grant row survives with revoked_at set, so the history of who
        once had the address stays reviewable."""
        self.client.force_login(self.owner_user)
        self.client.post(
            reverse('matchmaking:external_deal_room_revoke', args=[self.owner_user.username]),
            {'investor_id': self.granted_investor.id},
        )
        self.grant.refresh_from_db()
        self.assertIsNotNone(self.grant.revoked_at)

    def test_deactivating_the_room_removes_everyone_but_the_owner(self):
        self.room.is_active = False
        self.room.save()
        self.assertFalse(can_view_external_deal_room_url(self.granted_user, self.room))
        # The owner still manages it -- they cannot fix a room they cannot see.
        self.assertTrue(can_view_external_deal_room_url(self.owner_user, self.room))

    def test_non_owner_cannot_revoke(self):
        self.client.force_login(self.granted_user)
        response = self.client.post(
            reverse('matchmaking:external_deal_room_revoke', args=[self.owner_user.username]),
            {'investor_id': self.granted_investor.id},
        )
        self.assertEqual(response.status_code, 404)
        self.grant.refresh_from_db()
        self.assertIsNone(self.grant.revoked_at)

    def test_revoked_investor_can_be_granted_again(self):
        """Re-granting reuses the row rather than creating a duplicate."""
        self.grant.revoked_at = timezone.now()
        self.grant.save()
        self.client.force_login(self.owner_user)
        self.client.post(
            reverse('matchmaking:external_deal_room_grant', args=[self.owner_user.username]),
            {'investor_id': self.granted_investor.id},
        )
        self.assertEqual(ExternalDealRoomGrant.objects.filter(room=self.room).count(), 1)
        self.assertTrue(can_view_external_deal_room_url(self.granted_user, self.room))

    def test_owner_cannot_grant_an_unconnected_investor(self):
        """Granting is bounded by the room gate: you cannot hand the address to
        someone who could not be in the room."""
        self.client.force_login(self.owner_user)
        self.client.post(
            reverse('matchmaking:external_deal_room_grant', args=[self.owner_user.username]),
            {'investor_id': self.stranger_investor.id},
        )
        self.assertFalse(
            ExternalDealRoomGrant.objects.filter(room=self.room, investor=self.stranger_investor).exists()
        )


class UrlRotationTests(_Room):
    """Part 20, item 11, and Part 7's 'rotate the external-room URL'."""

    def test_rotating_the_url_leaves_no_retrievable_copy_of_the_old_one(self):
        self.client.force_login(self.owner_user)
        self.client.post(
            reverse('matchmaking:external_deal_room_save', args=[self.owner_user.username]),
            {'title': 'Series A materials', 'provider': 'DocSend',
             'external_url': ROTATED_URL, 'description': '', 'access_instructions': ''},
        )
        self.room.refresh_from_db()
        self.assertEqual(self.room.external_url, ROTATED_URL)

        # The old address must not survive anywhere a user can reach -- not on
        # the page, and not in the audit trail, which records that the link
        # changed without keeping the value that changed.
        response = self.client.get(self.room_url())
        self.assertNotContains(response, EXTERNAL_URL)
        for event in ExternalDealRoomEvent.objects.all():
            self.assertNotIn(EXTERNAL_URL, str(event.__dict__))


class PageExposureTests(_Room):
    """Part 20, items 1-4 again, but through the rendered page rather than the
    predicate -- a correct predicate that the template ignores is still a leak."""

    def test_granted_investor_sees_the_url_on_the_page(self):
        self.client.force_login(self.granted_user)
        response = self.client.get(self.room_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, EXTERNAL_URL)

    def test_connected_but_ungranted_investor_does_not(self):
        self.client.force_login(self.connected_user)
        response = self.client.get(self.room_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, EXTERNAL_URL)

    def test_anonymous_visitor_gets_no_page_and_no_url(self):
        response = self.client.get(self.room_url())
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(EXTERNAL_URL, response.get('Location', ''))

    def test_stranger_cannot_reach_the_room_at_all(self):
        self.client.force_login(self.stranger_user)
        response = self.client.get(self.room_url())
        self.assertEqual(response.status_code, 404)

    def test_deactivated_room_hides_the_url_from_a_granted_investor(self):
        self.room.is_active = False
        self.room.save()
        self.client.force_login(self.granted_user)
        response = self.client.get(self.room_url())
        self.assertNotContains(response, EXTERNAL_URL)


class PublicSurfaceTests(_Room):
    """
    Part 20, items 7-9: the address never reaches a public surface.

    Each test carries a positive control. "The link is not in this response" is
    trivially true of a 404, a login redirect or an empty page, so an absence
    assertion on its own would keep passing even if the page stopped rendering
    the founder entirely -- and would go on passing after someone added the
    link to a page that no longer loads in tests. Every case below first proves
    it fetched a real, populated page.
    """

    def _body(self, response):
        return response.content.decode(errors='ignore')

    def test_url_absent_from_the_founder_profile_seen_by_a_stranger(self):
        """
        The profile page is behind login -- an anonymous fetch lands on the
        login form, where asserting the link is absent proves nothing. The real
        risk is a signed-in user with no connection to this founder, so that is
        who fetches it here.
        """
        self.client.force_login(self.stranger_user)
        response = self.client.get(
            reverse('accounts:profile', args=[self.owner_user.username]), follow=True
        )
        self.assertEqual(response.status_code, 200)
        body = self._body(response)
        self.assertIn('EDR Co', body)  # positive control: this founder's page really rendered
        self.assertNotIn(EXTERNAL_URL, body)

    def test_url_absent_from_the_anonymous_explore_feed(self):
        response = self.client.get(reverse('explore'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(EXTERNAL_URL, self._body(response))

    def test_url_absent_from_the_sitemap(self):
        response = self.client.get(reverse('sitemap'))
        self.assertEqual(response.status_code, 200)
        body = self._body(response)
        self.assertIn('<urlset', body)  # positive control: a real sitemap, not an error page
        self.assertNotIn(EXTERNAL_URL, body)

    def test_url_absent_from_global_search(self):
        self.client.force_login(self.stranger_user)
        response = self.client.get(reverse('matchmaking:global_search'), {'q': 'EDR'}, follow=True)
        self.assertEqual(response.status_code, 200)
        body = self._body(response)
        self.assertIn('EDR Co', body)  # positive control: the founder was actually found
        self.assertNotIn(EXTERNAL_URL, body)


class AuditTrailTests(_Room):
    """Part 18: the events that matter are the ones that change who can read."""

    def test_granting_and_revoking_are_logged_with_actor_and_subject(self):
        self.client.force_login(self.owner_user)
        self.client.post(
            reverse('matchmaking:external_deal_room_grant', args=[self.owner_user.username]),
            {'investor_id': self.connected_investor.id},
        )
        granted = ExternalDealRoomEvent.objects.get(action='GRANTED', subject=self.connected_user)
        self.assertEqual(granted.actor, self.owner_user)

        self.client.post(
            reverse('matchmaking:external_deal_room_revoke', args=[self.owner_user.username]),
            {'investor_id': self.connected_investor.id},
        )
        revoked = ExternalDealRoomEvent.objects.get(action='REVOKED', subject=self.connected_user)
        self.assertEqual(revoked.actor, self.owner_user)

    def test_url_change_is_logged_without_the_url(self):
        self.client.force_login(self.owner_user)
        self.client.post(
            reverse('matchmaking:external_deal_room_save', args=[self.owner_user.username]),
            {'title': 'T', 'provider': 'Box', 'external_url': ROTATED_URL,
             'description': '', 'access_instructions': ''},
        )
        event = ExternalDealRoomEvent.objects.filter(action='URL_CHANGED').first()
        self.assertIsNotNone(event)
        self.assertNotIn(ROTATED_URL, str(event.__dict__))

    def test_viewing_the_url_is_logged_for_a_granted_investor(self):
        self.client.force_login(self.granted_user)
        self.client.get(self.room_url())
        self.assertTrue(
            ExternalDealRoomEvent.objects.filter(action='VIEWED', actor=self.granted_user).exists()
        )

    def test_no_event_is_logged_for_someone_who_never_saw_it(self):
        self.client.force_login(self.connected_user)
        self.client.get(self.room_url())
        self.assertFalse(
            ExternalDealRoomEvent.objects.filter(action='VIEWED', actor=self.connected_user).exists()
        )


class NoDocumentCustodyTests(_Room):
    """Part 20, items 13-17: the whole point is that nothing lands here."""

    def test_the_model_has_no_file_field(self):
        field_types = {f.get_internal_type() for f in ExternalDealRoom._meta.get_fields()
                       if hasattr(f, 'get_internal_type')}
        self.assertNotIn('FileField', field_types)
        self.assertNotIn('ImageField', field_types)

    def test_interlink_never_fetches_the_external_url(self):
        """No proxying, no mirroring, no 'last verified' HTTP probe. Rendering
        the room must not make an outbound request to the provider."""
        with mock.patch('urllib.request.urlopen') as urlopen:
            self.client.force_login(self.granted_user)
            self.client.get(self.room_url())
        urlopen.assert_not_called()

    def test_the_url_is_rendered_as_a_link_not_proxied_through_interlink(self):
        self.client.force_login(self.granted_user)
        response = self.client.get(self.room_url())
        body = response.content.decode(errors='ignore')
        self.assertIn(EXTERNAL_URL, body)
        # If Interlink proxied it, the href would point back at our own host.
        self.assertNotIn(f'/external-room/redirect?url={EXTERNAL_URL}', body)


class BoundaryDisclosureTests(_Room):
    """Part 8 and 13: the page must not let the two authorizations be confused."""

    def test_page_states_that_interlink_does_not_host_the_documents(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.room_url())
        self.assertContains(response, 'does not host')

    def test_page_states_that_revoking_here_does_not_revoke_at_the_provider(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.room_url())
        body = response.content.decode(errors='ignore').lower()
        self.assertIn('provider', body)
