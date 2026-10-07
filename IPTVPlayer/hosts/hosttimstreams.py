# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# Ported to the python3 framework (06.10.2026):
#   - TimStreams (timst.top, mirror tim-streams.com - the site's own fallback): the JSON API
#     <domain>/api/channels | /api/live-upcoming | /api/replays
#   - live TV channels per genre (the API's genres, local paging), events (start time converted from
#     America/New_York to the box time, "Live" once started), replays (VOD, watched flag)
#   - grandemx.org players: the page evals an XOR-obfuscated script holding SIGNED_URL (HLS) - decoded
#     here; other stream urls (voe.sx ... on replays) go through urlparser; VIP streams are marked
#   - favourites re-open from the API (stored streams as fallback), INFO with the site's event info
#   - removed: the unused AES-GCM SECRET_KEY / decrypt_url, the unused *.pages.dev worker url and the
#     dead api.vixnuvew.uk base (NXDOMAIN), the hard-coded genre table (the API sends its own)
import calendar
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, requireDownloaderForDisguisedHls
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR, GetIconDir, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://timst.top/"


MIRROR_URL = "https://tim-streams.com/"
PAGE_SIZE = 100
# kind -> (API endpoint, list key)
API = {"channel": ("channels", "channels"), "event": ("live-upcoming", "events"), "replay": ("replays", "replays")}
ROW_CATEGORY = {"channel": "ts_channel", "event": "ts_event", "replay": "ts_replay"}
VIDEO_CATEGORIES = tuple(ROW_CATEGORY.values())
# ((array[i] ^ xor) - sub + 256) % 256 of the grandemx.org player script
DECODE_RE = re.compile(r"\(\(\s*(\w+)\s*\[\s*\w+\s*\]\s*\^\s*(\w+)\s*\)\s*-\s*(\w+)\s*\+\s*256\s*\)\s*%\s*256")


def _domain(url):
    m = re.match(r"^https?://(?:www\.)?([^/:?#]+)", url or "")
    return m.group(1).lower() if m else ""


def _nthSunday(year, month, nth):
    # day of the month of the nth Sunday (calendar: Monday = 0)
    first = (6 - calendar.weekday(year, month, 1)) % 7 + 1
    return first + 7 * (nth - 1)


def _etToTimestamp(value):
    # "2026-10-06T14:45" in America/New_York (EDT from the 2nd Sunday of March to the 1st Sunday of November) -> UTC timestamp
    m = re.match(r"^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)", value or "")
    if not m:
        return 0
    year, month, day, hour, minute = [int(x) for x in m.groups()]
    dstStart = (3, _nthSunday(year, 3, 2), 2)
    dstEnd = (11, _nthSunday(year, 11, 1), 2)
    offset = 4 if dstStart <= (month, day, hour) < dstEnd else 5
    return calendar.timegm((year, month, day, hour, minute, 0)) + offset * 3600


