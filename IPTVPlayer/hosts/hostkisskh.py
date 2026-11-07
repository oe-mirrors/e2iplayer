# -*- coding: utf-8 -*-
LAST_MODIFIED = "07.11.2026"
# KissKH (Asian dramas, movies, anime, Hollywood with English subtitles): the site's JSON API (DramaList/List with
# type / country / order filters, Search, Drama/<id>, Episode/<id>.png with the "kkey" signature the site's player
# computes: AES-128-CBC over its parameter string), HLS per episode, subtitles decrypted line by line on demand
# (dashmpd.localTextUrl)
import base64
import hashlib
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs import pyaes
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, MergeDicts, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

try:
    from Plugins.Extensions.IPTVPlayer.libs import dashmpd
except Exception:  # the local text server needs Python 3
    dashmpd = None

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.kisskh_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.kisskh_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.kisskh_proxy))
    if config.plugins.iptvplayer.kisskh_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.kisskh_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://kisskh.co/"


# the site's player signs its episode / subtitle requests: constants of its build (kisskh 2.8.10)
APP_VER = "2.8.10"
PLATFORM_VER = "4830201"
APP_NAME = "kisskh"
VIDEO_GUID = "62f176f3bb1b5b8e70e39932ad34a0c7"
SUB_GUID = "VgV52sWhwvBSf8BsM3BRY9weWiiCbtGp"
KKEY_SALT = "mg3c3b04ba"
KKEY_KEY = (0x4f6bdaa3, 0x9e2f8cb0, 0x7f5e722d, 0x9edef314)
KKEY_IV = (0x01504af3, 0x56e619cf, 0x2e42bba6, 0x8c3f70f9)
# the cue lines of the subtitle files (.txt1 / .txt) are AES-CBC base64 with one of two key / iv pairs
SUB_KEYS = ((b"AmSmZVcH93UQUezi", (1382367819, 1465333859, 1902406224, 1164854838)),
            (b"8056483646328763", (909653298, 909193779, 925905208, 892483379)))
PAGE_SIZE = 40
# DramaList/List filters (site values)
TYPES = ((1, "TVSeries"), (2, "Movie"), (3, "Anime"), (4, "Hollywood"))
COUNTRIES = ((1, "China"), (2, "Korea"), (3, "Japan"), (5, "Thailand"), (7, "Taiwan"), (8, "Philippines"), (6, "Hollywood"))
# "Squid Game Season 3" -> ("Squid Game", 3); "Ash (2026)" -> ("Ash", "2026")
SEASON_RE = re.compile(r"^(.*?)\s+Season\s+(\d+)\s*$", re.I)
YEAR_RE = re.compile(r"^(.*?)\s*\(((?:19|20)\d\d)\)\s*$")
TITLE_URI_RE = re.compile(r"[^A-Za-z0-9]+")
TMDB_IMG_RE = re.compile(r"^https?://(?:media\.themoviedb\.org|image\.tmdb\.org)/t/p/[^/]+/")


def _words(ws):
    return b"".join(bytes(bytearray([(w >> 24) & 255, (w >> 16) & 255, (w >> 8) & 255, w & 255])) for w in ws)


def _jsHash(text):
    # the player's checksum: h = (h << 5) - h + c with only the shift operand truncated to int32
    h = 0
    for ch in text:
        t = h & 0xffffffff
        t = t - 0x100000000 if t & 0x80000000 else t
        s = (t << 5) & 0xffffffff
        s = s - 0x100000000 if s & 0x80000000 else s
        h = s - h + ord(ch)
    return h


def kkey(episodeId, guid):
    parts = ["", str(episodeId), "", KKEY_SALT, APP_VER, guid, PLATFORM_VER, APP_NAME, APP_NAME, APP_NAME, APP_NAME, APP_NAME, APP_NAME, "00", ""]
    parts.insert(1, str(_jsHash("|".join(parts))))
    data = "|".join(parts)
    pad = 16 - len(data) % 16
    data += chr(pad) * pad
    encrypter = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(_words(KKEY_KEY), iv=_words(KKEY_IV)), padding=pyaes.PADDING_NONE)
    raw = encrypter.feed(data.encode("latin-1")) + encrypter.feed()
    return "".join("%02X" % (b if isinstance(b, int) else ord(b)) for b in bytearray(raw))


