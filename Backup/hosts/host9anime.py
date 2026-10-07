# -*- coding: utf-8 -*-
# Last Modified: 30.01.26 - Mr.X
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads


def GetConfigList():
    return []


def gettytul():
    return "https://9animetv.to/"


class AnimeTV(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "AnimeTV"})
        self.HTTP_HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HTTP_HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl('images/logo.png')
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movie")},
        {"category": "list_items", "title": _("TV Series"), "url": self.getFullUrl("tv")},
        {"category": "list_items", "title": "OVAs", "url": self.getFullUrl("ova")},
        {"category": "list_items", "title": "ONAs", "url": self.getFullUrl("ona")},
        {"category": "list_items", "title": "Specials", "url": self.getFullUrl("special")},
        {"category": "list_items", "title": _("Latest update"), "url": self.getFullUrl("recently-updated")},
        {"category": "list_items", "title": _("Latest added"), "url": self.getFullUrl("recently-added")},
        {"category": "list_value", "title": _("Genres"), "s": '">Genres<'}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("AnimeTV.listItems |%s|" % cItem)
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, 'next"><a href="([^"]+)')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="film-poster">', 'class="clearfix')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'epx">([^<]+)')[0])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "icon": icon, "desc": desc})
            self.addDir(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage.replace("$TV Series", "tv").replace("$", "").lower())})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("AnimeTV.listEpisodes")
        url = cItem["url"]
        icon = cItem["icon"]
        params = self.HTTP_HEADER
        params["Referer"] = gettytul()
        sts, htm = self.getPage(url, {"header": params})
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(htm, 'description" content="([^"]+)')[0])
        did = self.cm.ph.getSearchGroups(htm, r'id="wrapper" data-id="(\d+)')
        if did:
            sts, data = self.getPage(self.getFullUrl("ajax/episode/list/%s" % did[0]))
            if not sts:
                return
            data = re.compile(r'title=\\"([^\\]+).*?data-id=\\"([^\\]+)', re.DOTALL).findall(data)
            if data:
                for ep, did in data:
                    params = dict(cItem)
                    params.update({"good_for_fav": True, "title": cItem["title"] + " - " + ep, "id": did, "icon": icon, "desc": desc})
                    self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("AnimeTV.getLinksForVideo [%s]" % cItem)
        urltab = []
        params = self.HTTP_HEADER
        params["Referer"] = cItem["url"]
        params["X-Requested-With"] = "XMLHttpRequest"
        if cItem.get("id"):
            sts, data = self.getPage(self.getFullUrl("ajax/episode/servers?episodeId=%s" % cItem["id"]), {"header": params})
            if not sts:
                return []
            data = json_loads(data).get("html", "")
            data = re.compile(r'data-id="(\d+).*?class="btn">([^<]+)', re.DOTALL).findall(data)
            if data:
                for did, title in data:
                    url = self.getFullUrl("ajax/episode/sources?id=%s" % did)
                    urltab.append({"name": title, "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, url):
        printDBG("AnimeTV.getVideoLinks [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return []
        url = self.cm.ph.getSearchGroups(data, '"link":"([^"]+)')[0]
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return []

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AnimeTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("search?keyword=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getArticleContent(self, cItem):
        printDBG("AnimeTV.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0]
        desc = desc if desc else cItem.get("desc", "")
        title = cItem["title"]
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        return [{"title": title, "text": self.cleanHtmlStr(desc), "images": [{"title": "", "url": self.getFullUrl(icon)}], "other_info": otherInfo}]

    def listValue(self, cItem):
        printDBG("AnimeTV.listValue")
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], "</ul>")[0]
        data = re.compile('href="([^"]+).*?>([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

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
        CHostBase.__init__(self, AnimeTV(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_episodes"]
