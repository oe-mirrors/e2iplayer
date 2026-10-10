# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# RetroFlix Plugin for e2iplayer
# Created: 13.01.2025
# 09.10.2026 - host standard + the new site layout
#   retroflix.org moved its lists (/browse/movies/ -> /movies/, /browse/anime/ -> /collection/anime/ ...) and
#   plays every film from its own player page (iframe) with an archive.org MP4 - the film page itself has no
#   <video> any more. The MP4 comes from the page's JSON-LD (VideoObject contentUrl), the player page or the
#   archive.org item page (urlparser parserARCHIVEORG) as fallbacks.
#   - films are VIDEO rows keyed on their page url (watched flag, downloaded marker, favourites)
#   - name normalisation "Title (Year)", sidecar, INFO via moviemeta (IMDb id of the page) + the site's fields
#   - First / Jump / Next page with the last page for the lists, the search and the long term lists (cast ...)
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://retroflix.org/"


PAGE_RE = re.compile(r"/page/\d+/?")


class RetroFlix(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "RetroFlix", "cookie": "RetroFlix.cookie"})
        self.defaultParams = {"header": self.cm.getDefaultHeader(), "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("wp-content/uploads/2026/09/cropped-retroflix-icon.png")
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies/")},
                     {"category": "list_items", "title": _("Cartoons"), "url": self.getFullUrl("cartoons/")},
                     {"category": "list_items", "title": _("Anime"), "url": self.getFullUrl("collection/anime/")},
                     {"category": "list_items", "title": _("Documentaries"), "url": self.getFullUrl("genre/documentary/")},
                     {"category": "list_items", "title": _("Cinema History"), "url": self.getFullUrl("collection/cinema-history/")},
                     {"category": "list_value", "title": _("Genres"), "url": self.getFullUrl("genre/")},
                     {"category": "list_value", "title": _("Year"), "url": self.getFullUrl("year-released/")},
                     {"category": "list_value", "title": _("Actors"), "url": self.getFullUrl("cast/")},
                     {"category": "list_value", "title": _("Directors"), "url": self.getFullUrl("director/")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("retroflix")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("category") == "video":
                url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
                return "video:%s" % url if url else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _pageUrlTpl(url):
        # ".../movies/page/3/" -> ".../movies/page/{page}/", "https://site/?s=x" -> "https://site/page/{page}/?s=x"
        base, sep, query = url.partition("?")
        base = PAGE_RE.sub("/", base)
        if not base.endswith("/"):
            base += "/"
        return base + "page/{page}/" + sep + query

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _lastPage(data, page):
        # the highest numbered link; on the last page itself every link points back, the page is the last one
        nums = [int(n) for n in re.findall(r'class="page-numbers"\s+href="[^"]*/page/(\d+)/', data)]
        return max(nums + [page]) if nums else 0

    def _jsonLd(self, data):
        # {"@type": node} of the page's JSON-LD graph (Movie, VideoObject)
        nodes = {}
        for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', data, re.S):
            try:
                js = json_loads(block)
            except Exception:
                continue
            graph = js.get("@graph", [js]) if isinstance(js, dict) else js
            for node in graph if isinstance(graph, list) else []:
                if isinstance(node, dict) and node.get("@type") and not isinstance(node["@type"], (list, dict)):
                    nodes.setdefault(ensure_str(node["@type"]), node)
        return nodes

    def _text(self, value):
        # a JSON-LD value (text, {"name": ...} or a list of them) -> "a, b, c"
        value = value if isinstance(value, list) else [value]
        return ", ".join(self.cleanHtmlStr(ensure_str(v.get("name", "") if isinstance(v, dict) else v)) for v in value if v)

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("RetroFlix.listItems |%s|" % cItem)
        page = self._page(cItem)
        pageUrlTpl = self._pageUrlTpl(cItem["url"])
        url = cItem["url"] if page == 1 else pageUrlTpl.format(page=page)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        hasNext = 'class="next page-numbers"' in data
        lastPage = self._lastPage(data, page)
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, "<article", "</article>"):
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]*/watch/[^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)
            if url in seen:
                continue
            seen.add(url)
            alt = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"<h3[^>]*>(.*?)</h3>")[0])
            if not title:
                title = re.sub(r"\s*(?:\(\d{4}\))?\s*Cover$", "", alt).strip()
            if not title:
                continue
            year = self.cm.ph.getSearchGroups(alt, r"\(((?:18|19|20)\d\d)\)")[0]
            icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]
            dispTitle = "%s (%s)" % (title, year) if (normalize and year and "(%s)" % year not in title) else title
            desc = year
            self.addVideo({"name": "category", "good_for_fav": True, "category": "video", "title": dispTitle, "url": url,
                           "icon": self.getFullIconUrl(icon) if icon else "", "desc": desc,
                           "meta_type": "movie", "meta_title": title, "meta_year": year})
        addPagingItems(self, cItem, page, bool(seen) and hasNext, lastPage, pageUrlTpl)

    def listValue(self, cItem):
        printDBG("RetroFlix.listValue |%s|" % cItem)
        page = self._page(cItem)
        pageUrlTpl = self._pageUrlTpl(cItem["url"])
        url = cItem["url"] if page == 1 else pageUrlTpl.format(page=page)
        sts, data = self.getPage(url)
        if not sts:
            return
        base = PAGE_RE.sub("/", cItem["url"])
        found = False
        for url, name, count in re.findall(r'<a class="watch-term-button" href="([^"]+)"><span class="watch-term-name">(.*?)</span>(?:<span class="watch-term-count">(\d+)</span>)?', data):
            title = self.cleanHtmlStr(name)
            url = self.getFullUrl(url)
            if not title or url == base:
                continue
            found = True
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": url,
                         "desc": "%s: %s" % (_("Movies"), count) if count else ""})
        hasNext = 'class="next page-numbers"' in data
        addPagingItems(self, cItem, page, found and hasNext, self._lastPage(data, page), pageUrlTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("RetroFlix.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("?s=%s" % urllib_quote_plus(searchPattern.strip())), "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("RetroFlix.getLinksForVideo [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        nodes = self._jsonLd(data)
        sidecarTxt = self._text(nodes.get("Movie", {}).get("description", "") or nodes.get("VideoObject", {}).get("description", ""))
        videoUrl = self._text(nodes.get("VideoObject", {}).get("contentUrl", ""))
        if not videoUrl:
            # the film's own player page
            player = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]*/player/[^"]+)"')[0]
            if player:
                sts, pdata = self.getPage(self.getFullUrl(player))
                if sts:
                    videoUrl = self.cm.ph.getSearchGroups(pdata, r'<video[^>]+src="([^"]+)"')[0]
        urltab = []
        if self.cm.isValidUrl(videoUrl):
            name = "archive.org MP4" if "archive.org" in videoUrl else self.up.getHostName(videoUrl).capitalize()
            direct = "archive.org" in videoUrl or videoUrl.split("?", 1)[0].lower().endswith((".mp4", ".m3u8"))
            urltab.append({"name": name, "url": strwithmeta(videoUrl, {"Referer": self.MAIN_URL}), "need_resolve": 0 if direct else 1})
        else:
            # only the archive.org item page ("Hosted by the Internet Archive")
            item = self.cm.ph.getSearchGroups(data, r'href="(https?://archive\.org/details/[^"]+)"')[0]
            if item:
                urltab.append({"name": "archive.org", "url": strwithmeta(item, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("RetroFlix.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            # archive.org item pages: urlparser parserARCHIVEORG
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("RetroFlix.getArticleContent [%s]" % cItem)
        info = {}
        desc = ""
        imdbId = ""
        title = cItem.get("meta_title", "") or re.sub(r"\s*\(\d{4}\)$", "", cItem.get("title", ""))
        year = cItem.get("meta_year", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            nodes = self._jsonLd(data)
            movie = nodes.get("Movie", {})
            desc = self._text(movie.get("description", ""))
            title = self._text(movie.get("name", "")) or title
            year = self._text(movie.get("datePublished", ""))[:4] or year
            imdbId = self.cm.ph.getSearchGroups(self._text(movie.get("sameAs", "")) or data, r"imdb\.com/title/(tt\d+)")[0]
            actors = movie.get("actor", [])
            for key, value in (("year", year), ("genres", self._text(movie.get("genre", []))), ("directors", self._text(movie.get("director", []))),
                               ("cast", self._text(actors[:10] if isinstance(actors, list) else actors))):
                if value:
                    info[key] = value
            seconds = self.cm.ph.getSearchGroups(self._text(nodes.get("VideoObject", {}).get("duration", "")), r"PT(\d+)S")[0]
            if seconds:
                minutes = int(seconds) // 60
                info["duration"] = "%dh %02dmin" % (minutes // 60, minutes % 60) if minutes >= 60 else "%dmin" % minutes
            country = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'about-key">Country</span>(.*?)</div>')[0])
            if country:
                info["country"] = country
        meta = {}
        try:
            if imdbId:
                meta = getMetaByImdbId("movie", imdbId)
            if not meta and title:
                meta = getMeta("movie", title, year, maxYearDiff=1)
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = desc or cItem.get("desc", "")
        if plot and text and plot != text and len(text) > 10:
            text = "%s[/br][/br]%s" % (text, plot)
        else:
            text = plot if len(plot) > len(text) else text
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_value":
            self.listValue(self.currItem)
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
        CHostBase.__init__(self, RetroFlix(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("retroflix")

    def withArticleContent(self, cItem):
        return cItem.get("category") == "video"
