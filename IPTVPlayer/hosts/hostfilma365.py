# -*- coding: utf-8 -*-
# Last Modified: 15.03.2026 - Mr.X
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://filma365.me/"


class Filma365(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Filma365", "cookie": "Filma365.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("static/img/logo-1734102348.png")
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies")}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("tv-shows")}, {"category": "list_items", "title": _("Top-IMDB"), "url": self.getFullUrl("top-imdb")}]

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        if url:
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
            return strwithmeta(self.getFullUrl(url), {"Cookie": cookieHeader, "User-Agent": self.HEADER.get("User-Agent")})
        return ""

    def listItems(self, cItem, nextCategory):
        printDBG("Filma365.listItems |%s|" % cItem)
        page = cItem.get("page", 1)
        sts, htm = self.getPage(cItem["url"] + "?page=" + str(page))
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'overflow-hidden">', '<div class="')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'data-src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": nextCategory, "title": title, "url": url, "icon": icon, "desc": ""})
            if "/tv/" in url:
                params.update({"category": "list_episodes"})
                self.addDir(params)
            else:
                self.addVideo(params)
        params = dict(cItem)
        params.update({"good_for_fav": False, "title": _("Next page"), "page": page + 1})
        self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Filma365.listEpisodes")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="grid-episode"', '<div class="text-center my-4">')
        if data:
            data = re.findall(r'<a href="([^"]+).*?alt="([^"]+)', data[0], re.DOTALL)
        for url, name in data:
            title = "{} - {}".format(cItem["title"], name)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url})
            self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("Filma365.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, data = self.getPage(cItem["url"], self.defaultParams)
        if not sts:
            return []
        data = re.findall(r"source&quot;:&quot;\s*(.*?)(?:&quot|&amp)", data, re.DOTALL)
        for url in data:
            url = url.replace(r"\/", "/").strip()
            if url in str(urltab):
                continue
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(self.getFullUrl(url), {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("Filma365.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return []

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem, "video")
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


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Filma365(), True, [])
