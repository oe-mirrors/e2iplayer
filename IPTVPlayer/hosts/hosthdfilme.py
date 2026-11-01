# -*- coding: utf-8 -*-
LAST_MODIFIED = "01.11.2026"
# 01.11.2026 - the site moved to hd-filme.one and was rebuilt: new cards, ?page=N paging, /suche search, player and IMDb id in the page data.

import re

from Components.config import config, ConfigYesNo, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase, RetHost
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.meinecloud import MeineCloud, isPlayerUrl
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhostmixin import WatchedFlagHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, sidecarMetaQuery, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import extractNum, formatSxxExx
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized

config.plugins.iptvplayer.hdfilme_mkv = ConfigYesNo(default=True)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Create MKV"), config.plugins.iptvplayer.hdfilme_mkv))
    return optionList


def gettytul():
    return "https://hd-filme.one/"


PAGING_KEYS = ("base_url", "page_tpl")
# the page data of the player: \"src\":\"https://devideosrc.co/custom/movie/tt123\" (movie), \"imdb\":\"tt123\" (series)
MOVIE_PLAYER_RE = r'(https://(?:devideosrc\.co|meinecloud\.click)/(?:custom/)?movie/tt\d+)'
SERIES_IMDB_RE = r'\\?"imdb\\?":\\?"(tt\d+)'


def _pageUrl(url):
    # an episode row's url is the series page + "#s<season>e<episode>" (its own download / favourite key)
    return (url or "").split("#")[0]


