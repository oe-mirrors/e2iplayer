# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - rewrite of the MOHAMED_OS host for the current site (b.txcima.com, "CimaclubBlocks"
#   card grids with "?page=N" paging, /series/<slug>/ = flat episode list, <post>/watch/ = server list with the
#   embeds in data-url) + paging (First page / Jump / Next page with the last page) / watched flag / downloaded
#   flag / name normalisation / sidecar / moviemeta INFO / favourites.
#   Every server goes to urlparser: 71stream.one / ult4vid.one (parserR2EMBED), megamax mirror and "leech"
#   pages (parserMEGAMAX), ...; a download mirror of the same video as a server is left out.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

# the site moves between mirrors (txcima.com -> b.txcima.com): change only this line
MAIN_URL = "https://b.txcima.com/"


def GetConfigList():
    return []


def gettytul():
    return MAIN_URL


# "مشاهدة فيلم X 2026 مترجم", "مسلسل X الموسم الثاني الحلقة 2 مترجمة", "انمي ...", "برنامج ..."
TITLE_PREFIX_RE = re.compile(r"^(?:مشاهدة\s+)?(?:فيلم|مسلسل|انمي|برنامج|عرض)\s+")
TITLE_SUFFIX_RE = re.compile(r"\s+(?:مترجمة|مترجمه|مترجم|مدبلجة|مدبلجه|مدبلج|كاملة|كامل|اون\s*لاين|HD)$", re.I)
EPISODE_NUM_RE = re.compile(r"\s*(?:الحلقة|حلقة)\s+(\d+)")
SEASON_RE = re.compile(r"\s*الموسم\s+(\d+|الحادي\s+عشر|الثاني\s+عشر|الثالث\s+عشر|الرابع\s+عشر|الخامس\s+عشر|\S+)")
YEAR_RE = re.compile(r"\s+((?:19|20)\d\d)$")
SEASON_WORDS = {"الاول": 1, "الأول": 1, "الثاني": 2, "الثالث": 3, "الرابع": 4, "الخامس": 5, "السادس": 6, "السابع": 7,
                "الثامن": 8, "التاسع": 9, "العاشر": 10}
SEASON_TEENS = {"الحادي": 11, "الثاني": 12, "الثالث": 13, "الرابع": 14, "الخامس": 15}
# the video id in an embed / download url (71stream.one/embed/<id> = /download/<id>, ult4vid.one/en/<id>/watch)
VIDEO_ID_RE = re.compile(r"/([A-Za-z0-9]{8,})(?:/watch)?/?$")


