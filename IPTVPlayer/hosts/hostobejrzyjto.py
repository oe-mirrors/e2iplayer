# -*- coding: utf-8 -*-
# Completely rewritten: 19.02.2026 - Mr.X
# Fixed Pagination for episodes: 02.05.2026 - SlyceMaster
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://obejrzyj.to/"


class Obejrzyjto(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Obejrzyjto", "cookie": "Obejrzyjto.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("storage/branding_media/ead386d3-fca5-4082-8754-2a0992ae8c22.png")
        self.API_URL = self.getFullUrl("api/v1/channel/%s?restriction=&order=%s:desc&paginate=lengthAware&returnContentOnly=true&page=")
        self.MENU = [
            {"category": "submenu", "title": _("Movies"), "id": "78"},
            {"category": "list_items", "title": "Popularne polskie filmy", "url": self.API_URL % ("99", "popularity")},
            {"category": "submenu", "title": _("Series"), "id": "79"},
            {"category": "list_items", "title": "Polskie seriale", "url": self.API_URL % ("1994", "popularity")},
            {"category": "list_items", "title": "Polskie programy", "url": self.API_URL % ("396", "popularity")},
            {"category": "list_items", "title": "Seriale dokumentalne", "url": self.API_URL % ("9742", "popularity")},
        ] + self.searchItems()

    def listsubMenu(self, cItem):
        self.listsTab([{"category": "list_items", "title": _("Popular"), "url": self.API_URL % (cItem["id"], "popularity")}, {"category": "list_items", "title": _("Lastest"), "url": self.API_URL % (cItem["id"], "created_at")}, {"category": "list_items", "title": _("Latest update"), "url": self.API_URL % (cItem["id"], "videos_updated_at")}, {"category": "list_items", "title": _("Rating"), "url": self.API_URL % (cItem["id"], "rating")}, {"category": "list_items", "title": "Największy budżet", "url": self.API_URL % (cItem["id"], "budget")}, {"category": "list_items", "title": "Największy przychód", "url": self.API_URL % (cItem["id"], "revenue")}], cItem)

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("Obejrzyjto.listItems |%s|" % cItem)
        page = cItem.get("page", 1)
        url = cItem["url"]
        if "searchPage" not in url:
            url = url + str(page)

        sts, data = self.getPage(url)
        if not sts:
            return
        htm = json_loads(data)
        data = htm.get("pagination", {}).get("data", [])
        if not data:
            data = htm.get("results", [])
        nextPage = htm.get("pagination", {}).get("next_page", False)
        for js in data:
            title = js.get("name")
            icon = js.get("poster")
            desc = js.get("description", "")
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title, "icon": icon.replace("/original/", "/w500/"), "desc": desc})
            if js.get("is_series"):
                url_id = js.get("id")
                params.update({"category": "list_seasons", "url": url_id})
                self.addDir(params)
            else:
                url_id = self.getFullUrl("api/v1/titles/%s?loader=titlePage" % js.get("id", "0"))
                params.update({"url": url_id})
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "page": nextPage})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("Obejrzyjto.listSeasons")
        sts, data = self.getPage(self.getFullUrl("api/v1/titles/%s?loader=titlePage" % cItem["url"]))
        if not sts:
            return
        htm = json_loads(data)
        desc = htm.get("title", {}).get("description", "")
        data = htm.get("seasons", {}).get("data", [])
        for js in data:
            title = "%s %s" % (_("Season"), js.get("number"))
            url = self.getFullUrl("api/v1/titles/%s/seasons/%s?loader=seasonPage" % (js.get("title_id"), js.get("number")))
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "icon": js.get("poster") or cItem["icon"], "desc": desc})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Obejrzyjto.listEpisodes")
        page = cItem.get("page", 1)
        url = cItem["url"]

        if page > 1:
            if "?" in url:
                url += "&page=%s" % page
            else:
                url += "?page=%s" % page

        sts, data = self.getPage(url)
        if not sts:
            return
        htm = json_loads(data)

        ep_obj = htm.get("episodes", {})
        data = ep_obj.get("data", [])
        nextPage = ep_obj.get("pagination", {}).get("next_page", False)

        for js in data:
            title = "%s %s" % (_("Episodes"), js.get("episode_number"))
            params = dict(cItem)
            url_ep = self.getFullUrl("api/v1/titles/%s/seasons/%s/episodes/%s?loader=episodePage" % (js.get("title_id"), js.get("season_number"), js.get("episode_number")))
            params.update({"good_for_fav": True, "title": title, "url": url_ep, "icon": js.get("poster") or cItem["icon"], "desc": js.get("description")})
            self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "page": nextPage})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Obejrzyjto.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("api/v1/search/%s?loader=searchPage" % urllib_quote(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("Obejrzyjto.getLinksForVideo [%s]" % cItem)
        urltab = []
        url = cItem["url"]
        if "=titlePage" in url:
            sts, data = self.getPage(url)
            if not sts:
                return []
            js = json_loads(data)
            url = self.getFullUrl("api/v1/watch/%s" % js.get("title", {}).get("primary_video", {}).get("id"))
        sts, data = self.getPage(url)
        if not sts:
            return []
        data = json_loads(data)
        js = data.get("alternative_videos", [])
        if not js:
            js = data.get("episode", {}).get("videos", [])
        for item in js:
            urltab.append({"name": self.up.getHostName(item["src"]).capitalize(), "url": strwithmeta(item["src"], {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, url):
        printDBG("Obejrzyjto.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return []

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "submenu":
            self.listsubMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
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
        CHostBase.__init__(self, Obejrzyjto(), True, [])
