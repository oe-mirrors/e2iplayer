# -*- coding: utf-8 -*-
LAST_MODIFIED = "21.10.2026"
# 21.10.2026 - watching page loader changed again: loader and page sit base64 with swapped halves in data-*
#   attributes; RC4 variant (S-box shifted, key schedule adds (i * 7) & 255, every byte also XORed with
#   (n + tw) & 255 and j & 31), key = 'd' + String((sA ^ sB) % m) after a two-register LCG; the hidden box's CSS
#   order replaces the z-index, the flex box now sizes by min-/max-width and min-height; new literal wrappers
#   ('J'.charCodeAt(0), 'abc'.length, Math.imul, [x].map(function(z){return z^y;})[0], window.Navigator ? 1 : 0,
#   Number.parseInt('2m', 14 + 14)). The server <li> carry data-cnv (reversed base64 "index|id"), the token "tk"
#   is an XOR array ((k + i) & 255)
# 20.10.2026 - watching page loader changed again: loader and page sit reversed base64 in data-* attributes, RC4 with
#   an extra XOR of (i + n) & 255, key from a summed list + a second LCG register; new literal wrappers
#   ((function(a){return a^x;})(y), parseInt('x', 32), ('0x2b' - 0), [0, x][+!!window.document]); "x / 6 | 0" now
#   evaluated like JS (own evaluator instead of eval). The server token "tk" is hidden the same way, the server
#   <li> carry data-id before data-index
# 18.10.2026 - watching page loader changed again: RC4 instead of XOR, the page sits base64 in a <script
#   type="application/octet-stream">; key = String(LCG(15000 rounds) of _part1 + _part2 + _part3 + a CSS z-index +
#   the height of a hidden flex-wrap box) + suffix; the literals are wrapped ({'v': x}).v, [x].pop(), parseInt('x', 16)
# 12.10.2026 - watching page loader changed again: its key variables are pushed into the array (_arrX['p'+'ush'](...))
#   and rounded with Math.round under an alias instead of Math.floor - both read now
# 11.10.2026 - the token API (cimaleech.vercel.app) answers 404: when it gives no link, MyE2i (NAV job, extension
#   v1.21) opens the watch button's ad gateway in the user's browser and sends back the tokenised watching link
#   the gateway's scripts build there (obfuscated, with decoys against scrapers - not doable without a browser);
#   the link is kept for 10 minutes per page; the watching page has a new loader (key = sum of the "_arrX" variables:
#   hex sums, floor(x / 2), a CSS z-index, a div width; _part1/2/3 are decoys now), the old one stays as fallback;
#   the own "Cima Now" server moved to <x>.worldcdn.online/e/<id> (same Playerjs file list) and is resolved by urlparser
#   (parserCIMANOWTV) like every other server - the host's own copy of that code is gone
# 08.10.2026 - server list fixed: the "ffQualities" forafile object is gone; the page's watch button now leads
#   through an ad gateway (rm.freex2line.online) to <page>/watching/?token=... (without a valid token the site
#   redirects home). The token is fetched from the cimaleech.vercel.app API (same as MOHAMED_OS's host), the
#   watching page is XOR/base64 obfuscated (key = sum of the page's JS constants) and decoded here; its server
#   list (<ul id="watch">, data-index/data-id + "var tk") is resolved through core.php?action=switch -> iframe,
#   plus the forafile links of its download box
# 03.10.2026 - revived for cimanow.cc (the site dropped its "hide_my_HTML_" obfuscation)
#   Rewrite against the plain-HTML site (same markup as before: <section aria-label="posts">,
#   <article aria-label="post">, aria-label="title|year|ribbon|tab", <ul aria-label="pagination">):
#   - categories, "Latest" (/الاحدث/) and search (/search/<q>/) with First page / Jump / Next page
#   - movies and episodes are VIDEO rows keyed on their page url (links: see 08.10.2026)
#   - series -> seasons (when the show has more than one) -> episodes (ascending)
#   - watched flag (stable series:/season:/video: page-url keys), downloaded flag, favourites,
#     name normalisation ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the site's
#     story/poster/fields; no blocking retry loops, no colour codes in titles
import ast
import math
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import strDecode
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR, StripColorCodes, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://cimanow.cc/"


# Arabic ordinals used in season labels ("الموسم الثاني")
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالث", 3), ("الرابع", 4), ("الخامس", 5), ("السادس", 6), ("السابع", 7), ("الثامن", 8),
    ("التاسع", 9), ("العاشر", 10),
]
SEASON_WORD_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجم|مترجمة|اون لاين|أون لاين|مشاهدة|فيلم|مسلسل|برنامج|كامل|كاملة|بجودة عالية|HD)(?=\s|$)")
# "<strong>..مدة العرض : </strong>" rows of the details tab -> INFO keys
INFO_FIELDS = (("language", "المحتوي"), ("duration", "مدة العرض"), ("quality", "الجودة"), ("actors", "بطولة"),
               ("director", "اخراج"), ("writer", "تأليف"))
# the watch button's ad gateway is a per-request obfuscated anti-bot page; this API returns the tokenised
# <page>/watching/?token=... url for the gateway link ("upcloud" first, "test" as the fallback endpoint)
TOKEN_APIS = ("https://cimaleech.vercel.app/api/upcloud", "https://cimaleech.vercel.app/api/test")
# MyE2i NAV job for the same gateway: the countdown page's watch button, once its scripts put the token in
WATCH_LINK_JOB = {"selector": "a#downloadbtn", "attr": "href", "pattern": r"/watching/\?token=[^&#\s]+"}
WATCH_LINK_TTL = 600  # seconds a link from MyE2i is reused for the same page
NUM_RE = re.compile(r"0x[0-9a-fA-F]+|\d+")


def _numSum(expr):
    # the obfuscator's constants are plain sums of hex/decimal literals - add them up instead of eval()
    return sum(int(n, 16) if n.lower().startswith("0x") else int(n) for n in NUM_RE.findall(expr or ""))


# bit operators (<< >> | ^ &) since the loader of 12.10.2026; Python and JS rank them alike, the operands are small ints
# number literal node: ast.Constant (py3.8+), ast.Num on py2 - ast.Num is only looked up where Constant is missing
_JS_CONST = getattr(ast, "Constant", None) or ast.Num
_JS_NUM_TYPES = (int, float, type(2 ** 64))  # type(2 ** 64): long on py2, int on py3
_JS_NUM_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, _JS_CONST, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.USub, ast.UAdd, ast.Call, ast.Name, ast.Load,
                 ast.LShift, ast.RShift, ast.BitOr, ast.BitXor, ast.BitAnd)


def _jsRound(value):
    # JS Math.round: halves go up (Python's round() rounds them to even)
    return _jsFloor(value + 0.5)


def _jsFloor(value):
    # int() for py2, where math.floor() returns a float (and float << int fails)
    return int(math.floor(value))


def _jsInt32(value):
    # JS ToInt32 of a bit operator's operand (truncated, 32 bit, signed) - "x / 6 | 0" floors a float in JS
    value = int(value) & 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def _jsMod(a, b):
    # JS %: the sign of the dividend (Python's % takes the divisor's)
    return math.fmod(a, b) if isinstance(a, float) or isinstance(b, float) else (abs(a) % abs(b)) * (1 if a >= 0 else -1)