class TimStreams(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "kind", "slug", "streams")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "timstreams", "cookie": "timstreams.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/timstreams135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.apiCache = {}
        self.watchedHelper = IPTVWatchedHelper("timstreams")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def _getApi(self, kind):
        # {"channels"|"events"|"replays": [...], "genres": [...]} of the current domain, else of the mirror
        if kind in self.apiCache:
            return self.apiCache[kind]
        endpoint = API[kind][0]
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Accept="application/json", Referer=self.MAIN_URL)
        for domain in [self.MAIN_URL] + [d for d in (gettytul(), MIRROR_URL) if d != self.MAIN_URL]:
            sts, data = self.cm.getPage(domain + "api/" + endpoint, params)
            if not sts:
                continue
            try:
                data = json_loads(data)
            except Exception:
                printExc()
                continue
            if isinstance(data, dict) and isinstance(data.get(API[kind][1]), list):
                if domain != self.MAIN_URL:
                    printDBG("TimStreams: switching to %s" % domain)
                    self.MAIN_URL = domain
                self.apiCache[kind] = data
                return data
        return {}

    @staticmethod
    def _genres(data):
        # {id: name} incl. sub categories
        genres = {}
        for genre in data.get("genres") or []:
            if isinstance(genre, dict):
                genres[genre.get("id")] = genre.get("name", "")
                for sub in genre.get("sub_categories") or []:
                    if isinstance(sub, dict):
                        genres[("sub", sub.get("id"))] = sub.get("name", "")
        return genres

    @staticmethod
    def _localTime(timestamp, fmt="%d.%m. %H:%M"):
        return time.strftime(fmt, time.localtime(timestamp)) if timestamp else ""

    def _icon(self, url):
        url = (url or "").replace("&amp;", "&").strip()
        if not url.startswith("http"):
            return ""
        return strwithmeta(url, {"User-Agent": self.HEADER.get("User-Agent")})

    def _streams(self, entry):
        return [{"name": s.get("name") or "%s %d" % (_("Server"), idx + 1), "url": s.get("url", ""), "vip": bool(s.get("vip"))}
                for idx, s in enumerate(s for s in entry.get("streams") or [] if isinstance(s, dict) and s.get("url"))]

    def _info(self, kind, entry, genres):
        # [(INFO key, label, value)] of an API entry for desc / INFO
        rows = [("genre", _("Genre"), genres.get(entry.get("genre"), ""))]
        if entry.get("sub_genre"):
            rows.append(("category", _("Category"), genres.get(("sub", entry.get("sub_genre")), "")))
        if kind == "event":
            rows.append(("broadcast", _("Start"), self._localTime(_etToTimestamp(entry.get("time")), "%d.%m.%Y %H:%M")))
        elif kind == "replay":
            rows.append(("released", _("Date"), entry.get("date", "")))
        if entry.get("flag"):
            rows.append(("country", _("Country"), entry["flag"].upper()))
        rows.append(("source", _("Server"), ", ".join(s["name"] + (" (VIP)" if s["vip"] else "") for s in self._streams(entry))))
        return [row for row in rows if row[2]]

    def _row(self, kind, entry, genres):
        slug = entry.get("url", "")
        name = (entry.get("name") or "").strip()
        if not slug or not name:
            return None
        title = name
        if kind == "event":
            start = _etToTimestamp(entry.get("time"))
            title = "%s - %s" % (_("Live") if start <= time.time() else self._localTime(start), name) if start else name
        desc = " | ".join(["%s%s:%s %s" % (E2ColoR("yellow"), label, E2ColoR("white"), value) for _key, label, value in self._info(kind, entry, genres)])
        return {"name": "category", "category": ROW_CATEGORY[kind], "good_for_fav": True, "title": title, "kind": kind, "slug": slug,
                "url": "%swatch/%s" % (self.MAIN_URL, slug), "icon": self._icon(entry.get("logo")), "desc": desc,
                "streams": self._streams(entry)}

    def _findEntry(self, cItem):
        kind = cItem.get("kind", "")
        if kind not in API:
            return {}, {}
        data = self._getApi(kind)
        for entry in data.get(API[kind][1], []):
            if isinstance(entry, dict) and entry.get("url") == cItem.get("slug"):
                return entry, self._genres(data)
        return {}, self._genres(data)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES:
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag (replays only - channels and events are live)
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        if isinstance(cItem, dict) and cItem.get("category") == "ts_replay" and cItem.get("slug"):
            return "video:replay/%s" % cItem["slug"]
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        self.listsTab([{"category": "ts_genres", "title": _("Channels"), "kind": "channel"},
                       {"category": "ts_list", "title": _("Events"), "kind": "event"},
                       {"category": "ts_list", "title": _("Replay"), "kind": "replay"}], cItem)

    def listGenres(self, cItem):
        data = self._getApi("channel")
        channels = [c for c in data.get("channels", []) if isinstance(c, dict)]
        genres = self._genres(data)
        self.addDir({"name": "category", "category": "ts_list", "title": "%s (%d)" % (_("All"), len(channels)), "kind": "channel", "genre": "", "good_for_fav": True})
        for genreId, genreName in genres.items():
            if isinstance(genreId, tuple):
                continue
            count = len([c for c in channels if c.get("genre") == genreId])
            if count:
                self.addDir({"name": "category", "category": "ts_list", "title": "%s (%d)" % (genreName, count), "kind": "channel", "genre": genreId, "good_for_fav": True})

    def listItems(self, cItem):
        kind = cItem.get("kind", "")
        page = cItem.get("page", 1)
        data = self._getApi(kind)
        genres = self._genres(data)
        entries = [e for e in data.get(API[kind][1], []) if isinstance(e, dict)]
        if kind == "channel" and cItem.get("genre", "") != "":
            entries = [e for e in entries if e.get("genre") == cItem["genre"]]
        if kind == "event":
            entries.sort(key=lambda e: e.get("time", ""))
        rows = [r for r in (self._row(kind, e, genres) for e in entries) if r]
        lastPage = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
        for row in rows[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]:
            self.addVideo(row)
        addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("TimStreams.getLinksForVideo [%s]" % cItem.get("slug", ""))
        entry = self._findEntry(cItem)[0]
        streams = self._streams(entry) if entry else cItem.get("streams", [])
        urltab = []
        for stream in streams:
            name = "%s (VIP)" % stream["name"] if stream.get("vip") else stream["name"]
            urltab.append({"name": "%s - %s" % (name, _domain(stream["url"])), "url": strwithmeta(stream["url"], {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), ""))

    def _decodePlayer(self, data):
        # (function(){var _a=[49,39,...],_b=71,_c=214,_s="",_i;for(...){_s+=String.fromCharCode(((_a[_i]^_b)-_c+256)%256);}window["ev"+"al"](_s);})()
        # names and numbers change on every request: the formula names the array and the two constants
        # (variables declared anywhere in the page, or literal numbers)
        formula = DECODE_RE.search(data)
        if not formula:
            return ""
        values = [self.cm.ph.getSearchGroups(data, r"\b%s\s*=\s*\[([\d,\s]+)\]" % re.escape(formula.group(1)))[0]]
        for token in formula.group(2, 3):
            values.append(token if token.isdigit() else self.cm.ph.getSearchGroups(data, r"\b%s\s*=\s*(\d+)\b" % re.escape(token))[0])
        if not all(values):
            return ""
        xorC, subC = int(values[1]), int(values[2])
        return "".join(chr(((int(v) ^ xorC) - subC) % 256) for v in values[0].split(",") if v.strip())

    def _resolvePlayer(self, videoUrl):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self.MAIN_URL)
        sts, data = self.cm.getPage(videoUrl, params)
        if not sts:
            return []
        script = self._decodePlayer(data)
        hlsUrl = self.cm.ph.getSearchGroups(script, r"SIGNED_URL\s*=\s*[\"']([^\"']+)[\"']")[0] or self.cm.ph.getSearchGroups(data, r"data-signed-url=[\"']([^\"']+)[\"']")[0]
        if not self.cm.isValidUrl(hlsUrl):
            return None  # not this player
        playerUrl = "https://%s/" % _domain(self.cm.meta.get("url", "") or str(videoUrl))
        meta = {"iptv_proto": "m3u8", "iptv_livestream": True, "User-Agent": self.HEADER.get("User-Agent"), "Referer": playerUrl, "Origin": playerUrl[:-1]}
        # fix 071026: the segments are WEBP images with the MPEG-TS data behind (box log 07.10. #4, no player opened
        # them) - the check sends such streams to the curl-impersonate helper, which cuts the image header off
        return requireDownloaderForDisguisedHls(getDirectM3U8Playlist(strwithmeta(hlsUrl, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999))

    def getVideoLinks(self, videoUrl):
        printDBG("TimStreams.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if self.up.checkHostSupport(videoUrl) == 1:
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        links = self._resolvePlayer(videoUrl)
        if links is None:
            # an unknown player page: let urlparser try its generic way
            links = self.up.getVideoLinkExt(videoUrl)
        if not links:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        entry, genres = self._findEntry(cItem)
        info = {}
        if entry:
            rows = self._info(cItem.get("kind", ""), entry, genres)
            for key, _label, value in rows:
                info[key] = value
            if entry.get("viewers") is not None:
                info["views"] = str(entry["viewers"])
            text = "[/br]".join([entry.get("name", "")] + ["%s: %s" % (label, value) for _key, label, value in rows])
        else:
            text = StripColorCodes(cItem.get("desc", "")).replace(" | ", "[/br]")
        icon = cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("TimStreams.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if refresh or name is None:
            self.apiCache = {}  # live data: fresh on every refresh / new start
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "ts_genres":
            self.listGenres(self.currItem)
        elif category == "ts_list":
            self.listItems(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, TimStreams(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("timstreams")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES
