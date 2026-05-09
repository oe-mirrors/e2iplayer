# -*- coding: utf-8 -*-
# Last Modified: 07.05.2026 - schwatter
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
import re


def gettytul():
    return "https://www.gaskrank.tv/"


class GaskrankTV(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "gaskrank.tv", "cookie": "gaskrank.tv.cookie"})
        self.MAIN_URL = "https://www.gaskrank.tv/"
        self.DEFAULT_ICON_URL = "https://static.gaskrank.tv/gaskrank2.png"

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HTTP_HEADER.update({"Accept": "text/html", "Referer": self.getMainUrl()})

        self.defaultParams = {"header": self.HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def listMainMenu(self, cItem):
        printDBG("GaskrankTV.listMainMenu")

        MAIN_CAT_TAB = [{"category": "list_items", "title": _("Neuste Filme"), "url": self.getFullUrl("/tv/motorrad-videos/")}, {"category": "list_items", "title": _("Am besten bewertet"), "url": self.getFullUrl("/tv/user-voted/")}, {"category": "list_items", "title": _("Am meisten gesehen"), "url": self.getFullUrl("/tv/top-videos/")}, {"category": "list_cats", "title": _("Video Kategorien"), "url": self.getFullUrl("/tv/")}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem):
        printDBG("GaskrankTV.listCategories START")

        cat_list = [("Motorrad-Fun", "motorrad-fun"), ("Racing", "racing"), ("Superbike WM", "wsbk"), ("Rennstrecken", "rennstrecken"), ("Motorrad Rennfahrer", "motorrad-rennfahrer"), ("Motorradhersteller", "hersteller"), ("Straße", "touring-strasse"), ("Motorrad Pässe", "paesse"), ("Offroad / MX", "gelaende"), ("Supermoto", "supermoto"), ("Streetfighter", "streetfighter"), ("Custombikes", "custombikes"), ("Cafe Racer", "cafe_racer"), ("Sahnestücke", "sahne"), ("Motorradgespanne", "gespanne"), ("Oldtimer", "motorrad-oldtimer"), ("Pocket Bikes", "pocketbikes"), ("Jungbiker", "youngbiker"), ("Quad ATV", "quad"), ("Hall of Fame", "halloffame"), ("Motorroller", "roller"), ("Motorrad Schule", "motorrad-schule"), ("Motorradzubehör", "zubehoer"), ("Motorradbekleidung", "motorradbekleidung"), ("Auspuffanlagen", "motorrad-auspuffanlagen"), ("Werkstatt / Tests", "werkstatt"), ("Video Contest", "video-contest"), ("Helmkamera Test", "helmkamera-test"), ("Motorradtreffen/Messen", "motorradtreffen"), ("Motorrad Foren/Clubs", "motorrad-foren")]

        for title, path in cat_list:
            params = dict(cItem)
            params.update({"category": "list_items", "title": title, "url": self.getFullUrl("/tv/" + path + "/")})
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("GaskrankTV.listItems")
        page = cItem.get("page", 1)
        url = cItem["url"]

        if page > 1:
            offset = (page - 1) * 15
            url = url.rstrip("/") + "/filme-%d.htm" % offset

        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return

        videos = re.findall('"gkVidImg">.*?<img.*?src="(.*?)".*?href="(.*?)">(.*?)</a>', data, re.S)

        for icon, v_url, title in videos:
            params = dict(cItem)
            params.update({"title": self.cleanHtmlStr(title), "url": self.getFullUrl(v_url), "icon": self.getFullUrl(icon)})
            self.addVideo(params)

        if "icon-forward" in data:
            params = dict(cItem)
            params.update({"title": _("Next page"), "page": page + 1})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("GaskrankTV.getLinksForVideo [%s]" % cItem)
        sts, data = self.cm.getPage(cItem["url"], self.defaultParams)
        if not sts:
            return []

        linksTab = []
        links = re.findall('source\ssrc="(.*?)"', data)

        for url in links:
            priority = 0
            extension = url.split(".")[-1].upper()
            res_match = re.search(r"-(\d{3,4})p?\.\w+$", url)

            if res_match:
                res_val = res_match.group(1)
                label = "%s (720p/1080p)" % extension
                priority = int(res_val)
            else:
                label = "%s (SD)" % extension
                priority = 100

            linksTab.append({"name": label, "url": url, "need_resolve": 0, "priority": priority})

        linksTab.sort(key=lambda x: x["priority"], reverse=True)

        return linksTab

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")

        self.currList = []

        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_cats":
            self.listCategories(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, GaskrankTV(), True, [])
