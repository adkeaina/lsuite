"""Evidence-backed section adapters; unknown shapes fail explicitly."""
import re
from bs4 import BeautifulSoup
from .http import literal, ORIGIN, checked_source
from .models import SectionResult, LSuiteError
from .parsing import sanitize, readable, references, date_value

SECTIONS = ('assignments', 'announcements', 'grades', 'schedule', 'syllabus', 'content')
PATHS = {'assignments': 'home/assignments', 'announcements': 'home/announcements', 'grades': 'gradebook', 'schedule': 'calendar', 'syllabus': 'syllabus'}
DATE_WARNING = 'Source dates are preserved without invented offsets; numeric timestamp units and institutional timezone conversions are not assumed.'


def array(document, pattern):
    value = literal(document, pattern)
    if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
        raise LSuiteError('representation_changed', 'Expected a list of website records; retrieval is incomplete.')
    return value


def unique(rows, key):
    seen, out = set(), []
    for row in rows:
        identifier = row.get(key)
        if identifier is not None and identifier in seen:
            continue
        seen.add(identifier)
        out.append(row)
    return out


def assignment_rows(document):
    rows = array(document, r'datastore\.assignments\.reset\(\s*')
    out = []
    for a in unique(rows, 'id'):
        if not a.get('id') or not isinstance(a.get('name'), str):
            raise LSuiteError('representation_changed', 'Assignment identifiers or titles are missing.')
        out.append({'source_id': a['id'], 'title': a['name'], 'body': readable(a.get('description')), 'category_id': a.get('categoryID'), 'points': a.get('points'),
                    'opens': date_value(a.get('beginDate')), 'due': date_value(a.get('dueDate')), 'due_label': a.get('fullDueTime'),
                    'submission_status': a.get('studentAction'), 'attachment_reference': a.get('attachment'),
                    'references': references(a.get('description')), 'field_availability': {'description': 'available' if a.get('description') is not None else 'not_exposed', 'attachments': 'reference_only' if a.get('attachment') else 'none_exposed'}})
    return out


def unsupported(reason):
    return SectionResult('unsupported', [], complete=False, reason={'code': 'unsupported', 'message': reason})


