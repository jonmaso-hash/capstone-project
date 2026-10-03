"""
Phase 1 Task 1: the Principal. These are the bypass tests that ship with the
boundary (locked contract, point 4): every way of getting a principal without
a real, active user must refuse, and no unrestricted principal may exist.
"""
import ast
import dataclasses
import inspect
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from zelda_api import principal as principal_module
from zelda_api.principal import (
    IMPERSONATOR_SESSION_KEY, ORIGIN_COMMAND, ORIGIN_HTTP, ORIGIN_TASK,
    Principal, PrincipalRequired, require_principal,
)

User = get_user_model()


def _request(user, impersonator_id=None):
    request = RequestFactory().get('/')
    request.user = user
    request.session = SessionStore()
    if impersonator_id is not None:
        request.session[IMPERSONATOR_SESSION_KEY] = impersonator_id
    return request


class _Users(TestCase):

    def setUp(self):
        self.founder = User.objects.create_user('pr_founder', password='x')
        self.staff = User.objects.create_user('pr_staff', password='x', is_staff=True)
        self.other_staff = User.objects.create_user('pr_staff2', password='x', is_staff=True)


class NoUserRefusesTests(_Users):
    """Absence is never read as unrestricted."""

    def test_anonymous_request_refuses(self):
        with self.assertRaises(PrincipalRequired):
            Principal.from_request(_request(AnonymousUser()))

    def test_request_without_user_attribute_refuses(self):
        request = RequestFactory().get('/')
        request.session = SessionStore()
        with self.assertRaises(PrincipalRequired):
            Principal.from_request(request)

    def test_none_user_refuses(self):
        with self.assertRaises(PrincipalRequired):
            Principal.for_user(None, ORIGIN_TASK)

    def test_unsaved_user_refuses(self):
        with self.assertRaises(PrincipalRequired):
            Principal.for_user(User(username='ghost'), ORIGIN_TASK)

    def test_deactivated_user_refuses(self):
        self.founder.is_active = False
        self.founder.save()
        with self.assertRaises(PrincipalRequired):
            Principal.from_request(_request(self.founder))
        with self.assertRaises(PrincipalRequired):
            Principal.for_user(self.founder, ORIGIN_TASK)

    def test_unknown_origin_refuses(self):
        with self.assertRaises(PrincipalRequired):
            Principal(user=self.founder, origin='system')

    def test_for_user_cannot_mint_an_http_principal(self):
        # HTTP principals must come from the request, so impersonation is seen.
        with self.assertRaises(PrincipalRequired):
            Principal.for_user(self.founder, ORIGIN_HTTP)

    def test_require_principal_refuses_none_and_lookalikes(self):
        for value in (None, self.founder, {'user_id': self.founder.pk}, 'system'):
            with self.subTest(value=value), self.assertRaises(PrincipalRequired):
                require_principal(value)

    def test_refusal_is_a_permission_denied(self):
        self.assertTrue(issubclass(PrincipalRequired, PermissionDenied))


class RefusalIsA403Tests(_Users):
    """A refusal reaches the client as 403 -- not a 500, not a result."""

    class _Probe(APIView):
        authentication_classes = []
        permission_classes = []

        def get(self, request):
            require_principal(None)

    def test_drf_view_answers_403(self):
        response = self._Probe.as_view()(APIRequestFactory().get('/'))
        self.assertEqual(response.status_code, 403)


class ValidPrincipalTests(_Users):
    """Positive controls: the refusals above are not refusing everything."""

    def test_request_principal(self):
        p = Principal.from_request(_request(self.founder), label='zelda_api:document_rag')
        self.assertEqual(p.user, self.founder)
        self.assertEqual(p.user_id, self.founder.pk)
        self.assertEqual(p.origin, ORIGIN_HTTP)
        self.assertEqual(p.label, 'zelda_api:document_rag')
        self.assertIsNone(p.actor)
        self.assertFalse(p.read_only)
        self.assertFalse(p.is_impersonated)
        self.assertIs(require_principal(p), p)

    def test_task_and_command_principals(self):
        for origin in (ORIGIN_TASK, ORIGIN_COMMAND):
            with self.subTest(origin=origin):
                p = Principal.for_user(self.founder, origin, label='monitor')
                self.assertEqual((p.user, p.origin, p.read_only), (self.founder, origin, False))

    def test_staff_are_principals_like_anyone_else(self):
        p = Principal.from_request(_request(self.staff))
        self.assertEqual(p.user, self.staff)
        self.assertFalse(p.is_impersonated)

    def test_principal_is_immutable(self):
        p = Principal.for_user(self.founder, ORIGIN_TASK)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            p.user = self.staff


