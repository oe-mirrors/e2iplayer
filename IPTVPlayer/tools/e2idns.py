# -*- coding: utf-8 -*-
#  Author: DigiTalik - E2iPlayer on Python 2.7 and 3.x, GPLv3
#
#  e2idns.py - bypass DNS blocks of the internet provider (e.g. CUII in Germany) without changing the box DNS.
#  Python 2.7 and 3.x.
#
#  The host names of the pages E2iPlayer opens (pCommon.getPage / getURLRequestData) are resolved
#  through encrypted DNS (DNS-over-HTTPS, JSON API): Cloudflare 1.1.1.1 / 1.0.0.1, Google 8.8.8.8.
#  ONLY names registered by the plugin (register) are affected - the rest of Enigma2 keeps using the system DNS.
#  When DoH does not answer, the system answer is used. Results are cached in memory (TTL, at least 5 min).
#  Setting: config.plugins.iptvplayer.dns_doh (on / off).
#
import json
import socket
import ssl
import threading
import time

try:
    from urllib.request import Request, urlopen, HTTPRedirectHandler
    from urllib.parse import quote
except ImportError:
    from urllib2 import Request, urlopen, HTTPRedirectHandler
    from urllib import quote

_SERVERS = (
    'https://1.1.1.1/dns-query?name=%s&type=A',
    'https://1.0.0.1/dns-query?name=%s&type=A',
    'https://8.8.8.8/resolve?name=%s&type=A',
)
_orig_getaddrinfo = socket.getaddrinfo
_names = set()          # host names registered by the plugin
_cache = {}             # name -> (expiry time, [ip, ...])
_lock = threading.Lock()
_local = threading.local()


def _enabled():
    try:
        from Components.config import config
        return config.plugins.iptvplayer.dns_doh.value
    except Exception:
        return True


def _ssl_context():
    # connection to a bare IP address: these servers have the IP in the certificate, old Python 2.7 cannot check that
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        return None


def _query(name):
    for url in _SERVERS:
        try:
            req = Request(url % quote(name), headers={'Accept': 'application/dns-json', 'User-Agent': 'E2iPlayer'})
            ctx = _ssl_context()
            resp = urlopen(req, timeout=4, context=ctx) if ctx is not None else urlopen(req, timeout=4)
            data = json.loads(resp.read().decode('utf-8', 'replace'))
            if data.get('Status') != 0:
                continue
            ips, ttl = [], 3600
            for r in data.get('Answer') or []:
                if r.get('type') == 1 and r.get('data'):
                    ips.append(str(r['data']))
                    ttl = min(ttl, int(r.get('TTL') or 300))
            if ips:
                return ips, max(ttl, 300)
        except Exception:
            continue
    return None, 0


def resolve(name):
    """list of IPv4 addresses from DoH or None"""
    now = time.time()
    with _lock:
        c = _cache.get(name)
        if c and c[0] > now:
            return c[1]
    ips, ttl = _query(name)
    if ips:
        with _lock:
            _cache[name] = (now + ttl, ips)
    return ips


def _getaddrinfo(host, port, *a, **k):
    try:
        name = host.decode('ascii') if isinstance(host, bytes) else host
    except Exception:
        name = None
    if name and name.lower() in _names and not getattr(_local, 'busy', False) and _enabled():
        _local.busy = True
        try:
            ips = resolve(name.lower())
        finally:
            _local.busy = False
        if ips:
            result = []
            for ip in ips:
                try:
                    result.extend(_orig_getaddrinfo(ip, port, *a, **k))
                except Exception:
                    pass
            if result:
                return result
    return _orig_getaddrinfo(host, port, *a, **k)


def register(url):
    """register a page (URL or bare host name) whose address should be resolved through DoH"""
    try:
        h = url
        if '://' in h:
            h = h.split('://', 1)[1]
        h = h.split('/', 1)[0].split('?', 1)[0].split('@')[-1]
        if h.startswith('['):
            return
        h = h.split(':', 1)[0].strip().lower()
        if not h or h.replace('.', '').isdigit() or '.' not in h or h == 'localhost':
            return
        if h not in _names:
            with _lock:
                _names.add(h)
    except Exception:
        pass


def _host(url):
    try:
        return url.split('://', 1)[1].split('/', 1)[0].split('@')[-1].split(':', 1)[0].lower()
    except Exception:
        return ''


def install():
    if getattr(socket.getaddrinfo, '_e2idns', False):
        return
    _getaddrinfo._e2idns = True
    socket.getaddrinfo = _getaddrinfo
    # redirect from a registered page (site moved to a new domain): the new address goes through DoH as well
    try:
        orig = HTTPRedirectHandler.redirect_request
        if not getattr(orig, '_e2idns', False):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                try:
                    old = req.get_full_url() if hasattr(req, 'get_full_url') else ''
                    if _host(old) in _names:
                        register(newurl)
                except Exception:
                    pass
                return orig(self, req, fp, code, msg, headers, newurl)
            redirect_request._e2idns = True
            HTTPRedirectHandler.redirect_request = redirect_request
    except Exception:
        pass


install()
