"""
Local development data stays out of git.

db.sqlite3 (password hashes, sessions, API tokens) and user uploads under
media/ were committed to a public repository. They are untracked and ignored
now. media/img/ is the one exception: seed art the local database references,
kept until it moves to S3 at deploy.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

SEED_MEDIA_PREFIX = 'media/img/'


def _git(*args):
    return subprocess.run(['git', *args], cwd=settings.BASE_DIR, capture_output=True, text=True)


class LocalDataIsNotTrackedTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not shutil.which('git') or not (Path(settings.BASE_DIR) / '.git').exists():
            raise unittest.SkipTest('needs a git checkout')

    def test_no_sqlite_database_is_tracked(self):
        self.assertEqual(_git('ls-files', '--', '*.sqlite3').stdout.split(), [])

    def test_only_seed_images_are_tracked_under_media(self):
        tracked = _git('ls-files', '--', 'media').stdout.split('\n')
        self.assertEqual([p for p in tracked if p and not p.startswith(SEED_MEDIA_PREFIX)], [])

    def test_new_local_data_is_ignored(self):
        for path in ('db.sqlite3', 'media/data_room/new-upload.csv', 'media/elevator_pitches/clip.mp4'):
            with self.subTest(path=path):
                self.assertEqual(_git('check-ignore', '--no-index', '-q', path).returncode, 0)

    def test_seed_images_are_not_ignored(self):
        self.assertEqual(_git('check-ignore', '--no-index', '-q', 'media/img/new-seed.png').returncode, 1)
