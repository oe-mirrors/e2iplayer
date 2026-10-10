# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# MaxTVGO (maxtvgo.com): videos of Max Kolonko's MaxTV - subscription service, needs the user's own account
#   (e-mail + password in the host configuration)
# 10.10.2026 - host standard: login through the site's current ajax/login.php (the old login form is gone),
#   category folders that reopen from favourites, watched flag / downloaded marker on the video page url,
#   local paging for long lists, INFO with the video page text and the latest comments, sidecar, current user
#   agent; removed the two YouTube channels (both deleted on YouTube) and the Cloudflare path (no Cloudflare)
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
from Components.config import config, getConfigListEntry
###################################################
# E2 GUI COMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

config.plugins.iptvplayer.maxtvgo_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.maxtvgo_password = ConfigSecret(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login") + ":", config.plugins.iptvplayer.maxtvgo_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.maxtvgo_password))
    return optionList


def gettytul():
    return "https://maxtvgo.com/"


class MaxtvGO(GenericFolderWatchedScraperMixin, CBaseHostClass):

    # stable identity of a video row
    VIDEO_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc")
    PAGE_SIZE = 100

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "maxtvgo.com", "cookie": "maxtvgo.com.cookie"})
        self.DEFAULT_ICON_URL = "https://maxtvgo.com/images/logo_37.png"
        self.MAIN_URL = "https://maxtvgo.com/"
        self.HTTP_HEADER = {"User-Agent": self.cm.getDefaultUserAgent(), "Accept": "text/html", "Accept-Encoding": "gzip, deflate", "Referer": self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                                 "Accept": "application/json, text/javascript, */*; q=0.01", "Origin": self.getMainUrl()[:-1]})
        self.defaultParams = {"header": self.HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.loggedIn = None
        self.login = ""
        self.password = ""
        self.watchedHelper = IPTVWatchedHelper("maxtvgo")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(self.cm.iriToUri(baseUrl), addParams, post_data)

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, url.strip())
        if url == "" or "maxtvgo.com" not in url:
            return url
        return strwithmeta(url, {"Cookie": self.cm.getCookieHeader(self.COOKIE_FILE), "User-Agent": self.HTTP_HEADER["User-Agent"], "Referer": self.getMainUrl()})

    ###################################################
    # watched flag / favourites
    ###################################################
    def _isVideo(self, cItem):
        return cItem.get("type") == "video" and "video.php?film=" in cItem.get("url", "")

    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and self._isVideo(cItem):
                return "video:%s" % cItem["url"]
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if self._isVideo(cItem):
                return json_dumps(dict((key, cItem[key]) for key in self.VIDEO_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def _needLogin(self):
        if self.loggedIn:
            return False
        SetIPTVPlayerLastHostError(_("The host %s requires registration. \nPlease fill your login and password in the host configuration. Available under blue button.") % "maxtvgo.com")
        return True

    def listMainMenu(self, cItem):
        printDBG("MaxtvGO.listMainMenu")
        if self._needLogin():
            return
        MAIN_CAT_TAB = [{"category": "list_cats", "title": _("Categories"), "url": self.getFullUrl("/api/videos.php?action=find")}] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def _getCategories(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return []
        try:
            data = ensure_str_deep(json_loads(data))
            if data.get("error"):
                SetIPTVPlayerLastHostError(self.cleanHtmlStr(str((data["error"] or {}).get("message", ""))))
                if (data["error"] or {}).get("code") == "session_expired":
                    # the site logged the session out - log in again on the next call
                    self.loggedIn = None
                return []
            return data.get("data") or []
        except Exception:
            printExc()
        return []

    def _videoParams(self, item, category=""):
        title = self.cleanHtmlStr(item.get("title", ""))
        code = str(item.get("code", "") or "")
        if not title or not code:
            return None
        icon = str(item.get("vimeoPosterId", "") or "")
        icon = "https://i.vimeocdn.com/video/%s.jpg?mw=300" % icon if icon else self.getFullIconUrl(item.get("image", "") or "")
        desc = [x for x in (category, self.cleanHtmlStr(str(item.get("date", "") or "")), self.cleanHtmlStr(str(item.get("duration", "") or ""))) if x]
        desc = " | ".join(desc)
        text = self.cleanHtmlStr(item.get("description", "") or "")
        if text:
            desc += ("[/br]" if desc else "") + text
        return {"name": "category", "type": "video", "good_for_fav": True, "title": title, "url": self.getFullUrl("/video.php?film=") + code, "icon": icon, "desc": desc}

    def listCategories(self, cItem):
        printDBG("MaxtvGO.listCategories")
        for item in self._getCategories(cItem["url"]):
            title = self.cleanHtmlStr(item.get("name", ""))
            if title and item.get("videos"):
                self.addDir({"name": "category", "category": "list_items", "title": title, "url": cItem["url"], "f_cat": title, "good_for_fav": True})

    def _addRows(self, cItem, rows):
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        lastPage = (len(rows) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        for params in rows[(page - 1) * self.PAGE_SIZE:page * self.PAGE_SIZE]:
            self.addVideo(params)
        if lastPage > 1:
            addPagingItems(self, cItem, page, page < lastPage, lastPage, cItem.get("url", ""))

    def listItems(self, cItem):
        printDBG("MaxtvGO.listItems [%s]" % cItem.get("f_cat", ""))
        rows = []
        for item in self._getCategories(cItem["url"]):
            category = self.cleanHtmlStr(item.get("name", ""))
            if cItem.get("f_cat") and category != cItem["f_cat"]:
                continue
            for video in item.get("videos") or []:
                params = self._videoParams(video, category)
                if params and params["url"] not in [x["url"] for x in rows]:
                    rows.append(params)
        self._addRows(cItem, rows)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MaxtvGO.listSearchResult [%s]" % searchPattern)
        if self._needLogin():
            return
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("/api/videos.php?action=find&fullText=") + urllib_quote_plus(searchPattern)
        cItem.pop("f_cat", None)
        self.listItems(cItem)
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No matching entries found."))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("MaxtvGO.getLinksForVideo [%s]" % cItem.get("url", ""))
        if self._needLogin():
            return []
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        if "login.php" in self.cm.meta.get("url", ""):
            self.loggedIn = None
            SetIPTVPlayerLastHostError(_("Login failed."))
            return []
        retTab = []
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "<video", "</video>")[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(tmp, "<source", ">"):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, """src=['"]([^'^"]+?)['"]""")[0])
            if not self.cm.isValidUrl(url):
                continue
            typ = self.cm.ph.getSearchGroups(item, """type=['"]([^'^"]+?)['"]""")[0].lower()
            if "mp4" in typ or "mpegurl" in typ or ".m3u8" in url:
                url = strwithmeta(url, {"Cookie": cookieHeader, "User-Agent": self.HTTP_HEADER["User-Agent"], "Referer": cItem["url"]})
                retTab.append({"name": "m3u8" if ("mpegurl" in typ or ".m3u8" in url) else "mp4", "url": url, "need_resolve": 0})
        tmp = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "player"), ("</div", ">"), False)[1]
        videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, """<iframe[^>]+?src=['"]([^"^']+?)['"]""", 1, True)[0], self.cm.meta["url"])
        if self.cm.isValidUrl(videoUrl):
            retTab.append({"name": self.up.getHostName(videoUrl), "url": strwithmeta(videoUrl, {"Referer": self.cm.meta["url"]}), "need_resolve": 1})
        if not retTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
        return applySidecarToLinks(retTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("MaxtvGO.getVideoLinks [%s]" % videoUrl)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))

    ###################################################
    # login
    ###################################################
    def tryTologin(self):
        printDBG("MaxtvGO.tryTologin start")
        login = config.plugins.iptvplayer.maxtvgo_login.value
        password = config.plugins.iptvplayer.maxtvgo_password.value
        if self.loggedIn is not None and self.login == login and self.password == password:
            return self.loggedIn
        self.login = login
        self.password = password
        self.loggedIn = False
        rm(self.COOKIE_FILE)
        if not login.strip() or not password.strip():
            return False
        httpParams = dict(self.defaultParams)
        httpParams["header"] = dict(self.AJAX_HEADER)
        httpParams["header"]["Referer"] = self.getFullUrl("/login.php")
        sts, data = self.getPage(self.getFullUrl("/ajax/login.php"), httpParams, {"email": login, "pass": password, "typ": "logowanie"})
        message = ""
        if sts:
            try:
                data = ensure_str_deep(json_loads(data))
                if data.get("success"):
                    printDBG("MaxtvGO.tryTologin OK")
                    self.loggedIn = True
                    return True
                message = self.cleanHtmlStr(data.get("message", ""))
            except Exception:
                printExc()
        self.sessionEx.open(MessageBox, "\n".join([x for x in (_("Login failed."), message) if x]), type=MessageBox.TYPE_ERROR, timeout=10)
        return False

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("MaxtvGO.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        desc = cItem.get("desc", "")
        icon = cItem.get("icon", "") or self.DEFAULT_ICON_URL
        if self.loggedIn:
            sts, data = self.getPage(cItem["url"])
            if sts and "login.php" not in self.cm.meta.get("url", ""):
                tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "video-title"), ("</p", ">"), False)[1])
                if tmp:
                    title = tmp
                tmp = self.cm.ph.getDataBeetwenNodes(data, ("<video", ">"), ("</video", ">"))[1]
                tmp = self.cm.ph.getSearchGroups(tmp, """poster=['"]([^'^"]+?)['"]""")[0]
                if tmp:
                    icon = self.getFullIconUrl(tmp)
                text = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "chat_round"), ("<div", ">", "CommentsSection"))[1].replace("</p>", "[/br]"))
                if text:
                    desc = text
                videoID = self.cm.ph.getSearchGroups(data, """(<input[^>]+?videoID[^>]+?>)""", 1, True)[0]
                videoID = self.cm.ph.getSearchGroups(videoID, r"""\svalue=['"]([^'^"]+?)['"]""", 1, True)[0]
                if videoID:
                    # the latest comments (one request)
                    sts, data = self.getPage(self.getFullUrl("/api/comments.php?action=get&videoID=%s" % videoID))
                    try:
                        comments = []
                        for item in (ensure_str_deep(json_loads(data)).get("data") or []) if sts else []:
                            comments.append("%s | %s[/br]%s" % (self.cleanHtmlStr(item.get("date", "")), self.cleanHtmlStr(item.get("nick", "")), self.cleanHtmlStr(item.get("text", ""))))
                        if comments:
                            desc = "[/br][/br]".join([desc] + comments) if desc else "[/br][/br]".join(comments)
                    except Exception:
                        printExc()
        return [{"title": title, "text": desc or title, "images": [{"title": "", "url": icon}], "other_info": {}}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        self.tryTologin()
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_cats":
            self.listCategories(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category in ["search", "search_next_page"]:
            searchPattern = self.currItem.get("search_pattern", searchPattern)
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category", "category": "search_next_page", "search_pattern": searchPattern})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MaxtvGO(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("maxtvgo")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" and "maxtvgo.com" in cItem.get("url", "")
