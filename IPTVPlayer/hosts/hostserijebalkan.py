# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 04.10.2026 - new host for serijebalkan.com (Serije Balkan - movies and series with
#   Serbian / Croatian / Bosnian subtitles)
#   - the site is a Next.js app: the whole catalogue (~24000 movies and series) comes from one JSON
#     (/api/search-data, ~2 MB gzip) that the site filters in the browser - it is loaded once, kept in
#     memory for 30 minutes and filtered / sorted / paged here (50 per page, First page / Jump / Next)
#   - movies / series: latest, most viewed, top rated, genres, years; new episodes (home page); search
#     (title and original title, like the site)
#   - show and episode pages: the data rides in the React Server Components payload
#     (self.__next_f.push) - show object with IMDb id, plot, genres, the episode list
#   - links: server1..server4 of the movie / episode (base64, every char +1) -> urlparser
#     (byse, hqq/netu, vidsrc); the site's own .srt goes along as external subtitle
#   - watched flag (series -> season -> episode), downloaded flag, favourites, name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta (IMDb id) + the site's fields
###################################################
import base64
import json
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://www.serijebalkan.com/"


CDN_URL = "https://cdn.serijebalkan.com/"
CATALOG_TTL = 1800
# the catalogue survives a new host object (leaving and opening the host again)
_CATALOG = {"time": 0, "items": []}
PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')
SERVER_RE = re.compile(r'"server(\d)":"([^"]+)"')
EPISODE_SLUG_RE = re.compile(r"-(\d+)-(\d+)$")
PAGING_KEYS = ("kind", "genre", "year", "sort", "search")
VIDEO_CATEGORIES = ("sb_video",)
SERIES_CATEGORIES = ("sb_series", "sb_season")


def _str(value):
    if value is None:
        return ""
    if not isinstance(value, (type(u""), bytes)):
        value = str(value)
    return ensure_str(value).strip()


def _text(value):
    # unicode (py2) / str (py3) for case-insensitive search over the catalogue
    if value is None:
        return u""
    if isinstance(value, bytes):
        return value.decode("utf-8", "ignore")
    if not isinstance(value, type(u"")):
        return type(u"")(value)
    return value


def _decodeServer(value):
    # the player url is base64 of the url with every char shifted by +1 (the site's JS undoes it)
    value = _str(value)
    try:
        url = ensure_str(base64.b64decode(value))
        url = "".join(chr(ord(c) - 1) for c in url)
        if url.startswith("http"):
            return url
    except Exception:
        pass
    return value if value.startswith("http") else ""


