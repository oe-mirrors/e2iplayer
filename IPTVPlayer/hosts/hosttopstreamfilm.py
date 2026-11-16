# -*- coding: utf-8 -*-
LAST_MODIFIED = "16.11.2026"
# 14.06.2026 - Mr.X
# 16.11.2026 - the site moved to a new platform (shared with streamcloud.date): new lists/paging/search, menus
# from the site's links, series IMDb id from the page data, INFO from its ld+json. Player still devideosrc.co.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.meinecloud import MeineCloud, MOVIE_IFRAME_RE, isPlayerUrl
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
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
    return "https://topstreamfilm.best/"


PAGING_KEYS = ("base_url", "page_tpl")
# the IMDb id of a series page sits in the (escaped) Next.js data: \"imdb\":\"tt0096697\"
SERIES_IMDB_RE = r'\\?"imdb\\?"\s*:\s*\\?"(tt\d+)'
LD_JSON_RE = r'<script type="application/ld\+json">(\{"@context":"https://schema.org","@type":"(?:Movie|TVSeries)".*?\})</script>'
# list_value favourites from before 16.11.2026 carry the old menu markers
OLD_VALUE_KEYS = {">KATEGORIEN<": "/genre/", ">YAHRE<": "/jahr/", ">LAND<": "/land/"}


def _pageUrl(url):
    # episode rows: the series page + "#s<season>e<episode>"; favourites from before 27.09.2026 may carry a list
    return "" if (not url or isinstance(url, list)) else url.split("#")[0]


def _stripPage(url):
    return re.sub(r"([?&])page=\d+&?", r"\1", url or "").rstrip("?&")


