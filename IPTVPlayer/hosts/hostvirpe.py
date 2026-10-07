# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - new host for virpe.cc (Polish TV series, shows and films, Elxis CMS)
#   Main page: "Ostatnio dodane" (latest episodes), a poster grid of series and the per-channel series
#   lists (TVP / Polsat / TVN / entertainment / foreign / programmes / archive); category pages are
#   <li class="sectiontableentry"> lists with an Elxis pager ("Dalej"); film sections; GET search.
#   The article pages only link external hosters (vidmoly, vidara, dood) -> urlparser.
#   Watched flag / downloaded flag / name normalisation (episodes "Show - S01E1238", the site has
#   absolute episode numbers) / sidecar / moviemeta INFO / favourites.
#   The audiobook section is left out: its only hoster (userload) is gone.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://virpe.cc/"


# film sections: everything below them is a movie
FILM_RE = re.compile(r'/(?:filmy-polskie-online-za-darmo|online-filmy-zagraniczne-za-darmo)/')
EPISODE_RE = re.compile(r'odcinek\s*(\d+)', re.I)
SEASON_RE = re.compile(r'\bsezon[\s-]*(\d+)', re.I)
LOCAL_PAGE_SIZE = 100


class Virpe(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what identifies a row and is needed to open it again
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "season", "episode", "kind",
                  "icon", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "virpe", "cookie": "virpe.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.homeData = None
        self.posters = {}
        self.MENU = [{"category": "list_latest", "title": _("Newest Episodes")},
                     {"category": "list_posters", "title": _("Series")}]
        # main page modules with series lists: heading on the site (the module key) -> menu title
        modules = (("Seriale TVP", "%s - TVP" % _("Series")), ("Seriale Polsat", "%s - Polsat" % _("Series")), ("Seriale TVN", "%s - TVN" % _("Series")),
                   ("Programy Rozrywkowe", _("TV Shows")), ("Seriale zagraniczne", _("Foreign series")), ("Programy i audycje", _("Programmes")),
                   ("Archiwa Telewizji", _("Archive")))
        for module, title in modules:
            self.MENU.append({"category": "list_module", "title": title, "module": module})
        self.MENU.extend([{"category": "list_items", "title": "%s - %s" % (_("Films"), _("Polish")), "url": self.getFullUrl("/filmy-polskie-online-za-darmo/polskie-filmy/"), "kind": "movie"},
                          {"category": "list_items", "title": _("Foreign movies"), "url": self.getFullUrl("/online-filmy-zagraniczne-za-darmo/filmy-online-za-darmo/"), "kind": "movie"}])
        self.MENU.extend(self.searchItems())

        self.watchedHelper = IPTVWatchedHelper("virpe")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
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
            if cItem.get("category", "") == "list_items" and cItem.get("kind", "") == "series":
                return "series:%s" % self.wfNormalizeUrlKey(url)
            return ""
        except Exception:
            printExc()
        return ""

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getFullUrl(self, url, currUrl=None):
        # keeps a strwithmeta (poster Referer) untouched when there is nothing to fix
        if url and "&amp;" in url:
            url = url.replace("&amp;", "&")
        if url and url.startswith("//"):
            url = "https:" + url
        return CBaseHostClass.getFullUrl(self, url, currUrl)

    ###################################################
    # titles
    ###################################################
    def _seriesTitle(self, title):
        # "Przyjaciółki sezon 9" -> ("Przyjaciółki", "9")
        title = self.cleanHtmlStr(title)
        season = SEASON_RE.search(title)
        if season:
            return re.sub(r'\s*-?\s*\bsezon[\s-]*\d+\s*', ' ', title, flags=re.I).strip(), season.group(1)
        return title, ""

    def _videoParams(self, cItem, url, title, sTitle=""):
        title = self.cleanHtmlStr(title)
        params = self._childParams(cItem)
        params.update({"good_for_fav": True, "url": url})
        if FILM_RE.search(url):
            params.update({"category": "video", "title": title, "s_title": title, "season": "", "episode": "",
                           "meta_type": "movie", "meta_title": title, "meta_year": ""})
            return params
        epMatch = EPISODE_RE.search(title)
        if not sTitle:
            sTitle = re.sub(r'\s*-?\s*odcinek.*$', '', title, flags=re.I).strip() or title
        sTitle, season = self._seriesTitle(sTitle)
        if not season:
            m = SEASON_RE.search(url.replace("-", " "))
            season = m.group(1) if m else ""
        episode = epMatch.group(1) if epMatch else ""
        if IsMediaNamingNormalized() and episode:
            name = "%s - %s" % (sTitle, formatSxxExx(season or "1", episode))
        else:
            name = title
        params.update({"category": "video", "title": name, "s_title": sTitle, "season": season, "episode": episode,
                       "meta_type": "tv", "meta_title": sTitle, "meta_year": ""})
        return params

    @staticmethod
    def _childParams(cItem):
        # a row of a list: without the list's own pager state
        return stripPagerKeys(dict(cItem), ("search_pattern", "base_url"))

    def _seriesParams(self, cItem, url, title):
        params = self._childParams(cItem)
        title = self.cleanHtmlStr(title)
        sTitle = self._seriesTitle(title)[0]
        params.update({"good_for_fav": True, "category": "list_items", "kind": "series", "url": url, "title": title,
                       "s_title": title, "icon": self.posters.get(url, ""), "desc": "",
                       "meta_type": "tv", "meta_title": sTitle, "meta_year": ""})
        return params

    ###################################################
    # main page
    ###################################################
    def _getHome(self):
        if self.homeData is None:
            sts, data = self.getPage(self.MAIN_URL)
            if not sts:
                return ""
            self.homeData = data
            grid = self.cm.ph.getDataBeetwenMarkers(data, 'class="cuatro"', "Ostatnio dodane", False)[1]
            for href, icon in re.findall(r'<a href="([^"]+)"><img src="([^"]+)"', grid):
                # most posters live on fastpic.org, which answers 404 to a "Python-urllib" User-Agent
                icon = self.getFullIconUrl(self.getFullUrl(icon))
                if icon:
                    self.posters[self.getFullUrl(href)] = strwithmeta(icon, {"Referer": self.MAIN_URL, "User-Agent": self.HEADER["User-Agent"]})
        return self.homeData

    def _getModule(self, data, heading):
        for block in data.split('<div class="moduletable')[1:]:
            if ("<h3>%s</h3>" % heading) in block:
                return block
        return ""

    def listLatest(self, cItem):
        printDBG("Virpe.listLatest")
        data = self._getModule(self._getHome(), "Ostatnio dodane")
        seen = set()
        for href, title in re.findall(r'<a href="([^"]+\.html)" class="latestnews"[^>]*>(.*?)</a>', data, re.DOTALL):
            url = self.getFullUrl(href)
            if url in seen:
                continue
            seen.add(url)
            self.addVideo(self._videoParams(cItem, url, title))

    def listPosters(self, cItem):
        printDBG("Virpe.listPosters")
        data = self._getHome()
        grid = self.cm.ph.getDataBeetwenMarkers(data, 'class="cuatro"', "Ostatnio dodane", False)[1]
        seen = set()
        rows = []
        for href, title in re.findall(r'<a href="([^"]+)"><img [^>]+><h2>(.*?)</h2>', grid, re.DOTALL):
            url = self.getFullUrl(href)
            if url in seen or not url.endswith("/"):
                continue
            seen.add(url)
            rows.append((url, title))
        self._addSeriesPaged(cItem, rows)

    def listModule(self, cItem):
        printDBG("Virpe.listModule [%s]" % cItem.get("module", ""))
        data = self._getModule(self._getHome(), cItem.get("module", ""))
        seen = set()
        rows = []
        for href, title in re.findall(r'<a href="([^"]+/)"[^>]*>(.*?)</a>', data, re.DOTALL):
            url = self.getFullUrl(href)
            if url in seen or not self.cleanHtmlStr(title):
                continue
            seen.add(url)
            rows.append((url, title))
        self._addSeriesPaged(cItem, rows)

    def _addSeriesPaged(self, cItem, rows):
        # the main page lists up to ~270 series per module in one go - paged here
        page = max(1, int(cItem.get("page", 1) or 1))
        start = (page - 1) * LOCAL_PAGE_SIZE
        for url, title in rows[start:start + LOCAL_PAGE_SIZE]:
            self.addDir(self._seriesParams(cItem, url, title))
        lastPage = (len(rows) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
        # constant template: the page number drives the list, the template only lets "Jump" through
        addPagingItems(self, cItem, page, page < lastPage, lastPage, self.MAIN_URL)

    ###################################################
    # category pages
    ###################################################
    def listItems(self, cItem):
        printDBG("Virpe.listItems |%s|" % cItem.get("url", ""))
        base = cItem.get("base_url") or cItem["url"]
        page = int(cItem.get("page", 1) or 1)
        sts, data = self.getPage(self._pageUrl(base, page))
        if not sts:
            return
        if "<title>Error 404" in data:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return
        sTitle = ""
        if cItem.get("kind") == "series":
            sTitle = cItem.get("s_title", "") or self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<h1 class="componentheading">(.*?)</h1>')[0])
        body = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="table">', "</ul>", False)[1]
        seen = set()
        for href, title in re.findall(r'<li class="sectiontableentry\d"\s*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', body, re.DOTALL):
            itemUrl = self.getFullUrl(href)
            if itemUrl in seen or not self.cleanHtmlStr(title):
                continue
            seen.add(itemUrl)
            if itemUrl.endswith(".html"):
                self.addVideo(self._videoParams(cItem, itemUrl, title, sTitle))
            else:
                self.addDir(self._seriesParams(cItem, itemUrl, title))
        if seen:
            self._addPager(cItem, data, base, page)

    @staticmethod
    def _pageUrl(base, page):
        # Elxis pages count from 0: "?page=1" is the second page
        if page <= 1:
            return base
        return "%s%spage=%d" % (base, "&" if "?" in base else "?", page - 1)

    def _addPager(self, cItem, data, base, page):
        hasNext = bool(re.search(r'<a href="[^"]+" class="pagenav" title="Dalej"', data))
        end = self.cm.ph.getSearchGroups(data, r'[?&;]page=(\d+)" class="pagenav" title="End"')[0]
        lastPage = int(end) + 1 if end else page
        # the list url is built from base_url + page; the template only gives the pager rows distinct urls
        addPagingItems(self, dict(cItem, base_url=base), page, hasNext, lastPage, base.split("#")[0] + "#page={page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Virpe.listSearchResult [%s]" % searchPattern)
        base = cItem.get("base_url") or self.getFullUrl("/search.html?searchword=%s&ordering=category" % urllib_quote_plus(searchPattern))
        page = int(cItem.get("page", 1) or 1)
        sts, data = self.getPage(self._pageUrl(base, page))
        if not sts:
            return
        body = self.cm.ph.getDataBeetwenMarkers(data, '<div class="searchresults">', "</ul>", False)[1]
        seen = set()
        for href, title, section in re.findall(r'<li class="row\d">\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>\s*<span class="small">([^<]*)</span>', body, re.DOTALL):
            itemUrl = self.getFullUrl(href)
            if itemUrl in seen or not self.cleanHtmlStr(title) or "ksiazki-audio" in itemUrl:
                continue
            seen.add(itemUrl)
            if "Category List" in section and itemUrl.endswith("/"):
                self.addDir(self._seriesParams(cItem, itemUrl, title))
            elif itemUrl.endswith(".html") and "Newsflashes" not in section:
                self.addVideo(self._videoParams(cItem, itemUrl, title))
        if seen:
            self._addPager(dict(cItem, category="search_next_page"), data, base, page)

    ###################################################
    # article page
    ###################################################
    def _parseArticle(self, data):
        body = self.cm.ph.getDataBeetwenMarkers(data, '<div id="elxisarticle', '<div style="clear:both;"></div>', False)[1]
        servers = []
        for href, label in re.findall(r'<p class="server"><b><a href="([^"]+)"[^>]*>(.*?)</a>', body, re.DOTALL):
            servers.append((self.getFullUrl(href), self.cleanHtmlStr(label)))
        desc = []
        for para in re.findall(r'<p(?: class="audiobook")?>(.*?)</p>', body, re.DOTALL):
            para = self.cleanHtmlStr(para)
            if para:
                desc.append(para)
        return {"servers": servers, "desc": "\n".join(desc),
                "title": self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<h1 class="contentheading">(.*?)</h1>')[0])}

    def getLinksForVideo(self, cItem):
        printDBG("Virpe.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = cItem.get("url", "")
        if not self.cm.isValidUrl(pageUrl):
            return []
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        info = self._parseArticle(data)
        urltab = []
        unsupported = []
        for url, label in info["servers"]:
            if not self.cm.isValidUrl(url):
                continue
            hostName = self.up.getHostName(url)
            if self.up.checkHostSupport(url) != 1:
                unsupported.append(hostName)
                continue
            urltab.append({"name": hostName or label, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            if unsupported:
                SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(unsupported))
            else:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), info["desc"]))

    def getVideoLinks(self, videoUrl):
        printDBG("Virpe.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Virpe.getArticleContent [%s]" % cItem.get("url", ""))
        mediaType = cItem.get("meta_type", "")
        siteDesc = ""
        episodes = ""
        url = cItem.get("url", "")
        if self.cm.isValidUrl(url):
            sts, data = self.getPage(url)
            if sts and cItem.get("type") == "video":
                siteDesc = self._parseArticle(data)["desc"]
            elif sts:
                # series category: "<title> online" description + "Rezultatów 1 - 50 of 617"
                siteDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="contentdescription">', "</div>", False)[1])
                episodes = self.cm.ph.getSearchGroups(data, r'Rezultat\S*\s+[\d\s-]+of\s+(\d+)')[0]
        meta = {}
        try:
            meta = getMeta(mediaType, cItem.get("meta_title", ""), cItem.get("meta_year", ""))
        except Exception:
            printExc()
            meta = {}
        otherInfo = dict(meta.get("info", {}) or {})
        if episodes:
            otherInfo["episodes"] = episodes
        text = meta.get("plot", "")
        if siteDesc and siteDesc not in text:
            text = (siteDesc + "\n\n" + text).strip() if text else siteDesc
        icon = meta.get("poster", "") or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text or cItem.get("desc", ""),
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
        printDBG("Virpe.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_latest":
            self.listLatest(self.currItem)
        elif category == "list_posters":
            self.listPosters(self.currItem)
        elif category == "list_module":
            self.listModule(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "search":
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category", "url": ""})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_next_page":
            self.listSearchResult(self.currItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Virpe(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("virpe")

    def withArticleContent(self, cItem):
        return bool(cItem.get("meta_type"))
