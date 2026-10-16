"""Validated local credential storage. Never log credential contents."""
import json
import os
import tempfile
from pathlib import Path
from typing import Callable
from .models import LSuiteError


def normalize_credentials(candidate: dict) -> dict:
    try:
        cookies = candidate['cookies']
        value = cookies['PHPSESSID']
        if set(candidate) != {'cookies'} or set(cookies) != {'PHPSESSID'}:
            raise ValueError()
        if not isinstance(value, str) or not value or len(value) > 4096 or any(ord(c) < 33 or c in ';,' for c in value):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise LSuiteError('invalid_credentials', 'Expected JSON with only cookies.PHPSESSID containing a nonempty session cookie.', 2) from None
    return {'cookies': {'PHPSESSID': value}}


class AuthStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / 'credentials.json'

    def _secure_root(self):
        if self.root.is_symlink() or self.path.is_symlink():
            raise LSuiteError('unsafe_storage', 'Credential storage cannot be a symbolic link.')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root.chmod(0o700)

    def load(self) -> dict:
        self._secure_root()
        try:
            self.path.chmod(0o600)
            return normalize_credentials(json.loads(self.path.read_text()))
        except FileNotFoundError:
            raise LSuiteError('auth_required', 'No saved session. Run lsuite auth.', 3) from None
        except (json.JSONDecodeError, UnicodeError):
            raise LSuiteError('auth_required', 'Saved session is unreadable. Run lsuite auth.', 3) from None

    def save_validated(self, candidate: dict, validate: Callable[[dict], None]) -> None:
        value = normalize_credentials(candidate)
        validate(normalize_credentials(value))
        self._secure_root()
        fd, name = tempfile.mkstemp(prefix='.candidate-', dir=self.root)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(value, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def clear(self) -> None:
        if self.path.is_symlink():
            self.path.unlink()
        else:
            self.path.unlink(missing_ok=True)
