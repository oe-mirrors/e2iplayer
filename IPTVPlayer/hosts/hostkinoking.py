# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# 02.09.2026 - rewrite for the redesigned kinoking.cc
#   (Tailwind "fav-data-source" cards; series.php?id=..&season=.. -> inline allEpisodesData JSON
#    with video_links) + watched flag / sidecar / name norm.
# 07.10.2026 - movies: movie.php now ships its server list as "const SERVERS = [...]" (mirrors per
#   server, the DeVideoSRC entry expanded through libs/meinecloud.py; the vidsync/cinesrc aggregators
#   are skipped) - the old ?link= server pages are gone, the host asked up to 11 slow pages for nothing.
#   Series: seasons from allEpisodesData (all of them), episodes without own video_links are listed too -
#   their links come from the page's ajax_huhu_links / ajax_fp_links answers like in the browser.
#   First/Jump/Next paging, "Title (Year)" / "Show - SxxExx", episodes keyed on their own url (downloaded
#   marker), INFO via moviemeta merged with the site's fields.
# 08.10.2026 - TMDb posters as w342 instead of the original (up to 2 MB a cover).
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.libs.meinecloud import MeineCloud, MAIN_URL as MC_URL, isPlayerUrl
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized


def GetConfigList():
    return []


def gettytul():
    return "https://kinoking.cc/"


# aggregator players (vidsync / cinesrc) are pages of other players - no hoster urlparser knows
AGGREGATOR_RE = re.compile(r"(?:vidsync|cinesrc)\.")
CARDS_PER_PAGE = 20
EPISODES_PER_PAGE = 100


