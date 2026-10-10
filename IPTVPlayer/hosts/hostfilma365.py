# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# 15.03.2026 - Mr.X
# 09.10.2026 - host standard (filma365.me, Livewire site):
#   - cards parsed from the "group" grid (title, year, rating, quality, type) - the old marker also caught the
#     page chrome; First / Jump / Next page ("Next" button of the Livewire pager), animes, genres, search
#     (browse?search=)
#   - series / animes: seasons from the season switch, episodes of a season from the tv page (its first season)
#     or from an episode page of that season (the other seasons are only loaded by Livewire); every
#     episode keeps its own page url (watched key + downloaded marker), seasons the series url + "#s<season>"
#   - watched flag (series -> season -> episode), favourites reopen without state (also the old series rows),
#     "Title (Year)" / "Show - SxxExx" names, sidecar on the links, INFO via moviemeta merged with the site's
#     fields (overview, genres, country, release date, duration, rating, quality)
#   - links: label + embed url from the Livewire player state (byse / voe / strp2p), default user agent
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
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://filma365.me/"


# href="https://filma365.me/episode/<slug>/<season>-<episode>"
EPISODE_RE = re.compile(r'href="(https?://[^"]+/episode/[^"/]+/(\d+)-(\d+))"')
QUALITY_RE = r"(FHD|HD|SD|CAM|4K|HDTV|TS)"


