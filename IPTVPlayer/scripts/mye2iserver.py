# -*- encoding: utf-8 -*-

import base64
import hmac
from html import escape as html_escape
from http.server import SimpleHTTPRequestHandler
import json
import re
import socketserver
import sys
import os
import tempfile
import threading
import time
import traceback
import signal
from urllib.parse import urlsplit, parse_qs, quote


def signal_handler(sig, frame):
    os.kill(os.getpid(), signal.SIGTERM)


signal.signal(signal.SIGINT, signal_handler)


def updateStatus(pType, pData, pCode=None):
    if isinstance(pData, bytes):
        pData = pData.decode()
    obj = {'type': pType, 'data': pData, 'code': pCode}
    sys.stderr.write("\n%s\n" % json.dumps(obj))


# Minimum MyE2i browser-extension version this server expects. Bump this
# whenever a server-side change (like the new /debug endpoint, or a future
# protocol change) needs a matching extension release to work correctly.
# (Kept at 1.17: extensions older than 1.18 do not send the session token but keep
# working - see _authorized() below. Newer features need newer extensions.)
MIN_EXTENSION_VERSION = (1, 17)
MIN_EXTENSION_VERSION_STR = '.'.join(str(part) for part in MIN_EXTENSION_VERSION)
# Fixed download link: the release named "mye2i-extension" keeps its asset name
# and gets the asset replaced on every new extension version (see
# mye2i-extension/README.md), so this URL never has to change.
UPDATE_URL = 'https://github.com/oe-mirrors/e2iplayer/releases/download/mye2i-extension/mye2iv3-latest.zip'


# Texts of everything this server (and the browser extension, which gets them
# from here) shows in the browser. The E2iPlayer plugin sends its translations
# for the same keys in CAPTCHA_DATA['i18n'] (recaptcha_mye2i_widget.py,
# _serverTexts); a key it does not send - a language nobody translated yet, an
# older plugin - falls back to the English text below.
DEFAULT_TEXTS = {
    # short-code page
    'pin_prompt': "Enter the code shown in the title of the window on your receiver's screen (or scan the QR code shown there - no code needed then):",
    'pin_continue': 'Continue',
    'pin_no_session_code': 'This session has no code - scan the QR code on the receiver screen.',
    'pin_locked': 'Too many wrong codes - scan the QR code on the receiver screen instead.',
    'pin_wrong': 'Wrong code.',
    # relay page
    'extension_outdated': 'Your MyE2i extension is outdated or unknown (v%s or newer needed). Please update:',
    'extension_download': 'Download new version',
    'job_cloudflare': 'Get Cloudflare job',
    'job_cookies': 'Get cookies job',
    'job_captcha': 'Get captcha job',
    'status_waiting': 'Waiting for the result ...',
    'debug_pill': 'debug',
    'debug_title': 'Debug snapshot (for site development)',
    'debug_text': 'Needs extension v1.18+. Opens the page in this browser, waits until it is fully rendered (Cloudflare challenge included, solve it if it shows up) and sends the rendered HTML, the fetch/XHR calls and the cookie names to the box debug log.',
    'debug_button': 'Debug snapshot',
    # HTTP error pages
    'err_title': 'Error',
    'err_forbidden': 'Access denied - open the page with the QR code or the code shown on the receiver screen.',
    'err_not_found': 'Page not found - please check the address.',
    'err_bad_length': 'The request has no valid length.',
    'err_too_large': 'The data is too large.',
    # shown by the extension on the relay page (e2it.js reads them from the page)
    'x_done': 'Done - the result was sent to the box, you can close this page.',
    'x_send_failed': 'Sending the result to the box failed.',
    'x_dump_ok': 'Debug snapshot: "%s" received by the box',
    'x_dump_failed': 'Debug snapshot: sending "%s" failed',
    'x_error': 'Error occurs:',
    # shown by the extension on the solver page (passed in the address fragment)
    'header_please_solve': 'Please solve to continue downloads with:',
    'help_whats_happening_header': "What's happening?",
    'help_whats_happening_description': 'wants you to solve a captcha. Only after solving this captcha, you are allowed to continue with your downloads. E2iPlayer is not able to auto-solve these captchas, so we need to pass the captcha to you.',
    'help_whats_happening_link': 'Find out more.',
    'button_i_am_no_robot': 'I am no robot',
    'button_please_wait': 'Please wait...',
    'captcha_error': 'Captcha error:',
}
TEXTS = {}
SOLVER_TEXT_KEYS = ('header_please_solve', 'help_whats_happening_header', 'help_whats_happening_description',
                    'help_whats_happening_link', 'button_i_am_no_robot', 'button_please_wait', 'captcha_error')


