# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 host standard
#   - cpasmieux.is (French movies and series, DLE site): movies, series, movie genres, search
#   - First page / Jump / Next page on every list (/<list>/<n>/), search paged by /search/<q>/<n>/
#   - movies are VIDEO rows keyed on their page url; series -> seasons -> episodes (site order
#     reversed to ascending); search results open as a folder (the list does not tell movie from series)
#   - links: the player list of the page -> urlparser (kokoflix / kakaflix redirect followed on play)
#   - watched flag, downloaded flag, favourites, name normalisation ("Title (Year)", "Show - SxxExx"),
#     sidecar, INFO via moviemeta + the site's fields
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://www.cpasmieux.is/"


TILE_RE = re.compile(r'(?s)<div class="movie-item2">(.*?)</a>\s*</div>')
SEASON_URL_RE = re.compile(r"-saison-(\d+)\.html$", re.I)
EPISODE_URL_RE = re.compile(r"-saison-(\d+)-episode-(\d+)\.html$", re.I)
SEARCH_PAGE_SIZE = 18
VIDEO_CATEGORIES = ("cpm_video",)
FOLDER_CATEGORIES = ("cpm_series", "cpm_season", "cpm_explore")
LIST_SEP_RE = re.compile(r",\s*")


def _joinList(text):
    # "a ,b , c" -> "a, b, c": the spaces around each comma are dropped
    parts = LIST_SEP_RE.split(text)
    return ", ".join([p.rstrip() for p in parts[:-1]] + parts[-1:])


