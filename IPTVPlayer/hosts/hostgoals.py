# -*- coding: utf-8 -*-
# Last Modified: 27.02.2026 - by Mr.X
from datetime import datetime

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "Goals.Zone"


class GoalsZoneAPI(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "GoalsZoneAPI", "cookie": "GoalsZoneAPI.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = "https://gogz.meneses.pt/"
        self.DEFAULT_ICON_URL = "https://h.top4top.io/p_3650w3uf91.png"
        self.MENU = [{"category": "list_items", "title": "Latest matches", "url": self.getFullUrl("api/matches/?limit=50&offset=%s&format=json")}, {"category": "list_items", "title": "Teams", "url": self.getFullUrl("api/teams/?limit=50&offset=%s&format=json")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("GoalsZoneAPI.listItems |%s|" % cItem)
        url = cItem["url"]
        if "search-week" not in url:
            url = url % cItem.get("offset", 0)
        sts, data = self.getPage(url)
        if not sts:
            return
        data = json_loads(data)
        if not isinstance(data, list):
            data = data.get("matches", [])
        for item in data:
            title = item.get("name") or "%s %s %s" % (item.get("home_team", {}).get("name"), item.get("score"), item.get("away_team", {}).get("name"))
            url = self.getFullUrl("api/matches/%s?format=json" % item.get("slug"))
            desc = datetime.strptime(item.get("datetime"), "%Y-%m-%dT%H:%M:%SZ") if item.get("datetime") else ""
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "icon": "", "desc": desc})
            if "teams/?" in cItem["url"]:
                url = self.getFullUrl("api/teams/%s?limit=50&" % item.get("slug")) + "offset=%s&format=json"
                params.update({"category": "list_items", "url": url})
            self.addDir(params)
        if "search-week" not in cItem["url"]:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "offset": cItem.get("offset", 0) + 50})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("GoalsZoneAPI.listEpisodes")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = json_loads(data)
        for item in data.get("videos", []):
            title = item.get("title")
            url = []
            for m in item.get("mirrors", []):
                url.append(m.get("url"))
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "urls": url})
            self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("GoalsZoneAPI.getLinksForVideo [%s]" % cItem)
        urltab = []
        for url in cItem.get("urls", []):
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": url}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, url):
        printDBG("GoalsZoneAPI.getVideoLinks [%s]" % url)
        urltab = []
        host = self.up.getDomain(url, False)
        if "streamusk" in url:
            url = self.up.decorateUrl("https://d3ctycp5ce1kgh.cloudfront.net/videos/%s/video.m3u8" % url.split("/")[-1], {"User-Agent": self.HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
            urltab.extend(getDirectM3U8Playlist(url))
            return urltab
        if "streamff" in url:
            url = "https://ffedge.streamff.com/share/" + url.split("/")[-1]
        sts, data = self.getPage(url)
        if not sts:
            return []
        if "streamain" in url:
            url = self.cm.ph.getSearchGroups(data, r'iframe\s*src="([^"]+)')[0]
            sts, data = self.getPage(url)
            if not sts:
                return []
        url = self.cm.ph.getSearchGroups(data, r"""["']((?:https?:)?//[^'^"]+?\.(?:mp4|m3u8|mkv)(?:\?[^"^']+?)?)["']""")[0]
        url = self.up.decorateUrl(url.replace("amp;", ""), {"User-Agent": self.HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
        if ".m3u8" in url:
            urltab.extend(getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999))
        else:
            urltab.append({"name": "MP4", "url": url})
        return urltab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("GoalsZoneAPI.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = "%sapi/matches-search-week/?filter=%s&format=json" % (self.MAIN_URL, urllib_quote(searchPattern))
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
        CHostBase.__init__(self, GoalsZoneAPI(), True, [])
