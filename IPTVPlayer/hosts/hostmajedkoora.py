# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# Ported to the python3 framework (08.10.2026):
#   - Majed Sport (majed-koora.live): the site's JSON API /api/v1/matches?lang=ar&date=<day>&scope=all;
#     today / tomorrow (live and coming matches), start time in the box time, live score, tournament, channel, commentator
#   - links: a match's "watch_url" carries the key (?mk=) of /api/public/watch-card; the card only lists its
#     servers inside the stream window (opens 30 min before kick-off, closes 4 h after - outside the window the
#     server list is empty, that was the "links 0"). Server types like the site's own player script:
#     m3u8 / hls_js / dplayer / mp4 / mpd direct, YouTube / Twitch / Kick / ok.ru / goodgame / mux / iframe /
#     external through urlparser (else the first stream address of the page), "majed_player" pages
#     (?channel=<id>): /api/stream.php answers AES-256-GCM (key sha256("majed-player-stream-v1|<authorization
#     meta of the page>")) -> the stream url
#   - favourites re-open the match from the API by its key, INFO with the match data
# 09.10.2026 - the player pages (player.majed-koora.live) answer 403 unless the Referer is the watch page
#     (the match's watch_url, live.<idn>.com - the only frame ancestor the player allows): Referer = watch page;
#     the stream hosts behind it want the player's origin (smarter.majedcss.site: 403 "origin denied" else)
import calendar
import hashlib
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.aesgcm import python_aesgcm
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta, requireDownloaderForDisguisedHls
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, b64urlDecode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://majed-koora.live/"


STREAM_AAD = b"majed-player-stream-v1"
DIRECT_TYPES = ("m3u8", "hls_js", "dplayer", "mp4", "mpd")


def _domain(url):
    m = re.match(r"^https?://(?:www\.)?([^/:?#]+)", url or "")
    return m.group(1).lower() if m else ""


def _isoToTimestamp(value):
    # "2026-10-08T18:45:00+03:00" / "...Z" / "....000Z" -> UTC timestamp, 0 when unknown
    m = re.match(r"^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)(?::(\d\d))?(?:\.\d+)?(Z|[+-]\d\d:?\d\d)?", value or "")
    if not m:
        return 0
    stamp = calendar.timegm(tuple(int(x or 0) for x in m.groups()[:6]))
    zone = m.group(7) or "Z"
    if zone != "Z":
        sign = -1 if zone[0] == "+" else 1
        zone = zone[1:].replace(":", "")
        stamp += sign * (int(zone[:2]) * 3600 + int(zone[2:]) * 60)
    return stamp


