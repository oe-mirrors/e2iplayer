# -*- coding: utf-8 -*-
# Last Modified: 09.11.2025 - Mr.X
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://megafilme.vip/"


def urlify(text):
    text = text.replace("- ", "")
    text = re.sub(r"[^A-Za-z0-9_ ]", "", text)
    text = "-".join(filter(None, text.split(" ")))
    return text.lower()


class MegaFilme(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "MegaFilme", "cookie": "MegaFilme.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "raw_post_data": True, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + "apple-touch-icon.png"
        apiurl = "api/public/movies?limit=24&sort=%s"
        self.MENU = [
            {"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl(apiurl % "release_date&featured=CINEMA")},
            {"category": "list_items", "title": _("Lastest"), "url": self.getFullUrl(apiurl % "newest")},
            {"category": "list_items", "title": _("Most popular"), "url": self.getFullUrl(apiurl % "popularity")},
            {"category": "list_items", "title": _("Top movies"), "url": self.getFullUrl(apiurl % "tmdb_votes")},
            {"category": "list_value", "title": _("Genres")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem, nextCategory):
        printDBG("MegaFilme.listItems |%s|" % cItem)
        page = cItem.get("page", 1)
        sts, htm = self.getPage(cItem["url"] + "&page=" + str(page))
        if not sts:
            return
        htm = json.loads(htm)
        data = htm.get("movies") or htm.get("suggestions", [])
        for js in data:
            title = self.cleanHtmlStr(js.get("title"))
            url = self.getFullUrl("filme/" + urlify(title))
            poster = js.get("posterPath") or js.get("poster")
            icon = "https://image.tmdb.org/t/p/w300/%s" % poster.split("/")[-1] if poster else ""
            desc = "%s " % js.get("releaseDate")[:4] if js.get("releaseDate") else ""
            desc += "%s Min\n" % js.get("runtime") if js.get("runtime") else ""
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": nextCategory, "title": title, "url": url, "icon": icon, "desc": self.cleanHtmlStr(desc + js.get("overview", ""))})
            self.addVideo(params)
        if htm.get("pagination", {}).get("totalPages", 0) > int(page):
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "page": page + 1})
            self.addDir(params)

    def listValue(self, cItem):
        printDBG("MegaFilme.listValue")
        genres = ["Abenteuer", "Action", "Animation", "Biografie", "Dokumentation", "Drama", "Familie", "Fantasy", "Geschichte", "Horror", "Komödie", "Krieg", "Krimi", "Liebesfilm", "Musik", "Mystery", "Romance", "Science Fiction", "Sport", "TV Film", "Thriller", "Western"]
        for title in genres:
            url = "api/public/movies?limit=24&sort=popularity&genre=%s" % urllib_quote_plus(title)
            params = dict(cItem)
            params.update({"good_for_fav": False, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("MegaFilme.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, data = self.getPage(cItem["url"], self.defaultParams)
        if not sts:
            return []
        match = re.search('encodedFileName[^>]":[^>]"([^"]+)', data)
        if match:
            sts, data = self.getPage("%sapi/fetch-link" % gettytul(), self.defaultParams, json.dumps({"fileName": match.group(1)[:-1]}))
            if not sts:
                return []
            data = json.loads(data)
            urltab.append({"name": data.get("streamUrl"), "url": strwithmeta(data.get("streamUrl"), {"Referer": gettytul(), "Origin": gettytul()[:-1]}), "need_resolve": 0})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("MegaFilme.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return []

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MegaFilme.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = "%sapi/search/suggestions?q=%s&type=filme" % (self.MAIN_URL, urllib_quote(searchPattern))
        self.listItems(cItem, "video")

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem, "video")
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
        CHostBase.__init__(self, MegaFilme(), True, [])
