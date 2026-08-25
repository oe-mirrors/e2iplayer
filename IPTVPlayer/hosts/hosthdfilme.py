# -*- coding: utf-8 -*-
#  2025 Team Jogi  #
# Last Modified: 24.08.2026 - Adapted to the new meinecloud.click player backend, restored season/episode navigation, added watched/started flag support, switched to the current hdfilme.win domain

import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase, RetHost
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhostmixin import WatchedFlagHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://hdfilme.win/"


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
            {"category": "list_genres", "title": "Genres"},
            {"category": "list_year", "title": _("Year")},
            {"category": "list_country", "title": _("Country")}] + self.searchItems()

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
                streamUrl = str(cItem.get("stream_url", "") or "").strip()
                if url != "" and streamUrl != "":
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
        try:
            if not isinstance(item, dict):
                return
            seasonId = str(item.get("season_id", "") or "").strip()
            url = str(item.get("url", "") or self.currItem.get("url", "") or "").strip()
            if seasonId == "" or url == "":
                return
            seasonParent = self._buildSeasonItem(seasonId)
            seasonEpisodes = self.cacheSeasons.get(seasonId, [])
            if seasonEpisodes:
                self.watchedHelper.updateParentWatchedState(seasonParent, seasonEpisodes, self._getWatchedKeyForItem)
            seasonChildren = [self._buildSeasonItem(sid) for sid in self.cacheSeasons]
            if seasonChildren:
                seriesParent = {"category": "list_seasons", "url": url}
                self.watchedHelper.updateParentWatchedState(seriesParent, seasonChildren, self._getWatchedKeyForItem)
        except Exception:
            printExc()

    def listItems(self, cItem):
        printDBG("HDFilme.listItems |%s|" % cItem)
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = re.findall('nav_ext">.*?next">.*?href="([^"]+)', data, re.DOTALL)
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="item relative', 'class="absolute')
        if not items:
            items = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="pages">', "<svg")

        for item in items:
            desc = ""
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'data-src="([^"]+)')[0])
            duration = self.cm.ph.getSearchGroups(item, r"<span>(\d+ min)</span>")
            year = self.cm.ph.getSearchGroups(item, r"<span>(\d{4})</span>")
            if year:
                desc += "Jahr: %s \n" % year[0]
            if duration:
                desc += "Dauer: %s" % duration[0]
            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0]
            if not title:
                title = self.cm.ph.getSearchGroups(item, "<strong>(.*?)</strong>")[0]
            title = title.split(" &#8211;")[0]
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_seasons", "title": self.cleanHtmlStr(title), "url": url, "icon": icon, "desc": desc})
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

    def listSeasons(self, cItem):
        printDBG("HDFilme.listSeasons |%s|" % cItem)
        url = cItem["url"]
        icon = cItem["icon"]
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
        sts, data = self.getPage(target)
        if not sts:
            return
        tabs = self.cm.ph.getDataBeetwenMarkers(data, 'class="_stabs"', 'class="_now"', False)[1]
        seasons = re.findall(r'data-season="(\d+)">\s*(\S+)', tabs)
        seasonBlocks = data.split('class="_season-eps')
        del seasonBlocks[0]
        blocksById = {}
        for block in seasonBlocks:
            blockId = self.cm.ph.getSearchGroups(block, r'data-season="(\d+)"')[0]
            if blockId != "":
                blocksById[blockId] = block
        self.cacheSeasons = {}
        seasonParams = {}
        for seasonId, seasonLabel in seasons:
            episodes = []
            for link, label in re.findall(r'data-link="([^"]+)"\s*data-label="([^"]+)"', blocksById.get(seasonId, "")):
                episodes.append({"type": "video", "url": url, "title": self.cleanHtmlStr(label), "icon": icon, "desc": desc, "stream_url": link, "stream_type": "direct", "season_id": seasonId})
            self.cacheSeasons[seasonId] = episodes
            title = cItem["title"] + " - " + seasonLabel
            params = dict(cItem)
            params.pop("isWatched", None)
            params.pop("isStarted", None)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": url, "icon": icon, "desc": desc, "season_id": seasonId})
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
        for item in self.cacheSeasons.get(seasonId, []):
            params = dict(item)
            self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            self.addVideo(params)

    def listValue(self, cItem, v):
        printDBG("HDFilme.Value |%s|" % cItem)
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, ">%s<" % v, "<div class")
        data = re.findall('href="([^"]+).*?>([^<]+)', data[0], re.DOTALL)
        for url, title in data:
            if "ino" in title or "erien" in title or "chst" in title:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
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
        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("HDFilme.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("HDFilme.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0]) or cItem.get("desc", "")
        actors = self.cm.ph.getAllItemsBeetwenMarkers(data, "Schauspieler:", "</li>")
        if actors:
            names = re.findall('">([^<]+)', actors[0], re.DOTALL)
            if names:
                otherInfo["actors"] = ", ".join(names)
        released = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<span>(\d{4})</span>")[0])
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
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
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
            self.listValue(self.currItem, "Genre")
        elif category == "list_year":
            self.listValue(self.currItem, "Jahres")
        elif category == "list_country":
            self.listValue(self.currItem, "Land")
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(WatchedFlagHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, HDFilme(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("hdfilme")

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
                    seasonItem = self.host._buildSeasonItem(seasonId)
                    changed = self._setWatchedStateForSeasonItem(seasonItem, action) or changed
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
            if category == "list_episodes":
                seasonId = str(item.get("season_id", "") or "").strip()
                url = str(item.get("url", "") or "").strip()
                if seasonId != "" and url != "":
                    seasonParent = dict(item)
                    seasonParent.pop("isWatched", None)
                    seasonEpisodes = self.host.cacheSeasons.get(seasonId, [])
                    if seasonEpisodes:
                        self.watchedHelper.updateParentWatchedState(seasonParent, seasonEpisodes, self.host._getWatchedKeyForItem)
                    seriesParent = {"category": "list_seasons", "url": url}
                    seasonChildren = [self.host._buildSeasonItem(sid) for sid in self.host.cacheSeasons]
                    self.watchedHelper.updateParentWatchedState(seriesParent, seasonChildren, self.host._getWatchedKeyForItem)
            elif category == "list_seasons":
                url = str(item.get("url", "") or "").strip()
                if url != "" and str(self.host.currItem.get("url", "") or "").strip() == url:
                    seriesParent = {"category": "list_seasons", "url": url}
                    seasonChildren = [self.host._buildSeasonItem(sid) for sid in self.host.cacheSeasons]
                    self.watchedHelper.updateParentWatchedState(seriesParent, seasonChildren, self.host._getWatchedKeyForItem)
            elif str(item.get("type", "") or "").strip() in ["video", "audio"]:
                self.host._propagateEpisodeWatchedState(item)
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
