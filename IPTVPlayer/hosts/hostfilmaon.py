# -*- coding: utf-8 -*-
# Last Modified: 07.12.2025 - Mr.X
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://www.filmaon.bz/"


class Filmaon(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Filmaon", "cookie": "Filmaon.cookie"})
        self.defaultParams = {"header": self.cm.getDefaultHeader(), "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "wp-content/uploads/2025/06/logofix22.png"
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("filma/")}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("seriale/")}, {"category": "list_value", "title": _("Genres"), "s": "ZHANRET"}, {"category": "list_value", "title": _("Country"), "s": "SHTETET"}, {"category": "list_value", "title": _("Year"), "s": "releases scrolling"}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("Filmaon.listItems |%s|" % cItem)
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, 'rel="next" href="([^"]+)')[0]
        if "animation-2" in data:
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, "animation-2", "</article></div>")
            if "?s=" not in url:
                data = data[0]
        if "?s=" not in url:
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<article id", "</article>")
        for item in data:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)')[0])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title, "url": url, "icon": icon})
            if "seriale" in url:
                params.update({"category": "list_seasons"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listValue(self, cItem):
        printDBG("Filmaon.listValue")
        sts, data = self.getPage(gettytul() + "filma/")
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], "</ul>")
        if data:
            data = re.findall('href="([^"]+).*?>([^<]+)', data[0], re.DOTALL)
            for url, title in data:
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
                self.addDir(params)

    def Seasons(self, cItem):
        printDBG("Filmaon.Seasons")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "se-t", "</ul>")
        for se in data:
            if "class='none" in se:
                continue
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(se, r">(\d+)<")[0])
            title = cItem["title"] + " - %s %s" % (_("Season"), title)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "desc": desc, "se": se})
            self.addDir(params)

    def Episodes(self, cItem):
        printDBG("Filmaon.Episodes")
        data = re.findall(r"mark-(\d+).*?data-src='([^']+).*?href='([^']+)", cItem["se"], re.DOTALL)
        for title, icon, url in data:
            title = cItem["title"] + " - %s %s" % (_("Episode"), title)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url, "icon": icon})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Filmaon.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("?s=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("Filmaon.getLinksForVideo [%s]" % cItem)
        urltab = []
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return []
        data = re.findall(r"data-type='([^']+)'\s*data-post='(\d+)'\s*data-nume='(\d+)'", data, re.DOTALL)
        if data:
            params = dict(self.defaultParams)
            params["header"] = dict(params["header"])
            params["header"].update({"Referer": url, "Origin": gettytul()[:-1], "X-Requested-With": "XMLHttpRequest", "Accept": "*/*"})
            for dt, dp, dn in data:
                sts, data = self.getPage(self.getFullUrl("wp-admin/admin-ajax.php"), params, {"action": "doo_player_ajax", "post": dp, "nume": dn, "type": dt})
                if not sts:
                    continue
                url = self.cm.ph.getSearchGroups(data, 'url":"([^"]+)')[0]
                if url:
                    url = url.replace(r"\/", "/")
                    urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta("https:" + url if url.startswith("//") else url, {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("Filmaon.getVideoLinks [%s]" % videoUrl)
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
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Filmaon(), True, [])
