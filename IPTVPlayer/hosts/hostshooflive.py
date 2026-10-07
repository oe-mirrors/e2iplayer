# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# Ported to the python3 framework (06.10.2026):
#   - shooflive.net: movie and series categories (the site menu) with First page / Jump / Next page
#     (last page from the pager), series -> episodes (ascending)
#   - search: the site's new search page (?s=<q>&sp=<page>, "slv2" cards) - the old list markup
#     there is gone, that was the empty search
#   - links: the AlbaPlayer page of the post (shooof.site/albaplayer/...) lists the servers
#     (AnaFast, MP4Plus, VidSpeed, VK ...); each server page holds the hoster iframe -> urlparser
#   - watched flag (series -> episodes), downloaded flag on page-url keys, favourites, name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the site's story
#   - covers: sent with a browser User-Agent (urllib's default UA gets a 403)
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://shooflive.net/"


LOCAL_PAGE_SIZE = 100
SEASON_RE = re.compile(r"الموسم\s*(\d+)")
EPISODE_RE = re.compile(r"الحلقة\s*(\d+)")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجم|مترجمة|مدبلج|مدبلجة|اون لاين|أون لاين|كامل|كاملة|فيلم|مسلسل)(?=\s|$)")
YEAR_RE = re.compile(r"\s(19\d\d|20\d\d)(?=\s|$)")
VIDEO_CATEGORIES = ("sl_video", "sl_episode")
SERIES_CATEGORIES = ("sl_series",)


def _domain(url):
    m = re.match(r"^https?://(?:www\.)?([^/:?#]+)", url or "")
    return m.group(1).lower() if m else ""


