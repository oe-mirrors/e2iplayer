# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# 11.01.2026 - Mr.X - Site Fix
# 07.10.2026 - host standard
#   JSON API of einschalten.in (api/movies, api/collections, api/genres, api/search, api/movies/<id>/watch):
#   - every film is a VIDEO row keyed on its own page url (/movies/<id>) - films of one list no longer share
#     the list url (download marker / watched flag / favourite)
#   - watched flag (video:/collection: keys, collection folders show the state of their films), favourites
#     that reopen without menu state, downloaded marker, name normalisation "Title (Year)", sidecar,
#     INFO via moviemeta (IMDb id of the site) + the site's overview/runtime/genres, First / Jump / Next page
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
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
    return "https://einschalten.in/"


class Einschalten(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Einschalten", "cookie": "Einschalten.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "raw_post_data": True, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("api/movies?order=new")},
                     {"category": "list_items", "title": _("Latest added"), "url": self.getFullUrl("api/movies?order=added")},
                     {"category": "list_items", "title": _("Collections"), "url": self.getFullUrl("api/collections")},
                     {"category": "list_value", "title": _("Genres")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("einschalten")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _getJson(self, url, params=None, post_data=None):
        sts, data = self.getPage(url, params, post_data)
        if not sts or not data:
            return None
        try:
            return json.loads(data)
        except Exception:
            printDBG("Einschalten: no JSON from [%s]" % url)
        return None

    def _movieId(self, cItem):
        # m_id (current rows), the /movies/<id> page url, or "id" of favourites saved by older versions
        mid = str(cItem.get("m_id", "") or "")
        if not mid:
            mid = self.cm.ph.getSearchGroups(cItem.get("url", ""), r"/movies/(\d+)")[0]
        if not mid:
            mid = str(cItem.get("id", "") or "")
        return mid if mid.isdigit() else ""

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category == "video":
                mid = self._movieId(cItem)
                return "video:movies/%s" % mid if mid else ""
            if category == "list_items" and cItem.get("coll_id"):
                return "collection:%s" % cItem["coll_id"]
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("Einschalten.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        query = cItem.get("query", "")
        if query:
            params = dict(self.defaultParams)
            params["header"] = dict(params["header"])
            params["header"].update({"Origin": self.MAIN_URL[:-1], "Accept": "application/json, text/plain, */*", "Content-Type": "application/json"})
            data = self._getJson(self.MAIN_URL + "api/search", params, json.dumps({"query": query, "pageNumber": page}))
            # only for "Jump" - the search itself is a POST built from query + page
            pageUrlTpl = "%ssearch?query=%s&pageNumber={page}" % (self.MAIN_URL, urllib_quote_plus(query))
        else:
            baseUrl = re.sub(r"[?&]pageNumber=\d+", "", cItem.get("url", ""))
            pageUrlTpl = baseUrl + ("&" if "?" in baseUrl else "?") + "pageNumber={page}"
            data = self._getJson(pageUrlTpl.format(page=page))
        if not isinstance(data, dict):
            return
        isCollections = not query and "api/collections" in cItem.get("url", "")
        normalize = IsMediaNamingNormalized()
        for js in data.get("data") or []:
            if not isinstance(js, dict) or not js.get("id"):
                continue
            title = self.cleanHtmlStr(js.get("title") or js.get("name") or "")
            if not title:
                continue
            icon = self.MAIN_URL + "api/image/poster/" + js["posterPath"].lstrip("/") if js.get("posterPath") else ""
            params = {"name": "category", "good_for_fav": True, "icon": icon}
            if isCollections:
                desc = self.cleanHtmlStr(js.get("overview") or "")
                years = [str(js.get(k) or "")[:4] for k in ("releaseDateFrom", "releaseDateTo") if js.get(k)]
                if years:
                    desc = ("%s %s" % (_("Year:"), " - ".join(sorted(set(years)))) + ("[/br]" + desc if desc else "")).strip()
                params.update({"category": "list_items", "title": title, "coll_id": str(js["id"]), "desc": desc,
                               "url": "%sapi/movies?collectionId=%s" % (self.MAIN_URL, js["id"])})
                self.addDir(params)
            else:
                year = str(js.get("releaseDate") or "")[:4]
                year = year if year.isdigit() else ""
                desc = "%s %s" % (_("Year:"), year) if year else ""
                dispTitle = "%s (%s)" % (title, year) if (normalize and year and year not in title) else title
                params.update({"category": "video", "title": dispTitle, "m_id": str(js["id"]), "desc": desc,
                               "url": "%smovies/%s" % (self.MAIN_URL, js["id"]),
                               "meta_type": "movie", "meta_title": title, "meta_year": year})
                self.addVideo(params)
        hasNext = bool(data.get("data")) and bool((data.get("pagination") or {}).get("hasMore"))
        addPagingItems(self, cItem, page, hasNext, 0, pageUrlTpl)

    def listValue(self, cItem):
        printDBG("Einschalten.listValue")
        data = self._getJson(self.MAIN_URL + "api/genres")
        if not isinstance(data, list):
            return
        for js in data:
            if not isinstance(js, dict) or not js.get("id"):
                continue
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(js.get("name") or ""),
                         "url": "%sapi/movies?genreId=%s&order=new" % (self.MAIN_URL, js["id"])})

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Einschalten.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "query": searchPattern, "url": "", "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Einschalten.getLinksForVideo [%s]" % cItem)
        mid = self._movieId(cItem)
        if not mid:
            return []
        url = "%sapi/movies/%s/watch" % (self.MAIN_URL, mid)
        data = self._getJson(url)
        streamUrl = data.get("streamUrl", "") if isinstance(data, dict) else ""
        if not self.cm.isValidUrl(streamUrl):
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        name = self.up.getHostName(streamUrl).capitalize()
        if data.get("releaseName"):
            name = "%s - %s" % (name, self.cleanHtmlStr(data["releaseName"]))
        urltab = [{"name": name, "url": strwithmeta(streamUrl, {"Referer": self.MAIN_URL}), "need_resolve": 1}]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    def getVideoLinks(self, url):
        printDBG("Einschalten.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            sidecar = sidecarFromUrlMeta(url, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Einschalten.getArticleContent [%s]" % cItem)
        info = {}
        text = ""
        icon = cItem.get("icon", "")
        if cItem.get("category") == "list_items":
            # collection folder
            data = self._getJson("%sapi/collections/%s" % (self.MAIN_URL, cItem.get("coll_id", "0")))
            if isinstance(data, dict):
                text = ensure_str(data.get("overview") or "")
                if data.get("movieCount"):
                    info["episodes"] = str(data["movieCount"])
                genres = ", ".join(ensure_str(g.get("name", "")) for g in data.get("genres") or [] if isinstance(g, dict))
                if genres:
                    info["genres"] = genres
            return [{"title": cItem.get("title", ""), "text": self.cleanHtmlStr(text) or cItem.get("desc", ""),
                     "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

        mid = self._movieId(cItem)
        data = self._getJson("%sapi/movies/%s" % (self.MAIN_URL, mid)) if mid else None
        title = cItem.get("meta_title", "") or cItem.get("title", "")
        year = cItem.get("meta_year", "")
        imdbId = ""
        if isinstance(data, dict):
            text = ensure_str(data.get("overview") or "")
            title = ensure_str(data.get("title") or title)
            year = str(data.get("releaseDate") or year)[:4]
            imdbId = ensure_str(data.get("imdbId") or "")
            if data.get("runtime"):
                info["duration"] = "%s min" % data["runtime"]
            if data.get("voteAverage"):
                info["rating"] = "%.1f" % float(data["voteAverage"])
            genres = ", ".join(ensure_str(g.get("name", "")) for g in data.get("genres") or [] if isinstance(g, dict))
            if genres:
                info["genres"] = genres
            if data.get("posterPath") and not icon:
                icon = self.MAIN_URL + "api/image/poster/" + data["posterPath"].lstrip("/")
        if year.isdigit():
            info["year"] = year
        meta = {}
        try:
            meta = getMetaByImdbId("movie", imdbId) if imdbId else {}
            if not meta and title:
                meta = getMeta("movie", title, year)
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = self.cleanHtmlStr(text)
        if plot and text and plot != text:
            text = "%s[/br][/br]%s" % (text, plot)
        else:
            text = text or plot or cItem.get("desc", "")
        icon = icon or meta.get("poster", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

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
        CHostBase.__init__(self, Einschalten(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("einschalten")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "video" or (cItem.get("category", "") == "list_items" and bool(cItem.get("coll_id")))
