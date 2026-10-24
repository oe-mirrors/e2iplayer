# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host
# Kanal D (kanald.com.tr): free Turkish channel - live stream, current and archive series / programmes,
# Retro D and D-Shorts. Episode lists are read from the site's pages (seasons, ?page= paging), the stream
# of an episode from /actions/media?id=<data-saved-id> (own HLS) or the page's VideoObject contentUrl
# (own HLS) with the Dailymotion copy as fallback (metadata with the kanald.com.tr embedder, no DRM).
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetCookieDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://www.kanald.com.tr/"


MAIN = "https://www.kanald.com.tr"
MEDIA_URL = MAIN + "/actions/media?id=%s&p=1&pc=1"
SEARCH_URL = MAIN + "/actions/search?f=Title,TitleWithoutHypen&keyword=%s&top=%d&skip=%d&contentTypes=%s&orderBy=StartDate%%20-1"
SEARCH_SHOWS = "SerieContainer,TVShowContainer,MovieContainer"
SEARCH_VIDEOS = "Episode,TVShow,Clip,Movie"
SEARCH_PAGE_SIZE = 30
VOD_CDN = "https://kanaldvod.duhnet.tv/"
LIVE_URL = "https://demiroren.daioncdn.net/kanald/kanald.m3u8?app=kanald_web&ce=3"
DM_METADATA = "https://www.dailymotion.com/player/metadata/video/%s?embedder=%s"
DM_VIDEO = "https://www.dailymotion.com/video/%s"
# a list page with fewer cards than this is the last one (the pager of the site may name pages that are empty)
FULL_PAGE = 20

# sub pages of a show with videos (the others are news, photo galleries, cast, quizzes, the reels feed)
SHOW_TABS = ("bolumler", "fragmanlar", "ozel-klipler", "ozel-klip")

CARD_RE = re.compile(r'(?s)<a\s[^>]*?href="([^"]+)"[^>]*?data-saved-id="([0-9a-f]+)"[^>]*?card-type="video"[^>]*>(.*?)</a>')
POSTER_RE = re.compile(r'(?s)<a\s[^>]*?href="([^"]+)"[^>]*?class="poster-card[^"]*"[^>]*>(.*?)</a>')
# "Arka Sokaklar 749. Bölüm - SEZON FİNALİ", "79.Bölüm-VEDA", "Aşk-ı Memnu Bölüm 1"
EPISODE_RES = (re.compile(r'(\d+)\s*\.\s*[bB](?:ö|o|Ö|O)[lL](?:ü|u|Ü|U)[mM]'), re.compile(r'[bB](?:ö|o|Ö|O)[lL](?:ü|u|Ü|U)[mM]\s*(\d+)'))


