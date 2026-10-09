# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - carateen.tv (Arabic cartoons: the site's own catalogue + the SpaceToon Go catalogue); the JSON API
#     answers AES-256-CBC encrypted ({"iv", "encryptedData"}, key from the site's web client) - the two
#     show lists (~1.3 MB / ~0.9 MB) are fetched once per session and filtered locally
#   - Carateen films / series, SpaceToon "planets" (sections) and search over both catalogues
#   - series -> parts (SpaceToon "الجزء ..." groups, when there is more than one) -> episodes (local paging
#     over 100); films are VIDEO rows whose links are their versions (Japanese / Arabic dub ...)
#   - links: the episode API gives an HLS playlist on the site's CDN, which wants Referer / Origin carateen.tv
#   - watched flag (series:/season:/video: keys), downloaded flag, favourites, name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the API's description / info
import re
import time
from binascii import unhexlify
from random import choice

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs import pyaes
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, requireDownloaderForDisguisedHls
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

try:
    # pycryptodome (when the image has it) is much faster than pyaes for the 1.3 MB show list
    from Crypto.Cipher import AES as CryptoAES
except Exception:
    CryptoAES = None


def GetConfigList():
    return []


def gettytul():
    return "https://carateen.tv/"


KEY = b"7annaba3l_loves_crypto_safe_key!"
LOCAL_PAGE_SIZE = 100
PART_ORDINALS = [
    ("الأول", 1), ("الاول", 1), ("الثاني", 2), ("الثالث", 3), ("الرابع", 4), ("الخامس", 5), ("السادس", 6),
    ("السابع", 7), ("الثامن", 8), ("التاسع", 9), ("العاشر", 10), ("الحادي عشر", 11), ("الثاني عشر", 12),
    ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
]
# "description_technical" lines of the Carateen catalogue -> INFO keys
TECH_KEYS = (("genres", "نوع"), ("production", "إنتاج شركة"), ("translation", "الترجمة"), ("episodes", "عدد الحلقات"),
             ("duration", "مدة الحلقة"), ("quality", "الجودة"))


def _decrypt(js):
    # {"iv": hex, "encryptedData": hex} -> the decoded JSON (AES-256-CBC, PKCS#7), None on failure
    try:
        iv, data = unhexlify(js["iv"]), unhexlify(js["encryptedData"])
        if CryptoAES is not None:
            plain = CryptoAES.new(KEY, CryptoAES.MODE_CBC, iv).decrypt(data)
        else:
            decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(KEY, iv), padding=pyaes.PADDING_NONE)
            plain = decrypter.feed(data) + decrypter.feed()
        pad = plain[-1] if isinstance(plain[-1], int) else ord(plain[-1])
        return json_loads(ensure_str(plain[:-pad]))
    except Exception:
        printExc()
    return None


def _anonymousId():
    # the web client's anonymous user id: anon_<13 random [a-z0-9]>_<base36 ms timestamp>
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    number, stamp = int(time.time() * 1000), ""
    while number:
        number, rest = divmod(number, 36)
        stamp = chars[rest] + stamp
    return "anon_%s_%s" % ("".join(choice(chars) for _i in range(13)), stamp)


def _partNum(label):
    # "الجزء السابع" -> 7 (longest ordinal first: "الثاني عشر" before "الثاني")
    label = label or ""
    num = re.search(r"\d+", label)
    if num:
        return int(num.group(0))
    for word, val in sorted(PART_ORDINALS, key=lambda o: -len(o[0])):
        if word in label:
            return val
    return 0


def _metaTitle(name):
    # Latin words for the metadata search, the Arabic title when there are none
    latin = " ".join(word for word in (name or "").split() if re.search(r"[A-Za-z]", word))
    return latin or name


