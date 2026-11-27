"""
Uploaded images are parsed by Pillow 13.0.0 or later.

Any signed-in user can upload a profile picture, and the blog accepts an
article image. Both go through Django's ImageField, which runs Pillow's
Image.open() and verify() before the form looks at the format. Pillow picks
the parser from the file's bytes, not its name, so a TIFF, XBM or SPIDER file
named me.png is parsed by that plugin first; ProfilePictureForm only refuses
it afterwards, and the blog form keeps it. Pillow 12.3.0 has 43 published
advisories (13.0.0 fixes every one), including parser denial-of-service
issues in exactly those open/verify paths.

The pin is what the production image installs; the runtime check catches an
environment that drifted from it. The remaining tests show that upload
validation still accepts real pictures and refuses everything else under the
upgraded Pillow.
"""
import io
import re
from pathlib import Path

import PIL
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from packaging.version import Version
from PIL import Image

from blog.forms import ArticleUploadForm
from usersettings.forms import ProfilePictureForm

PATCHED = Version('13.0.0')
ROOT = Path(__file__).resolve().parents[1]


def _image(fmt, mode='RGB', name=None):
    buffer = io.BytesIO()
    Image.new(mode, (8, 8), 1 if mode in ('1', 'P') else (40, 90, 160)).save(buffer, format=fmt)
    return SimpleUploadedFile(name or f'picture.{fmt.lower()}', buffer.getvalue(),
                              content_type='application/octet-stream')


class PillowFloorTests(SimpleTestCase):

    def test_requirements_pin_pillow_at_or_above_the_patched_release(self):
        text = (ROOT / 'requirements.txt').read_text(encoding='utf-8')
        pins = re.findall(r'(?im)^pillow==([0-9][^\s;#]*)\s*$', text)
        self.assertEqual(len(pins), 1, pins)
        self.assertGreaterEqual(Version(pins[0]), PATCHED)

    def test_runtime_pillow_is_at_or_above_the_patched_release(self):
        self.assertGreaterEqual(Version(PIL.__version__), PATCHED)


class ProfilePictureValidationUnderPillowTests(SimpleTestCase):

    def _form(self, upload):
        return ProfilePictureForm(files={'profile_picture': upload})

    def test_real_jpeg_png_and_webp_pictures_are_accepted(self):
        for fmt, name in (('JPEG', 'me.jpg'), ('PNG', 'me.png'), ('WEBP', 'me.webp')):
            with self.subTest(fmt=fmt):
                form = self._form(_image(fmt, name=name))
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data['profile_picture'].image.format, fmt)

    def test_other_formats_renamed_to_png_are_refused(self):
        for fmt, mode in (('GIF', 'P'), ('TIFF', 'RGB'), ('XBM', '1'), ('BMP', 'RGB')):
            with self.subTest(fmt=fmt):
                self.assertFalse(self._form(_image(fmt, mode, name='me.png')).is_valid())

    def test_text_and_truncated_files_named_png_are_refused(self):
        whole = _image('PNG').read()
        for label, data in (('script', b'<script>alert(1)</script>'), ('truncated', whole[:len(whole) // 2])):
            with self.subTest(label):
                upload = SimpleUploadedFile('me.png', data, content_type='image/png')
                self.assertFalse(self._form(upload).is_valid())


class BlogImageValidationUnderPillowTests(TestCase):
    """A ModelForm: its clean step may consult the database, so this one gets a test database."""

    def _image_errors(self, upload):
        form = ArticleUploadForm(data={'company_name': 'Co', 'title': 'T', 'body': 'B'}, files={'image': upload})
        form.is_valid()
        return form.errors.get('image')

    def test_a_real_png_passes_image_validation(self):
        self.assertIsNone(self._image_errors(_image('PNG')))

    def test_a_non_image_named_png_is_refused(self):
        upload = SimpleUploadedFile('post.png', b'not an image', content_type='image/png')
        self.assertTrue(self._image_errors(upload))