class TopStreamFilm(GenericFolderWatchedScraperMixin, CBaseHostClass):
    USE_CF_PROTECTION = True

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "TopStreamFilm", "cookie": "TopStreamFilm.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "brand/topstream/apple-touch.png"
        self.MAIN_URL = "https://topstreamfilm.best"
        self.MENU = [{"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("/kinofilme")},
                     {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/filme-online-sehen")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/serien")},
                     {"category": "list_items", "title": _("Popular"), "url": self.getFullUrl("/im-gespraech")},
                     {"category": "list_value", "title": _("Genres"), "s": "/genre/"},
                     {"category": "list_value", "title": _("Year"), "s": "/jahr/"},
                     {"category": "list_value", "title": _("Country"), "s": "/land/"}] + self.searchItems()
        self.cacheSeasons = {}
        self.watchedHelper = IPTVWatchedHelper("topstreamfilm")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = _pageUrl(cItem.get("url", ""))
            if not url:
                return ""
            category = cItem.get("category", "")
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % cItem["url"]
            if category == "list_seasons":
                return "series:%s" % url
            if category == "list_episodes":
                return "season:%s#s%s" % (url, cItem.get("mc_season", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _ld(self, data):
        # the schema.org Movie / TVSeries block of a title page
        raw = self.cm.ph.getSearchGroups(data or "", LD_JSON_RE)[0]
        try:
            ld = json_loads(raw) if raw else {}
        except Exception:
            printDBG("TopStreamFilm: broken ld+json")
            ld = {}
        return ld if isinstance(ld, dict) else {}

    def _ldInfo(self, ld):
        info = {}
        released = ensure_str(ld.get("datePublished") or "")[:10]
        if released:
            info["released"] = released
        rating = ld.get("aggregateRating")
        rating = rating.get("ratingValue") if isinstance(rating, dict) else ""
        try:
            if rating and float(rating) > 0:
                # the site's ratings are TMDB ones
                info["tmdb_rating"] = "%.1f/10" % float(rating)
        except (TypeError, ValueError):
            pass
        return info

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("TopStreamFilm.listItems |%s|" % cItem)
        page = int(cItem.get("page", 1) or 1)
        baseUrl = _stripPage(cItem.get("base_url") or cItem["url"])
        tpl = cItem.get("page_tpl", "") or (baseUrl.replace("{", "{{").replace("}", "}}") + ("&" if "?" in baseUrl else "?") + "page={page}")
        sts, data = self.getPage(baseUrl if page <= 1 else tpl.format(page=page))
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        count = 0
        seen = set()
        for item in data.split('<a class="cv" ')[1:]:
            item = item.split("</a>", 1)[0]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="cv-t">([^<]+)')[0] or self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            if not title or not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)')[0])
            meta = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="cv-m">(.*?)</div>')[0])
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="rate">(.*?)</span>')[0])
            # "2026" for a film, "3 Staffeln" / "Serie" for a series
            isSeries = bool(re.search(r"Staffel|Serie", meta))
            year = "" if isSeries else self.cm.ph.getSearchGroups(meta, r"\b((?:19|20)\d\d)\b")[0]
            desc = " | ".join(x for x in (meta, rating) if x)
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "category": "list_seasons", "title": "%s (%s)" % (title, year) if (normalize and year) else title,
                           "s_title": title, "url": url, "icon": icon, "desc": desc, "meta_title": title, "meta_year": year,
                           "meta_type": "tv" if isSeries else "movie"})
            self.addDir(params)
            count += 1
        # no last page on the site: only a "more titles" link to the next one
        hasNext = bool(re.search(r"[?&;]page=%d(?!\d)" % (page + 1), data))
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl, page_tpl=tpl)
        addPagingItems(self, listItem, page, bool(count) and hasNext, 0, tpl)

    def _meineCloud(self):
        return MeineCloud(self.cm, self.defaultParams, gettytul())

    def _seriesEpisodes(self, imdb):
        if imdb not in self.cacheSeasons:
            self.cacheSeasons = {imdb: self._meineCloud().seriesEpisodes(imdb)}
        return self.cacheSeasons[imdb]

    def listSeasons(self, cItem):
        printDBG("TopStreamFilm.listSeasons")
        sts, data = self.getPage(_pageUrl(cItem["url"]))
        if not sts:
            return
        ld = self._ld(data)
        desc = self.cleanHtmlStr(ensure_str(ld.get("description") or "")) or cItem.get("desc", "")
        show = cItem.get("s_title", "") or cItem["title"]
        movieUrl = self.cm.ph.getSearchGroups(data, MOVIE_IFRAME_RE)[0]
        imdb = self.cm.ph.getSearchGroups(data, SERIES_IMDB_RE)[0]
        if movieUrl or ld.get("@type") == "Movie":
            movie = MeineCloud.imdbFromUrl(movieUrl) or imdb
            if not movie:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
                return
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "category": "video", "title": cItem["title"], "desc": desc, "mc_movie": movie, "meta_type": "movie"})
            self.addVideo(params)
            return
        seasons = self._seriesEpisodes(imdb) if imdb else []
        for seasonNum, episodes in seasons:
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            seasonTag = formatSxxExx(seasonNum) if IsMediaNamingNormalized() else "%s %d" % (_("Season"), seasonNum)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (show, seasonTag), "desc": desc, "s_title": show,
                           "mc_imdb": imdb, "mc_season": seasonNum, "meta_type": "tv", "meta_title": show})
            self.addDir(params)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))

    def listEpisodes(self, cItem):
        printDBG("TopStreamFilm.listEpisodes")
        show = cItem.get("s_title", "") or re.sub(r"\s*-\s*(?:S\d+|\S+ \d+)$", "", cItem.get("title", ""))
        normalize = IsMediaNamingNormalized()
        seasonNum = int(cItem.get("mc_season", 1) or 1)
        pageUrl = _pageUrl(cItem["url"])
        if not cItem.get("mc_imdb"):
            return
        # favourites from before 07.10.2026 still carry "mc_episodes"
        episodes = cItem.get("mc_episodes") or dict(self._seriesEpisodes(cItem["mc_imdb"])).get(seasonNum, [])
        for ep in sorted(episodes, key=lambda x: x["episode"]):
            name = self.cleanHtmlStr(ep["title"])
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(seasonNum, ep["episode"]))
            else:
                title = " - ".join(x for x in (show, "%s %d" % (_("Episode"), ep["episode"]), name) if x)
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.pop("mc_episodes", None)
            params.update({"good_for_fav": True, "category": "episode", "title": title, "url": "%s#s%de%d" % (pageUrl, seasonNum, ep["episode"]),
                           "desc": self.cleanHtmlStr(ep["desc"]) or cItem.get("desc", ""), "ep_desc": self.cleanHtmlStr(ep["desc"]),
                           "mc_episode": "%s/%d/%d" % (cItem["mc_imdb"], seasonNum, ep["episode"]), "mc_url": ep["url"]})
            self.addVideo(params)

    def listValue(self, cItem):
        # genres / years / countries: the links of the site's menu
        prefix = OLD_VALUE_KEYS.get(cItem.get("s", ""), cItem.get("s", ""))
        if not prefix.startswith("/"):
            return
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        rows = []
        seen = set()
        for url, title in re.findall(r'<a href="(%s[^"]+)"[^>]*>([^<]+)</a>' % re.escape(prefix), data):
            title = self.cleanHtmlStr(title)
            if not title or url in seen:
                continue
            seen.add(url)
            rows.append((title, url))
        if prefix == "/jahr/":
            rows.sort(reverse=True)
        for title, url in rows:
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TopStreamFilm.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        # one page (up to 60 titles), the site has no paging for it
        url = self.getFullUrl("/suche?q=%s" % urllib_quote_plus(searchPattern))
        self.listItems(dict(cItem, category="list_items", url=url, base_url=url, page=1))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("TopStreamFilm.getLinksForVideo [%s]" % cItem)
        urltab = []
        if cItem.get("mc_movie"):
            links = self._meineCloud().movieLinks(cItem["mc_movie"])
        elif cItem.get("mc_episode"):
            imdb, season, episode = cItem["mc_episode"].split("/")
            links = self._meineCloud().episodeLinks(imdb, season, episode) or [cItem.get("mc_url", "")]
        else:
            # favourites saved before 27.09.2026 carry the link list in "url"
            links = cItem.get("links") or (cItem["url"] if isinstance(cItem.get("url"), list) else [])
        for url in links:
            if not url or isPlayerUrl(url):
                continue
            if url.startswith("//"):
                url = "https:" + url
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        # the moviemeta query of INFO: the IMDb id of the player first
        imdb = cItem.get("mc_movie", "") or cItem.get("mc_imdb", "") or cItem.get("mc_episode", "").split("/")[0]
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", "") or "movie", cItem.get("meta_title", ""), cItem.get("meta_year", ""), imdb, skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("ep_desc", "") or cItem.get("desc", ""), metaQuery))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("TopStreamFilm.getArticleContent [%s]" % cItem)
        pageUrl = _pageUrl(cItem.get("url"))
        if not pageUrl:
            return []
        info, story = {}, ""
        imdb = cItem.get("mc_movie", "") or cItem.get("mc_imdb", "")
        mediaType = cItem.get("meta_type", "")
        sts, data = self.getPage(pageUrl)
        if sts:
            ld = self._ld(data)
            story = self.cleanHtmlStr(ensure_str(ld.get("description") or ""))
            info = self._ldInfo(ld)
            movieUrl = self.cm.ph.getSearchGroups(data, MOVIE_IFRAME_RE)[0]
            imdb = imdb or MeineCloud.imdbFromUrl(movieUrl) or self.cm.ph.getSearchGroups(data, SERIES_IMDB_RE)[0]
            mediaType = mediaType or {"Movie": "movie", "TVSeries": "tv"}.get(ld.get("@type"), "")
        mediaType = mediaType or "movie"
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and cItem.get("meta_title"):
                meta = getMeta(mediaType, cItem["meta_title"], cItem.get("meta_year", "") or info.get("released", "")[:4])
        except Exception:
            printExc()
        other = dict(meta.get("info", {}))
        for key, value in info.items():
            other.setdefault(key, value)
        plot = meta.get("plot", "")
        text = cItem.get("ep_desc", "") or story or plot or cItem.get("desc", "")
        if plot and text != plot and not cItem.get("ep_desc"):
            text = "%s[/br][/br]%s" % (text, plot)
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem["title"], "text": text, "images": [{"title": "", "url": icon}], "other_info": other}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_value":
            self.listValue(self.currItem)
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
        CHostBase.__init__(self, TopStreamFilm(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("topstreamfilm")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