def T(key, *args):
    """Text for `key`: the plugin's translation, else the English default; `args` fill its %s."""
    text = TEXTS.get(key)
    if not text or not isinstance(text, str):
        text = DEFAULT_TEXTS[key]
    if not args:
        return text
    try:
        return text % args
    except (TypeError, ValueError):
        return DEFAULT_TEXTS[key] % args


def H(key, *args):
    return html_escape(T(key, *args))


def _json_for_html(obj):
    # inside <script type="application/json">: no "</script>" or "<!--" possible
    return json.dumps(obj, ensure_ascii=False).replace('<', '\\u003c')


def _parse_version_tuple(version):
    parts = []
    for piece in str(version).split('.'):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return tuple(parts)


# Debug snapshot ("probe") support: the extension (v1.18+) can load any page in
# the real browser, wait until it is fully rendered and POST the result back
# here. Bodies are far too big for a GET query string, hence do_POST below.
DEBUG_DUMP_MAX_BYTES = 30 * 1024 * 1024
DEBUG_DUMP_LOG_MAX_CHARS = 500000
DEBUG_DUMP_LOG_LINE_CHARS = 4000
DEBUG_DUMP_DIR = os.path.join(tempfile.gettempdir(), 'mye2i_debug')


_DUMP_LOCK = threading.Lock()


def _save_and_log_dump(name, text):
    with _DUMP_LOCK:
        _save_and_log_dump_locked(name, text)


def _save_and_log_dump_locked(name, text):
    safe_name = re.sub(r'[^A-Za-z0-9_.-]', '_', name)[:40] or 'dump'
    path = ''
    try:
        os.makedirs(DEBUG_DUMP_DIR, exist_ok=True)
        path = os.path.join(DEBUG_DUMP_DIR, '%d_%s.txt' % (int(time.time()), safe_name))
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
    except Exception:
        path = '(could not save: %s)' % traceback.format_exc().strip().splitlines()[-1]
    print('[MyE2i-DUMP] ===== BEGIN %s (%d chars, file: %s) =====' % (safe_name, len(text), path))
    emitted = 0
    for line in text.splitlines() or ['']:
        while True:
            chunk, line = line[:DEBUG_DUMP_LOG_LINE_CHARS], line[DEBUG_DUMP_LOG_LINE_CHARS:]
            print('[MyE2i-DUMP %s] %s' % (safe_name, chunk))
            emitted += len(chunk)
            if not line:
                break
        if emitted >= DEBUG_DUMP_LOG_MAX_CHARS:
            print('[MyE2i-DUMP %s] ... log output truncated at %d chars, full dump is in the file above' % (safe_name, DEBUG_DUMP_LOG_MAX_CHARS))
            break
    print('[MyE2i-DUMP] ===== END %s =====' % safe_name)
    sys.stdout.flush()


def _build_debug_block(url):
    base = html_escape(url.split('#')[0], quote=True)
    return '''
        <center>
            <div id="mye2i-status" style="font-family:sans-serif;margin-top:28px;color:#18383f;font-size:15px">
                <span id="mye2i-status-text">%(waiting)s</span> <span id="mye2i-elapsed"></span>
            </div>
        </center>
        <script>
            var mye2iStart = Date.now();
            setInterval(function () {
                var sec = Math.floor((Date.now() - mye2iStart) / 1000);
                document.getElementById('mye2i-elapsed').textContent = '(' + Math.floor(sec / 60) + ':' + ('0' + (sec %% 60)).slice(-2) + ')';
            }, 1000);
        </script>
        <center>
            <details style="margin-top:56px;font-family:sans-serif;max-width:640px;color:#4a5f66">
                <summary style="cursor:pointer;font-size:12px;color:#7a8f96;list-style:none;width:max-content;margin:0 auto;padding:3px 10px;border:1px solid #b5cbd0;border-radius:12px">%(pill)s</summary>
                <div style="margin-top:14px">
                <b>%(title)s</b><br>
                <small>%(text)s</small><br>
                <input id="dbgurl" type="text" value="%(base)s" style="width:90%%;margin:10px 0;padding:6px">
                <br>
                <button type="button" onclick="startDebug()" style="color: white; font-weight: bold; font-size: large; padding: 2ex; border-radius: 14px; background-color:#3a6ea5">%(button)s</button>
                </div>
            </details>
        </center>
        <script>
            function startDebug() {
                var u = document.getElementById('dbgurl').value.split('#')[0];
                if (u) { window.open(u + '#e2itdbg_sep_c=' + Date.now(), '_blank'); }
            }
        </script>
''' % {'base': base, 'waiting': H('status_waiting'), 'pill': H('debug_pill'), 'title': H('debug_title'), 'text': H('debug_text'), 'button': H('debug_button')}


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    # One thread per connection. Browsers open extra "preconnect" sockets and keep
    # them idle; a single-threaded server sits on such a socket until the browser
    # closes it and every request queued behind it (the /response with the
    # captcha result, debug lines, ...) is held up meanwhile.
    daemon_threads = True
    allow_reuse_address = True


