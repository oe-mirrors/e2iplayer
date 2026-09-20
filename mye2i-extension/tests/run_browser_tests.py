# -*- coding: utf-8 -*-
# Browser regression tests for the MyE2i extension + mye2iserver.py.
#
# Drives real browsers (headless): Chrome, Edge (Chromium) and Firefox. Needs the
# browsers installed and - for the cases marked [net] - internet access
# (Cloudflare Turnstile / Google / hCaptcha test keys). Not part of CI.
#
#   python mye2i-extension/tests/run_browser_tests.py                  # every installed browser
#   python mye2i-extension/tests/run_browser_tests.py chrome firefox   # only these
#   python mye2i-extension/tests/run_browser_tests.py --only cookies   # cases whose name contains "cookies"
#
# How it works: starts mye2iserver.py (with a session token, like the box) and a
# small local "site" that imitates bot protections (DDoS-Guard-like and Anubis-like
# gates, a page with fetch/XHR calls, a page that sets cf_clearance). The browser
# opens the server's e2it.html page (the relay) and then one tab per case; the
# outcome is read from what the server printed (results, debug dumps, errors).
import argparse
import base64
import json
import os
import re
import shutil
import http.client
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import socketserver
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
EXT_DIR = os.path.dirname(HERE)
EXTRA_ARGS = []  # --chromium-arg
ENTRY = 'token'  # --entry pin: open the relay page the way the typed address + short code does
EXT_UNDER_TEST = EXT_DIR  # --ext-dir replaces it (older releases, backward-compatibility check)
REPO = os.path.dirname(EXT_DIR)
SERVER = os.path.join(REPO, 'IPTVPlayer', 'scripts', 'mye2iserver.py')
PORT_SERVER, PORT_SITE, PORT_DEBUG = 9001, 9100, 9226
TOKEN = 'testtoken1234abcd'
PIN = '482913'
SITE = 'http://127.0.0.1:%d' % PORT_SITE

CHROMIUM = {
    'chrome': [r'C:\Program Files\Google\Chrome\Application\chrome.exe', r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe', '/usr/bin/google-chrome'],
    'edge': [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', r'C:\Program Files\Microsoft\Edge\Application\msedge.exe', '/usr/bin/microsoft-edge'],
}
FIREFOX = [r'C:\Program Files\Mozilla Firefox\firefox.exe', r'C:\Program Files (x86)\Mozilla Firefox\firefox.exe', '/usr/bin/firefox']

NORMAL_PAGE = '<html><head><title>real page</title></head><body><h1>real page</h1></body></html>'
DDG_CHALLENGE = ("<html><head><title>DDoS-Guard</title></head><body><h1>Checking your browser before accessing the site</h1>"
                 "<script>setTimeout(function(){document.cookie='__ddg1_=abc123; path=/'; location.reload();}, 1500);</script></body></html>")
ANUBIS_CHALLENGE = ("<html><head><title>Making sure you're not a bot!</title></head><body><h1>Making sure you're not a bot!</h1><p>Protected by Anubis from Techaro.</p>"
                    "<script>setTimeout(function(){document.cookie='techaro.lol-anubis-auth=tok456; path=/'; location.reload();}, 1500);</script></body></html>")
CF_PAGE = "<html><head><title>CF test</title></head><body><h1>normal page</h1><script>document.cookie='cf_clearance=testvalue123; path=/';</script></body></html>"
# a cookie value whose base64 form contains "+" (three "~" in a row always put one at the third byte of a group)
CF_PLUS_PAGE = CF_PAGE.replace('testvalue123', 'a~~~~~~b')
LATE_PAGE = ("<html><head><title>Late</title></head><body><h1>late</h1><script>setTimeout(function(){"
             "fetch('/api/late', {method:'POST', body:'a=1'}); var x=new XMLHttpRequest(); x.open('GET','/api/late2'); x.send(); }, 1500);</script></body></html>")


# ------------------------------------------------------------ local test site
class Site(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, headers=()):
        data = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', '0')))
        self._send(200, '{"ok":true}')

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        cookies = self.headers.get('Cookie', '')
        if path == '/gate':
            if '__ddg1_=' in cookies:
                self._send(200, NORMAL_PAGE, [('Set-Cookie', '__ddg2_=srv123; Path=/; HttpOnly')])
            else:
                self._send(403, DDG_CHALLENGE, [('Server', 'ddos-guard')])
        elif path == '/anubis':
            self._send(200, NORMAL_PAGE if 'techaro.lol-anubis-auth=' in cookies else ANUBIS_CHALLENGE)
        elif path == '/cf.html':
            self._send(200, CF_PAGE)
        elif path == '/cf-plus.html':
            self._send(200, CF_PLUS_PAGE)
        elif path == '/late.html':
            self._send(200, LATE_PAGE)
        elif path.startswith('/api/'):
            self._send(200, '{"items":[1,2,3]}')
        else:
            self._send(200, '<html><body>x</body></html>')


class QuietServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass  # browsers abort connections when a tab closes itself - not interesting


# ------------------------------------------------------- minimal websocket/CDP
def ws_connect(url):
    hp, path = url[5:].split('/', 1)
    host, port = hp.split(':')
    s = socket.create_connection((host, int(port)))
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall(('GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n' % (path, hp, key)).encode())
    buf = b''
    while b'\r\n\r\n' not in buf:
        buf += s.recv(1)
    s.settimeout(15)
    return s


def ws_send(s, obj):
    data = json.dumps(obj).encode()
    hdr = bytearray([0x81])
    if len(data) < 126:
        hdr.append(0x80 | len(data))
    else:
        hdr.append(0x80 | 126)
        hdr += struct.pack('>H', len(data))
    mask = os.urandom(4)
    hdr += mask
    s.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))


