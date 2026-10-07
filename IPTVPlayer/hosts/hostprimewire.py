# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 host standard
#   - primewire.mov (mirrors .pw / .zip, own domain in the settings); the /filter lists, genres, search
#     (the site wants the "ds" hash of the search text; on HTTP 401 the key is read again from the site's
#     app script) with the movie / series search types
#   - movies and episodes are VIDEO rows keyed on their page url; series -> seasons -> episodes
#   - links: the site's own API (/api/v1/s = the server list, /api/v1/l = the hoster url of one server);
#     /api/v1/l sits behind a Cloudflare check -> getPageCFProtection (MyE2i on the box)
#   - First page / Jump / Next page, watched flag, downloaded flag, favourites, name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta (IMDb id of the page) + the site's fields
###################################################
import re
from hashlib import sha1

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.primewire_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.primewire_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.primewire_proxy))
    if config.plugins.iptvplayer.primewire_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.primewire_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://primewire.mov/"


DOMAINS = ["https://primewire.mov/", "https://primewire.pw/", "https://primewire.zip/"]
# key the site hashes the search text with (its "ds" parameter)
SEARCH_KEY = "JyjId97F9PVqUPuMO0"
TILE_START = '<div class="index_item">'
TILE_END = '<div class="clearer">'
EPISODE_RE = re.compile(r'(?s)<div class="tv_episode_item([^"]*)">\s*<a href="([^"]+)">(.*?)</a>\s*<input[^>]+value="(\d+)"\s+data-season="(\d*)"')
YEAR_RE = re.compile(r"\((\d{4})\)\s*$")
PAGING_KEYS = ("base_url",)
EPISODES_PER_PAGE = 100
VIDEO_CATEGORIES = ("pw_video",)
SERIES_CATEGORIES = ("pw_series", "pw_season")


def _tiles(data):
    # html of each tile: from <div class="index_item"> up to the next tile, the "clearer" div or the end of the page
    # (the end without a final line break, as the former lookahead regex with "$" did)
    blocks = data.split(TILE_START)[1:]
    for idx, block in enumerate(blocks):
        end = block.find(TILE_END)
        if end > -1:
            blocks[idx] = block[:end]
        elif idx == len(blocks) - 1 and block.endswith("\n"):
            blocks[idx] = block[:-1]
    return blocks


