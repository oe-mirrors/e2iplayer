# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# Based on the preparatory work of odem2014
# 03.10.2026 - new domain shaahiied4u.net (shahid4uu.day is dead, shed4u1.com is
#   parked; shaiid4u.co / shhaiid4u.net redirect here): "show-card" grids, ?page=N with rel="next" (First page /
#   Jump / Next page, also for the episodes of a season - no blocking loop over all pages),
#   /series/ -> /season/ -> /episode/ pages, the /watch/ page (needs the title page as Referer)
#   carries "let servers = [...]" whose /m/<hash> urls redirect to the hosters
#   + watched flag / downloaded flag / name normalisation / sidecar / moviemeta INFO / favourites.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://shaahiied4u.net/"


# Arabic ordinals used in "الموسم الثاني"
ORDINALS = [(u"الحادي عشر", 11), (u"الثاني عشر", 12), (u"الثالث عشر", 13), (u"الرابع عشر", 14), (u"الخامس عشر", 15),
            (u"الاول", 1), (u"الأول", 1), (u"الثاني", 2), (u"الثالث", 3), (u"الرابع", 4), (u"الخامس", 5),
            (u"السادس", 6), (u"السابع", 7), (u"الثامن", 8), (u"التاسع", 9), (u"العاشر", 10)]
TITLE_PREFIX_RE = re.compile(u"^\\s*(?:مسلسل|مسلسلات|انمي|أنمي|برنامج|عرض|فيلم|فلم)\\s+")
TITLE_SUFFIX_RE = re.compile(u"\\s+(?:مترجمة|مترجم|مدبلجة|مدبلج|اون لاين|أون لاين|كامل|كاملة|والاخيرة|والأخيرة|الاخيرة|الأخيرة)\\s*$")
# paging / search state of a list that must not reach the rows listed in it
LIST_STATE_KEYS = ("base_url", "search_pattern")


def _toUnicode(text):
    try:
        if not isinstance(text, type(u"")):
            return text.decode("utf-8", "ignore")
    except Exception:
        pass
    return text


def _toNative(text):
    if isinstance(text, str):
        return text
    return text.encode("utf-8")  # py2 unicode -> str


