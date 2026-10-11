"""Exercise the deployed CSP configuration in headless Chrome, using only localhost.

Uses the browser already installed on GitHub's Ubuntu runner. A missing browser
or failed assertion is a failure, not a skipped test. No application data,
credentials, CDN fetches, third-party API calls or browser package are needed.
"""
import argparse
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from django.utils.csp import build_policy, generate_nonce
from config.browser_policy import policies


def page(nonce):
    # The expected success element is created only after browser assertions run.
    return '''<!doctype html><html><body>
<script nonce="NONCE">
window.policyEvents = [];
document.addEventListener('securitypolicyviolation', event => {
    window.policyEvents.push([event.effectiveDirective, event.disposition]);
});
window.trustedRan = true;
try { eval('window.evalRan = true'); } catch (error) { window.evalBlocked = true; }
</script>
<script>window.missingNonceRan = true;</script>
<script nonce="wrong-nonce">window.wrongNonceRan = true;</script>
<script src="http://127.0.0.1:9/untrusted.js"></script>
<button id="control" onclick="window.handlerRan = true">Existing control</button>
<script nonce="NONCE">
document.getElementById('control').click();
setTimeout(() => {
    const checks = {
        trusted: window.trustedRan === true,
        missingNonceBlocked: window.missingNonceRan !== true,
        wrongNonceBlocked: window.wrongNonceRan !== true,
        evaluationBlocked: window.evalBlocked === true && window.evalRan !== true,
        handlerCompatible: window.handlerRan === true,
        handlerReported: window.policyEvents.some(([directive, disposition]) =>
            directive === 'script-src-attr' && disposition === 'report'),
        scriptsEnforced: window.policyEvents.some(([directive, disposition]) =>
            directive === 'script-src-elem' && disposition === 'enforce'),
    };
    const result = document.createElement('output');
    result.id = Object.values(checks).every(Boolean) ? 'policy-pass' : 'policy-fail';
    result.textContent = JSON.stringify(checks);
    document.body.appendChild(result);
}, 500);
</script></body></html>'''.replace('NONCE', nonce).encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        nonce = generate_nonce()
        enforced, report_only = policies()
        body = page(nonce)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Content-Security-Policy', build_policy(enforced, nonce))
        self.send_header('Content-Security-Policy-Report-Only', build_policy(report_only, nonce))
        self.send_header('Cache-Control', 'private, no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class Result(HTMLParser):
    def __init__(self):
        super().__init__()
        self.passed = False

    def handle_starttag(self, tag, attrs):
        if tag == 'output' and dict(attrs).get('id') == 'policy-pass':
            self.passed = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', default=next((path for name in (
        'google-chrome', 'chromium', 'chromium-browser') if (path := shutil.which(name))), None))
    args = parser.parse_args()
    if not args.browser:
        parser.error('Chrome/Chromium is required; use --browser PATH')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='browser-policy-') as profile:
            result = subprocess.run([
                args.browser, '--headless', '--no-sandbox', '--disable-gpu',
                '--disable-background-networking', '--no-first-run',
                '--no-default-browser-check', f'--user-data-dir={profile}',
                '--dump-dom', '--virtual-time-budget=2000',
                f'http://127.0.0.1:{server.server_port}/',
            ], capture_output=True, text=True, timeout=30)
            parsed = Result()
            parsed.feed(result.stdout)
            if result.returncode or not parsed.passed:
                raise SystemExit('Browser CSP smoke test failed:\n'
                                 + result.stdout[-6000:] + '\n' + result.stderr[-1500:])
            print('Browser CSP smoke: PASS (nonces, inline scripts, eval, compatible handlers, report-only warnings)')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


if __name__ == '__main__':
    main()