class TaxiElCima(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what identifies a row and is needed to open it again (desc carries the IMDb rating, which changes)
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "season", "episode", "icon",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "taxielcima", "cookie": "taxielcima.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = MAIN_URL
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies/")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("series/")},
                     {"category": "list_items", "title": _("Newest Episodes"), "url": self.getFullUrl("episodes/")},
                     {"category": "list_items", "title": _("TV Shows"), "url": self.getFullUrl("tv/")},
                     {"category": "list_items", "title": _("Anime"), "url": self.getFullUrl("anime/")},
                     {"category": "list_groups", "title": _("Categories"), "url": self.MAIN_URL},
                     {"category": "list_genres", "title": _("Genres"), "url": self.getFullUrl("movies/")}] + self.searchItems()
        self.groupsCache = []

        self.watchedHelper = IPTVWatchedHelper("taxielcima")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url if url else ""
            if cItem.get("category", "") == "tx_series":
                return "series:%s" % url if url else ""
            return ""
        except Exception:
            printExc()
        return ""

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _normUrl(self, url, currUrl=None):
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if url.startswith("//"):
            url = "https:" + url
        # some hrefs / poster paths carry raw Arabic letters: percent-encode them (already encoded ones stay as they are)
        return self.cm.iriToUri(self.getFullUrl(url, currUrl)) if url else ""

    ###################################################
    # titles
    ###################################################
    def _stripTitle(self, title):
        title = TITLE_PREFIX_RE.sub("", self.cleanHtmlStr(title).strip())
        prev = None
        while prev != title:
            prev = title
            title = TITLE_SUFFIX_RE.sub("", title).strip()
        return title

    def _seasonNum(self, word):
        word = word.strip()
        if word.isdigit():
            return int(word)
        parts = word.split()
        if len(parts) == 2 and parts[1] == "عشر":
            return SEASON_TEENS.get(parts[0], 0)
        return SEASON_WORDS.get(word, 0)

    def _parseTitle(self, rawTitle):
        # -> {"title": clean name, "year", "season", "episode"}
        title = self._stripTitle(rawTitle)
        info = {"title": title, "year": "", "season": 0, "episode": 0}
        epMatch = EPISODE_NUM_RE.search(title)
        if epMatch:
            info["episode"] = int(epMatch.group(1))
            title = (title[:epMatch.start()] + title[epMatch.end():]).strip()
        seMatch = SEASON_RE.search(title)
        if seMatch:
            info["season"] = self._seasonNum(seMatch.group(1))
            title = (title[:seMatch.start()] + title[seMatch.end():]).strip()
        title = self._stripTitle(title)
        yMatch = YEAR_RE.search(title)
        if yMatch:
            info["year"] = yMatch.group(1)
            title = title[:yMatch.start()].strip()
        info["title"] = title.strip(" -") or info["title"]
        return info

    def _movieTitle(self, rawTitle, info):
        if IsMediaNamingNormalized():
            return "%s (%s)" % (info["title"], info["year"]) if info["year"] else info["title"]
        return self.cleanHtmlStr(rawTitle)

    def _episodeTitle(self, rawTitle, info):
        if IsMediaNamingNormalized():
            return "%s - %s" % (info["title"], formatSxxExx(info["season"] or 1, info["episode"]))
        return self.cleanHtmlStr(rawTitle)

    def _seriesTitle(self, rawTitle, info):
        if IsMediaNamingNormalized():
            title = info["title"]
            if info["season"]:
                title = "%s - %s %s" % (title, _("Season"), info["season"])
            return "%s (%s)" % (title, info["year"]) if info["year"] else title
        return self.cleanHtmlStr(rawTitle)

    ###################################################
    # lists
    ###################################################
    def _getGroups(self):
        if self.groupsCache:
            return self.groupsCache
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return []
        groups = []
        for gTitle, body in re.findall(r'menu-item-has-children[^>]*>\s*<a href="#">(.*?)</a>\s*<ul class="sub-menu">(.*?)</ul>', data, re.DOTALL):
            gTitle = self.cleanHtmlStr(gTitle)
            links = []
            for url, title in re.findall(r'<a href="([^"#]+)"[^>]*>(.*?)</a>', body, re.DOTALL):
                url = self._normUrl(url)
                title = self.cleanHtmlStr(title)
                if self.cm.isValidUrl(url) and title:
                    links.append((title, url))
            if gTitle and links:
                groups.append((gTitle, links))
        self.groupsCache = groups
        return groups

    def listGroups(self, cItem):
        printDBG("TaxiElCima.listGroups")
        for gTitle, links in self._getGroups():
            params = dict(cItem)
            params.update({"good_for_fav": False, "category": "list_group", "title": gTitle, "group": gTitle})
            self.addDir(params)

    def listGroup(self, cItem):
        printDBG("TaxiElCima.listGroup [%s]" % cItem.get("group", ""))
        for gTitle, links in self._getGroups():
            if gTitle != cItem.get("group"):
                continue
            for title, url in links:
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": url})
                self.addDir(params)

    def listGenres(self, cItem):
        printDBG("TaxiElCima.listGenres")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        # full list in the filter box (<li data-tax="genre">), the "Hotlinks" slider only shows a few
        links = re.findall(r'<li data-tax="genre"[^>]*><a href="([^"]+)">(.*?)</a>', data, re.DOTALL)
        links += re.findall(r'<a href="([^"]+/genre/[^"]+)"[^>]*title="([^"]+)"', data)
        seen = set()
        for url, title in links:
            url = self._normUrl(url)
            title = self.cleanHtmlStr(title)
            if url in seen or not title:
                continue
            seen.add(url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": url})
            self.addDir(params)

    def _addCards(self, cItem, data, currUrl):
        cnt = 0
        seen = set()
        for card in data.split('<div class="SMallBloca"')[1:]:
            url = self._normUrl(self.cm.ph.getSearchGroups(card, r'<a href="([^"]+)"')[0], currUrl).split("#", 1)[0]
            rawTitle = self.cm.ph.getSearchGroups(card, r'<a href="[^"]+" title="([^"]+)"')[0] or self.cm.ph.getSearchGroups(card, r"<h2>(.*?)</h2>")[0]
            rawTitle = self.cleanHtmlStr(rawTitle)
            if not self.cm.isValidUrl(url) or url in seen or not rawTitle:
                continue
            seen.add(url)
            if url.rstrip("/").endswith("-trailer") or "trailer" in rawTitle.lower():
                continue
            icon = self._normUrl(self.cm.ph.getSearchGroups(card, r'data-src="([^"]+)"')[0], currUrl)
            rating = self.cm.ph.getSearchGroups(card, r'class="IMDBRS">.*?<span>([0-9.]+)</span>')[0]
            info = self._parseTitle(rawTitle)
            desc = []
            if info["year"]:
                desc.append(info["year"])
            if rating and rating != "0":
                desc.append("IMDb %s" % rating)
            params = stripPagerKeys(dict(cItem), ("search_pattern",))
            params.update({"good_for_fav": True, "url": url, "icon": icon, "desc": " | ".join(desc), "s_title": info["title"],
                           "meta_title": info["title"], "meta_year": info["year"]})
            if "/series/" in url:
                params.update({"category": "tx_series", "title": self._seriesTitle(rawTitle, info), "meta_type": "tv",
                               "season": str(info["season"] or "")})
                self.addDir(params)
            elif info["episode"]:
                params.update({"category": "tx_episode", "title": self._episodeTitle(rawTitle, info), "meta_type": "tv",
                               "season": str(info["season"] or 1), "episode": str(info["episode"])})
                self.addVideo(params)
            else:
                params.update({"category": "tx_movie", "title": self._movieTitle(rawTitle, info), "meta_type": "movie"})
                self.addVideo(params)
            cnt += 1
        return cnt

    def _pageTpl(self, cItem):
        # "?page=N" paging ("&page=N" for the search); the url of page 1 has no page parameter
        if cItem.get("search_pattern"):
            return "%s?s=%s&page={page}" % (self.MAIN_URL, urllib_quote_plus(cItem["search_pattern"]))
        return cItem["url"].split("?", 1)[0] + "?page={page}"

    def listItems(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        tpl = self._pageTpl(cItem)
        url = tpl.format(page=page) if page > 1 else re.sub(r"[?&]page=\{page\}$", "", tpl)
        printDBG("TaxiElCima.listItems |%s|" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        start = data.find('class="CimaclubBlocks')
        end = data.find('class="pagination', start)
        if end < 0:
            end = data.find('class="Hotlinks', start)
        block = data[start:end] if start >= 0 and end > start else data
        cnt = self._addCards(cItem, block, url)
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination', "</ul>", False)[1]
        hasNext = bool(cnt) and 'class="next page-numbers"' in pager
        nums = [re.sub(r"\D", "", n) for n in re.findall(r'class="page-numbers[^"]*"[^>]*>([^<]+)<', pager)]
        lastPage = max([int(n) for n in nums if n] + [page])
        addPagingItems(self, dict(cItem, category="list_items"), page, hasNext, lastPage if hasNext or page > 1 else 0, tpl)

    def listEpisodes(self, cItem):
        printDBG("TaxiElCima.listEpisodes |%s|" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        start = data.find('class="CimaclubBlocks')
        end = data.find('class="Hotlinks', start)
        block = data[start:end] if start >= 0 and end > start else data
        before = len(self.currList)
        self._addCards(cItem, block, cItem["url"])
        # the page lists the newest first
        episodes = self.currList[before:]
        try:
            episodes.sort(key=lambda item: (int(item.get("season") or 0), int(item.get("episode") or 0)))
        except Exception:
            printExc()
        self.currList[before:] = episodes

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TaxiElCima.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.MAIN_URL, "search_pattern": searchPattern})
        self.listItems(cItem)

    ###################################################
    # title page
    ###################################################
    def _parseTitlePage(self, data):
        info = {"desc": "", "poster": "", "year": "", "duration": "", "quality": "", "rating": "", "genres": "", "series_url": ""}
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<p class="Description">', "<p", False)[1]
        if not desc:
            desc = self.cm.ph.getDataBeetwenMarkers(data, 'class="SingleContentStory">', "</div>", False)[1]
            desc = re.sub(r"<h2>.*?</h2>", "", desc, flags=re.DOTALL)
        else:
            desc = re.sub(r"<span>.*?</span>", "", desc, count=1, flags=re.DOTALL)
        info["desc"] = self.cleanHtmlStr(desc)
        info["poster"] = self._normUrl(self.cm.ph.getSearchGroups(data, r'class="(?:BG|PosterInner)[^"]*"[^>]*data-bg="([^"]+)"')[0] or
                                       self.cm.ph.getSearchGroups(data, r'data-bg="([^"]+)"[^>]*class="PosterInner')[0])
        info["rating"] = self.cm.ph.getSearchGroups(data, r"<strong>IMDB<em>(?:<i[^>]*></i>)?\s*([0-9.]+)")[0]
        terms = self.cm.ph.getDataBeetwenMarkers(data, 'class="SingleContentTerms"', "</ul>", False)[1]
        for icon, value in re.findall(r'<i class="ion (ion-[a-z\-]+)"></i><em>[^<]*</em><span>([^<]*)</span>', terms):
            value = self.cleanHtmlStr(value)
            if icon == "ion-md-calendar":
                info["year"] = value
            elif icon == "ion-md-time":
                info["duration"] = value
            elif icon == "ion-ios-tv":
                info["quality"] = value
        genres = re.findall(r'<a href="[^"]+/genre/[^"]+" title="([^"]+)"', self.cm.ph.getDataBeetwenMarkers(data, 'class="StageRight"', "</h1>", False)[1] or
                            self.cm.ph.getDataBeetwenMarkers(data, 'class="GenresArea"', "</div>", False)[1])
        info["genres"] = ", ".join(self.cleanHtmlStr(g) for g in genres)
        seasons = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="Seasons">', "</ul>", False)[1]
        info["series_url"] = self._normUrl(self.cm.ph.getSearchGroups(seasons, r'href="([^"]+/series/[^"]+)"')[0])
        return info

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("TaxiElCima.getLinksForVideo [%s]" % cItem.get("url", ""))
        urltab = []
        pageUrl = cItem.get("url", "")
        if not self.cm.isValidUrl(pageUrl):
            return []
        watchUrl = pageUrl.split("?", 1)[0].rstrip("/") + "/watch/"
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"]["Referer"] = pageUrl
        sts, data = self.getPage(watchUrl, params)
        if not sts:
            return []

        embeds = []
        servers = self.cm.ph.getDataBeetwenMarkers(data, 'class="ServersTitle"', "</ul>", False)[1]
        for url, label in re.findall(r'data-url="([^"]*)"[^>]*>(.*?)</li>', servers, re.DOTALL):
            embeds.append((self._normUrl(url), self.cleanHtmlStr(label)))
        # download mirrors: only the ones urlparser knows (the rest are file lockers / ad pages)
        downloads = self.cm.ph.getDataBeetwenMarkers(data, 'class="DownloadServers"', "</ul>", False)[1]
        for url in re.findall(r'<a href="([^"]+)"', downloads):
            url = self._normUrl(url)
            if self.cm.isValidUrl(url) and self.up.checkHostSupport(url) == 1:
                embeds.append((url, _("Download")))

        seen = set()
        trailers = []
        for url, label in embeds:
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            hostName = self.up.getHostName(url)
            videoId = VIDEO_ID_RE.search(url.split("?", 1)[0])
            if videoId:
                # a download mirror of a video that is already a server (71stream /download/<id>, ult4vid
                # /en/<id>/watch, megamax.me/d/<id> = share4max.com/e/<id>)
                if label == _("Download") and videoId.group(1) in seen:
                    continue
                seen.add(videoId.group(1))
            if "youtube" in hostName:
                # the posts without real sources only carry the trailer
                trailers.append({"name": "%s (%s)" % (_("Trailer"), hostName), "url": url, "need_resolve": 1})
                continue
            name = "%s (%s)" % (label, hostName) if label else hostName
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": watchUrl}), "need_resolve": 1})
        urltab.extend(trailers)
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []

        sidecarTxt = cItem.get("desc", "")
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("TaxiElCima.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("TaxiElCima.getArticleContent [%s]" % cItem.get("url", ""))
        mediaType = cItem.get("meta_type", "")
        info = {"desc": "", "poster": "", "year": "", "duration": "", "quality": "", "rating": "", "genres": "", "series_url": ""}
        if self.cm.isValidUrl(cItem.get("url", "")):
            sts, data = self.getPage(cItem["url"])
            if sts:
                info = self._parseTitlePage(data)
        meta = {}
        try:
            meta = getMeta(mediaType, cItem.get("meta_title", ""), cItem.get("meta_year", "") or info["year"])
        except Exception:
            printExc()
            meta = {}
        otherInfo = dict(meta.get("info", {}) or {})
        if info["year"]:
            otherInfo.setdefault("year", info["year"])
        if info["duration"]:
            otherInfo.setdefault("duration", info["duration"])
        if info["quality"]:
            otherInfo.setdefault("quality", info["quality"])
        if info["genres"]:
            otherInfo.setdefault("genres", info["genres"])
        if info["rating"] and info["rating"] != "0":
            otherInfo.setdefault("imdb_rating", info["rating"])
        text = meta.get("plot", "") or info["desc"] or cItem.get("desc", "")
        icon = meta.get("poster", "") or info["poster"] or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text,
                 "images": [{"title": "", "url": icon}] if icon else [],
                 "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("meta_type"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("TaxiElCima.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_groups":
            self.listGroups(self.currItem)
        elif category == "list_group":
            self.listGroup(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "tx_series":
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
        CHostBase.__init__(self, TaxiElCima(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("taxielcima")

    def withArticleContent(self, cItem):
        return bool(cItem.get("meta_type"))
