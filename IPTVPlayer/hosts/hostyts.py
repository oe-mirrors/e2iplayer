# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - YTS (YIFY movies) through the official JSON API (was hostytxmx)
#   - list_movies.json / movie_details.json of the API; the API moves its base url
#     (movies-api.accel.li, yts.gg) - the first one that answers is kept, an alternative domain
#     from the settings is tried first
#   - Latest / Popular / Top rated, genres, qualities, search (title, IMDb code, actor, director),
#     First page / Jump / Next page (50 movies per page)
#   - links: one magnet per torrent (quality, release type, codec, size, seeders / peers), best
#     quality first, played through TorrServer (urlparser parserTORRSERVER); the YouTube trailer
#   - watched flag, downloaded flag, favourites, name normalisation, sidecar, INFO via moviemeta
#     (IMDb code of the movie) + the site's fields
###################################################
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.yts_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.yts_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.yts_proxy))
    if config.plugins.iptvplayer.yts_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.yts_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://yts.gg/"


# the API announces its moves in "status_message" ("Base URL moving to ...")
API_DOMAINS = ("https://movies-api.accel.li/", "https://yts.gg/")
PER_PAGE = 50
TRACKERS = (
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.dler.org:6969/announce",
)
GENRES = ("Action", "Adventure", "Animation", "Biography", "Comedy", "Crime", "Documentary", "Drama", "Family",
          "Fantasy", "Film-Noir", "History", "Horror", "Music", "Musical", "Mystery", "Romance", "Sci-Fi", "Sport",
          "Thriller", "War", "Western")
QUALITIES = ("2160p", "1080p", "1080p.x265", "720p", "3D")
QUALITY_RANK = {"2160p": 5, "1080p": 4, "720p": 3, "480p": 2}
RELEASE_TYPES = {"web": "WEB", "bluray": "BluRay"}
MOVIE_PATH_RE = re.compile(r"(/movies?/[^/?#]+)")
HASH_RE = re.compile(r"^[0-9A-Fa-f]{40}$")


def _formatTorrentName(torrent):
    # "1080p BluRay x265 10bit 5.1 - 1.6 GB - S:120 P:15"
    parts = [torrent.get("quality", ""), RELEASE_TYPES.get(torrent.get("type", ""), torrent.get("type", "")), torrent.get("video_codec", "")]
    if str(torrent.get("bit_depth", "")) not in ("", "8"):
        parts.append("%sbit" % torrent["bit_depth"])
    if torrent.get("audio_channels") and torrent["audio_channels"] != "2.0":
        parts.append(torrent["audio_channels"])
    if str(torrent.get("is_repack", "0")) == "1":
        parts.append("REPACK")
    label = " ".join(p for p in parts if p)
    return "%s - %s - S:%s P:%s" % (label, torrent.get("size", ""), torrent.get("seeds", 0), torrent.get("peers", 0))


