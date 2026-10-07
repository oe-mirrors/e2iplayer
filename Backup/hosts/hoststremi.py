# -*- coding: utf-8 -*-
# Last Modified: 27.02.2026 - Mr.X
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://stremi.eu/"


class Stremi(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Stremi", "cookie": "Stremi.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + "wp-content/uploads/2025/08/ChatGPT-Image-8-%CE%91%CF%85%CE%B3-2025-11_08_29-%CF%80.%CE%BC.png"
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies")}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("tvshows")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("Stremi.listItems |%s|" % cItem)
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(htm, r'href="([^"]+)"\s*><span class="fas\s*fa-chevron-right">')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="item-box"', "</div></div>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'data-original="([^"]+)')[0])
            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0]
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "videos", "title": self.cleanHtmlStr(title), "url": url, "icon": icon, "desc": ""})
            if "tvshows" in url:
                params.update({"category": "list_seasons"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("Stremi.listSeasons")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'desc">(.*?)</div>')[0])
        data = re.compile(r"<ul\s*id='season-listep-(\d+)(.*?)</ul>", re.DOTALL).findall(data)
        for se, ep in data:
            title = "%s %s" % (_("Season"), se)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "ep": ep, "desc": desc})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Stremi.listEpisodes")
        ep = cItem["ep"]
        data = re.compile(r"class='ep-(\d+).*?href='([^']+).*?src='([^']+).*?ep-title'>([^<]+)", re.DOTALL).findall(ep)
        for ep, url, icon, name in data:
            title = "%s %s - %s" % (_("Episode"), ep, name)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url, "icon": icon, "episode": ep})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Stremi.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("?s=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("Stremi.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return []
        data = re.findall('option value="([^"]+)', htm, re.DOTALL)
        if not data:
            data = re.findall("setPlayer[^>]'([^']+)", htm, re.DOTALL)
        for url in data:
            if "vidsrc.xyz" in url:
                continue
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": gettytul(), "Episode": cItem.get("episode", "")}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, url):
        printDBG("Stremi.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
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
            self.listSeasons(self.currItem)
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
        CHostBase.__init__(self, Stremi(), True, [])
