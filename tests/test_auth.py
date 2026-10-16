import json
import os
import pytest
from lsuite.auth import AuthStore
from lsuite.models import LSuiteError

CREDENTIALS = {'cookies': {'PHPSESSID': 'synthetic-session'}}


def test_invalid_replacement_preserves_existing_credentials(tmp_path):
    store = AuthStore(tmp_path / 'auth')
    store.save_validated(CREDENTIALS, lambda c: None)
    before = store.path.read_bytes()
    def reject(c):
        raise LSuiteError('auth_required', 'Invalid session', 3)
    with pytest.raises(LSuiteError):
        store.save_validated({'cookies': {'PHPSESSID': 'bad'}}, reject)
    assert store.path.read_bytes() == before
    assert store.load() == CREDENTIALS


def test_permissions_are_restricted_including_existing_directory(tmp_path):
    root = tmp_path / 'auth'
    root.mkdir(mode=0o755)
    store = AuthStore(root)
    store.save_validated(CREDENTIALS, lambda c: None)
    assert root.stat().st_mode & 0o777 == 0o700
    assert store.path.stat().st_mode & 0o777 == 0o600
    store.path.chmod(0o644)
    assert store.load() == CREDENTIALS
    assert store.path.stat().st_mode & 0o777 == 0o600
    store.clear()
    with pytest.raises(LSuiteError) as exc:
        store.load()
    assert exc.value.exit_code == 3


@pytest.mark.parametrize('candidate', [{}, {'cookies': {}}, {'cookies': {'PHPSESSID': ''}}, {'cookies': {'PHPSESSID': 'a\nb'}}, {'cookies': {'PHPSESSID': 'x', 'foreign': 'secret'}}])
def test_rejects_invalid_credential_schema(tmp_path, candidate):
    with pytest.raises(LSuiteError):
        AuthStore(tmp_path).save_validated(candidate, lambda c: None)
    assert not (tmp_path / 'credentials.json').exists()


def test_credential_file_input_validates_before_saving(tmp_path):
    from io import StringIO
    from lsuite.auth import authenticate
    source = tmp_path / 'import.json'
    source.write_text(json.dumps(CREDENTIALS))
    store = AuthStore(tmp_path / 'config')
    checked = []
    diagnostics = StringIO()
    authenticate(store, StringIO(str(source) + '\n'), diagnostics, validate=lambda c: checked.append(c))
    assert checked == [CREDENTIALS]
    assert store.load() == CREDENTIALS
    assert 'synthetic-session' not in diagnostics.getvalue()
