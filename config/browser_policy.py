"""Browser resource policy for the application's actual integrations."""
from django.utils.csp import CSP


def policies(bucket='', region='us-east-1'):
    # Signed S3 URLs may use either global or regional virtual-host addressing.
    storage = [f'https://{bucket}.s3.amazonaws.com',
               f'https://{bucket}.s3.{region}.amazonaws.com'] if bucket else []
    enforced = {
        'default-src': [CSP.SELF],
        'base-uri': [CSP.SELF],
        'object-src': [CSP.NONE],
        'frame-ancestors': [CSP.NONE],
        'form-action': [CSP.SELF],
        # Only trusted template blocks get a nonce; never bless arbitrary
        # response HTML. CDN imports cover Bootstrap, Chart.js, Stream and PDF.js.
        'script-src': [CSP.SELF, CSP.NONCE, 'https://cdn.jsdelivr.net', 'https://cdnjs.cloudflare.com'],
        # Existing markup still has event attributes, including generated
        # widget controls. Track their removal with the report-only policy.
        'script-src-attr': [CSP.UNSAFE_INLINE],
        'style-src': [CSP.SELF, CSP.UNSAFE_INLINE, 'https://cdn.jsdelivr.net',
                      'https://cdnjs.cloudflare.com', 'https://fonts.googleapis.com'],
        'font-src': [CSP.SELF, 'data:', 'https://cdn.jsdelivr.net',
                     'https://cdnjs.cloudflare.com', 'https://fonts.gstatic.com'],
        # Member images and videos can be hosted externally. These permissions
        # never allow remote JavaScript, frames, objects or arbitrary API calls.
        'img-src': [CSP.SELF, 'https:', 'data:', 'blob:'],
        'media-src': [CSP.SELF, 'https:', 'blob:'],
        'connect-src': [CSP.SELF, 'https://*.stream-io-api.com',
                        'wss://*.stream-io-api.com', 'https://cdnjs.cloudflare.com', *storage],
        'worker-src': [CSP.SELF, 'blob:', 'https://cdnjs.cloudflare.com'],
        'frame-src': [CSP.NONE],
        'manifest-src': [CSP.SELF],
    }
    # Browser console diagnostics only: no user URLs, snippets or tokens are
    # uploaded to a reporting service. This candidate does not block handlers.
    report_only = {**enforced, 'script-src-attr': [CSP.NONE]}
    return enforced, report_only


PERMISSIONS_POLICY = ', '.join([
    'camera=()', 'microphone=()', 'geolocation=()', 'payment=()',
    'usb=()', 'serial=()', 'hid=()', 'accelerometer=()', 'gyroscope=()',
    'magnetometer=()', 'browsing-topics=()', 'clipboard-read=()',
    'clipboard-write=(self)', 'fullscreen=(self)',
])
