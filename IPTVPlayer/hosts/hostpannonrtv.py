# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# Python3 version
# 24.01.2026 - WhiteWolf
# 10.10.2026 - host standard: live TV / radios from the site's own pages (no third-party playlist any more), the TV
#   shows ("Műsoraink") -> episodes (YouTube through urlparser, own players direct), news sections and search with
#   First page / Jump / Next page and the last page; articles without a video as article rows (text in INFO); watched
#   flag (show -> episode), downloaded marker, favourites (also rows of version 1.2), sidecar, "Title (YYYY-MM-DD)"
#   naming, INFO from the site's own data, local icons, default user agent, no "requests" import
###################################################
HOST_VERSION = "1.3"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://pannonrtv.com/"


MAIN_URL = "https://pannonrtv.com/"
# live streams: (title, page of the site, stream when the page does not name one, type)
LIVE_TAB = [("Pannon TV", MAIN_URL + "onlinepannon-tv", "https://stream2.nmih.hu:4102/live.m3u8", "video"),
            ("Pannon Rádió", MAIN_URL + "pannon-radio", "http://stream2.nmih.hu:4120/live.mp3", "audio"),  # NOSONAR - the radio server has no https
            ("Szabadkai Magyar Rádió", MAIN_URL + "szabadkai-magyar-radio-0", "http://stream2.nmih.hu:4110/live.mp3", "audio")]  # NOSONAR


