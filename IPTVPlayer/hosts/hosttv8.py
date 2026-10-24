# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host
#   - TV8 Turkey (tv8.com.tr): free catch-up of the channel's own shows and series, live stream
#   - shows from the site menu / programme page, video tabs per show through the site's JSON (Ajax/icerik/haberler)
#   - links: direct HLS of video-cdn.tv8.com.tr (variants) + the MP4 of the page, live HLS of daioncdn.net
#   - search: the site only has a Google search box, so the show names are searched
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://www.tv8.com.tr/"


MAIN_URL = "https://www.tv8.com.tr/"
IMG_URL = "https://img.tv8.com.tr/"
PROGRAMMES_URL = MAIN_URL + "programlar"
LIVE_URL = MAIN_URL + "canli-yayin"
LIVE_ICON = IMG_URL + "s/template/v2/img/tv8-canli-yayin.jpg"
# the stream of the live page, when the page can not be read
LIVE_STREAM = "https://tv8.daioncdn.net/tv8/tv8.m3u8?app=7ddc255a-ef47-4e81-ab14-c0e5f2949788&ce=3"
# "Daha Fazla Video" of a video tab: 14 videos per page, false after the last one
TAB_JSON_URL = MAIN_URL + "Ajax/icerik/haberler/%s/%d?tip=videolar"
TAB_PAGE_SIZE = 14
# "En yeniler" of the videos page
LATEST_JSON_URL = MAIN_URL + "Ajax/icerik/videolar/en_yeniler/%d/%d"
LATEST_PAGE_SIZE = 21
# drop-down menus of the site header: label of the menu -> menu row
NAV_MENUS = (("Yarışmalar", "Competitions"), ("Diziler", "Series"), ("Programlar", "Programmes"))
ALL_TAB = "Tüm Bölümler"

NAV_LINK_RE = re.compile(r'<a href="https://www\.tv8\.com\.tr/([a-z0-9-]+)"\s+data-image="([^"]*)"[^>]*?\stitle="([^"]*)"')
GRID_LINK_RE = re.compile(r'<a href="https://www\.tv8\.com\.tr/([a-z0-9-]+)" title="([^"]*)">\s*<div class="list-type-one-img">\s*<img [^>]*?data-original="([^"]+)"')
TAB_RE = re.compile(r'data-toggle="tab" data-id="(\d+)">([^<]+)<')
TILE_RE = re.compile(r'(?s)<a href="(https://www\.tv8\.com\.tr/[^"]+-video\.htm)" class="tile-link">.*?(?:data-original|src)="([^"]+)".*?<h3 class="tile-title">(.*?)</h3>(?:\s*<span class="tile-summary">([^<]*)<)?')
HLS_RE = re.compile(r'hls:\s*"(https?://[^"]+\.m3u8[^"]*)"')
MP4_RE = re.compile(r'"contentURL":\s*"(https?://[^"]+\.mp4)"')
# Turkish letters spelled out (py2 byte strings: re.I does not fold ö/Ö), so no re.I on these two
EPISODE_RE = re.compile(r'(\d+)\.\s*[Bb](?:ö|Ö|o|O)[Ll](?:ü|Ü|u|U)[Mm]')
SEASON_RE = re.compile(r'(\d+)\.\s*Sezon', re.I)
TRAILER_RE = re.compile(r'[Tt]an(?:ı|i)t(?:ı|i)m|TANITIM|[Ff]ragman|FRAGMAN')
# lower case without the Turkish letters for the show search
FOLD_CHARS = (("İ", "i"), ("I", "i"), ("ı", "i"), ("Ş", "s"), ("ş", "s"), ("Ğ", "g"), ("ğ", "g"), ("Ü", "u"), ("ü", "u"),
              ("Ö", "o"), ("ö", "o"), ("Ç", "c"), ("ç", "c"), ("Â", "a"), ("â", "a"), ("&#039;", "'"))


def _fold(text):
    text = str(text or "")
    for src, dst in FOLD_CHARS:
        text = text.replace(src, dst)
    return text.lower()


