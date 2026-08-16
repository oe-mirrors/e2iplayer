# -*- coding: utf-8 -*-
# Last Modified: 12.11.2025 - by Mr.X
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://cuevanatv.lol/"


class CuevanaTV(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "CuevanaTV", "cookie": "CuevanaTV.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "raw_post_data": True, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + "templates/cuevana/img/cropped-favicon-1-180x180.png"
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("peliculas")}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("series")}, {"category": "list_value", "title": _("Genres"), "s": "Géneros<"}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("CuevanaTV.listItems |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, 'href="([^"]+)"><i class="fa-arrow-right">')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'TPostMv">', "</li>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)')[0])
            title = self.cm.ph.getSearchGroups(item, 'Title">([^<]+)')[0]
            desc = self.cleanHtmlStr(self.cm.ph.getAllItemsBeetwenMarkers(item, '<div class="Description">', "</div>")[0])
            dur = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'access_time">([\d]+)m')[0])
            if dur:
                desc = "Spielzeit: %sMin\n%s" % (dur, desc)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": self.cleanHtmlStr(title), "url": url, "icon": icon, "desc": desc})
            if "temporada" in url:
                params.update({"category": "list_seasons"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("CuevanaTV.listSeasons")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        seasons = []
        first_s = self.cm.ph.getSearchGroups(data, r'canonical" href="([^"]+)')
        if first_s:
            seasons.append(first_s[0])
        seasons.extend(re.findall(r'<option value="([^"]+)', data))
        for url in seasons:
            url = self.getFullUrl(url)
            title = self.cm.ph.getSearchGroups(url, r"temporada-(\d+)-episodio")[0]
            if title:
                title = cItem["title"] + " - %s %s" % (_("Season"), title)
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "icon": cItem["icon"], "desc": cItem.get("desc", "")})
                self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("CuevanaTV.listEpisodes")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        ep = []
        first_s = self.cm.ph.getSearchGroups(data, r'canonical" href="([^"]+)')
        if first_s:
            ep.append(first_s[0])
        ep.extend(re.findall(r'data-episode="\d+" href="([^"]+)', data))
        for url in ep:
            url = self.getFullUrl(url)
            title = self.cm.ph.getSearchGroups(url, r"episodio-(\d+)")[0]
            title = cItem["title"] + " - %s %s" % (_("Episode"), title)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url})
            self.addVideo(params)

    def listValue(self, cItem):
        printDBG("CuevanaTV.listValue")
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], "</ul>")[0]
        data = re.compile('href="([^"]+).*?>([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("CuevanaTV.getLinksForVideo [%s]" % cItem)
        urltab = []
        TITLE_MAP = {'OptL1': ' - Latino', 'OptS1': ' - Subtitulado', 'OptE1': ' - Español', 'OptY': ' - Trailer'}
        url = cItem["url"]
        sts, htm = self.getPage(url, self.defaultParams)
        if not sts:
            return []
        if "temporada" in url:
            data = re.compile(r"var\s+playlist_lang\s*=\s*(\{.*?\});", re.DOTALL).findall(htm)
            data = json.loads(data[0])["links"]
            for title, url in data.items():
                if url and title:
                    url = "https://goodstream.one/video/embed/" + url
                    urltab.append({"name": self.up.getHostName(url).capitalize() + " - " + title, "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        else:
            data = re.compile('t-playerTb.*?id="([^"]+).*?data-src="([^"]+)', re.DOTALL).findall(htm)
            for title, url in data:
                url = "https:" + url if url.startswith("//") else url
                urltab.append({"name": self.up.getHostName(url).capitalize() + TITLE_MAP.get(title, ''), "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("CuevanaTV.getVideoLinks [%s]" % videoUrl)
        return self.up.getVideoLinkExt(videoUrl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CuevanaTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = "%s?do=search&mode=advanced&subaction=search&story=%s" % (self.MAIN_URL, urllib_quote(searchPattern))
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
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, CuevanaTV(), True, [])
