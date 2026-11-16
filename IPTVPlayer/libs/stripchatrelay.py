# -*- coding: utf-8 -*-
# Stripchat above 480p. The API hands out the 480p master only; the edge (edge-hls.doppiocdn.*) serves the whole ladder
# (source 720x960 ... 240p) but hides the segment names ("MOUFLON"): the media playlist lists a placeholder
# (".../media.mp4") after every "#EXT-X-MOUFLON:URI:<segment url with an encrypted name>" line, and without the query
# "psch=v2&pkey=<key id>" the master points to an advert loop. The name is
#   base64( reversed(token) ) xor sha256(key of the key id)
# with fixed keys of the web player (a streamlink plugin that handles the same scheme keeps this table, too). The segments
# themselves need no header. exteplayer3 / ffmpeg know no MOUFLON, so localUrls() serves the live playlist of every
# rendition on 127.0.0.1 with the real segment urls (rewritten at every request) and the player loads the segments from
# the CDN directly. Anything unexpected (unknown key id, playlist not answering, first segment not readable) gives
# an empty list: the caller keeps the 480p master.
# The local url names the stream and the rendition (/sc/<stream id>/<rendition>/index.m3u8), so a url the relay does not
# know (yet, or any more: a download started later, the GUI restarted) is looked up again on the edge. Python 2 too
# (hostxxx is copied onto Python 2 images).
import base64
import hashlib
import re
import ssl
import sys
import threading
import time

if sys.version_info[0] == 2:
    # (stdlib modules: the "future" backport of http.server some images ship lacks ThreadingHTTPServer)
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from SocketServer import ThreadingMixIn
    from urllib2 import Request, urlopen
else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from socketserver import ThreadingMixIn
    from urllib.request import Request, urlopen

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc

KEYS = {
    "Zokee2OhPh9kugh4": "Quean4cai9boJa5a",
    "Zeechoej4aleeshi": "ubahjae7goPoodi6",
    "Ook7quaiNgiyuhai": "EQueeGh2kaewa3ch",
    "Fq6m2TO2ZeBkRPm9": "xb6di1NF9EFXHUwb",
    "GrRncsoByZmsiT6L": "NigHYyOD9l4rvAEb",
    "1Dzcc6OjP73LKbtI": "Y64UVwX5RrIWnOLp",
    "N2oLovTIXb0o28Uj": "ABE7Sj8jh3oPM2ae",
    "NTK9aqcLmNFMWrpQ": "tOcYOap4Ty1l9Jzb",
    "7uUnbD0jMCB9GH32": "lzCQ6QBTnLpB0zMF",
    "Ohi7eTRBpkAuML0l": "kExe29N2sLFrHGqu",
    "OLzu7QlySkG2fVRn": "CsovScFH9VirSJ4Z",
}
DEFAULT_PKEY = "Fq6m2TO2ZeBkRPm9"
EDGES = ("edge-hls.doppiocdn.com", "edge-hls.doppiocdn.net", "edge-hls.doppiocdn.org")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Origin": "https://stripchat.com", "Referer": "https://stripchat.com/", "Accept": "*/*"}
# a fixed port keeps the local urls valid over a GUI restart (another free one when it is taken)
PORT = 42199
# renditions kept; the least recently requested one goes first (a playing stream or a download asks every few seconds)
MAX_ENTRIES = 200

_lock = threading.Lock()
_server = None
_entries = {}


class _Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _open(url, headers=None, timeout=15):
    # like pCommon on the box: no certificate check (many images ship no CA bundle)
    ctx = ssl._create_unverified_context()  # NOSONAR - same as the plugin's other requests, receivers lack CA certificates
    return urlopen(Request(url, headers=headers or HEADERS), timeout=timeout, context=ctx)


def _text(url):
    return _open(url).read().decode("utf-8", "ignore")


