# -*- coding: utf-8 -*-
# Last Modified: 17.08.2025
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://zaluknij.cc/"


class Zaluknij(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Zaluknij", "cookie": "Zaluknij.cookie"})
        self.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0"
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "text/html"}
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "public/dist/images/logozaluknijcccc.png"
        self.MAIN_URL = None

    def menu(self):
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "movies", "title": _("Movies")}, {"category": "series", "title": _("Series")}, {"category": "search", "title": _("Search"), "search_item": True}, {"category": "search_history", "title": _("Search history")}]
        self.MOVIES = [{"category": "list_items", "title": _("Most recent"), "url": self.getFullUrl("filmy-online/?url=filmy-online%2F&sort=recent&page=1")}, {"category": "list_items", "title": _("Most popular"), "url": self.getFullUrl("filmy-online/?url=filmy-online%2F&sort=votes&page=1")}, {"category": "list_items", "title": _("By year"), "url": self.getFullUrl("filmy-online/?url=filmy-online%2F&sort=year&page=1")}, {"category": "list_items", "title": _("Views"), "url": self.getFullUrl("filmy-online/?url=filmy-online%2F&sort=views&page=1")}, {"category": "list_items", "title": _("Most rated"), "url": self.getFullUrl("filmy-online/?url=filmy-online%2F&sort=rate&page=1")}]
        self.SERIES = [{"category": "list_items", "title": _("All"), "url": self.getFullUrl("series/index/?url=series%2Findex%2F&sort=all_series&page=1")}, {"category": "list_items", "title": _("Latest"), "url": self.getFullUrl("series/index/?url=series%2Findex%2F&sort=latest_episodes&page=1")}, {"category": "list_items", "title": _("Most recent"), "url": self.getFullUrl("series/index/?url=series%2Findex%2F&sort=recent_series&page=1")}, {"category": "list_items", "title": _("Most popular"), "url": self.getFullUrl("series/index/?url=series%2Findex%2F&sort=popular_series&page=1")}, {"category": "list_items", "title": _("Views"), "url": self.getFullUrl("series/index/?url=series%2Findex%2F&sort=most_viewed_recently&page=1")}]

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem, nextCategory):
        printDBG("Zaluknij.listItems |%s|" % cItem)
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(htm, 'href="([^"]+)">Nast')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="card"', "</a>")
        if not data:
            data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-xs-6 col-sm-3 col-lg-2"', "</a>")
        if not data:
            data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-sm-4"', "</a>")
        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0]
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            se = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'class="tiny">([^<]+)')[0])
            if se:
                title = "%s - %s" % (title, se)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": nextCategory, "title": title.replace("amp;", ""), "url": url, "icon": icon})
            if not se and "serial" in url:
                params.update({"category": "list_episodes"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": cItem["url"] + nextPage.replace("amp;", "")})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("MovieDream.listEpisodes")
        icon = cItem["icon"]
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = re.findall(r'href="([^"]+)">\W(s\d+e\d+)', data, re.DOTALL)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": "%s %s" % (cItem["title"], title), "url": self.getFullUrl(url), "icon": icon, "desc": ""})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Zaluknij.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = "%swyszukiwarka?phrase=%s" % (gettytul(), urllib_quote(searchPattern))
        self.listItems(cItem, "video")

    def getLinksForVideo(self, cItem):
        printDBG("Zaluknij.getLinksForVideo [%s]" % cItem)
        urlTab = []
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="link-to-video">', "</td>")
        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0]
            urlTab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("Zaluknij.getVideourls [%s]" % videoUrl)
        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("Zaluknij.getArticleContent [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        otherInfo = {}
        if not sts:
            return []
        desc = self.cm.ph.getSearchGroups(data, 'class="description">([^<]+)')[0]
        title = cItem["title"]
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        return [{"title": self.cleanHtmlStr(title), "text": self.cleanHtmlStr(desc), "images": [{"title": "", "url": self.getFullUrl(icon)}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.menu()
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif "list_items" == category:
            self.listItems(self.currItem, "video")
        elif "list_episodes" == category:
            self.listEpisodes(self.currItem)
        elif "movies" == category:
            self.listsTab(self.MOVIES, self.currItem)
        elif "series" == category:
            self.listsTab(self.SERIES, self.currItem)
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
        CHostBase.__init__(self, Zaluknij(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_episodes"]
