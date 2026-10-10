# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 03.03.2019 - Celeburdi
# 10.10.2026 - the MinDig TV app api (api.mindigtv.appsters.me) is gone (no DNS) and the HbbTV HD launcher answers
#   404: channels, radios and videos now come only from the MinDig TV HbbTV portal (hbbtv-as.connectmedia.hu, plain
#   urls instead of the zlib/base64 packed ones that were bytes on py3), stream token fetched fresh on every play,
#   favourites of the old version (H / D rows) still open, INFO from the portal's data, local icons, default user agent
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://www.mindigtv.hu/"


HBBTV_URL = "http://hbbtv-as.connectmedia.hu/"
HBBTV_LAUNCHER_URL = HBBTV_URL + "ah/launcher/"  # live channels ("token:<id>") + videos
HBBTV_RADIO_URL = HBBTV_URL + "ah/radio/index.php"
HBBTV_MTVA_URL = HBBTV_URL + "mtva/launcher/index.php"  # MTVA news / weather videos
HBBTV_STREAM_URL = HBBTV_URL + "ah/getstreamurl.php?id=%s"  # token -> stream url with a short-lived token


def _gh(name):
    return "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/refs/heads/gh-pages/icons/" + name if name else ""


# title of the portal -> (title shown, icon, sort group)
GROUPS = ["", "main", "movie", "news", "docu", "child", "sport", "music", "regional", "religious"]
CHANNEL_DEFS = {
    "Balaton TV": ("Balaton TV", "balatontv.jpg", "regional"),
    "C Music TV": ("C Music TV", "cmusictv.jpg", "music"),
    "iConcerts HD": ("iConcerts HD", "iconcerts.jpg", "music"),
    "Heti TV": ("Heti TV", "hetitv.jpg", "regional"),
    "FixTV": ("Fix TV HD", "fixtv.jpg", "regional"),
    "Fix TV HD": ("Fix TV HD", "fixtv.jpg", "regional"),
    "Fishing & Hunting": ("Fishing & Hunting", "fishingandhunting.jpg", "sport"),
    "The Fishing & Hunting Channel": ("Fishing & Hunting", "fishingandhunting.jpg", "sport"),
    "Fit HD": ("Fit HD", "fithd.jpg", "sport"),
    "DOQ TV": ("DOQ TV", "doq.jpg", "docu"),
    "Kossuth rádió": ("Kossuth rádió", "kossuthradio.jpg", "main"),
    "Petőfi rádió": ("Petőfi rádió", "petofiradio.jpg", "main"),
    "Bartók rádió": ("Bartók rádió", "bartokradio.jpg", "main"),
    "Dankó Rádió": ("Dankó rádió", "dankoradio.jpg", "main"),
    "Dankó rádió": ("Dankó rádió", "dankoradio.jpg", "main"),
    "Duna World Rádió": ("Duna World Rádió", "dunaworldradio.jpg", "main"),
    "Nemzetiségi adások": ("Nemzetiségi adások", "nemzetisegiadasok.jpg", "main"),
    "Parlamenti adások": ("Parlamenti adások", "parlamentiadasok.jpg", "main"),
    "Radio Swiss Classic (fr)": ("Radio Swiss Classic (fr)", "swissclassic.jpg", "music"),
    "Radio Swiss Classic (ger)": ("Radio Swiss Classic (ger)", "swissclassic.jpg", "music"),
    "Radio Swiss Jazz": ("Radio Swiss Jazz", "swissjazz.jpg", "music"),
    "Radio Swiss Pop": ("Radio Swiss Pop", "swisspop.jpg", "music"),
}


