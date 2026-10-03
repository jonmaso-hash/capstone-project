"""
Who is asking, carried through the intelligence layer.

The AI layer is not an authority; it consumes the authorities that already
exist (document_is_visible_to, truth_delta_unlocked, can_view_profile_field,
.discoverable(), may_establish). Those all take a User at the view. A
Principal is how that User travels past the view -- into retrieval, into a
Celery task, into scheduled monitoring -- without being reconstructed from
request.user somewhere it no longer exists, and without a missing user ever
being read as "unrestricted".

Rules this module enforces:

- No user, no principal. Anonymous, unsaved and deactivated users refuse.
  There is no system, internal or anonymous principal, and there must never
  be one: scheduled work runs AS the user it is for.
- A principal wraps a User; it does not replace one. It holds no
  entitlements of its own. What the principal may see is decided by the
  existing User-based authorities (and, from Phase 1 Task 2, the resolver
  that calls them), never by a snapshot taken here that could go stale.
- Staff "view as" (ops/impersonation.py) yields the impersonated user as the
  subject, the staff member as the actor, and read_only=True -- staff see
  exactly what the user sees and act as no one.
- Refusal is PrincipalRequired, a PermissionDenied: Django and DRF answer it
  with 403, never with a 500 and never by carrying on unrestricted.
"""
from dataclasses import dataclass, field
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

ORIGIN_HTTP = 'http'
ORIGIN_TASK = 'task'
ORIGIN_COMMAND = 'command'
ORIGINS = frozenset({ORIGIN_HTTP, ORIGIN_TASK, ORIGIN_COMMAND})

# Mirrors ops.impersonation.SESSION_KEY; read here rather than imported so the
# AI layer does not depend on the ops app.
IMPERSONATOR_SESSION_KEY = 'impersonator_id'


class PrincipalRequired(PermissionDenied):
    """No acceptable principal. Callers refuse; they never fall back."""


def _require_active_user(user, what):
    if user is None:
        raise PrincipalRequired(f'{what}: no user.')
    if not getattr(user, 'is_authenticated', False):
        raise PrincipalRequired(f'{what}: not an authenticated user.')
    if getattr(user, 'pk', None) is None:
        raise PrincipalRequired(f'{what}: user is not saved.')
    if not getattr(user, 'is_active', False):
        raise PrincipalRequired(f'{what}: user is deactivated.')


@dataclass(frozen=True)
class Principal:
    """
    The user an intelligence operation is performed for, and how it was asked.

    user       -- whose access applies. Always a saved, active, authenticated User.
    origin     -- 'http', 'task' or 'command': where the request entered.
    label      -- what asked, for provenance (a view or task name). Not authority.
    actor      -- the staff member acting as `user` during "view as", else None.
    read_only  -- True whenever an actor is present; nothing may be written as `user`.
    """
    user: object
    origin: str
    label: str = ''
    actor: Optional[object] = field(default=None)
    read_only: bool = False

    def __post_init__(self):
        _require_active_user(self.user, 'Principal')
        if self.origin not in ORIGINS:
            raise PrincipalRequired(f'Principal: unknown origin {self.origin!r}.')
        if self.actor is not None:
            _require_active_user(self.actor, 'Principal actor')
            if not self.actor.is_staff:
                raise PrincipalRequired('Principal: only staff may act as another user.')
            if self.actor.pk == self.user.pk:
                raise PrincipalRequired('Principal: an actor cannot impersonate themselves.')
            if not self.read_only:
                raise PrincipalRequired('Principal: impersonation is always read-only.')

    @property
    def user_id(self):
        return self.user.pk

    @property
    def is_impersonated(self):
        return self.actor is not None

    # -- construction -------------------------------------------------------

    @classmethod
    def from_request(cls, request, label=''):
        """
        The principal for an HTTP request (Django or DRF). Anonymous refuses.
        During staff "view as" the subject is the viewed user and the
        principal is read-only, matching ops/impersonation.py.
        """
        user = getattr(request, 'user', None)
        actor = None
        session = getattr(request, 'session', None)
        impersonator_id = session.get(IMPERSONATOR_SESSION_KEY) if session is not None else None
        if impersonator_id:
            actor = get_user_model().objects.filter(pk=impersonator_id).first()
            if actor is None:
                raise PrincipalRequired('Principal: the impersonating staff account no longer exists.')
        return cls(user=user, origin=ORIGIN_HTTP, label=label, actor=actor, read_only=actor is not None)

    @classmethod
    def for_user(cls, user, origin, label=''):
        """
        The principal for work done on a specific user's behalf outside a
        request: a Celery task, a management command, scheduled monitoring.
        The caller must name the user. There is deliberately no variant that
        does not.
        """
        if origin == ORIGIN_HTTP:
            raise PrincipalRequired('Principal: HTTP principals come from from_request().')
        return cls(user=user, origin=origin, label=label)

    # -- crossing a task boundary -------------------------------------------

    def to_task_payload(self):
        """A JSON-safe description to pass as a Celery argument."""
        return {
            'user_id': self.user.pk,
            'origin': self.origin,
            'label': self.label,
            'actor_id': self.actor.pk if self.actor is not None else None,
            'read_only': self.read_only,
        }

    @classmethod
    def from_task_payload(cls, payload):
        """
        Rebuild a principal inside a task. The user is re-loaded and
        re-validated: a user deleted or deactivated since the task was queued
        refuses rather than running with access they no longer have.
        """
        if not isinstance(payload, dict) or payload.get('user_id') is None:
            raise PrincipalRequired('Principal: task payload names no user.')
        User = get_user_model()
        user = User.objects.filter(pk=payload['user_id']).first()
        if user is None:
            raise PrincipalRequired('Principal: the task user no longer exists.')
        actor = None
        if payload.get('actor_id') is not None:
            actor = User.objects.filter(pk=payload['actor_id']).first()
            if actor is None:
                raise PrincipalRequired('Principal: the impersonating staff account no longer exists.')
        return cls(
            user=user,
            origin=payload.get('origin'),
            label=payload.get('label') or '',
            actor=actor,
            read_only=bool(payload.get('read_only')),
        )


def require_principal(principal):
    """
    The first line of anything that reads evidence for someone. A missing or
    wrong-typed principal refuses; it is never treated as unrestricted.
    """
    if not isinstance(principal, Principal):
        raise PrincipalRequired('This operation requires a Principal.')
    return principal
