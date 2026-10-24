# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host: seriale.vip (films and series with Polish lektor / dubbing / subtitles, DLE)
#   latest, films, series, cartoons, anime, TV shows, genres (First / Jump / Next page), search; series ->
#   seasons -> episodes from the playlist AJAX of the title; links = every player of the film / episode with
#   its version in the name; other address in the settings
###################################################
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

config.plugins.iptvplayer.serialevip_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.serialevip_alt_domain)]


def gettytul():
    return "https://seriale.vip/"


# the site's own categories (titles as the site writes them)
GENRES = (("action", "Akcja"), ("action_adventure", "Akcja i przygoda"), ("adventure", "Przygoda"), ("comedy", "Komedia"),
          ("crime", "Kryminał"), ("documentary", "Dokumentalne"), ("drama", "Dramat"), ("family", "Familijne"),
          ("fantasy", "Fantasy"), ("history", "Historyczne"), ("horror", "Horror"), ("music", "Muzyczne"),
          ("mystery", "Detektyw"), ("romance", "Melodramat"), ("romans", "Romans"), ("sci-fi_fantasy", "Sci-Fi"),
          ("science-fiction", "Fantazyjne"), ("thriller", "Thriller"), ("war", "Wojenne"), ("war_politics", "Wojna i polityka"),
          ("western", "Western"))
PER_PAGE = 12
EPISODES_PER_PAGE = 100
TITLE_URL_RE = re.compile(r"/(\d+)-[^/]*\.html")
SEASON_RE = re.compile(r"Sezon\s*(\d+)", re.I)
EPISODE_RE = re.compile(r"(\d+)\s*odcin|odcinek\s*(\d+)", re.I)
VIDEO_CATEGORIES = ("movie", "episode")
FOLDER_CATEGORIES = ("series", "season")