class PrimeWire(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "e_id", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "primewire", "cookie": "primewire.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/primewire135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "with_metadata": True, "use_cookie": True, "load_cookie": True,
                              "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.searchSalt = SEARCH_KEY
        self.watchedHelper = IPTVWatchedHelper("primewire")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = GetAlternativeProxyUrl(config.plugins.iptvplayer.primewire_proxy.value)
        if proxy:
            addParams = dict(addParams, http_proxy=proxy)
        if re.search(r"[?&]ds=", baseUrl):
            # search: an outdated key answers HTTP 401, which must not start the browser check (MyE2i)
            plainParams = dict(addParams, header=dict(addParams.get("header", self.HEADER), **{"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER["User-Agent"]}))
            sts, data = self.cm.getPage(baseUrl, plainParams, post_data)
            if sts or (getattr(data, "meta", None) or {}).get("status_code") == 401:
                return sts, data
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        # cf_clearance is bound to the UA that solved the check
        try:
            cfUser = data.meta.get("cf_user", "")
        except Exception:
            cfUser = ""
        if cfUser and cfUser != self.HEADER.get("User-Agent"):
            self.HEADER["User-Agent"] = cfUser
        return sts, data

    def getJson(self, url):
        sts, data = self.getPage(url, dict(self.defaultParams, header=dict(self.HEADER, Referer=self.getMainUrl())))
        if not sts:
            return {}
        try:
            return json_loads(data)
        except Exception:
            printDBG("PrimeWire.getJson no JSON from [%s]: %s" % (url, data[:200]))
        return {}

    def selectDomain(self):
        domains = list(DOMAINS)
        domain = config.plugins.iptvplayer.primewire_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain if domain.endswith("/") else domain + "/")
        for domain in domains:
            sts, data = self.getPage(domain)
            if sts and "PrimeWire Official" in data:
                self.setMainUrl(self.cm.getBaseUrl(data.meta.get("url", domain)))
                break
        if self.MAIN_URL is None:
            self.MAIN_URL = domains[0]

    def onMain(self, url):
        # urls saved in favourites / history keep working when the site moves to another mirror
        return re.sub(r"^https?://[^/]+/", self.getMainUrl(), url or "")

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", url or "").split("#")[0].rstrip("/").lower()

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + SERIES_CATEGORIES:
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def searchKey(self, text):
        return sha1(ensure_binary(text + self.searchSalt)).hexdigest()[:10]

    def refreshSearchKey(self):
        # the key sits in the site's app script: e.target.elements.s.value+"<key>"
        sts, data = self.getPage(self.getMainUrl())
        script = self.cm.ph.getSearchGroups(data, r'<script[^>]+src="([^"]*/js/app-[^"]+)"')[0] if sts else ""
        if not script:
            return False
        sts, data = self.getPage(self.getFullUrl(script.replace("&amp;", "&")))
        key = self.cm.ph.getSearchGroups(data, r'\.s\.value\s*\+\s*"([^"]+)"')[0] if sts else ""
        printDBG("PrimeWire.refreshSearchKey [%s] -> [%s]" % (self.searchSalt, key))
        if not key or key == self.searchSalt:
            return False
        self.searchSalt = key
        return True

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
            if category == "pw_video" and cItem.get("type") == "video":
                return "video:%s" % path
            if category == "pw_series":
                return "series:%s" % path
            if category == "pw_season":
                return "season:%s#s%s" % (path, cItem.get("s_season", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        movies = [("Featured", _("Featured")), ("Popular", _("Popular")), ("Just Added", _("Recently added")),
                  ("Trending this Week", _("Trending this week")), ("External Rating", _("Top rated"))]
        series = [("Latest Episode", _("Latest episodes")), ("Popular", _("Popular")), ("Just Added", _("Recently added")),
                  ("Trending this Week", _("Trending this week")), ("External Rating", _("Top rated"))]
        menu = [{"category": "pw_menu", "title": _("Movies"), "sub": [("movie", sort, title) for sort, title in movies]},
                {"category": "pw_menu", "title": _("Series"), "sub": [("tv", sort, title) for sort, title in series]}]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listMenu(self, cItem):
        mediaType = cItem["sub"][0][0]
        for kind, sort, title in cItem["sub"]:
            url = self.getFullUrl("filter?sort=%s&type=%s" % (urllib_quote_plus(sort), kind))
            self.addDir({"name": "category", "category": "pw_list", "title": title, "url": url, "good_for_fav": True})
        self.addDir({"name": "category", "category": "pw_genres", "title": _("Genres"), "media_type": mediaType,
                     "url": self.getFullUrl("movies" if mediaType == "movie" else "tv")})

    def listGenres(self, cItem):
        sts, data = self.getPage(self.onMain(cItem["url"]))
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, "menu-genre-list", "</ul>", False)[1]
        for genre in re.findall(r'name="genre\[\]" type="checkbox" value="([^"]+)"', block):
            url = self.getFullUrl("filter?genre%%5B%%5D=%s&type=%s" % (urllib_quote_plus(genre), cItem.get("media_type", "movie")))
            self.addDir({"name": "category", "category": "pw_list", "title": self.cleanHtmlStr(genre), "url": url, "good_for_fav": True})

    def _addTile(self, block):
        url = self.cm.ph.getSearchGroups(block, r'<a href="(/(?:movie|tv)/[^"]+)"')[0]
        if not url:
            return False
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<a href="[^"]+" title="([^"]+)"')[0])
        if not title:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(block, ("<h2", ">"), ("</h2", ">"), False)[1])
        if not title:
            return False
        year = self.cm.ph.getSearchGroups(title, YEAR_RE.pattern)[0]
        name = YEAR_RE.sub("", title).strip()
        icon = self.cm.ph.getSearchGroups(block, r'<img src="([^"]+)"')[0]
        genres = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r'<a href="/filter\?genre\[\]=[^"]*">([^<]+)</a>', block))
        width = self.cm.ph.getSearchGroups(block, r'width:\s*([\d.]+)px;" class="current-rating"')[0]
        desc = " | ".join(x for x in (("%s: %s" % (_("Year"), year)) if year else "",
                                      ("%s: %s" % (_("Genres"), genres)) if genres else "",
                                      ("%s: %.1f/5" % (_("Rating"), float(width) / 20)) if width else "") if x)
        params = {"name": "category", "good_for_fav": True, "url": self.getFullUrl(url), "title": title, "desc": desc,
                  "icon": self.getFullIconUrl(icon) if icon else self.DEFAULT_ICON_URL, "meta_title": name, "meta_year": year}
        if url.startswith("/tv/"):
            params.update({"category": "pw_series", "s_title": name, "meta_type": "tv"})
            self.addDir(params)
        else:
            params.update({"category": "pw_video", "meta_type": "movie"})
            self.addVideo(params)
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = self.onMain(cItem.get("base_url") or cItem["url"])
        url = baseUrl if page <= 1 else "%s&page=%d" % (baseUrl, page)
        printDBG("PrimeWire.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts and cItem.get("search_text") and (getattr(data, "meta", None) or {}).get("status_code") == 401 and self.refreshSearchKey():
            # HTTP 401: the site's search key changed
            baseUrl = self._searchUrl(cItem["search_text"], cItem.get("search_type", ""))
            url = baseUrl if page <= 1 else "%s&page=%d" % (baseUrl, page)
            sts, data = self.getPage(url)
        if not sts:
            return
        content = self.cm.ph.getDataBeetwenMarkers(data, "index_item_container", 'class="pagination"', False)[1] or data
        added = sum(1 for block in _tiles(content) if self._addTile(block))
        pagination = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination"', "</div>", False)[1]
        hasNext = bool(re.search(r"[?&;]page=%d\b" % (page + 1), pagination)) and added > 0
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        addPagingItems(self, listItem, page, hasNext, 0, baseUrl.replace("{", "{{").replace("}", "}}") + "&page={page}")

    def _searchUrl(self, pattern, searchType):
        url = "filter?s=%s&ds=%s" % (urllib_quote_plus(pattern), self.searchKey(pattern))
        if searchType in ("movie", "tv"):
            url += "&type=%s" % searchType
        return self.getFullUrl(url)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("PrimeWire.listSearchResult [%s] [%s]" % (searchPattern, searchType))
        pattern = searchPattern.strip()
        self.listItems(dict(cItem, category="pw_list", url=self._searchUrl(pattern, searchType), search_text=pattern, search_type=searchType))

    def _episodes(self, data):
        # {season: [(episode, url, name, e_id)]} of the released episodes; specials are season 0
        seasons = {}
        for cls, url, inner, eId, season in EPISODE_RE.findall(data):
            if "released" not in cls:
                continue  # announced, no links yet
            label = self.cleanHtmlStr(inner.split("<div", 1)[0])
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'(?s)<span class="tv_episode_name">(.*?)</span>')[0]).lstrip("- ").strip()
            episode = int(self.cm.ph.getSearchGroups(label, r"E(\d+)")[0] or 0)
            season = int(season) if season.isdigit() and episode else 0
            if season == 0:
                episode = len(seasons.get(0, [])) + 1
            seasons.setdefault(season, []).append((episode, self.getFullUrl(url), name, eId))
        return seasons

    def listSeasons(self, cItem):
        printDBG("PrimeWire.listSeasons [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(self.onMain(cItem["url"]))
        if not sts:
            return
        seasons = self._episodes(data)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        if len(seasons) == 1:
            season = next(iter(seasons))
            self.listEpisodes(dict(cItem, s_season=season), seasons[season])
            return
        for season in sorted(seasons, key=lambda s: s or 9999):
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "good_for_fav": True, "category": "pw_season", "s_season": season,
                           "title": "%s %d" % (_("Season"), season) if season else _("Specials"),
                           "desc": "%s: %d" % (_("Episodes"), len(seasons[season]))})
            self.addDir(params)

    def listEpisodes(self, cItem, episodes=None):
        printDBG("PrimeWire.listEpisodes [%s]" % cItem.get("url", ""))
        season = cItem.get("s_season", 1)
        if episodes is None:
            sts, data = self.getPage(self.onMain(cItem["url"]))
            if not sts:
                return
            episodes = self._episodes(data).get(season, [])
        page = cItem.get("page", 1)
        lastPage = (len(episodes) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        for episode, url, name, eId in episodes[(page - 1) * EPISODES_PER_PAGE:page * EPISODES_PER_PAGE]:
            if not season:
                title = " - ".join(x for x in (show, _("Specials"), name) if x)
            elif normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = " - ".join(x for x in (show, "S%02d E%02d" % (season, episode), name) if x)
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "good_for_fav": True, "category": "pw_video", "title": title, "url": url, "e_id": eId,
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv", "desc": name})
            self.addVideo(params)
        if lastPage > 1:
            listItem = dict(cItem, s_season=season, category="pw_season")
            addPagingItems(self, listItem, page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    ###################################################
    # links
    ###################################################
    def _serverListUrl(self, cItem):
        url = self.onMain(cItem.get("url", ""))
        if "/movie/" in url:
            return self.getFullUrl("api/v1/s?s_id=%s&type=movie" % self.cm.ph.getSearchGroups(url, r"/movie/(\d+)")[0])
        sId = self.cm.ph.getSearchGroups(url, r"/tv/(\d+)")[0]
        eId = cItem.get("e_id", "")
        if not eId:
            sts, data = self.getPage(url)
            if sts:
                eId = self.cm.ph.getSearchGroups(data, r'id="link_target"[^>]+e_id="(\d+)"')[0]
        if not (sId and eId):
            return ""
        return self.getFullUrl("api/v1/s?s_id=%s&e_id=%s&type=tv" % (sId, eId))

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("PrimeWire.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        apiUrl = self._serverListUrl(cItem)
        data = self.getJson(apiUrl) if apiUrl else {}
        servers = []
        for server in data.get("servers", []):
            key = server.get("key")
            if not key:
                continue
            extra = [x for x in (server.get("quality"), server.get("file_size")) if x]
            name = server.get("name") or "?"
            if server.get("file_name"):
                name = "%s - %s" % (name, server["file_name"])
            if extra:
                name = "%s [%s]" % (name, ", ".join(extra))
            # fix 071026: the API lists the servers in random order - highest resolution (quality field or file name) first
            height = self.cm.ph.getSearchGroups(" %s %s " % (server.get("quality") or "", server.get("file_name") or ""), r"[\W_](2160|1080|720|576|480|360)p[\W_]")[0]
            servers.append((-int(height or 0), name, key))
        urltab, seen = [], {}
        for _height, name, key in sorted(servers, key=lambda x: x[0]):
            # the same hoster often comes several times without a file name: number them
            seen[name] = seen.get(name, 0) + 1
            if seen[name] > 1:
                name = "%s #%d" % (name, seen[name])
            linkUrl = strwithmeta(self.getFullUrl("api/v1/l?key=%s" % urllib_quote_plus(key)), {"Referer": self.onMain(url)})
            urltab.append({"name": name, "url": linkUrl, "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        story = (data.get("info") or {}).get("description", "")
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("PrimeWire.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        link = self.getJson(self.onMain(str(videoUrl))).get("link", "")
        if not self.cm.isValidUrl(link):
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(link, {"Referer": self.getMainUrl()})), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, imdb id, {INFO fields}) of a movie / series / episode page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]+)"')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<a href="(https://image\.tmdb\.org/[^"]+)" target="_blank">')[0]
        imdb = self.cm.ph.getSearchGroups(data, r'"imdb_id":"(tt\d+)"')[0]
        info = {}

        def field(label):
            return self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<strong>%s:</strong></td>\s*<td>(.*?)</td>" % label)[0])
        info["released"] = field("Released")
        info["duration"] = field("Runtime")
        info["genres"] = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r'class="movie_info_genres"><a [^>]+>([^<]+)</a>', data))
        info["status"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'class="tv_show_status"[^>]*>([^<]+)<')[0])
        return story, poster, imdb, {k: v for k, v in info.items() if v}

    def getArticleContent(self, cItem):
        printDBG("PrimeWire.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, imdb, info = "", "", "", {}
        url = self.onMain(cItem.get("url", ""))
        # an episode page has the episode's text; the series page the show's IMDb id and fields
        sts, data = self.getPage(url)
        if sts:
            story, poster, imdb, info = self._siteInfo(data)
        meta = {}
        mediaType = cItem.get("meta_type", "") or ("tv" if "/tv/" in url else "movie")
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and cItem.get("meta_title"):
                meta = getMeta(mediaType, cItem["meta_title"], cItem.get("meta_year", ""))
        except Exception:
            printExc()
        meta = meta or {}
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

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
        printDBG("PrimeWire.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "pw_menu":
            self.listMenu(self.currItem)
        elif category == "pw_genres":
            self.listGenres(self.currItem)
        elif category == "pw_list":
            self.listItems(self.currItem)
        elif category == "pw_series":
            self.listSeasons(self.currItem)
        elif category == "pw_season":
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
        CHostBase.__init__(self, PrimeWire(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("primewire")

    def getSearchTypes(self):
        return [(_("All"), "all"), (_("Movies"), "movie"), (_("Series"), "tv")]

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + SERIES_CATEGORIES
