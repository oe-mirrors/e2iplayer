# -*- coding: utf-8 -*-
# Last Modified: 26.12.2025 - fixed pycurl for py3 version - by Mr.X
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://bflix.sh/"


class Bflix(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Bflix", "cookie": "Bflix.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + "images/logo.png"
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies/")}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("tv-series/")}, {"category": "list_items", "title": _("Top-IMDB"), "url": self.getFullUrl("top-imdb/")}, {"category": "list_value", "title": _("Genres"), "s": "Genre<"}, {"category": "list_value", "title": _("Country"), "s": "Country<"}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("Bflix.listItems |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, 'class="page-item active">.*?class="page-item"><a href="([^"]+)')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="film">', "</span></div>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getAllItemsBeetwenMarkers(item, '<div class="start">', "</div>")[0])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title, "url": url, "icon": icon, "desc": desc})
            if "serie" in url:
                params.update({"category": "list_seasons"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("Bflix.listSeasons")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'cts-wrapper">([^<]+)')[0])
        data = re.findall(r'data-ss="(\d+).*?data-id="([^"]+)', data, re.DOTALL)
        for title, url in data:
            url = "%sajax/ajax.php?episode=%s" % (gettytul(), url)
            title = cItem["title"] + " - %s %s" % (_("Season"), title)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "icon": cItem["icon"], "desc": desc})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Bflix.listEpisodes")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = re.findall(r'href="([^"]+).*?class="num">(.*?)</a>', data)
        for url, title in data:
            title = cItem["title"] + " - %s" % self.cleanHtmlStr(title)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url})
            self.addVideo(params)

    def listValue(self, cItem):
        printDBG("Bflix.listValue")
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], "</ul>")[0]
        if data:
            data = re.findall('href="([^"]+).*?>([^<]+)', data, re.DOTALL)
            for url, title in data:
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
                self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("Bflix.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return []
        url = self.cm.ph.getSearchGroups(htm, r"const pl_url = '([^']+)")[0]
        sts, htm = self.getPage(url)
        if not sts:
            return []
        data = re.findall('data-srv="([^"]+).*?data-id="([^"]+)', htm, re.DOTALL)
        for title, url in data:
            if "etu" in title:
                continue
            urltab.append({"name": title, "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, url):
        printDBG("Bflix.getVideoLinks [%s]" % url)
        params = dict(self.defaultParams)
        params["no_redirection"] = True
        sts, dummy = self.cm.getPage(url, params)
        if self.cm.meta.get("location"):
            return self.up.getVideoLinkExt(self.cm.meta.get("location"))
        return url

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Bflix.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = "%ssearch?keyword=%s" % (self.MAIN_URL, urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
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


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Bflix(), True, [])
