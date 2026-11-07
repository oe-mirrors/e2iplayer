# -*- coding: utf-8 -*-
#  Author: DigiTalik - E2iPlayer on Python 2.7 and 3.x, GPLv3
#
#  e2idns.py - bypass DNS blocks of the internet provider (e.g. CUII in Germany) without changing the box DNS.
#  Python 2.7 and 3.x.
#
#  The host names of the pages E2iPlayer opens (pCommon.getPage / getURLRequestData) are resolved
#  through encrypted DNS (DNS-over-HTTPS, JSON API): Cloudflare, Google. The DoH servers themselves are
#  reached through the system DNS and their certificates are verified.
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
    'https://cloudflare-dns.com/dns-query?name=%s&type=A',
    'https://dns.google/resolve?name=%s&type=A',
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


def _open(url):
    req = Request(url, headers={'Accept': 'application/dns-json', 'User-Agent': 'E2iPlayer'})
    try:
        ctx = ssl.create_default_context()           # certificate and host name are verified
    except AttributeError:                           # very old Python 2.7 without SSL contexts
        return urlopen(req, timeout=4)
    return urlopen(req, timeout=4, context=ctx)


def _parse(data):
    """(ips, ttl) from a DoH JSON answer"""
    ips, ttl = [], 3600
    if data.get('Status') != 0:
        return ips, ttl
    for r in data.get('Answer') or []:
        if r.get('type') == 1 and r.get('data'):
            ips.append(str(r['data']))
            ttl = min(ttl, int(r.get('TTL') or 300))
    return ips, max(ttl, 300)


def _query(name):
    for url in _SERVERS:
        try:
            ips, ttl = _parse(json.loads(_open(url % quote(name)).read().decode('utf-8', 'replace')))
        except Exception:
            continue
        if ips:
            return ips, ttl
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


def _registered(host):
    """lower-case host name when it was registered by the plugin, else None"""
    try:
        name = (host.decode('ascii') if isinstance(host, bytes) else host).lower()
    except Exception:
        return None
    return name if name in _names else None


def _resolve_once(name):
    """resolve() but never recursively (the DoH request itself also calls getaddrinfo)"""
    if getattr(_local, 'busy', False) or not _enabled():
        return None
    _local.busy = True
    try:
        return resolve(name)
    finally:
        _local.busy = False


def _getaddrinfo(host, port, *a, **k):
    name = _registered(host)
    ips = _resolve_once(name) if name else None
    result = []
    for ip in ips or ():
        try:
            result.extend(_orig_getaddrinfo(ip, port, *a, **k))
        except socket.error:
            pass
    return result or _orig_getaddrinfo(host, port, *a, **k)


def register(url):
    """register a page (URL or bare host name) whose address should be resolved through DoH"""
    try:
        h = url.split('://', 1)[1] if '://' in url else url
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
