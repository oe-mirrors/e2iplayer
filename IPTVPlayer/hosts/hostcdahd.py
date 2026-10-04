# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026 - new host for cda-hd.cc (Polish movies and series, WordPress "Grifus" theme)
#   - Cloudflare: every request goes through getPageCFProtection (MyE2i solves the browser check, the
#     solving User-Agent is remembered next to the cookie jar)
#   - latest, movies, series, new episodes, movie / series genres, years and search (?s=), with
#     First page / Jump / Next page (/page/N/)
#   - movies and episodes are VIDEO rows keyed on their page url; series -> seasons (when more than
#     one) -> episodes (ascending)
#   - links: the player iframes of the page (one per tab, label = "Lektor PL", "Napisy PL" ...) go to
#     urlparser (voe mirrors, dood mirrors ...)
#   - watched flag, downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx"), sidecar, INFO via moviemeta (IMDb id of the movie page) + the site's fields
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://cda-hd.cc/"


COLOR_CODE_RE = re.compile(r"\\c[0-9A-Fa-f]{8}")
NUMBERS_RE = re.compile(r"(\d+)\s*x\s*(\d+)")
PAGING_KEYS = ("base_url", "page_tpl")
# "<b>Label</b><span>value</span>" rows of the series / episode pages -> INFO keys
META_ROWS = (("released", "Data emisji"), ("first_air_date", "Data pierwszej odsłony"), ("director", "Reżyser"),
             ("production", "Produkcja"), ("station", "Serial"), ("status", "Status TV"))


def _stripColors(text):
    return COLOR_CODE_RE.sub("", text or "")


def _splitTitle(title):
    # "Anatomia grzechu / La Confesión (2025)" -> ("Anatomia grzechu / La Confesión", "2025")
    m = re.match(r"^(.*?)\s*\(((?:19|20)\d{2})\)\s*$", (title or "").strip())
    return (m.group(1), m.group(2)) if m else ((title or "").strip(), "")


def _metaTitle(title):
    # the original title (after " / ") finds more on TMDb / IMDb than the Polish one
    parts = [p.strip() for p in (title or "").split(" / ") if p.strip()]
    return parts[-1] if parts else ""