class SerijeBalkan(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year", "imdb_id")
    ITEMS_PER_PAGE = 50
    EPISODES_PER_PAGE = 100

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "serijebalkan", "cookie": "serijebalkan.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("apple-touch-icon.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER["User-Agent"] = self.cm.getDefaultUserAgent("chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.MENU = [
            {"category": "sb_home", "title": _("New episodes"), "url": self.MAIN_URL},
            {"category": "sb_menu", "title": _("Movies"), "kind": "Film"},
            {"category": "sb_menu", "title": _("Series"), "kind": "Serija"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("serijebalkan")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(self.cm.iriToUri(baseUrl), addParams, post_data)

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", url or "").split("#")[0].split("?")[0].rstrip("/").lower()

    def _fileUrl(self, collectionId, recordId, fileName, thumb="350x0"):
        if not (collectionId and recordId and fileName):
            return ""
        url = "%sapi/files/%s/%s/%s" % (CDN_URL, _str(collectionId), _str(recordId), urllib_quote(_str(fileName)))
        return url + "?thumb=" + thumb if thumb else url

    def _rsc(self, data):
        # the React Server Components payload of a page as one string
        parts = []
        for chunk in PUSH_RE.findall(data):
            try:
                parts.append(json.loads(chunk))
            except Exception:
                pass
        return u"".join(_text(p) for p in parts)

    def _showObject(self, rsc):
        # the show / movie record of a show or episode page (with expand.episodes)
        for m in re.finditer(r'"(?:show|movie)":\{', rsc):
            try:
                obj = json.JSONDecoder().raw_decode(rsc, m.end() - 1)[0]
            except Exception:
                continue
            if isinstance(obj, dict) and obj.get("slug") and obj.get("type"):
                return obj
        return {}

    def _servers(self, rsc):
        # (player urls, subtitle file) of the movie / episode record that carries the servers
        pos = -1
        for m in SERVER_RE.finditer(rsc):
            pos = m.start()
            break
        if pos < 0:
            return [], ""
        start = max(rsc.rfind("{", 0, pos), rsc.rfind("}", 0, pos)) + 1
        end = rsc.find("}", pos)
        segment = rsc[start:end if end > 0 else len(rsc)]
        urls = []
        for num, value in sorted(SERVER_RE.findall(segment)):
            url = _decodeServer(value)
            if url and url not in [u[1] for u in urls]:
                urls.append((num, url))
        subtitle = _str(self.cm.ph.getSearchGroups(segment, r'"subtitle":"([^"]+\.(?:srt|vtt))"')[0])
        return urls, subtitle

    def _desc(self, fields, plot=""):
        desc = " | ".join("%s: %s" % (label, value) for label, value in fields if value)
        if plot:
            desc = "%s[/br]%s" % (desc, plot) if desc else plot
        return desc

    def _plot(self, text):
        return self.cleanHtmlStr(_str(text).replace("<br/>", " ").replace("<br>", " "))

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + SERIES_CATEGORIES:
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
            path = self._path(cItem.get("url", ""))
            category = cItem.get("category", "")
            if not path:
                return ""
            if cItem.get("type") == "video" and (path.startswith("/show/") or path.startswith("/epizoda/")):
                return "video:%s" % path
            if category == "sb_series":
                return "series:%s" % path
            if category == "sb_season":
                return "season:%s#s%s" % (path, cItem.get("s_season", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # catalogue
    ###################################################
    def _catalog(self):
        # [(slug, title, original title, type, year, genres, rating, views, created, poster)]
        if _CATALOG["items"] and time.time() - _CATALOG["time"] < CATALOG_TTL:
            return _CATALOG["items"]
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Accept="application/json", Referer=self.MAIN_URL)
        sts, data = self.getPage(self.getFullUrl("api/search-data"), params)
        if not sts:
            return _CATALOG["items"]
        try:
            raw = json_loads(data)
        except Exception:
            printExc()
            return _CATALOG["items"]
        data = None
        items = []
        for row in raw if isinstance(raw, list) else []:
            try:
                genres = tuple(_text(g) for g in re.findall(r'"([^"]+)"', _text(row.get("genres") or "")))
                try:
                    rating = float(row.get("rating") or 0)
                except ValueError:
                    rating = 0.0
                try:
                    views = int(row.get("views") or 0)
                except ValueError:
                    views = 0
                items.append((_text(row.get("slug")), _text(row.get("title")), _text(row.get("originalTitle")), _text(row.get("type")),
                              _text(row.get("year")), genres, rating, views, _text(row.get("created")),
                              self._fileUrl(row.get("collectionId"), row.get("id"), row.get("poster"))))
            except Exception:
                printExc()
        raw = None
        printDBG("SerijeBalkan._catalog %d items" % len(items))
        if items:
            _CATALOG["items"] = items
            _CATALOG["time"] = time.time()
        return _CATALOG["items"]

    def _filtered(self, cItem):
        items = self._catalog()
        kind = cItem.get("kind", "")
        genre = _text(cItem.get("genre", ""))
        year = _text(cItem.get("year", ""))
        search = _text(cItem.get("search", "")).lower().strip()
        if kind:
            items = [i for i in items if i[3] == kind]
        if genre:
            items = [i for i in items if genre in i[5]]
        if year:
            items = [i for i in items if i[4] == year]
        if search:
            items = [i for i in items if search in i[1].lower() or search in i[2].lower()]
        sort = cItem.get("sort", "")
        if sort == "views":
            items = sorted(items, key=lambda i: i[7], reverse=True)
        elif sort == "rating":
            items = sorted(items, key=lambda i: i[6], reverse=True)
        elif sort == "created":
            items = sorted(items, key=lambda i: i[8], reverse=True)
        return items

    def listMenu(self, cItem):
        kind = cItem.get("kind", "")
        base = {"name": "category", "category": "sb_list", "kind": kind}
        url = self.getFullUrl("list?type=%s" % kind)
        for title, sort in ((_("Latest"), "created"), (_("Most viewed"), "views"), (_("Top rated"), "rating")):
            self.addDir(dict(base, title=title, sort=sort, url="%s&sort=%s" % (url, sort)))
        self.addDir(dict(base, category="sb_genres", title=_("Genres"), url=url))
        self.addDir(dict(base, category="sb_years", title=_("Year"), url=url))

    def listGenres(self, cItem):
        counts = {}
        for item in self._filtered({"kind": cItem.get("kind", "")}):
            for genre in item[5]:
                counts[genre] = counts.get(genre, 0) + 1
        for genre in sorted(counts, key=lambda g: g.lower()):
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "category": "sb_list", "title": _str(genre), "kind": cItem.get("kind", ""), "genre": _str(genre),
                           "sort": "created", "desc": "%s: %d" % (_("Titles"), counts[genre]), "good_for_fav": True,
                           "url": self.getFullUrl("list?type=%s&genre=%s" % (cItem.get("kind", ""), urllib_quote(_str(genre))))})
            self.addDir(params)

    def listYears(self, cItem):
        counts = {}
        for item in self._filtered({"kind": cItem.get("kind", "")}):
            if item[4].isdigit():
                counts[item[4]] = counts.get(item[4], 0) + 1
        for year in sorted(counts, reverse=True):
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "category": "sb_list", "title": _str(year), "kind": cItem.get("kind", ""), "year": _str(year),
                           "sort": "created", "desc": "%s: %d" % (_("Titles"), counts[year]), "good_for_fav": True,
                           "url": self.getFullUrl("list?type=%s&year=%s" % (cItem.get("kind", ""), _str(year)))})
            self.addDir(params)

    def _addShow(self, cItem, item, normalize):
        slug, title, original, kind, year, genres, rating, views = item[:8]
        poster = item[9]
        title, original, year = _str(title), _str(original), _str(year)
        if not slug or not title:
            return
        fields = ((_("Original title"), original if original != title else ""), (_("Year"), year),
                  (_("Genres"), ", ".join(_str(g) for g in genres)), (_("Rating"), "%.1f" % rating if rating else ""),
                  (_("Views"), str(views) if views else ""))
        params = stripPagerKeys(dict(cItem), PAGING_KEYS)
        params.update({"name": "category", "good_for_fav": True, "url": self.getFullUrl("show/" + _str(slug)), "icon": poster,
                       "desc": self._desc(fields), "meta_title": original or title, "meta_year": year})
        if kind == "Serija":
            params.update({"category": "sb_series", "title": title, "s_title": title, "meta_type": "tv"})
            self.addDir(params)
        else:
            params.update({"category": "sb_video", "title": "%s (%s)" % (title, year) if normalize and year else title, "meta_type": "movie"})
            self.addVideo(params)

    def listCatalog(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        items = self._filtered(cItem)
        if not items:
            if not _CATALOG["items"]:
                SetIPTVPlayerLastHostError(_("The site's catalogue could not be loaded."))
            return
        normalize = IsMediaNamingNormalized()
        start = (page - 1) * self.ITEMS_PER_PAGE
        for item in items[start:start + self.ITEMS_PER_PAGE]:
            self._addShow(cItem, item, normalize)
        lastPage = (len(items) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE
        # the whole list is in memory: the folder url stays the same for every page ("Jump" template)
        addPagingItems(self, cItem, page, page < lastPage, lastPage, cItem.get("url", "").replace("{", "%7B").replace("}", "%7D"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SerijeBalkan.listSearchResult [%s]" % searchPattern)
        pattern = (searchPattern or "").strip()
        if not pattern:
            return
        params = dict(cItem)
        params.update({"category": "sb_list", "search": pattern, "page": 1,
                       "url": self.getFullUrl("list?search=%s" % urllib_quote(pattern))})
        self.listCatalog(params)

    ###################################################
    # home page: new episodes
    ###################################################
    def listHome(self, cItem):
        sts, data = self.getPage(cItem.get("url") or self.MAIN_URL)
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, "Nove Epizode</h2>", "</section>", False)[1]
        normalize = IsMediaNamingNormalized()
        for tile in block.split('<div><a class="block"')[1:]:
            url = self.cm.ph.getSearchGroups(tile, r'href="(/epizoda/[^"]+)"')[0]
            show = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tile, r"(?s)<h3[^>]*>(.*?)</h3>")[0])
            if not url or not show:
                continue
            showUrl = self.cm.ph.getSearchGroups(tile, r'href="(/show/[^"]+)"')[0]
            icon = self.cm.ph.getSearchGroups(tile, r'<img src="([^"]+)"')[0].replace("&amp;", "&")
            badge = self.cleanHtmlStr(re.sub(r"<!--.*?-->", "", self.cm.ph.getSearchGroups(tile, r"(?s)rounded-r-full[^>]*>(.*?)</div>")[0]))
            numbers = re.search(r"S\s*(\d+)\s*E\s*(\d+)", badge) or EPISODE_SLUG_RE.search(url)
            params = {"name": "category", "category": "sb_video", "good_for_fav": True, "url": self.getFullUrl(url), "icon": icon,
                      "s_title": show, "meta_type": "tv", "meta_title": show, "show_url": self.getFullUrl(showUrl) if showUrl else ""}
            if numbers:
                season, episode = int(numbers.group(1)), int(numbers.group(2))
                params.update({"s_season": season, "s_episode": episode,
                               "title": "%s - %s" % (show, formatSxxExx(season, episode) if normalize else "S%02d E%02d" % (season, episode))})
            else:
                params["title"] = show
            self.addVideo(params)

    ###################################################
    # series -> seasons -> episodes
    ###################################################
    def _episodes(self, show):
        # {season: [(episode, slug, title, desc, icon)]}
        seasons = {}
        for ep in (show.get("expand") or {}).get("episodes") or []:
            if not isinstance(ep, dict) or not ep.get("slug"):
                continue
            try:
                season, episode = int(ep.get("season") or 0), int(ep.get("number") or 0)
            except (TypeError, ValueError):
                continue
            icon = self._fileUrl(ep.get("collectionId"), ep.get("id"), ep.get("image"), "350x0")
            row = (episode, _str(ep.get("slug")), _str(ep.get("title")), self._plot(ep.get("desc")), icon)
            if row[1] not in [e[1] for e in seasons.get(season, [])]:
                seasons.setdefault(season, []).append(row)
        return seasons

    def _loadShow(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return {}, ""
        rsc = self._rsc(data)
        return self._showObject(rsc), rsc

    def listSeries(self, cItem):
        printDBG("SerijeBalkan.listSeries [%s]" % cItem.get("url", ""))
        show = self._loadShow(cItem["url"])[0]
        seasons = self._episodes(show)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No episodes found."))
            return
        if len(seasons) == 1:
            season = list(seasons)[0]
            self.listEpisodes(dict(cItem, s_season=season), seasons[season])
            return
        for season in sorted(seasons):
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "good_for_fav": True, "category": "sb_season", "s_season": season,
                           "title": "%s %d" % (_("Season"), season), "desc": "%s: %d" % (_("Episodes"), len(seasons[season])),
                           "imdb_id": _str(show.get("imdbId")) or cItem.get("imdb_id", "")})
            self.addDir(params)

    def listEpisodes(self, cItem, episodes=None):
        printDBG("SerijeBalkan.listEpisodes [%s]" % cItem.get("url", ""))
        season = cItem.get("s_season", 1)
        if episodes is None:
            episodes = self._episodes(self._loadShow(cItem["url"])[0]).get(season, [])
        episodes = sorted(episodes)
        page = max(1, int(cItem.get("page", 1) or 1))
        lastPage = (len(episodes) + self.EPISODES_PER_PAGE - 1) // self.EPISODES_PER_PAGE
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        for episode, slug, name, plot, icon in episodes[(page - 1) * self.EPISODES_PER_PAGE:page * self.EPISODES_PER_PAGE]:
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = " - ".join(x for x in (show, "S%02d E%02d" % (season, episode), name) if x)
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "good_for_fav": True, "category": "sb_video", "title": title, "url": self.getFullUrl("epizoda/" + slug),
                           "icon": icon or cItem.get("icon", ""), "desc": self._desc(((_("Episode"), name),), plot), "s_title": show,
                           "s_season": season, "s_episode": episode, "meta_type": "tv", "show_url": cItem["url"]})
            self.addVideo(params)
        if lastPage > 1:
            listItem = dict(cItem, s_season=season, category="sb_season")
            addPagingItems(self, listItem, page, page < lastPage, lastPage, cItem["url"].replace("{", "%7B").replace("}", "%7D"))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("SerijeBalkan.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        show, rsc = self._loadShow(url)
        servers, subtitle = self._servers(rsc)
        if not servers:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        meta = {"Referer": self.MAIN_URL}
        if subtitle:
            meta["serijebalkan_subs"] = json_dumps([{"title": "SerijeBalkan", "url": CDN_URL + "subtitles/" + urllib_quote(subtitle), "lang": "sr",
                                                     "format": "vtt" if subtitle.lower().endswith(".vtt") else "srt"}])
        urltab, unsupported = [], []
        for num, playerUrl in servers:
            host = self.up.getHostName(playerUrl)
            if self.up.checkHostSupport(playerUrl) != 1:
                unsupported.append(host)
                continue
            urltab.append({"name": "%s %s - %s" % (_("Server"), num, host), "url": strwithmeta(playerUrl, dict(meta)), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(unsupported))
            return []
        story = self._plot(show.get("desc"))
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("SerijeBalkan.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        videoUrl = strwithmeta(videoUrl)
        siteSubs = []
        try:
            if videoUrl.meta.get("serijebalkan_subs"):
                siteSubs = json_loads(videoUrl.meta["serijebalkan_subs"])
        except Exception:
            printExc()
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        links = decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        if siteSubs:
            for item in links:
                url = strwithmeta(item["url"])
                # the site's translation first, the hoster's own tracks (vidsrc: many languages) after it
                tracks = siteSubs + [t for t in (url.meta.get("external_sub_tracks") or []) if t.get("url") not in [s["url"] for s in siteSubs]]
                item["url"] = strwithmeta(url, {"external_sub_tracks": tracks})
        return links

    ###################################################
    # INFO
    ###################################################
    def _episodeText(self, show, url):
        # "Episode title[/br]episode plot" of an episode page from the show's episode list
        slug = self._path(url).rsplit("/", 1)[-1]
        for episodes in self._episodes(show).values():
            for row in episodes:
                if row[1] == slug:
                    return "[/br]".join(x for x in (row[2], row[3]) if x)
        return ""

    def _siteInfo(self, show):
        info = {}
        year = _str(show.get("year"))
        if year and year != "0":
            info["year"] = year
        genres = show.get("genres") or []
        if isinstance(genres, list) and genres:
            info["genres"] = ", ".join(_str(g) for g in genres)
        if show.get("rating"):
            info["rating"] = "%s/10" % _str(show.get("rating"))
        if show.get("views"):
            info["views"] = _str(show.get("views"))
        original = _str(show.get("originalTitle"))
        if original and original != _str(show.get("title")):
            info["original_title"] = original
        cast = [_str(p.get("name")) for p in ((show.get("expand") or {}).get("cast") or []) if isinstance(p, dict) and p.get("name")]
        if cast:
            info["actors"] = ", ".join(cast[:6])
        return info

    def _lookupMeta(self, cItem, show, year):
        mediaType = "tv" if _str(show.get("type")) == "Serija" or cItem.get("meta_type") == "tv" else "movie"
        imdbId = _str(show.get("imdbId")) or cItem.get("imdb_id", "")
        meta = {}
        try:
            if imdbId:
                meta = getMetaByImdbId(mediaType, imdbId)
            metaTitle = _str(show.get("originalTitle")) or _str(show.get("title")) or cItem.get("meta_title", "") or cItem.get("s_title", "")
            if not meta and metaTitle:
                meta = getMeta(mediaType, metaTitle, year)
        except Exception:
            printExc()
        return meta or {}

    def getArticleContent(self, cItem):
        url = cItem.get("url", "")
        printDBG("SerijeBalkan.getArticleContent [%s]" % url)
        show = self._loadShow(url)[0] if self.cm.isValidUrl(url) else {}
        story = self._plot(show.get("desc"))
        if "/epizoda/" in url:
            own = self._episodeText(show, url)  # the episode's own title and description first
            if own:
                story = "%s[/br][/br]%s" % (own, story) if story else own
        info = self._siteInfo(show)
        meta = self._lookupMeta(cItem, show, info.get("year", "") or cItem.get("meta_year", ""))
        for key, value in meta.get("info", {}).items():
            info.setdefault(key, value)
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot not in story:
            text = "%s[/br][/br]%s" % (story, plot)
        poster = self._fileUrl(show.get("collectionId"), show.get("id"), show.get("poster"), "") if show else ""
        icon = meta.get("poster") or poster or cItem.get("icon", "")
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
        printDBG("SerijeBalkan.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "sb_home":
            self.listHome(self.currItem)
        elif category == "sb_menu":
            self.listMenu(self.currItem)
        elif category == "sb_genres":
            self.listGenres(self.currItem)
        elif category == "sb_years":
            self.listYears(self.currItem)
        elif category == "sb_list":
            self.listCatalog(self.currItem)
        elif category == "sb_series":
            self.listSeries(self.currItem)
        elif category == "sb_season":
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
        CHostBase.__init__(self, SerijeBalkan(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("serijebalkan")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in SERIES_CATEGORIES