_JS_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: float(a) / b,  # true division like JS, also on py2
    ast.Mod: _jsMod,
    ast.LShift: lambda a, b: _jsInt32(_jsInt32(a) << (_jsInt32(b) & 31)),
    ast.RShift: lambda a, b: _jsInt32(a) >> (_jsInt32(b) & 31),
    ast.BitOr: lambda a, b: _jsInt32(a) | _jsInt32(b),
    ast.BitXor: lambda a, b: _jsInt32(a) ^ _jsInt32(b),
    ast.BitAnd: lambda a, b: _jsInt32(a) & _jsInt32(b),
}
_JS_FUNCS = {"floor": _jsFloor, "jsround": _jsRound, "imul": lambda a, b: _jsInt32(_jsInt32(a) * _jsInt32(b))}


def _jsEval(node):
    # evaluates the checked tree of _jsNum (numbers, + - * / % << >> | ^ &, unary +/-, floor() / jsround())
    if isinstance(node, ast.Expression):
        return _jsEval(node.body)
    if isinstance(node, ast.BinOp):
        return _JS_BINOPS[type(node.op)](_jsEval(node.left), _jsEval(node.right))
    if isinstance(node, ast.UnaryOp):
        value = _jsEval(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.Call):
        return _JS_FUNCS[node.func.id](*[_jsEval(arg) for arg in node.args])
    return node.value if hasattr(node, "value") else node.n


def _jsNum(expr, floorName="", roundName=""):
    # a JS arithmetic expression of number literals (hex too), + - * / % and Math.floor / Math.round (under their
    # aliases) -> int; anything else (a name, a string, a call of something else) is refused - no eval() of page code
    if floorName:
        expr = re.sub(r"\b%s\s*\(" % re.escape(floorName), "floor(", expr)
    if roundName:
        expr = re.sub(r"\b%s\s*\(" % re.escape(roundName), "jsround(", expr)
    tree = ast.parse(expr.strip(), mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _JS_NUM_NODES) or (isinstance(node, ast.Name) and node.id not in _JS_FUNCS) or (isinstance(node, _JS_CONST) and not isinstance(node.value if hasattr(node, "value") else node.n, _JS_NUM_TYPES)) or \
                (isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or getattr(node, "keywords", None))):
            raise ValueError("not a plain number expression: %r" % expr)
    return int(_jsEval(tree))


def _jsParseInt(match):
    # parseInt('<digits>', base) like JS: a "0x" prefix for base 16, the digits up to the first one invalid in the base;
    # no digit at all (NaN) leaves the call in place (the expression is then refused)
    digits, base = match.group(1), _jsNum(match.group(2))
    if base == 16 and digits.lower().startswith("0x"):
        digits = digits[2:]
    valid = re.match(r"[0-9a-z]*", digits.lower()).group(0)
    for pos, char in enumerate(valid):
        if int(char, 36) >= base:
            valid = valid[:pos]
            break
    return str(int(valid, base)) if valid and 2 <= base <= 36 else match.group(0)


_JS_LIT = r"(0x[0-9a-fA-F]+|\d+)"
# loader property assignment of the hidden element's z-index: style['z-i' + 'ndex'], style['z' + 'Index'], style['zIndex']
_ZINDEX_RE = re.compile(r"""\.style\[\s*(?:['"]z-i['"]\s*\+\s*['"]ndex['"]|['"]z['"]\s*\+\s*['"]Index['"]|['"]zIndex['"])\s*\]\s*=\s*String\((.*?)\)\s*;""")
# loader of 21.10.2026: the hidden element's CSS order, set in its cssText ('...order:' + String(x) + '!important;')
_ORDER_RE = re.compile(r"""order:['"]\s*\+\s*String\((.*?)\)\s*\+\s*['"]!important""")
_JS_WRAPPED = (
    # loader of 21.10.2026: 'J'.charCodeAt(0), 'abc'.length, Math.imul(a, b), [x].map(function(z){return z^y;})[0],
    # (window.Navigator ? x : y); first, the base of a parseInt can be one of them
    (re.compile(r"""(['"])([^'"\\])\1\s*\.\s*charCodeAt\(\s*0?\s*\)"""), lambda m: str(ord(m.group(2)))),
    (re.compile(r"""(['"])([^'"\\]*)\1\s*\.\s*length\b"""), lambda m: str(len(m.group(2)))),
    (re.compile(r"\bMath\s*\.\s*imul\s*\("), lambda m: "imul("),
    (re.compile(r"\[\s*%s\s*\]\s*\.\s*map\(\s*function\s*\(\s*(\w+)\s*\)\s*\{\s*return\s+\2\s*\^\s*%s\s*;?\s*\}\s*\)\s*\[\s*0\s*\]" % (_JS_LIT, _JS_LIT)), lambda m: "(%s ^ %s)" % (m.group(1), m.group(3))),
    (re.compile(r"\(\s*window\s*\.\s*Navigator\s*\?\s*%s\s*:\s*%s\s*\)" % (_JS_LIT, _JS_LIT)), lambda m: m.group(1)),
    # parseInt('x', 16) since 18.10.2026, parseInt('ga', 32) since 20.10.2026, Number.parseInt('2m', 14 + 14) and
    # parseInt('h2', (19 ^ 0)) since 21.10.2026
    (re.compile(r"""(?:\bNumber\s*\.\s*)?parseInt\(\s*['"]([0-9a-zA-Z]+)['"]\s*,\s*(\(\s*[\d\s+\-*^|&]+\)|[\d\s+\-*^|&]+?)\s*\)"""), _jsParseInt),
    # the environment check of a literal: the browser value
    (re.compile(r"""\(\s*typeof\s+document\s*!==?\s*['"]undefined['"]\s*\?\s*%s\s*:\s*%s\s*\)""" % (_JS_LIT, _JS_LIT)), lambda m: m.group(1)),
    # loader of 20.10.2026: (function(a){return a^x;})(y), ('0x2b' - 0), [0x0, x][+!!window.document], document.nodeType (9)
    (re.compile(r"\(\s*function\s*\(\s*(\w+)\s*\)\s*\{\s*return\s+\1\s*\^\s*%s\s*;?\s*\}\s*\)\s*\(\s*%s\s*\)" % (_JS_LIT, _JS_LIT)), lambda m: "(%s ^ %s)" % (m.group(3), m.group(2))),
    (re.compile(r"""\(\s*['"]%s['"]\s*-\s*0\s*\)""" % _JS_LIT), lambda m: m.group(1)),
    (re.compile(r"\[\s*%s\s*,\s*%s\s*\]\s*\[\s*\+\s*!!\s*(?:window\.)?document\s*\]" % (_JS_LIT, _JS_LIT)), lambda m: m.group(2)),
    (re.compile(r"\bdocument\.nodeType\b"), lambda m: "9"),
)


def _jsUnwrap(expr):
    # the loader of 18.10.2026 hides its literals in ({'v': x}).v, [x].pop(), parseInt('x', 16) and a typeof check
    for regex, repl in _JS_WRAPPED:
        expr = regex.sub(repl, expr)
    return expr