class MajedKoora(CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "match_id", "watch_key", "day")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "majedkoora", "cookie": "majedkoora.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/majedkoora135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": dict(self.HEADER, Accept="application/json", Referer=self.MAIN_URL)}
        self.cache = {}

    ###################################################
    # helpers
    ###################################################
    def _json(self, url, params=None):
        sts, data = self.cm.getPage(url, params or self.defaultParams)
        if not sts:
            return {}
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return {}
        return data if isinstance(data, dict) else {}

    def _matches(self, day):
        if day not in self.cache:
            date = time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400 * day))
            data = self._json(self.getFullUrl("api/v1/matches?lang=ar&date=%s&scope=all" % date))
            self.cache[day] = [m for m in data.get("matches") or [] if isinstance(m, dict)]
        return self.cache[day]

    def _icon(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        return strwithmeta(self.getFullUrl(url), {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL})

    @staticmethod
    def _watchKey(match):
        m = re.search(r"[?&]mk=([^&#]+)", match.get("watch_url") or "")
        return m.group(1) if m else ""

    def _info(self, match):
        # [(INFO key, label, value)]
        broadcast = match.get("broadcast") or {}
        start = match.get("timestamp") or _isoToTimestamp(match.get("start_at"))
        rows = [("broadcast", _("Start"), time.strftime("%d.%m.%Y %H:%M", time.localtime(int(start))) if start else ""),
                ("status", _("Status"), match.get("state_text", "")),
                ("genre", _("Tournament"), (match.get("tournament") or {}).get("name", "")),
                ("station", _("Channel"), broadcast.get("channel", "")),
                ("director", _("Commentator"), broadcast.get("commentator", "")),
                ("country", _("Venue"), match.get("stadium", ""))]
        return [row for row in rows if row[2]]

    def _row(self, match, day):
        home, away = match.get("home_team") or {}, match.get("away_team") or {}
        if not home.get("name") or not away.get("name"):
            return None
        state = match.get("state", "")
        start = match.get("timestamp") or _isoToTimestamp(match.get("start_at"))
        teams = "%s - %s" % (home["name"].strip(), away["name"].strip())
        if state in ("live", "finished"):
            teams = "%s %s:%s %s" % (home["name"].strip(), home.get("score", 0), away.get("score", 0), away["name"].strip())
        prefix = _("Live") if state == "live" else time.strftime("%H:%M", time.localtime(int(start))) if start else ""
        desc = "[/br]".join("%s: %s" % (label, value) for _key, label, value in self._info(match))
        return {"name": "category", "category": "mk_match", "good_for_fav": True, "title": "%s %s" % (prefix, teams) if prefix else teams,
                "match_id": str(match.get("id", "")), "watch_key": self._watchKey(match), "day": day,
                "url": self.getFullUrl("?match=%s" % match.get("id", "")), "desc": desc,
                "icon": self._icon(home.get("logo") or away.get("logo") or (match.get("tournament") or {}).get("logo"))}

    def _findMatch(self, cItem):
        for day in (cItem.get("day", 0), 0, -1, 1):
            for match in self._matches(day):
                if str(match.get("id", "")) == cItem.get("match_id"):
                    return match
        return {}

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") == "mk_match":
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        self.listsTab([{"category": "mk_day", "title": _("Today"), "day": 0},
                       {"category": "mk_day", "title": _("Tomorrow"), "day": 1}], cItem)

    def listDay(self, cItem):
        day = cItem.get("day", 0)
        # finished matches never play (the site has no replays): only live and coming ones
        matches = [m for m in self._matches(day) if m.get("state") not in ("finished", "postponed", "cancelled")]
        matches.sort(key=lambda m: (m.get("state") != "live", m.get("timestamp") or 0))
        if not matches:
            SetIPTVPlayerLastHostError(_("No items found"))
        for match in matches:
            row = self._row(match, day)
            if row:
                self.addVideo(row)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("MajedKoora.getLinksForVideo [%s]" % cItem.get("match_id", ""))
        self.cache = {}
        match = self._findMatch(cItem)
        key = self._watchKey(match) or cItem.get("watch_key", "")
        watchPage = match.get("watch_url") or ""
        watchPage = watchPage if self.cm.isValidUrl(watchPage) else self.MAIN_URL
        if not key:
            SetIPTVPlayerLastHostError(_("Not available yet"))
            return []
        watch = self._json(self.getFullUrl("api/public/watch-card?key=%s" % urllib_quote(key))).get("watch") or {}
        servers = [s for s in watch.get("servers") or [] if isinstance(s, dict) and s.get("url")]
        if not watch.get("available") or not servers:
            availability = watch.get("availability") or {}
            opens = _isoToTimestamp(availability.get("opens_at"))
            if availability.get("code") in ("closed", "expired") or not opens or opens < time.time():
                SetIPTVPlayerLastHostError(_("Content not available"))
            else:
                SetIPTVPlayerLastHostError("%s (%s %s)" % (_("Not available yet"), _("Start"), time.strftime("%H:%M", time.localtime(opens))))
            return []
        servers.sort(key=lambda s: (not s.get("is_default"), int(s.get("priority") or 0)))
        urltab = []
        for server in servers:
            name = (server.get("name") or "").strip() or "%s %d" % (_("Server"), len(urltab) + 1)
            if server.get("quality"):
                name = "%s (%s)" % (name, server["quality"])
            url = strwithmeta(server["url"], {"mk_type": server.get("type", ""), "mk_page": watchPage, "Referer": self.MAIN_URL})
            urltab.append({"name": "%s - %s" % (name, _domain(server["url"])), "url": url, "need_resolve": 1})
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), ""))

    def _majedPlayer(self, playerUrl, watchPage):
        # player page: <meta name="majed-player-authorization" content="..."> + ./api/stream.php?id=<channel>
        # (403 without the watch page as Referer)
        params = {"header": dict(self.HEADER, Referer=watchPage)}
        sts, data = self.cm.getPage(playerUrl, params)
        if not sts:
            printDBG("MajedKoora: player page HTTP %s" % self.cm.meta.get("status_code", 0))
            return "", {}
        auth = self.cm.ph.getSearchGroups(data, r"""name=['"]majed-player-authorization['"]\s+content=['"]([^'"]+)['"]""")[0]
        channel = self.cm.ph.getSearchGroups(playerUrl, r"[?&](?:channel|id)=([^&#]+)")[0]
        if not auth or not channel:
            return "", {}
        api = re.sub(r"[^/]*$", "", playerUrl.split("?", 1)[0]) + "api/stream.php?id=" + channel
        params = {"header": dict(self.HEADER, Referer=playerUrl, Accept="application/json", **{"X-Player-Authorization": auth})}
        js = self._json(api, params)
        try:
            cipher = python_aesgcm.new(bytearray(hashlib.sha256(STREAM_AAD + b"|" + auth.encode("utf-8")).digest()))
            plain = cipher.open(bytearray(b64urlDecode(js["iv"], binary=True)),
                                bytearray(b64urlDecode(js["data"], binary=True) + b64urlDecode(js["tag"], binary=True)), bytearray(STREAM_AAD))
            stream = json_loads(bytes(plain).decode("utf-8")) if plain else {}
        except Exception:
            printExc()
            return "", {}
        return stream.get("url", ""), stream.get("requestHeaders") or (stream.get("drm") or {}).get("requestHeaders") or {}

    def _streamLinks(self, url, meta):
        meta = dict(meta, iptv_livestream=True)
        path = url.split("?", 1)[0].lower()
        if path.endswith(".mpd"):
            return getMPDLinksWithMeta(strwithmeta(url, meta), False, sortWithMaxBandwidth=99999999)
        if path.endswith(".mp4"):
            return [{"name": _domain(url), "url": strwithmeta(url, meta)}]
        meta["iptv_proto"] = "m3u8"
        return requireDownloaderForDisguisedHls(getDirectM3U8Playlist(strwithmeta(url, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999))

    def _pageStream(self, url):
        # an iframe page without a parser: the first stream address in it
        origin = "https://%s" % _domain(url)
        srcId = self.cm.ph.getSearchGroups(url, r"\?(\d+)$")[0]
        if srcId and "good" in _domain(url):
            # the "good" players: <domain>/api/player?src=<id> -> {"sources": {"master": hls}}
            master = (self._json("%s/api/player?src=%s" % (origin, srcId)).get("sources") or {}).get("master", "")
            if self.cm.isValidUrl(master):
                return self._streamLinks(master, {"User-Agent": self.HEADER.get("User-Agent"), "Referer": url, "Origin": origin})
        sts, data = self.cm.getPage(url, {"header": dict(self.HEADER, Referer=self.MAIN_URL)})
        if not sts:
            return []
        stream = self.cm.ph.getSearchGroups(data, r"""(https?:)?(//[^"'\s<>\\]+?\.(?:m3u8|mpd)(?:\?[^"'\s<>\\]*)?)["'\s]""", 2)[1]
        if not stream:
            return []
        return self._streamLinks("https:" + stream, {"User-Agent": self.HEADER.get("User-Agent"), "Referer": origin + "/", "Origin": origin})

    def getVideoLinks(self, videoUrl):
        printDBG("MajedKoora.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        meta = getattr(videoUrl, "meta", {})
        serverType = meta.get("mk_type", "")
        url = str(videoUrl)
        headers = {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL, "Origin": self.MAIN_URL[:-1]}
        if serverType == "majed_player" or re.search(r"[?&]channel=", url):
            playerOrigin = "https://%s" % _domain(url)
            url, extra = self._majedPlayer(url, meta.get("mk_page") or self.MAIN_URL)
            # the stream hosts check the player's origin (majedcss: 403 "origin denied" for majed-koora.live)
            headers.update({"Referer": playerOrigin + "/", "Origin": playerOrigin})
            headers.update(dict((k, v) for k, v in extra.items() if k in ("User-Agent", "Referer", "Origin")))
            links = self._streamLinks(url, headers) if self.cm.isValidUrl(url) else []
        elif serverType in DIRECT_TYPES:
            links = self._streamLinks(url, headers)
        elif self.up.checkHostSupport(url) == 1:
            links = self.up.getVideoLinkExt(strwithmeta(url, {"Referer": self.MAIN_URL}))
        else:
            links = self._pageStream(url)
        if not links:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        match = self._findMatch(cItem)
        info = {}
        if match:
            rows = self._info(match)
            for key, _label, value in rows:
                info[key] = value
            home, away = match.get("home_team") or {}, match.get("away_team") or {}
            text = "[/br]".join(["%s - %s" % (home.get("name", ""), away.get("name", ""))] + ["%s: %s" % (label, value) for _key, label, value in rows])
        else:
            text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("MajedKoora.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if refresh or name is None:
            self.cache = {}  # live data: fresh on every refresh / new start
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "mk_day":
            self.listDay(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MajedKoora(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "mk_match"
