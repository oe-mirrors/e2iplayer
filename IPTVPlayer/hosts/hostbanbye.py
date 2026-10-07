# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - new host for BanBye (banbye.com, Polish video platform)
#   Everything comes from the public JSON API on api.banbye.com:
#   /videos?sort=new|views&category=<key>&channelId=<id>&limit&offset, /channels?sort=subscriptionsCount,
#   /search?query=&entity=all, /videos/<id> (INFO). The stream is asked for with
#   POST /videos/<id>/url -> {"src": {"hls": {"masterPlaylist": ...}} or {"mp4": {"levels": {...}}}}.
#   Lists are paged with First page / Jump / Next page (limit 40, last page from "count").
#   Watched flag / downloaded flag / sidecar / INFO / favourites. Titles stay as the uploaders wrote them
#   (user videos, no film naming).
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://banbye.com/"


# category keys of the site and their labels (from its English UI)
def categories():
    return [("news", _("News")), ("newsPoland", _("News Poland")), ("politics", _("Politics")), ("history", _("History")),
            ("education", _("Education")), ("science", _("Science")), ("health", _("Health")), ("economy", _("Economy")), ("law", _("Law")),
            ("religion", _("Religion")), ("philosophy", _("Philosophy")), ("patriotism", _("Patriotism")), ("military", _("Military")),
            ("intervention", _("Intervention")), ("family", _("Family")), ("upbringing", _("Upbringing")), ("kids", _("Kids")), ("movie", _("Movie")),
            ("music", _("Music")), ("entertainment", _("Entertainment")), ("art", _("Art")), ("books", _("Books")), ("gaming", _("Gaming")),
            ("sport", _("Sport")), ("technology", _("Technology")), ("automotive", _("Automotive")), ("tourism", _("Tourism")),
            ("cooking", _("Cooking")), ("lifestyle", _("Lifestyle")), ("fashion", _("Fashion")), ("animals", _("Animals")),
            ("tutorials", _("Tutorials"))]


