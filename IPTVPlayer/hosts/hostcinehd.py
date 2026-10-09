# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# CineHD (cinehd.vc / cinehd.cc) - English TMDb-indexed movie / series guide
#   - the catalogue comes from the site's own JSON API (api/search/discover: trending, popular, now playing,
#     latest, top rated, most voted, genres, years, search) with First page / Jump / Next page (n/last)
#   - a series page carries the TMDb seasons in its React payload; episode titles / air dates come from TMDb only
#     with the user's own TMDb key (metadata settings), numbered episodes from the site's episode count without it
#   - the site's player only iframes TMDb-keyed embed providers: the ones urlparser resolves are offered
#     (vixsrc incl. the Italian audio, vidrock, vidnest, videasy, peachify; vidfast / vidcore only
#     when the external link decryption is switched on in the settings); vidlink.pro is not offered: its
#     MovieBox CDN mp4s (bcdn.hakunaymatata.com) answer 429 to every request (box + PC, 09.10.2026)
#   - watched flag (series -> season -> episode), downloaded flag on stable page urls, favourites (rows
#     re-open from their TMDb id), name normalisation, sidecar, INFO via moviemeta (by IMDb id when the user's
#     TMDb key gives it, else by title + year)
import json
import re
import time

from Components.config import config
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsExternalResolveAllowed, IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://cinehd.vc/"


TMDB_API = "https://api.themoviedb.org/3/"
POSTER_URL = "https://image.tmdb.org/t/p/w342"
BACKDROP_URL = "https://image.tmdb.org/t/p/w780"
STILL_URL = "https://image.tmdb.org/t/p/w300"
EPISODES_PER_PAGE = 100
FIRST_YEAR = 1950

# (label, url template, needs the external link decryption) - %(kind)s movie|tv, %(id)s TMDb id,
# %(se)s "/<season>/<episode>" for an episode; the url shapes urlparser expects for these providers
EMBEDS = (
    ("Vidpro (vixsrc.to)", "https://vixsrc.to/%(kind)s/%(id)s%(se)s", False),
    ("Vidpro Italian (vixsrc.to)", "https://vixsrc.to/%(kind)s/%(id)s%(se)s?lang=it", False),
    ("Rock (vidrock.net)", "https://vidrock.net/%(kind)s/%(id)s%(se)s", False),
    ("Vidnest (vidnest.fun)", "https://vidnest.fun/%(kind)s/%(id)s%(se)s", False),
    ("4K (videasy.to)", "https://player.videasy.to/%(kind)s/%(id)s%(se)s?title=%(title)s&year=%(year)s", False),
    ("Vidfast (vidfast.vc)", "https://vidfast.vc/%(kind)s/%(id)s%(se)s", True),
    ("Vidcore (vidcore.net)", "https://vidcore.net/%(kind)s/%(id)s%(se)s", True),
    ("Peachify (peachify.top)", "https://peachify.top/embed/%(kind)s/%(id)s%(se)s", False),
)

RSC_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')


