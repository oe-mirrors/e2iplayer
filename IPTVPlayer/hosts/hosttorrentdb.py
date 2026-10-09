# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - TorrentDB: one host for films and series from several torrent sources
#   - catalogue from Cinemeta (Stremio, no API key): Popular / Featured / New (this year) / genres /
#     years for movies and series, search (movies / series); First page / Jump / Next page
#     (50 titles per page)
#   - series -> seasons (Specials last) -> aired episodes
#   - links: the sources (Torrentio, MediaFusion, PeerFlix, Popcorn Time API, YTS, EZTV, The Pirate Bay
#     API) are asked in parallel by IMDb id (The Pirate Bay episodes by "Show SxxExx"), merged by
#     info hash, best resolution / most seeders first; played through TorrServer (urlparser
#     parserTORRSERVER), the file of the episode is picked from a season pack
#   - host options: every source on / off, maximum torrent size; MediaFusion only with the user's own addon
#     manifest url (empty: off)
#   - watched flag (video:/series:/season: IMDb keys), downloaded flag, favourites, name normalisation,
#     sidecar, INFO via moviemeta (IMDb id) + Cinemeta
###################################################
import re
import threading
import time
from base64 import b32decode
from binascii import hexlify

from Components.config import ConfigSelection, ConfigYesNo, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigSecret
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems, getUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str, ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

# (config key, name) in the order the links of equal quality are listed
SOURCES = (("torrentio", "Torrentio"), ("mediafusion", "MediaFusion"), ("peerflix", "PeerFlix"),
           ("popcorn", "Popcorn Time"), ("yts", "YTS"), ("eztv", "EZTV"), ("apibay", "The Pirate Bay"))

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.torrentdb_max_size = ConfigSelection(default="0", choices=[("0", _("unlimited"))] + [(str(gb), "%d GB" % gb) for gb in (2, 4, 8, 16, 32)])
config.plugins.iptvplayer.torrentdb_torrentio = ConfigYesNo(default=True)
# fix 091026: MediaFusion only through the user's own addon configuration - its manifest url embeds that personal
# configuration, so it is kept like a secret (masked in the lists, never sent out by the web interface); empty = off
config.plugins.iptvplayer.torrentdb_mediafusion_manifest = ConfigSecret(default="", fixed_size=False)
config.plugins.iptvplayer.torrentdb_peerflix = ConfigYesNo(default=True)
config.plugins.iptvplayer.torrentdb_popcorn = ConfigYesNo(default=True)
config.plugins.iptvplayer.torrentdb_yts = ConfigYesNo(default=True)
config.plugins.iptvplayer.torrentdb_eztv = ConfigYesNo(default=True)
config.plugins.iptvplayer.torrentdb_apibay = ConfigYesNo(default=True)


def GetConfigList():
    optionList = [getConfigListEntry(_("Maximum torrent size:"), config.plugins.iptvplayer.torrentdb_max_size)]
    for key, name in SOURCES:
        if key == "mediafusion":
            optionList.append(getConfigListEntry(_("MediaFusion manifest URL (your own):"), config.plugins.iptvplayer.torrentdb_mediafusion_manifest))
        else:
            optionList.append(getConfigListEntry("%s:" % name, getattr(config.plugins.iptvplayer, "torrentdb_" + key)))
    return optionList
###################################################


def gettytul():
    return "TorrentDB"


CINEMETA_URL = "https://v3-cinemeta.strem.io/"
IMDB_URL = "https://www.imdb.com/title/%s/"
PER_PAGE = 50
# Cinemeta drops duplicates from a page, so a page before the last one has 48-50 titles
FULL_PAGE = 40
MOVIE_GENRES = ("Action", "Adventure", "Animation", "Biography", "Comedy", "Crime", "Documentary", "Drama", "Family",
                "Fantasy", "History", "Horror", "Mystery", "Romance", "Sci-Fi", "Sport", "Thriller", "War", "Western")
SERIES_GENRES = MOVIE_GENRES + ("Reality-TV", "Talk-Show", "Game-Show")
FIRST_YEAR = 1960

SOURCE_TIMEOUT = 15  # seconds per request of a source
TOTAL_TIMEOUT = 25  # seconds for all sources together
MAX_PER_SOURCE = 50  # best torrents taken from one source
EZTV_MAX_PAGES = 10  # 100 torrents per page, newest first
TORRENTIO_URL = "https://torrentio.strem.fun/"
PEERFLIX_URL = "https://peerflix.mov/"
POPCORN_URL = "https://yrkde.link/"
# the YTS API moves its base url (see hostyts)
YTS_API_URLS = ("https://movies-api.accel.li/", "https://yts.gg/")
EZTV_URL = "https://eztv.yt/"
APIBAY_URL = "https://apibay.org/"
TRACKERS = (
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.dler.org:6969/announce",
)