class CaraTeen(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "show_id", "source", "part", "s_title",
                  "s_season", "s_episode", "episode_id", "meta_type", "meta_title", "meta_year")
    SHOWS = {}  # source -> decrypted show list, once per session

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "carateen", "cookie": "carateen.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/carateen135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.MENU = [
            {"category": "ct_list", "title": _("Movies"), "source": "ct", "filter": "movies"},
            {"category": "ct_list", "title": _("Series"), "source": "ct", "filter": "series"},
            {"category": "ct_planets", "title": "SpaceToon"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("carateen")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def _api(self, path, post=None):
        params = {"header": dict(self.HEADER, Referer=self.MAIN_URL, Accept="application/json, text/plain, */*")}
        params["header"]["X-Carateen-Client"] = "web-frontend-v1"
        if post is not None:
            params["header"]["Content-Type"] = "application/json"
            params["raw_post_data"] = True
            post = json_dumps(post)
        sts, data = self.cm.getPage(self.getFullUrl(path), params, post)
        if not sts:
            return None
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return None
        return _decrypt(data) if isinstance(data, dict) and "encryptedData" in data else data

    def _shows(self, source):
        shows = CaraTeen.SHOWS.get(source)
        if not shows:
            shows = self._api("/api/sp/tvshows" if source == "sp" else "/api/tvshows")
            shows = shows if isinstance(shows, list) else []
            if shows:
                CaraTeen.SHOWS[source] = shows
        return shows

    def _showUrl(self, source, showId, episodeId=""):
        # stable page-like keys (watched / downloaded / favourites), the site's own route is /watch/<show>/<episode>
        url = self.getFullUrl("/%swatch/%s" % ("sp/" if source == "sp" else "", showId))
        return "%s/%s" % (url, episodeId) if episodeId else url

    def _icon(self, path, folder="posters"):
        if not path:
            return ""
        return path if path.startswith("http") else self.getFullUrl("/assets/img/%s/%s" % (folder, path))

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("ct_video", "ct_series", "ct_part"):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"ct_video": "video", "ct_series": "series", "ct_part": "season"}.get(cItem.get("category", ""), "")
            path = re.sub(r"^https?://[^/]+", "", cItem.get("url", "")) if prefix else ""
            if path and prefix == "season":
                path = "%s#%s" % (path, cItem.get("part", ""))
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _showParams(self, source, show):
        # one show of either catalogue -> folder / video row params
        if source == "sp":
            title, year = show.get("name", ""), ""
            isMovie = show.get("is_movie") == 1
            desc = " | ".join(x for x in (show.get("planet_name"), show.get("tags"), show.get("pref")) if x)
            icon = self._icon(show.get("cover_full_path", ""))
        else:
            title, year = show.get("title", ""), show.get("release_year", "") or ""
            isMovie = "فيلم" in (show.get("category") or "")
            desc = " | ".join(x for x in (show.get("category"), year, show.get("quality"), show.get("description")) if x)
            icon = self._icon(show.get("poster_cover") or show.get("poster_cover_alt", ""))
        title = (title or "").strip()
        params = {"name": "category", "good_for_fav": True, "source": source, "show_id": show.get("id", ""), "icon": icon,
                  "desc": desc, "url": self._showUrl(source, show.get("id", "")), "s_title": title, "meta_title": title,
                  "meta_year": year}
        if isMovie:
            params.update({"category": "ct_video", "meta_type": "movie",
                           "title": ("%s (%s)" % (title, year) if year else title) if IsMediaNamingNormalized() else title})
        else:
            params.update({"category": "ct_series", "title": title, "meta_type": "tv"})
        return params

    def _addRows(self, cItem, rows):
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in rows[start:start + LOCAL_PAGE_SIZE]:
            if params["category"] == "ct_video":
                self.addVideo(params)
            else:
                self.addDir(params)
        if len(rows) > LOCAL_PAGE_SIZE:
            lastPage = (len(rows) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listShows(self, cItem):
        source, flt = cItem.get("source", "ct"), cItem.get("filter", "")
        printDBG("CaraTeen.listShows [%s] [%s]" % (source, flt))
        rows = []
        for show in self._shows(source):
            if source == "sp" and show.get("planet_name") != flt:
                continue
            params = self._showParams(source, show)
            if source == "ct" and (params["category"] == "ct_video") != (flt == "movies"):
                continue
            rows.append(params)
        self._addRows(cItem, rows)

    def listPlanets(self, cItem):
        planets = []
        for show in self._shows("sp"):
            if show.get("planet_name") and show["planet_name"] not in planets:
                planets.append(show["planet_name"])
        for planet in planets:
            self.addDir({"name": "category", "category": "ct_list", "title": planet, "source": "sp", "filter": planet,
                         "icon": self.DEFAULT_ICON_URL})

    def _episodes(self, cItem):
        source, showId = cItem.get("source", "ct"), cItem.get("show_id", "")
        episodes = self._api("/api/sp/episodes?id=%s" % showId if source == "sp" else "/api/episodes?id=%s" % showId)
        return episodes if isinstance(episodes, list) else []

    def listSeries(self, cItem):
        printDBG("CaraTeen.listSeries [%s]" % cItem.get("url", ""))
        episodes = self._episodes(cItem)
        parts = []
        for episode in episodes:
            # SpaceToon groups long shows in parts ("الجزء السابع", "الحلقات الحديثة"), specials have none
            part = (episode.get("season") or "") if cItem.get("source") == "sp" else ""
            if part not in parts:
                parts.append(part)
        if len(parts) <= 1:
            self._listEpisodes(cItem, episodes)
            return
        show = cItem.get("s_title", "") or cItem.get("title", "")
        for part in sorted(parts, key=lambda p: (_partNum(p) or 99) if p else 100):
            num = _partNum(part)
            label = part or _("Specials")
            params = stripPagerKeys(dict(cItem))
            params.update({"category": "ct_part", "part": part, "s_season": num or 1,
                           "title": "%s - %s" % (show, formatSxxExx(num)) if num and IsMediaNamingNormalized() else "%s - %s" % (show, label)})
            self.addDir(params)

    def listPart(self, cItem):
        part = cItem.get("part", "")
        self._listEpisodes(cItem, [e for e in self._episodes(cItem) if (e.get("season") or "") == part])

    def _listEpisodes(self, cItem, episodes):
        source = cItem.get("source", "ct")
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        rows = []
        for idx, episode in enumerate(episodes):
            if source == "sp":
                num = episode.get("number")
                label = "%s %s" % (num, episode.get("pref", "")) if num is not None else episode.get("pref", "")
                icon = self._icon(episode.get("cover_full_path", ""))
            else:
                label = (episode.get("title") or "").replace("اضغط للمشاهدة", "").strip()
                num = self.cm.ph.getSearchGroups(label, r"^(\d+)\s*[.-]")[0]
                icon = self._icon(episode.get("thumbnail", ""), "thumbnails")
            label = label or _("Episode %d") % (idx + 1)
            title = "%s - %s" % (show, formatSxxExx(season or 1, num)) if IsMediaNamingNormalized() and num else "%s - %s" % (show, label)
            params = stripPagerKeys(dict(cItem))
            params.update({"category": "ct_video", "title": title, "icon": icon or cItem.get("icon", ""), "episode_id": episode.get("id", ""),
                           "url": self._showUrl(source, cItem.get("show_id", ""), episode.get("id", "")),
                           "s_episode": str(num) if num else "", "meta_type": "tv"})
            rows.append(params)
        self._addRows(cItem, rows)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CaraTeen.listSearchResult [%s]" % searchPattern)
        pattern = searchPattern.strip().lower()
        rows = []
        for source in ("ct", "sp"):
            for show in self._shows(source):
                if pattern and pattern in (show.get("title") or show.get("name") or "").lower():
                    rows.append(self._showParams(source, show))
        cItem = dict(cItem)
        cItem.update({"category": "ct_search", "search_pattern": searchPattern})
        self._addRows(cItem, rows)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("CaraTeen.getLinksForVideo [%s]" % cItem.get("url", ""))
        if cItem.get("episode_id"):
            versions = [(cItem.get("episode_id"), "")]
        else:
            # a film: its "episodes" are the versions (Japanese / Arabic dub ...), without the intro clip
            versions = [(e.get("id", ""), (e.get("pref") or e.get("title") or "").replace("اضغط للمشاهدة", "").strip())
                        for e in self._episodes(cItem) if "شارة" not in (e.get("title") or "")]
        urltab = []
        server = "SpaceToon" if cItem.get("source") == "sp" else "Carateen"
        for idx, (episodeId, label) in enumerate(versions):
            if episodeId:
                if not label:
                    label = "%s %d" % (_("Version"), idx + 1) if len(versions) > 1 else server
                urltab.append({"name": label,
                               "url": "%s#%s" % (self._showUrl(cItem.get("source", "ct"), cItem.get("show_id", ""), episodeId),
                                                 cItem.get("source", "ct")), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("CaraTeen.getVideoLinks [%s]" % videoUrl)
        match = re.search(r"/watch/(\d+)/(\d+)#(sp|ct)$", videoUrl)
        if not match:
            return []
        showId, episodeId, source = match.groups()
        if source == "sp":
            data = self._api("/api/sp/episode/link", {"episodeId": episodeId, "userId": _anonymousId()})
        else:
            data = self._api("/api/episode?episodeId=%s&showId=%s" % (episodeId, showId))
        url = (data or {}).get("link") or (data or {}).get("streamUrl") or ""
        printDBG("CaraTeen.getVideoLinks stream [%s]" % url)
        if not self.cm.isValidUrl(url):
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        # the CDN answers 403 without the site as Referer / Origin (playlist and segments)
        url = strwithmeta(url, {"Referer": self.MAIN_URL, "Origin": self.MAIN_URL.rstrip("/"), "User-Agent": self.HEADER["User-Agent"]})
        # segments are MPEG-TS named *.jpg - exteplayer3's ffmpeg refuses them, hlsdl buffering does not
        links = requireDownloaderForDisguisedHls(getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=99999999))
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(links or [{"name": "HLS", "url": url}], sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, cItem):
        source, showId = cItem.get("source", "ct"), cItem.get("show_id", "")
        show = [s for s in self._shows(source) if str(s.get("id", "")) == str(showId)]
        if not show:
            return "", {}
        show, info = show[0], {}
        if source == "sp":
            for key, field in (("genres", "tags"), ("category", "planet_name"), ("episodes", "ep_count"), ("age_limit", "min_age")):
                if show.get(field):
                    info[key] = str(show[field])
            story = show.get("pref", "")
        else:
            for key, field in (("category", "category"), ("year", "release_year"), ("quality", "quality"), ("duration", "episodes_length")):
                if show.get(field):
                    info[key] = str(show[field])
            for key, word in TECH_KEYS:
                val = self.cm.ph.getSearchGroups(show.get("description_technical", ""), r"%s[^:\n]*:\s*([^\n]+)" % word)[0].strip()
                if val:
                    info[key] = val
            story = show.get("description", "")
        try:
            if show.get("rating"):
                info["rating"] = "%.1f" % float(show["rating"])
        except (TypeError, ValueError):
            printExc()
        return (story or "").strip(), info

    def getArticleContent(self, cItem):
        printDBG("CaraTeen.getArticleContent [%s]" % cItem.get("url", ""))
        story, info = self._siteInfo(cItem)
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                title = _metaTitle(cItem["meta_title"])
                meta = getMeta(cItem["meta_type"], title, cItem.get("meta_year") or info.get("year", ""), () if isLatinTitle(title) else LATIN_ONLY)
            except Exception:
                printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("CaraTeen.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "ct_list":
            self.listShows(self.currItem)
        elif category == "ct_planets":
            self.listPlanets(self.currItem)
        elif category == "ct_series":
            self.listSeries(self.currItem)
        elif category == "ct_part":
            self.listPart(self.currItem)
        elif category in ["search", "search_next_page", "ct_search"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern or cItem.get("search_pattern", ""), searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, CaraTeen(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("carateen")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("ct_video", "ct_series", "ct_part")
