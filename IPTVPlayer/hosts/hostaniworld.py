# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# 02.02.2026 - Mr.X
#   - search: no crash on an empty / non-JSON ajax answer, only series links (no season / episode / page links)
#   - "All" (2500+ series) and "Latest episodes" are paged here (100 rows), genre / A-Z lists use the site's
#     pages with First page / Jump / Next page (last page from the pager)
#   - series -> seasons ("Filme" included) -> episodes; watched flag (stable page-path keys, series -> season ->
#     episode), downloaded flag on the episode url, favourites, name normalisation ("Show - SxxExx"), sidecar,
#     INFO via moviemeta (the series' IMDb id) + the site's description / cast / episode synopsis
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://aniworld.to/"


PAGE_SIZE = 100  # rows per page of the lists the site sends in one piece
LANGUAGES = {"1": "DE", "2": "JPN, Sub: EN", "3": "JPN, Sub: DE"}
SERIES_PATH_RE = re.compile(r"^/anime/stream/[^/?#]+$")


class AniWorld(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode", "s_url",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "AniWorld", "cookie": "AniWorld.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("public/img/facebook.jpg")
        self.MENU = [
            {"category": "list_items", "title": _("New"), "url": self.getFullUrl("neu")},
            {"category": "list_items", "title": _("Popular"), "url": self.getFullUrl("beliebte-animes")},
            {"category": "list_newepisodes", "title": _("Latest episodes"), "url": self.getFullUrl("neue-episoden")},
            {"category": "list_items", "title": _("All"), "url": self.getFullUrl("animes-alphabet")},
            {"category": "list_value", "title": _("A-Z"), "s": 'class="catalogNav">', "filter": "/katalog/"},
            {"category": "list_value", "title": _("Genres"), "s": 'class="homeContentGenresList">', "filter": "/genre/"}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("aniworld")
        self.wfInitFolderCache()
        self.listCache = {}

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == "":
            return ""
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {"Cookie": cookieHeader, "User-Agent": self.HEADER.get("User-Agent")})

    @staticmethod
    def _path(url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", url or "").split("?")[0].split("#")[0].rstrip("/").lower()

    @staticmethod
    def _seasonOf(url):
        # "staffel-3" -> 3, the "filme" (movies) part -> 0
        num = re.search(r"/staffel-(\d+)", url or "")
        return int(num.group(1)) if num else 0

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("aw_video", "aw_series", "aw_season"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"aw_video": "video", "aw_series": "series", "aw_season": "season"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _seriesParams(self, cItem, url, title, icon="", desc=""):
        params = stripPagerKeys(dict(cItem), ("base_url", "s", "filter"))
        params.update({"name": "category", "good_for_fav": True, "category": "aw_series", "title": title, "url": url, "icon": icon, "desc": desc,
                       "s_title": title, "s_url": url, "meta_type": "tv", "meta_title": title})
        for key in ("s_season", "s_episode", "meta_year"):
            params.pop(key, None)
        return params

    def _parseSeriesList(self, data):
        items = []
        seen = set()
        blocks = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="col-md-15 col-sm-3 col-xs-6">', "</div>")
        isIndex = not blocks
        if isIndex:
            blocks = self.cm.ph.getAllItemsBeetwenMarkers(data, "data-alternative", "</li>")
        for item in blocks:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            if not url or url in seen:
                continue
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"<h3>(.*?)</h3>")[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r">([^<]+)</a>")[0]) if isIndex else ""
            if not title:
                title = self.cleanHtmlStr(re.split(r" [Ss]tream ", self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])[0])
            if not title:
                continue
            seen.add(url)
            items.append({"url": url, "title": title, "icon": self.cm.ph.getSearchGroups(item, 'data-src="([^"]+)')[0],
                          "desc": self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"<small>(.*?)</small>")[0])})
        return items

    def _cachedList(self, url, parser):
        # lists the site sends in one piece are read once per session folder and paged here
        if url not in self.listCache:
            sts, data = self.getPage(url)
            if not sts:
                return []
            self.listCache = {url: parser(data)}
        return self.listCache.get(url, [])

    def listItems(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        baseUrl = cItem.get("base_url") or cItem["url"]
        printDBG("AniWorld.listItems [%s] page %d" % (baseUrl, page))
        if baseUrl.rstrip("/").endswith("/animes-alphabet"):
            items = self._cachedList(baseUrl, self._parseSeriesList)
            start = (page - 1) * PAGE_SIZE
            for item in items[start:start + PAGE_SIZE]:
                self.addDir(self._seriesParams(cItem, item["url"], item["title"], self.getFullIconUrl(item["icon"]), item["desc"]))
            lastPage = (len(items) + PAGE_SIZE - 1) // PAGE_SIZE
            listItem = dict(cItem)
            listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
            addPagingItems(self, listItem, page, page < lastPage, lastPage, baseUrl)
            return
        url = baseUrl if page <= 1 else "%s/%d" % (baseUrl.rstrip("/"), page)
        sts, data = self.getPage(url)
        if not sts:
            return
        items = self._parseSeriesList(data)
        for item in items:
            self.addDir(self._seriesParams(cItem, item["url"], item["title"], self.getFullIconUrl(item["icon"]), item["desc"]))
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'pagination">', "</ul>", False)[1]
        if not pager:
            return
        nums = [int(n) for n in re.findall(r'href="[^"]+/(\d+)"', pager)]
        lastPage = max(nums + [page])
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, bool(items) and lastPage > page, lastPage, baseUrl.rstrip("/") + "/{page}")

    def _seriesInfo(self, data):
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'data-full-description="([^"]+)')[0])
        icon = self.cm.ph.getSearchGroups(data, 'data-src="(/public/img/cover/[^"]+)')[0]
        year = self.cm.ph.getSearchGroups(data, r'itemprop="startDate"><a[^>]*>(\d{4})<')[0]
        imdb = self.cm.ph.getSearchGroups(data, r'data-imdb="(tt\d+)"')[0]
        return desc, self.getFullIconUrl(icon) if icon else "", year, imdb

    def listSeasons(self, cItem):
        printDBG("AniWorld.listSeasons [%s]" % cItem.get("url"))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        desc, icon, year, _imdb = self._seriesInfo(data)
        show = cItem.get("s_title") or cItem.get("title", "")
        block = self.cm.ph.getDataBeetwenMarkers(data, "strong>Staffeln", "</ul>", False)[1]
        seasons = []
        for url, label in re.findall(r'href="([^"]+)"\s*title="([^"]+)', block):
            url = self.getFullUrl(url)
            if url not in [s[1] for s in seasons]:
                seasons.append((self._seasonOf(url), url, self.cleanHtmlStr(label)))
        seasons.sort(key=lambda s: (s[0] == 0, s[0]))  # films after the seasons
        for num, url, label in seasons:
            params = stripPagerKeys(dict(cItem), ("base_url", "s", "filter"))
            params.update({"good_for_fav": True, "category": "aw_season", "title": "%s - %s" % (show, label), "url": url, "icon": icon or cItem.get("icon", ""),
                           "desc": desc or cItem.get("desc", ""), "s_title": show, "s_season": num, "s_url": cItem["url"], "meta_year": year})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("AniWorld.listEpisodes [%s]" % cItem.get("url"))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title") or cItem.get("title", "")
        season = cItem.get("s_season", self._seasonOf(cItem["url"]))
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'itemprop="episode"', "</tr>"):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            if not url:
                continue
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, "<span>([^<]+)")[0])
            if not name:
                # no English title yet (e.g. an announced episode): the German one / "[Start: ...]" note
                name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, "<strong>([^<]+)")[0])
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '">([^<]+)</a>')[0])
            episode = self.cm.ph.getSearchGroups(item, r'itemprop="episodeNumber" content="(\d+)"')[0] or \
                self.cm.ph.getSearchGroups(url, r"/(?:episode|film)-(\d+)")[0]
            if normalize and season and episode:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            elif normalize and name:
                title = "%s - %s" % (show, self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, "<strong>([^<]+)")[0]) or name)
            else:
                title = "{} - {}{}".format(cItem["title"], name, " - " + label if label else "")
            params = stripPagerKeys(dict(cItem), ("base_url", "s", "filter"))
            params.update({"good_for_fav": True, "category": "aw_video", "title": title, "url": url, "s_title": show, "s_season": season, "s_episode": episode,
                           "desc": name})
            self.addVideo(params)

    def listValue(self, cItem):
        printDBG("AniWorld.listValue")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, cItem["s"], "</ul>", False)[1]
        for url, title in re.findall(r'href="([^"]+)"[^>]*>([^<]+)<', data):
            if cItem.get("filter", "") not in url:
                continue
            params = stripPagerKeys(dict(cItem), ("base_url",))
            params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url)})
            params.pop("s", None)
            params.pop("filter", None)
            self.addDir(params)

    def _parseNewEpisodes(self, data):
        items = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="row">', "</div>"):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            show = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, "<strong>([^<]+)")[0])
            se = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'bigListTag blue2">([^<]+)')[0])
            date = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'elementFloatRight">([^<]+)')[0])
            if not re.search(r"/(?:episode|film)-\d+", url) or not show or url in seen:  # one row per language
                continue
            seen.add(url)
            items.append({"url": url, "show": show, "se": se, "date": date})
        return items

    def listNewEpisodes(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        baseUrl = cItem.get("base_url") or cItem.get("url") or self.getFullUrl("neue-episoden")
        printDBG("AniWorld.listNewEpisodes page %d" % page)
        normalize = IsMediaNamingNormalized()
        items = self._cachedList(baseUrl, self._parseNewEpisodes)
        start = (page - 1) * PAGE_SIZE
        for item in items[start:start + PAGE_SIZE]:
            url = item["url"]
            season, episode = self._seasonOf(url), self.cm.ph.getSearchGroups(url, r"/episode-(\d+)")[0]
            if normalize and season and episode:
                title = "%s - %s" % (item["show"], formatSxxExx(season, episode))
            else:
                title = " - ".join(x for x in (item["show"], item["se"]) if x)
            params = stripPagerKeys(dict(cItem), ("base_url",))
            params.update({"good_for_fav": True, "category": "aw_video", "title": title, "url": url, "desc": item["date"], "s_title": item["show"],
                           "s_season": season, "s_episode": episode, "s_url": re.sub(r"/(?:staffel-\d+|filme)/.*$", "", url), "meta_type": "tv", "meta_title": item["show"]})
            self.addVideo(params)
        lastPage = (len(items) + PAGE_SIZE - 1) // PAGE_SIZE
        listItem = dict(cItem)
        listItem.update({"category": "list_newepisodes", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, page < lastPage, lastPage, baseUrl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AniWorld.listSearchResult [%s]" % searchPattern)
        searchPattern = (searchPattern or "").strip()
        if not searchPattern:
            return
        sts, data = self.getPage(self.getFullUrl("ajax/search"), post_data={"keyword": searchPattern})
        if not sts or not (data or "").strip():
            return
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return
        if not isinstance(data, list):
            return
        cItem = dict(cItem)
        cItem["name"] = "category"
        for item in data:
            if not isinstance(item, dict):
                continue
            link = item.get("link") or ""
            title = self.cleanHtmlStr(item.get("title") or "")
            if not title or not SERIES_PATH_RE.match(link):
                continue
            self.addDir(self._seriesParams(cItem, self.getFullUrl(link), title, "", self.cleanHtmlStr(item.get("description") or "")))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("AniWorld.getLinksForVideo [%s]" % cItem.get("url"))
        urltab = []
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'changeLanguageBox"', "</ul>")
        data = re.compile(r'<li[^>]*?data-lang-key\s*=\s*"(\d+)".*?data-link-target="([^"]+).*?<h4>(.*?)</h4>', re.DOTALL).findall(data[0] if data else "")
        for lang, url, title in data:
            name = self.cleanHtmlStr(title)
            if lang in LANGUAGES:
                name = "%s (%s)" % (name, LANGUAGES[lang])
            urltab.append({"name": name, "url": strwithmeta(self.getFullUrl(url), {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, url):
        printDBG("AniWorld.getVideoLinks [%s]" % url)
        sidecar = sidecarFromUrlMeta(url, IsSidecarEnabled())
        params = dict(self.defaultParams)
        params["no_redirection"] = True
        self.cm.getPage(url, params)
        location = self.cm.meta.get("location", "")
        if location and self.cm.isValidUrl(location):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(location), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("AniWorld.getArticleContent [%s]" % cItem.get("url"))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            data = ""
        desc, icon, year, imdb = self._seriesInfo(data)
        info = {}
        if year:
            info["year"] = year
        fields = {"country": 'itemprop="countryOfOrigin".*?itemprop="name">([^<]+)', "director": 'itemprop="director.*?itemprop="name">([^<]+)',
                  "actors": 'itemprop="actor.*?itemprop="name">([^<]+)', "production": 'itemprop="creator.*?itemprop="name">([^<]+)'}
        for key, pattern in fields.items():
            value = re.findall(pattern, data)
            if value:
                info[key] = ", ".join(self.cleanHtmlStr(v) for v in value[:6])
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId("tv", imdb)
            if not meta and (cItem.get("s_title") or cItem.get("meta_title")):
                meta = getMeta("tv", cItem.get("s_title") or cItem.get("meta_title"), year)
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        text = desc or meta.get("plot", "") or cItem.get("desc", "")
        if cItem.get("category") == "aw_video":
            epTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'class="episodeGermanTitle">([^<]+)')[0])
            epDesc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="descriptionSpoiler"[^>]*>(.*?)</p>')[0])
            epText = "[/br]".join(x for x in (epTitle, epDesc) if x)
            if epText:
                text = epText
        icon = icon or meta.get("poster") or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("AniWorld.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category in ("aw_series", "list_seasons"):
            self.listSeasons(self.currItem)
        elif category in ("aw_season", "list_episodes"):
            self.listEpisodes(self.currItem)
        elif category == "list_value":
            self.listValue(self.currItem)
        elif category == "list_newepisodes":
            self.listNewEpisodes(self.currItem)
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
        CHostBase.__init__(self, AniWorld(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("aniworld")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("aw_video", "aw_series", "aw_season")