IMDB_RE = re.compile(r"^tt\d+$")
HASH_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[A-Za-z2-7]{32})$")
MAGNET_HASH_RE = re.compile(r"btih:([0-9a-fA-F]{40}|[A-Za-z2-7]{32})(?![0-9A-Za-z])")
SIZE_RE = re.compile(r"(\d{1,9}(?:[.,]\d{1,9}){0,4})\s*([KMGT])i?B\b", re.I)
# Stremio stream texts put the seeders after a "bust in silhouette" (U+1F464); compared as native
# str (UTF-8 bytes on py2) like the texts, which ensure_str_deep() converts
SEED_MARK = ensure_str(u"\U0001F464")
SEEDS_RE = re.compile(re.escape(SEED_MARK) + r"\s*(\d+)")
# (pattern, label, rank) - the first that matches wins
RESOLUTIONS = (
    (re.compile(r"2160p?|\b4k\b|\buhd\b", re.I), "2160p", 4),
    (re.compile(r"\b1080[pi]\b", re.I), "1080p", 3),
    (re.compile(r"\b720p\b", re.I), "720p", 2),
    (re.compile(r"\b(?:576p|480p|360p|dvdrip)\b", re.I), "480p", 1),
)
SXXEXX_RE = re.compile(r"\bS\d{1,2}\s?E\d{1,3}\b|\b\d{1,2}x\d{2,3}\b", re.I)
NOT_ALNUM_RE = re.compile(r"[^a-z0-9]+")
SOURCE_RE = re.compile(r"\b(Remux|BluRay|Blu-Ray|BDRip|BRRip|WEB-DL|WEBRip|WEB|HDTV|HDRip|DVDRip|DVD|HDCAM|CAM|TS|TC)\b", re.I)
CODEC_RE = re.compile(r"\b(x265|x264|HEVC|H\.?265|H\.?264|AVC|AV1|XviD|VP9)\b", re.I)


def _text(value):
    return "" if value is None else str(value).strip()


def _toInt(value, default=0):
    try:
        return int(float(_text(value).replace(",", "")))
    except ValueError:
        return default


def _normHash(value):
    # info hash as 40 lower-case hex digits (a base32 hash converted), "" when it is none
    value = _text(value)
    if not HASH_RE.match(value):
        return ""
    if len(value) == 32:
        try:
            return ensure_str(hexlify(b32decode(value.upper()))).lower()
        except Exception:
            return ""
    return value.lower()


def _sizeBytes(text):
    # "14.47 GB" / "651.55 MB" in a text -> bytes, 0 when there is none
    match = SIZE_RE.search(text or "")
    if not match:
        return 0
    number = match.group(1)
    number = number.replace(",", "") if "." in number else number.replace(",", ".")
    try:
        return int(float(number) * 1024 ** ("KMGT".index(match.group(2).upper()) + 1))
    except ValueError:
        return 0


