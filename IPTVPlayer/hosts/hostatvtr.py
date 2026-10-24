# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host
# atv (Turkey, atv.com.tr): free catch-up of the current and old series, programmes and news, live atv and atv Avrupa.
# Episode lists from the site's own ajax calls (seasons, episode lists), streams from the Turkuvaz player
# API videojs.tmgrup.com.tr/getvideo (MP4 + HLS on erbvr/ercdn, Turkish SRT), live HLS with a token from
# securevideotoken.tmgrup.com.tr.
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx, normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://www.atv.com.tr/"


PLAYER_API = "https://videojs.tmgrup.com.tr/getvideo/%s/%s"
TOKEN_URL = "https://securevideotoken.tmgrup.com.tr/webtv/secure?%d&url=%s"
ATV_SITE_ID = "0fe2a405-8afa-4238-b429-e5f96aec3a5c"
LIVE_ID = "00000000-0000-0000-0000-000000000000"
# live channels: page, player website id (the live stream of that site), referer, player cover
LIVE_CHANNELS = (("atv", "https://www.atv.com.tr/canli-yayin", ATV_SITE_ID, "https://www.atv.com.tr/",
                  "https://i.tmgrup.com.tr/atv/c/i/player_imaj_v3.png"),
                 ("atv Avrupa", "https://www.atvavrupa.tv/canli-yayin", "45d4cd69-814c-4e2e-bdad-11de9e4b9afd", "https://www.atvavrupa.tv/",
                  "https://i.tmgrup.com.tr/aav/site/v2/i/imaj_atvavrupa_yeni.jpg"))
