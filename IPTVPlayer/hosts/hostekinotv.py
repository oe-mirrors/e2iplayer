# -*- coding: utf-8 -*-
# Last Modified: 19.09.2025 - Mr.X
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return 'https://ekino-tv.pl/'


class EkinoTv(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "EkinoTv", "cookie": "EkinoTv.cookie"})
        self.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0"
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "text/html"}
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "views/img/logo.png"
        self.MAIN_URL = None

    def menu(self):
        self.MAIN_URL = gettytul()
        self.MENU = [
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movie/cat/+")},
            {"category": "Series", "title": _("Series"), "url": self.getFullUrl("serie/")},
            {"category": "Genres", "title": _("Genres"), "url": self.getFullUrl("/movie/cat/+")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem, nextCategory):
        printDBG("EkinoTv.listItems |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r'Następna strona" href="([^"]+)')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="movies-list', 'class="info-list')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'href="[^"]+">([^<]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'class="movieDesc">([^<]+)')[0])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": nextCategory, "title": title, "url": url, "icon": icon, "desc": desc})
            if "serie" in url:
                params.update({"category": "list_seasons"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("EkinoTv.listSeasons")
        icon = cItem["icon"]
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        data = re.findall(r'<p>(Sezon \d+)</p>', data, re.DOTALL)
        for title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (cItem["title"], title), "url": self.getFullUrl(url), "icon": icon, "desc": cItem.get("desc", ""), "id": title})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("EkinoTv.listEpisodes")
        icon = cItem["icon"]
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["id"], '</ul>')[0]
        data = re.findall('href="([^"]+)">([^<]+)', data, re.DOTALL)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": "%s - %s" % (cItem["title"], title), "url": self.getFullUrl(url), "icon": icon, "desc": ""})
            self.addVideo(params)

    def listSeries(self, cItem):
        printDBG("EkinoTv.Value |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'serialsmenu">', '</ul>')[0]
        data = re.findall(r'href="([^"]+).*?name">([^<]+).*?count">(\d+)', data, re.DOTALL)
        for url, title, count in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": "%s(%s)" % (title, count), "url": self.getFullUrl(url)})
            self.addDir(params)

    def listGenres(self, cItem):
        printDBG("EkinoTv.Genres")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="movieCategories', '</ul>')[0]
        data = re.findall('href="([^"]+)">([^<]+)', data, re.DOTALL)
        for url, title in data:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("EkinoTv.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = "%ssearch/qf/?q=%s" % (gettytul(), urllib_quote(searchPattern))
        self.listItems(cItem, "video")

    def getLinksForVideo(self, cItem):
        printDBG("EkinoTv.getLinksForVideo [%s]" % cItem)
        urlTab = []
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        data = re.compile(r'''ShowPlayer[^"^']*?['"]([^"^']+?)['"]\s*\,\s*['"]([^"^']+?)['"]''', re.DOTALL).findall(data)
        if data:
            for title, url in data:
                url = "%s/watch/f/%s/%s" % (gettytul(), title, url)
                urlTab.append({"name": title.capitalize(), "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        return urlTab

    def getVideoLinks(self, url):
        printDBG("EkinoTv.getVideoLinks [%s]" % url)
        urlTab = []
        sts, data = self.getPage(url)
        if not sts:
            return []
        url = self.cm.ph.getSearchGroups(data, 'href="([^"]+)" target')[0]
        if 'play.ekino.link' in url:
            sts, data = self.cm._getPageWithPyCurl(url, self.HEADER)
            url = self.cm.ph.getSearchGroups(data, 'iframe src="([^"]+)')[0]
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.menu()
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif "list_items" == category:
            self.listItems(self.currItem, "video")
        elif "list_seasons" == category:
            self.listSeasons(self.currItem)
        elif "list_episodes" == category:
            self.listEpisodes(self.currItem)
        elif "Series" == category:
            self.listSeries(self.currItem)
        elif "Genres" == category:
            self.listGenres(self.currItem)
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
        CHostBase.__init__(self, EkinoTv(), True, [])
