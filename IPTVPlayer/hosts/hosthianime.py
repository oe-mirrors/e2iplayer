# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - new host for hianime.lol (HiAnime / Aniwatch / Zoro successor, anime with
#   English SUB and DUB). The site is a React app on top of the "sankavollerei" anime API (JSON, partly
#   zlib + base64url packed in "_encsankaa"): home lists, categories, genres, types, search, anime info
#   with IMDb / AniList mapping, seasons and episode lists. Playback goes through the same keyless embed
#   players the site uses, keyed by AniList id + episode number: ReCloud (cdn.4animo.xyz, plain HLS via
#   /stream/getSources) and MegaVid (megavid.buzz, JSON source). Watched flag, downloaded flag, name
#   normalisation, sidecar, moviemeta INFO (IMDb id from the site mapping), favourites.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
from base64 import urlsafe_b64decode
import re
import zlib
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://hianime.lol/"


class HiAnime(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what identifies a favourite and opens it again
    FAV_FIELDS = ("name", "category", "type", "url", "anime_id", "anilist", "ep_num", "season", "s_title", "icon",
                  "meta_type", "meta_title", "meta_year", "imdb", "dub")

    API_URL = "https://anime.sankavollerei.web.id/api"
    RECLOUD_URL = "https://cdn.4animo.xyz"
    MEGAVID_URL = "https://megavid.buzz"

    GENRES = ("Action", "Adventure", "Cars", "Comedy", "Dementia", "Demons", "Drama", "Ecchi", "Fantasy", "Game",
              "Harem", "Historical", "Horror", "Isekai", "Josei", "Kids", "Magic", "Martial Arts", "Mecha", "Military",
              "Music", "Mystery", "Parody", "Police", "Psychological", "Romance", "Samurai", "School", "Sci-Fi",
              "Seinen", "Shoujo", "Shoujo Ai", "Shounen", "Shounen Ai", "Slice of Life", "Space", "Sports",
              "Super Power", "Supernatural", "Thriller", "Vampire")

    # one folder per this many episodes for long running series
    EPISODE_RANGE = 100

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "HiAnime", "cookie": "hianime.cookie"})
        self.USER_AGENT = self.cm.getDefaultUserAgent('chrome')
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "*/*"}
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = "https://hianime.lol/to12/"
        # the site's logo answers 403 to anything but its own pages - no remote default icon
        self.DEFAULT_ICON_URL = ""
        self.MENU = [{"category": "list_api", "title": _("Newest Episodes"), "path": "/recently-updated"},
                     {"category": "list_api", "title": _("Top airing"), "path": "/top-airing"},
                     {"category": "list_api", "title": _("Most popular"), "path": "/most-popular"},
                     {"category": "list_api", "title": _("Most favourited"), "path": "/most-favorite"},
                     {"category": "list_api", "title": _("Recently added"), "path": "/recently-added"},
                     {"category": "list_api", "title": _("Completed"), "path": "/completed"},
                     {"category": "list_api", "title": _("Top upcoming"), "path": "/top-upcoming"},
                     {"category": "list_api", "title": _("Movies"), "path": "/filter?type=2"},
                     {"category": "types", "title": _("Types")},
                     {"category": "genres", "title": _("Genres")}] + self.searchItems()
        self.TYPES = [(_("TV series"), "/tv"), ("OVA", "/ova"), ("ONA", "/ona"), (_("Specials"), "/special"),
                      (_("Subbed anime"), "/subbed-anime"), (_("Dubbed anime"), "/dubbed-anime")]
        self.infoCache = {}
        self.episodesCache = {}

        self.watchedHelper = IPTVWatchedHelper("hianime")
        self.wfInitFolderCache()

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if not url:
                return ""
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url
            if cItem.get("category", "") in ("series", "episodes_range"):
                return "folder:%s" % url
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "") in ("series", "movie", "episode"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # helpers
    ###################################################
    def _api(self, path):
        # JSON of the site API; packed answers ({"_encsankaa": base64url(zlib(json))}) are unpacked
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Referer": "https://hianime.lol/", "Origin": "https://hianime.lol", "Accept": "application/json, text/plain, */*"})
        sts, data = self.cm.getPage(self.API_URL + path, params)
        if not sts:
            return {}
        try:
            data = json_loads(data)
            if isinstance(data, dict) and "_encsankaa" in data:
                packed = ensure_str(data["_encsankaa"]).strip()
                packed += "=" * (-len(packed) % 4)
                data = json_loads(ensure_str(zlib.decompress(urlsafe_b64decode(packed))))
            if isinstance(data, dict):
                return data
        except Exception:
            printExc()
        return {}

    def _results(self, path):
        data = self._api(path).get("results")
        return data if data is not None else {}

    def _str(self, value):
        if value is None:
            return ""
        return self.cleanHtmlStr(ensure_str(value) if not isinstance(value, (int, float)) else str(value))

    @staticmethod
    def _anilistId(animeId, info=None):
        try:
            anilist = ((info or {}).get("mappings") or {}).get("anilist")
            if anilist:
                return str(anilist)
        except Exception:
            printExc()
        # the site id ends with the AniList id ("one-piece-21")
        m = re.search(r"-(\d+)$", animeId or "")
        return m.group(1) if m else ""

    def _seriesUrl(self, animeId):
        return self.MAIN_URL + animeId

    def _episodeUrl(self, animeId, epNum):
        return "%swatch/%s?ep=%s" % (self.MAIN_URL, animeId, epNum)

    @staticmethod
    def _year(text):
        m = re.search(r"((?:19|20)\d{2})", text or "")
        return m.group(1) if m else ""

    @staticmethod
    def _seasonFromTitle(title):
        for pattern in (r"(\d+)(?:st|nd|rd|th)\s+Season", r"Season\s+(\d+)", r"\bS(\d+)\b"):
            m = re.search(pattern, title or "", re.I)
            if m:
                return int(m.group(1))
        return 1

    @staticmethod
    def _metaTitle(title):
        title = re.sub(r"\s*(?:\(\d{4}\)|:?\s*\d+(?:st|nd|rd|th)\s+Season|:?\s*Season\s+\d+|\bS\d+|Part\s+\d+)\s*$", "", title or "", flags=re.I)
        return title.strip(" -:")

    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year and ("(%s)" % year) not in title:
            return "%s (%s)" % (title, year)
        return title

    def _episodeTitle(self, sTitle, season, epNum, epName, isFiller=False):
        if IsMediaNamingNormalized():
            return "%s - %s" % (sTitle, formatSxxExx(season, epNum))
        label = "%s - %s %s" % (sTitle, _("Episode"), epNum)
        if epName and not re.match(r"^Episode\s+\d+$", epName, re.I):
            label += ": %s" % epName
        if isFiller:
            label += " (%s)" % _("Filler")
        return label

    def _itemDesc(self, item):
        tv = item.get("tvInfo") or {}
        head = []
        for label, key in ((_("Type"), "showType"), (_("Released"), "releaseDate"), (_("Episodes"), "eps"), ("SUB", "sub"), ("DUB", "dub"),
                           (_("Rating"), "quality"), (_("Duration"), "duration")):
            value = self._str(tv.get(key, ""))
            if value and not (key == "quality" and not re.match(r"^[0-9.]+$", value)):
                head.append("%s: %s" % (label, value))
        desc = self._str(item.get("description", ""))
        head = " | ".join(head)
        return "%s[/br]%s" % (head, desc) if head and desc else (head or desc)

    def _addAnime(self, item):
        animeId = self._str(item.get("id", ""))
        title = self._str(item.get("title", ""))
        if not animeId or not title:
            return False
        tv = item.get("tvInfo") or {}
        showType = self._str(tv.get("showType", "")).upper()
        year = self._year(self._str(tv.get("releaseDate", "")))
        eps = self._str(tv.get("eps", ""))
        params = {"good_for_fav": True, "url": self._seriesUrl(animeId), "anime_id": animeId, "anilist": self._anilistId(animeId),
                  "s_title": title, "icon": self._str(item.get("poster", "")), "desc": self._itemDesc(item), "meta_year": year,
                  "meta_title": self._metaTitle(title), "dub": self._str(tv.get("dub", ""))}
        if showType == "MOVIE" and eps in ("", "1"):
            params.update({"category": "movie", "title": self._movieTitle(title, year), "meta_type": "movie", "ep_num": "1"})
            self.addVideo(params)
        else:
            params.update({"category": "series", "title": title, "meta_type": "tv"})
            self.addDir(params)
        return True

    ###################################################
    # lists
    ###################################################
    def listApi(self, cItem):
        printDBG("HiAnime.listApi [%s]" % cItem.get("path", ""))
        page = cItem.get("page", 1)
        path = cItem.get("path", "")
        pageUrl = "%s%spage=" % (path, "&" if "?" in path else "?")
        data = self._results("%s%d" % (pageUrl, page))
        if not isinstance(data, dict):
            return
        cnt = 0
        for item in data.get("data") or []:
            if isinstance(item, dict) and self._addAnime(item):
                cnt += 1
        try:
            lastPage = int(data.get("totalPages") or data.get("totalPage") or 0)
        except (TypeError, ValueError):
            lastPage = 0
        # the list is read from path + page; the url only carries the page for "Jump"
        addPagingItems(self, cItem, page, bool(cnt and data.get("hasNextPage")), lastPage, self.API_URL + pageUrl + "{page}")

    def listTypes(self, cItem):
        for title, path in self.TYPES:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_api", "title": title, "path": path})
            self.addDir(params)

    def listGenres(self, cItem):
        for title in self.GENRES:
            params = dict(cItem)
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            params.update({"good_for_fav": True, "category": "list_api", "title": title, "path": "/genre/%s" % slug})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HiAnime.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_api", "path": "/search?keyword=%s" % urllib_quote(searchPattern.strip(), safe="")})
        self.listApi(cItem)

    ###################################################
    # anime page
    ###################################################
    def _getInfo(self, animeId):
        if animeId in self.infoCache:
            return self.infoCache[animeId]
        data = self._results("/info?id=%s" % urllib_quote(animeId, safe=""))
        if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
            return None
        if len(self.infoCache) > 30:
            self.infoCache = {}
        self.infoCache[animeId] = data
        return data

    def _getEpisodes(self, animeId):
        if animeId in self.episodesCache:
            return self.episodesCache[animeId]
        data = self._results("/episodes/%s" % urllib_quote(animeId, safe=""))
        episodes = []
        for ep in (data.get("episodes") or []) if isinstance(data, dict) else []:
            try:
                num = int(ep.get("episode_no") or 0)
            except (TypeError, ValueError):
                continue
            if num <= 0:
                continue
            episodes.append({"num": num, "title": self._str(ep.get("title", "")), "desc": self._str(ep.get("overview", "")),
                             "icon": self._str(ep.get("image", "")), "filler": ep.get("filler") is True})
        episodes.sort(key=lambda x: x["num"])
        if episodes:
            if len(self.episodesCache) > 30:
                self.episodesCache = {}
            self.episodesCache[animeId] = episodes
        return episodes

    def _seasonNum(self, animeId, info, title):
        for season in (info or {}).get("seasons") or []:
            if isinstance(season, dict) and season.get("id") == animeId:
                try:
                    num = int(season.get("data_number") or 0)
                    if num > 0:
                        return num
                except (TypeError, ValueError):
                    pass
        return self._seasonFromTitle(title)

    def listSeries(self, cItem):
        printDBG("HiAnime.listSeries [%s]" % cItem.get("anime_id", ""))
        animeId = cItem.get("anime_id", "")
        info = self._getInfo(animeId)
        episodes = self._getEpisodes(animeId)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No episodes available yet."))
            return
        data = (info or {}).get("data") or {}
        seasons = [s for s in ((info or {}).get("seasons") or []) if isinstance(s, dict) and s.get("id")]
        if len(seasons) > 1:
            params = dict(cItem)
            params.update({"good_for_fav": False, "category": "seasons", "title": "%s (%d)" % (_("All seasons"), len(seasons))})
            self.addDir(params)
        if len(episodes) > self.EPISODE_RANGE:
            for start in range(0, len(episodes), self.EPISODE_RANGE):
                chunk = episodes[start:start + self.EPISODE_RANGE]
                params = dict(cItem)
                params.update({"good_for_fav": False, "category": "episodes_range", "title": "%s %d-%d" % (_("Episodes"), chunk[0]["num"], chunk[-1]["num"]),
                               "url": "%s#%d" % (cItem["url"], chunk[0]["num"]), "ep_from": start, "ep_to": start + self.EPISODE_RANGE})
                self.addDir(params)
            return
        self._addEpisodes(cItem, info, data, episodes)

    def listEpisodesRange(self, cItem):
        animeId = cItem.get("anime_id", "")
        info = self._getInfo(animeId)
        episodes = self._getEpisodes(animeId)[cItem.get("ep_from", 0):cItem.get("ep_to", 0)]
        self._addEpisodes(cItem, info, ((info or {}).get("data") or {}), episodes)

    def _addEpisodes(self, cItem, info, data, episodes):
        animeId = cItem.get("anime_id", "")
        sTitle = self._str(data.get("title", "")) or cItem.get("s_title", "")
        season = self._seasonNum(animeId, info, sTitle)
        imdb = self._str(((data.get("mappings") or {}).get("imdb")) or "")
        icon = self._str(data.get("poster", "")) or cItem.get("icon", "")
        showType = self._str(data.get("showType", "")).upper()
        year = cItem.get("meta_year", "") or self._year(self._str((data.get("animeInfo") or {}).get("Aired", "")))
        isMovie = showType == "MOVIE" and len(episodes) == 1
        for ep in episodes:
            params = {"good_for_fav": True, "url": self._episodeUrl(animeId, ep["num"]), "anime_id": animeId, "anilist": self._anilistId(animeId, data),
                      "s_title": sTitle, "icon": ep["icon"] or icon, "ep_num": str(ep["num"]), "season": season, "imdb": imdb,
                      "meta_title": self._metaTitle(sTitle), "meta_year": year, "dub": cItem.get("dub", "")}
            if isMovie:
                params.update({"category": "movie", "title": self._movieTitle(sTitle, year), "meta_type": "movie", "url": self._seriesUrl(animeId),
                               "desc": cItem.get("desc", "")})
            else:
                desc = ep["desc"]
                if ep["title"]:
                    desc = "%s[/br]%s" % (ep["title"], desc) if desc else ep["title"]
                if ep["filler"]:
                    desc = "%s[/br]%s" % (_("Filler"), desc)
                params.update({"category": "episode", "title": self._episodeTitle(sTitle, season, ep["num"], ep["title"], ep["filler"]),
                               "meta_type": "tv", "desc": desc})
            self.addVideo(params)

    def listSeasons(self, cItem):
        info = self._getInfo(cItem.get("anime_id", ""))
        for season in (info or {}).get("seasons") or []:
            if not isinstance(season, dict) or not season.get("id"):
                continue
            animeId = self._str(season["id"])
            title = self._str(season.get("title", "")) or animeId
            label = self._str(season.get("season", ""))
            params = {"good_for_fav": True, "category": "series", "url": self._seriesUrl(animeId), "anime_id": animeId, "anilist": self._anilistId(animeId),
                      "s_title": title, "title": "%s - %s" % (label, title) if label and label not in title else title,
                      "icon": self._str(season.get("season_poster", "")), "meta_type": "tv", "meta_title": self._metaTitle(title), "meta_year": ""}
            self.addDir(params)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("HiAnime.getLinksForVideo [%s]" % cItem.get("url", ""))
        animeId = cItem.get("anime_id", "")
        anilist = cItem.get("anilist", "") or self._anilistId(animeId)
        epNum = cItem.get("ep_num", "") or "1"
        if not anilist:
            SetIPTVPlayerLastHostError(_("This video is only on hosters E2iPlayer cannot play."))
            return []
        urltab = []
        kinds = [("sub", "SUB"), ("dub", "DUB")]
        for kind, label in kinds:
            meta = {"Referer": self.MAIN_URL}
            urltab.append({"name": "ReCloud %s" % label, "url": strwithmeta("%s/embed/hd-2/ani/%s/%s/%s" % (self.RECLOUD_URL, anilist, epNum, kind), meta), "need_resolve": 1})
        for kind, label in kinds:
            meta = {"Referer": self.MAIN_URL}
            urltab.append({"name": "MegaVid %s" % label, "url": strwithmeta("%s/ani/%s/%s/%s" % (self.MEGAVID_URL, anilist, epNum, kind), meta), "need_resolve": 1})
        sidecarTxt = cItem.get("desc", "").replace("[/br]", "\n")
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def _getReCloud(self, embedUrl):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"]["Referer"] = "https://hianime.lol/"
        sts, data = self.cm.getPage(embedUrl, params)
        if not sts:
            return []
        sourcesUrl = self.cm.ph.getSearchGroups(data, r'''sourcesUrl\s*=\s*['"]([^'"]+)['"]''')[0]
        if not sourcesUrl:
            return []
        params["header"] = dict(self.HEADER)
        params["header"].update({"Referer": embedUrl, "Accept": "application/json, text/plain, */*"})
        sts, data = self.cm.getPage(self.cm.getFullUrl(sourcesUrl, self.RECLOUD_URL + "/"), params)
        if not sts:
            return []
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return []
        files = []
        for source in data.get("sources") or []:
            if isinstance(source, dict) and source.get("file"):
                files.append(self.cm.getFullUrl(ensure_str(source["file"]), self.RECLOUD_URL + "/"))
        if isinstance(data.get("link"), dict) and data["link"].get("file"):
            files.append(self.cm.getFullUrl(ensure_str(data["link"]["file"]), self.RECLOUD_URL + "/"))
        subtitles = []
        for track in data.get("tracks") or []:
            if isinstance(track, dict) and track.get("file") and track.get("kind", "captions") in ("captions", "subtitles"):
                label = self._str(track.get("label", "")) or "English"
                subtitles.append({"title": label, "url": self.cm.getFullUrl(ensure_str(track["file"]), self.RECLOUD_URL + "/"), "lang": self._subLang(label), "format": "vtt"})
        return self._hlsLinks(files, embedUrl, subtitles, "ReCloud")

    def _getMegaVid(self, embedUrl):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Referer": embedUrl, "Accept": "application/json"})
        sts, data = self.cm.getPage(embedUrl.rstrip("/") + "/source", params)
        if not sts:
            return []
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return []
        if data.get("status") != "ok" or not data.get("source"):
            printDBG("HiAnime: MegaVid [%s] %s" % (data.get("status"), data.get("message")))
            return []
        subtitles = []
        for track in data.get("tracks") or []:
            if isinstance(track, dict) and track.get("file") and track.get("kind", "captions") in ("captions", "subtitles"):
                label = self._str(track.get("label", "")) or "English"
                subtitles.append({"title": label, "url": ensure_str(track["file"]), "lang": self._subLang(label), "format": "vtt"})
        return self._hlsLinks([self.cm.getFullUrl(ensure_str(data["source"]), self.MEGAVID_URL + "/")], self.MEGAVID_URL + "/", subtitles, "MegaVid")

    SUB_LANGS = {"english": "en", "indonesian": "id", "arabic": "ar", "chinese": "zh", "spanish": "es", "portuguese": "pt", "french": "fr",
                 "german": "de", "italian": "it", "russian": "ru", "japanese": "ja", "thai": "th", "vietnamese": "vi", "malay": "ms",
                 "turkish": "tr", "korean": "ko", "polish": "pl", "hindi": "hi", "dutch": "nl"}

    def _subLang(self, label):
        word = (re.split(r"[^a-z]+", label.lower().strip()) or [""])[0]
        return self.SUB_LANGS.get(word, word[:2])

    def _hlsLinks(self, files, referer, subtitles, name):
        links = []
        for url in files:
            meta = {"User-Agent": self.USER_AGENT, "Referer": referer, "iptv_proto": "m3u8"}
            if subtitles:
                meta["external_sub_tracks"] = subtitles
            # a missing dub answers with an empty master playlist
            params = dict(self.defaultParams)
            params["header"] = {"User-Agent": self.USER_AGENT, "Referer": referer}
            sts, data = self.cm.getPage(url, params)
            if not sts or "#EXTM3U" not in data or ("#EXT-X-STREAM-INF" not in data and "#EXTINF" not in data):
                printDBG("HiAnime: empty playlist [%s]" % url)
                continue
            res = self.cm.ph.getSearchGroups(data, r"RESOLUTION=\d+x(\d+)")[0]
            links.append({"name": "%s %sp" % (name, res) if res else name, "url": strwithmeta(url, meta), "need_resolve": 0})
        return links

    def getVideoLinks(self, videoUrl):
        printDBG("HiAnime.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if videoUrl.startswith(self.RECLOUD_URL):
            links = self._getReCloud(videoUrl)
        elif videoUrl.startswith(self.MEGAVID_URL):
            links = self._getMegaVid(videoUrl)
        else:
            links = self.up.getVideoLinkExt(videoUrl)
        if not links:
            SetIPTVPlayerLastHostError(_("This episode is not available in this version (SUB/DUB) on this server. Try another one."))
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("HiAnime.getArticleContent [%s]" % cItem.get("anime_id", ""))
        otherInfo = {}
        title = cItem.get("s_title", "") or cItem.get("title", "")
        text = ""
        icon = cItem.get("icon", "")
        info = self._getInfo(cItem.get("anime_id", "")) if cItem.get("anime_id") else None
        data = (info or {}).get("data") or {}
        imdb = cItem.get("imdb", "")
        mediaType = cItem.get("meta_type", "tv")
        if data:
            title = self._str(data.get("title", "")) or title
            icon = self._str(data.get("poster", "")) or icon
            imdb = self._str((data.get("mappings") or {}).get("imdb") or "") or imdb
            animeInfo = data.get("animeInfo") or {}
            text = self._str(animeInfo.get("Overview", ""))
            if data.get("japanese_title") and data.get("japanese_title") != data.get("title"):
                otherInfo["alternate_title"] = self._str(data["japanese_title"])
            if data.get("showType"):
                otherInfo["type"] = self._str(data["showType"])
            for key, field in (("status", "Status"), ("duration", "Duration"), ("released", "Aired"), ("broadcast", "Premiered")):
                if animeInfo.get(field):
                    otherInfo[key] = self._str(animeInfo[field])
            for key, field in (("genres", "Genres"), ("production", "Studios")):
                value = animeInfo.get(field)
                if isinstance(value, list) and value:
                    otherInfo[key] = ", ".join([self._str(x) for x in value])
            if animeInfo.get("MAL Score"):
                otherInfo["rating"] = "%s/10" % self._str(animeInfo["MAL Score"])
            episodes = self.episodesCache.get(cItem.get("anime_id", ""))
            if episodes and data.get("showType", "").upper() != "MOVIE":
                otherInfo["episodes"] = str(len(episodes))
        meta = {}
        if imdb:
            meta = getMetaByImdbId(mediaType, imdb)
        if not meta and cItem.get("meta_title"):
            meta = getMeta(mediaType, cItem["meta_title"], cItem.get("meta_year", ""))
        sameAs = {"genre": "genres"}
        for key, value in meta.get("info", {}).items():
            if key not in otherInfo and sameAs.get(key) not in otherInfo:
                otherInfo[key] = value
        if not text:
            text = meta.get("plot", "") or cItem.get("desc", "").replace("[/br]", "\n")
        if not icon:
            icon = meta.get("poster", "")
        if cItem.get("category") == "episode":
            title = cItem.get("title", title)
            if cItem.get("desc"):
                text = "%s\n\n%s" % (cItem["desc"].replace("[/br]", "\n"), text) if text else cItem["desc"].replace("[/br]", "\n")
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("HiAnime.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_api":
            self.listApi(self.currItem)
        elif category == "types":
            self.listTypes(self.currItem)
        elif category == "genres":
            self.listGenres(self.currItem)
        elif category == "series":
            self.listSeries(self.currItem)
        elif category == "episodes_range":
            self.listEpisodesRange(self.currItem)
        elif category == "seasons":
            self.listSeasons(self.currItem)
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
        CHostBase.__init__(self, HiAnime(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("hianime")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("series", "movie", "episode")