def redirect_handler_factory(url, token='', pin=''):

    if 'e2itcf' in url:
        job_type = 'cloudflare'
    elif 'e2itck' in url:
        job_type = 'cookies'
    else:
        job_type = 'captcha'
    to_write = '''
<!doctype html>
<html>
    <head><meta charset="utf-8"><meta name="mye2i-token" content="%s"><script type="application/json" id="mye2i-i18n">%s</script></head>
    <body style="background-color: #c8dee1">
        <div id="mye2i_%s" style="background:#c0392b;color:#fff;padding:14px;text-align:center;font-family:sans-serif;font-size:16px;">
            %s
            <a href="%s" style="color:#fff;text-decoration:underline;">%s</a>
        </div>
        <img src="data:image/png;base64,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"/>
        <br><br><br><br>
        <center>
            <a href="%s" target="_blank"><button type="Button" style="color: white; font-weight: bold; font-size: x-large; text-align: center; padding: 4ex; border-radius: 20px; background-color:#448844">%s</button></a>
        </center>
        %s
    </body>
</html>
''' % (html_escape(token, quote=True), _json_for_html({k: T(k) for k in DEFAULT_TEXTS if k.startswith('x_')}), MIN_EXTENSION_VERSION_STR,
           html_escape(T('extension_outdated', MIN_EXTENSION_VERSION_STR)), UPDATE_URL, H('extension_download'),
           html_escape(url, quote=True), H('job_' + job_type), _build_debug_block(url))

    relay_page = to_write.encode('utf-8')

    DIRECTORY = os.path.join(os.path.dirname(__file__), "htdocs")
    print(DIRECTORY)

    # Clients (by IP) that opened the entry address WITH the session token or typed
    # the short code shown on the box screen.
    trusted_clients = set()
    last_popup = [0.0]
    pin_failures = [0]          # wrong codes, all clients together
    MAX_PIN_FAILURES = 10       # then the code is dead for this session (the QR code still works)

    def pin_page(error):
        return '''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MyE2i</title></head>
<body style="background:#c8dee1;font-family:sans-serif;text-align:center;padding:48px 16px;color:#18383f">
<h2>MyE2i</h2>
<p>%s</p>
<form method="get" action="/e2it.html">
<input name="pin" inputmode="numeric" pattern="[0-9]*" maxlength="6" autofocus autocomplete="off" style="font-size:30px;text-align:center;width:6em;padding:8px;letter-spacing:4px">
<br><br><button type="submit" style="font-size:20px;padding:10px 30px">%s</button>
</form>
<p style="color:#c0392b;font-weight:bold">%s</p>
</body></html>''' % (H('pin_prompt'), H('pin_continue'), html_escape(error))

    # the standard error page of http.server is English only: same content, texts from T()
    error_page = '''<!DOCTYPE HTML>
<html><head><meta charset="utf-8"><title>MyE2i</title></head>
<body style="background:#c8dee1;font-family:sans-serif;padding:32px;color:#18383f">
<h2>''' + H('err_title').replace('%', '%%') + '''</h2><p>%(code)d - %(explain)s</p></body></html>'''
    error_keys = {403: 'err_forbidden', 404: 'err_not_found', 411: 'err_bad_length', 413: 'err_too_large'}

    class RedirectHandler(SimpleHTTPRequestHandler):
        error_message_format = error_page
        error_content_type = 'text/html;charset=utf-8'

        def send_error(self, code, message=None, explain=None):
            # (the status line keeps the English reason phrase; only the page body is translated)
            if code in error_keys:
                message, explain = None, T(error_keys[code])
            SimpleHTTPRequestHandler.send_error(self, code, message, explain)

        def __init__(self, *args, **kwargs):
            SimpleHTTPRequestHandler.__init__(self, *args, directory=DIRECTORY, **kwargs)

        def _trusted(self):
            # Pages, results, debug lines and dumps are only for whoever has the
            # per-session token (QR code: /?t=...) or typed the short code:
            #  - a request carrying the token is accepted, and its client is
            #    remembered (by IP);
            #  - a request without it is accepted if it comes from such a client.
            #    That keeps extensions older than 1.18 working: they load the
            #    page through the entry address but do not repeat the token on
            #    their own /response and /debug requests;
            #  - everything else (another device in the LAN) gets nothing.
            # Without a token in the configuration (stand-alone test run)
            # everything is accepted as before.
            if not token:
                return True
            client = self.client_address[0]
            supplied = self._query().get('t', [''])[0]
            if hmac.compare_digest(supplied.encode('utf-8'), token.encode('utf-8')):
                trusted_clients.add(client)
                return True
            return client in trusted_clients

        def _authorized(self):
            if self._trusted():
                return True
            print('[MyE2i-Browser] rejected %s request from %s without a valid token' % (urlsplit(self.path).path, self.client_address[0]))
            sys.stdout.flush()
            self.send_error(403)
            return False

        def _redirect(self, location):
            self.send_response(302)
            self.send_header('Location', location)
            self.send_header('Content-Length', '0')
            self.end_headers()

        def _entry(self):
            # Page requests. True = serve the page. Otherwise this already
            # answered: a small page asking for the short code (the plain address
            # typed by hand), or the redirect after the right code.
            if self._trusted():
                return True
            error = ''
            given = self._query().get('pin', [''])[0].strip()
            if given:
                if not pin:
                    error = T('pin_no_session_code')
                elif pin_failures[0] >= MAX_PIN_FAILURES:
                    error = T('pin_locked')
                elif hmac.compare_digest(given.encode('utf-8'), pin.encode('utf-8')):
                    trusted_clients.add(self.client_address[0])
                    self._redirect('/e2it.html')
                    return False
                else:
                    pin_failures[0] += 1
                    error = T('pin_wrong')
                    print('[MyE2i-Browser] wrong code from %s (%d/%d)' % (self.client_address[0], pin_failures[0], MAX_PIN_FAILURES))
                    sys.stdout.flush()
            body = pin_page(error).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return False

        def _reply(self, body, content_type='text/plain'):
            if isinstance(body, str):
                body = body.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _query(self):
            return parse_qs(urlsplit(self.path).query)

        def do_GET(self):
            # Route on the exact path component only (never on the whole
            # self.path incl. query string) - a substring check like
            # "'response' in self.path" would also match e.g.
            # "/debug?msg=...response send OK..." (the debug relay forwards
            # free-text log lines that can legitimately contain the word
            # "response"), silently misrouting that request into the
            # /response handler, which then crashes on the missing token
            # param. Query values must never influence routing.
            route = urlsplit(self.path).path
            if route in ('/', '/index.html', '/e2it.html'):
                # the page carries the session token: only for trusted clients
                if not self._entry():
                    return
            if route == '/':
                self._redirect('/e2it.html')
                return
            if route == '/e2it.html':
                self._reply(relay_page, 'text/html; charset=utf-8')
                return
            if route == '/response':
                if not self._authorized():
                    return
                # (plain text: the reply repeats the request, it must never be rendered as a page)
                self._reply(self.path)
                token = self._query().get('token', [None])[0]
                if token is not None:
                    updateStatus('captcha_result', token)
                return
            if route == '/debug':
                if not self._authorized():
                    return
                # forwards free-text debug lines from the browser extension
                # into stdout, which the box side already reads line by
                # line into its own debug log (printDBG) - lets the
                # extension's own console.log-style diagnostics show up on
                # the box without needing browser devtools open.
                self._reply('OK')
                print('[MyE2i-Browser] ' + self._query().get('msg', [''])[0])
                sys.stdout.flush()
                return
            if route == '/version':
                # the browser extension reports its own manifest version
                # here as soon as the local page loads (before the user
                # even clicks the solve button) - if it's older than what
                # this server expects, surface an update hint directly on
                # the box's own captcha-solver screen instead of only in
                # the (easy to miss) browser page banner.
                self._reply('OK')
                ext_version = self._query().get('v', [''])[0]
                if not ext_version:
                    print('[MyE2i-Browser] Extension version check: no version reported (old extension?)')
                elif _parse_version_tuple(ext_version) < MIN_EXTENSION_VERSION:
                    print('[MyE2i-Browser] Extension version check: v%s is OUTDATED (min v%s)' % (ext_version, MIN_EXTENSION_VERSION_STR))
                    updateStatus('status', 'MyE2i extension is outdated - please update it.')
                else:
                    print('[MyE2i-Browser] Extension version check: v%s OK (min v%s)' % (ext_version, MIN_EXTENSION_VERSION_STR))
                sys.stdout.flush()
                return
            SimpleHTTPRequestHandler.do_GET(self)

        def do_POST(self):
            # Only /debugdump is handled: the extension's debug snapshot
            # (rendered DOM, network log, ...) arrives here as the request
            # body, is saved to DEBUG_DUMP_DIR and mirrored into stdout so
            # it lands in the box debug log. The route is matched on the
            # exact path, same as do_GET.
            route = urlsplit(self.path).path
            if route != '/debugdump':
                self.send_error(404)
                return
            if not self._authorized():
                return
            try:
                length = int(self.headers.get('Content-Length', '-1'))
            except ValueError:
                length = -1
            if length < 0:
                self.send_error(411)
                return
            if length > DEBUG_DUMP_MAX_BYTES:
                self.send_error(413)
                return
            body = self.rfile.read(length)
            name = self._query().get('name', ['dump'])[0]
            self._reply('OK')
            _save_and_log_dump(name, body.decode('utf-8', errors='replace'))
            # one pop-up on the box per snapshot (it arrives as several dumps in a row)
            now = time.time()
            if now - last_popup[0] > 60:
                last_popup[0] = now
                updateStatus('popup', 'MyE2i debug snapshot received - see the debug log.')
    return RedirectHandler


