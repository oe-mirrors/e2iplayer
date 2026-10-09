# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY popking (odem2014), angel_heart (Mohamed Elsafty)
# 08.10.2026 - EZTV (TV series torrents) through the site's JSON API (was hosttorrenteztv)
#   - the html pages sit behind a Cloudflare challenge, api/get-torrents does not: newest torrents and
#     the torrents of one show by IMDb id; the first domain that answers is kept, an alternative domain
#     from the settings is tried first
#   - Latest (100 torrents per page, First page / Jump / Next page); Popular / genres / search of
#     series from Cinemeta (Stremio, no API key) -> seasons -> episodes from the torrents EZTV has
#     (daily shows: years -> air dates); torrents of other shows filed under the IMDb id are dropped
#   - links: every release of the episode (resolution, size, seeders / peers), best resolution first,
#     played through TorrServer (urlparser parserTORRSERVER)
#   - watched flag (video:/series:/season: IMDb keys), downloaded flag, favourites, name normalisation,
#     sidecar, INFO via moviemeta (IMDb id) + Cinemeta
###################################################
import re
import time

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.eztv_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.eztv_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.eztv_proxy))
    if config.plugins.iptvplayer.eztv_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.eztv_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://eztvx.to/"


# mirrors of the same site (eztv.re redirects to eztvx.to)
API_DOMAINS = ("https://eztvx.to/", "https://eztv.yt/", "https://eztv.wf/", "https://eztv.tf/")
CINEMETA_URL = "https://v3-cinemeta.strem.io/"
IMDB_URL = "https://www.imdb.com/title/%s/"
PER_PAGE = 100  # the API's maximum
SHOW_MAX_PAGES = 15  # torrents of one show, newest first
CATALOG_PER_PAGE = 50
# Cinemeta drops duplicates from a page, so a page before the last one has 48-50 titles
CATALOG_FULL_PAGE = 40
SERIES_GENRES = ("Action", "Adventure", "Animation", "Biography", "Comedy", "Crime", "Documentary", "Drama", "Family",
                 "Fantasy", "Game-Show", "History", "Horror", "Mystery", "Reality-TV", "Romance", "Sci-Fi", "Sport",
                 "Talk-Show", "Thriller", "War", "Western")
TRACKERS = (
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.dler.org:6969/announce",
    "udp://open.demonii.com:1337/announce",
)
IMDB_RE = re.compile(r"^tt\d+$")
HASH_RE = re.compile(r"^[0-9a-fA-F]{40}$")
# (pattern, label, rank) - the first that matches wins
RESOLUTIONS = (
    (re.compile(r"2160p?|\b4k\b|\buhd\b", re.I), "2160p", 4),
    (re.compile(r"\b1080[pi]\b", re.I), "1080p", 3),
    (re.compile(r"\b720p\b", re.I), "720p", 2),
    (re.compile(r"\b(?:576p|480p|360p)\b", re.I), "480p", 1),
)
EZTV_TAG_RE = re.compile(r"(?:\[eztv[^\]]*\]|\bEZTV)$", re.I)
# the show name of a release ends before "S01E02" / "S01" / "S13E11E12" (fix 091026: double episodes)
SHOW_END_RE = re.compile(r"[\s._-]S(\d{1,3})(?:E(\d{1,3}))?(?:-?E\d{1,3})*(?=[\s._-]|$)", re.I)
# add 091026: ... or before the air date of a daily show ("Watch What Happens Live 2026 10 07")
DATE_RE = re.compile(r"[\s._-]((?:19|20)\d{2})[\s._-](\d{2})[\s._-](\d{2})(?=[\s._-]|$)")
# release tags after the guest name of a daily show
TAIL_TAG_RE = re.compile(r"(?:\b(?:REPACK|PROPER|INTERNAL|EXTENDED|AMZN|ATVP|DSNP|HMAX|NF|PCOK|PMTP|iP)\b)|(?:-\w+$)")
# add 091026: _sameShow (as in hosttorrentdb.py)
SXXEXX_RE = re.compile(r"\bS\d{1,2}\s?E\d{1,3}\b|\b\d{1,2}x\d{2,3}\b", re.I)
NOT_ALNUM_RE = re.compile(r"[^a-z0-9]+")
SOURCE_RE = re.compile(r"\b(Remux|BluRay|Blu-Ray|BDRip|BRRip|WEB-DL|WEBRip|WEB|HDTV|HDRip|DVDRip|DVD)\b", re.I)
# fix 091026: EZTV titles write "H.264" as "H 264"
CODEC_RE = re.compile(r"\b(x265|x264|HEVC|H[.\s]?265|H[.\s]?264|AVC|AV1|XviD|VP9)\b", re.I)


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


