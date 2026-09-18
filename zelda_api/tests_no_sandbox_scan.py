"""
The unrouted sandbox upload views are gone.

Two copies of `SandboxScanView` sat in the tree -- one in zelda_api/views.py,
one in zelda_api/test_views.py (a production view despite the name, which the
test runner also collected as a test module). Both took a file upload with
`AllowAny`: no authentication, no size cap, no quota, and both returned the
raw exception text to the caller. Nothing routed either, so they cost nothing
today and would have been a hole the moment somebody added a path to one.

Deleted rather than secured: analysis already has a routed, authenticated,
size-capped path in DocumentIngestView and PitchDeckAnalysisAPIView.
"""
import importlib

from django.test import TestCase
from django.urls import get_resolver


class SandboxScanViewRemovedTests(TestCase):

    def test_neither_sandbox_view_exists(self):
        import zelda_api.views
        self.assertFalse(hasattr(zelda_api.views, 'SandboxScanView'))
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module('zelda_api.test_views')

    def test_nothing_in_the_url_tree_points_at_one(self):
        def callbacks(resolver):
            for pattern in resolver.url_patterns:
                if hasattr(pattern, 'url_patterns'):
                    yield from callbacks(pattern)
                else:
                    yield pattern.callback
        names = {
            getattr(getattr(cb, 'view_class', cb), '__name__', '')
            for cb in callbacks(get_resolver())
        }
        # Positive control: the real, authenticated analysis paths are routed.
        self.assertIn('PitchDeckAnalysisAPIView', names)
        self.assertNotIn('SandboxScanView', names)
