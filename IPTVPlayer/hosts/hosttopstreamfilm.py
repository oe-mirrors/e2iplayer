# -*- coding: utf-8 -*-
# Last Modified: 01.10.2026
# 14.06.2026 - Mr.X
# 27.09.2026 - domain topstreamfilm.best; meinecloud.click embeds via its token API (libs/meinecloud.py),
# series seasons/episodes from it too; items keep their page url (INFO), links live in their own key.
# 01.10.2026 - the player iframe moved from meinecloud.click to devideosrc.co.
# 07.10.2026 - First/Jump/Next paging (lists + search); "Title (Year)" / "Show - SxxExx"; episodes keyed on
# their own url (page + "#s1e2"), seasons reload their episodes (no episode list stored in favourites);
# watched flag, sidecar, downloaded marker; INFO via moviemeta (IMDb id of the player) + the site's fields.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.meinecloud import MeineCloud, MOVIE_IFRAME_RE, isPlayerUrl
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
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
    return "https://topstreamfilm.best/"


PAGING_KEYS = ("base_url", "page_tpl")


def _pageUrl(url):
    # episode rows: the series page + "#s<season>e<episode>"; favourites from before 27.09.2026 may carry a list
    return "" if (not url or isinstance(url, list)) else url.split("#")[0]