def decodeName(token, key):
    # the plain segment name of an encrypted one ("" when it does not decode)
    try:
        padded = token[::-1]
        data = bytearray(base64.b64decode((padded + "=" * ((4 - len(padded) % 4) % 4)).encode("ascii")))
        digest = bytearray(hashlib.sha256(key.encode("utf-8")).digest())
        return bytearray(b ^ digest[i % 32] for i, b in enumerate(data)).decode("utf-8")
    except Exception:
        return ""


def keyId(text):
    # the key id a media playlist names ("" when none)
    match = re.search(r"#EXT-X-MOUFLON:PSCH:v2:(\S+)", text)
    return match.group(1) if match else ""


def decryptPlaylist(text):
    # the media playlist with the real segment urls instead of the placeholders, "" when a segment name does not decode
    key = KEYS.get(keyId(text))
    if not key:
        return ""
    out, skip = [], False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXT-X-MOUFLON:URI:"):
            match = re.match(r"^(https?://[^/]+/[^/]+/\d+/\d+_(?:[0-9A-Za-z]+_)*?\d+_)(.+)(_\d+\.\w+)$", line[len("#EXT-X-MOUFLON:URI:"):])
            name = decodeName(match.group(2), key) if match else ""
            if not name or not re.match(r"^[A-Za-z0-9]+$", name):
                return ""
            out.append(match.group(1) + name + match.group(3))
            skip = True  # the placeholder line behind it
            continue
        if line.startswith("#EXT-X-MOUFLON"):
            continue
        if skip and line and not line.startswith("#"):
            skip = False
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def _variantList(master):
    # [(width, height, bandwidth, name, playlist url)] of a master playlist, tallest first
    found, lines = [], master.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF") and idx + 1 < len(lines):
            size = re.search(r"RESOLUTION=(\d+)x(\d+)", line)
            bandwidth = re.search(r"BANDWIDTH=(\d+)", line)
            name = re.search(r'NAME="([^"]+)"', line)
            found.append((int(size.group(1)) if size else 0, int(size.group(2)) if size else 0, int(bandwidth.group(1)) if bandwidth else 0, name.group(1) if name else "", lines[idx + 1].strip()))
    found.sort(key=lambda v: (v[1], v[2], v[0]), reverse=True)
    return found


def _probe(url):
    # the first bytes of an fMP4 file must be readable
    headers = dict(HEADERS)
    headers["Range"] = "bytes=0-15"
    return len(_open(url, headers).read(16)) >= 8


def _upstream(streamId):
    # [(width, height, bandwidth, name, absolute url of the media playlist with the "psch=v2&pkey=" query)] tallest first, []
    # when no edge answers
    for edge in EDGES:
        try:
            auto = "https://%s/hls/%s/master/%s_auto.m3u8" % (edge, streamId, streamId)
            pkey = keyId(_text(auto)) or DEFAULT_PKEY
            master = _text("%s?psch=v2&pkey=%s" % (auto, pkey))
            variants = [(w, h, bw, name, url if url.startswith("http") else "https://%s%s" % (edge, url)) for w, h, bw, name, url in _variantList(master)]
            if variants:
                return variants
        except Exception:
            printDBG("stripchat: edge [%s] does not answer" % edge)
    return []


def _renditionKey(name, height):
    # the rendition part of the local url
    return re.sub(r"[^0-9A-Za-z]+", "", "%s" % (name or "")) or "%dp" % height


def _store(streamId, variants):
    # remembers the renditions of a stream; the least recently used ones beyond MAX_ENTRIES go
    now = time.time()
    with _lock:
        for _width, height, _bandwidth, name, upstream in variants:
            _entries[(streamId, _renditionKey(name, height))] = [upstream, now]
        if len(_entries) > MAX_ENTRIES:
            for key in sorted(_entries, key=lambda k: _entries[k][1])[:len(_entries) - MAX_ENTRIES]:
                _entries.pop(key, None)