class LearningSuiteClient:
    def __init__(self, http, browser):
        self.http, self.browser = http, browser

    def _read(self, path):
        if self.http is None:
            raise LSuiteError('transport_unavailable', 'Verified HTTP transport is required.')
        return self.http.read(path)

    def courses(self):
        data = literal(self._read('/student/top'), r'instance\.initialCourseGroups\s*=\s*')
        try:
            groups = data['data']['courseGroups']
            if data['status'] != 'OK' or not isinstance(groups, list):
                raise ValueError()
            out = []
            for group in groups:
                for row in group['courseList']:
                    href = row.get('href') or ''
                    m = re.search(r'(?:^|/)cid-([A-Za-z0-9_-]+)(?:/|$)', href)
                    cid = 'cid-' + m.group(1) if m else None
                    published = row.get('published')
                    out.append({'source_id': cid, 'name': row['courseTitle'], 'term': group.get('periodName'), 'section': (re.search(r'\((\d{1,4})\)', row['courseTitle']).group(1) if re.search(r'\((\d{1,4})\)', row['courseTitle']) else None),
                                'publication': 'published' if published is True else 'unpublished' if published is False else 'unknown',
                                'access': 'available' if published and cid and not row.get('externalURL') else 'external' if row.get('externalURL') else 'unavailable',
                                'url': ORIGIN + '/' + cid + '/student/home' if cid else None})
            return SectionResult('ok', sanitize(out), [ORIGIN + '/student/top'], ['Only the verified current-term course grouping is included.'])
        except (KeyError, TypeError, ValueError):
            raise LSuiteError('representation_changed', 'Course grouping changed; no empty list was inferred.') from None

    def section(self, name, course):
        if name not in SECTIONS:
            return unsupported('This section has no verified retrieval path.')
        if not re.fullmatch(r'cid-[A-Za-z0-9_-]+', course):
            raise LSuiteError('invalid_course', 'Use a stable course ID from lsuite courses.', 2)
        base = '/' + course + '/student/'
        if name == 'content':
            return self._content(base)
        path = base + PATHS[name]
        try:
            document = self._read(path)
            warnings = []
            if name == 'assignments':
                data = assignment_rows(document)
                warnings.append(DATE_WARNING)
            elif name == 'grades':
                items = assignment_rows(document)
                scores = array(document, r'datastore\.scores\.reset\(\s*')
                by_id = {s.get('assignmentID'): s for s in scores if not s.get('deleted')}
                for item in items:
                    s = by_id.get(item['source_id'], {})
                    item.update(score=s.get('score'), feedback=readable(s.get('note')) if s.get('note') is not None else None, excused=s.get('excuse'))
                data = {'items': items, 'categories': array(document, r'datastore\.categories\.reset\(\s*'), 'overall': {'availability': 'not_calculated', 'value': None}}
                warnings.extend([DATE_WARNING, 'Website calculated overall totals are not reproduced; missing scores are not zeros.'])
            elif name == 'announcements':
                rows = array(document, r'allAnnouncements:\s*')
                data = []
                for row in rows:
                    a = row.get('announcement', {})
                    if not a.get('id'):
                        raise LSuiteError('representation_changed', 'Announcement identifier is absent.')
                    data.append({'source_id': a['id'], 'title': a.get('title'), 'body': readable(a.get('text')), 'author': a.get('creatorName'), 'posted': date_value(a.get('date')), 'references': references(a.get('text'))})
                data = unique(data, 'source_id')
                warnings.append(DATE_WARNING)
            elif name == 'schedule':
                events = array(document, r'\b(?:var\s+)?eventArray\s*=\s*')
                data = {'events': [{'source_id': x.get('id'), 'body': readable(x.get('name')), 'date': date_value(x.get('serverDate')), 'source_timestamp': x.get('date'), 'column_id': x.get('column'), 'references': references(x.get('name'))} for x in events],
                        'assignments': array(document, r'\b(?:var|let|const)\s+assignments\s*=\s*'), 'columns': array(document, r'\b(?:var|let|const)\s+columns\s*=\s*')}
                warnings.append(DATE_WARNING)
            else:
                main = BeautifulSoup(document, 'html.parser').select_one('#mainContent')
                if main is None or not main.get_text(strip=True):
                    raise LSuiteError('representation_changed', 'Syllabus representation is absent.')
                data = {'body': readable(str(main)), 'references': references(str(main)), 'binary_contents': 'not_fetched'}
                warnings.append('Linked syllabus files are cataloged; binary contents are not fetched.')
            return SectionResult('ok', sanitize(data), [ORIGIN + path], warnings)
        except LSuiteError as e:
            if e.exit_code == 3:
                raise
            return SectionResult('unavailable' if e.code in ('unavailable', 'permission_denied') else 'error', [], [ORIGIN + path], complete=False, reason={'code': e.code, 'message': e.message})
        except (KeyError, TypeError, ValueError):
            return SectionResult('error', [], [ORIGIN + path], complete=False, reason={'code': 'representation_changed', 'message': 'Section record structure changed; no empty result was inferred.'})

    def _content(self, base):
        records, sources, problems = [], [], []
        for kind, route in [('class_information', 'home/info'), ('learning_outcomes', 'home/outcomes')]:
            source = base + route
            sources.append(ORIGIN + source)
            try:
                document = self._read(source)
                if kind == 'class_information':
                    people = lambda key: [{k: x.get(k) for k in ('name', 'email', 'officePhone', 'officeLocation', 'officeHours', 'appointment')} for x in array(document, r'instance\.' + key + r'\s*=\s*')]
                    records.append({'kind': kind, 'status': 'ok', 'meetings': array(document, r'instance\.meetingInformation\s*=\s*'), 'instructors': people('instructors'), 'teaching_assistants': people('tas')})
                else:
                    normalize = lambda key: [dict(source_id=x.get('CourseOutcomeID') or x.get('id'), title=x.get('Title') or x.get('title'), body=readable(x.get('Outcome') or x.get('outcome'))) for x in array(document, r'\b(?:var\s+)?' + key + r'\s*=\s*')]
                    records.append({'kind': kind, 'status': 'ok', 'department': normalize('departmentOutcomes'), 'instructor': normalize('instructorOutcomes')})
            except LSuiteError as e:
                if e.exit_code == 3:
                    raise
                problems.append({'code': e.code, 'message': e.message})
                records.append({'kind': kind, 'status': 'error', 'reason': problems[-1]})
        if self.browser is None:
            return SectionResult('unsupported', sanitize(records), sources, complete=False, reason={'code': 'browser_unavailable', 'message': 'Nested pages require the optional dedicated Chromium transport.'})
        try:
            initial = self.browser.read(base + 'pages')
            pages = initial.get('pages')
            if not isinstance(pages, list) or any(not isinstance(x, dict) for x in pages):
                raise LSuiteError('representation_changed', 'Content listing did not return page records.')
            if any(initial.get(k) for k in ('nextCursor', 'next_cursor', 'cursor', 'hasMore')):
                problems.append({'code': 'pagination_unverified', 'message': 'Unexpected pagination marker; traversal stopped without guessing its contract.'})
            valid_pages = []
            for row in pages:
                if not isinstance(row.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]+', row['id']) or (row.get('parentID') is not None and not isinstance(row['parentID'], str)):
                    problems.append({'code': 'representation_changed', 'message': 'Malformed page identifier or parent; record skipped.'})
                else:
                    valid_pages.append(row)
            pages = valid_pages
            ids = [x.get('id') for x in pages]
            if len(set(ids)) != len(ids):
                problems.append({'code': 'duplicate_page', 'message': 'Repeated page IDs were deduplicated.'})
            parents = {x.get('id'): x.get('parentID') for x in pages}
            for ident in ids:
                seen, current = set(), ident
                while current is not None and current in parents:
                    if current in seen:
                        problems.append({'code': 'content_cycle', 'message': 'Cyclic content parents detected; traversal is incomplete.'})
                        break
                    seen.add(current)
                    current = parents[current]
                if problems and problems[-1]['code'] == 'content_cycle':
                    break
            pages = unique(pages, 'id')
            if len(pages) > 200:
                problems.append({'code': 'traversal_limit', 'message': 'Content listing exceeds the 200-page read limit.'})
            for row in pages[:200]:
                ident = row.get('id')
                if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', ident):
                    problems.append({'code': 'representation_changed', 'message': 'Invalid page identifier; page skipped.'})
                    continue
                route_token = row.get('url')
                if not isinstance(route_token, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', route_token):
                    problems.append({'code': 'detail_unavailable', 'message': 'Page route token is missing or unverified; page skipped.'})
                    continue
                path = base + 'pages/id-' + route_token
                sources.append(ORIGIN + path)
                try:
                    detail = initial if (initial.get('page') or {}).get('id') == ident else self.browser.read(path)
                    page = detail.get('page')
                    if not isinstance(page, dict) or page.get('id') != ident or not isinstance(page.get('content'), list):
                        raise LSuiteError('detail_unavailable', 'The requested content page detail did not match its listing.')
                    if any(not isinstance(x, dict) for x in page['content']) or not isinstance(detail.get('html'), str):
                        raise LSuiteError('representation_changed', 'Content blocks or rendered HTML have an unexpected shape.')
                    if page.get('expires'):
                        raise LSuiteError('unavailable', 'Content page reports expired availability.')
                    main = BeautifulSoup(detail['html'], 'html.parser').select_one('#mainContent')
                    if main is None:
                        raise LSuiteError('detail_unavailable', 'Rendered page body is absent.')
                    records.append({'kind': 'page', 'status': 'ok', 'source_id': ident, 'parent_id': row.get('parentID'), 'title': page.get('title', row.get('title')),
                                    'body': readable(str(main)), 'references': references(str(main)), 'blocks': [{'source_id': x.get('id'), 'title': x.get('title'), 'body': readable(x.get('data'))} for x in page['content']], 'source': ORIGIN + path})
                except LSuiteError as e:
                    if e.exit_code == 3:
                        raise
                    problems.append({'code': e.code, 'message': e.message})
                    records.append({'kind': 'page', 'status': 'error', 'source_id': ident, 'reason': problems[-1]})
        except LSuiteError as e:
            if e.exit_code == 3:
                raise
            problems.append({'code': e.code, 'message': e.message})
        return SectionResult('ok' if not problems else 'error', sanitize(records), sanitize(sources), [DATE_WARNING] + [p['message'] for p in problems], not problems, problems[0] if problems else None, 'http+browser')

    def close(self):
        if self.http is not None:
            self.http.close()
        if self.browser is not None:
            self.browser.close()
