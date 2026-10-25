# -*- coding: utf-8 -*-
LAST_MODIFIED = "25.10.2026"
# 03.10.2026 - new host for BanBye (banbye.com, Polish video platform)
# 25.10.2026 - new site API (api.banbye.com/api), Trending, Live streams, Tags
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
    API = "https://api.banbye.com/api"
    LIMIT = 40
    FAV_FIELDS = ("name", "category", "type", "url", "title", "video_id", "channel_id", "channel", "icon", "api_url", "live")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "banbye", "cookie": "banbye.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept": "application/json, text/plain, */*", "Origin": "https://banbye.com", "Referer": "https://banbye.com/"})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://banbye.com/apple-icon.png"
        self.MENU = [{"category": "list_videos", "title": _("Latest"), "api_url": "/videos?sort=new"},
                     {"category": "list_trending", "title": _("Trending"), "api_url": "/videos/popular"},
                     {"category": "list_videos", "title": _("Most viewed"), "api_url": "/videos?sort=popular"},
                     {"category": "list_videos", "title": _("Live streams"), "api_url": "/videos/live"},
                     {"category": "list_categories", "title": _("Categories")},
                     {"category": "list_tags", "title": _("Tags")},
                     {"category": "list_channels", "title": _("Channels"), "api_url": "/channels?sort=popular"}] + self.searchItems()

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
    def _api(self, path):
        url = path if path.startswith("http") else self.API + path
        sts, data = self.cm.getPage(url, dict(self.defaultParams))
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except Exception:
            return 1

    def _pagedApi(self, cItem, path):
        # (page, json) of the 1-based cItem["page"] of a limit/offset listing
        page = self._page(cItem)
        sep = "&" if "?" in path else "?"
        return page, self._api("%s%slimit=%d&offset=%d" % (path, sep, self.LIMIT, (page - 1) * self.LIMIT))

    def _addPager(self, cItem, path, page, data):
        # the API only says "hasMore" (no total count), so Jump has no last page
        hasNext = bool(data.get("items")) and bool(data.get("hasMore"))
        # the listing is read from api_url + page; the url only carries the page for "Jump"
        addPagingItems(self, cItem, page, hasNext, 0, "%s%s#page={page}" % (self.API, path))

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

    @staticmethod
    def _image(image, width=""):
        # {"src": ".../480.webp", "srcSet": ".../144.webp 256w, ..., .../1080.webp 1920w"}; width e.g. "1280w" picks one of srcSet
        if not isinstance(image, dict):
            return ""
        if width:
            for entry in (image.get("srcSet") or "").split(","):
                entry = entry.strip().split(" ")
                if len(entry) == 2 and entry[1] == width:
                    return entry[0]
        return image.get("src", "") or ""

    @staticmethod
    def _isLive(video):
        return (video.get("live") or {}).get("state", "") == "live"

    def _addVideoItem(self, cItem, video):
        vid = video.get("id", "")
        title = self.cleanHtmlStr(video.get("title", ""))
        if not vid or not title:
            return
        channel = self.cleanHtmlStr((video.get("channel") or {}).get("name", ""))
        live = self._isLive(video)
        premiere = video.get("premiere") or {}
        state = _("Live") if live else (_("Upcoming") if premiere.get("at") and not premiere.get("endedAt") and not video.get("durationSeconds") else "")
        descTab = [x for x in (state, self._duration(video.get("durationSeconds")), (video.get("publishedAt") or "")[:10], channel,
                               "%s: %s" % (_("Views"), video["views"]) if video.get("views") is not None else "") if x]
        params = self._childParams(cItem)
        params.update({"good_for_fav": True, "category": "video", "title": title, "url": "https://banbye.com/watch/%s" % vid,
                       "video_id": vid, "channel": channel, "icon": self._image(video.get("thumbnail")), "live": live,
                       "desc": " | ".join(descTab)})
        self.addVideo(params)

    def _addChannelItem(self, cItem, channel):
        cid = channel.get("id", "")
        name = self.cleanHtmlStr(channel.get("name", ""))
        if not cid or not name:
            return
        params = self._childParams(cItem)
        params.update({"good_for_fav": True, "category": "list_videos", "title": name, "channel_id": cid, "channel": name,
                       "icon": self._image(channel.get("avatar"), "256w"), "api_url": "/videos?channelId=%s&sort=new" % cid,
                       "desc": "%s: %s" % (_("Subscribers"), channel.get("subscriptionsCount", 0))})
        self.addDir(params)

    @staticmethod
    def _childParams(cItem):
        # a row of a (paged) list: must not inherit the list's page / search state
        return stripPagerKeys(dict(cItem), ("search_pattern", "url", "cursor"))

    ###################################################
    # lists
    ###################################################
    def listCategories(self, cItem):
        for key, label in categories():
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_videos", "title": label, "api_url": "/videos?category=%s&sort=new" % key})
            self.addDir(params)

    def listTags(self, cItem):
        data = self._api("/tags/popular?limit=50")
        printDBG("BanBye.listTags")
        if not isinstance(data, list):
            return
        for entry in data:
            tag = entry.get("tag", "") if isinstance(entry, dict) else ""
            if not tag:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_videos", "title": "#%s" % tag, "desc": "%s: %s" % (_("Videos"), entry.get("count", 0)),
                           "api_url": "/videos?tag=%s&sort=new" % urllib_quote_plus(tag)})
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

    def listTrending(self, cItem):
        # ranking paged by cursor only: Next page carries it, First page (page 1) starts without
        page = self._page(cItem)
        cursor = cItem.get("cursor", "") if page > 1 else ""
        path = "%s?limit=%d" % (cItem.get("api_url", "/videos/popular"), self.LIMIT)
        if cursor:
            path += "&cursor=%s" % urllib_quote_plus(cursor)
        printDBG("BanBye.listTrending page %d" % page)
        data = self._api(path)
        if not isinstance(data, dict):
            return
        for video in data.get("items") or []:
            if isinstance(video, dict):
                self._addVideoItem(cItem, video)
        nextCursor = data.get("nextCursor") or ""
        addPagingItems(self, cItem, page, bool(nextCursor and data.get("items")), 0, "", {"cursor": nextCursor})

    def listChannels(self, cItem):
        path = cItem.get("api_url", "/channels?sort=popular")
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
        path = "/search?query=%s" % urllib_quote_plus(pattern)
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
        data = self._api("/videos/%s" % vid)
        playback = data.get("playback") if isinstance(data, dict) else None
        if not isinstance(playback, dict):
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        if playback.get("blocker") or data.get("ageGate"):
            # "preparing": older videos the site has not moved to its new storage yet (the site cannot play them either)
            printDBG("BanBye.getLinksForVideo blocker[%s] ageGate[%s]" % (playback.get("blocker"), data.get("ageGate")))
            SetIPTVPlayerLastHostError(_("Not available yet") if playback.get("blocker") == "preparing" else _("Content not available"))
            return []
        live = self._isLive(data)
        meta = {"User-Agent": self.HEADER.get("User-Agent", ""), "Referer": "https://banbye.com/", "Origin": "https://banbye.com"}
        urltab = []
        if playback.get("format") == "mp4":
            # qualities: [{"name", "label", "shortSide", "urls": [...]}]
            levels = [q for q in (playback.get("qualities") or []) if isinstance(q, dict) and q.get("urls")]
            levels.sort(key=lambda q: -int(q.get("shortSide")) if str(q.get("shortSide", "")).isdigit() else 0)
            for q in levels:
                urltab.append({"name": "MP4 %s" % (q.get("label") or q.get("name") or ""), "url": strwithmeta(q["urls"][0], meta), "need_resolve": 0})
            if not urltab:
                for url in playback.get("urls") or []:
                    urltab.append({"name": "MP4", "url": strwithmeta(url, meta), "need_resolve": 0})
        else:
            for url in (playback.get("urls") or [])[:1]:
                master = strwithmeta(url, dict(meta, iptv_proto="m3u8", iptv_livestream=live))
                if not live:
                    for item in getDirectM3U8Playlist(master, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999):
                        item["need_resolve"] = 0
                        urltab.append(item)
                if not urltab:
                    urltab.append({"name": "HLS", "url": master, "need_resolve": 0})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        if live:
            return urltab
        desc = self.cleanHtmlStr(data.get("description", ""))
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
                text = self.cleanHtmlStr((data.get("description") or "").replace("\n", "[/br]")) or text
                if data.get("tags"):
                    text += "[/br][/br]" + " ".join(["#%s" % x for x in data["tags"]])
                icon = self._image(data.get("thumbnail"), "1280w") or icon
                if self._duration(data.get("durationSeconds")):
                    otherInfo["duration"] = self._duration(data.get("durationSeconds"))
                if data.get("publishedAt"):
                    otherInfo["released"] = data["publishedAt"][:10]
                if data.get("views") is not None:
                    otherInfo["views"] = str(data["views"])
                if data.get("categories"):
                    labels = dict(categories())
                    otherInfo["genres"] = ", ".join([labels.get(x, str(x)) for x in data["categories"]])
                minimumAge = (data.get("restrictions") or {}).get("minimumAge")
                if minimumAge:
                    otherInfo["age_limit"] = "%s+" % minimumAge
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
        elif category == "list_trending":
            self.listTrending(self.currItem)
        elif category == "list_channels":
            self.listChannels(self.currItem)
        elif category == "list_categories":
            self.listCategories(self.currItem)
        elif category == "list_tags":
            self.listTags(self.currItem)
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
