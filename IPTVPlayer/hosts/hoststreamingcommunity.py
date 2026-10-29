# -*- coding: utf-8 -*-
LAST_MODIFIED = "29.10.2026"
# 29.10.2026 - new host: StreamingCommunity (streamingcommunityz.day; Italian movies and series, Laravel + Inertia)
#   - Movies / Series / Recently added / Most viewed / Top rated / genres / search: the archive and search pages
#     answer an XHR request with JSON (Laravel paginator, 60 per page, last page known)
#   - title page (data-page JSON): seasons; a season page: its episodes with name and plot
#   - links: the site's own player (iframe -> vixcloud.cc embed -> parserVIXSRC) and VixSrc by the TMDb id
#   - watched flag (series -> season -> episode), favourites, downloaded marker, "Title (Year)" / "Show - SxxExx"
#     names, sidecar, INFO via moviemeta merged with the site's fields
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://streamingcommunityz.day/"


VIXSRC_URL = "https://vixsrc.to/"
XHR_HEADER = {"Accept": "application/json, text/plain, */*", "X-Requested-With": "XMLHttpRequest"}


def _unescapeAttr(text):
    # Laravel e() only produces these entities
    return text.replace("&quot;", '"').replace("&#039;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


class StreamingCommunity(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "streamingcommunity", "cookie": "streamingcommunity.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/streamingcommunity135.png")
        self.MENU = [{"category": "list_items", "title": _("Movies"), "filters": {"type": "movie"}},
                     {"category": "list_items", "title": _("Series"), "filters": {"type": "tv"}},
                     {"category": "list_items", "title": _("Recently added"), "filters": {"sort": "created_at"}},
                     {"category": "list_items", "title": _("Most viewed"), "filters": {"sort": "views"}},
                     {"category": "list_items", "title": _("Top rated"), "filters": {"sort": "score"}},
                     {"category": "list_genres", "title": _("Genres")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("streamingcommunity")
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
    def _json(self, url):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self.MAIN_URL, **XHR_HEADER)
        sts, data = self.getPage(url, params)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
            return None

    def _props(self, url):
        # the Inertia props of a page (data-page attribute)
        sts, data = self.getPage(url)
        page = self.cm.ph.getSearchGroups(data, r'data-page="([^"]+)"')[0] if sts else ""
        try:
            return json_loads(_unescapeAttr(page)).get("props", {}) if page else {}
        except Exception:
            printExc()
            return {}

    def _image(self, images, kinds=("poster", "cover")):
        # the site's pictures sit on cdn.<domain>/images/<file> (webp)
        for kind in kinds:
            for image in images or []:
                if image.get("type") == kind and image.get("filename"):
                    return "%s/images/%s" % (self.getMainUrl().replace("://", "://cdn.").rstrip("/"), ensure_str(image["filename"]))
        return ""

    def _titleUrl(self, item):
        return self.getFullUrl("it/titles/%s-%s" % (item.get("id"), ensure_str(item.get("slug", ""))))

    ###################################################
    # lists
    ###################################################
    def _addTitles(self, titles, cItem):
        normalize = IsMediaNamingNormalized()
        for item in titles:
            title = self.cleanHtmlStr(ensure_str(item.get("name", "")))
            if not title or not item.get("id"):
                continue
            series = item.get("type") == "tv"
            year = ensure_str(item.get("last_air_date") or item.get("release_date") or "")[:4] if not series else ""
            info = [(_("Rating"), ensure_str(item.get("score") or "")), (_("Seasons"), str(item.get("seasons_count") or "") if series else ""),
                    (_("Subtitles"), "ITA" if item.get("sub_ita") else "")]
            # the plot comes as a translation of the title
            plot = "".join(ensure_str(t.get("value") or "") for t in item.get("translations") or [] if t.get("key") == "plot")
            desc = " | ".join("%s: %s" % (k, v) for k, v in info if v)
            params = stripPagerKeys(dict(cItem))
            params.pop("filters", None)
            params.update({"good_for_fav": True, "url": self._titleUrl(item), "icon": self._image(item.get("images")) or self.DEFAULT_ICON_URL,
                           "desc": "%s[/br]%s" % (desc, plot) if desc and plot else desc or plot, "plot": plot,
                           "s_title": title, "s_year": year, "title_id": str(item["id"])})
            if series:
                params.update({"category": "list_seasons", "title": title, "meta_type": "tv"})
                self.addDir(params)
            else:
                withYear = year and normalize and not title.endswith("(%s)" % year)
                params.update({"category": "video", "title": "%s (%s)" % (title, year) if withYear else title, "meta_type": "movie"})
                self.addVideo(params)

    def listItems(self, cItem):
        printDBG("StreamingCommunity.listItems |%s|" % cItem)
        page = max(1, int(cItem.get("page", 1) or 1))
        filters = cItem.get("filters", {})
        url = self.getFullUrl("%s?%s" % ("it/search" if "q" in filters else "it/archive", urllib_urlencode(filters)))
        res = self._json("%s&page=%d" % (url, page))
        if not isinstance(res, dict):
            return
        self._addTitles(res.get("data") or [], cItem)
        lastPage = int(res.get("last_page") or page)
        # the list reads its page from cItem["page"]; the template only gives the pager rows a url and the Jump row
        addPagingItems(self, dict(cItem, url=url), page, lastPage > page, lastPage, url.replace("{", "{{").replace("}", "}}") + "&page={page}")

    def listGenres(self, cItem):
        genres = self._props(self.getFullUrl("it/archive")).get("genres") or []
        for genre in sorted(genres, key=lambda g: ensure_str(g.get("name", "")).lower()):
            if genre.get("hidden") or not genre.get("id"):
                continue
            self.addDir(dict(cItem, good_for_fav=True, category="list_items", title=ensure_str(genre.get("name", "")),
                             filters={"genre[]": str(genre["id"])}))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("StreamingCommunity.listSearchResult [%s]" % searchPattern)
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        self.listItems(dict(cItem, category="search_next_page", s_pattern=pattern, filters={"q": pattern}))

    def _titleData(self, url):
        # (title dict, loaded season dict) of a title / season page
        props = self._props(url)
        return props.get("title") or {}, props.get("loadedSeason") or {}

    def listSeasons(self, cItem):
        printDBG("StreamingCommunity.listSeasons |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        title, loaded = self._titleData(url)
        seasons = [s for s in title.get("seasons") or [] if s.get("number")]
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", "") or cItem["title"]
        fields = {"s_title": sTitle, "tmdb_id": str(title.get("tmdb_id") or ""), "imdb": ensure_str(title.get("imdb_id") or ""), "plot": ensure_str(title.get("plot") or ""),
                  "s_year": ensure_str(title.get("release_date") or "")[:4], "title_id": str(title.get("id") or cItem.get("title_id", ""))}
        if len(seasons) == 1:
            number = str(seasons[0]["number"])
            self.listEpisodes(dict(cItem, category="list_episodes", season=number, url="%s#s%s" % (url, number), **fields),
                              loaded if str(loaded.get("number")) == number else None)
            return
        normalize = IsMediaNamingNormalized()
        for season in seasons:
            number = season["number"]
            seasonTag = formatSxxExx(number) if normalize else "%s %s" % (_("Season"), number)
            params = stripPagerKeys(dict(cItem))
            params.update(fields)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (sTitle, seasonTag), "season": str(number),
                           "url": "%s#s%s" % (url, number), "desc": "%s: %s[/br]%s" % (_("Episodes"), season.get("episodes_count") or "?", fields["plot"])})
            self.addDir(params)

    def listEpisodes(self, cItem, loaded=None):
        printDBG("StreamingCommunity.listEpisodes |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        season = str(cItem.get("season", "") or self.cm.ph.getSearchGroups(cItem["url"], r"#s(\d+)")[0])
        if loaded is None:
            title, loaded = self._titleData("%s/season-%s" % (url, season))
            if title:
                cItem = dict(cItem, tmdb_id=str(title.get("tmdb_id") or cItem.get("tmdb_id", "")), title_id=str(title.get("id") or cItem.get("title_id", "")),
                             imdb=ensure_str(title.get("imdb_id") or cItem.get("imdb", "")), plot=cItem.get("plot") or ensure_str(title.get("plot") or ""))
        episodes = [e for e in loaded.get("episodes") or [] if e.get("number") and e.get("id")]
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", "") or cItem["title"]
        normalize = IsMediaNamingNormalized()
        for item in episodes:
            # names and plots of the episodes may hold HTML entities ("L&#39;amore")
            episode, name = item["number"], self.cleanHtmlStr(ensure_str(item.get("name") or ""))
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            else:
                title = "%s - %s %s - %s %s" % (sTitle, _("Season"), season, _("Episode"), episode)
            if name and not re.match(r"^Episodio\s*\d+$", name, re.I):
                title = "%s - %s" % (title, name)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "url": "%s#s%se%s" % (url, season, episode),
                           "season": season, "episode": str(episode), "episode_id": str(item["id"]), "meta_type": "tv",
                           "icon": self._image(item.get("images"), ("cover",)) or cItem.get("icon", ""),
                           "desc": self.cleanHtmlStr(ensure_str(item.get("plot") or "")) or cItem.get("plot", "")})
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("StreamingCommunity.getLinksForVideo [%s]" % cItem.get("url", ""))
        titleId, tmdb, imdb = cItem.get("title_id", ""), cItem.get("tmdb_id", ""), cItem.get("imdb", "")
        if not titleId or not tmdb:
            # the list rows of movies carry no TMDb / IMDb id, the title page does
            title, _loaded = self._titleData(cItem["url"].split("#", 1)[0])
            titleId, tmdb, imdb = str(title.get("id") or titleId), str(title.get("tmdb_id") or tmdb), ensure_str(title.get("imdb_id") or imdb)
        if not titleId:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        season, episode, episodeId = str(cItem.get("season", "") or ""), str(cItem.get("episode", "") or ""), cItem.get("episode_id", "")
        iframe = self.getFullUrl("it/iframe/%s" % titleId) + ("?episode_id=%s" % episodeId if episodeId else "")
        urltab = [{"name": "VixCloud", "url": strwithmeta(iframe, {"Referer": self.MAIN_URL}), "need_resolve": 1}]
        if tmdb:
            vixsrc = "%stv/%s/%s/%s?lang=it" % (VIXSRC_URL, tmdb, season, episode) if episodeId else "%smovie/%s?lang=it" % (VIXSRC_URL, tmdb)
            urltab.append({"name": "VixSrc", "url": strwithmeta(vixsrc, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("plot", ""), metaQuery=self._metaQuery(cItem, imdb)))

    def getVideoLinks(self, videoUrl):
        printDBG("StreamingCommunity.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if "/it/iframe/" in videoUrl:
            # the site's player page: a vixcloud.cc embed with a fresh token
            sts, data = self.getPage(videoUrl, dict(self.defaultParams, header=dict(self.HEADER, Referer=self.MAIN_URL)))
            embed = _unescapeAttr(self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"')[0]) if sts else ""
            if not embed:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
                return []
            videoUrl = strwithmeta(embed, {"Referer": self.MAIN_URL})
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    @staticmethod
    def _metaQuery(cItem, imdb):
        # the lookup of the INFO view (getMetaByImdbId, else getMeta by title) for the download sidecar
        return sidecarMetaQuery(cItem.get("meta_type", "") or "movie", cItem.get("s_title", "") or cItem.get("title", ""), cItem.get("s_year", ""), imdbId=imdb, skip=())

    def getArticleContent(self, cItem):
        printDBG("StreamingCommunity.getArticleContent [%s]" % cItem.get("url", ""))
        title, _loaded = self._titleData(cItem.get("url", "").split("#", 1)[0])
        imdb = ensure_str(title.get("imdb_id") or cItem.get("imdb", ""))
        mediaType = cItem.get("meta_type", "") or "movie"
        info = {}
        for key, value in (("year", ensure_str(title.get("release_date") or "")[:4]), ("rating", ensure_str(title.get("score") or "")),
                           ("duration", "%s min" % title["runtime"] if title.get("runtime") else ""), ("quality", ensure_str(title.get("quality") or "")),
                           ("genres", ", ".join(ensure_str(g.get("name", "")) for g in title.get("genres") or [])),
                           ("actors", ", ".join(ensure_str(a.get("name", "")) for a in (title.get("main_actors") or [])[:6]))):
            if value:
                info[key] = value
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta:
                meta = getMeta(mediaType, cItem.get("s_title", "") or cItem.get("title", ""), info.get("year", cItem.get("s_year", "")))
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        if "cast" in info:
            info.pop("actors", None)
        text = cItem.get("desc", "") if cItem.get("episode") else ensure_str(title.get("plot") or "") or cItem.get("plot", "")
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
        printDBG("StreamingCommunity.handleService name[%s], category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category in ("list_items", "search_next_page"):
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "search":
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
        CHostBase.__init__(self, StreamingCommunity(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("streamingcommunity")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