class CpasMieux(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cpasmieux", "cookie": "cpasmieux.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/cpasmieux135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.MENU = [
            {"category": "cpm_list", "title": _("Movies"), "url": self.getFullUrl("filmstreaming/"), "kind": "movie"},
            {"category": "cpm_list", "title": _("Series"), "url": self.getFullUrl("seriestreaming/"), "kind": "tv"},
            {"category": "cpm_genres", "title": _("Genres")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("cpasmieux")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", url or "").split("#")[0].rstrip("/").lower()

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("cpm_list",):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS + ("kind",) if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            category = cItem.get("category", "")
            if category in VIDEO_CATEGORIES:
                return "video:%s" % path
            if category in ("cpm_series", "cpm_explore"):
                return "series:%s" % path
            if category == "cpm_season":
                return "season:%s" % path
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listGenres(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        seen = set()
        for url, label in re.findall(r'<a href="(/filmstreaming/genre/[^"]+)"[^>]*>([^<]+)</a>', data):
            label = self.cleanHtmlStr(label)
            if not label or url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "category": "cpm_list", "title": label, "url": self.getFullUrl(url), "kind": "movie", "good_for_fav": True})

    def _tiles(self, data):
        # [(url, title, icon, quality)] of the result grid
        content = self.cm.ph.getDataBeetwenMarkers(data, "dle-content", "col-side", False)[1] or data
        tiles = []
        for block in TILE_RE.findall(content):
            url = self.cm.ph.getSearchGroups(block, r'href="([^"]+\.html)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="mi2-title">(.*?)</div>')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<img[^>]+alt="([^"]+)"')[0])
            if not url or not title:
                continue
            icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0]
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<span class="mi2-version">([^<]+)<')[0])
            tiles.append((self.getFullUrl(url), title, self.getFullIconUrl(icon) if icon else "", quality))
        return tiles

    def _addTile(self, url, title, icon, quality, kind):
        # "HD" on movies, "VF" / "VOSTFR" on series
        label = _("Version") if quality.upper().startswith("V") else _("Quality")
        desc = "%s: %s" % (label, quality) if quality else ""
        params = {"name": "category", "good_for_fav": True, "url": url, "title": title, "icon": icon, "desc": desc,
                  "meta_title": title, "meta_year": ""}
        if kind == "movie":
            params.update({"category": "cpm_video", "meta_type": "movie"})
            self.addVideo(params)
        elif kind == "tv":
            params.update({"category": "cpm_series", "meta_type": "tv", "s_title": title})
            self.addDir(params)
        else:
            params.update({"category": "cpm_explore", "s_title": title})
            self.addDir(params)

    def _lastPage(self, data):
        nav = self.cm.ph.getDataBeetwenMarkers(data, "pagi-nav", "</div>", False)[1]
        pages = [int(x) for x in re.findall(r"/(\d+)/\"[^>]*>\d+<", nav)]
        return max(pages) if pages else 0

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        url = baseUrl if page <= 1 else "%s%d/" % (baseUrl, page)
        printDBG("CpasMieux.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        tiles = self._tiles(data)
        for tile in tiles:
            self._addTile(*(tile + (cItem.get("kind", ""),)))
        lastPage = self._lastPage(data)
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        addPagingItems(self, listItem, page, bool(tiles) and lastPage > page, lastPage, baseUrl.replace("{", "{{").replace("}", "}}") + "{page}/")

    def listSearchResult(self, cItem, searchPattern, searchType):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self.getFullUrl("search/%s/" % urllib_quote(searchPattern.strip()))
        url = baseUrl if page <= 1 else "%s%d/" % (baseUrl, page)
        printDBG("CpasMieux.listSearchResult [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        tiles = self._tiles(data)
        for tile in tiles:
            self._addTile(*(tile + ("",)))
        # the search has no page bar: a full page means there may be another one
        listItem = dict(cItem, category="search_next_page", base_url=baseUrl)
        addPagingItems(self, listItem, page, len(tiles) >= SEARCH_PAGE_SIZE)

    def _seasons(self, data):
        # [(season, url, icon)] of the season tiles of a series page
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="seasons">', "smart-text-s", False)[1]
        seasons, seen = [], set()
        for url, inner in re.findall(r'(?s)<a href="([^"]+-saison-\d+\.html)"[^>]*>(.*?)</a>', block):
            season = int(SEASON_URL_RE.search(url).group(1))
            if season in seen:
                continue
            seen.add(season)
            icon = self.cm.ph.getSearchGroups(inner, r'<img[^>]+src="([^"]+)"')[0]
            seasons.append((season, self.getFullUrl(url), self.getFullIconUrl(icon) if icon else ""))
        return sorted(seasons)

    def exploreItem(self, cItem):
        # search result: a series page lists its seasons, a movie page is the movie itself
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        if self._seasons(data):
            self.listSeasons(cItem, data)
            return
        params = stripPagerKeys(dict(cItem))
        params.update({"category": "cpm_video", "meta_type": "movie"})
        year = self._siteInfo(data)[2].get("year", "")
        if year and IsMediaNamingNormalized():
            params["title"] = "%s (%s)" % (cItem["title"], year)
        params["meta_year"] = year
        self.addVideo(params)

    def listSeasons(self, cItem, data=None):
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        seasons = self._seasons(data)
        if len(seasons) == 1:
            season, url, icon = seasons[0]
            self.listEpisodes(dict(cItem, url=url, s_season=season, icon=icon or cItem.get("icon", ""), category="cpm_season"))
            return
        if not seasons:
            SetIPTVPlayerLastHostError(_("No stream available"))
        show = cItem.get("s_title") or cItem.get("title", "")
        for season, url, icon in seasons:
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "cpm_season", "good_for_fav": True, "url": url, "s_title": show, "s_season": season,
                           "title": "%s %d" % (_("Season"), season), "icon": icon or cItem.get("icon", ""), "meta_type": "tv"})
            self.addDir(params)

    def listEpisodes(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="seasons">', "</div>\n", False)[1] or data
        episodes, seen = [], set()
        for url in re.findall(r'<a href="([^"]+-saison-\d+-episode-\d+\.html)"', block):
            numbers = EPISODE_URL_RE.search(url)
            key = (int(numbers.group(1)), int(numbers.group(2)))
            if key not in seen:
                seen.add(key)
                episodes.append(key + (self.getFullUrl(url),))
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title") or cItem.get("title", "")
        for season, episode, url in sorted(episodes):
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = "%s - %s %d - %s %d" % (show, _("Season"), season, _("Episode"), episode)
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "cpm_video", "good_for_fav": True, "title": title, "url": url,
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv"})
            self.addVideo(params)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of a movie / series / episode page
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="full-right">', "</div>", False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)Synopsis:</span>\s*</p>\s*<p>(.*?)</p>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        info = {}
        for key, label in (("original_title", "Titre Origine"), ("year", "Date de sortie"), ("genres", "Genre"), ("actors", "Acteurs"),
                           ("director", "Director"), ("quality", "Qualit[^:<]*"), ("translation", "Traduction")):
            value = self.cm.ph.getSearchGroups(block, r"(?s)<span>%s:</span>(.*?)</li>" % label)[0]
            value = _joinList(self.cleanHtmlStr(value.replace("&nbsp;", " "))).strip(", ")
            if value:
                info[key] = value
        return story, poster, info

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("CpasMieux.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            return []
        block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="player-list">', "</ul>", False)[1]
        urltab, seen = [], set()
        for playerUrl, server in re.findall(r'(?s)data-url="([^"]+)".*?<span class="serv">([^<]*)</span>', block):
            playerUrl = self.getFullUrl(playerUrl)
            if playerUrl in seen or not self.cm.isValidUrl(playerUrl):
                continue
            seen.add(playerUrl)
            name = self.cleanHtmlStr(server) or self.up.getHostName(playerUrl)
            same = len([x for x in urltab if x["name"] == name or x["name"].startswith(name + " #")])
            if same:
                name = "%s #%d" % (name, same + 1)
            urltab.append({"name": name, "url": strwithmeta(playerUrl, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        story = self._siteInfo(data)[0]
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("CpasMieux.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if "kokoflix" in videoUrl or "kakaflix" in videoUrl:
            # redirect page (302) to the real hoster
            params = dict(self.defaultParams, header=dict(self.HEADER, Referer=self.getMainUrl()), no_redirection=True)
            sts, _data = self.getPage(videoUrl, params)
            target = self.cm.meta.get("location", "") if sts else ""
            if not self.cm.isValidUrl(target) or target == videoUrl:
                SetIPTVPlayerLastHostError(_("No stream available"))
                return []
            videoUrl = strwithmeta(target, {"Referer": self.getMainUrl()})
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("CpasMieux.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        mediaType = cItem.get("meta_type") or ("tv" if self._seasons(data or "") else "movie")
        metaTitle = info.get("original_title") or cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(mediaType, metaTitle, cItem.get("meta_year") or info.get("year", ""))
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = meta.get("poster") or (self.getFullIconUrl(poster) if poster else cItem.get("icon", ""))
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
        printDBG("CpasMieux.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "cpm_genres":
            self.listGenres(self.currItem)
        elif category == "cpm_list":
            self.listItems(self.currItem)
        elif category == "cpm_explore":
            self.exploreItem(self.currItem)
        elif category == "cpm_series":
            self.listSeasons(self.currItem)
        elif category == "cpm_season":
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


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, CpasMieux(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cpasmieux")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in FOLDER_CATEGORIES