def _jsVars(code):
    # {name: expression} of the "var a = x, b = y;" statements; commas / semicolons inside brackets or strings do
    # not split (a declaration with a regex literal can come out wrong - not one the decoders read)
    found = {}
    for match in re.finditer(r"\bvar\s+", code):
        pos = start = match.end()
        depth, quote, parts = 0, None, []
        while pos < len(code):
            char = code[pos]
            if quote:
                if char == "\\":
                    pos += 1
                elif char == quote:
                    quote = None
            elif char in "'\"`":
                quote = char
            elif char in "([{":
                depth += 1
            elif char in ")]}" and depth:
                depth -= 1
            elif depth == 0 and char in ",;)}":
                parts.append(code[start:pos])
                start = pos + 1
                if char != ",":
                    break
            pos += 1
        for part in parts:
            name, eq, expr = part.partition("=")
            if eq and re.match(r"^\s*[\w$]+\s*$", name) and not expr.startswith("="):
                found[name.strip()] = expr.strip()
    return found


def _jsSplit(expr):
    # the top-level comma separated items of "a, f(b, c), [d, e]"
    items, depth, start = [], 0, 0
    for pos, char in enumerate(expr):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            items.append(expr[start:pos])
            start = pos + 1
    items.append(expr[start:])
    return [item.strip() for item in items if item.strip()]


def _flexStyledHeight(code):
    # loader of 20.10.2026: <x-fx style='display:flex; flex-wrap:wrap; width:490px'> with <x-i style='order:n;
    # height; width or flex-basis; display:block|none'> children - laid out in "order" (CSS order, stable), hidden
    # ones take no space; every line is as high as its highest child
    def px(value):
        found = re.match(r"\s*(\d+)", value or "")
        return int(found.group(1)) if found else 0

    box, items = None, []
    for tag, style in re.findall(r"""<([\w-]+)\s+style=\\?['"]([^'"\\]*)""", code):
        props = {}
        for decl in style.split(";"):
            key, _sep, value = decl.partition(":")
            props[key.strip().lower()] = value.replace("!important", "").strip()
        if box is None:
            if props.get("display") == "flex":
                box = props
                end = code.find("</%s>" % tag)
                code = code[:end] if end > 0 else code
            continue
        if props.get("display") != "none":
            items.append(props)
    if box is None or not items:
        return 0
    limit = px(box.get("width")) if box.get("flex-wrap", "").startswith("wrap") else float("inf")
    total = left = line = 0
    for props in sorted(items, key=lambda p: int(p.get("order") or 0)):
        # since 21.10.2026 also min-/max-width (no width: the min-width), min-/max-height and padding (border-box)
        width = px(props.get("flex-basis")) or px(props.get("width"))
        if props.get("max-width"):
            width = min(width, px(props.get("max-width")))
        width = max(width, px(props.get("min-width")))
        height = px(props.get("height"))
        if props.get("max-height"):
            height = min(height, px(props.get("max-height")))
        height = max(height, px(props.get("min-height")), px(props.get("padding-top")) + px(props.get("padding-bottom")))
        if left and left + width > limit:
            total, left, line = total + line, 0, 0
        left += width
        line = max(line, height)
    return total + line


def _flexHeight(code):
    # offsetHeight of the loader's hidden flex-wrap box: its children (fixed width/height, no gaps) fill lines of the
    # box width, every line is as high as its highest child
    box = re.search(r"display:\s*flex;(.*?)width:\s*(\d+)px", code)
    if not box:
        return 0
    limit = int(box.group(2)) if "wrap" in box.group(1) else float("inf")
    total = left = line = 0
    for w, h in re.findall(r"width:\s*(\d+)px;\s*height:\s*(\d+)px", code[box.end():]):
        w, h = int(w), int(h)
        if left and left + w > limit:
            total, left, line = total + line, 0, 0
        left += w
        line = max(line, h)
    return total + line


def _rc4(key, data, tweak=None):
    # tweak (loader of 20.10.2026): every byte is also XORed with (i + tweak) & 255
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + ord(key[i % len(key)])) & 255
        s[i], s[j] = s[j], s[i]
    out = bytearray(len(data))
    i = j = 0
    for n, c in enumerate(bytearray(data)):
        i = (i + 1) & 255
        j = (j + s[i]) & 255
        s[i], s[j] = s[j], s[i]
        out[n] = c ^ s[(s[i] + s[j]) & 255] ^ (((i + tweak) & 255) if tweak is not None else 0)
    return bytes(out)


def _rc4Mixed(key, data, sboxAdd, keyMul, tweak, jMask):
    # loader of 21.10.2026: S[i] = (i + sboxAdd) & 255, the key schedule also adds (i * keyMul) & 255, every byte
    # is also XORed with (n + tweak) & 255 (n = byte position) and with j & jMask
    s = [(i + sboxAdd) & 255 for i in range(256)]
    j = 0
    for i in range(256):
        j = (j + s[i] + ord(key[i % len(key)]) + ((i * keyMul) & 255)) & 255
        s[i], s[j] = s[j], s[i]
    out = bytearray(len(data))
    i = j = 0
    for n, c in enumerate(bytearray(data)):
        i = (i + 1) & 255
        j = (j + s[i]) & 255
        s[i], s[j] = s[j], s[i]
        out[n] = c ^ s[(s[i] + s[j]) & 255] ^ ((n + tweak) & 255) ^ (j & jMask)
    return bytes(out)


def _unrotate(text):
    # loader of 21.10.2026: base64 split in halves, swapped (s.substring(h) + s.substring(0, h), h = (len + 1) >> 1)
    half = (len(text) + 1) >> 1
    return text[half:] + text[:half]


def _restoreCnv(html):
    # since 21.10.2026 the server <li> carry data-cnv = reversed base64 of "index|id" instead of data-index/data-id
    def repl(match):
        try:
            index, serverId = strDecode(b64Decode(match.group(2)[::-1], binary=True), "ignore").split("|")[:2]
        except Exception:
            return match.group(0)
        return 'data-index="%s" data-id="%s"' % (index, serverId)
    return re.sub(r"""data-cnv=(["'])([A-Za-z0-9+/=]+)\1""", repl, html)


def _seasonNum(text):
    m = SEASON_WORD_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


