# -*- coding: utf-8 -*-
LAST_MODIFIED = "25.10.2026"
# capitanstrims.st: live sport (Flashscore match list, channels per match). The player builds its HLS playlist
#   from a WebSocket feed: a background client keeps writing it to a local m3u8 that hlsdl reads.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, requireDownloaderForDisguisedHls
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetTmpDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import base64
import json
import os
import re
import socket
import ssl
import struct
import threading
import time
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://capitanstrims.st/"


class CapitanPlaylistFeed(object):
    # WebSocket client for the live playlist of one channel token: wss://l1.strims24.st/ws sends a complete
    # media playlist about every 5 s after {"subscribe": token}; it is written to a local file the downloader
    # re-reads. Ends on stop(), when no process has the file open any more (/proc), or after MAX_LIFETIME.
    WS_HOST = "l1.strims24.st"
    WS_PATH = "/ws"
    ORIGIN = "https://iplayer24.me"
    FILE_PREFIX = "capitanstrims_"
    SOCKET_TIMEOUT = 5
    FIRST_TIMEOUT = 8      # the first playlist comes right after the subscription
    # Cloudflare in front of l1 answers most handshakes with 502 Bad Gateway or not at all, independent of the
    # token (the handshake comes before the subscription; 2026-10-25 about 1 in 7 got through). The site's
    # player reconnects every 2 s without limit, so keep trying for a while instead of a fixed number of tries.
    FIRST_BUDGET = 60      # seconds for the first playlist
    SILENT_LIMIT = 2       # subscriptions answered by no playlist at all = channel without picture -> give up
    RETRY_PAUSE = 1
    RECONNECT_BUDGET = 120  # a running feed gives up after this long without a playlist
    FRAME_TIMEOUT = 30     # no playlist for this long -> reconnect
    GRACE = 90             # time for the player selection / downloader start before the file must be in use
    CHECK_EVERY = 15
    IDLE_CHECKS = 2
    MAX_LIFETIME = 5 * 3600
    MAX_FRAME = 4 * 1024 * 1024  # a media playlist is a few KB

    _lock = threading.Lock()
    _active = []

    def __init__(self, token, path, userAgent):
        self.token = token
        self.path = path
        self.userAgent = userAgent
        self.sock = None
        self.buf = bytearray()
        self.fragments = bytearray()
        self.stopEvent = threading.Event()
        self.worker = None
        self.failReason = ""  # why start() failed: "busy" (handshakes refused / unanswered) or "silent"

    ###################################################
    # public
    ###################################################
    @classmethod
    def stopAll(cls):
        with cls._lock:
            feeds = list(cls._active)
            del cls._active[:]
        for feed in feeds:
            feed.stop()
        cls.removeStaleFiles()

    @classmethod
    def removeStaleFiles(cls):
        # playlists of feeds that ended without cleaning up (box restart)
        try:
            tmpDir = GetTmpDir()
            with cls._lock:
                inUse = set(os.path.basename(feed.path) for feed in cls._active)
            for name in os.listdir(tmpDir):
                if name.startswith(cls.FILE_PREFIX) and name not in inUse:
                    os.remove(os.path.join(tmpDir, name))
        except Exception:
            printExc()

    def start(self):
        # synchronous part: connect, subscribe and wait for the first playlist, then the rest in the background
        playlist = ""
        startedAt = time.time()
        deadline = startedAt + self.FIRST_BUDGET
        attempt = 0
        silent = 0
        while True:
            attempt += 1
            connected = False
            try:
                self._connect()
                connected = True
                playlist = self._readPlaylist(self.FIRST_TIMEOUT)
                if not playlist:
                    silent += 1
                    printDBG("CapitanPlaylistFeed [%s] attempt %d: subscribed, but no playlist within %d s" % (self.token, attempt, self.FIRST_TIMEOUT))
            except Exception as e:
                if connected:
                    silent += 1
                printDBG("CapitanPlaylistFeed [%s] attempt %d failed [%s]" % (self.token, attempt, e))
            if playlist:
                break
            self._close()
            if silent >= self.SILENT_LIMIT:
                self.failReason = "silent"
                break
            if self.stopEvent.is_set() or time.time() + self.RETRY_PAUSE >= deadline:
                self.failReason = "busy"
                break
            time.sleep(self.RETRY_PAUSE)
        if not playlist:
            printDBG("CapitanPlaylistFeed [%s] no playlist after %d attempts / %d s (%s)" % (self.token, attempt, time.time() - startedAt, self.failReason))
            return False
        printDBG("CapitanPlaylistFeed [%s] first playlist on attempt %d after %d s" % (self.token, attempt, time.time() - startedAt))
        self._writePlaylist(playlist)
        with self._lock:
            self._active.append(self)
        # a daemon thread, not AsyncMethod: only sockets and files in it (no pCommon/pycurl), and a running feed
        # must not hold up the enigma2 shutdown
        self.worker = threading.Thread(target=self._run, name="CapitanPlaylistFeed")
        self.worker.daemon = True
        self.worker.start()
        return True

    def stop(self):
        self.stopEvent.set()

    ###################################################
    # background loop
    ###################################################
    def _run(self):
        startedAt = time.time()
        lastCheck = startedAt
        lastFrame = startedAt
        lastPlaylist = startedAt
        idleChecks = 0
        failures = 0
        reason = "stopped"
        try:
            while not self.stopEvent.is_set():
                now = time.time()
                if now - startedAt > self.MAX_LIFETIME:
                    reason = "max lifetime"
                    break
                if now - startedAt >= self.GRACE and now - lastCheck >= self.CHECK_EVERY:
                    lastCheck = now
                    inUse = self._playlistInUse()
                    if inUse is False:
                        idleChecks += 1
                        if idleChecks >= self.IDLE_CHECKS:
                            reason = "playlist not read any more"
                            break
                    else:
                        idleChecks = 0
                if self.sock is None:
                    if failures and time.time() - lastPlaylist > self.RECONNECT_BUDGET:
                        reason = "no playlist for %d s (%d failed connections)" % (time.time() - lastPlaylist, failures)
                        break
                    if failures and self.stopEvent.wait(2):
                        break
                    try:
                        self._connect()
                        lastFrame = time.time()
                    except Exception as e:
                        printDBG("CapitanPlaylistFeed reconnect failed [%s]" % e)
                        self._close()
                        failures += 1
                        continue
                try:
                    playlist = self._readPlaylist(self.SOCKET_TIMEOUT)
                except Exception as e:
                    printDBG("CapitanPlaylistFeed connection lost [%s]" % e)
                    self._close()
                    failures += 1
                    continue
                if playlist:
                    lastFrame = lastPlaylist = time.time()
                    failures = 0
                    self._writePlaylist(playlist)
                elif time.time() - lastFrame > self.FRAME_TIMEOUT:
                    printDBG("CapitanPlaylistFeed no playlist for %d s -> reconnect" % self.FRAME_TIMEOUT)
                    self._close()
                    failures += 1
        except Exception:
            printExc()
            reason = "exception"
        self._close()
        with self._lock:
            if self in self._active:
                self._active.remove(self)
        for path in (self.path, self.path + ".part"):
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except Exception:
                printExc()
        printDBG("CapitanPlaylistFeed [%s] ended: %s" % (self.token, reason))

    def _playlistInUse(self):
        # True/False: a process (hlsdl, ffmpeg, the shell around them) names the playlist in its command line;
        # None: no /proc (not Linux) - then only stop() and MAX_LIFETIME end the feed
        if not os.path.isdir("/proc"):
            return None
        name = os.path.basename(self.path).encode("utf-8")
        try:
            for pid in os.listdir("/proc"):
                if not pid.isdigit():
                    continue
                try:
                    with open("/proc/%s/cmdline" % pid, "rb") as f:
                        if name in f.read():
                            return True
                except Exception:
                    continue
        except Exception:
            printExc()
            return None
        return False

    def _writePlaylist(self, playlist):
        # the reader must never see half a file: write next to it, then rename
        tmpPath = self.path + ".part"
        try:
            with open(tmpPath, "wb") as f:
                f.write(playlist.encode("utf-8") if not isinstance(playlist, bytes) else playlist)
            try:
                os.rename(tmpPath, self.path)
            except OSError:
                # Windows (harness): rename does not replace
                if os.path.isfile(self.path):
                    os.remove(self.path)
                os.rename(tmpPath, self.path)
        except Exception:
            printExc()

    ###################################################
    # WebSocket (RFC 6455, client side, text frames)
    ###################################################
    def _connect(self):
        self._close()
        raw = None
        try:
            # IPv4 first, then whatever the resolver gives
            for family in (socket.AF_INET, 0):
                try:
                    addr = socket.getaddrinfo(self.WS_HOST, 443, family, socket.SOCK_STREAM)[0]
                    raw = socket.socket(addr[0], addr[1], addr[2])
                    raw.settimeout(self.FIRST_TIMEOUT)
                    raw.connect(addr[4])
                    break
                except Exception:
                    if raw is not None:
                        raw.close()
                    raw = None
                    if family == 0:
                        raise
            if hasattr(ssl, "_create_unverified_context"):
                sock = ssl._create_unverified_context().wrap_socket(raw, server_hostname=self.WS_HOST)
            else:
                # Python 2.7 before 2.7.9: no SSLContext (and no SNI)
                sock = ssl.wrap_socket(raw)
        except Exception:
            if raw is not None:
                raw.close()
            raise
        self.sock = sock
        self.buf = bytearray()
        self.fragments = bytearray()
        key = ensure_str(base64.b64encode(os.urandom(16)))
        request = ("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                   "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nOrigin: %s\r\nUser-Agent: %s\r\n\r\n") % (self.WS_PATH, self.WS_HOST, key, self.ORIGIN, self.userAgent)
        sock.sendall(request.encode("utf-8"))
        deadline = time.time() + self.FIRST_TIMEOUT
        while b"\r\n\r\n" not in self.buf:
            if time.time() > deadline or len(self.buf) > 16384:
                raise IOError("no WebSocket handshake answer")
            self._recvMore()
        end = self.buf.find(b"\r\n\r\n") + 4
        head = ensure_str(bytes(self.buf[:end]), errors="replace")
        del self.buf[:end]
        if " 101 " not in head.split("\r\n", 1)[0] + " ":
            raise IOError("WebSocket handshake refused: %s" % head.split("\r\n", 1)[0])
        sock.settimeout(self.SOCKET_TIMEOUT)
        self._sendFrame(0x1, json.dumps({"subscribe": self.token}).encode("utf-8"))

    def _close(self):
        sock = self.sock
        self.sock = None
        # bytes of a frame cut by the lost connection must not reach the parser of the next one
        self.buf = bytearray()
        self.fragments = bytearray()
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

    def _recvMore(self):
        data = self.sock.recv(65536)
        if not data:
            raise EOFError("WebSocket closed by the server")
        self.buf.extend(bytearray(data))

    def _sendFrame(self, opcode, payload):
        payload = bytearray(payload)
        mask = bytearray(os.urandom(4))
        frame = bytearray([0x80 | opcode])
        n = len(payload)
        if n < 126:
            frame.append(0x80 | n)
        elif n < 65536:
            frame.append(0x80 | 126)
            frame.extend(bytearray(struct.pack(">H", n)))
        else:
            frame.append(0x80 | 127)
            frame.extend(bytearray(struct.pack(">Q", n)))
        frame.extend(mask)
        for i in range(n):
            payload[i] ^= mask[i % 4]
        frame.extend(payload)
        self.sock.sendall(bytes(frame))

    def _takeFrame(self):
        # one complete frame from the buffer: (fin, opcode, payload) or None
        buf = self.buf
        if len(buf) < 2:
            return None
        n = buf[1] & 0x7F
        pos = 2
        if n == 126:
            if len(buf) < 4:
                return None
            n = struct.unpack(">H", bytes(buf[2:4]))[0]
            pos = 4
        elif n == 127:
            if len(buf) < 10:
                return None
            n = struct.unpack(">Q", bytes(buf[2:10]))[0]
            pos = 10
        if n > self.MAX_FRAME:
            raise IOError("WebSocket frame too large (%d bytes)" % n)
        mask = None
        if buf[1] & 0x80:
            mask = buf[pos:pos + 4]
            pos += 4
        if len(buf) < pos + n:
            return None
        payload = bytearray(buf[pos:pos + n])
        if mask is not None and len(mask) == 4:
            for i in range(n):
                payload[i] ^= mask[i % 4]
        fin = bool(buf[0] & 0x80)
        opcode = buf[0] & 0x0F
        del buf[:pos + n]
        return fin, opcode, payload

    def _readPlaylist(self, timeout):
        # the next playlist within timeout seconds ('' = none in time); answers ping, raises on close / errors
        deadline = time.time() + timeout
        while True:
            frame = self._takeFrame()
            if frame is None:
                if time.time() >= deadline or self.stopEvent.is_set():
                    return ""
                try:
                    self._recvMore()
                except socket.timeout:
                    continue
                except ssl.SSLError as e:
                    if "timed out" in str(e):
                        continue
                    raise
                continue
            fin, opcode, payload = frame
            if opcode == 0x9:
                self._sendFrame(0xA, payload)
            elif opcode == 0x8:
                raise EOFError("WebSocket close frame")
            elif opcode in (0x0, 0x1):
                self.fragments.extend(payload)
                if fin:
                    text = ensure_str(bytes(self.fragments), errors="replace")
                    self.fragments = bytearray()
                    # like the site's service worker: only a playlist with segments counts
                    if "#EXTM3U" in text and "#EXTINF" in text:
                        return text
                    printDBG("CapitanPlaylistFeed other message [%s]" % text[:200])


class CapitanStrims(CBaseHostClass):
    # minutes a custom event runs without end_ts (site: SPORT_DURATIONS)
    CUSTOM_DURATIONS = {"football": 65, "basketball": 150, "hockey": 150, "tennis": 180}

    FEED_URL = "https://1.newsoccers.one/2/x/feed/f_%d_%d_2_en_1"
    FEED_SIGN = "SW9D1eZo"
    PLAYER_URL = "https://iplayer24.me/echo/%s"
    TOKEN_RE = re.compile("^[0-9a-f]{32}$")
    LINK_SCHEME = "capitanstrims://"
    EARLY_LINKS = 15 * 60  # links work from 15 minutes before the start

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "CapitanStrims", "cookie": "capitanstrims.cookie"})
        self.USER_AGENT = self.cm.getDefaultUserAgent("chrome")
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "application/json, text/plain, */*",
                       "Accept-Language": "en-US,en;q=0.8", "Referer": gettytul()}
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("assets/apple-touch-icon.png")
        self.feedCache = {}
        # (site slug, API slug, title, Flashscore sport id - 0 = no Flashscore feed)
        self.SPORTS = (("football", "football", _("Football"), 1), ("basketball", "basketball", _("Basketball"), 3),
                       ("tennis", "tennis", _("Tennis"), 2), ("hockey", "hockey", _("Hockey"), 4),
                       ("mma", "mma", "MMA", 28), ("boxing", "boxing", _("Boxing"), 16),
                       ("nfl", "american-football", _("American football"), 5), ("baseball", "baseball", "Baseball", 6),
                       ("cricket", "cricket", _("Cricket"), 13), ("cycling", "cycling", "Cycling", 34),
                       ("darts", "darts", _("Darts"), 14), ("futsal", "futsal", _("Futsal"), 11),
                       ("golf", "golf", "Golf", 23), ("handball", "handball", _("Handball"), 7),
                       ("motorsport", "motorsport", _("Motorsport"), 31), ("snooker", "snooker", _("Snooker"), 15),
                       ("volleyball", "volleyball", _("Volleyball"), 12), ("waterpolo", "waterpolo", "Water polo", 0),
                       ("winter-sports", "winter-sports", _("Winter sports"), 37))

    ###################################################
    # helpers
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getJson(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
            return None

    def _feedEvents(self, sportId):
        # Flashscore mirror feed of yesterday + today (the site does the same for matches across midnight):
        # records split by "~", fields by "¬", key÷value; ZA = tournament (record before its matches)
        cached = self.feedCache.get(sportId)
        if cached and time.time() - cached[0] < 60:
            return cached[1]
        events = {}
        params = {"header": dict(self.HEADER, **{"X-Fsign": self.FEED_SIGN, "Origin": self.MAIN_URL.rstrip("/")})}
        for dayOffset in (-1, 0):
            sts, data = self.getPage(self.FEED_URL % (sportId, dayOffset), dict(params))
            if not sts or not data:
                continue
            tournament = ""
            for record in ensure_str(data).split("~"):
                fields = {}
                for field in record.split("¬"):
                    if "÷" in field:
                        key, value = field.split("÷", 1)
                        if key not in fields:
                            fields[key] = value
                if "ZA" in fields:
                    tournament = fields["ZA"]
                eventId = fields.get("AA")
                if not eventId:
                    continue
                try:
                    start = int(fields.get("AD", "0"))
                except ValueError:
                    start = 0
                events[eventId] = {"home": fields.get("AE", ""), "away": fields.get("AF", ""), "start": start,
                                   "status": fields.get("AB", ""), "tournament": tournament,
                                   "home_score": fields.get("AG", ""), "away_score": fields.get("AH", "")}
        self.feedCache[sportId] = (time.time(), events)
        return events

    def _timeLabel(self, ts):
        if not ts:
            return ""
        local = time.localtime(ts)
        if time.strftime("%Y%m%d", local) == time.strftime("%Y%m%d", time.localtime()):
            return time.strftime("%H:%M", local)
        return time.strftime("%d.%m. %H:%M", local)

    def _customEvent(self, item, sport):
        try:
            start = int(item.get("start_ts") or 0)
            end = int(item.get("end_ts") or 0)
        except (TypeError, ValueError):
            return None
        if not end:
            end = start + self.CUSTOM_DURATIONS.get(item.get("sport") or sport, 180) * 60
        now = time.time()
        if now >= end:
            return None
        name = (item.get("name") or "").strip()
        home, away = (name.split(" - ", 1) + [""])[:2] if " - " in name else (name, "")
        return {"home": home.strip(), "away": away.strip(), "start": start, "status": "2" if now >= start else "1",
                "tournament": "", "home_score": "", "away_score": ""}

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        for slug, apiSlug, title, sportId in self.SPORTS:
            self.addDir({"name": "category", "category": "sport", "title": title, "sport": apiSlug, "sport_id": sportId, "good_for_fav": True,
                         "url": self.getFullUrl("sports/%s" % slug if slug != "football" else "")})

    def listSport(self, cItem):
        apiSlug = cItem["sport"]
        sportId = cItem.get("sport_id", 0)
        data = self.getJson(self.getFullUrl("api/v1/%s/%s" % (apiSlug, time.strftime("%Y-%m-%d"))))
        items = (data or {}).get("items") or []
        events = self._feedEvents(sportId) if sportId and any(str(i.get("match_id", "")).startswith("FS:") for i in items) else {}
        rows = []
        for item in items:
            matchId = str(item.get("match_id", ""))
            if matchId.startswith("FS:"):
                event = events.get(matchId[3:])
                if event is None:
                    if sportId:
                        continue  # not in yesterday's / today's feed: finished or another day
                    event = {"home": matchId[3:], "away": "", "start": 0, "status": "", "tournament": "", "home_score": "", "away_score": ""}
                elif event["status"] not in ("1", "2"):
                    continue  # finished (its links lead to google.com) or cancelled
            elif matchId.startswith("CUST:"):
                event = self._customEvent(item, apiSlug)
                if event is None:
                    continue
            else:
                continue
            rows.append((matchId, event))
        # live first, then by start time
        rows.sort(key=lambda row: (0 if row[1]["status"] == "2" else 1, row[1]["start"]))
        for matchId, event in rows:
            live = event["status"] == "2"
            name = event["home"] if not event["away"] else "%s - %s" % (event["home"], event["away"])
            if live:
                title = "%s | %s" % (_("Live"), name)
            else:
                title = "%s | %s" % (self._timeLabel(event["start"]), name) if event["start"] else name
            desc = []
            if event["tournament"]:
                desc.append(event["tournament"])
            if live and event["home_score"] != "" and event["away_score"] != "":
                desc.append("%s %s:%s %s" % (event["home"], event["home_score"], event["away_score"], event["away"]))
            if event["start"]:
                desc.append(self._timeLabel(event["start"]) if live else _("Live stream starts %s") % self._timeLabel(event["start"]))
            self.addVideo({"name": "category", "category": "match", "title": title, "match_id": matchId, "start": event["start"],
                           "url": self.getFullUrl("match/%s" % matchId), "desc": "\n".join(desc), "good_for_fav": True, "live": True})

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        matchId = cItem.get("match_id", "")
        printDBG("CapitanStrims.getLinksForVideo [%s]" % matchId)
        data = self.getJson(self.getFullUrl("api/v1/match/%s" % matchId))
        links = []
        for entry in (data or {}).get("custom_urls") or []:
            if not isinstance(entry, dict) or not entry.get("enabled", True):
                continue
            url = str(entry.get("url") or "").strip()
            name = entry.get("name") or "Stream"
            if entry.get("viewers"):
                name = "%s (%s)" % (name, entry["viewers"])
            if self.TOKEN_RE.match(url):
                links.append({"name": name, "url": self.LINK_SCHEME + url, "need_resolve": 1})
            elif url.startswith(("http://", "https://")):
                links.append({"name": name, "url": url, "need_resolve": 1})
        if not links:
            start = cItem.get("start", 0)
            if start and start - time.time() > self.EARLY_LINKS:
                SetIPTVPlayerLastHostError(_("Live stream starts %s") % self._timeLabel(start))
            else:
                SetIPTVPlayerLastHostError(_("No stream available"))
        return links

    def getVideoLinks(self, url):
        printDBG("CapitanStrims.getVideoLinks [%s]" % url)
        url = str(url)
        if url.startswith(self.LINK_SCHEME):
            return self._playToken(url[len(self.LINK_SCHEME):])
        # a stream address instead of a token (the site opens it in its embed player)
        if ".m3u8" in url.lower():
            meta = {"User-Agent": self.USER_AGENT, "Referer": self.PLAYER_URL % "", "iptv_livestream": True}
            return requireDownloaderForDisguisedHls(getDirectM3U8Playlist(strwithmeta(url, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999))
        return self.up.getVideoLinkExt(url)

    def _playToken(self, token):
        # an expired token: the player page redirects to google.com
        params = dict(self.defaultParams, no_redirection=True)
        params["header"] = dict(self.HEADER, Accept="text/html,application/xhtml+xml,*/*;q=0.8")
        self.cm.getPage(self.PLAYER_URL % token, params)
        if "google." in self.cm.meta.get("location", ""):
            SetIPTVPlayerLastHostError(_("The live stream is not available at the moment."))
            return []
        CapitanPlaylistFeed.stopAll()
        # a new file name per start: a stopped feed of the same token deletes its own file when its thread ends
        path = GetTmpDir("%s%s_%x.m3u8" % (CapitanPlaylistFeed.FILE_PREFIX, token, int(time.time() * 1000)))
        feed = CapitanPlaylistFeed(token, path, self.USER_AGENT)
        if not feed.start():
            if feed.failReason == "busy":
                SetIPTVPlayerLastHostError("The stream server of the site is overloaded (refuses the connection) - please try again in a moment.")
            else:
                SetIPTVPlayerLastHostError(_("The live stream is not available at the moment."))
            return []
        return [{"name": "CAPITANSTRIMS", "url": self._playlistUrl(path)}]

    def _playlistUrl(self, path):
        # the local playlist as the downloader gets it. hlsdl reads paths without "://" from disk and (0.34+) cuts
        # the 70-byte PNG head off the TS segments (*.image on a TikTok image CDN). A strip proxy would hand
        # out its own http://127.0.0.1 URL here instead.
        try:
            from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
            if not DMHelper.hlsdlCutsImageHeads():
                printDBG("CapitanStrims: hlsdl older than 0.34 keeps the PNG head of the segments - playback will likely fail")
        except Exception:
            printExc()
        meta = {"User-Agent": self.USER_AGENT, "iptv_proto": "m3u8", "iptv_buffering": "required", "iptv_livestream": True}
        return strwithmeta(path, meta)

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("CapitanStrims.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu(self.currItem)
        elif category == "sport":
            self.listSport(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, CapitanStrims(), True, [])
