# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# Completely rewritten: 19.02.2026 - Mr.X
# Fixed Pagination for episodes: 02.05.2026 - SlyceMaster
# 10.10.2026 - host standard:
#   - the API answers 401 without a Referer of the site - every request sends it now
#   - search: the answer mixes people with titles (a person without poster crashed the list) - titles only
#   - links straight from the title / episode page (all mirrors, best quality first, version in the name:
#     dubbing / lektor / napisy), no extra watch request; episodes without a video are left out
#   - seasons: all of them (the title page sends 8 per page), a series with one season lists its episodes
#   - watched flag (series -> season -> episode), favourites reopen without state (old rows too),
#     downloaded marker on the film / episode url, "Title (Year)" / "Show - SxxExx" names, sidecar
#   - INFO via moviemeta (IMDb id of the title) merged with the site's fields (genres, rating, cast ...)
#   - First / Jump / Next page with the last page, TMDb posters w342 instead of the original
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://obejrzyj.to/"


def _toInt(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Obejrzyjto(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "title_id", "season", "episode", "ep_title", "s_title", "s_year", "meta_type")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Obejrzyjto", "cookie": "Obejrzyjto.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.MAIN_URL = gettytul()
        # without the Referer every api/v1 request answers 401
        self.HEADER.update({"Referer": self.MAIN_URL, "Accept": "application/json, text/plain, */*"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = self.getFullUrl("storage/branding_media/ead386d3-fca5-4082-8754-2a0992ae8c22.png")
        self.API_URL = self.getFullUrl("api/v1/channel/%s?restriction=&order=%s:desc&paginate=lengthAware&returnContentOnly=true&page=")
        self.MENU = [
            {"category": "submenu", "title": _("Movies"), "id": "78"},
            {"category": "list_items", "title": "Popularne polskie filmy", "url": self.API_URL % ("99", "popularity")},
            {"category": "submenu", "title": _("Series"), "id": "79"},
            {"category": "list_items", "title": "Polskie seriale", "url": self.API_URL % ("1994", "popularity")},
            {"category": "list_items", "title": "Polskie programy", "url": self.API_URL % ("396", "popularity")},
            {"category": "list_items", "title": "Seriale dokumentalne", "url": self.API_URL % ("9742", "popularity")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("obejrzyjto")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _getJson(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return {}
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return {}
        return data if isinstance(data, dict) else {}

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            if cItem.get("type", "") == "video":
                url = str(cItem.get("url", "") or "").strip()
                return "video:%s" % url if url else ""
            category = cItem.get("category", "")
            tid = self._titleId(cItem)
            if category == "list_seasons" and tid:
                return "series:%s" % tid
            season = self._season(cItem)
            if category == "list_episodes" and tid and season:
                return "season:%s|%s" % (tid, season)
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _titleId(cItem):
        # series rows saved before 10.10.2026 carry the bare title id as url
        tid = str(cItem.get("title_id", "") or "").strip()
        if not tid:
            url = str(cItem.get("url", "") or "").strip()
            tid = (re.findall(r"titles/(\d+)", url) or re.findall(r"^(\d+)$", url) or [""])[0]
        return tid

    @staticmethod
    def _season(cItem):
        season = str(cItem.get("season", "") or "").strip()
        if not season:
            season = (re.findall(r"/seasons/(\d+)", str(cItem.get("url", "") or "")) or [""])[0]
        return season

    @staticmethod
    def _poster(url):
        # the TMDb original is up to 2 MB a poster - w342 is plenty for the box
        return re.sub(r"(image\.tmdb\.org/t/p/)original/", r"\1w342/", url or "")

    @staticmethod
    def _versionLabel(languageType):
        # "lektor_pl_napisy_pl" -> "lektor PL / napisy PL"
        return (languageType or "").replace("_pl", " PL").replace("_en", " EN").replace("_", " / ")

    def _titleUrl(self, tid):
        return self.getFullUrl("api/v1/titles/%s?loader=titlePage" % tid)

    def _seasonUrl(self, tid, season):
        return self.getFullUrl("api/v1/titles/%s/seasons/%s?loader=seasonPage" % (tid, season))

    def _episodeUrl(self, tid, season, episode):
        return self.getFullUrl("api/v1/titles/%s/seasons/%s/episodes/%s?loader=episodePage" % (tid, season, episode))

    @staticmethod
    def _genres(js):
        return ", ".join(g.get("display_name", "") or g.get("name", "") for g in (js.get("genres") or []) if isinstance(g, dict))

    def _titleDesc(self, js):
        tab = []
        if js.get("year"):
            tab.append("%s: %s" % (_("Year"), js["year"]))
        if js.get("rating"):
            tab.append("%s: %s" % (_("Rating"), js["rating"]))
        genres = self._genres(js)
        if genres:
            tab.append(genres)
        primary = js.get("primary_video")
        if isinstance(primary, dict) and primary.get("language_type"):
            tab.append(self._versionLabel(primary["language_type"]))
        desc = self.cleanHtmlStr(js.get("description", "") or "")
        return " | ".join(tab) + ("[/br]" + desc if desc else "")

    ###################################################
    # lists
    ###################################################
    def listsubMenu(self, cItem):
        tab = [(_("Popular"), "popularity"), (_("Latest"), "created_at"), (_("Latest update"), "videos_updated_at"), (_("Rating"), "rating"),
               ("Biggest budget", "budget"), ("Highest revenue", "revenue")]
        for title, order in tab:
            params = dict(cItem)
            params.update({"category": "list_items", "title": title, "url": self.API_URL % (cItem["id"], order)})
            self.addDir(params)

    def _addTitles(self, cItem, titles):
        normalize = IsMediaNamingNormalized()
        for js in titles:
            if not isinstance(js, dict) or js.get("model_type", "title") != "title" or not js.get("id"):
                continue
            name = self.cleanHtmlStr(js.get("name", "") or "")
            if not name:
                continue
            year = str(js.get("year", "") or "")
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "icon": self._poster(js.get("poster")), "desc": self._titleDesc(js), "title_id": str(js["id"]),
                           "s_title": name, "s_year": year, "url": self._titleUrl(js["id"])})
            if js.get("is_series"):
                params.update({"category": "list_seasons", "title": name, "meta_type": "tv"})
                self.addDir(params)
            else:
                params.update({"category": "video", "title": "%s (%s)" % (name, year) if (normalize and year) else name, "meta_type": "movie"})
                self.addVideo(params)

    def listItems(self, cItem):
        printDBG("Obejrzyjto.listItems |%s|" % cItem)
        page = max(1, _toInt(cItem.get("page", 1), 1))
        # the channel url ends in "page=" (the pager rows carry the full url of their page)
        url = re.sub(r"page=\d*$", "page=", cItem["url"])
        js = self._getJson(url + str(page))
        pagination = js.get("pagination") or {}
        self._addTitles(cItem, pagination.get("data") or [])
        perPage = _toInt(pagination.get("per_page"), 0)
        total = _toInt(pagination.get("total"), 0)
        lastPage = (total + perPage - 1) // perPage if (perPage and total) else 0
        addPagingItems(self, cItem, page, bool(pagination.get("next_page")), lastPage, url.replace("{", "{{").replace("}", "}}") + "{page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Obejrzyjto.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        # one page of up to 20 results, people included - no paging
        js = self._getJson(self.getFullUrl("api/v1/search/%s?loader=searchPage" % urllib_quote(searchPattern)))
        self._addTitles(cItem, js.get("results") or [])
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No matching entries found."))

    def listSeasons(self, cItem):
        printDBG("Obejrzyjto.listSeasons |%s|" % cItem)
        tid = self._titleId(cItem)
        if not tid:
            return
        js = self._getJson(self._titleUrl(tid))
        title = js.get("title") or {}
        seasons = js.get("seasons") or {}
        rows = seasons.get("data") or []
        if _toInt(seasons.get("last_page"), 1) > 1:
            # the title page sends 8 seasons per page
            more = self._getJson(self.getFullUrl("api/v1/titles/%s/seasons?perPage=100&page=1" % tid))
            rows = (more.get("pagination") or {}).get("data") or rows
        rows = sorted([r for r in rows if isinstance(r, dict) and r.get("number") is not None], key=lambda r: _toInt(r.get("number")))
        if not rows:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = self.cleanHtmlStr(title.get("name", "") or "") or cItem.get("s_title", "") or cItem.get("title", "")
        plot = self.cleanHtmlStr(title.get("description", "") or "") or cItem.get("desc", "")
        fields = {"title_id": tid, "s_title": sTitle, "s_year": str(title.get("year", "") or cItem.get("s_year", "")), "meta_type": "tv"}
        if len(rows) == 1:
            season = str(rows[0]["number"])
            self.listEpisodes(dict(cItem, category="list_episodes", season=season, url=self._seasonUrl(tid, season), desc=plot,
                                   episodes_count=rows[0].get("episodes_count", 0), **fields))
            return
        normalize = IsMediaNamingNormalized()
        for row in rows:
            season = str(row["number"])
            seasonTag = formatSxxExx(season) if normalize else "%s %s" % (_("Season"), season)
            params = stripPagerKeys(dict(cItem))
            params.update(fields)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (sTitle, seasonTag), "season": season,
                           "url": self._seasonUrl(tid, season), "icon": self._poster(row.get("poster")) or cItem.get("icon", ""),
                           "episodes_count": row.get("episodes_count", 0), "desc": "%s: %s\n%s" % (_("Episodes"), row.get("episodes_count", ""), plot)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Obejrzyjto.listEpisodes |%s|" % cItem)
        tid, season = self._titleId(cItem), self._season(cItem)
        if not (tid and season):
            return
        page = max(1, _toInt(cItem.get("page", 1), 1))
        url = self._seasonUrl(tid, season)
        js = self._getJson(url + ("&page=%d" % page if page > 1 else ""))
        episodes = js.get("episodes") or {}
        title = js.get("title") or {}
        sTitle = cItem.get("s_title", "") or self.cleanHtmlStr(title.get("name", "") or "") or cItem.get("title", "")
        normalize = IsMediaNamingNormalized()
        for ep in episodes.get("data") or []:
            if not isinstance(ep, dict) or not ep.get("primary_video"):
                # announced by TMDb, no video on the site yet
                continue
            epNum = str(ep.get("episode_number", "") or "")
            epName = self.cleanHtmlStr(ep.get("name", "") or "")
            if normalize:
                label = "%s - %s" % (sTitle, formatSxxExx(season, epNum))
            else:
                label = " - ".join(x for x in (sTitle, "%s %s, %s %s" % (_("Season"), season, _("Episode"), epNum), epName) if x)
            descTab = [x for x in (str(ep.get("release_date", "") or "")[:10], self._versionLabel((ep.get("primary_video") or {}).get("language_type", ""))) if x]
            plot = self.cleanHtmlStr(ep.get("description", "") or "")
            text = "%s: %s" % (epName, plot) if (epName and plot) else (plot or epName)
            params = stripPagerKeys(dict(cItem), ("episodes_count",))
            params.update({"good_for_fav": True, "category": "video", "title": label, "url": self._episodeUrl(tid, season, epNum), "title_id": tid,
                           "season": season, "episode": epNum, "ep_title": epName, "s_title": sTitle, "meta_type": "tv",
                           "icon": self._poster(ep.get("poster")) or cItem.get("icon", ""),
                           "desc": " | ".join(descTab) + ("[/br]" + text if text else "")})
            self.addVideo(params)
        perPage = _toInt(episodes.get("per_page"), 0)
        count = _toInt(cItem.get("episodes_count") or (js.get("season") or {}).get("episodes_count"), 0)
        lastPage = (count + perPage - 1) // perPage if (perPage and count) else 0
        # the page lives in cItem["page"] - the template keeps the season url
        addPagingItems(self, dict(cItem, category="list_episodes"), page, bool(episodes.get("next_page")), lastPage, url.replace("{", "{{").replace("}", "}}"))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Obejrzyjto.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        js = self._getJson(url)
        if "=episodePage" in url:
            videos = (js.get("episode") or {}).get("videos") or []
        else:
            title = js.get("title") or {}
            videos = title.get("videos") or []
            primary = title.get("primary_video")
            if not videos and isinstance(primary, dict) and primary.get("id"):
                watch = self._getJson(self.getFullUrl("api/v1/watch/%s" % primary["id"]))
                videos = watch.get("alternative_videos") or ([watch["video"]] if isinstance(watch.get("video"), dict) else [])
        rows = []
        for video in videos:
            if not isinstance(video, dict):
                continue
            src = video.get("src", "") or ""
            if src.startswith("//"):
                src = "https:" + src
            if not self.cm.isValidUrl(src) or src in [r[1] for r in rows]:
                continue
            quality = str(video.get("quality", "") or "")
            hoster = video.get("name", "") or self.up.getHostName(src).capitalize()
            name = " - ".join(x for x in (hoster, quality, self._versionLabel(video.get("language_type", ""))) if x)
            rows.append((_toInt(re.sub(r"\D", "", quality), 0), src, name))
        rows.sort(key=lambda r: -r[0])
        urltab = [{"name": name, "url": strwithmeta(src, {"Referer": self.MAIN_URL}), "need_resolve": 1} for _q, src, name in rows]
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    def getVideoLinks(self, videoUrl):
        printDBG("Obejrzyjto.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Obejrzyjto.getArticleContent [%s]" % cItem)
        tid = self._titleId(cItem)
        js = self._getJson(self._titleUrl(tid)) if tid else {}
        title = js.get("title") or {}
        mediaType = "tv" if (title.get("is_series") or cItem.get("meta_type") == "tv") else "movie"
        info = {}
        for key, field in (("year", "year"), ("rating", "rating"), ("seasons_count", "seasons")):
            if title.get(key) and (key != "seasons_count" or mediaType == "tv"):
                info[field] = str(title[key])
        if title.get("runtime"):
            info["duration"] = "%s min" % title["runtime"]
        if title.get("original_title") and title.get("original_title") != title.get("name"):
            info["original_title"] = self.cleanHtmlStr(title["original_title"])
        if title.get("certification"):
            info["age_limit"] = str(title["certification"]).upper()
        genres = self._genres(title)
        if genres:
            info["genres"] = genres
        credits = js.get("credits") or {}
        for field, dept in (("directors", "directing"), ("actors", "actors")):
            names = [self.cleanHtmlStr(p.get("name", "")) for p in (credits.get(dept) or []) if isinstance(p, dict)][:5]
            if names:
                info[field] = ", ".join(names)
        sTitle = self.cleanHtmlStr(title.get("name", "") or "") or cItem.get("s_title", "") or cItem.get("title", "")
        year = str(title.get("year", "") or cItem.get("s_year", ""))
        meta = {}
        try:
            if title.get("imdb_id"):
                meta = getMetaByImdbId(mediaType, title["imdb_id"])
            if not meta and sTitle:
                meta = getMeta(mediaType, title.get("original_title", "") or sTitle, year)
        except Exception:
            printExc()
        metaInfo = dict(meta.get("info", {}))
        metaInfo.update(info)
        text = self.cleanHtmlStr(title.get("description", "") or "") or cItem.get("desc", "")
        if cItem.get("type") == "video" and cItem.get("episode"):
            # an episode: its own text first
            epText = cItem.get("desc", "")
            text = "%s[/br][/br]%s" % (epText, text) if (epText and text and epText != text) else (epText or text)
        metaPlot = meta.get("plot", "")
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or self._poster(title.get("poster")) or meta.get("poster", "") or self.DEFAULT_ICON_URL
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
        elif category == "submenu":
            self.listsubMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
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
        CHostBase.__init__(self, Obejrzyjto(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("obejrzyjto")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
