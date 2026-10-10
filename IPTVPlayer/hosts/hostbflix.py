# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 26.12.2025 - fixed pycurl for py3 version - by Mr.X
# 09.10.2026 - host standard:
#   - links: the subdrc.xyz redirect is followed when the links are listed (real hoster name, one row per hoster -
#     films list "Filemoon" and "Doodstream" with the same vidsrc url); getVideoLinks returned the url string
#     instead of a list when the redirect failed; the site's subtitles (c1_file) go with the link
#   - seasons keep the series url + "#s<season>" (episodes come from the season's ajax list), a series with one
#     season lists its episodes directly; episodes have their own page url (".../<season>-<episode>/")
#   - watched flag (series -> season -> episode), favourites reopen without state (also the old season rows with
#     the ajax url), downloaded marker, "Title (Year)" / "Show - SxxExx" names, sidecar on the links,
#     INFO via moviemeta merged with the site's fields (genres, country, director, cast, production, release)
#   - First / Jump / Next page with the last page (Top-IMDB has none: its page 2 repeats page 1),
#     default user agent, Cloudflare: getPageCFProtection
# 10.10.2026 - Vidmoly / Filemoon links play again (their subdrc subtitle in the query was taken for the subdrc
#   redirect); a doubled subtitle query no longer gives a broken "Romanian?c1_file=..." track
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
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
    return "https://bflix.sh/"


# the subdrc.xyz redirect itself - not a hoster url whose query names a subdrc subtitle (?sub.info=https://subdrc.xyz/...)
SUBDRC_RE = re.compile(r"https?://(?:[^/?#]+\.)?subdrc\.", re.I)


