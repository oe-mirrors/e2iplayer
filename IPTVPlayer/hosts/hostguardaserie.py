# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# 06.04.2026 - MR.X
# 08.10.2026 - host standard (guarda-serie.ovh):
#   - episodes get their own url (series page + "#s<season>e<episode>") - before every episode of a series had the
#     series url (one downloaded marker / watched key for all of them); seasons keep the page url + "#s<season>"
#   - watched flag (series -> season -> episode), favourites reopen without state (also the old rows), downloaded
#     marker, "Show - SxxExx" names, sidecar on the links, INFO via moviemeta merged with the site's fields
#     (genres, cast, year, status, seasons, episodes, rating, plot)
#   - First / Jump / Next page with the last page from the pager (also for the search), a series with one
#     season lists its episodes directly, genres from the site menu (no IndexError on an empty page)
#   - default user agent, Cloudflare: getPageCFProtection + covers with the cookie / UA that passed the check
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://guarda-serie.ovh/"


PLAYER_URL = "https://vixsrc.to/"


class GuardaSerie(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "GuardaSerie", "cookie": "GuardaSerie.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.USER_AGENT = self.HEADER.get("User-Agent", "")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + "static/logo.png"
        self.MENU = [{"category": "list_items", "title": _("Series"), "url": self.getFullUrl("archive")},
                     {"category": "list_items", "title": _("Top rated"), "url": self.getFullUrl("archive?sort=vote")},
                     {"category": "list_genres", "title": _("Genres")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("guardaserie")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl.split("#", 1)[0], addParams, post_data)

    def getFullIconUrl(self, url, currUrl=None):
        # the covers sit behind the same Cloudflare check as the pages: cf_clearance + the UA that passed it
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http"):
            return url
        meta = {"Referer": self.MAIN_URL, "User-Agent": self.USER_AGENT}
        try:
            # getCookieHeader logs tracebacks for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.USER_AGENT, "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

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
            season, episode = self._season(cItem), str(cItem.get("episode", "") or "")
            if "#" not in url:
                # season / episode rows from before 08.10.2026 carried the plain series url
                if prefix == "season" and season:
                    url = "%s#s%s" % (url, season)
                elif prefix == "video" and season and episode:
                    url = "%s#s%se%s" % (url, season, episode)
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _season(cItem):
        # "season" since 08.10.2026, "seasons" in older favourites
        return str(cItem.get("season", "") or cItem.get("seasons", "") or "").strip()

    @staticmethod
    def _pageUrlTpl(url):
        # the list url with "{page}" in its page parameter
        url = re.sub(r"[?&]page=\d+", "", url).replace("{", "{{").replace("}", "}}")
        return url + ("&" if "?" in url else "?") + "page={page}"

    def _siteInfo(self, data):
        # the fields of a series page: (info dict, plot, year, tmdb id)
        info = {}
        rating = self.cm.ph.getSearchGroups(data, r'class="entry-imdb">[^0-9<]*([0-9.]+)')[0]
        if rating:
            info["rating"] = rating
        genres = self.cm.ph.getDataBeetwenMarkers(data, 'itemprop="genre"', "</span>", False)[1]
        genres = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r">([^<]+)</a>", genres))
        if genres:
            info["genres"] = genres
        for key, label in (("language", "Lingua"), ("cast", "Cast"), ("year", "Anno"), ("status", "Stato")):
            value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<b>%s:</b>\s*</li>\s*<li>(.*?)</li>" % label)[0])
            if value:
                info[key] = value
        year = self.cm.ph.getSearchGroups(info.get("year", ""), r"((?:19|20)\d\d)")[0]
        if year:
            info["year"] = year
        for key, prop in (("seasons", "numberOfSeasons"), ("episodes", "numberOfEpisodes")):
            value = self.cm.ph.getSearchGroups(data, r'itemprop="%s">(\d+)<' % prop)[0]
            if value:
                info[key] = value
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<b>Trama[^<]*</b>\s*<br\s*/?>(.*?)</div>")[0])
        if not plot:
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]+)')[0])
            plot = re.sub(r"^Guarda .+? streaming gratis,\s*", "", plot)
        tmdb = self.cm.ph.getSearchGroups(data, r"var\s+tmdbID\s*=\s*(\d+)")[0]
        return info, plot, year, tmdb

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("GuardaSerie.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        pageUrlTpl = self._pageUrlTpl(cItem["url"])
        sts, data = self.getPage(pageUrlTpl.format(page=page) if page > 1 else cItem["url"])
        if not sts:
            return
        pager = self.cm.ph.getDataBeetwenMarkers(data, "mlnew-pagination", "</div>", False)[1]
        pages = [int(n) for n in re.findall(r"[?&]page=(\d+)", pager)]
        hasNext = bool(re.search(r">\s*Next", pager))
        seen = set()
        for block in data.split('class="mlnew"')[1:]:
            url = self.cm.ph.getSearchGroups(block, r'mlnh-thumb">\s*<a href="([^"]+)"')[0]
            if not url or url in seen:
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<a href="[^"]+" title="([^"]+)"')[0]).replace(" streaming guardaserie", "")
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(block, r'<img src="([^"]+)"')[0])
            rating = self.cm.ph.getSearchGroups(block, r'mlnh-imdb">[^0-9<]*([0-9.]+)')[0]
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "title": title, "url": self.getFullUrl(url), "icon": icon,
                           "desc": "%s: %s" % (_("Rating"), rating) if rating else "", "s_title": title})
            if "/detail/film-" in url:
                # the site is about series - a film (search) plays like on alta-definizione
                params.update({"category": "video", "meta_type": "movie"})
                self.addVideo(params)
            else:
                params.update({"category": "list_seasons", "meta_type": "tv"})
                self.addDir(params)
        addPagingItems(self, cItem, page, hasNext, max(pages + [page]) if hasNext else page, pageUrlTpl)

    def listSeasons(self, cItem):
        printDBG("GuardaSerie.listSeasons |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        _info, plot, year, tmdb = self._siteInfo(data)
        seasons = []
        for season in re.findall(r'href="#season-(\d+)"\s+data-toggle="tab"', data):
            if season not in seasons:
                seasons.append(season)
        sTitle = cItem.get("s_title", "") or cItem["title"]
        fields = {"s_title": sTitle, "s_year": year, "tmdb_id": tmdb, "desc": plot}
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, category="list_episodes", season=seasons[0], url="%s#s%s" % (url, seasons[0]), **fields), data)
            return
        normalize = IsMediaNamingNormalized()
        for season in seasons:
            count = len(re.findall(r'data-season="%s"\s+data-episode="\d+"' % season, data))
            seasonTag = formatSxxExx(season) if normalize else "%s %s" % (_("Season"), season)
            params = dict(cItem)
            params.pop("seasons", None)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (sTitle, seasonTag), "season": season,
                           "url": "%s#s%s" % (url, season)})
            params.update(fields)
            params["desc"] = "%s: %d\n%s" % (_("Episodes"), count, plot)
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("GuardaSerie.listEpisodes |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        season = self._season(cItem)
        if data is None:
            sts, data = self.getPage(url)
            if not sts:
                return
            _info, plot, year, tmdb = self._siteInfo(data)
            # s_title: old favourites ("Show - Season 2") have no show name field - the one of the page
            cItem = dict(cItem, tmdb_id=tmdb or cItem.get("tmdb_id", "") or cItem.get("tmdbID", ""), s_year=year, desc=plot,
                         s_title=cItem.get("s_title", "") or self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<h1[^>]*>(.*?)</h1>")[0]))
        sTitle = cItem.get("s_title", "") or cItem["title"]
        normalize = IsMediaNamingNormalized()
        episodes = []
        for episode in re.findall(r'data-season="%s"\s+data-episode="(\d+)"' % re.escape(season), data):
            if episode not in episodes:
                episodes.append(episode)
        for episode in episodes:
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            else:
                title = "%s - %s %s - %s %s" % (sTitle, _("Season"), season, _("Episode"), episode)
            params = stripPagerKeys(dict(cItem))
            for key in ("seasons", "tmdbID"):
                params.pop(key, None)
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "url": "%s#s%se%s" % (url, season, episode),
                           "season": season, "episode": episode, "meta_type": "tv"})
            self.addVideo(params)

    def listGenres(self, cItem):
        printDBG("GuardaSerie.listGenres")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        seen = set()
        for url, title in re.findall(r'<a href="(/archive\?genre_id=\d+[^"]*)">([^<]+)</a>', data):
            if url in seen:
                continue
            seen.add(url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url.replace("&amp;", "&"))})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("GuardaSerie.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("search?q=%s" % urllib_quote_plus(searchPattern))})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("GuardaSerie.getLinksForVideo [%s]" % cItem)
        tmdb = str(cItem.get("tmdb_id", "") or cItem.get("tmdbID", "") or "")
        if not tmdb:
            sts, data = self.getPage(cItem["url"])
            if sts:
                tmdb = self._siteInfo(data)[3]
        if not tmdb:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        season, episode = self._season(cItem), str(cItem.get("episode", "") or "")
        if season and episode:
            url = "%stv/%s/%s/%s?lang=it" % (PLAYER_URL, tmdb, season, episode)
        else:
            url = "%smovie/%s?lang=it" % (PLAYER_URL, tmdb)
        # parserVIXSRC: token playlist with the audio / video variants
        urltab = [{"name": "VixSrc", "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1}]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

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
        printDBG("GuardaSerie.getArticleContent [%s]" % cItem)
        info, plot, year = {}, "", cItem.get("s_year", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot, year, _tmdb = self._siteInfo(data)
        title = cItem.get("s_title", "") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(cItem.get("meta_type", "") or "tv", title, year)
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        metaPlot = meta.get("plot", "")
        text = plot or cItem.get("desc", "")
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
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
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