class YTS(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "movie_id", "imdb_code",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "yts", "cookie": "yts.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/yts135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER["Accept"] = "application/json, text/plain, */*"
        self.apiBase = None
        self.movieCache = {}
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper("yts")
        self.wfInitFolderCache()

    ###################################################
    # API
    ###################################################
    def _apiBases(self):
        bases = list(API_DOMAINS)
        alt = config.plugins.iptvplayer.yts_alt_domain.value.strip()
        if self.cm.isValidUrl(alt):
            bases.insert(0, alt.rstrip("/") + "/")
        if self.apiBase in bases:
            bases.remove(self.apiBase)
            bases.insert(0, self.apiBase)
        return bases

    def _getJson(self, method, query):
        # the "data" dict of api/v2/<method>?<query> from the first base url that answers
        params = {"header": self.HEADER}
        proxy = GetAlternativeProxyUrl(config.plugins.iptvplayer.yts_proxy.value)
        if proxy:
            params["http_proxy"] = proxy
        for base in self._apiBases():
            url = "%sapi/v2/%s?%s" % (base, method, query)
            sts, data = self.cm.getPage(url, dict(params))
            if not sts:
                continue
            try:
                data = json_loads(data)
            except Exception:
                printDBG("YTS._getJson no JSON from [%s]" % url)
                continue
            if isinstance(data, dict) and data.get("status") == "ok" and isinstance(data.get("data"), dict):
                self.apiBase = base
                return data["data"]
            printDBG("YTS._getJson [%s] status[%s]" % (url, data.get("status_message", "") if isinstance(data, dict) else ""))
        return None

    def _listUrl(self, query, page):
        return "%sapi/v2/list_movies.json?%s&limit=%d&page=%s" % (self.apiBase or API_DOMAINS[0], query, PER_PAGE, page)

    def _movieDetails(self, cItem):
        movieId = str(cItem.get("movie_id", ""))
        if movieId and movieId in self.movieCache and "cast" in self.movieCache[movieId]:
            return self.movieCache[movieId]
        if movieId:
            query = "movie_id=%s&with_cast=true" % movieId
        elif cItem.get("imdb_code"):
            query = "imdb_id=%s&with_cast=true" % cItem["imdb_code"]
        else:
            return {}
        data = self._getJson("movie_details.json", query)
        movie = (data or {}).get("movie") or {}
        if movie.get("id"):
            movie.setdefault("cast", [])
            self.movieCache[str(movie["id"])] = movie
        return movie

    ###################################################
    # helpers
    ###################################################
    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") == "yts_movie":
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("type") == "video":
                path = MOVIE_PATH_RE.search(cItem.get("url", ""))
                if path:
                    return "video:%s" % path.group(1).lower()
        except Exception:
            printExc()
        return ""

    def _title(self, movie):
        title = self.cleanHtmlStr(movie.get("title_english") or movie.get("title") or "")
        year = movie.get("year") or ""
        if IsMediaNamingNormalized():
            return "%s (%s)" % (title, year) if year else title
        return self.cleanHtmlStr(movie.get("title_long", "")) or title

    def _qualities(self, movie):
        # "720p WEB, 1080p WEB, 1080p BluRay"
        qualities = []
        for torrent in movie.get("torrents") or []:
            label = ("%s %s" % (torrent.get("quality", ""), RELEASE_TYPES.get(torrent.get("type", ""), ""))).strip()
            if label not in qualities:
                qualities.append(label)
        return ", ".join(qualities)

    def _desc(self, movie):
        fields = ((_("Year"), movie.get("year")),
                  (_("Rating"), "%s/10" % movie["rating"] if movie.get("rating") else ""),
                  (_("Runtime"), "%s min" % movie["runtime"] if movie.get("runtime") else ""),
                  (_("Genres"), ", ".join(movie.get("genres") or [])))
        lines = [" | ".join("%s: %s" % (label, value) for label, value in fields if value)]
        qualities = self._qualities(movie)
        if qualities:
            lines.append("%s: %s" % (_("Quality"), qualities))
        summary = self.cleanHtmlStr(movie.get("summary") or movie.get("description_full") or "")
        if summary:
            lines.append(summary)
        return "[/br]".join(line for line in lines if line)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "yts_list", "title": _("Latest"), "query": "sort_by=date_added"},
            {"category": "yts_list", "title": _("Popular"), "query": "sort_by=download_count"},
            {"category": "yts_list", "title": _("Top rated"), "query": "sort_by=rating"},
            {"category": "yts_filter", "title": _("Genres"), "filter": "genre"},
            {"category": "yts_filter", "title": _("Quality"), "filter": "quality"},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listFilter(self, cItem):
        if cItem.get("filter") == "genre":
            values = [(genre, "genre=%s" % genre.lower()) for genre in GENRES]
        else:
            values = [(quality.replace(".x265", " x265"), "quality=%s" % quality) for quality in QUALITIES]
        for title, query in values:
            query += "&sort_by=date_added"
            self.addDir({"name": "category", "category": "yts_list", "title": title, "query": query,
                         "url": self._listUrl(query, 1), "good_for_fav": True})

    def listItems(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        query = cItem.get("query", "")
        printDBG("YTS.listItems query[%s] page[%d]" % (query, page))
        data = self._getJson("list_movies.json", "%s&limit=%d&page=%d" % (query, PER_PAGE, page))
        if data is None:
            SetIPTVPlayerLastHostError(_("Failed to connect to host."))
            return
        for movie in data.get("movies") or []:
            url = movie.get("url", "")
            if not url or not movie.get("id"):
                continue
            self.movieCache[str(movie["id"])] = movie
            title = self.cleanHtmlStr(movie.get("title_english") or movie.get("title") or "")
            self.addVideo({"name": "category", "category": "yts_movie", "good_for_fav": True, "title": self._title(movie),
                           "url": url, "icon": movie.get("medium_cover_image") or movie.get("large_cover_image", ""),
                           "desc": self._desc(movie), "movie_id": movie["id"], "imdb_code": movie.get("imdb_code", ""),
                           "meta_type": "movie", "meta_title": title, "meta_year": str(movie.get("year") or "")})
        try:
            lastPage = (int(data.get("movie_count", 0)) + PER_PAGE - 1) // PER_PAGE
        except (TypeError, ValueError):
            lastPage = 0
        listItem = stripPagerKeys(dict(cItem))
        listItem["url"] = self._listUrl(query, 1)
        addPagingItems(self, listItem, page, page < lastPage, lastPage, self._listUrl(query, "{page}"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("YTS.listSearchResult [%s]" % searchPattern)
        query = "query_term=%s&sort_by=download_count" % urllib_quote_plus(searchPattern.strip())
        self.listItems(dict(cItem, category="yts_list", query=query, page=1))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("YTS.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        movie = self.movieCache.get(str(cItem.get("movie_id", ""))) or self._movieDetails(cItem)
        torrents = sorted(movie.get("torrents") or [], key=lambda t: (QUALITY_RANK.get(t.get("quality", ""), 0), int(t.get("seeds") or 0)), reverse=True)
        titleLong = self.cleanHtmlStr(movie.get("title_long", "")) or cItem.get("title", "")
        icon = movie.get("large_cover_image") or cItem.get("icon", "")
        urltab = []
        for torrent in torrents:
            infoHash = torrent.get("hash", "")
            if not HASH_RE.match(infoHash):
                continue
            dn = "%s [%s] [YTS]" % (titleLong, torrent.get("quality", ""))
            magnet = "magnet:?xt=urn:btih:%s&dn=%s&tr=%s" % (infoHash, urllib_quote_plus(dn), "&tr=".join(urllib_quote_plus(t) for t in TRACKERS))
            urltab.append({"name": _formatTorrentName(torrent), "url": strwithmeta(magnet, {"title": titleLong, "icon": icon}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        if movie.get("yt_trailer_code"):
            urltab.append({"name": "%s (YouTube)" % _("Trailer"), "url": "https://www.youtube.com/watch?v=%s" % movie["yt_trailer_code"], "need_resolve": 1})
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("YTS.getVideoLinks [%s]" % videoUrl)
        if videoUrl.startswith("magnet:?") or self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("YTS.getArticleContent [%s]" % cItem.get("url", ""))
        movie = self._movieDetails(cItem) or self.movieCache.get(str(cItem.get("movie_id", ""))) or {}
        info = {}
        if movie.get("year"):
            info["year"] = str(movie["year"])
        if movie.get("rating"):
            info["imdb_rating"] = "%s/10" % movie["rating"]
        if movie.get("runtime"):
            info["duration"] = "%s min" % movie["runtime"]
        if movie.get("genres"):
            info["genres"] = ", ".join(movie["genres"])
        if movie.get("mpa_rating"):
            info["rated"] = movie["mpa_rating"]
        if movie.get("language"):
            info["language"] = movie["language"]
        if movie.get("cast"):
            info["cast"] = ", ".join(c.get("name", "") for c in movie["cast"] if c.get("name"))
        qualities = self._qualities(movie)
        if qualities:
            info["quality"] = qualities
        meta = {}
        try:
            meta = getMetaByImdbId("movie", cItem.get("imdb_code") or movie.get("imdb_code", ""))
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        story = self.cleanHtmlStr(movie.get("description_full") or movie.get("description_intro") or movie.get("summary") or "")
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or movie.get("large_cover_image") or cItem.get("icon", "")
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
        printDBG("YTS.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "yts_filter":
            self.listFilter(self.currItem)
        elif category == "yts_list":
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, YTS(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("yts")

    def withArticleContent(self, cItem):
        return cItem.get("category") == "yts_movie"