class Shahid44u(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "season", "episode", "series_url",
                  "icon", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Shahid44u", "cookie": "Shahid44u.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()

        def cat(slug):
            return self.getFullUrl("category/" + slug)

        self.MENU = [{"category": "sub_menu", "title": _("Movies"), "sub": "movies"},
                     {"category": "sub_menu", "title": _("Series"), "sub": "series"},
                     {"category": "list_items", "title": _("TV Show"), "url": cat("%D8%A8%D8%B1%D8%A7%D9%85%D8%AC-%D8%AA%D9%84%D9%81%D8%B2%D9%8A%D9%88%D9%86%D9%8A%D8%A9")},
                     {"category": "list_items", "title": _("Wrestling"), "url": cat("%D8%B9%D8%B1%D9%88%D8%B6-%D9%85%D8%B5%D8%A7%D8%B1%D8%B9%D8%A9")}] + self.searchItems()
        self.SUB_MENUS = {
            "movies": [{"category": "list_items", "title": _("Foreign movies"), "url": cat("%D8%A7%D9%81%D9%84%D8%A7%D9%85-%D8%A7%D8%AC%D9%86%D8%A8%D9%8A")},
                       {"category": "list_items", "title": _("Arabic Movies"), "url": cat("%D8%A7%D9%81%D9%84%D8%A7%D9%85-%D8%B9%D8%B1%D8%A8%D9%8A")},
                       {"category": "list_items", "title": _("Indian Movies"), "url": cat("%D8%A7%D9%81%D9%84%D8%A7%D9%85-%D9%87%D9%86%D8%AF%D9%8A")},
                       {"category": "list_items", "title": _("Turkish Movies"), "url": cat("%D8%A7%D9%81%D9%84%D8%A7%D9%85-%D8%AA%D8%B1%D9%83%D9%8A%D8%A9")},
                       {"category": "list_items", "title": _("Asian movies"), "url": cat("%D8%A7%D9%81%D9%84%D8%A7%D9%85-%D8%A7%D8%B3%D9%8A%D9%88%D9%8A%D8%A9")},
                       {"category": "list_items", "title": _("Anime Movies"), "url": cat("%D8%A7%D9%81%D9%84%D8%A7%D9%85-%D8%A7%D9%86%D9%85%D9%8A")}],
            "series": [{"category": "list_items", "title": _("Foreign series"), "url": cat("%D9%85%D8%B3%D9%84%D8%B3%D9%84%D8%A7%D8%AA-%D8%A7%D8%AC%D9%86%D8%A8%D9%8A")},
                       {"category": "list_items", "title": _("Arabic Series"), "url": cat("%D9%85%D8%B3%D9%84%D8%B3%D9%84%D8%A7%D8%AA-%D8%B9%D8%B1%D8%A8%D9%8A")},
                       {"category": "list_items", "title": _("Turkish Series"), "url": cat("%D9%85%D8%B3%D9%84%D8%B3%D9%84%D8%A7%D8%AA-%D8%AA%D8%B1%D9%83%D9%8A%D8%A9")},
                       {"category": "list_items", "title": _("Asian TV series"), "url": cat("%D9%85%D8%B3%D9%84%D8%B3%D9%84%D8%A7%D8%AA-%D8%A7%D8%B3%D9%8A%D9%88%D9%8A%D8%A9")},
                       {"category": "list_items", "title": _("Indian TV series"), "url": cat("%D9%85%D8%B3%D9%84%D8%B3%D9%84%D8%A7%D8%AA-%D9%87%D9%86%D8%AF%D9%8A%D8%A9")},
                       {"category": "list_items", "title": _("Dubbed series"), "url": cat("%D9%85%D8%B3%D9%84%D8%B3%D9%84%D8%A7%D8%AA-%D9%85%D8%AF%D8%A8%D9%84%D8%AC%D8%A9")},
                       {"category": "list_items", "title": _("Anime Series"), "url": cat("%D9%85%D8%B3%D9%84%D8%B3%D9%84%D8%A7%D8%AA-%D8%A7%D9%86%D9%85%D9%8A")},
                       {"category": "list_items", "title": "%s 2026" % _("Ramadan"), "url": cat("%D9%85%D8%B3%D9%84%D8%B3%D9%84%D8%A7%D8%AA-%D8%B1%D9%85%D8%B6%D8%A7%D9%86-2026")}],
        }

        self.watchedHelper = IPTVWatchedHelper("shahid44u")
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
            if category == "sh_series":
                return "series:%s" % self.wfNormalizeUrlKey(url) if url else ""
            if category == "sh_season":
                return "season:%s" % self.wfNormalizeUrlKey(url) if url else ""  # page 2+ keys like page 1
            return ""
        except Exception:
            printExc()
        return ""

    def _quoteUrl(self, url):
        # the site links contain raw Arabic letters and even spaces
        if any(ord(c) > 127 for c in _toUnicode(url)) or " " in url:
            url = urllib_quote(_toNative(url), safe=":/?=&%#+;,")
        return url

    def _fullUrl(self, url, currUrl=None):
        return self._quoteUrl(self.getFullUrl(url.replace("&amp;", "&"), currUrl))

    def getPage(self, baseUrl, addParams=None, post_data=None):
        baseUrl = self._quoteUrl(baseUrl)
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    ###################################################
    # title helpers
    ###################################################
    def _seasonNumber(self, text):
        text = _toUnicode(text)
        num = re.search(u"الموسم\\s+(\\d+)", text)
        if num:
            return str(int(num.group(1)))
        for word, value in ORDINALS:
            if re.search(u"الموسم\\s+" + word + u"(?:\\s|$)", text):
                return str(value)
        return ""

    def _showName(self, text):
        text = _toUnicode(self.cleanHtmlStr(text))
        text = re.split(u"\\s+(?:الموسم|الحلقة)\\s", u" " + text + u" ", 1)[0].strip()
        text = TITLE_PREFIX_RE.sub(u"", text)
        for _i in range(3):
            text = TITLE_SUFFIX_RE.sub(u"", text).strip()
        return _toNative(text)

    def _latinTitle(self, text):
        # "الخدعة السوداء Black Trick" -> "Black Trick" for the metadata lookup
        parts = re.findall(r"[A-Za-z0-9][A-Za-z0-9 :'&.,!?-]*[A-Za-z0-9!?]", _toNative(text))
        parts = [p.strip() for p in parts if re.search(r"[A-Za-z]{2}", p)]
        if parts:
            return max(parts, key=len)
        return text

    def _movieInfo(self, text):
        text = _toUnicode(self.cleanHtmlStr(text))
        text = TITLE_PREFIX_RE.sub(u"", text)
        year = ""
        match = re.search(u"^(.*?)\\s+((?:19|20)\\d{2})(?:\\s|$)", text)
        if match:
            title, year = match.group(1), match.group(2)
        else:
            title = text
        for _i in range(3):
            title = TITLE_SUFFIX_RE.sub(u"", title).strip()
        return _toNative(title), year

    def _movieTitle(self, title, year, siteTitle):
        if IsMediaNamingNormalized():
            return "%s (%s)" % (title, year) if year else title
        return siteTitle

    def _episodeTitle(self, sTitle, season, episode, siteTitle):
        if IsMediaNamingNormalized() and episode:
            return "%s - %s" % (sTitle, formatSxxExx(season or "1", episode))
        return siteTitle

    ###################################################
    # lists
    ###################################################
    def listSubMenu(self, cItem):
        self.listsTab(self.SUB_MENUS.get(cItem.get("sub", ""), []), cItem)

    def _addCard(self, cItem, url, siteTitle, icon, desc):
        params = stripPagerKeys(dict(cItem), LIST_STATE_KEYS)
        params.update({"good_for_fav": True, "url": url, "icon": icon, "desc": desc})
        path = url.split("/", 3)[-1]
        if path.startswith("series/") or path.startswith("season/"):
            sTitle = self._showName(siteTitle)
            params.update({"category": "sh_series" if path.startswith("series/") else "sh_season", "title": sTitle, "s_title": sTitle,
                           "season": self._seasonNumber(siteTitle), "meta_type": "tv", "meta_title": self._latinTitle(sTitle), "meta_year": ""})
            self.addDir(params)
        elif path.startswith("episode/"):
            sTitle = self._showName(siteTitle)
            season = self._seasonNumber(siteTitle) or "1"
            epMatch = re.search(u"الحلقة\\s*(\\d+)", _toUnicode(siteTitle))
            episode = epMatch.group(1) if epMatch else ""
            params.update({"category": "sh_episode", "title": self._episodeTitle(sTitle, season, episode, siteTitle), "s_title": sTitle,
                           "season": season, "episode": episode, "meta_type": "tv", "meta_title": self._latinTitle(sTitle), "meta_year": ""})
            self.addVideo(params)
        else:
            title, year = self._movieInfo(siteTitle)
            params.update({"category": "sh_movie", "title": self._movieTitle(title, year, siteTitle), "s_title": title,
                           "meta_type": "movie", "meta_title": self._latinTitle(title), "meta_year": year})
            self.addVideo(params)

    def _pagedUrl(self, cItem):
        # "?page=N" lists (rel="next", no page count): -> (page, base url, url of this page, url template)
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or re.sub(r"[?&]page=\d+$", "", self._quoteUrl(cItem["url"]))
        pageUrlTpl = baseUrl + ("&" if "?" in baseUrl else "?") + "page={page}"
        return page, baseUrl, baseUrl if page <= 1 else pageUrlTpl.format(page=page), pageUrlTpl

    def _addPaging(self, cItem, data, page, baseUrl, pageUrlTpl, hasItems):
        hasNext = hasItems and bool(self.cm.ph.getSearchGroups(data, r'<link rel="next" href="([^"]+)"')[0])
        listItem = dict(cItem)
        listItem.update({"base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, 0, pageUrlTpl)

    def listItems(self, cItem):
        page, baseUrl, url, pageUrlTpl = self._pagedUrl(cItem)
        printDBG("Shahid44u.listItems |%s|" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        cnt = 0
        seen = set()
        for item in data.split('class="col-6 col-md-4')[1:]:
            href = self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0]
            itemUrl = self._fullUrl(href, url)
            if not self.cm.isValidUrl(itemUrl) or itemUrl in seen:
                continue
            seen.add(itemUrl)
            siteTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<p class="title">(.*?)</p>')[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])
            if not siteTitle:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'<img\s+src="([^"]+)"')[0]
            icon = self._fullUrl(icon, url) if icon else ""
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<span class="categ">([^<]+)<')[0])
            self._addCard(cItem, itemUrl, siteTitle, icon, desc)
            cnt += 1
        # list_items, not the copied "search": that would rebuild page 1 from the search pattern
        self._addPaging(dict(cItem, category="list_items"), data, page, baseUrl, pageUrlTpl, bool(cnt))

    def _epssLinks(self, data, kind, currUrl):
        ret = []
        for href, body in re.findall(r'<a href="([^"]*/%s/[^"]+)" class="epss[^"]*">(.*?)</a>' % kind, data, re.DOTALL):
            url = self._fullUrl(href, currUrl)
            num = self.cm.ph.getSearchGroups(body, r'class="fs-2">\s*(\d+)')[0]
            if self.cm.isValidUrl(url) and url not in [r[0] for r in ret]:
                ret.append((url, num))
        return ret

    def listSeasons(self, cItem):
        printDBG("Shahid44u.listSeasons |%s|" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seasons = self._epssLinks(data, "season", cItem["url"])
        sTitle = cItem.get("s_title", cItem["title"])
        if len(seasons) == 1:
            params = dict(cItem)
            params.update({"url": seasons[0][0], "season": seasons[0][1] or "1", "series_url": cItem["url"]})
            self.listEpisodes(params)
            return
        for url, snum in seasons:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "sh_season", "url": url, "season": snum, "series_url": cItem["url"],
                           "title": "%s - %s %s" % (sTitle, _("Season"), snum)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        # the season page lists its episodes ?page=N wise like the category lists
        page, baseUrl, url, pageUrlTpl = self._pagedUrl(cItem)
        printDBG("Shahid44u.listEpisodes |%s|" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        sTitle = cItem.get("s_title", cItem["title"])
        season = cItem.get("season", "") or "1"
        if not cItem.get("series_url"):
            seriesUrl = self.cm.ph.getSearchGroups(data, r'href="([^"]*/series/[^"/]+)"')[0]
            if seriesUrl:
                cItem = dict(cItem, series_url=self._fullUrl(seriesUrl, url))
        episodes = self._epssLinks(data, "episode", url)
        for epUrl, episode in episodes:
            siteTitle = "%s - %s %s" % (sTitle, _("Episode"), episode) if episode else sTitle
            params = stripPagerKeys(dict(cItem), LIST_STATE_KEYS)
            params.update({"good_for_fav": True, "category": "sh_episode", "type": "video", "url": epUrl, "season": season, "episode": episode,
                           "title": self._episodeTitle(sTitle, season, episode, siteTitle)})
            self.addVideo(params)
        self._addPaging(dict(cItem, category="sh_season"), data, page, baseUrl, pageUrlTpl, bool(episodes))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Shahid44u.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("search?s=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Shahid44u.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = cItem.get("url", "")
        if not self.cm.isValidUrl(pageUrl):
            return []
        watchUrl = re.sub(r"^(https?://[^/]+/)(?:film|episode|post)/", r"\1watch/", pageUrl)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=pageUrl)
        sts, data = self.getPage(watchUrl, params)
        if not sts:
            return []
        servers = []
        try:
            servers = json_loads(self.cm.ph.getSearchGroups(data, r"let servers\s*=\s*(\[.*?\]);")[0] or "[]")
        except Exception:
            printExc()
        urltab = []
        for server in sorted(servers, key=lambda s: s.get("rank", 99) or 99):
            link = self._fullUrl(str(server.get("url", "") or ""), watchUrl)
            if not self.cm.isValidUrl(link):
                continue
            name = str(server.get("name", "") or "").strip() or self.up.getHostName(link)
            urltab.append({"name": name, "url": strwithmeta(link, {"Referer": watchUrl}), "need_resolve": 1})
        sidecarTxt = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="description">', "</div>", False)[1])
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def _resolveRedirect(self, videoUrl):
        # /m/<hash> answers 302 to the hoster embed, but only for an iframe request from the watch page
        url = strwithmeta(videoUrl)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Referer": url.meta.get("Referer", self.MAIN_URL), "Sec-Fetch-Dest": "iframe", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "same-origin"})
        params["no_redirection"] = True
        # through the Cloudflare-aware getPage: a plain cm.getPage goes through pycurl, which does not send the
        # MyE2i cf_clearance (stored without a domain by urllib) -> 403 challenge, and its cookie save drops it
        sts, data = self.getPage(str(url), params)
        location = self.cm.meta.get("location", "") or ""
        if not location and sts:
            location = self.cm.ph.getSearchGroups(data, r'''http-equiv="refresh" content="0;url='([^']+)'"''')[0]
        if not location:
            # an HTTP layer that followed the redirect anyway: take the final url
            finalUrl = str(self.cm.meta.get("url", "") or "")
            if self.cm.isValidUrl(finalUrl) and self.up.getHostName(finalUrl) != self.up.getHostName(self.MAIN_URL):
                location = finalUrl
        if location.startswith("//"):
            location = "https:" + location
        if self.cm.isValidUrl(location) and "/m/" not in location:
            return strwithmeta(location, {"Referer": self.MAIN_URL})
        return ""

    def getVideoLinks(self, videoUrl):
        printDBG("Shahid44u.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if self.up.getHostName(videoUrl) == self.up.getHostName(self.MAIN_URL) and "/m/" in videoUrl:
            videoUrl = self._resolveRedirect(videoUrl)
            if not videoUrl:
                return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # info / favourites
    ###################################################
    def _parsePage(self, data):
        info = {"desc": "", "poster": "", "year": "", "imdb": "", "genres": "", "series_url": ""}
        info["desc"] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="description">', "</div>", False)[1])
        if not info["desc"]:
            info["desc"] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="description">', "</span>", False)[1])
        if not info["desc"]:
            info["desc"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]+)"')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        info["poster"] = self._fullUrl(poster) if poster else ""
        info["imdb"] = self.cm.ph.getSearchGroups(poster, r"/imdb/(tt\d+)")[0]
        info["year"] = self.cm.ph.getSearchGroups(data, r"/release-year/(\d{4})")[0]
        genres = re.findall(r'href="[^"]+/genre/[^"]+"[^>]*>([^<]+)</a>', data)
        info["genres"] = ", ".join(self.cleanHtmlStr(g) for g in genres[:4])
        seriesUrl = self.cm.ph.getSearchGroups(data, r'href="([^"]*/series/[^"/]+)"')[0]
        info["series_url"] = self._fullUrl(seriesUrl) if seriesUrl else ""
        return info

    def getArticleContent(self, cItem):
        printDBG("Shahid44u.getArticleContent [%s]" % cItem.get("url", ""))
        mediaType = cItem.get("meta_type", "")
        pageUrl = cItem.get("url", "")
        info = {"desc": "", "poster": "", "year": "", "imdb": "", "genres": "", "series_url": ""}
        if self.cm.isValidUrl(pageUrl):
            sts, data = self.getPage(pageUrl)
            if sts:
                info = self._parsePage(data)
        if mediaType == "tv" and not info["imdb"]:
            # the series page carries the IMDb id (og:image /photos/shares/imdb/tt...)
            seriesUrl = cItem.get("series_url") or info["series_url"]
            if self.cm.isValidUrl(seriesUrl) and seriesUrl != pageUrl:
                sts, data = self.getPage(seriesUrl)
                if sts:
                    sInfo = self._parsePage(data)
                    info["imdb"] = sInfo["imdb"]
                    info["year"] = info["year"] or sInfo["year"]
                    info["desc"] = info["desc"] or sInfo["desc"]
        meta = {}
        try:
            if info["imdb"]:
                meta = getMetaByImdbId(mediaType, info["imdb"])
            if not meta:
                meta = getMeta(mediaType, cItem.get("meta_title", "") or cItem.get("s_title", ""), cItem.get("meta_year", "") or info["year"])
        except Exception:
            printExc()
            meta = {}
        otherInfo = dict(meta.get("info", {}) or {})
        if info["year"]:
            otherInfo.setdefault("year", info["year"])
        if info["genres"]:
            otherInfo.setdefault("genres", info["genres"])
        text = info["desc"] or meta.get("plot", "") or cItem.get("desc", "")
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
        printDBG("Shahid44u.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "sub_menu":
            self.listSubMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "sh_series":
            self.listSeasons(self.currItem)
        elif category == "sh_season":
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
        CHostBase.__init__(self, Shahid44u(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("shahid44u")

    def withArticleContent(self, cItem):
        return bool(cItem.get("meta_type"))
