# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - new host for documentaryarea.com (English documentaries)
#   Lists: recently added / most viewed / by year / A-Z / complete series / genres + search,
#   all on the site's "wthree-news-left" article cards with the ?page=N pager (4 site pages of 6 cards
#   per list page, First page / Jump / Next page).
#   player.php?title=<name> carries a jwplayer setup: the MP4 source (video.php?playback=<token>)
#   is bound to the PHPSESSID of the page request, so the session cookie goes into the link meta;
#   .srt captions are handed over as external subtitles.
#   Watched flag / downloaded flag / name normalisation "Title (Year)" / sidecar / INFO (moviemeta + site) / favourites.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://www.documentaryarea.com/"


class DocumentaryArea(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # stable identity of a row (the view counter in desc changes)
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "year", "genre", "icon", "meta_type", "meta_title")
    SITE_PAGES_PER_LIST = 4

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "documentaryarea", "cookie": "documentaryarea.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "with_metadata": True, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("/Favicons/social-logo.png")
        self.MENU = [{"category": "list_items", "title": _("Recently added"), "url": self.getFullUrl("/results-recent.php")},
                     {"category": "list_items", "title": _("Most viewed"), "url": self.getFullUrl("/results-mostviewed.php")},
                     {"category": "list_items", "title": _("Year"), "url": self.getFullUrl("/results-year.php")},
                     {"category": "list_items", "title": _("A-Z"), "url": self.getFullUrl("/results-alphabetical.php")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/series.php")},
                     {"category": "list_genres", "title": _("Genres"), "url": self.MAIN_URL}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("documentaryarea")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            if cItem.get("type", "") == "video":
                url = self.wfNormalizeUrlKey(cItem.get("url", ""))
                return "video:%s" % url if url else ""
            if cItem.get("category", "") == "list_series":
                url = self.wfNormalizeUrlKey(cItem.get("base_url") or cItem.get("url", ""))
                return "series:%s" % url if url else ""
            return ""
        except Exception:
            printExc()
        return ""

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _normUrl(self, url, currUrl=None):
        # the cards link to player.php?title=Foo+Bar with and without host, keep one spelling
        url = self.getFullUrl(url.replace("&amp;", "&").replace(" ", "+"), currUrl)
        return re.sub(r"^https?://(?:www\.)?documentaryarea\.com/", self.MAIN_URL, url)

    def _videoTitle(self, title, year):
        return normalizeMediathekTitle(title, year=year, isMovie=True)

    ###################################################
    # lists
    ###################################################
    def listGenres(self, cItem):
        printDBG("DocumentaryArea.listGenres")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for url, title in re.findall(r'href="(/results\.php\?genre=[^"]+)"[^>]*>(.*?)</a>', data, re.DOTALL):
            url = self._normUrl(url)
            title = self.cleanHtmlStr(title)
            if url in seen or not title:
                continue
            seen.add(url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": url})
            self.addDir(params)

    def _parseCard(self, block, currUrl):
        link = self.cm.ph.getSearchGroups(block, r'<h[12]>\s*<a[^>]+href="([^"]+)"')[0]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<h[12]>(.*?)</h[12]>', ignoreCase=True)[0])
        if not link or not title:
            return None
        icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0]
        meta = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'</h[12]>(.*?)<div class="comments-space"', ignoreCase=True)[0])
        year = self.cm.ph.getSearchGroups(meta, r'\b((?:19|20)\d{2})\b')[0]
        genre = meta.replace(year, "", 1).strip() if year else meta
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(block, '<div class="comments-space">', "</div>", False)[1])
        return {"url": self._normUrl(link, currUrl), "title": title, "icon": self.getFullIconUrl(icon.replace(" ", "%20"), currUrl) if icon else "",
                "year": year, "genre": genre, "plot": desc}

    def listItems(self, cItem):
        # the site shows only 6 cards per page (?page=N, 0-based) - one list page merges
        # SITE_PAGES_PER_LIST of them; the site url pattern is learned from the pager of the first page
        page = max(1, int(cItem.get("page", 1) or 1))
        baseUrl = cItem.get("base_url") or cItem["url"]
        siteTpl = cItem.get("site_tpl", "")
        printDBG("DocumentaryArea.listItems |%s| page %d" % (baseUrl, page))
        cnt = 0
        seen = set()
        hasMore = False
        lastIdx = 0
        for sitePage in range((page - 1) * self.SITE_PAGES_PER_LIST, page * self.SITE_PAGES_PER_LIST):
            if sitePage and not siteTpl:
                break
            url = siteTpl.replace("{site_page}", str(sitePage)) if sitePage else baseUrl
            sts, data = self.getPage(url)
            if not sts:
                hasMore = False
                break
            currUrl = data.meta.get("url", url) if hasattr(data, "meta") else url
            pager = re.findall(r'href="([^"]*[?&]page=(\d+)&[^"]*)"', data)
            if pager and not siteTpl:
                siteTpl = re.sub(r"([?&]page=)\d+", r"\g<1>{site_page}", self._normUrl(pager[0][0], currUrl), 1)
            numbers = [int(n) for _href, n in pager]
            lastIdx = max(numbers + [sitePage, lastIdx])
            hasMore = (sitePage + 1) in numbers
            cnt += self._addCards(cItem, data, currUrl, seen)
            if not hasMore:
                break
        listItem = dict(cItem)
        listItem.update({"base_url": baseUrl, "url": baseUrl, "site_tpl": siteTpl})
        lastPage = lastIdx // self.SITE_PAGES_PER_LIST + 1 if siteTpl else 0
        addPagingItems(self, listItem, page, bool(cnt) and hasMore, lastPage, (baseUrl + "#page={page}") if siteTpl else "")

    def _addCards(self, cItem, data, currUrl, seen):
        cnt = 0
        for block in data.split('<div class="wthree-news-left"')[1:]:
            block = block.split("</article>", 1)[0]
            item = self._parseCard(block, currUrl)
            if not item or item["url"] in seen:
                continue
            seen.add(item["url"])
            desc = " | ".join([x for x in (item["year"], item["genre"]) if x])
            if item["plot"]:
                desc = "%s[/br]%s" % (desc, item["plot"]) if desc else item["plot"]
            params = stripPagerKeys(dict(cItem), ("search_pattern", "base_url", "site_tpl"))
            params.update({"good_for_fav": True, "url": item["url"], "icon": item["icon"], "desc": desc,
                           "s_title": item["title"], "year": item["year"], "genre": item["genre"]})
            # "Name Ep 1-3" / "Name Season 2 Ep 4-6" are parts of a series
            metaTitle = re.sub(r"\s+(?:Season\s+\d+\s+)?Ep\s+\d+(?:\s*-\s*\d+)?$", "", item["title"], flags=re.I)
            if "/results-series.php" in item["url"] or "/series/" in item["url"]:
                params.update({"category": "list_series", "title": item["title"], "meta_type": "tv", "meta_title": item["title"]})
                self.addDir(params)
            elif "player.php" in item["url"] or "/video/" in item["url"]:
                params.update({"category": "video", "title": self._videoTitle(item["title"], item["year"]),
                               "meta_type": "movie" if metaTitle == item["title"] else "tv", "meta_title": metaTitle})
                self.addVideo(params)
            else:
                continue
            cnt += 1
        return cnt

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("DocumentaryArea.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("/results.php?search=%s" % urllib_quote_plus(searchPattern)), "page": 1})
        self.listItems(cItem)

    ###################################################
    # player page
    ###################################################
    def _parsePlayer(self, data):
        info = {"desc": "", "poster": "", "duration": "", "views": "", "sources": [], "subs": []}
        info["desc"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        # file names on the site contain spaces
        info["poster"] = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0].replace(" ", "%20")
        duration = self.cm.ph.getSearchGroups(data, r'"duration":\s*"PT(?:(\d+)H)?(?:(\d+)M)?', 2)
        if duration[0] or duration[1]:
            info["duration"] = "%sh %smin" % (duration[0] or "0", duration[1] or "0")
        info["views"] = self.cm.ph.getSearchGroups(data, r'"userInteractionCount":\s*(\d+)')[0]
        setup = self.cm.ph.getDataBeetwenMarkers(data, "jwplayer('myElement').setup(", "</script>", False)[1]
        sources = self.cm.ph.getDataBeetwenMarkers(setup, "sources:", "]", False)[1]
        for src in re.findall(r'\{[^{}]*file:\s*"([^"]+)"[^{}]*\}', sources):
            label = self.cm.ph.getSearchGroups(sources[sources.find(src):], r'label:\s*"([^"]*)"')[0]
            info["sources"].append((src.replace("&amp;", "&"), label))
        tracks = self.cm.ph.getDataBeetwenMarkers(setup, "tracks:", "]", False)[1]
        seenSubs = set()
        for track in re.findall(r'\{(.*?)\}', tracks, re.DOTALL):
            surl = self.cm.ph.getSearchGroups(track, r'file:\s*"([^"]+)"')[0]
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(track, r'label:\s*"([^"]*)"')[0])
            if not surl or surl in seenSubs:
                continue
            seenSubs.add(surl)
            fmt = "vtt" if surl.lower().endswith(".vtt") else "srt"
            lang = "en" if ("ENG" in surl.upper() or label.lower().startswith("eng")) else ("es" if label.lower().startswith("espa") else "")
            info["subs"].append({"title": label or lang or "Sub", "url": self.getFullUrl(surl.replace(" ", "%20")), "lang": lang, "format": fmt})
        return info

    def getLinksForVideo(self, cItem):
        printDBG("DocumentaryArea.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = cItem.get("url", "")
        if not self.cm.isValidUrl(pageUrl):
            return []
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        info = self._parsePlayer(data)
        if not info["sources"]:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        # the playback token only works together with the session cookie of this page request
        cookie = self.cm.getCookieHeader(self.COOKIE_FILE)
        refUrl = data.meta.get("url", pageUrl) if hasattr(data, "meta") else pageUrl
        urltab = []
        for src, label in info["sources"]:
            meta = {"Referer": refUrl, "User-Agent": self.HEADER.get("User-Agent", ""), "Origin": self.MAIN_URL.rstrip("/")}
            if cookie:
                meta["Cookie"] = cookie
            if info["subs"]:
                meta["external_sub_tracks"] = info["subs"]
            urltab.append({"name": "MP4 %s" % label if label else "MP4", "url": strwithmeta(self.getFullUrl(src), meta), "need_resolve": 0})
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), info["desc"]))

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("DocumentaryArea.getArticleContent [%s]" % cItem.get("url", ""))
        otherInfo = {}
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        title = cItem.get("s_title", cItem.get("title", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("year", "") if cItem["meta_type"] == "movie" else "")
            except Exception:
                printExc()
        if cItem.get("type") == "video" and self.cm.isValidUrl(cItem.get("url", "")):
            sts, data = self.getPage(cItem["url"])
            if sts:
                info = self._parsePlayer(data)
                text = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="comments-space">', "</div>", False)[1]) or info["desc"] or text
                icon = info["poster"] or icon
                if info["duration"]:
                    otherInfo["duration"] = info["duration"]
                if info["views"]:
                    otherInfo["views"] = info["views"]
        else:
            text = re.sub(r"^.*?\[/br\]", "", text) if "[/br]" in text else text
        if cItem.get("year"):
            otherInfo["year"] = cItem["year"]
        if cItem.get("genre"):
            otherInfo["genres"] = cItem["genre"]
        otherInfo.update(meta.get("info", {}))
        # the site's own text first (it describes exactly this video / these parts)
        plot = meta.get("plot", "")
        if plot and plot != text:
            text = "%s[/br][/br]%s" % (text, plot) if text else plot
        icon = icon or meta.get("poster", "")
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
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
        printDBG("DocumentaryArea.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category in ("list_items", "list_series"):
            self.listItems(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
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
        CHostBase.__init__(self, DocumentaryArea(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("documentaryarea")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category") == "list_series"
