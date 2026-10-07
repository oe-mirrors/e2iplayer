# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - Polskie Radio (polskieradio.pl), new host
#   Live: the antennas of player.polskieradio.pl (Jedynka, Dwojka, Trojka, Czworka, PR24, Chopin, ...),
#   stream urls from apipr.polskieradio.pl/api/stacje (HLS like the web player, plus the Icecast/Shoutcast MP3).
#   Programme archive: apipr.polskieradio.pl/api/mainschedule (last 7 days, broadcasts that have a recording).
#   Podcasts: apipodcasts.polskieradio.pl/api (all / categories / stations / search -> episodes, MP3).
#   Live radio: audio rows without watched flag; archive broadcasts and podcast episodes: watched flag +
#   downloaded marker (row url = the stable static.prsa.pl MP3 url), name normalisation "Show - Episode (date)".
import re
from datetime import datetime, timedelta

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://www.polskieradio.pl/"


# (label, name in /api/stacje, player slug, schedule id) - the antenna list of player.polskieradio.pl
ANTENNAS = [
    ("Jedynka", "Jedynka", "jedynka", 1),
    ("Dwójka", "Dwójka", "dwojka", 2),
    ("Trójka", "Trójka", "trojka", 3),
    ("Czwórka", "Czwórka", "czworka", 4),
    ("Polskie Radio 24", "Polskie Radio 24", "pr24", 6),
    ("Radio Dzieciom", "Radio Dzieciom", "dzieci", 11),
    ("Polskie Radio Kierowców", "Radio Kierowców", "prk", 12),
    ("Radio Chopin", "Radio Chopin", "chopin", 10),
    ("Polskie Radio dla Zagranicy (UA/BY/RU/PL)", "Polskie Radio Dla Zagranicy", "polsza", 9),
    ("Polskie Radio dla Zagranicy (DE/EN/PL)", "Radio Poland", "poland", 5),
    ("Polish Radio External Service DAB+", "Polish Radio External Service DAB+", "externaldab", 7),
    ("Cyfrowe Radio Gwiazdka", "Cyfrowe Radio Gwiazdka", "gwiazdka", 13),
    ("Radio Ukraina", "Українське радіо", "ukraina", 33),
]


MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


