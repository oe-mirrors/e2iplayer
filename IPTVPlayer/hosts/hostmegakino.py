# -*- coding: utf-8 -*-
# Last Modified: 31.12.2025 - Mr.X
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://megakino.lol/"


class MegaKino(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "MegaKino", "cookie": "MegaKino.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("films")}, {"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("kinofilme")}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serials")}, {"category": "list_items", "title": _("Animation"), "url": self.getFullUrl("multfilm")}, {"category": "list_items", "title": _("Documentary"), "url": self.getFullUrl("documentary")}, {"category": "list_value", "title": _("Collections"), "s": ">Sammlung"}, {"category": "list_value", "title": _("Genres"), "s": ">Genres"}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem, nextCategory):
        printDBG("MegaKino.listItems |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r'class="pagination.*?href="([^"]+)">\D')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="poster grid-item', "</a>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'line-clamp">([^<]+)')[0])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": nextCategory, "title": title, "url": url, "icon": icon, "desc": desc})
            if "taffel" in title or "documentary" in url:
                params.update({"category": "list_episodes"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("MegaKino.listEpisodes")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option value="e', "</option>")
        for item in data:
            episode = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'value="[^"]+">([^<]+)')[0])
            ep = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'value="([^"]+)')[0])
            title = cItem["title"] + " - " + episode
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url, "desc": desc, "episode": ep})
            self.addVideo(params)

    def listValue(self, cItem):
        printDBG("MegaKino.Genres")
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], 'class="side-block__title')[0]
        data = re.compile('href="([^"]+)(?:.*?title">|">)([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MegaKino.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("index.php?do=search&subaction=search&story=%s" % urllib_quote(searchPattern))
        self.listItems(cItem, "video")

    def getLinksForVideo(self, cItem):
        printDBG("MegaKino.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, data = self.getPage(cItem["url"], self.defaultParams)
        if not sts:
            return []
        if cItem.get("episode"):
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="%s' % cItem.get("episode"), "</select>")[0]
            data = re.compile('value="([^"]+)', re.DOTALL).findall(data)
        else:
            data = re.compile(r'(?:film_main"\s*data-src|iframe\s*src)="([^"]+)', re.DOTALL).findall(data)
        for url in data:
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta("https:" + url if url.startswith("//") else url, {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("MegaKino.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return []

    def getArticleContent(self, cItem):
        printDBG("MegaKino.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'itemprop="description"\s*data-rows="\d+">(.*?)</div>')[0])
        fields = {"duration": r"(\d+ min)</div>", "country": 'itemprop="countryOfOrigin">([^"]+)</span>', "director": 'itemprop="directors">(.*?)</span>', "actors": 'itemprop="actors">(.*?)</span>', "genres": 'itemprop="genre">([^"]+)</div>'}
        for key, pattern in fields.items():
            value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, pattern)[0])
            if value:
                otherInfo[key] = value
        return [{"title": cItem["title"], "text": desc if desc else cItem.get("desc", ""), "images": [{"title": "", "url": cItem.get("icon", "")}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.getPage(gettytul() + "index.php?yg=token", self.defaultParams)
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem, "video")
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
        CHostBase.__init__(self, MegaKino(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_episodes"]
