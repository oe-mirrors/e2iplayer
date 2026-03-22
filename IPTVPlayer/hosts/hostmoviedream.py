# -*- coding: utf-8 -*-
# Last Modified: 22.03.2026 - Mr.X
import base64
import json
import re
from binascii import unhexlify
from hashlib import md5

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs import pyaes
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://moviedream.to/"


def evp_bytes_to_key(password, salt, key_len=32):
    md5_bytes = b""
    prev = b""
    while len(md5_bytes) < key_len:
        hasher = md5()
        hasher.update(prev + password + salt)
        prev = hasher.digest()
        md5_bytes += prev
    return md5_bytes[:key_len]


class MovieDream(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "MovieDream", "cookie": "MovieDream.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "LOGO.png"
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("kino")}, {"category": "movies", "title": _("Movies")}, {"category": "series", "title": _("Series")}] + self.searchItems()
        self.MOVIES = [{"category": "list_items", "title": _("Lastest"), "url": self.getFullUrl("neuefilme")}, {"category": "list_items", "title": _("Popular"), "url": self.getFullUrl("beliebtefilme")}, {"category": "list_value", "title": _("Genres"), "s": "film"}]
        self.SERIES = [{"category": "list_items", "title": _("Lastest"), "url": self.getFullUrl("neueserien")}, {"category": "list_items", "title": _("Popular"), "url": self.getFullUrl("beliebteserien")}, {"category": "list_value", "title": _("Genres"), "s": "serie"}]

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("MovieDream.listItems |%s|" % cItem)
        sts, data = self.getPage(cItem["url"] + cItem.get("page", ""))
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r'class="righter"\s*href="([^"]+)')[0]
        lastPage = self.cm.ph.getSearchGroups(data, r'class="seiterr"\s*href="([^"]+)')[0]
        data = re.findall('class="linkto.*?href="([^"]+).*?src="([^"]+).*?>([^>]+)</div>', data, re.DOTALL)
        for url, icon, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "video", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url.replace("../..", "")), "icon": self.getFullUrl(icon.replace("../..", "")), "desc": ""})
            if "serie" in url:
                params.update({"category": "list_seasons"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage and cItem.get("page", "") != lastPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "page": nextPage})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("MovieDream.listSeasons")
        icon = cItem["icon"]
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '16px;">(.*?)</p>')[0])
        data = re.findall('href="([^"]+)" class="seasonbutton.*?">([^<]+)', data, re.DOTALL)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (cItem["title"], title), "url": self.getFullUrl(url), "icon": icon, "desc": desc})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("MovieDream.listEpisodes")
        icon = cItem["icon"]
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = re.findall(r'href="([^"]+)" class="episodebutton" id="episodebutton\d+">#([\d]+)', data, re.DOTALL)
        for url, title in data:
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": "%s - %s %s" % (cItem["title"], _("Episodes"), title), "url": self.getFullUrl(url), "icon": icon})
            self.addVideo(params)

    def listValue(self, cItem):
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        data = re.findall('href="(/%s[^"]+)">([^<]+)' % cItem["s"], data, re.DOTALL)
        if data:
            for url, title in data:
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
                self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MovieDream.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = "%ssuchergebnisse.php?text=%s&sprache=Deutsch" % (gettytul(), urllib_quote(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("MovieDream.getLinksForVideo [%s]" % cItem)
        urltab = []
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return []
        data = re.findall("""href="'+.CryptoJSAesJson.decrypt.'({.*?})', '([^']+)""", data, re.DOTALL)
        for js, pw in data:
            js = json.loads(js)
            key = evp_bytes_to_key(pw.encode("utf-8"), unhexlify(js.get("s", b"")))
            decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, unhexlify(js["iv"])))
            data = decrypter.feed(base64.b64decode(js["ct"])) + decrypter.feed()
            url = json.loads(data.decode("utf-8"))
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        return urltab

    def getVideoLinks(self, url):
        printDBG("MovieDream.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return []

    def getArticleContent(self, cItem):
        printDBG("MovieDream.getArticleContent [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        otherInfo = {}
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '16px;">(.*?)</p>')[0])
        actors = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, "Schauspieler:(.*?)<br>")[0])
        if actors:
            otherInfo["actors"] = actors
        director = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, "Regisseur:(.*?)<br>")[0])
        if director:
            otherInfo["director"] = director
        year = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r">(\d{4})<")[0])
        if year:
            otherInfo["year"] = year
        duration = self.cm.ph.getSearchGroups(data, r"(\d+ Min)")[0]
        if duration:
            otherInfo["duration"] = duration
        title = cItem["title"]
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        return [{"title": self.cleanHtmlStr(title), "text": self.cleanHtmlStr(desc), "images": [{"title": "", "url": self.getFullUrl(icon)}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
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
        elif category == "movies":
            self.listsTab(self.MOVIES, self.currItem)
        elif category == "series":
            self.listsTab(self.SERIES, self.currItem)
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
        CHostBase.__init__(self, MovieDream(), True, [])

    def withArticleContent(self, cItem):
        return cItem["category"] in ["video", "list_episodes", "list_seasons"]
