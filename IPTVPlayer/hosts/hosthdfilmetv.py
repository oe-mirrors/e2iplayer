# -*- coding: utf-8 -*-
# Last Modified: 14.03.2026
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://hdfilme-tv.cc/"


class HDFilmeTV(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "HDFilmeTV", "cookie": "HDFilmeTV.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/StoneOffStones/plugin.video.xstream/c88b2a6953febf6e46cf77f891d550a3c2ee5eea/resources/art/sites/hdfilme.png"
        self.MENU = [{"category": "list_items", "title": _("New"), "url": self.getFullUrl("aktuelle-kinofilme-im-kino/")}, {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("kinofilme-online/")}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serienstream-deutsch/")}, {"category": "list_value", "title": _("Genres"), "s": ">KATEGORIE <"}, {"category": "list_value", "title": _("Year"), "s": ">Release Jahre  <"}, {"category": "list_value", "title": _("Countries"), "s": ">Filme nach Ländern <"}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if any(ord(c) > 127 for c in baseUrl):
            baseUrl = urllib_quote_plus(baseUrl, safe="://")
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("HDFilmeTV.listItems |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, 'href="([^"]+)">\\u203a</a></div>')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="box-product clearfix" data-popover', "</li>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, """href=['"]([^'^"]+?)['"]""")[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r"""data-src=['"]([^'^"]+?\.jpe?g)['"]""")[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, """title=['"]([^'^"]+)['"]""")[0])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title.replace(" stream", ""), "url": url, "icon": icon, "desc": ""})
            if "taffel" in title:
                params.update({"category": "list_episodes"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("HDFilmeTV.listEpisodes")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description"\s*content="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li id="serie', "</ul>")
        for item in data:
            episode = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '><a href="#">([^<]+)')[0])
            title = cItem["title"] + " - " + episode
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url, "desc": desc, "episode": episode})
            self.addVideo(params)

    def listValue(self, cItem):
        printDBG("HDFilmeTV.listValue")
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], "</ul>")[0]
        if data:
            data = re.findall('href="([^"]+).*?>([^<]+)', data, re.DOTALL)
            for url, title in data:
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
                self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("HDFilmeTV.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        if cItem.get("episode"):
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem.get("episode"), "</ul>")[0]
        data = re.findall(r'link="([^"]+)', data, re.DOTALL)
        for url in data:
            url = "https:" + url if url.startswith("//") else url
            if "/vod/" in url:
                continue
            title = self.up.getHostName(url).capitalize()
            if "youtube" in url:
                title = "Trailer"
            urltab.append({"name": title, "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, url):
        printDBG("HDFilmeTV.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return []

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HDFilmeTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("index.php?do=search&subaction=search&story=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getArticleContent(self, cItem):
        printDBG("HDFilmeTV.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0])
        genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, "Genres:(.*?)</p>")[0])
        if genre:
            otherInfo["genre"] = genre
        fields = {"country": "<p>Produktionsland:(.*?)</p>", "duration": 'datetime=".*?">([^<]+)</time>', "actors": "<p>Mit:(.*?)</p>"}
        for key, pattern in fields.items():
            value = re.findall(pattern, data)
            if value:
                otherInfo[key] = ", ".join(value)
        return [{"title": cItem["title"], "text": desc, "images": [{"title": "", "url": cItem.get("icon", "")}], "other_info": otherInfo}]

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
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, HDFilmeTV(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_seasons", "list_episodes"]
