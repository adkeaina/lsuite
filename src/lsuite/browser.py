"""Optional, dedicated browser login and bounded content reads."""
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from .models import LSuiteError
from .http import ORIGIN, checked_source


def playwright_api():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        raise LSuiteError('browser_unavailable', 'Install lsuite[browser], then run python -m playwright install chromium.') from None


class BrowserTransport:
    def __init__(self, profile: Path, credentials=None):
        self.profile = Path(profile)
        self.credentials = credentials
        self._runtime = self._browser = self._context = self._page = None

    def _start(self):
        factory = playwright_api()
        if self._page is not None:
            return
        try:
            self._runtime = factory().start()
            self._browser = self._runtime.chromium.launch(headless=True)
            if self.credentials is None:
                from .auth import AuthStore
                self.credentials = AuthStore(Path.home() / '.config/lsuite').load()
            self._context = self._browser.new_context()
            self._context.add_cookies([{'name': 'PHPSESSID', 'value': self.credentials['cookies']['PHPSESSID'], 'url': ORIGIN, 'secure': True}])
            # Only the verified data host receives resources or navigation in read mode.
            self._context.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).scheme == urlsplit(ORIGIN).scheme and urlsplit(route.request.url).netloc == urlsplit(ORIGIN).netloc else route.abort())
            self._page = self._context.new_page()
        except LSuiteError:
            self.close()
            raise
        except Exception:
            self.close()
            raise LSuiteError('browser_unavailable', 'Chromium could not start. Run python -m playwright install chromium.') from None

    def validate(self):
        self.read('/student/top')

    def read(self, source: str):
        path = checked_source(source)
        self._start()
        result = {'pages': None, 'page': None, 'html': None}
        auth_failed = []
        def response(r):
            if urlsplit(r.url).hostname != 'learningsuite.byu.edu':
                return
            if r.status == 401:
                auth_failed.append(True)
            if urlsplit(r.url).path != '/ajax.php':
                return
            func = parse_qs(r.request.post_data or '').get('funcName', [''])[0]
            if func in ('getPublishedCoursePages', 'readPage'):
                try:
                    result['pages' if func == 'getPublishedCoursePages' else 'page'] = r.json()
                except Exception:
                    pass
        self._page.on('response', response)
        try:
            self._page.goto(ORIGIN + path, wait_until='domcontentloaded', timeout=30000)
            if urlsplit(self._page.url).netloc != urlsplit(ORIGIN).netloc:
                raise LSuiteError('auth_required', 'Browser session expired. Run lsuite auth.', 3)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if auth_failed or self._page.locator('input[type=password]').count():
                    raise LSuiteError('auth_required', 'Browser session expired. Run lsuite auth.', 3)
                if '/student/pages' in path:
                    if isinstance(result['pages'], list) and (not result['pages'] or isinstance(result['page'], dict)):
                        break
                elif self._page.locator('#mainContent h1').count():
                    break
                self._page.wait_for_timeout(50)
            else:
                raise LSuiteError('browser_incomplete', 'Browser did not finish the verified representation within 30 seconds.')
            result['html'] = self._page.content()
            return result
        except LSuiteError:
            raise
        except Exception:
            raise LSuiteError('browser_read_failed', 'Dedicated browser read failed; reauthenticate if the session expired.') from None
        finally:
            self._page.remove_listener('response', response)

    def close(self):
        if self._browser is not None:
            self._browser.close()
        if self._runtime is not None:
            self._runtime.stop()
        self._runtime = self._browser = self._context = self._page = None


def browser_candidate(diagnostics, parent: Path):
    """User-completed login in a fresh candidate profile; caller validates before saving."""
    factory = playwright_api()
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent.chmod(0o700)
    candidate = Path(tempfile.mkdtemp(prefix='login-', dir=parent))
    try:
        with factory() as p:
            context = p.chromium.launch_persistent_context(str(candidate), headless=False)
            page = context.pages[0] if context.pages else context.new_page()
            print('Complete BYU sign-in and MFA in the dedicated browser window. Waiting up to 10 minutes.', file=diagnostics, flush=True)
            try:
                page.goto(ORIGIN + '/student/top', wait_until='domcontentloaded', timeout=30000)
                deadline = time.monotonic() + 600
                while time.monotonic() < deadline:
                    if urlsplit(page.url).hostname == 'learningsuite.byu.edu' and page.locator('#mainContent h1').filter(has_text='Course List').count():
                        values = [c['value'] for c in context.cookies(ORIGIN) if c['name'] == 'PHPSESSID']
                        if values:
                            return {'cookies': {'PHPSESSID': values[0]}}
                    page.wait_for_timeout(200)
                raise LSuiteError('auth_required', 'Login was not completed within ten minutes.', 3)
            finally:
                context.close()
    except LSuiteError:
        raise
    except Exception:
        raise LSuiteError('browser_login_failed', 'Dedicated login failed. Install Chromium or retry lsuite auth.', 3) from None
    finally:
        shutil.rmtree(candidate)