def _lookup(streamId, rendition, refresh=False):
    # the media playlist url of a local one; asks the edge again when it is not known (or refresh)
    with _lock:
        entry = None if refresh else _entries.get((streamId, rendition))
        if entry:
            entry[1] = time.time()
            return entry[0]
    _store(streamId, _upstream(streamId))
    with _lock:
        entry = _entries.get((streamId, rendition))
        return entry[0] if entry else ""


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *args):
        pass

    def do_GET(self):
        parts = self.path.split("?", 1)[0].split("/")
        # ["", "sc", <stream id>, <rendition>, "index.m3u8"]
        if len(parts) != 5 or parts[1] != "sc" or not parts[2].isdigit():
            self.send_error(404)
            return
        try:
            body = ""
            for refresh in (False, True):
                upstream = _lookup(parts[2], parts[3], refresh)
                if not upstream:
                    break
                try:
                    body = decryptPlaylist(_text(upstream))
                except Exception:
                    printDBG("stripchat: playlist [%s] does not answer" % upstream)
                if "#EXTINF" in body:
                    break
            if not upstream:
                printDBG("stripchat: stream %s/%s not on the edge (any more)" % (parts[2], parts[3]))
                self.send_error(404)
                return
            if "#EXTINF" not in body:
                self.send_error(502)
                return
            body = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.apple.mpegurl")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
        except (IOError, OSError):
            printDBG("stripchat: request closed by the player")
        except Exception:
            printExc()
            try:
                self.send_error(502)
            except Exception:
                pass


def _startServer():
    global _server
    with _lock:
        if _server is None:
            try:
                server = _Server(("127.0.0.1", PORT), _Handler)
            except Exception:
                server = _Server(("127.0.0.1", 0), _Handler)
            thread = threading.Thread(target=server.serve_forever, name="E2iStripchat")
            thread.daemon = True
            thread.start()
            _server = server
            printDBG("stripchat: local relay on 127.0.0.1:%d" % server.server_address[1])
        return _server


def _usable(upstream):
    # the playlist decrypts, lists segments and the first bytes of its last segment and of its init part are readable
    text = _text(upstream)
    body = decryptPlaylist(text)
    if "#EXTINF" not in body:
        printDBG("stripchat: playlist not usable (key id [%s])" % keyId(text))
        return False
    segment = [line for line in body.splitlines() if line.startswith("http") and "_init_" not in line][-1:]
    init = re.search(r'#EXT-X-MAP:URI="([^"]+)"', body)
    for link in segment + ([init.group(1)] if init else []):
        if not _probe(link):
            printDBG("stripchat: segment not readable")
            return False
    return True


def localUrls(streamId, accept=None):
    # [(label, http://127.0.0.1:<port>/sc/<stream id>/<rendition>/index.m3u8, height)] of the renditions of a stream, tallest
    # first; the first one has been checked to play, [] when none can be played this way. accept(width, height) leaves out
    # the renditions the caller does not want (UHD playback off); when it leaves out all of them the smallest one stays
    result = []
    try:
        streamId = "%s" % streamId
        variants = _upstream(streamId)
        wanted = [v for v in variants if accept is None or accept(v[0], v[1])]
        if variants and not wanted:
            wanted = [min(variants, key=lambda v: v[0] * v[1])]
        port = 0
        for width, height, _bandwidth, name, upstream in wanted:
            if not result and not _usable(upstream):
                continue
            if not port:
                _store(streamId, variants)
                port = _startServer().server_address[1]
            label = ("%s  %dx%d" % (name, width, height) if name else "%dx%d" % (width, height)).strip() if width else (name or "HLS")
            # (str: plain ASCII, no unicode on Python 2)
            result.append((str(label), str("http://127.0.0.1:%d/sc/%s/%s/index.m3u8" % (port, streamId, _renditionKey(name, height))), height))
    except Exception:
        printExc()
        return []
    return result
