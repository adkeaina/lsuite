"""Normalize website content without executing it or inventing absent data."""
import re
from datetime import datetime
from urllib.parse import urlsplit, urljoin
from bs4 import BeautifulSoup
from .http import ORIGIN

SENSITIVE = r'(?:subsessionid|phpsessid|sessionid|session|access_token|refresh_token|token|authorization)'


def sanitize(value):
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items() if not re.fullmatch(SENSITIVE, str(k), re.I)}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r'(https?://learningsuite\.byu\.edu)/\.[A-Za-z0-9_-]+(?=/)', r'\1', value)
        value = re.sub(r'(?<![\w])/\.[A-Za-z0-9_-]+(?=/(?:student|cid-|plugins))', '', value)
        value = re.sub(r'([?&])' + SENSITIVE + r'=[^&\s\"\'<>]*&?', r'\1', value, flags=re.I)
        value = value.replace('?&', '?')
        value = re.sub(r'[?&](?=[\"\'<>\s]|$)', '', value)
        return value
    return value


def readable(html):
    soup = BeautifulSoup(str(html or ''), 'html.parser')
    for tag in soup(['script', 'style']):
        tag.decompose()
    return sanitize(re.sub(r'\s+([.,;:!?])', r'\1', soup.get_text(' ', strip=True)))


def references(html, base=ORIGIN):
    soup = BeautifulSoup(str(html or ''), 'html.parser')
    out, seen = [], set()
    for a in soup.select('a[href]'):
        url = sanitize(urljoin(base, a['href']))
        u = urlsplit(url)
        if u.scheme not in ('https', 'http') or u.username or u.password or url in seen:
            continue
        seen.add(url)
        out.append({'name': readable(a.get_text()) or None, 'url': url, 'external': u.hostname != 'learningsuite.byu.edu', 'access': 'not_fetched'})
    return out


def date_value(value):
    iso = None
    if isinstance(value, str):
        try:
            iso = datetime.fromisoformat(value).isoformat() if len(value) > 10 else datetime.fromisoformat(value).date().isoformat()
        except ValueError:
            pass
    return {'source': value, 'iso': iso, 'timezone': None}
