# -*- coding: utf-8 -*-
# Last Modified: 23.08.2024 BY MOHAMED_OS
from base64 import b64decode
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc


def GetConfigList():
    return []


def gettytul():
    return "https://av.tvfun.me"


class Tvfun(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"cookie": "tvfun.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://av.tvfun.me/apple-touch-icon.png"
        self.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0"
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "text/html"}
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("Tvfun.listCatItems |%s|" % cItem)
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        tmp = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "menu"), ("</ul", ">"), True)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, ("<li>", "<a"), ("</a>", "</li>"))
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ">", "</a>", False)[1])
            if title != "تيفي فان":
                params = dict(cItem)
                params.update({"category": "listItems", "good_for_fav": True, "title": title, "url": url, "icon": self.DEFAULT_ICON_URL})
                self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("Tvfun.listItems |%s|" % cItem)
        page = cItem.get("page", 1)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getDataBeetwenMarkers(data, ("<ul", ">", "pagination"), ("</ul", ">"), True)[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, r"""<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>{0}<""".format(page + 1))[0])
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="thumb series', "</div>")
        for item in tmp:
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0])
            params = dict(cItem)
            params.update({"category": nextCategory, "good_for_fav": True, "EPG": True, "title": title, "url": url, "icon": icon})
            self.addDir(params)
        if nextPage != "":
            params = dict(cItem)
            params.update({"title": _("Next page"), "url": nextPage, "page": page + 1})
            self.addDir(params)

    def exploreItems(self, cItem):
        printDBG("Tvfun.exploreItems |%s|" % cItem)
        page = cItem.get("page", 1)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getDataBeetwenMarkers(data, ("<ul", ">", "pagination"), ("</ul", ">"), True)[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, r"""<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>{0}<""".format(page + 1))[0])
        tmp = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "content"), ("<div", ">", "footer"), True)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, ("<div", ">", "video"), ("</a", ">"))
        for item in tmp:
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, """title=['"]([^"^']+?)['"]""")[0])
            desc = self.cm.ph.getSearchGroups(item, """video-time">([^<]+)""")[0]
            if desc:
                desc = _("Duration: %s") % (desc)
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url, "icon": icon, "desc": desc})
            self.addVideo(params)
        if nextPage != "":
            params = dict(cItem)
            params.update({"title": _("Next page"), "url": nextPage, "page": page + 1})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("Tvfun.getLinksForVideo [%s]" % cItem)
        urlTab = []
        baseUrl = cItem["url"].replace("video/", "watch/")
        sts, data = self.getPage(baseUrl)
        if not sts:
            return
        tmp = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "VideoServers"), ("</div", ">"), True)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, "<button", ("</button", ">"))
        for item in tmp:
            tmpUrl = b64decode(self.cm.ph.getSearchGroups(item, """setVideo.+?['"]([^"^']+?)['"]""")[0][2:])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("server color", ">"), ("</button", ">"), False)[1])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmpUrl, """src=['"]([^"^']+?)['"]""")[0])
            urlTab.append({"name": title, "url": url, "need_resolve": 1})
        return urlTab

    def getVideoLinks(self, url):
        printDBG("Tvfun.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return []

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None and not category:
            self.listMainMenu({"name": "category", "type": "category"})
        elif category == "listItems":
            self.listItems(self.currItem, "explore_item")
        elif category == "explore_item":
            self.exploreItems(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Tvfun(), True, [])
