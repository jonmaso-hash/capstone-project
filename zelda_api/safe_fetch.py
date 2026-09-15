"""
Fetching a web page from an address a user typed into their profile.

That address is untrusted input. Fetched naively, "https://my-startup.com" can
resolve to 127.0.0.1, a 10.x database host or the cloud metadata service at
169.254.169.254, and the server would request it on the user's behalf. So,
before anything is sent:

- only http and https, on their standard ports, with no login in the address
- the host name is resolved here, and every address it resolves to must be
  public -- loopback, private, link-local, shared and reserved ranges are refused
- the connection goes to the address that was checked, while the site's name is
  still used for the Host header and the TLS certificate, so DNS can't answer
  differently between the check and the request
- every redirect goes through the same checks, at most MAX_REDIRECTS of them
- only HTML is accepted, the body stops at MAX_BYTES, and each step has a timeout

Errors carry a short reason that is safe to show a user; resolved addresses
never appear in it.
"""
import codecs
import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import certifi
import urllib3

STANDARD_PORTS = {'http': 80, 'https': 443}
MAX_REDIRECTS = 3
MAX_BYTES = 1024 * 1024
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 10
TOTAL_SECONDS = 20
HTML_TYPES = ('text/html', 'application/xhtml+xml')
REDIRECT_STATUSES = (301, 302, 303, 307, 308)
USER_AGENT = 'InterlinkFoundry-EntityCheck/1.0 (+https://interlinkfoundry.com)'

NOT_PUBLIC = "That website address isn't a public web address."


class FetchError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class UnsafeAddress(FetchError):
    """The address points somewhere inside a private network rather than the public web."""


@dataclass
class FetchResult:
    final_url: str
    status: int
    text: str


def fetch_public_page(url):
    deadline = time.monotonic() + TOTAL_SECONDS
    current = (url or '').strip()
    for _ in range(MAX_REDIRECTS + 1):
        host = _checked_host(current)
        address = _public_address(host, STANDARD_PORTS[urlsplit(current).scheme.lower()])
        status, headers, chunks = _send(address, current, host)

        if status in REDIRECT_STATUSES:
            location = _header(headers, 'Location')
            if not location:
                raise FetchError("The website redirected without saying where to.")
            current = urljoin(current, location)
            continue
        if status >= 400:
            raise FetchError(f"The website answered with an error ({status}).")

        content_type = (_header(headers, 'Content-Type') or '').split(';')[0].strip().lower()
        if content_type not in HTML_TYPES:
            raise FetchError("That website address doesn't lead to a web page.")

        body = _read_capped(chunks, deadline)
        text = body.decode(_charset(headers), errors='replace')
        # Decoding can widen a byte cut mid-character; keep the promise about size.
        text = text.encode('utf-8')[:MAX_BYTES].decode('utf-8', errors='ignore')
        return FetchResult(final_url=current, status=status, text=text)

    raise FetchError("The website redirected too many times.")


def _checked_host(url):
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise FetchError("That isn't a website address.")
    scheme = (parts.scheme or '').lower()
    if scheme not in STANDARD_PORTS:
        raise FetchError("Only http and https website addresses can be checked.")
    if parts.username or parts.password:
        raise FetchError("Website addresses with a login in them can't be checked.")
    if port is not None and port != STANDARD_PORTS[scheme]:
        raise FetchError("Only websites on the standard web ports can be checked.")
    host = (parts.hostname or '').rstrip('.').lower()
    if not host:
        raise FetchError("That isn't a website address.")
    return host


def _public_address(host, port):
    try:
        candidates = [ipaddress.ip_address(host)]
    except ValueError:
        if host == 'localhost' or host.endswith('.localhost'):
            raise UnsafeAddress(NOT_PUBLIC)
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except (socket.gaierror, UnicodeError, OSError):
            raise FetchError("That website's address couldn't be found.")
        candidates = [ipaddress.ip_address(info[4][0].split('%')[0]) for info in infos]

    if not candidates:
        raise FetchError("That website's address couldn't be found.")
    for candidate in candidates:
        if not _is_public(candidate):
            raise UnsafeAddress(NOT_PUBLIC)
    return str(candidates[0])


def _is_public(address):
    if address.version == 6 and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_global and not address.is_multicast


def _send(address, url, host):
    """One request to an already-checked address. Returns (status, headers, body chunks)."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    path = (parts.path or '/') + (f'?{parts.query}' if parts.query else '')
    timeout = urllib3.Timeout(connect=CONNECT_TIMEOUT_SECONDS, read=READ_TIMEOUT_SECONDS)
    if scheme == 'https':
        pool = urllib3.HTTPSConnectionPool(
            address, port=STANDARD_PORTS[scheme], timeout=timeout, retries=False, maxsize=1,
            cert_reqs='CERT_REQUIRED', ca_certs=certifi.where(),
            server_hostname=host, assert_hostname=host,
        )
    else:
        pool = urllib3.HTTPConnectionPool(
            address, port=STANDARD_PORTS[scheme], timeout=timeout, retries=False, maxsize=1)
    try:
        response = pool.urlopen(
            'GET', path, redirect=False, preload_content=False, release_conn=False,
            headers={'Host': host, 'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml'},
        )
    except urllib3.exceptions.SSLError:
        pool.close()
        raise FetchError("The website's security certificate couldn't be confirmed.")
    except (urllib3.exceptions.TimeoutError, urllib3.exceptions.HTTPError, OSError):
        pool.close()
        raise FetchError("The website couldn't be reached.")
    return response.status, dict(response.headers), _stream(response, pool)


def _stream(response, pool):
    try:
        yield from response.stream(64 * 1024)
    except (urllib3.exceptions.HTTPError, OSError):
        raise FetchError("The website stopped answering part-way through.")
    finally:
        response.release_conn()
        pool.close()


def _read_capped(chunks, deadline):
    body = bytearray()
    try:
        for chunk in chunks:
            if time.monotonic() > deadline:
                raise FetchError("The website took too long to answer.")
            body.extend(chunk)
            if len(body) >= MAX_BYTES:
                break
    finally:
        close = getattr(chunks, 'close', None)
        if close:
            close()
    return bytes(body[:MAX_BYTES])


def _header(headers, name):
    for key, value in (headers or {}).items():
        if key.lower() == name.lower():
            return value
    return None


def _charset(headers):
    for part in (_header(headers, 'Content-Type') or '').split(';')[1:]:
        key, _, value = part.partition('=')
        if key.strip().lower() == 'charset':
            try:
                return codecs.lookup(value.strip().strip('"')).name
            except LookupError:
                break
    return 'utf-8'