class CimaNow(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cimanow", "cookie": "cimanow.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/cimanow.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchLinks = {}  # gateway link -> (time, tokenised watching link from MyE2i)

        def cat(slug):
            return self.getFullUrl("/category/%s/" % slug)

        self.MOVIES_TAB = [
            {"title": _("Foreign movies"), "url": cat("افلام-اجنبية")},
            {"title": _("Arabic Movies"), "url": cat("افلام-عربية")},
            {"title": _("Turkish Movies"), "url": cat("افلام-تركية")},
            {"title": _("Indian Movies"), "url": cat("افلام-هندية")},
            {"title": _("Korean movies"), "url": cat("افلام-كورية")},
            {"title": _("Anime Movies"), "url": cat("افلام-انيميشن")},
            {"title": _("Documentary Movies"), "url": cat("افلام-وثائقية")},
            {"title": _("Short Movies"), "url": cat("افلام-قصيرة")},
            {"title": _("Plays"), "url": cat("مسرحيات")},
        ]
        self.SERIES_TAB = [
            {"title": _("Foreign series"), "url": cat("مسلسلات-اجنبية")},
            {"title": _("Arabic Series"), "url": cat("مسلسلات-عربية")},
            {"title": _("Turkish Series"), "url": cat("مسلسلات-تركية")},
            {"title": _("Korean TV series"), "url": cat("مسلسلات-كورية")},
            {"title": _("Anime Series"), "url": cat("مسلسلات-انيميشن")},
            {"title": _("TV Shows"), "url": cat("البرامج-التلفزيونية")},
            {"title": "%s 2026" % _("Ramadan"), "url": cat("رمضان-2026")},
            {"title": "%s 2025" % _("Ramadan"), "url": cat("رمضان-2025")},
        ]
        self.MENU = [
            {"category": "cn_tab", "title": _("Movies"), "tab": "movies"},
            {"category": "cn_tab", "title": _("Series"), "tab": "series"},
            {"category": "list_items", "title": _("Latest"), "url": self.getFullUrl("/الاحدث/")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("cimanow")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def getFullUrl(self, url, currUrl=None):
        # menu urls are written in Arabic - one ASCII (percent-encoded) form for everything
        return self._quote(CBaseHostClass.getFullUrl(self, url, currUrl))

    @staticmethod
    def _quote(url):
        try:
            return urllib_quote(urllib_unquote(url.replace("&amp;", "&").replace("&#038;", "&")), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _canonUrl(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return self._quote(url)

    def _path(self, url):
        # domain independent identity of a page
        url = urllib_unquote(self._canonUrl(url))
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def _kind(self, url):
        path = self._path(url)
        if "/selary/" in path:
            return "series"
        if re.search(r"-ح\d+(?:-|$)|الحلقة-\d+", path):
            return "episode"
        return "movie"

    def _episodeNumbers(self, url, fallbackSeason=0):
        path = self._path(url)
        season = self.cm.ph.getSearchGroups(path, r"-ج(\d+)(?:-|$)")[0]
        episode = self.cm.ph.getSearchGroups(path, r"-ح(\d+)(?:-|$)")[0] or self.cm.ph.getSearchGroups(path, r"الحلقة-(\d+)")[0]
        return int(season) if season else (fallbackSeason or 1), episode

    @staticmethod
    def _clean(text):
        text = JUNK_RE.sub(" ", text or "")
        return re.sub(r"\s+", " ", text).strip(" -:|")

    def _icon(self, url):
        url = (url or "").replace("?quality=10", "").strip()
        return self.getFullIconUrl(self._quote(url)) if url else ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("cn_video", "cn_series", "cn_season"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"cn_video": "video", "cn_series": "series", "cn_season": "season"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listTab(self, cItem):
        tab = self.MOVIES_TAB if cItem.get("tab") == "movies" else self.SERIES_TAB
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params.update({"good_for_fav": True, "category": "list_items"})
            params.pop("tab", None)
            self.addDir(params)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem["url"])
        url = baseUrl if page <= 1 else "%spage/%d/" % (baseUrl, page)
        printDBG("CimaNow.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        posts = self.cm.ph.getDataBeetwenMarkers(data, '<section aria-label="posts">', "</section>", False)[1]
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(posts, '<article aria-label="post">', "</article>"):
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            if not href:
                continue
            url = self._canonUrl(href)
            if url in seen:
                continue
            seen.add(url)
            rawTitle = self.cm.ph.getSearchGroups(item, r'(?s)<li aria-label="title">(.*?)</li>')[0]
            genres = self.cleanHtmlStr(self.cm.ph.getSearchGroups(rawTitle, r"(?s)<em>(.*?)</em>")[0])
            title = self.cleanHtmlStr(re.sub(r"(?s)<em>.*?</em>", "", rawTitle))
            if not title:
                continue
            year = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<li aria-label="year">([^<]*)<')[0])
            ribbons = [self.cleanHtmlStr(r) for r in re.findall(r'<li aria-label="ribbon">([^<]*)<', item)]
            tabs = [self.cleanHtmlStr(t) for t in re.findall(r'<li aria-label="tab">([^<]*)<', item)]
            seasonLabel = ""
            for t in tabs:
                if _seasonNum(t):
                    seasonLabel = t
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            fields = ((_("Quality"), " ".join(r for r in ribbons if r), "yellow"), (_("Year"), year, "cyan"),
                      (_("Section"), ", ".join(t for t in tabs if t != seasonLabel), "green"), (_("Genres"), genres, "magenta"))
            desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self._icon(icon), "desc": desc}
            kind = self._kind(url)
            if kind == "series":
                season = self._episodeNumbers(url, _seasonNum(seasonLabel))[0]
                params.update({"category": "cn_series", "title": ("%s - %s" % (title, seasonLabel)) if seasonLabel else title,
                               "s_title": title, "s_season": season, "meta_type": "tv", "meta_title": title, "meta_year": year})
                self.addDir(params)
            elif kind == "episode":
                season, episode = self._episodeNumbers(url, _seasonNum(seasonLabel))
                if normalize and episode:
                    dispTitle = "%s - %s" % (title, formatSxxExx(season, episode))
                else:
                    dispTitle = " - ".join(x for x in (title, seasonLabel, ("%s %s" % (_("Episode"), episode)) if episode else "") if x)
                params.update({"category": "cn_video", "title": dispTitle, "s_title": title, "s_season": season, "s_episode": episode,
                               "meta_type": "tv", "meta_title": title, "meta_year": year})
                self.addVideo(params)
            else:
                dispTitle = title
                if normalize:
                    dispTitle = self._clean(title) or title
                    if year and year not in dispTitle:
                        dispTitle = "%s (%s)" % (dispTitle, year)
                params.update({"category": "cn_video", "title": dispTitle, "meta_type": "movie", "meta_title": self._clean(title) or title, "meta_year": year})
                self.addVideo(params)

        # pager: <li class="active"> = this page, the highest number = last page
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'aria-label="pagination"', "</ul>", False)[1]
        lastPage = max([int(n) for n in re.findall(r'<a[^>]+href="[^"]+"[^>]*>\s*(\d+)\s*</a>', pager)] + [page])
        hasNext = bool(seen) and lastPage > page
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage, baseUrl + "page/{page}/")

    def listSeries(self, cItem):
        # the series row is one season page; more seasons -> season folders, else the episodes
        printDBG("CimaNow.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<section aria-label="seasons">', "</section>", False)[1]
        seasons = []
        for href, label in re.findall(r'(?s)<a href="([^"]+)"[^>]*>(.*?)</a>', block):
            url = self._canonUrl(href)
            label = self.cleanHtmlStr(label)
            num = self._episodeNumbers(url, _seasonNum(label))[0]
            if url and url not in [s[1] for s in seasons]:
                seasons.append((num, url, label))
        if len(seasons) <= 1:
            self.listEpisodes(cItem, data)
            return
        seasons.sort(key=lambda s: s[0])
        for num, url, label in seasons:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "cn_season", "title": label, "url": url, "s_season": num})
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("CimaNow.listEpisodes [%s]" % cItem.get("url", ""))
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="eps">', "</ul>", False)[1]
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        episodes = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>"):
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not href:
                continue
            url = self._canonUrl(href)
            if url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'aria-label="([^"]+)"')[0])
            season, episode = self._episodeNumbers(url, cItem.get("s_season", 0) or _seasonNum(label))
            num = self.cm.ph.getSearchGroups(item, r"<em>\s*(\d+)\s*</em>")[0]
            if num:
                episode = str(int(num))
            imgs = re.findall(r'<img[^>]+src="([^"]+)"', item)
            if normalize and episode:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = label or ("%s - %s %s" % (show, _("Episode"), episode))
            episodes.append({"name": "category", "good_for_fav": True, "category": "cn_video", "title": title, "url": url,
                             "icon": self._icon(imgs[-1]) if imgs else cItem.get("icon", ""), "desc": cItem.get("desc", ""),
                             "s_title": show, "s_season": season, "s_episode": episode,
                             "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
        episodes.reverse()  # the site lists the newest first
        for params in episodes:
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CimaNow.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        base = self.getFullUrl("/search/%s/" % urllib_quote(searchPattern.strip(), safe=""))
        cItem.update({"category": "list_items", "url": base, "base_url": base, "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        details = self.cm.ph.getDataBeetwenMarkers(data, 'id="details">', "</ul>", False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(details, r"(?s)عن المحتوى[^<]*</strong>\s*<p>(.*?)</p>")[0])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<li aria-label="story">(.*?)</li>')[0])
        story = re.sub(r"\s*مشاهدة وتحميل.*$", "", story).strip()
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        info = {}
        for key, word in INFO_FIELDS:
            val = self.cm.ph.getSearchGroups(details, r"(?s)%s\s*:\s*</strong>(.*?)</li>" % word)[0]
            val = re.sub(r"\s*،\s*", ", ", self.cleanHtmlStr(val)).strip(" ,")
            if val:
                info[key] = val
        return story, self._icon(poster) if poster else "", info

    def getLinksForVideo(self, cItem):
        printDBG("CimaNow.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._canonUrl(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        shineUrl = self.cm.ph.getSearchGroups(data, r'<a[^>]+class="shine"[^>]+href="([^"]+)"')[0]
        watchUrl = self._watchingUrl(shineUrl)
        if not watchUrl:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=pageUrl)
        sts, data = self.getPage(watchUrl, params)
        if not sts:
            return []
        if 'id="watch"' not in data:
            data = self._decodeWatching(data)
        if 'id="watch"' not in data:
            # the token is no longer accepted (the site sent the start page): ask again next time
            self.watchLinks.pop(self._gatewayKey(shineUrl), None)
        urltab = []
        token = self.cm.ph.getSearchGroups(data, r"""var\s+tk\s*=\s*['"]([^'"]+)['"]""")[0] or self._hiddenToken(data)
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="watch">', "</ul>", False)[1]
        coreUrl = self.getFullUrl("/wp-content/themes/Cima%20Now%20New/core.php")
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=watchUrl)
        seen = set()
        servers = []
        for attrs, label in re.findall(r"(?s)<li([^>]*\sdata-index=[^>]*)>(.*?)</li>", block):
            # data-index / data-id in any order (data-id first since 20.10.2026)
            index = self.cm.ph.getSearchGroups(attrs, r'data-index="([^"]+)"')[0]
            serverId = self.cm.ph.getSearchGroups(attrs, r'data-id="([^"]+)"')[0]
            if index and serverId:
                servers.append((index, serverId, label))
        for index, serverId, label in servers:
            sts, frame = self.getPage("%s?%s" % (coreUrl, urllib_urlencode([("action", "switch"), ("index", index), ("id", serverId), ("token", token)])), params)
            url = self.cm.ph.getSearchGroups(frame, r"""<iframe[^>]+src=['"]([^'"]+)['"]""", ignoreCase=True)[0] if sts else ""
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            name = "%s - %s" % (self.cleanHtmlStr(label), self.up.getDomain(url, onlyDomain=True))
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        # download box: forafile per quality (the site's player adds them as the "Forafile" server)
        for code, rest in re.findall(r'forafile\.[a-z]+/([a-z0-9]{12})([^"\']*)', data):
            quality = self.cm.ph.getSearchGroups(rest, r"(\d{3,4}p)")[0]
            url = "https://forafile.com/embed-%s.html" % code
            if url in seen:
                continue
            seen.add(url)
            urltab.append({"name": ("Forafile %s" % quality).strip(), "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    @staticmethod
    def _hiddenToken(data):
        # since 20.10.2026: var tk = window[String.fromCharCode(97,116,111,98)](("..." + "...").split("").reverse().join(""))
        # since 21.10.2026: var tk = (function(a,k){... a[i] ^ ((k + i) & 255) ...})([11, 11, ...], 62)
        found = re.search(r"var\s+tk\s*=\s*\(\s*function\s*\(\s*\w+\s*,\s*(\w+)\s*\)\s*\{[^}]*?\^\s*\(\s*\(\s*\1\s*\+\s*\w+\s*\)\s*&\s*255\s*\)[^}]*\}\s*\)"
                          r"\s*\(\s*\[([\d\s,]+)\]\s*,\s*(\d+)\s*\)", data)
        if found:
            start = int(found.group(3))
            return "".join(chr(int(n) ^ ((start + i) & 255)) for i, n in enumerate(found.group(2).split(",") if found.group(2).strip() else [])).strip()
        found = re.search(r"""var\s+tk\s*=\s*window\[[^\]]+\]\(\s*\(?\s*((?:['"][A-Za-z0-9+/=]*['"]\s*\+?\s*)+)\)?\s*\.split\(""", data)
        if not found:
            return ""
        try:
            return strDecode(b64Decode("".join(re.findall(r"""['"]([A-Za-z0-9+/=]*)['"]""", found.group(1)))[::-1], binary=True), "ignore").strip()
        except Exception:
            printExc()
            return ""

    @staticmethod
    def _gatewayKey(shineUrl):
        return (shineUrl or "").replace("&amp;", "&").strip()

    def _watchingUrl(self, shineUrl):
        # direct <page>/watching/?token= link, or the ad gateway link -> tokenised url from the API, else from the
        # user's browser through MyE2i
        shineUrl = self._gatewayKey(shineUrl)
        if not shineUrl:
            return ""
        if "/watching/" in shineUrl and "token=" in shineUrl:
            return self._canonUrl(shineUrl)
        cached = self.watchLinks.get(shineUrl)
        if cached and time.time() - cached[0] < WATCH_LINK_TTL:
            return cached[1]
        url = self._tokenApiUrl(shineUrl) or self._myE2iWatchingUrl(shineUrl)
        if url:
            self.watchLinks[shineUrl] = (time.time(), url)
        return url

    def _myE2iWatchingUrl(self, shineUrl):
        # the gateway's countdown page gets its tokenised watch link only from its own (obfuscated) scripts:
        # MyE2i's NAV job opens the gateway in the user's browser, follows its redirects and sends that link back
        try:
            from Plugins.Extensions.IPTVPlayer.libs.recaptcha_mye2i import UnCaptchaReCaptcha
            answer = UnCaptchaReCaptcha().processCaptcha(time.time(), shineUrl, captchaType="NAV", captchaData=json_dumps(WATCH_LINK_JOB))
            url = (json_loads(b64Decode(answer)) or {}).get("url", "") if answer else ""
        except Exception:
            printExc()
            url = ""
        # the browser's absolute, already encoded address as it is - re-quoting could turn a %2B of the token into "+"
        if url.startswith("http") and "/watching/" in url and "token=" in url:
            return url
        printDBG("CimaNow._myE2iWatchingUrl no link for [%s]" % shineUrl)
        return ""

    def _tokenApiUrl(self, shineUrl):
        params = {"header": {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL, "Accept": "application/json"}}
        for api in TOKEN_APIS:
            sts, data = self.cm.getPage(api, params, {"id": shineUrl})
            if not sts:
                continue
            try:
                url = (json_loads(data) or {}).get("downloadLink") or ""
            except Exception:
                # no JSON (the API answers 404 since 11.10.2026): MyE2i takes over, no traceback in the log
                url = ""
            if "/watching/" in url:
                return self._canonUrl(url)
        printDBG("CimaNow._tokenApiUrl no token for [%s]" % shineUrl)
        return ""

    def _decodeWatching(self, data):
        # the current loader first, then the ones of 20.10., 18.10., 11.10. and 08.10.2026
        decoded = self._decodeWatchingRot(data) or self._decodeWatchingRev(data) or self._decodeWatchingRc4(data) or self._decodeWatchingSum(data)
        return decoded if decoded else self._decodeWatchingParts(data)

    def _decodeWatchingRot(self, data):
        # loader of 21.10.2026: loader and page sit in data-* attributes as base64 with swapped halves (_unrotate).
        # RC4 variant (_rc4Mixed) with key = prefix + String((sA ^ sB) % m): sA = one expression (wrapped literals,
        # "(x / 5) | 0", an environment check = 1, a CSS order, the height of a hidden flex box), then for st = 1..r:
        # sA = (sA * a + c + (st & x)) % m; sB = ((sB ^ sA) + ((st * y) & z)) % m. .substring(n) cuts the start off,
        # the server <li> carry data-cnv (_restoreCnv). "" when the page is not of this kind
        try:
            code = ""
            for attrs, body in re.findall(r"(?s)<script([^>]*)>(.*?)</script>", data):
                attr = re.search(r"""getAttribute\(\s*['"]([\w-]+)['"]\s*\)\s*,\s*\w+\s*=\s*\(\s*\w+\.length\s*\+\s*1\s*\)\s*>>\s*1""", body)
                value = re.search(r"""\s%s=["']([A-Za-z0-9+/=]{200,})["']""" % re.escape(attr.group(1)), attrs) if attr else None
                if value:
                    code = _jsUnwrap(b64Decode(_unrotate(value.group(1))))
                    break
            if not code:
                return ""
            payload = None
            for name in re.findall(r"""getAttribute\(\s*['"](data-[\w-]+)['"]\s*\)""", code):
                payload = re.search(r"""<script[^>]+\s%s=["']([A-Za-z0-9+/=]{100,})["']""" % re.escape(name), data)
                if payload:
                    break
            loop = re.search(r"for\s*\(\s*var\s+(\w+)\s*=\s*1\s*;\s*\1\s*<=\s*(\w+)\s*;\s*\1\s*\+\+\s*\)\s*\{"
                             r"\s*(\w+)\s*=\s*\(\s*\(\s*\3\s*\*\s*(\w+)\s*\)\s*\+\s*(\w+)\s*\+\s*\(\s*\1\s*&\s*(\d+)\s*\)\s*\)\s*%\s*(\d+)\s*;"
                             r"\s*(\w+)\s*=\s*\(\s*\(\s*\8\s*\^\s*\3\s*\)\s*\+\s*\(\s*\(\s*\1\s*\*\s*(\d+)\s*\)\s*&\s*(\d+)\s*\)\s*\)\s*%\s*(\d+)\s*;", code)
            if not payload or not loop:
                return ""
            kv = re.search(r"var\s+(\w+)\s*=\s*\(\s*%s\s*\^\s*%s\s*\)\s*%%\s*(\d+)" % (loop.group(3), loop.group(8)), code)
            sbox = re.search(r"\w+\[(\w+)\]\s*=\s*\(\s*\1\s*\+\s*(\w+)\s*\)\s*&\s*255", code)
            mixer = re.search(r"\^\s*\(\s*\(\s*\w+\s*\+\s*(\w+)\s*\)\s*&\s*255\s*\)\s*\^\s*\(\s*\w+\s*&\s*(\d+)\s*\)", code)
            if not kv or not sbox or not mixer:
                return ""
            keyMul = re.search(r"charCodeAt\(\s*(\w+)\s*%\s*\w+\.length\s*\)\s*\+\s*\(\s*\(\s*\1\s*\*\s*(\d+)\s*\)\s*&\s*255\s*\)", code)
            defs = _jsVars(code)
            order = _ORDER_RE.search(code)
            envNames = [n for n, e in defs.items() if "?" in e and "_h" in e and "documentElement" in e]

            def value(expr, depth=0):
                expr = expr.strip()
                if "getComputedStyle" in expr:
                    return _jsNum(order.group(1)) if order else 0
                if "offsetHeight" in expr:
                    return _flexStyledHeight(code)
                for name in set(re.findall(r"\b[A-Za-z_$][\w$]*\b", expr)):
                    if name in envNames:
                        expr = re.sub(r"\b%s\b" % re.escape(name), "1", expr)
                    elif name in defs and name not in _JS_FUNCS and depth < 5:
                        expr = re.sub(r"\b%s\b" % re.escape(name), "(%d)" % value(defs[name], depth + 1), expr)
                return _jsNum(expr)

            sA, sB = value(defs[loop.group(3)]), value(defs[loop.group(8)])
            rounds, mul, inc = value(defs[loop.group(2)]), value(defs[loop.group(4)]), value(defs[loop.group(5)])
            maskA, mod, mulB, maskB, modB = (int(loop.group(n)) for n in (6, 7, 9, 10, 11))
            for st in range(1, rounds + 1):
                # float like JS: sA * a can pass 2^53
                sA = int(math.fmod(float(sA) * mul + inc + (st & maskA), mod))
                sB = _jsMod((_jsInt32(sB) ^ _jsInt32(sA)) + ((st * mulB) & maskB), modB)
            kvValue = str(_jsMod(_jsInt32(sA) ^ _jsInt32(sB), int(kv.group(2))))
            prefix = re.search(r"""=\s*['"]([^'"]*)['"]\s*\+\s*String\(\s*%s\s*\)""" % re.escape(kv.group(1)), code)
            suffix = re.search(r"""=\s*String\(\s*%s\s*\)\s*\+\s*['"]([^'"]*)['"]""" % re.escape(kv.group(1)), code)
            key = (prefix.group(1) if prefix else "") + kvValue + (suffix.group(1) if suffix else "")
            raw = b64Decode(_unrotate(payload.group(1)), binary=True)
            out = strDecode(_rc4Mixed(key, raw, value(sbox.group(2)), int(keyMul.group(2)) if keyMul else 0, value(mixer.group(1)), int(mixer.group(2))), "ignore")
            cut = re.search(r"(\w+)\s*=\s*\1\.substring\(([^;]+?)\)\s*;", code)
            if cut:
                out = out[_jsNum(cut.group(2)):]
            if 'id="watch"' not in out:
                printDBG("CimaNow._decodeWatchingRot: key %s gave no server list" % key)
                return ""
            return _restoreCnv(out)
        except Exception:
            printExc()
        return ""

    def _decodeWatchingRev(self, data):
        # loader of 20.10.2026: the loader script sits reversed base64 in a data-* attribute of its own <script>
        # (getAttribute(..).split('').reverse().join('') -> atob -> new Function), the page reversed base64 in a
        # data-* attribute of a <script type="text/plain" id="p_...">. RC4 (every byte also XORed with (i + tw) & 255)
        # with key = String((sA + sB) % m) + suffix: sA = sum of the "_acc" list (wrapped literals, a CSS z-index,
        # the height of a hidden flex box, an environment check = 1), then r rounds of sA = (sA * a + c) % m;
        # sB = ((sB ^ sA) + (r & 255)) % m. .slice(n) cuts the start off. "" when the page is not of this kind
        try:
            code = ""
            for attrs, body in re.findall(r"(?s)<script([^>]*)>(.*?)</script>", data):
                attr = re.search(r"""getAttribute\(\s*['"]([\w-]+)['"]\s*\)\s*\.split\(\s*['"]{2}\s*\)\s*\.reverse\(\s*\)""", body)
                value = re.search(r"""\s%s=["']([A-Za-z0-9+/=]{200,})["']""" % re.escape(attr.group(1)), attrs) if attr else None
                if value:
                    code = _jsUnwrap(b64Decode(value.group(1)[::-1]))
                    break
            if not code:
                return ""
            payload = None
            for name in re.findall(r"""getAttribute\(\s*['"](data-[\w-]+)['"]\s*\)""", code):
                payload = re.search(r"""<script[^>]+\s%s=["']([A-Za-z0-9+/=]{100,})["']""" % re.escape(name), data)
                if payload:
                    break
            accSum = re.search(r"(\w+)\s*\+=\s*(\w+)\s*\[\s*\w+\s*\]", code)
            loop = re.search(r"while\s*\(\s*(\w+)\s*>\s*0\s*\)\s*\{\s*(\w+)\s*=\s*\(\s*\(\s*\2\s*\*\s*(\d+)\s*\)\s*\+\s*(\d+)\s*\)\s*%\s*(\d+)\s*;"
                             r"\s*(\w+)\s*=\s*\(\s*\(\s*\6\s*\^\s*\2\s*\)\s*\+\s*\(\s*\1\s*&\s*(\d+)\s*\)\s*\)\s*%\s*(\d+)\s*;", code)
            if not payload or not accSum or not loop:
                return ""
            defs = _jsVars(code)
            zindex = _ZINDEX_RE.search(code)
            envNames = [n for n, e in defs.items() if "?" in e and "_h" in e and "documentElement" in e]

            def value(expr, depth=0):
                expr = expr.strip()
                if "getComputedStyle" in expr:
                    return _jsNum(zindex.group(1)) if zindex else 0
                if "offsetHeight" in expr:
                    return _flexStyledHeight(code) or _flexHeight(code)
                for name in set(re.findall(r"\b[A-Za-z_$][\w$]*\b", expr)):
                    if name in envNames:
                        expr = re.sub(r"\b%s\b" % re.escape(name), "1", expr)
                    elif name in defs and depth < 5:
                        expr = re.sub(r"\b%s\b" % re.escape(name), "(%d)" % value(defs[name], depth + 1), expr)
                return _jsNum(expr)

            accExpr = defs.get(accSum.group(2), "").strip()
            if not (accExpr.startswith("[") and accExpr.endswith("]")):
                return ""
            sA = value(defs.get(accSum.group(1), "0")) + sum(value(item) for item in _jsSplit(accExpr[1:-1]))
            sB, rounds = value(defs[loop.group(6)]), value(defs[loop.group(1)])
            mul, inc, mod, mask, modB = (int(loop.group(n)) for n in (3, 4, 5, 7, 8))
            while rounds > 0:
                sA = (sA * mul + inc) % mod
                sB = ((sB ^ sA) + (rounds & mask)) % modB
                rounds -= 1
            kv = re.search(r"var\s+(\w+)\s*=\s*\(\s*%s\s*\+\s*%s\s*\)\s*%%\s*(\d+)" % (loop.group(2), loop.group(6)), code)
            if not kv:
                return ""
            suffix = re.search(r"""=\s*String\(\s*%s\s*\)\s*\+\s*['"]([^'"]*)['"]""" % re.escape(kv.group(1)), code)
            key = str((sA + sB) % int(kv.group(2))) + (suffix.group(1) if suffix else "")
            tweak = re.search(r"\^\s*\(\s*\(\s*\w+\s*\+\s*(\w+)\s*\)\s*&\s*255\s*\)", code)
            tweak = value(defs[tweak.group(1)]) if tweak and tweak.group(1) in defs else None
            out = strDecode(_rc4(key, b64Decode(payload.group(1)[::-1], binary=True), tweak), "ignore")
            cut = re.search(r"\.slice\(([^;]+?)\)\s*;", code)
            if cut:
                out = out[_jsNum(cut.group(1)):]
            if 'id="watch"' not in out:
                printDBG("CimaNow._decodeWatchingRev: key %s gave no server list" % key)
                return ""
            return out
        except Exception:
            printExc()
        return ""

    def _decodeWatchingRc4(self, data):
        # loader of 18.10.2026 (atob('...') script): RC4 of the base64 text of a <script type="application/
        # octet-stream" id="p_...">; key = String(kv after N rounds of kv = (kv * a + c) % m) + suffix, kv = sum of
        # the variables of "var kv = _part1 + _part2 + _part3 + _tVal + _flexVal;" (wrapped literals, Math.floor
        # under an alias, a CSS z-index, the height of a hidden flex box, an environment check = 1 in a browser);
        # .substring(n) cuts the start off. "" when the page is not of this kind
        try:
            loader = re.search(r"""\]\(\s*['"]([A-Za-z0-9+/=]{200,})['"]\s*\)""", data)
            if not loader:
                return ""
            code = b64Decode(loader.group(1))
            lcg = re.search(r"var\s+(\w+)\s*=\s*([\w$\s+]+);\s*for\s*\(\s*var\s+\w+\s*=\s*0\s*;\s*\w+\s*<\s*(\d+)\s*;[^)]*\)\s*\{\s*\1\s*=\s*\(\s*\(\s*\1\s*\*\s*(\d+)\s*\)\s*\+\s*(\d+)\s*\)\s*%\s*(\d+)", code)
            payload = None
            for elemId in re.findall(r"""getElementById\(\s*['"]([^'"]+)['"]\s*\)""", code):
                payload = re.search(r"""(?s)<script[^>]+id=["']%s["'][^>]*>\s*([A-Za-z0-9+/=\s]{100,}?)\s*</script>""" % re.escape(elemId), data)
                if payload:
                    break
            if not lcg or not payload:
                return ""
            floor = re.search(r"""var\s+(\w+)\s*=\s*\w+\[\s*['"]f['"]\s*\+\s*['"]loor['"]\s*\]""", code) or re.search(r"var\s+(\w+)\s*=\s*Math\.floor\b", code)
            floorName = floor.group(1) if floor else ""
            defs = dict(re.findall(r"var\s+(\w+)\s*=\s*([^;]+);", code))
            zindex = _ZINDEX_RE.search(code)
            envNames = [n for n, e in defs.items() if "?" in e and "_h" in e and "documentElement" in e]

            def value(name):
                expr = defs[name].strip()
                if "getComputedStyle" in expr:
                    return _jsNum(_jsUnwrap(zindex.group(1)), floorName) if zindex else 0
                if "offsetHeight" in expr:
                    return _flexHeight(code)
                expr = _jsUnwrap(expr)
                for env in envNames:
                    expr = re.sub(r"\b%s\b" % re.escape(env), "1", expr)
                return _jsNum(expr, floorName)

            kv = sum(value(v.strip()) for v in lcg.group(2).split("+") if v.strip())
            mul, inc, mod = int(lcg.group(4)), int(lcg.group(5)), int(lcg.group(6))
            for _ in range(int(lcg.group(3))):
                kv = (kv * mul + inc) % mod
            suffix = re.search(r"""=\s*String\(\s*%s\s*\)\s*\+\s*['"]([^'"]*)['"]""" % re.escape(lcg.group(1)), code)
            key = str(kv) + (suffix.group(1) if suffix else "")
            out = strDecode(_rc4(key, b64Decode(re.sub(r"\s+", "", payload.group(1)), binary=True)), "ignore")
            for arg in re.findall(r"\.substring\(([^;]+?)\)\s*;", code):
                try:
                    out = out[_jsNum(_jsUnwrap(arg), floorName):]
                    break
                except (ValueError, SyntaxError):
                    continue
            if 'id="watch"' not in out:
                printDBG("CimaNow._decodeWatchingRc4: key %s gave no server list" % key)
                return ""
            return out
        except Exception:
            printExc()
        return ""

    def _decodeWatchingSum(self, data):
        # loader of 11.10.2026: window["<arr>"] = new (window["Arr"+"ay"])("b64", ...); an atob('...') loader XORs
        # it with String(sum of the variables of its "_arrX = [a, b, c, ...]") + String.fromCharCode(n) and cuts
        # .substring(n) off the start. The variables are hex sums, Math.floor(x / 2), a CSS z-index and a div width
        # set from String(...) expressions, an environment check (1 in a browser); _part1/2/3 are decoys now.
        # "" when the page is not of this kind
        try:
            arr = re.search(r"""window\[['"](\w+)['"]\]\s*=\s*new\s*\(\s*window\[['"]Arr['"]\s*\+\s*['"]ay['"]\]\s*\)\s*\((.*?)\)\s*;""", data, re.S)
            loader = re.search(r"""\]\(\s*['"]([A-Za-z0-9+/=]{200,})['"]\s*\)""", data)
            if not arr or not loader:
                return ""
            code = b64Decode(loader.group(1))
            floor = re.search(r"""var\s+(\w+)\s*=\s*\w+\[\s*['"]f['"]\s*\+\s*['"]loor['"]\s*\]""", code) or re.search(r"var\s+(\w+)\s*=\s*Math\.floor\b", code)
            floorName = floor.group(1) if floor else ""
            rounder = re.search(r"""var\s+(\w+)\s*=\s*\w+\[\s*['"]r['"]\s*\+\s*['"]ound['"]\s*\]""", code) or re.search(r"var\s+(\w+)\s*=\s*Math\.round\b", code)
            roundName = rounder.group(1) if rounder else ""
            defs = dict(re.findall(r"var\s+(\w+)\s*=\s*([^;]+);", code))
            zindex = _ZINDEX_RE.search(code)
            width = re.search(r"""idth:['"]\s*\+\s*String\((.*?)\)\s*\+\s*['"]px""", code)
            # the key variables: "_arrX = [a, b, ...]; for" (11.10.) or "_arrX['p'+'ush'](a, b, ...); for" (12.10.)
            arrVars = re.search(r"=\s*\[([\w\s,$]+)\]\s*;\s*for", code) or \
                re.search(r"""\[\s*['"]p['"]\s*\+\s*['"]ush['"]\s*\]\s*\(([\w\s,$]+)\)\s*;\s*for""", code) or \
                re.search(r"\.push\(([\w\s,$]+)\)\s*;\s*for", code)
            if not arrVars:
                printDBG("CimaNow._decodeWatchingSum: no key variables")
                return ""

            def value(name, depth=0):
                expr = defs[name].strip()
                if "getComputedStyle" in expr and zindex:
                    return _jsNum(zindex.group(1), floorName, roundName)
                if "offsetWidth" in expr and width:
                    return _jsNum(width.group(1), floorName, roundName)
                if "?" in expr:  # the environment check: 1 in a browser
                    return 1
                if depth < 5:
                    for other in set(re.findall(r"\b[A-Za-z_$][\w$]*\b", expr)):
                        if other not in (floorName, roundName) and other in defs and other != name:
                            expr = re.sub(r"\b%s\b" % re.escape(other), str(value(other, depth + 1)), expr)
                return _jsNum(expr, floorName, roundName)

            key = str(sum(value(v.strip()) for v in arrVars.group(1).split(",") if v.strip()))
            key += "".join(chr(int(n)) for n in re.findall(r"toString\(\)\s*\+\s*String\.fromCharCode\((\d+)\)", code)[:1])
            raw = bytearray(b64Decode("".join(re.findall(r"""['"]([A-Za-z0-9+/=]+)['"]""", arr.group(2))), binary=True))
            out = strDecode(bytes(bytearray(b ^ ord(key[i % len(key)]) for i, b in enumerate(raw))), "ignore")
            # the first .substring() whose argument is a plain number (other code may use substring too)
            for arg in re.findall(r"\.substring\(([^;]+?)\)\s*;", code):
                try:
                    out = out[_jsNum(arg, floorName, roundName):]
                    break
                except (ValueError, SyntaxError):
                    continue
            if 'id="watch"' not in out:
                printDBG("CimaNow._decodeWatchingSum: key %s gave no server list" % key)
                return ""
            return out
        except Exception:
            printExc()
        return ""

    def _decodeWatchingParts(self, data):
        # loader of 08.10.2026: window['<arr>'] = new Array("b64", ...) XORed with String(_part1 + _part2 + _part3 +
        # _tVal + _dVal) + suffix; the constants sit in an atob("...") loader script
        code = data
        for b64 in re.findall(r"""\(\s*['"]([A-Za-z0-9+/=]{200,})['"]\s*\)""", data):
            try:
                code += "\n" + b64Decode(b64)
            except Exception:
                continue
        try:
            m1 = re.search(r"_part1\s*=\s*\w+\(\s*\((.*?)\)\s*/\s*(\d+)\s*\)", code)
            m2 = re.search(r"_part2\s*=\s*\((.*?)\)\s*\*", code)
            m3 = re.search(r"_part3\s*=\s*\((.*?)\)\s*;", code)
            mt = re.search(r"ndex'\]\s*=\s*String\(\(?([^)]+)\)?\)", code)
            md = re.search(r"idth:'\s*\+\s*String\(([^)]+)\)", code)
            mk = re.search(r"=\s*String\(\s*_part1[^)]*\)\s*\+\s*'([^']*)'", code)
            ma = re.search(r"""=\s*window\[['"](\w+)['"]\]\.join\(""", code)
            if not (m1 and m2 and m3 and ma):
                printDBG("CimaNow._decodeWatching: decoder constants not found")
                return data
            total = _numSum(m1.group(1)) // (int(m1.group(2)) or 1) + _numSum(m2.group(1)) + _numSum(m3.group(1))
            total += _numSum(mt.group(1)) if mt else 0
            total += _numSum(md.group(1)) if md else 0
            key = str(total) + (mk.group(1) if mk else "")
            arr = re.search(r"""window\[['"]%s['"]\]\s*=\s*(?:\[|new\s*\(?\s*window\[[^\]]*\]\s*\)?\s*\()(.*?)[\])]\s*;""" % ma.group(1), code, re.S)
            if not arr:
                return data
            raw = bytearray(b64Decode("".join(re.findall(r"""['"]([A-Za-z0-9+/=]+)['"]""", arr.group(1))), binary=True))
            out = bytearray(b ^ ord(key[i % len(key)]) for i, b in enumerate(raw))
            return strDecode(bytes(out), "ignore")
        except Exception:
            printExc()
        return data

    def getVideoLinks(self, videoUrl):
        printDBG("CimaNow.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        # every server through urlparser - also the site's own "Cima Now" player (cimanowtv.com / worldcdn.online:
        # parserCIMANOWTV)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("CimaNow.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or StripColorCodes(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("CimaNow.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "cn_tab":
            self.listTab(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "cn_series":
            self.listSeries(self.currItem)
        elif category == "cn_season":
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, CimaNow(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cimanow")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("cn_video", "cn_series", "cn_season")