class TV8(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "slug", "kat_id", "tab_title",
                  "tv8_date", "tv8_dur", "tv8_plot", "live")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "tv8", "cookie": "tv8.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Referer": MAIN_URL})
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest"})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = MAIN_URL
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/tv8135.png")
        # menus of the site header + all shows, read once per session
        self.showsCache = None
        self.watchedHelper = IPTVWatchedHelper("tv8")
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        return self.cm.getPage(url, addParams or self.defaultParams, post_data)

    def _json(self, url):
        sts, data = self.getPage(url, {"header": self.AJAX_HEADER})
        if not sts or not data:
            return []
        try:
            # Python 2: utf-8 str like the page data (the regexes and titles mix both)
            data = ensure_str_deep(json_loads(data))
            return data if isinstance(data, list) else []
        except Exception:
            printExc()
        return []

    @staticmethod
    def _path(url):
        return re.sub(r'^https?://[^/]+', '', str(url or "").split("#", 1)[0].strip())

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            category = cItem.get("category", "")
            if cItem.get("type", "") == "video" and category == "tv8_video":
                path = self._path(cItem.get("url", ""))
                return "video:%s" % path if path else ""
            if category == "tv8_tab" and cItem.get("kat_id"):
                return "folder:tab:%s" % cItem["kat_id"]
            if category == "tv8_show" and cItem.get("slug"):
                return "folder:show:%s" % cItem["slug"]
        except Exception:
            printExc()
        return ""

    ###################################################
    # shows
    ###################################################
    def _loadShows(self):
        if self.showsCache is not None:
            return self.showsCache
        sts, data = self.getPage(PROGRAMMES_URL)
        if not sts:
            return {"menus": {}, "all": []}
        shows = {}
        menus = {}

        def add(slug, title, icon):
            title = self.cleanHtmlStr(title).rstrip(".").strip()
            if not slug or not title:
                return
            icon = self.getFullIconUrl(icon, IMG_URL) if icon and not icon.startswith("http") else icon
            if slug in shows:
                if icon and not shows[slug]["icon"]:
                    shows[slug]["icon"] = icon
            else:
                shows[slug] = {"slug": slug, "title": title, "icon": icon}

        # the programme page: all shows with their logo
        for slug, title, icon in GRID_LINK_RE.findall(data):
            add(slug, title, icon)
        # the drop-down menus of the header: the current shows by type, "Tümü" = all shows
        for label in [x[0] for x in NAV_MENUS] + ["Tüm Programlar"]:
            start = data.find('title="%s">' % label)
            if start < 0:
                continue
            end = data.find("menuPhotoBoxWrapper", start)
            block = data[start:end if end > 0 else start + 30000]
            slugs = []
            for slug, icon, title in NAV_LINK_RE.findall(block):
                add(slug, title, icon)
                if slug not in slugs:
                    slugs.append(slug)
            menus[label] = slugs
        allShows = sorted(shows.values(), key=lambda x: _fold(x["title"]))
        # the same name for an old and a new run of a show (gel-konusalim / gel-konusalim1): tell them apart
        titles = [x["title"] for x in allShows]
        for show in allShows:
            if titles.count(show["title"]) > 1:
                show["title"] = "%s (%s)" % (show["title"], show["slug"])
        self.showsCache = {"menus": dict((label, [shows[s] for s in slugs if s in shows]) for label, slugs in menus.items()), "all": allShows}
        return self.showsCache

    def _addShow(self, cItem, show):
        params = stripPagerKeys(dict(cItem), ("kat_id", "tab_title", "nav", "search_pattern"))
        params.update({"good_for_fav": True, "category": "tv8_show", "title": show["title"], "s_title": show["title"],
                       "slug": show["slug"], "url": MAIN_URL + show["slug"], "icon": show.get("icon", ""), "desc": ""})
        self.addDir(params)

    def listMain(self, cItem):
        self.addVideo({"name": "category", "category": "tv8_live", "good_for_fav": True, "title": "TV8 Canlı Yayın", "url": LIVE_URL,
                       "icon": LIVE_ICON, "desc": _("Live"), "live": True})
        menu = [{"category": "tv8_latest", "title": _("Latest videos"), "url": MAIN_URL + "videolar"}]
        for label, title in NAV_MENUS:
            menu.append({"category": "tv8_nav", "title": _(title), "nav": label, "url": PROGRAMMES_URL + "#" + label})
        menu.append({"category": "tv8_all", "title": _("All"), "url": PROGRAMMES_URL})
        self.listsTab(menu + self.searchItems(), cItem)

    def listNav(self, cItem):
        shows = self._loadShows()
        rows = shows["menus"].get(cItem.get("nav", ""), [])
        for show in rows:
            self._addShow(cItem, show)

    def listAll(self, cItem):
        for show in self._loadShows()["all"]:
            self._addShow(cItem, show)

    def listShow(self, cItem):
        slug = cItem.get("slug", "") or self._path(cItem.get("url", "")).strip("/").split("/", 1)[0]
        url = MAIN_URL + slug + "/videolar"
        printDBG("TV8.listShow [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        tabs = []
        for katId, title in TAB_RE.findall(data):
            title = self.cleanHtmlStr(title)
            if katId not in [x[0] for x in tabs]:
                tabs.append((katId, title))
        # the full episodes first
        tabs.sort(key=lambda x: 0 if x[1] == ALL_TAB else 1)
        show = cItem.get("s_title", "") or cItem.get("title", "")
        base = stripPagerKeys(dict(cItem), ("nav", "search_pattern"))
        base.update({"slug": slug, "s_title": show})
        if len(tabs) == 1:
            base.update({"kat_id": tabs[0][0], "tab_title": tabs[0][1]})
            self.listTab(base)
            return
        for katId, title in tabs:
            params = dict(base)
            params.update({"good_for_fav": True, "category": "tv8_tab", "title": title, "kat_id": katId, "tab_title": title,
                           "url": "%s?tab=%s" % (url, katId), "desc": show})
            self.addDir(params)
        if not tabs:
            # no video tabs: the videos shown on the page itself
            for videoUrl, icon, title, date in TILE_RE.findall(data):
                params = dict(base)
                params.update({"good_for_fav": True, "category": "tv8_video", "url": videoUrl, "icon": self.getFullIconUrl(icon, IMG_URL),
                               "title": self._episodeTitle(show, self.cleanHtmlStr(title), ""), "desc": self.cleanHtmlStr(date)})
                self.addVideo(params)

    def listTab(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        katId = cItem.get("kat_id", "")
        printDBG("TV8.listTab [%s] page %d" % (katId, page))
        items = self._json(TAB_JSON_URL % (katId, page))
        for item in items:
            self._addEpisode(cItem, item)
        url = cItem.get("url", "").split("&page=", 1)[0]
        if "?tab=" not in url:
            url = "%s%s/videolar?tab=%s" % (MAIN_URL, cItem.get("slug", ""), katId)
        # no total from the site: Next page while a page is full
        addPagingItems(self, dict(cItem, category="tv8_tab", url=url, desc=""), page, len(items) >= TAB_PAGE_SIZE, 0, url + "&page={page}")

    def listLatest(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        items = self._json(LATEST_JSON_URL % (page, LATEST_PAGE_SIZE))
        for item in items:
            self._addEpisode(cItem, item)
        url = MAIN_URL + "videolar"
        addPagingItems(self, dict(cItem, url=url, desc=""), page, len(items) >= LATEST_PAGE_SIZE, 0, url + "?page={page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TV8.listSearchResult [%s]" % searchPattern)
        pattern = _fold(searchPattern.strip())
        if not pattern:
            return
        for show in self._loadShows()["all"]:
            if pattern in _fold(show["title"]) or pattern in show["slug"].replace("-", " "):
                self._addShow(cItem, show)

    ###################################################
    # episodes
    ###################################################
    @staticmethod
    def _image(resim):
        try:
            images = ensure_str_deep(json_loads(resim)) if resim and not isinstance(resim, dict) else (resim or {})
            for key in ("620_340", "620_400", "original"):
                if images.get(key):
                    return IMG_URL + images[key].lstrip("/")
        except Exception:
            printExc()
        return ""

    @staticmethod
    def _findShow(text, show):
        # index of the show name in the title (case-insensitive when lower() keeps the length), -1 if not there
        idx = text.find(show)
        if idx < 0:
            low, lowShow = text.lower(), show.lower()
            if len(low) == len(text) and len(lowShow) == len(show):
                idx = low.find(lowShow)
        return idx

    def _episodeTitle(self, show, raw, date):
        label = re.sub(r'\s+', ' ', raw or "").strip()
        parts = [x.strip() for x in label.split("|") if x.strip()]
        # "Title | Show": the tail only repeats the (long) show name
        while show and len(parts) > 1:
            idx = self._findShow(parts[-1], show)
            rest = (parts[-1][:idx] + parts[-1][idx + len(show):]) if idx >= 0 else parts[-1]
            if idx < 0 or len(rest.strip()) > 20 or re.search(r'\d', rest):
                break
            parts.pop()
        label = " - ".join(parts) or label
        if not show or not IsMediaNamingNormalized():
            return label
        idx = self._findShow(label, show)
        rest = label[idx + len(show):] if 0 <= idx <= 40 else label
        rest = rest.strip(" -|:,")
        # "Fragman: <show> 3. Bölüm": a trailer prefix stays part of the name (and gets no SxxExx)
        prefix = label[:idx].strip(" -|:,") if 0 < idx <= 40 else ""
        if prefix and TRAILER_RE.search(prefix):
            rest = "%s - %s" % (prefix, rest) if rest else prefix
        episode = EPISODE_RE.search(rest)
        season = SEASON_RE.search(rest)
        if episode and season and not TRAILER_RE.search(rest):
            tag = formatSxxExx(season.group(1), episode.group(1))
            rest = SEASON_RE.sub("", EPISODE_RE.sub("", rest, 1), 1).strip(" -|:,")
            return "%s - %s - %s" % (show, tag, rest) if rest else "%s - %s" % (show, tag)
        if rest:
            return "%s - %s" % (show, rest)
        return "%s - %s" % (show, date) if date else show

    def _addEpisode(self, cItem, item):
        try:
            if not isinstance(item, dict) or item.get("tip", "video") != "video":
                return
            videoId = str(item.get("id") or "")
            slug = item.get("slug") or ""
            parent = item.get("parent_kslug") or cItem.get("slug", "")
            if not videoId or not slug or not parent:
                return
            raw = self.cleanHtmlStr(item.get("baslik") or "")
            show = self.cleanHtmlStr(item.get("parent_kname") or "") or cItem.get("s_title", "")
            stamp = str(item.get("kayit_tarihi") or "")
            date = stamp[:10] if re.match(r'^\d{4}-\d\d-\d\d', stamp) else ""
            duration = str(item.get("video_suresi") or "")
            if not re.match(r'^\d+:\d\d:\d\d$', duration) or not duration.strip("0:"):
                duration = ""
            plot = self.cleanHtmlStr(item.get("spot") or "")
            line = " | ".join(x for x in ("%s.%s.%s" % (date[8:10], date[5:7], date[:4]) if date else "", duration, item.get("kname") or "") if x)
            params = stripPagerKeys(dict(cItem), ("nav", "search_pattern"))
            params.update({"good_for_fav": True, "category": "tv8_video", "url": "%s%s/%s-%s-video.htm" % (MAIN_URL, parent, slug, videoId),
                           "title": self._episodeTitle(show, raw, date), "s_title": show, "icon": self._image(item.get("resim")) or cItem.get("icon", ""),
                           "desc": "[/br]".join(x for x in (line, plot) if x), "tv8_date": date, "tv8_dur": duration, "tv8_plot": plot, "live": False})
            self.addVideo(params)
        except Exception:
            printExc()

    ###################################################
    # links
    ###################################################
    def _hlsLinks(self, master, meta, live=False):
        urlTab = []
        for item in getDirectM3U8Playlist(strwithmeta(master, dict(meta)), checkExt=False, checkContent=True):
            url = strwithmeta(item["url"])
            itemMeta = dict(url.meta)
            itemMeta.update(meta)
            name = "%sp" % item.get("height") if item.get("height") else item.get("name", "HLS")
            urlTab.append({"name": "HLS %s" % name, "url": strwithmeta(url, itemMeta), "need_resolve": 0, "bitrate": item.get("bitrate", 0)})
        try:
            urlTab.sort(key=lambda x: int(x.get("bitrate") or 0), reverse=True)
        except Exception:
            printExc()
        if urlTab and (live or len(urlTab) > 1):
            urlTab.append({"name": "HLS (adaptive)", "url": strwithmeta(master, dict(meta)), "need_resolve": 0})
        return urlTab

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("TV8.getLinksForVideo [%s]" % url)
        meta = {"iptv_proto": "m3u8", "User-Agent": self.HEADER.get("User-Agent"), "Referer": MAIN_URL, "Origin": MAIN_URL.rstrip("/")}
        if cItem.get("live"):
            sts, data = self.getPage(LIVE_URL)
            stream = self.cm.ph.getSearchGroups(data, r'videoUrl\s*=\s*"(https?://[^"]+\.m3u8[^"]*)"')[0] if sts else ""
            meta["iptv_livestream"] = True
            urlTab = self._hlsLinks(stream or LIVE_STREAM, meta, True)
            if not urlTab:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return urlTab
        sts, data = self.getPage(url)
        if not sts:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        urlTab = []
        hls = self.cm.ph.getSearchGroups(data, HLS_RE.pattern)[0]
        if hls:
            # videocdn.* checks the short-lived token (410 Gone), the same files on video-cdn.* play without it
            candidates = [hls.replace("//videocdn.", "//video-cdn."), hls] if "//videocdn." in hls else [hls]
            for master in candidates:
                urlTab = self._hlsLinks(master, meta)
                if urlTab:
                    break
        mp4 = self.cm.ph.getSearchGroups(data, MP4_RE.pattern)[0]
        if mp4:
            quality = self.cm.ph.getSearchGroups(mp4, r'-(\d+p)\.mp4$')[0]
            urlTab.append({"name": "MP4 %s" % quality if quality else "MP4", "url": strwithmeta(mp4, {"User-Agent": self.HEADER.get("User-Agent"), "Referer": MAIN_URL}), "need_resolve": 0})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("tv8_plot", ""), {}))

    def getVideoLinks(self, videoUrl):
        return []

    ###################################################
    # info / favourites
    ###################################################
    @staticmethod
    def _isoDuration(value):
        match = re.match(r'^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$', value or "")
        if not match or not any(match.groups()):
            return ""
        h, m, s = [int(x or 0) for x in match.groups()]
        return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)

    def getArticleContent(self, cItem):
        printDBG("TV8.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        icon = cItem.get("icon", "")
        text = cItem.get("tv8_plot", "")
        otherInfo = {"station": "TV8"}
        category = cItem.get("category", "")
        if cItem.get("live"):
            otherInfo["status"] = _("On Air")
            text = "TV8 - %s" % _("Live")
        elif category == "tv8_video":
            date, duration = cItem.get("tv8_date", ""), cItem.get("tv8_dur", "")
            if not text or not date or not icon:
                sts, data = self.getPage(cItem.get("url", ""))
                if sts:
                    icon = icon or self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="(https?://[^"]+)"')[0]
                    text = text or self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'"description":\s*"([^"]+)"')[0])
                    date = date or self.cm.ph.getSearchGroups(data, r'"uploadDate":\s*"(\d{4}-\d\d-\d\d)')[0]
                    duration = duration or self._isoDuration(self.cm.ph.getSearchGroups(data, r'"duration":\s*"(PT[^"]+)"')[0])
            if date:
                otherInfo["broadcast"] = "%s.%s.%s" % (date[8:10], date[5:7], date[:4])
            if duration:
                otherInfo["duration"] = duration
            episode = EPISODE_RE.search(title)
            if episode:
                otherInfo["episodes"] = episode.group(1)
            if cItem.get("tab_title"):
                otherInfo["category"] = cItem["tab_title"]
            if cItem.get("s_title"):
                otherInfo["alternate_title"] = cItem["s_title"]
        elif category == "tv8_tab":
            otherInfo["category"] = cItem.get("tab_title", "")
            text = "%s - %s" % (cItem.get("s_title", ""), cItem.get("tab_title", ""))
        if not text:
            text = "%s - TV8" % title
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("tv8_"):
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
        printDBG("TV8.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({"name": "category"})
        elif category == "tv8_latest":
            self.listLatest(self.currItem)
        elif category == "tv8_nav":
            self.listNav(self.currItem)
        elif category == "tv8_all":
            self.listAll(self.currItem)
        elif category == "tv8_show":
            self.listShow(self.currItem)
        elif category == "tv8_tab":
            self.listTab(self.currItem)
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
        CHostBase.__init__(self, TV8(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("tv8")

    def withArticleContent(self, cItem):
        # no INFO for the show folders: their pages carry only the site's stock SEO text
        return cItem.get("type") == "video" or cItem.get("category", "") == "tv8_tab"
