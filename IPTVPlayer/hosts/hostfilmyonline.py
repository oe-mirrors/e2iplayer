# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 04.10.2026 - new host for filmyonline.cc (Polish movies and series; MTDb 4 site,
#   filmyonline.pl is only a parked domain)
#   - Cloudflare: every request goes through getPageCFProtection (MyE2i solves the browser check, the
#     solving User-Agent is remembered next to the cookie jar)
#   - the site's own JSON API (/api/v1/..., same as its web app): channels (latest / trending / all
#     movies and series, yearly tops), genres and search; First page / Jump / Next page on channels
#   - movies and episodes are VIDEO rows keyed on their page url (/titles/<id>, /titles/<id>/season/<s>/
#     episode/<e>); series -> seasons (when more than one) -> episodes (ascending)
#   - links: the title's / episode's "full" videos (embed urls: streamtape, dood, voe ...) go to
#     urlparser, trailers are left out
#   - watched flag, downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx"), sidecar, INFO via moviemeta (the title's IMDb id) + the site's data
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://filmyonline.cc/"


COLOR_CODE_RE = re.compile(r"\\c[0-9A-Fa-f]{8}")
PAGING_KEYS = ("base_url", "page_tpl")
POLISH_ASCII = (("ą", "a"), ("ć", "c"), ("ę", "e"), ("ł", "l"), ("ń", "n"), ("ó", "o"), ("ś", "s"), ("ź", "z"), ("ż", "z"),
                ("Ą", "a"), ("Ć", "c"), ("Ę", "e"), ("Ł", "l"), ("Ń", "n"), ("Ó", "o"), ("Ś", "s"), ("Ź", "z"), ("Ż", "z"))


def _stripColors(text):
    return COLOR_CODE_RE.sub("", text or "")


