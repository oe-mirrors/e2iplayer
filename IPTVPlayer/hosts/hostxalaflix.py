# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# 19.09.2025 - Mr.X
# 09.10.2026 - host standard (old.xalaflix.cv - xalaflix.cv itself moved to a new site, xalaflix.tax):
#   - links: no KeyError "status_code" when a newPlayer redirect fails (kakaflix.lol is gone - the server is left
#     out, also flixeo.xyz that sends to ad pages), links that are no url (a bare file id) left out
#   - episodes get their own page url (".../ep-<id>") - before every episode had the season url (one downloaded
#     marker / watched key for all of them); a season row keeps the season page url (some list rows link "/ep-"
#     without an id)
#   - watched flag (season -> episode), favourites reopen without state (also the old rows), downloaded marker,
#     "Show - SxxExx" names with the version (VF / VOSTFR), sidecar on the links, INFO via moviemeta merged with the site's
#     fields (type, version, year, status, genres)
#   - First / Jump / Next page with the last page, default user agent, Cloudflare: getPageCFProtection
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://old.xalaflix.cv/"


class XalaFlix(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "XalaFlix", "cookie": "XalaFlix.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.USER_AGENT = self.HEADER.get("User-Agent", "")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("/images/xalaflix-logo.png")
        self.MENU = [
            {"category": "list_items", "title": _("New"), "url": self.getFullUrl("/newest")},
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/movies")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/series")},
            {"category": "list_items", "title": _("Most viewed"), "url": self.getFullUrl("/most-watched")},
            {"category": "list_items", "title": _("Latest added"), "url": self.getFullUrl("/added")},
            {"category": "list_az", "title": _("A-Z")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("xalaflix")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl.split("#", 1)[0], addParams, post_data)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            if cItem.get("type", "") == "video":
                epId = str(cItem.get("id", "") or "")
                if epId and not cItem.get("ep_id") and not url.endswith("/ep-%s" % epId):
                    # episode rows from before 09.10.2026 (the season url + the episode id): the key of the
                    # episode's own url, as the new rows have it
                    url = "%s/ep-%s" % (self._seasonUrl(url), epId)
                return "video:%s" % url if url else ""
            if cItem.get("category", "") == "list_episodes":
                return "season:%s" % self._seasonUrl(url) if url else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _seasonUrl(url):
        # ".../film/<slug>/ep-<id>" (also "/ep-" without an id) -> ".../film/<slug>"
        return re.sub(r"/ep-\d*/?$", "", url.split("#", 1)[0])

    @staticmethod
    def _pageUrlTpl(url):
        url = re.sub(r"[?&]page=\d+", "", url).replace("{", "{{").replace("}", "}}")
        return url + ("&" if "?" in url else "?") + "page={page}"

    @staticmethod
    def _splitSeason(title):
        # "La Guerre des Royaumes - Saison 1" -> ("La Guerre des Royaumes", "1")
        match = re.match(r"^(.*?)\s*[-:]?\s*Saison\s*(\d+)\s*$", title, re.I)
        return (match.group(1).strip(), match.group(2)) if match else (title.strip(), "")

    def _siteInfo(self, data):
        # (info dict, plot, year, movie id, episode id) of a film / season page
        info = {}
        meta = self.cm.ph.getDataBeetwenMarkers(data, 'class="bl-meta"', "</section>", False)[1]
        for key, label in (("type", "Type"), ("language", "Version"), ("year", "Date aired"), ("status", "Status")):
            value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(meta, r"(?s)%s:\s*<span>(.*?)</span>" % label)[0])
            if value:
                info[key] = value
        genres = self.cm.ph.getSearchGroups(meta, r"(?s)Genre:\s*<span>(.*?)</span>")[0]
        genres = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r">([^<]+)</a>", genres))
        if genres:
            info["genres"] = genres
        year = self.cm.ph.getSearchGroups(info.get("year", ""), r"((?:19|20)\d\d)")[0]
        if year:
            info["year"] = year
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="synopsis">\s*<div class="content">(.*?)</div>')[0])
        movieId = self.cm.ph.getSearchGroups(data, r'id="watch-page" data-id="(\d+)"')[0]
        epId = self.cm.ph.getSearchGroups(data, r'data-ep-name="(\d+)"')[0]
        return info, plot, year, movieId, epId

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("XalaFlix.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        pageUrlTpl = self._pageUrlTpl(cItem["url"])
        sts, data = self.getPage(pageUrlTpl.format(page=page) if page > 1 else cItem["url"])
        if not sts:
            return
        hasNext = bool(self.cm.ph.getSearchGroups(data, r'title="Next" href="([^"]+)')[0])
        lastPage = self.cm.ph.getSearchGroups(data, r'title="Last" href="[^"]*[?&]page=(\d+)')[0]
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in data.split('<div class="item">')[1:]:
            # up to the title link (the last block would run into the pager)
            item = item.split('d-title"', 1)[0]
            posterUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'class="ani poster" href="([^"]+)')[0])
            pageUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'href="([^"]+)" class="name')[0]) or self._seasonUrl(posterUrl)
            if not pageUrl or pageUrl in seen:
                continue
            seen.add(pageUrl)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)')[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'data-jp="([^"]+)')[0])
            version = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="version">([^<]+)<')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'src="([^"]+)')[0])
            sTitle, season = self._splitSeason(label)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "icon": icon, "desc": version, "s_title": sTitle, "version": version})
            if season or "saison" in pageUrl.lower():
                title = "%s - %s" % (sTitle, formatSxxExx(season or 1)) if normalize else label
                params.update({"category": "list_episodes", "meta_type": "tv", "title": "%s - %s" % (title, version) if version else title,
                               "url": pageUrl, "season": season or "1"})
                self.addDir(params)
            else:
                epId = self.cm.ph.getSearchGroups(posterUrl, r"/ep-(\d+)")[0]
                params.update({"category": "video", "meta_type": "movie", "title": "%s - %s" % (label, version) if version else label,
                               "url": posterUrl if epId else pageUrl, "ep_id": epId})
                self.addVideo(params)
        addPagingItems(self, cItem, page, hasNext, lastPage, pageUrlTpl)

    def listEpisodes(self, cItem):
        printDBG("XalaFlix.listEpisodes |%s|" % cItem)
        url = self._seasonUrl(cItem["url"])
        sts, data = self.getPage(url)
        if not sts:
            return
        _info, plot, _year, movieId, _epId = self._siteInfo(data)
        sts, data = self.getPage(self.getFullUrl("/ajax/episode/list-episode?movieId=%s" % movieId)) if movieId else (False, "")
        episodes = []
        try:
            html = json_loads(data).get("html", "") if sts else ""
            episodes = re.findall(r'href="([^"]+)"\s+data-num="(\d+)"\s+data-id="(\d+)"', html)
        except Exception:
            printExc()
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", "") or self._splitSeason(cItem["title"])[0]
        season = str(cItem.get("season", "") or self._splitSeason(self.cleanHtmlStr(self.cm.ph.getSearchGroups(cItem["title"], r"(Saison\s*\d+)")[0]))[1] or "1")
        version = cItem.get("version", "")
        normalize = IsMediaNamingNormalized()
        for epUrl, episode, epId in episodes:
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            else:
                title = "%s - %s %s - %s %s" % (sTitle, _("Season"), season, _("Episode"), episode)
            params = stripPagerKeys(dict(cItem))
            params.pop("id", None)
            params.update({"good_for_fav": True, "category": "video", "title": "%s - %s" % (title, version) if version else title, "s_title": sTitle,
                           "url": self.getFullUrl(epUrl), "ep_id": epId, "season": season, "episode": episode, "meta_type": "tv",
                           "desc": plot or cItem.get("desc", "")})
            self.addVideo(params)

    def listAZ(self, cItem):
        printDBG("XalaFlix.listAZ |%s|" % cItem)
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, '<section id="azlist">', "</ul>", False)[1]
        for url, title in re.findall(r'href="([^"]+)"[^>]*>([^<]+)<', data):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("XalaFlix.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("/filter?keyword=%s" % urllib_quote(searchPattern))})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _episodeId(self, cItem):
        # "ep_id" since 09.10.2026, "id" in older favourites, else the url or the page
        epId = str(cItem.get("ep_id", "") or cItem.get("id", "") or "")
        if not epId:
            epId = self.cm.ph.getSearchGroups(cItem.get("url", ""), r"/ep-(\d+)")[0]
        if not epId:
            sts, data = self.getPage(cItem.get("url", ""))
            if sts:
                epId = self._siteInfo(data)[4]
        return epId

    def getLinksForVideo(self, cItem):
        printDBG("XalaFlix.getLinksForVideo [%s]" % cItem)
        epId = self._episodeId(cItem)
        if not epId:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self.MAIN_URL)
        params["header"]["X-Requested-With"] = "XMLHttpRequest"
        sts, data = self.getPage(self.getFullUrl("/ajax/episode/player?episode_id=%s" % epId), params)
        if not sts:
            return []
        servers = []
        try:
            servers = json_loads(data).get("message", [])
        except Exception:
            printExc()
        urlTab = []
        for server in servers if isinstance(servers, list) else []:
            if not isinstance(server, dict):
                continue
            url = str(server.get("server_link", "") or "").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or "multiup" in url:
                continue
            if "newplayer" in url.lower():
                url = self._redirect(url)
                if not url:
                    continue
            # (the player's "version" field says VF for VOSTFR pages too - the row title has the page's version)
            name = "%s - %s" % (self.cleanHtmlStr(server.get("server_name", "")), self.up.getHostName(url).capitalize())
            urlTab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def _redirect(self, url):
        # kakaflix ".../voe3/newPlayer.php?id=..." answers with a 302 to the hoster; "" when it does not answer
        params = dict(self.defaultParams)
        params.update({"no_redirection": True, "header": dict(self.HEADER, Referer=self.MAIN_URL)})
        sts, _data = self.cm.getPage(url, params)
        location = self.cm.meta.get("location", "") if sts else ""
        if not location or self.cm.meta.get("status_code") == 404:
            return ""
        location = self.getFullUrl(location, url)
        if "/voe" in url and self.up.checkHostSupport(location) != 1:
            # a new voe mirror domain every few days - voe.sx serves the same ids
            location = location.replace(self.up.getDomain(location), "voe.sx", 1)
        if self.up.checkHostSupport(location) != 1:
            # flixeo.xyz/tod/newPlayer.php sends to ad pages
            printDBG("XalaFlix._redirect no hoster: %s" % location)
            return ""
        return location

    def getVideoLinks(self, videoUrl):
        printDBG("XalaFlix.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("XalaFlix.getArticleContent [%s]" % cItem)
        info, plot, year = {}, "", ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot, year, _movieId, _epId = self._siteInfo(data)
        mediaType = cItem.get("meta_type", "") or ("tv" if cItem.get("category") == "list_episodes" or cItem.get("episode") else "movie")
        title = cItem.get("s_title", "") or self._splitSeason(cItem.get("title", ""))[0]
        meta = {}
        try:
            meta = getMeta(mediaType, title, year)
        except Exception:
            printExc()
        metaInfo = dict(meta.get("info", {}))
        metaInfo.update(info)
        metaPlot = meta.get("plot", "")
        text = plot or cItem.get("desc", "")
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": metaInfo}]

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
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_az":
            self.listAZ(self.currItem)
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
        CHostBase.__init__(self, XalaFlix(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("xalaflix")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") == "list_episodes"
