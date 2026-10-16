import json
import httpx
import pytest
from lsuite.http import HTTPTransport
from lsuite.models import LSuiteError

CREDS = {'cookies': {'PHPSESSID': 'synthetic-secret'}}
COURSES = '<script>instance.initialCourseGroups = {"status":"OK","data":{"tab":"current","courseGroups":[]},"message":""};</script>'


def make(handler, delays=None):
    return HTTPTransport(CREDS, client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=(delays.append if delays is not None else lambda n: None))


@pytest.mark.parametrize('response', [httpx.Response(200, text='<html><input type="password"></html>'), httpx.Response(302, headers={'location': 'https://cas.byu.edu/cas/login'})])
def test_login_pages_are_authentication_errors_even_with_status_200(response):
    t = make(lambda r: response)
    with pytest.raises(LSuiteError) as exc:
        t.validate()
    assert exc.value.exit_code == 3


def test_external_redirect_never_receives_credentials():
    visited = []
    def handler(r):
        visited.append((r.url.host, r.headers.get('cookie')))
        return httpx.Response(302, headers={'location': 'https://outside.test/steal'})
    with pytest.raises(LSuiteError) as exc:
        make(handler).validate()
    assert exc.value.code == 'forbidden_redirect'
    assert visited == [('learningsuite.byu.edu', 'PHPSESSID=synthetic-secret')]


@pytest.mark.parametrize('source', ['https://outside.test/data', 'http://learningsuite.byu.edu/student/top', '/logout', '/plugins/Upload/fileDownload.php?fileId=test', '/cid-demo/student/home?token=x'])
def test_unverified_sources_are_rejected_without_requests(source):
    seen = []
    t = make(lambda r: seen.append(r))
    with pytest.raises(LSuiteError):
        t.read(source)
    assert seen == []


def test_safe_json_bootstrap_is_resolved_without_executing_javascript():
    visited = []
    def handler(r):
        visited.append(r.url.path)
        return httpx.Response(200, headers={'content-type': 'text/html'}, text=COURSES if r.url.path.startswith('/.demo/') else '<script>window.name="hidden"; location.href="\\/.demo\\/student\\/top";</script>')
    t = make(handler)
    t.validate()
    assert 'initialCourseGroups' in t.read('/student/top')
    assert visited[:2] == ['/student/top', '/.demo/student/top']


@pytest.mark.parametrize('kind', ['timeout', 'rate', 'server'])
def test_transient_reads_have_bounded_retries_and_delays(kind):
    seen, delays = [], []
    def handler(r):
        seen.append(r)
        if kind == 'timeout':
            raise httpx.ReadTimeout('synthetic-secret')
        return httpx.Response(429 if kind == 'rate' else 503, headers={'Retry-After': '99999999'})
    with pytest.raises(LSuiteError) as exc:
        make(handler, delays).validate()
    assert len(seen) == 3
    assert len(delays) == 2 and max(delays) <= 5
    assert 'synthetic-secret' not in str(exc.value)
    if kind == 'rate':
        assert 'later' in exc.value.message.lower()


def test_permission_failure_is_not_retried():
    seen = []
    def handler(r):
        seen.append(r)
        return httpx.Response(403)
    with pytest.raises(LSuiteError) as exc:
        make(handler).validate()
    assert exc.value.code == 'permission_denied' and len(seen) == 1


def test_redirect_cycle_terminates():
    seen = []
    def handler(r):
        seen.append(r)
        return httpx.Response(302, headers={'location': '/student/top'})
    with pytest.raises(LSuiteError):
        make(handler).validate()
    assert len(seen) <= 5
