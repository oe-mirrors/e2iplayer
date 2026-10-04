# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - wpolsce.pl is now wpolsce24.tv (Nuxt site with a JSON CMS API):
#   live channel (OnNetwork player), latest video articles, the channel's programmes
#   (YouTube playlists), news sections (video articles only, /api/cms/articles) and search
#   (/api/cms/search); OnNetwork embeds resolved here (embed.php -> frame<ver>.php ->
#   playerVideos: HLS variants + MP4) + watched flag / downloaded flag / sidecar / favourites.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.youtubeparser import YouTubeParser
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://wpolsce24.tv/"


ICON_PRESET = "?p=wpolsce_article_single_standard_small"
COVER_PRESET = "?p=wpolsce_article_single_standard_large"
ONNETWORK_URL = "https://video.onnetwork.tv/"
PAGE_SIZE = 60
MAX_PAGES_PER_LIST = 3


class WPolscePL(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what identifies a row and is needed to open it again
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "art_id", "page_id", "slug", "live", "page_ids")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "wpolsce24.tv", "cookie": "wpolsce24.tv.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.API_URL = self.MAIN_URL + "api/"
        self.DEFAULT_ICON_URL = self.getFullUrl("storage/files/2024/10/8/daabb25c-66d3-44d7-b035-634e57510aed/logo%20kwadrat.webp")
        self.ytp = None
        self.searchPageId = ""

        self.watchedHelper = IPTVWatchedHelper("wpolscepl")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url if url else ""
            if cItem.get("category", "") == "list_programme":
                return "folder:%s" % url if url else ""
            return ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # HTTP / API
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _getJson(self, url):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Accept": "application/json, text/plain, */*", "Origin": self.MAIN_URL.rstrip("/"), "Referer": self.MAIN_URL})
        sts, data = self.getPage(url, params)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printDBG("WPolscePL._getJson no JSON from %s" % url)
        return None

    def _dispatch(self, path):
        data = self._getJson(self.API_URL + "cms/dispatch?url=" + path)
        return data if isinstance(data, dict) else {}

    def _widgets(self, dispatchData, widgetType):
        try:
            widgets = dispatchData.get("layout", {}).get("widgets", {}) or {}
            return [w for w in widgets.values() if isinstance(w, dict) and w.get("widget") == widgetType]
        except Exception:
            printExc()
        return []

    def _pageIdsFromMenu(self, dispatchData):
        # basePath -> CMS page id; the main menu entries carry the id of their page
        pageIds = {}
        for widget in self._widgets(dispatchData, "menu"):
            for item in widget.get("data") or []:
                href = item.get("href", "") or ""
                if href.startswith("/") and item.get("id"):
                    pageIds[href] = str(item["id"])
        return pageIds

    def _picture(self, picture, preset=ICON_PRESET):
        try:
            url = (picture or {}).get("url", "")
            if url:
                return self.getFullIconUrl(url) + preset
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("WPolscePL.listMainMenu")
        params = dict(cItem)
        params.update({"good_for_fav": True, "title": "wPolsce24 - " + _("Live"), "category": "live", "url": self.getFullUrl("video"),
                       "live": True, "desc": _("Live stream of the %s channel") % "wPolsce24"})
        self.addVideo(params)
        params = dict(cItem)
        params.update({"good_for_fav": True, "title": _("Latest videos"), "category": "list_latest", "url": self.getFullUrl("video")})
        self.addDir(params)
        params = dict(cItem)
        params.update({"good_for_fav": True, "title": _("Programmes"), "category": "list_programmes", "url": self.getFullUrl("video")})
        self.addDir(params)

        data = self._dispatch("/video")
        pageIds = self._pageIdsFromMenu(data)
        seen = set()
        for widget in self._widgets(data, "menu"):
            if "główne" not in widget.get("name", "") or "header" not in widget.get("name", ""):
                continue
            for item in widget.get("data") or []:
                href = item.get("href", "") or ""
                title = self.cleanHtmlStr(item.get("name", ""))
                if not href.startswith("/") or href in seen or not title or href in ("/ramowka",):
                    continue
                seen.add(href)
                params = dict(cItem)
                params.update({"good_for_fav": True, "title": title, "category": "list_section", "url": self.getFullUrl(href.lstrip("/")),
                               "page_id": str(item.get("id", "")), "page_ids": pageIds})
                self.addDir(params)
        self.listsTab(self.searchItems(), cItem)

    def _addArticle(self, cItem, art, pageId=""):
        try:
            if not art.get("isVideoArticle") and art.get("isVideoArticle") is not None:
                return False
            url = art.get("url", "")
            if not url or not url.startswith(self.MAIN_URL):
                return False
            title = self.cleanHtmlStr(art.get("title", "") or art.get("shortTitle", ""))
            if not title:
                return False
            desc = []
            date = (art.get("datePublishedUtc", "") or "")[:16].replace("T", " ")
            if date:
                desc.append(date)
            if art.get("pageName"):
                desc.append(art["pageName"])
            text = " | ".join(desc)
            lead = self.cleanHtmlStr(art.get("lead", ""))
            if lead:
                text = "%s[/br]%s" % (text, lead) if text else lead
            # the article's own section page (the list may be "Najnowsze" with articles of all sections)
            pageId = (cItem.get("page_ids") or {}).get(art.get("basePath", ""), "") or pageId
            params = stripPagerKeys(dict(cItem), ("page_ids", "search_pattern"))
            params.update({"good_for_fav": True, "category": "article", "title": title, "url": url, "icon": self._picture(art.get("picture")),
                           "desc": text, "art_id": str(art.get("id", "")), "slug": art.get("slug", ""), "page_id": str(pageId or "")})
            self.addVideo(params)
            return True
        except Exception:
            printExc()
        return False

    def listLatest(self, cItem):
        printDBG("WPolscePL.listLatest")
        data = self._dispatch("/video")
        cItem = dict(cItem)
        cItem["page_ids"] = self._pageIdsFromMenu(data)
        for widget in self._widgets(data, "articles"):
            for art in (widget.get("data") or {}).get("items") or []:
                self._addArticle(cItem, art)

    def listProgrammes(self, cItem):
        printDBG("WPolscePL.listProgrammes")
        data = self._dispatch("/video")
        seen = set()
        for widget in self._widgets(data, "programs"):
            for prog in widget.get("data") or []:
                url = prog.get("basePath", "") or ""
                art = prog.get("article") or {}
                title = self.cleanHtmlStr(art.get("pageName", ""))
                if "list=" not in url or url in seen or not title:
                    continue
                seen.add(url)
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_programme", "title": title, "url": url,
                               "icon": self._picture(art.get("picture")), "desc": self.cleanHtmlStr(art.get("title", ""))})
                self.addDir(params)

    def listProgramme(self, cItem):
        printDBG("WPolscePL.listProgramme |%s|" % cItem.get("url", ""))
        if self.ytp is None:
            self.ytp = YouTubeParser()
            # EU: without the consent cookie YouTube answers with consent.youtube.com instead of the playlist;
            # Polish channel - ask for the original (not auto-translated) titles
            self.ytp.http_params["header"]["Cookie"] = "SOCS=CAI"
            self.ytp._getAcceptLanguage = lambda: "pl-PL,pl;q=0.9"
        try:
            items = self.ytp.getVideosApiPlayList(cItem["url"], "yt_video", cItem.get("page", 1), cItem) or []
        except Exception:
            printExc()
            items = []
        for item in items:
            if item.get("type") != "video" or not item.get("url"):
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "yt_video", "title": self.cleanHtmlStr(item.get("title", "")), "url": item["url"],
                           "icon": item.get("icon", ""), "desc": item.get("desc", "")})
            self.addVideo(params)
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No stream available"))

    def listSection(self, cItem):
        printDBG("WPolscePL.listSection |%s| page %s" % (cItem.get("url", ""), cItem.get("page", 1)))
        pageId = cItem.get("page_id", "")
        if not pageId:
            pageId = str((self._dispatch("/" + cItem["url"].replace(self.MAIN_URL, "", 1)).get("page") or {}).get("id", ""))
        if not pageId:
            return
        page = int(cItem.get("page", 1) or 1)
        lastPage = page - 1  # the last page actually read
        totalPages = page
        added = 0
        tpl = self.API_URL + "cms/articles?page=%s&index={page}&size=%d" % (pageId, PAGE_SIZE)
        # only video articles are listed - read on (max. MAX_PAGES_PER_LIST pages) until a few are there
        for index in range(page, page + MAX_PAGES_PER_LIST):
            data = self._getJson(tpl.format(page=index))
            if not isinstance(data, dict):
                break
            lastPage = index
            try:
                totalPages = int((data.get("meta") or {}).get("totalPages", 0) or 0)
            except Exception:
                totalPages = 0
            for item in data.get("items") or []:
                art = item.get("result", item) if isinstance(item, dict) else {}
                if self._addArticle(cItem, art, pageId):
                    added += 1
            if added >= 8 or index >= totalPages:
                break
        if lastPage >= page:
            addPagingItems(self, dict(cItem, page_id=pageId), lastPage, lastPage < totalPages, totalPages, tpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = cItem.get("search_pattern", "") or searchPattern
        printDBG("WPolscePL.listSearchResult [%s]" % searchPattern)
        if not self.searchPageId:
            self.searchPageId = str((self._dispatch("/wyszukiwarka").get("page") or {}).get("id", "") or "18")
        page = int(cItem.get("page", 1) or 1)
        tpl = self.API_URL + "cms/search?pageId=%s&websiteId=2&locale=pl&search=%s&index={page}&order=ASC&size=20&sort=DateCreatedUtc" % (self.searchPageId, urllib_quote_plus(searchPattern))
        data = self._getJson(tpl.format(page=page))
        if not isinstance(data, dict):
            return
        for item in data.get("items") or []:
            res = item.get("result") or {}
            meta = item.get("meta") or {}
            if res.get("module") != "CmsArticle" or not res.get("slug"):
                continue
            artUrl = self.getFullUrl("%s/%s,%s" % ((meta.get("baseUrl", "") or "").strip("/"), res["slug"], res.get("originId") or res.get("id")))
            title = self.cleanHtmlStr(res.get("title", ""))
            if not title:
                continue
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "article", "title": title, "url": artUrl, "icon": "",
                           "desc": self.cleanHtmlStr(res.get("description", "")), "art_id": str(res.get("originId") or res.get("id") or ""),
                           "slug": res["slug"], "page_id": str(res.get("pageId", "") or "")})
            self.addVideo(params)
        try:
            totalPages = int((data.get("meta") or {}).get("totalPages", 0) or 0)
        except Exception:
            totalPages = 0
        addPagingItems(self, dict(cItem, category="search_next_page", search_pattern=searchPattern), page, page < totalPages, totalPages, tpl)

    ###################################################
    # article / players
    ###################################################
    def _getArticle(self, cItem):
        # the article JSON (video type / url, lead, picture); via the API or the page itself
        artId = cItem.get("art_id", "")
        pageId = cItem.get("page_id", "")
        if artId and pageId:
            data = self._getJson(self.API_URL + "cms/articles/%s/page/%s?slug=%s" % (artId, pageId, cItem.get("slug", "")))
            if isinstance(data, dict) and isinstance(data.get("result"), dict):
                return data["result"]
        # no page id (favourite from elsewhere): the page's own section
        url = cItem.get("url", "")
        match = re.search(r'^https?://[^/]+(/[^/]+)/([^/,]+),(\d+)', url)
        if match:
            pageId = str((self._dispatch(match.group(1)).get("page") or {}).get("id", ""))
            if pageId:
                data = self._getJson(self.API_URL + "cms/articles/%s/page/%s?slug=%s" % (match.group(3), pageId, match.group(2)))
                if isinstance(data, dict) and isinstance(data.get("result"), dict):
                    return data["result"]
        return {}

    def _getOnNetworkLinks(self, embedUrl):
        printDBG("WPolscePL._getOnNetworkLinks [%s]" % embedUrl)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"]["Referer"] = self.MAIN_URL
        sts, data = self.getPage(embedUrl, params)
        if not sts:
            return []
        mid = self.cm.ph.getSearchGroups(data, r'"mid"\s*:\s*"([^"]+)"')[0]
        version = self.cm.ph.getSearchGroups(data, r'"version"\s*:\s*"(\d+)"')[0] or "86"
        if not mid:
            return []
        frameUrl = ONNETWORK_URL + "frame%s.php?mid=%s" % (version, mid)
        params["header"]["Referer"] = embedUrl
        sts, data = self.getPage(frameUrl, params)
        if not sts:
            return []
        videos = self.cm.ph.getDataBeetwenMarkers(data, "var playerVideos = ", "}];", False)[1]
        videos = (videos + "}]") if videos else "[]"
        try:
            videos = json_loads(videos)
        except Exception:
            printExc()
            return []
        urlTab = []
        for video in videos[:1]:
            hlsUrl = video.get("url", "")
            if self.cm.isValidUrl(hlsUrl) and ".m3u8" in hlsUrl:
                hls = getDirectM3U8Playlist(strwithmeta(hlsUrl, {"iptv_proto": "m3u8", "User-Agent": self.HEADER.get("User-Agent", "")}), checkExt=False, checkContent=True)
                hls = sorted(hls, key=lambda x: int(x.get("bitrate", 0) or 0), reverse=True)
                for item in hls:
                    item["need_resolve"] = 0
                    urlTab.append(item)
                if not hls:
                    urlTab.append({"name": "HLS", "url": strwithmeta(hlsUrl, {"iptv_proto": "m3u8"}), "need_resolve": 0})
            if not video.get("live"):
                for mp4 in video.get("urls") or []:
                    if self.cm.isValidUrl(mp4.get("url", "")):
                        urlTab.append({"name": "MP4 %s" % mp4.get("name", ""), "url": strwithmeta(mp4["url"], {"Referer": ONNETWORK_URL}), "need_resolve": 0})
        return urlTab

    def _getLiveUrl(self):
        for widget in self._widgets(self._dispatch("/video"), "video-stream"):
            url = (widget.get("data") or {}).get("liveVideoUrl", "")
            if url:
                return url
        return ""

    def getLinksForVideo(self, cItem):
        printDBG("WPolscePL.getLinksForVideo [%s]" % cItem.get("url", ""))
        category = cItem.get("category", "")
        if category == "yt_video":
            return applySidecarToLinks([{"name": "YouTube", "url": cItem["url"], "need_resolve": 1}], buildSidecarFromItem(cItem, IsSidecarEnabled()))
        if category == "live" or cItem.get("live"):
            url = self._getLiveUrl()
            if "onnetwork.tv" in url:
                return self._getOnNetworkLinks(url)
            if self.cm.isValidUrl(url):
                return [{"name": self.up.getHostName(url), "url": url, "need_resolve": 1}]
            SetIPTVPlayerLastHostError(_("The live stream is not available at the moment."))
            return []

        art = self._getArticle(cItem)
        if not art:
            return []
        sidecar = buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(art.get("lead", "")))
        videoType = (art.get("videoType", "") or "").lower()
        url = art.get("videoUrl", "") or ""
        if url.startswith("//"):
            url = "https:" + url
        urlTab = []
        if "onnetwork.tv" in url:
            urlTab = self._getOnNetworkLinks(url)
        elif self.cm.isValidUrl(url):
            urlTab = [{"name": self.up.getHostName(url) or videoType, "url": url, "need_resolve": 1}]
        else:
            videoId = art.get("video") or ""
            videoId = ensure_str(videoId) if not isinstance(videoId, (dict, list)) else ""
            if videoType == "youtube" and videoId:
                urlTab = [{"name": "YouTube", "url": "https://www.youtube.com/watch?v=" + videoId, "need_resolve": 1}]
        if not urlTab:
            if art.get("isPremium") or art.get("premiumVideoUrl"):
                SetIPTVPlayerLastHostError(_("This video is Premium-only content."))
            else:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urlTab, sidecar)

    def getVideoLinks(self, videoUrl):
        printDBG("WPolscePL.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("WPolscePL.getArticleContent [%s]" % cItem.get("url", ""))
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        if cItem.get("category") == "article":
            art = self._getArticle(cItem)
            if art:
                lead = self.cleanHtmlStr(art.get("lead", ""))
                body = self.cleanHtmlStr(" ".join([ensure_str(c) for c in (art.get("content") or []) if not isinstance(c, (dict, list))]))
                text = "[/br]".join([t for t in (lead, body) if t]) or text
                icon = self._picture(art.get("picture"), COVER_PRESET) or icon
                date = (art.get("datePublishedUtc", "") or "")[:16].replace("T", " ")
                if date:
                    otherInfo["released"] = date
                author = (art.get("author") or {}).get("userName", "")
                if author:
                    otherInfo["writer"] = author
                if art.get("pageName"):
                    otherInfo["category"] = art["pageName"]
        return [{"title": cItem.get("title", ""), "text": text,
                 "images": [{"title": "", "url": icon}] if icon else [],
                 "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("WPolscePL.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_latest":
            self.listLatest(self.currItem)
        elif category == "list_programmes":
            self.listProgrammes(self.currItem)
        elif category == "list_programme":
            self.listProgramme(self.currItem)
        elif category == "list_section":
            self.listSection(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, WPolscePL(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("wpolscepl")

    def withArticleContent(self, cItem):
        return cItem.get("category") in ("article", "live", "yt_video")