class PolskieRadio(GenericFolderWatchedScraperMixin, CBaseHostClass):
    API_PR = "https://apipr.polskieradio.pl/api/"
    API_POD = "https://apipodcasts.polskieradio.pl/api/"
    PLAYER = "https://player.polskieradio.pl/"
    PAGE_SIZE = 50
    LOCAL_PAGE_SIZE = 100
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "live", "stream_name", "schedule_id",
                  "podcast_id", "guid", "page")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "polskieradio", "cookie": "polskieradio.cookie"})
        self.MAIN_URL = "https://www.polskieradio.pl/"
        self.DEFAULT_ICON_URL = "https://player.polskieradio.pl/images/jedynka-color-logo.png"
        self.HEADER = {"User-Agent": self.cm.getDefaultUserAgent('chrome'),
                       "Accept": "application/json, text/plain, */*",
                       "Origin": "https://player.polskieradio.pl", "Referer": "https://player.polskieradio.pl/"}
        self.defaultParams = {"header": self.HEADER}
        self.cacheStations = None
        self.cachePodcasts = None
        self.MENU = [{"category": "list_live", "title": _("Radio stations")},
                     {"category": "list_archive", "title": _("Programme archive (last 7 days)")},
                     {"category": "list_podcasts", "title": _("Podcasts"), "page": 1},
                     {"category": "list_pod_categories", "title": _("Podcasts by category")},
                     {"category": "list_pod_stations", "title": _("Podcasts by station")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("polskieradio")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            itemType = cItem.get("type", "")
            if itemType in ("audio", "video"):
                key = cItem.get("guid") or self.wfNormalizeUrlKey(cItem.get("url", ""))
                return "audio:%s" % key if key else ""
            if itemType in ("more", "marker") or cItem.get("search_item") or cItem.get("name") == "history":
                return ""
            if cItem.get("category", "") == "list_episodes" and cItem.get("podcast_id"):
                return "folder:podcast:%s" % cItem["podcast_id"]
        except Exception:
            printExc()
        return ""

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _json(self, url):
        sts, data = self.getPage(url)
        if not sts or not data:
            return None
        try:
            return ensure_str_deep(json_loads(data))
        except Exception:
            printExc()
        return None

    @staticmethod
    def _fullUrl(url):
        if url.startswith("//"):
            return "https:" + url
        return url

    @staticmethod
    def _duration(secs):
        try:
            secs = int(secs or 0)
        except Exception:
            secs = 0
        if secs <= 0:
            return ""
        return "%d:%02d:%02d" % (secs // 3600, (secs % 3600) // 60, secs % 60) if secs >= 3600 else "%d:%02d" % (secs // 60, secs % 60)

    def _episodeTitle(self, show, title, date):
        if IsMediaNamingNormalized():
            base = "%s - %s" % (show, title) if show and show.lower() not in title.lower() else title
            return normalizeMediathekTitle(base, date=date)
        return title

    ###################################################
    # live
    ###################################################
    def _loadStations(self):
        if self.cacheStations is None:
            data = self._json(self.API_PR + "stacje")
            if isinstance(data, list):
                self.cacheStations = dict((s.get("Name"), s) for s in data if isinstance(s, dict) and s.get("Name"))
        return self.cacheStations or {}

    def listLive(self, cItem):
        stations = self._loadStations()
        for label, streamName, slug, scheduleId in ANTENNAS:
            if streamName not in stations:
                continue
            self.addAudio({"good_for_fav": True, "live": True, "title": label, "url": self.PLAYER + "anteny/" + slug,
                           "stream_name": streamName, "schedule_id": scheduleId,
                           "icon": self.PLAYER + "images/%s-color-logo.png" % slug})

    def _liveLinks(self, cItem):
        station = self._loadStations().get(cItem.get("stream_name", ""))
        if not station:
            return []
        hls, direct = [], []
        for url in (station.get("Streams") or []):
            url = url.strip()
            if url.startswith("//"):
                url = "http:" + url
            low = url.lower()
            if not low.startswith("http") or low.endswith(".f4m") or low.endswith("/manifest"):
                continue
            if ".m3u8" in low:
                # the web player uses the HLS stream over https
                hls.append(("HLS", self.up.decorateUrl(url.replace("http://", "https://", 1), {"iptv_proto": "m3u8", "iptv_livestream": True})))
            else:
                if re.match(r"^https?://[^/]+:\d+/?$", url):
                    # SHOUTcast v1 answers a browser User-Agent with its status page - "/;" always gives the stream
                    url = url.rstrip("/") + "/;"
                direct.append(("MP3", self.up.decorateUrl(url, {"iptv_livestream": True})))
        urlTab = []
        # the HLS stream is what the web player uses; the old SHOUTcast MP3 servers only as a fallback
        for name, url in (hls or direct):
            urlTab.append({"name": "%s (%d)" % (name, len(urlTab) + 1), "url": url, "need_resolve": 0})
        return urlTab

    ###################################################
    # programme archive
    ###################################################
    def listArchive(self, cItem):
        for label, streamName, slug, scheduleId in ANTENNAS:
            if slug in ("gwiazdka", "externaldab"):
                continue
            params = dict(cItem)
            params.update({"category": "list_archive_days", "title": label, "schedule_id": scheduleId,
                           "station": label, "icon": self.PLAYER + "images/%s-color-logo.png" % slug, "good_for_fav": False})
            self.addDir(params)

    def listArchiveDays(self, cItem):
        today = datetime.now()
        for i in range(7):
            day = today - timedelta(days=i)
            params = dict(cItem)
            params.update({"category": "list_archive_day", "title": day.strftime("%Y-%m-%d") if i else _("Today"),
                           "day": day.strftime("%Y-%m-%d"), "good_for_fav": False})
            self.addDir(params)

    @staticmethod
    def _parseHour(value):
        # "Sat, 03 Oct 2026 07:07:00" -> ("2026-10-03", "07:07")
        m = re.search(r"(\d{1,2}) (\w{3}) (\d{4}) (\d{2}):(\d{2})", value or "")
        if not m:
            return "", ""
        return "%s-%02d-%02d" % (m.group(3), MONTHS.get(m.group(2), 0), int(m.group(1))), "%s:%s" % (m.group(4), m.group(5))

    def listArchiveDay(self, cItem):
        data = self._json(self.API_PR + "mainschedule/?Program=%s&SelectedDate=%s" % (cItem.get("schedule_id", ""), cItem.get("day", "")))
        if not isinstance(data, dict):
            return
        now = datetime.now()
        for prog in (data.get("Schedule") or []):
            try:
                sounds = [s for s in (prog.get("Sounds") or []) if isinstance(s, dict) and s.get("MediaStreams")]
                if not sounds:
                    continue
                day, hour = self._parseHour(prog.get("StartHour"))
                if day == now.strftime("%Y-%m-%d") and hour > now.strftime("%H:%M"):
                    continue
                title = self.cleanHtmlStr(prog.get("Title") or "")
                desc = self.cleanHtmlStr(prog.get("Description") or "")
                icon = self._fullUrl(prog.get("Photo") or "") or cItem.get("icon", "")
                for sound in sounds:
                    # "...mp3?source=mobileapi&stream=all" answers with a JSON list of HLS/RTSP/RTMP variants,
                    # the bare static.prsa.pl url is the MP3 itself (range requests supported)
                    url = self._fullUrl(sound["MediaStreams"]).split("?")[0]
                    label = title
                    sDesc = self.cleanHtmlStr(sound.get("Description") or "")
                    if len(sounds) > 1 and sDesc:
                        label = "%s - %s" % (title, sDesc)
                    show = cItem.get("station", "")
                    rowTitle = self._episodeTitle(show, label, day) if IsMediaNamingNormalized() else "%s %s" % (hour, label)
                    self.addAudio({"good_for_fav": True, "title": rowTitle, "url": url, "guid": str(sound.get("Id") or ""),
                                   "icon": icon, "desc": "[/br]".join([x for x in ("%s %s" % (day, hour), sDesc, desc) if x])})
            except Exception:
                printExc()

    ###################################################
    # podcasts
    ###################################################
    def _podImage(self, pod):
        img = pod.get("image")
        if isinstance(img, dict):
            return img.get("main") or img.get("thumbnail") or img.get("recommended") or ""
        return img or ""

    def _podCategory(self, pod):
        # the list API calls it prCategory (mostly empty), the podcast details plCategory; iTunes as fallback
        return self.cleanHtmlStr(pod.get("prCategory") or pod.get("plCategory") or pod.get("itunesCategory") or "")

    def _podGroup(self, pod, key):
        return self._podCategory(pod) if key == "category" else self.cleanHtmlStr(pod.get(key) or "")

    def _addPodcast(self, cItem, pod):
        title = self.cleanHtmlStr(pod.get("title") or "")
        if not title or not pod.get("id"):
            return
        info = [x for x in (self.cleanHtmlStr(pod.get("radioStation") or ""), self._podCategory(pod),
                            _("%s episodes") % pod.get("itemCount") if pod.get("itemCount") else "") if x]
        desc = " | ".join(info)
        text = self.cleanHtmlStr(pod.get("description") or "")
        params = stripPagerKeys(dict(cItem))
        params.update({"category": "list_episodes", "title": title, "podcast_id": pod["id"], "page": 1,
                       "url": "https://podcasty.polskieradio.pl/podcast/%s/" % pod["id"],
                       "icon": self._podImage(pod), "desc": desc + ("[/br]" + text if text else ""), "good_for_fav": True})
        self.addDir(params)

    def listPodcasts(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        tpl = self.API_POD + "Podcasts?page={page}&pageSize=%d" % self.PAGE_SIZE
        data = self._json(tpl.format(page=page))
        if not isinstance(data, dict):
            return
        items = data.get("items") or []
        for pod in items:
            self._addPodcast(cItem, pod)
        lastPage = self._lastPage(data.get("count"))
        addPagingItems(self, cItem, page, bool(items) and page < lastPage, lastPage, tpl)

    def _lastPage(self, count):
        try:
            return (int(count or 0) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        except (TypeError, ValueError):
            return 0

    def _loadAllPodcasts(self):
        if self.cachePodcasts is None:
            pods = []
            page = 1
            while page <= 10:
                data = self._json(self.API_POD + "Podcasts?page=%d&pageSize=200" % page)
                if not isinstance(data, dict) or not data.get("items"):
                    break
                pods.extend([p for p in data["items"] if isinstance(p, dict)])
                if page * 200 >= int(data.get("count") or 0):
                    break
                page += 1
            if pods:
                self.cachePodcasts = pods
        return self.cachePodcasts or []

    def _listPodGroups(self, cItem, key):
        groups = {}
        for pod in self._loadAllPodcasts():
            name = self._podGroup(pod, key)
            if name:
                groups[name] = groups.get(name, 0) + 1
        for name in sorted(groups, key=lambda x: x.lower()):
            params = dict(cItem)
            params.update({"category": "list_pod_filtered", "title": "%s (%d)" % (name, groups[name]), "f_key": key,
                           "f_value": name, "good_for_fav": False})
            self.addDir(params)

    def listPodFiltered(self, cItem):
        key, value = cItem.get("f_key", ""), cItem.get("f_value", "")
        pods = []
        for pod in self._loadAllPodcasts():
            if self._podGroup(pod, key) == value:
                pods.append(pod)
        pods.sort(key=lambda p: (p.get("title") or "").lower())
        # the big groups (News, Trójka ...) hold more than 100 podcasts - shown LOCAL_PAGE_SIZE at a time
        page = max(1, int(cItem.get("page", 1) or 1))
        lastPage = max(1, (len(pods) + self.LOCAL_PAGE_SIZE - 1) // self.LOCAL_PAGE_SIZE)
        page = min(page, lastPage)
        for pod in pods[(page - 1) * self.LOCAL_PAGE_SIZE:page * self.LOCAL_PAGE_SIZE]:
            self._addPodcast(cItem, pod)
        if lastPage > 1:
            # the url template only serves "Jump" - the list is cut by cItem['page']
            addPagingItems(self, cItem, page, page < lastPage, lastPage, "https://podcasty.polskieradio.pl/#group-{page}")

    def listEpisodes(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        tpl = self.API_POD + "Podcasts/%s/?pageSize=%d&page={page}" % (cItem.get("podcast_id", ""), self.PAGE_SIZE)
        data = self._json(tpl.format(page=page))
        if not isinstance(data, dict):
            return
        show = self.cleanHtmlStr(data.get("title") or cItem.get("title", ""))
        seen = set()
        for ep in (data.get("items") or []):
            try:
                url = ep.get("url") or ""
                title = self.cleanHtmlStr(ep.get("title") or "")
                # the feeds sometimes carry the same recording twice
                if not url or not title or url in seen:
                    continue
                seen.add(url)
                date = (ep.get("publishDate") or "")[:10]
                desc = "[/br]".join([x for x in (" | ".join([y for y in (date, self._duration(ep.get("length"))) if y]),
                                                 self.cleanHtmlStr(ep.get("description") or "")) if x])
                self.addAudio({"good_for_fav": True, "title": self._episodeTitle(show, title, date), "url": url,
                               "guid": ep.get("guid") or "", "icon": ep.get("image") or cItem.get("icon", ""), "desc": desc})
            except Exception:
                printExc()
        lastPage = self._lastPage(data.get("itemCount"))
        addPagingItems(self, cItem, page, bool(data.get("items")) and page < lastPage, lastPage, tpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = (searchPattern or "").strip().lower()
        if not pattern:
            return
        found = []
        for pod in self._loadAllPodcasts():
            text = " ".join([pod.get("title") or "", pod.get("itunesKeywords") or "", pod.get("announcer") or "",
                             pod.get("radioStation") or ""]).lower()
            if pattern in text:
                found.append(pod)
        if not found:
            for pod in self._loadAllPodcasts():
                if pattern in (pod.get("description") or "").lower():
                    found.append(pod)
        for pod in found:
            self._addPodcast(cItem, pod)

    ###################################################
    # links / info / favourites
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("PolskieRadio.getLinksForVideo [%s]" % cItem.get("url", ""))
        if cItem.get("live"):
            urlTab = self._liveLinks(cItem)
            if not urlTab:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return urlTab
        url = cItem.get("url", "")
        if not self.cm.isValidUrl(url):
            return []
        urlTab = [{"name": "MP3", "url": url, "need_resolve": 0}]
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(cItem.get("desc", ""))))

    def getArticleContent(self, cItem):
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        if cItem.get("live") and cItem.get("schedule_id"):
            data = self._json(self.API_PR + "mainschedule/?Program=%s" % cItem["schedule_id"])
            for prog in ((data or {}).get("Schedule") or []) if isinstance(data, dict) else []:
                if prog.get("IsActive"):
                    day, start = self._parseHour(prog.get("StartHour"))
                    stop = self._parseHour(prog.get("StopHour"))[1]
                    otherInfo["station"] = title
                    title = self.cleanHtmlStr(prog.get("Title") or title)
                    text = self.cleanHtmlStr(prog.get("Description") or "")
                    if start:
                        otherInfo["duration"] = "%s - %s" % (start, stop)
                    icon = self._fullUrl(prog.get("Photo") or "") or icon
                    break
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("type") == "audio" or cItem.get("category") == "list_episodes":
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("PolskieRadio.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_live":
            self.listLive(self.currItem)
        elif category == "list_archive":
            self.listArchive(self.currItem)
        elif category == "list_archive_days":
            self.listArchiveDays(self.currItem)
        elif category == "list_archive_day":
            self.listArchiveDay(self.currItem)
        elif category == "list_podcasts":
            self.listPodcasts(self.currItem)
        elif category == "list_pod_categories":
            self._listPodGroups(self.currItem, "category")
        elif category == "list_pod_stations":
            self._listPodGroups(self.currItem, "radioStation")
        elif category == "list_pod_filtered":
            self.listPodFiltered(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, PolskieRadio(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("polskieradio")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "audio" or cItem.get("category") == "list_episodes"