def _str(value):
    # the API data is native str already (ensure_str_deep), numbers become text
    return "%s" % value if value is not None else ""


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _genreSlug(name):
    # "Sci-Fi & Fantasy" -> "sci-fi-fantasy", "Kryminał" -> "kryminal" (the genre channel's restriction)
    name = _str(name)
    for letter, plain in POLISH_ASCII:
        name = name.replace(letter, plain)
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class FilmyOnline(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "title_id", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "filmyonline", "cookie": "filmyonline.cookie"})
        self.MAIN_URL = gettytul()
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

        def channel(slug):
            return self.getFullUrl("/api/v1/channel/%s?loader=channelPage" % slug)

        self.MENU = [
            {"category": "list_items", "title": "%s - %s" % (_("Movies"), _("Latest")), "url": channel("latest-movies")},
            {"category": "list_items", "title": "%s - %s" % (_("Movies"), _("Popular")), "url": channel("trending-movies")},
            {"category": "list_items", "title": _("Movies"), "url": channel("movies")},
            {"category": "list_items", "title": "%s - %s" % (_("Series"), _("Latest")), "url": channel("latest-series")},
            {"category": "list_items", "title": "%s - %s" % (_("Series"), _("Popular")), "url": channel("trending-series")},
            {"category": "list_items", "title": _("Series"), "url": channel("series")},
            {"category": "list_items", "title": "Top 2026", "url": channel("top-filmy-2026")},
            {"category": "list_items", "title": "Top 2025", "url": channel("top-filmy-2025")},
            {"category": "fo_genres", "title": _("Genres")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("filmyonline")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _api(self, url):
        # the API answers 401 without the site's Referer (Laravel Sanctum: a request of its own web app)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, **{"Accept": "application/json, text/plain, */*", "Referer": self.MAIN_URL})
        sts, data = self.getPage(url, params)
        if not sts:
            return {}
        try:
            data = ensure_str_deep(json_loads(data))
            return data if isinstance(data, dict) else {}
        except Exception:
            printExc()
        return {}

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", url or "").rstrip("/").lower()

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("fo_video", "fo_series", "fo_season"):
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
            prefix = {"fo_video": "video", "fo_series": "series", "fo_season": "season"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listGenres(self, cItem):
        data = self._api(self.getFullUrl("/api/v1/value-lists/genres"))
        for genre in data.get("genres") or []:
            name = _str(genre.get("name")) if isinstance(genre, dict) else ""
            slug = _genreSlug(name)
            if not slug:
                continue
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"category": "list_items", "title": name, "good_for_fav": True,
                           "url": self.getFullUrl("/api/v1/channel/genre?restriction=%s&loader=channelPage" % slug)})
            self.addDir(params)

    def _addTitle(self, title, normalize):
        if not isinstance(title, dict) or title.get("model_type", "title") != "title" or not title.get("id"):
            return False
        if "primary_video" in title and not title.get("primary_video"):
            return False  # nothing to play on the site
        titleId = _int(title.get("id"))
        name = _str(title.get("name")).strip()
        year = _str(title.get("year") or _str(title.get("release_date"))[:4])
        if not name:
            return False
        rating = _str(title.get("rating"))
        fields = ((_("Year"), year, "cyan"), (_("Rating"), rating if rating not in ("0", "None") else "", "green"))
        desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
        plot = _str(title.get("description")).strip()
        if plot:
            desc = "%s[/br]%s" % (desc, plot) if desc else plot
        params = {"name": "category", "good_for_fav": True, "url": self.getFullUrl("/titles/%d" % titleId), "title_id": titleId,
                  "icon": _str(title.get("poster")), "desc": desc, "meta_title": _str(title.get("original_title")) or name, "meta_year": year}
        if title.get("is_series"):
            params.update({"category": "fo_series", "title": name, "s_title": name, "meta_type": "tv"})
            self.addDir(params)
        else:
            dispTitle = "%s (%s)" % (name, year) if normalize and year else name
            params.update({"category": "fo_video", "title": dispTitle, "meta_type": "movie"})
            self.addVideo(params)
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        url = baseUrl if page <= 1 else "%s&page=%d" % (baseUrl, page)
        printDBG("FilmyOnline.listItems [%s]" % url)
        content = ((self._api(url).get("channel") or {}).get("content")) or {}
        normalize = IsMediaNamingNormalized()
        added = False
        for title in content.get("data") or []:
            added = self._addTitle(title, normalize) or added
        hasNext = bool(content.get("next_page")) and bool(content.get("data"))
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, 0, baseUrl + "&page={page}")
        if not added and not hasNext and page <= 1:
            SetIPTVPlayerLastHostError(_("No items found"))

    def listSeries(self, cItem):
        printDBG("FilmyOnline.listSeries [%s]" % cItem.get("url", ""))
        titleId = cItem.get("title_id")
        title = self._api(self.getFullUrl("/api/v1/titles/%s?loader=titlePage" % titleId)).get("title") or {}
        seasons = sorted(set(_int(s.get("number")) for s in (title.get("seasons") or []) if isinstance(s, dict)) - set([0]))
        if not seasons:
            seasons = list(range(1, _int(title.get("seasons_count")) + 1))
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, s_season=seasons[0]))
            return
        for season in seasons:
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "category": "fo_season", "title": "%s %d" % (_("Season"), season), "s_season": season,
                           "url": self.getFullUrl("/titles/%s/season/%d" % (titleId, season))})
            self.addDir(params)

    def listEpisodes(self, cItem):
        titleId, season = cItem.get("title_id"), _int(cItem.get("s_season"))
        printDBG("FilmyOnline.listEpisodes [%s] season %d" % (titleId, season))
        baseUrl = self.getFullUrl("/api/v1/titles/%s/seasons/%d?loader=seasonPage" % (titleId, season))
        episodes, page = [], 1
        while page and page <= 10:  # 30 episodes per page
            data = self._api(baseUrl if page == 1 else "%s&page=%d" % (baseUrl, page)).get("episodes") or {}
            episodes.extend(e for e in (data.get("data") or []) if isinstance(e, dict))
            page = _int(data.get("next_page"))
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        seen = set()
        for ep in sorted(episodes, key=lambda e: _int(e.get("episode_number"))):
            num = _int(ep.get("episode_number"))
            if not num or num in seen or ("primary_video" in ep and not ep.get("primary_video")):
                continue  # episodes without a video are only TMDb data on the site
            seen.add(num)
            name = _str(ep.get("name")).strip()
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, num))
            else:
                title = " - ".join(x for x in (show, "S%02dE%02d" % (season, num), name) if x)
            plot = _str(ep.get("description")).strip()
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "category": "fo_video", "title": title,
                           "url": self.getFullUrl("/titles/%s/season/%d/episode/%d" % (titleId, season, num)),
                           "icon": _str(ep.get("poster")) or cItem.get("icon", ""), "desc": "[/br]".join(x for x in (name, plot) if x) or cItem.get("desc", ""),
                           "s_title": show, "s_season": season, "s_episode": num, "meta_type": "tv"})
            self.addVideo(params)
        if episodes and not seen:
            SetIPTVPlayerLastHostError(_("No stream available"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmyOnline.listSearchResult [%s]" % searchPattern)
        query = searchPattern.strip()
        if not query:
            return
        # with=primaryVideo: the site's search also lists TMDb titles nobody uploaded a video for (most of
        # the hits), they come without primary_video and _addTitle leaves them out
        data = self._api(self.getFullUrl("/api/v1/search/%s?loader=searchPage&with=primaryVideo" % urllib_quote(query, safe="")))
        normalize = IsMediaNamingNormalized()
        for title in data.get("results") or []:
            self._addTitle(title, normalize)

    ###################################################
    # links
    ###################################################
    def _episodeApi(self, cItem):
        return self.getFullUrl("/api/v1/titles/%s/seasons/%s/episodes/%s?loader=episodePage" % (cItem.get("title_id"), cItem.get("s_season"), cItem.get("s_episode")))

    def getLinksForVideo(self, cItem):
        printDBG("FilmyOnline.getLinksForVideo [%s]" % cItem.get("url", ""))
        if cItem.get("s_episode"):
            data = self._api(self._episodeApi(cItem))
            source = data.get("episode") or {}
        else:
            data = self._api(self.getFullUrl("/api/v1/titles/%s?loader=titlePage" % cItem.get("title_id")))
            source = data.get("title") or {}
        urltab, seen, names = [], set(), {}
        for video in source.get("videos") or []:
            if not isinstance(video, dict) or video.get("category") not in ("full", None):
                continue
            src = _str(video.get("src")).strip()
            if src.startswith("//"):
                src = "https:" + src
            if not self.cm.isValidUrl(src) or src in seen:
                continue
            seen.add(src)
            direct = video.get("type") != "embed" and re.search(r"\.(?:mp4|m3u8)(?:\?|$)", src)
            if not direct and self.up.checkHostSupport(src) != 1:
                printDBG("FilmyOnline.getLinksForVideo unsupported hoster [%s]" % src)  # e.g. listeamed.net (VidGuard)
                continue
            extra = " ".join(x for x in (_str(video.get("language")).upper(), _str(video.get("quality")).upper()) if x and x != "NONE")
            host = self.up.getHostName(src)
            name = "%s (%s)" % (host, extra) if extra else host
            names[name] = names.get(name, 0) + 1
            if names[name] > 1:
                name = "%s #%d" % (name, names[name])  # two uploads on the same hoster
            urltab.append({"name": name, "url": strwithmeta(src, {"Referer": self.MAIN_URL}), "need_resolve": 0 if direct else 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        story = _str(source.get("description"))
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=_stripColors(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("FilmyOnline.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("FilmyOnline.getArticleContent [%s]" % cItem.get("url", ""))
        data = self._api(self.getFullUrl("/api/v1/titles/%s?loader=titlePage" % cItem.get("title_id")))
        title = data.get("title") or {}
        info = {}
        year = _str(title.get("year")) or cItem.get("meta_year", "")
        if year:
            info["year"] = year
        if _int(title.get("runtime")):
            info["duration"] = "%d min" % _int(title.get("runtime"))
        genres = ", ".join(_str(g.get("display_name") or g.get("name")) for g in (title.get("genres") or []) if isinstance(g, dict))
        if genres:
            info["genres"] = genres
        if title.get("original_title") and title.get("original_title") != title.get("name"):
            info["original_title"] = _str(title.get("original_title"))
        if _str(title.get("rating")) not in ("", "0", "None"):
            info["rating"] = _str(title.get("rating"))
        credits = data.get("credits") or {}
        for key, group in (("director", "directing"), ("creator", "creators"), ("actors", "actors")):
            names = [_str(p.get("name")) for p in (credits.get(group) or [])[:6] if isinstance(p, dict) and p.get("name")]
            if names:
                info[key] = ", ".join(names)
        meta = {}
        mediaType = cItem.get("meta_type", "")
        try:
            if title.get("imdb_id"):
                meta = getMetaByImdbId(mediaType, _str(title.get("imdb_id")))
            if not meta and mediaType and cItem.get("meta_title"):
                meta = getMeta(mediaType, cItem["meta_title"], year)
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        story = _str(title.get("description")).strip()
        plot = meta.get("plot", "")
        text = story or plot or _stripColors(cItem.get("desc", ""))
        if cItem.get("s_episode") and cItem.get("desc"):
            text = "%s[/br][/br]%s" % (_stripColors(cItem["desc"]), text)
        icon = _str(title.get("poster")) or meta.get("poster") or cItem.get("icon", "")
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
        printDBG("FilmyOnline.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "fo_genres":
            self.listGenres(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "fo_series":
            self.listSeries(self.currItem)
        elif category == "fo_season":
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
        CHostBase.__init__(self, FilmyOnline(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("filmyonline")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("fo_video", "fo_series", "fo_season")