class ShoofLive(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "shooflive", "cookie": "shooflive.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/shooflive135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("shooflive")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    @staticmethod
    def _quote(url):
        try:
            return urllib_quote(urllib_unquote(url.replace("&amp;", "&").replace("&#038;", "&")), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _canonUrl(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return self._quote(url)

    def _path(self, url):
        url = urllib_unquote(self._canonUrl(url))
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def _icon(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        return strwithmeta(self._canonUrl(url), {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL})

    @staticmethod
    def _clean(text):
        text = SEASON_RE.sub(" ", text or "")
        text = EPISODE_RE.sub(" ", text)
        text = JUNK_RE.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip(" -:|")

    def _splitTitle(self, rawTitle):
        # "فيلم Moana 2026 مترجم" -> ("Moana", "2026")
        title = self._clean(rawTitle)
        year = ""
        m = YEAR_RE.search(" " + title)
        if m:
            year = m.group(1)
            stripped = re.sub(r"\s+", " ", YEAR_RE.sub(" ", " " + title)).strip(" -:|")
            if stripped:
                title = stripped
        return title or rawTitle, year

    def _kind(self, url):
        path = self._path(url)
        if path.startswith("/series/"):
            return "series"
        if path.startswith("/episode/"):
            return "episode"
        return "movie"

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + SERIES_CATEGORIES:
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
            prefix = {"sl_video": "video", "sl_episode": "video", "sl_series": "series"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        def cat(slug):
            return self.getFullUrl("/%s/" % slug)

        movies = [
            (_("Foreign movies"), cat("foreign-movies")),
            (_("Arabic Movies"), cat("arabic-movies")),
            (_("Turkish Movies"), cat("turkish-movies")),
            (_("Asian movies"), cat("asian-movies")),
            (_("Indian Movies"), cat("indian-movies")),
            (_("Animation"), cat("animation-movies")),
        ]
        series = [
            (_("Arabic Series"), cat("arabic-series")),
            (_("Turkish Series"), cat("turkish-series")),
            (_("Foreign series"), cat("foreign-series")),
            (_("Asian TV series"), cat("asian-series")),
            (_("Dubbed series"), cat("dubbed-series")),
            (_("Short series"), cat("short-series")),
            ("%s 2026" % _("Ramadan"), cat("ramadan-series-2026")),
        ]
        menu = [
            {"category": "sl_tab", "title": _("Movies"), "tab": movies},
            {"category": "sl_tab", "title": _("Series"), "tab": series},
        ]
        self.listsTab(menu + self.searchItems(), cItem)

    def listTab(self, cItem):
        for title, url in cItem.get("tab", []):
            self.addDir({"name": "category", "category": "list_items", "title": title, "url": url, "good_for_fav": True})

    def _addRow(self, url, rawTitle, icon, normalize):
        url = self._canonUrl(url)
        rawTitle = self.cleanHtmlStr(rawTitle)
        if not url or not rawTitle:
            return False
        title, year = self._splitTitle(rawTitle)
        desc = "%s: %s" % (_("Year"), year) if year else ""
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": self._icon(icon), "desc": desc}
        kind = self._kind(url)
        if kind == "series":
            params.update({"category": "sl_series", "title": title if normalize else rawTitle, "s_title": title,
                           "meta_type": "tv", "meta_title": title, "meta_year": year})
            self.addDir(params)
        elif kind == "episode":
            season = self.cm.ph.getSearchGroups(rawTitle, SEASON_RE.pattern)[0] or "1"
            episode = self.cm.ph.getSearchGroups(rawTitle, EPISODE_RE.pattern)[0]
            dispTitle = "%s - %s" % (title, formatSxxExx(season, episode)) if normalize and episode else rawTitle
            params.update({"category": "sl_episode", "title": dispTitle, "s_title": title, "s_season": int(season), "s_episode": episode,
                           "meta_type": "tv", "meta_title": title, "meta_year": year})
            self.addVideo(params)
        else:
            dispTitle = rawTitle
            if normalize:
                dispTitle = "%s (%s)" % (title, year) if year else title
            params.update({"category": "sl_video", "title": dispTitle, "meta_type": "movie", "meta_title": title, "meta_year": year})
            self.addVideo(params)
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = self._canonUrl(cItem.get("base_url") or cItem["url"])
        query = cItem.get("query", "")
        if query:
            # search page: ?s=<q>&sp=<page>, "slv2" cards, pager <nav class="slv2-pages">
            pageTpl = baseUrl + "?s=" + query + "&sp={page}"
            url = pageTpl.format(page=page) if page > 1 else baseUrl + "?s=" + query
        else:
            pageTpl = baseUrl + "page/{page}/"
            url = pageTpl.format(page=page) if page > 1 else baseUrl
        printDBG("ShoofLive.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        if query:
            for href, title, block in re.findall(r'(?s)<a class="slv2-card" href="([^"]+)" title="([^"]*)">(.*?)</a>', data):
                if href not in seen and self._addRow(href, title, self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0], normalize):
                    seen.add(href)
            pager = self.cm.ph.getDataBeetwenMarkers(data, '<nav class="slv2-pages"', "</nav>", False)[1]
            pages = [int(n) for n in re.findall(r"[?&]sp=(\d+)", pager)]
        else:
            block = self.cm.ph.getDataBeetwenMarkers(data, '<div id="load-post-', "</main>", False)[1]
            for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<article", "</article>"):
                href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
                title = self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'(?s)<div class="title">(.*?)</div>')[0]
                icon = self.cm.ph.getSearchGroups(item, r'data-src="?([^"\s>]+)')[0]
                if href and href not in seen and self._addRow(href, title, icon, normalize):
                    seen.add(href)
            pager = self.cm.ph.getDataBeetwenMarkers(data, "<div class='pagination'>", "</div>", False)[1]
            pages = [int(n) for n in re.findall(r"/page/(\d+)/", pager)]
        lastPage = max(pages + [page])
        hasNext = bool(seen) and lastPage > page
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    def listEpisodes(self, cItem):
        printDBG("ShoofLive.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        # the episodes of the show, before the "new on the site" tabs
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="singleSeries">', "</main>", False)[1]
        block = block.split('class="watch-tabs-cnt"')[0]
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        episodes = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, '<article class="postEp">', "</article>"):
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            url = self._canonUrl(href)
            if not url or url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            episode = self.cm.ph.getSearchGroups(label, EPISODE_RE.pattern)[0] or self.cm.ph.getSearchGroups(item, r"(?s)episodeNum.*?<span>\s*(\d+)\s*</span>")[0]
            season = int(self.cm.ph.getSearchGroups(label, SEASON_RE.pattern)[0] or 1)
            if normalize and episode:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = label or "%s %s" % (_("Episode"), episode)
            icon = self.cm.ph.getSearchGroups(item, r'data-src="?([^"\s>]+)')[0]
            episodes.append((season, int(episode or 0), {"name": "category", "good_for_fav": True, "category": "sl_episode", "title": title, "url": url,
                             "icon": self._icon(icon) if icon else cItem.get("icon", ""), "desc": cItem.get("desc", ""),
                             "s_title": show, "s_season": season, "s_episode": episode,
                             "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")}))
        episodes.sort(key=lambda e: (e[0], e[1]))
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params[2])
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ShoofLive.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.MAIN_URL, "base_url": self.MAIN_URL, "page": 1,
                      "query": urllib_quote_plus(searchPattern.strip())})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="story">(.*?)</div>')[0])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]+)"')[0])
        cover = self.cm.ph.getDataBeetwenMarkers(data, '<div class="singleSeries">', '<div class="info">', False)[1]
        poster = self.cm.ph.getSearchGroups(cover, r'data-src="([^"]+)"')[0]
        return story, self._icon(poster)

    def getLinksForVideo(self, cItem):
        printDBG("ShoofLive.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._canonUrl(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        embed = self.cm.ph.getDataBeetwenMarkers(data, '<div class="getEmbed', "</div>", False)[1]
        playerUrl = self.cm.ph.getSearchGroups(embed, r'<iframe[^>]+src="([^"]+)"')[0]
        urltab = []
        if playerUrl:
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=self.MAIN_URL)
            sts, player = self.cm.getPage(playerUrl, params)
            if sts:
                for href, name in re.findall(r'<a class="aplr-link[^"]*" href="([^"]+)"[^>]*>(.*?)</a>', player):
                    urltab.append({"name": self.cleanHtmlStr(name) or "%s %d" % (_("Server"), len(urltab) + 1),
                                   "url": strwithmeta(href.replace("&amp;", "&"), {"Referer": playerUrl}), "need_resolve": 1})
                if not urltab:
                    # a player page without a server menu: the iframe itself
                    frame = self.cm.ph.getSearchGroups(player, r'<iframe[^>]+src="([^"]+)"')[0].strip()
                    if frame:
                        urltab.append({"name": _domain(frame), "url": strwithmeta(frame, {"Referer": playerUrl}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("ShoofLive.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if "/albaplayer/" in videoUrl:
            # one server of the AlbaPlayer menu -> its hoster iframe
            referer = videoUrl.meta.get("Referer", self.MAIN_URL) if hasattr(videoUrl, "meta") else self.MAIN_URL
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=referer)
            sts, data = self.cm.getPage(videoUrl, params)
            if not sts:
                return []
            frame = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"')[0].replace("&amp;", "&").strip()
            if frame.startswith("//"):
                frame = "https:" + frame
            if not self.cm.isValidUrl(frame):
                SetIPTVPlayerLastHostError(_("No stream available"))
                return []
            videoUrl = strwithmeta(frame, {"Referer": "https://%s/" % _domain(str(videoUrl))})
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("ShoofLive.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""))
            except Exception:
                printExc()
        story, poster = "", ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster = self._siteInfo(data)
        info = {}
        if cItem.get("meta_year"):
            info["year"] = cItem["meta_year"]
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
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
        printDBG("ShoofLive.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "sl_tab":
            self.listTab(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "sl_series":
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
        CHostBase.__init__(self, ShoofLive(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("shooflive")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + SERIES_CATEGORIES
