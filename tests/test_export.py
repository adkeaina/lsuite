import json
import pytest
from lsuite.export import collect_export, write_snapshot
from lsuite.models import SectionResult, LSuiteError
from lsuite.adapters import SECTIONS

class Client:
    def __init__(self, available=True):
        self.available = available
        self.reads = []
    def courses(self):
        return SectionResult('ok', [{'source_id':'cid-demo','access':'available' if self.available else 'unavailable'}])
    def section(self, name, course):
        self.reads.append(name)
        status = {'announcements':'unavailable','grades':'unsupported','schedule':'error'}.get(name, 'ok')
        return SectionResult(status, [{'title':'kept'}] if status=='ok' else [], complete=status=='ok', reason=None if status=='ok' else {'code':status})


def test_mixed_export_retains_successes_and_traversal_state():
    c = Client()
    r = collect_export(c, 'cid-demo')
    assert not r.complete and r.reason['code'] == 'partial_export'
    assert r.data['attempted_sections'] == list(SECTIONS) == c.reads
    assert r.data['sections']['assignments']['data'] == [{'title':'kept'}]
    assert r.data['sections']['grades']['status'] == 'unsupported'
    assert r.data['sections']['schedule']['complete'] is False
    assert r.data['sections']['announcements']['status'] == 'unavailable'


def test_unavailable_course_is_checked_before_any_section_reads():
    c = Client(False)
    with pytest.raises(LSuiteError):
        collect_export(c, 'cid-demo')
    assert c.reads == []


def test_existing_output_is_preserved_and_new_files_are_restricted(tmp_path):
    path = tmp_path/'snapshot.json'
    path.write_bytes(b'previous')
    with pytest.raises(LSuiteError):
        write_snapshot(path, {'new':True})
    assert path.read_bytes() == b'previous'
    write_snapshot(path, {'new':True}, overwrite=True)
    assert json.loads(path.read_text()) == {'new':True}
    assert path.stat().st_mode & 0o777 == 0o600


def test_interrupted_overwrite_preserves_previous_file_and_cleans_temp(tmp_path, monkeypatch):
    import lsuite.export as module
    path = tmp_path/'snapshot.json'
    path.write_bytes(b'previous')
    def interrupt(*args):
        raise KeyboardInterrupt()
    monkeypatch.setattr(module.os, 'replace', interrupt)
    with pytest.raises(KeyboardInterrupt):
        write_snapshot(path, {'new':True}, overwrite=True)
    assert path.read_bytes() == b'previous'
    assert list(tmp_path.iterdir()) == [path]


def test_atomic_no_overwrite_handles_a_racing_writer(tmp_path, monkeypatch):
    import lsuite.export as module
    path = tmp_path/'snapshot.json'
    real = module.os.link
    def race(source, destination):
        path.write_text('another writer')
        return real(source, destination)
    monkeypatch.setattr(module.os, 'link', race)
    with pytest.raises(LSuiteError):
        write_snapshot(path, {'new':True})
    assert path.read_text() == 'another writer'