class Bflix(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Bflix", "cookie": "Bflix.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.USER_AGENT = self.HEADER.get("User-Agent", "")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + "images/logo.png"
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies/")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("tv-series/")},
                     {"category": "list_items", "title": _("Top-IMDB"), "url": self.getFullUrl("top-imdb/"), "no_paging": True},
                     {"category": "list_value", "title": _("Genres"), "s": "Genre<"},
                     {"category": "list_value", "title": _("Country"), "s": "Country<"}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("bflix")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl.split("#", 1)[0], addParams, post_data)

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
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _pageUrlTpl(url):
        # ".../movies/" or ".../movies/page/3/" -> ".../movies/page/{page}/"; search?keyword=x -> search/x/page/{page}/
        url = url.split("#", 1)[0].replace("{", "{{").replace("}", "}}")
        match = re.search(r"[?&]keyword=([^&]+)", url)
        if match:
            return "%ssearch/%s/page/{page}/" % (gettytul(), match.group(1).replace("+", "%20"))
        url = re.sub(r"page/\d+/?$", "", url)
        return url + ("" if url.endswith("/") else "/") + "page/{page}/"

    def _subTracks(self, url):
        # c1_file=<vtt>&c1_label=Romana ... in the hoster url
        # (subdrc sometimes doubles the query: "...&c1_label=Romanian?c1_file=...&c1_label=Romana")
        tracks, seen = [], set()
        for subUrl, label in re.findall(r"c\d+_file=([^&?]+)&c\d+_label=([^&?]+)", url):
            label = urllib_unquote(label)
            if urllib_unquote(subUrl) in seen:
                continue
            seen.add(urllib_unquote(subUrl))
            lang = self.cm.ph.getSearchGroups(subUrl, r"[._]([a-z]{2})\.vtt$")[0] or {"romana": "ro", "english": "en"}.get(label.lower(), label.lower()[:2])
            tracks.append({"title": label, "url": urllib_unquote(subUrl), "lang": lang, "format": "vtt"})
        return tracks

    def _siteInfo(self, data):
        # (info dict, plot, title, year) of a film / series / episode page
        info = {}
        meta = data.split('cts-wrapper">', 1)[-1]
        for key, label in (("genres", "Genre"), ("country", "Country"), ("released", "Release"), ("year", "Year"), ("director", "Director"),
                           ("production", "Production"), ("cast", "Cast")):
            value = self.cm.ph.getSearchGroups(meta, r"(?s)<div>%s:</div>\s*<span>(.*?)</span>" % label)[0]
            value = ", ".join(self.cleanHtmlStr(v) for v in re.findall(r">([^<]+)</a>", value)) if "</a>" in value else self.cleanHtmlStr(value)
            if value:
                info[key] = value
        rating = self.cm.ph.getSearchGroups(data, r'class="rating">([0-9.]+)<')[0]
        if rating:
            info["imdb_rating"] = rating
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h1[^>]*class="film-title"[^>]*>(.*?)</h1>')[0])
        year = self.cm.ph.getSearchGroups(info.get("year", "") or info.get("released", ""), r"((?:19|20)\d\d)")[0]
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)film-desc cts-wrapper">(.*?)</div>')[0])
        return info, plot, title, year

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("Bflix.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination"', "</ul>", False)[1]
        pages = [int(n) for n in re.findall(r"/page/(\d+)/", pager)]
        lastPage = max(pages + [page])
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="film">', "</span></div>"):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            if not url or url in seen:
                continue
            seen.add(url)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getAllItemsBeetwenMarkers(item, '<div class="start">', "</div>")[0])
            # movies show the year there, series "SS 2 EP 2" instead
            year = self.cm.ph.getSearchGroups(item, r'class="dot">\s*(\d{4})\s*<')[0]
            params = stripPagerKeys(dict(cItem), ("no_paging", "s"))
            params.update({"good_for_fav": True, "title": title, "url": url, "icon": icon, "desc": desc, "s_title": title, "s_year": year})
            if "/series/" in url:
                params.update({"category": "list_seasons", "meta_type": "tv"})
                self.addDir(params)
            else:
                if normalize and year:
                    params["title"] = "%s (%s)" % (title, year)
                params.update({"category": "video", "meta_type": "movie"})
                self.addVideo(params)
        if not cItem.get("no_paging"):
            # the pager's own links ("search/the man/page/2/" with a blank) - else built from the list url
            tpl = self.cm.ph.getSearchGroups(pager, r'href="([^"]+/page/)\d+/?"')[0]
            tpl = tpl.replace(" ", "%20").replace("{", "{{").replace("}", "}}") + "{page}/" if tpl else self._pageUrlTpl(cItem["url"])
            addPagingItems(self, cItem, page, page < lastPage, lastPage, tpl)

    def _seasons(self, data):
        # [(season, ajax id)]
        seasons = []
        for season, ssId in re.findall(r'data-ss="(\d+)"[^>]*?data-id="([^"]+)"', data):
            if season not in [s[0] for s in seasons]:
                seasons.append((season, ssId))
        return seasons

    def listSeasons(self, cItem):
        printDBG("Bflix.listSeasons |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        _info, plot, title, year = self._siteInfo(data)
        seasons = self._seasons(data)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", "") or title or cItem["title"]
        fields = {"s_title": sTitle, "s_year": year or cItem.get("s_year", ""), "desc": plot or cItem.get("desc", "")}
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, category="list_episodes", season=seasons[0][0], url="%s#s%s" % (url, seasons[0][0]), **fields), seasons[0][1])
            return
        normalize = IsMediaNamingNormalized()
        for season, _ssId in seasons:
            seasonTag = formatSxxExx(season) if normalize else "%s %s" % (_("Season"), season)
            params = stripPagerKeys(dict(cItem))
            params.update(fields)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (sTitle, seasonTag), "season": season,
                           "url": "%s#s%s" % (url, season)})
            self.addDir(params)

    def listEpisodes(self, cItem, ssId=None):
        printDBG("Bflix.listEpisodes |%s|" % cItem)
        url = cItem["url"]
        season = str(cItem.get("season", "") or "")
        if "ajax.php?episode=" in url:
            # season rows from before 09.10.2026: the season's ajax url, the number only in the title
            ajaxUrl = url
            season = season or self.cm.ph.getSearchGroups(cItem.get("title", ""), r"(\d+)\s*$")[0]
        elif ssId:
            ajaxUrl = "%sajax/ajax.php?episode=%s" % (self.MAIN_URL, ssId)
        else:
            sts, data = self.getPage(url)
            if not sts:
                return
            _info, plot, title, year = self._siteInfo(data)
            cItem = dict(cItem, s_title=cItem.get("s_title", "") or title, s_year=cItem.get("s_year", "") or year, desc=plot or cItem.get("desc", ""))
            ssId = dict(self._seasons(data)).get(season, "")
            if not ssId:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
                return
            ajaxUrl = "%sajax/ajax.php?episode=%s" % (self.MAIN_URL, ssId)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self.MAIN_URL)
        sts, data = self.getPage(ajaxUrl, params)
        if not sts:
            return
        sTitle = cItem.get("s_title", "") or cItem.get("meta_title", "") or re.sub(r"\s*-\s*%s\s*\d+\s*$" % re.escape(_("Season")), "", cItem["title"])
        normalize = IsMediaNamingNormalized()
        for epUrl, label in re.findall(r'(?s)href="([^"]+)"[^>]*>\s*<span class="num">(.*?)</a>', data):
            label = self.cleanHtmlStr(label)
            match = re.search(r"/(\d+)-(\d+)/?$", epUrl)
            epSeason, episode = (match.group(1), match.group(2)) if match else (season, self.cm.ph.getSearchGroups(label, r"(\d+)")[0])
            if normalize and episode:
                title = "%s - %s" % (sTitle, formatSxxExx(epSeason or season, episode))
            else:
                title = "%s - %s %s - %s" % (sTitle, _("Season"), epSeason or season, label)
            epTitle = re.sub(r"^Episode\s*\d+\s*:\s*", "", label)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "url": self.getFullUrl(epUrl),
                           "season": epSeason or season, "episode": episode, "meta_type": "tv",
                           "desc": "%s\n%s" % (epTitle, cItem.get("desc", "")) if epTitle else cItem.get("desc", "")})
            self.addVideo(params)

    def listValue(self, cItem):
        printDBG("Bflix.listValue")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, cItem.get("s", "Genre<"), "</ul>", False)[1]
        for url, title in re.findall(r'href="([^"]+)"[^>]*>([^<]+)<', data):
            params = stripPagerKeys(dict(cItem), ("s",))
            params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Bflix.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": "%ssearch?keyword=%s" % (self.MAIN_URL, urllib_quote_plus(searchPattern))})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _redirect(self, url):
        # subdrc.xyz/players_*/... answers with a 302 to the hoster; "" when it does not
        params = dict(self.defaultParams)
        params.update({"no_redirection": True, "header": dict(self.HEADER, Referer=self.MAIN_URL)})
        sts, _data = self.cm.getPage(url, params)
        location = self.cm.meta.get("location", "") if sts else ""
        return self.getFullUrl(location, url) if location else ""

    def getLinksForVideo(self, cItem):
        printDBG("Bflix.getLinksForVideo [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        plUrl = self.cm.ph.getSearchGroups(data, r"const pl_url = '([^']+)")[0]
        if not plUrl:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=cItem["url"])
        sts, data = self.getPage(plUrl, params)
        if not sts:
            return []
        urltab, seen = [], set()
        for srv, srvUrl in re.findall(r'(?s)data-srv="([^"]+)"[^>]*?data-id="([^"]+)"', data):
            url = self._redirect(srvUrl) if SUBDRC_RE.match(srvUrl) else srvUrl
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            meta = {"Referer": self.MAIN_URL}
            tracks = self._subTracks(url)
            if tracks:
                meta["bflix_subs"] = json_dumps(tracks)
            urltab.append({"name": "%s - %s" % (self.cleanHtmlStr(srv), self.up.getHostName(url).capitalize()), "url": strwithmeta(url, meta), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    def getVideoLinks(self, videoUrl):
        printDBG("Bflix.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        videoUrl = strwithmeta(videoUrl)
        if SUBDRC_RE.match(videoUrl):
            # links listed before 09.10.2026 (favourites keep no links, but a cached list may)
            location = self._redirect(videoUrl)
            if not location:
                return []
            videoUrl = strwithmeta(location, videoUrl.meta)
        siteSubs = []
        try:
            if videoUrl.meta.get("bflix_subs"):
                siteSubs = json_loads(videoUrl.meta["bflix_subs"])
        except Exception:
            printExc()
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        links = decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        if siteSubs:
            known = [s["url"] for s in siteSubs]
            for item in links:
                url = strwithmeta(item["url"])
                tracks = siteSubs + [t for t in (url.meta.get("external_sub_tracks") or []) if t.get("url") not in known]
                item["url"] = strwithmeta(url, {"external_sub_tracks": tracks})
        return links

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Bflix.getArticleContent [%s]" % cItem)
        info, plot, title, year = {}, "", "", ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot, title, year = self._siteInfo(data)
        mediaType = cItem.get("meta_type", "") or ("tv" if "/series/" in cItem.get("url", "") else "movie")
        # old favourites: meta_title / meta_year
        sTitle = cItem.get("s_title", "") or cItem.get("meta_title", "") or title or cItem.get("title", "")
        year = cItem.get("s_year", "") or cItem.get("meta_year", "") or year
        meta = {}
        try:
            meta = getMeta(mediaType, sTitle, year)
        except Exception:
            printExc()
        metaInfo = dict(meta.get("info", {}))
        metaInfo.update(info)
        if year and "year" not in metaInfo:
            metaInfo["year"] = year
        metaPlot = meta.get("plot", "")
        text = cItem.get("desc", "") if cItem.get("episode") else (plot or cItem.get("desc", ""))
        if metaPlot and text and metaPlot not in text:
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
        CHostBase.__init__(self, Bflix(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("bflix")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