def _recvn(s, n):
    buf = b''
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise EOFError
        buf += chunk
    return buf


def ws_recv(s):
    head = _recvn(s, 2)
    ln = head[1] & 0x7f
    if ln == 126:
        ln = struct.unpack('>H', _recvn(s, 2))[0]
    elif ln == 127:
        ln = struct.unpack('>Q', _recvn(s, 8))[0]
    return _recvn(s, ln).decode('utf-8', 'replace')


# ---------------------------------------------------------------- Marionette
class Marionette(object):
    def __init__(self, port=2828):
        end = time.time() + 60
        while True:
            try:
                self.sock = socket.create_connection(('127.0.0.1', port))
                break
            except OSError:
                if time.time() > end:
                    raise
                time.sleep(0.5)
        self.sock.settimeout(60)
        self.msg_id = 0
        self._recv()

    def _recv(self):
        buf = b''
        while b':' not in buf:
            buf += self.sock.recv(1)
        size = int(buf.split(b':')[0])
        return json.loads(_recvn(self.sock, size).decode('utf-8'))

    def cmd(self, name, params=None):
        self.msg_id += 1
        body = json.dumps([0, self.msg_id, name, params or {}]).encode()
        self.sock.sendall(str(len(body)).encode() + b':' + body)
        while True:
            m = self._recv()
            if m[0] == 1 and m[1] == self.msg_id:
                if m[2]:
                    raise RuntimeError('%s: %s' % (name, m[2].get('message', m[2])))
                return m[3]


