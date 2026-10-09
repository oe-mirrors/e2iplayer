# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# 09.10.2026 - StreamDB: "TorrentDB without torrents" - films and series from the Cinemeta catalogue, links from
#   HTTP embed providers (idea from MOHAMED_OS's themoviedb host)
#   - catalogue from Cinemeta (Stremio, no API key): Popular / Featured / New (this year) / genres /
#     years for movies and series, search (movies / series); First page / Jump / Next page
#     (50 titles per page)
#   - series -> seasons (Specials last) -> aired episodes
#   - links: the sources are asked in parallel and resolved right away, so only answering ones are listed;
#     once one source has links the others get 10 more seconds (25 s at most), a source that gave no answer
#     in time (server hangs, e.g. Peachify's x.eat-peach.sbs) is left out for 10 minutes
#     ("<source> - <quality>"): vixsrc, vidrock, vidlink, peachify, videasy (urlparser, by TMDb id - from
#     Cinemeta, else the user's own TMDb key), WebStreamr (HdHub through the user's own AIOStreams / addon
#     manifest url from the host options, by IMDb id; direct MKV, only the pixeldrain files without captcha
#     and R2 urls whose signature is still valid),
#     VidCore / VidUp / VidFast (urlparser, only when the external link decryption is allowed in the settings)
#   - host options: every embed source on / off, the user's own WebStreamr / AIOStreams manifest url (empty: off);
#     VidLink is off by default: its CDN (bcdn.hakunaymatata.com) answers 429 / 428 to the box for every
#     Referer (the links are cached server-side), so it never played - it can still be switched on
#   - watched flag (video:/series:/season: IMDb keys), downloaded flag, favourites, name normalisation,
#     sidecar, INFO via moviemeta (IMDb id) + Cinemeta
###################################################
import calendar
import re
import threading
import time

from Components.config import ConfigYesNo, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigSecret
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsExternalResolveAllowed, IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

# (config key, name, default) in the order the links are listed
# default None: no yes/no option (WebStreamr is on while the user's own manifest url is set)
SOURCES = (("vixsrc", "Vixsrc", True), ("vidrock", "VidRock", True), ("vidlink", "VidLink", False),
           ("peachify", "Peachify", True), ("videasy", "Videasy", True), ("webstreamr", "WebStreamr", None),
           ("vidcore", "VidCore / VidUp / VidFast", False))

###################################################
# Config options for HOST
###################################################
for _key, _name, _default in SOURCES:
    if _default is not None:
        setattr(config.plugins.iptvplayer, "streamdb_" + _key, ConfigYesNo(default=_default))
# the manifest url of the user's own AIOStreams / Stremio addon configuration (it embeds that personal
# configuration, so it is kept like a secret: masked in the lists, never sent out by the web interface)
config.plugins.iptvplayer.streamdb_webstreamr_manifest = ConfigSecret(default="", fixed_size=False)


def GetConfigList():
    optionList = [getConfigListEntry("%s:" % name, getattr(config.plugins.iptvplayer, "streamdb_" + key))
                  for key, name, default in SOURCES if default is not None]
    optionList.append(getConfigListEntry(_("WebStreamr / AIOStreams manifest URL (your own):"), config.plugins.iptvplayer.streamdb_webstreamr_manifest))
    return optionList
###################################################


def gettytul():
    return "StreamDB"


CINEMETA_URL = "https://v3-cinemeta.strem.io/"
IMDB_URL = "https://www.imdb.com/title/%s/"
TMDB_API = "https://api.themoviedb.org/3/"
PER_PAGE = 50
# Cinemeta drops duplicates from a page, so a page before the last one has 48-50 titles
FULL_PAGE = 40
MOVIE_GENRES = ("Action", "Adventure", "Animation", "Biography", "Comedy", "Crime", "Documentary", "Drama", "Family",
                "Fantasy", "History", "Horror", "Mystery", "Romance", "Sci-Fi", "Sport", "Thriller", "War", "Western")
SERIES_GENRES = MOVIE_GENRES + ("Reality-TV", "Talk-Show", "Game-Show")
FIRST_YEAR = 1960

TOTAL_TIMEOUT = 25  # seconds for all sources together
LINKS_GRACE = 10  # once a source has listed links, wait at most this long for the others
SLOW_SKIP_TTL = 600  # a source that gave no answer in time is left out for 10 minutes
LINK_CACHE_TTL = 600  # resolved stream urls carry tokens - list them again after 10 minutes

