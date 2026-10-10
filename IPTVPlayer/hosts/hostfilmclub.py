# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Update: 06.06.2026 - Mr.X
# for Panda555
# 09.10.2026 - host standard:
#   - series: seasons / episodes from the episode list of the series page (a season row keeps the series url +
#     "#s<season>", no html snippet in the item any more - old favourite season rows reopen too), a series with
#     one season lists its episodes directly
#   - links: every server of the page ("Server 1" of an episode is an iframe, the others data-src - before only the
#     data-src ones were taken, an episode had byse only), the filmclub.store redirect resolved to the hoster,
#     the site's subtitles (Srpski / English / Hrvatski) go with each link instead of a host-wide list
#   - watched flag (series -> season -> episode), favourites reopen without state, downloaded marker on the
#     episode / film page url, "Title (Year)" / "Show - SxxExx" names, sidecar on the links
#   - INFO via moviemeta (IMDb id of the film page) merged with the site's fields (director, cast, genres, rating)
#   - First / Jump / Next page with the last page from the pager (Popular has none: its page 2 repeats page 1),
#     Movies menu, default user agent, covers with the Cloudflare cookie / UA
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://filmclub.tv/"


SUB_LANGS = {"srpski": "sr", "english": "en", "hrvatski": "hr", "bosanski": "bs", "slovenski": "sl", "makedonski": "mk"}


