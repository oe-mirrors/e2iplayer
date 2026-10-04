# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - Last.fm (last.fm), new host
#   Last.fm radio stations as track lists, played through YouTube (the station's own YouTube playlink,
#   else the first YouTube search hit): artist top tracks, similar-artists mix, similar artists,
#   user library / mix / recommendations (search by user or set a Last.fm user name in the host options).
#   Only www.last.fm/player/station/... answers without the site's JavaScript "Client Challenge" -
#   charts, tag pages and the site search are behind it, so artists are found by their exact name.
#   Tracks: video rows (YouTube) with watched flag + downloaded marker keyed on the Last.fm track page, sidecar.
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.youtubeparser import YouTubeParser
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Components.config import config, ConfigText, getConfigListEntry

config.plugins.iptvplayer.lastfm_user = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Last.fm user name:"), config.plugins.iptvplayer.lastfm_user)]


def gettytul():
    return "https://www.last.fm/"


class LastFM(GenericFolderWatchedScraperMixin, CBaseHostClass):
    STATION = "https://www.last.fm/player/station/%s?ajax=1"
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "station", "artist", "track", "yt_url", "duration")
    SEARCH_TYPES = [(_("Artist"), "artist"), (_("User"), "user")]

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "lastfm", "cookie": "lastfm.cookie"})
        self.MAIN_URL = "https://www.last.fm/"
        self.DEFAULT_ICON_URL = "https://www.last.fm/static/images/lastfm_avatar_twitter.52a5d69a85ac.png"
        self.HEADER = {"User-Agent": self.cm.getDefaultUserAgent(), "Accept": "application/json, text/javascript, */*; q=0.01",
                       "X-Requested-With": "XMLHttpRequest", "Referer": self.MAIN_URL}
        self.defaultParams = {"header": self.HEADER}
        self.watchedHelper = IPTVWatchedHelper("lastfm")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("type") == "video":
                url = self.wfNormalizeUrlKey(cItem.get("url", ""))
                return "video:%s" % url if url else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _station(self, path):
        # path: "music/<artist>", "music/<artist>/+similar", "user/<name>/library|mix|recommended"
        sts, data = self.getPage(self.STATION % path)
        if not sts or not data:
            return None
        try:
            playlist = ensure_str_deep(json_loads(data)).get("playlist")
            return playlist if isinstance(playlist, list) else None
        except Exception:
            printExc()
        return None

    @staticmethod
    def _quote(name):
        return urllib_quote_plus(name)

    @staticmethod
    def _duration(secs):
        try:
            secs = int(secs or 0)
        except Exception:
            secs = 0
        return "%d:%02d" % (secs // 60, secs % 60) if secs > 0 else ""

    ###################################################
    # lists
    ###################################################
    def listMain(self, cItem):
        user = config.plugins.iptvplayer.lastfm_user.value.strip()
        if user:
            self._userMenu(cItem, user, prefix=True)
        else:
            self.addMarker({"title": _("Search for an artist (exact name) or a Last.fm user"),
                            "desc": _("Last.fm charts and tag pages are behind a browser check, only the radio stations can be used.")})
        self.listsTab(self.searchItems(), cItem)

    def _userMenu(self, cItem, user, prefix=False):
        for sub, title in (("library", _("Library")), ("mix", _("Mix")), ("recommended", _("Recommended"))):
            params = dict(cItem)
            params.update({"category": "list_station", "title": ("%s: %s" % (user, title)) if prefix else title,
                           "station": "user/%s/%s" % (self._quote(user), sub), "good_for_fav": True,
                           "url": "https://www.last.fm/user/%s" % self._quote(user)})
            self.addDir(params)

    def _artistMenu(self, cItem, artist, artistPath):
        for station, title in (("music/%s" % artistPath, _("Top tracks")), ("music/%s/+similar" % artistPath, _("Similar artists mix"))):
            params = dict(cItem)
            params.update({"category": "list_station", "title": "%s - %s" % (artist, title), "station": station,
                           "artist": artist, "url": "https://www.last.fm/music/%s" % artistPath, "good_for_fav": True})
            self.addDir(params)
        params = dict(cItem)
        params.update({"category": "list_similar", "title": "%s - %s" % (artist, _("Similar artists")),
                       "station": "music/%s/+similar" % artistPath, "artist": artist,
                       "url": "https://www.last.fm/music/%s/+similar" % artistPath, "good_for_fav": True})
        self.addDir(params)

    def listArtist(self, cItem):
        self._artistMenu(cItem, cItem.get("artist", ""), cItem.get("artist_path", ""))

    def listStation(self, cItem):
        playlist = self._station(cItem.get("station", ""))
        if playlist is None:
            SetIPTVPlayerLastHostError(_("No matching entries found."))
            return
        for track in playlist:
            try:
                name = self.cleanHtmlStr(track.get("name") or track.get("_name") or "")
                artists = [self.cleanHtmlStr(a.get("name") or "") for a in (track.get("artists") or []) if isinstance(a, dict)]
                artist = ", ".join([a for a in artists if a])
                url = track.get("url") or ""
                if not name or not url:
                    continue
                ytUrl = ""
                ytId = ""
                for link in (track.get("playlinks") or track.get("_playlinks") or []):
                    if isinstance(link, dict) and link.get("affiliate") == "youtube" and link.get("url"):
                        ytUrl, ytId = link["url"], link.get("id") or ""
                        break
                duration = self._duration(track.get("duration"))
                self.addVideo({"good_for_fav": True, "title": "%s - %s" % (artist, name) if artist else name,
                               "url": "https://www.last.fm" + url, "artist": artist, "track": name, "yt_url": ytUrl,
                               "duration": duration, "icon": "https://i.ytimg.com/vi/%s/hqdefault.jpg" % ytId if ytId else "",
                               "desc": " | ".join([x for x in (artist, duration) if x])})
            except Exception:
                printExc()

    def listSimilar(self, cItem):
        playlist = self._station(cItem.get("station", ""))
        if playlist is None:
            return
        seen = set([cItem.get("artist", "").lower()])
        for track in playlist:
            for a in (track.get("artists") or []):
                if not isinstance(a, dict):
                    continue
                name = self.cleanHtmlStr(a.get("name") or "")
                path = (a.get("url") or "").replace("/music/", "", 1).strip("/")
                if not name or not path or name.lower() in seen:
                    continue
                seen.add(name.lower())
                params = dict(cItem)
                params.update({"category": "list_artist", "title": name, "artist": name, "artist_path": path,
                               "url": "https://www.last.fm/music/" + path, "good_for_fav": True})
                self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = (searchPattern or "").strip()
        if not pattern:
            return
        if searchType == "user":
            if self._station("user/%s/library" % self._quote(pattern)) is None:
                SetIPTVPlayerLastHostError(_("Last.fm user \"%s\" not found.") % pattern)
                return
            self._userMenu(cItem, pattern)
            return
        path = self._quote(pattern)
        playlist = self._station("music/%s" % path)
        if playlist is None:
            SetIPTVPlayerLastHostError(_("Artist \"%s\" not found on Last.fm - the exact artist name is needed.") % pattern)
            return
        artist = pattern
        for track in playlist:
            for a in (track.get("artists") or []):
                if isinstance(a, dict) and (a.get("name") or "").lower() == pattern.lower():
                    artist = a["name"]
                    path = (a.get("url") or "").replace("/music/", "", 1).strip("/") or path
                    break
            else:
                continue
            break
        self._artistMenu(cItem, artist, path)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("LastFM.getLinksForVideo [%s]" % cItem.get("url", ""))
        ytUrl = cItem.get("yt_url", "")
        if not ytUrl:
            # no playlink on Last.fm - the first YouTube search hit for "artist track"
            query = ("%s %s" % (cItem.get("artist", ""), cItem.get("track", ""))).strip() or cItem.get("title", "")
            try:
                for item in YouTubeParser().getSearchResult(urllib_quote_plus(query), "video", 1, ""):
                    if item.get("type") == "video" and "watch?v=" in (item.get("url") or ""):
                        ytUrl = item["url"]
                        break
            except Exception:
                printExc()
        if not ytUrl:
            SetIPTVPlayerLastHostError(_("No YouTube video found for this track."))
            return []
        return applySidecarToLinks([{"name": "YouTube", "url": ytUrl, "need_resolve": 1}], buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, url):
        printDBG("LastFM.getVideoLinks [%s]" % url)
        if not self.cm.isValidUrl(url):
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecarFromUrlMeta(url, IsSidecarEnabled()))

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        otherInfo = {}
        if cItem.get("artist"):
            otherInfo["creator"] = cItem["artist"]
        if cItem.get("duration"):
            otherInfo["duration"] = cItem["duration"]
        icon = cItem.get("icon", "")
        return [{"title": cItem.get("track") or cItem.get("title", ""), "text": cItem.get("desc", ""),
                 "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("type") == "video" or cItem.get("category") in ("list_station", "list_similar", "list_artist"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS + ("artist_path",) if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("LastFM.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({"name": "category"})
        elif category == "list_station":
            self.listStation(self.currItem)
        elif category == "list_similar":
            self.listSimilar(self.currItem)
        elif category == "list_artist":
            self.listArtist(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, LastFM(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("lastfm")

    def getSearchTypes(self):
        return self.host.SEARCH_TYPES

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video"