# (link name, embed url) per source: %(kind)s movie|tv, %(id)s TMDb id, %(se)s "/<season>/<episode>" for an
# episode (the url shapes urlparser expects for these providers)
EMBEDS = {
    "vixsrc": (("Vixsrc", "https://vixsrc.to/%(kind)s/%(id)s%(se)s"),),
    "vidrock": (("VidRock", "https://vidrock.net/%(kind)s/%(id)s%(se)s"),),
    "vidlink": (("VidLink", "https://vidlink.pro/%(kind)s/%(id)s%(se)s"),),
    "peachify": (("Peachify", "https://peachify.top/embed/%(kind)s/%(id)s%(se)s"),),
    "videasy": (("Videasy", "https://player.videasy.to/%(kind)s/%(id)s%(se)s?title=%(title)s&year=%(year)s"),),
    "vidcore": (("VidCore", "https://vidcore.net/%(kind)s/%(id)s%(se)s"), ("VidUp", "https://vidup.to/%(kind)s/%(id)s%(se)s"),
                ("VidFast", "https://vidfast.vc/%(kind)s/%(id)s%(se)s")),
}
# WebStreamr / HdHub (through AIOStreams or the addon itself): of its file hosts only pixeldrain and the signed R2 urls play (hubcloud / hubdrive are pages, pub-*.r2.dev 404)
WEBSTREAMR_HOSTS = ((re.compile(r"^https?://(?:[^/]+\.)?pixeldrain\.[a-z]+/", re.I), "Pixeldrain"),
                    (re.compile(r"^https?://[^/]+\.r2\.cloudflarestorage\.com/", re.I), "R2"))
PIXELDRAIN_ID_RE = re.compile(r"^(https?://[^/]+)/api/file/([A-Za-z0-9]+)")
AMZ_DATE_RE = re.compile(r"[?&]X-Amz-Date=(\d{8}T\d{6}Z)")
AMZ_EXPIRES_RE = re.compile(r"[?&]X-Amz-Expires=(\d+)")
MIN_SIGNATURE_LEFT = 900  # seconds a signed R2 url must still be valid to be listed

IMDB_RE = re.compile(r"^tt\d+$")
# quality of a link name: "res: 1920x1080", "1080p", "4K"
RES_HEIGHT_RE = re.compile(r"res:\s*\d+x(\d+)", re.I)
RES_P_RE = re.compile(r"\b(\d{3,4})p\b", re.I)
RES_4K_RE = re.compile(r"\b(?:4k|uhd)\b", re.I)
# what is left of a resolver's link name besides the quality (server / audio language)
NAME_NOISE_RE = re.compile(r"bitrate:\s*\d+|res:\s*\d+x\d+|\b\d+(?:\.\d+)?\s*fps\b|\b\d{3,4}p\b|\b(?:mp4a|avc1|hvc1|hev1|av01|ac-3|ec-3)[\w.,-]*|\bm3u8\b|\bmp4\b|[\[\]()|]", re.I)


def _text(value):
    return "" if value is None else str(value).strip()


def _toInt(value, default=0):
    try:
        return int(float(_text(value).replace(",", "")))
    except ValueError:
        return default


