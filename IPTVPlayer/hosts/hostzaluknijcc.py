# -*- coding: utf-8 -*-
# Last Modified: 17.11.2025 - Mr.X
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
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "public/dist/images/lgbt.png"
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "movies", "title": _("Movies")}, {"category": "series", "title": _("Series")}] + self.searchItems()
        self.MOVIES = [{"category": "list_items", "title": _("Most recent"), "url": self.getFullUrl("filmy-online/?sort:date/")}, {"category": "list_items", "title": _("Most popular"), "url": self.getFullUrl("filmy-online/sort:vote/")}, {"category": "list_items", "title": _("By year"), "url": self.getFullUrl("filmy-online/sort:premiere/")}, {"category": "list_items", "title": _("Views"), "url": self.getFullUrl("filmy-online/sort:view/")}, {"category": "list_items", "title": _("Most rated"), "url": self.getFullUrl("filmy-online/sort:rate/")}]
        self.SERIES = [{"category": "list_items", "title": _("All"), "url": self.getFullUrl("seriale-online/index?url=seriale-online%2Findex&sort=all_series&page=1")}, {"category": "list_items", "title": _("Latest added"), "url": self.getFullUrl("seriale-online/index?url=seriale-online%2Findex&sort=latest_episodes&page=1")}, {"category": "list_items", "title": _("Most recent"), "url": self.getFullUrl("seriale-online/index?url=seriale-online%2Findex&sort=recent_series&page=1")}, {"category": "list_items", "title": _("Most popular"), "url": self.getFullUrl("seriale-online/index?url=seriale-online%2Findex&sort=popular_series&page=1")}, {"category": "list_items", "title": _("Views"), "url": self.getFullUrl("seriale-online/index?url=seriale-online%2Findex&sort=most_viewed_recently&page=1")}]

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("Zaluknij.listItems |%s|" % cItem)
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(htm, r"""href=['"]([^"']+)["'](?: data-pagenumber='\d+'>|>)Nast""")[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'role="listitem', "</a>") or self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-sm-4">', "</a>")
        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0]
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            se = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'meta-line">(.*?)</span>')[0])
            if se:
                title = "%s - %s" % (title, se)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title.replace("amp;", ""), "url": url, "icon": icon})
            if not se and "serial" in url:
                params.update({"category": "list_episodes"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": cItem["url"].split("?")[0] + nextPage.replace("amp;", "")})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Zaluknij.listEpisodes")
        icon = cItem["icon"]
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        desc = self.cm.ph.getSearchGroups(data, 'class="description">([^<]+)')[0]
        data = re.findall(r'href="([^"]+)">\W(s\d+e\d+)', data, re.DOTALL)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": "%s %s" % (cItem["title"], title), "url": self.getFullUrl(url), "icon": icon, "desc": desc})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Zaluknij.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = "%swyszukiwarka?phrase=%s" % (gettytul(), urllib_quote(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("Zaluknij.getLinksForVideo [%s]" % cItem)
        urltap = []
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'link-to-video">', "</td>")
        for item in data:
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0]
            urltap.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        return urltap

    def getVideoLinks(self, url):
        printDBG("Zaluknij.getVideourls [%s]" % url)
        return self.up.getVideoLinkExt(url)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "movies":
            self.listsTab(self.MOVIES, self.currItem)
        elif category == "series":
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