def decryptSubtitle(text):
    # the cue text lines of a KissKH subtitle file -> plain SRT text ("" when nothing could be decrypted)
    out, decrypted = [], 0
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            out.append(block.strip())
            continue
        head, cues = lines[:2], []
        for line in lines[2:]:
            line = line.strip()
            plain = ""
            for key, iv in SUB_KEYS:
                try:
                    decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, iv=_words(iv)))
                    plain = (decrypter.feed(base64.b64decode(line)) + decrypter.feed()).decode("utf-8")
                    break
                except Exception:
                    plain = ""
            if plain:
                decrypted += 1
                cues.append(plain)
            elif line:
                cues.append(line)
        out.append("\n".join(head + cues))
    return "\n\n".join(out) if decrypted else ""


class KissKH(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_year", "s_season", "s_episode", "meta_type", "drama_id", "episode_id", "ep_count")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "kisskh", "cookie": "kisskh.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/kisskh135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("kisskh")
        self.wfInitFolderCache()
        # set here (no request): links / INFO of a favourite are asked for before any list was opened
        self.selectDomain()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.kisskh_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def selectDomain(self):
        domain = config.plugins.iptvplayer.kisskh_alt_domain.value.strip()
        self.MAIN_URL = domain.rstrip("/") + "/" if self.cm.isValidUrl(domain) else gettytul()

    def _api(self, path):
        # -> parsed JSON of api/<path> or None
        params = dict(self.defaultParams)
        params["header"] = MergeDicts(self.HEADER, {"Referer": self.MAIN_URL, "Accept": "application/json, text/plain, */*"})
        sts, data = self.getPage(self.MAIN_URL + "api/" + path, params)
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
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _splitTitle(title):
        # -> (show, season, year)
        title = (title or "").strip()
        year = ""
        m = YEAR_RE.match(title)
        if m:
            title, year = m.group(1).strip(), m.group(2)
        m = SEASON_RE.match(title)
        if m:
            return m.group(1).strip(), int(m.group(2)), year
        return title, 0, year

    @staticmethod
    def _icon(url):
        # media.themoviedb.org answers with a redirect to image.tmdb.org (JPEG); the poster size is enough
        return TMDB_IMG_RE.sub(r"https://image.tmdb.org/t/p/w500/", url or "")

    def _siteUrl(self, item):
        # the page the site shows for a title (used as the identity of favourites / watched flags)
        return "%sDrama/%s?id=%s" % (self.MAIN_URL, TITLE_URI_RE.sub("-", item.get("title", "") or "").strip("-"), item.get("id", ""))

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
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
            if cItem.get("type", "") == "video" and cItem.get("episode_id"):
                return "video:%s" % cItem["episode_id"]
            if cItem.get("category", "") == "list_episodes" and cItem.get("drama_id"):
                return "series:%s" % cItem["drama_id"]
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _addDrama(self, cItem, item):
        title = (item.get("title") or "").strip()
        dramaId = item.get("id")
        if not title or not dramaId:
            return
        show, season, year = self._splitTitle(title)
        count = item.get("episodesCount") or 0
        desc = []
        if count:
            desc.append("%s: %s" % (_("Episodes"), count))
        if item.get("label"):
            desc.append(str(item["label"]))
        params = stripPagerKeys(dict(cItem))
        params.update({"name": "category", "good_for_fav": True, "category": "list_episodes", "title": title, "url": self._siteUrl(item),
                       "icon": self._icon(item.get("thumbnail")), "desc": " | ".join(desc), "drama_id": dramaId, "ep_count": count,
                       "s_title": show, "s_season": season, "s_year": year, "meta_type": "tv" if (count and count > 1) or season else "movie"})
        self.addDir(params)

    def listItems(self, cItem):
        printDBG("KissKH.listItems [%s]" % cItem.get("api", ""))
        page = self._page(cItem)
        path = cItem.get("api", "")
        if "{page}" in path:
            data = self._api(path.format(page=page))
            items = data.get("data", []) if isinstance(data, dict) else []
            total = data.get("totalCount", 0) if isinstance(data, dict) else 0
            lastPage = max(1, (int(total or 0) + PAGE_SIZE - 1) // PAGE_SIZE)
        else:
            items = self._api(path) or []
            lastPage = 1
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict):
                self._addDrama(cItem, item)
        if not self.currList:
            self.addMarker({"title": _("No items found"), "desc": ""})
            return
        if lastPage > 1:
            addPagingItems(self, dict(cItem, category="list_items"), page, page < lastPage, lastPage)

    def listFilter(self, cItem, values, key):
        for value, name in values:
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "good_for_fav": True, "category": "list_items", "title": name,
                           "api": "DramaList/List?page={page}&type=%s&sub=0&country=%s&status=0&order=1&pageSize=%d" % (value if key == "type" else 0, value if key == "country" else 0, PAGE_SIZE)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("KissKH.listEpisodes [%s]" % cItem.get("drama_id", ""))
        dramaId = cItem.get("drama_id") or self.cm.ph.getSearchGroups(cItem.get("url", ""), r"[?&]id=(\d+)")[0]
        drama = self._api("DramaList/Drama/%s?isq=false" % dramaId)
        if not isinstance(drama, dict):
            return
        episodes = [e for e in drama.get("episodes") or [] if isinstance(e, dict) and e.get("id")]
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        title = (drama.get("title") or cItem.get("title", "")).strip()
        show, season, year = self._splitTitle(title)
        plot = self.cleanHtmlStr(drama.get("description") or "")
        normalize = IsMediaNamingNormalized()
        isMovie = len(episodes) == 1 and (drama.get("type") or "") in ("Movie", "Hollywood") and not season
        for ep in sorted(episodes, key=self._episodeNumber):
            number = self._episodeNumber(ep)
            # 6.0 -> 6; a special such as 6.5 stays as it is
            number = int(number) if number == int(number) else number
            if isMovie:
                epTitle = "%s (%s)" % (show, year) if (normalize and year) else title
            elif normalize:
                epTitle = "%s - %s" % (show, formatSxxExx(season or 1, int(number)) if isinstance(number, int) else "%s %s" % (_("Episode"), number))
            else:
                epTitle = "%s - %s %s" % (title, _("Episode"), number)
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "ks_video", "good_for_fav": True, "title": epTitle, "url": "%s#ep=%s" % (self._siteUrl(drama), ep["id"]),
                           "icon": self._icon(drama.get("thumbnail")) or cItem.get("icon", ""), "desc": plot, "drama_id": dramaId, "episode_id": ep["id"], "s_title": show,
                           "s_season": season or (0 if isMovie else 1), "s_episode": number, "s_year": year, "meta_type": "movie" if isMovie else "tv"})
            self.addVideo(params)

    @staticmethod
    def _episodeNumber(ep):
        try:
            return float(ep.get("number") or 0)
        except (TypeError, ValueError):
            return 0.0

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KissKH.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "page": 1, "api": "DramaList/Search?q=%s&type=0" % urllib_quote_plus(searchPattern.strip())})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _subtitleTracks(self, episodeId):
        subs = self._api("Sub/%s?kkey=%s" % (episodeId, kkey(episodeId, SUB_GUID)))
        tracks = []
        for sub in subs if isinstance(subs, list) else []:
            src, label, lang = sub.get("src", ""), sub.get("label", "") or sub.get("land", ""), sub.get("land", "") or ""
            if not self.cm.isValidUrl(src):
                continue
            if src.split("?")[0].endswith((".txt1", ".txt")):
                if dashmpd is None:
                    # encrypted cues and no local text server (Python 2): the track would be unreadable
                    continue
                # decrypted when the player asks for the track, served by the local text server
                headers = {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL, "Origin": self.MAIN_URL.rstrip("/")}
                url = dashmpd.localTextUrl("kisskh/%s/%s" % (episodeId, hashlib.md5(src.encode("utf-8")).hexdigest()[:12]), self._subtitleLoader(src, headers), "srt")
                if not url:
                    continue
            else:
                url = src
            tracks.append({"title": label, "url": url, "lang": lang[:2], "format": "srt"})
        return tracks

    @staticmethod
    def _subtitleLoader(src, headers):
        def load():
            resp = dashmpd.openUrl(src, headers, timeout=20)
            try:
                text = resp.read().decode("utf-8", "replace")
            finally:
                resp.close()
            return decryptSubtitle(text) or (text if "-->" in text and not re.search(r"^[A-Za-z0-9+/=]{16,}$", text, re.M) else "")
        return load

    def getLinksForVideo(self, cItem):
        episodeId = cItem.get("episode_id") or self.cm.ph.getSearchGroups(cItem.get("url", ""), r"#ep=(\d+)")[0]
        printDBG("KissKH.getLinksForVideo [%s]" % episodeId)
        if not episodeId:
            return []
        data = self._api("DramaList/Episode/%s.png?err=false&ts=&time=&kkey=%s" % (episodeId, kkey(episodeId, VIDEO_GUID)))
        if not isinstance(data, dict):
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        urltab = []
        meta = {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL}
        tracks = self._subtitleTracks(episodeId)
        for key, name in (("Video", "HLS"), ("Video_tmp", "HLS 2"), ("ThirdParty", "Third party")):
            url = data.get(key) or ""
            if not self.cm.isValidUrl(url):
                continue
            if key == "ThirdParty":
                if self.up.checkHostSupport(url) == 1:
                    urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
                continue
            linkMeta = dict(meta)
            if ".m3u8" in url:
                linkMeta["iptv_proto"] = "m3u8"
            if tracks:
                linkMeta["external_sub_tracks"] = tracks
            urltab.append({"name": name, "url": strwithmeta(url, linkMeta), "need_resolve": 0})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", "tv"), cItem.get("s_title", "") or cItem.get("title", ""), cItem.get("s_year", ""), skip=(), maxYearDiff=1)
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", ""), metaQuery=metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("KissKH.getVideoLinks [%s]" % videoUrl)
        return self.up.getVideoLinkExt(videoUrl) if self.cm.isValidUrl(videoUrl) else []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("KissKH.getArticleContent [%s]" % cItem.get("drama_id", ""))
        info, plot = {}, cItem.get("desc", "")
        dramaId = cItem.get("drama_id") or self.cm.ph.getSearchGroups(cItem.get("url", ""), r"[?&]id=(\d+)")[0]
        drama = self._api("DramaList/Drama/%s?isq=false" % dramaId) if dramaId else None
        icon = cItem.get("icon", "")
        if isinstance(drama, dict):
            plot = self.cleanHtmlStr(drama.get("description") or "") or plot
            for key, field in (("country", "country"), ("status", "status"), ("type", "type"), ("episodes", "episodesCount")):
                if drama.get(field):
                    info[key] = str(drama[field])
            released = (drama.get("releaseDate") or "")[:10]
            if released:
                info["released"] = released
            icon = icon or self._icon(drama.get("thumbnail"))
        show = cItem.get("s_title") or self._splitTitle(cItem.get("title", ""))[0]
        year = cItem.get("s_year", "") or self.cm.ph.getSearchGroups(info.get("released", ""), r"((?:19|20)\d\d)")[0]
        meta = {}
        try:
            meta = getMeta(cItem.get("meta_type", "tv"), show, year, maxYearDiff=1)
        except Exception:
            printExc()
        for key, value in meta.get("info", {}).items():
            info.setdefault(key, value)
        metaPlot = meta.get("plot", "")
        text = plot
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = icon or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("KissKH.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            listAll = "DramaList/List?page={page}&type=0&sub=0&country=0&status=0&order=%d&pageSize=%d"
            menu = [{"category": "list_items", "title": _("Latest"), "api": listAll % (1, PAGE_SIZE)},
                    {"category": "list_items", "title": _("Popular"), "api": listAll % (2, PAGE_SIZE)},
                    {"category": "list_items", "title": _("Top rated"), "api": "DramaList/TopRating?ispc=true"},
                    {"category": "list_items", "title": _("Most viewed"), "api": "DramaList/MostView?ispc=true"},
                    {"category": "list_items", "title": _("Upcoming"), "api": "DramaList/Upcoming?ispc=true"},
                    {"category": "list_types", "title": _("Type")},
                    {"category": "list_countries", "title": _("Country")}]
            self.listsTab(menu + self.searchItems(), {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_types":
            self.listFilter(self.currItem, TYPES, "type")
        elif category == "list_countries":
            self.listFilter(self.currItem, COUNTRIES, "country")
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, KissKH(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("kisskh")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_episodes",)
