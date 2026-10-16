from pathlib import Path
import pytest
from lsuite.adapters import LearningSuiteClient
from lsuite.models import LSuiteError

HTML = (Path(__file__).parent / 'fixtures/sections.html').read_text()

class HTTP:
    def __init__(self, html=HTML, failure=None):
        self.html, self.failure = html, failure
    def read(self, source):
        if self.failure:
            raise self.failure
        return self.html

class Browser:
    def __init__(self, pages=None, extra=None):
        self.pages = pages if pages is not None else [{'id': 'page-demo', 'title': 'Reading', 'parentID': None, 'published': True, 'url': 'route-demo'}]
        self.reads = []
        self.extra = extra or {}
    def read(self, source):
        self.reads.append(source)
        page_id = next((x['id'] for x in self.pages if '/id-' in source and x.get('url') == source.split('/id-')[-1]), 'page-demo')
        return dict({'pages': self.pages, 'page': {'id': page_id, 'title': 'Reading', 'content': [{'id': 'block-demo', 'data': '<p>Read thoughtfully</p>', 'displayOrder': 1, 'title': ''}], 'status': 'OK', 'expires': False}, 'html': HTML}, **self.extra)


def test_course_ids_and_publication_status_come_from_source():
    rows = LearningSuiteClient(HTTP(), None).courses().data
    assert rows[0]['source_id'] == 'cid-demo' and rows[0]['term'] == 'Fall 2026'
    assert rows[1]['publication'] == 'unpublished' and rows[1]['source_id'] is None


def test_assignment_details_and_ambiguous_due_date_are_preserved():
    r = LearningSuiteClient(HTTP(), None).section('assignments', 'cid-demo')
    row = r.data[0]
    assert r.status == 'ok' and row['source_id'] == 'assignment-demo'
    assert 'Read chapter one.' in row['body']
    assert row['due']['iso'] == '2026-10-16T23:59:00' and row['due']['timezone'] is None
    assert row['points'] == 10 and row['submission_status'] == 'Completed'
    assert row['references'][0]['external'] is True


def test_announcements_and_grades_keep_available_fields():
    c = LearningSuiteClient(HTTP(), None)
    a = c.section('announcements', 'cid-demo').data[0]
    assert a['source_id'] == 'news-demo' and a['body'] == 'Hello everyone'
    assert a['author'] == 'Example Instructor'
    g = c.section('grades', 'cid-demo').data
    assert g['items'][0]['score'] == 8 and g['items'][0]['feedback'] == 'Good work'
    assert g['overall']['availability'] == 'not_calculated'


def test_schedule_and_syllabus_keep_source_dates_and_file_references():
    c = LearningSuiteClient(HTTP(), None)
    s = c.section('schedule', 'cid-demo').data
    assert s['events'][0]['date']['iso'] == '2026-10-17'
    assert s['events'][0]['body'] == 'Discussion'
    syllabus = c.section('syllabus', 'cid-demo').data
    assert syllabus['references'][0]['url'] == 'https://learningsuite.byu.edu/plugins/Upload/fileDownload.php?fileId=file-demo'
    assert 'Read carefully.' in syllabus['body']


def test_content_includes_distinct_info_outcomes_and_nested_pages():
    b = Browser()
    r = LearningSuiteClient(HTTP(), b).section('content', 'cid-demo')
    assert r.complete and r.transport == 'http+browser'
    assert [x['kind'] for x in r.data] == ['class_information', 'learning_outcomes', 'page']
    assert r.data[1]['department'][0]['body'] == 'Explain ideas'
    assert r.data[2]['source_id'] == 'page-demo'
    assert len(b.reads) == 1


def test_empty_accessible_assignments_are_ok():
    empty = HTML.replace('datastore.assignments.reset([', 'datastore.assignments.reset_UNUSED([') + '<script>datastore.assignments.reset([]);</script>'
    r = LearningSuiteClient(HTTP(empty), None).section('assignments', 'cid-demo')
    assert r.status == 'ok' and r.data == []


def test_unsupported_representation_is_explicit_and_auth_never_falls_back():
    assert LearningSuiteClient(HTTP(), None).section('unknown', 'cid-demo').status == 'unsupported'
    b = Browser()
    with pytest.raises(LSuiteError) as exc:
        LearningSuiteClient(HTTP(failure=LSuiteError('auth_required', 'Expired', 3)), b).section('content', 'cid-demo')
    assert exc.value.exit_code == 3 and b.reads == []


@pytest.mark.parametrize('pages,extra,reason', [
    ([{'id':'a','parentID':'b','title':'A'},{'id':'b','parentID':'a','title':'B'}], {}, 'content_cycle'),
    ([{'id':'a','parentID':None,'title':'A'},{'id':'a','parentID':None,'title':'A'}], {}, 'duplicate_page'),
    (None, {'nextCursor':'repeated'}, 'pagination_unverified'),
])
def test_cycles_duplicates_and_unverified_cursors_are_incomplete(pages, extra, reason):
    b = Browser(pages, extra)
    r = LearningSuiteClient(HTTP(), b).section('content', 'cid-demo')
    assert not r.complete and r.reason['code'] == reason
    assert len(b.reads) <= 3


def test_browser_unavailable_preserves_http_content_records():
    r = LearningSuiteClient(HTTP(), None).section('content', 'cid-demo')
    assert r.status == 'unsupported' and not r.complete
    assert r.data[0]['kind'] == 'class_information'


def test_content_uses_source_route_token_separately_from_stable_id():
    b = Browser([{'id':'page-demo','url':'route-demo','parentID':None,'title':'First'}, {'id':'opaque-id','url':'short-route','parentID':None,'title':'Second'}])
    r = LearningSuiteClient(HTTP(), b).section('content', 'cid-demo')
    assert '/cid-demo/student/pages/id-short-route' in b.reads
    assert r.data[-1]['source_id'] == 'opaque-id' and r.complete
