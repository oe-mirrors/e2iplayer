# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 09.10.2026 - menu labels in English (translatable), genre lists on the right TMDb ids (Adventure / War / Sci-Fi
#   listed nothing or the wrong genre; series have their own TV genre ids), local pages for long seasons
# 08.10.2026 - replaces the old egy.best host (site dead): MOHAMED_OS's EgyBest app host (eegebest.com,
#   data from the app's EasyPlex API hrrejhp.com/mycimaa), ported to the python3 framework / host standard:
#   - movies / series / dubbed / Ramadan / anime / genres (the app's network ids) and search, with
#     First page / Jump / Next page (n/last from the API)
#   - series and anime -> seasons (only when there are more than one) -> episodes; movies and episodes are
#     VIDEO rows on their key-less API url (stable for the downloaded flag and favourites)
#   - links: the videos of media/detail | series/show | animes/show with the Referer / Origin /
#     User-Agent the app sends, handed to urlparser
#   - watched flag (series -> season -> episode), favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx"), sidecar, INFO via moviemeta + the app's story/genres/cast/rating/poster;
#     no colour codes in titles
import re

from Components.config import ConfigSelection, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, E2ColoR, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.egybest_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.egybest_proxy))
    return optionList
###################################################


def gettytul():
    return "https://eegebest.com/"


EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(\d+)")
NET = "networks/media/show/%s"
# (title, network path) of the app's lists
MOVIES_TAB = ((_("Trending"), "vide-vide-view-vide-movie"), (_("Latest"), "vide-vide-created-vide-movie"),
              (_("Top rated"), "vide-vide-toprated-vide-movie"), (_("Foreign movies"), "7093-vide-created-vide-movie"),
              (_("Arabic Movies"), "7462-vide-created-vide-movie"), (_("Anime Movies"), "7094-vide-created-vide-movie"),
              (_("Asian movies"), "7095-vide-created-vide-movie"), (_("Indian Movies"), "7096-vide-created-vide-movie"),
              (_("Turkish Movies"), "7097-vide-created-vide-movie"), (_("Documentary Movies"), "7098-vide-created-vide-movie"))
SERIES_TAB = ((_("Latest"), "vide-vide-created-vide-serie"), (_("Trending"), "vide-vide-view-vide-serie"),
              (_("Top rated"), "vide-vide-toprated-vide-serie"), (_("Foreign series"), "7865-vide-created-vide-serie"),
              (_("Arabic Series"), "7007-vide-created-vide-serie"), (_("Asian TV series"), "7866-vide-created-vide-serie"),
              (_("Turkish Series"), "7867-vide-created-vide-serie"), (_("Indian TV series"), "7868-vide-created-vide-serie"))
DUBBED_TAB = ((_("Trending"), "vide-vide-view-vide-modablej"), (_("Latest"), "vide-vide-created-vide-modablej"),
              (_("Top rated"), "vide-vide-toprated-vide-modablej"), (_("Turkish series (dubbed)"), "7870-vide-created-vide-modablej"),
              (_("Indian series (dubbed)"), "7875-vide-created-vide-modablej"), (_("Cartoons"), "7884-vide-created-vide-modablej"),
              (_("Dubbed anime"), "7885-vide-created-vide-modablej"))
RAMADAN_TAB = tuple(("%s %d" % (_("Ramadan"), year), "%s-vide-created-vide-serie" % net)
                    for year, net in ((2026, 8618), (2025, 8006), (2024, 7270), (2023, 6394)))
# TMDb genre ids - movies and series have their own (the series lists of a movie genre id are empty)
MOVIE_GENRES = ((_("Action"), 28), (_("Adventure"), 12), (_("Animation"), 16), (_("Comedy"), 35), (_("Crime"), 80),
                (_("Documentary"), 99), (_("Drama"), 18), (_("Family"), 10751), (_("Fantasy"), 14), (_("Sci-Fi"), 878),
                (_("History"), 36), (_("Horror"), 27), (_("Music"), 10402), (_("Mystery"), 9648), (_("Romance"), 10749),
                (_("Thriller"), 53), (_("War"), 10752))
SERIES_GENRES = (("%s & %s" % (_("Action"), _("Adventure")), 10759), (_("Animation"), 16), (_("Comedy"), 35), (_("Crime"), 80),
                 (_("Documentary"), 99), (_("Drama"), 18), (_("Family"), 10751), (_("Fantasy"), 14), (_("Sci-Fi & Fantasy"), 10765),
                 (_("Horror"), 27), (_("Mystery"), 9648), (_("Romance"), 10749), ("%s & %s" % (_("War"), _("Politics")), 10768))
