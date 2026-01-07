# -*- coding: utf-8 -*-
# Last Modified: 07.01.2026 - Mr.X
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

try:
    from itertools import zip_longest
except ImportError:
    from itertools import izip_longest as zip_longest


def GetConfigList():
    return []


def gettytul():
    return "https://kinoger.to/"


class KinoGer(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "kinoger", "cookie": "kinoger.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "templates/kinoger/images/logo.png"
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_items", "title": "Neues", "url": self.MAIN_URL}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/stream/serie/")}, {"category": "list_genres", "title": "Genres"}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == "":
            return ""
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {"Cookie": cookieHeader, "User-Agent": self.HEADER.get("User-Agent")})

    def listItems(self, cItem):
        printDBG("KinoGer.listItems |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, '<a[^>]href="([^"]+)">vorw')[0]
        data = re.compile('class="title".*?href="([^"]+)">([^<]+).*?src="([^"]+)(.*?)"footercontrol">', re.DOTALL).findall(data)

        for url, title, icon, dummy in data:
            if title.startswith("KinoGer"):
                continue
            desc = re.compile('<div style="text-align:right;">(.*?)<div[^>]class', re.DOTALL).findall(dummy)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": self.cleanHtmlStr(title), "url": url, "icon": icon, "desc": self.cleanHtmlStr(desc[0]) if desc else ""})
            if "taffel" in title or "serie" in cItem["url"] or ">S0" in dummy:
                params.update({"category": "list_seasons"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("KinoGer.listSeasons")
        url = cItem["url"]
        icon = cItem["icon"]
        sts, data = self.getPage(url)
        if not sts:
            return
        season_lists = {}
        total = 0
        for key in ["sst", "ollhd", "pw", "go"]:
            container = re.compile(r"%s.show.*?</script>" % key, re.DOTALL).findall(data)
            if container:
                container = container[0]
                container = container.replace("[", "<").replace("]", ">")
                season_lists[key] = re.compile(r"<'([^>]+)", re.DOTALL).findall(container)
                if container:
                    total = len(season_lists[key])
        for i in range(total):
            params = dict(cItem)
            title = "%s - Staffel %s" % (cItem.get("title"), i + 1)
            for key in ["sst", "ollhd", "pw", "go"]:
                if key in season_lists and i < len(season_lists[key]):
                    params.update({key: season_lists[key][i]})
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "icon": icon, "desc": cItem.get("desc", "")})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("KinoGer.listEpisodes")
        icon = cItem["icon"]
        episode_lists = {}
        for key in ["sst", "ollhd", "pw", "go"]:
            if cItem.get(key):
                episode_lists[key] = re.compile("(http[^']+)", re.DOTALL).findall(cItem[key])
        liste = zip_longest(*[episode_lists[key] for key in ["sst", "ollhd", "pw", "go"] if key in episode_lists])
        for i, url in enumerate(liste, start=1):
            title = "%s - Episode %s" % (cItem.get("title"), i)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "Episode": url, "icon": icon, "desc": cItem.get("desc", "")})
            self.addVideo(params)

    def listGenres(self, cItem):
        printDBG("KinoGer.Value")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="sidelinks', "</ul>")[0]
        data = re.compile('href="([^"]+).*?/>([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            if "erie" in title or url == "/":
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KinoGer.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("?do=search&subaction=search&titleonly=3&story=%s&x=0&y=0&submit=submit" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("KinoGer.getLinksForVideo [%s]" % cItem)
        urltab = []
        if cItem.get("Episode"):
            data = re.compile("(http[^']+)", re.DOTALL).findall(str(cItem["Episode"]))
        else:
            sts, data = self.getPage(cItem["url"], self.defaultParams)
            if not sts:
                return []
            data = re.compile(r"show[^>]\d,[^>][^>]'([^']+)", re.DOTALL).findall(data)
        for url in data:
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(self.getFullUrl(url), {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("KinoGer.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return []

    def getArticleContent(self, cItem):
        printDBG("KinoGer.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'description" content="([^"]+)')[0])
        desc = desc if desc else cItem.get("desc", "")
        actors = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, ">Schauspieler:([^<]+)")[0])
        if actors:
            otherInfo["actors"] = actors
        d = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, ">Regie:([^<]+)")[0])
        if d:
            otherInfo["director"] = d
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, ">Spielzeit:([^<]+)")[0])
        if duration:
            otherInfo["duration"] = duration
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        return [{"title": cItem["title"], "text": self.cleanHtmlStr(desc), "images": [{"title": "", "url": self.getFullUrl(icon)}], "other_info": otherInfo}]

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
        elif category == "list_genres":
            self.listGenres(self.currItem)
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
        CHostBase.__init__(self, KinoGer(), True, [])

    def withArticleContent(self, cItem):
        return cItem["type"] == "video" or cItem.get("category") in ["list_seasons", "list_episodes"]
