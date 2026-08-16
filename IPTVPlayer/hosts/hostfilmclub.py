# -*- coding: utf-8 -*-
# Update: 06.06.2026 - Mr.X
# for Panda555
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://filmclub.tv/"


class FilmClub(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "FilmClub", "cookie": "FilmClub.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.sub_tracks = []
        self.DEFAULT_ICON_URL = self.getFullUrl("templates/playtube/img/apple-touch-icon.png")
        self.MENU = [{"category": "list_items", "title": _("New"), "url": self.getFullUrl("newvideos.html")}, {"category": "list_items", "title": _("Popular"), "url": self.getFullUrl("topvideos.php?do=recent")}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("series/")}, {"category": "list_value", "title": _("Genres"), "s": 'class="pt-menu-title">ŽANROVI'}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("FilmClub.listItems |%s|" % cItem)
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(htm, 'href="([^"]+)">&raquo;')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="pm-video-thumb', "</li>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'data-echo="([^"]+)')[0])
            if not icon:
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'img src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            dur = self.cm.ph.getSearchGroups(item, 'duration">([^<]+)')[0]
            desc = _("Duration: %s") % dur if dur else ""
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title, "url": url, "icon": icon, "desc": desc})
            if "series" in url:
                params.update({"category": "list_seasons"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("FilmClub.listSeasons")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'description" content="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="collapse', "/div>")
        for item in data:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'id="collapse_(\d+)')[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            title = cItem["title"] + " - %s %s" % (_("Season"), title)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "se": item, "desc": desc})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("FilmClub.listEpisodes")
        data = re.compile(r'href="([^"]+)" title="([^"]+).*?S\d+ - E(\d+)', re.DOTALL).findall(cItem["se"])
        for url, title, ep in data:
            title = cItem["title"] + " - %s %s - %s" % ((_("Episode"), ep, self.cleanHtmlStr(title)))
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url})
            self.addVideo(params)

    def listValue(self, cItem):
        printDBG("FilmClub.listValue")
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], "</ul>")[0]
        data = re.compile('href="([^"]+).*?<span>([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmClub.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("search.php?keywords=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def get_redirected_url(self, url):
        params = dict(self.defaultParams)
        params["no_redirection"] = True
        self.cm.getPage(url, params)
        if self.cm.meta.get("location"):
            if "voe.php" in url and "play_" not in self.cm.meta.get("location"):
                url = self.cm.meta.get("location")
                url = url.replace(self.up.getDomain(url), "voe.sx")
            else:
                url = self.cm.meta.get("location")
        return url

    def getLinksForVideo(self, cItem):
        printDBG("FilmClub.getLinksForVideo [%s]" % cItem)
        urltab = []
        self.sub_tracks = []
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return []
        data = re.findall(r'data-src="([^"]+)', htm, re.DOTALL)
        if not data:
            data = re.findall(r'iframe src="([^"]+)', htm, re.DOTALL)
        for url in data:
            if "filmclub.sbs" in url:
                url = self.get_redirected_url(url)
            if "filmclub.sbs" in url:
                url = self.get_redirected_url(url)
            if "?c1_file" in url:
                sub = re.findall(r'file=([^&]+).*?label=([^&]+)', url, re.DOTALL)
                for f, t in sub:
                    self.sub_tracks.append({"title": "", "url": f, "lang": t})
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(self.getFullUrl(url), {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("FilmClub.getVideoLinks [%s]" % videoUrl)
        videoUrl = self.up.getVideoLinkExt(videoUrl)
        if self.sub_tracks:
            for url in videoUrl:
                meta = url.get("url").meta
                meta["external_sub_tracks"] = self.sub_tracks
                strwithmeta(str(url), meta)
        return videoUrl

    def getArticleContent(self, cItem):
        printDBG("FilmClub.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'description" content="([^"]+)')[0]) or cItem.get("desc", "")
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
        CHostBase.__init__(self, FilmClub(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_seasons", "list_episodes"]