def _resolution(text):
    for regex, label, rank in RESOLUTIONS:
        if text and regex.search(text):
            return label, rank
    return "", 0


def _release(torrent):
    # "Taskmaster S22E06 720p HEVC x265-MeGusta" (the title without the site tag)
    return EZTV_TAG_RE.sub("", _text(torrent.get("title")) or _text(torrent.get("filename"))).strip()


def _showEnd(release):
    # the SxxExx / air date match that ends the show name of a release, None when there is none
    return SHOW_END_RE.search(release) or DATE_RE.search(release)


def _qualityLabel(release):
    # "1080p WEB x264" from a release name (fix 091026: only after the show name - "Web Therapy" is no source)
    end = _showEnd(release)
    tags = release[end.end():] if end else release
    parts = [_resolution(tags)[0]]
    for regex in (SOURCE_RE, CODEC_RE):
        match = regex.search(tags)
        if match:
            parts.append(re.sub(r"(?i)^H[.\s](?=26)", "H", match.group(1)))
    return " ".join(part for part in parts if part)


def _airDate(torrent):
    # "2026-10-07" of a daily-show release (EZTV files them under season 0), "" for SxxExx releases
    if _toInt(torrent.get("season")):
        return ""
    match = DATE_RE.search(_release(torrent))
    return "%s-%s-%s" % match.groups() if match else ""


def _airDateName(release):
    # "Sebastian Stan" of "The Daily Show 2026 10 07 Sebastian Stan 1080p WEB h264-EDITH"
    match = DATE_RE.search(release)
    tail = release[match.end():] if match else ""
    cut = len(tail)
    for regex in [r[0] for r in RESOLUTIONS] + [SOURCE_RE, CODEC_RE, TAIL_TAG_RE]:
        found = regex.search(tail)
        if found:
            cut = min(cut, found.start())
    return re.sub(r"[._]+", " ", tail[:cut]).strip(" -")


def _sameShow(release, show):
    # add 091026: the show name before SxxExx of a release matches the show (EZTV tags e.g. "Breaking Brad" with
    # the IMDb id of Breaking Bad); true when unsure
    match = SXXEXX_RE.search(release or "")
    if not match:
        return True
    name, wanted = [re.sub(r"^the", "", NOT_ALNUM_RE.sub("", text.lower())) for text in (release[:match.start()], show or "")]
    return not name or not wanted or name.startswith(wanted) or wanted.startswith(name)


def _rowTitle(release):
    # "Show - S01E02 - 1080p WEB x264" / "Show - 2026-10-07 - 720p WEB h264" (daily show) like the other torrent
    # hosts; the raw release name when the show is unknown
    end = _showEnd(release)
    show = re.sub(r"[._]+", " ", release[:end.start()]).strip(" -") if end else ""
    if not show:
        return release
    if end.re is DATE_RE:
        title = "%s - %s-%s-%s" % (show, end.group(1), end.group(2), end.group(3))
    else:
        title = "%s - %s" % (show, formatSxxExx(end.group(1), end.group(2)))
    quality = _qualityLabel(release)
    return "%s - %s" % (title, quality) if quality else title


def _sortKey(torrent):
    return (_resolution(_release(torrent))[1], _toInt(torrent.get("seeds")))


def _imdbId(torrent):
    imdb = _text(torrent.get("imdb_id")).lstrip("t")
    return "tt%s" % imdb if imdb.isdigit() and int(imdb) else ""


