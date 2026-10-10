# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# =========== Created by angel_heart (Mohamed Elsafty) ======== 20260801
# 24.08.2026 - Fixed search (search_item was False), switched to
# searchItems()/listsHistory() pattern, added watched/started flag support,
# removed duplicated link-building code
# 10.10.2026 - links: the watch page has no window.__OPT server list any more, the servers are a form
# (/api/go?t=..&slug=..[&s=..&e=..]&x=N -> embed url of server N, like vumoo of the same network); the site's
# "Quick check" page is passed like the vumoo host does it
import hashlib
import struct

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase, RetHost
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary, ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhostmixin import WatchedFlagHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
import re


_SERIES_SUFFIX_RE = re.compile(r"\s*[-–]\s*Season\s+\d+\s*$", re.I)
_EP_STATUS_RE = re.compile(r"\s*\((?:trailer only|coming soon|not released|no source)\)\s*$", re.I)


def _cleanSeriesTitle(title):
    return _SERIES_SUFFIX_RE.sub("", title or "").strip()


# servers of the site that urlparser resolves, best first: (label of the site's button, lowercase), needs enc-dec.app
SERVERS = (("vidsrc.mov", False), ("vidsrc-v1", False), ("vidrock", False), ("vixsrc", False), ("vidlink", False),
           ("vidsrc.fyi", False), ("vidnest", False), ("peachify", False),
           ("vidfast", True), ("vidup", True), ("vidcore-v2", True))
# their numbers on 10.10.2026, used when the server list cannot be read from the page
SERVER_FALLBACK = (("0", "vidsrc.mov"), ("5", "vidrock"), ("7", "vidlink"), ("1", "vidsrc.fyi"), ("6", "vidnest"))
WATCH_RE = re.compile(r"/watch/((movie|tv)-[^/?#]+)")


def GetConfigList():
    return []


def gettytul():
    return "https://cineb.sx/"


