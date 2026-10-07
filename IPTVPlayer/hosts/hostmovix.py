# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 host standard
#   - movix.zip (French movies and series): movies, series, trending, top IMDb, genres, search
#   - First page / Jump / Next page on every list and the search (?page=N; the site shows no last page)
#   - movies are VIDEO rows keyed on their page url; series -> seasons -> episodes (one episode page
#     per season lists that season's episodes)
#   - links: the page's "const videos" list (server / version / quality in the name) -> urlparser
#     (kokoflix / kakaflix / trakx redirect followed on play), plus the YouTube trailer of a movie
#   - watched flag, downloaded flag, favourites, name normalisation ("Title (Year)", "Show - SxxExx"),
#     sidecar, INFO via moviemeta + the site's fields
###################################################
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://movix.zip/"


TILE_SPLIT = '<div class="relative group overflow-hidden">'
TILE_URL_RE = re.compile(r'<a href="([^"]+/(movie|tv-show)/[^"/]+)"')
SEASON_RE = re.compile(r"(?s)posterUrl:\s*'([^']*)'.{0,400}?>\s*Saison\s+(\d+)\s*</button>")
# series page: <a ...><img ...></a><div ...><h3>name</h3>; episode page: <a ...><div>Épisode #3</div><div>name</div></a>
EPISODE_RE = re.compile(r'(?s)<a href="([^"]+/episode/[^"/]+/(\d+)-(\d+))"[^>]*>(.*?)</a>(?:\s*(?:<!--[^>]*>\s*)*<div[^>]*>\s*<h3[^>]*>(.*?)</h3>)?')
# link shorteners of the site: one 302 / 303 to the hoster
REDIRECTORS = ("kokoflix.", "kakaflix.", "trakx.")
VIDEO_CATEGORIES = ("mvx_video",)
FOLDER_CATEGORIES = ("mvx_series", "mvx_season")
GENRE_LINK_RE = re.compile(r'<a href="(https?://[^"]+)"[^>]*>')
LINK_GAP_RE = re.compile(r"</a>\s*<a[^>]*>")


def _genreLinks(data):
    # [(url, inner html)] of the absolute ".../genre/..." links, up to their first "</a>"; the rows of
    # re.findall(r'(?s)<a href="(https?://[^"]+/genre/[^"]+)"[^>]*>(.*?)</a>') with the url test done in Python
    rows, pos = [], 0
    while True:
        match = GENRE_LINK_RE.search(data, pos)
        if not match:
            return rows
        end = data.find("</a>", match.end())
        if end < 0:
            return rows
        url = match.group(1)
        path = url.split("://", 1)[1]
        genre = path.find("/genre/", 1)
        if 0 < genre and genre + 7 < len(path):
            rows.append((url, data[match.end():end]))
            pos = end + 4
        else:
            pos = match.start() + 1


def _joinLinks(value):
    # "A </a> <a ...> B" -> "A, B", like re.sub(r"\s*</a>\s*<a[^>]*>\s*", ", ", value)
    parts = LINK_GAP_RE.split(value)
    for idx in range(len(parts)):
        if idx:
            parts[idx] = parts[idx].lstrip()
        if idx < len(parts) - 1:
            parts[idx] = parts[idx].rstrip()
    return ", ".join(parts)


