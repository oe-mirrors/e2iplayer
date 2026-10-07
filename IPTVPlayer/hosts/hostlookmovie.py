# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - new host for lookmovie2.to (www.lookmovie2.to)
#   English movies and TV shows. Lists: /movies[/page/N], /movies/genre/<g>[/page/N], /shows (latest episodes),
#   /shows/filter (latest shows), /shows/genre/<g>, search /movies/search/?q= + /shows/search/?q=.
#   Streams: the /movies/play/<slug> and /shows/play/<slug> pages carry a short-lived hash/expires pair,
#   /api/v1/security/movie-access?id_movie=..  resp. episode-access?id_episode=.. answer with HLS
#   (one quality per entry, 480p for guests) + VTT subtitles. The slug's number is the IMDb id (moviemeta INFO).
#   + watched flag / downloaded flag / name normalisation / sidecar / favourites / paging (First / Jump / Next).
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://www.lookmovie2.to/"


VIEW_RE = re.compile(r'/(movies|shows)/view/((\d+)-[^/?#]+)')
EPISODE_JS_RE = re.compile(r"\{\s*title:\s*'((?:[^'\\]|\\.)*)',\s*index:\s*'\d+',\s*episode:\s*'(\d+)',\s*id_episode:\s*(\d+),\s*season:\s*'(\d+)'")