class TopStreamFilm(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "TopStreamFilm", "cookie": "TopStreamFilm.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "templates/topstreamfilm/images/logo-1.png"
        self.MAIN_URL = "https://topstreamfilm.best"
        self.MENU = [{"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("kinofilme")},
                     {"category": "list_items", "title": _("New"), "url": self.getFullUrl("filme-online-sehen")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serien")},
                     {"category": "list_value", "title": _("Genres"), "s": ">KATEGORIEN<"},
                     {"category": "list_value", "title": _("A-Z"), "s": "AZList"},
                     {"category": "list_value", "title": _("Year"), "s": ">YAHRE<"},
                     {"category": "list_value", "title": _("Country"), "s": ">LAND<"}] + self.searchItems()
        self.cacheSeasons = {}
        self.watchedHelper = IPTVWatchedHelper("topstreamfilm")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

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
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("TopStreamFilm.listItems |%s|" % cItem)
        page = int(cItem.get("page", 1) or 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        tpl = cItem.get("page_tpl", "") or (re.sub(r"/page/\d+/?$", "", baseUrl).rstrip("/").replace("{", "{{").replace("}", "}}") + "/page/{page}/")
        sts, data = self.getPage(baseUrl if page <= 1 else tpl.format(page=page))
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        con = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="TPostMv">', "</article>")
        if not con:
            con = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="Num">', "</tr>")
        count = 0
        for item in con:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)')[0])
            title = self.cm.ph.getSearchGroups(item, 'Title">([^<]+)')[0]
            if not title:
                title = self.cm.ph.getSearchGroups(item, "<strong>(.*?)</strong>")[0]
            title = self.cleanHtmlStr(title.split(" &#8211;")[0])
            if not title or not self.cm.isValidUrl(url):
                continue
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '(?s)Description">(.*?)</div>')[0])
            dur = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'access_time">([\d]+)m')[0])
            year = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'"Year">(\d+)<')[0])
            head = " | ".join("%s: %s" % (label, value) for label, value in ((_("Year"), year), (_("Duration"), "%s min" % dur if dur else "")) if value)
            desc = "\n".join(x for x in (head, plot) if x)
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "category": "list_seasons", "title": "%s (%s)" % (title, year) if (normalize and year) else title,
                           "s_title": title, "url": url, "icon": icon, "desc": desc, "meta_title": title, "meta_year": year})
            self.addDir(params)
            count += 1
        nums = [int(a or b) for a, b in re.findall(r"/page/(\d+)/|list_submit\((\d+)\)", data)]
        lastPage = max(nums) if nums else 0
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl, page_tpl=tpl)
        addPagingItems(self, listItem, page, bool(count) and page < lastPage, lastPage, tpl)

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
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0]) or cItem.get("desc", "")
        show = cItem.get("s_title", "") or cItem["title"]
        movieUrl = self.cm.ph.getSearchGroups(data, MOVIE_IFRAME_RE)[0]
        if movieUrl:
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "category": "video", "title": cItem["title"], "desc": desc, "mc_movie": MeineCloud.imdbFromUrl(movieUrl), "meta_type": "movie"})
            self.addVideo(params)
            return
        imdb = self.cm.ph.getSearchGroups(data, r"imdb\s*=\s*'(tt\d+)'")[0]
        if imdb:
            seasons = self._seriesEpisodes(imdb)
            for seasonNum, episodes in seasons:
                params = stripPagerKeys(dict(cItem), PAGING_KEYS)
                seasonTag = formatSxxExx(seasonNum) if IsMediaNamingNormalized() else "%s %d" % (_("Season"), seasonNum)
                params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (show, seasonTag), "desc": desc, "s_title": show,
                               "mc_imdb": imdb, "mc_season": seasonNum, "meta_type": "tv", "meta_title": show})
                self.addDir(params)
            if not seasons:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        serieold = re.findall(r'<div class="tt_season">.*?</ul>', data, re.DOTALL)
        if serieold:
            for s in re.findall(r'"#season-(\d+)', serieold[0], re.DOTALL):
                params = stripPagerKeys(dict(cItem), PAGING_KEYS)
                params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s %s" % (show, _("Season"), s), "s_title": show,
                               "mc_season": int(s), "desc": desc, "meta_type": "tv", "meta_title": show})
                self.addDir(params)
            return
        SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))

    def listEpisodes(self, cItem):
        printDBG("TopStreamFilm.listEpisodes")
        show = cItem.get("s_title", "") or re.sub(r"\s*-\s*(?:S\d+|\S+ \d+)$", "", cItem.get("title", ""))
        normalize = IsMediaNamingNormalized()
        seasonNum = int(cItem.get("mc_season", 1) or 1)
        pageUrl = _pageUrl(cItem["url"])
        if cItem.get("mc_imdb"):
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
            return
        # very old pages: <div id="season-1"> ... data-title / data-link
        seasons = cItem.get("serieold")
        if not seasons:
            sts, data = self.getPage(pageUrl)
            seasons = re.findall(r'id="season-%d">.*?</ul>' % seasonNum, data, re.DOTALL) if sts else []
        if seasons:
            for idx, (title, d) in enumerate(re.findall(r'data-title="([^"]+)(.*?</div>)', seasons[0], re.DOTALL)):
                params = stripPagerKeys(dict(cItem), PAGING_KEYS)
                params.pop("serieold", None)
                params.update({"good_for_fav": True, "category": "episode", "title": "%s - %s" % (show, self.cleanHtmlStr(title)),
                               "url": "%s#s%de%d" % (pageUrl, seasonNum, idx + 1), "links": re.findall(r'data-link="([^"]+)', d, re.DOTALL)})
                self.addVideo(params)

    def listValue(self, cItem):
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], "</ul>")
        if data:
            for url, title in re.findall("""href=["']([^"']+).*?>([^<]+)""", data[0]):
                if any(k in title for k in ("kino", "Dem", "Seri")):
                    continue
                params = stripPagerKeys(dict(cItem), PAGING_KEYS)
                params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url)})
                self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TopStreamFilm.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        story = urllib_quote_plus(searchPattern).replace("{", "{{").replace("}", "}}")
        tpl = self.getFullUrl("index.php?do=search&subaction=search&search_start={page}&story=%s" % story)
        self.listItems(dict(cItem, category="list_items", url=tpl.format(page=1), base_url=tpl.format(page=1), page_tpl=tpl))

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
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("ep_desc", "") or cItem.get("desc", "")))

    def getVideoLinks(self, url):
        printDBG("TopStreamFilm.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecarFromUrlMeta(url, IsSidecarEnabled()))
        return []

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
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0])
            for key, pat in {"director": r'temprop="director" content="([^"]+)"', "released": r'date_range">([^<]+)', "duration": r'access_time">([^<]+)'}.items():
                value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, pat)[0])
                if value:
                    info[key] = value
            movieUrl = self.cm.ph.getSearchGroups(data, MOVIE_IFRAME_RE)[0]
            seriesImdb = self.cm.ph.getSearchGroups(data, r"imdb\s*=\s*'(tt\d+)'")[0]
            imdb = imdb or MeineCloud.imdbFromUrl(movieUrl) or seriesImdb
            mediaType = mediaType or ("movie" if movieUrl else ("tv" if seriesImdb else ""))
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
        other.update(info)
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