class FilmClub(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "FilmClub", "cookie": "FilmClub.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.USER_AGENT = self.HEADER.get("User-Agent", "")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("templates/playtube/img/apple-touch-icon.png")
        self.MENU = [{"category": "list_items", "title": _("New"), "url": self.getFullUrl("newvideos.html")},
                     {"category": "list_items", "title": _("Popular"), "url": self.getFullUrl("topvideos.php?do=recent"), "no_paging": True},
                     {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("category.php?cat=strani-filmovi")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("series/")},
                     {"category": "list_value", "title": _("Genres")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("filmclub")
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
            prefix = {"list_seasons": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
            if cItem.get("type", "") == "video":
                prefix = "video"
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            if prefix == "season" and "#" not in url:
                # season rows from before 09.10.2026 carried the plain series url
                season = self._season(cItem)
                if season:
                    url = "%s#s%s" % (url, season)
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _season(cItem):
        season = str(cItem.get("season", "") or "").strip()
        if not season:
            # season rows from before 09.10.2026: the html of the season panel in "se"
            match = re.search(r"collapse_(\d+)", cItem.get("se", "") or "") or re.search(r"#s(\d+)$", cItem.get("url", "") or "")
            season = match.group(1) if match else ""
        return season

    @staticmethod
    def _splitYear(title):
        # "Animals (2026)" -> ("Animals", "2026")
        match = re.match(r"^(.*?)\s*\(((?:19|20)\d\d)\)\s*$", title)
        return (match.group(1).strip(), match.group(2)) if match else (title.strip(), "")

    def _pager(self, data, page):
        # (hasNext, lastPage, pageUrlTpl) from <ul class="pagination">: "page-2/", "&page=2", "-videos-2-date.html"
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', "</ul>", False)[1]
        if not pager:
            return False, 0, ""
        links = [(self.getFullUrl(href.replace("&amp;", "&")), int(num)) for href, num in re.findall(r'href="([^"#][^"]*)">\s*(\d+)\s*<', pager)]
        hasNext = bool(re.search(r'href="[^"#][^"]*">\s*&raquo;', pager))
        tpl = ""
        for href, num in links:
            if num == page:
                continue
            tpl = re.sub(r"(page=|page-|-videos-)%d(?=\D|$)" % num, lambda m: m.group(1) + "{page}", href.replace("{", "{{").replace("}", "}}"), 1)
            if "{page}" in tpl:
                break
            tpl = ""
        lastPage = max([num for _href, num in links] + [page])
        return hasNext, lastPage, tpl

    def _subTracks(self, url):
        # c1_file=<vtt>&c1_label=Srpski ... (byse / vidara / iosbgaigo) or subtitles[]=Hrvatski;hr;<vtt> (voe)
        tracks = []
        for subUrl, label in re.findall(r"c\d+_file=([^&]+)&c\d+_label=([^&]+)", url):
            label = urllib_unquote(label)
            # the label first: "...S01E01.WEBRip.en.hi.vtt" ends in "hi" (hearing impaired), not a language
            lang = SUB_LANGS.get(label.lower(), "") or self.cm.ph.getSearchGroups(subUrl, r"[._]([a-z]{2})(?:[._](?:hi|sdh|forced))?\.vtt$")[0] or label.lower()[:2]
            tracks.append({"title": label, "url": urllib_unquote(subUrl), "lang": lang, "format": "vtt"})
        for value in re.findall(r"subtitles(?:\[\]|%5B%5D)=([^&]+)", url):
            parts = urllib_unquote(value).split(";", 2)
            if len(parts) == 3 and parts[2].startswith("http"):
                tracks.append({"title": parts[0], "url": parts[2], "lang": parts[1], "format": "vtt"})
        return tracks

    def _siteInfo(self, data):
        # the fields of a film / series / episode page: (info dict, plot, title, year, imdb id)
        info = {}
        for key, label in (("director", "Režiser"), ("rating", "Ocena"), ("genres", "Žanr"), ("cast", "Glumci")):
            value = self.cm.ph.getSearchGroups(data, r"(?s)<dt>%s:?</dt>\s*<dd>(.*?)</dd>" % label)[0]
            value = ", ".join(self.cleanHtmlStr(v) for v in re.findall(r">([^<]+)</a>", value)) if "</a>" in value else self.cleanHtmlStr(value)
            if value:
                info[key] = value
        if "genres" not in info:
            # series page: <span ...wmin-100">Žanr</span> <ul> <li><a ...>Western</a></li> ... </ul>
            genres = self.cm.ph.getSearchGroups(data, r'(?s)wmin-100">Žanr</span>(.*?)</ul>')[0]
            genres = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r">([^<]+)</a>", genres))
            if genres:
                info["genres"] = genres
        for key, label in (("seasons", "Sezone"), ("episodes", "Epizode")):
            value = self.cm.ph.getSearchGroups(data, r'wmin-100">%s</span>\s*<span>([^<]+)</span>' % label)[0]
            if value:
                info[key] = value.split("/")[-1].strip()
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<h1[^>]*>(.*?)</h1>")[0])
        title, year = self._splitYear(title)
        if year:
            info["year"] = year
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div itemprop="description">(.*?)</div>')[0])
        if not plot:
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'itemprop="description" content="([^"]+)')[0])
        if not plot:
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'name="description" content="([^"]+)')[0])
        imdb = self.cm.ph.getSearchGroups(data, r'"propertyID"\s*:\s*"imdb"\s*,\s*"value"\s*:\s*"(tt\d+)"')[0] or self.cm.ph.getSearchGroups(data, r"[?&]imdb=(tt\d+)")[0]
        return info, plot, title, year, imdb

    def _episodes(self, data):
        # {season: [(episode, url, title)]} in page order
        seasons = {}
        for url, title, season, episode in re.findall(r'<a href="([^"]+)" title="([^"]*)"[^>]*>\s*<span class="identifier[^"]*">\s*S(\d+)\s*-\s*E(\d+)', data):
            rows = seasons.setdefault(season, [])
            if episode not in [r[0] for r in rows]:
                rows.append((episode, self.getFullUrl(url), self.cleanHtmlStr(title)))
        return seasons

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("FilmClub.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        hasNext, lastPage, pageUrlTpl = self._pager(data, page)
        if "<h2>Serije sa prevodom" in data:
            # series/: the "popular series" carousel above the list would repeat on every page
            data = data.split("<h2>Serije sa prevodom", 1)[1]
        normalize = IsMediaNamingNormalized()
        seen, movies = set(), 0
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="pm-video-thumb', "</li>"):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            if not url or url in seen:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(item, 'data-echo="([^"]+)')[0] or self.cm.ph.getSearchGroups(item, 'img src="([^"]+)')[0]
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            sTitle, year = self._splitYear(label)
            dur = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'duration">([^<]+)')[0])
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)pm-rating-badge">(.*?)</div>')[0])
            desc = " | ".join(x for x in (_("Duration: %s") % dur if dur else "", "%s: %s" % (_("Rating"), rating) if rating else "") if x)
            params = stripPagerKeys(dict(cItem), ("no_paging", "is_search"))
            params.update({"good_for_fav": True, "title": label, "url": url, "icon": self.getFullIconUrl(icon), "desc": desc, "s_title": sTitle, "s_year": year})
            if "/series/" in url:
                params.update({"category": "list_seasons", "meta_type": "tv"})
                self.addDir(params)
            else:
                movies += 1
                if normalize and year:
                    params["title"] = "%s (%s)" % (sTitle, year)
                params.update({"category": "video", "meta_type": "movie"})
                self.addVideo(params)
        if cItem.get("no_paging"):
            return
        if cItem.get("is_search"):
            # the search pager lists pages that are empty - only a full page of films has a next one
            hasNext, lastPage = hasNext and movies >= 20, 0
        addPagingItems(self, cItem, page, hasNext, lastPage, pageUrlTpl)

    def listSeasons(self, cItem):
        printDBG("FilmClub.listSeasons |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        _info, plot, title, year, _imdb = self._siteInfo(data)
        seasons = self._episodes(data)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", "") or title or cItem["title"]
        fields = {"s_title": sTitle, "s_year": year or cItem.get("s_year", ""), "desc": plot or cItem.get("desc", "")}
        order = sorted(seasons, key=int)
        if len(order) == 1:
            self.listEpisodes(dict(cItem, category="list_episodes", season=order[0], url="%s#s%s" % (url, order[0]), **fields), data)
            return
        normalize = IsMediaNamingNormalized()
        for season in order:
            seasonTag = formatSxxExx(season) if normalize else "%s %s" % (_("Season"), season)
            params = stripPagerKeys(dict(cItem))
            params.pop("se", None)
            params.update(fields)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (sTitle, seasonTag), "season": season,
                           "url": "%s#s%s" % (url, season), "desc": "%s: %d\n%s" % (_("Episodes"), len(seasons[season]), fields["desc"])})
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("FilmClub.listEpisodes |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        season = self._season(cItem)
        if data is None:
            sts, data = self.getPage(url)
            if not sts:
                return
            _info, plot, title, year, _imdb = self._siteInfo(data)
            # old favourites ("Show - Season 2") have no show name field - the one of the page
            cItem = dict(cItem, s_title=cItem.get("s_title", "") or title, s_year=cItem.get("s_year", "") or year, desc=plot or cItem.get("desc", ""))
        sTitle = cItem.get("s_title", "") or cItem["title"]
        normalize = IsMediaNamingNormalized()
        for episode, epUrl, epTitle in self._episodes(data).get(season, []):
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            else:
                title = "%s - %s %s - %s %s" % (sTitle, _("Season"), season, _("Episode"), episode)
                if epTitle and not re.match(r"^Episode \d+$", epTitle):
                    title = "%s - %s" % (title, epTitle)
            params = stripPagerKeys(dict(cItem))
            params.pop("se", None)
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "url": epUrl, "season": season,
                           "episode": episode, "ep_title": epTitle, "meta_type": "tv",
                           "desc": "%s\n%s" % (epTitle, cItem.get("desc", "")) if epTitle else cItem.get("desc", "")})
            self.addVideo(params)

    def listValue(self, cItem):
        printDBG("FilmClub.listValue")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'class="pt-menu-title">ŽANROVI', "</ul>", False)[1]
        for url, title in re.findall(r'href="([^"]+)".*?<span>([^<]+)', data, re.DOTALL):
            # the menu has "...-videos-1-datehtml" for one genre
            url = re.sub(r"-datehtml$", "-date.html", url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmClub.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "is_search": True, "url": self.getFullUrl("search.php?keywords=%s" % urllib_quote_plus(searchPattern))})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _redirect(self, url):
        # filmclub.store/play_*.php / *-tv.php answer with a 302 to the hoster
        params = dict(self.defaultParams)
        params.update({"no_redirection": True, "header": dict(self.HEADER, Referer=self.MAIN_URL)})
        for _i in range(3):
            if "filmclub.store" not in url:
                break
            sts, _data = self.cm.getPage(url, params)
            location = self.cm.meta.get("location", "") if sts else ""
            if not location:
                break
            url = self.getFullUrl(location, url)
        return url

    def getLinksForVideo(self, cItem):
        printDBG("FilmClub.getLinksForVideo [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        # <div ... id="server1"> <iframe src=...> (episodes) or data-src=... (lazy tabs, films' placeholder)
        servers = []
        parts = re.split(r'id="server(\d+)"', data)
        for idx in range(1, len(parts) - 1, 2):
            src = self.cm.ph.getSearchGroups(parts[idx + 1], r'(?:data-src|iframe src)="([^"]+)"')[0]
            if src:
                servers.append((parts[idx], src))
        if not servers:
            servers = [(str(n + 1), src) for n, src in enumerate(re.findall(r'data-src="([^"]+)', data))]
        urltab = []
        for num, src in servers:
            url = self._redirect(self.getFullUrl(src.replace("&amp;", "&")))
            if not self.cm.isValidUrl(url) or "filmclub." in self.up.getDomain(url):
                continue
            isVoe = "voe" in src.lower()
            if isVoe and self.up.checkHostSupport(url) != 1:
                # play_voe.php sends to a new voe mirror domain every few days - voe.sx serves the same ids
                url = url.replace(self.up.getDomain(url), "voe.sx", 1)
            meta = {"Referer": self.MAIN_URL}
            tracks = self._subTracks(url)
            if tracks:
                meta["filmclub_subs"] = json_dumps(tracks)
            hoster = "Voe" if isVoe else self.up.getHostName(url).capitalize()
            urltab.append({"name": "%s %s - %s" % (_("Server"), num, hoster), "url": strwithmeta(url, meta), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    def getVideoLinks(self, videoUrl):
        printDBG("FilmClub.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        videoUrl = strwithmeta(videoUrl)
        siteSubs = []
        try:
            if videoUrl.meta.get("filmclub_subs"):
                siteSubs = json_loads(videoUrl.meta["filmclub_subs"])
        except Exception:
            printExc()
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        links = decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        if siteSubs:
            known = [s["url"] for s in siteSubs]
            for item in links:
                url = strwithmeta(item["url"])
                # the site's tracks first, the hoster's own after them
                tracks = siteSubs + [t for t in (url.meta.get("external_sub_tracks") or []) if t.get("url") not in known]
                item["url"] = strwithmeta(url, {"external_sub_tracks": tracks})
        return links

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("FilmClub.getArticleContent [%s]" % cItem)
        info, plot, title, year, imdb = {}, "", "", "", ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot, title, year, imdb = self._siteInfo(data)
        mediaType = cItem.get("meta_type", "") or ("tv" if "/series/" in cItem.get("url", "") else "movie")
        isEpisode = mediaType == "tv" and cItem.get("type") == "video"
        if isEpisode:
            # the page of an episode: h1 = the episode title, no year
            title, year = "", ""
            info.pop("year", None)
        sTitle = cItem.get("s_title", "") or title or cItem.get("title", "")
        year = cItem.get("s_year", "") or year
        meta = {}
        try:
            if imdb and mediaType == "movie":
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and sTitle:
                meta = getMeta(mediaType, sTitle, year)
        except Exception:
            printExc()
        metaInfo = dict(meta.get("info", {}))
        metaInfo.update(info)
        if year and "year" not in metaInfo:
            metaInfo["year"] = year
        metaPlot = meta.get("plot", "")
        text = plot or cItem.get("desc", "")
        if isEpisode and cItem.get("ep_title") and cItem["ep_title"] not in text:
            text = "%s[/br]%s" % (cItem["ep_title"], text)
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": metaInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_value":
            self.listValue(self.currItem)
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
        CHostBase.__init__(self, FilmClub(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("filmclub")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
