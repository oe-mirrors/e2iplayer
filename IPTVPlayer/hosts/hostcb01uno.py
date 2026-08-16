# -*- coding: utf-8 -*-
# Last Modified: 05.05.2026 - update to current url - Masta2002
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://cb01uno.watch/"


class Cb01(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Cb01"})
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HTTP_HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("wp-content/uploads/2025/02/logo-cb01-it-com-film-streaming.png")
        self.MENU = [{"category": "movies", "title": _("Movies")}, {"category": "series", "title": _("Series")}] + self.searchItems()
        self.MOVIES = [{"category": "list_items", "title": _("Movies"), "url": gettytul()}, {"category": "list_genres", "title": _("Genres"), "url": gettytul()}, {"category": "list_year", "title": _("Year"), "url": gettytul()}]
        self.SERIES = [{"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serietv/")}, {"category": "list_genres", "title": _("Genres"), "url": self.getFullUrl("serietv/")}, {"category": "list_year", "title": _("Year"), "url": self.getFullUrl("serietv/")}]

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listItems(self, cItem, nextCategory="video"):
        printDBG("cb01uno.listItems |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, '"next" href="([^"]+)')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="card-image">', 'class="card-action')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '</strong>([^"]+)</div>')[0])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": nextCategory, "title": title, "url": url, "icon": icon, "desc": desc})
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
        printDBG("cb01uno.listSeasons |%s|" % cItem)
        icon = cItem["icon"]
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        data = re.findall(r"STAGIONE (\d+) -", data, re.DOTALL)
        for seasons in data:
            title = "%s - %s %s" % (cItem["title"], _("Season"), seasons)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "icon": icon, "seasons": seasons})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("cb01uno.listEpisodes |%s|" % cItem)
        seasons = cItem["seasons"]
        icon = cItem["icon"]
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "STAGIONE %s -" % seasons, "</strong>")[0]
        data = re.findall(r"215;(\d+)", data, re.DOTALL)
        for episode in data:
            title = "%s - %s %s" % (cItem["title"], _("Episode"), episode)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url, "icon": icon, "desc": cItem.get("desc", ""), "seasons": seasons, "episode": episode})
            self.addVideo(params)

    def listValue(self, cItem, s, e):
        printDBG("cb01uno.Value |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, s, e)[0]
        data = re.findall('href="([^"]+).*?>([^<]+)', data, re.DOTALL)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("cb01uno.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem["url"] = self.getFullUrl("?s=%s" % urllib_quote(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("cb01uno.getLinksForVideo [%s]" % cItem)
        urlTab = []
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        if cItem.get("seasons") and cItem.get("episode"):
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, "STAGIONE %s" % cItem.get("seasons"), "</strong>")[0]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, ";%s" % cItem.get("episode"), "</a></p>")[0]
        data = re.findall('href="([^"]+)" target.*?>([^<]+)', data, re.DOTALL)
        for url, title in data:
            if "ixdrop" not in title:
                continue
            urlTab.append({"name": title.capitalize(), "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        return urlTab

    def getVideoLinks(self, url):
        printDBG("cb01uno.getVideoLinks [%s]" % url)
        if "https://stayonline.pro" in url:
            sts, data = self.getPage(url)
            if not sts:
                return
            data = re.findall(r'linkId = "([^"]+)"', data, re.DOTALL)
            if data:
                sts, data = self.getPage("https://stayonline.pro/ajax/linkView.php", self.defaultParams, {"id": data[0], "ref": ""})
                if not sts:
                    return
            url = json.loads(data).get("data", {}).get("value")
            return self.up.getVideoLinkExt(url)

    def getArticleContent(self, cItem):
        printDBG("cb01uno.getArticleContent [%s]" % cItem)
        desc = cItem.get("desc", "")
        title = cItem["title"]
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        return [{"title": title, "text": self.cleanHtmlStr(desc), "images": [{"title": "", "url": self.getFullUrl(icon)}]}]

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
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_genres":
            self.listValue(self.currItem, "Genere", "</li></ul>")
        elif category == "list_year":
            self.listValue(self.currItem, " Anno", "</li></ul>")
        elif category == "movies":
            self.listsTab(self.MOVIES, self.currItem)
        elif category == "series":
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
        CHostBase.__init__(self, Cb01(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_episodes"]
