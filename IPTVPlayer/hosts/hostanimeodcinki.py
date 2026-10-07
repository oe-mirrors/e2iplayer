# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - revival for the redesigned anime-odcinki.pl ("VOD Dashboard", Cloudflare):
#   catalogue from the hex encoded JSON of /anime-lista/ (series / movies A-Z, airing now), latest
#   episodes via admin-ajax ao_get_latest_episodes (First page / Next page), genre / season / search pages
#   (anime-card lists, First page / Jump / Next page over .../strona/N/), episode list from the series page (base64 data-url), hoster iframes from the reversed
#   base64 data-token tabs of the episode page; watched flag, downloaded flag, name normalisation,
#   sidecar, moviemeta INFO (combined with the site's Polish description), favourites.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
from binascii import a2b_base64, unhexlify
import re
import time
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://anime-odcinki.pl/"


class AnimeOdcinkiPL(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what identifies a favourite and opens it again; desc / rating differ between the lists
    FAV_FIELDS = ("name", "category", "type", "url", "s_title", "icon", "meta_type", "meta_title", "meta_year", "season", "ep_num")

    GENRES = (("akcja", "Akcja"), ("dramat", "Dramat"), ("fantasy", "Fantasy"), ("historyczne", "Historyczne"),
              ("horror", "Horror"), ("isekai", "Isekai"), ("komedia", "Komedia"),
              ("kryminalyzagadkitajemnice", "Kryminały/zagadki/tajemnice"), ("okruchy-zycia", "Okruchy życia"),
              ("przygodowe", "Przygodowe"), ("romans", "Romans"), ("sportowe", "Sportowe"),
              ("szkolne-zycie", "Szkolne życie"), ("sztuki-walki", "Sztuki walki"), ("wojskowewojenne", "Wojskowe/Wojenne"))

    # (url slug, first month of the anime season)
    SEASONS = (("jesien", 10), ("lato", 7), ("wiosna", 4), ("zima", 1))

    LATEST_LIMIT = 24
    DB_PAGE_SIZE = 100
    # a film page with up to this many episodes is one film in parts (one link list), more is a collection (folder)
    MAX_FILM_PARTS = 3

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "AnimeOdcinki.pl", "cookie": "animeodcinkipl.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://i0.wp.com/anime-odcinki.pl/wp-content/uploads/2016/12/cropped-favicon-1.jpg?fit=192%2C192&ssl=1"
        self.AJAX_URL = self.getFullUrl("wp-admin/admin-ajax.php")
        self.MENU = [{"category": "latest", "title": _("Latest episodes (airing)"), "filter": "emitowane"},
                     {"category": "latest", "title": _("Latest episodes (finished series)"), "filter": "nieemitowane"},
                     {"category": "db_items", "title": _("Airing now"), "f_air": 1},
                     {"category": "db_letters", "title": _("Anime series A-Z"), "f_mv": 0},
                     {"category": "db_letters", "title": _("Anime movies A-Z"), "f_mv": 1},
                     {"category": "genres", "title": _("Genres")},
                     {"category": "season_years", "title": _("Seasons")}] + self.searchItems()
        self.catalog = None
        self.seriesCache = {}

        self.watchedHelper = IPTVWatchedHelper("animeodcinki")
        self.wfInitFolderCache()

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if not url:
                return ""
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url
            if cItem.get("category", "") == "series":
                return "series:%s" % url
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "") in ("series", "movie", "episode"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _icon(self, url):
        # one stable, small poster url for the same picture from every list (i0.wp.com resizer)
        url = ensure_str(url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if not url:
            return ""
        url = self.getFullIconUrl(url)
        m = re.match(r"https?://(?:i\d\.wp\.com/)?(anime-odcinki\.pl/wp-content/[^?#]+)", url)
        if m:
            return "https://i0.wp.com/%s?w=300" % m.group(1)
        return url

    @staticmethod
    def _seriesUrl(url):
        # episode page .../anime/<slug>/<num>/ -> series page .../anime/<slug>/
        return re.sub(r"(/anime/[^/]+/)\d+[^/]*/?$", r"\1", url)

    @staticmethod
    def _seasonNum(title):
        for pattern in (r"(\d+)(?:st|nd|rd|th)\s+Season", r"Season\s+(\d+)", r"\bS(\d+)\b"):
            m = re.search(pattern, title, re.I)
            if m:
                return int(m.group(1))
        return 1

    @staticmethod
    def _metaTitle(title):
        title = re.sub(r"\s*(?:\(\d{4}\)|\d+(?:st|nd|rd|th)\s+Season|Season\s+\d+|\bS\d+|Part\s+\d+)\s*$", "", title, flags=re.I)
        return title.strip(" -:")

    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year and ("(%s)" % year) not in title:
            return "%s (%s)" % (title, year)
        return title

    def _episodeTitle(self, sTitle, epNum, siteLabel):
        num = self.cm.ph.getSearchGroups(str(epNum), r"(\d+)")[0]
        if IsMediaNamingNormalized() and num:
            return "%s - %s" % (sTitle, formatSxxExx(self._seasonNum(sTitle), num))
        return siteLabel or ("%s - %s %s" % (sTitle, _("Episode"), epNum))

    def _seriesParams(self, url, title, icon, year="", desc="", isMovie=False):
        title = self.cleanHtmlStr(title)
        params = {"name": "category", "good_for_fav": True, "url": url, "s_title": title, "icon": icon, "desc": desc,
                  "meta_type": "movie" if isMovie else "tv", "meta_title": self._metaTitle(title), "meta_year": year}
        if isMovie:
            params.update({"category": "movie", "title": self._movieTitle(title, year)})
        else:
            params.update({"category": "series", "title": title})
        return params

    def _addSeries(self, params):
        if params["category"] == "movie":
            self.addVideo(params)
        else:
            self.addDir(params)

    ###################################################
    # catalogue (/anime-lista/ carries the whole database as hex encoded JSON)
    ###################################################
    def _getCatalog(self):
        if self.catalog is not None:
            return self.catalog
        sts, data = self.getPage(self.getFullUrl("anime-lista/"))
        if not sts:
            return []
        hexData = self.cm.ph.getSearchGroups(data, r'hexData\s*=\s*"([0-9a-fA-F]+)"')[0]
        try:
            items = json_loads(unhexlify(hexData).decode("utf-8"))
        except Exception:
            printExc()
            return []
        catalog = []
        for item in items:
            try:
                url = ensure_str(item.get("url", ""))
                title = ensure_str(item.get("t", ""))
                if not url or not title:
                    continue
                catalog.append({"url": url, "t": title, "l": ensure_str(item.get("l", "") or "#"), "img": ensure_str(item.get("img", "") or ""),
                                "y": ensure_str(item.get("y", "") or ""), "mv": item.get("mv", 0) == 1, "air": item.get("air", 0) == 1,
                                "ep": int(item.get("ep", 0) or 0), "rt": ensure_str(item.get("rt", "") or "")})
            except Exception:
                printExc()
        catalog.sort(key=lambda x: x["t"].lower())
        self.catalog = catalog
        return catalog

    def _catalogDesc(self, item):
        desc = []
        if item["y"]:
            desc.append("%s: %s" % (_("Year"), item["y"]))
        if item["ep"] > 1 or (item["ep"] and not item["mv"]):
            desc.append("%s: %s" % (_("Episodes"), item["ep"]))
        if item["rt"] and item["rt"] not in ("0", "0.00"):
            desc.append("%s: %s/10" % (_("Rating"), item["rt"]))
        return " | ".join(desc)

    def listDbLetters(self, cItem):
        printDBG("AnimeOdcinkiPL.listDbLetters")
        isMovie = cItem.get("f_mv", 0) == 1
        counts = {}
        letters = []
        for item in self._getCatalog():
            if item["mv"] != isMovie:
                continue
            if item["l"] not in counts:
                counts[item["l"]] = 0
                letters.append(item["l"])
            counts[item["l"]] += 1
        letters.sort(key=lambda x: (x != "#", x))
        for letter in letters:
            params = dict(cItem)
            params.update({"good_for_fav": False, "category": "db_items", "title": "%s (%d)" % (letter, counts[letter]), "f_letter": letter})
            self.addDir(params)

    def listDbItems(self, cItem):
        printDBG("AnimeOdcinkiPL.listDbItems")
        isMovie = cItem.get("f_mv", None)
        letter = cItem.get("f_letter", None)
        items = []
        for item in self._getCatalog():
            if cItem.get("f_air") and not item["air"]:
                continue
            if isMovie is not None and item["mv"] != (isMovie == 1):
                continue
            if letter is not None and item["l"] != letter:
                continue
            items.append(item)
        # the catalogue is one big answer - long letters / "Airing now" are paged here
        page = max(1, int(cItem.get("page", 1) or 1))
        start = (page - 1) * self.DB_PAGE_SIZE
        for item in items[start:start + self.DB_PAGE_SIZE]:
            isFilm = item["mv"] and item["ep"] <= self.MAX_FILM_PARTS
            self._addSeries(self._seriesParams(item["url"], item["t"], self._icon(item["img"]), item["y"], self._catalogDesc(item), isFilm))
        lastPage = (len(items) + self.DB_PAGE_SIZE - 1) // self.DB_PAGE_SIZE
        # constant template: the page number drives the list, the template only lets "Jump" through
        addPagingItems(self, cItem, page, page < lastPage, lastPage, self.getFullUrl("anime-lista/"))

    ###################################################
    # lists
    ###################################################
    def listLatest(self, cItem):
        printDBG("AnimeOdcinkiPL.listLatest")
        page = cItem.get("page", 1)
        post = {"action": "ao_get_latest_episodes", "filter": cItem.get("filter", "emitowane"), "limit": str(self.LATEST_LIMIT), "page": str(page)}
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Referer": self.MAIN_URL, "X-Requested-With": "XMLHttpRequest"})
        sts, data = self.getPage(self.AJAX_URL, params, post)
        if not sts:
            return
        cnt = 0
        seen = set()
        for url, body in re.findall(r'<a\s+href="([^"]+)"\s+class="ep-card">(.*?)</a>', data, re.S):
            url = self.getFullUrl(url)
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(body, ("<div", ">", "ep-title"), ("</div", ">"), False)[1])
            if not url or not sTitle:
                continue
            cnt += 1
            badge = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(body, ("<span", ">", "badge-ep"), ("</span", ">"), False)[1])
            fmt = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(body, ("<span", ">", "badge-format"), ("</span", ">"), False)[1]).upper()
            icon = self._icon(self.cm.ph.getSearchGroups(body, r'src="([^"]+)"')[0])
            epNum = self.cm.ph.getSearchGroups(url, r"/anime/[^/]+/(\d+)/?$")[0] or self.cm.ph.getSearchGroups(badge, r"(\d+)")[0]
            seriesUrl = self._seriesUrl(url)
            if fmt in ("MOVIE", "FILM"):
                params = self._seriesParams(seriesUrl, sTitle, icon, "", badge, True)
            else:
                params = {"name": "category", "good_for_fav": True, "category": "episode", "url": url, "s_title": sTitle, "icon": icon,
                          "title": self._episodeTitle(sTitle, epNum, "%s - %s" % (sTitle, badge) if badge else sTitle),
                          "season": self._seasonNum(sTitle), "ep_num": epNum, "desc": badge,
                          "meta_type": "tv", "meta_title": self._metaTitle(sTitle), "meta_year": ""}
            if params["url"] in seen:
                continue
            seen.add(params["url"])
            self.addVideo(params)
        # admin-ajax answers one page of cards without a page count: First page / Next page only
        addPagingItems(self, cItem, page, cnt >= self.LATEST_LIMIT)

    def listGenres(self, cItem):
        printDBG("AnimeOdcinkiPL.listGenres")
        for slug, title in self.GENRES:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_cards", "title": title, "url": self.getFullUrl("gatunki/%s/" % slug)})
            self.addDir(params)

    def listSeasonYears(self, cItem):
        printDBG("AnimeOdcinkiPL.listSeasonYears")
        for year in range(time.localtime()[0], 2004, -1):
            params = dict(cItem)
            params.update({"good_for_fav": False, "category": "seasons", "title": str(year), "f_year": year})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("AnimeOdcinkiPL.listSeasons")
        year = cItem.get("f_year", 0)
        now = time.localtime()
        labels = {"jesien": _("Autumn"), "lato": _("Summer"), "wiosna": _("Spring"), "zima": _("Winter")}
        for slug, month in self.SEASONS:
            if year == now[0] and month > now[1]:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_cards", "title": "%s %s" % (labels[slug], year), "url": self.getFullUrl("sezon/%s-%s/" % (slug, year))})
            self.addDir(params)

    def listCards(self, cItem):
        # genre / season pages (anime-card-h) and search results (anime-card), paged by wp-pagenavi
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or re.sub(r"strona/\d+/?$", "", cItem["url"])
        url = baseUrl if page <= 1 else "%sstrona/%d/" % (baseUrl, page)
        printDBG("AnimeOdcinkiPL.listCards [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        pager = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "wp-pagenavi"), ("</div", ">"), False)[1]
        hasNext = "nextpostslink" in pager
        lastPage = self.cm.ph.getSearchGroups(pager, r"class=.pages.>[^<]*?\d+\s+\S+\s+(\d+)")[0]
        lastPage = max([int(n) for n in re.findall(r"/strona/(\d+)/", pager)] + [int(lastPage) if lastPage else 0, page])
        seen = set()
        for item in re.split(r'<article\s+class="anime-card', data)[1:]:
            item = item.split("</article>")[0]
            url = self.cm.ph.getSearchGroups(item, r'href="(https?://[^"]+/anime/[^"/]+/)"')[0]
            if not url or url in seen:
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<h2", ">"), ("</h2", ">"), False)[1])
            icon = self._icon(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            year = self.cm.ph.getSearchGroups(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "meta-date"), ("</div", ">"), False)[1], r"(\d{4})")[0]
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "desc-scroll"), ("</div", ">"), False)[1])
            score = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "meta-score"), ("</div", ">"), False)[1])
            if score:
                score = "%s: %s/10" % (_("Rating"), score)
            else:
                score = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "anime-card-rating"), ("</div", ">"), False)[1])
            head = " | ".join([x for x in ("%s: %s" % (_("Year"), year) if year else "", score) if x])
            desc = "%s[/br]%s" % (head, desc) if head and desc else (head or desc)
            self.addDir(self._seriesParams(url, title, icon, year, desc))
        listItem = dict(cItem)
        listItem.update({"category": "list_cards", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext and bool(seen), lastPage, baseUrl + "strona/{page}/")

    ###################################################
    # series page
    ###################################################
    def _getSeries(self, url):
        # parsed series page (cached per session); None on error, {"login": True} behind the login wall
        url = self._seriesUrl(url)
        if url in self.seriesCache:
            return self.seriesCache[url]
        sts, data = self.getPage(url)
        if not sts:
            return None
        if "vod-hero-title-edge" not in data:
            if "cv-wrapper" in data or "noindex, nofollow, noarchive" in data:
                ret = {"login": True}
                self.seriesCache[url] = ret
                return ret
            return None
        ret = {"login": False, "url": url}
        ret["title"] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<h1", ">", "vod-hero-title-edge"), ("</h1", ">"), False)[1])
        ret["alt"] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<h2", ">", "vod-hero-subtitle-edge"), ("</h2", ">"), False)[1])
        ret["icon"] = self._icon(self.cm.ph.getSearchGroups(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "vod-poster-3d"), ("</div", ">"), False)[1], r'src="([^"]+)"')[0])
        meta = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "vod-hero-meta-row"), ("</div", ">"), False)[1]
        ret["year"] = self.cm.ph.getSearchGroups(meta, r"Rok:\s*(\d{4})")[0]
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(meta, r"Czas:\s*([^<]+)")[0])
        ret["duration"] = duration
        ret["is_movie"] = bool(duration) and "×" not in duration and "min" in duration
        ret["rating"] = self.cm.ph.getSearchGroups(meta, r"([0-9.]+)/10")[0]
        ret["season_name"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(meta, r'class="vod-season-btn">(.*?)</a>')[0])
        genres = []
        heroMeta = self.cm.ph.getDataBeetwenMarkers(data, "vod-hero-meta-row", "vod-hero-actions", False)[1]
        for name in re.findall(r'href="https?://anime-odcinki\.pl/gatunki/[^"/]+/">([^<]+)</a>', heroMeta):
            name = self.cleanHtmlStr(name)
            if name and name not in genres:
                genres.append(name)
        ret["genres"] = ", ".join(genres)
        desc = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "vod-desc-text"), ("<!--", ">"), False)[1]
        ret["desc"] = self.cleanHtmlStr(desc.replace("</p>", "[/br]")).replace("[/br]", "\n").strip()
        episodes = []
        for attrs, body in re.findall(r'<div\s+class="vod-ep-item vod-ep-element"([^>]*)>(.*?)</div>', data, re.S):
            token = self.cm.ph.getSearchGroups(attrs, r'data-url="([^"]+)"')[0]
            try:
                epUrl = ensure_str(a2b_base64(token)).strip()
            except Exception:
                continue
            if not self.cm.isValidUrl(epUrl):
                continue
            num = self.cm.ph.getSearchGroups(attrs, r'data-num="([^"]+)"')[0]
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="vod-ep-name"[^>]*>(.*?)</span>')[0])
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="vod-ep-num"[^>]*>(.*?)</span>')[0])
            episodes.append({"url": epUrl, "num": num, "name": name, "label": label})

        def _order(ep):
            try:
                return float(ep["num"])
            except Exception:
                return 0.0
        episodes.sort(key=_order)
        ret["episodes"] = episodes
        self.seriesCache[url] = ret
        return ret

    def listEpisodes(self, cItem):
        printDBG("AnimeOdcinkiPL.listEpisodes [%s]" % cItem.get("url", ""))
        series = self._getSeries(cItem["url"])
        if series is None:
            return
        if series.get("login"):
            SetIPTVPlayerLastHostError(_("anime-odcinki.pl shows this title only to logged-in users."))
            return
        sTitle = series["title"] or cItem.get("s_title", "") or cItem.get("title", "")
        icon = series["icon"] or cItem.get("icon", "")
        year = series["year"] or cItem.get("meta_year", "")
        episodes = series["episodes"]
        if not episodes:
            SetIPTVPlayerLastHostError(_("No episodes available yet."))
            return
        if series["is_movie"] and len(episodes) == 1:
            self.addVideo(self._seriesParams(series["url"], sTitle, icon, year, series["desc"], True))
            return
        season = self._seasonNum(sTitle)
        for ep in episodes:
            raw = ep["name"] or ("%s - %s" % (sTitle, ep["label"]))
            params = {"name": "category", "good_for_fav": True, "category": "episode", "url": ep["url"], "s_title": sTitle, "icon": icon,
                      "title": self._episodeTitle(sTitle, ep["num"], raw), "season": season, "ep_num": ep["num"],
                      "desc": series["desc"], "meta_type": "tv", "meta_title": self._metaTitle(sTitle), "meta_year": year}
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AnimeOdcinkiPL.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_cards", "url": self.getFullUrl("szukaj/%s/" % urllib_quote(searchPattern.strip(), safe=""))})
        self.listCards(cItem)

    ###################################################
    # links
    ###################################################
    def _getEpisodeLinks(self, url, prefix=""):
        urltab = []
        sts, data = self.getPage(url)
        if not sts:
            return urltab
        for attrs, body in re.findall(r'<div\s+class="vod-tab[^"]*"([^>]*)>(.*?)</div>', data, re.S):
            token = self.cm.ph.getSearchGroups(attrs, r'data-token="([^"]+)"')[0]
            try:
                link = ensure_str(a2b_base64(token[::-1])).strip()
            except Exception:
                printExc()
                continue
            link = "https:" + link if link.startswith("//") else link
            if not self.cm.isValidUrl(link):
                continue
            name = re.sub(r"^Serwer\s+", "", self.cleanHtmlStr(body))
            if prefix:
                name = "%s - %s" % (prefix, name)
            if re.search(r"\.(?:mp4|m3u8)(?:$|\?)", link):
                urltab.append({"name": name, "url": strwithmeta(link, {"User-Agent": self.HEADER["User-Agent"], "Referer": self.MAIN_URL}), "need_resolve": 0})
                continue
            link = strwithmeta(link, {"Referer": self.MAIN_URL})
            if self.up.checkHostSupport(link) != 1:
                printDBG("AnimeOdcinkiPL: hoster not supported by urlparser [%s]" % link)
                continue
            urltab.append({"name": name, "url": link, "need_resolve": 1})
        return urltab

    def getLinksForVideo(self, cItem):
        printDBG("AnimeOdcinkiPL.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        sidecarTxt = cItem.get("desc", "")
        urltab = []
        if self._seriesUrl(url) == url:
            # a film is listed with its title page - the player sits on the page of its (first) episode
            series = self._getSeries(url)
            if series is None:
                return []
            if series.get("login"):
                SetIPTVPlayerLastHostError(_("anime-odcinki.pl shows this title only to logged-in users."))
                return []
            sidecarTxt = series["desc"] or sidecarTxt
            episodes = series["episodes"][:self.MAX_FILM_PARTS]
            for ep in episodes:
                urltab.extend(self._getEpisodeLinks(ep["url"], ep["label"] if len(episodes) > 1 else ""))
        else:
            urltab = self._getEpisodeLinks(url)
        if not urltab:
            SetIPTVPlayerLastHostError(_("This video is only on hosters E2iPlayer cannot play."))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("AnimeOdcinkiPL.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("AnimeOdcinkiPL.getArticleContent [%s]" % cItem.get("url", ""))
        otherInfo = {}
        title = cItem.get("s_title", "") or cItem.get("title", "")
        text = ""
        icon = cItem.get("icon", "")
        series = None
        if "/anime/" in cItem.get("url", ""):
            series = self._getSeries(cItem["url"])
        if series and not series.get("login"):
            title = series["title"] or title
            text = series["desc"]
            icon = series["icon"] or icon
            for key, field in (("alternate_title", "alt"), ("year", "year"), ("genres", "genres"), ("duration", "duration"), ("broadcast", "season_name")):
                if series[field]:
                    otherInfo[key] = series[field]
            if series["rating"]:
                otherInfo["rating"] = "%s/10" % series["rating"]
            if series["episodes"] and not series["is_movie"]:
                otherInfo["episodes"] = str(len(series["episodes"]))
        meta = {}
        if cItem.get("meta_title"):
            year = cItem.get("meta_year", "") or (series or {}).get("year", "")
            mediaType = "movie" if (series or {}).get("is_movie") else cItem.get("meta_type", "tv")
            try:
                meta = getMeta(mediaType, cItem["meta_title"], year)
            except Exception:
                printExc()
        sameAs = {"genre": "genres"}
        for key, value in meta.get("info", {}).items():
            if key not in otherInfo and sameAs.get(key) not in otherInfo:
                otherInfo[key] = value
        if not text:
            text = meta.get("plot", "") or cItem.get("desc", "").replace("[/br]", "\n")
        if not icon:
            icon = meta.get("poster", "")
        if cItem.get("category") == "episode":
            title = cItem.get("title", title)
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        # the root item is {"name": None}; rows (and favourites saved before rows carried "name") open by category
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("AnimeOdcinkiPL.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "latest":
            self.listLatest(self.currItem)
        elif category == "db_letters":
            self.listDbLetters(self.currItem)
        elif category == "db_items":
            self.listDbItems(self.currItem)
        elif category == "genres":
            self.listGenres(self.currItem)
        elif category == "season_years":
            self.listSeasonYears(self.currItem)
        elif category == "seasons":
            self.listSeasons(self.currItem)
        elif category == "list_cards":
            self.listCards(self.currItem)
        elif category == "series":
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
        CHostBase.__init__(self, AnimeOdcinkiPL(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("animeodcinki")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("series", "movie", "episode")
