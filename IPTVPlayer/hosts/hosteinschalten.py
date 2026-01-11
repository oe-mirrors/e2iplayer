# -*- coding: utf-8 -*-
# Last Modified: 11.01.2026 - Mr.X - Site Fix
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
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("api/movies?order=new")}, {"category": "list_items", "title": _("Latest added"), "url": self.getFullUrl("api/movies?order=added")}, {"category": "list_items", "title": "Sammlungen", "url": self.getFullUrl("api/collections")}, {"category": "list_value", "title": _("Genres")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("Einschalten.listItems |%s|" % cItem)
        page = cItem.get("page", 1)
        if cItem.get("query"):
            params = dict(self.defaultParams)
            params["header"] = dict(params["header"])
            params["header"].update({"Origin": gettytul()[:-1], "Accept": "application/json, text/plain, */*", "Content-Type": "application/json"})
            post = {"query": cItem.get("query"), "pageNumber": page}
            sts, htm = self.getPage(gettytul() + "api/search", params, post_data=json.dumps(post))
        else:
            url = cItem.get("url")
            sep = "&" if "?" in url else "?"
            url += "%spageNumber=%s" % (sep, page)
            sts, htm = self.getPage(url)
        if sts and htm.startswith("{"):
            data = json.loads(htm)
            for js in data.get("data"):
                title = self.cleanHtmlStr(js.get("title") or js.get("name", ""))
                icon = gettytul() + "api/image/poster/" + js.get("posterPath") if js.get("posterPath") else ""
                desc = _("Year: ") + js.get("releaseDate")[:4] if js.get("releaseDate") else ""
                params = dict(cItem)
                params.update({"good_for_fav": True, "title": title, "icon": icon, "desc": self.cleanHtmlStr(desc)})
                if "collections" in str(cItem.get("url")):
                    params.update({"category": "list_items", "url": gettytul() + "api/movies?collectionId=%s" % js.get("id")})
                    self.addDir(params)
                else:
                    params.update({"category": "video", "id": js.get("id")})
                    self.addVideo(params)
            if data.get("pagination", {}).get("hasMore", False):
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
            params.update({"good_for_fav": False, "category": "list_items", "title": self.cleanHtmlStr(js.get("name")), "url": "%sapi/movies?genreId=%s&order=new" % (gettytul(), js.get("id"))})
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

    def getVideoLinks(self, url):
        printDBG("Einschalten.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return []

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Einschalten.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["query"] = searchPattern
        self.listItems(cItem)

    def getArticleContent(self, cItem):
        printDBG("Einschalten.getArticleContent [%s]" % cItem)
        otherInfo = {}
        desc = ""
        sts, htm = self.getPage(gettytul() + "api/movies/%s" % cItem.get("id", "0"))
        if sts and htm.startswith("{"):
            data = json.loads(htm)
            desc = data.get("overview")
            if data.get("runtime"):
                otherInfo["duration"] = "%s Min" % data.get("runtime")
            if data.get("voteAverage"):
                otherInfo["rating"] = str(data.get("voteAverage"))
            if data.get("releaseDate"):
                otherInfo["released"] = str(data.get("releaseDate")[:4])
        return [{"title": cItem["title"], "text": desc, "images": [{"title": "", "url": cItem["icon"]}], "other_info": otherInfo}]

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

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video"]
