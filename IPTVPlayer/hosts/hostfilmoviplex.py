# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - revival + rewrite for the current filmoviplex.com
#   (WordPress "cbp-rfgrid" cards with FILM/SERIJA badge; First page / Jump / Next page over ".../page/N";
#    movie players as loadEmbed('/embed.php?vid=<base64 url>') / plain embed url;
#    series episodes as inline window.DB_EPISODES {season: {episode: <base64 url>}})
#   + genres / collections / years / 4K, search, watched flag, downloaded flag
#   (stable page urls), name normalisation, sidecar, moviemeta INFO, favourites.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx, extractNum
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized


def GetConfigList():
    return []


def gettytul():
    return "https://www.filmoviplex.com/"


class Filmoviplex(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what a favourite needs to open the row again - nothing list/page specific
    FAV_FIELDS = ("name", "category", "type", "title", "url", "icon", "desc", "s_title", "season", "episode",
                  "meta_type", "meta_title", "meta_year", "good_for_fav")
    # "(sinkronizirano)" & co. are site tags, not part of the title
    JUNK_RE = re.compile(r'\s*[\(\[]\s*(?:sinkronizirano|sinhronizovano|sinkronizovano|titlovano|sa prevodom|online|hd|4k)\s*[\)\]]', re.I)

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "filmoviplex", "cookie": "filmoviplex.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("wp-content/uploads/logo__nf.png")
        self.MENU = [
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("browse-all-videos.html")},
            {"category": "list_items", "title": _("Popular movies"), "url": self.getFullUrl("browse-popular-videos-1.html")},
            {"category": "list_items", "title": _("Most viewed movies"), "url": self.getFullUrl("browse-views-videos-1.html")},
            {"category": "list_items", "title": _("Top rated movies"), "url": self.getFullUrl("browse-top-videos-1.html")},
            {"category": "list_items", "title": _("4K movies"), "url": self.getFullUrl("4k.html")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("browse-series-videos-1.html")},
            {"category": "list_items", "title": _("Popular series"), "url": self.getFullUrl("browse-series-popular-1.html")},
            {"category": "list_items", "title": _("Most viewed series"), "url": self.getFullUrl("browse-series-views-1.html")},
            {"category": "list_items", "title": _("Top rated series"), "url": self.getFullUrl("browse-series-top-1.html")},
            {"category": "list_filters", "title": _("Genres"), "filter": "genre"},
            {"category": "list_filters", "title": _("Collections"), "filter": "keyword"},
            {"category": "list_filters", "title": _("Year"), "filter": "years"},
        ] + self.searchItems()
        self.filtersCache = {}
        self.pageCache = {}
        self.watchedHelper = IPTVWatchedHelper("filmoviplex")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = self._pageUrl(cItem.get("url", ""))
            if url == "" or "/sa-prevodom/" not in url or "/years/" in url:
                return ""
            category = cItem.get("category", "")
            if cItem.get("type", "") in ("video", "audio"):
                if category == "fp_episode":
                    return "episode:%s|%s|%s" % (url, cItem.get("season", ""), cItem.get("episode", ""))
                return "video:%s" % url
            if category == "list_seasons":
                return "series:%s" % url
            if category == "list_episodes":
                return "season:%s|%s" % (url, cItem.get("season", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _pageUrl(self, url):
        # episode rows carry "#sXeY" behind the series page url - the request goes without it
        return str(url or "").split("#", 1)[0].strip()

    def _getCachedPage(self, url):
        url = self._pageUrl(url)
        if url == "":
            return False, ""
        data = self.pageCache.get(url)
        if data is not None:
            return True, data
        sts, data = self.getPage(url)
        if not sts or not data:
            return False, ""
        if len(self.pageCache) > 20:
            self.pageCache = {}
        self.pageCache[url] = data
        return True, data

    def _splitLabel(self, label):
        # "Slow Horses (2022) (2022)" -> ("Slow Horses (2022)", "Slow Horses", "2022")
        label = self.cleanHtmlStr(label)
        label = re.sub(r'\((\d{4})\)(?:\s*\(\1\))+', r'(\1)', label).strip()
        year = self.cm.ph.getSearchGroups(label, r'\((\d{4})\)\s*$')[0]
        base = label
        while True:
            stripped = re.sub(r'\s*\(\d{4}\)\s*$', '', base).strip()
            if stripped == base or stripped == "":
                break
            base = stripped
        return label, base, year

    def _cleanTitle(self, base):
        return re.sub(r'\s{2,}', ' ', self.JUNK_RE.sub('', base)).strip(" -") or base

    def _metaTitle(self, base):
        # "Cukur aka Jama" -> "Cukur"
        return re.split(r'\s+aka\s+', self._cleanTitle(base), maxsplit=1, flags=re.I)[0].strip()

    def _pageDesc(self, data):
        m = re.search(r'<span itemprop="description">(.*?)</span>', data, re.S)
        text = self.cleanHtmlStr(m.group(1)) if m else ""
        # "Gledaj hd besplatno <title> sa prevodom online, <plot>"
        return re.sub(r'^Gledaj\s.*?\ssa prevodom online\s*,\s*', '', text, count=1, flags=re.I | re.S).strip()

    def _decodeEmbed(self, value):
        value = ("%s" % (value or "")).strip().replace("&amp;", "&")
        if "vid=" in value:
            value = value.split("vid=", 1)[1]
        if value == "" or value.startswith("http") or value.startswith("//"):
            url = value
        else:
            try:
                url = b64Decode(value).strip()
            except Exception:
                printExc()
                return ""
        if url.startswith("//"):
            url = "https:" + url
        return url if self.cm.isValidUrl(url) else ""

    ###################################################
    # lists
    ###################################################
    def listFilters(self, cItem):
        printDBG("Filmoviplex.listFilters [%s]" % cItem.get("filter"))
        flt = cItem.get("filter", "")
        if not self.filtersCache:
            sts, data = self.getPage(self.getFullUrl("browse-all-videos.html"))
            if not sts:
                return
            for key, pattern in (("genre", r'href="(/genre/[^"]+)"[^>]*>(.*?)</a>'),
                                 ("keyword", r'href="(/keyword/[^"]+|/4k\.html)"[^>]*>(.*?)</a>'),
                                 ("years", r'href="(/sa-prevodom/years/\d{4})"[^>]*>(.*?)</a>')):
                tab = []
                seen = set()
                for url, title in re.findall(pattern, data, re.S):
                    url = self.getFullUrl(url)
                    title = re.sub(r'\s*Godina$', '', self.cleanHtmlStr(title))
                    if url in seen or title == "":
                        continue
                    seen.add(url)
                    tab.append({"title": title, "url": url})
                self.filtersCache[key] = tab
        for item in self.filtersCache.get(flt, []):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": item["title"], "url": item["url"]})
            params.pop("filter", None)
            self.addDir(params)

    def listItems(self, cItem):
        # paging: <path>/page/N[?query]
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or re.sub(r"/page/\d+/?(?=$|\?)", "", cItem["url"])
        path, sep, query = baseUrl.partition("?")
        pageUrlTpl = path.rstrip("/") + "/page/{page}" + sep + query
        url = baseUrl if page <= 1 else pageUrlTpl.format(page=page)
        printDBG("Filmoviplex.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        grid = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "cbp-rfgrid"), ("</ul", ">"), False)[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(grid, "<li", "</li>"):
            url = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]*/sa-prevodom/[^"#]+)"')[0]
            if url == "":
                continue
            url = self.getFullUrl(url)
            label = self.cm.ph.getSearchGroups(item, r'<div>([^<]+)</div>\s*</a>')[0] or self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0]
            label, base, year = self._splitLabel(label)
            if label == "":
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            isSeries = "SERIJA" in self.cm.ph.getSearchGroups(item, r'id="hd_s_g">([^<]*)<')[0].upper()
            cleanBase = self._cleanTitle(base)
            if normalize:
                title = "%s (%s)" % (cleanBase, year) if year else cleanBase
            else:
                title = label
            params = stripPagerKeys(dict(cItem), ("base_url",))
            params.update({"good_for_fav": True, "title": title, "url": url, "icon": icon,
                           "desc": "%s%s" % (_("Series") if isSeries else _("Movie"), (" | %s" % year) if year else ""),
                           "meta_type": "tv" if isSeries else "movie", "meta_title": self._metaTitle(base), "meta_year": year})
            if isSeries:
                params.update({"category": "list_seasons", "s_title": cleanBase if normalize else base})
                self.addDir(params)
            else:
                params.update({"category": "fp_movie"})
                self.addVideo(params)

        hasNext = bool(re.search(r'<a href="[^"]+"\s*>\s*Next Page', data))
        lastPage = max([int(n) for n in re.findall(r'<a href="[^"]*/page/(\d+)[^"]*"\s*>\s*\d+\s*<', data)] + [page])
        listItem = dict(cItem)
        # list_items, not the copied "search": that would rebuild page 1 from the search pattern
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext and bool(self.currList), lastPage, pageUrlTpl)

    def _getEpisodes(self, data):
        # window.DB_EPISODES {"1": {"1": "<b64 url>", ...}, ...} -> [(season, [(episode, value), ...]), ...] numerically sorted
        ret = []
        m = re.search(r'DB_EPISODES\s*=\s*(\{.*?\})\s*;?\s*(?:\n|</script>|window\.)', data, re.S)
        raw = m.group(1) if m else ""
        if raw == "":
            return ret
        try:
            seasons = json_loads(raw)
        except Exception:
            printExc()
            return ret
        if not isinstance(seasons, dict):
            return ret
        for sNum in sorted(seasons.keys(), key=extractNum):
            eps = seasons[sNum]
            if isinstance(eps, list):
                eps = dict((str(idx + 1), val) for idx, val in enumerate(eps))
            if not isinstance(eps, dict) or str(sNum) == "0":
                continue  # the site itself hides season 0
            epList = [(str(eNum), eps[eNum]) for eNum in sorted(eps.keys(), key=extractNum)]
            if epList:
                ret.append((str(sNum), epList))
        return ret

    def listSeasons(self, cItem):
        printDBG("Filmoviplex.listSeasons [%s]" % cItem.get("url"))
        sts, data = self._getCachedPage(cItem["url"])
        if not sts:
            return
        desc = self._pageDesc(data) or cItem.get("desc", "")
        sTitle = cItem.get("s_title") or cItem.get("title", "")
        for sNum, dummy in self._getEpisodes(data):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s %s" % (sTitle, _("Season"), sNum),
                           "s_title": sTitle, "season": sNum, "desc": desc})
            self.addDir(params)
        if not self.currList and "loadEmbed(" in data:
            # badged as series, but the page is a single video
            params = dict(cItem)
            params.update({"category": "fp_movie", "desc": desc})
            self.addVideo(params)

    def listEpisodes(self, cItem):
        printDBG("Filmoviplex.listEpisodes [%s] season[%s]" % (cItem.get("url"), cItem.get("season")))
        sts, data = self._getCachedPage(cItem["url"])
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        sTitle = cItem.get("s_title") or cItem.get("title", "")
        season = str(cItem.get("season", ""))
        seriesUrl = self._pageUrl(cItem["url"])
        for sNum, eps in self._getEpisodes(data):
            if sNum != season:
                continue
            for eNum, dummy in eps:
                if normalize:
                    title = "%s - %s" % (sTitle, formatSxxExx(sNum, eNum))
                else:
                    title = "%s - %s %s, %s %s" % (sTitle, _("Season"), sNum, _("Episode"), eNum)
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "fp_episode", "title": title, "s_title": sTitle,
                               "season": sNum, "episode": eNum, "url": "%s#s%se%s" % (seriesUrl, sNum, eNum)})
                self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Filmoviplex.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem["url"] = "%s?s=%s" % (self.MAIN_URL, urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _collectEmbeds(self, cItem, data):
        embeds = []
        season = str(cItem.get("season", "") or "")
        episode = str(cItem.get("episode", "") or "")
        if not episode:
            season, episode = self.cm.ph.getSearchGroups(cItem.get("url", ""), r'#s(\d+)e(\d+)', 2)
        if episode:
            for sNum, eps in self._getEpisodes(data):
                if sNum != season:
                    continue
                for eNum, value in eps:
                    if eNum == episode:
                        for val in (value if isinstance(value, list) else [value]):
                            embeds.append(self._decodeEmbed(val))
        else:
            for value in re.findall(r'''loadEmbed\(\s*this\s*,\s*['"]([^'"]*)['"]''', data):
                embeds.append(self._decodeEmbed(value))
            for value in re.findall(r'<iframe[^>]+id="embed\d+"[^>]+src="([^"]+)"', data):
                embeds.append(self._decodeEmbed(value))
        ret = []
        for url in embeds:
            if url and url not in ret:
                ret.append(url)
        return ret

    def getLinksForVideo(self, cItem):
        printDBG("Filmoviplex.getLinksForVideo [%s]" % cItem.get("url"))
        urltab = []
        sts, data = self._getCachedPage(cItem.get("url", ""))
        if not sts:
            return []
        sidecarTxt = self._pageDesc(data) or cItem.get("desc", "")
        unsupported = []
        for url in self._collectEmbeds(cItem, data):
            host = self.up.getHostName(url)
            if self.up.checkHostSupport(url) != 1:
                printDBG("Filmoviplex: hoster not supported [%s]" % url)
                if host not in unsupported:
                    unsupported.append(host)
                continue
            # the site's own player subdomains: netu.filmoviplex.com = netu/hqq, btgNNN.filmoviplex.com = abyss
            if host.endswith("filmoviplex.com"):
                host = "netu/hqq" if host.startswith("netu.") else "abyss"
            urltab.append({"name": "%d. %s" % (len(urltab) + 1, host), "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            if unsupported:
                SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(unsupported))
            else:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("Filmoviplex.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # favourites / INFO
    ###################################################
    def getFavouriteData(self, cItem):
        try:
            if cItem.get("good_for_fav"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def getArticleContent(self, cItem):
        printDBG("Filmoviplex.getArticleContent [%s]" % cItem.get("url"))
        title = cItem.get("title", "")
        text = ""
        icon = cItem.get("icon", "")
        other = {}
        imdbId = ""
        mediaType = cItem.get("meta_type", "")
        sts, data = self._getCachedPage(cItem.get("url", ""))
        if sts:
            text = self._pageDesc(data)
            imdbId = self.cm.ph.getSearchGroups(data, r'imdb\.com/title/(tt\d+)')[0]
            icon = icon or self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
            m = re.search(r'itemprop="genre"[^>]*>(.*?)</span>', data, re.S)
            genres = [self.cleanHtmlStr(g) for g in re.findall(r'href="[^"]*/genre/[^"]*"[^>]*>(.*?)</a>', m.group(1))] if m else []
            if genres:
                other["genres"] = ", ".join(genres)
            year = self.cm.ph.getSearchGroups(data, r'Godina:\s*<a[^>]*>(\d{4})<')[0]
            if year:
                other["year"] = year
            duration = self.cm.ph.getSearchGroups(data, r'Trajanje:\s*(\d+\s*min)')[0]
            if duration:
                other["duration"] = duration
            rating = self.cm.ph.getSearchGroups(data, r'itemprop="ratingValue" content="([^"]+)"')[0]
            if rating and rating not in ("0", "0.0"):
                other["imdb_rating"] = "%s/10" % rating
            actors = [self.cleanHtmlStr(a) for a in re.findall(r'href="[^"]*/actors/[^"]*"[^>]*>(.*?)</a>', data)[:6]]
            if actors:
                other["actors"] = ", ".join(actors)
        meta = {}
        try:
            if mediaType in ("movie", "tv"):
                meta = getMetaByImdbId(mediaType, imdbId) if imdbId else {}
                if not meta:
                    meta = getMeta(mediaType, cItem.get("meta_title", ""), cItem.get("meta_year", ""))
        except Exception:
            printExc()
        if meta:
            other.update(meta.get("info", {}))
            text = meta.get("plot") or text
            icon = meta.get("poster") or icon
        return [{"title": title, "text": text or cItem.get("desc", ""), "images": [{"title": "", "url": icon}] if icon else [], "other_info": other}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Filmoviplex.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_filters":
            self.listFilters(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
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
        CHostBase.__init__(self, Filmoviplex(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("filmoviplex")

    def withArticleContent(self, cItem):
        return cItem.get("meta_type", "") in ("movie", "tv")
