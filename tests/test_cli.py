import json
from io import StringIO
import pytest
from lsuite.cli import main
from lsuite.models import SectionResult, LSuiteError
from lsuite.auth import AuthStore
from lsuite.adapters import SECTIONS

class Client:
    def __init__(self, partial=False):
        self.partial = partial
    def courses(self):
        return SectionResult('ok', [{'source_id':'cid-demo','access':'available'}])
    def section(self, name, course):
        if self.partial and name == 'grades':
            return SectionResult('error', [], complete=False, reason={'code':'permission_denied'})
        return SectionResult('ok', [{'title':'Demo'}], ['https://learningsuite.byu.edu/.demo/cid-demo/student/home?subsessionID=hidden'])
    def close(self):
        pass


@pytest.mark.parametrize('command', ['courses'] + list(SECTIONS) + ['export'])
def test_successful_commands_emit_exactly_one_json_document(command, capsys):
    argv = [command] + ([] if command == 'courses' else ['--course','cid-demo'])
    assert main(argv, client=Client()) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload['command'] == command and payload['schema_version'] == '1.0'
    assert '.demo' not in captured.out and 'hidden' not in captured.out


@pytest.mark.parametrize('argv', [[], ['assignments'], ['wrong'], ['grades','--course','https://evil.test'], ['export','--course','cid-demo','--overwrite']])
def test_invalid_input_emits_json_and_returns_2(argv, capsys):
    assert main(argv, client=Client()) == 2
    output = capsys.readouterr()
    assert json.loads(output.out)['error']['exit_code'] == 2


def test_missing_authentication_returns_3_as_json(tmp_path, capsys):
    assert main(['courses'], store=AuthStore(tmp_path)) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload['error']['code'] == 'auth_required'


def test_mixed_export_emits_successful_sections_and_returns_4(capsys):
    assert main(['export','--course','cid-demo'], client=Client(True)) == 4
    data = json.loads(capsys.readouterr().out)
    assert data['data']['sections']['assignments']['data'] == [{'title':'Demo'}]
    assert data['complete'] is False


def test_output_file_matches_stdout_without_overwriting(tmp_path, capsys):
    path = tmp_path/'snapshot.json'
    argv = ['export','--course','cid-demo','--output',str(path)]
    assert main(argv, client=Client()) == 0
    first = capsys.readouterr().out
    assert json.loads(path.read_text()) == json.loads(first)
    assert main(argv, client=Client()) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'error'
    assert path.read_text() == first


def test_auth_import_prompts_stay_on_stderr(tmp_path, capsys, monkeypatch):
    import lsuite.cli as module
    credential = tmp_path/'import.json'
    credential.write_text('{"cookies":{"PHPSESSID":"synthetic-secret"}}')
    monkeypatch.setattr(module, 'validate_credentials', lambda c: None)
    monkeypatch.setattr(module.sys, 'stdin', StringIO(str(credential)+'\n'))
    assert main(['auth'], store=AuthStore(tmp_path/'config')) == 0
    out = capsys.readouterr()
    assert json.loads(out.out)['data']['authenticated'] is True
    assert 'credential-file' in out.err and 'synthetic-secret' not in out.out + out.err


def test_auth_status_and_logout(tmp_path, capsys, monkeypatch):
    import lsuite.cli as module
    store=AuthStore(tmp_path/'config')
    store.save_validated({'cookies':{'PHPSESSID':'synthetic-secret'}},lambda c: None)
    monkeypatch.setattr(module,'validate_credentials',lambda c: None)
    profile=tmp_path/'profile';profile.mkdir();(profile/'state').write_text('private')
    monkeypatch.setattr(module,'PROFILE_ROOT',profile)
    assert main(['auth','status'],store=store)==0
    assert json.loads(capsys.readouterr().out)['data']['authenticated'] is True
    assert main(['auth','logout'],store=store)==0
    assert 'remote' in json.loads(capsys.readouterr().out)['warnings'][0]
    assert not profile.exists() and not store.path.exists()


def test_cleanup_failure_does_not_corrupt_json_or_leak_exception(capsys):
    class ClosingClient(Client):
        def close(self):
            raise RuntimeError('synthetic-private-error')
    assert main(['courses'], client=ClosingClient()) == 0
    out=capsys.readouterr()
    assert json.loads(out.out)['status']=='ok'
    assert 'synthetic-private-error' not in out.out+out.err
    assert 'cleanup' in out.err.lower()
