# -*- coding: utf-8 -*-
LAST_MODIFIED = "29.10.2026"
# 06.04.2026 - MR.X
# 29.10.2026 - rewritten for guardaseriex.best (guarda-serie.ovh is gone; DLE site, Italian series):
#   - Series / Top IMDb / genres of the site menu / search, First / Jump / Next page with the last page
#   - the site has no episode list (its player counts to 12 seasons / 24 episodes): seasons and episodes come
#     from TVmaze by the IMDb id (Cinemeta when TVmaze does not know the show), only aired episodes
#   - links: VixSrc by the IMDb id (/tv/<imdb>/<season>/<episode>) and the site's own player vidxgo
#   - watched flag (series -> season -> episode), favourites, downloaded marker, "Show - SxxExx" names, sidecar,
#     INFO via moviemeta merged with the site's fields
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://guardaseriex.best/"


VIXSRC_URL = "https://vixsrc.to/"
VIDXGO_URL = "https://v.vidxgo.co/"
TVMAZE_URL = "https://api.tvmaze.com/"
CINEMETA_URL = "https://v3-cinemeta.strem.io/"
SEARCH_TPL = "index.php?do=search&subaction=search&search_start={page}&full_search=0&story=%s"


class GuardaSerie(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "GuardaSerie", "cookie": "GuardaSerie.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/guardaserie135.png")
        self.MENU = [{"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serietv-streaming/")},
                     {"category": "list_items", "title": _("Top rated"), "url": self.getFullUrl("top-imdb/")},
                     {"category": "list_genres", "title": _("Genres")}] + self.searchItems()
        self.episodeCache = {}
        self.watchedHelper = IPTVWatchedHelper("guardaserie")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl.split("#", 1)[0], addParams, post_data)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"list_seasons": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
            if cItem.get("type", "") == "video":
                prefix = "video"
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _imdb(text):
        # the covers are named after the IMDb id (/uploads/posters/tt2531336.webp)
        match = re.search(r"tt\d{5,10}", text or "")
        return match.group(0) if match else ""

    def _getJson(self, url):
        sts, data = self.cm.getPage(url, {"header": dict(self.HEADER, Accept="application/json")})
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            return None

    def _episodes(self, imdb):
        # {season: [(episode, title, plot)]} of the aired episodes; TVmaze first, Cinemeta for shows TVmaze lacks
        if imdb in self.episodeCache:
            return self.episodeCache[imdb]
        today = time.strftime("%Y-%m-%d")
        seasons = {}
        show = self._getJson(TVMAZE_URL + "lookup/shows?imdb=" + imdb)
        if isinstance(show, dict) and show.get("id"):
            for ep in self._getJson(TVMAZE_URL + "shows/%s/episodes" % show["id"]) or []:
                if ep.get("season") and ep.get("number") and (ep.get("airdate") or "9999") <= today:
                    plot = self.cleanHtmlStr(ep.get("summary") or "")
                    seasons.setdefault(int(ep["season"]), []).append((int(ep["number"]), ep.get("name") or "", plot))
        if not seasons:
            meta = (self._getJson(CINEMETA_URL + "meta/series/%s.json" % imdb) or {}).get("meta") or {}
            for ep in meta.get("videos") or []:
                number = ep.get("episode") or ep.get("number")
                if ep.get("season") and number and (ep.get("released") or "9999")[:10] <= today:
                    seasons.setdefault(int(ep["season"]), []).append((int(number), ep.get("name") or ep.get("title") or "", ep.get("overview") or ""))
        for season in seasons:
            seasons[season] = sorted(set(seasons[season]))
        self.episodeCache[imdb] = seasons
        return seasons

    def _siteInfo(self, data):
        # the fields of a series page: (info dict, plot, year, imdb id)
        info = {}
        badges = [self.cleanHtmlStr(b) for b in re.findall(r'<span class="badge[^"]*">(.*?)</span>', self.cm.ph.getDataBeetwenMarkers(data, "movieEntry-meta", "</div>", False)[1])]
        year = ""
        for badge in badges:
            if re.match(r"^\d\.\d$", badge):
                info["rating"] = badge
            elif re.match(r"^(?:19|20)\d\d$", badge):
                year = badge
            elif re.match(r"^\d+\s*m$", badge):
                info["duration"] = badge
            elif badge:
                info["language"] = badge
        if year:
            info["year"] = year
        for key, label in (("country", "Nazione"), ("genres", "Categoria")):
            value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<b>%s:</b>(.*?)</div>" % label)[0])
            if value:
                info[key] = value.replace(" / ", ", ")
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="movieEntry-text">(.*?)</div>')[0])
        imdb = self.cm.ph.getSearchGroups(data, r"""var\s+imdb\s*=\s*['"](tt\d+)""")[0]
        return info, plot, year, imdb

    def _pageInfo(self, cItem):
        # imdb id, plot and year of a series: from the row, else from its page
        imdb, plot, year = cItem.get("imdb", ""), cItem.get("plot", ""), cItem.get("s_year", "")
        if not imdb:
            sts, data = self.getPage(cItem["url"])
            if sts:
                _info, plot, year, imdb = self._siteInfo(data)
        return imdb, plot, year

    ###################################################
    # lists
    ###################################################
    def _addTiles(self, data, cItem):
        count = 0
        seen = set()
        for block in data.split('<div class="movieItem"')[1:]:
            url = self.cm.ph.getSearchGroups(block, r'<a href="([^"]+\.html)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'data-title="([^"]+)"')[0])
            if not url or not title or url in seen:
                continue
            seen.add(url)
            count += 1
            # the jpg fallback of the cover (the webp files first)
            icon = self.cm.ph.getSearchGroups(block, r"this\.src='([^']+\.jpg[^']*)'")[0] or self.cm.ph.getSearchGroups(block, r'data-cover="([^"]+)"')[0]
            year = self.cm.ph.getSearchGroups(block, r'data-year="(\d{4})"')[0]
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'data-text="([^"]*)"')[0])
            genres = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'data-category="([^"]*)"')[0])
            desc = " | ".join("%s: %s" % (k, v) for k, v in ((_("Year"), year), (_("Genre"), genres), (_("Rating"), self.cm.ph.getSearchGroups(block, r'data-rate="([^"]+)"')[0])) if v)
            params = stripPagerKeys(dict(cItem), ("base_url",))
            params.update({"good_for_fav": True, "category": "list_seasons", "title": title, "s_title": title, "url": self.getFullUrl(url),
                           "icon": self.getFullIconUrl(icon) if icon else self.DEFAULT_ICON_URL, "desc": "%s[/br]%s" % (desc, plot) if plot else desc,
                           "imdb": self._imdb(block), "s_year": year, "plot": plot, "meta_type": "tv"})
            self.addDir(params)
        return count

    def listItems(self, cItem):
        printDBG("GuardaSerie.listItems |%s|" % cItem)
        page = max(1, int(cItem.get("page", 1) or 1))
        baseUrl = cItem.get("base_url") or cItem["url"]
        sts, data = self.getPage(baseUrl if page <= 1 else "%spage/%d/" % (baseUrl, page))
        if not sts:
            return
        count = self._addTiles(data, cItem)
        nav = self.cm.ph.getDataBeetwenMarkers(data, 'id="navigation"', "</main>", False)[1]
        lastPage = max([int(n) for n in re.findall(r"/page/(\d+)/", nav)] + [page])
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        addPagingItems(self, listItem, page, bool(count) and lastPage > page, lastPage, baseUrl.replace("{", "{{").replace("}", "}}") + "page/{page}/")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("GuardaSerie.listSearchResult [%s]" % searchPattern)
        page = max(1, int(cItem.get("page", 1) or 1))
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        pageTpl = self.getFullUrl(SEARCH_TPL % urllib_quote_plus(pattern))
        sts, data = self.getPage(pageTpl.format(page=page))
        if not sts:
            return
        count = self._addTiles(data, cItem)
        lastPage = max([int(n) for n in re.findall(r"list_submit\((\d+)\)", data)] + [page])
        listItem = dict(cItem, category="search_next_page", s_pattern=pattern)
        addPagingItems(self, listItem, page, bool(count) and lastPage > page, lastPage, pageTpl)

    def listGenres(self, cItem):
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        seen = set()
        for url, title in re.findall(r'<a class="dropdown-item" href="([^"]+)">([^<]+)</a>', data):
            if url in seen:
                continue
            seen.add(url)
            self.addDir(dict(cItem, good_for_fav=True, category="list_items", title=self.cleanHtmlStr(title), url=self.getFullUrl(url)))

    def listSeasons(self, cItem):
        printDBG("GuardaSerie.listSeasons |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        imdb, plot, year = self._pageInfo(cItem)
        seasons = self._episodes(imdb) if imdb else {}
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", "") or cItem["title"]
        fields = {"s_title": sTitle, "s_year": year, "imdb": imdb, "plot": plot}
        if len(seasons) == 1:
            season = list(seasons)[0]
            self.listEpisodes(dict(cItem, category="list_episodes", season=str(season), url="%s#s%s" % (url, season), **fields))
            return
        normalize = IsMediaNamingNormalized()
        for season in sorted(seasons):
            seasonTag = formatSxxExx(season) if normalize else "%s %s" % (_("Season"), season)
            params = stripPagerKeys(dict(cItem))
            params.update(fields)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (sTitle, seasonTag), "season": str(season),
                           "url": "%s#s%s" % (url, season), "desc": "%s: %d[/br]%s" % (_("Episodes"), len(seasons[season]), plot)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("GuardaSerie.listEpisodes |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        season = str(cItem.get("season", "") or self.cm.ph.getSearchGroups(cItem["url"], r"#s(\d+)")[0])
        imdb, plot, year = self._pageInfo(cItem)
        episodes = self._episodes(imdb).get(int(season or 0), []) if imdb else []
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", "") or cItem["title"]
        normalize = IsMediaNamingNormalized()
        for episode, name, epPlot in episodes:
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            else:
                title = "%s - %s %s - %s %s" % (sTitle, _("Season"), season, _("Episode"), episode)
            if name and not re.match(r"^(?:Episod(?:e|io)|Chapitre|Folge)\s*\d+$", name, re.I):
                title = "%s - %s" % (title, name)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "url": "%s#s%se%s" % (url, season, episode),
                           "season": season, "episode": str(episode), "imdb": imdb, "s_year": year, "plot": plot, "desc": epPlot or plot, "meta_type": "tv"})
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("GuardaSerie.getLinksForVideo [%s]" % cItem.get("url", ""))
        imdb, plot, year = self._pageInfo(cItem)
        season, episode = str(cItem.get("season", "") or ""), str(cItem.get("episode", "") or "")
        if not imdb or not season or not episode:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        # VixSrc takes the IMDb id; vidxgo the IMDb digits
        urltab = [{"name": "VixSrc", "url": strwithmeta("%stv/%s/%s/%s?lang=it" % (VIXSRC_URL, imdb, season, episode), {"Referer": self.MAIN_URL}), "need_resolve": 1},
                  {"name": "vidxgo", "url": strwithmeta("%s%s/%s/%s" % (VIDXGO_URL, imdb[2:], season, episode), {"Referer": self.MAIN_URL}), "need_resolve": 1}]
        # the lookup of the INFO view (getMetaByImdbId, else getMeta by title)
        metaQuery = sidecarMetaQuery("tv", cItem.get("s_title", "") or cItem.get("title", ""), year, imdbId=imdb, skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), plot, metaQuery=metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("GuardaSerie.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("GuardaSerie.getArticleContent [%s]" % cItem.get("url", ""))
        info, plot, year, imdb = {}, cItem.get("plot", ""), cItem.get("s_year", ""), cItem.get("imdb", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot, year, siteImdb = self._siteInfo(data)
            imdb = imdb or siteImdb
        title = cItem.get("s_title", "") or cItem.get("title", "")
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId("tv", imdb)
            if not meta:
                meta = getMeta("tv", title, year)
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        text = cItem.get("desc", "") if cItem.get("type") == "video" and cItem.get("desc") else plot
        metaPlot = meta.get("plot", "")
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("GuardaSerie.handleService name[%s], category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
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
        CHostBase.__init__(self, GuardaSerie(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("guardaserie")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
