# -*- coding: utf-8 -*-
import json

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://einschalten.in/"


class Einschalten(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Einschalten", "cookie": "Einschalten.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "raw_post_data": True, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [
            {"category": "list_items", "title": _("Movies")},
            {"category": "list_items", "title": _("Latest added"), "order": "added"},
            {"category": "list_items", "title": "Sammlungen", "url": self.getFullUrl("api/collections?pageSize=32")},
            {"category": "list_value", "title": _("Genres")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("Einschalten.listItems |%s|" % cItem)
        page = cItem.get("page", 1)
        if cItem.get("url"):
            url = cItem.get("url") + "&pageNumber=%s" % page
            sts, htm = self.getPage(url)
        else:
            params = dict(self.defaultParams)
            params["header"] = dict(params["header"])
            params["header"].update({"Origin": gettytul()[:-1], "Accept": "application/json, text/plain, */*", "Content-Type": "application/json"})
            post = {"pageSize": 32, "pageNumber": page}
            if cItem.get("query"):
                post["query"] = cItem.get("query")
            elif cItem.get("collectionId"):
                post = {"collectionId": cItem.get("collectionId")}
            else:
                post["genreId"] = cItem.get("genreId", 0)
                post["order"] = cItem.get("order", "")
            sts, htm = self.getPage(gettytul() + "api/search", params, post_data=json.dumps(post))
        if not sts:
            return
        data = json.loads(htm)
        for js in data:
            title = self.cleanHtmlStr(js.get("title") or js.get("name", ""))
            icon = gettytul() + "api/image/poster/" + js.get("posterPath") if js.get("posterPath") else ""
            desc = _("Year: ") + js.get("releaseDate")[:4] if js.get("releaseDate") else ""
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "icon": icon, "desc": self.cleanHtmlStr(desc)})
            if "collections" in str(cItem.get("url")):
                params.update({"category": "list_items", "url": "", "collectionId": js.get("id")})
                self.addDir(params)
            else:
                params.update({"category": "video", "id": js.get("id")})
                self.addVideo(params)
        if not cItem.get("query") and not cItem.get("collectionId"):
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "page": page + 1})
            self.addDir(params)

    def listValue(self, cItem):
        printDBG("Einschalten.listValue")
        sts, htm = self.getPage(gettytul() + "api/genres")
        if not sts:
            return
        data = json.loads(htm)
        for js in data:
            params = dict(cItem)
            params.update({"good_for_fav": False, "category": "list_items", "title": self.cleanHtmlStr(js.get("name")), "genreId": js.get("id")})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("Einschalten.getLinksForVideo [%s]" % cItem)
        urltab = []
        url = "%sapi/movies/%s/watch" % (gettytul(), cItem.get("id"))
        sts, data = self.getPage(url)
        if not sts:
            return []
        data = json.loads(data)
        if data.get("streamUrl"):
            urltab.append({"name": data.get("streamUrl"), "url": strwithmeta(data.get("streamUrl"), {"Referer": url}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("Einschalten.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return []

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Einschalten.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["query"] = searchPattern
        self.listItems(cItem)

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
        CHostBase.__init__(self, Einschalten(), True, [])
