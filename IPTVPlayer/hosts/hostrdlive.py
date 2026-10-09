# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - RDaily (rdaily.live, live sport): the matches come from the site's Flashscore feed
#     (1.newsoccers.one/2/x/feed/f_<sport>_0_1_en_1, X-Fsign of the site), only those the site has
#     streams for are listed (rdaily.live/api/v1/<sport>/<local date>), live ones first, then the
#     upcoming ones of the day by start time; finished matches are left out
#   - links: rdaily.live/api/v1/match/FS:<id> -> custom_urls (32-hex tokens) -> iplayer.is/beta/<token>
#     (needs the rdaily referer, else it redirects to google) -> STREAM_URL (HLS); the site opens a
#     stream 10 minutes before the start, until then the playlist answers 404
#   - some streams send their segments as PNG images on the TikTok CDN with the MPEG-TS behind a small
#     image head: requireDownloaderForDisguisedHls sends those to the curl-impersonate helper, which
#     cuts the head off (the others are plain .ts)
#   - removed: the proxy / alternative domain options, the stale assets/sports-feed.json (last update
#     27.09.2026) for the sport list, ParseColor / MessageBox, the remote mohamed_os icon
# 09.10.2026 (box log): some servers (the "... PT Q" ones: Sport TV / Canal 11 PT) open an obfuscated bitmovin
#     player page without STREAM_URL (the stream address only behind ~54 KB of obfuscated script): the player
#     pages are checked when the link list is built and only the ones with a STREAM_URL are offered
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, requireDownloaderForDisguisedHls
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://rdaily.live/"


FEED_URL = "https://1.newsoccers.one/2/x/feed/f_%s_0_1_en_1"
FEED_SIGN = "SW9D1eZo"  # X-Fsign of the site's main.js
PLAYER_URL = "https://iplayer.is/beta/"
IMAGE_URL = "https://static.flashscore.com/res/image/data/"
STATUS_LIVE, STATUS_SCHEDULED = "2", "1"


def _sports():
    # the site's sport menu: (API slug, Flashscore sport id, title)
    return (("football", 1, _("Football")), ("basketball", 3, _("Basketball")), ("tennis", 2, _("Tennis")), ("hockey", 4, _("Hockey")),
            ("volleyball", 12, _("Volleyball")), ("handball", 7, _("Handball")), ("futsal", 11, _("Futsal")),
            ("american-football", 5, _("American football")), ("mma", 28, "MMA"), ("boxing", 16, _("Boxing")),
            ("motorsport", 31, _("Motorsport")), ("snooker", 15, _("Snooker")), ("darts", 14, _("Darts")), ("cricket", 13, _("Cricket")),
            ("winter-sports", 37, _("Winter sports")))


