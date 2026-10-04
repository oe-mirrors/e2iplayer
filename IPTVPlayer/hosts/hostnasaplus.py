# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - new host for NASA+ (plus.nasa.gov)
#   The site is WordPress: everything comes from its public REST API
#   (/wp-json/wp/v2/video with series / topic taxonomies and ?search=, the video's
#   meta "video-url" is a plain HLS master on nasaplus.akamaized.net; a few entries only
#   carry a YouTube id) and /wp-json/nasaplus/v1/live-streams for the live channels.
#   Watched flag / downloaded flag / name normalisation ("Series - SxxExx - Title",
#   "Title (Year)") / sidecar / INFO / favourites / paging (First / Jump / Next, X-WP-TotalPages).
#   Live streams get no watched key.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://plus.nasa.gov/"


# leading / trailing quotes around an episode name (plain and typographic; works on py2 utf-8 str too)
QUOTES_RE = re.compile(r'(?:^(?:\s|"|\'|“|”|‘|’)+)|(?:(?:\s|"|\'|“|”|‘|’)+$)')


class NasaPlus(GenericFolderWatchedScraperMixin, CBaseHostClass):
    API = "https://plus.nasa.gov/wp-json/wp/v2/"
    LIVE_API = "https://plus.nasa.gov/wp-json/nasaplus/v1/live-streams"
    PER_PAGE = 40
    VIDEO_FIELDS = "id,date,link,title,content,meta,series,featured_media,_links,_embedded"
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "video_id", "video_url", "youtube", "icon",
                  "series_name", "episode", "year", "live", "api_url", "term_id", "taxonomy", "desc")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "nasaplus", "cookie": "nasaplus.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER["Accept"] = "application/json, text/plain, */*"
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://plus.nasa.gov/wp-content/uploads/2023/03/nasa-png-placeholder.png"
        self.seriesNames = None
        self.MENU = [{"category": "list_videos", "title": _("Latest videos"), "api_url": self._videosUrl()},
                     {"category": "list_live", "title": _("Live")},
                     {"category": "list_terms", "title": _("Series"), "taxonomy": "series"},
                     {"category": "list_terms", "title": _("Topics"), "taxonomy": "topic"}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("nasaplus")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            if cItem.get("type", "") == "video":
                url = self.wfNormalizeUrlKey(cItem.get("url", ""))
                return "video:%s" % url if url else ""
            if cItem.get("category", "") == "list_videos" and cItem.get("term_id"):
                return "%s:%s" % (cItem.get("taxonomy", ""), cItem["term_id"])
            return ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _videosUrl(self, extra=""):
        url = "%svideo?per_page=%d&_embed=wp:featuredmedia&_fields=%s" % (self.API, self.PER_PAGE, self.VIDEO_FIELDS)
        return url + extra

    def _json(self, url):
        params = dict(self.defaultParams)
        params.update({"with_metadata": True, "collect_all_headers": True})
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return None, {}
        meta = getattr(data, "meta", {}) or {}
        try:
            return json_loads(data), meta
        except Exception:
            printExc()
        return None, meta

    def _getSeriesNames(self):
        if self.seriesNames is None:
            self.seriesNames = {}
            data, _meta = self._json("%sseries?per_page=100&_fields=id,name" % self.API)
            for term in data if isinstance(data, list) else []:
                try:
                    self.seriesNames[term["id"]] = self.cleanHtmlStr(term.get("name", ""))
                except Exception:
                    continue
        return self.seriesNames

    def _icon(self, video):
        try:
            media = (video.get("_embedded") or {}).get("wp:featuredmedia") or []
            src = media[0].get("source_url", "") if media and isinstance(media[0], dict) else ""
            if src:
                # WordPress VIP resizes on the fly - the originals are multi-MB PNGs
                return src.split("?", 1)[0] + "?w=480"
        except Exception:
            printExc()
        return ""

    def _duration(self, seconds):
        try:
            seconds = int(seconds or 0)
        except Exception:
            return ""
        if seconds <= 0:
            return ""
        if seconds >= 3600:
            return "%d:%02d:%02d" % (seconds // 3600, seconds % 3600 // 60, seconds % 60)
        return "%d:%02d" % (seconds // 60, seconds % 60)

    def _videoTitle(self, title, seriesName, episode, season, year, contentType):
        if seriesName and episode:
            # "Far Out: "Sailing On Sunlight"" -> "Far Out - S01E03 - Sailing On Sunlight"
            rest = title
            if rest.lower().startswith(seriesName.lower()):
                rest = rest[len(seriesName):].lstrip(" :-|")
            rest = QUOTES_RE.sub("", rest) or title
            sxe = "S%sE%s" % (season or "1", episode)
            normalized = normalizeMediathekTitle("%s - %s" % (seriesName, rest), sxeHint=sxe)
            return normalized if normalized != "%s - %s" % (seriesName, rest) else title
        if contentType.lower() == "movie":
            return normalizeMediathekTitle(title, year=year, isMovie=True)
        return title

    ###################################################
    # lists
    ###################################################
    def listTerms(self, cItem):
        taxonomy = cItem.get("taxonomy", "series")
        printDBG("NasaPlus.listTerms %s" % taxonomy)
        data, _meta = self._json("%s%s?per_page=100&orderby=name&_fields=id,name,count,description" % (self.API, taxonomy))
        if not isinstance(data, list):
            return
        for term in data:
            try:
                if int(term.get("count", 0) or 0) <= 0:
                    continue
                title = self.cleanHtmlStr(term.get("name", ""))
                if not title:
                    continue
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_videos", "title": title, "term_id": term["id"],
                               "desc": "%s: %s[/br]%s" % (_("Videos"), term.get("count", 0), self.cleanHtmlStr(term.get("description", ""))),
                               "api_url": self._videosUrl("&%s=%s" % (taxonomy, term["id"]) + ("&orderby=date&order=asc" if taxonomy == "series" else "")),
                               "page": 0})
                self.addDir(params)
            except Exception:
                printExc()

    def listVideos(self, cItem):
        page = int(cItem.get("page", 0) or 0) or 1
        url = cItem.get("api_url", "") or self._videosUrl()
        if cItem.get("search_pattern"):
            url = self._videosUrl("&search=%s" % urllib_quote_plus(cItem["search_pattern"]))
        printDBG("NasaPlus.listVideos page %d |%s|" % (page, url))
        data, meta = self._json("%s&page=%d" % (url, page))
        if not isinstance(data, list):
            return
        names = self._getSeriesNames()
        for video in data:
            try:
                vmeta = video.get("meta") or {}
                videoUrl = vmeta.get("video-url", "") or ""
                youtube = vmeta.get("youtube-url", "") or ""
                if not videoUrl and not youtube:
                    continue
                title = self.cleanHtmlStr((video.get("title") or {}).get("rendered", ""))
                if not title:
                    continue
                seriesName = ""
                for sid in video.get("series") or []:
                    seriesName = names.get(sid, "")
                    if seriesName:
                        break
                year = (video.get("date") or "")[:4]
                episode = re.sub(r"\D", "", str(vmeta.get("episode-num", "") or ""))
                season = re.sub(r"\D", "", str(vmeta.get("season", "") or ""))
                plot = self.cleanHtmlStr((video.get("content") or {}).get("rendered", ""))
                descTab = [x for x in (self._duration(vmeta.get("runtime")), (video.get("date") or "")[:10], seriesName, vmeta.get("rating", "")) if x]
                params = stripPagerKeys(dict(cItem), ("search_pattern",))
                params.update({"good_for_fav": True, "category": "video", "url": video.get("link", ""), "video_id": video.get("id", ""),
                               "video_url": videoUrl, "youtube": youtube, "icon": self._icon(video), "s_title": title,
                               "series_name": seriesName, "episode": episode, "year": year,
                               "title": self._videoTitle(title, seriesName, episode, season, year, vmeta.get("content-type", "") or ""),
                               "desc": " | ".join(descTab) + ("[/br]" + plot if plot else "")})
                self.addVideo(params)
            except Exception:
                printExc()
        try:
            totalPages = int(meta.get("x-wp-totalpages", 0) or 0)
        except Exception:
            totalPages = 0
        hasNext = page < totalPages if totalPages else len(data) >= self.PER_PAGE
        # the page number drives the request; the template (the same API url) only gives Jump its target
        addPagingItems(self, cItem, page, bool(data) and hasNext, totalPages, url + "&page={page}")

    def listLive(self, cItem):
        printDBG("NasaPlus.listLive")
        data, _meta = self._json(self.LIVE_API)
        if not isinstance(data, list):
            return
        for stream in data:
            try:
                url = stream.get("live-stream-link") or ""
                if not self.cm.isValidUrl(url):
                    continue
                title = self.cleanHtmlStr(stream.get("title", ""))
                if "mediatailor" in title.lower() or not title:
                    title = "NASA+ Live"
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "live", "title": title, "url": url, "live": True, "video_url": url})
                self.addVideo(params)
            except Exception:
                printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("NasaPlus.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_videos", "search_pattern": searchPattern, "page": 0})
        self.listVideos(cItem)

    ###################################################
    # links
    ###################################################
    def _refreshVideo(self, cItem):
        # favourites / old rows: read the video entry again for its current stream url
        vid = cItem.get("video_id", "")
        if not vid:
            return cItem.get("video_url", ""), cItem.get("youtube", ""), ""
        data, _meta = self._json("%svideo/%s?_fields=meta,content" % (self.API, vid))
        if not isinstance(data, dict):
            return cItem.get("video_url", ""), cItem.get("youtube", ""), ""
        vmeta = data.get("meta") or {}
        return vmeta.get("video-url", "") or "", vmeta.get("youtube-url", "") or "", self.cleanHtmlStr((data.get("content") or {}).get("rendered", ""))

    def getLinksForVideo(self, cItem):
        printDBG("NasaPlus.getLinksForVideo [%s]" % cItem.get("url", ""))
        if cItem.get("live"):
            url = cItem.get("video_url", "") or cItem.get("url", "")
            if not self.cm.isValidUrl(url):
                return []
            meta = {"iptv_proto": "m3u8", "iptv_livestream": True, "User-Agent": self.HEADER.get("User-Agent", "")}
            return [{"name": "HLS live", "url": strwithmeta(url, meta), "need_resolve": 0}]

        videoUrl, youtube, plot = self._refreshVideo(cItem)
        urltab = []
        if self.cm.isValidUrl(videoUrl):
            master = strwithmeta(videoUrl, {"iptv_proto": "m3u8", "User-Agent": self.HEADER.get("User-Agent", ""),
                                            "Referer": self.MAIN_URL, "Origin": self.MAIN_URL.rstrip("/")})
            for item in getDirectM3U8Playlist(master, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999):
                item["need_resolve"] = 0
                urltab.append(item)
            if not urltab:
                urltab.append({"name": "HLS", "url": master, "need_resolve": 0})
        if youtube:
            ytUrl = youtube if youtube.startswith("http") else "https://www.youtube.com/watch?v=%s" % youtube
            urltab.append({"name": "YouTube", "url": ytUrl, "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), plot))

    def getVideoLinks(self, videoUrl):
        printDBG("NasaPlus.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("NasaPlus.getArticleContent [%s]" % cItem.get("video_id", ""))
        otherInfo = {}
        text = cItem.get("desc", "")
        vid = cItem.get("video_id", "")
        if vid:
            data, _meta = self._json("%svideo/%s?_fields=date,content,meta" % (self.API, vid))
            if isinstance(data, dict):
                vmeta = data.get("meta") or {}
                text = self.cleanHtmlStr((data.get("content") or {}).get("rendered", "")) or text
                if self._duration(vmeta.get("runtime")):
                    otherInfo["duration"] = self._duration(vmeta.get("runtime"))
                for key, field in (("rating", "rating"), ("language", "language"), ("narrated-by", "director"), ("featuring", "actors")):
                    if vmeta.get(key):
                        otherInfo[field] = self.cleanHtmlStr(vmeta[key])
                if data.get("date"):
                    otherInfo["released"] = data["date"][:10]
        if cItem.get("series_name"):
            otherInfo["genres"] = cItem["series_name"]
        icon = cItem.get("icon", "")
        return [{"title": cItem.get("s_title", cItem.get("title", "")), "text": text,
                 "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

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
        printDBG("NasaPlus.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_videos":
            self.listVideos(self.currItem)
        elif category == "list_terms":
            self.listTerms(self.currItem)
        elif category == "list_live":
            self.listLive(self.currItem)
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
        CHostBase.__init__(self, NasaPlus(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("nasaplus")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" and not cItem.get("live")