class PannonRTV(GenericFolderWatchedScraperMixin, CBaseHostClass):

    # stable identity of a row (no state of an earlier menu)
    FAV_FIELDS = ("name", "category", "type", "url", "title", "raw_title", "icon", "desc", "date", "live", "f_live", "f_base")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "pannonrtv", "cookie": "pannonrtv.cookie"})
        self.MAIN_URL = MAIN_URL
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/pannonrtv135.png")
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("pannonrtv")
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getFullUrl(self, url, curUrl=None):
        return CBaseHostClass.getFullUrl(self, url.replace("&amp;", "&"), curUrl)

    def _meta(self, data, name):
        return self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''<meta[^>]+(?:property|name)=['"]%s['"][^>]+content=['"]([^'"]*)['"]''' % name)[0])

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            # live rows; rows of version 1.2 with a stream / YouTube url
            if not isinstance(cItem, dict) or cItem.get("live") or not cItem.get("url", "").startswith(MAIN_URL):
                return ""
            path = re.sub(r"^https?://[^/]+", "", cItem.get("url", "")).split("?")[0].rstrip("/")
            if cItem.get("type") == "video" and path:
                return "video:%s" % path
            if cItem.get("category") == "list_items" and path.startswith("/tv/"):
                return "folder:%s" % path
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("PannonRTV.listMainMenu")
        for title, url, stream, kind in LIVE_TAB:
            params = {"name": "category", "good_for_fav": True, "live": True, "f_live": True, "title": title, "url": url, "icon": self.DEFAULT_ICON_URL,
                      "desc": "%s - %s" % (title, _("Live"))}
            if kind == "audio":
                self.addAudio(params)
            else:
                self.addVideo(params)
        MAIN_CAT_TAB = [{"category": "list_shows", "title": "Műsoraink", "url": MAIN_URL + "musoraink"},
                        {"category": "list_items", "title": "Legfrissebb", "url": MAIN_URL + "legfrissebb"},
                        {"category": "list_sections", "title": "Rovatok", "url": MAIN_URL}]
        for item in MAIN_CAT_TAB:
            item.update({"name": "category", "good_for_fav": True})
            self.addDir(item)
        self.listsTab(self.searchItems(), cItem)

    def listSections(self, cItem):
        printDBG("PannonRTV.listSections")
        sts, data = self.getPage(MAIN_URL)
        if not sts:
            return
        seen = set()
        for url, title in re.findall(r'''<a[^>]+href=['"](/(?:rovatok/[a-z0-9-]+|vesti-na-srpskom))['"][^>]*>([^<]+)</a>''', data):
            title = self.cleanHtmlStr(title)
            if title and url not in seen:
                seen.add(url)
                self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})

    def _page(self, cItem):
        try:
            if "page" not in cItem and not cItem.get("f_base"):
                # "Következő oldal" rows of version 1.2: the site's 0-based page in the url
                return int(self.cm.ph.getSearchGroups(cItem.get("url", ""), r"[?&]page=(\d+)")[0] or 0) + 1
            return max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            return 1

    def _pagedUrl(self, cItem):
        # the site counts its pages from 0 ("?page=0" = first page)
        base = cItem.get("f_base") or re.sub(r"[?&]page=\d+", "", cItem["url"])
        sep = "&" if "?" in base else "?"
        return base, base + sep + "page={page}"

    def _addPager(self, cItem, data, page, tpl, base):
        lastPage = self.cm.ph.getSearchGroups(data, r'''pager__item--last['"][^>]*>\s*<a[^>]+href=['"][^'"]*?page=(\d+)''')[0]
        lastPage = int(lastPage) + 1 if lastPage.isdigit() else 0
        hasNext = "pager__item--next" in data
        # Jump / First page give the site's page (0-based) in the url: the list builds its url from "page" (1-based)
        addPagingItems(self, dict(stripPagerKeys(dict(cItem)), f_base=base), page, hasNext, lastPage, tpl)

    def listShows(self, cItem):
        printDBG("PannonRTV.listShows")
        page = self._page(cItem)
        base, tpl = self._pagedUrl(cItem)
        sts, data = self.getPage(tpl.format(page=page - 1) if page > 1 else base)
        if not sts:
            return
        for item in data.split("view-musorok-page-page-1__row ")[1:]:
            url = self.cm.ph.getSearchGroups(item, r'''href=['"](/tv/[^'"]+)['"]''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "item-name-content"), ("</span", ">"), False)[1])
            if not url or not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'''<img[^>]+src=['"]([^'"]+)['"]''')[0]
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "paragraph-text-preview__field-text"), ("</div", ">"), False)[1])
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url),
                         "icon": self.getFullIconUrl(icon) if icon else self.DEFAULT_ICON_URL, "desc": desc})
        self._addPager(cItem, data, page, tpl, base)

    def _articleRows(self, data, search=False):
        rows = []
        marker = "<article class=\"node-article-search-result" if search else "<article class=\"node-article-rovatok-"
        for item in data.split(marker)[1:]:
            item = item.split("</article>", 1)[0]
            link = self.cm.ph.getDataBeetwenNodes(item, ("<a", ">", "__title-link"), ("</a", ">"))[1] or \
                self.cm.ph.getDataBeetwenNodes(item, ("<a", ">", "bookmark"), ("</a", ">"))[1]
            url = self.cm.ph.getSearchGroups(link, r'''href=['"]([^'"]+)['"]''')[0]
            title = self.cleanHtmlStr(link)
            if not url or not title or "/koz/" in url:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'''data-src=['"]([^'"]+)['"]''')[0] or self.cm.ph.getSearchGroups(item, r'''<img[^>]+src=['"](/[^'"]+)['"]''')[0]
            day = self.cm.ph.getSearchGroups(item, r'''(\d{4})[-.]\s*(\d\d)[-.]\s*(\d\d)''', 3)
            date = "-".join(day) if day[0] else ""
            hours = self.cm.ph.getSearchGroups(item, r'''date--hours['"]>\s*([0-9:]+)''')[0] or self.cm.ph.getSearchGroups(item, r'''\d\d\.\s*-\s*(\d\d:\d\d)''')[0]
            teaser = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "field-teaser-text"), ("</div", ">"), False)[1])
            isVideo = 'class="video"' in item
            rows.append({"url": self.getFullUrl(url), "title": title, "icon": self.getFullIconUrl(icon) if icon else "", "date": date,
                         "desc": "[/br]".join([x for x in (" ".join([x for x in ("%s.%s.%s" % (date[8:10], date[5:7], date[:4]) if date else "", hours) if x]), teaser) if x]),
                         "video": isVideo or "/tv/" in url})
        return rows

    def listItems(self, cItem, search=False):
        printDBG("PannonRTV.listItems [%s]" % cItem.get("url", ""))
        page = self._page(cItem)
        base, tpl = self._pagedUrl(cItem)
        sts, data = self.getPage(tpl.format(page=page - 1) if page > 1 else base)
        if not sts:
            return
        for row in self._articleRows(data, search):
            params = {"name": "category", "good_for_fav": True, "url": row["url"], "raw_title": row["title"], "icon": row["icon"] or self.DEFAULT_ICON_URL,
                      "desc": row["desc"], "date": row["date"]}
            if row["video"]:
                # titles of the news shows already carry their date ("Híradó – 2026.10.09. 20.00h")
                hasDate = row["date"] and row["date"][:4] in row["title"]
                params["title"] = normalizeMediathekTitle(row["title"], date="" if hasDate else row["date"])
                self.addVideo(params)
            else:
                params["title"] = row["title"]
                self.addArticle(params)
        self._addPager(cItem, data, page, tpl, base)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("PannonRTV.listSearchResult [%s]" % searchPattern)
        url = MAIN_URL + "search?text=" + urllib_quote_plus(searchPattern)
        self.listItems({"name": "category", "category": "list_search", "url": url, "f_base": url}, True)
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No matching entries found."))

    ###################################################
    # links
    ###################################################
    def _getLiveLinks(self, cItem):
        url = cItem["url"]
        fallback = next((x[2] for x in LIVE_TAB if x[1] == url), "")
        stream = ""
        sts, data = self.getPage(url)
        if sts:
            stream = self.cm.ph.getSearchGroups(data, r'''<source[^>]+src=['"](https?://[^'"]+?\.m3u8[^'"]*)['"]''')[0] or \
                self.cm.ph.getSearchGroups(data, r'''(https?://[^'"\s<>)]+?/live\.mp3)''')[0]
        stream = stream or fallback
        if not stream:
            return []
        if ".m3u8" in stream:
            return getDirectM3U8Playlist(stream, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
        return [{"name": "mp3", "url": stream, "need_resolve": 0}]

    def _getPageLinks(self, url):
        linksTab = []
        sts, data = self.getPage(url)
        if not sts:
            return linksTab
        content = self.cm.ph.getDataBeetwenMarkers(data, "<section id=\"content\"", "region-sidebar-second")[1] or data
        seen = set()
        for frame in re.findall(r'''<iframe[^>]+src=['"]([^'"]+)['"]''', content):
            frame = self.getFullUrl(frame)
            if "/media/oembed" in frame:
                frame = urllib_unquote(self.cm.ph.getSearchGroups(frame, r"[?&]url=([^&]+)")[0])
            if not self.cm.isValidUrl(frame) or frame in seen or "googletagmanager" in frame:
                continue
            seen.add(frame)
            if 1 == self.up.checkHostSupport(frame):
                linksTab.append({"name": self.up.getHostName(frame), "url": frame, "need_resolve": 1})
        for src in re.findall(r'''<source[^>]+src=['"]([^'"]+)['"]''', content):
            src = self.getFullUrl(src)
            if src in seen or not self.cm.isValidUrl(src):
                continue
            seen.add(src)
            if ".m3u8" in src:
                linksTab.extend(getDirectM3U8Playlist(src, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))
            elif ".mp4" in src:
                linksTab.append({"name": "mp4", "url": src, "need_resolve": 0})
        return linksTab

    def _getLegacyLinks(self, cItem):
        # favourites of version 1.2: the live rows (stream2.nmih.hu / a third-party playlist url) and the
        # "Youtube videó" row of an article (the YouTube player url)
        url = cItem.get("url", "")
        if url.startswith("//"):
            url = "https:" + url
        live = next((x for x in LIVE_TAB if x[0] == cItem.get("title") or x[2] == url), None)
        if live:
            return self._getLiveLinks({"url": live[1]})
        if not self.cm.isValidUrl(url):
            return []
        if 1 == self.up.checkHostSupport(url):
            return [{"name": self.up.getHostName(url), "url": url, "need_resolve": 1}]
        if ".m3u8" in url:
            return getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
        return [{"name": "direct link", "url": url, "need_resolve": 0}]

    def getLinksForVideo(self, cItem):
        printDBG("PannonRTV.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = cItem.get("url", "")
        if cItem.get("f_live"):
            return self._getLiveLinks(cItem)
        if url.startswith(MAIN_URL):
            linksTab = self._getPageLinks(url)
        else:
            linksTab = self._getLegacyLinks(cItem)
        if not linksTab:
            SetIPTVPlayerLastHostError(_("No valid links available."))
        return applySidecarToLinks(linksTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, url):
        printDBG("PannonRTV.getVideoLinks [%s]" % url)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecarFromUrlMeta(url, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("PannonRTV.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("raw_title", cItem.get("title", ""))
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        url = cItem.get("url", "")
        if cItem.get("live"):
            otherInfo["status"] = _("Live")
        elif url.startswith(MAIN_URL):
            sts, data = self.getPage(url)
            if sts:
                title = self._meta(data, "og:title") or title
                teaser = self._meta(data, "og:description")
                body = self.cm.ph.getDataBeetwenMarkers(data, "<section id=\"content\"", "region-sidebar-second")[1]
                paragraphs = [self.cleanHtmlStr(x) for x in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)]
                paragraphs = [x for x in paragraphs if x and x != teaser]
                text = "[/br]".join([x for x in [teaser] + paragraphs[:30] if x]) or text
                image = self.cm.ph.getSearchGroups(data, r'''<meta[^>]+property=['"]og:image['"][^>]+content=['"]([^'"]+)['"]''')[0]
                if image:
                    icon = self.getFullIconUrl(image)
            if cItem.get("date"):
                otherInfo["released"] = cItem["date"]
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon or self.DEFAULT_ICON_URL}], "other_info": otherInfo}]

    def listLegacy(self, cItem):
        # folder favourites of version 1.2 (any row could be saved)
        category = cItem.get("category", "")
        printDBG("PannonRTV.listLegacy [%s] [%s]" % (category, cItem.get("url", "")))
        if category == "list_filters":
            # "Kategóriák" (next False) -> the sections; a section with sub-sections (next True) -> its list
            if cItem.get("next") is True:
                self.listItems({"name": "category", "category": "list_items", "url": cItem.get("url", "")})
            else:
                self.listSections(cItem)
        elif category == "cont_search":
            # "Következő oldal" of a search: "page" = the site's 0-based page
            url = MAIN_URL + "search?text=" + urllib_quote_plus(cItem.get("searchPattern", ""))
            try:
                page = int(cItem.get("page", 0)) + 1
            except (TypeError, ValueError):
                page = 1
            self.listItems({"name": "category", "category": "list_search", "url": url, "f_base": url, "page": page}, True)
        elif category == "explore_item":
            # an article (its paragraphs were rows): the article as one row, a video row when it has a player
            url = cItem.get("url", "")
            if url.startswith("//"):
                url = "https:" + url
            params = {"name": "category", "good_for_fav": True, "title": cItem.get("title", ""), "url": url,
                      "icon": cItem.get("icon") or self.DEFAULT_ICON_URL, "desc": cItem.get("desc", "")}
            sts, data = self.getPage(url)
            content = self.cm.ph.getDataBeetwenMarkers(data, "<section id=\"content\"", "region-sidebar-second")[1] if sts else ""
            if "<iframe" in content or "<source" in content:
                self.addVideo(params)
            else:
                self.addArticle(params)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("PannonRTV.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("PannonRTV.handleService: name[%s], category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_shows":
            self.listShows(self.currItem)
        elif category == "list_sections":
            self.listSections(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_search":
            self.listItems(self.currItem, True)
        elif category in ("list_filters", "explore_item", "cont_search"):
            self.listLegacy(self.currItem)
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
        CHostBase.__init__(self, PannonRTV(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("pannonrtv")

    def withArticleContent(self, cItem):
        return cItem.get("type", "") in ("video", "audio", "article")