class ImpersonationTests(_Users):
    """Staff "view as": the subject is the user, the actor is recorded, nothing is writable."""

    def test_view_as_is_the_user_read_only_with_actor(self):
        p = Principal.from_request(_request(self.founder, impersonator_id=self.staff.pk))
        self.assertEqual(p.user, self.founder)
        self.assertEqual(p.actor, self.staff)
        self.assertTrue(p.read_only)
        self.assertTrue(p.is_impersonated)

    def test_impersonator_who_lost_staff_refuses(self):
        self.staff.is_staff = False
        self.staff.save()
        with self.assertRaises(PrincipalRequired):
            Principal.from_request(_request(self.founder, impersonator_id=self.staff.pk))

    def test_deleted_impersonator_refuses(self):
        staff_id = self.staff.pk
        self.staff.delete()
        with self.assertRaises(PrincipalRequired):
            Principal.from_request(_request(self.founder, impersonator_id=staff_id))

    def test_impersonation_cannot_be_writable(self):
        with self.assertRaises(PrincipalRequired):
            Principal(user=self.founder, origin=ORIGIN_HTTP, actor=self.staff, read_only=False)

    def test_non_staff_cannot_act_as_another_user(self):
        with self.assertRaises(PrincipalRequired):
            Principal(user=self.staff, origin=ORIGIN_HTTP, actor=self.founder, read_only=True)

    def test_cannot_impersonate_self(self):
        with self.assertRaises(PrincipalRequired):
            Principal(user=self.staff, origin=ORIGIN_HTTP, actor=self.staff, read_only=True)


class TaskBoundaryTests(_Users):
    """Crossing into Celery re-validates; a stale payload never grants access."""

    def test_round_trip_is_json_safe_and_equal(self):
        p = Principal.from_request(_request(self.founder, impersonator_id=self.staff.pk), label='v')
        payload = json.loads(json.dumps(p.to_task_payload()))
        self.assertEqual(Principal.from_task_payload(payload), p)

    def test_user_deactivated_after_queueing_refuses(self):
        payload = Principal.for_user(self.founder, ORIGIN_TASK).to_task_payload()
        self.founder.is_active = False
        self.founder.save()
        with self.assertRaises(PrincipalRequired):
            Principal.from_task_payload(payload)

    def test_user_deleted_after_queueing_refuses(self):
        payload = Principal.for_user(self.founder, ORIGIN_TASK).to_task_payload()
        self.founder.delete()
        with self.assertRaises(PrincipalRequired):
            Principal.from_task_payload(payload)

    def test_actor_demoted_after_queueing_refuses(self):
        payload = Principal.from_request(_request(self.founder, impersonator_id=self.staff.pk)).to_task_payload()
        self.staff.is_staff = False
        self.staff.save()
        with self.assertRaises(PrincipalRequired):
            Principal.from_task_payload(payload)

    def test_malformed_payloads_refuse(self):
        for payload in (None, {}, {'user_id': None}, 'user:1', [self.founder.pk],
                        {'user_id': self.founder.pk, 'origin': 'system'}):
            with self.subTest(payload=payload), self.assertRaises(PrincipalRequired):
                Principal.from_task_payload(payload)

    def test_tampered_payload_cannot_drop_read_only(self):
        payload = Principal.from_request(_request(self.founder, impersonator_id=self.staff.pk)).to_task_payload()
        payload['read_only'] = False
        with self.assertRaises(PrincipalRequired):
            Principal.from_task_payload(payload)


# -- structural guards -------------------------------------------------------

UNRESTRICTED_NAMES = ('system', 'anonymous', 'internal', 'unrestricted', 'superuser', 'root', 'service')
# What a principal is allowed to be made of. Entitlements are resolved from
# `user` by the existing authorities; a field here would be a second,
# stale-able authority.
ALLOWED_FIELDS = {'user', 'origin', 'label', 'actor', 'read_only'}


def unrestricted_constructors(source):
    """Names of functions/methods in `source` that look like a principal-without-a-user."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name.lower()
            if any(word in name for word in UNRESTRICTED_NAMES):
                found.append(node.name)
    return found


class StructuralTests(TestCase):

    def test_no_unrestricted_principal_constructor_exists(self):
        source = inspect.getsource(principal_module)
        self.assertEqual(unrestricted_constructors(source), [])

    def test_the_scan_can_fail(self):
        # Mutation: the escape hatch this guard exists to stop. If the scan
        # cannot see it, the test above proves nothing.
        mutated = inspect.getsource(principal_module).replace(
            '    @classmethod\n    def for_user(',
            '    @classmethod\n    def system(cls):\n        return cls.__new__(cls)\n\n'
            '    @classmethod\n    def for_user(',
        )
        self.assertNotEqual(mutated, inspect.getsource(principal_module), 'mutation did not apply')
        self.assertEqual(unrestricted_constructors(mutated), ['system'])

    def test_principal_holds_no_entitlement_snapshot(self):
        self.assertEqual({f.name for f in dataclasses.fields(Principal)}, ALLOWED_FIELDS)
