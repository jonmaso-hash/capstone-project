"""
The brand mark is actually served, and every page that claims it has one does.

A `{% static %}` tag pointing at a file that does not exist renders a perfectly
valid URL and fails silently: the page loads, the browser requests it, gets a
404, and shows nothing. Nobody sees an error -- which is the same
silent-absence shape as a verification that never ran and a toggle that
reported success without writing.

So these tests assert two different things, because one does not imply the
other:

    THE FILE EXISTS on disk, at the path the template asks for. A template
    can reference anything; only the filesystem settles whether it arrives.

    THE MARKUP IS PRESENT on the rendered page. A file nobody references is
    as invisible as a reference to a file that is not there.

Formats are not interchangeable here, and the tests say why:

    SVG for the navbar, favicon and report headers -- scales to any size,
    no background, tiny.

    PNG for email and social preview. Gmail and Outlook strip SVG entirely
    and OG scrapers will not render it, so those two surfaces would show
    nothing at all. This is the one place a raster is the correct answer.

And the email keeps a TEXT wordmark beside the image: most clients block
remote images by default, so an image-only header renders as an empty bar
for a large share of recipients.
"""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

User = get_user_model()

BRAND = Path(settings.BASE_DIR) / 'static' / 'img' / 'brand'

# Every asset, the surface that needs it, and why that format.
ASSETS = {
    'interlink-mark.svg': 'navbar, favicon and report headers -- vector, any size',
    'interlink-logo.svg': 'auth pages -- full lockup, vector',
    'interlink-og.png': 'social preview -- scrapers do not render SVG',
    'interlink-mark-96.png': 'email header -- Gmail and Outlook strip SVG',
    'interlink-apple-touch.png': 'iOS home screen -- must be raster',
    'interlink-mark-32.png': 'favicon fallback for browsers ignoring SVG icons',
}


class TheAssetsExistOnDiskTests(SimpleTestCase):
    """
    The half a rendered-markup test cannot reach. A page can reference a file
    that was never committed and look entirely healthy while serving a 404.
    """

    def test_every_brand_asset_is_present(self):
        missing = sorted(name for name in ASSETS if not (BRAND / name).is_file())
        self.assertEqual(missing, [], f'referenced brand assets are not on disk: {missing}')

    def test_no_asset_is_empty(self):
        for name in ASSETS:
            with self.subTest(asset=name):
                self.assertGreater((BRAND / name).stat().st_size, 500,
                                   f'{name} is too small to be a real asset')

    def test_the_vector_assets_are_really_vector(self):
        """
        A PNG renamed .svg would pass an existence check and then fail to
        scale, which is the entire reason those surfaces use SVG.
        """
        for name in ('interlink-mark.svg', 'interlink-logo.svg'):
            with self.subTest(asset=name):
                head = (BRAND / name).read_text(encoding='utf-8')[:400]
                self.assertIn('<svg', head)
                self.assertIn('viewBox', head, 'an SVG without a viewBox will not scale')

    def test_the_lockup_carries_the_wordmark_as_geometry(self):
        """
        The wordmark must be drawn, not typeset. An SVG <text> element renders
        in whatever font the viewer happens to have, so the lockup would look
        different on different machines and in email.
        """
        svg = (BRAND / 'interlink-logo.svg').read_text(encoding='utf-8')
        self.assertNotIn('<text', svg, 'the wordmark depends on a font')
        self.assertGreater(svg.count('<path'), 10, 'the wordmark is not drawn as paths')

    def test_the_social_card_is_the_size_scrapers_expect(self):
        from PIL import Image
        with Image.open(BRAND / 'interlink-og.png') as im:
            self.assertEqual(im.size, (1200, 630))