class SerialeVip(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "icon", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "serialevip", "cookie": "serialevip.cookie"})
        domain = config.plugins.iptvplayer.serialevip_alt_domain.value.strip()
        if domain and not domain.startswith("http"):
            domain = "https://" + domain
        self.MAIN_URL = self.cm.getBaseUrl(domain) if self.cm.isValidUrl(domain) else gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/serialevip135.png")
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [{"category": "list_items", "title": _("Latest added"), "url": self.getFullUrl("/")},
                     {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("films/")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serials/")},
                     {"category": "list_items", "title": _("Cartoons"), "url": self.getFullUrl("animation/")},
                     {"category": "list_items", "title": _("Anime"), "url": self.getFullUrl("anime/")},
                     {"category": "list_items", "title": _("TV Shows"), "url": self.getFullUrl("reality/")},
                     {"category": "genres", "title": _("Genres")}] + self.searchItems()
        self.playlistCache = {}
        self.watchedHelper = IPTVWatchedHelper("serialevip")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def _siteUrl(self, url):
        # urls of favourites saved under another address of the site -> the current one
        url = re.sub(r"^https?://[^/]+/", self.MAIN_URL, url or "")
        return url.split("#", 1)[0]

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self.cm.iriToUri(self._siteUrl(url)), addParams, post_data)

    @staticmethod
    def _path(url):
        return re.sub(r"^https?://[^/]+", "", url or "").rstrip("/")

    def _yearFromUrl(self, url):
        return self.cm.ph.getSearchGroups(url, r"-((?:19|20)\d{2})(?:-online)?\.html")[0]

    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year and ("(%s)" % year) not in title:
            return "%s (%s)" % (title, year)
        return title

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = self._path(cItem.get("url", ""))
            if not TITLE_URL_RE.search(path):
                return ""
            category = cItem.get("category", "")
            if cItem.get("type", "") == "video":
                return "video:%s" % path
            if category == "series":
                return "series:%s" % path
            if category == "season":
                return "season:%s#s%s" % (path, cItem.get("s_season", ""))
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES:
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def _addTiles(self, data):
        content = data[data.find('id="dle-content"'):] if 'id="dle-content"' in data else data
        content = content.split("<!--ENGINE_NAVIGATION-->", 1)[0]
        seen = set()
        for tile in re.split(r'<a\s+class="poster grid-item', content)[1:]:
            tile = tile.split("</a>", 1)[0]
            url = self.cm.ph.getSearchGroups(tile, r'href="([^"#]+)')[0]
            if not TITLE_URL_RE.search(url) or url in seen:
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tile, r'(?s)<h3[^>]*class="poster__title[^"]*"[^>]*>(.*?)</h3>')[0])
            if not title:
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(tile, r'<img[^>]+src="([^"]+)"')[0])
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tile, r'(?s)class="poster__label[^"]*"[^>]*>\s*<span>(.*?)</span>')[0])
            seasons = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tile, r'(?s)class="poster__series">(.*?)</div>')[0])
            year = self._yearFromUrl(url)
            desc = " | ".join(x for x in (label, seasons, "%s: %s" % (_("Year"), year) if year else "") if x)
            params = {"name": "category", "good_for_fav": True, "url": url, "s_title": title, "icon": icon, "desc": desc,
                      "meta_title": title, "meta_year": year}
            if label == "Film" and not seasons:
                params.update({"category": "movie", "title": self._movieTitle(title, year), "meta_type": "movie"})
                self.addVideo(params)
            else:
                # series, cartoons, anime ... - the playlist tells whether it is a film after all
                params.update({"category": "series", "title": title, "meta_type": "tv"})
                self.addDir(params)
        return len(seen)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        url = baseUrl if page <= 1 else "%spage/%d/" % (baseUrl, page)
        printDBG("SerialeVip.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        count = self._addTiles(data)
        pager = self.cm.ph.getDataBeetwenMarkers(data, "<!--ENGINE_NAVIGATION-->", "<!--/ENGINE_NAVIGATION-->", False)[1]
        lastPage = max([int(n) for n in re.findall(r"/page/(\d+)/", pager)] + [page])
        listItem = dict(cItem)
        listItem.update({"base_url": baseUrl, "url": baseUrl})
        tpl = baseUrl.replace("{", "{{").replace("}", "}}") + "page/{page}/"
        addPagingItems(self, listItem, page, bool(count) and page < lastPage, lastPage, tpl)

    def listGenres(self, cItem):
        for slug, title in GENRES:
            params = stripPagerKeys(dict(cItem), ("base_url",))
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl("%s/" % slug)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        cItem = dict(cItem)
        cItem.update({"category": "search_list", "f_pattern": searchPattern.strip(), "page": 1})
        self.listSearch(cItem)

    def listSearch(self, cItem):
        page = cItem.get("page", 1)
        searchPattern = cItem.get("f_pattern", "")
        printDBG("SerialeVip.listSearch [%s] page %s" % (searchPattern, page))
        url = self.getFullUrl("index.php?do=search&subaction=search&story=%s" % urllib_quote_plus(searchPattern))
        if page > 1:
            url += "&search_start=%d&full_search=0&result_from=%d" % (page, (page - 1) * PER_PAGE + 1)
        sts, data = self.getPage(url)
        if not sts:
            return
        count = self._addTiles(data)
        total = int(self.cm.ph.getSearchGroups(data, r"Znaleziono\s+(\d+)")[0] or 0)
        lastPage = (total + PER_PAGE - 1) // PER_PAGE
        # constant template: the page number drives the search, the template only lets "Jump" through
        addPagingItems(self, cItem, page, bool(count) and page < lastPage, lastPage, self.MAIN_URL)

    ###################################################
    # playlist (engine/ajax/controller.php?mod=playlists)
    ###################################################
    def _getPlaylist(self, url):
        # [{"url", "player", "version", "season", "episode"}] of a title page, cached per session
        newsId = self.cm.ph.getSearchGroups(url, r"/(\d+)-[^/]*\.html")[0]
        if not newsId:
            return []
        if newsId in self.playlistCache:
            return self.playlistCache[newsId]
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Referer": self._siteUrl(url), "X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/javascript, */*; q=0.01"})
        sts, data = self.getPage(self.getFullUrl("engine/ajax/controller.php?mod=playlists&news_id=%s&xfield=pl" % newsId), params)
        if not sts:
            return []
        try:
            html = json_loads(data).get("response", "") or ""
        except Exception:
            printExc()
            return []
        labels = {}
        for itemId, label in re.findall(r'<li\s+data-id="([^"]+)"\s*>(.*?)</li>', html, re.S):
            labels[itemId] = self.cleanHtmlStr(label)
        ret = []
        seen = set()
        for fileUrl, itemId, label in re.findall(r'<li\s+data-file="([^"]+)"\s+data-id="([^"]+)"\s*>(.*?)</li>', html, re.S):
            fileUrl = fileUrl.replace("\\/", "/").strip()
            if fileUrl.startswith("//"):
                fileUrl = "https:" + fileUrl
            if not self.cm.isValidUrl(fileUrl) or fileUrl in seen:
                continue
            seen.add(fileUrl)
            parts = itemId.split("_")
            chain = [labels.get("_".join(parts[:n]), "") for n in range(2, len(parts) + 1)]
            label = self.cleanHtmlStr(label)
            player = re.sub(r"^Stream-", "", chain[0] if chain else "") or self.up.getHostName(fileUrl)
            season, episode, version = 0, 0, []
            for text in chain[1:]:
                m = SEASON_RE.search(text)
                if m and not season:
                    season = int(m.group(1))
                elif text and text not in version:
                    version.append(text)
            m = EPISODE_RE.search(label)
            if m:
                episode = int(m.group(1) or m.group(2))
                season = season or 1
            elif label and label not in version:
                version.append(label)
            ret.append({"url": fileUrl, "player": player, "version": " / ".join(version), "season": season, "episode": episode, "label": label})
        self.playlistCache[newsId] = ret
        return ret

    def _episodes(self, playlist):
        # {season: {episode: label}}
        seasons = {}
        for item in playlist:
            if item["episode"]:
                seasons.setdefault(item["season"], {}).setdefault(item["episode"], item["label"])
        return seasons

    def listSeries(self, cItem):
        printDBG("SerialeVip.listSeries [%s]" % cItem.get("url", ""))
        playlist = self._getPlaylist(cItem["url"])
        seasons = self._episodes(playlist)
        if not seasons:
            if playlist:
                # a film listed among series / cartoons
                year = cItem.get("meta_year", "")
                params = dict(cItem)
                params.update({"category": "movie", "title": self._movieTitle(cItem.get("s_title", "") or cItem.get("title", ""), year), "meta_type": "movie"})
                self.addVideo(params)
            else:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return
        if len(seasons) == 1:
            season = list(seasons)[0]
            self.listEpisodes(dict(cItem, s_season=season), seasons[season])
            return
        for season in sorted(seasons):
            params = stripPagerKeys(dict(cItem), ("base_url",))
            params.update({"name": "category", "good_for_fav": True, "category": "season", "s_season": season,
                           "title": _("Season %d (%d episodes)") % (season, len(seasons[season]))})
            self.addDir(params)

    def listEpisodes(self, cItem, episodes=None):
        season = cItem.get("s_season", 1)
        if episodes is None:
            episodes = self._episodes(self._getPlaylist(cItem["url"])).get(season, {})
        show = cItem.get("s_title", "") or cItem.get("title", "")
        baseUrl = self._siteUrl(cItem["url"])
        numbers = sorted(episodes)
        page = cItem.get("page", 1)
        normalize = IsMediaNamingNormalized()
        for episode in numbers[(page - 1) * EPISODES_PER_PAGE:page * EPISODES_PER_PAGE]:
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = "%s - %s %d - %s" % (show, _("Season"), season, episodes[episode])
            params = stripPagerKeys(dict(cItem), ("base_url",))
            # an own url per episode: watched flag, downloaded marker and favourite of the episode
            params.update({"name": "category", "good_for_fav": True, "category": "episode", "title": title,
                           "url": "%s#s%de%d" % (baseUrl, season, episode), "s_title": show, "s_season": season,
                           "s_episode": episode, "meta_type": "tv"})
            self.addVideo(params)
        lastPage = (len(numbers) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE
        if lastPage > 1:
            listItem = dict(cItem, s_season=season, category="season")
            addPagingItems(self, listItem, page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("SerialeVip.getLinksForVideo [%s]" % url)
        season = cItem.get("s_season", 0)
        episode = cItem.get("s_episode", 0)
        m = re.search(r"#s(\d+)e(\d+)$", url)
        if m:
            season, episode = int(m.group(1)), int(m.group(2))
        urltab = []
        for item in self._getPlaylist(url):
            if episode and (item["season"], item["episode"]) != (season, episode):
                continue
            link = strwithmeta(item["url"], {"Referer": self._siteUrl(url)})
            if self.up.checkHostSupport(link) != 1:
                printDBG("SerialeVip: hoster not supported by urlparser [%s]" % item["url"])
                continue
            name = "%s [%s]" % (item["player"], item["version"]) if item["version"] else item["player"]
            urltab.append({"name": name, "url": link, "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("SerialeVip.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        info = {}
        original = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="pmovie__original-title">(.*?)</div>')[0])
        original = re.sub(r"^Original:\s*", "", original)
        if original:
            info["original_title"] = original
        yearLine = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="pmovie__year">(.*?)</div>')[0])
        year = self.cm.ph.getSearchGroups(yearLine, r"\(((?:19|20)\d{2})\)")[0]
        if year:
            info["year"] = year
        country = self.cleanHtmlStr(re.sub(r"^\(\d{4}\)\s*", "", yearLine).split("/")[0])
        if country:
            info["country"] = country
        quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="pmovie__quality[^"]*">.*?<div>(.*?)</div>')[0])
        if quality:
            info["quality"] = quality
        rating = self.cm.ph.getSearchGroups(data, r'pmovie__ext-rating--imdb">\s*([\d.]+)')[0]
        if rating.strip("0."):
            info["rating"] = "%.1f/10" % float(rating)
        fields = {}
        for label, value in re.findall(r'(?s)<li><span[^>]*>([^<]+):</span>(.*?)</li>', data):
            fields[self.cleanHtmlStr(label)] = self.cleanHtmlStr(value)
        for label, key in (("Gatunek", "genres"), ("Wersje", "translation"), ("Reżyser", "director"), ("Actors", "actors"),
                           ("Studio", "production"), ("Światowa premiera", "released"), ("Start emisji serialu", "first_air_date")):
            if fields.get(label):
                info[key] = fields[label]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<h1[^>]*>(.*?)</h1>")[0])
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="page__text[^"]*">(.*?)</div>')[0])
        poster = self.cm.ph.getSearchGroups(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "pmovie__poster"), ("</div", ">"), False)[1], r'src="([^"]+)"')[0]
        return title, story, self.getFullIconUrl(poster) if poster else "", info

    def getArticleContent(self, cItem):
        printDBG("SerialeVip.getArticleContent [%s]" % cItem.get("url", ""))
        title, story, poster, info = "", "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            title, story, poster, info = self._siteInfo(data)
        meta = {}
        metaTitle = info.get("original_title", "") or cItem.get("meta_title", "") or title
        mediaType = cItem.get("meta_type", "") or "movie"
        if cItem.get("category") in ("episode", "season"):
            mediaType = "tv"
        try:
            if metaTitle:
                meta = getMeta(mediaType, metaTitle, info.get("year", "") or cItem.get("meta_year", ""))
        except Exception:
            printExc()
        for key, value in meta.get("info", {}).items():
            if key not in info and not (key == "genre" and "genres" in info):
                info[key] = value
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = poster or meta.get("poster", "") or cItem.get("icon", "")
        return [{"title": cItem.get("title", "") or title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("SerialeVip.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "genres":
            self.listGenres(self.currItem)
        elif category == "series":
            self.listSeries(self.currItem)
        elif category == "season":
            self.listEpisodes(self.currItem)
        elif category == "search_list":
            self.listSearch(self.currItem)
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
        CHostBase.__init__(self, SerialeVip(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("serialevip")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