class MindigTVHU(CBaseHostClass):

    # stable identity of a row (no state of an earlier menu)
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "live")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "mindigtv.hu", "cookie": "mindigtvhu.cookie"})
        self.MAIN_URL = HBBTV_URL
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/mindigtv135.png")
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER}

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _channelDef(self, title):
        title, icon, group = CHANNEL_DEFS.get(title, (title, "", ""))
        return title, _gh(icon) or self.DEFAULT_ICON_URL, GROUPS.index(group)

    def listMainMenu(self, cItem):
        printDBG("MindigTVHU.listMainMenu")
        MAIN_CAT_TAB = [{"category": "list_tvChannels", "title": _("TV channels")},
                        {"category": "list_radioChannels", "title": _("Radio stations")},
                        {"category": "list_videos", "title": _("Videos")}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listTVChannels(self, cItem):
        printDBG("MindigTVHU.listTVChannels")
        sts, data = self.getPage(HBBTV_LAUNCHER_URL)
        if not sts:
            return
        rows = []
        for token, title in re.findall(r'''<span[^>]+href=['"]token:([^'"]+)['"][^>]*>([^<]+)<''', data):
            title, icon, order = self._channelDef(self.cleanHtmlStr(title))
            if title:
                rows.append((order, title, {"name": "category", "good_for_fav": True, "live": True, "title": title, "url": "H" + token, "icon": icon,
                                            "desc": "MinDig TV HbbTV - %s" % _("Live")}))
        for row in sorted(rows, key=lambda x: (x[0], x[1])):
            self.addVideo(row[2])

    def listRadioChannels(self, cItem):
        printDBG("MindigTVHU.listRadioChannels")
        sts, data = self.getPage(HBBTV_RADIO_URL)
        if not sts:
            return
        rows = []
        for url, mime, title in re.findall(r'''videos\[\d+\]\s*=\s*\[\s*"([^"]+)"\s*,\s*"([^"]*)"\s*,\s*"([^"]+)"''', data):
            title, icon, order = self._channelDef(self.cleanHtmlStr(title))
            if title and url.startswith("http"):
                rows.append((order, title, {"name": "category", "good_for_fav": True, "live": True, "title": title, "url": "D" + url, "icon": icon,
                                            "desc": "MinDig TV HbbTV - %s[/br]%s" % (_("Live"), mime)}))
        for row in sorted(rows, key=lambda x: (x[0], x[1])):
            self.addAudio(row[2])

    def listVideos(self, cItem):
        printDBG("MindigTVHU.listVideos")
        seen = set()
        for pageUrl in (HBBTV_MTVA_URL, HBBTV_LAUNCHER_URL):
            sts, data = self.getPage(pageUrl)
            if not sts:
                continue
            for url, title in re.findall(r'''<span[^>]+href=['"](https?://[^'"]+?\.mp4)['"][^>]*>([^<]+)<''', data):
                title = self.cleanHtmlStr(title)
                if not title or url in seen:
                    continue
                seen.add(url)
                # MTVA news / weather: one file the portal replaces with the newest programme (no watched flag)
                self.addVideo({"name": "category", "good_for_fav": True, "title": title, "url": "D" + url, "icon": self.DEFAULT_ICON_URL,
                               "desc": "MinDig TV HbbTV - %s" % ("MTVA" if pageUrl == HBBTV_MTVA_URL else "MinDig TV")})

    def getLinksForVideo(self, cItem):
        url = ensure_str(cItem.get("url", ""))
        printDBG("MindigTVHU.getLinksForVideo url[%s]" % url)
        linksTab = []
        if url[:1] == "D":
            url = url[1:]
            if url.endswith(".m3u"):
                sts, data = self.getPage(url)
                if sts:
                    for item in data.replace("\r", "").split("\n"):
                        item = item.strip()
                        if item.startswith("http") and item.split("?")[0][-4:] in (".mp3", ".aac"):
                            linksTab.append({"name": item.split("?")[0][-3:], "url": item, "need_resolve": 0})
            else:
                linksTab.append({"name": "direct link", "url": url, "need_resolve": 0})
        elif url[:1] == "H":
            # the stream url carries a short-lived token: always fetched new
            sts, data = self.getPage(HBBTV_STREAM_URL % url[1:])
            data = ensure_str(data).strip() if sts else ""
            if self.cm.isValidUrl(data):
                linksTab.append({"name": "HbbTV", "url": data, "need_resolve": 0})
        if not linksTab:
            # also the "M" rows of the old version: the MinDig TV app api they used is gone
            SetIPTVPlayerLastHostError(_("No valid links available."))
        return linksTab

    def getFavouriteData(self, cItem):
        printDBG("MindigTVHU.getFavouriteData")
        return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))

    def getArticleContent(self, cItem):
        printDBG("MindigTVHU.getArticleContent [%s]" % cItem)
        icon = cItem.get("icon") or self.DEFAULT_ICON_URL
        otherInfo = {"status": _("Live")} if cItem.get("live") else {}
        return [{"title": cItem.get("title", ""), "text": cItem.get("desc", ""), "images": [{"title": "", "url": icon}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("MindigTVHU.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("MindigTVHU.handleService: name[%s], category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_tvChannels":
            self.listTVChannels(self.currItem)
        elif category == "list_radioChannels":
            self.listRadioChannels(self.currItem)
        elif category == "list_videos":
            self.listVideos(self.currItem)
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MindigTVHU(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def withArticleContent(self, cItem):
        return cItem.get("type", "") in ("video", "audio")
