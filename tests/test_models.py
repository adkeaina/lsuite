from datetime import datetime, timezone
from lsuite.models import SectionResult, LSuiteError, envelope


def test_envelope_preserves_ambiguous_dates_and_incompleteness():
    r = SectionResult('ok', [{'due': '2026-10-16T10:00:00'}], ['https://example.test'], ['Timezone unknown'], False, {'code': 'detail_unavailable'})
    out = envelope('assignments', 'cid-demo', r, 'http')
    assert out['schema_version'] == '1.0'
    assert out['complete'] is False
    assert out['reason']['code'] == 'detail_unavailable'
    assert out['data'][0]['due'] == '2026-10-16T10:00:00'
    assert datetime.fromisoformat(out['retrieved_at'].replace('Z', '+00:00')).utcoffset().total_seconds() == 0
    assert out['transport'] == 'http'


def test_structured_error_contract():
    e = LSuiteError('auth_required', 'Run lsuite auth', 3)
    assert (e.code, e.message, e.exit_code) == ('auth_required', 'Run lsuite auth', 3)
