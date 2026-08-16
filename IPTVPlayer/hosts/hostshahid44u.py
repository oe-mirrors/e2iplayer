# -*- coding: utf-8 -*-
# Based on the preparatory work of odem2014
# Last Modified: 04.10.2025 - Mr.X
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://shahid4uu.day/"


class Shahid44u(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Shahid44u", "cookie": "Shahid44u.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/popking159/softcam/refs/heads/master/shahid44u.png"
        self.MAIN_URL = None

    def menu(self):
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "movies", "title": _("Movies")}, {"category": "series", "title": _("Series")}, {"category": "list_items", "title": _("TV Show"), "url": self.getFullUrl("category/برامج-تلفزيونية")}, {"category": "list_items", "title": "عروض مصارعة", "url": self.getFullUrl("category/عروض-مصارعة")}] + self.searchItems()
        self.MOVIES = [{"category": "list_items", "title": "افلام اجنبي", "url": self.getFullUrl("category/افلام-اجنبي")}, {"category": "list_items", "title": "افلام هندي", "url": self.getFullUrl("category/افلام-هندي")}, {"category": "list_items", "title": "افلام انمي", "url": self.getFullUrl("category/افلام-انمي")}, {"category": "list_items", "title": "افلام اسيوية", "url": self.getFullUrl("category/افلام-اسيوية")}, {"category": "list_items", "title": "افلام تركية", "url": self.getFullUrl("category/افلام-تركية")}, {"category": "list_items", "title": "افلام عربي", "url": self.getFullUrl("category/افلام-عربي")}]
        self.SERIES = [{"category": "list_items", "title": "مسلسلات اجنبي", "url": self.getFullUrl("category/مسلسلات-اجنبي")}, {"category": "list_items", "title": "مسلسلات انمي", "url": self.getFullUrl("category/مسلسلات-انمي")}, {"category": "list_items", "title": "مسلسلات تركية", "url": self.getFullUrl("category/مسلسلات-تركية")}, {"category": "list_items", "title": "مسلسلات اسيوية", "url": self.getFullUrl("category/مسلسلات-اسيوية")}, {"category": "list_items", "title": "مسلسلات مدبلجة", "url": self.getFullUrl("category/مسلسلات-مدبلجة")}, {"category": "list_items", "title": "مسلسلات عربي", "url": self.getFullUrl("category/مسلسلات-عربي")}, {"category": "list_items", "title": "مسلسلات هندية", "url": self.getFullUrl("category/مسلسلات-هندية")}]

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if any(ord(c) > 127 for c in baseUrl):
            baseUrl = urllib_quote(baseUrl, safe="://")
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == "":
            return ""
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {"Cookie": cookieHeader, "User-Agent": self.HEADER.get("User-Agent")})

    def listItems(self, cItem, nextCategory):
        printDBG("Shahid44u.listItems |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r"updateQuery\('page',\s*([0-9]+)\)")[-1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="col-6 col-md-4', "</a>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, """href=['"]([^'"]+)""")[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r"""background-image:\s*url\(([^'")]+)[^'"]*['"]""")[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title">([^<]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'class="description">([^<]+)')[0])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": nextCategory, "title": title, "url": url, "icon": icon, "desc": desc})
            self.addVideo(params)
        if nextPage:
            nextPage = cItem["url"].split("?")[0] + "?page=" + nextPage
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Shahid44u.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("search?s=%s" % urllib_quote(searchPattern, safe="://"))
        self.listItems(cItem, "video")

    def getLinksForVideo(self, cItem):
        printDBG("Shahid44u.getLinksForVideo [%s]" % cItem)
        urltab = []
        url = cItem["url"].replace("film", "watch").replace("episode", "watch").replace("post", "watch")
        sts, data = self.getPage(url, self.defaultParams)
        if not sts:
            return []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "JSON.parse", ";")[0]
        data = re.compile(r'url":"([^"]+)', re.DOTALL).findall(data)
        for url in data:
            url = url.replace(r"\/", "/")
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta("https:" + url if url.startswith("//") else url, {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, url):
        printDBG("Shahid44u.getVideoLinks [%s]" % url)
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
            self.listItems(self.currItem, "video")
        elif "movies" == category:
            self.listsTab(self.MOVIES, self.currItem)
        elif "series" == category:
            self.listsTab(self.SERIES, self.currItem)
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
        CHostBase.__init__(self, Shahid44u(), True, [])
