# -*- coding: utf-8 -*-
LAST_MODIFIED = "25.10.2026"
# 25.10.2026 - new host
# Show TV (showtv.com.tr): free Turkish channel - live streams of Show TV and Show Türk (the time-shifted
# international feed, its site links all videos to showtv.com.tr), series and programmes with episodes,
# scenes and trailers. Lists come from the site's "daha fazla" JSON endpoints, the stream from the page's
# data-hope-video player JSON (own MP4 / HLS, Turkish VTT subtitles on some episodes, no DRM).
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://www.showtv.com.tr/"


MAIN = "https://www.showtv.com.tr"
LIST_URL = MAIN + "/%s/daha-fazla?page=%d"
VIDEOS_URL = MAIN + "/video/sezon/%s?base=%s&section=%s&limit=%d&page=%d"
SEARCH_URL = MAIN + "/arama?ara=%s"
SEARCH_VIDEOS_URL = MAIN + "/arama/daha-fazla?q=%s&type=videos&page=%d"
# the endpoint returns at most 50 videos per page
VIDEOS_PAGE_SIZE = 30
SEARCH_PAGE_SIZE = 12
CHANNELS = {
    "showtv": {"title": "Show TV", "page": MAIN + "/canli-yayin", "var": "STREAM", "referer": gettytul(),
               "fallback": "https://ciner.daioncdn.net/showtv/showtv.m3u8?ce=3&app=4bc856ef-4c68-4a94-bc87-37dfaaa66558"},
    "showturk": {"title": "Show Türk", "page": "https://www.showturk.com.tr/canli-yayin", "var": "videoUrl", "referer": "https://www.showturk.com.tr/",
                 "fallback": "https://ciner.daioncdn.net/showturk/showturk.m3u8?app=web"},
}

# kind of a show's video section, named by its "TÜMÜ" link
SECTION_TYPES = (("tum_bolumler", "episodes"), ("videolar", "episodes"), ("sahne", "scenes"), ("fragman", "trailers"))
SECTION_TITLES = {"episodes": "Bölümler", "scenes": "Sahneler", "trailers": "Fragmanlar"}

VIDEO_CARD_RE = re.compile(r'(?s)data-name="box-type7">\s*<a\s[^>]*?title="([^"]*)"[^>]*?href="([^"]+)"[^>]*>(.*?)</a>')
SHOW_CARD_RE = re.compile(r'(?s)<a\s[^>]*?href="(/(?:dizi|programlar)/tanitim/[^"]+/\d+)"[^>]*>(.*?)</a>')
EPISODE_RE = re.compile(r'sezon-(\d+)-bolum-(\d+)-izle/')


