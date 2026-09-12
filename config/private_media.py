"""
Development media serving that never hands out private files.

The production-readiness audit found that an anonymous `GET
/media/data_room/captable.csv` returned the file. The data-room view itself
checks authorization correctly, but `config/urls.py` served everything under
MEDIA_ROOT with `static()`, so the raw path went straight around it. The same
applied to seller CIMs, pitch decks and job-applicant resumes.

Private uploads are only ever meant to leave the application through a view
that checks authorization first:

    data_room/       -> matchmaking:data_room_document_serve
    cim_documents/   -> matchmaking:cim_document_serve
    decks/           -> matchmaking:pitch_deck_file
    resumes/         -> not served to the product UI at all

Public uploads -- pitch videos, elevator pitches, profile pictures, blog images
-- are still served here, because the pages embed them directly.

This only governs Django's own development serving. In production Django does
not serve media: with S3 the objects are private and reached through the views
above; with a web server serving /media/ from disk, that server must refuse the
same prefixes. The application must not depend on either -- which is why the
product UI never links a private file's storage URL.
"""
import posixpath

from django.http import Http404
from django.urls import re_path
from django.views.static import serve

PRIVATE_MEDIA_PREFIXES = ('data_room/', 'cim_documents/', 'decks/', 'resumes/')


def is_private_media_path(path):
    """
    True if a media-relative path falls under a private prefix.

    Normalised before comparing, so the check can't be dodged with a leading
    slash, `./`, `..` segments, backslashes, or different letter case. That last
    one matters because Windows and macOS filesystems are case-insensitive:
    /media/DATA_ROOM/captable.csv would otherwise reach the same file.
    """
    candidate = (path or '').replace('\\', '/')
    candidate = posixpath.normpath('/' + candidate).lstrip('/').lower()
    if candidate in ('', '.'):
        return False
    return any(candidate == p.rstrip('/') or candidate.startswith(p)
               for p in PRIVATE_MEDIA_PREFIXES)


def serve_public_media(request, path, document_root=None):
    """Serve a media file in development unless it is private."""
    if is_private_media_path(path):
        raise Http404('Not found.')
    return serve(request, path, document_root=document_root)


def media_urlpatterns(debug, media_url, media_root):
    """
    URL patterns for development media serving, or none.

    Empty when DEBUG is off (production never serves media through Django) and
    when MEDIA_URL is absolute, i.e. media lives on S3.
    """
    if not debug or not media_url or not media_url.startswith('/'):
        return []
    prefix = media_url.strip('/')
    return [
        re_path(r'^%s/(?P<path>.*)$' % prefix, serve_public_media,
                {'document_root': media_root}),
    ]
