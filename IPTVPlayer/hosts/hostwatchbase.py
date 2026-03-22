# -*- coding: utf-8 -*-
# Last Modified: 20.03.2026 - Mr.X
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://watchbase.mov/"


class WatchBase(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "WatchBase", "cookie": "WatchBase.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "assets/image/logo.png"
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies")}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("series")}, {"category": "list_items", "title": _("Newest Episodes"), "url": self.getFullUrl("episodes")}, {"category": "list_value", "title": _("Genres"), "s": ">Genres<"}, {"category": "list_value", "title": _("A-Z"), "s": 'class="flex w-full text-white">'}, {"category": "list_value", "title": _("Year"), "s": ">Jahre<"}, {"category": "list_items", "title": _("Collections"), "url": self.getFullUrl("collections")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("WatchBase.listItems |%s|" % cItem)
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r'href="([^"]+)"\s*rel="next">')[0]
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="card-wrapper">', "</div>")
        for item in items:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0]
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": self.cleanHtmlStr(title), "url": url, "icon": icon, "desc": ""})
            if "series" in url:
                params.update({"category": "list_seasons"})
                self.addDir(params)
            elif "collection" in url:
                params.update({"category": "list_items"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("WatchBase.listSeasons |%s|" % cItem)
        icon = cItem["icon"]
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        se = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="season-episodes"', "justify-end")
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'leading-6">([^<]+)')[0])
        data = re.findall(r"Staffel\s*(\d+)", data, re.DOTALL)
        for seasons in data:
            title = cItem["title"] + " - Staffel " + seasons
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "se": se, "icon": icon, "seasons": seasons, "desc": desc})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("WatchBase.listEpisodes |%s|" % cItem)
        seasons = cItem["seasons"]
        se = cItem["se"]
        if not seasons and not se:
            return
        data = re.findall(r'href\s*=\s*"([^"]*season-%s[^"]*)".*?tracking-widest">([^<]+).*?px-2">([^<]+)' % seasons, se[0], re.DOTALL)
        for url, ep, name in data:
            title = cItem["title"] + " - %s - %s" % (ep, name)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url})
            self.addVideo(params)

    def listValue(self, cItem):
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], "</div>")[0]
        data = re.compile('href="([^"]+).*?>([^<]+)', re.DOTALL).findall(data)
        if data:
            for url, title in data:
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
                self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("WatchBase.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("search?keywords=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("WatchBase.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return []
        data = re.findall(r'data-type="embeded"\s*data-url="([^"]+)', htm, re.DOTALL)
        for url in data:
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, url):
        printDBG("WatchBase.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return []

    def getArticleContent(self, cItem):
        printDBG("WatchBase.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<p class="leading-6">([^<]+)')[0])
        actors = re.findall('href="/person/.*?text-sm">([^<]+)</span>', data, re.DOTALL)
        if actors:
            otherInfo["actors"] = ", ".join(actors)
        released = re.findall(r'Veröffentlicht.*?text-sm">([^<]+)</p>', data, re.DOTALL)
        if released:
            otherInfo["released"] = released[0]
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(\d+\s*Minuten)")[0])
        if duration:
            otherInfo["duration"] = duration
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        return [{"title": cItem["title"], "text": self.cleanHtmlStr(desc), "images": [{"url": self.getFullUrl(icon)}], "other_info": otherInfo}]

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
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, WatchBase(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_seasons", "list_episodes"]
