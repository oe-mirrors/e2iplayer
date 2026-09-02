# -*- coding: utf-8 -*-
# Last Modified: 25.08.2026 - strip the leading "S<n> E<n>" NUMBERS from the site's raw episode label and keep whatever separator character the site itself already uses (dash or em-dash) untouched, instead of re-building a custom separator; removed the unnecessary EM_DASH/EN_DASH constants and literal-unicode-escape decoding machinery from the previous iteration.

import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase, RetHost
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhostmixin import WatchedFlagHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import extractNum, formatSxxExx, stripLeadingSxxExx
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized


def GetConfigList():
    return []


def gettytul():
    return "https://hdfilme.win/"


def _parseLeadingSxEx(label):
    """Detect a leading 'S1 E1' / 'S01E01' style tag inside a raw episode label; returns (seasonNum, episodeNum) or (None, None)."""
    m = re.match(r"\s*S\s*(\d+)\s*E\s*(\d+)", label, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _trimTrailingDashPart(title):
    """Drop a trailing ' – <type>' marker the listing appends after the real title (en/em dash
    only, never a plain hyphen). Runs on already-HTML-decoded text so it works whether the site
    emits a literal dash or the &#8211; entity."""
    return re.split(r"\s+[–—]\s*", title, maxsplit=1)[0].strip()


class HDFilme(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "HDFilme", "cookie": "HDFilme.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = gettytul() + "templates/hdfilme/images/apple-touch-icon.png"
        self.MAIN_URL = gettytul()
        self.cacheSeasons = {}
        self.watchedHelper = IPTVWatchedHelper("hdfilme")
        self.MENU = [
            {"category": "list_items", "title": _("New"), "url": self.getFullUrl("filme1/")},
            {"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("kinofilme/")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serien/")},
            {"category": "list_genres", "title": "Genres"}] + self.searchItems()

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
                url = str(cItem.get("url", "") or "").strip()
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
        return {"category": "list_episodes", "url": self.currItem.get("url", ""), "season_id": seasonId}

    def _propagateEpisodeWatchedState(self, item):
        """Recompute the season-parent and series-parent watched state for an episode-ish item
        (an episode video, or a list_episodes season node). No-op for anything without a season."""
        try:
            if not isinstance(item, dict):
                return
            seasonId = str(item.get("season_id", "") or "").strip()
            url = str(item.get("url", "") or self.currItem.get("url", "") or "").strip()
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

    def listItems(self, cItem):
        printDBG("HDFilme.listItems |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        if "Fatal error: Uncaught" in data[:2000]:
            SetIPTVPlayerLastHostError(_("The website returned a server error for this request."))
            return
        nextPage = re.findall('nav_ext">.*?next">.*?href="([^"]+)', data, re.DOTALL)
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="item relative', 'class="absolute')
        if not items:
            items = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="pages">', "<svg")
        for item in items:
            itemUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0]
            if not title:
                title = self.cm.ph.getSearchGroups(item, '<strong>(.*?)</strong>')[0]
            title = _trimTrailingDashPart(self.cleanHtmlStr(title))
            if not title or not self.cm.isValidUrl(itemUrl):
                continue
            desc = ""
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'data-src="([^"]+)')[0])
            duration = self.cm.ph.getSearchGroups(item, r'<span[^>]*>(\d+ min)</span>')
            year = self.cm.ph.getSearchGroups(item, r'<span[^>]*>(\d{4})</span>')
            if year:
                desc += "Jahr: %s \n" % year[0]
            if duration:
                desc += "Dauer: %s" % duration[0]
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_seasons", "title": title, "url": itemUrl, "icon": icon, "desc": desc})
            self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            self.addDir(params)
        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "url": self.getFullUrl(nextPage[0])})
            self.addDir(params)

    def _resolveMeineCloud(self, data):
        movieUrl = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="(https://meinecloud\.click/movie/[^"]+)"')[0]
        if movieUrl:
            return "movie", movieUrl
        imdb = self.cm.ph.getSearchGroups(data, r"var imdb = '([^']+)'")[0]
        if not imdb:
            return None, None
        sts, jdata = self.getPage("https://meinecloud.click/serials.php?task=check&id_imdb=%s" % imdb)
        if not sts:
            return None, None
        try:
            info = json_loads(jdata)
        except Exception:
            return None, None
        if isinstance(info, dict) and info.get("exists") and info.get("player_url"):
            return "series", info["player_url"]
        fallbackUrl = self.cm.ph.getSearchGroups(data, r"iframe\.src = '([^']+)';")[0]
        if fallbackUrl:
            return "direct", fallbackUrl
        return None, None

    def _buildEpisodesForSeason(self, seasonId, seasonNum, seriesName, url, icon, desc, blocksById):
        episodes = []
        episodeMatches = re.findall(r'data-link="([^"]+)"[^>]*?data-label="([^"]+)"', blocksById.get(seasonId, ""))
        for episodeIndex, (link, label) in enumerate(episodeMatches, start=1):
            cleanLabelRaw = self.cleanHtmlStr(label)
            if not IsMediaNamingNormalized():
                # normalisation off: keep the site's raw episode label
                episodeTitle = "%s - %s" % (seriesName, cleanLabelRaw) if seriesName else cleanLabelRaw
                episodes.append({"type": "video", "url": url, "title": episodeTitle, "icon": icon, "desc": desc, "stream_url": link, "stream_type": "direct", "season_id": seasonId})
                continue
            embeddedSeason, embeddedEpisode = _parseLeadingSxEx(cleanLabelRaw)
            seasonNumForTag = embeddedSeason if embeddedSeason is not None else seasonNum
            episodeNum = embeddedEpisode if embeddedEpisode is not None else episodeIndex
            epTag = formatSxxExx(seasonNumForTag, episodeNum)
            rest = stripLeadingSxxExx(cleanLabelRaw).strip()
            if seriesName:
                episodeTitle = "%s - %s %s" % (seriesName, epTag, rest) if rest else "%s - %s" % (seriesName, epTag)
            else:
                episodeTitle = "%s %s" % (epTag, rest) if rest else epTag
            episodes.append({"type": "video", "url": url, "title": episodeTitle, "icon": icon, "desc": desc, "stream_url": link, "stream_type": "direct", "season_id": seasonId})
        return episodes

    def _loadSeriesCache(self, playerUrl, seriesName, seriesUrl, icon, desc):
        """Fetch the meinecloud player page and (re)populate self.cacheSeasons.
        Returns (seasons, seasonNumsById); seasons is [] on failure."""
        self.cacheSeasons = {}
        seasonNumsById = {}
        sts, data = self.getPage(playerUrl)
        if not sts:
            return [], seasonNumsById
        tabs = self.cm.ph.getDataBeetwenMarkers(data, 'class="_stabs"', 'class="_now"', False)[1]
        seasons = re.findall(r'data-season="(\d+)"[^>]*>\s*(\S+)', tabs)
        seasonBlocks = data.split('class="_season-eps')
        del seasonBlocks[0]
        blocksById = {}
        for block in seasonBlocks:
            blockId = self.cm.ph.getSearchGroups(block, r'data-season="(\d+)"')[0]
            if blockId != "":
                blocksById[blockId] = block
        for seasonIndex, (seasonId, seasonLabelRaw) in enumerate(seasons, start=1):
            seasonNumFromLabel = extractNum(self.cleanHtmlStr(seasonLabelRaw), 0)
            seasonNum = seasonNumFromLabel if seasonNumFromLabel > 0 else seasonIndex
            seasonNumsById[seasonId] = seasonNum
            self.cacheSeasons[seasonId] = self._buildEpisodesForSeason(seasonId, seasonNum, seriesName, seriesUrl, icon, desc, blocksById)
        return seasons, seasonNumsById

    def listSeasons(self, cItem):
        printDBG("HDFilme.listSeasons |%s|" % cItem)
        url = cItem["url"]
        icon = cItem.get("icon", "") or self.DEFAULT_ICON_URL
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0])
        kind, target = self._resolveMeineCloud(data)
        if kind != "series":
            params = dict(cItem)
            params.pop("isWatched", None)
            params.pop("isStarted", None)
            params.update({"good_for_fav": True, "category": "video", "title": cItem["title"], "url": self.getFullUrl(url), "icon": icon, "desc": desc, "stream_url": target, "stream_type": kind or ""})
            self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            self.addVideo(params)
            return
        seriesName = self.cleanHtmlStr(cItem.get("title", "") or "")
        seasons, seasonNumsById = self._loadSeriesCache(target, seriesName, url, icon, desc)
        if not seasons:
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
            params = dict(cItem)
            params.pop("isWatched", None)
            params.pop("isStarted", None)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "icon": icon, "desc": desc, "season_id": seasonId, "series_name": seriesName})
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
        seriesUrl = cItem.get("url", "") or self.currItem.get("url", "")
        if not seriesUrl:
            return
        seriesName = cItem.get("series_name", "")
        if not seriesName:
            seriesName = re.sub(r"\s*-\s*S\d+(?:E\d+)?\s*$", "", self.cleanHtmlStr(cItem.get("title", "") or ""))
        sts, data = self.getPage(seriesUrl)
        if not sts:
            return
        kind, target = self._resolveMeineCloud(data)
        if kind != "series":
            return
        icon = cItem.get("icon", "") or self.DEFAULT_ICON_URL
        desc = cItem.get("desc", "") or self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0])
        self._loadSeriesCache(target, seriesName, seriesUrl, icon, desc)

    def listGenres(self, cItem):
        printDBG("HDFilme.listGenres")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        pos = data.find('class="mr-1">Genre<')
        if pos != -1:
            pos = data.find("dropdown-content", pos)
        if pos == -1:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data[pos:], ">", "</div>", False)[1]
        for url, title in re.findall(r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', block):
            title = self.cleanHtmlStr(title).strip()
            url = self.getFullUrl(url)
            if not title or not self.cm.isValidUrl(url):
                continue
            # the genre dropdown also carries a few plain nav links (Serien, Demnächst, kinofilme)
            if "ino" in title or "erien" in title or "chst" in title:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": url})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HDFilme.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("?story=%s&do=search&subaction=search" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("HDFilme.getLinksForVideo [%s]" % cItem)
        linksTab = []
        streamUrl = cItem.get("stream_url", "")
        if not streamUrl:
            return linksTab

        sidecarEnabled = IsSidecarEnabled()
        extraText = ""
        if sidecarEnabled:
            try:
                article = self.getArticleContent(cItem)
                if article and isinstance(article, list):
                    articleItem = article[0]
                    extraText = articleItem.get("text", "") or ""
                    otherInfo = articleItem.get("other_info", {}) or {}
                    head = [str(otherInfo[k]) for k in ("released", "duration", "actors") if otherInfo.get(k)]
                    if head:
                        extraText = " / ".join(head) + (("\n\n" + extraText) if extraText else "")
            except Exception:
                printExc("HDFilme getArticleContent for sidecar failed")
        sidecar = buildSidecarFromItem(cItem, sidecarEnabled, extraText)

        if cItem.get("stream_type") == "movie":
            sts, data = self.getPage(streamUrl, self.defaultParams)
            if not sts:
                return linksTab
            data = re.findall('data-link="([^"]+)', data, re.DOTALL)
        else:
            data = [streamUrl]
        for url in data:
            if "meinecloud" in url or "player.php" in url:
                continue
            url = "https:" + url if url.startswith("//") else url
            linksTab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        return applySidecarToLinks(linksTab, sidecar)

    def getVideoLinks(self, videoUrl):
        printDBG("HDFilme.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    def getArticleContent(self, cItem):
        printDBG("HDFilme.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0]) or cItem.get("desc", "")
        actors = self.cm.ph.getAllItemsBeetwenMarkers(data, "Schauspieler:", "</li>")
        if actors:
            names = re.findall('>([^<]+)</a>', actors[0], re.DOTALL)
            if names:
                otherInfo["actors"] = ", ".join(names)
        released = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<span[^>]*>(\d{4})</span>')[0])
        if released:
            otherInfo["released"] = released
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(\d+ min)")[0])
        if duration:
            otherInfo["duration"] = duration
        title = cItem["title"]
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        return [{"title": self.cleanHtmlStr(title), "text": self.cleanHtmlStr(desc), "images": [{"url": self.getFullUrl(icon)}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
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
        return cItem.get("category", "") in ["video", "list_seasons", "list_episodes"]
