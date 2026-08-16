# -*- coding: utf-8 -*-
# RetroFlix Plugin for e2iplayer
# Created: 13.01.2025
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://retroflix.org/"


class RetroFlix(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "RetroFlix", "cookie": "RetroFlix.cookie"})
        self.defaultParams = {"header": self.cm.getDefaultHeader(), "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "wp-content/uploads/2023/01/RetroFlix-Square-Logo.png"
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("browse/movies/")}, {"category": "list_items", "title": _("Cartoons"), "url": self.getFullUrl("browse/cartoons/")}, {"category": "list_items", "title": _("Anime"), "url": self.getFullUrl("browse/anime/")}, {"category": "list_items", "title": _("Documentaries"), "url": self.getFullUrl("genre/documentary/")}, {"category": "list_items", "title": _("Cinema History"), "url": self.getFullUrl("browse/cinema-history/")}, {"category": "list_value", "title": _("Genres"), "url": self.getFullUrl("genre/")}, {"category": "list_value", "title": _("Year"), "url": self.getFullUrl("year-released/")}, {"category": "list_value", "title": _("Actors"), "url": self.getFullUrl("cast/")}, {"category": "list_value", "title": _("Directors"), "url": self.getFullUrl("director/")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("RetroFlix.listItems |%s|" % cItem)
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        # Extraction de la page suivante
        nextPage = self.cm.ph.getSearchGroups(data, r'<a[^>]*?href="([^"]+/page/\d+/)"[^>]*?>Next')[0]
        if not nextPage:
            nextPage = self.cm.ph.getSearchGroups(data, r'rel="next"\s+href="([^"]+)"')[0]
        # Extraction des items
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<article", "</article>")
        for item in data:
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url or "watch/" not in url:
                continue
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'gb-headline-text">.*?<a[^>]+>([^<]+)')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])
            # Extraction de l'image (style ou src)
            icon = self.cm.ph.getSearchGroups(item, r'style="--background-url:url\(([^)]+)\)')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]
            if icon:
                icon = self.getFullIconUrl(icon)
            # Extraction d'une mini description pour l'affichage en bas de liste
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<p>", "</p>")[1])
            # On force la catégorie à "video" pour que Enigma2 appelle getArticleContent
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": title, "url": self.getFullUrl(url), "icon": icon, "desc": desc})
            self.addVideo(params)
        # Page suivante
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage)})
            self.addDir(params)

    def listValue(self, cItem):
        printDBG("RetroFlix.listValue")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        # Extraction des catégories/filtres
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a href="' + cItem["url"], "</a>")
        for item in data:
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            title = self.cleanHtmlStr(item)
            if url and title and url != cItem["url"]:
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
                self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("RetroFlix.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        # Recherche du lien dans la balise video (src)
        videoUrl = self.cm.ph.getSearchGroups(data, r'<video[^>]+src="(https://archive\.org/download/[^"]+\.mp4)"')[0]
        # Recherche du lien direct vers archive.org (href)
        if not videoUrl:
            videoUrl = self.cm.ph.getSearchGroups(data, r'href="(https://archive\.org/download/[^"]+\.mp4)"')[0]
        if not videoUrl:
            videoUrl = self.cm.ph.getSearchGroups(data, r'<a[^>]*?href="(https://archive\.org/[^"]+)"')[0]
        if videoUrl:
            urltab.append({"name": "Archive.org MP4", "url": strwithmeta(videoUrl, {"Referer": self.MAIN_URL}), "need_resolve": 0})
        # Recherche alternative dans les iframes
        if not urltab:
            iframes = re.findall(r'<iframe[^>]+src="([^"]+)"', data)
            for iframe in iframes:
                if "archive.org" in iframe:
                    urltab.append({"name": "Archive.org Stream", "url": strwithmeta(iframe, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("RetroFlix.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if "archive.org" in videoUrl:
            # Si c'est déjà un lien direct MP4
            if videoUrl.endswith(".mp4"):
                urlTab.append({"name": "MP4", "url": videoUrl})
            else:
                # Essayer d'extraire le lien MP4 de la page archive.org
                sts, data = self.getPage(videoUrl)
                if sts:
                    mp4Link = self.cm.ph.getSearchGroups(data, r'"(https://archive\.org/download/[^"]+\.mp4)"')[0]
                    if mp4Link:
                        urlTab.append({"name": "MP4", "url": mp4Link})
        if not urlTab and self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("RetroFlix.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("?s=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getArticleContent(self, cItem):
        printDBG("RetroFlix.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        # Extraction de la description
        desc = self.cm.ph.getSearchGroups(data, r'<meta\s+name="description"\s+content="([^"]+)"')[0]
        if not desc or len(desc) < 10:
            # Essayer de trouver le bloc de texte principal
            desc = self.cm.ph.getDataBeetwenMarkers(data, '<div class="entry-content', "</div>")[1]
            if desc:
                # Nettoyer les balises de scripts ou styles potentiels
                desc = re.sub(r"<style[^>]*>.*?</style>", "", desc, flags=re.DOTALL)
                desc = self.cleanHtmlStr(desc)
        # Extraction de l'année (supporte le lien dans le texte)
        year = self.cm.ph.getSearchGroups(data, r"Year Released:.*?<a[^>]*>(\d{4})</a>")[0]
        if not year:
            year = self.cm.ph.getSearchGroups(data, r"Year Released:.*?(\d{4})")[0]
        if year:
            otherInfo["year"] = year
        # Extraction du genre
        genre = self.cm.ph.getSearchGroups(data, r"Genre:.*?<a[^>]*>([^<]+)</a>")[0]
        if genre:
            otherInfo["genre"] = genre
        # Extraction de la durée
        duration = self.cm.ph.getSearchGroups(data, r"(\d+h\s+\d+m)")[0]
        if duration:
            otherInfo["duration"] = duration
        # Extraction des acteurs
        actors = []
        actors_data = self.cm.ph.getDataBeetwenMarkers(data, "stars:", "</div>", caseSensitive=False)[1]
        if actors_data:
            actors_list = self.cm.ph.getAllItemsBeetwenMarkers(actors_data, "<a", "</a>")
            for actor in actors_list:
                actors.append(self.cleanHtmlStr(actor))
        if actors:
            otherInfo["actors"] = ", ".join(actors)
        title = cItem.get("title", "")
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        return [{"title": title, "text": self.cleanHtmlStr(desc), "images": [{"title": "", "url": self.getFullUrl(icon)}], "other_info": otherInfo}]

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
        CHostBase.__init__(self, RetroFlix(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get("category") == "video"
