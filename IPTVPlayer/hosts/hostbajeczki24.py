# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# Bajeczki24 (bajeczki24.pl): films, series and cartoons in Polish; one Byse player per title (urlparser),
# search through the site's own search API
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://bajeczki24.pl/"


# the search box of the site asks this Meilisearch proxy, with the public key from its own script (Search.*.js)
SEARCH_API = "https://api.bajeczki24.pl/radar/v1/multi-search"
SEARCH_KEY = "118b6cd0fd246c02d4fe6465a1e5c16d7ce09fb67935180da44a060db68855c2"
SEARCH_PAGE_SIZE = 30
POSTER_TPL = "https://bajeczki24.pl/images/v1/format=auto,quality=75,fit=cover,w=300,h=450/%s"
# "1 h 46 min", "51 min"
DURATION_RE = re.compile(r"^(?:\d+\s*h\s*)?\d+\s*min$")
# plot paragraph of a card (not an svg <path>)
PLOT_RE = r"(?s)<p(?:\s[^>]*)?>(.*?)</p>"


class Bajeczki24(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "bajeczki24", "cookie": "bajeczki24.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.HEADER.update({"Accept-Language": "pl,en;q=0.8"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("/apple-touch-icon.png")
        self.MENU = [{"category": "list_home", "title": _("Featured"), "url": self.getFullUrl("/glowna/"), "section": 0},
                     {"category": "list_home", "title": _("Latest"), "url": self.getFullUrl("/glowna/"), "section": 1},
                     {"category": "list_genres", "title": _("Movies"), "url": self.getFullUrl("/filmy/")},
                     {"category": "list_shows", "title": _("Series"), "url": self.getFullUrl("/seriale/")},
                     {"category": "list_shows", "title": _("Cartoons"), "url": self.getFullUrl("/bajki/")}] + self.searchItems()
        self.pageCache = ("", "")
        self.watchedHelper = IPTVWatchedHelper("bajeczki24")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _getTitlePage(self, url):
        # INFO and the link list read the same page - fetch it once
        if self.pageCache[0] == url:
            return True, self.pageCache[1]
        sts, data = self.getPage(url)
        if sts and data:
            self.pageCache = (url, data)
        return sts, data

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            if not path:
                return ""
            if cItem.get("type", "") == "video":
                return "video:%s" % path
            if cItem.get("category", "") in ("list_seasons", "list_episodes"):
                return "folder:%s" % path
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _spans(self, html):
        return [s for s in (self.cleanHtmlStr(x) for x in re.findall(r"<span[^>]*>(.*?)</span>", html)) if s and s != "•"]

    def _addMovie(self, url, title, icon, year="", origTitle="", desc=""):
        title = self.cleanHtmlStr(title)
        if not url or not title:
            return False
        label = "%s (%s)" % (title, year) if (year and IsMediaNamingNormalized()) else title
        self.addVideo({"name": "category", "category": "video", "good_for_fav": True, "url": self.getFullUrl(url), "title": label, "icon": icon, "desc": desc,
                       "meta_type": "movie", "meta_title": origTitle or title, "meta_year": year, "local_title": title})
        return True

    def _addCards(self, data):
        # film / show cards: <article> ... <span>16+</span> <span>2026</span> <span>1 h 46 min</span> </div>
        # <h3>Title</h3> <span>Original title</span> <div><span>Genre</span> ...</div> <p>plot</p> ... </article>
        count = 0
        for item in re.findall(r"(?s)<article[^>]*>(.*?)</article>", data):
            url = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="(/(?:filmy|seriale|bajki)/[^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<h3[^>]*>(.*?)</h3>")[0])
            if not url or not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            head, _sep, tail = item.partition("<h3")
            facts = self._spans(head.rsplit("</a>", 1)[-1])
            year = ([s for s in facts if re.match(r"^\d{4}$", s)] or [""])[0]
            origTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tail, r"(?s)</h3>\s*<span[^>]*>(.*?)</span>")[0])
            genres = self._spans(self.cm.ph.getSearchGroups(tail, r"(?s)</h3>\s*(?:<span[^>]*>.*?</span>\s*)?<div[^>]*>(.*?)</div>")[0])
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tail, PLOT_RE)[0])
            descLine = " | ".join([x for x in [origTitle if origTitle != title else ""] + facts + [", ".join(genres)] if x])
            desc = "%s[/br]%s" % (descLine, plot) if descLine and plot else (descLine or plot)
            if url.startswith("/filmy/"):
                if self._addMovie(url, title, icon, year, origTitle, desc):
                    count += 1
                continue
            show = origTitle or title
            self.addDir({"name": "category", "category": "list_seasons", "good_for_fav": True, "url": self.getFullUrl(url), "title": title, "icon": icon, "desc": desc,
                         "meta_type": "tv", "meta_title": show, "meta_year": year, "s_title": title})
            count += 1
        return count

    def listHome(self, cItem):
        printDBG("Bajeczki24.listHome |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        sections = re.split(r"<h2[^>]*>", data)[1:]
        idx = int(cItem.get("section", 0) or 0)
        if idx < len(sections):
            self._addCards(sections[idx])

    def listGenres(self, cItem):
        printDBG("Bajeczki24.listGenres")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for url, title, count in re.findall(r'(?s)<a[^>]+href="(/filmy/[^/"]+/)"[^>]*>\s*<span[^>]*>([^<]+)</span>\s*<span[^>]*>\s*(\d+)\s*</span>', data):
            if url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "url": self.getFullUrl(url), "title": self.cleanHtmlStr(title),
                         "desc": "%s: %s" % (_("Movies"), count)})

    def listItems(self, cItem):
        # genre pages: /filmy/<genre>/, /filmy/<genre>/<N>/
        printDBG("Bajeczki24.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        baseUrl = re.sub(r"/\d+/$", "/", cItem["url"])
        pageUrlTpl = baseUrl + "{page}/"
        sts, data = self.getPage(baseUrl if page == 1 else pageUrlTpl.format(page=page))
        if not sts:
            return
        count = self._addCards(data)
        lastPage = int(self.cm.ph.getSearchGroups(data, r'data-lastpage="(\d+)"')[0] or 0)
        nextItem = dict(cItem)
        nextItem["url"] = baseUrl
        addPagingItems(self, nextItem, page, bool(count) and page < lastPage, lastPage, pageUrlTpl)

    def listShows(self, cItem):
        printDBG("Bajeczki24.listShows")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        main = self.cm.ph.getDataBeetwenNodes(data, ("<main", ">"), ("</main", ">"), False)[1] or data
        self._addCards(main)

    def _children(self, data):
        # season / episode cards: <a href="N/"> <article> ... </article> </a>
        return re.findall(r'(?s)<a[^>]+href="(\d+)/"[^>]*>\s*<article[^>]*>(.*?)</article>', data)

    def listSeasons(self, cItem):
        printDBG("Bajeczki24.listSeasons |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)id="folded-text-content"[^>]*>(.*?)</div>')[0])
        for num, item in self._children(data):
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<h3[^>]*>(.*?)</h3>")[0])
            facts = self._spans(item.split("</h3>", 1)[-1])
            facts = [s for s in facts if s != num and not s.startswith("Zobacz")]
            title = _("Season %s") % num
            if name and not re.match(r"(?i)^sezon\s*%s$" % num, name):
                title = "%s - %s" % (title, name)
            seasonPlot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, PLOT_RE)[0]) or plot
            desc = " | ".join(facts)
            params = dict(cItem)
            params.update({"category": "list_episodes", "good_for_fav": True, "url": cItem["url"].rstrip("/") + "/%s/" % num, "title": title,
                           "icon": self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0] or cItem.get("icon", ""),
                           "desc": "%s[/br]%s" % (desc, seasonPlot) if desc and seasonPlot else (desc or seasonPlot), "season": num, "s_title": show})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Bajeczki24.listEpisodes |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        show = cItem.get("s_title") or self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<h2[^>]*>(.*?)</h2>")[0])
        season = cItem.get("season") or self.cm.ph.getSearchGroups(cItem["url"], r"/(\d+)/?$")[0]
        normalize = IsMediaNamingNormalized()
        for num, item in self._children(data):
            raw = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<h3[^>]*>(.*?)</h3>")[0])
            epName = re.sub(r"^\d+\.\s*", "", raw)
            duration = ([s for s in self._spans(item) + [self.cleanHtmlStr(x) for x in re.findall(r"<div[^>]*>([^<]+)</div>", item)] if DURATION_RE.match(s)] or [""])[0]
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, PLOT_RE)[0])
            title = "%s - %s" % (show, formatSxxExx(season, num)) if (normalize and show) else (raw or "%s %s" % (_("Episode"), num))
            descLine = " | ".join(x for x in (epName if normalize else "", duration) if x)
            self.addVideo({"name": "category", "category": "video", "good_for_fav": True, "url": cItem["url"].rstrip("/") + "/%s/" % num, "title": title,
                           "icon": self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0] or cItem.get("icon", ""),
                           "desc": "%s[/br]%s" % (descLine, plot) if descLine and plot else (descLine or plot),
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", "") or show, "meta_year": cItem.get("meta_year", ""), "s_title": show,
                           "season": season, "episode": num, "ep_name": epName})

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Bajeczki24.listSearchResult [%s] page[%s]" % (searchPattern, cItem.get("page", 1)))
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        pattern = cItem.get("search_pattern") or searchPattern
        post = {"queries": [{"indexUid": "movies-v2", "q": pattern}, {"indexUid": "tv-shows-v2", "q": pattern}],
                "federation": {"offset": (page - 1) * SEARCH_PAGE_SIZE, "limit": SEARCH_PAGE_SIZE}}
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, **{"Content-Type": "application/json", "Accept": "application/json", "Authorization": "Bearer " + SEARCH_KEY,
                                                "Origin": self.MAIN_URL.rstrip("/"), "Referer": self.MAIN_URL})
        params["raw_post_data"] = True
        sts, data = self.cm.getPage(SEARCH_API, params, json_dumps(post))
        if not sts:
            return
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return
        hits = data.get("hits") or []
        for hit in hits:
            path = ensure_str(hit.get("path") or "")
            title = ensure_str(hit.get("title") or "")
            year = str(hit.get("releaseYear") or "")
            poster = ensure_str(hit.get("posterPath") or "")
            icon = POSTER_TPL % poster if poster else ""
            facts = [x for x in (year, ", ".join(ensure_str(c) for c in hit.get("categories") or [])) if x]
            plot = self.cleanHtmlStr(ensure_str(hit.get("shortDescription") or ""))
            desc = "%s[/br]%s" % (" | ".join(facts), plot) if facts and plot else (" | ".join(facts) or plot)
            if path.startswith("/filmy/"):
                self._addMovie(path, title, icon, year, "", desc)
            elif path.startswith(("/seriale/", "/bajki/")):
                self.addDir({"name": "category", "category": "list_seasons", "good_for_fav": True, "url": self.getFullUrl(path), "title": title, "icon": icon, "desc": desc,
                             "meta_type": "tv", "meta_title": title, "meta_year": year, "s_title": title})
        try:
            total = int(data.get("estimatedTotalHits") or 0)
        except (TypeError, ValueError):
            total = 0
        lastPage = (total + SEARCH_PAGE_SIZE - 1) // SEARCH_PAGE_SIZE
        nextItem = dict(cItem)
        nextItem.update({"category": "search_next_page", "search_pattern": pattern})
        # constant template: the page number drives the search, the template only lets "Jump" through
        addPagingItems(self, nextItem, page, len(hits) >= SEARCH_PAGE_SIZE and page < lastPage, lastPage, self.MAIN_URL)

    ###################################################
    # links
    ###################################################
    def _plot(self, data):
        # <div class="prose ..."> [<div class="badge ...">18+</div>] <span>plot</span> </div>
        text = self.cm.ph.getSearchGroups(data, r'(?s)<div[^>]+class="prose[^"]*"[^>]*>(.*?)</span>\s*</div>')[0]
        return self.cleanHtmlStr(re.sub(r"(?s)<div[^>]+badge[^>]*>.*?</div>", "", text))

    def getLinksForVideo(self, cItem):
        printDBG("Bajeczki24.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self._getTitlePage(cItem.get("url", ""))
        if not sts:
            return []
        urlTab = []
        unsupported = []
        for url in re.findall(r'<iframe[^>]+src="([^"]+)"', data, re.I):
            url = url.replace("&amp;", "&")
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in [str(x["url"]) for x in urlTab]:
                continue
            if self.up.checkHostSupport(url) != 1:
                printDBG("Bajeczki24: unsupported hoster [%s]" % url)
                unsupported.append(self.up.getHostName(url))
                continue
            urlTab.append({"name": self.up.getHostName(url, True).capitalize(), "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urlTab:
            if unsupported:
                SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(unsupported))
            else:
                SetIPTVPlayerLastHostError(_("No player found for this title."))
            return []
        sidecarTxt = self._plot(data) or cItem.get("desc", "")
        # the same lookup as the INFO view (answers from its cache)
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", ""), cItem.get("meta_title", ""), cItem.get("meta_year", ""), skip=(), maxYearDiff=1)
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt, metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("Bajeczki24.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Bajeczki24.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        icon = cItem.get("icon", "")
        text = ""
        other = {}
        if cItem.get("type") == "video":
            sts, data = self._getTitlePage(cItem.get("url", ""))
            if sts:
                text = self._plot(data)
        else:
            text = re.sub(r"^.*?\[/br\]", "", cItem.get("desc", "")) if "[/br]" in cItem.get("desc", "") else cItem.get("desc", "")
        if cItem.get("local_title") and cItem.get("meta_title") and cItem["meta_title"] != cItem["local_title"]:
            other["original_title"] = cItem["meta_title"]
        meta = {}
        if cItem.get("meta_title"):
            try:
                meta = getMeta(cItem.get("meta_type", ""), cItem["meta_title"], cItem.get("meta_year", ""), maxYearDiff=1)
            except Exception:
                printExc()
        if meta:
            other.update(meta.get("info", {}))
            plot = meta.get("plot") or ""
            if plot and plot != text:
                text = "%s[/br][/br]%s" % (text, plot) if text else plot
        if cItem.get("episode"):
            title = "%s - %s" % (cItem.get("s_title") or title, formatSxxExx(cItem.get("season"), cItem["episode"]))
            if cItem.get("ep_name"):
                title = "%s %s" % (title, cItem["ep_name"])
        images = [{"title": "", "url": url} for url in (icon, meta.get("poster")) if url]
        return [{"title": title, "text": text or cItem.get("desc", ""), "images": images[:1], "other_info": other}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Bajeczki24.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_home":
            self.listHome(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_shows":
            self.listShows(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
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
        CHostBase.__init__(self, Bajeczki24(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("bajeczki24")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category") in ("list_seasons", "list_episodes")
