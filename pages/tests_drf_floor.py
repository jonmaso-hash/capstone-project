"""
Django REST framework is at least 3.18.2.

DRF negotiates the response format from the Accept header before it
authenticates, checks permissions or throttles (APIView.initial), so every
API URL, the public /api/v1/zelda/health/ included, parses an anonymous
client's Accept header. 3.17.1 can spend many seconds of CPU on one header
with many large quoted parameters (GHSA-33wh-fxxf-88vv) and decodes JSON
bodies with a codec the client names (GHSA-3547-9m27-7rxg); 3.18.2 fixes
both, and three more (GHSA-xw6w-gcfp-cf8m, GHSA-2m8g-3cmr-wg3w,
GHSA-g47c-3xmw-q6m2).

The pin is what the production image installs; the runtime check catches an
environment that drifted from it. The remaining tests show that content
negotiation and authentication still behave the same after the upgrade.
"""
import re
from pathlib import Path

import rest_framework
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from packaging.version import Version

PATCHED = Version('3.18.2')
ROOT = Path(__file__).resolve().parents[1]


class DrfFloorTests(SimpleTestCase):

    def test_requirements_pin_drf_at_or_above_the_patched_release(self):
        text = (ROOT / 'requirements.txt').read_text(encoding='utf-8')
        pins = re.findall(r'(?im)^djangorestframework==([0-9][^\s;#]*)\s*$', text)
        self.assertEqual(len(pins), 1, pins)
        self.assertGreaterEqual(Version(pins[0]), PATCHED)

    def test_runtime_drf_is_at_or_above_the_patched_release(self):
        self.assertGreaterEqual(Version(rest_framework.__version__), PATCHED)


class ApiNegotiationStillWorksTests(TestCase):

    def test_public_health_answers_json_for_ordinary_accept_headers(self):
        for accept in ('application/json', 'application/json; charset=utf-8', '*/*',
                       'text/html;q=0.5, application/json;q=1.0'):
            with self.subTest(accept=accept):
                response = self.client.get(reverse('zelda_api:health_check'), HTTP_ACCEPT=accept)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Content-Type'].split(';')[0], 'application/json')
                self.assertEqual(response.json()['status'], 'ok')

    def test_an_unrenderable_accept_header_is_still_refused(self):
        response = self.client.get(reverse('zelda_api:health_check'), HTTP_ACCEPT='application/xml')
        self.assertEqual(response.status_code, 406)

    def test_protected_api_still_refuses_an_anonymous_client(self):
        response = self.client.get(reverse('zelda_api:library'), HTTP_ACCEPT='application/json')
        self.assertIn(response.status_code, (401, 403))