class Movix(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "series_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "movix", "cookie": "movix.cookie"})
        self.MAIN_URL = gettytul()
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.MENU = [
            {"category": "mvx_list", "title": _("Movies"), "url": self.getFullUrl("movies")},
            {"category": "mvx_list", "title": _("Series"), "url": self.getFullUrl("tv-shows")},
            {"category": "mvx_list", "title": _("Trending"), "url": self.getFullUrl("trending")},
            {"category": "mvx_list", "title": _("Top IMDb"), "url": self.getFullUrl("top-imdb")},
            {"category": "mvx_genres", "title": _("Genres")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("movix")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", url or "").split("#")[0].rstrip("/")

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("mvx_list",):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
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
            if category == "mvx_series":
                return "series:%s" % path
            if category == "mvx_season":
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
        for url, inner in _genreLinks(data):
            # the genre cards: name, then "1957 film & ..." below it
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r">\s*([^<\s][^<]*?)\s*<")[0] or inner)
            if not label or url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "category": "mvx_list", "title": label, "url": url, "good_for_fav": True})

    def _addTiles(self, data):
        normalize = IsMediaNamingNormalized()
        start = data.find("wire:loading.remove")
        content = data[start:] if start > -1 else data
        end = content.find("Pagination Navigation")
        content = content[:end] if end > -1 else content
        seen = set()
        for block in content.split(TILE_SPLIT)[1:]:
            match = TILE_URL_RE.search(block)
            if not match:
                continue
            url, kind = self.getFullUrl(match.group(1)), match.group(2)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<h3[^>]*>(.*?)</h3>')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<img[^>]+alt="([^"]+)"')[0])
            if not title or url in seen:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(block, r'data-src="([^"]+)"')[0]
            year = self.cm.ph.getSearchGroups(block, r"<span>((?:19|20)\d{2})</span>")[0]
            duration = self.cm.ph.getSearchGroups(block, r"<span>(\d+\s*min)</span>")[0]
            version = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<span class="bg-red-[^"]*">(.*?)</span>')[0])
            rating = self.cm.ph.getSearchGroups(block, r'<span class="text-xs">([\d.]+)</span>')[0]
            genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)</h3>\s*<div[^>]*>(?:\s*<!--[^>]*>)*\s*<span>([^<]+)</span>')[0])
            desc = " | ".join("%s: %s" % (label, value) for label, value in
                              ((_("Year"), year), (_("Duration"), duration), (_("Version"), version), (_("Rating"), rating), (_("Genre"), genre)) if value)
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc, "meta_title": title, "meta_year": year}
            if kind == "movie":
                params.update({"category": "mvx_video", "meta_type": "movie", "title": "%s (%s)" % (title, year) if year and normalize else title})
                self.addVideo(params)
            else:
                params.update({"category": "mvx_series", "meta_type": "tv", "title": title, "s_title": title})
                self.addDir(params)
        return len(seen)

    def _listPage(self, cItem, baseUrl):
        page = cItem.get("page", 1)
        url = baseUrl if page <= 1 else "%s?page=%d" % (baseUrl, page)
        printDBG("Movix.listPage [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        count = self._addTiles(data)
        hasNext = bool(count) and "nextPage('page')" in data
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        addPagingItems(self, listItem, page, hasNext, 0, baseUrl.replace("{", "{{").replace("}", "}}") + "?page={page}")

    def listItems(self, cItem):
        self._listPage(cItem, cItem.get("base_url") or cItem["url"])

    def listSearchResult(self, cItem, searchPattern, searchType):
        baseUrl = cItem.get("base_url") or self.getFullUrl("search/%s" % urllib_quote(searchPattern.strip()))
        self._listPage(dict(cItem, category="search_next_page"), baseUrl)

    def listSeasons(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        # the episode urls use their own slug ("/tv-show/outside" -> "/episode/outside-2/1-1")
        slug = self.cm.ph.getSearchGroups(data, r'/episode/([^"/]+)/\d+-\d+"')[0] or cItem["url"].rstrip("/").split("/")[-1]
        seasons = {}
        for icon, season in SEASON_RE.findall(data):
            seasons.setdefault(int(season), icon)
        if len(seasons) < 2:
            # the series page lists the episodes of its (only / last) season
            params = dict(cItem, series_url=cItem["url"])
            if seasons:
                params["s_season"] = next(iter(seasons))
            self.listEpisodes(params, data)
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        for season in sorted(seasons):
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "mvx_season", "good_for_fav": True, "s_title": show, "s_season": season, "series_url": cItem["url"],
                           "url": self.getFullUrl("episode/%s/%d-1" % (slug, season)), "title": "%s %d" % (_("Season"), season),
                           "icon": seasons[season] or cItem.get("icon", "")})
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        wanted = cItem.get("s_season")
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title") or cItem.get("title", "")
        episodes, seen = [], set()
        for url, season, episode, inner, name in EPISODE_RE.findall(data):
            season, episode = int(season), int(episode)
            if (wanted and season != wanted) or (season, episode) in seen:
                continue
            seen.add((season, episode))
            if not name:
                divs = [self.cleanHtmlStr(x) for x in re.findall(r"(?s)<div[^>]*>(.*?)</div>", inner)]
                name = divs[-1] if len(divs) > 1 else ""
            episodes.append((season, episode, self.getFullUrl(url), self.cleanHtmlStr(name)))
        for season, episode, url, name in sorted(episodes):
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = " - ".join(x for x in (show, "%s %d - %s %d" % (_("Season"), season, _("Episode"), episode), name) if x)
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "mvx_video", "good_for_fav": True, "title": title, "url": url,
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv"})
            self.addVideo(params)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of a movie / series / episode page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<p class="text-gray-400 mt-3">(.*?)</p>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        info = {}
        head = self.cm.ph.getDataBeetwenMarkers(data, "<h1", "wire:snapshot", False)[1]
        info["duration"] = self.cm.ph.getSearchGroups(head, r"<span>(\d+\s*min)</span>")[0]
        info["year"] = self.cm.ph.getSearchGroups(head, r"<span>((?:19|20)\d{2})</span>")[0]
        info["rating"] = self.cm.ph.getSearchGroups(head, r'<span class="[^"]*">([\d.]+)</span>')[0]
        block = self.cm.ph.getDataBeetwenMarkers(data, '<p class="text-gray-400 mt-3">', "/tag/", False)[1]
        for key, label in (("country", "Pays"), ("genres", "Genre"), ("released", "Sorti")):
            value = self.cm.ph.getSearchGroups(block, r"(?s)>\s*%s\s*</div>\s*<div[^>]*>(.*?)</div>" % label)[0]
            info[key] = self.cleanHtmlStr(_joinLinks(value))
        return story, poster, {k: v for k, v in info.items() if v}

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("Movix.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            return []
        urltab, seen = [], set()
        try:
            videos = json_loads(self.cm.ph.getSearchGroups(data, r"const\s+videos\s*=\s*(\[.*?\]);")[0] or "[]")
        except Exception:
            printExc()
            videos = []
        for video in videos:
            playerUrl = video.get("link", "")
            if playerUrl in seen or not self.cm.isValidUrl(playerUrl):
                continue
            seen.add(playerUrl)
            label = " / ".join(x for x in (video.get("version", ""), video.get("label", "")) if x)
            host = self.up.getHostName(playerUrl)
            name = "%s [%s]" % (host, label) if label else host
            same = len([x for x in urltab if x["name"] == name or x["name"].startswith(name + " #")])
            if same:
                name = "%s #%d" % (name, same + 1)
            urltab.append({"name": name, "url": strwithmeta(playerUrl, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        trailer = self.cm.ph.getSearchGroups(data, r"""iframeSrc\s*=\s*['"](https?://[^'"]+)['"]""")[0]
        if trailer:
            urltab.append({"name": _("Trailer"), "url": trailer, "need_resolve": 1})
        story = self._siteInfo(data)[0]
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("Movix.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if any(x in videoUrl for x in REDIRECTORS):
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
        printDBG("Movix.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        # seasons and episodes: the series page carries the story and the fields
        url = cItem.get("series_url") or cItem.get("url", "")
        sts, data = self.getPage(url)
        if sts:
            story, poster, info = self._siteInfo(data)
        mediaType = cItem.get("meta_type") or ("tv" if "/tv-show/" in url else "movie")
        metaTitle = cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", "")
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
        icon = meta.get("poster") or poster or cItem.get("icon", "")
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
        printDBG("Movix.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "mvx_genres":
            self.listGenres(self.currItem)
        elif category == "mvx_list":
            self.listItems(self.currItem)
        elif category == "mvx_series":
            self.listSeasons(self.currItem)
        elif category == "mvx_season":
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
        CHostBase.__init__(self, Movix(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("movix")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in FOLDER_CATEGORIES