class KinoKing(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "KinoKing", "cookie": "KinoKing.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "max_data_size": 1024 * 1024, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("index.php?genre=current-movies&filter=movies&view=grid&page=")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("index.php?genre=recently-added&filter=series&view=grid&page=")}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("kinoking")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if cItem.get("type", "") in ("video", "audio"):
                if category == "episode":
                    sid = str(cItem.get("s_id", "") or "").strip()
                    season = str(cItem.get("season", "") or "").strip()
                    epnum = str(cItem.get("ep_num", "") or "").strip()
                    if sid and epnum:
                        return "episode:%s|%s|%s" % (sid, season, epnum)
                    vl = str(cItem.get("video_links", "") or "").strip()
                    return "episode:%s" % vl if vl else ""
                url = str(cItem.get("url", "") or "").strip()
                return "video:%s" % url if url else ""
            if category == "kk_series":
                url = str(cItem.get("url", "") or "").strip()
                return "series:%s" % url if url else ""
            if category == "kk_season":
                url = str(cItem.get("url", "") or "").strip()
                return "season:%s" % url if url else ""
            return ""
        except Exception:
            printExc()
        return ""

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _getJson(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return []
        try:
            data = json.loads(data)
        except Exception:
            return []
        return data if isinstance(data, list) else []

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("KinoKing.listItems |%s|" % cItem)
        url = cItem.get("base_url") or cItem["url"]
        page = int(cItem.get("page", 1) or 1)
        isSearch = "search=" in url
        sts, data = self.getPage(url if isSearch else url + str(page))
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        cnt = 0
        seen = set()
        for block in data.split("fav-data-source")[1:]:
            attrs = block.split(">", 1)[0]
            cid = self.cm.ph.getSearchGroups(attrs, r'data-id="(\d+)"')[0]
            ctype = self.cm.ph.getSearchGroups(attrs, r'data-type="([^"]+)"')[0]
            if cid == "" or ctype == "" or (ctype, cid) in seen:
                continue
            seen.add((ctype, cid))
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(attrs, r'data-title="([^"]*)"')[0])
            icon = self.cm.ph.getSearchGroups(attrs, r'data-img="([^"]*)"')[0]
            if re.search(r'/t/p/[^/]+/?$', icon):
                # a title without a poster carries the bare TMDb size path (.../t/p/w500) - that is no picture
                icon = ""
            # the site links the TMDb original (up to 2 MB a poster) - w342 is plenty for the box
            icon = re.sub(r'(image\.tmdb\.org/t/p/)original/', r'\1w342/', icon)
            quality = self.cm.ph.getSearchGroups(attrs, r'data-quality="([^"]*)"')[0]
            tmdb = self.cm.ph.getSearchGroups(attrs, r'data-tmdb="(\d+)"')[0]
            card = block[:5000]
            year = self.cm.ph.getSearchGroups(card, r">\s*((?:19|20)\d{2})\s*</span>")[0]
            rating = self.cm.ph.getSearchGroups(card, r"</i>\s*(\d+(?:\.\d+)?)\s*</span>")[0]
            release = self.cm.ph.getSearchGroups(card, r">\s*(\d{2}\.\d{2}\.\d{4})\s*</span>")[0]
            desc = " | ".join("%s: %s" % (label, value) for label, value in ((_("Year"), year), (_("Rating"), rating), (_("Quality"), quality), (_("Released"), release)) if value)
            cnt += 1
            params = stripPagerKeys(dict(cItem), ("base_url",))
            params.update({"good_for_fav": True, "icon": icon, "desc": desc, "s_title": title, "tmdb": tmdb, "s_year": year, "meta_title": title, "meta_year": year})
            if ctype == "series":
                params.update({"category": "kk_series", "title": title, "s_id": cid, "url": "%sseries.php?id=%s" % (self.MAIN_URL, cid), "meta_type": "tv"})
                self.addDir(params)
            else:
                if normalize:
                    dispTitle = "%s (%s)" % (title, year) if year else title
                else:
                    dispTitle = "%s [%s]" % (title, quality) if quality else title
                params.update({"category": "movie", "title": dispTitle, "url": "%smovie.php?id=%s" % (self.MAIN_URL, cid), "meta_type": "movie"})
                self.addVideo(params)
        if not isSearch:
            # endless "load more" list - no last page known
            addPagingItems(self, dict(cItem, base_url=url, url=url), page, cnt >= CARDS_PER_PAGE, 0, url.replace("{", "{{").replace("}", "}}") + "{page}")

    def _episodes(self, url):
        """(allEpisodesData list, page data) of a series page"""
        sts, data = self.getPage(url)
        if not sts:
            return [], ""
        m = re.search(r'allEpisodesData\s*=\s*(\[.*?\])\s*;', data, re.DOTALL)
        try:
            episodes = json.loads(m.group(1)) if m else []
        except Exception:
            printExc()
            episodes = []
        return [ep for ep in episodes if isinstance(ep, dict)], data

    def _seriesFields(self, cItem, data):
        # what the episode links need (huhu: TMDb id, filmpalast: title + year)
        return {"tmdb": cItem.get("tmdb", "") or self.cm.ph.getSearchGroups(data, r"TMDB_SERIES_ID\s*=\s*'(\d+)'")[0],
                "s_year": cItem.get("s_year", "") or self.cm.ph.getSearchGroups(data, r"seriesYear\s*=\s*'(\d+)'")[0]}

    def listSeasons(self, cItem):
        printDBG("KinoKing.listSeasons")
        url = cItem["url"].split("&season=")[0]
        episodes, data = self._episodes(url)
        seasons = sorted(set(int(ep.get("season_number") or 0) for ep in episodes if str(ep.get("season_number", "")).isdigit()))
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]+)')[0])
        sTitle = cItem.get("s_title", cItem["title"])
        fields = self._seriesFields(cItem, data)
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, category="kk_season", season=str(seasons[0]), url="%s&season=%s" % (url, seasons[0]), **fields), episodes)
            return
        for snum in seasons:
            count = len([ep for ep in episodes if str(ep.get("season_number")) == str(snum)])
            seasonTag = formatSxxExx(snum) if IsMediaNamingNormalized() else "%s %s" % (_("Season"), snum)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "kk_season", "title": "%s - %s" % (sTitle, seasonTag), "s_title": sTitle, "season": str(snum),
                           "url": "%s&season=%s" % (url, snum), "desc": "%s: %d\n%s" % (_("Episodes"), count, desc)})
            params.update(fields)
            self.addDir(params)

    def listEpisodes(self, cItem, episodes=None):
        printDBG("KinoKing.listEpisodes")
        if episodes is None:
            episodes, data = self._episodes(cItem["url"])
            cItem = dict(cItem, **self._seriesFields(cItem, data))
        normalize = IsMediaNamingNormalized()
        sTitle = cItem.get("s_title", cItem["title"])
        wantSeason = str(cItem.get("season", "") or "").strip()
        episodes = [ep for ep in episodes if not wantSeason or str(ep.get("season_number", "")).strip() == wantSeason]
        # podcasts / soaps have hundreds of episodes in one season - 100 per page
        page = int(cItem.get("page", 1) or 1)
        lastPage = (len(episodes) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE
        for ep in episodes[(page - 1) * EPISODES_PER_PAGE:page * EPISODES_PER_PAGE]:
            epName = self.cleanHtmlStr(ep.get("name", "") or "")
            season, epNum = ep.get("season_number", ""), ep.get("episode_number", "")
            if normalize and season and epNum:
                title = "%s - %s" % (sTitle, formatSxxExx(season, epNum))
            else:
                title = " - ".join(x for x in (sTitle, "S%s E%s" % (season, epNum) if epNum else "", epName) if x)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "episode", "title": title, "url": "%s#e%s" % (cItem["url"], epNum),
                           "s_id": cItem.get("s_id", ""), "season": str(season), "ep_num": epNum,
                           "video_links": ep.get("video_links") or "", "desc": self.cleanHtmlStr(ep.get("overview", "") or "")})
            self.addVideo(params)
        if lastPage > 1:
            # the page lives in cItem["page"] - the template keeps the season url unchanged
            addPagingItems(self, dict(cItem, category="kk_season"), page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KinoKing.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("index.php?search=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _appendHosterLinks(self, urltab, raw, referer, label=""):
        for url in raw:
            url = (url or "").strip()
            if url == "":
                continue
            url = "https:" + url if url.startswith("//") else url
            if not self.cm.isValidUrl(url) or AGGREGATOR_RE.search(url) or url in [str(x["url"]) for x in urltab]:
                continue
            if isPlayerUrl(url):
                # the DeVideoSRC player is a mirror list, not a hoster
                subs = MeineCloud(self.cm, {"header": self.HEADER}, self.MAIN_URL).movieLinks(MeineCloud.imdbFromUrl(url)) if "/movie/" in url else []
                self._appendHosterLinks(urltab, [sub for sub in subs if "/vod/" not in sub], MC_URL)
                continue
            name = self.up.getHostName(url).capitalize()
            lang = self.cm.ph.getSearchGroups(url, r"default_audio_language=([a-z]+)")[0]
            tag = "%s %s" % (label, lang.upper()) if (label and lang) else label
            urltab.append({"name": "%s [%s]" % (name, tag) if tag else name, "url": strwithmeta(url, {"Referer": referer}), "need_resolve": 1})

    def _episodeLinks(self, cItem, urltab):
        videoLinks = cItem.get("video_links")
        if videoLinks:
            # own links of the site: comma separated (old favourites: a json list)
            try:
                parsed = json.loads(videoLinks)
                raw = parsed if isinstance(parsed, list) else [str(parsed)]
            except Exception:
                raw = re.split(r"[\s,;|]+", str(videoLinks))
            self._appendHosterLinks(urltab, raw, self.MAIN_URL)
        sid, season, epNum = cItem.get("s_id", ""), cItem.get("season", ""), cItem.get("ep_num", "")
        if not (sid and epNum):
            return
        base = "%sseries.php?id=%s" % (self.MAIN_URL, sid)
        if cItem.get("tmdb"):
            for row in self._getJson("%s&ajax_huhu_links=1&tmdb=%s&s=%s&e=%s" % (base, cItem["tmdb"], season, epNum)):
                if isinstance(row, dict):
                    self._appendHosterLinks(urltab, row.get("urls") if row.get("is_group") else [row.get("link_url", "")], self.MAIN_URL, row.get("host", ""))
        title = cItem.get("s_title", "")
        if title:
            for row in self._getJson("%s&ajax_fp_links=1&title=%s&y=%s&s=%s&e=%s" % (base, urllib_quote_plus(title), cItem.get("s_year", ""), season, epNum)):
                if isinstance(row, dict):
                    self._appendHosterLinks(urltab, [row.get("link_url", "")], self.MAIN_URL, row.get("host", ""))

    def _movieLinks(self, cItem, urltab):
        # movie.php: const SERVERS = [{"name": "VOE (FILMO DE)", "mirrors": [...]}, ...] (the page takes ~10 s)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return ""
        try:
            servers = json.loads(self.cm.ph.getSearchGroups(data, r"const SERVERS\s*=\s*(\[.*?\]);\s*\n")[0] or "[]")
        except Exception:
            printExc()
            servers = []
        for srv in servers:
            if isinstance(srv, dict):
                self._appendHosterLinks(urltab, srv.get("mirrors") or [], self.MAIN_URL, self.cleanHtmlStr(srv.get("name", "")))
        return self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]+)')[0])

    def getLinksForVideo(self, cItem):
        printDBG("KinoKing.getLinksForVideo [%s]" % cItem)
        urltab = []
        sidecarTxt = cItem.get("desc", "")
        if cItem.get("category") == "episode":
            self._episodeLinks(cItem, urltab)
        else:
            pageDesc = self._movieLinks(cItem, urltab)
            sidecarTxt = sidecarTxt or pageDesc
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("KinoKing.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("KinoKing.getArticleContent [%s]" % cItem)
        mediaType = "movie" if cItem.get("category") == "movie" else "tv"
        title = cItem.get("meta_title", "") or cItem.get("s_title", "") or cItem.get("title", "")
        year = cItem.get("meta_year", "") or cItem.get("s_year", "")
        story, imdb = "", ""
        if mediaType == "tv" and cItem.get("s_id"):
            # the series page answers fast (movie.php takes ~10 s - movies use the title lookup only)
            sts, data = self.getPage("%sseries.php?id=%s" % (self.MAIN_URL, cItem["s_id"]))
            if sts:
                imdb = self.cm.ph.getSearchGroups(data, r"(tt\d{6,9})")[0]
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and title:
                meta = getMeta(mediaType, title, year)
        except Exception:
            printExc()
        info = dict(meta.get("info", {}))
        if year and "year" not in info:
            info["year"] = year
        story = cItem.get("desc", "") if cItem.get("category") == "episode" else ""
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = cItem.get("icon", "") or meta.get("poster", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("KinoKing.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "kk_series":
            self.listSeasons(self.currItem)
        elif category == "kk_season":
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, KinoKing(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("kinoking")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("kk_series", "kk_season")