if __name__ == "__main__":
    try:
        if len(sys.argv) < 4:
            sys.stderr.write('Wrong parameters\n')
            sys.exit(1)

        CAPTCHA_DATA = json.loads(base64.b64decode(sys.argv[1]))
        IP = sys.argv[2]
        PORT = int(sys.argv[3])

        returnCode = 0

        siteUrl = CAPTCHA_DATA['siteUrl']
        siteKey = CAPTCHA_DATA['siteKey']
        captchaType = CAPTCHA_DATA['captchaType']
        captchaAction = CAPTCHA_DATA.get('captchaAction') or ''
        if CAPTCHA_DATA.get('tmpDir'):
            DEBUG_DUMP_DIR = os.path.join(CAPTCHA_DATA['tmpDir'], 'mye2i_debug')
        captchaData = CAPTCHA_DATA.get('captchaData') or ''
        sessionToken = CAPTCHA_DATA.get('token') or ''
        sessionPin = CAPTCHA_DATA.get('pin') or ''
        # the plugin's translations of the texts above (keys as in DEFAULT_TEXTS)
        translations = CAPTCHA_DATA.get('i18n')
        if isinstance(translations, dict):
            TEXTS.update({k: v for k, v in translations.items() if k in DEFAULT_TEXTS})

        socketserver.TCPServer.allow_reuse_address = True
        if captchaType == 'CF':
            httpd = ThreadedServer((IP, PORT), redirect_handler_factory('%s#e2itcf_sep_c=%s' % (siteUrl, siteKey), sessionToken, sessionPin))
        elif captchaType == 'COOKIES':
            # generic browser check (DDoS-Guard, Sucuri, Imperva, Anubis, ...): every cookie comes back
            httpd = ThreadedServer((IP, PORT), redirect_handler_factory('%s#e2itck_sep_c=%s' % (siteUrl, siteKey), sessionToken, sessionPin))
        else:
            fragment = '%s/#e2it?k=%s&st=%s' % (siteUrl, siteKey, captchaType)
            if captchaAction:
                # score based reCAPTCHA (v3 / Enterprise) needs the action name
                fragment += '&a=' + quote(captchaAction, safe='')
            if captchaData:
                # Turnstile customer data
                fragment += '&d=' + quote(captchaData, safe='')
            # the extension's solver page texts, only the translated ones (English is built in there)
            solver_texts = {k: TEXTS[k] for k in SOLVER_TEXT_KEYS if TEXTS.get(k) and TEXTS[k] != DEFAULT_TEXTS[k]}
            if solver_texts:
                fragment += '&l=' + quote(json.dumps(solver_texts, ensure_ascii=False), safe='')
            httpd = ThreadedServer((IP, PORT), redirect_handler_factory(fragment, sessionToken, sessionPin))
        print("Http Server Serving at port", PORT)
        httpd.serve_forever()
    except Exception:
        sys.stderr.write(traceback.format_exc())
        returnCode = -1

    sys.exit(returnCode)
