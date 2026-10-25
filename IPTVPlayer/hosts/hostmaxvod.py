# -*- coding: utf-8 -*-
LAST_MODIFIED = "25.10.2026"
# 25.10.2026 - new host for maxvod.tv (Polish free video library): films, series, kids, categories, search;
#   every player source (Lektor / Dubbing / Napisy PL / Oryginał) is one link, resolved at play time.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
import time
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://maxvod.tv/"


class MaxVOD(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what identifies a favourite and opens it again
    FAV_FIELDS = ("name", "category", "type", "url", "page_url", "season", "episode", "s_title", "icon", "meta_type", "meta_title", "meta_year")

    # local paging of very long seasons (soaps with hundreds of episodes in one season)
    EPISODES_PER_PAGE = 100
    # parsed title pages: kept for a while (new episodes of running series) and only for the last titles opened
    PAGE_CACHE_TTL = 900
    PAGE_CACHE_MAX = 40

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "MaxVOD", "cookie": "maxvod.cookie"})
        self.USER_AGENT = self.cm.getDefaultUserAgent("chrome")
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                       "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.6"}
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("apple-touch-icon.png")
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("tv-shows")},
                     {"category": "list_items", "title": _("Popular"), "url": self.getFullUrl("popular")},
                     {"category": "list_items", "title": _("Kids"), "url": self.getFullUrl("kids")},
                     {"category": "categories", "title": _("Categories")}] + self.searchItems()
        self.pageCache = {}
        self.categoriesCache = []

        self.watchedHelper = IPTVWatchedHelper("maxvod")
        self.wfInitFolderCache()

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if not url:
                return ""
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url
            if cItem.get("category", "") in ("series", "season"):
                return "folder:%s" % url
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "") in ("series", "season", "movie", "episode"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _paramsWithReferer(self, referer):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=referer)
        return params

    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year and ("(%s)" % year) not in title:
            return "%s (%s)" % (title, year)
        return title

    def _episodeTitle(self, sTitle, season, episode, label):
        if IsMediaNamingNormalized() and episode:
            return "%s - %s" % (sTitle, formatSxxExx(season or 1, episode))
        return "%s - %s" % (sTitle, label)

    @staticmethod
    def _metaTitle(title):
        # the site writes "Polish title / Original title": the original one finds the film in moviemeta
        parts = [x.strip() for x in title.split(" / ") if x.strip()]
        if len(parts) > 1:
            return parts[1]
        return title

    @staticmethod
    def _slug(url):
        return re.sub(r"[?#].*$", "", url).rstrip("/").split("/")[-1]

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("MaxVOD.listItems [%s]" % cItem.get("url", ""))
        page = int(cItem.get("page", 1) or 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        tpl = baseUrl + ("&" if "?" in baseUrl else "?") + "page={page}"
        url = baseUrl if page <= 1 else tpl.format(page=page)
        sts, data = self.getPage(url)
        if not sts:
            return
        seen = set()
        for kind, slug, body in re.findall(r'<a\s+href="/(movie|series)/([^"?#]+)"(.*?)</a>', data, re.S):
            url = self.getFullUrl("%s/%s" % (kind, slug))
            if url in seen:
                continue
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'alt="([^"]+)"')[0])
            if not title:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(body, r'<img[^>]+src="([^"]+)"')[0]
            year = self.cm.ph.getSearchGroups(body, r">\s*((?:19|20)\d{2})\s*</span>")[0]
            params = {"good_for_fav": True, "url": url, "page_url": url, "s_title": title, "icon": self.getFullIconUrl(icon) if icon else "",
                      "desc": " | ".join([x for x in (year, _("Series") if kind == "series" else "") if x]),
                      "meta_title": self._metaTitle(title), "meta_year": year}
            if kind == "series":
                params.update({"category": "series", "title": title, "meta_type": "tv"})
                self.addDir(params)
            else:
                params.update({"category": "movie", "title": self._movieTitle(title, year), "meta_type": "movie"})
                self.addVideo(params)
        if seen:
            hasNext = bool(re.search(r'rel="next"\s+href=', data))
            lastPage = self.cm.ph.getSearchGroups(data, r"svp-info\">[^<]*?\d+\D+(\d+)\s*<")[0]
            addPagingItems(self, dict(cItem, base_url=baseUrl), page, hasNext, int(lastPage) if lastPage else 0, tpl)

    def listCategories(self, cItem):
        if not self.categoriesCache:
            sts, data = self.getPage(self.getFullUrl("movies"))
            if not sts:
                return
            for slug, name in re.findall(r'<a\s+class="dropdown-item"\s+href="/category/([^"]+)">(.*?)</a>', data, re.S):
                name = self.cleanHtmlStr(name)
                if name and slug not in [x[0] for x in self.categoriesCache]:
                    self.categoriesCache.append((slug, name))
        for slug, name in self.categoriesCache:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": name, "url": self.getFullUrl("category/%s" % slug)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MaxVOD.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("search?q=%s" % urllib_quote_plus(searchPattern.strip()))})
        self.listItems(cItem)

    ###################################################
    # title page
    ###################################################
    def _getTitlePage(self, url):
        now = time.time()
        cached = self.pageCache.get(url)
        if cached and now - cached[0] < self.PAGE_CACHE_TTL:
            return cached[1]
        sts, data = self.getPage(url)
        if not sts:
            return None
        ret = {"url": url}
        h1 = self.cm.ph.getDataBeetwenNodes(data, ("<h1", ">", "movie-title-main"), ("</h1", ">"), False)[1]
        ret["title"] = self.cleanHtmlStr(re.sub(r"<span[^>]+badge.*?</span>", "", h1, flags=re.S))
        ret["desc"] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<p", ">", "info-desc"), ("</p", ">"), False)[1])
        ret["imdb"] = self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
        icon = self.cm.ph.getSearchGroups(data, r'<img[^>]+src="([^"]+)"[^>]+class="info-poster')[0]
        ret["icon"] = self.getFullIconUrl(icon) if icon else ""
        meta = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "info-meta"), ("</div", ">"), False)[1]
        ret["year"] = self.cm.ph.getSearchGroups(meta, r"bi-calendar3[^>]*></i>\s*((?:19|20)\d{2})")[0]
        ret["duration"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(meta, r"bi-clock[^>]*></i>([^<]+)<")[0])
        cast = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "cast-inline"), ("</div", ">"), False)[1]
        ret["actors"] = ", ".join([self.cleanHtmlStr(x) for x in re.findall(r"<a[^>]*>([^<]+)</a>", cast) if self.cleanHtmlStr(x)])
        ret["seasons"] = []
        tabs = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "season-tabs"), ("<div", ">", "episode-list"), False)[1]
        for sNum, body in re.findall(r'<a\s+href="[^"]*\?sezon=(\d+)[^"]*"[^>]*class="season-tab-btn[^"]*">(.*?)</a>', tabs, re.S):
            label = self.cleanHtmlStr(re.sub(r"<small.*?</small>", "", body, flags=re.S))
            if int(sNum) not in [x[0] for x in ret["seasons"]]:
                ret["seasons"].append((int(sNum), label or (_("Season %s") % sNum)))
        ret["seasons"].sort()
        ret["episodes"] = []
        for href, sNum, eNum, body in re.findall(r'<a\s+href="(/series/[^"]+\?sezon=(\d+)&amp;odcinek=(\d+))"\s+class="episode-item[^"]*">(.*?)</a>', data, re.S):
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(body, ("<div", ">", "episode-title"), ("</div", ">"), False)[1])
            duration = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(body, ("<div", ">", "episode-duration"), ("</div", ">"), False)[1])
            ret["episodes"].append({"season": int(sNum), "episode": int(eNum), "label": label, "duration": duration,
                                    "url": self.getFullUrl(href.replace("&amp;", "&"))})
        ret["episodes"].sort(key=lambda x: x["episode"])
        if len(self.pageCache) >= self.PAGE_CACHE_MAX:
            self.pageCache = dict((key, value) for key, value in self.pageCache.items() if now - value[0] < self.PAGE_CACHE_TTL)
            if len(self.pageCache) >= self.PAGE_CACHE_MAX:
                self.pageCache = {}
        self.pageCache[url] = (now, ret)
        return ret

    def listSeries(self, cItem):
        printDBG("MaxVOD.listSeries [%s]" % cItem.get("url", ""))
        url = cItem.get("page_url", cItem["url"])
        page = self._getTitlePage(url)
        if page is None:
            return
        sTitle = page["title"] or cItem.get("s_title", "")
        if len(page["seasons"]) <= 1:
            self._addEpisodes(cItem, page, page["seasons"][0][0] if page["seasons"] else 0)
            return
        for sNum, label in page["seasons"]:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "season", "title": "%s - %s" % (sTitle, label), "season": sNum,
                           "url": "%s?sezon=%d&odcinek=1" % (url, sNum), "page_url": url, "s_title": sTitle,
                           "icon": page["icon"] or cItem.get("icon", ""), "meta_year": page["year"] or cItem.get("meta_year", "")})
            self.addDir(params)

    def listSeason(self, cItem):
        page = self._getTitlePage(cItem["url"])
        if page is None:
            return
        page = dict(page)
        page["title"] = cItem.get("s_title", "") or page["title"]
        page["url"] = cItem.get("page_url", page["url"])
        self._addEpisodes(cItem, page, cItem.get("season", 0))

    def _addEpisodes(self, cItem, page, season):
        sTitle = page["title"] or cItem.get("s_title", "")
        episodes = [x for x in page["episodes"] if not season or x["season"] == season]
        pageNum = int(cItem.get("page", 1) or 1)
        start = (pageNum - 1) * self.EPISODES_PER_PAGE
        for ep in episodes[start:start + self.EPISODES_PER_PAGE]:
            label = ep["label"] or ("%s %d" % (_("Episode"), ep["episode"]))
            params = {"good_for_fav": True, "category": "episode", "url": ep["url"], "page_url": page["url"], "s_title": sTitle,
                      "icon": page["icon"] or cItem.get("icon", ""), "season": ep["season"], "episode": ep["episode"],
                      "title": self._episodeTitle(sTitle, ep["season"], ep["episode"], label),
                      "desc": " | ".join([x for x in ("%s %d" % (_("Season"), ep["season"]), label, ep["duration"]) if x]),
                      "meta_type": "tv", "meta_title": self._metaTitle(sTitle), "meta_year": page["year"] or cItem.get("meta_year", "")}
            self.addVideo(params)
        if len(episodes) > self.EPISODES_PER_PAGE:
            lastPage = (len(episodes) + self.EPISODES_PER_PAGE - 1) // self.EPISODES_PER_PAGE
            addPagingItems(self, cItem, pageNum, pageNum < lastPage, lastPage)

    ###################################################
    # links
    ###################################################
    def _playerUrl(self, cItem):
        # the player page of the item: /player/<slug> (film) or /player/series/<slug>?sezon=S&odcinek=E (episode)
        url = cItem.get("url", "")
        if cItem.get("category") == "episode" or "/series/" in url:
            return self.getFullUrl("player/series/%s?sezon=%s&odcinek=%s" % (self._slug(url), cItem.get("season", 1), cItem.get("episode", 1)))
        return self.getFullUrl("player/%s" % self._slug(url))

    @staticmethod
    def _qualityNum(quality):
        m = re.search(r"(\d{3,4})", quality or "")
        if m:
            return int(m.group(1))
        if "4k" in (quality or "").lower():
            return 2160
        return 1081 if quality else 0

    def _sources(self, playerUrl, referer):
        sts, data = self.getPage(playerUrl, self._paramsWithReferer(referer))
        if not sts:
            return []
        raw = self.cm.ph.getSearchGroups(data, r"const\s+SOURCES\s*=\s*(\[.*?\]);\s*\n")[0]
        try:
            items = json_loads(raw) if raw else []
        except Exception:
            printExc()
            items = []
        sources = []
        for src in items:
            if not isinstance(src, dict) or not src.get("uuid"):
                continue
            uuid = ensure_str(src["uuid"])
            playUrl = self.getFullUrl("player/play/%s" % uuid)
            if ensure_str(src.get("variant", "") or "") == "original":
                playUrl += "?original=1"
            sources.append({"url": playUrl, "label": ensure_str(src.get("label", "") or ""), "lang": ensure_str(src.get("langLabel", "") or ""),
                            "quality": ensure_str(src.get("quality", "") or ""), "direct": ensure_str(src.get("mediaType", "")) == "video"})
        # the site's own MP4 servers ("Player bez limitu") first, then by quality
        sources.sort(key=lambda x: (not ("bez limitu" in x["label"].lower() and x["direct"]), not x["direct"], -self._qualityNum(x["quality"])))
        return sources

    def getLinksForVideo(self, cItem):
        printDBG("MaxVOD.getLinksForVideo [%s]" % cItem)
        pageUrl = cItem.get("page_url", "") or cItem.get("url", "")
        # the title page only feeds the sidecar (plot, year, IMDb id)
        page = (self._getTitlePage(pageUrl) if IsSidecarEnabled() else None) or {}
        playerUrl = self._playerUrl(cItem)
        urltab = []
        names = {}
        seen = set()
        for src in self._sources(playerUrl, cItem.get("url", "") or self.MAIN_URL):
            if src["url"] in seen:
                continue
            seen.add(src["url"])
            name = " - ".join([x for x in (src["lang"], " ".join([x for x in (src["label"], src["quality"]) if x])) if x]) or "MaxVOD"
            names[name] = names.get(name, 0) + 1
            if names[name] > 1:
                name = "%s (%d)" % (name, names[name])
            urltab.append({"name": name, "url": strwithmeta(src["url"], {"Referer": playerUrl, "User-Agent": self.USER_AGENT}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        sidecarTxt = page.get("desc", "") or cItem.get("desc", "")
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", "movie"), cItem.get("meta_title", ""), page.get("year", "") or cItem.get("meta_year", ""),
                                     page.get("imdb", ""), skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt, metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("MaxVOD.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        url = str(videoUrl)
        if not self.cm.isValidUrl(url):
            return []
        if "/player/play/" not in url:
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        # /player/play/<uuid> answers with a 302 to a signed, expiring link: the site's MP4 server or an external hoster
        referer = getattr(videoUrl, "meta", {}).get("Referer", "") or self.MAIN_URL
        params = self._paramsWithReferer(referer)
        params["no_redirection"] = True
        sts, _data = self.getPage(url, params)
        location = self.cm.meta.get("location", "") if sts else ""
        location = self.getFullUrl(location, url) if location else ""
        printDBG("MaxVOD.getVideoLinks location [%s]" % location)
        if not location or "/login" in location or "maxvod.tv" in location:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        ipHost = re.match(r"https?://\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?/", location)
        if ipHost or self.up.checkHostSupport(location) != 1:
            # the site's MP4 servers answer only with the Referer of the site (403 without)
            meta = {"Referer": self.MAIN_URL, "User-Agent": self.USER_AGENT}
            linksTab = [{"name": "MP4", "url": strwithmeta(location, meta), "need_resolve": 0}]
        else:
            # an external hoster: drop the signature of the site from the embed link
            location = re.sub(r"[?&](?:md5|expires)=[^&]*", "", location)
            if "?" not in location and "&" in location:
                location = location.replace("&", "?", 1)
            linksTab = self.up.getVideoLinkExt(strwithmeta(location, {"Referer": self.MAIN_URL}))
        return decorateResolvedLinkItems(linksTab, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("MaxVOD.getArticleContent [%s]" % cItem.get("url", ""))
        otherInfo = {}
        title = cItem.get("s_title", "") or cItem.get("title", "")
        text = ""
        icon = cItem.get("icon", "")
        page = self._getTitlePage(cItem.get("page_url", "") or cItem.get("url", ""))
        imdb = ""
        if page:
            title = page["title"] or title
            text = page["desc"]
            icon = page["icon"] or icon
            imdb = page["imdb"]
            for key, field in (("year", "year"), ("duration", "duration"), ("actors", "actors")):
                if page.get(field):
                    otherInfo[key] = page[field]
            if page.get("seasons"):
                otherInfo["seasons"] = str(len(page["seasons"]))
        mediaType = cItem.get("meta_type", "movie")
        meta = getMetaByImdbId(mediaType, imdb) if imdb else {}
        if not meta and cItem.get("meta_title"):
            meta = getMeta(mediaType, cItem["meta_title"], (page or {}).get("year", "") or cItem.get("meta_year", ""))
        sameAs = {"cast": "actors"}
        for key, value in meta.get("info", {}).items():
            if key not in otherInfo and sameAs.get(key) not in otherInfo:
                otherInfo[key] = value
        if not text:
            text = meta.get("plot", "") or cItem.get("desc", "")
        if not icon:
            icon = meta.get("poster", "")
        if cItem.get("category") == "episode":
            title = cItem.get("title", title)
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("MaxVOD.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "categories":
            self.listCategories(self.currItem)
        elif category == "series":
            self.listSeries(self.currItem)
        elif category == "season":
            self.listSeason(self.currItem)
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
        CHostBase.__init__(self, MaxVOD(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("maxvod")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("series", "season", "movie", "episode")