class CineHD(GenericFolderWatchedScraperMixin, CBaseHostClass):
    GENRES = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "tmdb_id", "media_type", "s_title", "s_year",
                  "s_season", "s_episode", "ep_count", "ep_name", "ep_overview", "ep_air", "rating", "genres", "overview", "backdrop")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cinehd", "cookie": "cinehd.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/cinehd135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("cinehd")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _getJson(self, url, params=None):
        sts, data = self.getPage(url, params)
        if not sts:
            return {}
        try:
            data = json.loads(data)
        except Exception:
            printExc()
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _tmdbKey():
        # the user's own TMDb key of the metadata settings (as libs/moviemeta reads it), "" when none is set
        cp = config.plugins.iptvplayer
        try:
            if cp.meta_tmdb.value:
                return cp.meta_tmdb_apikey.value.strip()
        except Exception:
            printExc()
        return ""

    def _tmdb(self, path):
        # TMDb answer with the user's key, {} without one (callers fall back to the site data / moviemeta)
        key = self._tmdbKey()
        if not key:
            return {}
        params = {"header": {"User-Agent": self.HEADER["User-Agent"], "Accept": "application/json"}}
        return self._getJson("%s%s?%s" % (TMDB_API, path, urllib_urlencode({"language": "en-US", "api_key": key})), params)

    def _genres(self):
        if CineHD.GENRES is None:
            data = self._getJson(self.getFullUrl("/api/search/meta?country=all"))
            genres = {}
            for kind, key in (("movie", "movieGenres"), ("tv", "tvGenres")):
                genres[kind] = [(g["id"], self.cleanHtmlStr(g.get("name", ""))) for g in (data.get(key) or []) if g.get("id")]
            if genres["movie"] or genres["tv"]:
                CineHD.GENRES = genres
            return genres
        return CineHD.GENRES

    def _genreNames(self, ids):
        names = {}
        for items in (self._genres() or {}).values():
            names.update(dict(items))
        return ", ".join(names[g] for g in (ids or []) if g in names)

    def _discoverUrl(self, kind, **filters):
        params = [("type", kind), ("sort", filters.pop("sort", "popularity"))]
        params += sorted(filters.items())
        return self.MAIN_URL + "api/search/discover?" + urllib_urlencode(params)

    def _videoUrl(self, kind, tmdbId, season=0, episode=0):
        if kind == "tv":
            return self.getFullUrl("/tv/%s?season=%s&episode=%s" % (tmdbId, season, episode))
        return self.getFullUrl("/movie/%s" % tmdbId)

    def _desc(self, year, rating, genres, overview):
        head = " | ".join(x for x in (year, ("TMDb %s" % rating) if rating else "", genres) if x)
        return "\n".join(x for x in (head, overview) if x)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("ch_video", "ch_series", "ch_season"):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or not cItem.get("tmdb_id"):
                return ""
            category = cItem.get("category", "")
            tmdbId = cItem["tmdb_id"]
            if category == "ch_video":
                if cItem.get("media_type") == "tv":
                    return "video:tv:%s:%s:%s" % (tmdbId, cItem.get("s_season", 0), cItem.get("s_episode", 0))
                return "video:movie:%s" % tmdbId
            if category == "ch_series":
                return "series:%s" % tmdbId
            if category == "ch_season":
                return "season:%s:%s" % (tmdbId, cItem.get("s_season", 0))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "ch_list", "title": _("Trending"), "url": self._discoverUrl("all", trending="true"), "good_for_fav": True},
            {"category": "ch_menu", "title": _("Movies"), "media_type": "movie"},
            {"category": "ch_menu", "title": _("Series"), "media_type": "tv"},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listTypeMenu(self, cItem):
        kind = cItem.get("media_type", "movie")
        tab = [(_("Trending"), {"trending": "true"}), (_("Popular"), {})]
        if kind == "movie":
            tab += [(_("Now playing"), {"now_playing": "true"}), (_("Latest"), {"sort": "latest"})]
        tab += [(_("Top rated"), {"sort": "rating"}), (_("Most voted"), {"sort": "vote_count"})]
        for title, filters in tab:
            self.addDir({"name": "category", "category": "ch_list", "good_for_fav": True, "title": title, "media_type": kind,
                         "url": self._discoverUrl(kind, **filters)})
        self.addDir({"name": "category", "category": "ch_genres", "title": _("Genres"), "media_type": kind})
        self.addDir({"name": "category", "category": "ch_years", "title": _("Year"), "media_type": kind})

    def listGenres(self, cItem):
        kind = cItem.get("media_type", "movie")
        for genreId, name in (self._genres() or {}).get(kind, []):
            self.addDir({"name": "category", "category": "ch_list", "good_for_fav": True, "title": name, "media_type": kind,
                         "url": self._discoverUrl(kind, genre=str(genreId))})

    def listYears(self, cItem):
        kind = cItem.get("media_type", "movie")
        for year in range(time.localtime().tm_year, FIRST_YEAR - 1, -1):
            self.addDir({"name": "category", "category": "ch_list", "good_for_fav": True, "title": str(year), "media_type": kind,
                         "url": self._discoverUrl(kind, year=str(year))})

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = re.sub(r"&page=\d+", "", cItem["url"])
        printDBG("CineHD.listItems [%s] page[%s]" % (baseUrl, page))
        data = self._getJson("%s&page=%d" % (baseUrl, page))
        defKind = self.cm.ph.getSearchGroups(baseUrl, r"[?&]type=(movie|tv)")[0] or "movie"
        normalize = IsMediaNamingNormalized()
        count = 0
        for item in data.get("results") or []:
            tmdbId = item.get("id")
            title = self.cleanHtmlStr(item.get("title") or item.get("name") or "")
            if not tmdbId or not title or item.get("adult") or item.get("softcore"):
                continue
            kind = item.get("media_type") or defKind
            if kind not in ("movie", "tv"):
                continue
            count += 1
            year = (item.get("release_date") or item.get("first_air_date") or "")[:4]
            vote = item.get("vote_average") or 0
            rating = ("%.1f" % vote) if vote else ""
            genres = self._genreNames(item.get("genre_ids"))
            overview = self.cleanHtmlStr(item.get("overview") or "")
            poster = item.get("poster_path") or ""
            backdrop = item.get("backdrop_path") or ""
            params = {"name": "category", "good_for_fav": True, "tmdb_id": str(tmdbId), "media_type": kind, "s_title": title,
                      "s_year": year, "rating": rating, "genres": genres, "overview": overview,
                      "icon": (POSTER_URL + poster) if poster else "", "backdrop": (BACKDROP_URL + backdrop) if backdrop else "",
                      "desc": self._desc(year, rating, genres, overview)}
            if kind == "tv":
                params.update({"category": "ch_series", "title": title, "url": self.getFullUrl("/tv/%s" % tmdbId)})
                self.addDir(params)
            else:
                params.update({"category": "ch_video", "title": ("%s (%s)" % (title, year)) if (normalize and year) else title,
                               "url": self._videoUrl("movie", tmdbId)})
                self.addVideo(params)

        lastPage = data.get("total_pages") or 0
        try:
            lastPage = int(lastPage)
        except (TypeError, ValueError):
            lastPage = 0
        listItem = dict(cItem)
        listItem.update({"category": "ch_list", "url": baseUrl})
        addPagingItems(self, listItem, page, count > 0 and page < lastPage, lastPage, baseUrl + "&page={page}")

    def _seasonsFromPage(self, tmdbId):
        # the series page sends the TMDb tv object in its React payload: decode the pushed strings, then the seasons array
        sts, data = self.getPage(self.getFullUrl("/tv/%s" % tmdbId))
        if not sts:
            return []
        try:
            text = "".join(json.loads(m.group(1)) for m in RSC_PUSH_RE.finditer(data))
            pos = text.find('"seasons":[')
            if pos >= 0:
                seasons = json.JSONDecoder().raw_decode(text, pos + len('"seasons":'))[0]
                return [s for s in seasons if isinstance(s, dict)]
        except Exception:
            printExc()
        return []

    def listSeasons(self, cItem):
        tmdbId = cItem.get("tmdb_id", "")
        printDBG("CineHD.listSeasons [%s]" % tmdbId)
        seasons = self._seasonsFromPage(tmdbId)
        if not seasons:
            seasons = self._tmdb("tv/%s" % tmdbId).get("seasons") or []
        show = cItem.get("s_title", "") or cItem.get("title", "")
        normalize = IsMediaNamingNormalized()
        # the specials (season 0) last
        for season in sorted(seasons, key=lambda s: (s.get("season_number") or 0) == 0):
            num = season.get("season_number")
            count = season.get("episode_count") or 0
            if num is None or not count:
                continue
            label = self.cleanHtmlStr(season.get("name") or "") or "%s %d" % (_("Season"), num)
            title = ("%s - %s" % (show, formatSxxExx(num))) if (normalize and num) else label
            poster = season.get("poster_path") or ""
            year = (season.get("air_date") or "")[:4]
            head = " | ".join(x for x in (label if title != label else "", year, _("Episodes: %s") % count) if x)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "ch_season", "title": title, "s_season": num, "ep_count": count,
                           "icon": (POSTER_URL + poster) if poster else cItem.get("icon", ""),
                           "desc": "\n".join(x for x in (head, self.cleanHtmlStr(season.get("overview") or "")) if x)})
            self.addDir(params)
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No episodes found."))

    def listEpisodes(self, cItem):
        tmdbId = cItem.get("tmdb_id", "")
        season = cItem.get("s_season", 0)
        page = cItem.get("page", 1)
        printDBG("CineHD.listEpisodes [%s] season[%s] page[%s]" % (tmdbId, season, page))
        episodes = [e for e in (self._tmdb("tv/%s/season/%s" % (tmdbId, season)).get("episodes") or []) if e.get("episode_number")]
        if not episodes:
            # no TMDb answer: numbered episodes from the site's episode count
            episodes = [{"episode_number": n} for n in range(1, (cItem.get("ep_count") or 0) + 1)]
        show = cItem.get("s_title", "")
        normalize = IsMediaNamingNormalized()
        start = (page - 1) * EPISODES_PER_PAGE
        for ep in episodes[start:start + EPISODES_PER_PAGE]:
            num = ep["episode_number"]
            name = self.cleanHtmlStr(ep.get("name") or "")
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, num))
            else:
                title = "%s %d" % (_("Episode"), num) + (": %s" % name if name else "")
            still = ep.get("still_path") or ""
            airDate = ep.get("air_date") or ""
            runtime = ep.get("runtime") or 0
            head = " | ".join(x for x in (name if normalize else "", airDate, ("%d min" % runtime) if runtime else "") if x)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "ch_video", "title": title, "s_episode": num,
                           "url": self._videoUrl("tv", tmdbId, season, num), "icon": (STILL_URL + still) if still else cItem.get("icon", ""),
                           "ep_name": name, "ep_overview": self.cleanHtmlStr(ep.get("overview") or ""), "ep_air": airDate,
                           "desc": "\n".join(x for x in (head, self.cleanHtmlStr(ep.get("overview") or "")) if x)})
            self.addVideo(params)
        lastPage = (len(episodes) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE
        if lastPage > 1:
            addPagingItems(self, cItem, page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CineHD.listSearchResult [%s] type[%s]" % (searchPattern, searchType))
        kind = searchType if searchType in ("movie", "tv") else "all"
        cItem = dict(cItem)
        cItem.update({"category": "ch_list", "url": self._discoverUrl(kind, q=searchPattern.strip()), "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("CineHD.getLinksForVideo [%s]" % cItem.get("url", ""))
        tmdbId = cItem.get("tmdb_id", "")
        if not tmdbId:
            return []
        kind = "tv" if cItem.get("media_type") == "tv" else "movie"
        fields = {"kind": kind, "id": tmdbId, "se": "", "title": urllib_quote(cItem.get("s_title", ""), safe=""), "year": cItem.get("s_year", "")}
        if kind == "tv":
            fields["se"] = "/%s/%s" % (cItem.get("s_season", 1), cItem.get("s_episode", 1))
        external = IsExternalResolveAllowed()
        urltab = []
        for label, tpl, needsExternal in EMBEDS:
            if needsExternal and not external:
                continue
            urltab.append({"name": label, "url": strwithmeta(tpl % fields, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        sidecar = buildSidecarFromItem(dict(cItem, desc=cItem.get("overview", "") or cItem.get("ep_overview", "")), IsSidecarEnabled())
        return applySidecarToLinks(urltab, sidecar)

    def getVideoLinks(self, videoUrl):
        printDBG("CineHD.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("CineHD.getArticleContent [%s]" % cItem.get("url", ""))
        kind = "tv" if cItem.get("media_type") == "tv" else "movie"
        meta = {}
        try:
            imdbId = self._tmdb("%s/%s/external_ids" % (kind, cItem.get("tmdb_id", ""))).get("imdb_id") or ""
            if imdbId:
                meta = getMetaByImdbId(kind, imdbId)
            if not meta and cItem.get("s_title"):
                meta = getMeta(kind, cItem["s_title"], cItem.get("s_year", ""), maxYearDiff=1)
        except Exception:
            printExc()
        info = {}
        for key, value in (("year", cItem.get("s_year")), ("tmdb_rating", cItem.get("rating")), ("genres", cItem.get("genres"))):
            if value:
                info[key] = value
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "") or cItem.get("overview", "")
        text = plot
        if cItem.get("category") == "ch_video" and kind == "tv":
            head = " | ".join(x for x in (cItem.get("ep_name", ""), cItem.get("ep_air", "")) if x)
            episode = "\n".join(x for x in (head, cItem.get("ep_overview", "")) if x)
            text = "[/br][/br]".join(x for x in (episode, plot) if x)
        elif cItem.get("category") == "ch_season":
            text = "\n".join(x for x in (cItem.get("desc", ""), plot) if x)
        images = [{"title": "", "url": u} for u in (meta.get("poster"), cItem.get("icon"), cItem.get("backdrop")) if u][:2]
        title = cItem.get("s_title", "") or cItem.get("title", "")
        if kind == "tv" and cItem.get("category") != "ch_series":
            title = cItem.get("title", "")
        return [{"title": title, "text": text, "images": images, "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", "")
        printDBG("CineHD.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "ch_menu":
            self.listTypeMenu(self.currItem)
        elif category == "ch_genres":
            self.listGenres(self.currItem)
        elif category == "ch_years":
            self.listYears(self.currItem)
        elif category == "ch_list":
            self.listItems(self.currItem)
        elif category == "ch_series":
            self.listSeasons(self.currItem)
        elif category == "ch_season":
            self.listEpisodes(self.currItem)
        elif category in ("search", "search_next_page"):
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
        CHostBase.__init__(self, CineHD(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cinehd")

    def getSearchTypes(self):
        return [(_("All"), "all"), (_("Movies"), "movie"), (_("Series"), "tv")]

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("ch_video", "ch_series", "ch_season")
