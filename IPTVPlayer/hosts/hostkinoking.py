# -*- coding: utf-8 -*-
# Last Modified: 04.12.2025 - Mr.X
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://KinoKing.cc/"


class KinoKing(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "KinoKing", "cookie": "KinoKing.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "max_data_size": 1024 * 1024, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("index.php?genre=current-movies&filter=movies&view=grid&page=")}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("index.php?genre=recently-added&filter=series&view=grid&page=")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
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

    def listItems(self, cItem):
        printDBG("KinoKing.listItems |%s|" % cItem)
        url = cItem["url"]
        page = cItem.get("page", 1)
        sts, data = self.getPage(url if "?search" in url else url + str(page))
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="content-card', "</div></div>")
        for item in data:
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title">([^<]+)')[0])
            url = self.cm.ph.getSearchGroups(item, r"playMovie[^>](\d+)")[0] or self.cm.ph.getSearchGroups(item, r"""playContent[^>]\d+,\s*'[^']+',\s*(\d+)""")[0]
            if url:
                url = "%smovie.php?id=%s" % (gettytul(), url) if "playMovie" in item else "%sseries.php?id=%s" % (gettytul(), url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title, "url": url, "icon": icon})
            if "series" in url:
                params.update({"category": "list_seasons"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if "?search" not in url:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "page": page + 1})
            self.addDir(params)

    def Seasons(self, cItem):
        printDBG("KinoKing.Seasons")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="season', "content-card")[0]
        data = re.compile(r'href="([^"]+).*?Staffel\s*(\d+)', re.DOTALL).findall(data)
        for url, title in data:
            title = cItem["title"] + " - Season " + title
            url = self.getFullUrl("series.php" + url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "desc": desc})
            self.addDir(params)

    def Episodes(self, cItem):
        printDBG("KinoKing.Episodes")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        data = re.compile(r"""onclick="playEpisode[^>](\d+),\s*'([^']+)""", re.DOTALL).findall(data)

        for url, title in data:
            title = cItem["title"] + " - " + title
            url = gettytul() + "api/episode-navigation.php?episode_id=" + url
            self.getFullUrl("series.php" + url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url, "desc": url})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KinoKing.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("index.php?search=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("KinoKing.getLinksForVideo [%s]" % cItem)
        urltab = []
        link = cItem["url"]
        sts, data = self.getPage(link, self.defaultParams)
        if not sts:
            return []
        if "episode_id" in link:
            data = json.loads(data)
            url = data.get("links")[0]
        else:
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="movie-container">', " </div>")[0]
            url = self.cm.ph.getSearchGroups(data, 'src="([^"]+)')[0]
        if url:
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta("https:" + url if url.startswith("//") else url, {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("KinoKing.getVideoLinks [%s]" % videoUrl)
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
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.Seasons(self.currItem)
        elif category == "list_episodes":
            self.Episodes(self.currItem)
        elif category == "list_value":
            self.listValue(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, KinoKing(), True, [])