class CdaHD(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cdahd", "cookie": "cdahd.cookie"})
        self.MAIN_URL = gettytul()
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "list_items", "title": _("Latest"), "url": self.MAIN_URL},
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/filmy-online/")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/seriale-online/")},
            {"category": "list_new_episodes", "title": _("New episodes"), "url": self.getFullUrl("/episode/")},
            {"category": "cda_filter", "title": "%s - %s" % (_("Movies"), _("Genres")), "url": self.MAIN_URL, "filter": "gatunki/"},
            {"category": "cda_filter", "title": "%s - %s" % (_("Series"), _("Genres")), "url": self.getFullUrl("/seriale-online/"), "filter": "tvshows-genre/"},
            {"category": "cda_filter", "title": _("Year"), "url": self.MAIN_URL, "filter": "release-year/"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("cdahd")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", url or "").rstrip("/").lower()

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("cda_video", "cda_series", "cda_season"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            prefix = {"cda_video": "video", "cda_series": "series", "cda_season": "season"}.get(category, "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            if path and category == "cda_season":
                path = "%s#s%s" % (path, cItem.get("s_season", ""))
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listFilter(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        prefix = cItem.get("filter", "")
        seen = set()
        for href, label in re.findall(r'<a[^>]+href="(https?://[^/"]+/%s[^"]+)"[^>]*>([^<]+)</a>' % re.escape(prefix), data):
            label = self.cleanHtmlStr(label)
            if not label or href in seen:
                continue
            seen.add(href)
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"category": "list_items", "title": label, "url": href, "good_for_fav": True})
            params.pop("filter", None)
            self.addDir(params)

    def _paging(self, data, page):
        # (url template with "{page}", last page, has a next page)
        pager = self.cm.ph.getDataBeetwenMarkers(data, "class='paginado'", "</div>", False)[1]
        tpl, lastPage = "", 0
        for href, label in re.findall(r"<a[^>]+href='([^']+)'[^>]*>([^<]+)</a>", pager):
            num = self.cm.ph.getSearchGroups(href, r"/page/(\d+)")[0]
            if not num:
                continue
            tpl = tpl or re.sub(r"/page/\d+", "/page/{page}", href.replace("{", "{{").replace("}", "}}"), 1)
            lastPage = max(lastPage, int(num))
        nextUrl = self.cm.ph.getSearchGroups(data, r'href="([^"]+/page/\d+/?[^"]*)"[^>]*>\s*Następna')[0]
        if nextUrl and not tpl:
            tpl = re.sub(r"/page/\d+", "/page/{page}", nextUrl.replace("{", "{{").replace("}", "}}"), 1)
        hasNext = lastPage > page or bool(nextUrl)
        return tpl, lastPage, hasNext

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        tpl = cItem.get("page_tpl", "")
        url = baseUrl if page <= 1 or not tpl else tpl.format(page=page)
        printDBG("CdaHD.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        content = self.cm.ph.getDataBeetwenMarkers(data, '<div class="item_1 items">', 'id="paginador"', False)[1] or data
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in content.split('<div id="mt-')[1:]:
            url = self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0]
            if not url or url in seen:
                continue
            seen.add(url)
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<span class="tt">(.*?)</span>')[0])
            title, year = _splitTitle(rawTitle)
            year = year or self.cm.ph.getSearchGroups(item, r'<span class="year">\s*(\d{4})')[0]
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<span class="ttx">(.*?)<div')[0])
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<span class="calidad2">([^<]+)<')[0])
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<span class="imdbs">([^<]+)<')[0])
            fields = ((_("Quality"), quality, "yellow"), (_("Year"), year, "cyan"), (_("Rating"), rating, "green"))
            desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
            if plot:
                desc = "%s[/br]%s" % (desc, plot) if desc else plot
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon.strip()), "desc": desc,
                      "meta_title": _metaTitle(title), "meta_year": year}
            if "/tvshows/" in url:
                params.update({"category": "cda_series", "title": rawTitle, "s_title": title, "meta_type": "tv"})
                self.addDir(params)
            else:
                dispTitle = rawTitle
                if normalize:
                    dispTitle = "%s (%s)" % (title, year) if year else title
                params.update({"category": "cda_video", "title": dispTitle, "meta_type": "movie"})
                self.addVideo(params)

        pageTpl, lastPage, hasNext = self._paging(data, page)
        pageTpl = pageTpl or tpl
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl, "page_tpl": pageTpl})
        addPagingItems(self, listItem, page, hasNext and bool(seen) and bool(pageTpl), lastPage, pageTpl)

    def listNewEpisodes(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        tpl = cItem.get("page_tpl", "")
        url = baseUrl if page <= 1 or not tpl else tpl.format(page=page)
        printDBG("CdaHD.listNewEpisodes [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        tbody = self.cm.ph.getDataBeetwenMarkers(data, "<tbody>", "</tbody>", False)[1]
        seen = set()
        for row in self.cm.ph.getAllItemsBeetwenMarkers(tbody, "<tr>", "</tr>"):
            url = self.cm.ph.getSearchGroups(row, r'<a href="([^"]+/episode/[^"]+)"')[0]
            if not url or url in seen:
                continue
            seen.add(url)
            numbers = NUMBERS_RE.search(self.cm.ph.getSearchGroups(row, r"<span>([^<]+)</span>")[0])
            show = self.cleanHtmlStr(self.cm.ph.getSearchGroups(row, r'(?s)<td class="cc">(.*?)</td>')[0])
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(row, r"(?s)<h2>(.*?)</h2>")[0])
            if not show or not numbers:
                continue
            season, episode = int(numbers.group(1)), int(numbers.group(2))
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = " - ".join(x for x in (show, "%d x %d" % (season, episode), name) if x)
            icon = self.cm.ph.getSearchGroups(row, r'data-src="\s*([^"]+)"')[0]
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(row, r"(?s)<p>(.*?)</p>")[0])
            aired = self.cleanHtmlStr(self.cm.ph.getSearchGroups(row, r'<td class="dd">([^<]*)<')[0])
            desc = "%s%s:%s %s" % (E2ColoR("cyan"), _("Aired"), E2ColoR("white"), aired) if aired else ""
            if name or plot:
                desc = "[/br]".join(x for x in (desc, name, plot) if x)
            self.addVideo({"name": "category", "good_for_fav": True, "category": "cda_video", "title": title, "url": url,
                           "icon": self.getFullIconUrl(icon.strip()), "desc": desc, "s_title": show, "s_season": season, "s_episode": episode,
                           "meta_type": "tv", "meta_title": _metaTitle(show), "meta_year": ""})
        pageTpl, lastPage, hasNext = self._paging(data, page)
        pageTpl = pageTpl or tpl
        listItem = dict(cItem)
        listItem.update({"base_url": baseUrl, "url": baseUrl, "page_tpl": pageTpl})
        addPagingItems(self, listItem, page, hasNext and bool(seen) and bool(pageTpl), lastPage, pageTpl)

    def _seasons(self, data):
        # {season: [(episode, url, name)]} from the "Sezony i odcinki" block
        seasons = {}
        for block in data.split('<div class="se-c">')[1:]:
            for li in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>"):
                numbers = NUMBERS_RE.search(self.cm.ph.getSearchGroups(li, r'<div class="numerando">([^<]+)<')[0])
                url = self.cm.ph.getSearchGroups(li, r'<a href="([^"]+)"')[0]
                if not numbers or not url:
                    continue
                name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(li, r'(?s)<a href="[^"]+">(.*?)</a>')[0])
                season = int(numbers.group(1))
                if url not in [e[1] for e in seasons.get(season, [])]:
                    seasons.setdefault(season, []).append((int(numbers.group(2)), url, name))
        return seasons

    def listSeries(self, cItem):
        printDBG("CdaHD.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seasons = self._seasons(data)
        if len(seasons) == 1:
            season = list(seasons)[0]
            self.listEpisodes(dict(cItem, s_season=season), seasons[season])
            return
        for season in sorted(seasons):
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "category": "cda_season", "title": "%s %d" % (_("Season"), season), "s_season": season})
            self.addDir(params)

    def listEpisodes(self, cItem, episodes=None):
        printDBG("CdaHD.listEpisodes [%s]" % cItem.get("url", ""))
        season = cItem.get("s_season", 1)
        if episodes is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
            episodes = self._seasons(data).get(season, [])
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        for episode, url, name in sorted(episodes):
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = " - ".join(x for x in (show, "%d x %d" % (season, episode), name) if x)
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "category": "cda_video", "title": title, "url": url,
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv"})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CdaHD.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        base = self.getFullUrl("/?s=%s" % urllib_quote_plus(searchPattern.strip()))
        cItem.update({"category": "list_items", "url": base, "base_url": base, "page": 1, "page_tpl": ""})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'itemprop="description" content="([^"]*)"')[0])
        poster = self.cm.ph.getSearchGroups(data, r'itemprop="image" content="([^"]+)"')[0]
        imdbId = self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
        info = {}
        meta = self.cm.ph.getDataBeetwenMarkers(data, '<p class="meta">', "</p>", False)[1]
        if meta:
            info["year"] = self.cm.ph.getSearchGroups(meta, r"release-year/(\d{4})")[0]
            info["duration"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(meta, r'icon-time"></b>\s*([^<]+)<')[0])
            info["genres"] = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r'rel="category tag">([^<]+)<', meta))
        for key, icon in (("director", "icon-megaphone"), ("actors", "icon-star"), ("country", "icon-network")):
            val = self.cm.ph.getSearchGroups(data, r'(?s)<p class="meta_dd[^"]*">\s*<b class="%s"></b>(.*?)(?:</p>|<div)' % icon)[0]
            val = self.cleanHtmlStr(val).strip(" ,")
            if val:
                info[key] = val
        for key, label in META_ROWS:
            val = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="metadatac"><b>%s</b><span>(.*?)</span></div>' % re.escape(label))[0])
            if val:
                info[key] = val
        return story, poster, imdbId, dict((k, v) for k, v in info.items() if v)

    def getLinksForVideo(self, cItem):
        printDBG("CdaHD.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        labels = dict((tab, self.cleanHtmlStr(label)) for tab, label in re.findall(r'(?s)<a href="#((?:div|player)\d+)"[^>]*>(.*?)</a>', data))
        urltab, seen = [], set()
        for m in re.finditer(r'<iframe[^>]+src="([^"]+)"', data):
            src = m.group(1).strip()
            if src.startswith("//"):
                src = "https:" + src
            divStart = data.rfind('<div id="', 0, m.start())
            tab = self.cm.ph.getSearchGroups(data[divStart:m.start()], r'<div id="([^"]+)"')[0] if divStart >= 0 else ""
            if not re.match(r"^(?:div|player)\d+$", tab) or not self.cm.isValidUrl(src) or src in seen:
                continue
            seen.add(src)
            label = labels.get(tab) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(data[m.end():m.end() + 300], r'<span class="tit">([^<]+)<')[0])
            host = self.up.getHostName(src)
            urltab.append({"name": "%s (%s)" % (host, label) if label else host, "url": strwithmeta(src, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=_stripColors(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("CdaHD.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("CdaHD.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, imdbId, info = "", "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, imdbId, info = self._siteInfo(data)
        meta = {}
        mediaType = cItem.get("meta_type", "")
        try:
            if imdbId and mediaType == "movie":
                meta = getMetaByImdbId(mediaType, imdbId)
            if not meta and mediaType and cItem.get("meta_title"):
                meta = getMeta(mediaType, cItem["meta_title"], cItem.get("meta_year", "") or info.get("year", ""))
        except Exception:
            printExc()
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or _stripColors(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("CdaHD.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "cda_filter":
            self.listFilter(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_new_episodes":
            self.listNewEpisodes(self.currItem)
        elif category == "cda_series":
            self.listSeries(self.currItem)
        elif category == "cda_season":
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
        CHostBase.__init__(self, CdaHD(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cdahd")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("cda_video", "cda_series", "cda_season")