class BanBye(GenericFolderWatchedScraperMixin, CBaseHostClass):
    API = "https://api.banbye.com"
    LIMIT = 40
    FAV_FIELDS = ("name", "category", "type", "url", "title", "video_id", "channel_id", "channel", "icon", "api_url", "live")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "banbye", "cookie": "banbye.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept": "application/json, text/plain, */*", "Origin": "https://banbye.com", "Referer": "https://banbye.com/"})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://banbye.com/_nuxt/icons/icon_512x512.5406dd.png"
        self.MENU = [{"category": "list_videos", "title": _("Latest"), "api_url": "/videos?sort=new"},
                     {"category": "list_videos", "title": _("Most viewed"), "api_url": "/videos?sort=views"},
                     {"category": "list_categories", "title": _("Categories")},
                     {"category": "list_channels", "title": _("Channels"), "api_url": "/channels?sort=subscriptionsCount&sortDesc=true"}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("banbye")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            if cItem.get("type", "") == "video" and cItem.get("video_id"):
                return "video:%s" % cItem["video_id"]
            if cItem.get("category", "") == "list_videos" and cItem.get("channel_id"):
                return "channel:%s" % cItem["channel_id"]
            return ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _api(self, path, post=None):
        url = path if path.startswith("http") else self.API + path
        params = dict(self.defaultParams)
        postData = None
        if post is not None:
            params["header"] = dict(self.HEADER, **{"Content-Type": "application/json"})
            params["raw_post_data"] = True
            postData = json_dumps(post)
        sts, data = self.cm.getPage(url, params, postData)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def _pagedApi(self, cItem, path):
        # (page, json) of the 1-based cItem["page"] of a limit/offset listing
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except Exception:
            page = 1
        sep = "&" if "?" in path else "?"
        return page, self._api("%s%slimit=%d&offset=%d" % (path, sep, self.LIMIT, (page - 1) * self.LIMIT))

    def _addPager(self, cItem, path, page, data):
        try:
            count = int(data.get("count") or 0)
        except Exception:
            count = 0
        got = len(data.get("items") or [])
        lastPage = (count + self.LIMIT - 1) // self.LIMIT if count else 0
        hasNext = got > 0 and (page < lastPage if lastPage else got >= self.LIMIT)
        # the listing is read from api_url + page; the url only carries the page for "Jump"
        addPagingItems(self, cItem, page, hasNext, lastPage, "%s%s#page={page}" % (self.API, path))

    def _duration(self, seconds):
        try:
            seconds = int(float(seconds or 0))
        except Exception:
            return ""
        if seconds <= 0:
            return ""
        if seconds >= 3600:
            return "%d:%02d:%02d" % (seconds // 3600, seconds % 3600 // 60, seconds % 60)
        return "%d:%02d" % (seconds // 60, seconds % 60)

    def _addVideoItem(self, cItem, video):
        vid = video.get("_id", "")
        title = self.cleanHtmlStr(video.get("title", ""))
        if not vid or not title:
            return
        channel = self.cleanHtmlStr((video.get("channel") or {}).get("name", ""))
        live = bool(video.get("live")) and not video.get("livestreamEndedAt")
        icon = video.get("ogImageUrl", "") or ("%s/1080.jpg" % video["thumbnailBaseUrl"] if video.get("thumbnailBaseUrl") else "")
        descTab = [x for x in (self._duration(video.get("duration")), (video.get("publishedAt") or "")[:10], channel,
                               "%s: %s" % (_("Views"), video["views"]) if video.get("views") is not None else "") if x]
        params = self._childParams(cItem)
        params.update({"good_for_fav": True, "category": "video", "title": title, "url": "https://banbye.com/watch/%s" % vid,
                       "video_id": vid, "channel": channel, "icon": icon, "live": live,
                       "desc": " | ".join(descTab) + ("[/br]" + self.cleanHtmlStr(video["desc"]) if video.get("desc") else "")})
        self.addVideo(params)

    def _addChannelItem(self, cItem, channel):
        cid = channel.get("_id", "")
        name = self.cleanHtmlStr(channel.get("name", ""))
        if not cid or not name:
            return
        icon = self.getFullIconUrl(channel["avatarUrl"]) if channel.get("avatarUrl") else ""
        descTab = ["%s: %s" % (_("Videos"), channel.get("videoCount", 0)), "%s: %s" % (_("Subscribers"), channel.get("subscriptionsCount", 0))]
        params = self._childParams(cItem)
        params.update({"good_for_fav": True, "category": "list_videos", "title": name, "channel_id": cid, "channel": name,
                       "icon": icon, "api_url": "/videos?channelId=%s&sort=new" % cid,
                       "desc": " | ".join(descTab) + ("[/br]" + self.cleanHtmlStr(channel["description"]) if channel.get("description") else "")})
        self.addDir(params)

    @staticmethod
    def _childParams(cItem):
        # a row of a (paged) list: must not inherit the list's page / search state
        return stripPagerKeys(dict(cItem), ("search_pattern", "url"))

    ###################################################
    # lists
    ###################################################
    def listCategories(self, cItem):
        for key, label in categories():
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_videos", "title": label, "api_url": "/videos?category=%s&sort=new" % key})
            self.addDir(params)

    def listVideos(self, cItem):
        path = cItem.get("api_url", "/videos?sort=new")
        page, data = self._pagedApi(cItem, path)
        printDBG("BanBye.listVideos |%s| page %d" % (path, page))
        if not isinstance(data, dict):
            return
        for video in data.get("items") or []:
            if isinstance(video, dict):
                self._addVideoItem(cItem, video)
        self._addPager(cItem, path, page, data)

    def listChannels(self, cItem):
        path = cItem.get("api_url", "/channels?sort=subscriptionsCount&sortDesc=true")
        page, data = self._pagedApi(cItem, path)
        printDBG("BanBye.listChannels page %d" % page)
        if not isinstance(data, dict):
            return
        for channel in data.get("items") or []:
            if isinstance(channel, dict):
                self._addChannelItem(cItem, channel)
        self._addPager(cItem, path, page, data)

    def listSearch(self, cItem):
        pattern = cItem.get("search_pattern", "")
        path = "/search?query=%s&entity=all&sort=new&sortDesc=true" % urllib_quote_plus(pattern)
        page, data = self._pagedApi(cItem, path)
        printDBG("BanBye.listSearch [%s] page %d" % (pattern, page))
        if not isinstance(data, dict):
            return
        for entry in data.get("items") or []:
            if not isinstance(entry, dict):
                continue
            if isinstance(entry.get("video"), dict):
                self._addVideoItem(cItem, entry["video"])
            elif isinstance(entry.get("channel"), dict):
                self._addChannelItem(cItem, entry["channel"])
        self._addPager(cItem, path, page, data)

    def listSearchResult(self, cItem, searchPattern, searchType):
        cItem = dict(cItem)
        cItem.update({"category": "list_search", "search_pattern": searchPattern, "page": 1})
        self.listSearch(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        vid = cItem.get("video_id", "")
        printDBG("BanBye.getLinksForVideo [%s]" % vid)
        if not vid:
            return []
        data = self._api("/videos/%s/url" % vid, {})
        if not isinstance(data, dict) or not isinstance(data.get("src"), dict):
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        src = data["src"]
        live = bool(cItem.get("live"))
        meta = {"User-Agent": self.HEADER.get("User-Agent", ""), "Referer": "https://banbye.com/", "Origin": "https://banbye.com"}
        urltab = []
        hls = src.get("hls") or {}
        if hls.get("masterPlaylist"):
            master = strwithmeta(hls["masterPlaylist"], dict(meta, iptv_proto="m3u8", iptv_livestream=live))
            if not live:
                for item in getDirectM3U8Playlist(master, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999):
                    item["need_resolve"] = 0
                    urltab.append(item)
            if not urltab:
                urltab.append({"name": "HLS", "url": master, "need_resolve": 0})
        levels = hls.get("levels") or {}
        if not urltab and isinstance(levels, dict):
            for q in sorted(levels.keys(), key=lambda x: -int(x) if str(x).isdigit() else 0):
                urltab.append({"name": "HLS %sp" % q, "url": strwithmeta(levels[q], dict(meta, iptv_proto="m3u8")), "need_resolve": 0})
        mp4 = (src.get("mp4") or {}).get("levels") or {}
        if isinstance(mp4, dict):
            for q in sorted(mp4.keys(), key=lambda x: -int(x) if str(x).isdigit() else 0):
                urltab.append({"name": "MP4 %sp" % q, "url": strwithmeta(mp4[q], meta), "need_resolve": 0})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        if live:
            return urltab
        desc = self.cleanHtmlStr((data.get("video") or {}).get("desc", ""))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), desc))

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        vid = cItem.get("video_id", "")
        printDBG("BanBye.getArticleContent [%s]" % vid)
        otherInfo = {}
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        if vid:
            data = self._api("/videos/%s" % vid)
            if isinstance(data, dict):
                text = self.cleanHtmlStr(data.get("desc", "")) or text
                icon = data.get("ogImageUrl", "") or icon
                if self._duration(data.get("duration")):
                    otherInfo["duration"] = self._duration(data.get("duration"))
                if data.get("publishedAt"):
                    otherInfo["released"] = data["publishedAt"][:10]
                if data.get("views") is not None:
                    otherInfo["views"] = str(data["views"])
                if data.get("categories"):
                    otherInfo["genres"] = ", ".join([str(x) for x in data["categories"]])
        if cItem.get("channel"):
            otherInfo["station"] = cItem["channel"]
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

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
        printDBG("BanBye.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_videos":
            self.listVideos(self.currItem)
        elif category == "list_channels":
            self.listChannels(self.currItem)
        elif category == "list_categories":
            self.listCategories(self.currItem)
        elif category == "list_search":
            self.listSearch(self.currItem)
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
        CHostBase.__init__(self, BanBye(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("banbye")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video"
