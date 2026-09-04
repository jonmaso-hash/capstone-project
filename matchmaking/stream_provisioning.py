"""
Server-side provisioning for the chat channel behind an accepted deal.

The channel used to be created in the browser, by
StreamChatController.createDealRoom(). That cannot work: the client SDK
acts only as the connected user, and Stream refuses GetOrCreateChannel
when a listed member has no user object yet. Only a counterparty who had
already opened chat themselves would exist, so in practice whichever
side accepted first always failed -- "User X has not initialized their
chat profile" -- and neither party had any way to resolve it. An
accepted connection produced an empty room on both sides.

initiate_direct_chat already had the correct sequence for plain DMs:
upsert both users with the API secret, then create the channel with an
explicit created_by_id. This is that same sequence for the deal channel,
so both entry points provision identically instead of one of them
guessing from the browser.

Provisioning is best-effort on purpose. The Connection's status is the
source of truth for whether two parties are connected; a Stream outage
must never make an accepted connection look unaccepted. Callers get None
and carry on.
"""
import logging

from django.conf import settings
from stream_chat import StreamChat

logger = logging.getLogger(__name__)

CHANNEL_TYPE = 'messaging'


def deal_channel_id(user_id_a, user_id_b):
    """
    The deterministic per-pair channel id, so either side computes the
    same one and "Open Chat" always resolves the channel Stream already
    has rather than standing up a second, competing one.

    sorted() on strings is lexicographic ("10" before "9"). That is not
    numeric order, but both sides only need to agree with each other.
    """
    member_ids = sorted([str(user_id_a), str(user_id_b)])
    return f"deal_{member_ids[0]}_{member_ids[1]}"


def deal_channel_cid(user_id_a, user_id_b):
    """
    Stream's fully-qualified id, "messaging:deal_3_7".

    chat.html picks the conversation to open by comparing ?cid= against
    channel.cid, which is always type-prefixed, so anything building that
    link needs this form. The Deal Workspace's "Open Chat" passed the
    bare id and so could never auto-select the conversation, even once
    the channel existed.
    """
    return f"{CHANNEL_TYPE}:{deal_channel_id(user_id_a, user_id_b)}"


def ensure_deal_channel(user_a, user_b, name=None):
    """
    Create or resolve the deal channel for this pair, returning its cid,
    or None if Stream could not be reached.

    Safe to call repeatedly: the id is deterministic, so a later call
    resolves the existing channel instead of creating another. That is
    what lets connections accepted before this existed get a working
    channel simply by opening the Deal Workspace, with no backfill.
    """
    if not getattr(settings, 'STREAM_API_KEY', None) or not getattr(settings, 'STREAM_API_SECRET', None):
        logger.warning("Stream is not configured; skipping deal channel provisioning.")
        return None

    a_id, b_id = str(user_a.id), str(user_b.id)
    if a_id == b_id:
        return None

    try:
        client = StreamChat(api_key=settings.STREAM_API_KEY, api_secret=settings.STREAM_API_SECRET)

        # Both users must exist as Stream user objects before either can
        # be named as a channel member -- this is the step the browser
        # could not perform, and the whole reason the old path 400'd.
        client.upsert_users([
            {'id': a_id, 'name': user_a.username},
            {'id': b_id, 'name': user_b.username},
        ])

        channel = client.channel(CHANNEL_TYPE, deal_channel_id(a_id, b_id))
        channel.create(
            user_id=a_id,
            data={
                'created_by_id': a_id,
                'members': sorted([a_id, b_id]),
                'name': name or f"{user_a.username} & {user_b.username}",
            },
        )
        return deal_channel_cid(a_id, b_id)
    except Exception as exc:
        logger.error("Deal channel provisioning failed for %s/%s: %s", a_id, b_id, exc)
        return None
