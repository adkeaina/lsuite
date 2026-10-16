from pathlib import Path
from lsuite.parsing import sanitize, readable, references, date_value


def test_session_urls_are_sanitized_in_nested_content():
    out = sanitize({'url': 'https://learningsuite.byu.edu/.secret/cid-demo/student/pages/id-page?subsessionID=hidden&fileId=f', 'body': '<a href="https://learningsuite.byu.edu/.secret/student/top">Go</a>'})
    assert '.secret' not in str(out) and 'hidden' not in str(out)
    assert 'fileId=f' in out['url']


def test_readable_html_and_external_reference_are_preserved():
    html = '<p>Hello <b>world</b></p><a href="https://outside.test/x">Read</a><script>ignore()</script>'
    assert readable(html) == 'Hello world Read'
    assert references(html)[0] == {'name': 'Read', 'url': 'https://outside.test/x', 'external': True, 'access': 'not_fetched'}


def test_dates_do_not_invent_an_offset():
    assert date_value('2026-10-16 23:59:00') == {'source': '2026-10-16 23:59:00', 'iso': '2026-10-16T23:59:00', 'timezone': None}
    assert date_value('2026-10-16')['iso'] == '2026-10-16'
    assert date_value(None)['iso'] is None
