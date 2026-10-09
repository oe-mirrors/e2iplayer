# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# 07.05.2026 - schwatter
# 08.10.2026 - host standard: category tree and tags from the site, tag search, First page / Jump / Next page
#   with the last page, watched flag, downloaded marker, favourites, sidecar, INFO with the site's data,
#   "Title (YYYY-MM-DD)" naming, best quality first
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
###################################################

PER_PAGE = 15  # the site pages with an offset: <list>/filme-15.htm, <tag>/videos-30.htm ...


def gettytul():
    return "https://www.gaskrank.tv/"


class GaskrankTV(GenericFolderWatchedScraperMixin, CBaseHostClass):

    # stable identity of a row (views / rating in desc change)
    FAV_FIELDS = ("name", "category", "type", "url", "title", "raw_title", "icon", "date")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "gaskrank.tv", "cookie": "gaskrank.tv.cookie"})
        self.MAIN_URL = "https://www.gaskrank.tv/"
        self.DEFAULT_ICON_URL = "https://static.gaskrank.tv/gaskrank2.png"

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HTTP_HEADER.update({"Accept": "text/html", "Referer": self.getMainUrl()})

        self.defaultParams = {"header": self.HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("gaskrank")
        self.wfInitFolderCache()

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("type") == "video":
                url = cItem.get("url", "")
                return "video:%s" % url if url else ""
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("type") == "video":
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("GaskrankTV.listMainMenu")
        MAIN_CAT_TAB = [{"category": "list_items", "title": _("Latest"), "url": self.getFullUrl("/tv/motorrad-videos/"), "good_for_fav": True},
                        {"category": "list_items", "title": _("Top rated"), "url": self.getFullUrl("/tv/user-voted/"), "good_for_fav": True},
                        {"category": "list_items", "title": _("Most viewed"), "url": self.getFullUrl("/tv/top-videos/"), "good_for_fav": True},
                        {"category": "list_cats", "title": _("Categories"), "url": self.getFullUrl("/tv/")},
                        {"category": "list_tags", "title": _("Tags"), "url": self.getFullUrl("/tv/tags/")}]
        self.listsTab(MAIN_CAT_TAB + self.searchItems(), cItem)

    def _getCategoryTree(self):
        # the nested <ul> menu "Video Kategorien" -> [{'title', 'url', 'children': [...]}]
        sts, data = self.getPage(self.getFullUrl("/tv/"))
        if not sts:
            return []
        data = self.cm.ph.getDataBeetwenMarkers(data, "<h3>Video Kategorien</h3>", "gkBoxHead", False)[1]
        root = []
        stack = [root]
        last = None
        for m in re.finditer(r'<ul[^>]*>|</ul>|<a[^>]+href="([^"]+)"[^>]*>([^<]*)</a>', data):
            token = m.group(0)
            if token.startswith("<ul"):
                stack.append(last["children"] if last is not None else stack[-1])
                last = None
            elif token == "</ul>":
                if len(stack) > 1:
                    stack.pop()
                last = None
            else:
                title = self.cleanHtmlStr(m.group(2))
                if not title:
                    continue
                last = {"title": title, "url": self.getFullUrl(m.group(1)), "children": []}
                stack[-1].append(last)
        return root

    @staticmethod
    def _findNode(nodes, url):
        for node in nodes:
            if node["url"] == url:
                return node
            found = GaskrankTV._findNode(node["children"], url)
            if found is not None:
                return found
        return None

    def listCategories(self, cItem):
        printDBG("GaskrankTV.listCategories [%s]" % cItem.get("url", ""))
        tree = self._getCategoryTree()
        url = cItem.get("url", "")
        if url.rstrip("/").endswith("/tv"):
            nodes = tree
        else:
            node = self._findNode(tree, url)
            if node is None:
                return
            nodes = node["children"]
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": _("All videos"), "url": url})
        for node in nodes:
            category = "list_cats" if node["children"] else "list_items"
            self.addDir({"name": "category", "category": category, "good_for_fav": True, "title": node["title"], "url": node["url"]})

    def listTags(self, cItem):
        printDBG("GaskrankTV.listTags")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for url, title in re.findall(r'<a class="tc" href="(/tv/tags/[^"]+/)">([^<]+)</a>', data):
            if url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url)})

    ###################################################
    # videos
    ###################################################
    def listItems(self, cItem):
        printDBG("GaskrankTV.listItems [%s]" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        baseUrl = cItem["url"]
        pgWord = cItem.get("pg_word", "filme")
        url = baseUrl
        if page > 1:
            url = baseUrl.rstrip("/") + "/%s-%d.htm" % (pgWord, (page - 1) * PER_PAGE)

        sts, data = self.getPage(url)
        if not sts:
            return

        lastPage = 0
        m = re.search(r'href="[^"]+?/(filme|videos)-(\d+)\.htm"><i class="icon-forward"', data)
        if m:
            pgWord = m.group(1)
            lastPage = int(m.group(2)) // PER_PAGE + 1
        else:
            m = re.search(r'<link rel="next" href="[^"]+?/(filme|videos)-\d+\.htm"', data)
            if m:
                pgWord = m.group(1)
        hasNext = bool(re.search(r'<link rel="next" href=', data)) or (lastPage > page)

        tmp = data.split('<table class="gkPager">')
        data = tmp[1] if len(tmp) > 2 else data
        count = 0
        seen = set()
        for block in data.split('<div class="gkVidCon"')[1:]:
            m = re.search(r'<a[^>]+href="([^"]+\.htm)"><img[^>]+src="([^"]+)"', block)
            if not m:
                continue
            videoUrl = self.getFullUrl(m.group(1))
            if videoUrl in seen:
                continue  # the tag pages list some videos twice
            seen.add(videoUrl)
            icon = self.getFullUrl(m.group(2))
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(block, '<div class="gkVidConL">', "</div>", False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<img[^>]+alt="([^"]+)"')[0])
            if not title:
                continue
            date = ""
            dm = re.search(r'gkVidMetaR">\s*(\d{2})\.(\d{2})\.(\d{4})\s*<', block)
            if dm:
                date = "%s-%s-%s" % (dm.group(3), dm.group(2), dm.group(1))
            views = self.cm.ph.getSearchGroups(block, r'icon-eye-open[^>]*></i>\s*([0-9.]+)')[0]
            rating = self.cm.ph.getSearchGroups(block, r'icon-star[^>]*></i>\s*([0-9,]+)')[0]
            desc = ["%s.%s.%s" % dm.groups() if dm else ""]
            if views:
                desc.append(_("%s views") % views)
            if rating:
                desc.append(_("Rating: %s") % (rating + "/5"))
            if 'label-important">HD<' in block:
                desc.append("HD")
            count += 1
            self.addVideo({"good_for_fav": True, "title": normalizeMediathekTitle(title, date=date), "raw_title": title, "url": videoUrl,
                           "icon": icon, "date": date, "desc": " | ".join([x for x in desc if x])})

        params = dict(cItem, pg_word=pgWord, desc="")
        addPagingItems(self, params, page, bool(count) and hasNext, lastPage, baseUrl.replace("{", "%7B").replace("}", "%7D"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        # the site's own full text search answers no hits at all - the tag pages are the search
        printDBG("GaskrankTV.listSearchResult [%s]" % searchPattern)
        pattern = (searchPattern or "").strip().lower()
        if not pattern:
            return
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("/tv/tags/%s/" % urllib_quote_plus(pattern))})
        self.listItems(cItem)
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No matching entries found."))

    ###################################################
    # video page
    ###################################################
    def _parseVideoPage(self, data):
        info = {"sources": [], "title": "", "desc": "", "icon": "", "date": "", "author": "", "duration": "", "views": "", "rating": ""}
        video = self.cm.ph.getDataBeetwenMarkers(data, "<video", "</video>", False)[1]
        for tag in re.findall(r"<source[^>]+>", video):
            src = self.cm.ph.getSearchGroups(tag, r'''src=['"]([^'"]+)['"]''')[0]
            if not src:
                continue
            res = self.cm.ph.getSearchGroups(tag, r'''res=['"]?([0-9]+)''')[0]
            label = self.cm.ph.getSearchGroups(tag, r'''label=['"]([^'"]+)['"]''')[0]
            info["sources"].append((int(res) if res else 0, label, self.getFullUrl(src)))
        info["sources"].sort(key=lambda x: -x[0])
        info["title"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<h1[^>]*>(.*?)</h1>')[0]) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:title" content="([^"]*)"')[0])
        tmp = data.split("<h3>Details:", 1)[-1] if "<h3>Details:" in data else ""
        tmp = self.cm.ph.getDataBeetwenMarkers(tmp, '<div class="gkPageBoxCont">', "</div>", False)[1]
        info["desc"] = self.cleanHtmlStr(tmp.replace("<br />", "[/br]").replace("<br>", "[/br]")).strip()
        if not info["desc"]:
            info["desc"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        info["icon"] = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        m = re.search(r"Video von:\s*(.*?)\s*\|\s*vom:\s*(\d{2})\.(\d{2})\.(\d{4})", data)
        if m:
            info["author"] = self.cleanHtmlStr(m.group(1))
            info["date"] = "%s-%s-%s" % (m.group(4), m.group(3), m.group(2))
        info["duration"] = self.cm.ph.getSearchGroups(data, r"Laufzeit:\s*([0-9:]+)")[0]
        info["views"] = self.cm.ph.getSearchGroups(data, r'<div class="gkRight">\s*<i class="icon-eye-open[^>]*></i>\s*([0-9.]+)')[0]
        rating = self.cm.ph.getSearchGroups(data, r'id="vote-sum"[^>]*>([0-9,]+)<')[0]
        if rating:
            info["rating"] = rating + "/5"
        return info

    def getLinksForVideo(self, cItem):
        printDBG("GaskrankTV.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = cItem.get("url", "")
        if not self.cm.isValidUrl(url):
            return []
        sts, data = self.getPage(url)
        if not sts:
            return []
        info = self._parseVideoPage(data)
        if not info["sources"]:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        meta = {"User-Agent": self.HTTP_HEADER["User-Agent"], "Referer": url}
        linksTab = []
        for res, label, src in info["sources"]:
            linksTab.append({"name": "MP4 %s" % (label or ("%dp" % res if res else "")), "url": strwithmeta(src, meta), "need_resolve": 0})
        return applySidecarToLinks(linksTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), info["desc"]))

    def getArticleContent(self, cItem):
        printDBG("GaskrankTV.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("raw_title", cItem.get("title", ""))
        text = ""
        icon = cItem.get("icon", "")
        otherInfo = {}
        if cItem.get("date"):
            otherInfo["released"] = cItem["date"]
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info = self._parseVideoPage(data)
            title = info["title"] or title
            text = info["desc"]
            icon = info["icon"] or icon
            for key, src in (("released", "date"), ("duration", "duration"), ("views", "views"), ("rating", "rating"), ("creator", "author")):
                if info[src]:
                    otherInfo[key] = info[src]
        if not text:
            text = cItem.get("desc", "")
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")

        self.currList = []

        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_cats":
            self.listCategories(self.currItem)
        elif category == "list_tags":
            self.listTags(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category in ("search", "search_next_page"):
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
        CHostBase.__init__(self, GaskrankTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("gaskrank")

    def withArticleContent(self, cItem):
        return cItem.get("type", "") == "video"
