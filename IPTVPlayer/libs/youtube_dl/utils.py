#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc


try:
    try:
        import urllib.request as compat_urllib_request
    except ImportError: # Python 2
        import urllib2 as compat_urllib_request
except Exception:
    printDBG("YT import problem 1")

try:
    try:
        import urllib.error as compat_urllib_error
    except ImportError: # Python 2
        import urllib2 as compat_urllib_error
except Exception:
    printDBG("YT import problem 2")

try:
    try:
        import urllib.parse as compat_urllib_parse
    except ImportError: # Python 2
        import urllib as compat_urllib_parse
except Exception:
    printDBG("YT import problem 3")

try:
    try:
        from urllib.parse import urlparse as compat_urllib_parse_urlparse
    except ImportError: # Python 2
        from urlparse import urlparse as compat_urllib_parse_urlparse
except Exception:
    printDBG("YT import problem 4")

try:
    try:
        import http.cookiejar as compat_cookiejar
    except ImportError: # Python 2
        import cookielib as compat_cookiejar
except Exception:
    printDBG("YT import problem 5")

try:
    try:
        import html.entities as compat_html_entities
    except ImportError: # Python 2
        import htmlentitydefs as compat_html_entities
except Exception:
    printDBG("YT import problem 6")

try:
    try:
        import http.client as compat_http_client
    except ImportError: # Python 2
        import httplib as compat_http_client
except Exception:
    printDBG("YT import problem 8")

try:
    from urllib.parse import parse_qs as compat_parse_qs
except ImportError: # Python 2
    # HACK: The following is the correct parse_qs implementation from cpython 3's stdlib.
    # Python 2's version is apparently totally broken
    def _unquote(string, encoding='utf-8', errors='replace'):
        if string == '':
            return string
        res = string.split('%')
        if len(res) == 1:
            return string
        # pct_sequence: contiguous sequence of percent-encoded bytes, decoded
        pct_sequence = b''
        string = res[0]
        for item in res[1:]:
            try:
                if not item:
                    raise ValueError
                pct_sequence += item[:2].decode('hex')
                rest = item[2:]
                if not rest:
                    # This segment was just a single percent-encoded character.
                    # May be part of a sequence of code units, so delay decoding.
                    # (Stored in pct_sequence).
                    continue
            except ValueError:
                rest = '%' + item
            # Encountered non-percent-encoded characters. Flush the current
            # pct_sequence.
            string += pct_sequence if encoding == None else pct_sequence.decode(encoding, errors)
            string += rest
            pct_sequence = b''
        if pct_sequence:
            # Flush the final pct_sequence
            string += pct_sequence if encoding == None else pct_sequence.decode(encoding, errors)
        return string

    def _parse_qsl(qs, keep_blank_values=False, strict_parsing=False,
                encoding='utf-8', errors='replace'):
        qs, _coerce_result = qs, unicode
        pairs = [s2 for s1 in qs.split('&') for s2 in s1.split(';')]
        r = []
        for name_value in pairs:
            if not name_value and not strict_parsing:
                continue
            nv = name_value.split('=', 1)
            if len(nv) != 2:
                if strict_parsing:
                    raise ValueError("bad query field: %r" % (name_value,))
                # Handle case of a control-name with no equal sign
                if keep_blank_values:
                    nv.append('')
                else:
                    continue
            if len(nv[1]) or keep_blank_values:
                name = nv[0].replace('+', ' ')
                name = _unquote(name, encoding=encoding, errors=errors)
                name = _coerce_result(name)
                value = nv[1].replace('+', ' ')
                value = _unquote(value, encoding=encoding, errors=errors)
                value = _coerce_result(value)
                r.append((name, value))
        return r

    def compat_parse_qs(qs, keep_blank_values=False, strict_parsing=False,
                encoding='utf-8', errors='replace'):
        parsed_result = {}
        pairs = _parse_qsl(qs, keep_blank_values, strict_parsing,
                        encoding=encoding, errors=errors)
        for name, value in pairs:
            if name in parsed_result:
                parsed_result[name].append(value)
            else:
                parsed_result[name] = [value]
        return parsed_result

try:
    compat_str = unicode # Python 2
except NameError:
    compat_str = str

try:
    compat_chr = unichr # Python 2
except NameError:
    compat_chr = chr


def compat_ord(c):
    if type(c) is int:
        return c
    else:
        return ord(c)


def preferredencoding():
    """Get preferred encoding."""
    pref = 'UTF-8'
    return pref


if sys.version_info < (3, 0):
    def compat_print(s):
        printDBG(s.encode(preferredencoding(), 'xmlcharrefreplace'))
else:
    def compat_print(s):
        assert type(s) == type(u'')
        printDBG(s)


def htmlentity_transform(entity):
    """Transforms an HTML entity to a character."""
    # Known non-numeric HTML entity
    try:
        if entity in compat_html_entities.name2codepoint:
            return compat_chr(compat_html_entities.name2codepoint[entity])
    except Exception:
        pass

    mobj = re.match(r'#(x?[0-9A-Fa-f]+)', entity)
    if mobj is not None:
        numstr = mobj.group(1)
        if numstr.startswith(u'x'):
            base = 16
            numstr = u'0%s' % numstr
        else:
            base = 10
        try:
            ret = compat_chr(int(numstr, base))
            return ret
        except Exception:
            printExc()
    # Unknown entity in name, return its literal representation
    return (u'&%s;' % entity)


def clean_html(html):
    """Clean an HTML snippet into a readable string"""
    if type(html) == type(u''):
        strType = 'unicode'
    elif type(html) == type(''):
        strType = 'utf-8'
        html = html.decode("utf-8", 'ignore')

    # Newline vs <br />
    html = html.replace('\n', ' ')
    html = re.sub(r'\s*<\s*br\s*/?\s*>\s*', '\n', html)
    html = re.sub(r'<\s*/\s*p\s*>\s*<\s*p[^>]*>', '\n', html)
    # Strip html tags
    html = re.sub('<.*?>', '', html)
    # Replace html entities
    html = unescapeHTML(html)

    if strType == 'utf-8':
        html = html.encode("utf-8")

    return html.strip()


def unescapeHTML(s):
    if s is None:
        return None
    assert type(s) == compat_str

    return re.sub(r'&([^;]+);', lambda m: htmlentity_transform(m.group(1)), s)


class ExtractorError(Exception):
    """Error during info extraction."""

    def __init__(self, msg, tb=None):
        """ tb, if given, is the original traceback (so that it can be printed out). """
        printDBG(msg)
        super(ExtractorError, self).__init__(msg)
        self.traceback = tb
        self.exc_info = sys.exc_info()  # preserve original exception

    def format_traceback(self):
        if self.traceback is None:
            return None
        return u''.join(traceback.format_tb(self.traceback))


def url_basename(url):
    path = compat_urllib_parse_urlparse(url).path
    return path.strip('/').split('/')[-1]