def _formatSize(size):
    if size >= 1024 ** 3:
        return "%.2f GB" % (size / float(1024 ** 3))
    if size > 0:
        return "%d MB" % max(1, size // 1024 ** 2)
    return ""


def _quality(*texts):
    # ("1080p", 1080) of the first text that tells the height, ("", 0) when none does
    for text in texts:
        text = text or ""
        height = 0
        match = RES_HEIGHT_RE.search(text) or RES_P_RE.search(text)
        if match:
            height = int(match.group(1))
        elif RES_4K_RE.search(text):
            height = 2160
        if height:
            # nearest usual label (854x480 -> 480p, 1920x800 -> 1080p)
            for limit, label in ((1800, 2160), (780, 1080), (600, 720), (420, 480), (300, 360)):
                if height >= limit:
                    return "%dp" % label, label
            return "%dp" % height, height
    return "", 0


def _nameExtra(name, source):
    # server / audio language of a resolver's link name ("[English] bitrate: ... res: ..." -> "English")
    text = re.sub(re.escape(source), " ", name or "", flags=re.I)
    text = NAME_NOISE_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip(" -:,")


def _newWorkerThread(target, args):
    thread = threading.Thread(target=target, args=args)
    thread.daemon = True
    # pCommon's http code asks the current thread whether it was cancelled (asynccall.IsThreadTerminated)
    # and fails every request in a thread without this record - the same one AsyncCall gives its threads
    thread._iptvplayer_ext = {"kill_lock": threading.Lock(), "killable": True, "terminated": False, "iptv_execute": None}
    return thread


def _terminate(threads):
    for thread in threads:
        with thread._iptvplayer_ext["kill_lock"]:
            thread._iptvplayer_ext["terminated"] = True


class StreamDB(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "imdb_id", "tmdb_id", "kind", "season", "episode",
                  "show", "episode_name", "meta_type", "meta_title", "meta_year")
    CONTENT_CATEGORIES = ("sdb_movie", "sdb_series", "sdb_season", "sdb_episode")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "streamdb", "cookie": "streamdb.cookie"})
        self.MAIN_URL = CINEMETA_URL
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/streamdb135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER["Accept"] = "application/json, text/plain, */*"
        self.metaCache = {}
        self.cacheLinks = {}
        self.slowSources = {}  # link name of a source -> time it last gave no answer in time
        self.watchedHelper = IPTVWatchedHelper("streamdb")
        self.wfInitFolderCache()

    ###################################################
    # requests
    ###################################################
    def _getJson(self, url, cm=None, timeout=20):
        # the JSON answer of url (unicode turned into native str), None on failure
        sts, data = (cm or self.cm).getPage(url, {"header": dict(self.HEADER), "timeout": timeout})
        if not sts:
            printDBG("StreamDB: request failed [%s]" % url)
            return None
        try:
            return ensure_str_deep(json_loads(data))
        except Exception:
            printDBG("StreamDB: no JSON from [%s]" % url)
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

    @staticmethod
    def _tmdbKey():
        # the user's own TMDb key of the metadata settings (as libs/moviemeta reads it), "" when none is set
        cp = config.plugins.iptvplayer
        try:
            if cp.meta_tmdb.value:
                return cp.meta_tmdb_apikey.value.strip()
        except Exception:
            printExc()
        return ""

    def _tmdbId(self, cItem, kind, imdbId):
        # TMDb id of the title: from the row (Cinemeta catalogue), its Cinemeta meta, else TMDb /find with the user's key
        tmdbId = _text(cItem.get("tmdb_id")) or _text(self._cinemeta(kind, imdbId).get("moviedb_id"))
        if tmdbId.isdigit():
            return tmdbId
        key = self._tmdbKey()
        if not key:
            return ""
        data = self._getJson("%sfind/%s?external_source=imdb_id&api_key=%s" % (TMDB_API, imdbId, urllib_quote(key, safe="")))
        if isinstance(data, dict):
            for item in data.get("movie_results" if kind == "movie" else "tv_results") or []:
                if _text(item.get("id")).isdigit():
                    return _text(item["id"])
        return ""

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
            if category == "sdb_movie":
                return "video:%s" % imdbId
            if category == "sdb_episode":
                return "video:%s:%d:%d" % (imdbId, _toInt(cItem.get("season")), _toInt(cItem.get("episode")))
            if category == "sdb_series":
                return "series:%s" % imdbId
            if category == "sdb_season":
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
            self.addDir({"name": "category", "category": "sdb_menu", "title": title, "kind": kind, "good_for_fav": True})
        self.listsTab(self.searchItems(), {"name": "category"})

    def listMenu(self, cItem):
        kind = cItem.get("kind", "movie")
        base = {"name": "category", "kind": kind, "good_for_fav": True, "desc": ""}
        for title, catalog, genre in ((_("Popular"), "top", ""), (_("Featured"), "imdbRating", ""),
                                      (_("New"), "year", str(time.localtime().tm_year))):
            self.addDir(dict(base, category="sdb_list", title=title, catalog=catalog, genre=genre,
                             url=self._catalogUrl(kind, catalog, genre)))
        self.addDir(dict(base, category="sdb_genres", title=_("Genres")))
        self.addDir(dict(base, category="sdb_years", title=_("Year")))

    def listGenres(self, cItem):
        kind = cItem.get("kind", "movie")
        for genre in SERIES_GENRES if kind == "series" else MOVIE_GENRES:
            self.addDir({"name": "category", "category": "sdb_list", "title": genre, "kind": kind, "catalog": "top",
                         "genre": genre, "url": self._catalogUrl(kind, "top", genre), "good_for_fav": True})

    def listYears(self, cItem):
        kind = cItem.get("kind", "movie")
        for year in range(time.localtime().tm_year, FIRST_YEAR - 1, -1):
            self.addDir({"name": "category", "category": "sdb_list", "title": str(year), "kind": kind, "catalog": "year",
                         "genre": str(year), "url": self._catalogUrl(kind, "year", str(year)), "good_for_fav": True})

    def _addTitle(self, meta, kind, normalize):
        imdbId = _text(meta.get("imdb_id") or meta.get("id"))
        name = self.cleanHtmlStr(_text(meta.get("name")))
        if not IMDB_RE.match(imdbId) or not name:
            return False
        year = _text(meta.get("releaseInfo") or meta.get("year"))[:4]
        tmdbId = _text(meta.get("moviedb_id"))
        params = {"name": "category", "good_for_fav": True, "url": IMDB_URL % imdbId, "imdb_id": imdbId, "kind": kind,
                  "tmdb_id": tmdbId if tmdbId.isdigit() else "", "icon": _text(meta.get("poster")),
                  "desc": self._desc(meta, kind), "meta_title": name, "meta_year": year}
        if kind == "movie":
            title = "%s (%s)" % (name, year) if normalize and year.isdigit() else name
            self.addVideo(dict(params, category="sdb_movie", title=title, meta_type="movie"))
        else:
            self.addDir(dict(params, category="sdb_series", title=name, show=name, meta_type="tv"))
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
        printDBG("StreamDB.listItems [%s]" % url)
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
        printDBG("StreamDB.listSearchResult [%s] [%s]" % (searchPattern, searchType))
        pattern = searchPattern.strip()
        if not pattern:
            return
        for kind in [searchType] if searchType in ("movie", "series") else ["movie", "series"]:
            self.listItems(dict(cItem, category="sdb_list", kind=kind, catalog="top", search=pattern, page=1))

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
            params = dict((key, cItem[key]) for key in ("imdb_id", "tmdb_id", "kind", "show", "meta_type", "meta_title", "meta_year", "icon") if key in cItem)
            params.update({"name": "category", "category": "sdb_season", "good_for_fav": True, "title": title,
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
            self.addVideo({"name": "category", "category": "sdb_episode", "good_for_fav": True, "title": title,
                           "url": "%s?season=%d&episode=%d" % (IMDB_URL % imdbId, season, episode),
                           "icon": _text(video.get("thumbnail")) or cItem.get("icon", ""),
                           "desc": "[/br]".join(line for line in descLines if line), "imdb_id": imdbId,
                           "tmdb_id": cItem.get("tmdb_id", ""), "kind": "series", "season": season, "episode": episode,
                           "show": show, "episode_name": name, "meta_type": "tv",
                           "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
        if not videos:
            self.addMarker({"title": _("No items found"), "desc": ""})

    ###################################################
    # sources - each runs in its own thread with its own common() / urlparser()
    # ctx: kind ("movie" / "series"), imdb, tmdb, season, episode, title, year
    # a source returns [(name, url, rank)]
    ###################################################
    @staticmethod
    def _srcEmbed(source, tpl, ctx):
        # one embed provider resolved through urlparser
        if not ctx["tmdb"]:
            return []
        fields = {"kind": "movie" if ctx["kind"] == "movie" else "tv", "id": ctx["tmdb"], "se": "",
                  "title": urllib_quote(ctx["title"], safe=""), "year": ctx["year"]}
        if ctx["kind"] != "movie":
            fields["se"] = "/%d/%d" % (ctx["season"], ctx["episode"])
        links = []
        for item in urlparser().getVideoLinkExt(strwithmeta(tpl % fields)) or []:
            url = item.get("url", "")
            if not url:
                continue
            name = _text(item.get("name"))
            label, rank = _quality(name)
            links.append((" - ".join(x for x in (source, label, _nameExtra(name, source)) if x), url, rank))
        return links

    def _webstreamrPlayable(self, cm, url, fileHost):
        # R2: the signed url still valid for a while (the instance caches its answers longer than the
        # 3 hours a signature lasts); pixeldrain: the file not behind its captcha (busy big files)
        if fileHost == "R2":
            match = AMZ_DATE_RE.search(url)
            expires = AMZ_EXPIRES_RE.search(url)
            if not match or not expires:
                return True
            signed = calendar.timegm(time.strptime(match.group(1), "%Y%m%dT%H%M%SZ"))
            return signed + int(expires.group(1)) - time.time() > MIN_SIGNATURE_LEFT
        match = PIXELDRAIN_ID_RE.search(url)
        if not match:
            return True
        data = self._getJson("%s/api/file/%s/info" % (match.group(1), match.group(2)), cm, 10)
        return not isinstance(data, dict) or not _text(data.get("availability"))

    @staticmethod
    def _webstreamrBase():
        # ".../manifest.json" (also stremio://...) of the user's own addon configuration -> ".../", "" when not set
        url = _text(config.plugins.iptvplayer.streamdb_webstreamr_manifest.value)
        if url.startswith("stremio://"):
            url = "https://" + url[len("stremio://"):]
        if not url.startswith(("http://", "https://")):
            return ""
        url = url.split("?")[0]
        if url.endswith("/manifest.json"):
            url = url[:-len("manifest.json")]
        return url if url.endswith("/") else url + "/"

    def _srcWebstreamr(self, cm, ctx):
        base = self._webstreamrBase()
        if not base:
            return []
        videoId = ctx["imdb"] if ctx["kind"] == "movie" else "%s:%d:%d" % (ctx["imdb"], ctx["season"], ctx["episode"])
        data = self._getJson("%sstream/%s/%s.json" % (base, ctx["kind"], videoId), cm)
        links = []
        seen = set()
        for stream in (data.get("streams") or []) if isinstance(data, dict) else []:
            url = _text(stream.get("url"))
            fileHost = ""
            for regex, label in WEBSTREAMR_HOSTS:
                if regex.match(url):
                    fileHost = label
                    break
            if not fileHost:
                continue
            hints = stream.get("behaviorHints") or {}
            fileName = _text(hints.get("filename")) or _text(stream.get("title") or stream.get("description")).split("\n")[0]
            # the same file uploaded twice to the same file host
            if (fileHost, fileName, hints.get("videoSize")) in seen or not self._webstreamrPlayable(cm, url, fileHost):
                continue
            seen.add((fileHost, fileName, hints.get("videoSize")))
            label, rank = _quality(fileName, _text(hints.get("bingeGroup")).replace("|", " "))
            referer = _text(((hints.get("proxyHeaders") or {}).get("request") or {}).get("Referer"))
            meta = {"User-Agent": self.HEADER["User-Agent"]}
            if referer:
                meta["Referer"] = referer
            name = " - ".join(x for x in ("WebStreamr", label, _formatSize(_toInt(hints.get("videoSize"))), fileHost, fileName) if x)
            links.append((name, strwithmeta(url, meta), rank))
        return links

    def _collectLinks(self, ctx):
        # all enabled sources in parallel -> [(name, url)] in source order, best quality first within a source
        # a source that gave no answer in time (its server hangs - curl gives up only after 10 s without data per
        # request) is left out for SLOW_SKIP_TTL, so it does not cost the whole TOTAL_TIMEOUT on every title
        external = IsExternalResolveAllowed()
        printDBG("StreamDB: external link decryption allowed[%s] VidCore option[%s]" % (external, config.plugins.iptvplayer.streamdb_vidcore.value))
        now = time.time()
        for label in [label for label, since in self.slowSources.items() if now - since >= SLOW_SKIP_TTL]:
            del self.slowSources[label]
        candidates = []  # (source key, source name, embed (name, url template) or None)
        for key, name, default in SOURCES:
            if default is None:
                enabled = bool(self._webstreamrBase())
            else:
                enabled = getattr(config.plugins.iptvplayer, "streamdb_" + key).value and (key != "vidcore" or external)
            if enabled:
                candidates.extend((key, name, embed) for embed in EMBEDS.get(key) or (None,))
        # every enabled source slow: ask them all again rather than list nothing
        if all((embed[0] if embed else name) in self.slowSources for key, name, embed in candidates):
            self.slowSources.clear()
        sources = []
        jobs = []  # (job number, source key, embed (name, url template) or None)
        for key, name, embed in candidates:
            label = embed[0] if embed else name
            if label in self.slowSources:
                printDBG("StreamDB: %s skipped (no answer in time %d s ago)" % (label, now - self.slowSources[label]))
                continue
            if (key, name) not in sources:
                sources.append((key, name))
            jobs.append((len(jobs), key, embed))
        results = {}
        lock = threading.Lock()

        def worker(job, key, embed):
            found = []
            try:
                if embed is None:
                    found = self._srcWebstreamr(common(), ctx)
                else:
                    found = self._srcEmbed(embed[0], embed[1], ctx)
            except Exception:
                printExc()
            with lock:
                results[job] = found

        threads = [_newWorkerThread(worker, job) for job in jobs]
        for thread in threads:
            thread.start()
        # wait in short steps; when the user cancels the links (the calling AsyncCall thread is terminated) or the
        # time is up, mark the source threads terminated so pCommon aborts their requests. Once a source has listed
        # links, the others get LINKS_GRACE more seconds (not the rest of TOTAL_TIMEOUT)
        parent = getattr(threading.current_thread(), "_iptvplayer_ext", None)
        start = time.time()
        deadline = start + TOTAL_TIMEOUT
        graceSet = False
        while True:
            alive = [thread for thread in threads if thread.is_alive()]
            if not alive or time.time() >= deadline:
                break
            if parent is not None and parent["terminated"]:
                _terminate(threads)
                return []
            if not graceSet:
                with lock:
                    hasLinks = any(results.values())
                if hasLinks:
                    graceSet = True
                    deadline = min(deadline, time.time() + LINKS_GRACE)
            alive[0].join(0.25)
        _terminate([thread for thread in threads if thread.is_alive()])
        with lock:
            results = dict(results)
        printDBG("StreamDB: %d of %d sources answered in %.1f s" % (len(results), len(jobs), time.time() - start))

        links = []
        for key, name in sources:
            found = []
            for job, jobKey, embed in jobs:
                if jobKey != key:
                    continue
                if job in results:
                    found.extend(results[job])
                else:
                    label = embed[0] if embed else name
                    printDBG("StreamDB: %s gave no answer in time - left out for %d min" % (label, SLOW_SKIP_TTL // 60))
                    self.slowSources[label] = time.time()
            printDBG("StreamDB: %s -> %d links" % (name, len(found)))
            links.extend(sorted(found, key=lambda link: link[2], reverse=True))
        return links

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("StreamDB.getLinksForVideo [%s]" % url)
        cached = self.cacheLinks.get(url)
        if cached and time.time() - cached[0] < LINK_CACHE_TTL:
            return cached[1]
        imdbId = cItem.get("imdb_id", "")
        if not IMDB_RE.match(imdbId):
            return []
        isEpisode = cItem.get("category") == "sdb_episode"
        kind = "series" if isEpisode else "movie"
        ctx = {"kind": kind, "imdb": imdbId, "tmdb": self._tmdbId(cItem, kind, imdbId), "season": _toInt(cItem.get("season")),
               "episode": _toInt(cItem.get("episode")), "title": cItem.get("meta_title", ""), "year": cItem.get("meta_year", "")}
        links = self._collectLinks(ctx)
        if not links:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        urltab = []
        names = {}
        for name, link, _rank in links:
            names[name] = names.get(name, 0) + 1
            if names[name] > 1:
                name = "%s #%d" % (name, names[name])
            urltab.append({"name": name, "url": link, "need_resolve": 0})
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))
        self.cacheLinks[url] = (time.time(), urltab)
        return urltab

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("StreamDB.getArticleContent [%s]" % cItem.get("url", ""))
        category = cItem.get("category", "")
        imdbId = cItem.get("imdb_id", "")
        kind = "movie" if category == "sdb_movie" else "series"
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
        if category == "sdb_season":
            info["episodes"] = str(len(self._videos(site, _toInt(cItem.get("season")))))
        elif category == "sdb_episode":
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
        printDBG("StreamDB.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "sdb_menu":
            self.listMenu(self.currItem)
        elif category == "sdb_genres":
            self.listGenres(self.currItem)
        elif category == "sdb_years":
            self.listYears(self.currItem)
        elif category == "sdb_list":
            self.listItems(self.currItem)
        elif category == "sdb_series":
            self.listSeasons(self.currItem)
        elif category == "sdb_season":
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
        CHostBase.__init__(self, StreamDB(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("streamdb")

    def getSearchTypes(self):
        return [(_("Movies"), "movie"), (_("Series"), "series")]

    def withArticleContent(self, cItem):
        return cItem.get("category") in StreamDB.CONTENT_CATEGORIES
