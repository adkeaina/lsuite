"""Partial aggregation and atomic, restricted JSON snapshots."""
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from .adapters import SECTIONS
from .models import SectionResult, LSuiteError


def accessible_course(client, course):
    result = client.courses()
    if result.status != 'ok':
        raise LSuiteError('course_unavailable', 'Course discovery failed; course access could not be validated.')
    match = next((x for x in result.data if x.get('source_id') == course), None)
    if match is None or match.get('access') != 'available':
        raise LSuiteError('course_unavailable', 'Course is unavailable in the verified current-term list. Run lsuite courses.')
    return match


def collect_export(client, course: str) -> SectionResult:
    record = accessible_course(client, course)
    sections, attempted, sources, transports = {}, [], [], set()
    for name in SECTIONS:
        attempted.append(name)
        try:
            result = client.section(name, course)
        except LSuiteError as e:
            result = SectionResult('error', None, complete=False, reason={'code': e.code, 'message': e.message})
        except Exception:
            result = SectionResult('error', None, complete=False, reason={'code': 'internal_error', 'message': 'Section retrieval failed; other section results were retained.'})
        sections[name] = asdict(result)
        sources.extend(result.sources)
        transports.add(result.transport)
    complete = all(x['status'] == 'ok' and x['complete'] for x in sections.values())
    return SectionResult('ok' if complete else 'error', {'course': record, 'attempted_sections': attempted, 'sections': sections},
                         list(dict.fromkeys(sources)), [] if complete else ['Some sections failed or could not be completely traversed; successful results are retained.'], complete,
                         None if complete else {'code': 'partial_export', 'message': 'Inspect per-section statuses and completeness.'}, '+'.join(sorted(transports)))


def write_snapshot(path: Path, payload: dict, overwrite: bool = False) -> None:
    path = Path(path).expanduser()
    if not overwrite and (path.exists() or path.is_symlink()):
        raise LSuiteError('output_exists', 'Output already exists; use --overwrite explicitly.', 2)
    name = None
    try:
        fd, name = tempfile.mkstemp(prefix='.lsuite-', suffix='.json', dir=path.parent)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        if overwrite:
            os.replace(name, path)
        else:
            os.link(name, path)
    except FileExistsError:
        raise LSuiteError('output_exists', 'Output already exists; use --overwrite explicitly.', 2) from None
    except OSError:
        raise LSuiteError('output_failed', 'Snapshot could not be written atomically; previous output was preserved.') from None
    finally:
        if name is not None:
            try:
                os.unlink(name)
            except FileNotFoundError:
                pass
