"""Machine-readable CLI; interactive diagnostics go only to stderr."""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional
from .adapters import LearningSuiteClient, SECTIONS
from .auth import AuthStore, authenticate
from .browser import BrowserTransport
from .export import accessible_course, collect_export, write_snapshot
from .http import HTTPTransport
from .models import SectionResult, LSuiteError, envelope
from .parsing import sanitize

PROFILE_ROOT = Path.home() / '.local/share/lsuite'


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise LSuiteError('invalid_input', 'Invalid command or arguments. Run lsuite --help for usage.', 2)


def parser():
    p = Parser(prog='lsuite', description='Read-only BYU Learning Suite JSON for agents.')
    commands = p.add_subparsers(dest='command', required=True)
    auth = commands.add_parser('auth', help='Import a validated session or sign in in a dedicated browser')
    auth.add_argument('action', nargs='?', choices=['status', 'logout'])
    commands.add_parser('courses', help='List the verified current-term course group')
    for name in SECTIONS + ('export',):
        s = commands.add_parser(name)
        s.add_argument('--course', required=True, help='Stable ID from lsuite courses')
        if name == 'export':
            s.add_argument('--output', type=Path)
            s.add_argument('--overwrite', action='store_true')
    return p


def validate_credentials(credentials):
    transport = HTTPTransport(credentials)
    try:
        transport.validate()
    finally:
        transport.close()


def main(argv: Optional[List[str]] = None, *, client=None, store=None) -> int:
    command, course, active_client, secrets = 'unknown', None, None, []
    store = store or AuthStore(Path.home() / '.config/lsuite')
    try:
        args = parser().parse_args(argv)
        command, course = args.command, getattr(args, 'course', None)
        if course is not None and not re.fullmatch(r'cid-[A-Za-z0-9_-]+', course):
            raise LSuiteError('invalid_course', 'Use a stable course ID from lsuite courses.', 2)
        if command == 'export' and args.overwrite and args.output is None:
            raise LSuiteError('invalid_input', '--overwrite requires --output.', 2)
        if command == 'export' and args.output and not args.overwrite and (args.output.exists() or args.output.is_symlink()):
            raise LSuiteError('output_exists', 'Output already exists; use --overwrite explicitly.', 2)
        if command == 'auth':
            if args.action == 'logout':
                store.clear()
                if PROFILE_ROOT.is_symlink():
                    PROFILE_ROOT.unlink()
                elif PROFILE_ROOT.exists():
                    shutil.rmtree(PROFILE_ROOT)
                result = SectionResult('ok', {'authenticated': False}, warnings=['Local tool state removed; remote BYU sessions were not revoked.'], transport='local')
            elif args.action == 'status':
                creds = store.load()
                secrets = list(creds['cookies'].values())
                validate_credentials(creds)
                result = SectionResult('ok', {'authenticated': True}, transport='http')
            else:
                authenticate(store, sys.stdin, sys.stderr, validate=validate_credentials)
                result = SectionResult('ok', {'authenticated': True}, transport='http')
        else:
            if client is None:
                creds = store.load()
                secrets = list(creds['cookies'].values())
                active_client = LearningSuiteClient(HTTPTransport(creds), BrowserTransport(PROFILE_ROOT, credentials=creds))
            else:
                active_client = client
            if command == 'courses':
                result = active_client.courses()
            elif command == 'export':
                result = collect_export(active_client, course)
            else:
                accessible_course(active_client, course)
                result = active_client.section(command, course)
        payload = sanitize(envelope(command, course, result, result.transport))
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        for secret in secrets:
            serialized = serialized.replace(secret, '[redacted]')
        payload = json.loads(serialized)
        if command == 'export' and args.output:
            write_snapshot(args.output, payload, args.overwrite)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if command == 'export' and not result.complete:
            return 4
        return 0 if result.complete and result.status == 'ok' else 1
    except LSuiteError as e:
        failure = SectionResult('error', None, complete=False, reason={'code': e.code, 'message': e.message}, transport='none')
        payload = sanitize(envelope(command, course, failure, 'none'))
        payload['error'] = {'code': e.code, 'message': e.message, 'exit_code': e.exit_code}
        output = json.dumps(payload, ensure_ascii=False, indent=2)
        for secret in secrets:
            output = output.replace(secret, '[redacted]')
        print(output)
        return e.exit_code
    except (KeyboardInterrupt, Exception) as e:
        code = 'interrupted' if isinstance(e, KeyboardInterrupt) else 'internal_error'
        failure = SectionResult('error', None, complete=False, reason={'code': code, 'message': 'Operation interrupted.' if code == 'interrupted' else 'Operation failed; no credential details are printed.'}, transport='none')
        payload = envelope(command, None, failure, 'none')
        payload['error'] = dict(failure.reason, exit_code=1)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    finally:
        if active_client is not None:
            try:
                active_client.close()
            except Exception:
                print('Transport cleanup could not finish; close any remaining dedicated browser window.', file=sys.stderr)