class TheMarkReachesEveryPageTests(TestCase):

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def home(self):
        response = self.client.get(reverse('pages:home'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def navbar_brand(self):
        """
        Just the brand link. A page-wide search for the mark matches the
        FAVICON link too, so it cannot tell "the navbar shows the mark" from
        "the mark appears somewhere in the document" -- a mutation emptying
        the navbar image survived exactly that way.
        """
        html = self.home()
        self.assertIn('navbar-brand', html, 'no brand link on the page at all')
        return html.split('navbar-brand', 1)[1].split('</a>', 1)[0]

    def test_the_navbar_carries_the_mark(self):
        self.assertIn('interlink-mark.svg', self.navbar_brand())

    def test_the_brand_link_still_names_the_company_in_text(self):
        """
        An image-only brand link is unreadable to a screen reader and to
        anyone whose images fail. The name stays in text beside the mark.
        """
        html = self.home()
        self.assertIn('Interlink Foundry', html)

    def test_the_favicon_is_declared(self):
        """
        All three, asserted separately. `rel="icon"` alone is satisfied by
        either link, so removing just the SVG icon passed -- each format
        exists for a different client and none is redundant.
        """
        html = self.home()
        self.assertIn('rel="icon" type="image/svg+xml"', html, 'no scalable favicon')
        self.assertIn('rel="icon" type="image/png" sizes="32x32"', html,
                      'no raster favicon fallback')
        self.assertIn('apple-touch-icon', html, 'no iOS home-screen icon')

    def test_the_social_preview_is_declared_absolutely(self):
        """
        og:image must be an absolute URL -- a scraper has no page context to
        resolve a relative one against, so a relative path yields no preview.
        """
        html = self.home()
        self.assertIn('og:image', html)
        self.assertIn('interlink-og.png', html)
        marker = 'property="og:image" content="'
        url = html.split(marker, 1)[1].split('"', 1)[0]
        self.assertTrue(url.startswith('http'), f'og:image is not absolute: {url}')


class TheReportsCarryTheMarkTests(TestCase):
    """
    The eyebrow is included by all four intelligence reports, so one assertion
    on it covers Truth Delta, the IC memo, the valuation report and the memo
    detail page.
    """

    def test_the_intelligence_eyebrow_carries_the_mark(self):
        from django.template.loader import render_to_string
        html = render_to_string('includes/intelligence_eyebrow.html')
        self.assertIn('interlink-mark.svg', html)

    def test_the_eyebrow_still_names_the_family_in_text(self):
        from django.template.loader import render_to_string
        html = render_to_string('includes/intelligence_eyebrow.html')
        self.assertIn('Interlink', html)
        self.assertIn('Zelda', html)


class TheEmailDegradesGracefullyTests(SimpleTestCase):
    """
    Email is the one surface where the image is the least reliable part. Most
    clients block remote images by default and several strip SVG outright, so
    the header must read correctly with no images loaded at all.
    """

    def source(self):
        return (Path(settings.BASE_DIR) / 'templates' / 'emails'
                / 'founder_match.html').read_text(encoding='utf-8')

    def test_the_email_uses_a_raster_mark(self):
        html = self.source()
        self.assertIn('interlink-mark-96.png', html)
        self.assertNotIn('interlink-mark.svg', html,
                         'SVG is stripped by Gmail and Outlook')

    def test_the_email_keeps_a_text_wordmark(self):
        self.assertIn('INTERLINK FOUNDRY', self.source(),
                      'with images blocked the header would be empty')

    def test_the_email_image_url_is_absolute_when_rendered(self):
        """
        Source alone cannot settle this: the template writes
        {{ site_url }}{% static ... %}, which renders a RELATIVE url if
        site_url is missing from the context. A mail client has no page to
        resolve that against, so the image is simply broken -- and nothing
        errors, so nothing reveals it.
        """
        from django.template.loader import render_to_string
        from matchmaking.emails import site_url
        html = render_to_string('emails/founder_match.html', {
            'founder': None, 'investor': None, 'visible_fields': [],
            'site_url': site_url(),
        })
        src = html.split('interlink-mark-96.png', 1)[0].rsplit('src="', 1)[1]
        self.assertTrue(src.startswith('http'),
                        f'email image url is relative and will not load: {src!r}')

    def test_the_email_context_actually_supplies_the_origin(self):
        """
        The other half. The template can be perfect and still render a broken
        url if the sender never puts site_url in the context -- which is
        exactly what the admin action did before this change.
        """
        from matchmaking.emails import founder_match_context
        context = founder_match_context(founder=None, investor=None, visible_fields=[])
        self.assertTrue(str(context.get('site_url', '')).startswith('http'),
                        'the email is rendered without an absolute origin')

    def test_the_email_image_has_alt_text(self):
        html = self.source()
        block = html.split('interlink-mark-96.png', 1)[1][:200]
        self.assertIn('alt=', block, 'a blocked image with no alt text is a blank gap')
