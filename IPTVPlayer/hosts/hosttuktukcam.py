# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - rewrite for the new domain tuktukhd.com (tuk.cam is dead,
#   www.tuktukcima.com redirects here): "Block--Item" grids with WordPress pager, /series/ pages
#   with season cards and episode cards, the player servers sit in data-link (reversed base64)
#   and data-crypt (base64); the TukTuk/Megamax mirror page goes to urlparser (parserMEGAMAX);
#   paging via tools/iptvpaging (First page / Jump / Next page with the last page) + watched flag /
#   downloaded flag / name normalisation / sidecar / moviemeta INFO / favourites.
import base64
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
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
    return "https://tuktukhd.com/"


# Arabic ordinals used in "الموسم الثاني"
ORDINALS = [(u"الحادي عشر", 11), (u"الثاني عشر", 12), (u"الثالث عشر", 13), (u"الرابع عشر", 14), (u"الخامس عشر", 15),
            (u"الاول", 1), (u"الأول", 1), (u"الثاني", 2), (u"الثالث", 3), (u"الرابع", 4), (u"الخامس", 5),
            (u"السادس", 6), (u"السابع", 7), (u"الثامن", 8), (u"التاسع", 9), (u"العاشر", 10)]
TITLE_PREFIX_RE = re.compile(u"^\\s*(?:مسلسل|مسلسلات|انمي|أنمي|برنامج|عرض|فيلم|فلم)\\s+")
TITLE_SUFFIX_RE = re.compile(u"\\s+(?:مترجمة|مترجم|مدبلجة|مدبلج|اون لاين|أون لاين|كامل|كاملة|بجودة.*|حصري.*|والاخيرة|والأخيرة|الاخيرة|الأخيرة|bet)\\s*$", re.IGNORECASE)


def _toUnicode(text):
    try:
        if isinstance(text, bytes) and not isinstance(text, str):
            return text.decode("utf-8", "ignore")  # py3 bytes
        if not isinstance(text, type(u"")):
            return text.decode("utf-8", "ignore")  # py2 str
    except Exception:
        pass
    return text


def _toNative(text):
    if isinstance(text, str):
        return text
    return text.encode("utf-8")  # py2 unicode -> str


