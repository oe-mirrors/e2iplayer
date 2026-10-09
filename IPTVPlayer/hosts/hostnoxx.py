# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# 03.10.2026 - new host for noxx.gg (noxx.to), free TV series (English, TMDb catalogue)
#   Every visit first lands on /verify: a cookie check (token in the page, POST /verified -> PHPSESSID,
#   valid ~2 hours) that is passed here automatically, no captcha. Browse / genres / years / sort /
#   search through the JSON endpoint /api/load-more-browse, "Aired this week" from /timeline,
#   series page /tv/<slug> carries all seasons and episodes, episode page /tv/<slug>/<s>/<e> the
#   servers: Doodstream (myvidplay/playmogo) and SeekStreaming (seekplayer.vip) first, then videasy;
#   vidcore / vidup / vidfast only when the opt-in enc-dec.app resolving is switched on; the vidsrc player is skipped.
#   Watched flag / downloaded flag / name normalisation / sidecar / moviemeta INFO / favourites /
#   paging (First / Jump / Next, the endpoint only tells whether there is more).
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized, IsExternalResolveAllowed
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://noxx.gg/"


EPISODE_RE = re.compile(r'^https?://[^/]+/tv/([^/?#]+)/(\d+)/(\d+)')
SERIES_RE = re.compile(r'^https?://[^/]+/tv/([^/?#]+)/?$')
TMDB_IMG = "https://image.tmdb.org/t/p/w342"
# the release-year filter of the site
YEAR_RANGES = ("2025-2026", "2020-2024", "2015-2019", "2010-2014", "2005-2009", "2000-2004")


