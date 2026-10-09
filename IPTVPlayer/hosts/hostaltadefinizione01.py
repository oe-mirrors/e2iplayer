# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# Modified: 09.06.2026 - passata
# 27.09.2026 - paging past page 2, seasons in order, movies/episodes are playable rows (no extra folder),
# the player url goes straight to urlparser (parserVIXSRC), no "open in browser" dead end; Python 2 safe.
# Default icon = the bundled PNG logo instead of the site's favicon.ico (red X on the box). Domain alta-definizione.beer.
# 08.10.2026 - host standard (alta-definizione.beer):
#   - episodes get their own url (series page + "#s<season>e<episode>") - before every episode had the series url
#     (one downloaded marker for all of them); seasons are the page url + "#s<season>" and read the page again
#     (a favourite season no longer carries a frozen episode list)
#   - watched flag (series -> season -> episode), favourites reopen without state (also the old rows), downloaded
#     marker, "Show - SxxExx" names, sidecar on the links, INFO via moviemeta merged with the site's fields
#     (rating, year, duration, language, genres, cast, budget) instead of the unknown custom_items_list
#   - First / Jump / Next page with the last page from the pager (also for the search), local pages for the home
#     page (no title twice any more), Recently added / Top rated / Genres / Year menus ("Title (Year)" in the year
#     lists - the cards have no year), English menu labels, search history
#   - the vixsrc player url comes from the TMDb id in the row url (no page request when playing)
#   - default user agent instead of a fixed Chrome 120, covers with the cookie / UA of a Cloudflare check
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://alta-definizione.beer/"


PLAYER_URL = "https://vixsrc.to/"
LOCAL_PAGE_SIZE = 50


