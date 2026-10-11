# Browser policy contract (prelaunch Batch 34)

## Enforcement

Django 6's native CSP middleware generates a new nonce for each HTML response.
Trusted script tags in the application templates use that request nonce.
Arbitrary response HTML is never scanned to add nonces. Inline script blocks
without a matching nonce and JavaScript evaluation are blocked. Script imports
are restricted to the application, jsDelivr and cdnjs.

The enforced policy keeps existing inline event attributes working through
`script-src-attr 'unsafe-inline'`. A parallel report-only policy uses
`script-src-attr 'none'` to show remaining handlers in the browser console.
It has no reporting endpoint: page URLs, source snippets and tokens are not
sent to an external reporting service. Inline styles remain allowed because
existing templates and Bootstrap use them. This is a staged policy, not a
claim that all inline execution has been eliminated.

Objects and embedded frames are disabled. Forms submit to the application.
`frame-ancestors 'none'` agrees with the existing `X-Frame-Options: DENY`.

## Integration inventory

| Resource | Required sources / behavior |
|---|---|
| Bootstrap, icons, Chart.js, Stream SDK | jsDelivr; scripts, styles and fonts as applicable |
| Font Awesome, PDF.js | cdnjs; scripts, styles, fonts, PDF worker and worker fetch; PDF evaluation explicitly disabled |
| Job page fonts | Google Fonts styles and gstatic fonts |
| Chat | HTTPS and WSS on `*.stream-io-api.com` |
| App API calls and protected deck viewer | Same origin |
| Signed storage URLs | Configured bucket's global and regional S3 endpoints for connections |
| Member images and videos | HTTPS, plus same-origin and required data/blob resources |
| Hosted Stripe Checkout and OAuth | Top-level navigation; no embedded payment frame |
| Readiness badge | Public SVG explicitly permits cross-origin embedding after existing privacy checks |

`Cross-Origin-Opener-Policy: same-origin-allow-popups` preserves OAuth and
payment popup compatibility. `Cross-Origin-Resource-Policy: same-origin` is
the default for app responses; only the successful public badge response
overrides it. This does not replace authorization or S3 bucket CORS settings.
COEP is intentionally absent: third-party media and CDN responses have not
been certified for cross-origin isolation.

The referrer policy is `strict-origin-when-cross-origin`. Permissions disable
camera, microphone, geolocation, payment, USB, serial, HID, motion sensors,
interest topics and clipboard reading. Clipboard writing and fullscreen remain
available to same-origin pages for existing copy buttons and video controls.

## Response and cache behavior

CSP and the custom policy middleware wrap SecurityMiddleware, WhiteNoise and
early refusal middleware. Static responses, HTTPS redirects, upload refusals,
API errors and streaming responses receive policies too. Policies apply in
development and production without new environment variables.

HTML responses are `private, no-store` to prevent a cached body from disagreeing
with a fresh header nonce. Static asset caching is preserved. Server-side
idempotency caching records an HTML response's generated nonce and replaces
only that token on replay with a fresh request nonce. It never adds trust to
un-nonced script tags, and never reruns the mutation. JSON replay is unchanged.

## Verification and remaining acceptance

`pages.tests_browser_policy` is automatically discovered by the blocking CI
job's whole-app `pages` entry. It covers nonce/header agreement, fresh nonces,
untrusted markup, cached replay, staging of handlers, real home/login rendering,
errors, redirects, WhiteNoise, upload refusals and integration sources. Badge
tests cover both public embedding and private-profile denial.

The blocking job also runs `tools/browser_policy_smoke.py` with the runner's
headless Chrome. A localhost fixture verifies that matching-nonce scripts run,
missing/wrong nonces and evaluation are blocked, and existing event handlers
run while generating report-only violations. A missing browser fails the step.
This smoke test does not certify the external integrations below.

Before marking Batch 34 production-accepted, check deployed responses and
exercise current Chrome, Firefox and Safari:

- Password login, signup, staff MFA, OAuth and logout.
- Checkout return and entitlement flow; do not infer payment acceptance from CSP tests.
- Chat REST connection, websocket messages and reconnect.
- PDF worker rendering, protected document downloads and signed storage media.
- Copy buttons, fullscreen video, profile/dashboard controls and public badge embedding.
- Browser console: unexpected enforced CSP failures; expected report-only handler warnings.

Do not tighten event attributes until existing handlers have been migrated and
the report-only candidate has passed that acceptance matrix. This change does
not complete the separate Zelda deck rerun or Zelda-Assessed Match work.
