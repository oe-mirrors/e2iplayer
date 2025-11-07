# -*- coding: utf-8 -*-
# Last Modified: 04.11.2025 - Mr.X
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://aniworld.to/"


class AniWorld(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "AniWorld", "cookie": "AniWorld.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("public/img/facebook.jpg")
        self.MENU = [
            {"category": "list_items", "title": _("New"), "url": self.getFullUrl("neu")},
            {"category": "list_items", "title": _("Popular"), "url": self.getFullUrl("beliebte-animes")},
            {"category": "list_items", "title": _("All"), "url": self.getFullUrl("animes-alphabet")},
            {"category": "list_value", "title": _("A-Z"), "s": 'class="catalogNav">'},
            {"category": "list_value", "title": _("Genres"), "s": 'class="homeContentGenresList">'}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == "":
            return ""
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {"Cookie": cookieHeader, "User-Agent": self.HEADER.get("User-Agent")})

    def listItems(self, cItem, nextCategory):
        printDBG("AniWorld.listItems |%s|" % cItem)
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(htm, 'href="([^"]+)">&gt;')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-md-15 col-sm-3 col-xs-6">', "</div>")
        if not data:
            data = self.cm.ph.getAllItemsBeetwenMarkers(htm, "data-alternative", "</li>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'data-src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_seasons", "title": title.split(" stream ")[0].split(" Stream ")[0], "url": url, "icon": icon})
            self.addDir(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("AniWorld.listSeasons")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'data-full-description="([^"]+)')[0])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, 'data-src="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "strong>Staffeln", "</div>")
        data = re.compile(r'href="([^"]+)"\s*title="([^"]+)', re.DOTALL).findall(data[0])
        for url, title in data:
            title = cItem["title"] + " - " + title
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": self.getFullUrl(url), "icon": icon, "desc": desc})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("AniWorld.listEpisodes")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'itemprop="episode"', "</tr>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, "<span>([^<]+)")[0])
            ep = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '">([^<]+)</a>')[0])
            title = "{} - {}{}".format(cItem["title"], name, " - " + ep if ep else "")
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url})
            self.addVideo(params)

    def listValue(self, cItem):
        printDBG("AniWorld.listValue")
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], "</ul>")[0]
        data = re.compile('href="([^"]+).*?>([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            if "/anim" in url:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AniWorld.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        sts, data = self.getPage(self.getFullUrl("ajax/search"), post_data={"keyword": searchPattern})
        if not sts:
            return
        data = json_loads(data)
        for item in data:
            title = self.cleanHtmlStr(item["title"])
            desc = self.cleanHtmlStr(item["description"])
            url = self.getFullUrl(item["link"])
            if "anime/" in url and title:
                params = {"name": "category", "category": "list_seasons", "good_for_fav": True, "title": title, "url": url, "desc": desc}
                self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("AniWorld.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, data = self.getPage(cItem["url"], self.defaultParams)
        if not sts:
            return []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'changeLanguageBox"', "</ul>")[0]
        data = re.compile(r'<li[^>]*?data-lang-key\s*=\s*"(\d+)".*?data-link-target="([^"]+).*?<h4>(.*?)</h4>', re.DOTALL).findall(data)
        language_map = {"1": " (DE)", "2": " (JPN) Sub: (EN)", "3": " (JPN) Sub: (DE)"}
        for lang, url, title in data:
            urltab.append({"name": title + language_map.get(lang), "url": strwithmeta(self.getFullUrl(url), {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("AniWorld.getVideoLinks [%s]" % videoUrl)
        params = dict(self.defaultParams)
        params["no_redirection"] = True
        sts, dummy = self.cm.getPage(videoUrl, params)
        if sts and self.cm.meta.get("location"):
            videoUrl = self.cm.meta.get("location")
            if self.cm.isValidUrl(videoUrl):
                return self.up.getVideoLinkExt(videoUrl)
        return []

    def getArticleContent(self, cItem):
        printDBG("AniWorld.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'full-description="([^"]+)')[0]) or cItem.get("desc", "")
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, 'data-src="([^"]+)')[0]) or cItem.get("icon", "")
        fields = {"country": 'itemprop="countryOfOrigin".*?itemprop="name">([^<]+)', "director": 'itemprop="director.*?itemprop="name">([^<]+)', "actors": 'itemprop="actor.*?itemprop="name">([^<]+)', "production": 'itemprop="creator.*?itemprop="name">([^<]+)'}
        for key, pattern in fields.items():
            value = re.findall(pattern, data)
            if value:
                otherInfo[key] = ", ".join(value)
        return [{"title": cItem["title"], "text": desc, "images": [{"title": "", "url": icon}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif "list_items" == category:
            self.listItems(self.currItem, "video")
        elif "list_seasons" == category:
            self.listSeasons(self.currItem)
        elif "list_episodes" == category:
            self.listEpisodes(self.currItem)
        elif "list_value" == category:
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
        CHostBase.__init__(self, AniWorld(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_seasons", "list_episodes"]
