"""Stable Stream identities scoped to this deployment's configured environment.

Database user IDs are local to each database. A shared Stream app previously
treated production user 1 and development user 1 as the same chat participant.
"""
import re

from django.conf import settings


def stream_namespace():
    namespace = settings.STREAM_ID_NAMESPACE
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,24}', namespace):
        raise ValueError('STREAM_ID_NAMESPACE must contain 1–24 letters, digits, hyphens, or underscores.')
    return namespace


def stream_user_id(user_id):
    return f'{stream_namespace()}_user_{user_id}'


def direct_channel_id(user_id_a, user_id_b):
    a, b = sorted([int(user_id_a), int(user_id_b)])
    return f'{stream_namespace()}_chat_{a}_and_{b}'