# video types of the site's lists: episodes, trailers, special clips (each with its own sort order)
VTYPE_EPISODES, VTYPE_TRAILERS, VTYPE_CLIPS = "10", "11", "12"
VTYPE_ORDER = {VTYPE_EPISODES: "4", VTYPE_TRAILERS: "4", VTYPE_CLIPS: "3"}
PAGE_SIZE = 30
LOCAL_PAGE_SIZE = 50
MAX_SEASONS = 40
# Turkish month names, folded to ASCII (Ocak, Şubat, Mart ... Aralık)
TR_MONTHS = {"ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6, "temmuz": 7,
             "agustos": 8, "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12}
TR_FOLD = (("ç", "c"), ("Ç", "c"), ("ğ", "g"), ("Ğ", "g"), ("ı", "i"), ("İ", "i"), ("ö", "o"), ("Ö", "o"),
           ("ş", "s"), ("Ş", "s"), ("ü", "u"), ("Ü", "u"))
# list pages of the main menu: path, kind
SHOW_LISTS = {"diziler": "series", "eski-diziler": "series", "programlar": "programme"}

SHOW_ITEM_RE = re.compile(r'<div class="category-classic-item[^"]*">\s*<a href="/([a-z0-9-]+)"(.*?)</a>', re.S)
VIDEO_BOX_RE = re.compile(r'<a href="(/[^"]+/izle)"[^>]*>(.*?)</a>', re.S)
SEARCH_BOX_RE = re.compile(r'<figure class="news-box">(.*?)</figure>', re.S)


class AtvTR(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "slug", "kind", "cid", "season", "vtype",
                  "s_title", "episode", "live", "site_id", "referer", "total")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "atvtr", "cookie": "atvtr.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Referer": gettytul()})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/atvtr135.png")
        self.showCache = {}  # list path -> [(slug, title, icon)]
        self.seriesCache = {}  # slug -> parsed episodes page
        self.MENU = [{"category": "atv_live", "title": _("Live channels")},
                     {"category": "atv_shows", "title": _("Series"), "list_path": "diziler", "url": self.MAIN_URL + "diziler"},
                     {"category": "atv_shows", "title": _("Archive"), "list_path": "eski-diziler", "url": self.MAIN_URL + "eski-diziler"},
                     {"category": "atv_shows", "title": _("Programmes"), "list_path": "programlar", "url": self.MAIN_URL + "programlar"},
                     {"category": "atv_news", "title": "atv Haber"}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("atvtr")
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        return self.cm.getPage(url, addParams or self.defaultParams, post_data)

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
            if cItem.get("category", "") in ("atv_series", "atv_season", "atv_videos"):
                return "folder:%s" % url
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _json(self, url, params=None):
        sts, data = self.getPage(url, params)
        if not sts or not data:
            return {}
        try:
            data = ensure_str_deep(json_loads(data))
            return data if isinstance(data, dict) else {}
        except Exception:
            printExc()
        return {}

    def _slug(self, cItem):
        slug = cItem.get("slug", "")
        if not slug:
            slug = self.cm.ph.getSearchGroups(cItem.get("url", ""), r'atv\.com\.tr/([a-z0-9-]+)')[0]
        return slug

    @staticmethod
    def _fold(text):
        text = str(text or "")
        for src, dst in TR_FOLD:
            text = text.replace(src, dst)
        return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip("-")

    def _isoDate(self, text):
        # "17 Mart 2026, Salı" / "20.09.2019, Cuma" -> "2026-03-17"
        text = self.cleanHtmlStr(text)
        match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', text)
        if match:
            return "%s-%02d-%02d" % (match.group(3), int(match.group(2)), int(match.group(1)))
        match = re.search(r'(\d{1,2})\s+(\S+)\s+(\d{4})', text)
        if match:
            month = TR_MONTHS.get(self._fold(match.group(2)), 0)
            if month:
                return "%s-%02d-%02d" % (match.group(3), month, int(match.group(1)))
        return ""

    def _rawEpisodeTitle(self, show, label):
        label = label.strip()
        if show and label and self._fold(show) not in self._fold(label):
            return "%s - %s" % (show, label)
        return label or show

    def _episodeTitle(self, show, label, season, episode):
        if IsMediaNamingNormalized() and show and season and episode:
            return "%s - %s" % (show, formatSxxExx(season, episode))
        return self._rawEpisodeTitle(show, label)

    ###################################################
    # main lists
    ###################################################
    def _shows(self, path):
        if path in self.showCache:
            return self.showCache[path]
        shows = []
        sts, data = self.getPage(self.MAIN_URL + path)
        if sts:
            # only the page body, the menu holds the same links
            data = data[data.find('class="container-fluid'):] if 'class="container-fluid' in data else data
            seen = set()
            for slug, body in SHOW_ITEM_RE.findall(data):
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="title">(.*?)</h[23]>')[0])
                alt = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'alt="([^"]+)"')[0])
                if slug in seen or not (alt or title):
                    continue
                seen.add(slug)
                info = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'</h[23]>\s*<span>(.*?)</span>')[0])
                shows.append((slug, alt or title, self.cm.ph.getSearchGroups(body, r'<img src="([^"]+)"')[0], info))
        if shows:
            self.showCache[path] = shows
        return shows

    def _addShow(self, cItem, slug, title, icon, info, kind):
        params = stripPagerKeys(dict(cItem), ("list_path", "list_url", "search_pattern"))
        params.update({"good_for_fav": True, "category": "atv_series", "title": title, "slug": slug, "kind": kind,
                       "url": self.MAIN_URL + slug, "icon": icon or self.DEFAULT_ICON_URL, "desc": info})
        self.addDir(params)

    def listShows(self, cItem):
        path = cItem.get("list_path", "diziler")
        kind = SHOW_LISTS.get(path, "series")
        shows = self._shows(path)
        page = max(1, int(cItem.get("page", 1) or 1))
        lastPage = max(1, (len(shows) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE)
        if len(shows) <= 100:
            page, lastPage, part = 1, 1, shows
        else:
            part = shows[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]
        for slug, title, icon, info in part:
            self._addShow(cItem, slug, title, icon, info, kind)
        if lastPage > 1:
            addPagingItems(self, dict(cItem, desc=""), page, page < lastPage, lastPage, self.MAIN_URL + path + "?sayfa={page}")

    def listNews(self, cItem):
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        menu = self.cm.ph.getDataBeetwenMarkers(data, "<button>atv Haber</button>", "</ul>", False)[1]
        for slug, title in re.findall(r'<a href="/([a-z0-9-]+)"[^>]*>(.*?)</a>', menu):
            self._addShow(cItem, slug, self.cleanHtmlStr(title), "", "", "news")

    def listLive(self, cItem):
        for title, url, siteId, referer, icon in LIVE_CHANNELS:
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": url, "site_id": siteId, "referer": referer, "icon": icon,
                           "live": True, "desc": _("Live channels")})
            self.addVideo(params)

    ###################################################
    # series
    ###################################################
    def _seriesData(self, slug):
        # the episodes page: category id, season / episode selectors, trailer and clip sections
        if slug in self.seriesCache:
            return self.seriesCache[slug]
        info = {"cid": "", "seasons": [], "episodes": [], "trailers": False, "clips": False, "probed": None}
        sts, data = self.getPage(self.MAIN_URL + slug + "/bolumler")
        if not sts or not data:
            return info
        info["cid"] = self.cm.ph.getSearchGroups(data, r'id="category-id" value="([^"]+)"')[0]
        seasonBox = self.cm.ph.getDataBeetwenMarkers(data, 'id="season-combobox"', "</select>", False)[1]
        info["seasons"] = sorted(set(int(s) for s in re.findall(r'<option value="(\d+)"', seasonBox)))
        episodeBox = self.cm.ph.getDataBeetwenMarkers(data, 'id="episode-combobox"', "</select>", False)[1]
        for url, label in re.findall(r'<option value="(/[^"]+/izle)"[^>]*>([^<]*)<', episodeBox):
            info["episodes"].append((url, self.cleanHtmlStr(label)))
        info["trailers"] = ('href="/%s/fragman"' % slug) in data
        info["clips"] = ('href="/%s/ozelvideo"' % slug) in data
        if info["cid"]:
            self.seriesCache[slug] = info
        return info

    def _seasonList(self, cid, season):
        url = self.MAIN_URL + "ajax/get-season-episode-list?seriesid=%s&season=%s&type=%s" % (cid, season, VTYPE_EPISODES)
        episodes = []
        for entry in self._json(url).get("list") or []:
            path, text = entry.get("Value") or "", self.cleanHtmlStr(entry.get("Text") or "")
            if not path:
                continue
            label, _sep, date = text.partition(" / ")
            episodes.append((path, label.strip(), date.strip()))
        return episodes

    def _probeSeasons(self, info):
        # series without a season selector: the season lists of the ajax call, episodes missing there
        # (often the first ones) go to the season their number belongs to
        if info["probed"] is not None:
            return info["probed"]
        seasons = {}
        for season in range(1, MAX_SEASONS + 1):
            episodes = self._seasonList(info["cid"], season)
            if not episodes:
                break
            seasons[season] = episodes
        if seasons:
            known = set(e[0] for eps in seasons.values() for e in eps)
            ranges = []
            for season in sorted(seasons):
                nums = [self._epNum(e[1]) for e in seasons[season]]
                ranges.append((season, max(nums or [0])))
            for path, label in info["episodes"]:
                if path in known:
                    continue
                num = self._epNum(label)
                target = ranges[-1][0]
                for season, top in ranges:
                    if num and num <= top:
                        target = season
                        break
                seasons[target].append((path, label, ""))
        info["probed"] = seasons
        return seasons

    @staticmethod
    def _epNum(label):
        match = re.match(r'\s*(\d+)\s*\.', label or "")
        return int(match.group(1)) if match else 0

    def listSeries(self, cItem):
        slug = self._slug(cItem)
        printDBG("AtvTR.listSeries [%s]" % slug)
        info = self._seriesData(slug)
        if not info["cid"]:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        page = max(1, int(cItem.get("page", 1) or 1))
        base = stripPagerKeys(dict(cItem), ("list_path", "search_pattern"))
        base.update({"slug": slug, "cid": info["cid"], "s_title": show, "good_for_fav": True})
        seasons = info["seasons"]
        probed = {}
        if not seasons:
            probed = self._probeSeasons(info)
            seasons = sorted(probed)
        if page == 1:
            for vtype, label, path, present in ((VTYPE_TRAILERS, "Fragmanlar", "fragman", info["trailers"]),
                                                (VTYPE_CLIPS, "Özel Videolar", "ozelvideo", info["clips"])):
                if present:
                    self.addDir(dict(base, category="atv_videos", vtype=vtype, title=label, url=self.MAIN_URL + "%s/%s" % (slug, path), desc=show))
        if len(seasons) == 1 and probed:
            # one season only: its episodes right in the series folder (local pages keep this folder's category)
            self._listEpisodes(dict(base, page=page), probed[seasons[0]], seasons[0])
            return
        if seasons:
            for season in seasons:
                count = len(probed.get(season) or [])
                self.addDir(dict(base, category="atv_season", season=str(season), title=_("Season %s") % season,
                                 url=self.MAIN_URL + "%s/bolumler?sezon=%d" % (slug, season),
                                 desc=("%s: %d" % (_("Episodes"), count)) if count else show))
            return
        # no seasons at all (news, films): the plain episode list with covers and dates
        params = dict(base, category="atv_videos", vtype=VTYPE_EPISODES, url=self.MAIN_URL + slug + "/bolumler",
                      total=len(info["episodes"]))
        self.listVideos(params)

    def listSeason(self, cItem):
        slug = self._slug(cItem)
        season = int(cItem.get("season", 0) or 0)
        info = self._seriesData(slug)
        cid = cItem.get("cid") or info["cid"]
        if not info["seasons"] and info["cid"]:
            episodes = self._probeSeasons(info).get(season) or []
        else:
            episodes = self._seasonList(cid, season)
        self._listEpisodes(cItem, episodes, season)

    def _listEpisodes(self, cItem, episodes, season):
        show = cItem.get("s_title") or cItem.get("title", "")
        episodes = sorted(episodes, key=lambda e: self._epNum(e[1]))
        page = max(1, int(cItem.get("page", 1) or 1))
        lastPage = 1
        if len(episodes) > 100:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            page = min(page, lastPage)
            episodes = episodes[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]
        else:
            page = 1
        base = stripPagerKeys(dict(cItem), ("total", "vtype"))
        for path, label, date in episodes:
            num = self._epNum(label)
            params = dict(base)
            params.update({"good_for_fav": True, "url": self.MAIN_URL + path.lstrip("/"), "s_title": show,
                           "season": str(season), "episode": str(num) if num else "",
                           "title": self._episodeTitle(show, label, season, num), "desc": date})
            params.pop("category", None)
            self.addVideo(params)
        if lastPage > 1:
            # the page lives in cItem["page"] - the template keeps the url (and so the folder's watched key) unchanged
            url = cItem.get("url", "").replace("{", "{{").replace("}", "}}")
            addPagingItems(self, dict(cItem, desc=""), page, page < lastPage, lastPage, url)

    def listVideos(self, cItem):
        # the site's "load more" list: episodes / trailers / clips of a series, PAGE_SIZE per page
        slug = self._slug(cItem)
        cid = cItem.get("cid") or self._seriesData(slug)["cid"]
        vtype = cItem.get("vtype", VTYPE_EPISODES)
        page = max(1, int(cItem.get("page", 1) or 1))
        url = self.MAIN_URL + "ajax/series/infinityvideolist?pageindex=%d&takecount=%d&categoryid=%s&videotype=%s&orderby=%s&articletype=%s" % (
            page, PAGE_SIZE, cid, vtype, VTYPE_ORDER.get(vtype, "4"), vtype)
        data = self._json(url)
        html = data.get("html") or "" if data.get("status") else ""
        show = cItem.get("s_title") or cItem.get("title", "")
        base = stripPagerKeys(dict(cItem), ("total", "vtype", "season"))
        count = 0
        for path, body in VIDEO_BOX_RE.findall(html):
            count += 1
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="style-01[^"]*">(.*?)</span>')[0])
            sub = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="style-02[^"]*">(.*?)</span>')[0])
            date = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="date">(.*?)</div>')[0])
            params = dict(base)
            params.pop("category", None)
            params.update({"good_for_fav": True, "url": self.MAIN_URL + path.lstrip("/"), "s_title": show,
                           "icon": self.cm.ph.getSearchGroups(body, r'<img src="([^"]+)"')[0] or cItem.get("icon", "")})
            if not date and self._isoDate(sub):
                # news: show name + broadcast date instead of "N. Bölüm" + show name
                date, sub = sub, ""
            if vtype == VTYPE_EPISODES:
                num = self._epNum(label) or int(self.cm.ph.getSearchGroups(path, r'/(\d+)-bolum/izle')[0] or 0)
                if num and not self._epNum(label):
                    label = "%d. Bölüm" % num
                elif not label or self._fold(label) == self._fold(show):
                    label = sub or label
                title = self._rawEpisodeTitle(show, label)
                params.update({"title": normalizeMediathekTitle(title, date=self._isoDate(date)), "episode": str(num) if num else "",
                               "desc": date})
            elif vtype == VTYPE_TRAILERS:
                # "23. Bölüm" + "23. Bölüm 2. Fragmanı"
                params.update({"title": self._rawEpisodeTitle(show, sub or label), "desc": date})
            else:
                params.update({"title": self._rawEpisodeTitle(show, label or sub), "desc": " | ".join([x for x in (date, sub) if x and x != show])})
            self.addVideo(params)
        total = int(cItem.get("total", 0) or 0)
        lastPage = (total + PAGE_SIZE - 1) // PAGE_SIZE if total else 0
        hasNext = count >= PAGE_SIZE and (not lastPage or page < lastPage)
        addPagingItems(self, dict(cItem, desc="", category="atv_videos"), page, hasNext, lastPage, cItem.get("url", "").replace("{", "{{").replace("}", "}}"))

    ###################################################
    # search
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AtvTR.listSearchResult [%s]" % searchPattern)
        folded = self._fold(searchPattern)
        if folded:
            seen = set()
            for path, kind in (("diziler", "series"), ("eski-diziler", "series"), ("programlar", "programme")):
                for slug, title, icon, info in self._shows(path):
                    if slug not in seen and (folded in slug or folded in self._fold(title)):
                        seen.add(slug)
                        self._addShow(cItem, slug, title, icon, info, kind)
        self.listSearchVideos(dict(cItem, category="atv_search_videos", s_query=searchPattern,
                                   url=self.MAIN_URL + "arama?query=" + urllib_quote_plus(searchPattern)))

    def listSearchVideos(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        query = urllib_quote(cItem.get("s_query", ""))
        if page == 1:
            url = self.MAIN_URL + "arama?query=" + query
        else:
            url = self.MAIN_URL + "get/arama?query=%s&page=%d" % (query, page)
        sts, data = self.getPage(url)
        if not sts:
            return
        boxes = SEARCH_BOX_RE.findall(data)
        base = stripPagerKeys(dict(cItem), ("s_title", "season", "episode"))
        base.pop("category", None)
        for body in boxes:
            path = self.cm.ph.getSearchGroups(body, r'href="(/[^"]+/izle)"')[0]
            if not path:
                continue  # galleries, news
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="new-box-name">(.*?)</span>')[0])
            txt = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="txt">(.*?)</span>')[0])
            number = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="bolum-number">(.*?)</span>')[0])
            if not title:
                continue
            # "26. BÖLÜM" for the episode and for both its trailers - the path tells them apart
            episode, trailer = self.cm.ph.getSearchGroups(path, r'/(\d+)-bolum(?:-(\d+)-fragman)?/izle', 2)
            if episode and trailer:
                label = "%s. Bölüm %s. Fragmanı" % (episode, trailer)
            elif episode:
                label = "%s. Bölüm" % episode
            else:
                label = number or txt
            params = dict(base)
            params.update({"good_for_fav": True, "url": self.MAIN_URL + path.lstrip("/"), "title": self._rawEpisodeTitle(title, label),
                           "s_title": title, "episode": "" if trailer else episode,
                           "icon": self.cm.ph.getSearchGroups(body, r'<img src="([^"]+)"')[0],
                           "desc": " | ".join([x for x in (number, txt) if x])})
            self.addVideo(params)
        addPagingItems(self, dict(cItem, desc="", category="atv_search_videos"), page, len(boxes) >= 20)

    ###################################################
    # links
    ###################################################
    def _playerVideo(self, cItem):
        if cItem.get("live"):
            siteId, videoId, referer = cItem.get("site_id") or ATV_SITE_ID, LIVE_ID, cItem.get("referer") or self.MAIN_URL
        else:
            sts, data = self.getPage(cItem.get("url", ""))
            if not sts:
                return {}, ""
            videoId = self.cm.ph.getSearchGroups(data, r'data-videoid="([^"]+)"')[0]
            siteId = self.cm.ph.getSearchGroups(data, r'data-websiteid="([^"]+)"')[0] or ATV_SITE_ID
            referer = self.MAIN_URL
            if not videoId:
                return {}, ""
        params = {"header": dict(self.HEADER, Referer=referer, Accept="application/json")}
        data = self._json(PLAYER_API % (siteId, videoId), params)
        return (data.get("video") or {}) if data.get("success") else {}, referer

    def _liveToken(self, url, referer):
        params = {"header": dict(self.HEADER, Referer=referer, Accept="application/json")}
        params["header"].update({"X-isApp": "false", "X-Rand": str(int(time.time() * 1000))})
        data = self._json(TOKEN_URL % (int(time.time()) % 1000000 + 1, urllib_quote_plus(url)), params)
        return data.get("Url") or "" if data.get("Success") else ""

    def getLinksForVideo(self, cItem):
        printDBG("AtvTR.getLinksForVideo [%s]" % cItem.get("url", ""))
        video, referer = self._playerVideo(cItem)
        if not video:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        live = bool(cItem.get("live"))
        origin = referer.rstrip("/")
        baseMeta = {"User-Agent": self.HEADER.get("User-Agent"), "Referer": referer, "Origin": origin}
        if live:
            master = self._liveToken(video.get("VideoUrl") or "", referer)
            if not master:
                SetIPTVPlayerLastHostError(_("Content not available"))
                return []
            liveMeta = dict(baseMeta, iptv_livestream=True)
            urlTab = []
            for item in getDirectM3U8Playlist(strwithmeta(master, dict(liveMeta)), checkExt=False, checkContent=True):
                name = "%sp" % item.get("height") if item.get("height") else item.get("name", "HLS")
                urlTab.append({"name": "HLS %s" % name, "url": strwithmeta(item["url"], dict(liveMeta, iptv_proto="m3u8")), "need_resolve": 0})
            urlTab.append({"name": "HLS (adaptive)", "url": strwithmeta(master, dict(liveMeta, iptv_proto="m3u8")), "need_resolve": 0})
            return urlTab

        subTracks = []
        srt = video.get("VideoSrtFile") or ""
        if srt.startswith("http"):
            subTracks.append({"title": "Türkçe", "url": srt, "lang": "tr", "format": "srt"})
        vodMeta = dict(baseMeta)
        if subTracks:
            vodMeta["external_sub_tracks"] = subTracks
        urlTab = []
        mp4 = video.get("VideoUrl") or ""
        if ".mp4" in mp4:
            quality = self.cm.ph.getSearchGroups(mp4, r'_(\d{3,4}p)_')[0]
            urlTab.append({"name": "MP4 %s" % quality if quality else "MP4", "url": strwithmeta(mp4, dict(vodMeta)), "need_resolve": 0})
        hlsUrl = video.get("VideoSmilUrl") or video.get("VideoMobileUrl") or ""
        if ".m3u8" in hlsUrl:
            hls = getDirectM3U8Playlist(strwithmeta(hlsUrl, dict(baseMeta)), checkExt=False, checkContent=True)
            try:
                hls.sort(key=lambda x: int(x.get("bitrate") or 0), reverse=True)
            except Exception:
                printExc()
            names = set()
            for item in hls:
                name = "%sp" % item.get("height") if item.get("height") else item.get("name", "")
                if name in names and item.get("bitrate"):
                    name = "%s %dk" % (name, int(item["bitrate"]) // 1000)
                names.add(name)
                urlTab.append({"name": ("HLS %s" % name).strip(), "url": strwithmeta(item["url"], dict(vodMeta, iptv_proto="m3u8")), "need_resolve": 0})
            if not hls and not urlTab:
                urlTab.append({"name": "HLS", "url": strwithmeta(hlsUrl, dict(vodMeta, iptv_proto="m3u8")), "need_resolve": 0})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("Content not available"))
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        return []

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("AtvTR.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        if cItem.get("live"):
            otherInfo["status"] = _("On Air")
            return [{"title": title, "text": "%s - %s" % (title, _("Live channels")), "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]
        plot = ""
        if cItem.get("type") == "video":
            sts, data = self.getPage(cItem.get("url", ""))
            if sts:
                ld = {}
                for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', data, re.S):
                    try:
                        ld = json_loads(block.strip())
                    except Exception:
                        ld = {}
                    if isinstance(ld, dict) and ld.get("@type") == "VideoObject":
                        break
                    ld = {}
                match = re.search(r'class="detail-text">(.*?)</div>', data, re.S)
                synopsis = self.cleanHtmlStr(match.group(1)) if match else ""
                text = synopsis or text or self.cleanHtmlStr(ld.get("description", ""))
                icon = str(ld.get("thumbnailUrl") or "") or icon
                date = str(ld.get("uploadDate") or "")[:10]
                if date:
                    otherInfo["released"] = date
                match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', str(ld.get("duration") or ""))
                if match and (match.group(1) or match.group(2)):
                    otherInfo["duration"] = "%d min" % (int(match.group(1) or 0) * 60 + int(match.group(2) or 0))
                if cItem.get("season") and cItem.get("episode"):
                    otherInfo["episodes"] = formatSxxExx(cItem["season"], cItem["episode"])
        show = cItem.get("s_title") or (title if cItem.get("category") == "atv_series" else "")
        if show and cItem.get("kind", "series") == "series":
            try:
                meta = getMeta("tv", show) or {}
            except Exception:
                printExc()
                meta = {}
            # the episode's own date / duration win over the series data
            otherInfo = dict(meta.get("info", {}), **otherInfo)
            plot = meta.get("plot", "")
            if not icon or icon == self.DEFAULT_ICON_URL:
                icon = meta.get("poster", "") or icon
        if cItem.get("type") == "video":
            text = text or plot
        elif plot and plot != text:
            text = "%s[/br][/br]%s" % (text, plot) if text else plot
        if not text:
            text = "%s - atv" % title
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("atv_") or cItem.get("type") == "video":
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
        printDBG("AtvTR.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "atv_live":
            self.listLive(self.currItem)
        elif category == "atv_shows":
            self.listShows(self.currItem)
        elif category == "atv_news":
            self.listNews(self.currItem)
        elif category == "atv_series":
            self.listSeries(self.currItem)
        elif category == "atv_season":
            self.listSeason(self.currItem)
        elif category == "atv_videos":
            self.listVideos(self.currItem)
        elif category == "atv_search_videos":
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
        CHostBase.__init__(self, AtvTR(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("atvtr")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") == "atv_series"
