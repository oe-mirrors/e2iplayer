# -*- coding: utf-8 -*-
# Last Modified: 02.06.2026 MR.X
import re
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://kkiste.study"


class KKisteAG(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "kkiste.ag", "cookie": "kkiste.ag.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = "https://tarnkappe.info/wp-content/uploads/kkiste-logo.jpg"
        self.MAIN_URL = gettytul()
        self.MAIN_CAT_TAB = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/kinofilme-online/")}, {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/serienstream-deutsch/")}, {"category": "list_items", "title": _("Animation"), "url": self.getFullUrl("/animation/")}, {"category": "list_year", "title": _("Year"), "url": self.MAIN_URL}, {"category": "list_genres", "title": "Genres", "url": self.MAIN_URL}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("KKisteAG.listItems |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, 'next"><a href="([^"]+)')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="short">', "</article>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'img src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'href="[^"]+">([^<]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'st-desc">([^<]+)')[0])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title, "url": url, "icon": icon, "desc": desc})
            if "taffel" in title or "serie" in title:
                params.update({"category": "list_episodes"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage.startswith("https"):
            self.apply_next_url(cItem, self.getFullUrl(nextPage))

    def listEpisodes(self, cItem):
        printDBG("KKisteAG.listEpisodes")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li id="serie', "</ul>")
        for item in data:
            episode = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '><a href="#">([^<]+)')[0])
            title = cItem["title"] + " - " + episode
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url, "desc": desc, "episode": episode})
            self.addVideo(params)

    def listGenres(self, cItem, t):
        printDBG("KKisteAG.Genres")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, ">%s<" % t, "</ul>")[0]
        data = re.compile('href="([^"]+).*?>([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            if "kino" in title.lower() or "serie" in title.lower():
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title.replace(" stream", ""), "url": self.getFullUrl(url), "icon": "", "desc": ""})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KKisteAG.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("index.php?do=search&subaction=search&story=%s" % urllib_quote(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("KKisteAG.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        if cItem.get("episode"):
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem.get("episode"), "</ul>")[0]
        data = re.findall('data-link="(h[^"]+)', data, re.DOTALL)
        for url in data:
            if "meinecloud" in url or "player.php" in url:
                continue
            url = "https:" + url if url.startswith("//") else url
            urltab.append({"name": "Trailer" if "youtu" in url else self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("KKisteAG.getVideoLinks [%s]" % videoUrl)
        urltab = []
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urltab

    def getArticleContent(self, cItem):
        printDBG("KKisteAG.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'video-box clearfix"><strong>([^"]+)</div>')[0])
        desc = desc if desc else cItem.get("desc", "")
        patterns = {"actors": r"Darsteller:(.*?)</div>", "director": r"Regisseur:(.*?)</div>", "released": r"Jahr:(.*?)</div>", "duration": r"Zeit:(.*?)</div>"}
        for k, p in patterns.items():
            v = self.cm.ph.getSearchGroups(data, p)
            if v:
                otherInfo[k] = self.cleanHtmlStr(v[0])
        return [{"title": self.cleanHtmlStr(cItem["title"]), "text": self.cleanHtmlStr(desc), "images": [{"title": "", "url": self.getFullUrl(cItem.get("icon", self.DEFAULT_ICON_URL))}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MAIN_CAT_TAB, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_year":
            self.listGenres(self.currItem, "Release Jahre")
        elif category == "list_genres":
            self.listGenres(self.currItem, "Genres")
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
        CHostBase.__init__(self, KKisteAG(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_episodes"]