class TukTukCam(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "season", "episode", "series_url",
                  "icon", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "tuktukcam", "cookie": "tuktukcam.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/tuktuk.png"
        cat = self.getFullUrl
        self.MENU = [{"category": "list_items", "title": _("Recently added"), "url": cat("recent/")},
                     {"category": "sub_menu", "title": _("Movies"), "sub": "movies"},
                     {"category": "sub_menu", "title": _("Series"), "sub": "series"},
                     {"category": "sub_menu", "title": _("Anime"), "sub": "anime"},
                     {"category": "list_items", "title": _("TV Shows"), "url": cat("sercat/%d8%a8%d8%b1%d8%a7%d9%85%d8%ac-%d8%aa%d9%84%d9%81%d8%b2%d9%8a%d9%88%d9%86%d9%8a%d8%a9/")},
                     {"category": "list_items", "title": "Netflix - %s" % _("Movies"), "url": cat("channel/film-netflix-1/")},
                     {"category": "list_items", "title": "Netflix - %s" % _("Series"), "url": cat("channel/series-netflix-2/")}] + self.searchItems()
        self.SUB_MENUS = {
            "movies": [{"category": "list_items", "title": _("All movies"), "url": cat("category/movies-2/")},
                       {"category": "list_items", "title": _("Foreign movies"), "url": cat("category/movies-2/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/")},
                       {"category": "list_items", "title": _("Asian movies"), "url": cat("category/movies-2/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a/")},
                       {"category": "list_items", "title": _("Turkish Movies"), "url": cat("category/movies-2/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%aa%d8%b1%d9%83%d9%8a/")},
                       {"category": "list_items", "title": _("Indian Movies"), "url": cat("category/movies-2/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%87%d9%86%d8%af%d9%89/")},
                       {"category": "list_items", "title": _("Dubbed movies"), "url": cat("category/movies-2/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/")}],
            "series": [{"category": "list_items", "title": _("Foreign series"), "url": cat("sercat/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/")},
                       {"category": "list_items", "title": _("Asian TV series"), "url": cat("sercat/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a3%d8%b3%d9%8a%d9%88%d9%8a/")},
                       {"category": "list_items", "title": _("Turkish Series"), "url": cat("sercat/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%aa%d8%b1%d9%83%d9%8a/")},
                       {"category": "list_items", "title": _("Indian TV series"), "url": cat("sercat/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%87%d9%86%d8%af%d9%8a/")},
                       {"category": "list_items", "title": _("Complete series"), "url": cat("channel/full-series-1/")},
                       {"category": "list_items", "title": _("Newest Episodes"), "url": cat("category/series-1/")}],
            "anime": [{"category": "list_items", "title": _("Anime list"), "url": cat("sercat/%d9%82%d8%a7%d8%a6%d9%85%d8%a9-%d8%a7%d9%84%d8%a7%d9%86%d9%85%d9%8a/")},
                      {"category": "list_items", "title": "%s - %s" % (_("Anime"), _("Episodes")), "url": cat("category/anime-6/%d8%a7%d9%86%d9%85%d9%8a-%d9%85%d8%aa%d8%b1%d8%ac%d9%85/")},
                      {"category": "list_items", "title": _("Anime movies"), "url": cat("category/anime-6/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%86%d9%85%d9%8a/")}],
        }

        self.watchedHelper = IPTVWatchedHelper("tuktukcam")
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
            if category == "tk_series":
                return "series:%s" % url if url else ""
            if category == "tk_season":
                return "season:%s" % url if url else ""
            return ""
        except Exception:
            printExc()
        return ""

    def getPage(self, baseUrl, addParams=None, post_data=None):
        baseUrl = self._quoteUrl(baseUrl)
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _quoteUrl(self, url):
        # the site links are percent-encoded already; quote only raw non-ASCII characters / spaces
        if any(ord(c) > 127 for c in _toUnicode(url)) or " " in url:
            url = urllib_quote(_toNative(url), safe=":/?=&%#+;,")
        return url

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

    def _addBlock(self, cItem, url, siteTitle, icon, desc):
        params = stripPagerKeys(dict(cItem), ("search_pattern",))
        params.update({"good_for_fav": True, "url": url, "icon": icon, "desc": desc})
        if "/series/" in url:
            sTitle = self._showName(siteTitle)
            params.update({"category": "tk_series", "title": sTitle, "s_title": sTitle, "series_url": url,
                           "meta_type": "tv", "meta_title": self._latinTitle(sTitle), "meta_year": ""})
            self.addDir(params)
        elif re.search(u"الحلقة\\s*\\d+", _toUnicode(siteTitle)):
            sTitle = self._showName(siteTitle)
            season = self._seasonNumber(siteTitle) or "1"
            episode = re.search(u"الحلقة\\s*(\\d+)", _toUnicode(siteTitle)).group(1)
            params.update({"category": "tk_episode", "title": self._episodeTitle(sTitle, season, episode, siteTitle), "s_title": sTitle,
                           "season": season, "episode": episode, "meta_type": "tv", "meta_title": self._latinTitle(sTitle), "meta_year": ""})
            self.addVideo(params)
        else:
            title, year = self._movieInfo(siteTitle)
            params.update({"category": "tk_movie", "title": self._movieTitle(title, year, siteTitle), "s_title": title,
                           "meta_type": "movie", "meta_title": self._latinTitle(title), "meta_year": year})
            self.addVideo(params)

    def listItems(self, cItem):
        printDBG("TukTukCam.listItems |%s|" % cItem.get("url", ""))
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', "</ul>", False)[1]
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<section class="MasterArchiveSection', '<div class="pagination">', False)[1] or data
        cnt = 0
        seen = set()
        for item in tmp.split('<div class="Block--Item')[1:]:
            href = self.cm.ph.getSearchGroups(item, r'<a\s+href="([^"]+)"')[0]
            itemUrl = self.getFullUrl(href, url)
            if not self.cm.isValidUrl(itemUrl) or itemUrl in seen:
                continue
            seen.add(itemUrl)
            siteTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h[23][^>]*>(.*?)</h[23]>')[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not siteTitle:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            icon = self.getFullIconUrl(icon, url) if icon else ""
            genres = [self.cleanHtmlStr(g) for g in re.findall(r"<li>(.*?)</li>", self.cm.ph.getDataBeetwenMarkers(item, '<ul class="Genres">', "</ul>", False)[1], re.DOTALL)]
            self._addBlock(cItem, itemUrl, siteTitle, icon, ", ".join([g for g in genres if g]))
            cnt += 1
        # WordPress pager: ".../page/N/", ".../?page=N" (sercat) or "?s=x&page=N" (search) - the page
        # url template comes from the pager's own links; "2٬411" = 2411
        page = int(cItem.get("page", 0) or 0) or int(self.cm.ph.getSearchGroups(url, r"(?:/page/|[?&]page=)(\d+)")[0] or 1)
        tpl = ""
        for href in re.findall(r'<a[^>]+href="([^"]+)"', pager):
            href = self.getFullUrl(href.replace("&#038;", "&").replace("&amp;", "&"), url)
            if re.search(r"(?:/page/|[?&]page=)\d+", href):
                tpl = re.sub(r"(/page/|[?&]page=)\d+", r"\g<1>{page}", href, 1)
                break
        nums = [re.sub(r"\D", "", n) for n in re.findall(r'class="page-numbers[^"]*"[^>]*>([^<]+)<', pager)]
        lastPage = max([int(n) for n in nums if n] + [page])
        hasNext = bool(cnt) and 'class="next page-numbers"' in pager
        addPagingItems(self, dict(cItem, category="list_items"), page, hasNext, lastPage if hasNext or page > 1 else 0, tpl)

    def _parseSeasons(self, data, pageUrl):
        seasons = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<section class="SeriesSeasons"', "</section>", False)[1]
        for item in tmp.split("SeriesPosterCard")[1:]:
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            url = self.getFullUrl(href, pageUrl)
            if not self.cm.isValidUrl(url) or url in [s[0] for s in seasons]:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]
            if "no.png" in icon:
                icon = ""
            seasons.append((url, title, self._seasonNumber(title), self.getFullIconUrl(icon, pageUrl) if icon else ""))
        return seasons

    def listSeasons(self, cItem):
        printDBG("TukTukCam.listSeasons |%s|" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seasons = self._parseSeasons(data, cItem["url"])
        if len(seasons) > 1:
            sTitle = cItem.get("s_title", cItem["title"])
            for url, title, snum, icon in seasons:
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "tk_season", "url": url, "season": snum,
                               "title": "%s - %s %s" % (sTitle, _("Season"), snum) if snum else "%s - %s" % (sTitle, title),
                               "series_url": cItem["url"], "icon": icon or cItem.get("icon", "")})
                self.addDir(params)
            return
        if len(seasons) == 1 and seasons[0][0].rstrip("/") != cItem["url"].rstrip("/"):
            params = dict(cItem)
            params.update({"url": seasons[0][0], "season": seasons[0][2] or "1", "series_url": cItem["url"]})
            self.listEpisodes(params)
            return
        params = dict(cItem)
        params.update({"season": seasons[0][2] if seasons else "", "series_url": cItem["url"]})
        self.listEpisodes(params, data)

    def listEpisodes(self, cItem, data=None):
        printDBG("TukTukCam.listEpisodes |%s|" % cItem["url"])
        url = cItem["url"]
        sTitle = cItem.get("s_title", cItem["title"])
        seen = set()
        episodes = []
        for _page in range(10):
            if data is None:
                sts, data = self.getPage(url)
                if not sts:
                    break
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<section class="SeriesEpisodes', "</section>", False)[1] or data
            for item in tmp.split('class="SeriesEpisodeCard"')[1:]:
                href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
                epUrl = self.getFullUrl(href, url)
                if not self.cm.isValidUrl(epUrl) or epUrl in seen:
                    continue
                seen.add(epUrl)
                siteTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h3>(.*?)</h3>')[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
                numMatch = re.search(r'class="SeriesEpisodeNumber">.*?<strong>\s*(\d+)', item, re.DOTALL)
                if numMatch:
                    episode = numMatch.group(1)
                else:
                    epMatch = re.search(u"الحلقة\\s*(\\d+)", _toUnicode(siteTitle))
                    episode = epMatch.group(1) if epMatch else ""
                season = cItem.get("season", "") or self._seasonNumber(siteTitle) or "1"
                icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]
                episodes.append((epUrl, siteTitle or sTitle, season, episode, self.getFullIconUrl(icon, url) if icon else ""))
            nextPage = self.cm.ph.getSearchGroups(data, r'<link rel="next" href="([^"]+)"')[0]
            data = None
            if not nextPage:
                break
            nextUrl = self.getFullUrl(self.cleanHtmlStr(nextPage), url)
            if nextUrl == url:
                break
            url = nextUrl
        # the site lists the newest episode first
        try:
            episodes.sort(key=lambda e: (int(e[2] or 0), int(e[3] or 0)))
        except Exception:
            printExc()
        for epUrl, siteTitle, season, episode, icon in episodes:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "tk_episode", "type": "video", "url": epUrl, "season": season, "episode": episode,
                           "title": self._episodeTitle(sTitle, season, episode, siteTitle), "icon": icon or cItem.get("icon", "")})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TukTukCam.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("?s=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _b64(self, text):
        try:
            text = text.strip()
            text += "=" * (-len(text) % 4)
            return _toNative(base64.b64decode(text).decode("utf-8", "ignore"))
        except Exception:
            return ""

    def _decodeLink(self, value):
        # setup.js decodeLink(): split at "0REL0Y&", reverse, atob
        value = value.replace("&amp;", "&").split("0REL0Y&")[0]
        return self._b64(value[::-1])

    def getLinksForVideo(self, cItem):
        printDBG("TukTukCam.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = cItem.get("url", "")
        if not self.cm.isValidUrl(pageUrl):
            return []
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        sidecarTxt = self._parsePage(data)["desc"]

        embeds = []
        for attrs in re.findall(r'<li([^>]+data-link="[^"]+"[^>]*)>', data):
            link = self._decodeLink(self.cm.ph.getSearchGroups(attrs, r'data-link="([^"]+)"')[0])
            if link and link not in embeds:
                embeds.append(link)
        crypt = self.cm.ph.getSearchGroups(data, r'data-crypt="([^"]+)"')[0]
        if crypt:
            link = self._b64(crypt)
            if link and link not in embeds:
                embeds.append(link)

        # the TukTuk/Megamax mirror page (megatuktuk.store/iframe/..) is urlparser.parserMEGAMAX
        urltab = []
        for embed in embeds:
            if embed.startswith("//"):
                embed = "https:" + embed
            if self.cm.isValidUrl(embed) and embed not in [x["url"] for x in urltab]:
                urltab.append({"name": self.up.getHostName(embed), "url": strwithmeta(embed, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("TukTukCam.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # info / favourites
    ###################################################
    def _parsePage(self, data):
        info = {"desc": "", "poster": "", "year": "", "duration": "", "genres": "", "series_url": ""}
        info["desc"] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="story">', "</div>", False)[1])
        poster = self.cm.ph.getSearchGroups(self.cm.ph.getDataBeetwenMarkers(data, '<div class="image">', "</div>", False)[1], r'<img[^>]+src="([^"]+)"')[0]
        if not poster:
            poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        info["poster"] = self.getFullIconUrl(poster) if poster else ""
        info["year"] = self.cm.ph.getSearchGroups(data, r'/release-year/(\d{4})')[0]
        durMatch = re.search(r'fa-clock"></i>\s*<span>[^<]*</span>\s*<strong>([^<]+)</strong>', data)
        info["duration"] = self.cleanHtmlStr(durMatch.group(1)) if durMatch else ""
        genres = re.findall(r'href="[^"]+/genre/[^"]+">([^<]+)</a>', data)
        info["genres"] = ", ".join(self.cleanHtmlStr(g) for g in genres[:4])
        info["series_url"] = self.cm.ph.getSearchGroups(self.cm.ph.getDataBeetwenMarkers(data, 'id="mpbreadcrumbs"', "</div>", False)[1], r'href="([^"]+/series/[^"]+)"')[0]
        return info

    def getArticleContent(self, cItem):
        printDBG("TukTukCam.getArticleContent [%s]" % cItem.get("url", ""))
        mediaType = cItem.get("meta_type", "")
        pageUrl = cItem.get("series_url") or cItem.get("url", "")
        info = {"desc": "", "poster": "", "year": "", "duration": "", "genres": "", "series_url": ""}
        if self.cm.isValidUrl(pageUrl):
            sts, data = self.getPage(pageUrl)
            if sts:
                info = self._parsePage(data)
        meta = {}
        try:
            meta = getMeta(mediaType, cItem.get("meta_title", "") or cItem.get("s_title", ""), cItem.get("meta_year", "") or info["year"])
        except Exception:
            printExc()
            meta = {}
        otherInfo = dict(meta.get("info", {}) or {})
        if info["year"]:
            otherInfo.setdefault("year", info["year"])
        if info["duration"]:
            otherInfo.setdefault("duration", info["duration"])
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
        printDBG("TukTukCam.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "sub_menu":
            self.listSubMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "tk_series":
            self.listSeasons(self.currItem)
        elif category == "tk_season":
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
        CHostBase.__init__(self, TukTukCam(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("tuktukcam")

    def withArticleContent(self, cItem):
        return bool(cItem.get("meta_type"))
