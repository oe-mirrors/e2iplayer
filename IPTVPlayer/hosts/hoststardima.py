# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - rewrite for the new stardima.com (Laravel site, the old
#   stardima.vip WordPress/DooPlay site redirects there):
#   lists are JSON (/aflam, /mosalsalat, /search?query=, /search/<category> with
#   X-Requested-With; First page / Jump / Next page), series seasons/episodes via /series/season/<id> and
#   /series/episode/<id>, the player is a v2.hyperwatching.com embed whose servers
#   (Uqload, Lulustream, Savefiles, Mixdrop, StreamHG) are read from its Inertia page
#   + watched flag / downloaded flag / name normalisation / sidecar / moviemeta INFO /
#   favourites.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
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
    return "https://www.stardima.com/"


# episode page: /tvshow/<series slug>/play/<episode id>
EPISODE_RE = re.compile(r'^(https?://[^/]+/tvshow/[^/?#]+)/play/(\d+)')
MOVIE_RE = re.compile(r'^https?://[^/]+/movie/([^/?#]+)')
PLAYER_URL = "https://v2.hyperwatching.com/"
# site labels (dubbed / subtitled): parsed from the site's season and title labels
LABEL_DUB = "مدبلج"
LABEL_SUB = "مترجم"


def _unescapeAttr(text):
    # Laravel e() only produces these entities
    return text.replace("&quot;", '"').replace("&#039;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def _searchAll(data, pattern):
    # first group of a multi-line match
    match = re.search(pattern, data or "", re.DOTALL)
    return match.group(1) if match else ""


class Stardima(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "season", "season_id", "season_label", "episode",
                  "episode_id", "series_url", "icon", "desc", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "stardima", "cookie": "stardima.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/plain, */*"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://stardima.com/storage/branding/mvH3ZNfqfrmbAy03MftbtcJ7vaVENPnX1PtLWGvF.png"
        movies = _("Movies")
        series = _("Series")
        self.MENU = [{"category": "list_items", "title": movies, "url": self.getFullUrl("aflam")},
                     {"category": "list_items", "title": "%s - %s" % (movies, _("Dubbed")), "url": self.getFullUrl("aflam?language=dub")},
                     {"category": "list_items", "title": "%s - %s" % (movies, _("With subtitles")), "url": self.getFullUrl("aflam?language=sub")},
                     {"category": "list_items", "title": series, "url": self.getFullUrl("mosalsalat")},
                     {"category": "list_items", "title": "%s - %s" % (series, _("Dubbed")), "url": self.getFullUrl("mosalsalat?language=dub")},
                     {"category": "list_items", "title": "%s - %s" % (series, _("With subtitles")), "url": self.getFullUrl("mosalsalat?language=sub")},
                     {"category": "list_latest", "title": _("Newest Episodes"), "url": self.getFullUrl("newrelases")},
                     {"category": "list_cats", "title": _("Categories"), "url": self.getFullUrl("aflam")}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("stardima")
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
            if category == "st_series":
                return "series:%s" % url if url else ""
            if category == "st_season":
                seasonId = str(cItem.get("season_id", "") or "").strip()
                return "season:%s" % seasonId if seasonId else ""
            return ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # http
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _getJson(self, url, referer=None):
        params = dict(self.defaultParams)
        params["header"] = dict(self.AJAX_HEADER)
        params["header"]["Referer"] = referer or self.MAIN_URL
        sts, data = self.getPage(url, params)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printDBG("Stardima._getJson no JSON from %s" % url)
        return None

    ###################################################
    # helpers
    ###################################################
    def _posterUrl(self, url):
        url = (url or "").strip()
        if not url or "placehold.co" in url:
            return ""
        if not url.startswith("http") and not url.startswith("/"):
            url = "/storage/" + url
        return self.getFullIconUrl(url)

    @staticmethod
    def _cleanMetaTitle(title):
        # "Title (مدبلج)" / "Title - مترجم" -> "Title" for the metadata services
        title = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]\s*$', '', title or "")
        title = re.sub(r'\s*-\s*(?:%s|%s)[^-]*$' % (LABEL_DUB, LABEL_SUB), '', title)
        return title.strip()

    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year:
            return "%s (%s)" % (title, year)
        return title

    def _episodeTitle(self, sTitle, season, episode, seasonLabel):
        # the season label may carry the audio ("1 مدبلج" / "1 مترجم"); dubbed and subbed
        # seasons can share a number, so the audio stays in the name ("[Dub]" / "[Sub]")
        extra = ""
        for label, tag in ((LABEL_DUB, "[Dub]"), (LABEL_SUB, "[Sub]")):
            if label in (seasonLabel or ""):
                extra = tag
                break
        if IsMediaNamingNormalized():
            title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            return "%s %s" % (title, extra) if extra else title
        label = seasonLabel or season
        return "%s - %s %s - %s %s" % (sTitle, _("Season"), label, _("Episode"), episode)

    @staticmethod
    def _addPage(url, page):
        return "%s%spage=%s" % (url, "&" if "?" in url else "?", page)

    ###################################################
    # lists
    ###################################################
    def _addVideoEntry(self, cItem, video):
        url = str(video.get("url", "") or "").strip()
        title = self.cleanHtmlStr(str(video.get("title", "") or ""))
        if not self.cm.isValidUrl(url) or not title:
            return False
        year = str(video.get("year", "") or "").strip()[:4]
        if not year.isdigit():
            year = ""
        quality = self.cleanHtmlStr(str(video.get("video_quality", "") or ""))
        descTxt = self.cleanHtmlStr(str(video.get("description", "") or ""))
        info = [x for x in (year, quality) if x]
        desc = " | ".join(info)
        if descTxt:
            desc = "%s\n%s" % (desc, descTxt) if desc else descTxt
        params = stripPagerKeys(dict(cItem), ("search_pattern", "base_url"))
        params.update({"good_for_fav": True, "url": url, "icon": self._posterUrl(video.get("poster_url", "")), "desc": desc,
                       "s_title": title, "meta_title": self._cleanMetaTitle(title), "meta_year": year})
        if video.get("is_series") or "/tvshow/" in url:
            params.update({"category": "st_series", "title": title, "meta_type": "tv"})
            self.addDir(params)
        else:
            params.update({"category": "st_movie", "title": self._movieTitle(title, year), "meta_type": "movie"})
            self.addVideo(params)
        return True

    def listItems(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        # the pager rows carry the url of their page ("?page=N") - the list's own url without it
        url = cItem.get("base_url") or cItem["url"]
        cItem = dict(cItem, base_url=url)
        printDBG("Stardima.listItems |%s| page %s" % (url, page))
        data = self._getJson(self._addPage(url, page))
        if not isinstance(data, dict):
            return
        cnt = 0
        seen = set()
        for video in data.get("videos", []) or []:
            if not isinstance(video, dict) or video.get("url") in seen:
                continue
            seen.add(video.get("url"))
            if self._addVideoEntry(cItem, video):
                cnt += 1
        pagination = data.get("pagination", {}) or {}
        try:
            lastPage = int(pagination.get("last_page", 1) or 1)
        except Exception:
            lastPage = 1
        addPagingItems(self, cItem, page, bool(cnt) and page < lastPage, lastPage, self._addPage(url, "{page}"))

    def listCategories(self, cItem):
        printDBG("Stardima.listCategories")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for slug, title in re.findall(r'name="category"[^>]*value="([^"]+)">\s*<label[^>]*>\s*<span[^>]*></span>([^<]+)<', data):
            title = self.cleanHtmlStr(title)
            if slug == "all" or slug in seen or not title:
                continue
            seen.add(slug)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl("search/" + slug)})
            self.addDir(params)

    def listLatest(self, cItem):
        printDBG("Stardima.listLatest")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'data-content="episodes"', 'data-content="movies"', False)[1] or data
        days = re.split(r'(<h2[^>]*>[^<]+</h2>)', data)
        day = ""
        seen = set()
        for part in days:
            if part.startswith("<h2"):
                day = self.cleanHtmlStr(part)
                continue
            for card in part.split('<img ')[1:]:
                href = self.cm.ph.getSearchGroups(card, r'href="([^"]+/play/\d+)"')[0]
                epMatch = EPISODE_RE.search(href)
                if not epMatch or href in seen:
                    continue
                seen.add(href)
                title = self.cleanHtmlStr(_searchAll(card, r'<h3[^>]*>(.*?)</h3>'))
                if not title:
                    title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'alt="Poster for ([^"]+)"')[0])
                if not title:
                    continue
                sTitle, episode = title, ""
                m = re.match(r'^(.*?)\s*-\s*حلقة\s*(\d+)\s*$', title)
                if m:
                    sTitle, episode = m.group(1).strip(), m.group(2)
                year = self.cm.ph.getSearchGroups(card, r'<span>\s*(\d{4})\s*</span>')[0]
                icon = self._posterUrl(self.cm.ph.getSearchGroups(card, r'src="([^"]+)"')[0])
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "st_episode", "title": title, "url": href, "icon": icon,
                               "desc": day, "s_title": sTitle, "episode": episode, "episode_id": epMatch.group(2),
                               "series_url": epMatch.group(1), "meta_type": "tv", "meta_title": self._cleanMetaTitle(sTitle), "meta_year": year})
                self.addVideo(params)

    def _getSeasons(self, cItem):
        # the series page only links its first episode; the episode page has the season picker
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        playUrl = self.cm.ph.getSearchGroups(data, r'href="([^"]+/tvshow/[^"/]+/play/\d+)"')[0]
        if not playUrl:
            return []
        sts, data = self.getPage(playUrl)
        if not sts:
            return []
        seasons = []
        for seasonId, label in re.findall(r'data-season-id="(\d+)"\s+data-season-number="([^"]*)"', data):
            if seasonId not in [s[0] for s in seasons]:
                seasons.append((seasonId, self.cleanHtmlStr(label)))
        if not seasons:
            seasonId = self.cm.ph.getSearchGroups(data, r'data-initial-season-id="(\d+)"')[0]
            if seasonId:
                seasons.append((seasonId, "1"))
        return seasons

    def listSeasons(self, cItem):
        printDBG("Stardima.listSeasons |%s|" % cItem["url"])
        seasons = self._getSeasons(cItem)
        sTitle = cItem.get("s_title", cItem["title"])
        items = []
        for idx, (seasonId, label) in enumerate(seasons):
            # "1 مدبلج", "Mechasia Start S01", "الأول" (no number: position in the picker)
            num = self.cm.ph.getSearchGroups(label, r'(?:^|\s|S)(\d{1,2})(?:\s|$)')[0] or str(idx + 1)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "st_season", "title": "%s - %s %s" % (sTitle, _("Season"), label or num),
                           "s_title": sTitle, "season": num, "season_id": seasonId, "season_label": label, "series_url": cItem["url"]})
            items.append(params)
        if len(items) == 1:
            # one season: show its episodes right away
            self.listEpisodes(items[0])
            return
        for params in items:
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Stardima.listEpisodes season_id %s" % cItem.get("season_id", ""))
        seriesUrl = cItem.get("series_url", cItem["url"]).rstrip("/")
        data = self._getJson(self.getFullUrl("series/season/%s" % cItem["season_id"]), seriesUrl)
        if not isinstance(data, dict):
            return
        sTitle = cItem.get("s_title", cItem["title"])
        seen = set()
        for ep in data.get("episodes", []) or []:
            if not isinstance(ep, dict):
                continue
            epId = str(ep.get("id", "") or "")
            if not epId.isdigit() or epId in seen:
                continue
            seen.add(epId)
            episode = str(ep.get("episode_number", "") or "") or str(len(seen))
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "st_episode", "url": "%s/play/%s" % (seriesUrl, epId),
                           "title": self._episodeTitle(sTitle, cItem.get("season", "1"), episode, cItem.get("season_label", "")),
                           "s_title": sTitle, "episode": episode, "episode_id": epId, "series_url": seriesUrl})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Stardima.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("search?query=%s" % urllib_quote_plus(searchPattern)), "page": 1})
        self.listItems(cItem)

    ###################################################
    # title page
    ###################################################
    def _parseTitlePage(self, data):
        info = {"desc": "", "poster": "", "year": "", "rating": "", "quality": "", "genres": ""}
        hero = self.cm.ph.getDataBeetwenMarkers(data, "</header>", "<main", False)[1] or data
        info["desc"] = self.cleanHtmlStr(_searchAll(hero, r'<p[^>]*>(.*?)</p>'))
        if not info["desc"]:
            info["desc"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]+)"')[0])
        info["poster"] = self.cm.ph.getSearchGroups(hero, r"background-image:\s*url\('([^']+)'")[0]
        info["year"] = self.cm.ph.getSearchGroups(hero, r'>\s*((?:19|20)\d{2})\s*</div>')[0]
        info["rating"] = self.cm.ph.getSearchGroups(hero, r'<span class="font-bold text-white">\s*([0-9.]+)\s*</span>')[0]
        info["quality"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(hero, r'</div>\s*<span>([^<]+)</span>\s*</div>')[0])
        genres = []
        for genre in re.findall(r'href="[^"]+/search(?:/[^"]+|\?tag=[^"]+)"[^>]*>(.*?)</a>', hero, re.DOTALL):
            genre = self.cleanHtmlStr(genre)
            if genre and genre not in genres:
                genres.append(genre)
        info["genres"] = ", ".join(genres)
        return info

    ###################################################
    # links
    ###################################################
    def _hyperwatchingLinks(self, watchUrl):
        # Inertia page props: video.hashid + video.servers[]; each server's real embed url
        # comes from /embed/<hashid>/server/<id>/url
        links = []
        sts, data = self.getPage(watchUrl, dict(self.defaultParams, header=dict(self.HEADER, Referer=self.MAIN_URL)))
        if not sts:
            return links
        page = self.cm.ph.getSearchGroups(data, r'data-page="([^"]+)"')[0]
        try:
            props = json_loads(_unescapeAttr(page)).get("props", {}) if page else {}
        except Exception:
            printExc()
            props = {}
        video = props.get("video", {}) or {}
        hashId = video.get("hashid", "")
        origin = self.cm.ph.getSearchGroups(watchUrl, r'^(https?://[^/]+/)')[0] or PLAYER_URL
        for server in video.get("servers", []) or []:
            if not isinstance(server, dict) or server.get("is_vip") or not hashId:
                continue
            if server.get("status", "completed") != "completed":
                continue
            ret = self._getJson("%sembed/%s/server/%s/url" % (origin, hashId, server.get("id", "")), watchUrl)
            if not isinstance(ret, dict):
                continue
            url = str(ret.get("watch_url", "") or "").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url):
                continue
            label = self.cleanHtmlStr(str(server.get("name", "") or ""))
            hostName = self.up.getHostName(url)
            name = "%s (%s)" % (label, hostName) if label and hostName and label.lower() not in hostName else (hostName or label)
            if ret.get("player", "iframe") != "iframe" and re.search(r'\.(?:m3u8|mp4)(?:\?|$)', url):
                meta = {"Referer": origin, "Origin": origin.rstrip("/"), "User-Agent": self.HEADER.get("User-Agent")}
                headers = ret.get("headers", {})
                if isinstance(headers, dict):
                    meta.update(headers)
                links.append({"name": name, "url": strwithmeta(url, meta), "need_resolve": 0})
            else:
                links.append({"name": name, "url": strwithmeta(url, {"Referer": origin}), "need_resolve": 1})
        # hosters urlparser knows first
        links.sort(key=lambda x: 0 if not x["need_resolve"] or self.up.checkHostSupport(x["url"]) == 1 else 1)
        return links

    def getLinksForVideo(self, cItem):
        printDBG("Stardima.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = cItem.get("url", "")
        if not self.cm.isValidUrl(pageUrl):
            return []
        sidecarTxt = ""
        watchUrl = ""
        epMatch = EPISODE_RE.search(pageUrl)
        if epMatch:
            data = self._getJson(self.getFullUrl("series/episode/%s" % epMatch.group(2)), pageUrl)
            ep = data.get("episode", {}) if isinstance(data, dict) else {}
            if isinstance(ep, dict) and ep:
                if ep.get("can_watch") is False:
                    SetIPTVPlayerLastHostError(_("This video is Premium-only content."))
                    return []
                watchUrl = str(ep.get("watch_url", "") or "")
                sidecarTxt = self.cleanHtmlStr(str(ep.get("description", "") or ""))
            if not watchUrl:
                sts, data = self.getPage(pageUrl)
                if sts:
                    watchUrl = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"')[0]
        else:
            movieMatch = MOVIE_RE.search(pageUrl)
            playUrl = self.getFullUrl("play/%s" % movieMatch.group(1)) if movieMatch else pageUrl
            sts, data = self.getPage(playUrl)
            if sts:
                watchUrl = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"')[0]
        watchUrl = _unescapeAttr(watchUrl).strip()
        if watchUrl.startswith("//"):
            watchUrl = "https:" + watchUrl
        if not self.cm.isValidUrl(watchUrl):
            SetIPTVPlayerLastHostError(_("No player found for this title."))
            return []
        if "hyperwatching." in watchUrl:
            urltab = self._hyperwatchingLinks(watchUrl)
        else:
            urltab = [{"name": self.up.getHostName(watchUrl), "url": strwithmeta(watchUrl, {"Referer": self.MAIN_URL}), "need_resolve": 1}]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt or cItem.get("desc", "")))

    def getVideoLinks(self, videoUrl):
        printDBG("Stardima.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Stardima.getArticleContent [%s]" % cItem.get("url", ""))
        mediaType = cItem.get("meta_type", "")
        pageUrl = cItem.get("series_url") or cItem.get("url", "")
        info = {"desc": "", "poster": "", "year": "", "rating": "", "quality": "", "genres": ""}
        if self.cm.isValidUrl(pageUrl):
            sts, data = self.getPage(pageUrl)
            if sts:
                info = self._parseTitlePage(data)
        meta = {}
        try:
            meta = getMeta(mediaType, cItem.get("meta_title", "") or cItem.get("s_title", ""), cItem.get("meta_year", "") or info["year"])
        except Exception:
            printExc()
            meta = {}
        otherInfo = dict(meta.get("info", {}) or {})
        if info["year"]:
            otherInfo.setdefault("year", info["year"])
        if info["genres"]:
            otherInfo.setdefault("genres", info["genres"])
        if info["rating"]:
            otherInfo.setdefault("rating", info["rating"])
        if info["quality"]:
            otherInfo.setdefault("quality", info["quality"])
        # the site's own Arabic story first, the services' text when the site has none
        siteDesc = info["desc"]
        text = siteDesc or meta.get("plot", "") or cItem.get("desc", "")
        icon = cItem.get("icon", "") or meta.get("poster", "") or info["poster"]
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
        printDBG("Stardima.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_cats":
            self.listCategories(self.currItem)
        elif category == "list_latest":
            self.listLatest(self.currItem)
        elif category == "st_series":
            self.listSeasons(self.currItem)
        elif category == "st_season":
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
        CHostBase.__init__(self, Stardima(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("stardima")

    def withArticleContent(self, cItem):
        return bool(cItem.get("meta_type"))
