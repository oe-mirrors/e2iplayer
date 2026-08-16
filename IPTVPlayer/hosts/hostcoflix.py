# -*- coding: utf-8 -*-
# ADD: 20.04.2026 - Mr.X
import base64
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://coflix.wales/"


class Coflix(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Coflix", "cookie": "Coflix.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "wp-content/uploads/2023/01/cropped-coflix.png"
        self.MAIN_URL = gettytul()
        self.API_URL = self.getFullUrl("wp-json/apiflix/v1/options/?post_type=%s&sort=1&page=%s")
        self.MENU = [{"category": "list_items", "title": _("Movies"), "typ": "movies"}, {"category": "list_value", "title": _("Genre"), "uri": self.getFullUrl("film/"), "cat": "genre", "typ": "movies"}, {"category": "list_value", "title": _("Year"), "uri": self.getFullUrl("film/"), "cat": "year", "typ": "movies"}, {"category": "list_items", "title": _("Series"), "typ": "series"}, {"category": "list_value", "title": _("Genre"), "uri": self.getFullUrl("serie/"), "cat": "genre", "typ": "series"}, {"category": "list_value", "title": _("Year"), "uri": self.getFullUrl("serie/"), "cat": "year", "typ": "series"}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("Coflix.listItems |%s|" % cItem)
        page = cItem.get("page", 1)
        url = cItem.get("url") or self.API_URL % (cItem["typ"], page) + cItem.get("id", "")
        sts, htm = self.getPage(url)
        if not sts:
            return
        data = json.loads(htm)
        items = data.get("results", data) if isinstance(data, dict) else data
        for js in items:
            title = js.get("name") or js.get("title")
            url = self.getFullUrl(js.get("url"))
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(js.get("path") or js.get("image"), 'src="([^"]+)')[0])
            desc = js.get("excerpt", "") + (js.get("cast") or js.get("casts") or "")
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": self.cleanHtmlStr(title), "url": url, "icon": icon, "desc": self.cleanHtmlStr(desc)})
            if "series" in js.get("ts", "") or "series" in js.get("post_type", ""):
                params.update({"category": "list_seasons"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if isinstance(data, dict) and data.get("next", False):
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "page": page + 1})
            self.addDir(params)

    def listValue(self, cItem):
        printDBG("Coflix.Value |%s|" % cItem)
        sts, data = self.getPage(cItem["uri"])
        if not sts:
            return
        data = re.findall(r'%s-\d+"\s*value="(\d+)"\s*data-name="([^"]+)' % cItem["cat"], data, re.DOTALL)
        for ids, title in data:
            url = "&genres=" + ids if cItem["cat"] == "genre" else "&years=" + ids
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "id": url, "typ": cItem["typ"]})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("Coflix.listSeasons |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = re.findall(r'data-season="(\d+)" data-id="\d+" post-id="(\d+)"', data, re.DOTALL)
        for seasons, pid in data:
            title = cItem["title"] + " - Staffel " + seasons
            params = dict(cItem)
            url = self.getFullUrl("wp-json/apiflix/v1/series/%s/%s" % (pid, seasons))
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Coflix.listEpisodes |%s|" % cItem)
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        data = json.loads(htm)
        for js in data.get("episodes", []):
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(js.get("path") or js.get("image"), 'src="([^"]+)')[0])
            title = js.get("title")
            url = self.getFullUrl(js.get("links"))
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url, "icon": icon})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Coflix.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("suggest.php?query=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        urltab = []
        url = cItem["url"]
        if "?ads=true" not in url:
            url += "?ads=true"
        sts, htm = self.getPage(url)
        if not sts:
            return []
        link = self.cm.ph.getSearchGroups(htm, 'iframe src="([^"]+)')[0]
        if not link:
            return []
        params = {"header": self.cm.getDefaultHeader()}
        params["header"]["Referer"] = gettytul()
        params["header"]["Upgrade-Insecure-Requests"] = "1"
        sts, htm = self.cm.getPage(link, params)
        if not sts:
            return []
        data = re.findall(r"showVideo[^>]'([^']+)", htm, re.DOTALL)
        for b64 in data:
            url = base64.b64decode(b64).decode("latin1")
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": self.up.getDomain(link, False)}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, url):
        printDBG("Coflix.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return []

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
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Coflix(), True, [])