def _formatSize(size):
    if size >= 1024 ** 3:
        return "%.2f GB" % (size / float(1024 ** 3))
    if size > 0:
        return "%d MB" % max(1, size // 1024 ** 2)
    return ""


def _resolution(*texts):
    # (label, rank) of the first text that tells the resolution
    for text in texts:
        for regex, label, rank in RESOLUTIONS:
            if text and regex.search(text):
                return label, rank
    return "", 0


def _sameShow(release, show):
    # add 091026: the show name before SxxExx of a release matches the show (EZTV tags e.g. "Breaking Brad" with
    # the IMDb id of Breaking Bad, a Pirate Bay text search finds "The Bad Guys Breaking In"); true when unsure
    match = SXXEXX_RE.search(release or "")
    if not match:
        return True
    name, wanted = [re.sub(r"^the", "", NOT_ALNUM_RE.sub("", text.lower())) for text in (release[:match.start()], show or "")]
    return not name or not wanted or name.startswith(wanted) or wanted.startswith(name)


def _qualityLabel(torrent):
    # "2160p WEB-DL x265": resolution, source and codec once each, like the other torrent hosts' link names
    parts = [torrent["res"]]
    for regex in (SOURCE_RE, CODEC_RE):
        for text in (torrent["title"], torrent["file"]):
            match = regex.search(text)
            if match:
                parts.append(match.group(1))
                break
    return " ".join(part for part in parts if part)


def _torrent(source, infoHash, title, size=0, seeds=0, resolution=None, magnet="", trackers=(), fileHint="", peers=None):
    # peers None: the source does not tell them
    title = _text(title)
    if resolution is None:
        resolution = _resolution(title, fileHint)
    return {"sources": [source], "hash": infoHash, "title": title, "size": size, "seeds": seeds, "peers": peers,
            "res": resolution[0], "rank": resolution[1], "magnet": magnet, "trackers": list(trackers), "file": _text(fileHint)}


def _sortKey(torrent):
    return (torrent["rank"], torrent["seeds"])


def _newWorkerThread(target, args):
    thread = threading.Thread(target=target, args=args)
    thread.daemon = True
    # pCommon's http code asks the current thread whether it was cancelled (asynccall.IsThreadTerminated)
    # and fails every request in a thread without this record - the same one AsyncCall gives its threads
    thread._iptvplayer_ext = {"kill_lock": threading.Lock(), "killable": True, "terminated": False, "iptv_execute": None}
    return thread


class TorrentDB(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "imdb_id", "kind", "season", "episode",
                  "show", "episode_name", "meta_type", "meta_title", "meta_year")
    CONTENT_CATEGORIES = ("tdb_movie", "tdb_series", "tdb_season", "tdb_episode")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "torrentdb", "cookie": "torrentdb.cookie"})
        self.MAIN_URL = CINEMETA_URL
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/torrentdb135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER["Accept"] = "application/json, text/plain, */*"
        self.metaCache = {}
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper("torrentdb")
        self.wfInitFolderCache()

    ###################################################
    # requests
    ###################################################
    def _getJson(self, url, cm=None, timeout=20):
        # the JSON answer of url (unicode turned into native str), None on failure
        sts, data = (cm or self.cm).getPage(url, {"header": dict(self.HEADER), "timeout": timeout})
        if not sts:
            printDBG("TorrentDB: request failed [%s]" % url)
            return None
        try:
            return ensure_str_deep(json_loads(data))
        except Exception:
            printDBG("TorrentDB: no JSON from [%s]" % url)
            return None

    def _cinemeta(self, kind, imdbId):
        # Cinemeta "meta" of a movie / series (the series with its "videos"), {} when unknown
        key = "%s:%s" % (kind, imdbId)
        if key not in self.metaCache:
            data = self._getJson("%smeta/%s/%s.json" % (CINEMETA_URL, kind, imdbId))
            if data is None:
                return {}
            self.metaCache[key] = (data.get("meta") or {}) if isinstance(data, dict) else {}
        return self.metaCache[key]

    @staticmethod
    def _catalogUrl(kind, catalog, genre="", search=""):
        extras = []
        if genre:
            extras.append("genre=" + urllib_quote(genre, safe=""))
        if search:
            extras.append("search=" + urllib_quote(search, safe=""))
        return "%scatalog/%s/%s%s.json" % (CINEMETA_URL, kind, catalog, ("/" + "&".join(extras)) if extras else "")

    ###################################################
    # helpers
    ###################################################
    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in self.CONTENT_CATEGORIES:
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            imdbId = cItem.get("imdb_id", "")
            if not IMDB_RE.match(imdbId):
                return ""
            category = cItem.get("category", "")
            if category == "tdb_movie":
                return "video:%s" % imdbId
            if category == "tdb_episode":
                return "video:%s:%d:%d" % (imdbId, _toInt(cItem.get("season")), _toInt(cItem.get("episode")))
            if category == "tdb_series":
                return "series:%s" % imdbId
            if category == "tdb_season":
                return "season:%s:%d" % (imdbId, _toInt(cItem.get("season")))
        except Exception:
            printExc()
        return ""

    @staticmethod
    def _aired(video):
        released = _text(video.get("released") or video.get("firstAired"))
        return not released or released <= time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

    def _videos(self, meta, season=None):
        # aired episodes of a series meta (of one season)
        videos = []
        for video in meta.get("videos") or []:
            if not isinstance(video, dict) or not self._aired(video):
                continue
            if season is not None and _toInt(video.get("season"), -1) != season:
                continue
            videos.append(video)
        return videos

    @staticmethod
    def _siteInfo(meta, kind):
        info = {}
        year = _text(meta.get("releaseInfo") or meta.get("year"))
        if year:
            info["year"] = year
        if meta.get("imdbRating"):
            info["imdb_rating"] = "%s/10" % meta["imdbRating"]
        if kind == "movie" and meta.get("runtime"):
            info["duration"] = _text(meta["runtime"])
        genres = meta.get("genres") or meta.get("genre") or []
        if genres:
            info["genres"] = ", ".join(_text(g) for g in genres[:5])
        if meta.get("cast"):
            info["cast"] = ", ".join(_text(c) for c in meta["cast"][:5])
        if meta.get("director"):
            info["directors"] = ", ".join(_text(d) for d in meta["director"][:3])
        if meta.get("country"):
            info["country"] = _text(meta["country"])
        if meta.get("awards"):
            info["awards"] = _text(meta["awards"])
        return info

    def _desc(self, meta, kind):
        info = self._siteInfo(meta, kind)
        fields = ((_("Year"), info.get("year")), (_("Rating"), info.get("imdb_rating")),
                  (_("Runtime"), info.get("duration")), (_("Genres"), info.get("genres")))
        lines = [" | ".join("%s: %s" % (label, value) for label, value in fields if value)]
        lines.append(self.cleanHtmlStr(_text(meta.get("description"))))
        return "[/br]".join(line for line in lines if line)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        for kind, title in (("movie", _("Movies")), ("series", _("Series"))):
            self.addDir({"name": "category", "category": "tdb_menu", "title": title, "kind": kind, "good_for_fav": True})
        self.listsTab(self.searchItems(), {"name": "category"})

    def listMenu(self, cItem):
        kind = cItem.get("kind", "movie")
        base = {"name": "category", "kind": kind, "good_for_fav": True, "desc": ""}
        for title, catalog, genre in ((_("Popular"), "top", ""), (_("Featured"), "imdbRating", ""),
                                      (_("New"), "year", str(time.localtime().tm_year))):
            self.addDir(dict(base, category="tdb_list", title=title, catalog=catalog, genre=genre,
                             url=self._catalogUrl(kind, catalog, genre)))
        self.addDir(dict(base, category="tdb_genres", title=_("Genres")))
        self.addDir(dict(base, category="tdb_years", title=_("Year")))

    def listGenres(self, cItem):
        kind = cItem.get("kind", "movie")
        for genre in SERIES_GENRES if kind == "series" else MOVIE_GENRES:
            self.addDir({"name": "category", "category": "tdb_list", "title": genre, "kind": kind, "catalog": "top",
                         "genre": genre, "url": self._catalogUrl(kind, "top", genre), "good_for_fav": True})

    def listYears(self, cItem):
        kind = cItem.get("kind", "movie")
        for year in range(time.localtime().tm_year, FIRST_YEAR - 1, -1):
            self.addDir({"name": "category", "category": "tdb_list", "title": str(year), "kind": kind, "catalog": "year",
                         "genre": str(year), "url": self._catalogUrl(kind, "year", str(year)), "good_for_fav": True})

    def _addTitle(self, meta, kind, normalize):
        imdbId = _text(meta.get("imdb_id") or meta.get("id"))
        name = self.cleanHtmlStr(_text(meta.get("name")))
        if not IMDB_RE.match(imdbId) or not name:
            return False
        year = _text(meta.get("releaseInfo") or meta.get("year"))[:4]
        params = {"name": "category", "good_for_fav": True, "url": IMDB_URL % imdbId, "imdb_id": imdbId, "kind": kind,
                  "icon": _text(meta.get("poster")), "desc": self._desc(meta, kind), "meta_title": name, "meta_year": year}
        if kind == "movie":
            title = "%s (%s)" % (name, year) if normalize and year.isdigit() else name
            self.addVideo(dict(params, category="tdb_movie", title=title, meta_type="movie"))
        else:
            self.addDir(dict(params, category="tdb_series", title=name, show=name, meta_type="tv"))
        return True

    def listItems(self, cItem):
        kind = cItem.get("kind", "movie")
        catalog = cItem.get("catalog", "top")
        genre = cItem.get("genre", "")
        search = cItem.get("search", "")
        page = max(1, _toInt(cItem.get("page", 1), 1))
        url = self._catalogUrl(kind, catalog, genre, search)
        if page > 1:
            url = url[:-len(".json")] + ("&" if (genre or search) else "/") + "skip=%d.json" % ((page - 1) * PER_PAGE)
        printDBG("TorrentDB.listItems [%s]" % url)
        data = self._getJson(url)
        if not isinstance(data, dict):
            SetIPTVPlayerLastHostError(_("Failed to connect to host."))
            return
        normalize = IsMediaNamingNormalized()
        count = 0
        for meta in data.get("metas") or []:
            if isinstance(meta, dict) and self._addTitle(meta, kind, normalize):
                count += 1
        if search:
            return  # Cinemeta answers a search with one page only
        if not count and page == 1:
            self.addMarker({"title": _("No items found"), "desc": ""})
            return
        # last page unknown: a full page has a next one
        listItem = stripPagerKeys(dict(cItem))
        listItem["url"] = self._catalogUrl(kind, catalog, genre)
        addPagingItems(self, listItem, page, count >= FULL_PAGE, 0, listItem["url"] + "?page={page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TorrentDB.listSearchResult [%s] [%s]" % (searchPattern, searchType))
        pattern = searchPattern.strip()
        if not pattern:
            return
        for kind in [searchType] if searchType in ("movie", "series") else ["movie", "series"]:
            self.listItems(dict(cItem, category="tdb_list", kind=kind, catalog="top", search=pattern, page=1))

    def listSeasons(self, cItem):
        imdbId = cItem.get("imdb_id", "")
        meta = self._cinemeta("series", imdbId)
        episodes = {}
        for video in self._videos(meta):
            season = _toInt(video.get("season"), -1)
            if season >= 0:
                episodes[season] = episodes.get(season, 0) + 1
        # Specials (season 0) last
        for season in sorted(episodes, key=lambda s: (s == 0, s)):
            title = _("Specials") if season == 0 else _("Season %d") % season
            params = dict((key, cItem[key]) for key in ("imdb_id", "kind", "show", "meta_type", "meta_title", "meta_year", "icon") if key in cItem)
            params.update({"name": "category", "category": "tdb_season", "good_for_fav": True, "title": title,
                           "url": cItem.get("url", ""), "season": season, "desc": "%s: %d" % (_("Episodes"), episodes[season])})
            self.addDir(params)
        if not episodes:
            self.addMarker({"title": _("No items found"), "desc": ""})

    def listEpisodes(self, cItem):
        imdbId = cItem.get("imdb_id", "")
        season = _toInt(cItem.get("season"))
        show = cItem.get("show") or cItem.get("meta_title", "")
        normalize = IsMediaNamingNormalized()
        meta = self._cinemeta("series", imdbId)
        videos = sorted(self._videos(meta, season), key=lambda v: _toInt(v.get("episode") or v.get("number")))
        for video in videos:
            episode = _toInt(video.get("episode") or video.get("number"))
            sxe = formatSxxExx(season, episode)
            name = self.cleanHtmlStr(_text(video.get("name") or video.get("title")))
            title = "%s - %s" % (show, sxe) if normalize and show else ("%s - %s" % (sxe, name) if name else sxe)
            descLines = [name]
            released = _text(video.get("released") or video.get("firstAired"))[:10]
            if released:
                descLines.append("%s %s" % (_("Released:"), released))
            descLines.append(self.cleanHtmlStr(_text(video.get("overview") or video.get("description"))))
            self.addVideo({"name": "category", "category": "tdb_episode", "good_for_fav": True, "title": title,
                           "url": "%s?season=%d&episode=%d" % (IMDB_URL % imdbId, season, episode),
                           "icon": _text(video.get("thumbnail")) or cItem.get("icon", ""),
                           "desc": "[/br]".join(line for line in descLines if line), "imdb_id": imdbId, "kind": "series",
                           "season": season, "episode": episode, "show": show, "episode_name": name,
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
        if not videos:
            self.addMarker({"title": _("No items found"), "desc": ""})

    ###################################################
    # torrent sources - each runs in its own thread with its own common()
    # ctx: kind ("movie" / "series"), imdb, season, episode, show
    ###################################################
    def _srcStremio(self, cm, ctx, base, source):
        # Stremio stream addons (Torrentio, PeerFlix, MediaFusion): stream/<type>/<imdb>[:S:E].json
        videoId = ctx["imdb"] if ctx["kind"] == "movie" else "%s:%d:%d" % (ctx["imdb"], ctx["season"], ctx["episode"])
        data = self._getJson("%sstream/%s/%s.json" % (base, ctx["kind"], videoId), cm, SOURCE_TIMEOUT)
        torrents = []
        for stream in (data.get("streams") or []) if isinstance(data, dict) else []:
            infoHash = _normHash(stream.get("infoHash"))
            if not infoHash:
                continue
            lines = [line.strip() for line in _text(stream.get("title") or stream.get("description")).split("\n") if line.strip()]
            hints = stream.get("behaviorHints") or {}
            fileHint = _text(hints.get("filename"))
            release = lines[0] if lines else fileHint
            if source == "MediaFusion" and fileHint:
                release = fileHint  # its first line holds only the quality tags
            elif not fileHint and len(lines) > 2:
                fileHint = lines[1]  # the file of a pack: release / file / stats
            size = _toInt(hints.get("videoSize"))
            if not size:
                for line in reversed(lines[1:]):
                    size = _sizeBytes(line)
                    if size:
                        break
            seeds = SEEDS_RE.search("\n".join(lines))
            resolution = _resolution(_text(stream.get("name")).replace("\n", " "), release, fileHint)
            trackers = [s[8:] for s in stream.get("sources") or [] if _text(s).startswith("tracker:")]
            torrents.append(_torrent(source, infoHash, release, size, _toInt(seeds.group(1)) if seeds else 0, resolution,
                                     trackers=trackers, fileHint=fileHint))
        return torrents

    def _srcTorrentio(self, cm, ctx):
        return self._srcStremio(cm, ctx, TORRENTIO_URL, "Torrentio")

    def _srcPeerflix(self, cm, ctx):
        return self._srcStremio(cm, ctx, PEERFLIX_URL, "PeerFlix")

    @staticmethod
    def _mediafusionBase():
        # ".../manifest.json" (also stremio://...) or the base url of the user's own addon configuration -> ".../",
        # "" when not set
        url = _text(config.plugins.iptvplayer.torrentdb_mediafusion_manifest.value)
        if url.startswith("stremio://"):
            url = "https://" + url[len("stremio://"):]
        if not url.startswith(("http://", "https://")):
            return ""
        url = url.split("?")[0]
        if url.endswith("/manifest.json"):
            url = url[:-len("manifest.json")]
        return url if url.endswith("/") else url + "/"

    def _srcMediafusion(self, cm, ctx):
        base = self._mediafusionBase()
        return self._srcStremio(cm, ctx, base, "MediaFusion") if base else []

    def _srcPopcorn(self, cm, ctx):
        # Popcorn Time API: movie/<imdb> {torrents: {lang: {quality: {...}}}}, show/<imdb> {episodes: [...]}
        torrents = []
        entries = []
        data = self._getJson("%s%s/%s" % (POPCORN_URL, "movie" if ctx["kind"] == "movie" else "show", ctx["imdb"]), cm, SOURCE_TIMEOUT)
        if not isinstance(data, dict):
            return torrents
        if ctx["kind"] == "movie":
            for qualities in (data.get("torrents") or {}).values():
                entries.extend((qualities or {}).items())
        else:
            for episode in data.get("episodes") or []:
                if _toInt(episode.get("season"), -1) == ctx["season"] and _toInt(episode.get("episode"), -1) == ctx["episode"]:
                    entries.extend((episode.get("torrents") or {}).items())
        for quality, item in entries:
            if not isinstance(item, dict):
                continue
            magnet = _text(item.get("url")).replace("&amp;", "&")
            match = MAGNET_HASH_RE.search(magnet)
            infoHash = _normHash(match.group(1)) if match else ""
            if not infoHash:
                continue
            title = _text(item.get("title"))
            fileHint = _text(item.get("file"))
            resolution = _resolution(title, fileHint, _text(item.get("quality")), _text(quality))
            torrents.append(_torrent("Popcorn Time", infoHash, title, _toInt(item.get("size")) or _sizeBytes(_text(item.get("filesize"))),
                                     _toInt(item.get("seed") or item.get("seeds")), resolution, magnet, fileHint=fileHint,
                                     peers=_toInt(item.get("peer") or item.get("peers"))))
        return torrents

    def _srcYts(self, cm, ctx):
        if ctx["kind"] != "movie":
            return []
        movies = []
        for base in YTS_API_URLS:
            data = self._getJson("%sapi/v2/list_movies.json?query_term=%s" % (base, ctx["imdb"]), cm, SOURCE_TIMEOUT)
            if isinstance(data, dict) and data.get("status") == "ok" and isinstance(data.get("data"), dict):
                movies = data["data"].get("movies") or []
                break
        torrents = []
        for movie in movies:
            if movie.get("imdb_code") != ctx["imdb"]:
                continue
            for item in movie.get("torrents") or []:
                infoHash = _normHash(item.get("hash"))
                if not infoHash:
                    continue
                title = " ".join(_text(x) for x in (movie.get("title_long"), item.get("quality"), item.get("type"),
                                                    item.get("video_codec"), "[YTS]") if x)
                torrents.append(_torrent("YTS", infoHash, title, _toInt(item.get("size_bytes")), _toInt(item.get("seeds")),
                                         _resolution(_text(item.get("quality"))), peers=_toInt(item.get("peers"))))
        return torrents

    def _srcEztv(self, cm, ctx):
        if ctx["kind"] != "series":
            return []
        torrents = []
        imdbNum = ctx["imdb"][2:]
        for page in range(1, EZTV_MAX_PAGES + 1):
            data = self._getJson("%sapi/get-torrents?imdb_id=%s&limit=100&page=%d" % (EZTV_URL, imdbNum, page), cm, SOURCE_TIMEOUT)
            if not isinstance(data, dict):
                break
            items = data.get("torrents") or []
            for item in items:
                if _toInt(item.get("season"), -1) != ctx["season"] or _toInt(item.get("episode"), -1) != ctx["episode"]:
                    continue
                infoHash = _normHash(item.get("hash"))
                release = _text(item.get("filename") or item.get("title"))
                if infoHash and _sameShow(release, ctx["show"]):
                    torrents.append(_torrent("EZTV", infoHash, release, _toInt(item.get("size_bytes")),
                                             _toInt(item.get("seeds")), magnet=_text(item.get("magnet_url")), peers=_toInt(item.get("peers"))))
            if len(items) < 100 or page * 100 >= _toInt(data.get("torrents_count")):
                break
        return torrents

    def _srcApibay(self, cm, ctx):
        # The Pirate Bay API: movies by IMDb id, episodes by "Show SxxExx" in the video categories (2xx)
        if ctx["kind"] == "movie":
            query = ctx["imdb"]
            episodeRe = None
        else:
            show = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", ctx["show"])).strip()
            if not show:
                return []
            query = "%s %s&cat=200" % (urllib_quote_plus(show), formatSxxExx(ctx["season"], ctx["episode"]))
            episodeRe = re.compile(r"\bS0*%d\s?E0*%d(?!\d)" % (ctx["season"], ctx["episode"]), re.I)
        data = self._getJson("%sq.php?q=%s" % (APIBAY_URL, query.replace(" ", "+")), cm, SOURCE_TIMEOUT)
        torrents = []
        for item in data if isinstance(data, list) else []:
            infoHash = _normHash(item.get("info_hash"))
            name = _text(item.get("name"))
            if not infoHash or infoHash == "0" * 40 or not _text(item.get("category")).startswith("2"):
                continue
            if episodeRe and (not episodeRe.search(name) or item.get("imdb") not in ("", None, ctx["imdb"]) or not _sameShow(name, ctx["show"])):
                continue
            torrents.append(_torrent("The Pirate Bay", infoHash, name, _toInt(item.get("size")), _toInt(item.get("seeders")),
                                     peers=_toInt(item.get("leechers"))))
        return torrents

    def _collectTorrents(self, ctx):
        # all enabled sources in parallel -> merged torrents (one per info hash), best first
        funcs = {"torrentio": self._srcTorrentio, "mediafusion": self._srcMediafusion, "peerflix": self._srcPeerflix,
                 "popcorn": self._srcPopcorn, "yts": self._srcYts, "eztv": self._srcEztv, "apibay": self._srcApibay}
        jobs = [(name, funcs[key]) for key, name in SOURCES
                if (self._mediafusionBase() if key == "mediafusion" else getattr(config.plugins.iptvplayer, "torrentdb_" + key).value)]
        results = {}
        lock = threading.Lock()

        def worker(name, func):
            found = []
            try:
                found = func(common(), ctx)
            except Exception:
                printExc()
            with lock:
                results[name] = found

        threads = [_newWorkerThread(worker, job) for job in jobs]
        for thread in threads:
            thread.start()
        # add 091026: wait in short steps; when the user cancels the links (the calling AsyncCall thread is
        # terminated), mark the source threads terminated too so pCommon aborts their requests
        parent = getattr(threading.current_thread(), "_iptvplayer_ext", None)
        deadline = time.time() + TOTAL_TIMEOUT
        for thread in threads:
            while thread.is_alive() and time.time() < deadline:
                if parent is not None and parent["terminated"]:
                    for worker in threads:
                        with worker._iptvplayer_ext["kill_lock"]:
                            worker._iptvplayer_ext["terminated"] = True
                    return []
                thread.join(0.25)
        with lock:
            results = dict(results)

        maxSize = _toInt(config.plugins.iptvplayer.torrentdb_max_size.value) * 1024 ** 3
        merged = {}
        for name, _func in jobs:
            if name not in results:
                printDBG("TorrentDB: %s gave no answer in time" % name)
                continue
            # fix 091026: size limit before the per-source cut, else 50 big 2160p releases hid the small ones
            found = [t for t in results[name] if not maxSize or t["size"] <= maxSize]
            found = sorted(found, key=_sortKey, reverse=True)[:MAX_PER_SOURCE]
            printDBG("TorrentDB: %s -> %d torrents" % (name, len(found)))
            for torrent in found:
                known = merged.get(torrent["hash"])
                if known is None:
                    merged[torrent["hash"]] = torrent
                    continue
                if name not in known["sources"]:
                    known["sources"].append(name)
                known["seeds"] = max(known["seeds"], torrent["seeds"])
                if torrent["peers"] is not None:
                    known["peers"] = max(known["peers"] or 0, torrent["peers"])
                for key in ("size", "file", "magnet"):
                    if not known[key]:
                        known[key] = torrent[key]
                if not known["rank"] and torrent["rank"]:
                    known["res"], known["rank"] = torrent["res"], torrent["rank"]
                known["trackers"].extend(t for t in torrent["trackers"] if t not in known["trackers"])
        # fix 091026: a torrent of unknown size can get its size from a later source - check the limit again
        return sorted((t for t in merged.values() if not maxSize or t["size"] <= maxSize), key=_sortKey, reverse=True)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("TorrentDB.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        imdbId = cItem.get("imdb_id", "")
        if not IMDB_RE.match(imdbId):
            return []
        isEpisode = cItem.get("category") == "tdb_episode"
        ctx = {"kind": "series" if isEpisode else "movie", "imdb": imdbId, "season": _toInt(cItem.get("season")),
               "episode": _toInt(cItem.get("episode")), "show": cItem.get("show") or cItem.get("meta_title", "")}
        torrents = self._collectTorrents(ctx)
        if not torrents:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        title = cItem.get("title", "")
        icon = cItem.get("icon", "")
        if not icon.startswith("http"):
            icon = ""
        sxe = "%d:%d" % (ctx["season"], ctx["episode"]) if isEpisode else ""
        urltab = []
        names = set()
        for torrent in torrents:
            magnet = torrent["magnet"]
            if not magnet:
                trackers = torrent["trackers"] or list(TRACKERS)
                magnet = "magnet:?xt=urn:btih:%s&dn=%s&tr=%s" % (torrent["hash"], urllib_quote_plus(torrent["title"] or title),
                                                                  "&tr=".join(urllib_quote_plus(t) for t in trackers))
            # fix 091026: link name in the style of the other torrent hosts plus source and release:
            # "[Torrentio+YTS] 1080p WEB x264 - 2.10 GB - S:123 P:4 - <release>"
            health = "S:%d" % torrent["seeds"] + (" P:%d" % torrent["peers"] if torrent["peers"] is not None else "")
            label = ("[%s] %s" % ("+".join(torrent["sources"]), _qualityLabel(torrent))).strip()
            name = " - ".join(x for x in (label, _formatSize(torrent["size"]), health, torrent["title"]) if x)
            if name in names:
                name += " - #%s" % torrent["hash"][:8]  # the same release under another info hash
            names.add(name)
            meta = {"title": title, "icon": icon, "torrentdb_file": torrent["file"], "torrentdb_sxe": sxe}
            urltab.append({"name": name, "url": strwithmeta(magnet, meta), "need_resolve": 1})
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))
        self.cacheLinks[url] = urltab
        return urltab

    @staticmethod
    def _pickFile(links, meta):
        # the file of the episode (or the one the source named) out of a pack, all files when none matches
        if len(links) < 2:
            return links
        fileHint = _text(meta.get("torrentdb_file")).replace("\\", "/").split("/")[-1].lower()
        picked = []
        if fileHint:
            picked = [link for link in links if _text(link.get("name")).lower().startswith(fileHint)]
        sxe = _text(meta.get("torrentdb_sxe"))
        if not picked and sxe:
            season, episode = sxe.split(":")
            regex = re.compile(r"(?:\bS0*%s\s?E0*%s|\b%sx0*%s)(?!\d)" % (season, episode, season, episode), re.I)
            picked = [link for link in links if regex.search(_text(link.get("name")))]
        return picked or links

    def getVideoLinks(self, videoUrl):
        printDBG("TorrentDB.getVideoLinks [%s]" % videoUrl)
        if videoUrl.startswith("magnet:?") or self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            links = self._pickFile(self.up.getVideoLinkExt(videoUrl), getUrlMeta(videoUrl))
            return decorateResolvedLinkItems(links, sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("TorrentDB.getArticleContent [%s]" % cItem.get("url", ""))
        category = cItem.get("category", "")
        imdbId = cItem.get("imdb_id", "")
        kind = "movie" if category == "tdb_movie" else "series"
        site = self._cinemeta(kind, imdbId) if IMDB_RE.match(imdbId) else {}
        info = self._siteInfo(site, kind)
        meta = {}
        try:
            meta = getMetaByImdbId("movie" if kind == "movie" else "tv", imdbId)
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        story = self.cleanHtmlStr(_text(site.get("description")))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or _text(site.get("poster")) or cItem.get("icon", "")
        title = cItem.get("title", "")
        if category == "tdb_season":
            info["episodes"] = str(len(self._videos(site, _toInt(cItem.get("season")))))
        elif category == "tdb_episode":
            season, episode = _toInt(cItem.get("season")), _toInt(cItem.get("episode"))
            for video in self._videos(site, season):
                if _toInt(video.get("episode") or video.get("number")) == episode:
                    overview = self.cleanHtmlStr(_text(video.get("overview") or video.get("description")))
                    if overview:
                        text = "%s[/br][/br]%s" % (overview, text) if text else overview
                    released = _text(video.get("released") or video.get("firstAired"))[:10]
                    if released:
                        info["released"] = released
                    break
            if cItem.get("episode_name") and cItem["episode_name"] not in title:
                title = "%s - %s" % (title, cItem["episode_name"])
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("TorrentDB.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "tdb_menu":
            self.listMenu(self.currItem)
        elif category == "tdb_genres":
            self.listGenres(self.currItem)
        elif category == "tdb_years":
            self.listYears(self.currItem)
        elif category == "tdb_list":
            self.listItems(self.currItem)
        elif category == "tdb_series":
            self.listSeasons(self.currItem)
        elif category == "tdb_season":
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
        CHostBase.__init__(self, TorrentDB(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("torrentdb")

    def getSearchTypes(self):
        return [(_("Movies"), "movie"), (_("Series"), "series")]

    def withArticleContent(self, cItem):
        return cItem.get("category") in TorrentDB.CONTENT_CATEGORIES
