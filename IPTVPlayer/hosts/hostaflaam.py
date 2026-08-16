# -*- coding: utf-8 -*-
# Last Modified: 28.09.2025 - Mr.X

import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc


def GetConfigList():
    return []


def gettytul():
    return "https://aflaam.com/"


class Aflaam(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Aflaam"})
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser="firefox")
        self.defaultParams = {"header": self.HTTP_HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("style/assets/images/logo.png")
        self.MENU = [
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("series")},
            {"category": "list_value", "title": "القسم", "s": "القسم"},
            {"category": "list_value", "title": _("Genres"), "s": "التصنيف"},
            {"category": "list_value", "title": _("Year"), "s": "سنة الإنتاج"}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("Aflaam.listItems |%s|" % cItem)
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r'href="([^"]+)" rel="next"')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="entry-box', "</h")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'data-src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'class="entry-title.*?>([^<]+)')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title, "url": url, "icon": icon})
            if "series" in url:
                params.update({"category": "list_items"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listValue(self, cItem):
        printDBG("Aflaam.Value |%s|" % cItem)
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], "</ul>")
        data = re.findall('href="([^"]+).*?>([^<]+)', data[0], re.DOTALL)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Aflaam.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem["url"] = self.getFullUrl("search?q=%s" % urllib_quote(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("Aflaam.getLinksForVideo [%s]" % cItem)
        urlTab = []
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        url = re.findall(r'Quality">.*?href="([^"]+)', data, re.DOTALL)
        if url:
            sts, data = self.getPage(url[0])
            if not sts:
                return []
        data = re.findall(r'<source\s+[^>]*src="([^"]+)"\s+[^>]*size="(\d+)"', data, re.DOTALL)
        for url, q in data:
            urlTab.append({"name": q, "url": url, "need_resolve": 0})
        return urlTab

    def getVideoLinks(self, url):
        printDBG("Aflaam.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return []

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.menu()
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif "list_items" == category:
            self.listItems(self.currItem)
        elif "list_value" == category:
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


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Aflaam(), True, [])
