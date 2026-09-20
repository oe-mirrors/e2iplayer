# -*- coding: utf-8 -*-
# Recognises WHICH bot protection / captcha system answered a request, so the
# debug log can name it (instead of a bare "403") and so pCommon can pick the
# matching MyE2i browser mode, and keeps the User-Agent that solved a browser
# check next to the cookie file. Pure functions - no Enigma2 imports, covered by
# mye2i-extension/tests/test_botprotection.py.

# how the box can deal with it
KIND_CLOUDFLARE = 'cf'         # Cloudflare challenge -> MyE2i "CF" mode (cf_clearance)
KIND_COOKIE_GATE = 'cookies'   # JS/PoW check that ends in cookies -> MyE2i "COOKIES" mode
KIND_CAPTCHA = 'captcha'       # interactive captcha, no automatic mode
KIND_BLOCK = 'block'           # hard block, nothing to solve in a browser

_BODY_LIMIT = 200000


# A Cloudflare clearance (cf_clearance) only works together with the User-Agent of
# the browser that solved the challenge. The cookie jar keeps the cookie, so the
# solving User-Agent is kept next to it (<cookie file>.ua) and used for every later
# request that goes through this jar - otherwise the next page of the same site
# arrives with another User-Agent and a browser check is asked for again.
def _ua_file(cookie_file):
    return (cookie_file + '.ua') if cookie_file else ''


def remembered_user_agent(cookie_file):
    path = _ua_file(cookie_file)
    if not path:
        return ''
    try:
        with open(path, 'rb') as handle:
            text = handle.read(1024).decode('utf-8', 'replace').strip()
    except (IOError, OSError):
        return ''
    return text if text and '\n' not in text and '\r' not in text else ''


def remember_user_agent(cookie_file, user_agent):
    path = _ua_file(cookie_file)
    if not path or not user_agent or '\n' in user_agent or '\r' in user_agent:
        return False
    try:
        with open(path, 'wb') as handle:
            handle.write(user_agent.encode('utf-8'))
        return True
    except (IOError, OSError):
        return False


class Protection(object):
    def __init__(self, name, kind, evidence):
        self.name = name
        self.kind = kind
        self.evidence = evidence

    def __repr__(self):
        return 'Protection(%r, %r, %r)' % (self.name, self.kind, self.evidence)

    def describe(self):
        text = {
            KIND_CLOUDFLARE: 'browser challenge, solvable with MyE2i',
            KIND_COOKIE_GATE: 'browser check that ends in cookies, MyE2i cookie mode',
            KIND_CAPTCHA: 'interactive captcha, no automatic mode',
            KIND_BLOCK: 'hard block, nothing to solve',
        }.get(self.kind, '')
        return '%s (%s) [%s]' % (self.name, text, self.evidence)


def _lower_headers(headers):
    out = {}
    try:
        for key, value in dict(headers or {}).items():
            out[str(key).lower()] = str(value).lower()
    except Exception:
        pass
    return out


