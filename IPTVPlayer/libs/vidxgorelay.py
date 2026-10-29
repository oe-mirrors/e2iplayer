# -*- coding: utf-8 -*-
# vidxgo (v.vidxgo.co, the player of altadefinizionex / guardaseriex): GET /t/<id>[/<season>/<episode>] answers
# {"url": ".../master.m3u8?t=..&e=..&b=..", "expire": <ms>}; the token in that query is valid for ~180 s, for the
# playlists and for every segment. exteplayer3 / hlsdl read a VOD playlist once, so a film would stop after three
# minutes: localUrl() serves the media playlist on 127.0.0.1 with local segment paths, each segment is fetched with
# the current token (a new one is asked for when less than REMINT_BEFORE seconds are left) and passed through.
# The CDN wants Referer = the player + Sec-Fetch-Dest / Sec-Fetch-Site and refuses ffmpeg's own UA (Lavf).
import hashlib
import json
import re
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc

VX_HOST = "https://v.vidxgo.co"
VX_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0"
CDN_HEADERS = {"User-Agent": VX_UA, "Referer": VX_HOST + "/", "Origin": VX_HOST, "Accept": "*/*",
               "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "cross-site"}
REMINT_BEFORE = 30
MAX_ENTRIES = 32
READ_BLOCK = 64 * 1024

_lock = threading.Lock()
_server = None
_entries = {}


def _open(url, headers, timeout=20):
    # like pCommon on the box: no certificate check (many images ship no CA bundle)
    ctx = ssl._create_unverified_context()  # NOSONAR - same as the plugin's other requests, receivers lack CA certificates
    return urlopen(Request(url, headers=headers), timeout=timeout, context=ctx)


def videoPath(url):
    # "32333324" (movie) or "2531336/1/1" (episode) of a v.vidxgo.co url, "" for anything else
    match = re.search(r"vidxgo\.\w+/(\d+)(?:/(\d+)/(\d+))?", str(url))
    return "/".join(x for x in match.groups() if x) if match else ""


def mint(path):
    # (master url, expire time in seconds) of a fresh token, ("", 0) when the title is not on vidxgo
    try:
        resp = _open("%s/t/%s" % (VX_HOST, path), {"User-Agent": VX_UA, "Referer": "%s/%s" % (VX_HOST, path), "Accept": "application/json, text/plain, */*"})
        data = json.loads(resp.read().decode("utf-8", "ignore"))
        url = data.get("url") or ""
        expire = float(data.get("expire") or 0) / 1000.0 or time.time() + 170
        return (url, expire) if url.startswith("http") else ("", 0)
    except Exception:
        printDBG("vidxgo: no token for [%s]" % path)
        return "", 0


def _dirAndQuery(url):
    base, _sep, query = url.partition("?")
    return base.rsplit("/", 1)[0] + "/", query


def _fresh(entry, force=False):
    # the current (cdn dir, token query) of an entry, a new token when it runs out
    with entry["lock"]:
        if force or entry["expire"] - time.time() < REMINT_BEFORE:
            url, expire = mint(entry["path"])
            if url:
                entry["dir"], entry["query"] = _dirAndQuery(url)
                entry["expire"] = expire
                printDBG("vidxgo: new token for [%s], valid %d s" % (entry["path"], expire - time.time()))
        return entry["dir"], entry["query"]


def _bestVariant(master):
    # the media playlist of the highest BANDWIDTH of a master playlist (relative path without query)
    best, bandwidth, lines = "", -1, master.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF") and idx + 1 < len(lines):
            value = re.search(r"BANDWIDTH=(\d+)", line)
            value = int(value.group(1)) if value else 0
            if value > bandwidth:
                best, bandwidth = lines[idx + 1].strip().split("?", 1)[0], value
    return best


def _mediaPlaylist(token, entry):
    # the media playlist with local segment urls: /vx/<token>/<sub dir>/<segment>
    cdnDir, query = _fresh(entry)
    master = _open("%smaster.m3u8?%s" % (cdnDir, query), CDN_HEADERS).read().decode("utf-8", "ignore")
    media = _bestVariant(master) if "#EXT-X-STREAM-INF" in master else ""
    text = master
    if media:
        entry["media"] = media
        text = _open("%s%s?%s&p=" % (cdnDir, media, query), CDN_HEADERS).read().decode("utf-8", "ignore")
    sub = entry.get("media", "").rsplit("/", 1)[0] + "/" if "/" in entry.get("media", "") else ""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            line = "/vx/%s/%s%s" % (token, sub, line.split("?", 1)[0].lstrip("/"))
        out.append(line)
    return "\n".join(out) + "\n"


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *args):
        pass

    def do_GET(self):
        parts = self.path.split("?", 1)[0].split("/", 3)
        # ["", "vx", <token>, <file>]
        entry = _entries.get(parts[2]) if len(parts) == 4 and parts[1] == "vx" else None
        if not entry:
            self.send_error(404)
            return
        try:
            if parts[3] == "index.m3u8":
                body = _mediaPlaylist(parts[2], entry).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)
                return
            self._segment(entry, parts[3])
        except OSError:
            printDBG("vidxgo: request closed by the player")
        except Exception:
            printExc()
            self.send_error(502)

    def _segment(self, entry, name):
        headers = dict(CDN_HEADERS)
        if self.headers.get("Range"):
            headers["Range"] = self.headers["Range"]
        resp = None
        for force in (False, True):
            cdnDir, query = _fresh(entry, force)
            try:
                resp = _open("%s%s?%s&p=" % (cdnDir, name, query), headers)
                break
            except Exception as e:
                # 403: the token ran out early - one more try with a new one
                if force or getattr(e, "code", 0) != 403:
                    raise
        self.send_response(resp.status)
        for key in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
            if resp.headers.get(key):
                self.send_header(key, resp.headers[key])
        self.end_headers()
        while True:
            block = resp.read(READ_BLOCK)
            if not block:
                break
            self.wfile.write(block)


def _startServer():
    global _server
    with _lock:
        if _server is None:
            server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, name="E2iVidxgo")
            thread.daemon = True
            thread.start()
            _server = server
            printDBG("vidxgo: local relay on 127.0.0.1:%d" % server.server_address[1])
        return _server


def localUrl(url):
    # http://127.0.0.1:<port>/vx/<token>/index.m3u8 for a v.vidxgo.co url, None when vidxgo has no token for it
    path = videoPath(url)
    if not path:
        return None
    masterUrl, expire = mint(path)
    if not masterUrl:
        return None
    token = hashlib.md5(path.encode("utf-8")).hexdigest()[:16]
    cdnDir, query = _dirAndQuery(masterUrl)
    with _lock:
        _entries.pop(token, None)
        _entries[token] = {"path": path, "dir": cdnDir, "query": query, "expire": expire, "lock": threading.Lock()}
        if len(_entries) > MAX_ENTRIES:
            for key in list(_entries)[:len(_entries) - MAX_ENTRIES]:
                _entries.pop(key, None)
    try:
        server = _startServer()
    except Exception:
        printExc()
        return None
    return "http://127.0.0.1:%d/vx/%s/index.m3u8" % (server.server_address[1], token)