class Noxx(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what identifies a row and is needed to open it again
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "slug", "season", "episode", "series_url",
                  "icon", "desc", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "noxx", "cookie": "noxx.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_timeline", "title": _("Aired this week"), "url": self.getFullUrl("/timeline")},
                     {"category": "list_browse", "title": _("Latest"), "filters": {}},
                     {"category": "list_browse", "title": _("Top rated"), "filters": {"s": "rating"}},
                     {"category": "list_browse", "title": _("Alphabetically"), "filters": {"s": "alphabetical"}},
                     {"category": "list_genres", "title": _("Genres"), "url": self.getFullUrl("/browse")},
                     {"category": "list_years", "title": _("Year")}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("noxx")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            url = str(cItem.get("url", "") or "").strip()
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url if url else ""
            if category == "nx_series":
                return "series:%s" % url if url else ""
            if category == "nx_season":
                slug = str(cItem.get("slug", "") or "").strip()
                season = str(cItem.get("season", "") or "").strip()
                return "season:%s|%s" % (slug, season) if slug and season else ""
            return ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # HTTP + the /verify cookie check
    ###################################################
    def _isVerifyPage(self, data):
        return 'var verifyEndpoint' in data and 'var token' in data

    def _passVerify(self, data, pageUrl):
        token = self.cm.ph.getSearchGroups(data, r'var\s+token\s*=\s*"([^"]+)"')[0]
        endpoint = self.cm.ph.getSearchGroups(data, r'var\s+verifyEndpoint\s*=\s*"([^"]+)"')[0] or "/verified"
        if not token:
            return False
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Referer": pageUrl or self.MAIN_URL, "Origin": self.MAIN_URL.rstrip("/")})
        sts, resp = self.cm.getPage(self.getFullUrl(endpoint), params, {"token": token})
        printDBG("Noxx._passVerify -> %s" % (resp[:100] if sts else sts))
        return bool(sts and '"ok":true' in resp.replace(" ", ""))

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        sts, data = self.cm.getPage(baseUrl, addParams, post_data)
        if sts and self._isVerifyPage(data):
            if self._passVerify(data, self.cm.meta.get("url", "") or baseUrl):
                sts, data = self.cm.getPage(baseUrl, addParams, post_data)
                if sts and self._isVerifyPage(data):
                    sts, data = False, ""
            else:
                sts, data = False, ""
            if not sts:
                SetIPTVPlayerLastHostError(_("The site's browser check could not be passed."))
        return sts, data

    def _getJson(self, url):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Accept": "application/json, */*", "Referer": self.getFullUrl("/browse")})
        sts, data = self.getPage(url, params)
        if not sts:
            return {}
        try:
            data = json_loads(data)
            if isinstance(data, dict):
                return data
        except Exception:
            printDBG("Noxx._getJson: no JSON from %s" % url)
        return {}

    ###################################################
    # titles
    ###################################################
    def _episodeTitle(self, sTitle, season, episode, epTitle):
        if IsMediaNamingNormalized():
            return "%s - %s" % (sTitle, formatSxxExx(season, episode))
        title = "%s S%s E%s" % (sTitle, season, episode)
        return "%s - %s" % (title, epTitle) if epTitle else title

    def _seriesParams(self, cItem, url, title, icon, year="", desc=""):
        params = stripPagerKeys(dict(cItem), ("search_pattern", "filters"))
        slug = (SERIES_RE.search(url) or EPISODE_RE.search(url)).group(1)
        params.update({"good_for_fav": True, "category": "nx_series", "url": url, "title": title, "s_title": title,
                       "slug": slug, "icon": icon, "desc": desc,
                       "meta_type": "tv", "meta_title": title, "meta_year": year})
        return params

    ###################################################
    # lists
    ###################################################
    def listBrowse(self, cItem):
        filters = dict(cItem.get("filters", {}) or {})
        page = int(cItem.get("page", 1) or 1)
        # the page number drives the request, the template (the same endpoint) only gives Jump its target
        tpl = self.getFullUrl("/api/load-more-browse?" + (urllib_urlencode(filters) + "&" if filters else "") + "page={page}")
        printDBG("Noxx.listBrowse %s page %d" % (filters, page))
        data = self._getJson(tpl.format(page=page))
        cnt = 0
        for show in data.get("series", []) or []:
            try:
                slug = str(show.get("slug", "") or "")
                title = self.cleanHtmlStr(str(show.get("title", "") or ""))
                if not slug or not title:
                    continue
                year = str(show.get("first_air_date", "") or "")[:4]
                poster = str(show.get("poster_path", "") or "")
                icon = (TMDB_IMG + poster) if poster.startswith("/") else ""
                desc = []
                if year:
                    desc.append(year)
                rating = str(show.get("vote_average", "") or "")
                if rating and rating not in ("0", "0.0"):
                    desc.append("TMDb %s" % rating)
                self.addDir(self._seriesParams(cItem, self.getFullUrl("/tv/%s" % slug), title, icon, year, " | ".join(desc)))
                cnt += 1
            except Exception:
                printExc()
        addPagingItems(self, cItem, page, bool(cnt and data.get("hasMore")), 0, tpl)

    def listGenres(self, cItem):
        printDBG("Noxx.listGenres")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for genre in re.findall(r'data-genre="([^"]+)"', data):
            genre = self.cleanHtmlStr(genre)
            if not genre or genre in seen:
                continue
            seen.add(genre)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_browse", "title": genre, "filters": {"genres": genre}})
            self.addDir(params)

    def listYears(self, cItem):
        for years in YEAR_RANGES:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_browse", "title": years, "filters": {"year": years}})
            self.addDir(params)

    def listTimeline(self, cItem):
        printDBG("Noxx.listTimeline")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for section in data.split('<section class="timeline-item">')[1:]:
            day = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(section, '<span class="date-full">', '</span></span>', False)[1])
            for href, body in re.findall(r'<a href="(/tv/[^"]+)" class="poster-card">(.*?)</a>', section, re.DOTALL):
                url = self.getFullUrl(href)
                epMatch = EPISODE_RE.search(url)
                if not epMatch or url in seen:
                    continue
                seen.add(url)
                slug, season, episode = epMatch.groups()
                sTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="poster-card__title">(.*?)</span>')[0])
                icon = self.cm.ph.getSearchGroups(body, r'<img[^>]+src="([^"]+)"')[0]
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "nx_episode", "url": url, "icon": icon, "desc": day,
                               "title": self._episodeTitle(sTitle, season, episode, ""), "s_title": sTitle, "slug": slug,
                               "season": season, "episode": episode, "series_url": self.getFullUrl("/tv/%s" % slug),
                               "meta_type": "tv", "meta_title": sTitle, "meta_year": ""})
                self.addVideo(params)

    def _parseSeriesPage(self, data):
        info = {"title": "", "desc": "", "poster": "", "year": "", "facts": [], "genres": []}
        info["title"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<h1 class="watch-hero__title">(.*?)</h1>')[0])
        info["desc"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<p class="watch-hero__overview[^"]*">(.*?)</p>')[0])
        info["poster"] = self.cm.ph.getSearchGroups(data, r'<img class="watch-hero__poster" src="([^"]+)"')[0]
        facts = self.cm.ph.getDataBeetwenMarkers(data, '<div class="watch-hero__facts">', "</div>", False)[1]
        info["facts"] = [self.cleanHtmlStr(f) for f in re.findall(r'<span(?: class="status-badge[^"]*")?>(.*?)</span>', facts, re.DOTALL)]
        info["year"] = self.cm.ph.getSearchGroups(" ".join(info["facts"]), r'\b((?:19|20)\d\d)\b')[0]
        info["genres"] = [self.cleanHtmlStr(g) for g in re.findall(r'class="genre-tag">(.*?)</a>', data, re.DOTALL)]
        return info

    def listSeasons(self, cItem):
        printDBG("Noxx.listSeasons |%s|" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        info = self._parseSeriesPage(data)
        sTitle = cItem.get("s_title", "") or info["title"]
        tabs = re.findall(r'data-season="(\d+)" role="tab".*?<span class="season-tab__name">(.*?)</span>\s*<span class="season-tab__count">(.*?)</span>', data, re.DOTALL)
        for season, label, count in tabs:
            label = self.cleanHtmlStr(label) or "%s %s" % (_("Season"), season)
            count = self.cleanHtmlStr(count)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "nx_season", "title": "%s - %s" % (sTitle, label),
                           "s_title": sTitle, "season": season, "series_url": cItem["url"],
                           "desc": "[/br]".join([t for t in (count, info["desc"]) if t]) or cItem.get("desc", ""),
                           "icon": cItem.get("icon", "") or info["poster"]})
            if info["year"] and not params.get("meta_year"):
                params["meta_year"] = info["year"]
            self.addDir(params)
        if not self.currList and 'class="episode-card' in data:
            # a show without season tabs: the episodes straight away
            params = dict(cItem)
            params.update({"season": "", "series_url": cItem["url"]})
            self._addEpisodes(params, data)

    def _addEpisodes(self, cItem, data):
        sTitle = cItem.get("s_title", "")
        season = cItem.get("season", "")
        if season:
            data = self.cm.ph.getDataBeetwenMarkers(data, 'id="season-%s"' % season, '<div class="episode-grid', False)[1] or \
                self.cm.ph.getDataBeetwenMarkers(data, 'id="season-%s"' % season, '</section>', False)[1]
        seen = set()
        for href, body in re.findall(r'<a href="(/tv/[^"]+)"\s+class="episode-card[^"]*">(.*?)</a>', data, re.DOTALL):
            url = self.getFullUrl(href)
            epMatch = EPISODE_RE.search(url)
            if not epMatch or url in seen:
                continue
            seen.add(url)
            slug, sNum, eNum = epMatch.groups()
            epTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="episode-card__title">(.*?)</div>')[0])
            desc = []
            for cls in ("date", "overview"):
                txt = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="episode-card__%s">(.*?)</div>' % cls)[0])
                if txt:
                    desc.append(txt)
            runtime = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="episode-card__runtime">(.*?)</span>')[0])
            if runtime:
                desc.insert(0, runtime)
            icon = self.cm.ph.getSearchGroups(body, r'class="episode-card__thumb" src="([^"]+)"')[0] or cItem.get("icon", "")
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "nx_episode", "url": url, "icon": icon,
                           "title": self._episodeTitle(sTitle, sNum, eNum, epTitle), "ep_title": epTitle,
                           "slug": slug, "season": sNum, "episode": eNum, "desc": "[/br]".join(desc)})
            self.addVideo(params)

    def listEpisodes(self, cItem):
        printDBG("Noxx.listEpisodes |%s| season %s" % (cItem.get("series_url", ""), cItem.get("season", "")))
        sts, data = self.getPage(cItem.get("series_url") or cItem["url"])
        if not sts:
            return
        self._addEpisodes(cItem, data)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Noxx.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_browse", "filters": {"q": searchPattern}, "page": 1})
        self.listBrowse(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Noxx.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = cItem.get("url", "")
        if not self.cm.isValidUrl(pageUrl):
            return []
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        urltab = []
        skipped = []
        externalOk = IsExternalResolveAllowed()
        servers = self.cm.ph.getDataBeetwenMarkers(data, '<div class="server-buttons">', '<div class="server-backdrop"', False)[1] or data
        for value, server, label in re.findall(r'<button value="([^"]+)" data-server="([^"]*)" data-name="([^"]*)"', servers):
            url = value.replace("&amp;", "&")
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url):
                continue
            label = self.cleanHtmlStr(label) or server
            hostName = self.up.getHostName(url)
            # upd 091026: only the vidcore family still resolves through the opt-in enc-dec.app service
            # (videasy decrypts on the box)
            external = "vidcore" in hostName or "vidup" in hostName or "vidfast" in hostName
            if self.up.checkHostSupport(url) != 1 or (external and not externalOk):
                skipped.append(label)
                continue
            if "videasy" in hostName and "title=" not in url:
                # the videasy resolver needs the show title on the embed url
                url = "%s%stitle=%s&year=%s" % (url, "&" if "?" in url else "?", urllib_quote(cItem.get("s_title", "") or cItem.get("meta_title", ""), safe=""), cItem.get("meta_year", ""))
            urltab.append({"name": "%s (%s)" % (label, hostName), "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1,
                           "_prio": 1 if external or "videasy" in hostName else 0})
        urltab.sort(key=lambda item: item.pop("_prio"))
        if not urltab:
            if skipped:
                SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(skipped))
            else:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        sidecarTxt = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<p class="watch-hero__overview[^"]*">(.*?)</p>')[0])
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("Noxx.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Noxx.getArticleContent [%s]" % cItem.get("url", ""))
        seriesUrl = cItem.get("series_url") or cItem.get("url", "")
        epMatch = EPISODE_RE.search(seriesUrl)
        if epMatch:
            seriesUrl = self.getFullUrl("/tv/%s" % epMatch.group(1))
        info = {"title": "", "desc": "", "poster": "", "year": "", "facts": [], "genres": []}
        if self.cm.isValidUrl(seriesUrl):
            sts, data = self.getPage(seriesUrl)
            if sts:
                info = self._parseSeriesPage(data)
        meta = {}
        try:
            meta = getMeta("tv", cItem.get("meta_title", "") or info["title"], cItem.get("meta_year", "") or info["year"])
        except Exception:
            printExc()
            meta = {}
        otherInfo = dict(meta.get("info", {}) or {})
        if info["genres"]:
            otherInfo.setdefault("genres", ", ".join(info["genres"]))
        for fact in info["facts"]:
            if re.search(r'\d+\s+Seasons?$', fact):
                otherInfo.setdefault("seasons", fact.split()[0])
            elif re.search(r'\d+\s+Episodes?$', fact):
                otherInfo.setdefault("episodes", fact.split()[0])
            elif re.search(r'(?:19|20)\d\d', fact):
                otherInfo.setdefault("year", fact)
        text = meta.get("plot", "") or info["desc"] or cItem.get("desc", "").replace("[/br]", "\n")
        if cItem.get("type") == "video" and cItem.get("desc"):
            # the episode's own synopsis first, the show's story after it
            epText = cItem["desc"].replace("[/br]", "\n")
            text = epText + ("\n\n" + text if text and text != epText else "")
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
        printDBG("Noxx.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_browse":
            self.listBrowse(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_years":
            self.listYears(self.currItem)
        elif category == "list_timeline":
            self.listTimeline(self.currItem)
        elif category == "nx_series":
            self.listSeasons(self.currItem)
        elif category == "nx_season":
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
        CHostBase.__init__(self, Noxx(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("noxx")

    def withArticleContent(self, cItem):
        return bool(cItem.get("meta_type"))
