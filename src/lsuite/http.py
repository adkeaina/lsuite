"""Restricted HTTPS reads of verified Learning Suite routes."""
import json
import re
import time
from urllib.parse import urlsplit, urljoin
from typing import Optional
import httpx
from .auth import normalize_credentials
from .models import LSuiteError

ORIGIN = 'https://learningsuite.byu.edu'
SOURCE = re.compile(r'/(?:student/top|cid-[A-Za-z0-9_-]+/student/(?:home(?:/(?:dashboard|assignments|announcements|info|outcomes))?|gradebook|calendar|syllabus|pages(?:/id-[A-Za-z0-9_-]+)?))\Z')


def checked_source(source: str) -> str:
    u = urlsplit(source)
    if u.scheme or u.netloc:
        if u.scheme != 'https' or u.hostname != 'learningsuite.byu.edu' or u.port not in (None, 443) or u.username or u.password:
            raise LSuiteError('forbidden_source', 'Only verified HTTPS Learning Suite sources may be read.', 2)
    if u.query or u.fragment or not SOURCE.fullmatch(u.path):
        raise LSuiteError('forbidden_source', 'Source is not a verified read-only course route.', 2)
    return u.path


def literal(document: str, pattern: str):
    """Decode a documented JSON literal; never execute website JavaScript."""
    m = re.search(pattern, document)
    if not m:
        raise LSuiteError('representation_changed', 'Expected website data is absent; retrieval is incomplete.')
    try:
        return json.JSONDecoder().raw_decode(document[m.end():].lstrip())[0]
    except (json.JSONDecodeError, ValueError):
        raise LSuiteError('representation_changed', 'Website data format changed; retrieval is incomplete.') from None


def is_login(text: str) -> bool:
    return bool(re.search(r'<input\b[^>]*type\s*=\s*[\"\']?password|<title>\s*(?:CAS|Login|Sign [Ii]n)', text, re.I))


class HTTPTransport:
    def __init__(self, credentials: dict, client: Optional[httpx.Client] = None, sleep=time.sleep):
        self.credentials = normalize_credentials(credentials)
        self._client = client or httpx.Client(timeout=30, follow_redirects=False)
        self._sleep = sleep
        self._prefix = None

    def _check_url(self, url, redirect=False):
        u = urlsplit(url)
        if u.hostname == 'cas.byu.edu' or (u.hostname == 'learningsuite.byu.edu' and re.search('login|logout|sso', u.path, re.I)):
            raise LSuiteError('auth_required', 'Session expired or missing. Run lsuite auth.', 3)
        if u.scheme != 'https' or u.hostname != 'learningsuite.byu.edu' or u.port not in (None, 443) or u.username or u.password:
            raise LSuiteError('forbidden_redirect' if redirect else 'forbidden_source', 'Refused a destination outside the verified data host.')
        path = re.sub(r'^/\.[A-Za-z0-9_-]+(?=/)', '', u.path)
        checked_source(path + ('?' + u.query if u.query else ''))

    def _request(self, url):
        seen = set()
        for _ in range(5):
            self._check_url(url, redirect=bool(seen))
            if url in seen:
                raise LSuiteError('redirect_cycle', 'Repeated redirect; authentication could not be validated.')
            seen.add(url)
            for attempt in range(3):
                try:
                    r = self._client.get(url, headers={'Cookie': 'PHPSESSID=' + self.credentials['cookies']['PHPSESSID']}, timeout=30, follow_redirects=False)
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt == 2:
                        raise LSuiteError('network_error', 'Read failed after three attempts; try again later.') from None
                    self._sleep(min(2 ** attempt, 5))
                    continue
                if r.status_code == 429 or r.status_code in (500, 502, 503, 504):
                    if attempt == 2:
                        raise LSuiteError('rate_limited' if r.status_code == 429 else 'server_error', 'Server could not complete the read; try again later.')
                    try:
                        delay = float(r.headers.get('retry-after', 2 ** attempt))
                    except ValueError:
                        delay = 2 ** attempt
                    self._sleep(max(0, min(delay, 5)))
                    continue
                break
            if r.status_code in (301, 302, 303, 307, 308):
                dest = urljoin(url, r.headers.get('location', ''))
                self._check_url(dest, redirect=True)
                url = dest
                continue
            if r.status_code == 401 or is_login(r.text):
                raise LSuiteError('auth_required', 'Session expired or missing. Run lsuite auth.', 3)
            if r.status_code == 403:
                raise LSuiteError('permission_denied', 'This account does not have permission to read the section.')
            if r.status_code == 404:
                raise LSuiteError('unavailable', 'The requested course section is unavailable.')
            if r.status_code != 200:
                raise LSuiteError('retrieval_failed', 'Learning Suite could not return the requested section.')
            if 'html' not in r.headers.get('content-type', 'text/html').lower():
                raise LSuiteError('representation_changed', 'Expected an HTML course document.')
            return r.text, url
        raise LSuiteError('redirect_limit', 'Too many redirects; read stopped.')

    def validate(self) -> None:
        document, url = self._request(ORIGIN + '/student/top')
        if re.search(r'location\.href\s*=', document):
            destination = literal(document, r'location\.href\s*=\s*')
            if not isinstance(destination, str):
                raise LSuiteError('auth_required', 'Authentication bootstrap is invalid. Run lsuite auth.', 3)
            document, url = self._request(urljoin(url, destination))
        try:
            data = literal(document, r'instance\.initialCourseGroups\s*=\s*')
            if data['status'] != 'OK' or not isinstance(data['data']['courseGroups'], list):
                raise ValueError()
        except (LSuiteError, KeyError, TypeError, ValueError):
            raise LSuiteError('auth_required', 'Authenticated course data is absent. Run lsuite auth.', 3) from None
        m = re.match(r'(/\.[A-Za-z0-9_-]+)?/student/top', urlsplit(url).path)
        self._prefix = m.group(1) or ''
        self._courses_document = document

    def read(self, source: str):
        path = checked_source(source)
        if self._prefix is None:
            self.validate()
            if path == '/student/top':
                return self._courses_document
        return self._request(ORIGIN + self._prefix + path)[0]

    def close(self) -> None:
        self._client.close()