class LookMovie(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "slug", "season", "episode", "id_episode",
                  "series_url", "icon", "desc", "meta_type", "meta_title", "meta_year", "imdb")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "lookmovie", "cookie": "lookmovie.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "lm_sub", "title": _("Movies"), "kind": "movies"},
                     {"category": "lm_sub", "title": _("Series"), "kind": "shows"}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("lookmovie")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            url = str(cItem.get("url", "") or "").strip()
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url if url else ""
            if category == "lm_show":
                return "series:%s" % url if url else ""
            if category == "lm_season":
                slug = str(cItem.get("slug", "") or "").strip()
                season = str(cItem.get("season", "") or "").strip()
                return "season:%s|%s" % (slug, season) if slug and season else ""
            return ""
        except Exception:
            printExc()
        return ""

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _ajaxParams(self, referer):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Referer": referer, "X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/plain, */*"})
        return params

    ###################################################
    # naming
    ###################################################
    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year:
            return "%s (%s)" % (title, year)
        return title

    def _episodeTitle(self, sTitle, season, episode, epName=""):
        if IsMediaNamingNormalized():
            return "%s - %s" % (sTitle, formatSxxExx(season, episode))
        title = "%s - %s %s, %s %s" % (sTitle, _("Season"), season, _("Episode"), episode)
        return "%s - %s" % (title, epName) if epName else title

    ###################################################
    # lists
    ###################################################
    def listSub(self, cItem):
        if cItem["kind"] == "movies":
            tab = [{"category": "list_items", "title": _("Latest"), "url": self.getFullUrl("movies")},
                   {"category": "list_genres", "title": _("Genres"), "url": self.getFullUrl("movies/genres")}]
        else:
            tab = [{"category": "list_items", "title": _("Newest Episodes"), "url": self.getFullUrl("shows")},
                   {"category": "list_items", "title": "%s - %s" % (_("Series"), _("Latest")), "url": self.getFullUrl("shows/filter")},
                   {"category": "list_genres", "title": _("Genres"), "url": self.getFullUrl("shows")}]
        params = dict(cItem)
        params.pop("title", None)
        self.listsTab(tab, params)

    def listGenres(self, cItem):
        printDBG("LookMovie.listGenres |%s|" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        kind = cItem["kind"]
        seen = set()
        for href, title in re.findall(r'<a href="(/%s/genre/[^"]+)"\s*>([^<]+)</a>' % kind, data):
            title = self.cleanHtmlStr(title)
            url = self.getFullUrl(href.replace(" ", "%20"))
            if not title or url in seen:
                continue
            seen.add(url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": url})
            self.addDir(params)
        self.currList.sort(key=lambda x: x["title"].lower())

    def _nextPageUrl(self, data):
        pag = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', "</ul>", False)[1]
        pos = pag.find('class="active"')
        if pos < 0:
            return ""
        current = 0
        nextUrl = ""
        for href, num in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*(\d+)\s*</a>', pag[pos:]):
            num = int(num)
            if not current:
                current = num
            elif num == current + 1:
                nextUrl = href
                break
        if not nextUrl:
            return ""
        return self._fixUrl(nextUrl)

    def _fixUrl(self, url):
        url = url.replace("&amp;", "&")
        if url.startswith("//"):
            url = "https:" + url
        return self.getFullUrl(url)

    def _pageTemplate(self, cItem, nextUrl, data):
        # "/movies/genre/action/page/2", "/shows?page=2", "/movies/search?q=x&page=2" -> {page} template;
        # the last page only where the site links it ("Last"), the genre pages show a sliding window only
        tpl = re.sub(r"(/page/|[?&]page=)\d+", r"\1{page}", nextUrl, count=1) if nextUrl else ""
        if "{page}" not in tpl:
            tpl = cItem.get("page_tpl", "")
        last = self.cm.ph.getSearchGroups(data, r'<li class="last"><a href="[^"]*?[?&;/]page[=/](\d+)"')[0]
        return tpl, int(last) if last else 0

    def _addCard(self, cItem, card):
        href = self.cm.ph.getSearchGroups(card, r'<a href="([^"]+)"')[0].replace("&amp;", "&")
        m = VIEW_RE.search(href)
        if not m:
            return False
        kind, slug, imdbNum = m.groups()
        icon = self.cm.ph.getSearchGroups(card, r'data-src="(/images/[^"]+)"')[0]
        icon = self.getFullIconUrl(icon) if icon else ""
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(card, "<h6>", "</h6>", False)[1])
        if not title:
            return False
        year = self.cm.ph.getSearchGroups(card, r'<p class="year">\s*(\d{4})')[0] or self.cm.ph.getSearchGroups(slug, r'-(\d{4})$')[0]
        rating = self.cm.ph.getSearchGroups(card, r'<p class="rate">.*?<span>([0-9.]+)</span>')[0]
        desc = [t for t in (year, ("IMDb %s" % rating) if rating else "") if t]
        imdb = "tt%s" % imdbNum if len(imdbNum) >= 7 else ""
        params = stripPagerKeys(dict(cItem), ("search_pattern", "page_tpl"))
        params.update({"good_for_fav": True, "icon": icon, "slug": slug, "imdb": imdb, "desc": " | ".join(desc)})
        if kind == "movies":
            params.update({"category": "lm_movie", "url": self.getFullUrl("movies/view/%s" % slug), "title": self._movieTitle(title, year),
                           "s_title": title, "meta_type": "movie", "meta_title": title, "meta_year": year})
            self.addVideo(params)
            return True
        seriesUrl = self.getFullUrl("shows/view/%s" % slug)
        epId = self.cm.ph.getSearchGroups(href, r'id_episode=(\d+)')[0]
        if epId:
            season = self.cm.ph.getSearchGroups(href, r'season=(\d+)')[0]
            episode = self.cm.ph.getSearchGroups(href, r'[?&]episode=(\d+)')[0]
            epDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(card, '<p class="describe">', "</p>", False)[1])
            params.update({"category": "lm_episode", "title": self._episodeTitle(title, season, episode), "s_title": title,
                           "season": season, "episode": episode, "id_episode": epId, "series_url": seriesUrl,
                           "url": "%s?season=%s&episode=%s&id_episode=%s" % (seriesUrl, season, episode, epId),
                           "desc": epDesc, "meta_type": "tv", "meta_title": title, "meta_year": year})
            self.addVideo(params)
            return True
        params.update({"category": "lm_show", "url": seriesUrl, "title": title, "s_title": title,
                       "meta_type": "tv", "meta_title": title, "meta_year": year})
        self.addDir(params)
        return True

    def listItems(self, cItem, paging=True):
        # returns the url of the next page ("" when there is none)
        printDBG("LookMovie.listItems |%s|" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return ""
        nextUrl = self._nextPageUrl(data)
        cnt = 0
        seen = set()
        for card in data.split('<div class="movie-item-style-2')[1:]:
            href = self.cm.ph.getSearchGroups(card, r'<a href="([^"]+)"')[0]
            if href in seen:
                continue
            seen.add(href)
            if self._addCard(cItem, card):
                cnt += 1
        if not cnt or nextUrl == cItem["url"]:
            nextUrl = ""
        if paging:
            page = int(cItem.get("page", 1) or 1)
            tpl, lastPage = self._pageTemplate(cItem, nextUrl, data)
            params = dict(cItem, page_tpl=tpl)
            addPagingItems(self, params, page, bool(nextUrl), lastPage, tpl, {"url": nextUrl} if nextUrl and not tpl else None)
        return nextUrl

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("LookMovie.listSearchResult [%s]" % searchPattern)
        query = urllib_quote_plus(searchPattern)
        for kind, title in (("movies", "%s: %s" % (_("More results"), _("Movies"))), ("shows", "%s: %s" % (_("More results"), _("Series")))):
            params = dict(cItem)
            params.update({"category": "list_items", "kind": kind, "url": self.getFullUrl("%s/search/?q=%s" % (kind, query))})
            nextUrl = self.listItems(params, False)
            if nextUrl:
                params.update({"good_for_fav": False, "title": title, "url": nextUrl, "page": 2})
                self.addDir(params)

    def _getShowStorage(self, slug):
        url = self.getFullUrl("shows/play/%s" % slug)
        sts, data = self.getPage(url)
        if not sts:
            return {}
        storage = self.cm.ph.getDataBeetwenMarkers(data, "window['show_storage']", "};", False)[1]
        if not storage:
            return {}
        ret = {"page": url, "hash": self.cm.ph.getSearchGroups(storage, r"hash:\s*'([^']+)'")[0],
               "expires": self.cm.ph.getSearchGroups(storage, r"expires:\s*(\d+)")[0], "episodes": []}
        for title, episode, epId, season in EPISODE_JS_RE.findall(storage):
            title = self.cleanHtmlStr(title.replace("\\'", "'").replace('\\"', '"'))
            ret["episodes"].append({"title": title, "episode": int(episode), "id_episode": epId, "season": int(season)})
        return ret

    def listSeasons(self, cItem):
        printDBG("LookMovie.listSeasons |%s|" % cItem["url"])
        storage = self._getShowStorage(cItem["slug"])
        seasons = sorted(set([e["season"] for e in storage.get("episodes", [])]))
        if not seasons:
            SetIPTVPlayerLastHostError(_("No episodes available yet."))
            return
        sTitle = cItem.get("s_title", cItem["title"])
        for season in seasons:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "lm_season", "title": "%s - %s %s" % (sTitle, _("Season"), season),
                           "s_title": sTitle, "season": str(season), "series_url": cItem["url"],
                           "url": "%s?season=%s" % (cItem["url"], season)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("LookMovie.listEpisodes |%s| season %s" % (cItem.get("slug", ""), cItem.get("season", "")))
        storage = self._getShowStorage(cItem["slug"])
        sTitle = cItem.get("s_title", cItem["title"])
        seriesUrl = cItem.get("series_url", cItem["url"])
        eps = [e for e in storage.get("episodes", []) if str(e["season"]) == str(cItem["season"])]
        eps.sort(key=lambda e: e["episode"])
        for e in eps:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "lm_episode", "title": self._episodeTitle(sTitle, e["season"], e["episode"], e["title"]),
                           "s_title": sTitle, "episode": str(e["episode"]), "id_episode": e["id_episode"],
                           "url": "%s?season=%s&episode=%s&id_episode=%s" % (seriesUrl, e["season"], e["episode"], e["id_episode"]),
                           "desc": ""})
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def _subtitles(self, data):
        subs = []
        seen = {}
        for sub in data.get("subtitles") or []:
            # "file" is a list for OpenSubtitles entries the site only fetches on demand - skip those
            path = sub.get("file", "") if isinstance(sub, dict) else ""
            if not isinstance(path, type("")) and not isinstance(path, type(u"")):
                continue
            if not path or not path.lower().endswith((".vtt", ".srt")):
                continue
            url = self.getFullUrl(path)
            if url in [s["url"] for s in subs]:
                continue
            lang = self.cm.ph.getSearchGroups(path, r'/([a-zA-Z]{2,3}(?:-[a-zA-Z]{2})?)(?:_[0-9a-f]+)?\.(?:vtt|srt)$')[0]
            title = sub.get("language", "") or lang or "?"
            seen[title] = seen.get(title, 0) + 1
            if seen[title] > 1:
                title = "%s #%d" % (title, seen[title])
            subs.append({"title": title, "lang": lang.split("-")[0].lower(), "url": url, "format": "vtt" if url.lower().endswith(".vtt") else "srt"})
        return subs

    def getLinksForVideo(self, cItem):
        printDBG("LookMovie.getLinksForVideo [%s]" % cItem.get("url", ""))
        slug = cItem.get("slug", "")
        if not slug:
            return []
        if cItem.get("category") == "lm_movie":
            playUrl = self.getFullUrl("movies/play/%s" % slug)
            sts, data = self.getPage(playUrl)
            if not sts:
                return []
            storage = self.cm.ph.getDataBeetwenMarkers(data, "window['movie_storage']", "};", False)[1]
            movieId = self.cm.ph.getSearchGroups(storage, r"id_movie:\s*(\d+)")[0]
            hashVal = self.cm.ph.getSearchGroups(storage, r'''hash:\s*["']([^"']+)["']''')[0]
            expires = self.cm.ph.getSearchGroups(storage, r"expires:\s*(\d+)")[0]
            if not movieId or not hashVal:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
                return []
            apiUrl = self.getFullUrl("api/v1/security/movie-access?id_movie=%s&hash=%s&expires=%s" % (movieId, hashVal, expires))
        else:
            storage = self._getShowStorage(slug)
            epId = cItem.get("id_episode", "")
            if not storage.get("hash") or not epId:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
                return []
            playUrl = storage["page"]
            apiUrl = self.getFullUrl("api/v1/security/episode-access?id_episode=%s&hash=%s&expires=%s" % (epId, storage["hash"], storage["expires"]))
        sts, data = self.getPage(apiUrl, self._ajaxParams(playUrl))
        if not sts:
            return []
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return []
        if not isinstance(data, dict) or not data.get("success"):
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        meta = {"User-Agent": self.HEADER["User-Agent"], "Referer": self.MAIN_URL, "Origin": self.MAIN_URL.rstrip("/"), "iptv_proto": "m3u8"}
        subs = self._subtitles(data)
        if subs:
            meta["external_sub_tracks"] = subs
        links = []
        for quality, url in (data.get("streams") or {}).items():
            if not url or not self.cm.isValidUrl(url):
                continue
            res = int(self.cm.ph.getSearchGroups(str(quality), r'(\d+)')[0] or 0)
            links.append((res, {"name": "%sp HLS" % res if res else str(quality), "url": strwithmeta(url, dict(meta)), "need_resolve": 0}))
        links.sort(key=lambda x: -x[0])
        urltab = [x[1] for x in links]
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    ###################################################
    # info / favourites
    ###################################################
    def _parseViewPage(self, data):
        info = {"desc": "", "poster": "", "year": "", "duration": "", "genres": "", "rating": ""}
        info["desc"] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<p class="description', "</p>", False)[1].split(">", 1)[-1])
        if not info["desc"]:
            info["desc"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]+)"')[0])
        poster = self.cm.ph.getSearchGroups(data, r'movie__poster[^>]+data-background-image="([^"]+)"')[0] or \
            self.cm.ph.getSearchGroups(data, r"poster_medium:\s*'([^']+)'")[0]
        info["poster"] = self.getFullIconUrl(poster) if poster else ""
        genres = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="genres">', "</div>", False)[1])
        parts = [t.strip() for t in genres.split(",") if t.strip()]
        if parts and re.match(r"^\d{4}$", parts[0]):
            info["year"] = parts.pop(0)
        info["genres"] = ", ".join(parts)
        info["duration"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'movie-description__duration">\s*<span>([^<]+)</span>')[0])
        return info

    def getArticleContent(self, cItem):
        printDBG("LookMovie.getArticleContent [%s]" % cItem.get("url", ""))
        mediaType = cItem.get("meta_type", "")
        kind = "movies" if mediaType == "movie" else "shows"
        info = {"desc": "", "poster": "", "year": "", "duration": "", "genres": "", "rating": ""}
        if cItem.get("slug"):
            sts, data = self.getPage(self.getFullUrl("%s/view/%s" % (kind, cItem["slug"])))
            if sts:
                info = self._parseViewPage(data)
        meta = {}
        try:
            if cItem.get("imdb"):
                meta = getMetaByImdbId(mediaType, cItem["imdb"])
            if not meta:
                meta = getMeta(mediaType, cItem.get("meta_title", ""), cItem.get("meta_year", "") or info["year"])
        except Exception:
            printExc()
            meta = {}
        otherInfo = dict(meta.get("info", {}) or {})
        for key in ("year", "duration", "genres"):
            if info[key]:
                otherInfo.setdefault(key, info[key])
        text = meta.get("plot", "") or info["desc"] or cItem.get("desc", "")
        icon = meta.get("poster", "") or info["poster"] or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text,
                 "images": [{"title": "", "url": icon}] if icon else [],
                 "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("meta_type"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("LookMovie.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "lm_sub":
            self.listSub(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "lm_show":
            self.listSeasons(self.currItem)
        elif category == "lm_season":
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, LookMovie(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("lookmovie")

    def withArticleContent(self, cItem):
        return bool(cItem.get("meta_type"))