class Filma365(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Filma365", "cookie": "Filma365.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("upload/static/favicon-1770548570.png")
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("tv-shows")},
                     {"category": "list_items", "title": _("Anime"), "url": self.getFullUrl("animes")},
                     {"category": "list_items", "title": _("Top IMDb"), "url": self.getFullUrl("top-imdb")},
                     {"category": "list_genres", "title": _("Genres")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("filma365")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl.split("#", 1)[0], addParams, post_data)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            if cItem.get("type", "") == "video":
                prefix = "video"
            else:
                prefix = {"list_seasons": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
                if prefix == "season" and "#s" not in url:
                    # "list_episodes" rows of the old version were whole series (tv page url)
                    prefix = "series"
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _pageUrlTpl(url):
        url = re.sub(r"([?&])page=\d+&?", r"\1", url).rstrip("?&").replace("{", "{{").replace("}", "}}")
        return url + ("&" if "?" in url else "?") + "page={page}"

    def _title(self, data):
        return self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<h1[^>]*>(.*?)</h1>")[0])

    def _siteInfo(self, data):
        # the fields of a movie / tv / episode page: (info dict, overview, year)
        info = {}
        head = self.cm.ph.getDataBeetwenMarkers(data, "<h1", "wire:snapshot", False)[1]
        year = self.cm.ph.getSearchGroups(head, r"<span>\s*((?:19|20)\d\d)\s*</span>")[0]
        if year:
            info["year"] = year
        duration = self.cm.ph.getSearchGroups(head, r"<span>\s*(\d+\s*min)\s*</span>")[0]
        if duration:
            info["duration"] = duration
        quality = self.cm.ph.getSearchGroups(head, r">\s*%s\s*</div>" % QUALITY_RE)[0]
        if quality:
            info["quality"] = quality
        rating = self.cm.ph.getSearchGroups(head, r"<span[^>]*>\s*(\d{1,2}\.\d)\s*</span>")[0]
        if rating:
            info["rating"] = rating
        for key, label in (("genres", "Genre"), ("country", "Country"), ("released", "Release date")):
            block = self.cm.ph.getSearchGroups(data, r"(?s)>\s*%s\s*</div>\s*<div[^>]*>(.*?)</div>" % label)[0]
            value = ", ".join(x for x in (self.cleanHtmlStr(v) for v in re.findall(r">([^<]+)</a>", block)) if x) or self.cleanHtmlStr(block)
            if value:
                info[key] = value
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<p class="text-muted-foreground text-sm mt-4">(.*?)</p>')[0])
        return info, plot, year

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("Filma365.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        pageUrlTpl = self._pageUrlTpl(cItem["url"])
        sts, data = self.getPage(pageUrlTpl.format(page=page) if page > 1 else cItem["url"])
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for block in data.split('<div class="group">')[1:]:
            url = self.cm.ph.getSearchGroups(block, r'href="(https?://[^"]+/(?:movie|tv|anime)/[^"]+)"')[0]
            if not url or url in seen:
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r"(?s)<h3[^>]*>(.*?)</h3>")[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'alt="([^"]+)"')[0])
            icon = self.cm.ph.getSearchGroups(block, r'data-src="([^"]+)"')[0]
            year = self.cm.ph.getSearchGroups(block, r"<span>\s*((?:19|20)\d\d)\s*</span>")[0]
            rating = self.cm.ph.getSearchGroups(block, r">\s*(\d{1,2}\.\d)\s*</div>")[0]
            quality = self.cm.ph.getSearchGroups(block, r">\s*%s\s*</div>" % QUALITY_RE)[0]
            desc = " | ".join("%s: %s" % (label, value) for label, value in ((_("Year"), year), (_("Rating"), rating), (_("Quality"), quality)) if value)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon), "desc": desc, "s_title": title, "s_year": year})
            if "/movie/" in url:
                params.update({"category": "video", "meta_type": "movie", "title": "%s (%s)" % (title, year) if (normalize and year) else title})
                self.addVideo(params)
            else:
                params.update({"category": "list_seasons", "meta_type": "tv", "title": title})
                self.addDir(params)
        addPagingItems(self, cItem, page, "nextPage('page')" in data, 0, pageUrlTpl)

    def listGenres(self, cItem):
        printDBG("Filma365.listGenres")
        sts, data = self.getPage(self.getFullUrl("browse"))
        if not sts:
            return
        for slug, title in re.findall(r'name="genre"\s+wire:model\.live="genre"\s+value="([^"]+)"[^>]*>\s*<label[^>]*>\s*([^<]+?)\s*</label>', data):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl("genre/" + slug)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("Filma365.listSeasons |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        _info, plot, year = self._siteInfo(data)
        sTitle = cItem.get("s_title", "") or self._title(data) or cItem["title"]
        seasons = []
        for season in re.findall(r'id="season(\d+)"\s+name="selectedSeason"', data) + [e[1] for e in EPISODE_RE.findall(data)]:
            if season not in seasons:
                seasons.append(season)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        fields = {"s_title": sTitle, "s_year": year or cItem.get("s_year", ""), "meta_type": "tv", "desc": plot}
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, category="list_episodes", season=seasons[0], url="%s#s%s" % (url, seasons[0]), **fields), data)
            return
        normalize = IsMediaNamingNormalized()
        for season in sorted(seasons, key=int):
            params = stripPagerKeys(dict(cItem))
            params.update(fields)
            params.update({"good_for_fav": True, "category": "list_episodes", "season": season, "url": "%s#s%s" % (url, season),
                           "title": "%s - %s" % (sTitle, formatSxxExx(season) if normalize else "%s %s" % (_("Season"), season))})
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("Filma365.listEpisodes |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        season = str(cItem.get("season", "") or "")
        if not season:
            # a "list_episodes" row of the old version (favourite) is the whole series
            self.listSeasons(dict(cItem, category="list_seasons", url=url))
            return
        if data is None:
            sts, data = self.getPage(url)
            if not sts:
                return
            cItem = dict(cItem, s_title=cItem.get("s_title", "") or self._title(data))
        # the tv page lists its first season in the "grid-episode" block; above it a "latest episode" link that can
        # belong to another season (dark-winds: grid 2-1..2-6, link 4-1) - an episode page has no such block
        episodes = [e for e in EPISODE_RE.findall(data.split('class="grid-episode"', 1)[-1]) if e[1] == season]
        if not episodes:
            # the other seasons are only loaded by Livewire - an episode page lists its whole season: the one the
            # tv page links for that season, else the season's first episode
            epUrl = ([e[0] for e in EPISODE_RE.findall(data) if e[1] == season] or [""])[0]
            if not epUrl:
                slug = self.cm.ph.getSearchGroups(data, r'/episode/([^"/]+)/\d+-\d+"')[0] or url.rstrip("/").rsplit("/", 1)[-1]
                epUrl = self.getFullUrl("episode/%s/%s-1" % (slug, season))
            sts, epData = self.getPage(epUrl)
            if sts:
                episodes = [e for e in EPISODE_RE.findall(epData) if e[1] == season]
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", "") or cItem["title"]
        normalize = IsMediaNamingNormalized()
        seen = set()
        for epUrl, _season, episode in sorted(episodes, key=lambda e: int(e[2])):
            if epUrl in seen:
                continue
            seen.add(epUrl)
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            else:
                title = "%s - %s %s - %s %s" % (sTitle, _("Season"), season, _("Episode"), episode)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "url": epUrl, "season": season, "episode": episode, "meta_type": "tv"})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Filma365.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("browse?search=%s" % urllib_quote_plus(searchPattern))})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Filma365.getLinksForVideo [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        # Livewire player state: "videos":[[[{"label":"VOE","type":"embed","source":"https:\/\/voe.sx\/e\/.."}, ...
        state = data.replace("&quot;", '"').replace("&amp;", "&").replace("\\/", "/")
        urltab = []
        for label, url in re.findall(r'\{"label":"([^"]*)","type":"embed","source":"([^"]+)"', state):
            url = url.strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in [str(x["url"]) for x in urltab]:
                continue
            name = self.up.getHostName(url).capitalize()
            if label and label.lower() not in name.lower():
                name = "%s [%s]" % (name, label)
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self._siteInfo(data)[1]))

    def getVideoLinks(self, videoUrl):
        printDBG("Filma365.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Filma365.getArticleContent [%s]" % cItem)
        info, plot, year = {}, "", cItem.get("s_year", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot, siteYear = self._siteInfo(data)
            year = year or siteYear
        mediaType = cItem.get("meta_type", "") or ("movie" if "/movie/" in cItem.get("url", "") else "tv")
        title = cItem.get("s_title", "") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(mediaType, title, year, maxYearDiff=1)
        except Exception:
            printExc()
        for key, value in meta.get("info", {}).items():
            info.setdefault(key, value)
        metaPlot = meta.get("plot", "")
        text = plot or cItem.get("desc", "")
        if metaPlot and text and metaPlot != text:
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
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
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
        CHostBase.__init__(self, Filma365(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("filma365")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