class ShowTV(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_id", "s_base", "section", "season",
                  "seasons", "episode", "channel", "live", "page")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "showtv", "cookie": "showtv.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Referer": gettytul()})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.watchedHelper = IPTVWatchedHelper("showtv")
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        return self.cm.getPage(url, addParams or self.defaultParams, post_data)

    def _json(self, url):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Accept="application/json", **{"X-Requested-With": "XMLHttpRequest"})
        sts, data = self.getPage(url, params)
        if not sts or not data:
            return {}
        try:
            data = json_loads(data)
            return data if isinstance(data, dict) else {}
        except Exception:
            printExc()
        return {}

    @staticmethod
    def _path(url):
        return re.sub(r'^https?://[^/]+', '', str(url or "").split("?", 1)[0].strip()).rstrip("/") or "/"

    @staticmethod
    def _full(url):
        url = str(url or "").replace("&amp;", "&")
        if url.startswith("//"):
            return "https:" + url
        return url if url.startswith("http") else MAIN + ("" if url.startswith("/") else "/") + url

    @staticmethod
    def _unescape(text):
        return text.replace("&quot;", '"').replace("&#039;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            path = self._path(cItem.get("url", ""))
            if not path or path == "/":
                return ""
            category = cItem.get("category", "")
            if cItem.get("type", "") == "video" and category == "st_video":
                return "video:%s" % path
            if category == "st_show":
                return "folder:%s" % path
            if category == "st_videos":
                return "folder:%s/%s%s" % (path, cItem.get("section", ""), "?season=%s" % cItem["season"] if cItem.get("season") else "")
        except Exception:
            printExc()
        return ""

    ###################################################
    # menu
    ###################################################
    def listMain(self, cItem):
        for key in ("showtv", "showturk"):
            channel = CHANNELS[key]
            self.addVideo(dict(cItem, good_for_fav=True, category="st_video", title="%s - %s" % (channel["title"], _("Live")),
                               url=channel["page"], channel=key, live=True, desc="%s Canlı Yayın" % channel["title"]))
        menu = [{"good_for_fav": True, "category": "st_shows", "title": "Diziler", "url": MAIN + "/diziler"},
                {"good_for_fav": True, "category": "st_shows", "title": "Programlar", "url": MAIN + "/programlar"}]
        self.listsTab(menu + self.searchItems(), cItem)

    ###################################################
    # shows
    ###################################################
    def _addShow(self, cItem, url, title, body):
        icon = self.cm.ph.getSearchGroups(body, r'<img[^>]+src="([^"]+)"')[0]
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'(?s)<span class="mb-4[^"]*">(.*?)</span>')[0])
        params = stripPagerKeys(dict(cItem), ("s_title", "s_id", "s_base", "section", "season", "seasons", "s_query"))
        params.update({"good_for_fav": True, "category": "st_show", "title": title, "s_title": title, "url": self._full(url),
                       "icon": self._full(icon) if icon else "", "desc": desc})
        self.addDir(params)

    def listShows(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        kind = self._path(cItem["url"]).strip("/")
        printDBG("ShowTV.listShows [%s] page %d" % (kind, page))
        data = self._json(LIST_URL % (kind, page))
        seen = set()
        for url, body in SHOW_CARD_RE.findall(data.get("html") or ""):
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'alt="([^"]+)"')[0])
            if not title or url in seen:
                continue
            seen.add(url)
            self._addShow(cItem, url, title, body)
        addPagingItems(self, dict(cItem, desc=""), page, bool(data.get("hasMore")), 0, cItem["url"])

    def listShow(self, cItem):
        url = cItem["url"]
        printDBG("ShowTV.listShow [%s]" % url)
        showId = self.cm.ph.getSearchGroups(url, r'/tanitim/[^/]+/(\d+)')[0]
        sts, data = self.getPage(url)
        if not sts or not showId:
            return
        base = "programs" if "/programlar/" in url else "series"
        seasons = []
        select = self.cm.ph.getDataBeetwenMarkers(data, 'onChangeSeason(', '</select>', False)[1]
        for num in re.findall(r'value="(\d+)"', select):
            if num not in seasons:
                seasons.append(num)
        sections = []
        for heading, link in re.findall(r'(?s)<h2 class="mb-5[^>]*>([^<]+)</h2>.*?title="TÜMÜ" href="([^"]+)"', data):
            kind = ""
            for marker, value in SECTION_TYPES:
                if "/%s/" % marker in link:
                    kind = value
                    break
            if not kind or kind in [x[0] for x in sections]:
                continue
            title = SECTION_TITLES[kind]
            if kind == "scenes" and self.cleanHtmlStr(heading).upper().startswith("SKE"):
                title = "Skeçler"
            sections.append((kind, title))
        for kind, title in sections:
            params = stripPagerKeys(dict(cItem), ("season",))
            params.update({"good_for_fav": True, "category": "st_videos", "title": title, "s_id": showId, "s_base": base, "section": kind,
                           "seasons": seasons if kind == "episodes" and len(seasons) > 1 else []})
            self.addDir(params)
        if not sections and 'data-hope-video="' in data:
            # a page with only its own video (film trailers)
            self.addVideo(dict(cItem, good_for_fav=True, category="st_video"))

    def _videoTitle(self, cItem, url, title):
        show = cItem.get("s_title", "")
        match = EPISODE_RE.search(url)
        if match and show and IsMediaNamingNormalized():
            return "%s - %s" % (show, formatSxxExx(match.group(1), match.group(2))), match.group(1), match.group(2)
        if show and show.lower() not in title.lower():
            title = "%s - %s" % (show, title)
        return title, match.group(1) if match else "", match.group(2) if match else ""

    def _addVideoCards(self, cItem, html):
        count = 0
        for title, url, body in VIDEO_CARD_RE.findall(html):
            title = self.cleanHtmlStr(title)
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(body, r'<img[^>]+src="([^"]+)"')[0]
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'(?s)<span class="mb-2\.5 line-clamp-2[^"]*">(.*?)</span>')[0])
            if "Alt Yaz" in body:
                desc = ("[Alt Yazılı] " + desc).strip()
            title, season, episode = self._videoTitle(cItem, url, title)
            params = stripPagerKeys(dict(cItem), ("seasons", "s_query"))
            params.update({"good_for_fav": True, "category": "st_video", "title": title, "url": self._full(url), "season": season,
                           "episode": episode, "icon": self._full(icon) if icon else cItem.get("icon", ""), "desc": desc})
            self.addVideo(params)
            count += 1
        return count

    def listVideos(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        season = cItem.get("season", "")
        if page == 1 and not season:
            # several seasons: one folder each (newest first) above the list of all episodes
            for num in cItem.get("seasons") or []:
                params = stripPagerKeys(dict(cItem))
                params.update({"good_for_fav": True, "title": _("Season %s") % num, "season": num, "seasons": []})
                self.addDir(params)
        url = VIDEOS_URL % (cItem.get("s_id", ""), cItem.get("s_base", "series"), cItem.get("section", "episodes"), VIDEOS_PAGE_SIZE, page)
        if season:
            url += "&season=%s" % season
        printDBG("ShowTV.listVideos [%s]" % url)
        data = self._json(url)
        self._addVideoCards(cItem, data.get("html") or "")
        addPagingItems(self, dict(cItem, desc=""), page, bool(data.get("hasMore")), 0, cItem["url"])

    ###################################################
    # search
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ShowTV.listSearchResult [%s]" % searchPattern)
        query = urllib_quote_plus(searchPattern.strip())
        sts, data = self.getPage(SEARCH_URL % query)
        if sts:
            # the results follow the heading; the header menu and footer name the current shows too
            data = data.split("Arama Sonu", 1)[-1].split("<footer", 1)[0]
            seen = set()
            for match in SHOW_CARD_RE.finditer(data):
                url, body = match.groups()
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'alt="([^"]+)"')[0])
                # result cards open in a new tab, the menus do not
                if not title or url in seen or 'target="_blank"' not in match.group(0).split(">", 1)[0]:
                    continue
                seen.add(url)
                self._addShow(cItem, url, title, body)
        self.listSearchVideos(dict(cItem, category="st_search_videos", s_query=query))

    def listSearchVideos(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        data = self._json(SEARCH_VIDEOS_URL % (cItem.get("s_query", ""), page))
        count = self._addVideoCards(dict(cItem, s_title=""), data.get("html") or "")
        # hasMore of the search endpoint is always false: a full page means there may be more
        addPagingItems(self, dict(cItem, desc=""), page, count >= SEARCH_PAGE_SIZE, 0, cItem.get("url", "") or MAIN)

    ###################################################
    # links
    ###################################################
    def _hlsLinks(self, url, label, meta):
        urlTab = []
        for item in getDirectM3U8Playlist(strwithmeta(url, dict(meta)), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999):
            name = "%sp" % item.get("height") if item.get("height") else "%d kbit/s" % (int(item.get("bitrate") or 0) // 1000)
            urlTab.append({"name": "%s %s" % (label, name), "url": strwithmeta(item["url"], dict(meta, iptv_proto="m3u8")), "need_resolve": 0,
                           "bitrate": int(item.get("bitrate") or 0)})
        urlTab.sort(key=lambda x: x["bitrate"], reverse=True)
        if urlTab:
            # the master itself: adaptive
            urlTab.append({"name": "%s (adaptive)" % label, "url": strwithmeta(url, dict(meta, iptv_proto="m3u8")), "need_resolve": 0})
        return urlTab

    def _liveLinks(self, cItem):
        channel = CHANNELS.get(cItem.get("channel", ""), CHANNELS["showtv"])
        sts, data = self.getPage(channel["page"], {"header": dict(self.HEADER, Referer=channel["referer"])})
        url = self.cm.ph.getSearchGroups(data, r'''var\s+%s\s*=\s*['"]([^'"]+\.m3u8[^'"]*)['"]''' % channel["var"])[0] if sts else ""
        meta = {"User-Agent": self.HEADER["User-Agent"], "Referer": channel["referer"], "Origin": channel["referer"].rstrip("/"),
                "iptv_livestream": True}
        urlTab = self._hlsLinks(url or channel["fallback"], "HLS", meta)
        if not urlTab and url:
            urlTab = self._hlsLinks(channel["fallback"], "HLS", meta)
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
        return urlTab

    def _playerData(self, data):
        player = self.cm.ph.getSearchGroups(data, r'data-hope-video="([^"]+)"')[0]
        try:
            player = json_loads(self._unescape(player)) if player else {}
        except Exception:
            printExc()
            player = {}
        return player if isinstance(player, dict) else {}

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("ShowTV.getLinksForVideo [%s]" % url)
        if cItem.get("live"):
            return self._liveLinks(cItem)
        sts, data = self.getPage(url)
        if not sts:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        player = self._playerData(data)
        media = player.get("media") if isinstance(player.get("media"), dict) else {}
        meta = {"User-Agent": self.HEADER["User-Agent"], "Referer": gettytul(), "Origin": MAIN}
        subTracks = []
        for sub in player.get("subtitles") or []:
            if isinstance(sub, dict) and str(sub.get("src", "")).startswith("http"):
                lang = sub.get("srclang") or "tr"
                subTracks.append({"title": "Türkçe" if lang == "tr" else lang, "url": sub["src"], "lang": lang, "format": "vtt"})
        if subTracks:
            meta["external_sub_tracks"] = subTracks
        urlTab = []
        mp4s = [x for x in media.get("mp4") or [] if isinstance(x, dict) and str(x.get("src", "")).startswith("http")]
        mp4s.sort(key=lambda x: int(self.cm.ph.getSearchGroups(str(x.get("label", "")), r'(\d+)')[0] or 0), reverse=True)
        for item in mp4s:
            urlTab.append({"name": "MP4 %s" % item.get("label", ""), "url": strwithmeta(item["src"], dict(meta)), "need_resolve": 0})
        for item in media.get("m3u8") or []:
            if isinstance(item, dict) and str(item.get("src", "")).startswith("http"):
                urlTab.extend(self._hlsLinks(item["src"], "HLS", meta))
                break
        if not urlTab:
            # the VideoObject names the 1080p MP4 too
            mp4 = self.cm.ph.getSearchGroups(data, r'"contentUrl"\s*:\s*"(https?://[^"]+\.mp4)"')[0]
            if mp4:
                urlTab.append({"name": "MP4", "url": strwithmeta(mp4, dict(meta)), "need_resolve": 0})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        return []

    ###################################################
    # info / favourites
    ###################################################
    @staticmethod
    def _isoDuration(value):
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$', str(value or ""))
        if not match or not any(match.groups()):
            return ""
        seconds = int(match.group(1) or 0) * 3600 + int(match.group(2) or 0) * 60 + int(match.group(3) or 0)
        return "%d:%02d:%02d" % (seconds // 3600, seconds % 3600 // 60, seconds % 60)

    def getArticleContent(self, cItem):
        printDBG("ShowTV.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        if cItem.get("live"):
            otherInfo["status"] = _("On Air")
            return [{"title": title, "text": cItem.get("desc", ""), "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]+)"')[0])
            if desc:
                text = desc
            if cItem.get("category") == "st_video":
                video = data.split('"@type":"VideoObject"', 1)
                video = video[1][:4000] if len(video) > 1 else ""
                date = self.cm.ph.getSearchGroups(video, r'"uploadDate"\s*:\s*"(\d{4}-\d\d-\d\d)')[0]
                if date:
                    otherInfo["released"] = date
                duration = self._isoDuration(self.cm.ph.getSearchGroups(video, r'"duration"\s*:\s*"([^"]+)"')[0])
                if duration:
                    otherInfo["duration"] = duration
                if cItem.get("season") and cItem.get("episode"):
                    otherInfo["episodes"] = formatSxxExx(cItem["season"], cItem["episode"])
            image = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
            if image and not icon:
                icon = image
        return [{"title": title, "text": text or title, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("st_"):
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
        printDBG("ShowTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({"name": "category"})
        elif category == "st_shows":
            self.listShows(self.currItem)
        elif category == "st_show":
            self.listShow(self.currItem)
        elif category == "st_videos":
            self.listVideos(self.currItem)
        elif category == "st_search_videos":
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
        CHostBase.__init__(self, ShowTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("showtv")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("st_video", "st_show")