class Altadefinizione(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        # named after the host, not the domain: search history and cookies survive the next domain move
        CBaseHostClass.__init__(self, {"history": "altadefinizione01", "cookie": "altadefinizione01.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.USER_AGENT = self.HEADER.get("User-Agent", "")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        # the site only has a 16x16 favicon.ico, which the box can't draw (red X on the categories) - use our own logo
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/altadefinizione01135.png")
        self.MENU = [{"category": "list_items", "title": _("Home"), "url": self.MAIN_URL},
                     {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("archive?type=movie")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("archive?type=tv")},
                     {"category": "list_items", "title": _("Recently added"), "url": self.getFullUrl("archive?sort=date")},
                     {"category": "list_items", "title": _("Top rated"), "url": self.getFullUrl("archive?sort=vote")},
                     {"category": "list_items", "title": _("Archive"), "url": self.getFullUrl("archive")},
                     {"category": "list_genres", "title": _("Genres")},
                     {"category": "list_years", "title": _("Year")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("altadefinizione01")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl.split("#", 1)[0], addParams, post_data)

    def getFullIconUrl(self, url, currUrl=None):
        # the covers sit behind the same Cloudflare check as the pages: cf_clearance + the UA that passed it
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http"):
            return url
        meta = {"Referer": self.MAIN_URL, "User-Agent": self.USER_AGENT}
        try:
            # getCookieHeader logs tracebacks for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.USER_AGENT, "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"explore_item": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
            if cItem.get("type", "") == "video":
                prefix = "video"
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            if "#" not in url:
                # season / episode rows from before 08.10.2026 carried the plain series url
                if prefix == "season":
                    url = "%s#s%s" % (url, cItem.get("season", ""))
                elif prefix == "video" and cItem.get("season") and cItem.get("episode"):
                    url = "%s#s%se%s" % (url, cItem["season"], cItem["episode"])
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _pageUrlTpl(url):
        # the list url with "{page}" in its page parameter
        url = re.sub(r"[?&]page=-?\d+", "", url).replace("{", "{{").replace("}", "}}")
        return url + ("&" if "?" in url else "?") + "page={page}"

    @staticmethod
    def _tmdbId(url, data=""):
        # /detail/film-936075-michael, /detail/tv-108978-reacher: the TMDb id is in the url (and in the page script)
        match = re.search(r"/detail/(?:film|tv)-(\d+)", url or "") or re.search(r"var\s+tmdbID\s*=\s*(\d+)", data or "")
        return match.group(1) if match else ""

    def _siteInfo(self, data):
        # the fields of a detail page: (info dict, plot, year)
        info = {}
        meta = self.cm.ph.getDataBeetwenMarkers(data, 'class="detail-meta"', "</div>", False)[1]
        rating = self.cm.ph.getSearchGroups(meta, r'class="label rate">([^<]+)<')[0].strip()
        if rating:
            info["rating"] = rating + "/10"
        year = ""
        for value in re.findall(r'class="meta-item">([^<]+)<', meta):
            value = value.strip()
            if re.match(r"^(?:19|20)\d\d$", value):
                year = info["year"] = value
            elif re.match(r"^(?:\d+h\s*)?\d+m$", value):
                info["duration"] = value
            elif re.match(r"^[A-Z]{2}$", value):
                info["language"] = value
        genres = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r'class="genre-badge">([^<]+)<', data))
        if genres:
            info["genres"] = genres
        cast = ", ".join(self.cleanHtmlStr(c) for c in re.findall(r'class="cast-item">.*?<strong>([^<]+)</strong>', data, re.DOTALL)[:6])
        if cast:
            info["cast"] = cast
        budget = self.cm.ph.getSearchGroups(data, r'field-label">Budget</span>\s*<span>([^<]+)<')[0]
        if budget:
            info["budget"] = budget
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<p class="detail-overview">(.*?)</p>')[0])
        if not plot:
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]+)')[0])
            plot = re.sub(r"^Guarda .+? streaming gratis,\s*", "", plot)
        tagline = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<p class="detail-tagline">(.*?)</p>')[0])
        if tagline and plot:
            plot = "%s[/br]%s" % (tagline, plot)
        return info, plot, year

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("Altadefinizione.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        url = cItem["url"]
        localPaging = cItem.get("local_paging", False)
        pageUrlTpl = self._pageUrlTpl(url)
        sts, data = self.getPage(pageUrlTpl.format(page=page) if (page > 1 and not localPaging) else url)
        if not sts or not data:
            return
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination"', "</nav>", False)[1]
        cards = []
        for itemUrl, block in re.findall(r'<a href="([^"]+)" class="movie-card">(.*?)</a>', data, re.DOTALL):
            # the home page shows a title in several rows
            if itemUrl not in [c[0] for c in cards]:
                cards.append((itemUrl, block))
        localPaging = not pager and (localPaging or len(cards) > LOCAL_PAGE_SIZE)
        if localPaging:
            # the home page (no pager, ~150 titles): local pages
            lastPage = max(1, (len(cards) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE)
            page = min(page, lastPage)
            cards = cards[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]
        listYear = self.cm.ph.getSearchGroups(url, r"[?&]year=((?:19|20)\d\d)")[0]
        normalize = IsMediaNamingNormalized()
        for itemUrl, block in cards:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<h6 class="movie-card-title">(.*?)</h6>')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'alt="([^"]+)"')[0])
            if title in ("", "None"):
                # "None": a card of the site without data (Top rated)
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0])
            rating = self.cm.ph.getSearchGroups(block, r'class="label rate">([^<]+)<')[0].strip()
            isTv = "/tv-" in itemUrl
            desc = " | ".join(x for x in ("%s: %s" % (_("Rating"), rating) if rating else "", _("Series") if isTv else _("Movies")) if x)
            params = stripPagerKeys(dict(cItem), ("local_paging",))
            params.update({"good_for_fav": True, "title": title, "s_title": title, "s_year": listYear, "url": self.getFullUrl(itemUrl), "icon": icon,
                           "desc": desc, "tmdb_id": self._tmdbId(itemUrl), "meta_type": "tv" if isTv else "movie"})
            if isTv:
                params["category"] = "explore_item"
                self.addDir(params)
            else:
                if listYear and normalize:
                    # the cards carry no year - only the year lists know it
                    params["title"] = "%s (%s)" % (title, listYear)
                params["category"] = "video"
                self.addVideo(params)
        if localPaging:
            addPagingItems(self, dict(cItem, local_paging=True), page, page < lastPage, lastPage)
            return
        # the pager links every page ("<", 1, 2, ... 580, ">") - the next page is page + 1, the last the highest number
        pages = [int(n) for n in re.findall(r"[?&]page=(\d+)", pager)]
        hasNext = page + 1 in pages
        addPagingItems(self, cItem, page, hasNext, max(pages + [page]) if hasNext else page, pageUrlTpl if pager else "")

    def listSeasons(self, cItem):
        printDBG("Altadefinizione.listSeasons - %s" % cItem["url"])
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts or not data:
            return
        if "/tv-" not in url:
            # a film (an old favourite of the former film folder): its playable row
            self.addVideo(dict(cItem, category="video", url=url, meta_type="movie"))
            return
        _info, plot, year = self._siteInfo(data)
        seasons = sorted(set(re.findall(r'data-season="(\d+)"', data)), key=int)
        sTitle = cItem.get("s_title", "") or cItem["title"]
        fields = {"s_title": sTitle, "s_year": year, "tmdb_id": self._tmdbId(url, data), "desc": plot, "meta_type": "tv"}
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, category="list_episodes", season=seasons[0], url="%s#s%s" % (url, seasons[0]), **fields), data)
            return
        normalize = IsMediaNamingNormalized()
        for season in seasons:
            count = len(set(re.findall(r'data-episode="%s-(\d+)"' % season, data)))
            if not count:
                continue
            seasonTag = formatSxxExx(season) if normalize else "%s %s" % (_("Season"), season)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (sTitle, seasonTag), "season": season,
                           "url": "%s#s%s" % (url, season)})
            params.update(fields)
            params["desc"] = "%s: %d\n%s" % (_("Episodes"), count, plot)
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("Altadefinizione.listEpisodes - season %s" % cItem.get("season"))
        url = cItem["url"].split("#", 1)[0]
        season = str(cItem.get("season", "") or "1")
        if data is None:
            sts, data = self.getPage(url)
            if not sts or not data:
                return
            _info, plot, year = self._siteInfo(data)
            # s_title: old favourites ("Stagione 2") have no show name - the one of the page
            cItem = dict(cItem, tmdb_id=self._tmdbId(url, data) or cItem.get("tmdb_id", ""), s_year=year, desc=plot,
                         s_title=cItem.get("s_title", "") or self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<h1 class="detail-title">(.*?)</h1>')[0]))
        sTitle = cItem.get("s_title", "") or cItem["title"]
        normalize = IsMediaNamingNormalized()
        group = re.search(r'data-group-season="%s"[^>]*>(.*?)</div>' % re.escape(season), data, re.DOTALL)
        episodes = sorted(set(int(e) for e in re.findall(r'data-episode="%s-(\d+)"' % re.escape(season), group.group(1) if group else data)))
        for episode in episodes:
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            else:
                title = "%s - %s %s - %s %d" % (sTitle, _("Season"), season, _("Episode"), episode)
            params = stripPagerKeys(dict(cItem))
            params.pop("episodes", None)
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "url": "%s#s%se%d" % (url, season, episode),
                           "season": season, "episode": str(episode), "meta_type": "tv"})
            self.addVideo(params)

    def listGenres(self, cItem):
        printDBG("Altadefinizione.listGenres")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        seen = set()
        for url, title in re.findall(r'<a href="(/archive\?type=movie&(?:amp;)?genre_id=\d+)"[^>]*>([^<]+)</a>', data):
            if url in seen:
                continue
            seen.add(url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url.replace("&amp;", "&"))})
            self.addDir(params)

    def listYears(self, cItem):
        printDBG("Altadefinizione.listYears")
        sts, data = self.getPage(self.getFullUrl("archive"))
        if not sts:
            return
        select = self.cm.ph.getDataBeetwenMarkers(data, 'id="year-filter"', "</select>", False)[1]
        for year in re.findall(r'<option value="(\d{4})"', select):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": year, "url": self.getFullUrl("archive?year=%s" % year)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Altadefinizione.listSearchResult - Pattern: %s" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("search?q=%s" % urllib_quote_plus(searchPattern))})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getPlayerUrl(self, cItem):
        """vixsrc.to embed url of a film / episode, or '' (the TMDb id + media type, like the site's own player script)"""
        tmdb = str(cItem.get("tmdb_id", "") or "") or self._tmdbId(cItem.get("url", ""))
        if not tmdb:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return ""
            tmdb = self._tmdbId("", data)
        if not tmdb:
            return ""
        season, episode = str(cItem.get("season", "") or ""), str(cItem.get("episode", "") or "")
        if season and episode:
            return "%stv/%s/%s/%s?lang=it" % (PLAYER_URL, tmdb, season, episode)
        return "%smovie/%s?lang=it" % (PLAYER_URL, tmdb)

    def getLinksForVideo(self, cItem):
        printDBG("Altadefinizione.getLinksForVideo [%s]" % cItem.get("url"))
        embedUrl = self.getPlayerUrl(cItem)
        if not embedUrl:
            SetIPTVPlayerLastHostError(_("No player found for this title."))
            return []
        # resolved by urlparser (parserVIXSRC: token playlist, audio/video variants)
        urltab = [{"name": "VixSrc", "url": strwithmeta(embedUrl, {"Referer": self.MAIN_URL}), "need_resolve": 1}]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    def getVideoLinks(self, videoUrl):
        printDBG("Altadefinizione.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Altadefinizione.getArticleContent [%s]" % cItem.get("url"))
        info, plot, year = {}, "", cItem.get("s_year", "")
        sts, data = self.getPage(cItem.get("url", "") or cItem.get("prev_url", ""))
        if sts and data:
            info, plot, year = self._siteInfo(data)
        mediaType = cItem.get("meta_type", "") or ("tv" if "/tv-" in cItem.get("url", "") else "movie")
        title = cItem.get("s_title", "") or cItem.get("title", "")
        if sts and data:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<h1 class="detail-title">(.*?)</h1>')[0]) or title
        meta = {}
        try:
            meta = getMeta(mediaType, title, year)
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        metaPlot = meta.get("plot", "")
        text = plot or cItem.get("desc", "")
        if metaPlot and text and metaPlot not in text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
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
        elif category == "explore_item":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_years":
            self.listYears(self.currItem)
        elif category in ("play_video", "video"):
            # folder favourites from before 27.09.2026 (episode / film folders) - now the playable row itself
            self.addVideo(dict(self.currItem, category="video"))
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
        CHostBase.__init__(self, Altadefinizione(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("altadefinizione01")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("explore_item", "list_episodes", "play_video", "video")
