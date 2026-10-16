import builtins
import pytest
from lsuite.browser import BrowserTransport
from lsuite.models import LSuiteError


def test_browser_dependency_is_optional_and_error_is_actionable(tmp_path, monkeypatch):
    real = builtins.__import__
    def missing(name, *args, **kwargs):
        if name.startswith('playwright'):
            raise ImportError('not installed')
        return real(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', missing)
    t = BrowserTransport(tmp_path, credentials={'cookies': {'PHPSESSID': 'demo'}})
    with pytest.raises(LSuiteError) as exc:
        t.validate()
    assert 'playwright install chromium' in exc.value.message


def test_browser_rejects_external_navigation_before_launch(tmp_path):
    with pytest.raises(LSuiteError):
        BrowserTransport(tmp_path).read('https://evil.test')


@pytest.mark.parametrize('expired', [False, True])
def test_optional_browser_reads_local_fixture_site(tmp_path, monkeypatch, expired):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import lsuite.browser as module
    pytest.importorskip('playwright.sync_api')
    class Site(BaseHTTPRequestHandler):
        def do_GET(self):
            if expired:
                self.send_response(302)
                self.send_header('Location', 'https://cas.byu.edu/cas/login')
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<main id="mainContent"><h1>Course List</h1><p>Synthetic fixture</p></main>')
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Site)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(module, 'ORIGIN', 'http://127.0.0.1:' + str(server.server_port))
    transport = BrowserTransport(tmp_path, credentials={'cookies': {'PHPSESSID': 'synthetic'}})
    try:
        if expired:
            with pytest.raises(LSuiteError) as exc:
                transport.validate()
            assert exc.value.exit_code == 3
        else:
            assert 'Synthetic fixture' in transport.read('/student/top')['html']
    finally:
        transport.close()
        server.shutdown()
        server.server_close()
