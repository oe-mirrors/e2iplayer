# -*- coding: utf-8 -*-
#  Author: DigiTalik - E2iPlayer on Python 2.7 and 3.x (DreamOS, OpenPLi 8, OpenATV 6), GPLv3
"""
py2shim - lets the Python 3 code of E2iPlayer run on Python 2.7 (DreamOS DM900 / DM920, OpenPLi 8, OpenATV 6).
Imported at the very beginning of the IPTVPlayer package ONLY on Python 2: provides the Python 3 modules
(urllib.parse, urllib.request, urllib.error, http.client, http.cookiejar, html.parser, queue, configparser,
concurrent.futures) from their Python 2 counterparts and smooths over differences of older Enigma2 images.
On Python 3 it does nothing.
"""
import sys

LOG = '/tmp/iptvplayer_py27.log'

if sys.version_info[0] == 2:
    import types

    def _module(name, parent=None, attr=None):
        m = sys.modules.get(name)
        if m is None:
            m = types.ModuleType(name)
            sys.modules[name] = m
        if parent is not None and attr:
            setattr(parent, attr, m)
        return m

    def _copy(dst, *sources):
        for src in sources:
            for n in dir(src):
                if not n.startswith('__') and not hasattr(dst, n):
                    setattr(dst, n, getattr(src, n))

    def _log(text):
        try:
            with open(LOG, 'a') as f:
                f.write(text + '\n')
        except Exception:
            pass

    import urllib as _urllib
    import urllib2 as _urllib2
    import urlparse as _urlparse
    import httplib as _httplib
    import cookielib as _cookielib

    # urllib.parse
    _p = _module('urllib.parse', _urllib, 'parse')
    _copy(_p, _urlparse)
    for _n in ('quote', 'quote_plus', 'unquote', 'unquote_plus', 'urlencode', 'splittype', 'splithost', 'splitport', 'splitquery'):
        if hasattr(_urllib, _n):
            setattr(_p, _n, getattr(_urllib, _n))
    if not hasattr(_p, 'unquote_to_bytes'):
        _p.unquote_to_bytes = _urllib.unquote

    # urllib.request / urllib.error / urllib.response
    _r = _module('urllib.request', _urllib, 'request')
    _copy(_r, _urllib2)
    for _n in ('urlretrieve', 'urlcleanup', 'pathname2url', 'url2pathname', 'getproxies', 'proxy_bypass'):
        if hasattr(_urllib, _n):
            setattr(_r, _n, getattr(_urllib, _n))
    _e = _module('urllib.error', _urllib, 'error')
    for _n in ('URLError', 'HTTPError', 'ContentTooShortError'):
        setattr(_e, _n, getattr(_urllib2, _n, getattr(_urllib, _n, Exception)))
    _rs = _module('urllib.response', _urllib, 'response')
    _rs.addinfourl = _urllib.addinfourl

    # http (package), http.client, http.cookiejar, http.cookies, http.server
    _h = _module('http')
    _h.__path__ = []
    _hc = _module('http.client', _h, 'client')
    _copy(_hc, _httplib)
    _hj = _module('http.cookiejar', _h, 'cookiejar')
    _copy(_hj, _cookielib)
    try:
        import Cookie as _Cookie
        _copy(_module('http.cookies', _h, 'cookies'), _Cookie)
    except ImportError:
        pass
    try:
        import BaseHTTPServer as _BHS
        _hs = _module('http.server', _h, 'server')
        _copy(_hs, _BHS)
        import SimpleHTTPServer as _SHS
        _copy(_hs, _SHS)
        import SocketServer as _SS
        if not hasattr(_hs, 'ThreadingHTTPServer'):          # Python 3.7+
            class ThreadingHTTPServer(_SS.ThreadingMixIn, _BHS.HTTPServer):
                daemon_threads = True
            _hs.ThreadingHTTPServer = ThreadingHTTPServer
    except ImportError:
        pass

    # html.parser, html (escape / unescape), html.entities
    try:
        import HTMLParser as _HP
        _ht = sys.modules.get('html')
        if _ht is None:
            _ht = _module('html')
            _ht.__path__ = []
        _hp = _module('html.parser', _ht, 'parser')
        _copy(_hp, _HP)
        if not hasattr(_ht, 'unescape'):
            _ht.unescape = _HP.HTMLParser().unescape
        if not hasattr(_ht, 'escape'):
            import cgi as _cgi
            _ht.escape = lambda s, quote=True: _cgi.escape(s, quote)
        try:
            import htmlentitydefs as _hed
            _copy(_module('html.entities', _ht, 'entities'), _hed)
        except ImportError:
            pass
    except ImportError:
        pass

    # queue, configparser, builtins, socketserver, _thread, reprlib
    for _a, _b in (('queue', 'Queue'), ('configparser', 'ConfigParser'), ('builtins', '__builtin__'), ('socketserver', 'SocketServer'),
                   ('_thread', 'thread'), ('reprlib', 'repr')):
        if _a not in sys.modules:
            try:
                sys.modules[_a] = __import__(_b)
            except ImportError:
                pass

    # Enigma2 on DreamOS / older images: constants of newer images (openATV)
    try:
        import enigma as _en
        for _n, _v in (('BT_SCALE', 0), ('BT_KEEP_ASPECT_RATIO', 0), ('BT_HALIGN_CENTER', 0), ('BT_VALIGN_CENTER', 0)):
            if not hasattr(_en, _n):
                setattr(_en, _n, _v)
    except Exception:
        pass

    # skin: values and attributes an older image does not understand
    #  - "12.5,7.0" / "1.2e-16": DreamOS reads positions and sizes as integers only
    #  - "e" / "e-16": up to the edge of the parent window (newer Enigma2) - computed from the parent size
    #  - unknown attribute (e.g. borderColor on eLabel in DreamOS): skipped instead of breaking the whole screen
    try:
        import skin as _skin
        if not getattr(_skin.applySingleAttribute, '_e2i', False):
            _orig = _skin.applySingleAttribute

            import re as _re
            _NUMBER = _re.compile(r'-?\d*\.\d+(?:[eE][-+]?\d+)?|-?\d+[eE][-+]?\d+')
            _NUM_ATTRS = ('position', 'size', 'font', 'itemHeight', 'scrollbarWidth', 'borderWidth',
                          'offset', 'valign', 'halign', 'spacing', 'itemWidth')

            def _to_int(v):
                return _NUMBER.sub(lambda m: str(int(round(float(m.group(0))))), v)

            def _edge(guiObject, desktop, attrib, value):
                """'e' / 'e-16' -> pixels, relative to the parent window (for size: from the widget position)"""
                try:
                    par = guiObject.parent() if hasattr(guiObject, 'parent') else None
                    ps = par.size() if par is not None else desktop.size()
                    dim = (ps.width(), ps.height())
                    if attrib == 'size':
                        try:
                            pos = guiObject.position()
                            dim = (dim[0] - pos.x(), dim[1] - pos.y())
                        except Exception:
                            pass
                except Exception:
                    return None
                out = []
                for i, x in enumerate(value.split(',')[:2]):
                    x = x.strip()
                    m = _re.match(r'^e\s*(?:-\s*(\d+(?:\.\d+)?))?$', x)
                    out.append(str(max(0, dim[i] - int(round(float(m.group(1) or 0))))) if m else x)
                return ','.join(out)

            def _int_or_keyword(x):
                x = x.strip()
                try:
                    return str(int(round(float(x))))
                except ValueError:
                    return x if x in ('center', 'fill') else '0'

            def applySingleAttribute(guiObject, desktop, attrib, value, *a, **k):
                if isinstance(value, basestring) and attrib in _NUM_ATTRS and _NUMBER.search(value):
                    value = _to_int(value)
                try:
                    return _orig(guiObject, desktop, attrib, value, *a, **k)
                except ValueError as e:
                    _log('skin: numbers %s=%r (%s)' % (attrib, value, e))
                    if isinstance(value, basestring) and attrib in ('position', 'size'):
                        for v in (_edge(guiObject, desktop, attrib, value), ','.join(_int_or_keyword(x) for x in value.split(','))):
                            if v:
                                try:
                                    return _orig(guiObject, desktop, attrib, v, *a, **k)
                                except Exception:
                                    pass
                except AttributeError as e:
                    _log('skin: skipped %s=%s (%s)' % (attrib, value, e))
            applySingleAttribute._e2i = True
            _skin.applySingleAttribute = applySingleAttribute
    except Exception:
        pass

    # Components.MultiContent: newer Enigma2 has extra keyword arguments (flags=BT_SCALE, cornerRadius ...) - drop unknown ones
    try:
        import inspect as _inspect
        import Components.MultiContent as _MC
        for _n in dir(_MC):
            _fn = getattr(_MC, _n)
            if not _n.startswith('MultiContentEntry') or not callable(_fn) or getattr(_fn, '_e2i', False):
                continue
            try:
                _spec = _inspect.getargspec(_fn)
            except TypeError:
                continue
            if _spec.keywords:
                continue                                         # accepts **kwargs - nothing to do

            def _wrap_mc(_fn=_fn, _known=set(_spec.args)):
                def f(*a, **k):
                    return _fn(*a, **dict((x, y) for x, y in k.items() if x in _known))
                f._e2i = True
                f.__name__ = _fn.__name__
                return f
            setattr(_MC, _n, _wrap_mc())
    except Exception:
        pass

    # Enigma2 (SWIG) on Python 2 accepts only str: unicode arguments -> UTF-8
    # (eLabel.setText, eWindow.setTitle, eConsoleAppContainer.execute, LoadPixmap, eServiceReference ...)
    try:
        import enigma as _en2

        def _b(x):
            return x.encode('utf-8') if isinstance(x, unicode) else x

        def _wrap_fn(fn):
            if getattr(fn, '_e2i', False):
                return fn

            def f(*a, **k):
                return fn(*[_b(x) for x in a], **dict((x, _b(y)) for x, y in k.items()))
            f._e2i = True
            return f

        def _wrap_method(o):
            def f(self, *a, **k):
                return o(self, *[_b(x) for x in a], **k)
            f._e2i = True
            f.__name__ = getattr(o, '__name__', 'f')
            return f

        for _n in ('loadPNG', 'loadJPG', 'loadSVG', 'loadPic', 'loadSizedImage', 'loadImage'):
            if hasattr(_en2, _n):
                setattr(_en2, _n, _wrap_fn(getattr(_en2, _n)))
        import Tools.LoadPixmap as _LP
        for _n in ('loadSizedImage', 'loadPNG', 'loadJPG', 'loadSVG'):
            if hasattr(_LP, _n):
                setattr(_LP, _n, _wrap_fn(getattr(_LP, _n)))
        _LP.LoadPixmap = _wrap_fn(_LP.LoadPixmap)
        try:
            import Tools.Directories as _TD
            for _n in ('resolveFilename', 'fileExists', 'pathExists'):
                if hasattr(_TD, _n):
                    setattr(_TD, _n, _wrap_fn(getattr(_TD, _n)))
        except Exception:
            pass
        # every Enigma2 class (eLabel, eWindow, eListbox, eConsoleAppContainer, gFont, gPixmap ...)
        _skip = set(['__getattr__', '__setattr__', '__repr__', '__del__', '__eq__', '__ne__', '__hash__', '__swig_destroy__'])
        for _cn in dir(_en2):
            _cls = getattr(_en2, _cn, None)
            if not isinstance(_cls, (type, types.ClassType)) or not _cn.startswith(('e', 'g')):
                continue
            for _mn, _mv in list(vars(_cls).items()):
                if _mn in _skip or (_mn.startswith('__') and _mn != '__init__') or not callable(_mv) or getattr(_mv, '_e2i', False):
                    continue
                if isinstance(_mv, (staticmethod, classmethod)):
                    continue
                try:
                    setattr(_cls, _mn, _wrap_method(_mv))
                except (TypeError, AttributeError):
                    pass
    except Exception:
        pass

    # StaticText.boolean (newer Enigma2; skin: ConditionalShowHide on key_menu) - true when there is text
    try:
        from Components.Sources.StaticText import StaticText as _ST
        if not hasattr(_ST, 'boolean'):
            _ST.boolean = property(lambda self: bool(self.getText()))
    except Exception:
        pass

    # email.utils.parsedate_to_datetime (Python 3.3+)
    try:
        import email.utils as _eu
        if not hasattr(_eu, 'parsedate_to_datetime'):
            import datetime as _dt

            def parsedate_to_datetime(data):
                t = _eu.parsedate_tz(data)
                if t is None:
                    raise ValueError('invalid date: %r' % (data,))
                return _dt.datetime.utcfromtimestamp(_eu.mktime_tz(t))
            _eu.parsedate_to_datetime = parsedate_to_datetime
    except ImportError:
        pass

    # concurrent.futures - a simple thread pool (Python 2 has none; the "futures" backport is often missing)
    try:
        import concurrent.futures  # noqa: F401 (backport installed)
    except ImportError:
        import threading

        class Future(object):
            def __init__(self):
                self._event = threading.Event()
                self._result = None
                self._error = None

            def result(self, timeout=None):
                self._event.wait(timeout)
                if self._error is not None:
                    raise self._error
                return self._result

            def done(self):
                return self._event.is_set()

            def exception(self, timeout=None):
                self._event.wait(timeout)
                return self._error

        class ThreadPoolExecutor(object):
            def __init__(self, max_workers=4, *a, **k):
                import Queue
                self._queue = Queue.Queue()
                self._workers = []
                for _ in range(max(1, int(max_workers or 4))):
                    t = threading.Thread(target=self._work)
                    t.daemon = True
                    t.start()
                    self._workers.append(t)

            def _work(self):
                while True:
                    job = self._queue.get()
                    if job is None:
                        return
                    f, fn, a, k = job
                    try:
                        f._result = fn(*a, **k)
                    except BaseException as e:
                        f._error = e
                    f._event.set()

            def submit(self, fn, *a, **k):
                f = Future()
                self._queue.put((f, fn, a, k))
                return f

            def map(self, fn, *iterables):
                return [f.result() for f in [self.submit(fn, *x) for x in zip(*iterables)]]

            def shutdown(self, wait=True):
                for _ in self._workers:
                    self._queue.put(None)
                if wait:
                    for t in self._workers:
                        t.join()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                self.shutdown(True)

        def as_completed(fs, timeout=None):
            for f in list(fs):
                f.result(timeout)
                yield f

        _c = _module('concurrent')
        _c.__path__ = []
        _cf = _module('concurrent.futures', _c, 'futures')
        _cf.ThreadPoolExecutor = ThreadPoolExecutor
        _cf.Future = Future
        _cf.as_completed = as_completed
        _cf.TimeoutError = Exception
