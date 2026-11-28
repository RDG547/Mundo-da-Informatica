"""Notify IndexNow of changed public URLs. No private API credentials required."""
import hashlib
import json
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import urllib.robotparser
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / 'indexnow-config.json').read_text())
ORIGIN = 'https://' + CONFIG['host']
KEY = CONFIG['key']
KEY_URL = ORIGIN + '/' + KEY + '.txt'
STATE = Path('.indexnow-state/state.json')
NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
BLOCKED = ('/admin', '/api/', '/auth', '/login', '/register', '/logout', '/profile', '/download/', '/area-vip', '/debug/', '/setup', '/.lovable/', '/checkout', '/pix-checkout')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

OPENER = urllib.request.build_opener(NoRedirect())

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'SiteOwner-IndexNow/1.0', 'Cache-Control': 'no-cache'})
    try:
        with OPENER.open(req, timeout=25) as response:
            data = response.read(8_000_001)
            if len(data) > 8_000_000:
                raise ValueError('Response too large')
            return response.status, data, response.headers
    except urllib.error.HTTPError as error:
        return error.code, b'', error.headers

def allowed(url):
    u = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(u.path).lower()
    return (u.scheme == 'https' and u.netloc == CONFIG['host']
            and bool(u.path) and not u.query and not u.fragment
            and not path.startswith(BLOCKED) and not path.endswith('/comments')
            and '..' not in path.split('/'))

def parse_sitemap(data):
    root = ET.fromstring(data)
    if root.tag != NS + 'urlset':
        raise ValueError('Expected sitemap urlset')
    result = {}
    for item in root.findall(NS + 'url'):
        url = (item.findtext(NS + 'loc') or '').strip()
        if not allowed(url):
            raise ValueError('Unexpected non-public or foreign sitemap URL: ' + url)
        result[url] = (item.findtext(NS + 'lastmod') or '').strip()
    if not result or len(result) > 1000:
        raise ValueError('Empty or unexpectedly large sitemap; review before submitting')
    return result

def changed_urls(previous, current):
    return sorted(url for url, fingerprint in current.items() if previous.get(url) != fingerprint)

def verify_key():
    for attempt in range(8):
        try:
            status, body, _ = fetch(KEY_URL)
            if status == 200 and body.decode('utf-8').strip() == KEY:
                return
        except (OSError, UnicodeError):
            pass
        if attempt < 7:
            time.sleep(30)
    raise RuntimeError('Production key not yet available; no notification sent')

def main():
    verify_key()
    status, body, _ = fetch(ORIGIN + '/robots.txt')
    if status != 200:
        raise RuntimeError('robots.txt unavailable')
    robots = urllib.robotparser.RobotFileParser()
    robots.parse(body.decode('utf-8').splitlines())
    status, body, _ = fetch(ORIGIN + '/sitemap.xml')
    if status != 200:
        raise RuntimeError('Sitemap unavailable')
    current = parse_sitemap(body)
    for url in current:
        if not robots.can_fetch('Bingbot', url):
            raise RuntimeError('Sitemap URL disallowed by robots.txt: ' + url)
        if CONFIG['mode'] == 'html':
            status, html, headers = fetch(url)
            if status != 200 or 'text/html' not in headers.get('Content-Type', '').lower():
                raise RuntimeError('Public page not available: ' + url)
            if 'noindex' in headers.get('X-Robots-Tag', '').lower():
                raise RuntimeError('Public page is noindex: ' + url)
            if re.search(rb'<meta\b[^>]*name=["\']robots["\'][^>]*content=["\'][^"\']*noindex', html, re.I):
                raise RuntimeError('Public HTML is noindex: ' + url)
            current[url] = hashlib.sha256(html).hexdigest()
    previous = json.loads(STATE.read_text()) if STATE.exists() else {}
    if not isinstance(previous, dict):
        raise ValueError('Invalid submission state')
    pending = changed_urls(previous, current)
    # Only notify confirmed removals of previously public URLs.
    for url in sorted(previous.keys() - current.keys()):
        if not allowed(url) or not robots.can_fetch('Bingbot', url):
            continue
        status, _, _ = fetch(url)
        if status in (404, 410, 301, 308):
            pending.append(url)
        elif status == 200 or status >= 500 or status == 429:
            current[url] = previous[url]
    if pending:
        if len(pending) > 1000:
            raise ValueError('Unexpected submission size')
        payload = json.dumps({'host': CONFIG['host'], 'key': KEY, 'keyLocation': KEY_URL, 'urlList': pending}).encode('utf-8')
        req = urllib.request.Request('https://api.indexnow.org/indexnow', data=payload, headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'SiteOwner-IndexNow/1.0'}, method='POST')
        with OPENER.open(req, timeout=30) as response:
            if response.status not in (200, 202):
                raise RuntimeError('Unexpected IndexNow status: ' + str(response.status))
            print('IndexNow HTTP', response.status, '| URLs accepted for processing:', len(pending))
    else:
        print('No changed public URLs; no IndexNow notification sent.')
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(current, sort_keys=True), encoding='utf-8')

if __name__ == '__main__':
    main()