SUB_MENUS = {
    "eb_movies": MOVIES_TAB, "eb_series": SERIES_TAB, "eb_dubbed": DUBBED_TAB, "eb_ramadan": RAMADAN_TAB,
    "eb_genre_movie": tuple((title, "vide-vide-created-%d-movie" % gid) for title, gid in MOVIE_GENRES),
    "eb_genre_serie": tuple((title, "vide-vide-created-%d-serie" % gid) for title, gid in SERIES_GENRES),
}
LOCAL_PAGE_SIZE = 100
# API path of the detail of a list row type
DETAIL_PATH = {"movie": "media/detail/%s", "serie": "series/show/%s", "anime": "animes/show/%s"}
# hosters the app reaches through its own Cloudflare worker - the stream urls it hands out are bound to the worker's IP
SKIP_LINK_RE = re.compile(r"https?://[^/]*developer-pro\.workers\.dev/|https?://(?:www\.)?akwam\.[^/]+/(?:watch|movies?)/")


class EgyBest(GenericFolderWatchedScraperMixin, CBaseHostClass):
    API_KEY = "p2lbgWkFrykA4QyUmpHihzmc5BNzIABq"  # NOSONAR - public client key built into the EasyPlex app (same for every install), not a user secret
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "item_id", "media_type", "s_title", "s_season", "s_episode",
                  "season_id", "episode_id", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "egybest", "cookie": "egybest.cookie"})
        self.MAIN_URL = "https://hrrejhp.com/mycimaa/public/api/"
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/egybest135.png")
        # the app's own client: the API checks the EasyPlex user agent and the package name
        self.HEADER = {"User-Agent": "EasyPlex (Android 11; Mi 5s; Xiaomi capricorn; en)", "Accept": "application/json", "Accept-Encoding": "gzip",
                       "packagename": "com.connectword.flechliv"}
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("egybest")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.egybest_proxy.value) or None

    def getApi(self, url, page=0):
        # url: the key-less API url of a list / detail ("#..." = our own row marker) -> parsed JSON or None
        params = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy:
            params = MergeDicts(params, {"http_proxy": proxy})
        url = "%s/%s" % (self.getFullUrl(url).split("#")[0].rstrip("/"), self.API_KEY)
        if page:
            url += "?page=%d" % page
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        proxy = self.getProxy()
        if url and proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("eb_video", "eb_series", "eb_season"):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    @staticmethod
    def _text(value):
        return ("%s" % value).strip() if value not in (None, "", 0, "0") else ""

    @staticmethod
    def _year(item):
        date = item.get("release_date") or item.get("first_air_date") or item.get("releaseDate") or ""
        m = re.match(r"((?:19|20)\d{2})", "%s" % date)
        return m.group(1) if m else ""

    def _genres(self, item):
        names = item.get("genreslist") or [g.get("name", "") for g in item.get("genres") or [] if isinstance(g, dict)]
        return ", ".join([self.cleanHtmlStr(n) for n in names if n])

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            itemId = cItem.get("item_id", "")
            if not itemId:
                return ""
            mediaType = cItem.get("media_type", "")
            if category == "eb_video":
                if cItem.get("episode_id"):
                    return "episode:%s|%s" % (mediaType, cItem["episode_id"])
                return "video:%s" % itemId
            if category == "eb_series":
                return "series:%s|%s" % (mediaType, itemId)
            if category == "eb_season":
                return "season:%s|%s|%s" % (mediaType, itemId, cItem.get("season_id", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "eb_menu", "title": _("Movies"), "menu": "eb_movies"},
            {"category": "eb_menu", "title": _("Series"), "menu": "eb_series"},
            {"category": "eb_menu", "title": _("Dubbed"), "menu": "eb_dubbed"},
            {"category": "eb_menu", "title": _("Ramadan"), "menu": "eb_ramadan"},
            {"category": "list_items", "title": _("Anime"), "url": self.getFullUrl(NET % "7869-vide-created-vide-serie"), "good_for_fav": True},
            {"category": "eb_menu", "title": "%s - %s" % (_("Movies"), _("Genres")), "menu": "eb_genre_movie"},
            {"category": "eb_menu", "title": "%s - %s" % (_("Series"), _("Genres")), "menu": "eb_genre_serie"},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listSubMenu(self, cItem):
        for title, path in SUB_MENUS.get(cItem.get("menu", ""), ()):
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": self.getFullUrl(NET % path)})

    def _addRow(self, item, normalize):
        mediaType = ("%s" % item.get("type", "")).lower()
        itemId = item.get("id")
        title = self.cleanHtmlStr(item.get("title") or item.get("name") or "")
        if not itemId or not title or mediaType not in DETAIL_PATH:
            return
        year = self._year(item)
        rating = self._text(item.get("vote_average"))
        genre = self._genres(item)
        label = self.cleanHtmlStr(item.get("subtitle") or "")
        plot = self.cleanHtmlStr(item.get("overview") or "")
        fields = ((_("Year"), year, "cyan"), (_("Rating"), rating, "yellow"), (_("Genre"), genre, "orange"))
        desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), name, E2ColoR("white"), value) for name, value, color in fields if value])
        if label:
            desc = "%s | %s" % (desc, label) if desc else label
        if plot:
            desc = "%s[/br]%s" % (desc, plot) if desc else plot
        params = {"name": "category", "good_for_fav": True, "icon": self.getFullIconUrl(item.get("poster_path") or ""), "desc": desc,
                  "item_id": "%s" % itemId, "media_type": mediaType, "url": self.getFullUrl(DETAIL_PATH[mediaType] % itemId),
                  "meta_title": title, "meta_year": year}
        if mediaType == "movie":
            params.update({"category": "eb_video", "title": ("%s (%s)" % (title, year)) if normalize and year else title, "meta_type": "movie"})
            self.addVideo(params)
        else:
            params.update({"category": "eb_series", "title": title, "s_title": title, "meta_type": "tv"})
            self.addDir(params)

    def listItems(self, cItem):
        # cItem["url"]: the key-less network url; the API pages it with ?page=N (1-based) and tells the last page.
        # The url itself is the pager template (no "{page}"), the page comes from cItem["page"].
        page = int(cItem.get("page", 1) or 1)
        printDBG("EgyBest.listItems [%s] page %d" % (cItem["url"], page))
        data = self.getApi(cItem["url"], page)
        if not isinstance(data, dict):
            return
        normalize = IsMediaNamingNormalized()
        for item in data.get("data") or []:
            if isinstance(item, dict):
                self._addRow(item, normalize)
        lastPage = int(data.get("last_page") or 0)
        listItem = dict(cItem)
        listItem["category"] = "list_items"
        addPagingItems(self, listItem, page, bool(data.get("next_page_url")) and page < lastPage, lastPage, cItem["url"])

    def _seasons(self, cItem):
        data = self.getApi(cItem.get("url", ""))
        if not isinstance(data, dict):
            return []
        return [s for s in data.get("seasons") or [] if isinstance(s, dict)]

    def listSeries(self, cItem):
        printDBG("EgyBest.listSeries [%s]" % cItem.get("url", ""))
        seasons = self._seasons(cItem)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No episodes found."))
            return
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, season_id="%s" % seasons[0].get("id", ""), s_season=seasons[0].get("season_number") or 1), seasons)
            return
        normalize = IsMediaNamingNormalized()
        for season in sorted(seasons, key=lambda s: s.get("season_number") or 0):
            num = season.get("season_number") or 0
            label = self.cleanHtmlStr(season.get("name", "")) or "%s %s" % (_("Season"), num)
            title = ("%s - %s" % (cItem.get("s_title", ""), formatSxxExx(num))) if normalize and num else label
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "eb_season", "title": title, "season_id": "%s" % season.get("id", ""), "s_season": num})
            self.addDir(params)

    def listEpisodes(self, cItem, seasons=None):
        printDBG("EgyBest.listEpisodes [%s|%s]" % (cItem.get("url", ""), cItem.get("season_id", "")))
        if seasons is None:
            seasons = self._seasons(cItem)
        show = cItem.get("s_title", "") or cItem.get("title", "")
        seasonNum = cItem.get("s_season", 0) or 1
        normalize = IsMediaNamingNormalized()
        baseUrl = cItem.get("url", "").split("#")[0]
        episodes = []
        for season in seasons:
            if "%s" % season.get("id", "") != cItem.get("season_id", ""):
                continue
            for episode in season.get("episodes") or []:
                epId = episode.get("id")
                if not epId or not episode.get("videos"):
                    continue
                label = self.cleanHtmlStr(episode.get("name", ""))
                num = episode.get("episode_number") or self.cm.ph.getSearchGroups(label, EPISODE_RE.pattern)[0]
                if normalize and num:
                    title = "%s - %s" % (show, formatSxxExx(seasonNum, num))
                else:
                    title = "%s - %s" % (show, label) if label else show
                params = stripPagerKeys(dict(cItem))
                params.update({"category": "eb_video", "good_for_fav": True, "title": title, "url": "%s#episode=%s" % (baseUrl, epId),
                               "episode_id": "%s" % epId, "s_season": seasonNum, "s_episode": num,
                               "icon": self.getFullIconUrl(episode.get("still_path") or "") or cItem.get("icon", "")})
                episodes.append(params)
        # long anime seasons: local pages
        page = int(cItem.get("page", 1) or 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem, category="eb_season"), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("EgyBest.listSearchResult [%s]" % searchPattern)
        # one answer with all hits, no pages
        data = self.getApi(self.getFullUrl("search/%s" % urllib_quote(searchPattern.strip(), safe="")))
        if not isinstance(data, dict):
            return
        normalize = IsMediaNamingNormalized()
        for item in data.get("search") or []:
            if isinstance(item, dict):
                self._addRow(item, normalize)

    ###################################################
    # links
    ###################################################
    def _videos(self, cItem):
        data = self.getApi(cItem.get("url", ""))
        if not isinstance(data, dict):
            return []
        if not cItem.get("episode_id"):
            return data.get("videos") or []
        for season in data.get("seasons") or []:
            for episode in season.get("episodes") or []:
                if "%s" % episode.get("id", "") == cItem["episode_id"]:
                    return episode.get("videos") or []
        return []

    @staticmethod
    def _linkMeta(video):
        # "header": "" | "https://referer/" | "origin:https://x|referer:https://x/|Accept:..."
        meta = {}
        header = ("%s" % (video.get("header") or "")).strip()
        if header.startswith("http"):
            meta["Referer"] = header
        else:
            for part in header.split("|"):
                key, sep, value = part.partition(":")
                key = key.strip().lower()
                if sep and key in ("referer", "origin"):
                    meta[key.capitalize()] = value.strip()
        userAgent = ("%s" % (video.get("useragent") or "")).strip()
        if userAgent:
            meta["User-Agent"] = userAgent
        return meta

    def getLinksForVideo(self, cItem):
        printDBG("EgyBest.getLinksForVideo [%s]" % cItem.get("url", ""))
        urltab = []
        seen = set()
        names = []
        for video in self._videos(cItem):
            if not isinstance(video, dict) or video.get("status") == 0 or video.get("drm"):
                continue
            url = ("%s" % (video.get("link") or "")).strip()
            if not self.cm.isValidUrl(url) or url in seen or SKIP_LINK_RE.search(url):
                continue
            seen.add(url)
            domain = self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/:]+)")[0]
            server = self.cleanHtmlStr(video.get("server") or "")
            name = "%s (%s)" % (server, domain) if server else domain
            names.append(name)
            if names.count(name) > 1:
                name = "%s %d" % (name, names.count(name))
            urltab.append({"name": name, "url": strwithmeta(url, self._linkMeta(video)), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled()))

    def _directMp4(self, videoUrl):
        # the app's own CDN (newcdn.seriesmp4.com): the ".mp4" url answers a small HTML page whose iframe
        # is the real file (a Yandex Disk download url); a plain file is used as it is
        userAgent = videoUrl.meta.get("User-Agent", "") if isinstance(videoUrl, strwithmeta) else ""
        header = {"User-Agent": userAgent or self.cm.getDefaultUserAgent(), "Accept-Encoding": "identity"}
        url = "%s" % videoUrl
        sts, data = self.cm.getPage(url, {"header": header, "max_data_size": 8192})
        if sts and "<iframe" in (data or ""):
            url = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"')[0].replace("&amp;", "&")
        if not self.cm.isValidUrl(url):
            return []
        return [{"name": "mp4", "url": strwithmeta(url, {"User-Agent": header["User-Agent"]}), "need_resolve": 0}]

    def getVideoLinks(self, videoUrl):
        printDBG("EgyBest.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if self.up.checkHostSupport(videoUrl) != 1 and re.search(r"\.mp4(?:$|\?)", "%s" % videoUrl):
            return decorateResolvedLinkItems(self._directMp4(videoUrl), sidecar)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("EgyBest.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        data = self.getApi(cItem.get("url", "")) or {}
        if not isinstance(data, dict):
            data = {}
        info = {}
        site = (("year", self._year(data) or cItem.get("meta_year", "")), ("genres", self._genres(data)),
                ("rating", self._text(data.get("vote_average"))), ("age_limit", self._text(data.get("Age_Rating"))),
                ("duration", ("%s min" % data["runtime"]) if self._text(data.get("runtime")) else ""),
                ("actors", ", ".join([c.get("name", "") for c in data.get("casterslist") or [] if isinstance(c, dict) and c.get("name")][:6])))
        for key, value in site:
            if value:
                info[key] = value
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        story = self.cleanHtmlStr(data.get("overview") or "")
        text = plot or story or StripColorCodes(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or self.getFullIconUrl(data.get("poster_path") or "") or cItem.get("icon", "")
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
        printDBG("EgyBest.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "eb_menu":
            self.listSubMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "eb_series":
            self.listSeries(self.currItem)
        elif category == "eb_season":
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
        CHostBase.__init__(self, EgyBest(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("egybest")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("eb_video", "eb_series", "eb_season")
