# -*- coding: utf-8 -*-
LAST_MODIFIED = "15.11.2026"
# 15.11.2026 - new host: videoteka.info (Bosnian/Croatian/Serbian subtitles; WordPress TOROFILM theme)
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getItemMeta, metaArticle
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx, extractNum
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized


LOCAL_PAGE_SIZE = 100  # rows per page of a long season (the site sends a season in one piece)


def GetConfigList():
    return []


def gettytul():
    return "https://videoteka.info/"


class Videoteka(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what a favourite needs to open the row again - nothing list/page specific
    FAV_FIELDS = ("name", "category", "type", "title", "url", "icon", "desc", "s_title", "season", "episode", "post_id",
                  "meta_type", "meta_title", "meta_year", "meta_season", "meta_episode", "good_for_fav")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "videoteka", "cookie": "videoteka.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies/")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("series/")},
            {"category": "list_filters", "title": _("Genres"), "filter": "category"},
            {"category": "list_filters", "title": _("Year"), "filter": "release"},
        ] + self.searchItems()
        self.filtersCache = {}
        self.pageCache = {}
        self.watchedHelper = IPTVWatchedHelper("videoteka")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = cItem.get("url", "")
            if not re.search(r'/(?:movies|series|episode)/[^/]+/?$', url):
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
        if len(self.pageCache) > 20:
            self.pageCache = {}
        self.pageCache[url] = data
        return True, data

    def _metaTitle(self, base):
        return re.split(r'\s+aka\s+', base, maxsplit=1, flags=re.I)[0].strip() or base

    ###################################################
    # lists
    ###################################################
    def listFilters(self, cItem):
        flt = cItem.get("filter", "")
        if not self.filtersCache:
            sts, data = self.getPage(self.MAIN_URL)
            if not sts:
                return
            for key, pattern in (("category", r'href="(https?://[^"/]+/category/[^"/]+/)"[^>]*>(.*?)</a>'),
                                 ("release", r'href="(https?://[^"/]+/release/(\d{4})/)"')):
                tab = []
                seen = set()
                for url, title in re.findall(pattern, data, re.S):
                    title = self.cleanHtmlStr(title)
                    if url in seen or title == "":
                        continue
                    seen.add(url)
                    tab.append({"title": title, "url": url})
                tab.sort(key=lambda item: item["title"].lower(), reverse=(key == "release"))
                self.filtersCache[key] = tab
        for item in self.filtersCache.get(flt, []):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": item["title"], "url": item["url"]})
            params.pop("filter", None)
            self.addDir(params)

    def _listCards(self, cItem, data):
        normalize = IsMediaNamingNormalized()
        seen = set()
        # only the list itself, not the sidebar widgets
        data = self.cm.ph.getDataBeetwenNodes(data, ("<main", ">"), ("</main", ">"), False)[1] or data
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<article class="post dfx fcl', "</article>"):
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+/(?:movies|series)/[^"]+)" class="lnk-blk"')[0]
            if url == "" or url in seen:
                continue  # news articles have no /movies/ or /series/ path
            seen.add(url)
            base = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h2 class="entry-title">(.*?)</h2>')[0])
            if base == "":
                continue
            year = self.cm.ph.getSearchGroups(item, r'<span class="year">\s*(\d{4})')[0]
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            isSeries = "/series/" in url
            title = "%s (%s)" % (base, year) if (normalize and year) else base
            params = stripPagerKeys(dict(cItem), ("base_url",))
            params.update({"good_for_fav": True, "title": title, "url": url, "icon": icon,
                           "desc": "%s%s" % (_("Series") if isSeries else _("Movie"), (" | %s" % year) if year else ""),
                           "meta_type": "tv" if isSeries else "movie", "meta_title": self._metaTitle(base), "meta_year": year})
            if isSeries:
                params.update({"category": "list_seasons", "s_title": base})
                self.addDir(params)
            else:
                params.update({"category": "vt_movie"})
                self.addVideo(params)

    def listItems(self, cItem):
        # paging: <path>/page/N/[?query]
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or re.sub(r"/page/\d+/?(?=$|\?)", "/", cItem["url"])
        path, sep, query = baseUrl.partition("?")
        pageUrlTpl = path.rstrip("/") + "/page/{page}/" + sep + query
        url = baseUrl if page <= 1 else pageUrlTpl.format(page=page)
        printDBG("Videoteka.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        self._listCards(cItem, data)
        lastPage = max([int(n) for n in re.findall(r'class="page-link[^"]*"[^>]*href="[^"]*/page/(\d+)/', data)] + [page])
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, lastPage > page and bool(self.currList), lastPage, pageUrlTpl)

    def _pageDesc(self, data):
        m = re.search(r'<div class="description">(.*?)</div>', data, re.S)
        return self.cleanHtmlStr(m.group(1)) if m else ""

    def listSeasons(self, cItem):
        printDBG("Videoteka.listSeasons [%s]" % cItem.get("url"))
        sts, data = self._getCachedPage(cItem["url"])
        if not sts:
            return
        desc = self._pageDesc(data) or cItem.get("desc", "")
        sTitle = cItem.get("s_title") or cItem.get("title", "")
        # <li class="sel-temp"><a data-post="116170" data-season="1" ...>Season 1</a>
        seasons = sorted(set(re.findall(r'<a data-post="(\d+)" data-season="(\d+)"', data)), key=lambda s: int(s[1]))
        if not seasons and 'id="episode_by_temp"' in data:
            seasons = [("", "1")]  # no season menu: the episodes listed on the page (listEpisodes without post_id)
        for postId, sNum in seasons:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s %s" % (sTitle, _("Season"), sNum),
                           "s_title": sTitle, "season": sNum, "post_id": postId, "desc": desc})
            self.addDir(params)
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No episodes found."))

    def listEpisodes(self, cItem):
        printDBG("Videoteka.listEpisodes [%s] season[%s]" % (cItem.get("url"), cItem.get("season")))
        season = str(cItem.get("season", ""))
        if cItem.get("post_id"):
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, **{"Referer": cItem["url"], "X-Requested-With": "XMLHttpRequest"})
            sts, data = self.getPage(self.getFullUrl("wp-admin/admin-ajax.php"), params,
                                     {"action": "action_select_season", "season": season, "post": cItem["post_id"]})
        else:
            sts, data = self._getCachedPage(cItem["url"])
            data = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", 'id="episode_by_temp"'), ("</ul", ">"), False)[1] if sts else ""
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        sTitle = cItem.get("s_title") or cItem.get("title", "")
        eps = []
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, "<article", "</article>"):
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+/episode/[^"]+)"')[0]
            eNum = self.cm.ph.getSearchGroups(item, r'class="num-epi">\s*\d+x(\d+)')[0]  # "2x1"
            if url == "" or eNum == "":
                continue
            eps.append((int(eNum), url, self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])))
        for eNum, url, icon in sorted(eps):
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(season, eNum))
            else:
                title = "%s - %s %s, %s %s" % (sTitle, _("Season"), season, _("Episode"), eNum)
            params = stripPagerKeys(dict(cItem), ("local_paging",))
            params.update({"good_for_fav": True, "category": "vt_episode", "title": title, "s_title": sTitle, "season": season,
                           "episode": str(eNum), "meta_season": season, "meta_episode": str(eNum), "url": url, "icon": icon or cItem.get("icon", "")})
            self.addVideo(params)
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No episodes found."))
        self._localPaging(cItem, cItem.get("page", 1))

    def _localPaging(self, cItem, page):
        # a long season: LOCAL_PAGE_SIZE rows per page (First page / Next page)
        lastPage = (len(self.currList) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
        if lastPage <= 1:
            return
        page = min(max(1, page), lastPage)
        self.currList = self.currList[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]
        params = dict(cItem)
        params["local_paging"] = True
        addPagingItems(self, params, page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Videoteka.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem["url"] = "%s?s=%s" % (self.MAIN_URL, urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Videoteka.getLinksForVideo [%s]" % cItem.get("url"))
        urltab = []
        sts, data = self._getCachedPage(cItem.get("url", ""))
        if not sts:
            return []
        # server tabs: <a class="btn" href="#options-N"> Sa prevodom <span>1</span> <span class="server">Hqq -ENGLISH</span></a>
        # + <div id="options-N"><iframe data-src="<site>/?trembed=N&trid=..&trtype=.."> -> that page holds the hoster iframe
        labels = {}
        for optId, label in re.findall(r'<a class="btn[^"]*" href="#(options-\d+)">(.*?)</a>', data, re.S):
            labels[optId] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(label, r'^\s*([^<]+)')[0])
        unsupported = []
        seen = set()
        for optId, embed in re.findall(r'<div id="(options-\d+)"[^>]*>\s*<iframe[^>]+?data-src="([^"]+)"', data):
            embed = embed.replace("&#038;", "&").replace("&amp;", "&")
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=cItem["url"])
            sts, frame = self.getPage(embed, params)
            url = self.cm.ph.getSearchGroups(frame, r'<iframe[^>]+src="([^"]+)"', ignoreCase=True)[0] if sts else ""
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            host = self.up.getHostName(url)
            if self.up.checkHostSupport(url) != 1:
                printDBG("Videoteka: hoster not supported [%s]" % url)
                if host not in unsupported:
                    unsupported.append(host)
                continue
            name = "%d. %s" % (len(urltab) + 1, host)
            if labels.get(optId):
                name += " (%s)" % labels[optId]
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            if unsupported:
                SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(unsupported))
            else:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        sidecarTxt = self._pageDesc(data) or cItem.get("desc", "")
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", ""), cItem.get("meta_title", ""), cItem.get("meta_year", ""), "", skip=(),
                                     season=cItem.get("meta_season", ""), episode=cItem.get("meta_episode", ""))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt, metaQuery=metaQuery))

    ###################################################
    # favourites / INFO
    ###################################################
    def getFavouriteData(self, cItem):
        if cItem.get("good_for_fav"):
            return self.getFavouriteFieldsData(cItem)
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _castField(self, data, name):
        m = re.search(r'<span>\s*%s\s*</span>\s*<p[^>]*>(.*?)</p>' % name, data, re.S)
        return ", ".join(self.cleanHtmlStr(a) for a in re.findall(r'<a[^>]*>(.*?)</a>', m.group(1))[:6]) if m else ""

    def getArticleContent(self, cItem):
        printDBG("Videoteka.getArticleContent [%s]" % cItem.get("url"))
        text = ""
        icon = cItem.get("icon", "")
        other = {}
        sts, data = self._getCachedPage(cItem.get("url", ""))
        if sts:
            text = self._pageDesc(data)
            icon = icon or self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
            m = re.search(r'<span class="genres">(.*?)</span>', data, re.S)
            if m:
                other["genres"] = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r'<a[^>]*>(.*?)</a>', m.group(1)))
            for key, pattern in (("duration", r'<span class="duration[^"]*">\s*([^<]+?)\s*<'),
                                 ("year", r'<span class="year[^"]*">\s*(\d{4})')):
                value = self.cm.ph.getSearchGroups(data, pattern)[0]
                if value:
                    other[key] = value
            # the moviemeta keys (directors / cast): a meta answer replaces the site's line instead of adding a second one
            for key, name in (("directors", "Direktor"), ("cast", "Glumci")):
                value = self._castField(data, name)
                if value:
                    other[key] = value
            rating = self.cm.ph.getSearchGroups(data, r'<span class="num">\s*(\d+(?:\.\d+)?)\s*</span>\s*<span>TMDB')[0]
            if rating and rating not in ("0", "0.0"):
                other["tmdb_rating"] = "%s/10" % rating
        return metaArticle(cItem, getItemMeta(cItem), story=text, poster=icon, info=other)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Videoteka.handleService name[%s] category[%s]" % (name, category))
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
        CHostBase.__init__(self, Videoteka(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("videoteka")

    def withArticleContent(self, cItem):
        return cItem.get("meta_type", "") in ("movie", "tv")
