# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - rewrite of the MOHAMED_OS host for the current shoofmax.com
#   (catalogue = JSON /genre/filter/<genre>/<page>/<sort>?country=&subgenre=, 16 rows a page, First page /
#    Jump / Next page (no page count),
#    search = HTML /search?q=, programs /program/<pid>[?ep=<n>], free HLS + MP4 on shoofmax.b-cdn.net)
#   + watched flag / downloaded flag / name normalisation / sidecar / moviemeta INFO / favourites.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://shoofmax.com/"


GENRE_MOVIE = "فيلم"
GENRE_SERIES = "مسلسل"
PAGE_SIZE = 16
ICON_URL = "https://shoofmax-static.b-cdn.net/v2/img/program/main/%s-2.jpg"
PROGRAM_RE = re.compile(r'/program/(\d+)')


class ShoofMax(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "pid", "episode", "episodes",
                  "series_url", "icon", "meta_type", "meta_title")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "shoofmax", "cookie": "shoofmax.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://shoofmax-static.b-cdn.net/v2/img/general/sm-deep.png"
        self.MENU = [{"category": "list_items", "title": _("Movies") + " - " + _("Latest"), "genre": GENRE_MOVIE, "sort": "yop"},
                     {"category": "list_items", "title": _("Movies") + " - " + _("Most viewed"), "genre": GENRE_MOVIE, "sort": "views"},
                     {"category": "list_filters", "title": _("Movies") + " - " + _("Genres"), "genre": GENRE_MOVIE, "filter": "subgenre"},
                     {"category": "list_filters", "title": _("Movies") + " - " + _("Countries"), "genre": GENRE_MOVIE, "filter": "country"},
                     {"category": "list_items", "title": _("Series") + " - " + _("Latest"), "genre": GENRE_SERIES, "sort": "yop"},
                     {"category": "list_items", "title": _("Series") + " - " + _("Most viewed"), "genre": GENRE_SERIES, "sort": "views"},
                     {"category": "list_filters", "title": _("Series") + " - " + _("Genres"), "genre": GENRE_SERIES, "filter": "subgenre"},
                     {"category": "list_filters", "title": _("Series") + " - " + _("Countries"), "genre": GENRE_SERIES, "filter": "country"}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("shoofmax")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url if url else ""
            if cItem.get("category", "") == "sm_series":
                return "series:%s" % url if url else ""
            return ""
        except Exception:
            printExc()
        return ""

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _movieTitle(self, title, year=""):
        if IsMediaNamingNormalized() and year:
            return "%s (%s)" % (title, year)
        return title

    def _episodeTitle(self, sTitle, episode):
        if IsMediaNamingNormalized():
            return "%s - %s" % (sTitle, formatSxxExx(1, episode))
        return "%s - %s %s" % (sTitle, _("Episode"), episode)

    def _programUrl(self, pid):
        return self.getFullUrl("program/%s" % pid)

    def _addProgram(self, cItem, pid, title, icon, episodes, desc=""):
        params = stripPagerKeys(dict(cItem), ("search_pattern", "sort", "genre", "filter", "country", "subgenre"))
        params.update({"good_for_fav": True, "pid": str(pid), "icon": icon, "desc": desc, "s_title": title, "meta_title": title})
        if episodes > 1 or episodes < 0:
            # episodes < 0: series from the search page, the count comes from the program page
            params.update({"category": "sm_series", "title": title, "url": self._programUrl(pid), "episodes": episodes, "meta_type": "tv"})
            self.addDir(params)
        else:
            params.update({"category": "sm_movie", "title": self._movieTitle(title), "url": self._programUrl(pid), "meta_type": "movie"})
            self.addVideo(params)

    ###################################################
    # lists
    ###################################################
    def _filterUrlTpl(self, cItem):
        # the catalogue url of any page, "{page}" for the page number
        return "%sgenre/filter/%s/{page}/%s?country=%s&subgenre=%s" % (self.MAIN_URL, urllib_quote(cItem["genre"]), cItem.get("sort", "yop"),
                                                                      urllib_quote_plus(cItem.get("country", "")), urllib_quote_plus(cItem.get("subgenre", "")))

    def listFilters(self, cItem):
        printDBG("ShoofMax.listFilters %s" % cItem.get("filter", ""))
        sts, data = self.getPage(self.getFullUrl("genre/%s" % urllib_quote(cItem["genre"])))
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'id="filter-%s"' % cItem["filter"], "</select>", False)[1]
        for value, title in re.findall(r'<option value="([^"]+)"[^>]*>([^<]+)</option>', data):
            title = self.cleanHtmlStr(title)
            if not title:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "sort": "yop", cItem["filter"]: value})
            self.addDir(params)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        pageUrlTpl = self._filterUrlTpl(cItem)
        url = pageUrlTpl.format(page=page)
        printDBG("ShoofMax.listItems |%s|" % url)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/javascript, */*; q=0.01"})
        sts, data = self.getPage(url, params)
        if not sts:
            return
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return
        if not isinstance(data, list):
            return
        cnt = 0
        for item in data:
            if not isinstance(item, dict) or not item.get("pid"):
                continue
            title = self.cleanHtmlStr(item.get("ptitle", "") or "")
            if not title:
                continue
            try:
                episodes = int(item.get("pepisodes") or 0)
            except (TypeError, ValueError):
                episodes = 0
            icon = ICON_URL % item["presbase"] if item.get("presbase") else ""
            self._addProgram(cItem, item["pid"], title, icon, episodes, self.cleanHtmlStr(item.get("sgname", "") or ""))
            cnt += 1
        # the JSON has no page count: a full page means there is a next one
        addPagingItems(self, cItem, page, cnt >= PAGE_SIZE, 0, pageUrlTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ShoofMax.listSearchResult [%s]" % searchPattern)
        sts, data = self.getPage(self.getFullUrl("search?q=%s" % urllib_quote_plus(searchPattern)))
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'class="general-body"', 'class="search-bottom-padding"', False)[1]
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '</a>'):
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            pid = PROGRAM_RE.search(href)
            if not pid or pid.group(1) in seen:
                continue
            pid = pid.group(1)
            seen.add(pid)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<span>([^<]+)</span>')[0])
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'url\(([^)]+)\)')[0].strip("'\" ")
            self._addProgram(cItem, pid, title, icon, -1 if "ep=" in href else 0)

    def listEpisodes(self, cItem):
        printDBG("ShoofMax.listEpisodes |%s|" % cItem["url"])
        episodes = cItem.get("episodes", 0)
        if episodes < 1:
            sts, data = self.getPage(cItem["url"] + "?ep=1")
            if not sts:
                return
            data = self.cm.ph.getDataBeetwenMarkers(data, 'class="episode-control-select"', "</select>", False)[1]
            nums = [int(n) for n in re.findall(r'<option value="(\d+)"', data)]
            episodes = max(nums) if nums else 1
        sTitle = cItem.get("s_title", cItem["title"])
        for episode in range(1, episodes + 1):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "sm_episode", "title": self._episodeTitle(sTitle, episode), "s_title": sTitle,
                           "episode": episode, "url": "%s?ep=%d" % (cItem["url"], episode), "series_url": cItem["url"]})
            self.addVideo(params)

    ###################################################
    # program page
    ###################################################
    def _parseProgramPage(self, data):
        info = {"desc": "", "year": "", "country": "", "genre": "", "actors": "", "poster": ""}
        about = self.cm.ph.getDataBeetwenMarkers(data, 'ref="about-program"', "</div><!-- col -->", False)[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(about, '<div class="meta-section-li">', "</div>", False):
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<b>([^<]+)</b>')[0])
            value = self.cleanHtmlStr(re.sub(r'<b>[^<]*</b>', '', item))
            if not label:
                info["desc"] = value
            elif "سنة" in label:
                info["year"] = self.cm.ph.getSearchGroups(value, r'(\d{4})')[0]
            elif "دولة" in label:
                info["country"] = value
            elif "الفئة" in label:
                info["genre"] = value
        actors = []
        for name in re.findall(r'<div><b>[^<]*</b>([^<]+)</div>', self.cm.ph.getDataBeetwenMarkers(data, 'ref="related-cast"', "<!-- meta-section -->", False)[1]):
            name = self.cleanHtmlStr(name)
            if name and name not in actors:
                actors.append(name)
        info["actors"] = ", ".join(actors)
        info["poster"] = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return info

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("ShoofMax.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = cItem.get("url", "")
        if not self.cm.isValidUrl(pageUrl):
            return []
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        origin = self.cm.ph.getSearchGroups(data, r'''var\s+origin_link\s*=\s*["']([^"']+)["']''')[0].rstrip("/")
        path = self.cm.ph.getSearchGroups(data, r'''hls:\s*origin_link\s*\+\s*["']([^"']+)/variant\.m3u8["']''')[0]
        if not origin or not path:
            printDBG("ShoofMax: no stream on the page")
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        base = origin + path
        meta = {"User-Agent": self.HEADER.get("User-Agent", ""), "Referer": self.MAIN_URL}
        hlsMeta = dict(meta)
        hlsMeta["iptv_proto"] = "m3u8"
        renditions = []
        for rendition in re.findall(r'''rendition\s*=\s*["'](\d+p)["']''', data):
            if rendition not in renditions:
                renditions.append(rendition)
        renditions.sort(key=lambda x: -int(x[:-1]))
        urltab = []
        for rendition in renditions:
            urltab.append({"name": "%s HLS" % rendition, "url": strwithmeta("%s/%s/index.m3u8" % (base, rendition), hlsMeta), "need_resolve": 0})
        if not urltab:
            urltab.append({"name": "HLS", "url": strwithmeta("%s/variant.m3u8" % base, hlsMeta), "need_resolve": 0})
        if "/fallback.mp4" in data:
            urltab.append({"name": "MP4", "url": strwithmeta("%s/fallback.mp4" % base, meta), "need_resolve": 0})
        if "/fallback-240p.mp4" in data:
            urltab.append({"name": "240p MP4", "url": strwithmeta("%s/fallback-240p.mp4" % base, meta), "need_resolve": 0})
        sidecarTxt = self._parseProgramPage(data)["desc"]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("ShoofMax.getArticleContent [%s]" % cItem.get("url", ""))
        mediaType = cItem.get("meta_type", "")
        pageUrl = cItem.get("url", "")
        if cItem.get("category") == "sm_series":
            pageUrl += "?ep=1"
        info = {"desc": "", "year": "", "country": "", "genre": "", "actors": "", "poster": ""}
        if self.cm.isValidUrl(pageUrl):
            sts, data = self.getPage(pageUrl)
            if sts:
                info = self._parseProgramPage(data)
        meta = {}
        try:
            meta = getMeta(mediaType, cItem.get("meta_title", ""), info["year"])
        except Exception:
            printExc()
            meta = {}
        otherInfo = dict(meta.get("info", {}) or {})
        for key in ("year", "country", "genre", "actors"):
            if info[key]:
                otherInfo[key] = info[key]
        text = info["desc"] or meta.get("plot", "") or cItem.get("desc", "")
        icon = cItem.get("icon", "") or meta.get("poster", "") or info["poster"]
        return [{"title": cItem.get("title", ""), "text": text,
                 "images": [{"title": "", "url": icon}] if icon else [],
                 "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("meta_type"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("ShoofMax.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_filters":
            self.listFilters(self.currItem)
        elif category == "sm_series":
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, ShoofMax(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("shoofmax")

    def withArticleContent(self, cItem):
        return bool(cItem.get("meta_type"))