def detect(status=0, headers=None, body='', url=''):
    """Return a Protection or None. headers: any mapping, body: str (a prefix is enough)."""
    h = _lower_headers(headers)
    try:
        b = (body or '')[:_BODY_LIMIT].lower()
    except Exception:
        b = ''
    url = (url or '').lower()
    server = h.get('server', '')
    cookies = h.get('set-cookie', '')

    def has(*needles):
        for needle in needles:
            if needle in b:
                return needle
        return ''

    # --- Cloudflare -------------------------------------------------------
    marker = has('sorry, you have been blocked', 'cf-error-details', 'error 1020')
    if marker and ('cloudflare' in server or 'cloudflare' in b):
        return Protection('Cloudflare WAF block', KIND_BLOCK, marker)
    if h.get('cf-mitigated') == 'challenge':
        return Protection('Cloudflare', KIND_CLOUDFLARE, 'cf-mitigated: challenge')
    marker = has('just a moment', 'cf-chl', '/cdn-cgi/challenge-platform', '_cf_chl_opt', 'cf_chl_')
    if marker:
        return Protection('Cloudflare', KIND_CLOUDFLARE, marker)
    if 'cloudflare' in server and status in (403, 503):
        return Protection('Cloudflare', KIND_CLOUDFLARE, 'server: cloudflare, HTTP %s' % status)

    # --- browser checks that end in cookies -------------------------------
    if 'ddos-guard' in server or has('ddos-guard', 'ddos guard'):
        return Protection('DDoS-Guard', KIND_COOKIE_GATE, 'server header' if 'ddos-guard' in server else has('ddos-guard', 'ddos guard'))
    if has('/.within.website/x/cmd/anubis') or (has('making sure you') and has('/.within.website/', 'techaro', 'protected by anubis')):
        return Protection('Anubis', KIND_COOKIE_GATE, 'anubis page')
    if 'x-vercel-mitigated' in h or has('vercel security checkpoint'):
        return Protection('Vercel Security Checkpoint', KIND_COOKIE_GATE, 'x-vercel-mitigated' if 'x-vercel-mitigated' in h else 'checkpoint page')
    if h.get('x-amzn-waf-action') in ('captcha', 'challenge') or has('awswafintegration', 'awswafcaptcha'):
        return Protection('AWS WAF', KIND_COOKIE_GATE, h.get('x-amzn-waf-action') or 'aws waf script')
    if has('sucuri_cloudproxy_js'):
        return Protection('Sucuri', KIND_COOKIE_GATE, 'sucuri_cloudproxy_js')
    if 'sucuri' in server or 'x-sucuri-id' in h or has('sucuri website firewall'):
        return Protection('Sucuri (block)', KIND_BLOCK, 'sucuri firewall page')
    if has('_incapsula_resource'):
        return Protection('Imperva / Incapsula', KIND_COOKIE_GATE, '_incapsula_resource')
    if 'incap_ses_' in cookies or 'visid_incap_' in cookies or 'incapsula' in h.get('x-cdn', '') or 'imperva' in h.get('x-cdn', '') or 'x-iinfo' in h or has('incapsula incident id'):
        return Protection('Imperva / Incapsula (block)', KIND_BLOCK, 'incapsula headers/incident page')
    if 'datadome' in server or 'x-datadome' in h or has('captcha-delivery.com', 'datadome'):
        return Protection('DataDome', KIND_COOKIE_GATE, 'datadome')
    if has('px-captcha', 'press &amp; hold', 'press & hold') or '_pxhd' in cookies or 'px-cdn.net' in b:
        return Protection('PerimeterX / HUMAN', KIND_COOKIE_GATE, 'px-captcha')

    # --- interactive captchas without an automatic mode -------------------
    marker = has('geetest', 'arkoselabs', 'funcaptcha', 'frc-captcha', 'friendlycaptcha', 'smartcaptcha.yandex', 'mcaptcha', 'keycaptcha', 'altcha')
    if marker:
        return Protection('Captcha (%s)' % marker, KIND_CAPTCHA, marker)
    if 'google.com/sorry' in url or has('/sorry/index', 'unusual traffic from your computer'):
        return Protection('Google "sorry" page', KIND_BLOCK, 'google sorry')

    # --- plain Akamai / generic blocks ------------------------------------
    if 'akamaighost' in server or has('errors.edgesuite.net'):
        return Protection('Akamai (block)', KIND_BLOCK, 'akamaighost / edgesuite')

    # a widget on a blocking page: name it, the widget modes already exist
    for needle, name in (('challenges.cloudflare.com/turnstile', 'Cloudflare Turnstile'), ('hcaptcha.com', 'hCaptcha'), ('google.com/recaptcha', 'reCAPTCHA')):
        if needle in b:
            return Protection(name, KIND_CAPTCHA, needle)
    return None
