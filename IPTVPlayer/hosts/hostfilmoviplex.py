# -*- coding: utf-8 -*-
LAST_MODIFIED = "15.11.2026"
# 15.11.2026 - adapted to the new site theme (article cards, ?pg=N / /page/N paging, server buttons, cv-eps episode json)
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMetaByImdbId, getItemMeta, metaArticle
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx, extractNum
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized, GetLocalPageSize


LOCAL_PAGE_SIZE = 100  # episodes per page of a long season


def GetConfigList():
    return []


def gettytul():
    return "https://www.filmoviplex.com/"


class Filmoviplex(GenericFolderWatchedScraperMixin, CBaseHostClass):
    USE_CF_PROTECTION = True
    # what a favourite needs to open the row again - nothing list/page specific
    FAV_FIELDS = ("name", "category", "type", "title", "url", "icon", "desc", "s_title", "season", "episode",
                  "meta_type", "meta_title", "meta_year", "meta_season", "meta_episode", "good_for_fav")
    # "(sinkronizirano)" & co. are site tags, not part of the title
    JUNK_RE = re.compile(r'\s*[\(\[]\s*(?:sinkronizirano|sinhronizovano|sinkronizovano|titlovano|sa prevodom|online|hd|4k)\s*[\)\]]', re.I)

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "filmoviplex", "cookie": "filmoviplex.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("wp-content/uploads/logo__nf.png")
        self.MENU = [
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("browse-all-videos-1.html")},
            {"category": "list_items", "title": _("Popular movies"), "url": self.getFullUrl("browse-popular-videos/browse-movies-popular.html")},
            {"category": "list_items", "title": _("Most viewed movies"), "url": self.getFullUrl("browse-views-videos/browse-views-videos-movies.html")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("browse-series-videos.html")},
            {"category": "list_items", "title": _("Popular series"), "url": self.getFullUrl("browse-popular-videos/browse-series-popular.html")},
            {"category": "list_items", "title": _("Most viewed series"), "url": self.getFullUrl("browse-views-videos/browse-series-views.html")},
            {"category": "list_filters", "title": _("Genres"), "filter": "genre"},
            {"category": "list_filters", "title": _("Collections"), "filter": "keyword"},
            {"category": "list_filters", "title": _("Countries"), "filter": "country"},
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
        m = re.search(r'<p class="plot">(.*?)</p>', data, re.S)
        return self.cleanHtmlStr(m.group(1)) if m else ""

    def _infoField(self, data, name):
        # <dl class="info"><dt>Genre</dt><dd class="people">Action, Science Fiction</dd>
        m = re.search(r'<dt>\s*%s\s*</dt>\s*<dd[^>]*>(.*?)</dd>' % name, data, re.S | re.I)
        return re.sub(r'\s*,\s*', ', ', self.cleanHtmlStr(m.group(1))).strip(" ,") if m else ""

    def _badges(self, data):
        # the title's own chips: <div class="badges"><span class="chip">Movie</span><a class="chip imdb" href=".../tt0133093/">★ IMDb 8.1</a>
        return self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", 'class="badges"'), ("</div", ">"), False)[1]

    def _imdbId(self, data):
        return self.cm.ph.getSearchGroups(self._badges(data), r'imdb\.com/title/(tt\d+)')[0]

    def _decodeEmbed(self, value):
        # server button / iframe: <site>/embed.php?vid=<urlencoded base64 url> or a plain embed url;
        # episode json: plain base64 url
        value = ("%s" % (value or "")).strip().replace("&amp;", "&")
        m = re.search(r'/embed\.php\?vid=([^&]+)', value)
        if m:
            value = urllib_unquote(m.group(1))
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
            sts, data = self.getPage(self.MAIN_URL)
            if not sts:
                return
            for key, pattern in (("genre", r'href="((?:https?://[^/"]+)?/genre/[^"]+)"[^>]*>(.*?)</a>'),
                                 ("keyword", r'href="((?:https?://[^/"]+)?/keyword/[^"]+)"[^>]*>(.*?)</a>'),
                                 ("country", r'href="((?:https?://[^/"]+)?/sa-prevodom/country/[^"]+)"[^>]*>(.*?)</a>'),
                                 ("years", r'href="((?:https?://[^/"]+)?/sa-prevodom/years/\d{4})"[^>]*>(.*?)</a>')):
                tab = []
                seen = set()
                for url, title in re.findall(pattern, data, re.S):
                    url = self.getFullUrl(url)
                    # year links carry a title count ("2025 1116 Naslova") - the url has the plain year
                    title = url.rsplit("/", 1)[-1] if key == "years" else self.cleanHtmlStr(title)
                    if url in seen or title == "":
                        continue
                    seen.add(url)
                    tab.append({"title": title, "url": url})
                if key == "years":
                    tab.sort(key=lambda item: item["title"], reverse=True)
                self.filtersCache[key] = tab
        for item in self.filtersCache.get(flt, []):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": item["title"], "url": item["url"]})
            params.pop("filter", None)
            self.addDir(params)

    def _pageUrlTpl(self, baseUrl):
        # browse-*.html lists page with ?pg=N, genre/keyword/year/country/search with <path>/page/N[?query]
        path, sep, query = baseUrl.partition("?")
        if path.endswith(".html"):
            return path + "?" + (query + "&" if query else "") + "pg={page}"
        return path.rstrip("/") + "/page/{page}" + sep + query

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or re.sub(r"/page/\d+/?(?=$|\?)", "", cItem["url"])
        baseUrl = re.sub(r"[?&]pg=\d+$", "", re.sub(r"([?&])pg=\d+&", r"\1", baseUrl))
        pageUrlTpl = self._pageUrlTpl(baseUrl)
        url = baseUrl if page <= 1 else pageUrlTpl.format(page=page)
        printDBG("Filmoviplex.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<article class="card', "</article>"):
            url = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]*/sa-prevodom/[^"#]+\.html)"')[0]
            if url == "":
                continue
            url = self.getFullUrl(url)
            label = self.cm.ph.getSearchGroups(item, r'<h3[^>]*>(.*?)</h3>')[0] or self.cm.ph.getSearchGroups(item, r'<img[^>]+alt="([^"]+)"')[0]
            label, base, year = self._splitLabel(label)
            if label == "":
                continue
            year = year or self.cm.ph.getSearchGroups(item, r'<small[^>]*>\s*(\d{4})\s*</small>')[0]
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            isSeries = any("SERIJA" in tag.upper() for tag in re.findall(r'class="tag"[^>]*>([^<]*)<', item))
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

        hasNext = 'class="next page-numbers"' in data
        lastPage = max([int(n) for n in re.findall(r'class="page-numbers"[^>]*>\s*(\d+)\s*<', data)] + [page])
        listItem = dict(cItem)
        # list_items, not the copied "search": that would rebuild page 1 from the search pattern
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext and bool(self.currList), lastPage, pageUrlTpl)

    def _getEpisodes(self, data):
        # <script type="application/json" id="cv-eps">{"1": {"1": {"l": "<b64 url>", "n": ""}, ...}, ...}
        # -> [(season, [(episode, value), ...]), ...] numerically sorted
        ret = []
        m = re.search(r'<script[^>]+id="cv-eps"[^>]*>(.*?)</script>', data, re.S)
        raw = m.group(1).strip() if m else ""
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
        if not self.currList and 'class="srv' in data:
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
                params = stripPagerKeys(dict(cItem), ("local_paging",))
                params.update({"good_for_fav": True, "category": "fp_episode", "title": title, "s_title": sTitle, "season": sNum,
                               "episode": eNum, "meta_season": sNum, "meta_episode": eNum, "url": "%s#s%se%s" % (seriesUrl, sNum, eNum)})
                self.addVideo(params)
        self._localPaging(cItem, cItem.get("page", 1))

    def _localPaging(self, cItem, page):
        pageSize = GetLocalPageSize(LOCAL_PAGE_SIZE)
        # a long season (the page carries all episodes): pageSize rows per page (First page / Next page)
        lastPage = (len(self.currList) + pageSize - 1) // pageSize
        if lastPage <= 1:
            return
        page = min(max(1, page), lastPage)
        self.currList = self.currList[(page - 1) * pageSize:page * pageSize]
        params = dict(cItem)
        params["local_paging"] = True
        addPagingItems(self, params, page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Filmoviplex.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem["url"] = "%s?s=%s" % (self.MAIN_URL, urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _collectEmbeds(self, cItem, data):
        # -> [(url, note), ...]; note = the site's "(BEZ PREVODA)" (no subtitles) marker of a server button
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
                    if eNum != episode:
                        continue
                    if isinstance(value, dict):
                        value = value.get("l", "")
                    for val in (value if isinstance(value, list) else [value]):
                        embeds.append((self._decodeEmbed(val), ""))
        else:
            for attrs, label in re.findall(r'<button([^>]+class="srv[^"]*"[^>]*)>(.*?)</button>', data, re.S):
                note = self.cm.ph.getSearchGroups(self.cleanHtmlStr(label), r'(\([^)]*\))\s*$')[0]
                embeds.append((self._decodeEmbed(self.cm.ph.getSearchGroups(attrs, r'data-src="([^"]+)"')[0]), note))
            player = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", 'class="player"'), ("</div", ">"), False)[1]
            for value in re.findall(r'<iframe[^>]+src="([^"]+)"', player):
                embeds.append((self._decodeEmbed(value), ""))
        ret = []
        seen = set()
        for url, note in embeds:
            if url and url not in seen:
                seen.add(url)
                ret.append((url, note))
        return ret

    def getLinksForVideo(self, cItem):
        printDBG("Filmoviplex.getLinksForVideo [%s]" % cItem.get("url"))
        urltab = []
        sts, data = self._getCachedPage(cItem.get("url", ""))
        if not sts:
            return []
        sidecarTxt = self._pageDesc(data) or cItem.get("desc", "")
        unsupported = []
        for url, note in self._collectEmbeds(cItem, data):
            host = self.up.getHostName(url)
            if self.up.checkHostSupport(url) != 1:
                printDBG("Filmoviplex: hoster not supported [%s]" % url)
                if host not in unsupported:
                    unsupported.append(host)
                continue
            # the site's own player subdomains: netu.filmoviplex.com = netu/hqq, btgNNN.filmoviplex.com = abyss
            if host.endswith("filmoviplex.com"):
                host = "netu/hqq" if host.startswith("netu.") else "abyss"
            urltab.append({"name": ("%d. %s %s" % (len(urltab) + 1, host, note)).strip(), "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            if unsupported:
                SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(unsupported))
            else:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        # moviemeta query of INFO: the page's IMDb id, else the item's title
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", ""), cItem.get("meta_title", ""), cItem.get("meta_year", ""), self._imdbId(data),
                                     skip=(), season=cItem.get("meta_season", ""), episode=cItem.get("meta_episode", ""))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt, metaQuery=metaQuery))

    ###################################################
    # favourites / INFO
    ###################################################
    def getFavouriteData(self, cItem):
        if cItem.get("good_for_fav"):
            return self.getFavouriteFieldsData(cItem)
        return CBaseHostClass.getFavouriteData(self, cItem)

    def getArticleContent(self, cItem):
        printDBG("Filmoviplex.getArticleContent [%s]" % cItem.get("url"))
        text = ""
        icon = cItem.get("icon", "")
        other = {}
        imdbId = ""
        mediaType = cItem.get("meta_type", "")
        sts, data = self._getCachedPage(cItem.get("url", ""))
        if sts:
            text = self._pageDesc(data)
            imdbId = self._imdbId(data)
            icon = icon or self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
            # the moviemeta keys (directors / cast): a meta answer replaces the site's line instead of adding a second one
            for key, field in (("genres", "Genre"), ("year", "Year"), ("directors", "Director"), ("country", "Country")):
                value = self._infoField(data, field)
                if value:
                    other[key] = value
            # <p class="meta-line"><span>1999</span><span>2h 16m</span></p>
            metaLine = self.cm.ph.getDataBeetwenNodes(data, ("<p", ">", 'class="meta-line"'), ("</p", ">"), False)[1]
            duration = self.cm.ph.getSearchGroups(metaLine, r'<span>\s*(\d+h(?:\s*\d+m)?|\d+\s*min)\s*</span>')[0]
            if duration:
                other["duration"] = duration
            # <div class="badges">...<a class="chip imdb" href="https://www.imdb.com/title/tt0133093/">★ IMDb 8.1</a>
            rating = self.cm.ph.getSearchGroups(self._badges(data), r'IMDb\s+(\d+(?:\.\d+)?)\s*<')[0]
            if rating and rating not in ("0", "0.0"):
                other["imdb_rating"] = "%s/10" % rating
            actors = [a for a in self._infoField(data, "Cast").split(", ") if a][:6]
            if actors:
                other["cast"] = ", ".join(actors)
        meta = {}
        if imdbId and mediaType in ("movie", "tv"):
            try:
                meta = getMetaByImdbId(mediaType, imdbId)
            except Exception:
                printExc()
        return metaArticle(cItem, meta or getItemMeta(cItem), story=text, poster=icon, info=other)

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
