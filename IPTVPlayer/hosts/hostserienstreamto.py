# -*- coding: utf-8 -*-
# Last Modified: 29.01.2026 - Mr.X - Completely new writen
import re

from Components.config import ConfigSelection, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

config.plugins.iptvplayer.serienstreamto_hosts = ConfigSelection(default="http://186.2.175.5/", choices=[("http://186.2.175.5/", "186.2.175.5"), ("https://s.to/", "s.to"), ("https://serienstream.to/", "serienstream.to")])  # NOSONAR


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("host") + ":", config.plugins.iptvplayer.serienstreamto_hosts))
    return optionList


def gettytul():
    return "https://serienstream.to/"


class SerienStreamTo(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "SerienStreamTo", "cookie": "SerienStreamTo.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = config.plugins.iptvplayer.serienstreamto_hosts.value
        self.DEFAULT_ICON_URL = self.getFullUrl("public/img/facebook.jpg")
        self.MENU = [{"category": "list_items", "title": _("Series"), "url": self.getFullUrl("suche")}, {"category": "list_items", "title": _("Collections"), "url": self.getFullUrl("sammlungen")}, {"category": "list_newepisodes", "title": "Neueste Episoden"}, {"category": "list_value", "title": _("Genres"), "s": ">Genres</h2>"}, {"category": "list_AZ", "title": "A-Z"}, {"category": "list_value", "title": _("Country"), "s": ">Länder</h2>"}, {"category": "list_value", "title": _("Persons"), "s": ">Personen</h2>"}, {"category": "list_items", "title": _("All"), "url": self.getFullUrl("serien")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("SerienStreamTo.listItems |%s|" % cItem)
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(htm, 'class="page-link" href="([^"]+)" rel="next">')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-6', "</div>")
        if not data:
            data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="series-item"', "</li>")
        if not data:
            data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="collection-item-cover', "</small>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cm.ph.getSearchGroups(item, 'data-search="([^"]+)')[0]
            if not title:
                title = self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0]
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_seasons", "title": self.cleanHtmlStr(title), "url": url, "icon": icon, "desc": ""})
            if "sammlung" in url:
                params.update({"category": "list_items"})
            self.addDir(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": nextPage})
            self.addDir(params)

    def AZ(self, cItem):
        az = [chr(t) for t in range(ord("A"), ord("Z") + 1)] + ["0-9"]
        for title in az:
            url = "katalog/" + title
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("SerienStreamTo.listSeasons")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'description-text">([^<]+)')[0])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, 'data-src="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="season-nav">', "</nav>")
        data = re.compile(r'href="([^"]+).*?data-season-pill="(\d+)', re.DOTALL).findall(data[0])
        for url, se in data:
            title = "%s - %s %s" % (cItem["title"], _("Season"), se)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": self.getFullUrl(url), "icon": icon, "desc": desc})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("SerienStreamTo.listEpisodes")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="episode-row', "</tr>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, "location='([^']+)")[0])
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            ep = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'cell">(\d+)')[0])
            title = "%s - %s %s - %s" % (cItem["title"], _("Episode"), ep, name)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url})
            self.addVideo(params)

    def listNewEpisodes(self, cItem):
        printDBG("SerienStreamTo.listNewEpisodes")
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="latest-episode', "</a>")
        if data:
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
                name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'ep-title"\stitle="([^"]+)')[0])
                se = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'ep-season">([^<]+)')[0])
                ep = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'ep-episode">([^<]+)')[0])
                title = "%s - %s - %s" % (name, se, ep)
                params = dict(cItem)
                params.update({"good_for_fav": True, "title": title, "url": url, "desc": url})
                self.addVideo(params)

    def listValue(self, cItem):
        printDBG("SerienStreamTo.listValue")
        sts, data = self.getPage(self.getFullUrl("suche"))
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem["s"], "</ul>")[0]
        data = re.compile('href="([^"]+).*?>([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SerienStreamTo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("suche?term=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("SerienStreamTo.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="episode-links"', "</article>")[0]
        data = re.compile(r'data-play-url="([^"]+).*?data-provider-name="([^"]+).*?data-language-label="([^"]+)', re.DOTALL).findall(data)
        for url, title, lang in data:
            urltab.append({"name": "%s (%s)" % (title, lang), "url": strwithmeta(self.getFullUrl(url), {"Referer": config.plugins.iptvplayer.serienstreamto_hosts.value}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, url):
        printDBG("SerienStreamTo.getVideoLinks [%s]" % url)
        params = dict(self.defaultParams)
        params["no_redirection"] = True
        self.cm.getPage(url, params)
        if self.cm.meta.get("location"):
            url = self.cm.meta.get("location")
            if self.cm.isValidUrl(url):
                return self.up.getVideoLinkExt(url)
        return []

    def getArticleContent(self, cItem):
        printDBG("SerienStreamTo.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'description-text">([^<]+)')[0])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, 'data-src="([^"]+)')[0]) or cItem.get("icon", "")
        fields = {"country": '<strong class="me-1">Land:</strong>', "director": '<strong class="me-1">Regisseur:</strong>', "actors": '<strong class="me-1">Besetzung:</strong>', "production": '<strong class="me-1">Produzent:</strong>'}
        for key, pattern in fields.items():
            value = self.cm.ph.getAllItemsBeetwenMarkers(data, pattern, "</li>")
            if value:
                value2 = re.findall('light">([^<]+)', value[0])
                if value2:
                    otherInfo[key] = ", ".join(value2)
        return [{"title": cItem["title"], "text": desc, "images": [{"title": "", "url": icon}], "other_info": otherInfo}]

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
        elif category == "list_AZ":
            self.AZ(self.currItem)
        elif category == "list_newepisodes":
            self.listNewEpisodes(self.currItem)
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
        CHostBase.__init__(self, SerienStreamTo(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_seasons", "list_episodes"]