class EZTV(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "imdb_id", "season", "episode", "show",
                  "info_hash", "magnet", "release", "meta_type", "meta_title", "meta_year", "air_year", "air_date")
    CONTENT_CATEGORIES = ("eztv_series", "eztv_season", "eztv_episode", "eztv_torrent")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "eztv", "cookie": "eztv.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/eztv135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER["Accept"] = "application/json, text/plain, */*"
        self.apiBase = None
        self.showCache = {}
        self.metaCache = {}
        self.torrentCache = {}
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper("eztv")
        self.wfInitFolderCache()

    ###################################################
    # requests
    ###################################################
    def _getJson(self, url, proxy=False):
        params = {"header": dict(self.HEADER)}
        if proxy:
            proxyUrl = GetAlternativeProxyUrl(config.plugins.iptvplayer.eztv_proxy.value)
            if proxyUrl:
                params["http_proxy"] = proxyUrl
        sts, data = self.cm.getPage(url, params)
        if not sts:
            printDBG("EZTV: request failed [%s]" % url)
            return None
        try:
            return ensure_str_deep(json_loads(data))
        except Exception:
            printDBG("EZTV: no JSON from [%s]" % url)
            return None

    def _apiBases(self):
        bases = list(API_DOMAINS)
        alt = config.plugins.iptvplayer.eztv_alt_domain.value.strip()
        if self.cm.isValidUrl(alt):
            bases.insert(0, alt.rstrip("/") + "/")
        if self.apiBase in bases:
            bases.remove(self.apiBase)
            bases.insert(0, self.apiBase)
        return bases

    def _getTorrents(self, query):
        # api/get-torrents?<query> from the first base url that answers, None when none does
        for base in self._apiBases():
            data = self._getJson("%sapi/get-torrents?%s" % (base, query), True)
            if isinstance(data, dict) and isinstance(data.get("torrents", []), list) and "torrents_count" in data:
                self.apiBase = base
                return data
        return None

    def _showTorrents(self, imdbId):
        # all torrents of a show (newest first, at most SHOW_MAX_PAGES pages), cached
        if imdbId in self.showCache:
            return self.showCache[imdbId]
        torrents = []
        for page in range(1, SHOW_MAX_PAGES + 1):
            data = self._getTorrents("imdb_id=%s&limit=%d&page=%d" % (imdbId[2:], PER_PAGE, page))
            if data is None:
                if page == 1:
                    return None
                break
            items = [t for t in data.get("torrents") or [] if isinstance(t, dict) and HASH_RE.match(_text(t.get("hash")))]
            torrents.extend(items)
            if len(data.get("torrents") or []) < PER_PAGE or page * PER_PAGE >= _toInt(data.get("torrents_count")):
                break
        for torrent in torrents:
            self.torrentCache[_text(torrent["hash"]).lower()] = torrent
        self.showCache[imdbId] = torrents
        return torrents

    def _cinemeta(self, imdbId):
        # Cinemeta "meta" of a series (with its "videos"), {} when unknown
        if imdbId not in self.metaCache:
            data = self._getJson("%smeta/series/%s.json" % (CINEMETA_URL, imdbId))
            if data is None:
                return {}
            self.metaCache[imdbId] = (data.get("meta") or {}) if isinstance(data, dict) else {}
        return self.metaCache[imdbId]

    @staticmethod
    def _catalogUrl(catalog, genre="", search=""):
        extras = []
        if genre:
            extras.append("genre=" + urllib_quote(genre, safe=""))
        if search:
            extras.append("search=" + urllib_quote(search, safe=""))
        return "%scatalog/series/%s%s.json" % (CINEMETA_URL, catalog, ("/" + "&".join(extras)) if extras else "")

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
            category = cItem.get("category", "")
            if category == "eztv_torrent":
                infoHash = cItem.get("info_hash", "")
                return "video:%s" % infoHash if HASH_RE.match(infoHash) else ""
            imdbId = cItem.get("imdb_id", "")
            if not IMDB_RE.match(imdbId):
                return ""
            if category == "eztv_episode":
                if cItem.get("air_date"):
                    return "video:%s:%s" % (imdbId, cItem["air_date"])
                return "video:%s:%d:%d" % (imdbId, _toInt(cItem.get("season")), _toInt(cItem.get("episode")))
            if category == "eztv_series":
                return "series:%s" % imdbId
            if category == "eztv_season":
                if cItem.get("air_year"):
                    return "season:%s:y%s" % (imdbId, cItem["air_year"])
                return "season:%s:%d" % (imdbId, _toInt(cItem.get("season")))
        except Exception:
            printExc()
        return ""

    @staticmethod
    def _seriesInfo(meta):
        info = {}
        year = _text(meta.get("releaseInfo") or meta.get("year"))
        if year:
            info["year"] = year
        if meta.get("imdbRating"):
            info["imdb_rating"] = "%s/10" % meta["imdbRating"]
        genres = meta.get("genres") or meta.get("genre") or []
        if genres:
            info["genres"] = ", ".join(_text(g) for g in genres[:5])
        if meta.get("cast"):
            info["cast"] = ", ".join(_text(c) for c in meta["cast"][:5])
        if meta.get("country"):
            info["country"] = _text(meta["country"])
        return info

    def _seriesDesc(self, meta):
        info = self._seriesInfo(meta)
        fields = ((_("Year"), info.get("year")), (_("Rating"), info.get("imdb_rating")), (_("Genres"), info.get("genres")))
        lines = [" | ".join("%s: %s" % (label, value) for label, value in fields if value)]
        lines.append(self.cleanHtmlStr(_text(meta.get("description"))))
        return "[/br]".join(line for line in lines if line)

    def _episodeNames(self, imdbId):
        # {(season, episode): (name, released, overview)} from Cinemeta
        names = {}
        for video in self._cinemeta(imdbId).get("videos") or []:
            if isinstance(video, dict):
                key = (_toInt(video.get("season"), -1), _toInt(video.get("episode") or video.get("number"), -1))
                names[key] = (self.cleanHtmlStr(_text(video.get("name") or video.get("title"))),
                              _text(video.get("released") or video.get("firstAired"))[:10],
                              self.cleanHtmlStr(_text(video.get("overview") or video.get("description"))))
        return names

    @staticmethod
    def _torrentParts(torrent):
        # ["720p WEB x264", "278 MB", "S:12 P:3"] (fix 091026: the style of the other torrent hosts)
        size = _formatSize(_toInt(torrent.get("size_bytes")))
        health = "S:%d P:%d" % (_toInt(torrent.get("seeds")), _toInt(torrent.get("peers")))
        return [x for x in (_qualityLabel(_release(torrent)), size, health) if x]

    def _showReleases(self, cItem):
        # the torrents of the show of cItem without those of other shows under its IMDb id, None when the API fails
        torrents = self._showTorrents(cItem.get("imdb_id", ""))
        if torrents is None:
            return None
        show = cItem.get("show") or cItem.get("meta_title", "")
        return [t for t in torrents if _sameShow(_release(t), show)]

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        base = {"name": "category", "good_for_fav": True, "desc": ""}
        self.addDir(dict(base, category="eztv_latest", title=_("Latest"), url=self.MAIN_URL))
        self.addDir(dict(base, category="eztv_catalog", title=_("Popular"), catalog="top", url=self._catalogUrl("top")))
        self.addDir(dict(base, category="eztv_catalog", title=_("Featured"), catalog="imdbRating", url=self._catalogUrl("imdbRating")))
        self.addDir(dict(base, category="eztv_genres", title=_("Genres")))
        self.listsTab(self.searchItems(), {"name": "category"})

    def listGenres(self, cItem):
        for genre in SERIES_GENRES:
            self.addDir({"name": "category", "category": "eztv_catalog", "title": genre, "catalog": "top", "genre": genre,
                         "url": self._catalogUrl("top", genre), "good_for_fav": True})

    def listLatest(self, cItem):
        page = max(1, _toInt(cItem.get("page", 1), 1))
        printDBG("EZTV.listLatest page[%d]" % page)
        data = self._getTorrents("limit=%d&page=%d" % (PER_PAGE, page))
        if data is None:
            SetIPTVPlayerLastHostError(_("Failed to connect to host."))
            return
        normalize = IsMediaNamingNormalized()
        for torrent in data.get("torrents") or []:
            infoHash = _text(torrent.get("hash")).lower() if isinstance(torrent, dict) else ""
            if not HASH_RE.match(infoHash):
                continue
            self.torrentCache[infoHash] = torrent
            release = _release(torrent)
            imdbId = _imdbId(torrent)
            title = _rowTitle(release) if normalize else release
            descLines = [release] if title != release else []
            descLines.append(" | ".join(self._torrentParts(torrent)))
            released = _toInt(torrent.get("date_released_unix"))
            if released:
                descLines.append("%s %s" % (_("Released:"), time.strftime("%Y-%m-%d %H:%M", time.localtime(released))))
            descLines.append(_text(torrent.get("filename")))
            params = {"name": "category", "category": "eztv_torrent", "good_for_fav": True, "title": title, "release": release,
                      "url": "%sep/%s/" % (self.MAIN_URL, _toInt(torrent.get("id"))), "info_hash": infoHash,
                      "magnet": _text(torrent.get("magnet_url")),
                      "icon": _text(torrent.get("small_screenshot")) or self.DEFAULT_ICON_URL,
                      "desc": "[/br]".join(line for line in descLines if line)}
            if imdbId:
                params.update({"imdb_id": imdbId, "season": _toInt(torrent.get("season")), "episode": _toInt(torrent.get("episode")),
                               "meta_type": "tv"})
            self.addVideo(params)
        count = _toInt(data.get("torrents_count"))
        lastPage = (count + PER_PAGE - 1) // PER_PAGE
        listItem = stripPagerKeys(dict(cItem))
        listItem["url"] = self.MAIN_URL
        addPagingItems(self, listItem, page, page < lastPage, lastPage, self.MAIN_URL + "?page={page}")

    def listCatalog(self, cItem):
        catalog = cItem.get("catalog", "top")
        genre = cItem.get("genre", "")
        search = cItem.get("search", "")
        page = max(1, _toInt(cItem.get("page", 1), 1))
        url = self._catalogUrl(catalog, genre, search)
        if page > 1:
            url = url[:-len(".json")] + ("&" if (genre or search) else "/") + "skip=%d.json" % ((page - 1) * CATALOG_PER_PAGE)
        printDBG("EZTV.listCatalog [%s]" % url)
        data = self._getJson(url)
        if not isinstance(data, dict):
            SetIPTVPlayerLastHostError(_("Failed to connect to host."))
            return
        count = 0
        for meta in data.get("metas") or []:
            if not isinstance(meta, dict):
                continue
            imdbId = _text(meta.get("imdb_id") or meta.get("id"))
            name = self.cleanHtmlStr(_text(meta.get("name")))
            if not IMDB_RE.match(imdbId) or not name:
                continue
            count += 1
            year = _text(meta.get("releaseInfo") or meta.get("year"))[:4]
            # the year tells apart shows of the same name (Taskmaster UK / NZ / ...)
            title = "%s (%s)" % (name, year) if year.isdigit() else name
            self.addDir({"name": "category", "category": "eztv_series", "good_for_fav": True, "title": title, "show": name,
                         "url": IMDB_URL % imdbId, "imdb_id": imdbId, "icon": _text(meta.get("poster")),
                         "desc": self._seriesDesc(meta), "meta_type": "tv", "meta_title": name, "meta_year": year})
        if search:
            return  # Cinemeta answers a search with one page only
        if not count and page == 1:
            self.addMarker({"title": _("No items found"), "desc": ""})
            return
        # last page unknown: a full page has a next one
        listItem = stripPagerKeys(dict(cItem))
        listItem["url"] = self._catalogUrl(catalog, genre)
        addPagingItems(self, listItem, page, count >= CATALOG_FULL_PAGE, 0, listItem["url"] + "?page={page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("EZTV.listSearchResult [%s]" % searchPattern)
        pattern = searchPattern.strip()
        if pattern:
            self.listCatalog(dict(cItem, category="eztv_catalog", catalog="top", search=pattern, page=1))

    def _itemBase(self, cItem):
        return dict((key, cItem[key]) for key in ("imdb_id", "show", "meta_type", "meta_title", "meta_year", "icon") if key in cItem)

    def listSeasons(self, cItem):
        torrents = self._showReleases(cItem)
        if torrents is None:
            SetIPTVPlayerLastHostError(_("Failed to connect to host."))
            return
        seasons = {}
        years = {}
        for torrent in torrents:
            airDate = _airDate(torrent)
            if airDate:
                years.setdefault(airDate[:4], set()).add(airDate)
                continue
            season = _toInt(torrent.get("season"), -1)
            if season >= 0:
                seasons.setdefault(season, set()).add(_toInt(torrent.get("episode")))
        # add 091026: daily shows (EZTV files their dated releases under season 0): one folder per year, newest first
        for year in sorted(years, reverse=True):
            self.addDir(dict(self._itemBase(cItem), name="category", category="eztv_season", good_for_fav=True, title=year,
                             url="%s?year=%s" % (cItem.get("url", ""), year), air_year=year,
                             desc="%s: %d" % (_("Episodes"), len(years[year]))))
        # Specials / packs (season 0) last
        for season in sorted(seasons, key=lambda s: (s == 0, -s)):
            title = _("Specials") if season == 0 else _("Season %d") % season
            episodes = len([e for e in seasons[season] if e > 0])
            self.addDir(dict(self._itemBase(cItem), name="category", category="eztv_season", good_for_fav=True, title=title,
                             url="%s?season=%d" % (cItem.get("url", ""), season), season=season,
                             desc="%s: %d" % (_("Episodes"), episodes) if episodes else ""))
        if not seasons and not years:
            self.addMarker({"title": _("No items found"), "desc": ""})

    @staticmethod
    def _releasesDesc(releases):
        # "Releases: 6 (1080p, 720p, 480p)"
        resolutions = []
        for torrent in releases:
            res = _resolution(_release(torrent))[0]
            if res and res not in resolutions:
                resolutions.append(res)
        return "%s: %d%s" % (_("Releases"), len(releases), (" (%s)" % ", ".join(resolutions)) if resolutions else "")

    def listAirDates(self, cItem, torrents):
        # add 091026: the episodes of a daily show in one year, by air date (newest first)
        imdbId = cItem.get("imdb_id", "")
        year = cItem.get("air_year", "")
        show = cItem.get("show") or cItem.get("meta_title", "")
        days = {}
        for torrent in torrents:
            airDate = _airDate(torrent)
            if airDate[:4] == year:
                days.setdefault(airDate, []).append(torrent)
        normalize = IsMediaNamingNormalized()
        for day in sorted(days, reverse=True):
            releases = sorted(days[day], key=_sortKey, reverse=True)
            name = _airDateName(_release(releases[0]))
            if normalize and show:
                title = "%s - %s" % (show, day)
            else:
                title = "%s - %s" % (day, name) if name else day
            self.addVideo(dict(self._itemBase(cItem), name="category", category="eztv_episode", good_for_fav=True, title=title,
                               url="%s?date=%s" % (IMDB_URL % imdbId, day), air_date=day,
                               icon=_text(releases[0].get("small_screenshot")) or cItem.get("icon", ""),
                               desc="[/br]".join(line for line in (name, self._releasesDesc(releases), "%s %s" % (_("Released:"), day)) if line)))
        if not days:
            self.addMarker({"title": _("No items found"), "desc": ""})

    def listEpisodes(self, cItem):
        imdbId = cItem.get("imdb_id", "")
        season = _toInt(cItem.get("season"))
        show = cItem.get("show") or cItem.get("meta_title", "")
        torrents = self._showReleases(cItem) or []
        if cItem.get("air_year"):
            self.listAirDates(cItem, torrents)
            return
        episodes = {}
        for torrent in torrents:
            if _toInt(torrent.get("season"), -1) == season and not _airDate(torrent):
                episodes.setdefault(_toInt(torrent.get("episode")), []).append(torrent)
        names = self._episodeNames(imdbId) if episodes else {}
        normalize = IsMediaNamingNormalized()
        # newest episode first, the packs of the season (episode 0) last
        for episode in sorted(episodes, key=lambda e: (e == 0, -e)):
            releases = sorted(episodes[episode], key=_sortKey, reverse=True)
            name, released, overview = names.get((season, episode), ("", "", ""))
            if episode:
                sxe = formatSxxExx(season, episode)
                if normalize and show:
                    title = "%s - %s" % (show, sxe)
                else:
                    title = "%s - %s" % (sxe, name) if name else sxe
            else:
                title = "%s - %s" % (show, formatSxxExx(season)) if show else formatSxxExx(season)
                title = "%s (%s)" % (title, _("Season pack"))
            descLines = [name, self._releasesDesc(releases)]
            if released:
                descLines.append("%s %s" % (_("Released:"), released))
            descLines.append(overview)
            self.addVideo(dict(self._itemBase(cItem), name="category", category="eztv_episode", good_for_fav=True, title=title,
                               url="%s?season=%d&episode=%d" % (IMDB_URL % imdbId, season, episode), season=season, episode=episode,
                               icon=_text(releases[0].get("small_screenshot")) or cItem.get("icon", ""),
                               desc="[/br]".join(line for line in descLines if line)))
        if not episodes:
            self.addMarker({"title": _("No items found"), "desc": ""})

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("EZTV.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        if cItem.get("category") == "eztv_torrent":
            infoHash = cItem.get("info_hash", "")
            # not cached any more (favourites): the API has no lookup by hash, the item keeps the magnet
            torrent = self.torrentCache.get(infoHash) or {"hash": infoHash, "title": cItem.get("release") or cItem.get("title", ""),
                                                          "magnet_url": cItem.get("magnet", "")}
            releases = [torrent]
        else:
            torrents = self._showReleases(cItem)
            if torrents is None:
                SetIPTVPlayerLastHostError(_("Failed to connect to host."))
                return []
            airDate = cItem.get("air_date", "")
            season, episode = _toInt(cItem.get("season")), _toInt(cItem.get("episode"))
            if airDate:
                releases = [t for t in torrents if _airDate(t) == airDate]
            else:
                releases = [t for t in torrents if _toInt(t.get("season"), -1) == season and _toInt(t.get("episode"), -1) == episode
                            and not _airDate(t)]
            releases.sort(key=_sortKey, reverse=True)
        title = cItem.get("title", "")
        icon = cItem.get("icon", "")
        if not icon.startswith("http"):
            icon = ""
        urltab = []
        for torrent in releases:
            infoHash = _text(torrent.get("hash")).lower()
            if not HASH_RE.match(infoHash):
                continue
            magnet = _text(torrent.get("magnet_url")).replace("&amp;", "&")
            if not magnet.startswith("magnet:?"):
                magnet = "magnet:?xt=urn:btih:%s&dn=%s&tr=%s" % (infoHash, urllib_quote_plus(_release(torrent) or title),
                                                                  "&tr=".join(urllib_quote_plus(t) for t in TRACKERS))
            # "720p WEB x264 - 278 MB - S:12 P:3 - <release>": several releases per episode
            name = " - ".join(self._torrentParts(torrent) + [_release(torrent)])
            urltab.append({"name": name, "url": strwithmeta(magnet, {"title": title, "icon": icon}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("EZTV.getVideoLinks [%s]" % videoUrl)
        if videoUrl.startswith("magnet:?") or self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("EZTV.getArticleContent [%s]" % cItem.get("url", ""))
        category = cItem.get("category", "")
        imdbId = cItem.get("imdb_id", "")
        title = cItem.get("title", "")
        if not IMDB_RE.match(imdbId):
            icon = cItem.get("icon", "")
            return [{"title": title, "text": cItem.get("desc", ""), "images": [{"title": "", "url": icon}] if icon else [], "other_info": {}}]
        site = self._cinemeta(imdbId)
        info = self._seriesInfo(site)
        meta = {}
        try:
            meta = getMetaByImdbId("tv", imdbId)
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        story = self.cleanHtmlStr(_text(site.get("description")))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (plot, story)
        if cItem.get("air_date"):
            info["released"] = cItem["air_date"]
        elif category in ("eztv_episode", "eztv_torrent") and _toInt(cItem.get("episode")):
            name, released, overview = self._episodeNames(imdbId).get((_toInt(cItem.get("season")), _toInt(cItem.get("episode"))), ("", "", ""))
            if overview:
                text = "%s[/br][/br]%s" % (overview, text) if text else overview
            if released:
                info["released"] = released
            if name and name not in title:
                title = "%s - %s" % (title, name)
        icon = meta.get("poster") or _text(site.get("poster")) or cItem.get("icon", "")
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
        printDBG("EZTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "eztv_latest":
            self.listLatest(self.currItem)
        elif category == "eztv_genres":
            self.listGenres(self.currItem)
        elif category == "eztv_catalog":
            self.listCatalog(self.currItem)
        elif category == "eztv_series":
            self.listSeasons(self.currItem)
        elif category == "eztv_season":
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
        CHostBase.__init__(self, EZTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("eztv")

    def withArticleContent(self, cItem):
        return cItem.get("category") in EZTV.CONTENT_CATEGORIES
