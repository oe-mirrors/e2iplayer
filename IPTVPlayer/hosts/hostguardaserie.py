# -*- coding: utf-8 -*-
# Last Modified: 06.04.2026 - MR.X
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://guarda-serie.ovh/"


class GuardaSerie(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "GuardaSerie", "cookie": "GuardaSerie.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + "static/logo.png"
        self.MENU = [{"category": "list_items", "title": _("Series"), "url": self.getFullUrl("archive")}, {"category": "list_items", "title": _("Top rated"), "url": self.getFullUrl("archive?sort=vote")}, {"category": "list_genres", "title": _("Genres")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("GuardaSerie.listItems |%s|" % cItem)
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, 'href="([^"]+)">Next')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'mlnh-thumb"><a', "</div>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_seasons", "title": title.replace(" streaming guardaserie", ""), "url": url, "icon": icon, "desc": ""})
            self.addDir(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("GuardaSerie.listSeasons |%s|" % cItem)
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0])
        data = re.findall(r'href="#[^"]+" data-toggle="tab">([^<]+)', data, re.DOTALL)
        if not data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": cItem["title"], "url": self.getFullUrl(url), "desc": desc})
            self.addVideo(params)
        else:
            for seasons in data:
                title = "%s - %s %s" % (cItem["title"], _("Season"), seasons)
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "desc": desc, "seasons": seasons})
                self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("GuardaSerie.listEpisodes |%s|" % cItem)
        url = cItem["url"]
        seasons = cItem["seasons"]
        sts, data = self.getPage(url)
        if not sts:
            return
        tmdbID = self.cm.ph.getSearchGroups(data, r"var\s*tmdbID\s*=\s*(\d+)")[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="season-%s' % seasons, "</ul>")[0]
        data = re.findall(r">(\d+)<", data, re.DOTALL)
        for episode in data:
            title = "%s - %s %s" % (cItem["title"], _("Episode"), episode)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "tmdbID": tmdbID, "desc": cItem.get("desc", ""), "seasons": seasons, "episode": episode})
            self.addVideo(params)

    def listValue(self, cItem, s, e):
        printDBG("GuardaSerie.Value |%s|" % cItem)
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, s, e)[0]
        data = re.findall('href="([^"]+).*?>([^<]+)', data, re.DOTALL)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("GuardaSerie.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem["url"] = self.getFullUrl("search?q=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("GuardaSerie.getLinksForVideo [%s]" % cItem)
        url = "https://vixsrc.to/tv/%s/%s/%s?lang=it" % (cItem.get("tmdbID"), cItem.get("seasons"), cItem.get("episode"))
        return [{"name": url, "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1}]

    def getVideoLinks(self, url):
        printDBG("GuardaSerie.getVideoLinks [%s]" % url)
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
        elif category == "list_genres":
            self.listValue(self.currItem, "Genere<", "</ul>")
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
        CHostBase.__init__(self, GuardaSerie(), True, [])