# ------------------------------------------------------------------- harness
class Run(object):
    """One browser session: server, site, browser, relay tab."""

    def __init__(self, browser, tmp):
        self.browser = browser
        self.tmp = tmp
        self.procs = []
        self.out_path = os.path.join(tmp, 'srv.out')
        self.err_path = os.path.join(tmp, 'srv.err')
        self.out_pos = 0
        self.err_pos = 0
        self.marionette = None
        self.case_tab = None

    def start(self, exe):
        payload = base64.b64encode(json.dumps({'siteKey': '1', 'siteUrl': SITE + '/', 'captchaType': 'CF', 'token': TOKEN, 'pin': PIN, 'i18n': GERMAN}).encode()).decode()
        self.procs.append(subprocess.Popen([sys.executable, SERVER, payload, '127.0.0.1', str(PORT_SERVER)], stdout=open(self.out_path, 'wb'), stderr=open(self.err_path, 'wb')))
        profile = os.path.join(self.tmp, 'profile')
        if self.browser == 'firefox':
            xpi_dir = os.path.join(self.tmp, 'xpi')
            subprocess.check_call([sys.executable, os.path.join(EXT_DIR, 'build_release.py'), '--firefox', '--out', xpi_dir], stdout=subprocess.DEVNULL)
            self.procs.append(subprocess.Popen([exe, '-headless', '-no-remote', '-marionette', '-profile', profile, 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            time.sleep(3)
            self.marionette = Marionette()
            self.marionette.cmd('WebDriver:NewSession', {})
            self.marionette.cmd('Addon:Install', {'path': os.path.join(xpi_dir, 'mye2iv3-firefox-unsigned.xpi'), 'temporary': True})
            time.sleep(2)
            self.marionette.cmd('WebDriver:Navigate', {'url': self.relay_url()})
        else:
            # a clean copy: Chrome refuses to load a folder that contains a
            # __pycache__ (names starting with "_" are reserved), and pytest or
            # build_release.py leave one behind in the working tree
            ext_copy = os.path.join(self.tmp, 'extension')
            shutil.copytree(EXT_UNDER_TEST, ext_copy, ignore=shutil.ignore_patterns('__pycache__', 'tests', '*.zip', '*.crx'))
            args = [exe, '--headless=new', '--remote-debugging-port=%d' % PORT_DEBUG, '--user-data-dir=' + profile, '--no-first-run'] + EXTRA_ARGS
            if self.browser == 'edge':
                args += ['--load-extension=' + ext_copy, '--disable-features=DisableLoadExtensionCommandLineSwitch']
            else:
                args += ['--enable-unsafe-extension-debugging']  # branded Chrome ignores --load-extension
            self.procs.append(subprocess.Popen(args + ['about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            time.sleep(5)
            if self.browser == 'chrome':
                version = json.load(urllib.request.urlopen('http://127.0.0.1:%d/json/version' % PORT_DEBUG))
                ws = ws_connect(version['webSocketDebuggerUrl'])
                ws_send(ws, {'id': 1, 'method': 'Extensions.loadUnpacked', 'params': {'path': ext_copy}})
                ws_recv(ws)
                time.sleep(2)
            self._new_tab(self.relay_url())
        time.sleep(3)

    def relay_url(self):
        # the entry address the QR code carries; the server redirects it to /e2it.html
        if ENTRY == 'pin':  # what the typed address + short code leads to (the form's GET, then a redirect)
            return 'http://127.0.0.1:%d/e2it.html?pin=%s' % (PORT_SERVER, PIN)
        return 'http://127.0.0.1:%d/?t=%s' % (PORT_SERVER, TOKEN)

    def _new_tab(self, url):
        info = json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:%d/json/new?%s' % (PORT_DEBUG, urllib.parse.quote(url, safe='')), method='PUT')))
        try:  # a background tab is throttled by Chromium - bring it to the front
            urllib.request.urlopen('http://127.0.0.1:%d/json/activate/%s' % (PORT_DEBUG, info['id'])).read()
        except Exception:
            pass
        return info.get('id')

    def list_tabs(self):
        if self.marionette:
            return '(n/a)'
        try:
            return ' ; '.join('%s %s' % (t.get('title', '')[:25], t['url'][:70]) for t in json.load(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % PORT_DEBUG)) if t['type'] == 'page')
        except Exception as e:
            return '(%s)' % e

    def close_case(self):
        """Close the tab of the case that just ran (it may already have closed itself)."""
        try:
            if self.marionette:
                self.marionette.cmd('WebDriver:CloseWindow', {})
                self.marionette.cmd('WebDriver:SwitchToWindow', {'handle': self.marionette.cmd('WebDriver:GetWindowHandles', {})[0]})
            elif self.case_tab:
                urllib.request.urlopen('http://127.0.0.1:%d/json/close/%s' % (PORT_DEBUG, self.case_tab)).read()
        except Exception:
            pass

    def open_case(self, url, wait):
        if self.marionette:
            handles = self.marionette.cmd('WebDriver:GetWindowHandles', {})
            self.marionette.cmd('WebDriver:SwitchToWindow', {'handle': handles[0]})
            handle = self.marionette.cmd('WebDriver:NewWindow', {'type': 'tab'})
            self.marionette.cmd('WebDriver:SwitchToWindow', {'handle': handle['handle']})
            self.marionette.cmd('WebDriver:Navigate', {'url': url})
        else:
            self.case_tab = self._new_tab(url)
        time.sleep(wait)

    def relay_eval(self, expr):
        """Evaluate JS in the relay tab (the page the box serves, first tab of the session)."""
        if self.marionette:
            try:
                self.marionette.cmd('WebDriver:SwitchToWindow', {'handle': self.marionette.cmd('WebDriver:GetWindowHandles', {})[0]})
                return self.marionette.cmd('WebDriver:ExecuteScript', {'script': 'return ' + expr, 'args': []})['value']
            except RuntimeError as e:
                return '(%s)' % e
        tabs = [t for t in json.load(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % PORT_DEBUG)) if t['type'] == 'page' and '/e2it.html' in t['url']]
        if not tabs:
            return '(relay tab gone)'
        ws = ws_connect(tabs[0]['webSocketDebuggerUrl'])
        ws_send(ws, {'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}})
        while True:
            m = json.loads(ws_recv(ws))
            if m.get('id') == 1:
                return m['result'].get('result', {}).get('value')

    def page_eval(self, url, expr):
        """Evaluate JS in the case tab; '(tab gone)' if it closed itself (the normal end of a solved job)."""
        if self.marionette:
            try:
                return self.marionette.cmd('WebDriver:ExecuteScript', {'script': 'return ' + expr, 'args': []})['value']
            except RuntimeError:
                return '(tab gone)'
        part = url.split('#', 1)[1]
        tabs = [t for t in json.load(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % PORT_DEBUG)) if t['type'] == 'page' and part in t['url']]
        if not tabs:
            return '(tab gone)'
        ws = ws_connect(tabs[-1]['webSocketDebuggerUrl'])
        ws_send(ws, {'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}})
        while True:
            m = json.loads(ws_recv(ws))
            if m.get('id') == 1:
                return m['result'].get('result', {}).get('value')

    def new_output(self):
        """(stdout, stderr) of the server since the last call."""
        chunks = []
        for name in ('out', 'err'):
            with open(getattr(self, name + '_path'), 'rb') as f:
                f.seek(getattr(self, name + '_pos'))
                data = f.read()
                setattr(self, name + '_pos', getattr(self, name + '_pos') + len(data))
            chunks.append(data.decode('utf-8', 'replace'))
        return chunks[0], chunks[1]

    def stop(self):
        for p in self.procs:
            try:
                p.kill()
            except Exception:
                pass
        time.sleep(1)


def token_results(err):
    """captcha_result payloads printed by the server: decoded CF/cookie tokens or the plain widget token."""
    found = []
    for line in err.splitlines():
        if 'captcha_result' not in line:
            continue
        data = json.loads(re.search(r'\{.*\}', line).group(0))['data']
        try:
            found.append(json.loads(base64.b64decode(data)))
        except Exception:
            found.append(data)
    return found


def cookie_names(result):
    return sorted(c['name'] for c in result['cookie']) if isinstance(result, dict) else []


TURNSTILE_OK = '1x00000000000000000000AA'
TURNSTILE_FAIL = '2x00000000000000000000AB'
FAKE_KEY = '6LfFAKEfakeFAKEfakeFAKEfakeFAKEfakeFAKE1'
HCAPTCHA_TEST = '10000000-ffff-ffff-ffff-000000000001'

GERMAN = {  # what the plugin sends for the language "de" (some keys left out on purpose: they stay English)
    'pin_prompt': 'Code eingeben (äöü)',
    'pin_continue': 'Weiter',
    'err_not_found': 'Seite nicht gefunden – bitte Adresse prüfen.',
    'status_waiting': 'Warte auf das Ergebnis ...',
    'extension_outdated': 'Erweiterung veraltet (ab v%s)',
    'x_done': 'Fertig – Seite kann geschlossen werden.',
    'header_please_solve': 'Bitte lösen, um fortzufahren mit:',
    'help_whats_happening_header': 'Was passiert hier?',
    'button_i_am_no_robot': 'Ich bin kein Roboter',
}


SOLVER_TEXTS = ("[document.getElementById('header_please_solve').textContent, document.getElementById('help_whats_happening_header').textContent, "
                "(document.querySelector('.invisible-captcha-button') || {textContent: 'no button'}).textContent].join('|')")
# name, url, options, check(out, err, page) -> failure message or ''
CASES = [
    ('cf-cookie', SITE + '/cf.html#e2itcf_sep_c=1', {},
     lambda out, err, page: '' if any('cf_clearance' in cookie_names(r) for r in token_results(err)) else 'no cf_clearance token'),
    ('cf-cookie-with-plus-in-token', SITE + '/cf-plus.html#e2itcf_sep_c=3', {},
     lambda out, err, page: '' if any(c.get('value') == 'a~~~~~~b' for r in token_results(err) if isinstance(r, dict) for c in r.get('cookie', [])) else 'result with "+" in its base64 did not arrive intact'),
    ('cookies-ddos-guard', SITE + '/gate#e2itck_sep_c=1', {'wait': 16},
     lambda out, err, page: '' if any({'__ddg1_', '__ddg2_'} <= set(cookie_names(r)) for r in token_results(err)) else 'expected __ddg1_ (script) and __ddg2_ (HttpOnly) cookies, got %s' % [cookie_names(r) for r in token_results(err)]),
    ('cookies-anubis', SITE + '/anubis#e2itck_sep_c=1', {'wait': 16},
     lambda out, err, page: '' if any('techaro.lol-anubis-auth' in cookie_names(r) for r in token_results(err)) else 'no anubis cookie'),
    ('debug-snapshot', SITE + '/late.html#e2itdbg_sep_c=1', {'wait': 14},
     lambda out, err, page: '' if all(('BEGIN ' + s) in out for s in ('meta', 'dom', 'resources', 'netlog', 'cookies')) and '"url":"/api/late"' in out and '"method":"POST"' in out and '"type": "popup"' in err else 'snapshot sections or POST netlog entry missing'),
    ('turnstile-ok [net]', SITE + '/#e2it?k=%s&st=cf_re' % TURNSTILE_OK, {},
     lambda out, err, page: '' if 'XXXX.DUMMY.TOKEN.XXXX' in token_results(err) else 'no Turnstile token'),
    ('turnstile-fail [net]', SITE + '/#e2it?k=%s&st=cf_re' % TURNSTILE_FAIL, {},
     lambda out, err, page: '' if 'reported an error: 600010' in out and 'Captcha error: 600010' in str(page) else 'error 600010 not shown/logged'),
    ('turnstile-action-cdata [net]', SITE + '/#e2it?k=%s&st=cf_re&a=login&d=cd1' % TURNSTILE_FAIL, {'expr': "document.querySelector('.cf-turnstile').getAttribute('data-action') + '|' + document.querySelector('.cf-turnstile').getAttribute('data-cdata')"},
     lambda out, err, page: '' if page == 'login|cd1' else 'data-action/data-cdata wrong: %r' % (page,)),
    ('recaptcha-v3-fake-key [net]', SITE + '/#e2it?k=%s&st=&a=login' % FAKE_KEY, {},
     lambda out, err, page: '' if 'reported an error' in out and 'Captcha error' in str(page) else 'rejected execute() not reported'),
    ('enterprise-score-fake-key [net]', SITE + '/#e2it?k=%s&st=ENTERPRISE&a=login' % FAKE_KEY, {'expr': "JSON.stringify([...document.scripts].map(s=>s.src).filter(x=>/enterprise/.test(x)))"},
     lambda out, err, page: '' if 'enterprise.js' in str(page) and 'reported an error' in out else 'enterprise.js not loaded / error not reported'),
    ('relay-status-translated', SITE + '/cf.html#e2itcf_sep_c=2', {'relay_expr': "document.getElementById('mye2i-status-text').textContent"},
     lambda out, err, page: '' if page == GERMAN['x_done'] else 'relay page status is %r, not the German text' % (page,)),
    ('solver-texts-english', SITE + '/#e2it?k=%s&st=INVISIBLE' % FAKE_KEY, {'expr': SOLVER_TEXTS},
     lambda out, err, page: '' if page == "Please solve to continue downloads with:|What's happening?|I am no robot" else 'built-in English texts wrong: %r' % (page,)),
    ('solver-texts-translated', SITE + '/#e2it?k=%s&st=INVISIBLE&l=%s' % (FAKE_KEY, urllib.parse.quote(json.dumps(GERMAN), safe='')), {'expr': SOLVER_TEXTS},
     lambda out, err, page: '' if page == '|'.join((GERMAN['header_please_solve'], GERMAN['help_whats_happening_header'], GERMAN['button_i_am_no_robot'])) else 'translated texts not shown: %r' % (page,)),
    ('hcaptcha-invisible [net]', SITE + '/#e2it?k=%s&st=h1_invisible' % HCAPTCHA_TEST, {'click': True},
     lambda out, err, page: '' if '10000000-aaaa-bbbb-cccc-000000000001' in token_results(err) else 'no hCaptcha token'),
]

CLICK = "(function(){var b=document.querySelector('.invisible-captcha-button'); if(b){b.click(); return 'clicked';} return 'no button';})()"
TEXT = "(document.getElementById('captchaContainer') ? document.getElementById('captchaContainer').innerText : document.title)"


def request(url, method='GET', data=None):
    """(status, body, Location header) - redirects are NOT followed."""
    parts = urllib.parse.urlsplit(url)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=10)
    try:
        conn.request(method, parts.path + ('?' + parts.query if parts.query else ''), body=data)
        resp = conn.getresponse()
        return resp.status, resp.read().decode('utf-8', 'replace'), resp.getheader('Location', '')
    finally:
        conn.close()


def http_status(url, method='GET', data=None):
    return request(url, method, data)[0]


def start_server(i18n=None, captcha_type='CF', secure=True, extra=None):
    data = {'siteKey': '1', 'siteUrl': SITE + '/', 'captchaType': captcha_type, 'token': TOKEN if secure else '', 'pin': PIN if secure else ''}
    data.update(extra or {})
    if i18n:
        data['i18n'] = i18n
    payload = base64.b64encode(json.dumps(data).encode()).decode()
    proc = subprocess.Popen([sys.executable, SERVER, payload, '127.0.0.1', str(PORT_SERVER)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    return proc


def token_enforcement():
    """Server only. Returns (number of checks, list of failed checks).

    A stranger (no token, no code) gets no page with the token and no results/debug
    access. Access is granted by the token (QR code address ?t=...), by typing the
    short code on the plain address, or - for extensions older than 1.18, that do not
    repeat the token on their own requests - by having got in that way before."""
    base = 'http://127.0.0.1:%d' % PORT_SERVER
    checks = []

    # 1) a stranger, then the code typed on the plain address
    proc = start_server()
    try:
        status, body, _loc = request(base + '/e2it.html')
        checks += [('stranger: plain address shows the code page', (status, 'name="pin"' in body), (200, True)),
                   ('stranger: the code page does not leak the token', (TOKEN in body, 'mye2i-token' in body), (False, False))]
        status, body, _loc = request(base + '/')
        checks.append(('stranger: entry address shows the code page', (status, 'name="pin"' in body), (200, True)))
        checks += [
            ('stranger: /response', http_status(base + '/response?c=1&token=x'), 403),
            ('stranger: /response wrong token', http_status(base + '/response?c=1&token=x&t=nope'), 403),
            ('stranger: /debug', http_status(base + '/debug?msg=x'), 403),
            ('stranger: /debugdump', http_status(base + '/debugdump?name=a', 'POST', b'x'), 403),
            ('/version needs no token', http_status(base + '/version?v=1.18'), 200),
        ]
        status, body, _loc = request(base + '/e2it.html?pin=000000')
        checks += [('wrong code: says so, still no access', (status, 'Wrong code' in body, 'mye2i-token' in body), (200, True, False)),
                   ('wrong code does not unlock /response', http_status(base + '/response?c=1&token=x'), 403)]
        status, _body, loc = request(base + '/e2it.html?pin=' + PIN)
        checks.append(('right code: redirects to the page', (status, loc), (302, '/e2it.html')))
        status, body, _loc = request(base + '/e2it.html')
        checks.append(('after the code: page with the token for the extension', (status, ('name="mye2i-token" content="%s"' % TOKEN) in body), (200, True)))
        checks += [
            ('after the code: /response without token (older extensions)', http_status(base + '/response?c=1&token=x'), 200),
            ('after the code: /debug', http_status(base + '/debug?msg=x'), 200),
            ('after the code: /debugdump', http_status(base + '/debugdump?name=a', 'POST', b'x'), 200),
        ]
    finally:
        proc.kill()
        time.sleep(1)

    # 2) guessing the code: locked after 10 wrong tries, the right code no longer works
    proc = start_server()
    try:
        for i in range(10):
            request(base + '/e2it.html?pin=%06d' % i)
        status, body, _loc = request(base + '/e2it.html?pin=' + PIN)
        checks.append(('locked after 10 wrong codes', (status, 'Too many wrong codes' in body, 'mye2i-token' in body), (200, True, False)))
        checks.append(('locked: /response still refused', http_status(base + '/response?c=1&token=x'), 403))
        status, _body, loc = request(base + '/?t=' + TOKEN)
        checks.append(('locked: the QR code address still works', (status, loc), (302, '/e2it.html')))
    finally:
        proc.kill()
        time.sleep(1)

    # 3) the QR code address (token)
    proc = start_server()
    try:
        status, _body, loc = request(base + '/?t=' + TOKEN)
        checks.append(('QR address with token redirects to the page', (status, loc), (302, '/e2it.html')))
        checks.append(('page after the QR address', http_status(base + '/e2it.html'), 200))
        checks.append(('/response without token after the QR address (older extensions)', http_status(base + '/response?c=1&token=x'), 200))
    finally:
        proc.kill()
        time.sleep(1)

    # 3b) replies that repeat the request are plain text (never rendered as a page); the page comes from memory
    proc = start_server()
    try:
        request(base + '/?t=' + TOKEN)
        conn = http.client.HTTPConnection('127.0.0.1', PORT_SERVER, timeout=10)
        conn.request('GET', '/response?c=1&token=%3Cb%3Ex')
        answer = conn.getresponse()
        answer.read()
        checks.append(('/response reply is plain text', answer.getheader('Content-Type'), 'text/plain'))
        conn.close()
        status, body, _loc = request(base + '/e2it.html')
        checks.append(('relay page is served (from memory)', (status, 'id="mye2i-i18n"' in body), (200, True)))
    finally:
        proc.kill()
        time.sleep(1)

    # 3c) debug dumps land in the plugin's temporary folder when the box names it
    with tempfile.TemporaryDirectory() as tmp_dir:
        proc = start_server(extra={'tmpDir': tmp_dir})
        try:
            request(base + '/?t=' + TOKEN)
            http_status(base + '/debugdump?name=probe', 'POST', b'hello')
            time.sleep(1)
            dumps = os.listdir(os.path.join(tmp_dir, 'mye2i_debug')) if os.path.isdir(os.path.join(tmp_dir, 'mye2i_debug')) else []
            checks.append(('debug dump goes to <tmpDir>/mye2i_debug', [name.endswith('_probe.txt') for name in dumps], [True]))
        finally:
            proc.kill()
            time.sleep(1)

    # 4) setting "increase security" off: no token, no code - the plain address opens the page
    proc = start_server(secure=False)
    try:
        status, body, _loc = request(base + '/e2it.html')
        checks.append(('security off: plain address opens the page', (status, 'name="pin"' in body, 'id="mye2i_' in body), (200, False, True)))
        status, _body, loc = request(base + '/')
        checks.append(('security off: entry address redirects to the page', (status, loc), (302, '/e2it.html')))
        checks.append(('security off: /response without token', http_status(base + '/response?c=1&token=x'), 200))
        checks.append(('security off: /debugdump', http_status(base + '/debugdump?name=a', 'POST', b'x'), 200))
    finally:
        proc.kill()
        time.sleep(1)
    return len(checks), [(name, got, want) for name, got, want in checks if got != want]


def translation_checks():
    """Server only: texts come from the plugin (CAPTCHA_DATA['i18n']), English where a key is missing."""
    base = 'http://127.0.0.1:%d' % PORT_SERVER
    checks = []

    proc = start_server(GERMAN)
    try:
        status, body, _loc = request(base + '/e2it.html')
        checks.append(('code page in German', (status, 'Code eingeben (äöü)' in body, '>Weiter<' in body), (200, True, True)))
        status, body, _loc = request(base + '/e2it.html?pin=000000')
        checks.append(('wrong code: key not sent stays English', (status, 'Wrong code.' in body), (200, True)))
        status, body, _loc = request(base + '/nothing-here')
        checks.append(('404 page in German', (status, 'Seite nicht gefunden' in body), (404, True)))
        checks.append(('403 page for a stranger keeps English (key not sent)', (http_status(base + '/response?c=1&token=x'),), (403,)))
        request(base + '/e2it.html?pin=' + PIN)
        status, body, _loc = request(base + '/e2it.html')
        checks.append(('relay page: status text in German', (status, 'Warte auf das Ergebnis' in body), (200, True)))
        checks.append(('relay page: outdated banner in German with the version', 'Erweiterung veraltet (ab v1.17)' in body, True))
        checks.append(('relay page: untranslated debug texts stay English', 'Debug snapshot (for site development)' in body, True))
        m = re.search(r'<script type="application/json" id="mye2i-i18n">(.*?)</script>', body, re.S)
        texts = json.loads(m.group(1)) if m else {}
        checks.append(('relay page: JSON for the extension', (texts.get('x_done'), texts.get('x_error')), (GERMAN['x_done'], 'Error occurs:')))
    finally:
        proc.kill()
        time.sleep(1)

    # captcha types: the solver page address carries the translated solver texts
    for i18n, expect in ((GERMAN, True), (None, False)):
        proc = start_server(i18n, 'v2')
        try:
            request(base + '/?t=' + TOKEN)
            status, body, _loc = request(base + '/e2it.html')
            href = re.search(r'<a href="([^"]*)" target="_blank"><button', body)
            url = href.group(1).replace('&amp;', '&') if href else ''
            fragment = url.split('#', 1)[1] if '#' in url else ''
            params = dict(p.split('=', 1) for p in fragment.split('?', 1)[-1].split('&') if '=' in p)
            got = json.loads(urllib.parse.unquote(params['l'])) if 'l' in params else None
            want = {k: GERMAN[k] for k in ('header_please_solve', 'help_whats_happening_header', 'button_i_am_no_robot')} if expect else None
            checks.append(('solver address %s translated texts' % ('carries' if expect else 'has no'), got, want))
        finally:
            proc.kill()
            time.sleep(1)
    return len(checks), [(name, got, want) for name, got, want in checks if got != want]


def find_browser(name):
    for path in (FIREFOX if name == 'firefox' else CHROMIUM.get(name, [])):
        if os.path.exists(path):
            return path
    return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('browsers', nargs='*', help='chrome edge firefox (default: all installed)')
    ap.add_argument('--only', default='', help='run only cases whose name contains this text (comma-separated list allowed)')
    ap.add_argument('--repeat', type=int, default=1, help='run every selected case this many times per browser (flakiness check)')
    ap.add_argument('--ext-dir', default='', help='unpacked older extension to test instead of the current one (Chrome/Edge only) - checks backward compatibility')
    ap.add_argument('--entry', choices=('token', 'pin'), default='token', help='how the relay page is opened: QR address with the token (default) or the short code')
    ap.add_argument('--chromium-arg', action='append', default=[], help='extra command line argument for Chrome/Edge (repeatable), e.g. to re-enable manifest v2 for very old extensions')
    ap.add_argument('-v', '--verbose', action='store_true', help='print what the server saw for failing cases')
    args = ap.parse_args()
    browsers = args.browsers or ['chrome', 'edge', 'firefox']
    global ENTRY
    ENTRY = args.entry
    EXTRA_ARGS.extend(args.chromium_arg)
    if args.ext_dir:
        global EXT_UNDER_TEST
        EXT_UNDER_TEST = os.path.abspath(args.ext_dir)
        browsers = [b for b in browsers if b != 'firefox']

    site = QuietServer(('127.0.0.1', PORT_SITE), Site)
    threading.Thread(target=site.serve_forever, daemon=True).start()

    failures = 0
    print('server token enforcement / backward compatibility:')
    count, bad = token_enforcement()
    for name, got, want in bad:
        print('  FAIL %s: got %s, expected %s' % (name, got, want))
    print('  %s' % ('FAIL' if bad else 'PASS (%d checks)' % count))
    failures += len(bad)

    print('translated pages (texts from the plugin):')
    count, bad = translation_checks()
    for name, got, want in bad:
        print('  FAIL %s: got %r, expected %r' % (name, got, want))
    print('  %s' % ('FAIL' if bad else 'PASS (%d checks)' % count))
    failures += len(bad)

    for browser in browsers:
        exe = find_browser(browser)
        if not exe:
            print('\n%s: not installed - skipped' % browser)
            continue
        print('\n%s (%s):' % (browser, exe))
        with tempfile.TemporaryDirectory() as tmp:
            run = Run(browser, tmp)
            try:
                run.start(exe)
                init_out, _init_err = run.new_output()
                if args.verbose:
                    print('  start-up server output: ' + ' | '.join(init_out.strip().splitlines())[-300:])
                for name, url, opts, check in [c for c in CASES if not args.only or any(part in c[0] for part in args.only.split(','))] * args.repeat:
                    run.new_output()
                    run.open_case(url, opts.get('wait', 10))
                    if opts.get('click'):
                        run.page_eval(url, CLICK)
                        time.sleep(8)
                    page = run.page_eval(url, opts.get('expr', TEXT))
                    if opts.get('relay_expr'):
                        page = run.relay_eval(opts['relay_expr'])
                    out, err = run.new_output()
                    tabs_seen = run.list_tabs() if args.verbose else ''
                    run.close_case()
                    problem = check(out, err, page)
                    print('  %s %s%s' % ('FAIL' if problem else 'PASS', name, (' - ' + problem) if problem else ''))
                    if problem and args.verbose:
                        print('    server stdout: ' + ' | '.join(out.strip().splitlines())[-700:])
                        print('    server stderr: ' + ' | '.join(err.strip().splitlines())[-300:])
                        print('    page: %r' % (page,))
                        print('    tabs: %s' % tabs_seen)
                    failures += 1 if problem else 0
            finally:
                run.stop()
    print('\n%s' % ('%d FAILURE(S)' % failures if failures else 'ALL PASSED'))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