class HDFilme(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "HDFilme", "cookie": "HDFilme.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "brand/hdfilme/logo-footer.png"
        self.MAIN_URL = gettytul()
        self.cacheSeasons = {}
        self.watchedHelper = IPTVWatchedHelper("hdfilme")
        self.MENU = [
            {"category": "list_items", "title": _("New"), "url": self.getFullUrl("filme1")},
            {"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("kinofilme")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serien")},
            {"category": "list_genres", "title": _("Genres")}] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            itemType = cItem.get("type", "")
            category = cItem.get("category", "")
            if itemType in ["video", "audio"]:
                # episodes: the series url + the stable "mc:<imdb>/<s>/<e>" id (keys from before the
                # "#s1e2" episode urls stay valid)
                url = _pageUrl(str(cItem.get("url", "") or "").strip())
                seasonId = str(cItem.get("season_id", "") or "").strip()
                streamUrl = str(cItem.get("stream_url", "") or "").strip()
                # only episodes (which share the series url) need the stream_url to stay unique;
                # a standalone movie must key on the plain url so its listing tile matches
                if seasonId != "" and url != "" and streamUrl != "":
                    return "url:%s|%s" % (url, streamUrl)
                if url != "":
                    return "url:%s" % url
                return ""
            if category == "list_episodes":
                url = str(cItem.get("url", "") or "").strip()
                seasonId = str(cItem.get("season_id", "") or "").strip()
                if url != "" and seasonId != "":
                    return "season:%s|%s" % (url, seasonId)
                return ""
            if category == "list_seasons":
                url = str(cItem.get("url", "") or "").strip()
                if url != "":
                    return "url:%s" % url
                return ""
            return ""
        except Exception:
            printExc()
            return ""

    def _buildSeasonItem(self, seasonId):
        return {"category": "list_episodes", "url": _pageUrl(self.currItem.get("url", "")), "season_id": seasonId}

    def _propagateEpisodeWatchedState(self, item):
        """Recompute the season-parent and series-parent watched state for an episode-ish item
        (an episode video, or a list_episodes season node). No-op for anything without a season."""
        try:
            if not isinstance(item, dict):
                return
            seasonId = str(item.get("season_id", "") or "").strip()
            url = _pageUrl(str(item.get("url", "") or self.currItem.get("url", "") or "").strip())
            if seasonId == "" or url == "":
                return
            seasonEpisodes = self.cacheSeasons.get(seasonId, [])
            if seasonEpisodes:
                self.watchedHelper.updateParentWatchedState(self._buildSeasonItem(seasonId), seasonEpisodes, self._getWatchedKeyForItem)
            seasonChildren = [self._buildSeasonItem(sid) for sid in self.cacheSeasons]
            if seasonChildren:
                self.watchedHelper.updateParentWatchedState({"category": "list_seasons", "url": url}, seasonChildren, self._getWatchedKeyForItem)
        except Exception:
            printExc()

    def _story(self, data):
        # the plot; og:description starts with the site's own "<title> stream online ..." text
        return self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="dsyn[^"]*">(.*?)</p>')[0])

    def _detailField(self, data, label):
        # <p class="dato"><strong>Regisseur<!-- -->:</strong><span><a ...>Name</a></span>...</p>, or the plain text
        block = self.cm.ph.getSearchGroups(data, r'(?s)<p class="dato"><strong>%s<.*?</strong>(.*?)</p>' % label)[0]
        names = re.findall(r">([^<]+)</a>", block)
        return ", ".join(self.cleanHtmlStr(name) for name in names) if names else self.cleanHtmlStr(block)

    def listItems(self, cItem):
        printDBG("HDFilme.listItems |%s|" % cItem)
        page = int(cItem.get("page", 1) or 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        tpl = cItem.get("page_tpl", "")
        if not tpl:
            # <list>?page=<n>
            tpl = baseUrl.replace("{", "{{").replace("}", "}}") + ("&" if "?" in baseUrl else "?") + "page={page}"
        sts, data = self.getPage(baseUrl if page <= 1 else tpl.format(page=page))
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        count = 0
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<a class="cv"', '</a>'):
            itemUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            if not title or not self.cm.isValidUrl(itemUrl):
                continue
            icon = self.cm.ph.getSearchGroups(item, '<img src="([^"]+)')[0]
            icon = self.getFullIconUrl(icon) if icon else self.DEFAULT_ICON_URL
            # below the title: the year of a movie, "2 Staffeln" of a series
            info = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'class="cv-m">(.*?)</div>')[0])
            isSeries = "/serie/" in itemUrl
            year = "" if isSeries else self.cm.ph.getSearchGroups(info, r"(\d{4})")[0]
            desc = "%s: %s" % (_("Year"), year) if year else info
            # series show no "(Year)" (it would end up in every episode name)
            dispTitle = "%s (%s)" % (title, year) if (normalize and year) else title
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "category": "list_seasons", "title": dispTitle, "s_title": title, "url": itemUrl, "icon": icon,
                           "desc": desc, "meta_type": "tv" if isSeries else "", "meta_title": title, "meta_year": year})
            self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            self.addDir(params)
            count += 1
        # the list only links the next page ("weitere Titel"), its last page is unknown
        hasNext = bool(count) and re.search(r'href="[^"]*[?&]page=%d"' % (page + 1), data) is not None
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl, page_tpl=tpl)
        addPagingItems(self, listItem, page, hasNext, 0, tpl)

    def _resolveMeineCloud(self, data):
        movieUrl = self.cm.ph.getSearchGroups(data, MOVIE_PLAYER_RE)[0]
        if movieUrl:
            return "movie", movieUrl
        imdb = self.cm.ph.getSearchGroups(data, SERIES_IMDB_RE)[0]
        if imdb:
            return "series", imdb
        return None, None

    def _meineCloud(self):
        return MeineCloud(self.cm, self.defaultParams, self.MAIN_URL)

    def _buildEpisodesForSeason(self, seasonId, seasonNum, seriesName, url, icon, desc, imdb, siteEpisodes):
        episodes = []
        for ep in siteEpisodes:
            episodeNum = ep["episode"]
            name = self.cleanHtmlStr(ep["title"])
            # stable per-episode id (watched key) - the hoster embed url behind it may change
            streamId = "mc:%s/%d/%d" % (imdb, seasonNum, episodeNum)
            if not IsMediaNamingNormalized():
                # normalisation off: the site's own episode label
                label = "S%d E%d – %s" % (seasonNum, episodeNum, name) if name else "S%d E%d" % (seasonNum, episodeNum)
                episodeTitle = "%s - %s" % (seriesName, label) if seriesName else label
            else:
                epTag = formatSxxExx(seasonNum, episodeNum)
                if seriesName:
                    episodeTitle = "%s - %s %s" % (seriesName, epTag, name) if name else "%s - %s" % (seriesName, epTag)
                else:
                    episodeTitle = "%s %s" % (epTag, name) if name else epTag
            # own url per episode: the download marker and the favourite identity are keyed on it
            episodes.append({"type": "video", "url": "%s#s%de%d" % (_pageUrl(url), seasonNum, episodeNum), "title": episodeTitle, "icon": icon,
                             "desc": self.cleanHtmlStr(ep["desc"]) or desc, "stream_url": streamId, "stream_type": "mc_episode", "mc_url": ep["url"],
                             "season_id": seasonId, "good_for_fav": True, "s_title": seriesName, "meta_type": "tv", "meta_title": seriesName, "imdb": imdb})
        return episodes

    def _loadSeriesCache(self, imdb, seriesName, seriesUrl, icon, desc):
        """Ask meinecloud for the series' seasons + episodes and (re)populate self.cacheSeasons.
        Returns (seasons, seasonNumsById); seasons is [] on failure."""
        self.cacheSeasons = {}
        seasonNumsById = {}
        seasons = []
        for seasonNum, siteEpisodes in self._meineCloud().seriesEpisodes(imdb):
            seasonId = str(seasonNum)
            seasons.append((seasonId, "S%d" % seasonNum))
            seasonNumsById[seasonId] = seasonNum
            self.cacheSeasons[seasonId] = self._buildEpisodesForSeason(seasonId, seasonNum, seriesName, seriesUrl, icon, desc, imdb, siteEpisodes)
        return seasons, seasonNumsById

    def listSeasons(self, cItem):
        printDBG("HDFilme.listSeasons |%s|" % cItem)
        url = cItem["url"]
        icon = cItem.get("icon", "") or self.DEFAULT_ICON_URL
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self._story(data)
        kind, target = self._resolveMeineCloud(data)
        if kind is None:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        if kind != "series":
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.pop("isWatched", None)
            params.pop("isStarted", None)
            params.update({"good_for_fav": True, "category": "video", "title": cItem["title"], "url": self.getFullUrl(url), "icon": icon, "desc": desc,
                           "stream_url": target, "stream_type": kind, "meta_type": "movie", "imdb": MeineCloud.imdbFromUrl(target)})
            self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            self.addVideo(params)
            return
        seriesName = self.cleanHtmlStr(cItem.get("s_title", "") or cItem.get("title", "") or "")
        seasons, seasonNumsById = self._loadSeriesCache(target, seriesName, url, icon, desc)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, season_id=seasons[0][0], series_name=seriesName))
            return
        seasonParams = {}
        for seasonId, _seasonLabelRaw in seasons:
            seasonNum = seasonNumsById.get(seasonId, 0)
            episodes = self.cacheSeasons.get(seasonId, [])
            seasonTag = formatSxxExx(seasonNum) if IsMediaNamingNormalized() else (_("Season") + " %d" % extractNum(seasonNum, 0))
            title = "%s - %s" % (seriesName, seasonTag) if seriesName else seasonTag
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.pop("isWatched", None)
            params.pop("isStarted", None)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "icon": icon, "desc": desc, "season_id": seasonId,
                           "series_name": seriesName, "s_title": seriesName, "meta_type": "tv", "meta_title": seriesName, "imdb": target})
            if episodes:
                self.watchedHelper.updateParentWatchedState(params, episodes, self._getWatchedKeyForItem)
            else:
                self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            seasonParams[seasonId] = params
            self.addDir(params)
        if seasonParams:
            seriesItem = {"category": "list_seasons", "url": url}
            self.watchedHelper.updateParentWatchedState(seriesItem, list(seasonParams.values()), self._getWatchedKeyForItem)

    def listEpisodes(self, cItem):
        printDBG("HDFilme.listEpisodes |%s|" % cItem)
        seasonId = cItem.get("season_id", "")
        if seasonId and seasonId not in self.cacheSeasons:
            self._rebuildSeasonCache(cItem)
        for item in self.cacheSeasons.get(seasonId, []):
            params = dict(item)
            self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            self.addVideo(params)

    def _rebuildSeasonCache(self, cItem):
        """cacheSeasons is only filled while browsing a series live; rebuild it when a season
        node is reopened from favourites/history (empty cache) so its episodes show up."""
        seriesUrl = _pageUrl(cItem.get("url", "") or self.currItem.get("url", ""))
        if not seriesUrl:
            return
        seriesName = cItem.get("series_name", "") or cItem.get("s_title", "")
        if not seriesName:
            seriesName = re.sub(r"\s*-\s*S\d+(?:E\d+)?\s*$", "", self.cleanHtmlStr(cItem.get("title", "") or ""))
        sts, data = self.getPage(seriesUrl)
        if not sts:
            return
        kind, target = self._resolveMeineCloud(data)
        if kind != "series":
            return
        icon = cItem.get("icon", "") or self.DEFAULT_ICON_URL
        desc = cItem.get("desc", "") or self._story(data)
        self._loadSeriesCache(target, seriesName, seriesUrl, icon, desc)

    def listGenres(self, cItem):
        printDBG("HDFilme.listGenres")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'class="panel p-genres"', "</div>", False)[1]
        for url, title in re.findall(r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', block):
            title = self.cleanHtmlStr(title).strip()
            url = self.getFullUrl(url)
            if not title or not self.cm.isValidUrl(url):
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": url})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HDFilme.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        # one page of results; the pager rows of listItems would open as an ordinary list
        self.listItems(dict(cItem, category="list_items", url=self.getFullUrl("suche?q=%s" % urllib_quote_plus(searchPattern))))

    def getLinksForVideo(self, cItem):
        printDBG("HDFilme.getLinksForVideo [%s]" % cItem)
        linksTab = []
        streamUrl = cItem.get("stream_url", "")
        if not streamUrl:
            return linksTab

        sidecarEnabled = IsSidecarEnabled()
        # sidecar: the item's text + picture; the download manager adds the moviemeta details INFO looks up
        # (IMDb id of the player, else the title)
        sidecarMeta = {}
        if sidecarEnabled:
            sidecarMeta = sidecarMetaQuery(cItem.get("meta_type", "") or "movie", cItem.get("meta_title", "") or cItem.get("s_title", ""),
                                           cItem.get("meta_year", ""), cItem.get("imdb", ""), skip=())
        sidecar = buildSidecarFromItem(cItem, sidecarEnabled, metaQuery=sidecarMeta)

        if cItem.get("stream_type") == "mc_episode":
            imdb, season, episode = streamUrl[3:].split("/")
            data = self._meineCloud().episodeLinks(imdb, season, episode) or [cItem.get("mc_url", "")]
        else:
            data = self._meineCloud().movieLinks(MeineCloud.imdbFromUrl(streamUrl))
        for url in data:
            if not url or isPlayerUrl(url) or "player.php" in url:
                continue
            url = "https:" + url if url.startswith("//") else url
            linksTab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        if not linksTab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
        return applySidecarToLinks(linksTab, sidecar)

    def getVideoLinks(self, videoUrl):
        printDBG("HDFilme.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            cfgMkvEnabled = config.plugins.iptvplayer.hdfilme_mkv.value
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar, cfgMkvEnabled)
        return []

    def getArticleContent(self, cItem):
        printDBG("HDFilme.getArticleContent [%s]" % cItem)
        otherInfo = {}
        story = ""
        imdb = cItem.get("imdb", "")
        mediaType = cItem.get("meta_type", "")
        sts, data = self.getPage(_pageUrl(cItem["url"]))
        if sts:
            story = self._story(data)
            for key, label in (("original_title", "Originaltitel"), ("director", "Regisseur"), ("actors", "Schauspieler")):
                value = self._detailField(data, label)
                if value:
                    otherInfo[key] = value
            # <i class="dsep">|</i>2027<i class="dsep">|</i>92<!-- --> Min.
            released = self.cm.ph.getSearchGroups(data, r"</i>(\d{4})<i")[0]
            if released:
                otherInfo["released"] = released
            duration = self.cm.ph.getSearchGroups(data, r"</i>(\d+)<!-- --> Min\.")[0]
            if duration:
                otherInfo["duration"] = "%s min" % duration
            kind, target = self._resolveMeineCloud(data)
            if kind:
                mediaType = mediaType or ("tv" if kind == "series" else "movie")
                imdb = imdb or (target if kind == "series" else MeineCloud.imdbFromUrl(target))
        mediaType = mediaType or "movie"
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            metaTitle = cItem.get("meta_title", "") or cItem.get("s_title", "")
            if not meta and metaTitle:
                meta = getMeta(mediaType, metaTitle, cItem.get("meta_year", "") or otherInfo.get("released", ""))
        except Exception:
            printExc()
        info = dict(meta.get("info", {}))
        info.update(otherInfo)  # the site's own fields win (German cast names, running time of this cut)
        plot = meta.get("plot", "")
        # an episode row carries its own description (from the player API)
        text = (cItem.get("desc", "") if cItem.get("stream_type") == "mc_episode" else "") or story or plot or cItem.get("desc", "")
        if plot and text != plot and cItem.get("stream_type") != "mc_episode":
            text = "%s[/br][/br]%s" % (text, plot) if text else plot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": self.cleanHtmlStr(cItem.get("title", "")), "text": self.cleanHtmlStr(text), "images": [{"title": "", "url": self.getFullIconUrl(icon)}], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: name[%s], category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printDBG("HDFilme.handleService: unknown category [%s]" % category)
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(WatchedFlagHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, HDFilme(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = self.host.watchedHelper

    def _setWatchedStateForSeasonItem(self, seasonItem, action):
        try:
            seasonId = str(seasonItem.get("season_id", "") or "").strip()
            seasonKey = self.host._getWatchedKeyForItem(seasonItem)
            if seasonKey == "":
                return False
            changed = False
            for episodeItem in self.host.cacheSeasons.get(seasonId, []):
                episodeKey = self.host._getWatchedKeyForItem(episodeItem)
                if episodeKey == "":
                    continue
                if action == "set_watched_flag":
                    changed = self.watchedHelper.markItemWatched(episodeItem, episodeKey) or changed
                else:
                    changed = self.watchedHelper.unmarkItemWatched(episodeItem, episodeKey) or changed
            if action == "set_watched_flag":
                changed = self.watchedHelper.markItemWatched(seasonItem, seasonKey) or changed
            else:
                changed = self.watchedHelper.unmarkItemWatched(seasonItem, seasonKey) or changed
            return changed
        except Exception:
            printExc()
            return False

    def _setWatchedStateForSeriesItem(self, seriesItem, action):
        try:
            url = str(seriesItem.get("url", "") or "").strip()
            if url == "":
                return False
            changed = False
            if str(self.host.currItem.get("url", "") or "").strip() == url:
                for seasonId in list(self.host.cacheSeasons):
                    changed = self._setWatchedStateForSeasonItem(self.host._buildSeasonItem(seasonId), action) or changed
            seriesKey = self.host._getWatchedKeyForItem(seriesItem)
            if seriesKey == "":
                return changed
            if action == "set_watched_flag":
                changed = self.watchedHelper.markItemWatched(seriesItem, seriesKey) or changed
            else:
                changed = self.watchedHelper.unmarkItemWatched(seriesItem, seriesKey) or changed
            return changed
        except Exception:
            printExc()
            return False

    def _refreshParentStateAfterAction(self, item, action):
        try:
            if not isinstance(item, dict):
                return
            category = str(item.get("category", "") or "").strip()
            itemType = str(item.get("type", "") or "").strip()
            if category == "list_episodes" or itemType in ("video", "audio"):
                self.host._propagateEpisodeWatchedState(item)
            elif category == "list_seasons":
                url = str(item.get("url", "") or "").strip()
                if url != "" and str(self.host.currItem.get("url", "") or "").strip() == url:
                    seriesParent = {"category": "list_seasons", "url": url}
                    seasonChildren = [self.host._buildSeasonItem(sid) for sid in self.host.cacheSeasons]
                    self.watchedHelper.updateParentWatchedState(seriesParent, seasonChildren, self.host._getWatchedKeyForItem)
        except Exception:
            printExc()

    def performCustomAction(self, privateData):
        ret = self.watchedHelper.performCustomAction(privateData)
        if ret.status == RetHost.OK:
            self.refreshAfterWatchedFlagChange = True
            try:
                action = privateData.get("action", "")
                if action in ("unset_watched_flag", "set_watched_flag"):
                    idx = privateData.get("item_index", -1)
                    item = self.host.currList[idx] if 0 <= idx < len(self.host.currList) else {}
                    category = item.get("category", "")
                    if category == "list_episodes":
                        self._setWatchedStateForSeasonItem(item, action)
                    elif category == "list_seasons":
                        self._setWatchedStateForSeriesItem(item, action)
                    self._refreshParentStateAfterAction(item, action)
                    seriesUrl = str(item.get("url", "") or "").strip()
                    if seriesUrl != "" and str(self.host.currItem.get("url", "") or "").strip() == seriesUrl:
                        self.watchedHelper.recomputeAllGroupsWatched(self.host.cacheSeasons, self.host._getWatchedKeyForItem, self.host._buildSeasonItem)
            except Exception:
                printExc()
        return ret

    def withArticleContent(self, cItem):
        # episode rows (meinecloud) carry no category, getArticleContent knows them by their stream_type
        return cItem.get("category", "") in ["video", "list_seasons", "list_episodes"] or cItem.get("stream_type") == "mc_episode"