class Cineb(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Cineb", "cookie": "Cineb.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        # hv / hv2 are set by the script of the "Quick check" page, hv3 comes from the server
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE,
                              "cookie_items": {"hv": "1", "hv2": "1"}}
        self.MAIN_URL = "https://cineb.sx"
        self.DEFAULT_ICON_URL = self.MAIN_URL + "/assets/brands/cineb/favicon.png"
        self.cacheSeasons = {}
        self.cacheEpisodes = {}
        self.watchedHelper = IPTVWatchedHelper("cineb")
        self.MAIN_CAT_TAB = [
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/movie")},
            {"category": "list_items", "title": _("TV Series"), "url": self.getFullUrl("/tv")},
            {"category": "list_items", "title": _("Top IMDb"), "url": self.getFullUrl("/top-imdb")},
            {"category": "list_items", "title": _("Updates"), "url": self.getFullUrl("/updates")},
            {"category": "list_genres", "title": _("Genres")},
            {"category": "list_countries", "title": _("Countries")},
        ] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        else:
            if "header" not in addParams:
                addParams["header"] = dict(self.HEADER)
        addParams["header"]["Referer"] = self.MAIN_URL
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        if sts and self._isGate(data):
            if self._passGate(baseUrl):
                sts, data = self.cm.getPageCFProtection(baseUrl, dict(addParams), post_data)
            if sts and self._isGate(data):
                printDBG("Cineb: still the quick check page [%s]" % baseUrl)
                return False, ""
        return sts, data

    @staticmethod
    def _isGate(data):
        return "<title>Quick check" in (data or "")[:2000]

    def _passGate(self, url):
        # what the script of the check page does: GET <path>?__hvtok=1&s=1 -> {"seed", "bits"}, find n with
        # sha256("seed:n") below 2^(32-bits), GET <path>?__hvtok=1&seed=..&n=.. -> sets the hv3 cookie
        path = url.split("#", 1)[0].split("?", 1)[0]
        sts, data = self.cm.getPage(path + "?__hvtok=1&s=1&r=0", dict(self.defaultParams))
        query = "nc=1"
        try:
            js = json_loads(data) if sts else {}
            seed, bits = ensure_str(js.get("seed") or ""), int(js.get("bits") or 0)
            if seed and 0 < bits <= 22:
                target = 2 ** (32 - bits)
                for n in range(1, 2 ** (bits + 4)):
                    digest = hashlib.sha256(ensure_binary("%s:%d" % (seed, n))).digest()
                    if struct.unpack(">I", digest[:4])[0] < target:
                        query = "seed=%s&n=%d" % (seed, n)
                        break
        except Exception:
            printExc()
        sts, data = self.cm.getPage("%s?__hvtok=1&%s&r=0" % (path, query), dict(self.defaultParams))
        ok = sts and re.match(r"^[0-9a-f]{32}", (data or "").strip()) is not None
        printDBG("Cineb: quick check %s [%s]" % ("passed" if ok else "failed", path))
        return ok

    def _servers(self, data):
        # [(x, label)] of the urlparser-known servers on a watch page, in the order of SERVERS
        found = {}
        for x, label in re.findall(r'name="x" value="(\d+)"[^>]*>(?:\s*<i[^>]*></i>)?([^<]+)<', data or ""):
            found.setdefault(self.cleanHtmlStr(label).lower(), (x, self.cleanHtmlStr(label)))
        return [found[key] for key, _enc in SERVERS if key in found]

    def _goLinks(self, cItem, data):
        # the server form of the watch page -> /api/go links (resolved in getVideoLinks)
        url = cItem.get("url", "")
        match = WATCH_RE.search(url)
        if not match:
            return []
        slug, kind = match.group(1), match.group(2)
        season = self.cm.ph.getSearchGroups(url, r"[?&]s=(\d+)")[0]
        episode = self.cm.ph.getSearchGroups(url, r"[?&]e=(\d+)")[0]
        if kind == "tv" and not (season and episode):
            return []
        servers = self._servers(data) or list(SERVER_FALLBACK)
        try:
            from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsExternalResolveAllowed
            external = IsExternalResolveAllowed()
        except Exception:
            external = False
        needsExternal = dict(SERVERS)
        urlTab = []
        for x, label in servers:
            if needsExternal.get(label.lower()) and not external:
                continue
            goUrl = "%s/api/go?t=%s&slug=%s&x=%s" % (self.MAIN_URL, kind, slug, x)
            if kind == "tv":
                goUrl += "&s=%s&e=%s" % (season, episode)
            urlTab.append({"name": label, "url": strwithmeta(goUrl, {"Referer": url}), "need_resolve": 1})
        return urlTab

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            itemType = cItem.get("type", "")
            category = cItem.get("category", "")
            if itemType in ["video", "audio"]:
                url = str(cItem.get("url", "") or "").strip()
                if url != "":
                    return "url:%s" % url
                return ""
            if category == "list_episodes":
                url = str(cItem.get("url", "") or "").strip()
                if url != "":
                    return "season:%s" % url
                return ""
            if category == "list_seasons":
                url = str(cItem.get("url", "") or "").strip()
                if url != "":
                    return "url:%s" % url
                return ""
            return ""
        except Exception:
            printExc()
        return ""

    def _buildSeasonItem(self, seasonUrl):
        return {"category": "list_episodes", "url": seasonUrl}

    def _buildSeriesItem(self, seriesUrl):
        return {"category": "list_seasons", "url": seriesUrl}

    def _propagateEpisodeWatchedState(self, item):
        try:
            if not isinstance(item, dict):
                return
            seasonUrl = str(item.get("season_url", "") or "").strip()
            if seasonUrl == "":
                return
            seasonEpisodes = self.cacheEpisodes.get(seasonUrl, [])
            if seasonEpisodes:
                self.watchedHelper.updateParentWatchedState(self._buildSeasonItem(seasonUrl), seasonEpisodes, self._getWatchedKeyForItem)
            seriesUrl = str(item.get("series_url", "") or "").strip()
            seasonChildren = self.cacheSeasons.get(seriesUrl, [])
            if seriesUrl != "" and seasonChildren:
                seriesItem = {"category": "list_seasons", "url": seriesUrl}
                self.watchedHelper.updateParentWatchedState(seriesItem, seasonChildren, self._getWatchedKeyForItem)
        except Exception:
            printExc()

    def listItems(self, cItem):
        printDBG("Cineb.listItems")
        page = cItem.get("page", 1)
        url = cItem["url"]
        if page > 1:
            if "?" in url:
                url += "&page=%d" % page
            else:
                url += "?page=%d" % page
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = ""
        nextMatch = re.search(r'href=["\']([^"\']+page=%d)["\'][^>]*rel=["\']next["\']' % (page + 1), data)
        if nextMatch:
            nextPage = nextMatch.group(1)
        else:
            nextMatch = re.search(r'href=["\']([^"\']+page=%d)["\']' % (page + 1), data)
            if nextMatch:
                nextPage = nextMatch.group(1)
        items = re.findall(r'<a class="bf-card".*?</a>', data, re.DOTALL)
        for item in items:
            itemUrl = self.cm.ph.getSearchGroups(item, """href=['"]([^'^"]+)['"]""")[0]
            itemUrl = self.getFullUrl(itemUrl)
            title = self.cm.ph.getSearchGroups(item, """title=['"]([^'^"]+)['"]""")[0]
            if not title:
                title = self.cm.ph.getSearchGroups(item, """alt=['"]([^'^"]+)['"]""")[0]
            icon = self.cm.ph.getSearchGroups(item, """src=['"]([^'^"]+)['"]""")[0]
            icon = self.getFullIconUrl(icon)
            quality = self.cm.ph.getSearchGroups(item, """class=['"]bf-card__qual['"][^>]*>([^<]+)<""")[0].strip()
            genre = self.cm.ph.getSearchGroups(item, """class=['"]bf-card__genre['"][^>]*>([^<]+)<""")[0].strip()
            desc_parts = []
            if quality:
                desc_parts.append("\\c0000ff00%s" % quality)
            if genre:
                desc_parts.append("\\c00ffff00%s" % genre)
            desc = " | ".join(desc_parts)
            title = self.cleanHtmlStr(title)
            if not itemUrl or not title:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": itemUrl, "icon": icon, "desc": desc})
            if "/watch/tv-" in itemUrl or "/tv/" in itemUrl:
                params["category"] = "list_seasons"
                params["s_title"] = _cleanSeriesTitle(title)
                self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
                self.addDir(params)
            else:
                params["category"] = "video"
                params["type"] = "video"
                self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.pop("isWatched", None)
            params.pop("isStarted", None)
            params.update({"good_for_fav": False, "title": _("Next page"), "page": page + 1})
            self.addDir(params)

    def listGenres(self, cItem):
        printDBG("Cineb.listGenres")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        matches = re.findall(r"""href=['"](/genre/[^"']+)['"][^>]*>([^<]+)<""", data)
        for url, title in matches:
            title = self.cleanHtmlStr(title)
            if not title or title.lower() in ["home", "movies", "tv series"]:
                continue
            params = dict(cItem)
            params.update({"category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listCountries(self, cItem):
        printDBG("Cineb.listCountries")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        matches = re.findall(r"""href=['"](/country/[^"']+)['"][^>]*>([^<]+)<""", data)
        for url, title in matches:
            title = self.cleanHtmlStr(title)
            if not title:
                continue
            params = dict(cItem)
            params.update({"category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("Cineb.listSeasons")
        seriesUrl = cItem["url"]
        sts, data = self.getPage(seriesUrl)
        if not sts:
            return
        episodesSection = self.cm.ph.getDataBeetwenMarkers(data, '<section id="movie-episodes"', "</section>", False)[1]
        seasons = re.findall(r'<a[^>]+class=["\']season-pill[^"\']*["\'][^>]+href=["\']([^"\']+)["\']', episodesSection)
        if not seasons:
            self.listEpisodesFromPage(cItem, episodesSection or data, seriesUrl)
            return
        sTitle = cItem.get("s_title") or _cleanSeriesTitle(cItem.get("title", ""))
        seasonItems = []
        for href in seasons:
            href = self.cleanHtmlStr(href)
            numMatch = re.search(r"[?&]s=(\d+)", href)
            seasonNum = numMatch.group(1) if numMatch else ""
            title = _("Season %s") % seasonNum if seasonNum else _("Season")
            params = dict(cItem)
            params.pop("isWatched", None)
            params.pop("isStarted", None)
            params.update({"category": "list_episodes", "title": title, "url": self.getFullUrl(href), "series_url": seriesUrl, "s_title": sTitle, "season": seasonNum})
            seasonItems.append(params)
        self.cacheSeasons[seriesUrl] = seasonItems
        for params in seasonItems:
            self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            self.addDir(params)

    def listEpisodesFromPage(self, cItem, data, seriesUrl=None):
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        if seriesUrl is None:
            seriesUrl = cItem.get("series_url", cItem["url"])
        seasonUrl = cItem["url"]
        # ep-card since 10.10.2026 (title "E5 · Name"), ep-tile before
        episodes = re.findall(r'<a[^>]+href=["\'](/watch/[^"\']+)["\'][^>]+class=["\']ep-(?:card|tile)[^"\']*["\'][^>]*title=["\']([^"\']+)["\']', data)
        if not episodes:
            episodes = re.findall(r'<a[^>]+href=["\'](/watch/[^"\']+)["\'][^>]+class=["\']ep-(?:card|tile)[^"\']*["\'][^>]*>([^<]+)<', data)
        episodes = [(url, re.sub(r"^E\d+\s*\S\s*", "", rawTitle)) for url, rawTitle in episodes]
        normalize = IsMediaNamingNormalized()
        sTitle = cItem.get("s_title") or _cleanSeriesTitle(cItem.get("title", ""))
        episodeItems = []
        for url, rawTitle in episodes:
            url = self.getFullUrl(self.cleanHtmlStr(url))
            epName = _EP_STATUS_RE.sub("", self.cleanHtmlStr(rawTitle)).strip()
            se = re.search(r"[?&]s=(\d+)&e=(\d+)", url)
            sNum = se.group(1) if se else str(cItem.get("season", "") or "")
            eNum = se.group(2) if se else ""
            if normalize and sNum and eNum:
                tag = formatSxxExx(sNum, eNum)
                title = "%s - %s - %s" % (sTitle, tag, epName) if (sTitle and epName) else ("%s - %s" % (sTitle or epName, tag))
            else:
                title = epName or (cItem.get("title", ""))
            params = dict(cItem)
            params.pop("isWatched", None)
            params.pop("isStarted", None)
            params.update({"category": "video", "type": "video", "title": title, "url": url, "season_url": seasonUrl, "series_url": seriesUrl})
            episodeItems.append(params)
        self.cacheEpisodes[seasonUrl] = episodeItems
        for params in episodeItems:
            self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            self.addVideo(params)

    def listEpisodes(self, cItem):
        printDBG("Cineb.listEpisodes")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        self.listEpisodesFromPage(cItem, data)

    def _scrapeDetails(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return {}
        info = {}
        imdb = self.cm.ph.getSearchGroups(data, r'class=["\']IMDb["\'][^>]*><b>IMDb</b>([^<]+)<')[0].strip()
        if not imdb:
            imdb = self.cm.ph.getSearchGroups(data, r"IMDb[^0-9]*([0-9.]+)")[0].strip()
        info["imdb"] = imdb
        info["quality"] = self.cm.ph.getSearchGroups(data, r'class=["\']quality["\'][^>]*>([^<]+)<')[0].strip()
        metaBlock = self.cm.ph.getDataBeetwenMarkers(data, '<div class="metadata set"', "</div>", False)[1]
        info["year"] = ""
        info["duration"] = ""
        if metaBlock:
            yearMatch = re.search(r"<span>\s*(\d{4})\s*</span>", metaBlock)
            durationMatch = re.search(r"<span>\s*(\d+\s*min)\s*</span>", metaBlock)
            if yearMatch:
                info["year"] = yearMatch.group(1).strip()
            if durationMatch:
                info["duration"] = durationMatch.group(1).strip()

        def extractNames(label):
            block = re.findall(r"<li>%s:(.*?)</li>" % label, data, re.DOTALL)
            if not block:
                return []
            return [self.cleanHtmlStr(name) for name in re.findall(r"<a[^>]+>([^<]+)</a>", block[0])]

        info["countries"] = extractNames("Country")
        info["genres"] = extractNames("Genres")
        released = self.cm.ph.getSearchGroups(data, r"Released:[\s\n]*<span[^>]+>([^<]+)<")[0].strip()
        if not released:
            released = self.cm.ph.getSearchGroups(data, r"First air date:[\s\n]*<span[^>]+>([^<]+)<")[0].strip()
        info["released"] = released
        info["directors"] = extractNames("Directors")
        info["creators"] = [] if info["directors"] else extractNames("Created by")
        info["productions"] = extractNames("Productions")
        info["casts"] = extractNames("Casts")
        info["lastUpdated"] = self.cm.ph.getSearchGroups(data, r"Last updated:[\s\n]*<time[^>]+>([^<]+)<")[0].strip()
        description = self.cm.ph.getSearchGroups(data, r'class=["\']description text-expand["\'][^>]*>(.*?)</div>', re.DOTALL)[0]
        info["description"] = self.cleanHtmlStr(description)
        return info

    def getArticleContent(self, cItem):
        printDBG("Cineb.getArticleContent [%s]" % cItem)
        contentUrl = cItem.get("url", "")
        if not contentUrl:
            return []
        info = self._scrapeDetails(contentUrl)
        if not info:
            return []
        otherInfo = {}
        if info["imdb"]:
            otherInfo["imdb"] = info["imdb"]
        if info["released"]:
            otherInfo["released"] = info["released"]
        if info["duration"]:
            otherInfo["duration"] = info["duration"]
        if info["genres"]:
            otherInfo["genres"] = ", ".join(info["genres"])
        if info["countries"]:
            otherInfo["countries"] = ", ".join(info["countries"])
        if info["directors"]:
            otherInfo["directors"] = ", ".join(info["directors"])
        elif info["creators"]:
            otherInfo["directors"] = ", ".join(info["creators"])
        if info["casts"]:
            otherInfo["actors"] = ", ".join(info["casts"])
        title = cItem.get("title", "")
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        return [{"title": title, "text": info["description"], "images": [{"url": self.getFullIconUrl(icon)}], "other_info": otherInfo}]

    def _embedTitleYear(self, cItem):
        title = cItem.get("s_title") or cItem.get("title", "") or ""
        m = re.match(r"^(.*?)\s*\((\d{4})\)\s*$", title)
        if m:
            return m.group(1).strip(), m.group(2)
        return title.strip(), cItem.get("year", "") or ""

    def _linkItemFromUrl(self, url, cItem=None):
        if url.startswith("//"):
            url = "https:" + url
        elif not url.startswith("http"):
            url = self.getFullUrl(url)
        # the videasy resolver (api.speedracelight.com) now needs the title
        # on the embed URL - cineb's own server list omits it. Also normalise
        # the dead player.videasy.net host to .to.
        if cItem is not None and "videasy" in url and "title=" not in url:
            url = url.replace("player.videasy.net", "player.videasy.to")
            t, y = self._embedTitleYear(cItem)
            if t:
                sep = "&" if "?" in url else "?"
                url = "%s%stitle=%s&year=%s" % (url, sep, urllib_quote(t, safe=""), y)
        hostName = self.up.getHostName(url)
        if not hostName:
            hostName = url.split("/")[2] if len(url.split("/")) > 2 else "Server"
        return {"name": hostName.capitalize(), "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1}

    def getLinksForVideo(self, cItem):
        printDBG("Cineb.getLinksForVideo [%s]" % cItem)
        urlTab = []
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        match = re.search(r"window\.__OPT\s*=\s*(\[.*?\]);", data, re.DOTALL)
        if match:
            try:
                serversList = json_loads(match.group(1))
                if isinstance(serversList, list):
                    for serverUrl in serversList:
                        if isinstance(serverUrl, str):
                            urlTab.append(self._linkItemFromUrl(serverUrl, cItem))
            except Exception:
                printExc()
        if not urlTab:
            urlTab = self._goLinks(cItem, data)
        if not urlTab:
            iframeList = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', data, re.I)
            for src in iframeList:
                if "youtube" not in src and "google" not in src:
                    urlTab.append(self._linkItemFromUrl(src, cItem))
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        descMatch = re.search(r'class=["\']description text-expand["\'][^>]*>(.*?)</div>', data, re.DOTALL)
        synopsis = self.cleanHtmlStr(descMatch.group(1)) if descMatch else ""
        if not synopsis:
            synopsis = re.sub(r"\\c[0-9a-fA-F]{8}", "", cItem.get("desc", "")).strip(" |")
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), synopsis))

    def getVideoLinks(self, url):
        printDBG("Cineb.getVideoLinks [%s]" % url)
        if not self.cm.isValidUrl(url):
            return []
        sidecar = sidecarFromUrlMeta(url, IsSidecarEnabled())
        embed = str(url)
        if "/api/go?" in embed:
            # answers with a page that refreshes to the embed url of the chosen server
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER)
            sts, data = self.getPage(embed, params)
            if not sts:
                return []
            embed = self.cm.ph.getSearchGroups(data, r'http-equiv="refresh" content="\d+;\s*url=([^"]+)"')[0] or self.cm.ph.getSearchGroups(data, r'<a href="(https?://[^"]+)"')[0]
            embed = embed.replace("&amp;", "&")
            if not self.cm.isValidUrl(embed):
                printDBG("Cineb: no player url")
                return []
            if self.up.checkHostSupport(embed) != 1:
                printDBG("Cineb: player not known to urlparser [%s]" % embed)
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
                return []
            url = strwithmeta(embed, {"Referer": self.MAIN_URL + "/"})
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecar)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Cineb.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("/browser?keyword=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MAIN_CAT_TAB, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_countries":
            self.listCountries(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
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


class IPTVHost(WatchedFlagHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Cineb(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cineb")

    def _setWatchedStateForSeasonItem(self, seasonItem, action):
        try:
            seasonUrl = str(seasonItem.get("url", "") or "").strip()
            seasonKey = self.host._getWatchedKeyForItem(seasonItem)
            if seasonKey == "":
                return False
            changed = False
            for episodeItem in self.host.cacheEpisodes.get(seasonUrl, []):
                episodeKey = self.host._getWatchedKeyForItem(episodeItem)
                if episodeKey == "":
                    continue
                if action == "set_watched_flag":
                    changed = self.watchedHelper.markItemWatched(episodeItem, episodeKey) or changed
                else:
                    changed = self.watchedHelper.unmarkItemWatched(episodeItem, episodeKey) or changed
            if action == "set_watched_flag":
                changed = self.watchedHelper.markItemWatched(seasonItem, seasonKey) or changed
            else:
                changed = self.watchedHelper.unmarkItemWatched(seasonItem, seasonKey) or changed
            return changed
        except Exception:
            printExc()
            return False

    def _setWatchedStateForSeriesItem(self, seriesItem, action):
        try:
            seriesUrl = str(seriesItem.get("url", "") or "").strip()
            if seriesUrl == "":
                return False
            changed = False
            for seasonItem in self.host.cacheSeasons.get(seriesUrl, []):
                changed = self._setWatchedStateForSeasonItem(seasonItem, action) or changed
            seriesKey = self.host._getWatchedKeyForItem(seriesItem)
            if seriesKey == "":
                return changed
            if action == "set_watched_flag":
                changed = self.watchedHelper.markItemWatched(seriesItem, seriesKey) or changed
            else:
                changed = self.watchedHelper.unmarkItemWatched(seriesItem, seriesKey) or changed
            return changed
        except Exception:
            printExc()
            return False

    def _refreshParentStateAfterAction(self, item, action):
        try:
            if not isinstance(item, dict):
                return
            category = str(item.get("category", "") or "").strip()
            if category == "list_episodes":
                seasonUrl = str(item.get("url", "") or "").strip()
                seriesUrl = str(item.get("series_url", "") or "").strip()
                if seasonUrl != "":
                    seasonEpisodes = self.host.cacheEpisodes.get(seasonUrl, [])
                    if seasonEpisodes:
                        self.watchedHelper.updateParentWatchedState(self.host._buildSeasonItem(seasonUrl), seasonEpisodes, self.host._getWatchedKeyForItem)
                if seriesUrl != "":
                    seasonChildren = self.host.cacheSeasons.get(seriesUrl, [])
                    if seasonChildren:
                        seriesParent = {"category": "list_seasons", "url": seriesUrl}
                        self.watchedHelper.updateParentWatchedState(seriesParent, seasonChildren, self.host._getWatchedKeyForItem)
            elif category == "list_seasons":
                seriesUrl = str(item.get("url", "") or "").strip()
                seasonChildren = self.host.cacheSeasons.get(seriesUrl, [])
                if seriesUrl != "" and seasonChildren:
                    seriesParent = {"category": "list_seasons", "url": seriesUrl}
                    self.watchedHelper.updateParentWatchedState(seriesParent, seasonChildren, self.host._getWatchedKeyForItem)
            elif str(item.get("type", "") or "").strip() in ["video", "audio"]:
                self.host._propagateEpisodeWatchedState(item)
        except Exception:
            printExc()

    def performCustomAction(self, privateData):
        ret = self.watchedHelper.performCustomAction(privateData)
        if ret.status == RetHost.OK:
            self.refreshAfterWatchedFlagChange = True
            try:
                action = privateData.get("action", "")
                if action in ("unset_watched_flag", "set_watched_flag"):
                    idx = privateData.get("item_index", -1)
                    item = self.host.currList[idx] if 0 <= idx < len(self.host.currList) else {}
                    category = item.get("category", "")
                    if category == "list_episodes":
                        self._setWatchedStateForSeasonItem(item, action)
                    elif category == "list_seasons":
                        self._setWatchedStateForSeriesItem(item, action)
                    self._refreshParentStateAfterAction(item, action)
                    self.watchedHelper.recomputeAllGroupsWatched(self.host.cacheEpisodes, self.host._getWatchedKeyForItem, self.host._buildSeasonItem)
                    self.watchedHelper.recomputeAllGroupsWatched(self.host.cacheSeasons, self.host._getWatchedKeyForItem, self.host._buildSeriesItem)
            except Exception:
                printExc()
        return ret

    def withArticleContent(self, cItem):
        if not isinstance(cItem, dict):
            return False
        if cItem.get("type", "") in ["video", "audio"]:
            return True
        return cItem.get("category", "") in ["list_seasons", "list_episodes"]