class KanalD(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "media_id", "s_title", "season", "episode",
                  "eps", "live", "page")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "kanald", "cookie": "kanald.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Referer": gettytul()})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.DM_COOKIE = GetCookieDir("kanald.dailymotion.cookie")
        self.watchedHelper = IPTVWatchedHelper("kanald")
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        return self.cm.getPage(url, addParams or self.defaultParams, post_data)

    def _json(self, url):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Accept="application/json")
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
    def _dict(value):
        # a changed JSON shape (list / string instead of an object) is skipped, not an exception
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _path(url):
        return re.sub(r'^https?://[^/]+', '', str(url or "").split("?", 1)[0].strip()).rstrip("/") or "/"

    def _full(self, url):
        url = str(url or "").replace("&amp;", "&")
        if url.startswith("//"):
            return "https:" + url
        return url if url.startswith("http") else MAIN + ("" if url.startswith("/") else "/") + url

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
            if cItem.get("type", "") == "video" and category == "kd_video":
                return "video:%s" % path
            if category == "kd_show":
                return "folder:%s" % path
            if category == "kd_episodes":
                return "folder:%s%s" % (path, "?season=%s" % cItem["season"] if cItem.get("season") else "")
        except Exception:
            printExc()
        return ""

    ###################################################
    # menu
    ###################################################
    def listMain(self, cItem):
        live = {"good_for_fav": True, "category": "kd_video", "title": "Kanal D - %s" % _("Live"), "url": MAIN + "/canli-yayin",
                "live": True, "desc": "Kanal D Canlı Yayın"}
        menu = [{"good_for_fav": True, "category": "kd_posters", "title": "Güncel Diziler", "url": MAIN + "/diziler"},
                {"good_for_fav": True, "category": "kd_tabs", "title": "Arşiv Dizileri", "url": MAIN + "/diziler/arsiv"},
                {"good_for_fav": True, "category": "kd_posters", "title": "Güncel Programlar", "url": MAIN + "/programlar"},
                {"good_for_fav": True, "category": "kd_posters", "title": "Arşiv Programları", "url": MAIN + "/programlar/arsiv"},
                {"good_for_fav": True, "category": "kd_sections", "title": "Retro D", "url": MAIN + "/retro-d/"},
                {"good_for_fav": True, "category": "kd_sections", "title": "D-Shorts", "url": MAIN + "/d-shorts-diziler/"}]
        self.addVideo(dict(cItem, **live))
        self.listsTab(menu + self.searchItems(), cItem)

    def listTabs(self, cItem):
        # the archive: all / genre tabs of the listing
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        tabs = self.cm.ph.getDataBeetwenMarkers(data, 'class="listing-tabs"', '</ul>', False)[1]
        found = False
        for url, title in re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', tabs):
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "kd_posters", "title": self.cleanHtmlStr(title), "url": self._full(url), "desc": ""})
            self.addDir(params)
            found = True
        if not found:
            # no genre tabs: the posters of page 1, the next pages as a poster list
            count = self._listPosters(cItem, data, 1)
            lastPage = self._pager(data)
            baseUrl = cItem["url"].split("?", 1)[0]
            addPagingItems(self, dict(cItem, url=baseUrl, desc="", category="kd_posters"), 1, 1 < lastPage and count >= FULL_PAGE, lastPage, baseUrl)

    def listSections(self, cItem):
        # Retro D / D-Shorts start pages: one rail per genre with a "Tümünü Gör" link
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        for block in data.split('<section class="section fluid')[1:]:
            url = self.cm.ph.getSearchGroups(block, r'class="btn-link[^"]*"\s+href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="section-title[^"]*">(.*?)<(?:a|i|div)\b')[0])
            if not url or not title:
                continue
            icon = self.cm.ph.getSearchGroups(block, r'data-src="([^"]+)"')[0]
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "kd_posters", "title": title, "url": self._full(url),
                           "icon": self._full(icon) if icon else cItem.get("icon", ""), "desc": ""})
            self.addDir(params)

    ###################################################
    # shows
    ###################################################
    @staticmethod
    def _pager(data):
        pager = data.split('<ul class="pagination"', 1)
        if len(pager) < 2:
            return 0
        pages = [int(x) for x in re.findall(r'[?&;]page=(\d+)', pager[1].split('</ul>', 1)[0])]
        return max(pages) if pages else 0

    def _listPosters(self, cItem, data, page):
        region = ""
        for marker in ('class="listing-holder', 'class="dshorts-category-grid"'):
            if marker in data:
                region = data.split(marker, 1)[1].split('</section>', 1)[0]
                break
        count = 0
        seen = set()
        for url, body in POSTER_RE.findall(region):
            # D-Shorts posters point to the first episode of the series
            url = url.split("/bolumler/", 1)[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'(?s)class="title">(.*?)</h')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'alt="([^"]+)"')[0])
            if not title or url in seen:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(body, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(body, r'src="([^"]+)"')[0]
            params = stripPagerKeys(dict(cItem), ("s_title", "season", "eps"))
            params.update({"good_for_fav": True, "category": "kd_show", "title": title, "s_title": title, "url": self._full(url),
                           "icon": self._full(icon) if icon else "", "desc": ""})
            self.addDir(params)
            count += 1
        return count

    def listPosters(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        baseUrl = cItem["url"].split("?", 1)[0]
        printDBG("KanalD.listPosters [%s] page %d" % (baseUrl, page))
        sts, data = self.getPage(baseUrl if page == 1 else "%s?page=%d" % (baseUrl, page))
        if not sts:
            return
        count = self._listPosters(cItem, data, page)
        lastPage = self._pager(data)
        addPagingItems(self, dict(cItem, url=baseUrl, desc=""), page, page < lastPage and count >= FULL_PAGE, lastPage, baseUrl)

    def listShow(self, cItem):
        url = cItem["url"]
        printDBG("KanalD.listShow [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        path = self._path(url)
        tabs = []
        for tabUrl, title in re.findall(r'<a href="([^"]+)" class="breadcrumb-link[^"]*"[^>]*>(.*?)</a>', data):
            tab = self._path(tabUrl)
            if tab.startswith(path + "/") and tab.rsplit("/", 1)[-1] in SHOW_TABS and tab not in [t[0] for t in tabs]:
                tabs.append((tab, self.cleanHtmlStr(title)))
        if not tabs:
            # D-Shorts series and small shows: the episode list right away
            self.listEpisodes(dict(cItem, category="kd_episodes", url=MAIN + path + "/bolumler", eps=True))
            return
        for tab, title in tabs:
            params = stripPagerKeys(dict(cItem), ("season",))
            params.update({"good_for_fav": True, "category": "kd_episodes", "title": title, "url": MAIN + tab,
                           "eps": tab.endswith("/bolumler"), "desc": cItem.get("desc", "")})
            self.addDir(params)

    def _episodeTitle(self, cItem, title):
        show = cItem.get("s_title", "")
        epNum = ""
        rest = ""
        if cItem.get("eps"):
            for regex in EPISODE_RES:
                match = regex.search(title)
                if match:
                    epNum = match.group(1)
                    rest = title[match.end():].strip(" -/|:.")
                    break
        if epNum and show and IsMediaNamingNormalized():
            season = cItem.get("season", "")
            tag = "%s - %s" % (show, formatSxxExx(season, epNum) if season else "Bölüm %s" % epNum)
            return ("%s - %s" % (tag, rest) if rest else tag), epNum
        if show and show.lower() not in title.lower():
            return "%s - %s" % (show, title), epNum
        return title, epNum

    def _addCard(self, cItem, url, mediaId, body):
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'(?s)class="title">(.*?)</h')[0]) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'alt="([^"]+)"')[0])
        if not title:
            return False
        icon = self.cm.ph.getSearchGroups(body, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(body, r'src="([^"]+)"')[0]
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'<time>([^<]+)</time>')[0])
        text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'(?s)class="desc">(.*?)</div>')[0])
        title, epNum = self._episodeTitle(cItem, title)
        params = stripPagerKeys(dict(cItem), ("eps",))
        params.update({"good_for_fav": True, "category": "kd_video", "title": title, "url": self._full(url), "media_id": mediaId,
                       "icon": self._full(icon) if icon else cItem.get("icon", ""), "episode": epNum,
                       "desc": "[/br]".join(x for x in (duration, text) if x)})
        self.addVideo(params)
        return True

    def listEpisodes(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        baseUrl = cItem["url"].split("?", 1)[0]
        season = cItem.get("season", "")
        query = []
        if page > 1:
            query.append("page=%d" % page)
        if season:
            query.append("activeSeasonNumber=%s" % season)
        url = baseUrl + ("?" + "&".join(query) if query else "")
        printDBG("KanalD.listEpisodes [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        if page == 1 and not season and cItem.get("eps"):
            # several seasons: one folder each (newest first) above the list of all episodes
            seasons = []
            for num in re.findall(r'activeSeasonNumber=(\d+)[^"]*"[^>]*class="link"', data):
                if num not in seasons:
                    seasons.append(num)
            if len(seasons) > 1:
                for num in seasons:
                    params = stripPagerKeys(dict(cItem))
                    params.update({"good_for_fav": True, "category": "kd_episodes", "title": _("Season %s") % num, "url": baseUrl,
                                   "season": num, "eps": True})
                    self.addDir(params)
        holder = data.split('class="listing-holder', 1)
        count = 0
        for cardUrl, mediaId, body in CARD_RE.findall(holder[1] if len(holder) > 1 else ""):
            if self._addCard(cItem, cardUrl, mediaId, body):
                count += 1
        lastPage = self._pager(data)
        addPagingItems(self, dict(cItem, url=baseUrl, desc=""), page, page < lastPage and count >= FULL_PAGE, lastPage, baseUrl)

    ###################################################
    # search
    ###################################################
    def _searchShowTitle(self, item):
        for anc in reversed(item.get("ancestors") or []):
            if anc.get("contentType") in ("SerieContainer", "TVShowContainer", "MovieContainer"):
                return self.cleanHtmlStr(anc.get("title") or "")
        return self.cleanHtmlStr(item.get("originalName") or "")

    @staticmethod
    def _searchIcon(item):
        files = item.get("files") or []
        return ("https:" + files[0]["url"]) if files and str(files[0].get("url", "")).startswith("//") else ""

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KanalD.listSearchResult [%s]" % searchPattern)
        query = urllib_quote(searchPattern.strip())
        data = self._json(SEARCH_URL % (query, SEARCH_PAGE_SIZE, 0, SEARCH_SHOWS))
        for item in self._dict(data.get("data")).get("items") or []:
            if not isinstance(item, dict):
                continue
            title = self.cleanHtmlStr(item.get("title") or "")
            url = item.get("url") or ""
            if not title or not url:
                continue
            section = self.cleanHtmlStr(((item.get("ancestors") or [{}])[0]).get("title") or "").split("|", 1)[0].strip()
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "kd_show", "title": "%s (%s)" % (title, section) if section else title,
                           "s_title": title, "url": self._full(url), "icon": self._searchIcon(item),
                           "desc": self.cleanHtmlStr(item.get("description") or "")})
            self.addDir(params)
        self.listSearchVideos(dict(cItem, category="kd_search_videos", s_query=query))

    def listSearchVideos(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        query = cItem.get("s_query", "")
        data = self._dict(self._json(SEARCH_URL % (query, SEARCH_PAGE_SIZE, (page - 1) * SEARCH_PAGE_SIZE, SEARCH_VIDEOS)).get("data"))
        for item in data.get("items") or []:
            if not isinstance(item, dict):
                continue
            title = self.cleanHtmlStr(item.get("title") or "")
            url = item.get("url") or ""
            if not title or not url or not item.get("id"):
                continue
            show = self._searchShowTitle(item)
            # D-Shorts episodes are "Clip"s below .../bolumler/
            fake = {"s_title": show, "eps": item.get("contentType") == "Episode" or re.search(r'/bolum(?:ler)?/', url) is not None}
            title, epNum = self._episodeTitle(fake, title)
            desc = []
            if str(item.get("startDate") or "")[:4].isdigit():
                desc.append(str(item["startDate"])[:10])
            duration = int(item.get("duration") or 0)
            if duration:
                desc.append("%d:%02d:%02d" % (duration // 3600, duration % 3600 // 60, duration % 60))
            text = self.cleanHtmlStr(item.get("description") or "")
            line = " | ".join(desc)
            params = stripPagerKeys(dict(cItem), ("s_query", "eps"))
            params.update({"good_for_fav": True, "category": "kd_video", "title": title, "url": self._full(url), "media_id": item["id"],
                           "s_title": show, "episode": epNum, "icon": self._searchIcon(item),
                           "desc": "[/br]".join(x for x in (line, text if text != title else "") if x)})
            self.addVideo(params)
        total = int(data.get("count") or 0)
        lastPage = (total + SEARCH_PAGE_SIZE - 1) // SEARCH_PAGE_SIZE
        addPagingItems(self, dict(cItem, desc=""), page, page < lastPage, lastPage, cItem.get("url", "") or MAIN)

    ###################################################
    # links
    ###################################################
    @staticmethod
    def _quality(item):
        # D-Shorts are vertical (1080x1920): the short side names the quality
        sizes = [int(item.get(key) or 0) for key in ("width", "height")]
        sizes = [x for x in sizes if x]
        return "%dp" % min(sizes) if sizes else ""

    def _hlsLinks(self, url, label, live=False):
        baseMeta = {"iptv_proto": "m3u8", "User-Agent": self.HEADER["User-Agent"], "Referer": gettytul(), "Origin": MAIN}
        if live:
            baseMeta["iptv_livestream"] = True
        urlTab = []
        for item in getDirectM3U8Playlist(strwithmeta(url, dict(baseMeta)), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999, mergeAltAudio=False):
            name = self._quality(item) or "%d kbit/s" % (int(item.get("bitrate") or 0) // 1000)
            urlTab.append({"name": "%s %s" % (label, name), "url": item["url"], "need_resolve": 0, "bitrate": int(item.get("bitrate") or 0)})
        urlTab.sort(key=lambda x: x["bitrate"], reverse=True)
        if urlTab:
            # the master itself: adaptive
            urlTab.append({"name": "%s (adaptive)" % label, "url": strwithmeta(url, dict(baseMeta)), "need_resolve": 0})
        return urlTab

    def _vodUrl(self, link):
        path = str(link.get("securePath") or "")
        if not path:
            return ""
        if path.startswith("http"):
            return path
        base = link.get("serviceUrl") or link.get("defaultServiceUrl") or VOD_CDN
        return base.rstrip("/") + "/" + path.lstrip("/")

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("KanalD.getLinksForVideo [%s]" % url)
        if cItem.get("live"):
            sts, data = self.getPage(url)
            liveUrl = self.cm.ph.getSearchGroups(data, r'id="playerArea"[^>]*data-url="([^"]+\.m3u8[^"]*)"')[0] if sts else ""
            urlTab = self._hlsLinks(self._full(liveUrl) if liveUrl else LIVE_URL, "Kanal D", True)
            if not urlTab:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return urlTab

        data = ""
        mediaId = cItem.get("media_id", "")
        if not mediaId:
            # favourites / links without the id: the player of the page
            sts, data = self.getPage(url)
            mediaId = self.cm.ph.getSearchGroups(data, r'class="player-container"[^>]*data-id="([0-9a-f]+)"')[0] if sts else ""
        link = self._dict(self._dict(self._dict(self._json(MEDIA_URL % mediaId).get("data")).get("media")).get("link")) if mediaId else {}
        urlTab = []
        dmId = ""
        if "mpegurl" in str(link.get("type", "")).lower():
            urlTab = self._hlsLinks(self._vodUrl(link), "Kanal D")
        elif "dailymotion" in str(link.get("type", "")).lower():
            dmId = link.get("securePath", "")
        if not urlTab:
            # the page's VideoObject names the own HLS copy of most Dailymotion episodes
            if not data:
                sts, data = self.getPage(url)
                data = data if sts else ""
            hls = self.cm.ph.getSearchGroups(data, r'"contentUrl"\s*:\s*"([^"]+\.m3u8[^"]*)"')[0]
            if hls:
                urlTab = self._hlsLinks(self._vodUrl({"securePath": hls}), "Kanal D")
        if dmId:
            urlTab.append({"name": "Dailymotion", "url": strwithmeta(DM_VIDEO % dmId, {"Referer": url}), "need_resolve": 1})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def _dailymotionLinks(self, videoUrl):
        # the videos are limited to the kanald.com.tr player: the metadata needs that embedder
        videoId = self.cm.ph.getSearchGroups(videoUrl, r'/video/([A-Za-z0-9]+)')[0]
        if not videoId:
            return []
        header = self.cm.getDefaultHeader(browser="chrome")
        cookieParams = {"header": header, "use_cookie": True, "save_cookie": True, "load_cookie": True, "cookiefile": self.DM_COOKIE}
        sts, data = self.cm.getPage(DM_METADATA % (videoId, urllib_quote(gettytul(), safe="")), dict(cookieParams, load_cookie=False))
        try:
            data = json_loads(data) if sts else {}
        except Exception:
            printExc()
            data = {}
        if not isinstance(data, dict):
            data = {}
        if data.get("error"):
            error = data["error"]
            SetIPTVPlayerLastHostError(error.get("title") or error.get("raw_message") or _("Content not available"))
            return []
        urlTab = []
        for media in (data.get("qualities") or {}).get("auto") or []:
            if media.get("type") != "application/x-mpegURL" or not media.get("url"):
                continue
            hlsTab = getDirectM3U8Playlist(strwithmeta(media["url"], {"User-Agent": header["User-Agent"]}), checkExt=False, checkContent=True,
                                           sortWithMaxBitrate=99999999, cookieParams=cookieParams)
            cookieHeader = self.cm.getCookieHeader(self.DM_COOKIE)
            for item in hlsTab:
                meta = {"iptv_proto": "m3u8", "Cookie": cookieHeader, "User-Agent": header["User-Agent"]}
                urlTab.append({"name": "Dailymotion %s" % (self._quality(item) or item.get("name", "HLS")),
                               "url": strwithmeta(str(item["url"]).split("#", 1)[0], meta), "need_resolve": 0})
            break
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("KanalD.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if "dailymotion.com/video/" in videoUrl:
            return decorateResolvedLinkItems(self._dailymotionLinks(videoUrl), sidecar)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

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
        printDBG("KanalD.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        if cItem.get("live"):
            otherInfo["status"] = _("On Air")
            return [{"title": title, "text": "Kanal D Canlı Yayın", "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]
        url = cItem.get("url", "")
        if cItem.get("category") == "kd_episodes":
            url = url.rsplit("/", 1)[0]
        sts, data = self.getPage(url) if url else (False, "")
        if sts and cItem.get("category") == "kd_video":
            video = data.split('schema.org/VideoObject', 1)
            video = video[1][:4000] if len(video) > 1 else ""
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(video, r'"description"\s*:\s*"([^"]+)"')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'itemprop="description" content="([^"]+)"')[0])
            if desc:
                text = desc
            date = self.cm.ph.getSearchGroups(video, r'"uploadDate"\s*:\s*"(\d{4}-\d\d-\d\d)')[0]
            if date:
                otherInfo["released"] = date
            duration = self._isoDuration(self.cm.ph.getSearchGroups(video, r'"duration"\s*:\s*"([^"]+)"')[0])
            if duration:
                otherInfo["duration"] = duration
            image = self.cm.ph.getSearchGroups(video, r'"thumbnailUrl"\s*:\s*"([^"]+)"')[0]
            if image:
                icon = image
            if cItem.get("season") and cItem.get("episode"):
                otherInfo["episodes"] = formatSxxExx(cItem["season"], cItem["episode"])
            elif cItem.get("episode"):
                otherInfo["episodes"] = "Bölüm %s" % cItem["episode"]
        elif sts:
            container = self.cm.ph.getSearchGroups(data, r"globals\['Container'\]\s*=\s*(\{.*?\});\s*\n")[0]
            try:
                container = json_loads(container) if container else {}
            except Exception:
                container = {}
            if isinstance(container, dict) and container.get("title"):
                text = self.cleanHtmlStr(container.get("description") or "") or text
                if str(container.get("startDate") or "")[:4].isdigit() and not str(container["startDate"]).startswith("0001"):
                    otherInfo["first_air_date"] = str(container["startDate"])[:10]
                for anc in container.get("ancestors") or []:
                    if anc.get("title") and anc.get("contentType") == "Folder":
                        otherInfo["category"] = self.cleanHtmlStr(anc["title"]).split("|", 1)[0].strip()
                        break
                icon = icon or container.get("coverImageUrl") or ""
            if not text:
                text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]+)"')[0])
        return [{"title": title, "text": text or title, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("kd_"):
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
        printDBG("KanalD.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({"name": "category"})
        elif category == "kd_posters":
            self.listPosters(self.currItem)
        elif category == "kd_tabs":
            self.listTabs(self.currItem)
        elif category == "kd_sections":
            self.listSections(self.currItem)
        elif category == "kd_show":
            self.listShow(self.currItem)
        elif category == "kd_episodes":
            self.listEpisodes(self.currItem)
        elif category == "kd_search_videos":
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
        CHostBase.__init__(self, KanalD(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("kanald")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("kd_video", "kd_show", "kd_episodes")
