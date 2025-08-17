# -*- coding: utf-8 -*-
# Last Modified: 17.08.2025 - Mr.X
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://xalaflix.cv"


class XalaFlix(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "XalaFlix"})
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser="firefox")
        self.defaultParams = {"header": self.HTTP_HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("/images/xalaflix-logo.png")
        self.MENU = [
            {"category": "list_items", "title": _("New"), "url": self.getFullUrl("/newest")},
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/movies/")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/series/")},
            {"category": "list_items", "title": _("Most viewed"), "url": self.getFullUrl("/most-watched")},
            {"category": "list_items", "title": _("Latest added"), "url": self.getFullUrl("/added")},
            {"category": "list_az", "title": _("A-Z")},
            {"category": "search", "title": _("Search"), "search_item": True}, {"category": "search_history", "title": _("Search history")}]

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("XalaFlix.listItems |%s|" % cItem)
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r'Next" href="([^"]+)')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="item', "</a>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0])
            ep = self.cm.ph.getSearchGroups(url, r"ep-(\d+)")[0]
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title, "url": url, "icon": icon, "desc": ep, "id": ep})
            if "aison" in url:
                params.update({"category": "list_episodes"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("XalaFlix.listEpisodes |%s|" % cItem)
        icon = cItem["icon"]
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        desc = self.cm.ph.getSearchGroups(data, r'class="synopsis">\s*<div class="content">\s*<p>(.*?)</p>')[0]
        ep = self.cm.ph.getSearchGroups(data, r'data-id="(\d+)')[0]
        sts, data = self.getPage(self.getFullUrl("/ajax/episode/list-episode?movieId=%s" % ep))
        if not sts:
            return
        data = re.findall(r'data-num.*?"(\d+).*?data-id=.*?"(\d+)', data, re.DOTALL)
        for episode, ep in data:
            title = "%s - %s %s" % (cItem["title"], _("Episode"), episode)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": cItem["url"], "icon": icon, "desc": desc, "id": ep})
            self.addVideo(params)

    def listValue(self, cItem, v):
        printDBG("XalaFlix.Value |%s|" % cItem)
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, v, "</ul>")
        data = re.findall('href="([^"]+).*?>([^<]+)', data[0], re.DOTALL)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("XalaFlix.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem["url"] = self.getFullUrl("filter?keyword=%s" % urllib_quote(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("XalaFlix.getLinksForVideo [%s]" % cItem)
        urlTab = []
        sts, data = self.getPage(self.getFullUrl("/ajax/episode/player?episode_id=%s" % cItem["id"]))
        if not sts:
            return []
        data = re.findall('server_link":"([^"]+)', data, re.DOTALL)
        for url in data:
            if "multiup" in url:
                continue
            url = url.replace("\\/", "/")
            if "flixeo.xyz" in url:
                params = dict(self.defaultParams)
                params["no_redirection"] = True
                sts, dummy = self.cm.getPage(url, params)
                if self.cm.meta["status_code"] == 404:
                    continue
                if sts and self.cm.meta.get("location"):
                    if "/voe" in url:
                        url = self.cm.meta.get("location")
                        url = url.replace(self.up.getDomain(url), "voe.sx")
                    else:
                        url = self.cm.meta.get("location")
            urlTab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta("https:" + url if url.startswith("//") else url, {"Referer": gettytul()}), "need_resolve": 1})
        return urlTab

    def getVideoLinks(self, url):
        printDBG("XalaFlix.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("XalaFlix.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cm.ph.getSearchGroups(data, r'class="synopsis">\s*<div class="content">\s*<p>(.*?)</p>')[0]
        released = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<span>\s*(\d{4})\s*</span>")[0])
        if released:
            otherInfo["released"] = released
        desc = desc if desc else cItem.get("desc", "")
        title = cItem["title"]
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        return [{"title": title, "text": self.cleanHtmlStr(desc), "images": [{"title": "", "url": self.getFullUrl(icon)}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.menu()
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif "list_items" == category:
            self.listItems(self.currItem)
        elif "list_episodes" == category:
            self.listEpisodes(self.currItem)
        elif "list_az" == category:
            self.listValue(self.currItem, '<section id="azlist">')
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
        CHostBase.__init__(self, XalaFlix(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_episodes"]
