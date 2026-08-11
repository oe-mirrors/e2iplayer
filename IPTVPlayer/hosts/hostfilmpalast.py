# -*- coding: utf-8 -*-
# Last Modified: 06.08.2026 - Centralized watched helper integration incl. favourite hash sync, Custom menu action handling (mark/unmark watched) added, sidecar/MKV article request now skipped when both are disabled - Kamikaze24
###################################################
# LOCAL import
###################################################
from Components.config import config, ConfigYesNo, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, RetHost
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecar, sidecarFromUrlMeta, decorateUrl, decorateCachedLinkItems, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhostmixin import WatchedFlagHostMixin
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled

###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin

###################################################
# FOREIGN import
###################################################
###################################################

config.plugins.iptvplayer.filmpalast_mkv = ConfigYesNo(default=True)


def GetConfigList():
    # "Allow watched flag to be set" / "The color of the viewed item" / "Create sidecar
    # files" now live in the global E2iPlayer settings (components/iptvconfigmenu.py),
    # not per-host
    optionList = [
        getConfigListEntry(_("Create MKV") + ":", config.plugins.iptvplayer.filmpalast_mkv),
    ]
    return optionList


def gettytul():
    return "https://filmpalast.to/"


class FilmPalastTo(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "filmpalast.to", "cookie": "filmpalast.to.cookie"})
        self.USER_AGENT = "Mozilla/5.0"
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "text/html"}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest"})

        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = "https://filmpalast.to/themes/downloadarchive/images/logo.png"
        self.MAIN_URL = None
        self.cacheSeries = {}
        self.cacheSeasons = {}
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper('filmpalastto')

    def selectDomain(self):
        self.MAIN_URL = "https://filmpalast.to/"
        self.MAIN_CAT_TAB = [
            {"category": "list_items", "title": _("Main"), "url": self.getMainUrl()},
            {"category": "movies", "title": _("Movies")},
            {"category": "series", "title": _("Series")},
        ] + self.searchItems()

        self.MOVIES_CAT_TAB = [
            {"category": "list_items", "title": _("New"), "url": self.getFullUrl("/movies/new")},
            {"category": "list_items", "title": _("Top"), "url": self.getFullUrl("/movies/top")},
            {"category": "movies_cats", "title": _("Categories"), "url": self.getFullUrl("/movies/new")},
            {"category": "movies_abc", "title": _("Alphabetically"), "url": self.getFullUrl("/movies/new")},
        ]

        self.SERIES_CAT_TAB = [
            {"category": "list_items", "title": _("--All Episodes--"), "url": self.getFullUrl("/serien/view")},
            {"category": "series_abc", "title": _("Alphabetically"), "url": self.getFullUrl("/serien/view")},
        ]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == "":
            return ""
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {"Cookie": cookieHeader, "User-Agent": self.USER_AGENT})

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            itemType = cItem.get("type", "")
            category = cItem.get("category", "")
            if itemType in ["video", "audio"]:
                url = str(cItem.get("url", "") or "").strip()
                if url != "":
                    return "url:%s" % url
                return ""
            if category == "explore_item":
                url = str(cItem.get("url", "") or "").strip()
                if url != "":
                    return "url:%s" % url
                return ""
            if category == "list_episodes":
                baseUrl = str(cItem.get("series_url", "") or "").strip() or str(cItem.get("url", "") or "").strip()
                seasonId = str(cItem.get("season_num", "") or "").strip() or str(cItem.get("f_season", "") or "").strip()
                if baseUrl != "" and seasonId != "":
                    return "season:%s|%s" % (baseUrl, seasonId)
                return ""
            if category == "list_seasons":
                url = str(cItem.get("url", "") or "").strip()
                if url != "":
                    return "series:%s" % url
                return ""
            return ""
        except Exception:
            printExc()
        return ""

    def _listLinks(self, cItem, m1, m2):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []

        retTab = []
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, m2)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<a", "</a>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, """href=['"]([^'^"]+?)['"]""")[0])
            title = self.cleanHtmlStr(item)
            retTab.append({"title": title, "url": url})
        return retTab

    def listSeriesABC(self, cItem, nextCategory):
        printDBG("FilmPalastTo.listSeriesABC |%s|" % cItem)
        self.cacheSeries = {"letters": []}
        tab = self._listLinks(cItem, 'id="serien"', "</ul>")
        for item in tab:
            letter = item["title"][0]
            if not letter.isalpha():
                letter = "#"
            if letter not in self.cacheSeries:
                self.cacheSeries["letters"].append(letter)
                self.cacheSeries[letter] = []
                params = dict(cItem)
                params.update({"category": nextCategory, "title": letter, "f_letter": letter})
                self.addDir(params)
            self.cacheSeries[letter].append(item)

        params = dict(cItem)
        params.update({"category": nextCategory, "title": _("--All--"), "f_letter": ""})
        self.currList.insert(0, params)

    def listSeriesByLetter(self, cItem, nextCategory):
        printDBG("FilmPalastTo.listSeriesByLetter |%s|" % cItem)

        if "" == cItem.get("f_letter", ""):
            letters = self.cacheSeries["letters"]
        else:
            letters = [cItem["f_letter"]]

        for letter in letters:
            for item in self.cacheSeries[letter]:
                params = dict(cItem)
                params.update(item)
                params["icon"] = self.getFullIconUrl("/files/movies/450/%s.jpg" % item["url"].split("/")[-1])
                params["category"] = nextCategory
                self.addDir(params)

    def listCats(self, cItem, nextCategory, m1, m2):
        printDBG("FilmPalastTo.listCats |%s|" % cItem)

        tab = self._listLinks(cItem, m1, m2)
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params["category"] = nextCategory
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("FilmPalastTo.listItems |%s|" % cItem)

        url = cItem["url"]
        page = cItem.get("page", 1)

        if "?" not in url:
            if page > 1:
                if not url.endswith("/"):
                    url += "/"
                if "/search/" not in url:
                    url += "page/"
                url += str(page)

        sts, data = self.getPage(url)
        if not sts:
            return

        if "vorw&auml;rts&nbsp;+" in data:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<article", "</article>")
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, """href=['"]([^'^"]+?)['"]""")[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r"""src=['"]([^'^"]+?\.jpe?g)['"]""")[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, """title=['"]([^'^"]+)['"]""")[0])

            # get desc
            sts, tmp = self.cm.ph.getDataBeetwenMarkers(item, '<ul class="clearfix">', "</ul>")
            if not sts:
                rating = item.count("/star_on.png")
                desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<small", "</small>")[1])
                desc = "%d/10 %s" % (rating, desc)
            else:
                desc = []
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, "<li", "</li>")
                for t in tmp:
                    t = t.split("</span>")
                    for t1 in t:
                        t1 = self.cleanHtmlStr(t1)
                        if t1 != "":
                            desc.append(t1)
                desc = "[/br]".join(desc)
            # get desc end

            params = dict(cItem)
            params.update({"good_for_fav": True, "category": nextCategory, "title": title, "url": url, "icon": icon, "desc": desc})
            self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "page": page + 1})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("FilmPalastTo.listEpisodes")
        seasonId = cItem.get("f_season", "")
        tab = self.cacheSeasons.get(seasonId, [])
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params.pop("isWatched", None)
            # cItem is the season item (category="list_episodes") - clear it here so this
            # episode isn't mistaken for its own season/series container elsewhere
            params.pop("category", None)
            # params['icon'] = self.getFullIconUrl('/files/movies/450/%s.jpg' % item['url'].split('/')[-1])
            self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            self.addVideo(params)

    def _buildSeasonItem(self, seasonId):
        return {"category": "list_episodes", "url": self.currItem.get("url", ""), "f_season": seasonId}

    def _propagateEpisodeWatchedState(self, item):
        # recomputes season+series state right when an episode's own watched/started
        # state changes, instead of relying on exploreItem() being re-run later - the
        # "refresh from cache" shortcut used after playback/marking often skips that
        try:
            if not isinstance(item, dict):
                return
            seasonId = str(item.get("season_num", "") or item.get("f_season", "") or "").strip()
            if seasonId == "":
                return
            seriesUrl = str(item.get("series_url", "") or item.get("url", "") or self.currItem.get("url", "") or "").strip()
            seasonParent = {"category": "list_episodes", "url": seriesUrl, "series_url": seriesUrl, "season_num": seasonId}
            seasonEpisodes = self.cacheSeasons.get(seasonId, [])
            if seasonEpisodes:
                self.watchedHelper.updateParentWatchedState(seasonParent, seasonEpisodes, self._getWatchedKeyForItem)
            if seriesUrl != "":
                seriesParent = {"category": "list_seasons", "url": seriesUrl}
                seasonChildren = [{"category": "list_episodes", "url": seriesUrl, "series_url": seriesUrl, "season_num": str(sid)} for sid in list(self.cacheSeasons.keys())]
                self.watchedHelper.updateParentWatchedState(seriesParent, seasonChildren, self._getWatchedKeyForItem)
        except Exception:
            printExc()

    def exploreItem(self, cItem, nextCategory):
        printDBG("FilmPalastTo.exploreItem")
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="staffelNav', "</ul>")[1]
        if 'data-id="staffId' not in data:
            params = dict(cItem)
            params.pop("isWatched", None)
            self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            self.addVideo(params)
            return
        if "" != self.cm.ph.getSearchGroups(cItem["title"] + " ", r"""\s([Ss][0-9]+[Ee][0-9]+)\s""")[0]:
            params = dict(cItem)
            params.pop("isWatched", None)
            self.watchedHelper.updateHostItemFlag(self, params, self._getWatchedKeyForItem)
            self.addVideo(params)
        self.cacheSeasons = {}
        seasonTitles = {}
        seasonParams = {}
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="staffelNav', "</ul>")[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, "<li", "</li>")
        for item in tmp:
            seasonId = self.cm.ph.getSearchGroups(item, """data-id=['"]([^"^']+?)['"]""")[0]
            title = self.cleanHtmlStr(item)
            seasonTitles[seasonId] = title
        sp = '<div class="staffelWrapperLoop'
        tmp = self.cm.ph.getDataBeetwenMarkers(data, sp, '<a name="comments_view">', False)[1]
        tmp = tmp.split(sp)
        for item in tmp:
            seasonId = self.cm.ph.getSearchGroups(item, """id=['"]([^"^']+?)['"]""")[0]
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, "<a", "</a>")
            for it in item:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(it, """href=['"]([^'^"]+?)['"]""")[0])
                if not url:
                    continue
                title = self.cleanHtmlStr(it)
                if seasonId not in self.cacheSeasons:
                    self.cacheSeasons[seasonId] = []
                    params = dict(cItem)
                    params.pop("isWatched", None)
                    params.update({"good_for_fav": False, "category": nextCategory, "title": seasonTitles.get(seasonId, seasonId), "f_season": seasonId})
                    params["isWatched"] = False
                    seasonParams[seasonId] = params
                    self.addDir(params)
                episodeParams = {"good_for_fav": True, "title": title, "url": url, "type": "video", "series_url": cItem.get("url", ""), "season_num": str(seasonId)}
                self.cacheSeasons[seasonId].append(episodeParams)

        for seasonId, seasonEpisodes in self.cacheSeasons.items():
            if seasonId not in seasonParams:
                continue
            self.watchedHelper.updateParentWatchedState(seasonParams[seasonId], seasonEpisodes, self._getWatchedKeyForItem)

        seriesItem = {"category": "list_seasons", "url": cItem.get("url", "")}
        seriesKey = self._getWatchedKeyForItem(seriesItem)
        if seriesKey != "":
            self.watchedHelper.updateParentWatchedState(seriesItem, [seasonParams[seasonId] for seasonId in seasonParams], self._getWatchedKeyForItem)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmPalastTo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("/search/title/%s" % urllib_quote(searchPattern))
        self.listItems(cItem, "explore_item")

    def getLinksForVideo(self, cItem):
        printDBG("FilmPalastTo.getLinksForVideo [%s]" % cItem)
        # NOTE: marking the item "started" happens later, in iptvplayerwidget.py's
        # playVideo() - not here. This method resolves links for both actually
        # streaming AND downloading, and can also fail/return nothing, so marking
        # here would (and used to) tag failed attempts and downloads as "started" too.
        linksTab = []
        sidecarTxt = ""
        sidecarImg = ""
        sidecarEnabled = IsSidecarEnabled()
        imdb_rating = cItem.get("imdb_rating", "")
        sidecarYear = ""
        sidecarDuration = ""
        sidecarGenre = ""

        if sidecarEnabled or config.plugins.iptvplayer.filmpalast_mkv.value:
            try:
                article = self.getArticleContent(cItem)
                if article and isinstance(article, list):
                    articleItem = article[0]
                    sidecarTxt = articleItem.get("text", "")
                    images = articleItem.get("images", [])
                    if images and images[0].get("url"):
                        sidecarImg = images[0].get("url")

                    otherInfo = articleItem.get("other_info", {})
                    if not imdb_rating or imdb_rating == "-":
                        imdb_rating = otherInfo.get("imdb_rating", "")
                    sidecarYear = otherInfo.get("year", "") or otherInfo.get("released", "")
                    sidecarDuration = otherInfo.get("duration", "")
                    sidecarGenre = otherInfo.get("genre", "")
            except Exception:
                printExc("getArticleContent for sidecar failed")

        if not sidecarTxt:
            sidecarTxt = cItem.get("desc", "")
        if not sidecarImg:
            sidecarImg = cItem.get("icon", "")

        sidecarLines = []

        if imdb_rating and imdb_rating != "-":
            sidecarLines.append(u"IMDb: %s" % imdb_rating)

        infoLine = []
        if sidecarYear:
            infoLine.append(u"Jahr: %s" % sidecarYear)
        if sidecarDuration:
            infoLine.append(u"Spielzeit: %s" % sidecarDuration)
        if infoLine:
            sidecarLines.append(u" / ".join(infoLine))

        if sidecarGenre:
            sidecarLines.append(sidecarGenre)

        if sidecarLines:
            prefix = u"\n".join(sidecarLines)
            if sidecarTxt:
                if not sidecarTxt.startswith("IMDb:"):
                    sidecarTxt = prefix + u"\n\n" + sidecarTxt
            else:
                sidecarTxt = prefix

        sidecar = buildSidecar(sidecarEnabled, sidecarTxt, sidecarImg)

        linksTab = self.cacheLinks.get(cItem["url"], [])
        if len(linksTab) > 0:
            return decorateCachedLinkItems(linksTab, sidecar)

        sts, data = self.getPage(cItem["url"], self.defaultParams)
        if not sts:
            return []

        data = ph.findall(data, ("<ul", ">", "currentStreamLinks"), "</ul>", flags=0)
        for item in data:
            printDBG("FilmPalastTo.getLinksForVideo item [%s]" % item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, """href=['"]([^"^']+?)['"]""")[0])
            title = ph.clean_html(ph.find(item, ("<p", ">"), "</p>", flags=0)[1])
            if title == "":
                title = ph.clean_html(item)

            url = decorateUrl(url, referer=cItem["url"], sidecar=sidecar)
            linksTab.append({"name": title, "url": url, "need_resolve": 1})

        if len(linksTab):
            self.cacheLinks[cItem["url"]] = linksTab

        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("FilmPalastTo.getVideoLinks [%s]" % videoUrl)
        linksTab = []

        videoUrl = strwithmeta(videoUrl)

        cfgSidecarEnabled = IsSidecarEnabled()
        cfgMkvEnabled = config.plugins.iptvplayer.filmpalast_mkv.value
        sidecar = sidecarFromUrlMeta(videoUrl, cfgSidecarEnabled)

        def _addFinalMeta(videoLinks):
            return decorateResolvedLinkItems(videoLinks, sidecar, cfgMkvEnabled)

        key = videoUrl.meta.get("links_key", "")
        if key != "":
            if key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if self.cacheLinks[key][idx]["url"] == videoUrl and not self.cacheLinks[key][idx]["name"].startswith("*"):
                        self.cacheLinks[key][idx]["name"] = "*" + self.cacheLinks[key][idx]["name"]

        data_id = videoUrl.meta.get("data_id", "")
        data_stamp = videoUrl.meta.get("data_stamp", "")

        if data_id and data_stamp:
            # sts, data = self.getPage(key, self.defaultParams)
            # if not sts: return []

            url = self.getFullUrl("/stream/%s/%s" % (data_id, data_stamp))
            urlParams = dict(self.defaultParams)
            urlParams["header"] = dict(self.AJAX_HEADER)
            urlParams["header"]["Referer"] = key
            sts, data = self.getPage(url, urlParams, {"streamID": data_id})
            if not sts:
                return []

            try:
                data = json_loads(data)
                url = data.get("url", "")
                if self.cm.isValidUrl(url):
                    return _addFinalMeta(self.up.getVideoLinkExt(url))
                SetIPTVPlayerLastHostError(data["msg"])
            except Exception:
                printExc()
        else:
            linksTab = _addFinalMeta(self.up.getVideoLinkExt(videoUrl))

        return linksTab

    def getArticleContent(self, cItem):
        printDBG("FilmPalastTo.getArticleContent [%s]" % cItem)
        retTab = []

        otherInfo = {}

        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="content" role="main">', "</ul>")[1]

        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, "<h2", "</h2>")[1])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="hidden', "</span>")[1])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, r"""src=['"]([^"^']+\.jpe?g)['"]""")[0])

        tmpTab = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "enre</p>", "</li>", False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, "<a", "</a>")
        for t in tmp:
            tmpTab.append(self.cleanHtmlStr(t))
        if len(tmpTab):
            otherInfo["genre"] = ", ".join(tmpTab)

        tmpTab = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "chauspieler</p>", "</li>", False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, "<a", "</a>")
        for t in tmp:
            tmpTab.append(self.cleanHtmlStr(t))
        if len(tmpTab):
            otherInfo["actors"] = ", ".join(tmpTab)

        tmpTab = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "chöpfer</p>", "</li>", False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, "<a", "</a>")
        for t in tmp:
            tmpTab.append(self.cleanHtmlStr(t))
        if len(tmpTab):
            otherInfo["creators"] = ", ".join(tmpTab)

        tmpTab = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "egie</p>", "</li>", False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, "<a", "</a>")
        for t in tmp:
            tmpTab.append(self.cleanHtmlStr(t))
        if len(tmpTab):
            otherInfo["director"] = ", ".join(tmpTab)

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, "hortinfos</p>", "</strong>", False)[1])
        if tmp != "":
            otherInfo["views"] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, "Ver&ouml;ffentlicht:", "<", False)[1])
        if tmp != "":
            otherInfo["released"] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, "<em>", "</em>", False)[1])
        if tmp != "":
            otherInfo["duration"] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, "Imdb:", "<", False)[1])
        if tmp != "":
            otherInfo["imdb_rating"] = tmp

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="average">', "<span", False)[1])
        if tmp != "":
            otherInfo["rating"] = tmp

        if title == "":
            title = cItem["title"]
        if desc == "":
            desc = cItem.get("desc", "")
        if icon == "":
            icon = cItem.get("icon", self.DEFAULT_ICON_URL)

        return [{"title": self.cleanHtmlStr(title), "text": self.cleanHtmlStr(desc), "images": [{"title": "", "url": self.getFullUrl(icon)}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            # rm(self.COOKIE_FILE)
            self.selectDomain()

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        mode = self.currItem.get("mode", "")

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

        # MAIN MENU
        if name is None:
            self.listsTab(self.MAIN_CAT_TAB, {"name": "category"})
        elif "movies" == category:
            self.listsTab(self.MOVIES_CAT_TAB, self.currItem)
        elif "movies_cats" == category:
            self.listCats(self.currItem, "list_items", 'id="genre"', "</ul>")
        elif "movies_abc" == category:
            self.listCats(self.currItem, "list_items", 'id="movietitle"', "</ul>")

        elif "series" == category:
            self.listsTab(self.SERIES_CAT_TAB, self.currItem)
        elif "series_abc" == category:
            self.listSeriesABC(self.currItem, "series_by_letter")
        elif "series_by_letter" == category:
            self.listSeriesByLetter(self.currItem, "explore_item")

        elif "list_items" == category:
            self.listItems(self.currItem, "explore_item")
        elif "explore_item" == category:
            self.exploreItem(self.currItem, "list_episodes")
        elif "list_episodes" == category:
            self.listEpisodes(self.currItem)

        # SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        # HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(WatchedFlagHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, FilmPalastTo(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('filmpalastto')

    def _setWatchedStateForSeasonItem(self, seasonItem, action):
        try:
            seasonId = str(seasonItem.get('season_num', '') or seasonItem.get('f_season', '') or '').strip()
            seasonKey = self.host._getWatchedKeyForItem(seasonItem)
            if seasonKey == '':
                return False
            changed = False
            for episodeItem in self.host.cacheSeasons.get(seasonId, []):
                episodeKey = self.host._getWatchedKeyForItem(episodeItem)
                if episodeKey == '':
                    continue
                if action == 'set_watched_flag':
                    changed = self.watchedHelper.markItemWatched(episodeItem, episodeKey) or changed
                else:
                    changed = self.watchedHelper.unmarkItemWatched(episodeItem, episodeKey) or changed
            if action == 'set_watched_flag':
                changed = self.watchedHelper.markItemWatched(seasonItem, seasonKey) or changed
            else:
                changed = self.watchedHelper.unmarkItemWatched(seasonItem, seasonKey) or changed
            return changed
        except Exception:
            printExc()
            return False

    def _setWatchedStateForSeriesItem(self, seriesItem, action):
        try:
            seriesUrl = str(seriesItem.get('url', '') or '').strip()
            if seriesUrl == '':
                return False
            changed = False
            for seasonId in list(self.host.cacheSeasons.keys()):
                seasonItem = {'category': 'list_episodes', 'url': seriesUrl, 'series_url': seriesUrl, 'season_num': str(seasonId)}
                changed = self._setWatchedStateForSeasonItem(seasonItem, action) or changed
            seriesKey = self.host._getWatchedKeyForItem(seriesItem)
            if seriesKey == '':
                return changed
            if action == 'set_watched_flag':
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
            category = str(item.get('category', '') or '').strip()
            if category == 'list_episodes':
                seasonId = str(item.get('season_num', '') or item.get('f_season', '') or '').strip()
                if seasonId != '':
                    seasonParent = dict(item)
                    seasonParent.pop('isWatched', None)
                    seasonEpisodes = self.host.cacheSeasons.get(seasonId, [])
                    if seasonEpisodes:
                        self.watchedHelper.updateParentWatchedState(seasonParent, seasonEpisodes, self.host._getWatchedKeyForItem)
                    seriesUrl = str(item.get('series_url', '') or self.host.currItem.get('url', '') or '').strip()
                    if seriesUrl != '':
                        seriesParent = {'category': 'list_seasons', 'url': seriesUrl}
                        seasonChildren = [{'category': 'list_episodes', 'url': seriesUrl, 'series_url': seriesUrl, 'season_num': str(sid)} for sid in list(self.host.cacheSeasons.keys())]
                        self.watchedHelper.updateParentWatchedState(seriesParent, seasonChildren, self.host._getWatchedKeyForItem)
            elif category == 'list_seasons':
                seriesUrl = str(item.get('url', '') or '').strip()
                if seriesUrl != '':
                    seriesParent = {'category': 'list_seasons', 'url': seriesUrl}
                    seasonChildren = [{'category': 'list_episodes', 'url': seriesUrl, 'series_url': seriesUrl, 'season_num': str(sid)} for sid in list(self.host.cacheSeasons.keys())]
                    self.watchedHelper.updateParentWatchedState(seriesParent, seasonChildren, self.host._getWatchedKeyForItem)
            elif str(item.get('type', '') or '').strip() in ['video', 'audio']:
                # item is a single episode (category is intentionally empty for these,
                # see listEpisodes()) - recompute its season+series from current state
                self.host._propagateEpisodeWatchedState(item)
        except Exception:
            printExc()

    def performCustomAction(self, privateData):
        ret = self.watchedHelper.performCustomAction(privateData)
        if ret.status == RetHost.OK:
            self.refreshAfterWatchedFlagChange = True
            try:
                action = privateData.get('action', '')
                if action in ('unset_watched_flag', 'set_watched_flag'):
                    idx = privateData.get('item_index', -1)
                    item = self.host.currList[idx] if 0 <= idx < len(self.host.currList) else {}
                    category = item.get('category', '')
                    if category == 'list_episodes':
                        self._setWatchedStateForSeasonItem(item, action)
                    elif category == 'list_seasons':
                        self._setWatchedStateForSeriesItem(item, action)
                    self._refreshParentStateAfterAction(item, action)
                    self.watchedHelper.recomputeAllGroupsWatched(self.host.cacheSeasons, self.host._getWatchedKeyForItem, self.host._buildSeasonItem)
            except Exception:
                printExc()
        return ret

    def withArticleContent(self, cItem):
        if "video" == cItem.get("type", "") or "explore_item" == cItem.get("category", ""):
            return True
        return False
