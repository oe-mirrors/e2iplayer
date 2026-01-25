# -*- coding: utf-8 -*-
# Last Modified: 26.12.2025
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://Movie2k.cx/"


class Movie2kcx(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Movie2kcx", "cookie": "Movie2kcx.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + "img/logo.png"
        self.MENU = [{"category": "list_items", "title": _("Cinema movies"), "url": gettytul()}, {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies")}, {"category": "list_value", "title": _("Movies genres"), "url": self.getFullUrl("genres")}, {"category": "list_items", "title": _("Top series"), "url": self.getFullUrl("tv")}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("tv/all")}, {"category": "list_value", "title": "Serien-Genre", "url": self.getFullUrl("tv/genres")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        baseUrl = baseUrl.replace("%C3%B6", "ö").replace("%20%26%20", " & ")
        baseUrl = urllib_quote(baseUrl, safe="/:@$&'()*+,;=?[]")
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("Movie2kcx.listItems |%s|" % cItem)
        page = cItem.get("page", 1)
        sts, htm = self.getPage("%s?page=%s" % (cItem["url"], str(page)))
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'id="maincontent', '<div id="maincontent2">')
        if not data:
            data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'id="maincontent', "</html>")
        data = self.cm.ph.getAllItemsBeetwenMarkers(data[0].replace("amp;", ""), "<tr>", 'id="xline">')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'img src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0])
            desc = self.cm.ph.getAllItemsBeetwenMarkers(item, 'class="info">', "</div>")
            desc = self.cleanHtmlStr(desc[0]).replace('class="info">', "") if desc else " "
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title, "url": url, "icon": icon, "desc": desc})
            if "type=tv" in url or "type=series" in url:
                params.update({"category": "list_seasons"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if ">Nächste &raquo" in htm:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "page": page + 1})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("Movie2kcx.listSeasons")
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(htm, """description" content="([^"]+)""")[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'id="season-select"', "</select>")
        if data:
            data = re.findall(r'<option value="(\d+)"', data[0], re.DOTALL)
        for sn in data:
            url = "%s&season=%s" % (cItem["url"], sn)
            title = cItem["title"] + " - %s %s" % (_("Season"), sn)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "icon": cItem["icon"], "desc": desc})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Movie2kcx.listEpisodes")
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'id="episode-select"', "</select>")
        if data:
            data = re.findall(r'value="([^"]+)" data-name="[^"]+" data-overview="([^"]*)">([^<]+)', data[0])
        for value, desc, title in data:
            if not desc:
                desc = cItem["desc"]
            title = cItem["title"] + " - %s" % self.cleanHtmlStr(title)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "desc": desc, "ep": value})
            self.addVideo(params)

    def listValue(self, cItem):
        printDBG("Movie2kcx.listValue")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="genres', "</html>")[0]
        if data:
            data = re.findall(r'href="([^"]+).*?name">([^<]+).*?count">(\d+)', data.replace("amp;", ""), re.DOTALL)
            for url, title, count in data:
                title = "%s(%s)" % (title, count)
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
                self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("Movie2kcx.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return []
        if cItem.get("ep"):
            htm = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'data-episode-id="%s' % cItem["ep"], "</td>")[0]
        data = re.findall("loadMirror[^>]'([^']+)", htm, re.DOTALL)
        for url in data:
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(self.getFullUrl(url), {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, url):
        printDBG("Movie2kcx.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return []

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Movie2kcx.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = "%ssearch?q=%s" % (self.MAIN_URL, urllib_quote_plus(searchPattern))
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
        CHostBase.__init__(self, Movie2kcx(), True, [])
