# -*- coding: utf-8 -*-
LAST_MODIFIED = "07.11.2026"
# HD Mozi (Hungarian films and series, WordPress / Dooplay): lists with cover, year, IMDb rating and plot, genres,
# seasons / episodes, search; links through doo_player_ajax (abyss / byse / vidhide / rpmshare players)
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://hdmozi.hu/"


SITE_URL_RE = re.compile(r"^https?://(?:www\.)?hdmozi\.[a-z]+/", re.I)
# the Dooplay labels of a title page -> INFO key
INFO_LABELS = (("original_title", "EREDETI FILM CÍM"), ("original_title", "EREDETI CÍM"), ("tmdb_rating", "TMDB ÉRTÉKELÉS"), ("imdb_rating", "IMDB ÉRTÉKELÉS"),
               ("first_air_date", "FIRST AIR DATE"), ("last_air_date", "LAST AIR DATE"), ("seasons", "SEASONS"), ("episodes", "EPISODES"))
# "A végső lista (1-2 évad)" -> "A végső lista"
SEASON_NOTE_RE = re.compile(r"\s*\([^)]*évad[^)]*\)\s*$", re.I)
LOCAL_PAGE_SIZE = 100


class HDMozi(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_year", "s_season", "s_episode", "meta_type")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "hdmozi", "cookie": "hdmozi.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/hdmozi135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("hdmozi")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._pageUrl(baseUrl), addParams, post_data)

    def _pageUrl(self, url):
        # urls of favourites on an older domain -> the current one, the #s<season> fragment dropped
        url = (url or "").replace("&amp;", "&").strip().split("#")[0]
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return SITE_URL_RE.sub(self.MAIN_URL, url)

    @staticmethod
    def _path(url):
        # domain independent identity of a page, the #s<season> fragment kept
        return re.sub(r"^https?://[^/]+", "", (url or "").split("?")[0]).rstrip("/").lower()

    @staticmethod
    def _pageUrlTpl(url):
        # https://hdmozi.hu/genre/akcio/page/{page}/ and https://hdmozi.hu/page/{page}/?s=..
        base, query = (url.split("?", 1) + [""])[:2]
        base = re.sub(r"/page/\d+/?$", "/", base).rstrip("/").replace("{", "{{").replace("}", "}}")
        query = query.replace("{", "{{").replace("}", "}}")
        return base + "/page/{page}/" + ("?" + query if query else "")

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            return 1

    def getFavouriteData(self, cItem):
        try:
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
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            if cItem.get("type", "") == "video":
                return "video:%s" % path
            prefix = {"list_seasons": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
            return "%s:%s" % (prefix, path) if prefix else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _addCard(self, cItem, block, itemUrl, normalize):
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r"(?s)<h3>\s*<a[^>]*>(.*?)</a>")[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="title">\s*<a[^>]*>(.*?)</a>')[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'alt="([^"]+)"')[0])
        if not title:
            return
        title = SEASON_NOTE_RE.sub("", title)
        icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0]
        year = self.cm.ph.getSearchGroups(block, r'class="year">((?:19|20)\d\d)<')[0] or self.cm.ph.getSearchGroups(block, r'<span>[^<]*((?:19|20)\d\d)</span>')[0] or self.cm.ph.getSearchGroups(block, r'class="metadata">.*?<span>((?:19|20)\d\d)</span>')[0]
        rating = self.cm.ph.getSearchGroups(block, r'class="rating">\s*([\d.]+)\s*<')[0] or self.cm.ph.getSearchGroups(block, r'class="imdb">IMDb:\s*([\d.]+)')[0]
        duration = self.cm.ph.getSearchGroups(block, r"<span>(\d+ min)</span>")[0]
        genreBlock = self.cm.ph.getSearchGroups(block, r'(?s)<div class="mta">(.*?)</div>')[0]
        genres = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r">([^<]+)</a>", genreBlock))
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="(?:texto|contenido)">(.*?)</div>')[0])
        rows = [(_("Year"), year), (_("Rating"), "IMDb %s" % rating if rating else ""), (_("Duration"), duration), (_("Genres"), genres)]
        desc = " | ".join("%s: %s" % (label, value) for label, value in rows if value)
        if plot:
            desc = "%s[/br]%s" % (desc, plot) if desc else plot
        params = stripPagerKeys(dict(cItem))
        params.update({"name": "category", "good_for_fav": True, "url": itemUrl, "icon": self.getFullIconUrl(icon) if icon else "", "desc": desc, "s_title": title, "s_year": year})
        if "/tvshows/" in itemUrl:
            params.update({"category": "list_seasons", "meta_type": "tv", "title": title})
            self.addDir(params)
        else:
            params.update({"category": "hdm_video", "meta_type": "movie", "title": "%s (%s)" % (title, year) if (normalize and year) else title})
            self.addVideo(params)

    def listItems(self, cItem):
        printDBG("HDMozi.listItems [%s]" % cItem.get("url", ""))
        page = self._page(cItem)
        url = self._pageUrl(cItem.get("url", ""))
        pageUrlTpl = self._pageUrlTpl(url)
        sts, data = self.getPage(pageUrlTpl.format(page=page) if page > 1 else url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        # genre / movies / tvshows lists: <article class="item movies">; search: <div class="result-item">
        for block in re.split(r'<article[^>]*class="item [^"]*"|<div class="result-item">', data)[1:]:
            itemUrl = self.cm.ph.getSearchGroups(block, r'href="(https?://[^"]+/(?:movies|tvshows)/[^"]+)"')[0]
            if not itemUrl or itemUrl in seen:
                continue
            seen.add(itemUrl)
            self._addCard(cItem, block, itemUrl, normalize)
        if not seen:
            self.addMarker({"title": _("No items found"), "desc": ""})
            return
        listBase = re.sub(r"/page/\d+/?$", "", url.split("?", 1)[0].rstrip("/"))
        pages = [int(n) for n in re.findall(r'href="%s/page/(\d+)/' % re.escape(listBase), data)]
        hasNext = 'class="next page-numbers"' in data or 'rel="next"' in data or 'id="nextpagination"' in data
        addPagingItems(self, dict(cItem, category="list_items", url=cItem.get("url", "")), page, hasNext, max(pages + [page]) if hasNext else page, pageUrlTpl)

    def listGenres(self, cItem):
        printDBG("HDMozi.listGenres")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        seen = set()
        for url, name in re.findall(r'href="(https?://[^"]+/genre/[^"]+/)"[^>]*>([^<]+)</a>', data):
            name = self.cleanHtmlStr(name)
            if url in seen or not name or name.isupper():
                # the header menu repeats a few genres in capitals (PREMIER, NÉPSZERŰ ...)
                continue
            seen.add(url)
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "good_for_fav": True, "category": "list_items", "title": name, "url": url})
            self.addDir(params)
        self.currList.sort(key=lambda x: x["title"].lower())

    def _seasonBlocks(self, data):
        # [(season, [(episode, url, name, icon)])] in page order
        seasons = []
        for block in data.split("<div class='se-c'>")[1:]:
            season = self.cm.ph.getSearchGroups(block, r"<span class='se-t[^']*'>(\d+)<")[0]
            if not season:
                continue
            episodes = []
            for li in block.split("<li class='mark-")[1:]:
                url = self.cm.ph.getSearchGroups(li, r"href='([^']+)'")[0]
                num = self.cm.ph.getSearchGroups(li, r"class='numerando'>\s*\d+\s*-\s*(\d+)")[0]
                if not url or not num:
                    continue
                name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(li, r"href='[^']+'>([^<]*)</a>")[0])
                icon = self.cm.ph.getSearchGroups(li, r"<img[^>]+src='([^']+)'")[0]
                episodes.append((num, url, name, icon))
            if episodes:
                seasons.append((season, episodes))
        return seasons

    def listSeasons(self, cItem):
        printDBG("HDMozi.listSeasons [%s]" % cItem.get("url", ""))
        url = self._pageUrl(cItem.get("url", ""))
        sts, data = self.getPage(url)
        if not sts:
            return
        _info, plot, year = self._siteInfo(data)
        show = SEASON_NOTE_RE.sub("", cItem.get("s_title", "") or self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<h1[^>]*>([^<]+)<")[0]) or cItem.get("title", ""))
        seasons = self._seasonBlocks(data)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        fields = {"s_title": show, "s_year": year or cItem.get("s_year", ""), "meta_type": "tv"}
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, category="list_episodes", s_season=seasons[0][0], url="%s#s%s" % (url, seasons[0][0]), **fields), seasons)
            return
        normalize = IsMediaNamingNormalized()
        for season, episodes in seasons:
            params = stripPagerKeys(dict(cItem))
            params.update(fields)
            params.update({"name": "category", "good_for_fav": True, "category": "list_episodes", "s_season": season, "url": "%s#s%s" % (url, season),
                           "title": "%s - %s" % (show, formatSxxExx(season)) if normalize else "%s - %s %s" % (show, _("Season"), season),
                           "desc": "%s: %d[/br]%s" % (_("Episodes"), len(episodes), plot)})
            self.addDir(params)

    def listEpisodes(self, cItem, seasons=None):
        printDBG("HDMozi.listEpisodes [%s]" % cItem.get("url", ""))
        url = self._pageUrl(cItem.get("url", ""))
        season = str(cItem.get("s_season", "") or self.cm.ph.getSearchGroups(cItem.get("url", ""), r"#s(\d+)")[0])
        if seasons is None:
            sts, data = self.getPage(url)
            if not sts:
                return
            seasons = self._seasonBlocks(data)
            if not cItem.get("s_title"):
                cItem = dict(cItem, s_title=SEASON_NOTE_RE.sub("", self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<h1[^>]*>([^<]+)<")[0])))
        episodes = dict(seasons).get(season, [])
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        show = cItem.get("s_title", "") or cItem.get("title", "")
        normalize = IsMediaNamingNormalized()
        page = self._page(cItem)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for episode, epUrl, name, icon in episodes[start:start + LOCAL_PAGE_SIZE]:
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = "%s - %s %s - %s %s" % (show, _("Season"), season, _("Episode"), episode)
                if name and not re.match(r"^\d+\.?\s*epiz", name, re.I):
                    title += " - " + name
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "good_for_fav": True, "category": "hdm_video", "title": title, "url": epUrl, "s_title": show, "s_season": season,
                           "s_episode": episode, "meta_type": "tv", "icon": self.getFullIconUrl(icon) if icon else cItem.get("icon", ""), "desc": name})
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem, category="list_episodes"), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HDMozi.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "page": 1, "url": self.getFullUrl("?s=%s" % urllib_quote_plus(searchPattern.strip()))})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = self._pageUrl(cItem.get("url", ""))
        printDBG("HDMozi.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return []
        info, plot, siteYear = self._siteInfo(data)
        urltab = []
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=url, Origin=self.MAIN_URL.rstrip("/"), Accept="*/*")
        params["header"]["X-Requested-With"] = "XMLHttpRequest"
        for dtype, post, nume in re.findall(r"data-type='([^']+)'\s*data-post='(\d+)'\s*data-nume='(\d+)'", data):
            sts, answer = self.getPage(self.getFullUrl("wp-admin/admin-ajax.php"), dict(params), {"action": "doo_player_ajax", "post": post, "nume": nume, "type": dtype})
            if not sts:
                continue
            link = self.cm.ph.getSearchGroups(answer, r'"embed_url"\s*:\s*"([^"]+)"')[0].replace("\\/", "/")
            if link.startswith("//"):
                link = "https:" + link
            if not self.cm.isValidUrl(link) or "youtube." in link or link in [str(x["url"]) for x in urltab]:
                continue
            if self.up.checkHostSupport(link) != 1:
                printDBG("HDMozi: unsupported link skipped [%s]" % link)
                continue
            # "Abyssplayer [1]" instead of "Player.abyssplayer.com [1]"
            urltab.append({"name": "%s [%s]" % (self.up.getHostName(link, True).capitalize(), nume), "url": strwithmeta(link, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        mediaType = cItem.get("meta_type", "") or ("movie" if "/movies/" in url else "tv")
        title = cItem.get("s_title", "") or cItem.get("title", "")
        metaQuery = sidecarMetaQuery(mediaType, info.get("original_title", "") or title, cItem.get("s_year", "") or siteYear, skip=(), maxYearDiff=1)
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), plot, metaQuery=metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("HDMozi.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # -> (info, plot, year) of a film / series / episode page
        info = {}
        for label, value in re.findall(r'(?s)<b class="variante">([^<]+)</b>\s*<span class="valor">(.*?)</span>', data):
            label, value = self.cleanHtmlStr(label).upper(), self.cleanHtmlStr(value)
            for key, name in INFO_LABELS:
                if label.startswith(name) and value:
                    info[key] = value.split(" ")[0] if key.endswith("_rating") else value
                    break
        genres = self.cm.ph.getDataBeetwenMarkers(data, '<div class="sgeneros">', "</div>", False)[1]
        genres = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r">([^<]+)</a>", genres))
        if genres:
            info["genres"] = genres
        cast = []
        for name in re.findall(r'itemprop="actor"[^>]*>.*?itemprop="name" content="([^"]+)"', data[:300000], re.S)[:6]:
            if name not in cast:
                cast.append(name)
        if cast:
            info["cast"] = ", ".join(cast)
        directors = []
        for name in re.findall(r'itemprop="director"[^>]*>.*?itemprop="name" content="([^"]+)"', data[:300000], re.S)[:3]:
            if name not in directors:
                directors.append(name)
        if directors:
            # the moviemeta key: one "Directors" row (moviemeta's list wins in getArticleContent)
            info["directors"] = ", ".join(directors)
        released = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<span class=.date. itemprop=.dateCreated.>([^<]+)<")[0])
        year = self.cm.ph.getSearchGroups(released, r"((?:19|20)\d\d)")[0]
        if released:
            info["released"] = released
        if year:
            info["year"] = year
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'class="runtime">([^<]+)<')[0])
        if duration:
            info["duration"] = duration
        plot = self.cm.ph.getSearchGroups(data, r'(?s)class="wp-content[^"]*"[^>]*>(.*?)<div')[0]
        plot = self.cleanHtmlStr(re.sub(r"(?s)<h\d[^>]*>.*?</h\d>", "", plot))
        return info, plot, year

    def getArticleContent(self, cItem):
        printDBG("HDMozi.getArticleContent [%s]" % cItem.get("url", ""))
        info, plot, year = {}, "", cItem.get("s_year", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot, siteYear = self._siteInfo(data)
            year = year or siteYear
        mediaType = cItem.get("meta_type", "") or ("movie" if "/movies/" in cItem.get("url", "") else "tv")
        title = cItem.get("s_title", "") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(mediaType, info.get("original_title", "") or title, year, maxYearDiff=1)
        except Exception:
            printExc()
        for key, value in meta.get("info", {}).items():
            # the site names only the first director of a film, moviemeta all of them
            if key == "directors" and value:
                info[key] = value
            else:
                info.setdefault(key, value)
        metaPlot = meta.get("plot", "")
        text = plot or cItem.get("desc", "")
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("HDMozi.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            menu = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies/")},
                    {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("tvshows/")},
                    {"category": "list_items", "title": _("Top rated"), "url": self.getFullUrl("ertekelesek/")},
                    {"category": "list_items", "title": _("Most viewed"), "url": self.getFullUrl("felkapott-nezettseg/")},
                    {"category": "list_genres", "title": _("Genres")}]
            self.listsTab(menu + self.searchItems(), {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
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
        CHostBase.__init__(self, HDMozi(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("hdmozi")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
