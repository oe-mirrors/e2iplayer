# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# ServusTV On (servustv.com): live channels and the free VOD catalogue through the public Red Bull
# content API (tv-api.redbull.com, namespace "stv"), streams from play.redbull.com (plain HLS, no DRM)
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def gettytul():
    return "https://www.servustv.com/"


API_URL = "https://tv-api.redbull.com/"
PRODUCT_URL = API_URL + "products/v5.3/stv/de/de/%s"
COLLECTION_URL = API_URL + "collections/v5.3/stv/de/de/%s"
SEARCH_URL = API_URL + "search/v5.1/stv/de/de/%s?offset=%d&q=%s"
PLAY_URL = "https://play.redbull.com/main/v1/stv/de/de/personal_computer/http/%s.m3u8?device_group=group_5"
IMAGE_SIZE = "im:i:w_640"
PAGE_SIZE = 20
SEARCH_PAGE_SIZE = 15

# page ids of the web app (clientConfiguration api_ids) and the "Kategorien" rail of the start page
HOME_PRODUCT = "PN-discover"
SHOWS_PRODUCT = "sendungen"
SPORT_PRODUCT = "PN7TCNATC1Q2LSY"
NEWS_PRODUCT = "PN9LZVQR5OAL00U"
EPG_PRODUCT = "epg"
CATEGORIES_COLLECTION = "1d9e083e-5b80-4f57-96dd-24d1e7cc6e27"

# rails without content for us: personal lists (need an account), promo banners / newsletter links
SKIP_LIST_TYPES = ("reference",)
SKIP_COLLECTION_TYPES = ("promo", "small_promo")
# badges already shown elsewhere or meaningless as text
SKIP_BADGES = ("duration",)

STV_ID_RE = re.compile(r'/(?:video|page)/(?:page:)?([A-Za-z0-9_-]+)')


