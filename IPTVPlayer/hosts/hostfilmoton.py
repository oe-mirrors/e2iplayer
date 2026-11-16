# -*- coding: utf-8 -*-
LAST_MODIFIED = "15.11.2026"
# 15.11.2026 - new host: filmoton.ba (Bosnian/Croatian/Serbian subtitles; WordPress Vodi/MasVideos theme)
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMetaByImdbId, getItemMeta, metaArticle
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx, extractNum
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized, GetLocalPageSize


LOCAL_PAGE_SIZE = 100  # rows per page of a list the site shows in one piece (Domaći filmovi: ~300, long seasons)


def GetConfigList():
    return []


def gettytul():
    return "https://filmoton.ba/"


class Filmoton(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what a favourite needs to open the row again - nothing list/page specific
    FAV_FIELDS = ("name", "category", "type", "title", "url", "icon", "desc", "s_title", "season", "episode",
                  "meta_type", "meta_title", "meta_year", "meta_season", "meta_episode", "good_for_fav")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "filmoton", "cookie": "filmoton.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("filmovi-online/")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serije-online/")},
            {"category": "list_items", "title": "Domaći filmovi", "url": self.getFullUrl("domaci-filmovi/")},
            {"category": "list_items", "title": "Domaće serije", "url": self.getFullUrl("gledaj-domace-serije/")},
            {"category": "list_items", "title": "Turske serije", "url": self.getFullUrl("turske-serije/")},
            {"category": "list_filters", "title": _("Genres")},
        ] + self.searchItems()
        self.genresCache = []
        self.pageCache = {}
        self.watchedHelper = IPTVWatchedHelper("filmoton")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = cItem.get("url", "")
            if not re.search(r'/(?:gledaj-film|serije-online|epizoda-online)/[^/]+/?$', url):
                return ""
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url
            category = cItem.get("category", "")
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
    def _getCachedPage(self, url):
        data = self.pageCache.get(url)
        if data is not None:
            return True, data
        sts, data = self.getPage(url)
        if not sts or not data:
            return False, ""
        self._cachePage(url, data)
        return True, data

    def _cachePage(self, url, data):
        if len(self.pageCache) > 20:
            self.pageCache = {}
        self.pageCache[url] = data

    def _splitLabel(self, label):
        # "Kumovi (2022)" -> ("Kumovi (2022)", "Kumovi", "2022")
        label = self.cleanHtmlStr(label)
        year = self.cm.ph.getSearchGroups(label, r'\((\d{4})\)\s*$')[0]
        base = re.sub(r'\s*\(\d{4}\)\s*$', '', label).strip() or label
        return label, base, year

    def _metaTitle(self, base):
        # "Kaeng Owoe AKA Overacting" -> "Kaeng Owoe"; "ABI (Porodica Je Iskusenje)" -> "ABI"
        base = re.split(r'\s+aka\s+', base, maxsplit=1, flags=re.I)[0]
        return re.sub(r'\s*\([^)]*\)\s*$', '', base).strip() or base

    def _imageUrl(self, item):
        # lazy-loaded posters: data-lazy-src / first data-lazy-srcset entry; plain src only when it is no svg placeholder
        for pattern in (r'data-lazy-src="([^"]+)"', r'data-lazy-srcset="([^"\s]+)', r'<img[^>]+src="((?!data:)[^"]+)"'):
            url = self.cm.ph.getSearchGroups(item, pattern)[0]
            if url:
                return self.getFullIconUrl(url)
        return ""

    def _addTitle(self, cItem, url, label, icon, isSeries, year=""):
        label, base, labelYear = self._splitLabel(label)
        if label == "":
            return
        year = labelYear or year
        normalize = IsMediaNamingNormalized()
        title = ("%s (%s)" % (base, year) if year else base) if normalize else label
        params = stripPagerKeys(dict(cItem), ("base_url", "local_paging"))
        params.update({"good_for_fav": True, "title": title, "url": url, "icon": icon,
                       "desc": "%s%s" % (_("Series") if isSeries else _("Movie"), (" | %s" % year) if year else ""),
                       "meta_type": "tv" if isSeries else "movie", "meta_title": self._metaTitle(base), "meta_year": year})
        if isSeries:
            params.update({"category": "list_seasons", "s_title": base})
            self.addDir(params)
        else:
            params.update({"category": "fo_movie"})
            self.addVideo(params)

    ###################################################
    # lists
    ###################################################
    def listFilters(self, cItem):
        if not self.genresCache:
            sts, data = self.getPage(self.MAIN_URL)
            if not sts:
                return
            seen = set()
            for path, suffix in (("zanr", ""), ("tv-show-genre", " - %s" % _("Series"))):
                tab = []
                for url, title in re.findall(r'href="(https?://[^"/]+/%s/[^"/]+/)"[^>]*>(.*?)</a>' % path, data, re.S):
                    title = self.cleanHtmlStr(title)
                    if url in seen or title == "":
                        continue
                    seen.add(url)
                    tab.append({"title": title + suffix, "url": url})
                tab.sort(key=lambda item: item["title"].lower())
                self.genresCache.extend(tab)
        for item in self.genresCache:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": item["title"], "url": item["url"]})
            self.addDir(params)

    def _listCards(self, cItem, data):
        seen = set()
        # only the list itself: the sidebar (id="secondary") carries its own movie / series cards, the pager follows the list
        data = re.split(r'<nav class="masvideos-pagination|<div id="secondary"', data, maxsplit=1)[0]
        # MasVideos loop cards: <div class="post-N movie ..."> / <div class="tv-show post-N ...">
        for item in re.split(r'<div class="(?:tv-show )?post-\d+ ', data)[1:]:
            m = re.search(r'<a href="([^"]+)" class="masvideos-Loop(Movie|TvShow)-link[^"]*">\s*<h3[^>]*>(.*?)</h3>', item, re.S)
            if not m or m.group(1) in seen:
                continue
            seen.add(m.group(1))
            year = self.cm.ph.getSearchGroups(item, r'release-year">\s*(\d{4})')[0]
            self._addTitle(cItem, m.group(1), m.group(3), self._imageUrl(item), m.group(2) == "TvShow", year)
        # "Turske serije": <li class="fk-card"> grid
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="fk-card"', "</li>"):
            url = self.cm.ph.getSearchGroups(item, r'class="fk-poster" href="([^"]+)"')[0]
            if url == "" or url in seen:
                continue
            seen.add(url)
            label = self.cm.ph.getSearchGroups(item, r'aria-label="([^"]+)"')[0]
            self._addTitle(cItem, url, label, self._imageUrl(item), True)

    def _localPaging(self, cItem, page):
        pageSize = GetLocalPageSize(LOCAL_PAGE_SIZE)
        # a list the site shows in one piece: pageSize rows per page (First page / Next page)
        lastPage = (len(self.currList) + pageSize - 1) // pageSize
        if lastPage <= 1:
            return
        page = min(max(1, page), lastPage)
        self.currList = self.currList[(page - 1) * pageSize:page * pageSize]
        params = dict(cItem)
        params["local_paging"] = True
        addPagingItems(self, params, page, page < lastPage, lastPage)

    def listItems(self, cItem):
        pageSize = GetLocalPageSize(LOCAL_PAGE_SIZE)
        # site paging: <path>/page/N/[?query]; lists without a pager (Domaći filmovi ...) get local paging
        page = cItem.get("page", 1)
        localPaging = cItem.get("local_paging", False)
        baseUrl = cItem.get("base_url") or re.sub(r"/page/\d+/?(?=$|\?)", "/", cItem["url"])
        path, sep, query = baseUrl.partition("?")
        pageUrlTpl = path.rstrip("/") + "/page/{page}/" + sep + query
        url = baseUrl if (page <= 1 or localPaging) else pageUrlTpl.format(page=page)
        printDBG("Filmoton.listItems [%s]" % url)
        sts, data = self._getCachedPage(url) if localPaging else self.getPage(url)
        if not sts:
            return
        self._listCards(cItem, data)
        hasNext = 'class="next page-numbers"' in data
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        if localPaging or not (hasNext or page > 1):
            if len(self.currList) > pageSize:
                self._cachePage(baseUrl, data)  # the next local page lists from it
            self._localPaging(listItem, page)
            return
        lastPage = max([int(n) for n in re.findall(r'class="page-numbers"[^>]*href="[^"]*/page/(\d+)/', data)] + [page])
        addPagingItems(self, listItem, page, hasNext and bool(self.currList), lastPage, pageUrlTpl)

    def _getSeasons(self, data):
        # season tabs: <a href="#tab-X" data-toggle="tab" ...> Sezona 2 </a> + <div id="tab-X" class="tab-pane"> episode cards
        # -> [(season, [(episode, url, title), ...]), ...] numerically sorted
        ret = []
        section = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "season-tabs-wrap"), ("<section", ">"), False)[1] or data
        tabs = re.findall(r'<a href="#(tab-[^"]+)" data-toggle="tab"[^>]*>(.*?)</a>', section, re.S)
        panes = re.split(r'<div id="(tab-[^"]+)" class="tab-pane', section)
        paneData = dict(zip(panes[1::2], panes[2::2]))
        if not paneData:
            # no season tabs: the episode cards of the page, season from their SxxEyy badge (else 1)
            tabs, paneData = [("", "1")], {"": section}
        for tabId, label in tabs:
            sNum = self.cm.ph.getSearchGroups(self.cleanHtmlStr(label), r'(\d+)')[0]
            eps = []
            seen = set()
            for item in re.split(r'<div class="post-\d+ episode ', paneData.get(tabId, ""))[1:]:
                url = self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)" class="masvideos-LoopEpisode-link')[0]
                if url == "" or url in seen:
                    continue
                seen.add(url)
                badge = self.cm.ph.getSearchGroups(item, r'fl-ep__badge">\s*S(\d+)E(\d+)', 2)
                # an episode without a number keeps its place in the list
                eNum = badge[1] or self.cm.ph.getSearchGroups(item, r'episode__number">\s*(\d+)')[0] or str(len(eps) + 1)
                if badge[0] and (not sNum or not tabId):
                    sNum = badge[0]  # tab label without a number, or no tabs at all
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h3[^>]*>(.*?)</h3>')[0])
                eps.append((str(int(eNum)), url, title))
            if sNum and eps:
                eps.sort(key=lambda e: extractNum(e[0]))
                ret.append((str(int(sNum)), eps))
        ret.sort(key=lambda s: extractNum(s[0]))
        return ret

    def _pageDesc(self, data):
        for pattern in (r'<div class="desc">(.*?)</div>', r'class="(?:movie|episode|tv-show)__short-description">(.*?)</div>',
                        r'class="(?:movie|episode|tv-show)__description">(.*?)</div>'):
            m = re.search(pattern, data, re.S)
            text = self.cleanHtmlStr(re.sub(r'<iframe.*?</iframe>|<noscript>.*?</noscript>', '', m.group(1), flags=re.S)) if m else ""
            if text:
                return text
        return ""

    def listSeasons(self, cItem):
        printDBG("Filmoton.listSeasons [%s]" % cItem.get("url"))
        sts, data = self._getCachedPage(cItem["url"])
        if not sts:
            return
        desc = self._pageDesc(data) or cItem.get("desc", "")
        sTitle = cItem.get("s_title") or cItem.get("title", "")
        for sNum, eps in self._getSeasons(data):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s %s" % (sTitle, _("Season"), sNum),
                           "s_title": sTitle, "season": sNum, "desc": "%s (%d)\n%s" % (_("Episodes"), len(eps), desc)})
            self.addDir(params)
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No episodes found."))

    def listEpisodes(self, cItem):
        printDBG("Filmoton.listEpisodes [%s] season[%s]" % (cItem.get("url"), cItem.get("season")))
        sts, data = self._getCachedPage(cItem["url"])
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        sTitle = cItem.get("s_title") or cItem.get("title", "")
        season = str(cItem.get("season", ""))
        # the season row's desc starts with "Episodes (n)" - the episodes keep only the show's text
        desc = cItem.get("desc", "").split("\n", 1)[-1]
        for sNum, eps in self._getSeasons(data):
            if sNum != season:
                continue
            for eNum, url, epTitle in eps:
                if normalize:
                    title = "%s - %s" % (sTitle, formatSxxExx(sNum, eNum))
                else:
                    title = epTitle or "%s - %s %s, %s %s" % (sTitle, _("Season"), sNum, _("Episode"), eNum)
                params = stripPagerKeys(dict(cItem), ("local_paging",))
                params.update({"good_for_fav": True, "category": "fo_episode", "title": title, "s_title": sTitle, "desc": desc,
                               "season": sNum, "episode": eNum, "meta_season": sNum, "meta_episode": eNum, "url": url})
                self.addVideo(params)
        self._localPaging(cItem, cItem.get("page", 1))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Filmoton.listSearchResult [%s] type[%s]" % (searchPattern, searchType))
        # one type: the site's paged search list; "all": the first page of both
        types = (searchType,) if searchType in ("movie", "tv_show") else ("movie", "tv_show")
        for postType in types:
            url = "%s?s=%s&post_type=%s" % (self.MAIN_URL, urllib_quote_plus(searchPattern), postType)
            if len(types) == 1:
                cItem = dict(cItem)
                cItem["url"] = url
                self.listItems(cItem)
                return
            sts, data = self.getPage(url)
            if sts:
                self._listCards(cItem, data)

    ###################################################
    # links
    ###################################################
    def _embeds(self, data):
        # players: lazy iframes (data-lazy-src) in the description / "Rezervni player" tab - only up to the related
        # titles and the comments; trailers are youtube/vimeo
        data = re.split(r'class="(?:movie|episode|tv-show)__related|<div id="comments"', data, maxsplit=1)[0]
        embeds = []
        for url in re.findall(r'<iframe[^>]+?(?:data-lazy-src|src)="(https?://[^"]+)"', data):
            url = url.replace("&amp;", "&")
            if url not in embeds and not re.search(r'youtube|youtu\.be|vimeo\.com|facebook\.com', url):
                embeds.append(url)
        return embeds

    def _imdbId(self, embeds):
        # vidsrc.sh/embed/movie/tt0133093 - the only place the site names the IMDb id
        return self.cm.ph.getSearchGroups(" ".join(embeds), r'/(tt\d{5,})')[0]

    def getLinksForVideo(self, cItem):
        printDBG("Filmoton.getLinksForVideo [%s]" % cItem.get("url"))
        urltab = []
        sts, data = self._getCachedPage(cItem.get("url", ""))
        if not sts:
            return []
        embeds = self._embeds(data)
        unsupported = []
        for url in embeds:
            host = self.up.getHostName(url)
            if self.up.checkHostSupport(url) != 1:
                printDBG("Filmoton: hoster not supported [%s]" % url)
                if host not in unsupported:
                    unsupported.append(host)
                continue
            urltab.append({"name": "%d. %s" % (len(urltab) + 1, host), "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            if unsupported:
                SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(unsupported))
            else:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        sidecarTxt = self._pageDesc(data) or cItem.get("desc", "")
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", ""), cItem.get("meta_title", ""), cItem.get("meta_year", ""), self._imdbId(embeds),
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
        printDBG("Filmoton.getArticleContent [%s]" % cItem.get("url"))
        text = ""
        icon = cItem.get("icon", "")
        other = {}
        imdbId = ""
        mediaType = cItem.get("meta_type", "")
        sts, data = self._getCachedPage(cItem.get("url", ""))
        if sts:
            text = self._pageDesc(data)
            icon = icon or self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
            imdbId = self._imdbId(self._embeds(data))
            m = re.search(r'class="(?:movie|tv-show)__meta--genre">(.*?)</span>', data, re.S)
            if m:
                other["genres"] = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r'<a[^>]*>(.*?)</a>', m.group(1)))
            year = self.cm.ph.getSearchGroups(data, r'__meta--release-year">\s*([\d\s-]+?)\s*<')[0]
            if year:
                other["year"] = year
            duration = self.cm.ph.getSearchGroups(data, r'__meta--movie-run-time">\s*([^<]+?)\s*<')[0]
            if duration:
                other["duration"] = duration
            rating = self.cm.ph.getSearchGroups(data, r'fl-score--imdb"><b>IMDb</b>\s*(\d+(?:\.\d+)?)')[0]
            if rating and rating not in ("0", "0.0"):
                other["imdb_rating"] = "%s/10" % rating
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
        printDBG("Filmoton.handleService name[%s] category[%s]" % (name, category))
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
        CHostBase.__init__(self, Filmoton(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("filmoton")

    def getSearchTypes(self):
        # the site searches one type at a time (post_type); one type pages, "All" shows the first page of both
        return [(_("All"), "all"), (_("Movies"), "movie"), (_("Series"), "tv_show")]

    def withArticleContent(self, cItem):
        return cItem.get("meta_type", "") in ("movie", "tv")
