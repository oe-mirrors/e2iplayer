# -*- coding: utf-8 -*-
LAST_MODIFIED = "21.11.2026"
# 24.10.2026 - new host
#   - TV8 Turkey (tv8.com.tr): free catch-up of the channel's own shows and series, live stream
#   - shows from the programme page (all / ?tur=<type>), a show's tabs are its own pages (/<slug>/<tab>?page=N)
# 21.11.2026 - new site layout: programme / video cards, tab pages instead of the JSON tabs, latest = home page
#   - links: direct HLS of video-cdn.tv8.com.tr (variants) + the MP4 of the page, live HLS of daioncdn.net
#   - search: the site only has a Google search box, so the show names are searched
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
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
# programme types of the programme page (?tur=..., 11.2026): menu row
NAV_MENUS = (("yarisma", "Competitions"), ("dizi", "Series"), ("program", "Programmes"))
# the show page's tab with the full episodes goes first
ALL_TAB = "tum-bolumler"

# 11.2026 layout: programme cards and video cards ("now-thumb"), a show's tabs are own pages /<slug>/<tab>?page=N
PROGRAM_CARD_RE = re.compile(r'(?s)<article class="now-thumb now-program-thumb">\s*<a href="/([a-z0-9-]+)"[^>]*>.*?<img src="([^"]+)" alt="([^"]*)"')
VIDEO_CARD_RE = re.compile(r'(?s)<article class="now-thumb">(.*?)</article>')
SHOW_TAB_RE = re.compile(r'class="nav-link[^"]*"\s+href="/([a-z0-9-]+)(?:/([a-z0-9-]+))?"\s*>\s*([^<]+?)\s*<')
# hls: "https:\/\/video-cdn.tv8.com.tr\/...\/playlist.m3u8?st=..&e=.." (escaped slashes)
HLS_RE = re.compile(r'hls:\s*"(https?:[^"]+\.m3u8[^"]*)"')
MP4_RE = re.compile(r'"content[Uu][Rr][Ll]":\s*"(https?:[^"]+\.mp4[^"]*)"|(https?://video-cdn\.tv8\.com\.tr/[^"\'\s<>]+\.mp4[^"\'\s<>]*)')
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
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = MAIN_URL
        # menus of the site header + all shows, read once per session
        self.showsCache = None
        self.watchedHelper = IPTVWatchedHelper("tv8")
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        return self.cm.getPage(url, addParams or self.defaultParams, post_data)

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
    def _programmeCards(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return []
        cards = []
        for slug, icon, title in PROGRAM_CARD_RE.findall(data):
            title = self.cleanHtmlStr(title).rstrip(".").strip()
            if slug and title:
                cards.append({"slug": slug, "title": title, "icon": self.getFullIconUrl(icon, IMG_URL) if icon else ""})
        return cards

    def _loadShows(self):
        if self.showsCache is not None:
            return self.showsCache
        # the programme page: all shows; ?tur=<type>: the shows of one type
        shows = {}
        menus = {}
        for card in self._programmeCards(PROGRAMMES_URL):
            shows.setdefault(card["slug"], card)
        for tur, _title in NAV_MENUS:
            menus[tur] = []
            for card in self._programmeCards("%s?tur=%s" % (PROGRAMMES_URL, tur)):
                shows.setdefault(card["slug"], card)
                if card["slug"] not in menus[tur]:
                    menus[tur].append(card["slug"])
        if not shows:
            return {"menus": {}, "all": []}
        allShows = sorted(shows.values(), key=lambda x: _fold(x["title"]))
        # the same name for an old and a new run of a show (gel-konusalim / gel-konusalim1): tell them apart
        titles = [x["title"] for x in allShows]
        for show in allShows:
            if titles.count(show["title"]) > 1:
                show["title"] = "%s (%s)" % (show["title"], show["slug"])
        self.showsCache = {"menus": dict((tur, [shows[s] for s in slugs if s in shows]) for tur, slugs in menus.items()), "all": allShows}
        return self.showsCache

    def _addShow(self, cItem, show):
        params = stripPagerKeys(dict(cItem), ("kat_id", "tab_title", "nav", "search_pattern"))
        params.update({"good_for_fav": True, "category": "tv8_show", "title": show["title"], "s_title": show["title"],
                       "slug": show["slug"], "url": MAIN_URL + show["slug"], "icon": show.get("icon", ""), "desc": ""})
        self.addDir(params)

    def listMain(self, cItem):
        self.addVideo({"name": "category", "category": "tv8_live", "good_for_fav": True, "title": "TV8 Canlı Yayın", "url": LIVE_URL,
                       "icon": LIVE_ICON, "desc": _("Live"), "live": True})
        menu = [{"category": "tv8_latest", "title": _("Latest videos"), "url": MAIN_URL}]
        for tur, title in NAV_MENUS:
            menu.append({"category": "tv8_nav", "title": _(title), "nav": tur, "url": "%s?tur=%s" % (PROGRAMMES_URL, tur)})
        menu.append({"category": "tv8_all", "title": _("All"), "url": PROGRAMMES_URL})
        self.listsTab(menu + self.searchItems(), cItem)

    def listNav(self, cItem):
        shows = self._loadShows()
        # favourites of the old menu rows carry the Turkish menu label
        nav = {"Yarışmalar": "yarisma", "Diziler": "dizi", "Programlar": "program"}.get(cItem.get("nav", ""), cItem.get("nav", ""))
        for show in shows["menus"].get(nav, []):
            self._addShow(cItem, show)

    def listAll(self, cItem):
        for show in self._loadShows()["all"]:
            self._addShow(cItem, show)

    def listShow(self, cItem):
        slug = cItem.get("slug", "") or self._path(cItem.get("url", "")).strip("/").split("/", 1)[0]
        url = MAIN_URL + slug
        printDBG("TV8.listShow [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        # tabs: /<slug> (all videos, "TÜM VİDEOLAR (7.214)"), /<slug>/tum-bolumler, /<slug>/kisa-videolar ...
        tabs = []
        for tabSlug, sub, title in SHOW_TAB_RE.findall(data):
            title = re.sub(r"\s*\([\d.,]+\)\s*$", "", self.cleanHtmlStr(title))
            if tabSlug == slug and title and sub not in [x[0] for x in tabs]:
                tabs.append((sub, title))
        tabs.sort(key=lambda x: 0 if x[0] == ALL_TAB else 1)
        show = cItem.get("s_title", "") or cItem.get("title", "")
        base = stripPagerKeys(dict(cItem), ("nav", "search_pattern"))
        base.update({"slug": slug, "s_title": show})
        if len(tabs) <= 1:
            # one tab or none: the videos of the show page
            base.update({"kat_id": tabs[0][0] if tabs else "", "tab_title": tabs[0][1] if tabs else ""})
            self.listTab(base)
            return
        for sub, title in tabs:
            params = dict(base)
            params.update({"good_for_fav": True, "category": "tv8_tab", "title": title, "kat_id": sub, "tab_title": title,
                           "url": "%s/%s" % (url, sub) if sub else url, "desc": show})
            self.addDir(params)

    def _addVideoCards(self, cItem, data):
        count = 0
        for card in VIDEO_CARD_RE.findall(data):
            href = self.cm.ph.getSearchGroups(card, r'href="([^"]+-video\.htm)"')[0]
            raw = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="now-thumb-desc">(.*?)</div>')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'aria-label="([^"]*)"')[0])
            if not href or not raw:
                continue
            show = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="now-thumb-prog[^"]*">(.*?)</a>')[0]) or cItem.get("s_title", "")
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="now-thumb-dur">(.*?)</span>')[0])
            icon = self.cm.ph.getSearchGroups(card, r'<img[^>]+src="([^"]+)"')[0]
            params = stripPagerKeys(dict(cItem), ("nav", "search_pattern"))
            params.update({"good_for_fav": True, "category": "tv8_video", "url": self.getFullUrl(href), "title": self._episodeTitle(show, raw, ""),
                           "s_title": show, "icon": self.getFullIconUrl(icon, IMG_URL) if icon else cItem.get("icon", ""), "desc": duration,
                           "tv8_date": "", "tv8_dur": duration, "tv8_plot": "", "live": False})
            self.addVideo(params)
            count += 1
        return count

    def listTab(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        slug = cItem.get("slug", "")
        sub = cItem.get("kat_id", "")
        if sub.isdigit():
            sub = ""  # favourites of the old JSON tabs (numeric ids): all videos of the show
        url = MAIN_URL + slug + ("/" + sub if sub else "")
        printDBG("TV8.listTab [%s] page %d" % (url, page))
        sts, data = self.getPage(url + ("?page=%d" % page if page > 1 else ""))
        if not sts:
            return
        count = self._addVideoCards(cItem, data)
        pager = " ".join(re.findall(r'class="page-link"[^>]*href="([^"]+)"', data))
        lastPage = max([int(x) for x in re.findall(r"[?&]page=(\d+)", pager)] + [page])
        addPagingItems(self, dict(cItem, category="tv8_tab", url=url, desc=""), page, bool(count) and lastPage > page, 0, url + "?page={page}")

    def listLatest(self, cItem):
        # the newest videos of the home page (the site has no paged list of them any more)
        sts, data = self.getPage(MAIN_URL)
        if sts:
            self._addVideoCards(dict(cItem, s_title=""), data)

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
        hls = self.cm.ph.getSearchGroups(data, HLS_RE.pattern)[0].replace("\\/", "/").replace("&amp;", "&")
        if hls:
            # videocdn.* checks the short-lived token (410 Gone), the same files on video-cdn.* play without it
            candidates = [hls.replace("//videocdn.", "//video-cdn."), hls] if "//videocdn." in hls else [hls]
            for master in candidates:
                urlTab = self._hlsLinks(master, meta)
                if urlTab:
                    break
        match = MP4_RE.search(data)
        mp4 = (match.group(1) or match.group(2) or "").replace("\\/", "/").replace("&amp;", "&") if match else ""
        if mp4:
            quality = self.cm.ph.getSearchGroups(mp4, r'-(\d+p)\.mp4')[0]
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