class RdLive(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "rdlive", "cookie": "rdlive.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/rdlive135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    ###################################################
    # helpers
    ###################################################
    def _params(self, **header):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, **header)
        return params

    def _getJson(self, url):
        sts, data = self.cm.getPage(url, self._params(Accept="application/json", Referer=self.MAIN_URL))
        if sts:
            try:
                return json_loads(data)
            except Exception:
                printExc()
        return {}

    @staticmethod
    def _parseFeed(data):
        # Flashscore feed: records split by "~", fields by "¬", key/value by "÷" (UTF-8 literals: bytes on py2, text
        # on py3 - like the page data); a "ZA" record names the tournament of the "AA" (match) records after it
        matches = []
        tournament = {}
        for record in data.split("~"):
            fields = {}
            for item in record.split("¬"):
                if "÷" in item:
                    key, value = item.split("÷", 1)
                    fields[key] = value
            if "ZA" in fields:
                tournament = fields
            elif "AA" in fields:
                fields["_tournament"] = tournament.get("ZA", "")
                fields["_tournament_icon"] = tournament.get("OAJ", "")
                matches.append(fields)
        return matches

    @staticmethod
    def _localTime(timestamp, fmt="%H:%M"):
        return time.strftime(fmt, time.localtime(timestamp)) if timestamp else ""

    def _matchInfo(self, match):
        # [(label, value)] for desc / INFO
        start = int(match.get("AD", "0") or 0)
        rows = [(_("Category"), match.get("_tournament", "")), (_("Start"), self._localTime(start, "%d.%m.%Y %H:%M"))]
        if match.get("AB") == STATUS_LIVE and match.get("AG", "") != "" and match.get("AH", "") != "":
            rows.append((_("Live"), "%s : %s" % (match["AG"], match["AH"])))
        return [row for row in rows if row[1]]

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        for slug, sportId, title in _sports():
            self.addDir({"name": "category", "category": "rd_sport", "title": title, "sport": slug, "sport_id": sportId, "good_for_fav": True})

    def listMatches(self, cItem):
        sts, data = self.cm.getPage(FEED_URL % cItem["sport_id"], self._params(Referer=self.MAIN_URL, **{"X-Fsign": FEED_SIGN}))
        if not sts:
            return
        api = self._getJson(self.getFullUrl("/api/v1/%s/%s" % (cItem["sport"], time.strftime("%Y-%m-%d"))))
        withStreams = set(item.get("match_id", "").replace("FS:", "") for item in api.get("items") or [] if isinstance(item, dict))
        matches = [m for m in self._parseFeed(data) if m["AA"] in withStreams and m.get("AB") in (STATUS_LIVE, STATUS_SCHEDULED)]
        matches.sort(key=lambda m: (m.get("AB") != STATUS_LIVE, int(m.get("AD", "0") or 0)))
        for match in matches:
            name = "%s - %s" % (match.get("CX", ""), match.get("AF", ""))
            start = self._localTime(int(match.get("AD", "0") or 0))
            title = "%s - %s" % (_("Live") if match.get("AB") == STATUS_LIVE else start, name)
            icon = match.get("_tournament_icon") or match.get("OA", "")
            info = self._matchInfo(match)
            desc = " | ".join("%s%s:%s %s" % (E2ColoR("yellow"), label, E2ColoR("white"), value) for label, value in info)
            self.addVideo({"name": "category", "category": "rd_match", "good_for_fav": True, "title": title, "match_id": match["AA"],
                           "sport": cItem["sport"], "url": self.getFullUrl("/match/%s/%s" % (cItem["sport"], match["AA"])),
                           "icon": IMAGE_URL + icon if icon else self.DEFAULT_ICON_URL, "desc": desc,
                           "info": ["%s: %s" % row for row in info]})
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No stream available"))

    ###################################################
    # links
    ###################################################
    def _streams(self, cItem):
        data = self._getJson(self.getFullUrl("/api/v1/match/FS:%s" % cItem.get("match_id", "")))
        return [s for s in data.get("custom_urls") or [] if isinstance(s, dict) and s.get("enabled", True) and
                len(s.get("url", "")) == 32 and all(c in "0123456789abcdef" for c in s["url"])]

    def getLinksForVideo(self, cItem):
        printDBG("RdLive.getLinksForVideo [%s]" % cItem.get("match_id", ""))
        urltab = []
        referer = cItem.get("url", self.MAIN_URL)
        for stream in self._streams(cItem):
            url = PLAYER_URL + stream["url"]
            if not self._streamUrl(url, referer):
                printDBG("RdLive: no STREAM_URL in the player page [%s]" % url)
                continue
            urltab.append({"name": stream.get("name") or "%s %d" % (_("Server"), len(urltab) + 1),
                           "url": strwithmeta(url, {"Referer": referer}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), ""))

    def _streamUrl(self, playerUrl, referer):
        # the player page answers only with the site as referer (else a redirect to google)
        sts, data = self.cm.getPage(playerUrl, self._params(Referer=referer))
        return self.cm.ph.getSearchGroups(data, r'STREAM_URL\s*=\s*"([^"]+)"')[0].replace("\\/", "/") if sts else ""

    def getVideoLinks(self, videoUrl):
        printDBG("RdLive.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        referer = videoUrl.meta.get("Referer", self.MAIN_URL) if hasattr(videoUrl, "meta") else self.MAIN_URL
        hlsUrl = self._streamUrl(str(videoUrl), referer)
        links = []
        if self.cm.isValidUrl(hlsUrl):
            meta = {"iptv_proto": "m3u8", "iptv_livestream": True, "User-Agent": self.HEADER["User-Agent"],
                    "Referer": "https://iplayer.is/", "Origin": "https://iplayer.is"}
            links = requireDownloaderForDisguisedHls(getDirectM3U8Playlist(strwithmeta(hlsUrl, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999))
        if not links:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        lines = [cItem.get("title", "")] + list(cItem.get("info") or [])
        streams = [s.get("name", "") for s in self._streams(cItem) if s.get("name")]
        if streams:
            lines.append("%s: %s" % (_("Channel"), ", ".join(streams)))
        icon = cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": "[/br]".join(line for line in lines if line),
                 "images": [{"title": "", "url": icon}] if icon else [], "other_info": {}}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("RdLive.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "rd_sport":
            self.listMatches(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, RdLive(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "rd_match"