class ServusTV(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "stv_id", "s_title", "season", "episode",
                  "icon", "desc", "live", "playable")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "servustv", "cookie": "servustv.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept": "application/json", "Referer": "https://www.servustv.com/", "Origin": "https://www.servustv.com"})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/servustv135.png")
        # first page of the collections a product page was listed with (opening a rail right after needs no request)
        self.colCache = {}
        self.MENU = [{"category": "stv_live", "title": _("Live channels")},
                     {"category": "stv_product", "title": _("Home page"), "stv_id": HOME_PRODUCT},
                     {"category": "stv_product", "title": _("Shows"), "stv_id": SHOWS_PRODUCT},
                     {"category": "stv_collection", "title": _("Categories"), "stv_id": CATEGORIES_COLLECTION},
                     {"category": "stv_product", "title": _("Sport"), "stv_id": SPORT_PRODUCT},
                     {"category": "stv_product", "title": _("News"), "stv_id": NEWS_PRODUCT}] + self.searchItems()
        for item in self.MENU:
            if item.get("stv_id"):
                item["url"] = self._pageUrl(item["stv_id"]) if item["category"] == "stv_product" else COLLECTION_URL % item["stv_id"]

        self.watchedHelper = IPTVWatchedHelper("servustv")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            url = self.wfNormalizeUrlKey(cItem.get("url", ""))
            if not url:
                return ""
            if cItem.get("type", "") == "video":
                return "video:%s" % url
            if cItem.get("category", "") in ("stv_product", "stv_collection") and cItem.get("stv_id") not in (HOME_PRODUCT, SHOWS_PRODUCT, SPORT_PRODUCT, NEWS_PRODUCT, CATEGORIES_COLLECTION):
                return "folder:%s" % url
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _json(self, url):
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts or not data:
            return {}
        try:
            data = json_loads(data)
            return data if isinstance(data, dict) else {}
        except Exception:
            printExc()
        return {}

    @staticmethod
    def _pageUrl(stvId):
        return "https://www.servustv.com/de/page/%s" % stvId

    @staticmethod
    def _videoUrl(stvId):
        return "https://www.servustv.com/de/video/%s" % stvId

    def _stvId(self, cItem):
        stvId = cItem.get("stv_id", "")
        if not stvId:
            match = STV_ID_RE.search(cItem.get("url", ""))
            if match:
                stvId = match.group(1)
        return stvId

    @staticmethod
    def _image(card, keys=("rbtv_display_art_landscape", "rbtv_background_landscape", "rbtv_channel_square", "rbtv_display_art_portrait")):
        res = card.get("media_resources") or {}
        for key in keys:
            url = (res.get(key) or {}).get("url", "")
            if url:
                return url.replace("{im}", IMAGE_SIZE)
        return ""

    def _episodeTitle(self, show, title, season, episode):
        if IsMediaNamingNormalized() and show and season and episode:
            tag = "%s - %s" % (show, formatSxxExx(season, episode))
            return "%s - %s" % (tag, title) if title and title != show else tag
        if show and title and show.lower() not in title.lower():
            return "%s - %s" % (show, title)
        return title or show

    def _cardDesc(self, card):
        desc = []
        if card.get("content_entitlements"):
            desc.append(_("Login needed"))
        for badge in card.get("badges") or []:
            value = self.cleanHtmlStr(str(badge.get("value") or ""))
            if value and badge.get("type") not in SKIP_BADGES and badge.get("display", "text") == "text":
                desc.append(value)
        if card.get("formatted_duration"):
            desc.append(card["formatted_duration"])
        start = str(card.get("start_time") or "")
        if len(start) >= 16:
            desc.append("%s %s" % (start[:10], start[11:16]))
        line = " | ".join(desc)
        text = self.cleanHtmlStr(card.get("long_description") or card.get("short_description") or "")
        sub = self.cleanHtmlStr(card.get("subheading") or "")
        if sub and sub not in text and sub != self.cleanHtmlStr(card.get("show_name") or ""):
            text = "%s[/br]%s" % (sub, text) if text else sub
        if line and text:
            return "%s[/br]%s" % (line, text)
        return line or text

    ###################################################
    # rows
    ###################################################
    def _addCard(self, cItem, card):
        try:
            stvId = card.get("id", "")
            cardType = card.get("type", "")
            contentType = card.get("content_type", "")
            title = self.cleanHtmlStr(card.get("title") or "")
            if not stvId or not title or cardType not in ("video", "page"):
                # "any" = promo / newsletter link to another site
                return False
            params = stripPagerKeys(dict(cItem), ("search_pattern", "s_title", "season", "episode", "playable"))
            params.update({"good_for_fav": True, "stv_id": stvId, "icon": self._image(card) or cItem.get("icon", ""),
                           "desc": self._cardDesc(card), "live": False})
            if cardType == "page":
                params.update({"category": "stv_product", "title": title, "url": self._pageUrl(stvId)})
                self.addDir(params)
                return True
            params.update({"url": self._videoUrl(stvId), "playable": card.get("playable") is not False})
            if contentType == "video_channel":
                params.update({"title": title, "live": True})
            elif contentType == "episode":
                show = self.cleanHtmlStr(card.get("show_name") or "")
                season = str(card.get("season_number") or "")
                episode = str(card.get("episode_number") or "")
                params.update({"title": self._episodeTitle(show, title, season, episode), "s_title": show,
                               "season": season, "episode": episode})
            else:
                params["title"] = title
            self.addVideo(params)
            return True
        except Exception:
            printExc()
        return False

    ###################################################
    # lists
    ###################################################
    def listLive(self, cItem):
        data = self._json(PRODUCT_URL % EPG_PRODUCT)
        for col in data.get("collections") or []:
            colData = self._json(COLLECTION_URL % col.get("id", ""))
            cards = [c for c in colData.get("cards") or [] if c.get("content_type") == "video_channel"]
            if cards:
                for card in cards:
                    self._addCard(cItem, card)
                return

    def listProduct(self, cItem):
        stvId = self._stvId(cItem)
        printDBG("ServusTV.listProduct [%s]" % stvId)
        data = self._json(PRODUCT_URL % stvId)
        if data.get("type") == "video":
            # a favourite / link to a single video that is no folder
            self._addCard(cItem, data)
            return
        rails = []
        for col in data.get("collections") or []:
            colId = col.get("id", "")
            if not colId or col.get("list_type") in SKIP_LIST_TYPES:
                continue
            colData = self._json(COLLECTION_URL % colId)
            if colData.get("list_type") in SKIP_LIST_TYPES or colData.get("type") in SKIP_COLLECTION_TYPES or not colData.get("cards"):
                continue
            self.colCache[colId] = colData
            rails.append(colData)
        if len(rails) == 1:
            self._listCollectionData(cItem, rails[0], 1)
            return
        for colData in rails:
            total = int((colData.get("meta") or {}).get("total") or 0)
            params = stripPagerKeys(dict(cItem), ("search_pattern",))
            params.update({"good_for_fav": True, "category": "stv_collection", "stv_id": colData.get("id", ""),
                           "url": COLLECTION_URL % colData.get("id", ""),
                           "title": self.cleanHtmlStr(colData.get("label") or "") or _("Videos"),
                           "icon": self._image(colData["cards"][0]) or cItem.get("icon", ""),
                           "desc": "%s: %d" % (_("Videos"), total) if total else ""})
            self.addDir(params)

    def listCollection(self, cItem):
        colId = self._stvId(cItem) if cItem.get("stv_id") else cItem.get("url", "").rsplit("/", 1)[-1]
        page = max(1, int(cItem.get("page", 1) or 1))
        printDBG("ServusTV.listCollection [%s] page %d" % (colId, page))
        data = self.colCache.pop(colId, None) if page == 1 else None
        if not data:
            data = self._json((COLLECTION_URL % colId) + "?offset=%d" % ((page - 1) * PAGE_SIZE))
        self._listCollectionData(cItem, data, page)

    def _listCollectionData(self, cItem, data, page):
        for card in data.get("cards") or []:
            self._addCard(cItem, card)
        meta = data.get("meta") or {}
        total = int(meta.get("total") or 0)
        lastPage = (total + PAGE_SIZE - 1) // PAGE_SIZE
        # offset paging: a constant template only lets "Jump" through, the page number drives the list
        addPagingItems(self, dict(cItem, desc="", category="stv_collection", stv_id=data.get("id", ""),
                                  url=COLLECTION_URL % data.get("id", "")),
                       page, bool(meta.get("next")), lastPage, COLLECTION_URL % data.get("id", ""))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ServusTV.listSearchResult [%s]" % searchPattern)
        query = urllib_quote(searchPattern)
        shows = self._json(SEARCH_URL % ("shows", 0, query))
        for card in shows.get("cards") or []:
            self._addCard(cItem, card)
        cItem = dict(cItem, category="stv_search_videos", s_query=query, url=SEARCH_URL % ("videos", 0, query))
        self.listSearchVideos(cItem)

    def listSearchVideos(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        query = cItem.get("s_query", "")
        data = self._json(SEARCH_URL % ("videos", (page - 1) * SEARCH_PAGE_SIZE, query))
        for card in data.get("cards") or []:
            self._addCard(cItem, card)
        meta = data.get("meta") or {}
        total = int(meta.get("total") or 0)
        lastPage = (total + SEARCH_PAGE_SIZE - 1) // SEARCH_PAGE_SIZE
        addPagingItems(self, dict(cItem, desc=""), page, bool(meta.get("next")), lastPage, SEARCH_URL % ("videos", 0, query))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        stvId = self._stvId(cItem)
        printDBG("ServusTV.getLinksForVideo [%s]" % stvId)
        if not stvId:
            return []
        live = bool(cItem.get("live"))
        url = PLAY_URL % stvId
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Accept="*/*")
        sts, data = self.cm.getPage(url, params)
        if not sts or "#EXTM3U" not in (data or ""):
            code = (self.cm.meta or {}).get("status_code", 0)
            if code == 403 or "geo" in (data or "").lower():
                SetIPTVPlayerLastHostError(_("Not available in your country (geo-blocking)."))
            elif code in (401, 402) or "entitle" in (data or "").lower():
                SetIPTVPlayerLastHostError(_("This content needs a login - not supported."))
            elif cItem.get("playable") is False:
                SetIPTVPlayerLastHostError(_("Upcoming"))
            else:
                SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        # live channels redirect to the channel's own CDN master
        master = (self.cm.meta or {}).get("url", "") or url
        baseMeta = {"iptv_proto": "m3u8", "iptv_livestream": live, "User-Agent": self.HEADER.get("User-Agent"),
                    "Referer": "https://www.servustv.com/", "Origin": "https://www.servustv.com"}
        if live:
            return [{"name": "HLS live", "url": strwithmeta(master, baseMeta), "need_resolve": 0}]

        urlTab = []
        hls = getDirectM3U8Playlist(strwithmeta(master, dict(baseMeta)), checkExt=False, checkContent=True, mergeAltAudio=False)
        for item in hls:
            videoUrl = strwithmeta(item["url"])
            meta = dict(videoUrl.meta)
            meta.update(baseMeta)
            name = "%sp" % item.get("height") if item.get("height") else item.get("name", "HLS")
            audios = item.get("alt_audio_streams") or []
            if audios:
                audio = audios[0]
                for stream in audios:
                    if getattr(stream, "default", False):
                        audio = stream
                        break
                # fMP4 renditions with a separate audio playlist: muxed by ffmpeg
                meta.update({"audio_url": strwithmeta(audio.absolute_uri, dict(baseMeta)), "video_url": strwithmeta(videoUrl, dict(baseMeta)),
                             "iptv_use_ffmpeg": True, "ff_out_container": "matroska", "iptv_format": "mkv"})
                meta.pop("iptv_proto", None)
                url = self.up.decorateUrl("merge://audio_url|video_url", meta)
            else:
                url = strwithmeta(videoUrl, meta)
            urlTab.append({"name": name, "url": url, "need_resolve": 0, "bitrate": item.get("bitrate", 0)})
        try:
            urlTab.sort(key=lambda x: int(x.get("bitrate") or 0), reverse=True)
        except Exception:
            printExc()
        # the master itself: adaptive, and the only option for gstplayer (no merge:// support)
        urlTab.append({"name": "HLS (adaptive)", "url": strwithmeta(master, dict(baseMeta)), "need_resolve": 0})
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        return []

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("ServusTV.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        stvId = self._stvId(cItem)
        if stvId and cItem.get("category") != "stv_collection":
            data = self._json(PRODUCT_URL % stvId)
            if data:
                text = self.cleanHtmlStr(data.get("long_description") or data.get("short_description") or "") or text
                icon = self._image(data, ("rbtv_display_art_landscape", "rbtv_background_landscape")) or icon
                if data.get("formatted_duration"):
                    otherInfo["duration"] = data["formatted_duration"]
                if data.get("season_number") and data.get("episode_number"):
                    otherInfo["episodes"] = formatSxxExx(data["season_number"], data["episode_number"])
                if data.get("maturity_rating_austria"):
                    otherInfo["age_limit"] = data["maturity_rating_austria"]
                genres = ", ".join([g for g in (data.get("content_color") or data.get("tags") or []) if g])
                if genres:
                    otherInfo["genres"] = genres
                sunset = str(data.get("sunset_timestamp") or "")
                if sunset[:4].isdigit() and sunset[:4] < "2090":
                    otherInfo["remaining"] = _("available until %s") % sunset[:10]
                if data.get("content_entitlements"):
                    otherInfo["status"] = _("Login needed")
        if cItem.get("live"):
            otherInfo["status"] = _("On Air")
            if len(text) < 40:
                text = "%s - %s (ServusTV On)" % (title, _("Live channels"))
        elif not text:
            # system pages (Sport, Shows ...) carry no text of their own
            text = "%s - ServusTV On" % title
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("stv_") or cItem.get("type") == "video":
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
        printDBG("ServusTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "stv_live":
            self.listLive(self.currItem)
        elif category == "stv_product":
            self.listProduct(self.currItem)
        elif category == "stv_collection":
            self.listCollection(self.currItem)
        elif category == "stv_search_videos":
            self.listSearchVideos(self.currItem)
        elif category in ("search", "search_next_page"):
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
        CHostBase.__init__(self, ServusTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("servustv")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") == "stv_product"
